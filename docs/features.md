# Folio: reader and editorial features

Start with `python3 start.py --demo` and follow the setup in [README](../README.md).
The publication includes the original twenty features and ten additions for
discovery, participation, and return visits. Open `/discover/` to explore them.

## Ten reader additions

| # | Feature | Where and how to use it |
| --- | --- | --- |
| 21 | Discovery hub | `/discover/` brings together topics, collections, and search with reading-length filters: 3 minutes or less, 4–7 minutes, and 8+ minutes. |
| 22 | Weekly trending | `/trending/` ranks public stories by reactions and approved comments created in the last seven days. Each response counts once; poll votes are not part of this score. Empty activity produces an honest empty state. |
| 23 | Follow topics and a personal feed | Select **Follow** on Discover or a category page, then open **For you**. Up to 20 followed topic IDs stay in this browser. Unfollow at any time. |
| 24 | Curated reading collections | `/collections/` contains editorial reading paths. Stories appear in the editor's chosen order, with previous/next links on article pages. Only public collections with published stories are listed. |
| 25 | Article reactions | Choose **Useful**, **Insightful**, or **Inspiring** beneath a story. Each browser has one reaction per article; choosing again updates that reaction, and **Remove reaction** clears it. |
| 26 | Reader polls | Vote on an article's question and see the actual vote counts and percentages. Each browser gets one final vote per poll. Editors can close a poll while retaining results. |
| 27 | Reading history and resume | **Continue reading** keeps the 20 most recent public articles you opened and your furthest reading position. Resume a partial read, read a finished story again, or clear the history. |
| 28 | Reading controls | Choose standard, large, or extra-large text. **Focus mode** removes surrounding navigation, artwork, and discussions; the visible **Exit focus mode** button or Escape restores them. Preferences persist in this browser. |
| 29 | Read aloud | **Listen to article** uses an available local English voice, with pause, resume, stop, and speed controls. The app explains when a compatible voice/browser is unavailable. Playback begins only on request and stops when the page closes. |
| 30 | Surprise me | Discover's **Surprise me** link opens a randomly selected published story. An empty publication returns to Discover. |

## Original publication features

| # | Feature | Where and how to use it |
| --- | --- | --- |
| 1 | Responsive article discovery | `/` displays article cards, metadata, and mobile layouts. Empty publications have a useful empty state. |
| 2 | Article detail and stable links | Open a card to read its full text at `/posts/<slug>/`. Editing a title preserves its URL. |
| 3 | Editorial management | `/admin/` supports creating, editing, and deleting articles. Editors need model permissions; superusers have full access. |
| 4 | Drafts and scheduled publication | Set a post's status and UTC publication time. Draft/future posts stay out of listings, detail pages, feeds, and sitemaps. No background worker is required. |
| 5 | Categories | Assign a category in the admin and browse its dedicated page from the navigation or article metadata. |
| 6 | Tags | Assign multiple tags and follow their links to browse related topics. |
| 7 | Text search | Search titles, excerpts, and article bodies. Searches stay within the current category, tag, author, or reading list. |
| 8 | Pagination | Browse six cards per page; search and sorting selections are retained. |
| 9 | Sort order | Choose newest, oldest, or most discussed. Only approved comments affect discussion counts. |
| 10 | Featured articles | Mark a post as featured in the admin. The newest eligible featured article leads the homepage without appearing twice. |
| 11 | Author pages | Follow an author's name to see their published articles. Private account email addresses are never displayed. |
| 12 | Moderated comments | Leave a comment on an article. Editors approve/hide comments in bulk; CSRF, validation, a honeypot, and submission limits protect the form. Approved discussions are paginated twenty comments at a time. |
| 13 | Estimated reading time | Cards and articles show a reading-time estimate based on 200 words per minute, rounded up. |
| 14 | Related articles | Article pages suggest up to three published articles sharing a category or tag. |
| 15 | Personal reading list | Use **Save** and **Reading list**. Up to 100 public post IDs are stored in this browser; no account is needed. |
| 16 | Light/dark theme | The header toggle remembers the theme locally and initially follows the system preference. |
| 17 | Reading progress | A progress indicator follows the article body as you scroll; updates use animation frames and a passive listener. |
| 18 | RSS subscription | Add `/rss/` to a feed reader for the latest 20 published articles. No email or external messaging service is used. |
| 19 | Search-engine discovery | `/sitemap.xml`, `/robots.txt`, article descriptions, canonical links, and social sharing metadata describe public content. Search and reading-list pages request no indexing. |
| 20 | Link sharing | **Copy link** copies the article's canonical URL and confirms success. The clipboard requires a secure context (HTTPS or localhost). |

## Editorial workflow

1. Run `python3 start.py --create-editor --setup-only` and sign in at `/admin/`.
2. Add categories and tags, then create a post with its author and cover style.
3. Save a draft, then select **Preview saved article**. Preview requires staff
   access and article permissions. Switch status to published when ready.
4. Select a future UTC timestamp to schedule publication, or use the current
   time for immediate publication.
5. Review pending comments and choose **Approve selected comments** or
   **Hide selected comments** as appropriate.

To make a collection, open **Publication → Collections**, add a name and
description, select its posts and positions, and enable **Is public**. Drafts
inside a collection remain private. Tied positions use the order entries were added.

To create a poll, open **Publication → Polls**, choose its article, write a
question, and add two to four distinct answers. Once voting starts, the question,
article, and answers become read-only in the editor; **Is open** remains editable.
The demo command adds two example collections and one poll without creating
reactions or votes or overwriting existing editorial changes.

The decorative cover artwork is rendered locally in CSS. Article and comment
HTML is escaped; this release uses plain-text writing rather than
accepting arbitrary HTML or uploads.

## Browser behavior

Reading and server-side search work without JavaScript. Saving articles, theme
preferences, copying links, and the reading indicator use JavaScript. Saved
articles and theme choices are local to the browser and are not synced between
devices. Deleting browser storage clears the reading list. Unpublished/deleted
articles are excluded even if their IDs remain in local storage.

Followed topics, reading history, and reading preferences also stay in local
storage. History stores article IDs and progress, not article text. Clearing
history in one tab prevents other open article tabs from immediately restoring
that history. Reactions and polls work without JavaScript and use a signed,
HTTP-only browser cookie lasting up to a year. The server stores only a keyed
digest of its random identifier. Browser limits are not verified person counts;
clearing cookies or using another browser creates a separate identity.

## Verification

The Django test suite covers the server features and security boundaries.
Browser verification covers search and pagination, adding/removing saved
articles, saved-theme persistence, copying URLs, reading progress, mobile
overflow, and reading without JavaScript.

`scripts/reader_check.py` checks all ten additions against a disposable seeded
instance, including real reaction/vote form submissions, mobile layouts, blocked
storage, and unavailable speech support. Speech controls are checked with a
deterministic test voice because CI has no audio device; this does not measure
the sound quality of a reader's installed voice.

See [quality.md](quality.md) for performance boundaries, keyboard navigation,
print layouts, error recovery, and repeatable verification commands.
