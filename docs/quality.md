# Quality and maintenance

Folio uses server-rendered Django pages with small, local CSS and JavaScript
assets. Browsing, searching, reading, and commenting do not require JavaScript.
The core twenty features are described in [features.md](features.md).

## Performance

- Listings fetch six cards at a time. Author/category joins and tag prefetching
  keep query counts independent of the number of displayed cards; a regression
  test checks this behavior.
- Approved comments load twenty at a time in stable chronological order.
  A composite index supports post, approval, and ordering lookups. Pending
  comments never contribute to the public list or count.
- Submission throttling checks whether a third recent comment exists, instead
  of counting an entire history. A digest/time index supports that lookup.
- Related suggestions are capped at three; RSS is capped at twenty entries;
  reading lists accept at most one hundred IDs.
- Cover illustrations use CSS. Font files are served locally with swap loading
  and normal-face preloads. Page views need no external font provider,
  analytics scripts, or cover-image downloads.

These are bounded-work improvements, not a claim of a measured tenfold speedup.
SQLite and substring search are appropriate for this small publication. Profile
with representative traffic and data before choosing a production database,
full-text search, or shared caching. Public visibility depends on the current
publication time; indiscriminate page caching can delay scheduled articles.

## Reading and accessibility

The interface, routes, messages, admin labels, and demo stories are English.
Source Serif 4 supplies editorial headlines and article text; Inter supplies
interface labels and controls. A navy, ivory, slate, and brass palette is defined
with shared semantic tokens, including matching dark-theme and cover colors.
Font sources and license notices live in `blog/static/blog/fonts/`.
Semantic landmarks, form labels, a skip link, visible focus indicators, live
status messages, and reduced-motion styles support accessible navigation.
Press `/` to focus search and Escape to leave it; shortcuts do not interrupt
typing in other fields. Print styles remove controls and discussions and use
a light, text-focused article layout.

Sticky navigation keeps saved articles and theme controls within reach. Search
results include a reset link that preserves the current category and sort order.
Save buttons expose the article title and pressed state, retain their icon when
toggled, and are also available on the featured story. Cards use one, two, or
three columns to maintain readable widths on phones, tablets, and desktops.

Browser checks exercise desktop and mobile layouts, keyboard controls, local
reading lists, theme persistence, sharing, print styles, and no-JavaScript
reading. These checks do not replace a complete assistive-technology audit.

## Reliability and security

Publication visibility is shared by listings, details, authors, feeds, and
sitemaps. Regression tests cover drafts and scheduled posts across these
surfaces, user permissions, escaping, CSRF, and login/submission throttling.
Comments require editorial approval. Rate limits discourage automated abuse;
they do not replace proxy-level traffic controls under high concurrent load.

The 404 page links readers back to the journal. The 500 page needs no database
queries, authentication context, or application scripts to render. Django uses
these production error pages with `DEBUG=False`.

Reading-list responses and comment submissions send no-store/private cache
directives. Browser-local IDs are preferences, not an access-control mechanism;
the server always filters them to public posts.

The sample-content command is repeatable and preserves existing edits. Its
author is inactive, has no usable password, and cannot log into the admin.
Local database content is excluded from Git. Back up the database before
schema changes and load environment variables before management commands.

## Repeatable checks

Follow [README](../README.md#quality-checks) for the test, audit, browser-check,
and demo-recording commands. CI defines a Python 3.12–3.14 test matrix and a
Chromium browser job. Browser tools are optional development dependencies,
separate from the application runtime. Their pinned releases are documented
by [Playwright](https://pypi.org/project/playwright/1.63.0/) and
[Pillow](https://pillow.readthedocs.io/en/stable/releasenotes/12.3.0.html).

Production configuration and trusted-proxy requirements are documented in
[README](../README.md#security-configuration). Dependency audits identify known
published advisories; passing one does not establish the absence of every
possible vulnerability.
