[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/JJMC89/copypatrol-backend/main.svg)](https://results.pre-commit.ci/latest/github/JJMC89/copypatrol-backend/main) [![tests](https://github.com/JJMC89/copypatrol-backend/actions/workflows/tests.yaml/badge.svg?branch=main)](https://github.com/JJMC89/copypatrol-backend/actions?query=workflow%3Atests+branch%3Amain) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

back end bot for [CopyPatrol](https://copypatrol.toolforge.org)

## configuration

*for pywikibot: [user-config.py](https://www.mediawiki.org/wiki/Special:MyLanguage/Manual:Pywikibot/user-config.py)*

configuration file: `~/.copypatrol.ini`

### sites

- each site is configured in a `[copypatrol:<domain>]` section.
- keys:
  - `enabled` (boolean): site is enabled
  - `namespaces` (comma-separated list of namespace numbers): namesapces to monitor
  - `pagetriage-namespaces` (comma-separated separated list of namespace numbers): mark in [PageTriage](https://www.mediawiki.org/wiki/Special:MyLanguage/Extension:PageTriage)

### Turnitin Core API

- configured in the `[tca]` section
- required keys:
  - `domain`: domain of the API URL
  - `key`: API key

### database

- will also be taken from `~/.my.cnf` and `~/replica.my.cnf`
- configured in the `[client]` section
- required keys:
  - `drivername`: name of the database backend (corresponds to a module in sqlalchemy/databases or a third party plug-in)
- optional keys (depending on the database):
  - `username`/`user`
  - `password`: database password
  - `host`: name of the host
  - `port`: port number
  - `database`: database name

### URL ignore list

- configured in the `[copypatrol]` section
- `ignore-list-title`: title of the wiki page with the ignore list

### example

```ini
[copypatrol]
ignore-list-title = example-title

[copypatrol:en.wikipedia.org]
enabled = true
namespaces = 0,2,118
pagetriage-namespaces = 0,118

[copypatrol:es.wikipedia.org]
enabled = true
namespaces = 0,2

[copypatrol:fr.wikipedia.org]
enabled = false

[client]
drivername = mysql+pymysql
username = example-db-user
password = example-db-password
database = example-db-name
host = localhost
port = 3306

[tca]
domain = example-tca-domain.com
key = example-tca-key
```

## Toolforge setup

clone this repository and setup the virtual enviornment
```
rm -fdr $HOME/backend && git clone --depth 1 https://github.com/JJMC89/copypatrol-backend $HOME/backend && toolforge-jobs run setup-venv --command $HOME/backend/.toolforge/bin/setup-venv --image python3.11 --wait
```

create database and tables
```sql
create database sNNNNN__copypatrol_p character set = utf8mb4;
```
```
toolforge-jobs run create-tables --command "$HOME/backend/.venv/bin/copypatrol-backend db --create-tables" --image python3.11 --wait
```

load jobs
```
toolforge-jobs load $HOME/backend/.toolforge/jobs.yaml
```

## licensing

Wikipedia content used for tests is available under the [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/legalcode) license. see [Wikipedia:Copyrights](https://en.wikipedia.org/wiki/Wikipedia:Copyrights) for details. see the history of [Kommet, ihr Hirten](https://en.wikipedia.org/w/index.php?oldid=1126962296&action=history) for attribution. content may be edited to remove markup and content available in a prior revision.

everything else in this repository is available under the MIT license.
