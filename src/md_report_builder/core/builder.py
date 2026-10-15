"""Shared build orchestration with atomic output replacement."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .docx_output import write_docx
from .errors import ReportError
from .history import History
from .html_output import render_html, write_pdf
from .model import make_model
from .source import lint_source, read_source
from .styles import load_template


def build(
    input: str | Path,
    to: str = "docx",
    template: str | None = None,
    out: str | Path = "data/reports",
    *,
    data_dir: str | Path | None = None,
    timezone: str = "Asia/Shanghai",
    strict: bool = False,
    progress=None,
) -> dict:
    """Build a local Markdown file/directory; atomically replace its named output.

    No network requests are made. data_dir optionally records idempotent build history.
    """
    if to not in {"docx", "pdf", "html"}:
        raise ReportError("invalid_format", "Output must be docx, pdf or html", 2)
    if progress:
        progress("Reading Markdown and local fragments")
    source = read_source(input, timezone)
    diagnostics = lint_source(source)
    if strict and diagnostics:
        raise ReportError("lint_failed", f"Source has {len(diagnostics)} lint diagnostics", 2)
    chosen = template or source["metadata"].get("template") or "business"
    style = load_template(chosen)
    if progress:
        progress("Rendering charts and preparing report structure")
    model = make_model(source, style)
    warnings = model["warnings"] + [
        f"{d['code']} at line {d['line']}: {d['message']}" for d in diagnostics
    ]
    destination = Path(out).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    stem = Path(source["name"]).stem
    path = destination / f"{stem}.{to}"
    if progress:
        progress(f"Writing {to.upper()}")
    handle, temporary = tempfile.mkstemp(prefix=".mdr-", suffix=f".{to}", dir=destination)
    os.close(handle)
    try:
        if to == "docx":
            write_docx(model, temporary)
            if source["metadata"].get("toc", style["toc"]):
                warnings.append(
                    "DOCX contents and page fields update in Word or LibreOffice; "
                    "cached navigation is included"
                )
        elif to == "html":
            Path(temporary).write_text(render_html(model), encoding="utf-8")
        else:
            write_pdf(model, temporary)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    source_hash = hashlib.sha256(source["markdown"].encode()).hexdigest()
    record_id = hashlib.sha256(
        json.dumps(
            [source["name"], source_hash, source["metadata"], chosen, to, str(path)],
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()[:24]
    result = {
        "id": record_id,
        "input": source["name"],
        "sources": source["sources"],
        "format": to,
        "template": style["name"],
        "output": str(path),
        "sha256": content_hash,
        "source_sha256": source_hash,
        "counts": model["counts"],
        "warnings": warnings,
        "built_at": datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds"),
    }
    if data_dir is not None:
        History(data_dir, timezone).record(result)
    return result
