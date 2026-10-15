"""Normalize Markdown tokens into a shared report model with numbered references."""

from __future__ import annotations

import csv
import io
import re

from PIL import Image

from .errors import ReportError
from .source import local_path, parser, yaml_load


def chinese_number(value: int) -> str:
    digits = "零一二三四五六七八九"
    if value < 10:
        return digits[value]
    if value < 100:
        tens, units = divmod(value, 10)
        return (digits[tens] if tens > 1 else "") + "十" + (digits[units] if units else "")
    return str(value)


def heading_number(counters: list[int], level: int, style: str) -> str:
    counters[level - 1] += 1
    counters[level:] = [0] * (6 - level)
    value = counters[level - 1]
    if style == "none":
        return ""
    if style == "technical":
        return ".".join(str(n) for n in counters[:level]) + " "
    return {
        1: f"{chinese_number(value)}、",
        2: f"（{chinese_number(value)}）",
        3: f"{value}.",
        4: f"（{value}）",
    }.get(level, f"{value}.")


def chart_image(content: str) -> tuple[bytes, dict]:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    spec = yaml_load(content)
    if not isinstance(spec, dict):
        rows = list(csv.reader(io.StringIO(content)))
        if len(rows) < 2 or len(rows[0]) < 2 or any(len(row) != len(rows[0]) for row in rows):
            raise ReportError(
                "invalid_chart", "CSV charts need a label column and numeric columns", 2
            )
        spec = {
            "type": "bar",
            "x": [row[0] for row in rows[1:]],
            "series": {name: [row[i] for row in rows[1:]] for i, name in enumerate(rows[0][1:], 1)},
        }
    if not isinstance(spec, dict) or spec.get("type", "bar") not in {"bar", "line", "pie"}:
        raise ReportError("invalid_chart", "Chart type must be bar, line or pie", 2)
    labels = spec.get("x", [])
    series = spec.get("series", {spec.get("label", "Value"): spec.get("y", [])})
    if (
        not isinstance(labels, list)
        or not labels
        or len(labels) > 1000
        or not isinstance(series, dict)
        or not series
        or len(series) > 12
    ):
        raise ReportError("invalid_chart", "Chart needs 1..1000 labels and at most 12 series", 2)
    try:
        values = {str(name): [float(v) for v in data] for name, data in series.items()}
    except (ValueError, TypeError) as exc:
        raise ReportError("invalid_chart", "Chart values must be numbers", 2) from exc
    import math

    if any(
        len(data) != len(labels) or not all(math.isfinite(x) for x in data)
        for data in values.values()
    ):
        raise ReportError(
            "invalid_chart", "Each chart series must match the label count with finite values", 2
        )
    fig, ax = plt.subplots(figsize=(6.5, 2.8), layout="constrained")
    colors = ["#247c82", "#d18d3b", "#546c90", "#ae6378"]
    try:
        for i, (name, data) in enumerate(values.items()):
            color = colors[i % len(colors)]
            if spec.get("type") == "pie":
                if len(values) != 1 or min(data) < 0 or sum(data) <= 0:
                    raise ReportError(
                        "invalid_chart",
                        "Pie charts need one nonnegative series with a positive total",
                        2,
                    )
                ax.pie(data, labels=labels, autopct="%1.0f%%", colors=colors)
            elif spec.get("type") == "line":
                ax.plot(labels, data, marker="o", color=color, label=name)
            else:
                width = 0.8 / len(values)
                ax.bar(
                    [x + (i - (len(values) - 1) / 2) * width for x in range(len(labels))],
                    data,
                    width,
                    color=color,
                    label=name,
                )
                ax.set_xticks(range(len(labels)), labels)
        if spec.get("type") != "pie":
            ax.spines[["right", "top"]].set_visible(False)
            ax.grid(axis="y", color="#e5e7eb", linewidth=0.7)
            ax.set_axisbelow(True)
            if len(values) > 1:
                ax.legend(frameon=False)
        buffer = io.BytesIO()
        if re.search(r"[\u3400-\u9fff]", str(spec)):
            from matplotlib import font_manager

            installed = {font.name for font in font_manager.fontManager.ttflist}
            font = next(
                (
                    name
                    for name in (
                        "Noto Sans CJK SC",
                        "Noto Sans CJK JP",
                        "Arial Unicode MS",
                        "Hiragino Sans GB",
                    )
                    if name in installed
                ),
                None,
            )
            if font is None:
                raise ReportError(
                    "missing_font", "Chinese charts require an installed Noto CJK font", 3
                )
            for text in fig.findobj(matplotlib.text.Text):
                text.set_fontfamily(font)
        fig.savefig(buffer, format="png", dpi=180, metadata={"Software": "md-report-builder"})
        return buffer.getvalue(), spec
    finally:
        plt.close(fig)


