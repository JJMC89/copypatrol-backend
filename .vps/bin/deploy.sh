#!/usr/bin/env bash
set -euo pipefail

setup=0
webhook=
while getopts swx opt; do
    case $opt in
        s) setup=1 ;;
        w) webhook=--webhook ;;
        x) set -x ;;
        \?) echo invalid option
            exit ;;
    esac
done

ENV_FILE=/etc/copypatrol-env.sh
if [ ! -f $ENV_FILE ]; then
    echo please export enviornment variables in $ENV_FILE
    exit 1
fi

NGINX_HOME_DIR=/var/www

# git
CPB_DIR=$NGINX_HOME_DIR/copypatrol-backend
if [ -d $CPB_DIR ]; then
    git -C $CPB_DIR pull -p
else
    git clone https://github.com/JJMC89/copypatrol-backend $CPB_DIR
fi

# auto configure
if [ ! -f $NGINX_HOME_DIR/.copypatrol.ini ]; then
    ln -s $CPB_DIR/.vps/.copypatrol.ini $NGINX_HOME_DIR/.copypatrol.ini
fi

# nginx
NGINX_DIR=/etc/nginx
if ! cmp --silent $CPB_DIR/.vps/nginx/copypatrol-api $NGINX_DIR/sites-available/copypatrol-api; then
    cp $CPB_DIR/.vps/nginx/copypatrol-api $NGINX_DIR/sites-available/copypatrol-api
    if [ ! -f $NGINX_DIR/sites-enabled/copypatrol-api ]; then
        ln -s $NGINX_DIR/sites-available/copypatrol-api $NGINX_DIR/sites-enabled
    fi
    nginx -t
    systemctl restart nginx
fi

# venv
VENV_DIR=$NGINX_HOME_DIR/.venv
if [ ! -d $VENV_DIR ]; then
    VENVPYZ=/tmp/virtualenv.pyz
    curl --silent --location --output $VENVPYZ https://bootstrap.pypa.io/virtualenv/3.11/virtualenv.pyz
    python3 $VENVPYZ $VENV_DIR
fi

# (re)install application
$VENV_DIR/bin/pip install --upgrade --upgrade-strategy eager pip setuptools wheel $CPB_DIR

# setup application
if [ $setup -eq 1 ]; then
    sudo -u www-data bash -c ". $ENV_FILE && $VENV_DIR/bin/copypatrol-backend setup -log:setup.log $webhook"
fi

# systemd
cd /etc/systemd/system
cp -u $CPB_DIR/.vps/systemd/* .
systemd-analyze verify copypatrol-*
systemctl daemon-reload
for f in copypatrol-*.{service,timer}; do
    if systemctl is-enabled "$f" > /dev/null; then
        systemctl restart "$f"
    else
        systemctl enable "$f"
        systemctl start "$f"
    fi
done
