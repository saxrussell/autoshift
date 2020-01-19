#!/bin/bash

set -x
epochts="$(date -u +%s)"
zip -u ./awslambda/bin/autoshift_${epochts}.zip fetch.py redeem.py shift.py common.py

venv_python="$(find .venv/lib -maxdepth 1 -name "python*" | cut -d"/" -f3)"
pushd $VIRTUAL_ENV/lib/$venv_python/site-packages
zip -u -r $OLDPWD/awslambda/bin/autoshift_${epochts}.zip . \
  --exclude pip\* \
  --exclude setuptools\* \
  --exclude virtualenv\*
popd
