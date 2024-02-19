from __future__ import annotations

import argparse
import os
import subprocess  # nosec: B404
from email.message import EmailMessage
from smtplib import SMTP


def main(*args: str) -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("unit")
    parser.add_argument("host")
    parsed_args = parser.parse_args()

    status = subprocess.run(  # nosec
        [
            "systemctl",
            "--full",
            "--no-pager",
            "--output",
            "short-iso",
            "status",
            parsed_args.unit,
        ],
        stdout=subprocess.PIPE,
    ).stdout.decode()
    journal = subprocess.run(  # nosec
        [
            "journalctl",
            "--lines",
            "25",
            "--no-pager",
            "--output",
            "short-iso",
            "--unit",
            parsed_args.unit,
        ],
        stdout=subprocess.PIPE,
    ).stdout.decode()

    msg = EmailMessage()
    msg["From"] = os.environ["CPB_SYSTEMD_EMAIL_FROM"]
    msg["To"] = os.environ["CPB_SYSTEMD_EMAIL_TO"]
    msg["Subject"] = f"{parsed_args.unit}@{parsed_args.host} failed"
    msg.set_content(f"{status}\n\n\nend of journal:\n{journal}")

    with SMTP(
        os.environ["CPB_SYSTEMD_SMTP_HOST"],
        int(os.environ["CPB_SYSTEMD_SMTP_PORT"]),
    ) as smtp:
        smtp.send_message(msg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
