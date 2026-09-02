# Django Blog App

[![Last commit](https://img.shields.io/github/last-commit/fatmakahveci/Django-Blog-App)](https://github.com/fatmakahveci/Django-Blog-App/commits/main)
[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-web%20app-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE.md)

A minimal server-rendered Django blog project for practicing application structure, URL routing, views, templates, and local development.

## Highlights

- Dedicated Django project and blog application packages
- Root blog route and Django admin integration
- Server-rendered application structure
- Simple foundation for expanding posts and templates

## Technology

- Python
- Django
- SQLite
- Django Templates

## Getting Started

### Prerequisites

- Python 3.11 or newer
- pip

### Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install Django
cd my_site
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000.

## Quality Checks

```bash
cd my_site && python manage.py check
cd my_site && python manage.py test
```

## Repository Structure

- `my_site/blog_app` — application views, models, and URLs
- `my_site/my_site` — project settings and root routing
- `header.png` — repository preview image

## Project Resources

- [Changelog](CHANGELOG.md)
- [Contributing guide](.github/CONTRIBUTING.md)
- [Security policy](.github/SECURITY.md)
- [License](LICENSE.md)
