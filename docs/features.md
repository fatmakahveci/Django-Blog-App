# Folio: 20 features

All features run locally in the Django application. Start with the setup in
[README](../README.md), migrate, and optionally run `python manage.py seed_demo`.

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

1. Run `python manage.py createsuperuser` and sign in at `/admin/`.
2. Add categories and tags, then create a post with its author and cover style.
3. Review the text in the editor and save it as a draft. Drafts have no public
   preview URL; switch status to published when the content is ready.
4. Select a future UTC timestamp to schedule publication, or use the current
   time for immediate publication.
5. Review pending comments and choose **Approve selected comments** or
   **Hide selected comments** as appropriate.

The decorative cover artwork is rendered locally in CSS. Article and comment
HTML is escaped; this release uses plain-text writing rather than
accepting arbitrary HTML or uploads.

## Browser behavior

Reading and server-side search work without JavaScript. Saving articles, theme
preferences, copying links, and the reading indicator use JavaScript. Saved
articles and theme choices are local to the browser and are not synced between
devices. Deleting browser storage clears the reading list. Unpublished/deleted
articles are excluded even if their IDs remain in local storage.

## Verification

The Django test suite covers the server features and security boundaries.
Browser verification covers search and pagination, adding/removing saved
articles, saved-theme persistence, copying URLs, reading progress, mobile
overflow, and reading without JavaScript.

See [quality.md](quality.md) for performance boundaries, keyboard navigation,
print layouts, error recovery, and repeatable verification commands.
