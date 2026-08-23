# Changelog

## [0.2.0] - 2026-08-23

First release with a graphical interface.

### Added
- Web application: single self-contained HTML file, runs offline, no upload
- Sign-in with session persistence held locally on the user's machine
- Explicit cleaning step. Loading a file segments and displays it; no output
  is produced until requested
- DOCX, EPUB and HTML import, standard library only
- Region hierarchy: acts contain scenes, books contain chapters
- Table-of-contents detection by entry density and repetition
- Transcriber and producer credit detection
- Parity harness comparing the Python and JavaScript implementations

### Fixed
- Heading matching was case-sensitive, so `Chapter 1` failed where `CHAPTER 1`
  worked. This silently affected the majority of real books
- Contents detection used a count ratio that sat exactly on its boundary for
  drama, where the contents mirrors the body one for one. Replaced with entry
  density
- Transcriber note patterns matched only the straight apostrophe, while
  Gutenberg uses the typographic form almost universally
- JavaScript tokeniser split non-ASCII words because `\w` is ASCII-only there.
  Found by the parity check as a nine-token drift on De Profundis
- The tail of a region split by an interruption inherited the original's title

## [0.1.0] - 2026-07-29

Initial prototype: segmentation engine, variant outputs, preprocessing log,
command-line interface.
