VIRTUAL_ENV = $(PWD)/.venv

export

all:
	virtualenv -p python3 .venv
	.venv/bin/pip install -r requirements.txt
	./make_deploy_pkg.sh
