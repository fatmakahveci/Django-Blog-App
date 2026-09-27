# Local fonts

Folio uses **Inter** for interface text and **Source Serif 4** for headlines,
article text, and editorial artwork. The three Latin WOFF2 files are served
locally; page views do not contact a font provider.

Both families are distributed under the SIL Open Font License 1.1. Keep
`Inter-OFL.txt` and `Source-Serif-4-OFL.txt` with these assets. These font-specific
notices apply independently of the application license.

`sources.json` records the original download URLs, byte sizes, and SHA-256
checksums. Fonts were retrieved from Google Fonts without modification.
CSS uses variable weights from 400 through 700, with Source Serif's optical
size range from 8 through 60. Browser fallbacks cover characters outside the
bundled Latin subset.

The normal faces are preloaded; all faces use `font-display: swap` so text
remains visible while fonts load. The italic serif loads when used.
