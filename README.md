[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/JJMC89/copypatrol-backend/main.svg)](https://results.pre-commit.ci/latest/github/JJMC89/copypatrol-backend/main) [![tests](https://github.com/JJMC89/copypatrol-backend/actions/workflows/tests.yaml/badge.svg?branch=main)](https://github.com/JJMC89/copypatrol-backend/actions/workflows/tests.yaml?query=branch%3Amain) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

back end bot for [CopyPatrol](https://meta.wikimedia.org/wiki/Special:MyLanguage/CopyPatrol)

## configuration

### `~/.copypatrol.ini`

#### general

- configured in the `[copypatrol]` section
- `url-ignore-list-title`: title of the wiki page with the ignore list
- `user-ignore-list-title`: title of the wiki page with the ignore list

#### sites

- each site is configured in a `[copypatrol:<domain>]` section.
- keys:
  - `enabled` (boolean): site is enabled (default: false)
  - `namespaces` (comma-separated list of namespace numbers): namesapces to monitor (default: 0)
  - `pagetriage-namespaces` (comma-separated separated list of namespace numbers): mark in [PageTriage](https://www.mediawiki.org/wiki/Special:MyLanguage/Extension:PageTriage)

#### example

```ini
[copypatrol]
url-ignore-list-title = example-url-title
user-ignore-list-title = example-user-title

[copypatrol:en.wikipedia.org]
enabled = true
namespaces = 0,2,118
pagetriage-namespaces = 0,118

[copypatrol:es.wikipedia.org]
enabled = true
namespaces = 0,2

[copypatrol:fr.wikipedia.org]
enabled = false
```

### environment variables

- `CPB_ENV`: `dev` or `prod`
- `CPB_DB_DATABASE`: database name[^dbo]
- `CPB_DB_DEFAULT_CHARACTER_SET`: database default character set[^dbo]
- `CPB_DB_DRIVERNAME`: name of the database backend (corresponds to a module in sqlalchemy/databases or a third party plug-in), e.g., `mysql+pymysql` or `sqlite`
- `CPB_DB_HOST`: database host[^dbo]
- `CPB_DB_PASSWORD`: database user password[^dbo]
- `CPB_DB_PORT`: database port number[^dbo]
- `CPB_DB_USERNAME`: database user[^dbo]
- `CPB_TCA_DOMAIN`: domain of the TCA URL
- `CPB_TCA_KEY`: TCA key
- `CPB_TCA_WEBHOOK_DOMAIN`: domain of the TCA webhook[^tcaw]
- `CPB_TCA_WEBHOOK_SIGNING_SECRET`: secret for TCA to sign the webhook payload[^tcaw]
[^dbo]: as needed depending on your database
[^tcaw]: required only when using a webhook

### pywikibot

see [user-config.py](https://www.mediawiki.org/wiki/Special:MyLanguage/Manual:Pywikibot/user-config.py)

## licensing

Wikipedia content used for tests is available under CC BY-SA. see [Wikipedia:Copyrights](https://en.wikipedia.org/wiki/Wikipedia:Copyrights) for details. see the histories of [Kommet, ihr Hirten](https://en.wikipedia.org/w/index.php?oldid=1126962296&action=history) and [Basil Lee Whitener](https://en.wikipedia.org/w/index.php?oldid=1173291523&action=history) for attribution. content may be edited to remove markup and content available in a prior revision.

everything else in this repository is available under the MIT license.
