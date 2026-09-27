# Django Blog App

[![Last commit](https://img.shields.io/github/last-commit/fatmakahveci/Django-Blog-App)](https://github.com/fatmakahveci/Django-Blog-App/commits/main)
[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-web%20app-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-See%20LICENSE-blue.svg)](LICENSE)

Folio is an English-language Django publication with an editorial interface,
scheduled posts, moderated discussions, and a personal reading experience.

## Demo

![Folio demo: articles, reading list, article detail, and dark theme](docs/assets/demo.gif)

## Highlights

- Responsive article pages with persistent light/dark themes
- Editorial admin with drafts, scheduled publication, categories, and tags
- Search, sorting, pagination, featured articles, and author pages
- Moderated comments, saved reading lists, RSS, and search-engine discovery
- Security defaults, login throttling, and regression tests

See the [20-feature guide](docs/features.md) for every feature and its entry point.

## Technology

- Python
- Django
- SQLite
- Django Templates

## Getting Started

### Prerequisites

- Python 3.12, 3.13, or 3.14
- pip

The project uses Django 6.1.1 and Django Axes, pinned in `requirements.txt`.

### Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On first setup, create a private local environment file and generate a key:

```bash
cp .env.example .env
chmod 600 .env
python -c 'import secrets; print("DJANGO_SECRET_KEY=" + secrets.token_urlsafe(64))' >> .env
```

Keep an existing `.env` and its key when updating the project. Load the file
in each new terminal before running Django commands; it is not loaded automatically:

```bash
set -a
source .env
set +a
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000.

To explore a populated publication, run `python manage.py seed_demo` after
migrating. It adds eight sample articles without overwriting existing content.
The sample author is inactive and has no usable password.

Create your own editor account with `python manage.py createsuperuser`, then
sign in at `/admin/`. Add categories/tags and create a post. Choose **Draft**
to keep it private, or **Published / scheduled** to publish it. A future
publication time keeps it private until that time (the admin uses UTC).
An active staff user also needs the relevant model permissions to edit content.

Post bodies are plain text with paragraph formatting; HTML is escaped.
Comments are pending until approved in the admin. Names and comments are public
after approval; commenter email addresses are not collected. A keyed IP digest
limits repeated submissions to three per ten minutes; raw commenter IPs are not stored.

To update an existing virtual environment after pulling dependency changes:

```bash
python -m pip install --upgrade -r requirements.txt
python -m pip check
python manage.py migrate
```

## Quality Checks

```bash
python -m pip install -r requirements-dev.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python -m pip_audit -r requirements-dev.txt
```

The suite covers publication visibility across all public surfaces, search,
pagination, ordering, taxonomy, author privacy, comment moderation/spam controls,
editor permissions, RSS/sitemaps, and query counts. Administration coverage includes
login redirects, authentication, CSRF protection, secure cookies, throttling, and logout.
Security tests also cover startup validation, HTTPS redirects, response
headers, untrusted hosts, and forged forwarding headers. Authentication tests use Django's
isolated test database and do not change the local development database.
They use a fast password hasher scoped to the authentication test class;
application password hashing retains Django's defaults. Anonymous admin-access
tests disallow database queries; article pages use the isolated test database.

To run one group with detailed output:

```bash
python manage.py test blog.tests --verbosity 2
python manage.py test tests.test_admin --verbosity 2
python manage.py test tests.test_security --verbosity 2
```

CI runs the server suite on Python 3.12, 3.13, and 3.14, checks migration and
static-file consistency, and runs browser regression checks on a fresh demo database.

### Browser checks and demo recording

These optional tools use isolated browser storage and expect the eight original
sample articles from `seed_demo`. Run them against a local demo instance:

```bash
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
python manage.py seed_demo
python manage.py runserver
```

In another terminal with the virtual environment active:

```bash
python scripts/browser_check.py
python scripts/record_demo.py
```

The browser check covers desktop/mobile layouts, keyboard search, saved articles,
theme persistence, sharing, print layout, and reading without JavaScript. It writes
screenshots to a temporary `folio-browser` directory. The recorder regenerates
`docs/assets/demo.gif` with five screens from the live app. Both commands accept
`--base-url` and `--output`. Set `CHROME_PATH` to use an existing Chrome executable
instead of Playwright's bundled Chromium.

For implementation details and operational tradeoffs, see the
[quality guide](docs/quality.md).

## Security Configuration

The default configuration is for HTTPS deployment. Startup fails when the
secret key is missing or weak, or when the host list is empty or contains a
wildcard. Provide these values through your deployment's secret/environment manager:

| Variable | Local development | Deployment |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Generated private key in `.env` | Independently generated private key, at least 50 characters |
| `DJANGO_DEBUG` | `true` | Unset or `false` |
| `DJANGO_ALLOWED_HOSTS` | Loopback hostnames | Comma-separated actual hostnames, without schemes or ports |

`.env` is excluded from version control. The former committed development key
has been removed; replace it in any existing deployment rather than retaining
it as a fallback. Key rotation invalidates existing signed sessions/tokens.

With debug disabled, the application redirects HTTP to HTTPS, marks session
and CSRF cookies as secure, and sends HSTS for one hour. TLS must be configured
on the application server or trusted reverse proxy. Forwarded protocol/host/IP
headers are not trusted by default. Behind a reverse proxy, configure trusted
TLS and client-IP handling only after ensuring that the proxy strips incoming
forwarded headers; otherwise HTTPS redirects may loop and clients may share an
IP-based login limit. See the [Django deployment checklist](https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/).

HSTS subdomain coverage and browser preloading are deliberately disabled until
TLS coverage for the actual domain is known. Only their advisory checks
(`security.W005` and `security.W021`) are silenced; all other deployment
warnings remain active. Enable these policies only after validating the
deployment's domains and the preload requirements.

Run these commands with production environment variables configured:

```bash
python manage.py check --deploy --fail-level WARNING
python manage.py migrate
python manage.py collectstatic --noinput
```

Serve only `staticfiles/` as static content, never the repository root.

After five failed login attempts for the same account **or** IP address,
further attempts return HTTP 429 for a 15-minute cool-off period. Counters
are stored in the database and successful login resets matching failures.
An operator can clear an account lock with `python manage.py axes_reset_username USERNAME`
or an IP lock with `python manage.py axes_reset_ip IP_ADDRESS`. Both may need
resetting when both limits have been reached.

CI checks production settings and audits runtime and development dependencies.

## Repository Structure

```text
Django-Blog-App/
├── .github/            # CI workflows and contribution policies
├── blog/               # Blog application, migrations, and tests
├── config/             # Django settings, root URLs, ASGI, and WSGI
├── docs/
│   └── assets/          # Documentation images
├── scripts/            # Browser checks and demo recording
├── tests/              # Project integration tests
├── manage.py           # Django management commands
├── requirements.txt    # Pinned Python dependencies
├── requirements-dev.txt # Test and security audit tooling
├── requirements-browser.txt # Optional browser and GIF tooling
├── CHANGELOG.md
├── LICENSE
└── README.md
```

Run all development commands from the repository root. SQLite uses
`db.sqlite3` in this directory; the database is excluded from version control.

### Existing Checkouts

The former `my_site/manage.py` now lives at the repository root. Update IDE
working directories and scripts accordingly. The Django settings module is
`config.settings`; server entry points are `config.wsgi:application` and
`config.asgi:application`.

If you have a local `my_site/db.sqlite3` from an older checkout, move it to
`db.sqlite3` in the repository root while the development server is stopped,
before running management commands. Do not overwrite an existing database.
The application package is now `blog`, while its Django app label remains
`blog_app` to preserve existing migration and content-type identifiers.

## Project Resources

- [Changelog](CHANGELOG.md)
- [Contributing guide](.github/CONTRIBUTING.md)
- [Security policy](.github/SECURITY.md)
- [License](LICENSE)
