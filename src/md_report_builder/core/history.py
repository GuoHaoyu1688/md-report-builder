"""Idempotent SQLite build history with portable snapshots and backups."""

import csv
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .errors import ReportError


class History:
    def __init__(self, data_dir="data", timezone="Asia/Shanghai"):
        self.directory = Path(data_dir).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "cache.sqlite"
        self.zone = ZoneInfo(timezone)
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS builds (id TEXT PRIMARY KEY, record TEXT NOT NULL)"
            )

    def record(self, record: dict) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT OR REPLACE INTO builds VALUES (?,?)",
                (record["id"], json.dumps(record, ensure_ascii=False)),
            )

    def list(self) -> list[dict]:
        with sqlite3.connect(self.path) as db:
            return [
                json.loads(row[0]) for row in db.execute("SELECT record FROM builds ORDER BY id")
            ]

    def export(self, path, format="json", bom=True) -> dict:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        records = self.list()
        if format == "json":
            target.write_text(
                json.dumps({"schema_version": 1, "builds": records}, ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
        elif format == "csv":
            with target.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["id", "record_json"])
                writer.writerows(
                    (row["id"], json.dumps(row, ensure_ascii=False)) for row in records
                )
        else:
            raise ReportError("invalid_format", "History export supports json or csv", 2)
        return {"path": str(target.resolve()), "count": len(records)}

    def import_file(self, path) -> dict:
        target = Path(path)
        if target.suffix.lower() == ".csv":
            with target.open(encoding="utf-8-sig", newline="") as stream:
                records = [json.loads(row["record_json"]) for row in csv.DictReader(stream)]
        else:
            records = json.loads(target.read_text(encoding="utf-8-sig"))["builds"]
        for row in records:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("id"), str)
                or row.get("format") not in {"docx", "html", "pdf"}
                or not isinstance(row.get("output"), str)
            ):
                raise ReportError(
                    "invalid_snapshot", "History snapshot contains an invalid record", 2
                )
        count = 0
        with sqlite3.connect(self.path) as db:
            for row in records:
                cursor = db.execute(
                    "INSERT OR IGNORE INTO builds VALUES (?,?)",
                    (row["id"], json.dumps(row, ensure_ascii=False)),
                )
                count += cursor.rowcount
        return {"imported": count, "skipped": len(records) - count}

    def backup(self, out=None) -> dict:
        directory = Path(out) if out else self.directory / "backups"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (
            datetime.now(self.zone).strftime("md-report-builder_%Y%m%dT%H%M%S_%f") + ".zip"
        )
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = Path(temporary) / "cache.sqlite"
            with sqlite3.connect(self.path) as source, sqlite3.connect(snapshot) as dest:
                source.backup(dest)
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(snapshot, "cache.sqlite")
        return {
            "path": str(path.resolve()),
            "scope": "Build history only; source and report files are not included",
        }

    def clear(self, confirm=False) -> dict:
        if not confirm:
            raise ReportError(
                "confirmation_required", "Clearing history requires --yes or confirm=true", 2
            )
        with sqlite3.connect(self.path) as db:
            count = db.execute("DELETE FROM builds").rowcount
        return {"deleted": count}
