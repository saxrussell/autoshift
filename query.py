#!/usr/bin/env python
import sqlite3
import requests
from bs4 import BeautifulSoup as BSoup

from common import _L


BLPS = "blps"
BL2 = "bl2"
PC = "pc"
PS = "ps"
XBOX = "xbox"

platforms = [PC, PS, XBOX]

conn = None
c = None


class Key:
    """small class like `functools.namedtuple` but with settable attributes"""
    __slots__ = ("id", "description", "key", "game", "redeemed")
    def __init__(self, *args, **kwargs): # noqa
        for el in Key.__slots__:
            setattr(self, el, None)
        for i, el in enumerate(args):
            setattr(self, Key.__slots__[i], el)
        for k in kwargs:
            setattr(self, k, kwargs[k])
    def __str__(self): # noqa
        return "Key({})".format(
            ", ".join([str(getattr(self, k))
                       for k in Key.__slots__]))
    def __repr__(self): # noqa
        return str(self)


def open_db():
    from os import path
    global conn, c
    filepath = path.realpath(__file__)
    dirname = path.dirname(filepath)
    conn = sqlite3.connect(path.join(dirname, "keys.db"),
                           detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()

    c.execute("CREATE TABLE IF NOT EXISTS keys "
              "(id INTEGER primary key, description TEXT, "
              "platform TEXT, key TEXT, game TEXT, redeemed INTEGER)")


def close_db():
    conn.commit()
    conn.close()


def insert(desc, platform, key, game):
    """Insert Key"""
    el = c.execute("select * from keys "
                   "where platform = ? "
                   "and key = ? "
                   "and game = ?",
                   (platform, key, game))
    if el.fetchone():
        return
    print("=== inserting {} Key '{}' for '{}' ===".format(game, key, platform))
    c.execute("INSERT INTO keys(description, platform, key, game, redeemed) "
              "VAlUES (?,?,?,?,0)", (desc, platform, key, game))
    conn.commit()


def get_keys(platform, game, all_keys=False):
    """Get all (unredeemed) keys of given platform and game"""
    cmd = """
        SELECT * FROM keys
        WHERE platform=?
        AND game=?"""
    if not all_keys:
        cmd += " AND redeemed=0"
    ex = c.execute(cmd, (platform, game))

    keys = []
    for row in ex:
        keys.append(Key(row[0], row[1], row[3], row[4], row[5]))

    return keys


def get_special_keys(platform, game):
    keys = get_keys(platform, game)
    num = 0
    ret = []
    for k in keys:
        if "gold" not in k.description.lower():
            num += 1
            ret.append(k)
    return num, ret


def get_golden_keys(platform, game, all_keys=False):
    import re
    # quite general regex..
    # you never know what they write in those tables..
    g_reg = re.compile(r"^(\d+).*gold.*", re.I)
    keys = get_keys(platform, game, all_keys)
    num = 0
    ret = []
    for k in keys:
        m = g_reg.match(k.description)
        if m:
            num += int(m.group(1))
            ret.append(k)
    return num, ret


def set_redeemed(key):
    key.redeemed = 1
    c.execute("UPDATE keys SET redeemed=1 WHERE id=(?)", (key.id, ))
    conn.commit()


def parse_keys(game):
    """Get all Keys from orcz"""
    key_urls = {BL2: "http://orcz.com/Borderlands_2:_Golden_Key",
                BLPS: "http://orcz.com/Borderlands_Pre-Sequel:_Shift_Codes",
                # BL3: "http://orcz.com/Borderlands_3:_Golden_Key"
                }

    def check(key):
        """Check if key is expired (return None if so)"""
        ret = None
        span = key.find("span")
        if (not span) or (not span.get("style")) or ("black" in span["style"]):
            ret = key.text.strip()

            # must be of format ABCDE-FGHIJ-KLMNO-PQRST
            if ret.count("-") != 4:
                return None
            spl = ret.split("-")
            spl = [len(el) == 5 for el in spl]
            if not all(spl):
                return None

        return ret

    r = requests.get(key_urls[game])
    soup = BSoup(r.text, "lxml")
    table = soup.find("table")
    rows = table.find_all("tr")[1:]
    for row in rows:
        cols = row.find_all("td")
        desc = cols[1].text.strip()
        the_keys = [None, None, None]
        for i in range(4, 7):
            try:
                the_keys[i - 4] = check(cols[i])
            except: # noqa
                pass

        for i in range(3):
            if the_keys[i]:
                insert(desc, platforms[i], the_keys[i], game)