def math_image(latex: str) -> bytes:
    from matplotlib import mathtext

    buffer = io.BytesIO()
    try:
        mathtext.math_to_image(f"${latex.strip()}$", buffer, dpi=220, format="png", color="black")
    except (ValueError, RuntimeError) as exc:
        raise ReportError(
            "invalid_math", "Unsupported equation; use the documented MathText subset", 2
        ) from exc
    return buffer.getvalue()


def image_bytes(key: str, source: dict) -> bytes:
    asset = source["assets"].get(key)
    path = local_path(
        asset["value"] if asset else key, asset["base"] if asset else source["root"], source["root"]
    )
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ReportError("image_too_large", "Images must be at most 20 MiB", 2)
    try:
        with Image.open(path) as image:
            if image.width * image.height > 40_000_000:
                raise ReportError("image_too_large", "Images must be at most 40 megapixels", 2)
            image.load()
            buffer = io.BytesIO()
            image.convert("RGBA").save(buffer, format="PNG")
            return buffer.getvalue()
    except (OSError, ValueError) as exc:
        raise ReportError(
            "invalid_image", "Images must be readable PNG, JPEG, GIF or WebP", 2
        ) from exc


def label_and_id(text: str, fallback: str) -> tuple[str, str]:
    match = re.search(r"\s*\{#([a-zA-Z][a-zA-Z0-9_-]*)\}\s*$", text)
    return (text[: match.start()].strip(), match.group(1)) if match else (text, fallback)


