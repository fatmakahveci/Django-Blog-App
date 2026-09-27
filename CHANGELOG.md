# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
where applicable.

## [Unreleased]

### Security

- Bound reaction, poll, and comment submissions with atomic database quotas
  that survive cookie changes, forged forwarding headers, and concurrent requests.
- Hide category and tag metadata until an attached article is published.
- Enforce a same-origin Content Security Policy and verify injected inline
  script blocking in the browser regression checks.
- Removed the committed development secret and require a private environment
  key. Disable debug by default and reject missing or wildcard deployment hosts.
- Enable HTTPS redirection, secure cookies, HSTS, and explicit browser security
  headers for deployment. Exclude local environment files and collected static
  output from version control.
- Add database-backed account and IP login limits with Django Axes, with a
  15-minute cool-off after five failures.
- Add security regression tests, dependency auditing, and deployment checks
  to CI.

### Changed

- Introduced locally served Inter and Source Serif 4 typography, with font
  license notices, loading fallbacks, and a navy/ivory/slate palette shared by
  light and dark themes. Refined reading sizes and small-text contrast.
- Refined the editorial UI with a contrasting featured story, sticky navigation,
  framed cards, consistent SVG controls, clearer search/reset states, and layouts
  for narrow phones and tablets. Updated article bylines and the demo recording.
- Upgraded Django from 5.2.17 to 6.1.1 and raised the minimum Python version
  to 3.12. Added weekly pip dependency updates and a CI compatibility check.
- Reduced authentication test overhead with a test-scoped password hasher,
  avoided session writes in assertions, and made the CSRF rejection test
  independent of the database.
- Consolidated the existing GPL v3 and Apache 2.0 texts into `LICENSE` and
  updated README links and the license badge.

- Moved Django management commands to the repository root and renamed the
  project configuration package to `config`.
- Renamed the application package to `blog`, retaining its existing Django
  app label for database compatibility.
- Moved the local SQLite database to the repository root, where the existing
  ignore rules exclude it from version control.
- Updated setup instructions and CI commands for the new layout.

### Added

- Added ten reader features: discovery by reading length, weekly trending,
  followed topics/personal feed, ordered reading collections, reactions, polls,
  reading history/resume, reading preferences/focus, local read-aloud, and random discovery.
- Added editorial collection and poll management, repeat-safe demo content,
  publication-aware navigation, browser identity protection, and regression checks.
- Added a one-command local launcher with environment setup, dependency installation,
  migrations, optional demo content, and guided editor account creation.
- Added a visible editor sign-in link, branded publishing dashboard, writing
  guidance, and permission-protected previews for saved drafts and scheduled articles.
- Added regression coverage for first-run setup, safe environment loading,
  editorial previews, and the complete save/preview/publish workflow.
- Added English content and URLs throughout, distinct sample articles, keyboard
  search, print layouts, social metadata, and custom recovery pages.
- Paginated approved comments, indexed discussion/rate-limit lookups, and
  disabled caching of personal reading lists and comment submissions.
- Added reproducible browser checks and GIF recording scripts, plus a Python
  3.12–3.14 CI matrix and browser regression job.
- Added the Folio publication experience: article CRUD, draft/scheduled
  publishing, category/tag/author pages, search, pagination, sorting, featured
  posts, moderated comments, reading estimates, and related articles.
- Added a local reading list, persistent light/dark themes, reading progress,
  link sharing, RSS, sitemap/robots metadata, and responsive article layouts.
- Added a non-destructive sample-content command and feature regression tests.
- Added home-page and administration integration tests covering routing,
  authentication, access control, CSRF protection, and logout.
- Added an initial changelog to track future project changes.

### Removed

- Removed the unused header image and superseded application scaffold.

<!--
When preparing a release, move relevant entries from Unreleased into a dated
version section. Use Added, Changed, Deprecated, Removed, Fixed, and Security
headings as appropriate.
-->
