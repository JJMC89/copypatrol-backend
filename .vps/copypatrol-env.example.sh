#!/usr/bin/env bash
# shellcheck disable=SC2034
set -aeuo pipefail

CPB_ENV=dev

CPB_DB_DATABASE=copypatrol_dev
CPB_DB_DEFAULT_CHARACTER_SET=utf8mb4
CPB_DB_DRIVERNAME=mysql+pymysql
CPB_DB_HOST=localhost
CPB_DB_PASSWORD=userpassword
CPB_DB_PORT=3306
CPB_DB_USERNAME=notroot

CPB_SYSTEMD_EMAIL_FROM=noreply@example.com
CPB_SYSTEMD_EMAIL_TO=you@example.com
CPB_SYSTEMD_SMTP_HOST=localhost
CPB_SYSTEMD_SMTP_PORT=587

CPB_TCA_DOMAIN=example.example.com
CPB_TCA_KEY=abcdefghijklmnopqrstuvqxyz1234567890
CPB_TCA_WEBHOOK_DOMAIN=copypatrol-api.example.com
CPB_TCA_WEBHOOK_SIGNING_SECRET=your-ascii-string-here
