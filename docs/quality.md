# Quality and maintenance

Folio uses server-rendered Django pages with small, local CSS and JavaScript
assets. Browsing, searching, reading, and commenting do not require JavaScript.
The thirty publication and reader features are described in [features.md](features.md).

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
- Followed topics and reading history accept at most twenty IDs. Discovery
  filters by a cached word count maintained by normal article saves; the
  migration backfills existing articles in batches. Bulk updates to article
  bodies must update `word_count` as well.
- Trending aggregates the last seven days of reactions and approved comments
  separately, avoiding a join that multiplies both histories. Collection pages
  contain at most twelve stories; unpublished entries never enter their counts
  or next/previous links.
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

Article, personal-feed, history, reading-list, and feedback responses send
no-store/private cache directives. Browser-local IDs are preferences, not an access-control mechanism;
the server always filters them to public posts.

The sample-content command is repeatable and preserves existing edits. Its
author is inactive, has no usable password, and cannot log into the admin.
Local database content is excluded from Git. Back up the database before
schema changes and load environment variables before management commands.

`python3 start.py` provides a repeatable local setup: an isolated virtual
environment, a private generated signing key, migrations, optional sample
articles, and interactive editor creation. It preserves existing keys and data,
rejects non-local settings, and never creates a default login. Direct management
commands and WSGI/ASGI retain explicit deployment environment configuration.

The editor dashboard links writing, article management, and comment moderation.
Saved drafts and scheduled articles have private previews using the public
article template. Preview requires active staff access and article view/change
permissions, disables response caching and search indexing, and omits sharing,
bookmarks, and commenting. Saving a draft does not expose its public URL.

Reactions and poll votes require CSRF-protected POST requests and a public
article. A signed cookie supplies an opaque browser identity; database uniqueness
constraints prevent a repeated submission from adding another reaction or vote
for that identity. Reactions can be changed or removed, while a poll vote is final.
Closed or incomplete polls reject new votes. Poll questions and answers become
read-only in the admin once votes exist, preserving the meaning of the results.
This is a low-friction participation mechanism, not verified identity or a
fraud-resistant voting system; clearing cookies or switching browsers bypasses
the per-browser limit.

Reader controls work without accounts. Topic following and history handle
unavailable or malformed browser storage without breaking reading. History keeps
only twenty article IDs and reading percentages, and clearing it works across
tabs. Focus mode always leaves an exit control and supports Escape. Read-aloud
uses only voices marked local and English by the browser, requires an explicit
click, chunks long text, and cancels playback when leaving the page. Browsers
without suitable voices keep normal reading available. See the
[SpeechSynthesis API](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis)
and [local voice flag](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisVoice/localService).

## Repeatable checks

Follow [README](../README.md#quality-checks) for the test, audit, browser-check,
and demo-recording commands. CI defines a Python 3.12–3.14 test matrix and a
Chromium browser job. Browser tools are optional development dependencies,
separate from the application runtime. Their pinned releases are documented
by [Playwright](https://pypi.org/project/playwright/1.63.0/) and
[Pillow](https://pillow.readthedocs.io/en/stable/releasenotes/12.3.0.html).

Reader browser checks use a disposable demo database and exercise reaction and
poll submissions. Playback state, chunking, speed, and cancellation use a test
voice; no automated check claims to assess actual audio output quality. Separate
cases verify no-JavaScript feedback and graceful handling of unavailable speech
or blocked storage.

Production configuration and trusted-proxy requirements are documented in
[README](../README.md#security-configuration). Dependency audits identify known
published advisories; passing one does not establish the absence of every
possible vulnerability.
