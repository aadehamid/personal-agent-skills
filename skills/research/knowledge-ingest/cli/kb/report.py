"""One report shape for every command: human text or JSON, and a consistent exit code.

Exit codes: 0 = clean (warnings allowed), 1 = failures found, 2 = usage or
configuration error (raised by Typer or by the command before checking).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import typer

FOOTER = "Mechanical checks only. Factual accuracy still needs the independent review."


def emit_error(message: str, as_json: bool) -> None:
    """A usage/config error (exit 2). In JSON mode stdout still carries valid JSON."""
    if as_json:
        typer.echo(json.dumps({"status": "error", "error": message, "reports": []}, indent=2))
    else:
        typer.echo(f"kb: {message}", err=True)


@dataclass
class Report:
    command: str
    subject: str = ""
    ok_lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    footer: bool = True

    def ok(self, msg: str) -> None:
        self.ok_lines.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    @property
    def exit_code(self) -> int:
        return 1 if self.failures else 0

    def as_dict(self) -> dict[str, Any]:
        return {"command": self.command, "subject": self.subject,
                "status": "fail" if self.failures else "clean",
                "failures": self.failures, "warnings": self.warnings,
                "ok": self.ok_lines, **self.data}

    def emit(self, as_json: bool) -> None:
        if as_json:
            typer.echo(json.dumps(self.as_dict(), indent=2, default=str))
            return
        if self.subject:
            typer.echo(f"{self.command}: {self.subject}")
        for line in self.ok_lines:
            typer.echo(f"  ok    {line}")
        for w in self.warnings:
            typer.echo(f"  WARN  {w}")
        for f in self.failures:
            typer.echo(f"  FAIL  {f}")
        status = (f"{len(self.failures)} failure(s)" if self.failures
                  else "Clean" + (f" ({len(self.warnings)} warning(s))" if self.warnings else ""))
        typer.echo(f"\n{status}." + (f" {FOOTER}" if self.footer else ""))


def emit_all(reports: list[Report], as_json: bool) -> int:
    """Emit reports and return the combined exit code.

    JSON is always one envelope, `{"status": ..., "reports": [...]}`, however many
    reports there are, so agents never have to branch on shape.
    """
    if as_json:
        status = "fail" if any(r.failures for r in reports) else "clean"
        typer.echo(json.dumps({"status": status, "reports": [r.as_dict() for r in reports]},
                              indent=2, default=str))
    else:
        for i, r in enumerate(reports):
            if i:
                typer.echo("")
            r.emit(False)
    return max((r.exit_code for r in reports), default=0)
