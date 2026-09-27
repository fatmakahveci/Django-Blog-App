# Security Policy

## Supported Versions

Security updates are provided for the latest version on the default branch.
Older releases and unmaintained branches may not receive security fixes.

## Deployment and Local Development

The application requires a private `DJANGO_SECRET_KEY` and explicit deployment
hosts. `DJANGO_DEBUG=true` enables local HTTP development; leave it unset or
false in deployment. See the repository [security configuration](../README.md#security-configuration)
for HTTPS, proxy handling, login lockouts, and key rotation.

Before deployment, run `python manage.py check --deploy --fail-level WARNING`
with the production environment and `python -m pip_audit -r requirements-dev.txt`.
Never commit `.env` files, database copies, or deployment credentials.

## Reporting a Vulnerability

Please do not disclose security vulnerabilities in public issues, discussions,
or pull requests.

Report a vulnerability through this repository's
[private vulnerability reporting](https://github.com/fatmakahveci/Django-Blog-App/security/advisories/new).
If that option is unavailable, contact the repository owner through the
[GitHub profile](https://github.com/fatmakahveci) to arrange a private reporting
channel.

Include the affected component and version, reproduction steps, potential
impact, and any suggested mitigation. Reports will be reviewed as promptly as
possible, and coordinated disclosure is appreciated.
