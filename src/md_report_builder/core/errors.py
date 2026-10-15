"""Shared error contract for Python, CLI and MCP."""


class ReportError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 1):
        super().__init__(message)
        self.code, self.message, self.exit_code = code, message, exit_code


def success(data, warnings=None) -> dict:
    return {"ok": True, "data": data, "warnings": warnings or []}


def failure(error: ReportError) -> dict:
    return {"ok": False, "error": {"code": error.code, "message": error.message}}
