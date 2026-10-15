"""Self-contained HTML and offline WeasyPrint PDF rendering."""

import base64
import html
import os
import re

from .errors import ReportError
from .model import image_bytes, math_image


def data_uri(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def inline_html(children, model, for_pdf=False) -> str:
    parts = []
    for child in children:
        kind = child.type
        if kind == "text":
            text = html.escape(child.content)
            text = re.sub(
                r"\[@((?:sec|fig|tbl):[a-zA-Z][a-zA-Z0-9_-]*)\]",
                lambda m: (
                    f'<a href="#{model["refs"][m[1]]["anchor"]}">{html.escape(model["refs"][m[1]]["label"])}</a>'
                ),
                text,
            )
            text = re.sub(r"^\[([ xX])\]\s", lambda m: "☑ " if m[1].lower() == "x" else "☐ ", text)
            parts.append(text)
        elif kind == "code_inline":
            parts.append(f"<code>{html.escape(child.content)}</code>")
        elif kind in {"strong_open", "strong_close", "em_open", "em_close", "s_open", "s_close"}:
            tag = {"strong": "strong", "em": "em", "s": "del"}[kind.split("_")[0]]
            parts.append(f"</{tag}>" if kind.endswith("close") else f"<{tag}>")
        elif kind == "link_open":
            target = child.attrGet("href") or ""
            if target.startswith(("javascript:", "data:", "file:")):
                raise ReportError("unsafe_link", "Active or file link schemes are not supported", 2)
            parts.append(f'<a href="{html.escape(target, quote=True)}">')
        elif kind == "link_close":
            parts.append("</a>")
        elif kind in {"softbreak", "hardbreak"}:
            parts.append("<br>" if kind == "hardbreak" else "\n")
        elif kind == "image":
            parts.append(
                f'<img class="inline-image" src="{data_uri(image_bytes(child.attrGet("src"), model["source"]))}" alt="{html.escape(child.content, quote=True)}">'
            )
        elif kind == "math_inline":
            parts.append(
                f'<img class="math-inline" src="{data_uri(math_image(child.content))}" alt="{html.escape(child.content, quote=True)}">'
            )
        elif kind == "footnote_ref":
            number = child.meta["id"] + 1
            if for_pdf:
                text = inline_html(model["footnotes"].get(child.meta["id"], []), model, False)
                parts.append(f'<span class="footnote">{text}</span>')
            else:
                parts.append(f'<sup><a href="#fn-{number}" id="fnref-{number}">{number}</a></sup>')
        else:
            parts.append(html.escape(child.content))
    return "".join(parts)


def render_html(model: dict, for_pdf: bool = False) -> str:
    meta, style = model["metadata"], model["style"]

    def esc(value):
        return html.escape(str(value), quote=True)

    title = esc(meta["title"])
    parts = [
        f'<section class="cover {"separate" if meta.get("cover", style["cover"]) else "inline"}"><h1 class="title">{title}</h1>'
    ]
    for key, css in [
        ("subtitle", "subtitle"),
        ("author", "author"),
        ("date", "date"),
        ("classification", "classification"),
    ]:
        if meta.get(key):
            parts.append(f'<p class="{css}">{esc(meta[key])}</p>')
    parts.append("</section>")
    if meta.get("toc", style["toc"]):
        parts.append('<nav class="toc"><h2>Contents</h2><ol>')
        for block in model["blocks"]:
            if block["type"] == "heading" and block["level"] <= 3:
                parts.append(
                    f'<li class="level-{block["level"]}"><a href="#{block["anchor"]}">{esc(block["number"] + block["text"])}</a></li>'
                )
        parts.append("</ol></nav>")
    ordered_count = 0
    for block in model["blocks"]:
        kind = block["type"]
        if kind == "heading":
            level = min(block["level"] + 1, 6)
            parts.append(
                f'<h{level} class="heading-{block["level"]}" id="{block["anchor"]}">{esc(block["number"])}{inline_html(block["children"], model, for_pdf)}</h{level}>'
            )
        elif kind == "paragraph":
            text = inline_html(block["children"], model, for_pdf)
            if block["list_depth"]:
                ordered_count = ordered_count + 1 if block["list_kind"] == "ordered" else 0
                prefix = f"{ordered_count}. " if ordered_count else "• "
                if text.startswith(("☐", "☑")):
                    prefix = ""
                parts.append(
                    f'<p class="list-item depth-{min(block["list_depth"], 6)}">{prefix}{text}</p>'
                )
            else:
                ordered_count = 0
                parts.append(
                    f"<blockquote>{text}</blockquote>" if block["quote"] else f"<p>{text}</p>"
                )
        elif kind == "table":
            parts.append(
                f'<div class="table-caption" id="{block["anchor"]}">{esc(block["label"] + (" — " + block["caption"] if block["caption"] else ""))}</div><table><thead>'
            )
            for index, row in enumerate(block["rows"]):
                if index == 1:
                    parts.append("</thead><tbody>")
                tag = "th" if index == 0 else "td"
                parts.append(
                    "<tr>"
                    + "".join(f"<{tag}>{inline_html(cell, model, for_pdf)}</{tag}>" for cell in row)
                    + "</tr>"
                )
            parts.append("</tbody></table>" if len(block["rows"]) > 1 else "</thead></table>")
        elif kind == "figure":
            parts.append(
                f'<figure id="{block["anchor"]}"><img src="{data_uri(block["data"])}" alt="{esc(block["caption"])}"><figcaption>{esc(block["label"] + " — " + block["caption"])}</figcaption></figure>'
            )
        elif kind == "math":
            parts.append(
                f'<p class="equation"><img src="{data_uri(block["data"])}" alt="{esc(block["latex"])}"></p>'
            )
        elif kind == "code":
            parts.append(f"<pre><code>{html.escape(block['text'])}</code></pre>")
    if model["footnotes"] and not for_pdf:
        parts.append('<section class="footnotes"><h2>Notes</h2><ol>')
        for ident, children in model["footnotes"].items():
            parts.append(
                f'<li id="fn-{ident + 1}">{inline_html(children, model)} <a href="#fnref-{ident + 1}">↩</a></li>'
            )
        parts.append("</ol></section>")
    family = f'"{style["font_latin"]}", "{style["font_body_cjk"]}", "Songti SC", serif'
    heading_family = f'"{style["font_heading_cjk"]}", "Heiti SC", sans-serif'
    css = f"""
@page {{ size:A4; margin:{style["margin_top"]}mm {style["margin_right"]}mm {style["margin_bottom"]}mm {style["margin_left"]}mm;
@top-center {{content: string(reporttitle); font: 9pt sans-serif; color:#555}}
@bottom-center {{content:"Page " counter(page) " of " counter(pages); font:9pt sans-serif; color:#555}}
@footnote {{border-top:.5pt solid #aaa; padding-top:4pt}}
}}
@page:first {{ @top-center {{content:none}} }}
* {{box-sizing:border-box}} body {{font-family:{family}; font-size:{style["body_size"]}pt; line-height:{style["line_spacing"]}; color:#161616; max-width:850px; margin:32px auto; padding:0 28px}}
h1,h2,h3,h4,h5,h6 {{font-family:{heading_family}; color:#000; line-height:1.25; break-after:avoid; margin:1.1em 0 .5em}}
.title {{font-size:{style["title_size"]}pt; string-set:reporttitle content(); color:#000}}
.cover.separate {{min-height:200mm; display:flex; flex-direction:column; justify-content:center; break-after:page}}
.cover.inline {{margin-bottom:24pt}} .subtitle {{font-size:15pt}} .author,.date,.classification {{margin:3pt 0}}
p {{margin:0 0 9pt}} .toc {{break-after:page}} .toc ol {{list-style:none;padding:0}} .toc li {{margin:7pt 0}}
.toc .level-2 {{margin-left:14pt}} .toc .level-3 {{margin-left:28pt}}
a {{color:#215b70;text-decoration:none}} table {{border-collapse:collapse; width:100%; margin:6pt 0 14pt; border-top:1.2pt solid #555; border-bottom:1.2pt solid #555; font-size:95%}}
thead {{display:table-header-group}} th {{border-bottom:.7pt solid #777;text-align:left; background:#f1f4f5}}
th,td {{padding:6pt 8pt; overflow-wrap:anywhere}} tr {{break-inside:avoid}} .table-caption {{break-after:avoid; font-size:90%; margin-top:10pt}}
figure {{margin:14pt 0;break-inside:avoid}} img {{max-width:100%;height:auto}} figure img {{display:block;max-height:60mm;width:auto;margin:auto}} figcaption {{font-size:90%;text-align:center;margin-top:5pt}}
pre {{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f4f5;padding:10pt;font-size:9pt;line-height:1.3}} code {{font-family:monospace}} blockquote {{margin:10pt 18pt;font-style:italic}}
.list-item {{margin-bottom:4pt;margin-left:14pt}} .depth-2 {{margin-left:28pt}} .depth-3 {{margin-left:42pt}}
.math-inline {{height:1.35em;vertical-align:middle}} .equation {{text-align:center; margin:12pt 0}} .equation img {{max-height:65pt}}
.footnote {{float:footnote;font-size:9pt}} ::footnote-call {{font-size:75%;vertical-align:super}} .footnotes {{font-size:90%}}
@media print {{body {{margin:0;padding:0;max-width:none}} .toc a::after {{content:leader('.') target-counter(attr(href), page)}}}}
@media(max-width:600px) {{body {{margin:18px auto;padding:0 16px}} .cover.separate {{min-height:70vh}} table {{font-size:85%}} th,td {{padding:5px}}}}
"""
    for level, size in enumerate(style["heading_sizes"], 1):
        css += f".heading-{level}{{font-size:{size}pt}}"
    return (
        f'<!doctype html><html lang="{esc(meta.get("language", "en"))}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{css}</style></head><body>'
        + "\n".join(parts)
        + "</body></html>"
    )


def write_pdf(model: dict, path) -> None:
    if os.environ.get("MDR_LIBRARY_DIR"):
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = os.environ["MDR_LIBRARY_DIR"]
    try:
        from weasyprint import HTML
        from weasyprint.urls import URLFetcher
    except (ImportError, OSError) as exc:
        raise ReportError(
            "missing_dependency",
            "PDF requires the pdf extra and local Pango libraries; see README",
            3,
        ) from exc

    fetcher = URLFetcher(allowed_protocols={"data"}, allow_redirects=False, fail_on_errors=True)
    HTML(string=render_html(model, for_pdf=True), url_fetcher=fetcher).write_pdf(path)
