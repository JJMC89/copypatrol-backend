## vps setup

### install nginx

```shell-script
sudo apt update && sudo apt --yes install nginx && sudo usermod --append --groups systemd-journal www-data
```

### configuration

export application and systemd enviornment variables in `/etc/copypatrol-env.sh` ([example](copypatrol-env.example.sh))

systemd enviornment variables:
- `CPB_SYSTEMD_EMAIL_FROM`: from email address
- `CPB_SYSTEMD_EMAIL_TO`: to email address
- `CPB_SYSTEMD_SMTP_HOST`: SMTP host
- `CPB_SYSTEMD_SMTP_PORT`: SMTP host port number

### deploy

after configuring the application, including pywikibot, for the nginx user, run [bin/deploy.sh](bin/deploy.sh) as root
- `-s`: run application setup (create database)
- `-w`: also setup the webhook (after deleting any existing)
- `-x`: `set -x`
