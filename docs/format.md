# Report source and template format

## Input and expansion

Input is a UTF-8 `.md` file or a directory of top-level `.md` files sorted by
filename. Front matter uses safe YAML with unique string keys. Known string
fields are title, subtitle, author, date, classification, template, numbering,
and language. `cover` and `toc` are booleans. Scalar extra fields can be used as
`{{variable}}`. Unknown variables remain visible with warnings. An ISO YAML date
is converted to its ISO string. No commands, expressions, or Jinja code execute.

Includes use a complete line `!include relative/file.md` outside code fences.
They resolve against the containing file. Maximum depth is 20 and cumulative
source size is 5 MiB. Include cycles, external symlinks, URL resources, and paths
outside the initial source directory are rejected. A directory's fragments should
live in a subdirectory to avoid including them both as top-level files and includes.

Images use local relative inline syntax `![caption](path.png)`. PNG/JPEG/GIF/WebP
files are decoded and re-encoded to PNG; the first frame is used for animations.
Limits are 20 MiB and 40 megapixels. HTML and PDF contain embedded data URIs.
External hyperlinks are preserved as links but never fetched by a build. Raw
HTML is escaped, and PDF's resource fetcher only allows the `data` scheme.

## Structure and references

Headings may end with `{#id}`. Standalone images use this suffix in their alt text.
A table can have a preceding paragraph `Table: Caption {#id}`. Chart YAML accepts
an `id` field. IDs begin with a letter and contain at most 101 ASCII letters,
digits, underscores, and hyphens. Duplicate IDs within a reference kind fail.

Reference syntax is `[@sec:id]`, `[@fig:id]`, or `[@tbl:id]`. Unknown targets fail
before an output is replaced. Forward references work. Heading numbers are
recomputed from the Markdown hierarchy; a skipped heading level is a lint
finding. Decimal numbering has up to six levels. Gongwen uses its four standard
patterns, then decimal prefixes for deeper levels. Numbering can be `none`.

DOCX figure/table numbers are `SEQ` fields; cross-references are `REF` fields with
cached results and bookmarks. DOCX contents is a `TOC` field with cached section
links; page counts use `PAGE` and `NUMPAGES`. Some viewers need a field refresh.
Heading prefixes themselves are literal generated text, so edit the Markdown and
rebuild to renumber. PDF contents page numbers are computed by WeasyPrint.

Footnotes use `[^label]` and `[^label]: text`. DOCX has a true `word/footnotes.xml`
part and corresponding body references, not footer imitations. Its note text is
flattened to plain text. PDF uses page footnotes; HTML uses linked endnotes.

## Charts and mathematics

Chart YAML has `type` (bar, line or pie), `x` (labels), and `y` (one series) or
`series` (mapping from names to arrays). Optional `title` is the caption and
`id` is the cross-reference target. Series must be finite numeric arrays of the
same length as x, with at most 1,000 labels and 12 series. Pie charts require one
nonnegative series with positive total. YAML is never evaluated as Python.

CSV chart fences use their first row as column headers. The first column supplies
labels and subsequent columns supply numeric series. CSV charts default to bar.
Chart numbers are visual data; the tool does not calculate financial amounts.

`$...$` and `$$...$$` use Matplotlib's MathText subset. Fractions, roots, sums,
Greek symbols, sub/superscripts and common operators work. Full TeX macros,
packages, environments and editable OMML are not supported. Equations and charts
are embedded PNGs with alt text. Unsupported equations fail visibly.

## Templates

A template directory has `style.yaml` and optionally `reference.docx`. Missing
settings inherit `business` defaults. Copy a bundled template from
`src/md_report_builder/templates/` to customize it.

| Key | Meaning and bounds |
| --- | --- |
| `name`, `description` | Template identity and purpose |
| `font_body_cjk` | East Asian body family, default Noto Serif CJK SC |
| `font_heading_cjk` | East Asian heading family, default Noto Sans CJK SC |
| `font_latin` | Latin DOCX font and HTML first family, default Times New Roman |
| `body_size`, `title_size` | Points from 6 to 72, or a Chinese size name |
| `heading_sizes` | Six point values or size names |
| `line_spacing` | Multiplier from 1 to 2.5 |
| `margin_top/bottom/left/right` | Millimeters from 10 to 45 |
| `numbering` | technical, gongwen, or none |
| `cover`, `toc` | Enable separate cover and contents |

Named sizes include `初号` 42, `小初` 36, `一号` 26, `小一` 24, `二号` 22,
`小二` 18, `三号` 16, `小三` 15, `四号` 14, `小四` 12, `五号` 10.5, `小五` 9.
A reference supplies Word styles/section configuration; its body is removed.
Report margins, font settings, header/footer and cover are generated consistently.
This is not a pixel-exact cloning tool for arbitrary reference layouts.

## Output and persistence

A build writes a temporary file beside the target and atomically replaces
`<source-stem>.<format>` after rendering succeeds. Two files with the same basename
and output directory target the same output; use separate output directories.
There is no automatic source mutation, report deletion, or network upload.

History records ID, source name/hash, included filenames, output path/hash, counts,
format, template name, warnings and timezone-aware build timestamp. It contains
no Markdown text or binary assets. Snapshot JSON is `{schema_version:1, builds:[]}`;
CSV is `id,record_json` with UTF-8 BOM. Imports validate all records before an
atomic transaction and skip existing IDs. Backups contain `cache.sqlite` only.

## Primary implementation references

- [markdown-it-py token and plugin usage](https://markdown-it-py.readthedocs.io/en/latest/using.html)
- [python-docx sections and headers](https://python-docx.readthedocs.io/en/stable/api/section.html)
- [WeasyPrint 70 URLFetcher and protocol restrictions](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html#weasyprint.urls.URLFetcher)
- [Matplotlib MathText syntax](https://matplotlib.org/stable/users/explain/text/mathtext.html)
