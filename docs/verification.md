# Verification record

Version 0.1.0 was verified locally with Python 3.12, using fictional example data.

- `ruff check .` and `ruff format --check .`: pass.
- `MDR_LIBRARY_DIR=/opt/homebrew/lib pytest -q --cov=md_report_builder`: 29 passed,
  95% statement coverage. Linux CI installs Pango and Noto CJK fonts and runs Python
  3.11 and 3.12; the macOS library override is unnecessary there.
- Tests generate DOCX, PDF and HTML for all four templates and inspect actual
  output structures and source-derived table values, figures, headings, footnotes,
  cross-references, contents, page numbers and exported history.
- Actual MCP stdio initialization, tool listing, lint, template listing and HTML
  build succeeded. The SDK schemas are in `mcp-tools.json`.
- Built a wheel and source distribution; an extracted wheel generated DOCX and
  included all four templates independently of the source checkout.
- Rendered all four DOCX templates with an isolated bundled LibreOffice profile.
  Inspected every page: business 5, tech 5, weekly 3, gongwen 6. The gongwen check
  used locally downloaded official Noto Sans/Serif CJK SC fonts through a temporary
  fontconfig file. Without an installed CJK font, a viewer can show missing glyphs.
- Inspected all five pages of the final PDF, including chart captions, page
  footnotes, tables and mathematical notation. A separate Chinese PDF and chart
  rendered readable CJK text. The preview image comes from the final PDF.
- Opened the standalone HTML in Chrome at desktop and mobile widths, verified
  embedded images and tables, and checked that the page has no horizontal overflow.

These are local checks, not a claim that a remote CI workflow has run. Word field
refresh behavior and exact pagination depend on the user's fonts and viewer.
Math uses a rendered MathText subset, not full TeX or editable Word equations.
