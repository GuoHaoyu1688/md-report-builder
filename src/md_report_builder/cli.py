"""Noninteractive JSON-first command line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

from . import __version__
from .core.builder import build
from .core.errors import ReportError, failure, success
from .core.history import History
from .core.source import lint_markdown
from .core.styles import list_templates


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ReportError("invalid_arguments", message, 2)


def parser() -> Parser:
    root = Parser(prog="mdr", description="Offline Markdown reports in DOCX, PDF and HTML")
    root.add_argument("--data-dir")
    root.add_argument("--config")
    root.add_argument("--json", action="store_true", help="Output one JSON object (the default)")
    root.add_argument("--quiet", action="store_true")
    root.add_argument("--progress", action="store_true")
    root.add_argument("--version", action="store_true")
    commands = root.add_subparsers(dest="command")
    command = commands.add_parser("build", help="Build a report; replaces the same output file")
    command.add_argument("input")
    command.add_argument("--to", choices=["docx", "pdf", "html"], default="docx")
    command.add_argument("--template")
    command.add_argument("--out")
    command.add_argument("--strict", action="store_true")
    command = commands.add_parser("lint")
    command.add_argument("input")
    commands.add_parser("templates")
    commands.add_parser("history")
    command = commands.add_parser("clear-history")
    command.add_argument("--yes", action="store_true")
    command = commands.add_parser("export")
    command.add_argument("--format", choices=["json", "csv"], default="json")
    command.add_argument("--out", required=True)
    command.add_argument("--no-bom", action="store_true")
    command = commands.add_parser("import")
    command.add_argument("path")
    command = commands.add_parser("backup")
    command.add_argument("--out")
    commands.add_parser("mcp")
    return root


def global_first(argv):
    global_args, rest = [], []
    index = 0
    while index < len(argv):
        item = argv[index]
        if item in {"--data-dir", "--config"}:
            if index + 1 >= len(argv):
                raise ReportError("invalid_arguments", f"{item} needs a value", 2)
            global_args.extend(argv[index : index + 2])
            index += 2
        elif item.split("=")[0] in {"--data-dir", "--config"} or item in {
            "--json",
            "--quiet",
            "--version",
            "--progress",
        }:
            global_args.append(item)
            index += 1
        else:
            rest.append(item)
            index += 1
    return [*global_args, *rest]


def main(argv=None) -> int:
    try:
        args = parser().parse_args(global_first(list(sys.argv[1:] if argv is None else argv)))
        if args.version:
            result = success({"version": __version__})
        else:
            if not args.command:
                raise ReportError("invalid_arguments", "Choose a subcommand; see mdr --help", 2)
            config = (
                tomllib.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
            )
            data_dir = (
                args.data_dir or os.environ.get("MDR_DATA_DIR") or config.get("data_dir", "./data")
            )
            timezone = config.get("timezone", "Asia/Shanghai")
            if args.command == "mcp":
                from .mcp_server import build_server

                build_server(data_dir, timezone).run(transport="stdio")
                return 0
            if args.command == "build":
                progress = (
                    (lambda message: print(message, file=sys.stderr))
                    if args.progress and not args.quiet
                    else None
                )
                value = build(
                    args.input,
                    args.to,
                    args.template,
                    args.out or Path(data_dir) / "reports",
                    data_dir=data_dir,
                    timezone=timezone,
                    strict=args.strict,
                    progress=progress,
                )
                result = success(value, value["warnings"])
            elif args.command == "lint":
                value = lint_markdown(args.input, timezone)
                result = success(value)
                print(json.dumps(result, ensure_ascii=False))
                return 0 if value["valid"] else 2
            elif args.command == "templates":
                result = success(list_templates())
            else:
                history = History(data_dir, timezone)
                if args.command == "history":
                    value = history.list()
                elif args.command == "clear-history":
                    value = history.clear(args.yes)
                elif args.command == "export":
                    value = history.export(args.out, args.format, not args.no_bom)
                elif args.command == "import":
                    value = history.import_file(args.path)
                else:
                    value = history.backup(args.out)
                result = success(value)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except ReportError as exc:
        print(json.dumps(failure(exc), ensure_ascii=False))
        return exc.exit_code
    except FileNotFoundError as exc:
        print(json.dumps(failure(ReportError("not_found", str(exc), 3))))
        return 3
    except (ValueError, TypeError, KeyError, ZoneInfoNotFoundError) as exc:
        print(json.dumps(failure(ReportError("invalid_input", str(exc), 2))))
        return 2
    except OSError as exc:
        print(json.dumps(failure(ReportError("io_error", str(exc)))))
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
