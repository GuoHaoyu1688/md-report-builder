"""Validated built-in and user-supplied report templates."""

from pathlib import Path

from .errors import ReportError
from .source import yaml_load

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates"
SIZE_NAMES = {
    "初号": 42,
    "小初": 36,
    "一号": 26,
    "小一": 24,
    "二号": 22,
    "小二": 18,
    "三号": 16,
    "小三": 15,
    "四号": 14,
    "小四": 12,
    "五号": 10.5,
    "小五": 9,
}


def points(value) -> float:
    if isinstance(value, str) and value in SIZE_NAMES:
        return SIZE_NAMES[value]
    try:
        size = float(value)
    except (TypeError, ValueError) as exc:
        raise ReportError(
            "invalid_style", "Unknown font size; use points or a Chinese size name", 2
        ) from exc
    if not 6 <= size <= 72:
        raise ReportError("invalid_style", "Font sizes must be 6..72 points", 2)
    return size


def load_template(name: str) -> dict:
    folder = (
        TEMPLATE_ROOT / name
        if name in {"business", "gongwen", "tech", "weekly"}
        else Path(name).expanduser().resolve()
    )
    if not folder.is_dir() or not (folder / "style.yaml").is_file():
        raise ReportError("not_found", "Template needs a directory containing style.yaml", 3)
    style = yaml_load((folder / "style.yaml").read_text(encoding="utf-8"))
    if not isinstance(style, dict):
        raise ReportError("invalid_style", "Style must be a mapping", 2)
    defaults = yaml_load((TEMPLATE_ROOT / "business/style.yaml").read_text(encoding="utf-8"))
    defaults.update(style)
    style = defaults
    for key in ("cover", "toc"):
        if type(style[key]) is not bool:
            raise ReportError("invalid_style", f"{key} must be a boolean", 2)
    style["body_size"] = points(style["body_size"])
    style["title_size"] = points(style["title_size"])
    style["heading_sizes"] = [points(value) for value in style["heading_sizes"]]
    if len(style["heading_sizes"]) != 6:
        raise ReportError("invalid_style", "heading_sizes needs six values", 2)
    if style["numbering"] not in {"technical", "gongwen", "none"}:
        raise ReportError("invalid_style", "Unknown heading numbering style", 2)
    for key in ("margin_top", "margin_bottom", "margin_left", "margin_right"):
        if not isinstance(style[key], (float, int)) or not 10 <= style[key] <= 45:
            raise ReportError("invalid_style", "Margins must be 10..45 mm", 2)
    if not isinstance(style["line_spacing"], (int, float)) or not 1 <= style["line_spacing"] <= 2.5:
        raise ReportError("invalid_style", "line_spacing must be 1..2.5", 2)
    for key in ("font_body_cjk", "font_heading_cjk", "font_latin", "name"):
        if not isinstance(style[key], str) or any(c in style[key] for c in '<>{};"\\\n'):
            raise ReportError("invalid_style", "Invalid style name or font family", 2)
    style["reference"] = (
        folder / "reference.docx" if (folder / "reference.docx").is_file() else None
    )
    return style


def list_templates() -> list[dict]:
    return [
        {
            "name": folder.name,
            "description": yaml_load((folder / "style.yaml").read_text())["description"],
        }
        for folder in sorted(TEMPLATE_ROOT.iterdir())
        if folder.is_dir()
    ]
