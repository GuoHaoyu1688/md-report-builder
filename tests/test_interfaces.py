import asyncio
import json
from pathlib import Path

from md_report_builder.cli import main
from md_report_builder.mcp_server import build_server


def test_cli_complete_workflow(tmp_path, capsys):
    source = tmp_path / "source.md"
    source.write_text("# Example\n\nLocal report")
    config = tmp_path / "config.toml"
    config.write_text(f'data_dir="{tmp_path / "data"}"\ntimezone="UTC"')
    base = ["--config", str(config), "--json"]

    def run(*args, expected=0):
        assert main([*args, *base]) == expected
        return json.loads(capsys.readouterr().out)

    assert run("--version")["data"]["version"] == "0.1.0"
    assert len(run("templates")["data"]) == 4
    assert run("lint", str(source))["data"]["valid"]
    result = run("build", str(source), "--to", "html", "--progress")
    assert Path(result["data"]["output"]).is_file()
    assert len(run("history")["data"]) == 1
    assert run("export", "--format", "csv", "--out", str(tmp_path / "history.csv"))["ok"]
    assert run("backup")["ok"]
    assert run("clear-history", "--yes")["data"]["deleted"] == 1
    assert run("import", str(tmp_path / "history.csv"))["data"]["imported"] == 1
    assert not run("clear-history", expected=2)["ok"]
    assert run("build", "missing.md", expected=3)["error"]["code"] == "not_found"
    assert run("build", expected=2)["error"]["code"] == "invalid_arguments"
    source.write_text("### Skipped")
    assert not run("lint", str(source), expected=2)["data"]["valid"]


def test_all_mcp_tools_official_sdk(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# Example\n\nLocal report")
    server = build_server(tmp_path / "data")

    async def call(name, args):
        result = await server.call_tool(name, args)
        return result[1] if isinstance(result, tuple) else json.loads(result[0].text)

    async def run():
        assert {tool.name for tool in await server.list_tools()} == {
            "build_report",
            "list_templates",
            "lint_markdown",
        }
        assert len((await call("list_templates", {}))["data"]) == 4
        assert (await call("lint_markdown", {"path": str(source)}))["data"]["valid"]
        result = await call("build_report", {"input_path": str(source), "to": "html"})
        assert result["ok"] and Path(result["data"]["output"]).is_file()
        assert not (await call("build_report", {"input_path": "missing.md"}))["ok"]
        assert not (await call("lint_markdown", {"path": "missing.md"}))["ok"]

    asyncio.run(run())