def make_model(source: dict, style: dict) -> dict:
    md = parser()
    tokens = md.parse(source["markdown"])
    metadata = source["metadata"]
    numbering = metadata.get("numbering", style["numbering"])
    if numbering not in {"technical", "gongwen", "none"}:
        raise ReportError("invalid_numbering", "Numbering must be technical, gongwen or none", 2)
    blocks, refs, footnotes, warnings = [], {}, {}, list(source["warnings"])
    counters = [0] * 6
    figure_count = table_count = 0
    quote_depth = list_depth = 0
    list_kind = []
    pending_caption = None

    def register(kind, ident, label):
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,100}", ident):
            raise ReportError(
                "invalid_reference", "Reference IDs must be plain letters, digits, _ or -", 2
            )
        key = f"{kind}:{ident}"
        if key in refs:
            raise ReportError("duplicate_reference", f"Duplicate reference: {key}", 2)
        refs[key] = {"anchor": f"{kind}-{ident}", "label": label}
        return refs[key]["anchor"]

    def figure(data, caption, ident):
        nonlocal figure_count
        figure_count += 1
        label = ("图" if metadata.get("language") == "zh" else "Figure") + f" {figure_count}"
        return {
            "type": "figure",
            "data": data,
            "caption": caption,
            "label": label,
            "anchor": register("fig", ident, label),
            "number": figure_count,
        }

    index = 0
    while index < len(tokens):
        token = tokens[index]
        kind = token.type
        if kind == "footnote_block_open":
            current = None
            index += 1
            while index < len(tokens) and tokens[index].type != "footnote_block_close":
                item = tokens[index]
                if item.type == "footnote_open":
                    current = item.meta["id"]
                    footnotes[current] = []
                elif item.type == "inline" and current is not None:
                    footnotes[current].extend(item.children or [])
                index += 1
        elif kind == "heading_open":
            level = int(token.tag[1:])
            text, ident = label_and_id(tokens[index + 1].content, f"section-{len(refs) + 1}")
            number = heading_number(counters, level, numbering)
            anchor = register("sec", ident, (number + text).strip())
            blocks.append(
                {
                    "type": "heading",
                    "level": level,
                    "text": text,
                    "number": number,
                    "children": md.parseInline(text)[0].children,
                    "anchor": anchor,
                }
            )
            index += 2
        elif kind == "table_open":
            rows, row = [], []
            index += 1
            while tokens[index].type != "table_close":
                item = tokens[index]
                if item.type == "tr_open":
                    row = []
                elif item.type == "inline":
                    row.append(item.children or [])
                elif item.type == "tr_close":
                    rows.append(row)
                index += 1
            table_count += 1
            caption, ident = pending_caption or ("", f"table-{table_count}")
            pending_caption = None
            label = ("表" if metadata.get("language") == "zh" else "Table") + f" {table_count}"
            blocks.append(
                {
                    "type": "table",
                    "rows": rows,
                    "caption": caption,
                    "label": label,
                    "anchor": register("tbl", ident, label),
                    "number": table_count,
                }
            )
        elif kind == "paragraph_open":
            inline = tokens[index + 1]
            children = inline.children or []
            if (
                inline.content.startswith("Table: ")
                and index + 3 < len(tokens)
                and tokens[index + 3].type == "table_open"
            ):
                pending_caption = label_and_id(inline.content[7:], f"table-{table_count + 1}")
            elif len(children) == 1 and children[0].type == "image":
                caption, ident = label_and_id(children[0].content, f"figure-{figure_count + 1}")
                blocks.append(
                    figure(image_bytes(children[0].attrGet("src"), source), caption, ident)
                )
            else:
                blocks.append(
                    {
                        "type": "paragraph",
                        "children": children,
                        "quote": quote_depth,
                        "list_depth": list_depth,
                        "list_kind": list_kind[-1] if list_kind else "",
                    }
                )
            index += 2
        elif kind == "fence":
            language = token.info.strip().split()[0] if token.info.strip() else ""
            if language == "chart":
                data, spec = chart_image(token.content)
                blocks.append(
                    figure(
                        data,
                        str(spec.get("title", "Chart")),
                        str(spec.get("id", f"figure-{figure_count + 1}")),
                    )
                )
            else:
                if language == "mermaid":
                    warnings.append("Mermaid renderer is unavailable; source code is preserved")
                blocks.append(
                    {"type": "code", "text": token.content.rstrip(), "language": language}
                )
        elif kind == "code_block":
            blocks.append({"type": "code", "text": token.content.rstrip(), "language": ""})
        elif kind == "math_block":
            blocks.append(
                {"type": "math", "data": math_image(token.content), "latex": token.content}
            )
        elif kind == "blockquote_open":
            quote_depth += 1
        elif kind == "blockquote_close":
            quote_depth -= 1
        elif kind in {"bullet_list_open", "ordered_list_open"}:
            list_depth += 1
            list_kind.append("ordered" if kind.startswith("ordered") else "bullet")
        elif kind in {"bullet_list_close", "ordered_list_close"}:
            list_depth -= 1
            list_kind.pop()
        elif kind == "hr":
            blocks.append(
                {"type": "paragraph", "children": [], "quote": 0, "list_depth": 0, "list_kind": ""}
            )
        index += 1
    model = {
        "metadata": metadata,
        "blocks": blocks,
        "refs": refs,
        "footnotes": footnotes,
        "warnings": warnings,
        "source": source,
        "style": style,
        "counts": {
            "tables": table_count,
            "figures": figure_count,
            "headings": sum(b["type"] == "heading" for b in blocks),
        },
    }
    for token in tokens:
        for child in token.children or []:
            if child.type == "text":
                for ref in re.findall(
                    r"\[@((?:sec|fig|tbl):[a-zA-Z][a-zA-Z0-9_-]*)\]", child.content
                ):
                    if ref not in refs:
                        raise ReportError("unknown_reference", f"Unknown cross-reference: {ref}", 2)
    return model
