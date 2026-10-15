"""Read bounded local Markdown, expand fragments and validate source structure."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin

from .errors import ReportError

MAX_SOURCE = 5 * 1024 * 1024


def parser() -> MarkdownIt:
    return MarkdownIt("default", {"html": False}).use(footnote_plugin).use(dollarmath_plugin)


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ReportError("invalid_yaml", "YAML keys must be unique strings", 2)
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def yaml_load(value: str):
    try:
        return yaml.load(value, Loader=UniqueLoader)
    except yaml.YAMLError as exc:
        raise ReportError("invalid_yaml", "Invalid YAML syntax", 2) from exc


def front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    closing = re.search(r"(?m)^---\s*$", text[4:])
    if not closing:
        raise ReportError("invalid_front_matter", "Front matter needs a closing ---", 2)
    metadata = yaml_load(text[4 : closing.start() + 4]) or {}
    if not isinstance(metadata, dict):
        raise ReportError("invalid_front_matter", "Front matter must be a mapping", 2)
    for key in (
        "title",
        "subtitle",
        "author",
        "date",
        "classification",
        "template",
        "numbering",
        "language",
    ):
        if key in metadata:
            if isinstance(metadata[key], date):
                metadata[key] = metadata[key].isoformat()
            if metadata[key] is None:
                metadata[key] = ""
            if not isinstance(metadata[key], str):
                raise ReportError("invalid_front_matter", f"{key} must be a string", 2)
    for key in ("cover", "toc"):
        if key in metadata and type(metadata[key]) is not bool:
            raise ReportError("invalid_front_matter", f"{key} must be a boolean", 2)
    return metadata, text[closing.end() + 4 :].lstrip("\n")


def local_path(value: str, base: Path, root: Path) -> Path:
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) or value.startswith("//"):
        raise ReportError("network_disabled", "Only local relative resources are supported", 2)
    path = (base / value).resolve()
    if not path.is_relative_to(root):
        raise ReportError(
            "path_escape", "Included resources must stay inside the source directory", 2
        )
    if not path.is_file():
        raise ReportError("not_found", f"Resource not found: {value}", 3)
    return path


def read_source(input_path: str | Path, timezone: str = "Asia/Shanghai") -> dict:
    source = Path(input_path).expanduser().resolve()
    if not source.exists():
        raise ReportError("not_found", "Markdown input does not exist", 3)
    root = source if source.is_dir() else source.parent
    files = sorted(source.glob("*.md")) if source.is_dir() else [source]
    if any(not path.resolve().is_relative_to(root) for path in files):
        raise ReportError("path_escape", "Source directory contains an external symlink", 2)
    if not files or any(p.suffix.lower() != ".md" for p in files):
        raise ReportError(
            "invalid_input", "Provide a .md file or directory containing .md files", 2
        )
    byte_count = 0
    assets = {}
    metadata = {}
    included = []

    def expand(path: Path, ancestors: tuple[Path, ...] = ()) -> str:
        nonlocal byte_count
        if path in ancestors or len(ancestors) >= 20:
            raise ReportError("include_cycle", "Include cycle or depth limit reached", 2)
        byte_count += path.stat().st_size
        if byte_count > MAX_SOURCE:
            raise ReportError("input_too_large", "Expanded source exceeds 5 MiB", 2)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            raise ReportError("invalid_encoding", "Markdown input must be UTF-8", 2) from exc
        meta, text = front_matter(text)
        if not ancestors:
            for key, value in meta.items():
                if key not in metadata:
                    metadata[key] = value
        included.append(path.relative_to(root).as_posix())
        lines = []
        fence = None
        for line in text.splitlines():
            marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
            if marker:
                value = marker.group(1)
                if fence is None:
                    fence = value
                elif value[0] == fence[0] and len(value) >= len(fence):
                    fence = None
                lines.append(line)
                continue
            include = re.fullmatch(r"\s*!include\s+(.+?)\s*", line)
            if include and fence is None:
                child = local_path(include.group(1), path.parent, root)
                if child.suffix.lower() != ".md":
                    raise ReportError("invalid_include", "Included files must be Markdown", 2)
                lines.append(expand(child, (*ancestors, path)))
                continue
            if fence is None:
                # Normalize local image paths across included files without exposing them in output.
                def replace_image(match):
                    target = match.group(2)
                    key = f"asset-{len(assets) + 1}"
                    assets[key] = {"value": target, "base": path.parent}
                    return f"![{match.group(1)}]({key})"

                line = re.sub(r"!\[([^\]]*)\]\(([^\s)]+)\)", replace_image, line)
            lines.append(line)
        return "\n".join(lines)

    markdown = "\n\n".join(expand(path) for path in files)
    metadata.setdefault("title", source.stem if source.is_file() else source.name)
    metadata.setdefault("author", "")
    metadata.setdefault("date", datetime.now(ZoneInfo(timezone)).date().isoformat())
    warnings = []

    def variable(match):
        name = match.group(1)
        if name not in metadata or not isinstance(metadata[name], (str, int, float)):
            warnings.append(f"Unknown variable retained: {name}")
            return match.group(0)
        return str(metadata[name])

    markdown = re.sub(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}", variable, markdown)
    return {
        "name": source.name,
        "root": root,
        "markdown": markdown,
        "metadata": metadata,
        "assets": assets,
        "sources": sorted(set(included)),
        "warnings": warnings,
    }


def lint_source(source: dict) -> list[dict]:
    diagnostics = []
    tokens = parser().parse(source["markdown"])
    level = 0
    for token in tokens:
        line = (token.map or [0])[0] + 1
        if token.type == "heading_open":
            current = int(token.tag[1:])
            if current > level + 1:
                diagnostics.append(
                    {
                        "code": "heading_jump",
                        "line": line,
                        "message": f"Heading jumps from level {level} to {current}",
                    }
                )
            level = current
        for child in token.children or []:
            if child.type == "link_open" and not child.attrGet("href"):
                diagnostics.append(
                    {"code": "empty_link", "line": line, "message": "Empty link target"}
                )
            if child.type == "image":
                key = child.attrGet("src")
                asset = source["assets"].get(key)
                try:
                    local_path(
                        asset["value"] if asset else key,
                        asset["base"] if asset else source["root"],
                        source["root"],
                    )
                except ReportError as exc:
                    diagnostics.append(
                        {"code": "missing_image", "line": line, "message": exc.message}
                    )
    # markdown-it deliberately repairs uneven rows; inspect their source before normalization.
    lines = source["markdown"].splitlines()
    table_lines = {
        index
        for token in tokens
        if token.type == "table_open" and token.map
        for index in range(*token.map)
    }
    for index, line in enumerate(lines):
        if (
            index in table_lines
            and index
            and re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*", line)
        ):

            def cells(value):
                return re.split(r"(?<!\\)\|", value.strip().strip("|"))

            count = len(cells(lines[index - 1]))
            row = index + 1
            while row < len(lines) and "|" in lines[row] and lines[row].strip():
                if len(cells(lines[row])) != count:
                    diagnostics.append(
                        {
                            "code": "table_columns",
                            "line": row + 1,
                            "message": "Table row has a different column count",
                        }
                    )
                row += 1
    return diagnostics


def lint_markdown(path: str | Path, timezone: str = "Asia/Shanghai") -> dict:
    source = read_source(path, timezone)
    diagnostics = lint_source(source)
    return {"valid": not diagnostics, "diagnostics": diagnostics, "sources": source["sources"]}
