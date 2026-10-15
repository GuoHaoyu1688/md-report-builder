"""Official MCP tools backed by the same report core as the CLI."""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .core.builder import build
from .core.errors import ReportError, failure, success
from .core.source import lint_markdown as lint
from .core.styles import list_templates as templates


def build_server(data_dir="data", timezone="Asia/Shanghai") -> FastMCP:
    server = FastMCP("md-report-builder")

    @server.tool()
    def build_report(
        input_path: str,
        to: str = "docx",
        template: str | None = None,
        out: str | None = None,
        strict: bool = False,
    ) -> dict:
        """Build a local report without network access.

        Side effects: atomically writes/replaces the output and records build history.
        out is a directory; omit it for the configured data directory's reports folder.
        """
        try:
            value = build(
                input_path,
                to,
                template,
                out or Path(data_dir) / "reports",
                data_dir=data_dir,
                timezone=timezone,
                strict=strict,
            )
            return success(value, value["warnings"])
        except ReportError as exc:
            return failure(exc)

    @server.tool()
    def list_templates() -> dict:
        """List the four bundled report templates without writing data."""
        return success(templates())

    @server.tool()
    def lint_markdown(path: str) -> dict:
        """Check local Markdown headings, links, images and table widths."""
        try:
            return success(lint(path, timezone))
        except ReportError as exc:
            return failure(exc)

    return server


def main():
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
