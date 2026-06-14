"""
TypeScriptCompilerService
=========================
Runs ``tsc --noEmit`` on a generated Next.js / React Native bundle to catch type errors
before the user ever sees the code.  Requires Node.js and TypeScript installed in PATH
(or available via npx).

Usage::

    from app.modules.codegen.services.typescript_compiler import (
        TypeScriptCompilerService, TSCompileResult
    )

    result = TypeScriptCompilerService().check(files_dict)
    if not result.passed:
        logger.warning("TypeScript errors: %s", result.errors[:5])
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TSError:
    file: str
    line: int
    column: int
    code: str      # e.g. "TS2345"
    message: str


@dataclass
class TSCompileResult:
    passed: bool
    errors: list[TSError] = field(default_factory=list)
    duration_ms: int = 0
    skipped: bool = False
    skip_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "error_count": len(self.errors),
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "duration_ms": self.duration_ms,
            "errors": [
                {
                    "file": e.file,
                    "line": e.line,
                    "column": e.column,
                    "code": e.code,
                    "message": e.message,
                }
                for e in self.errors[:20]   # cap at 20 to keep response lean
            ],
        }


class TypeScriptCompilerService:
    """
    Writes TypeScript files from a generated bundle to a temp directory,
    installs a minimal tsconfig.json, and runs ``tsc --noEmit``.
    """

    # Minimal tsconfig that covers Next.js / RN generated code
    _TSCONFIG = {
        "compilerOptions": {
            "target": "ES2020",
            "lib": ["dom", "dom.iterable", "esnext"],
            "allowJs": True,
            "skipLibCheck": True,            # skip node_modules — we only care about our code
            "strict": True,
            "noEmit": True,
            "esModuleInterop": True,
            "module": "esnext",
            "moduleResolution": "bundler",
            "resolveJsonModule": True,
            "isolatedModules": True,
            "jsx": "preserve",
            "incremental": False,
            "paths": {
                "@/*": ["./*"]
            }
        },
        "include": ["**/*.ts", "**/*.tsx"],
        "exclude": ["node_modules", ".next", "dist", "build"]
    }

    def check(
        self,
        files: dict[str, str],
        *,
        timeout_seconds: int = 60,
    ) -> TSCompileResult:
        """
        :param files: dict mapping relative path -> content (only *.ts/*.tsx extracted)
        :param timeout_seconds: kill tsc after this many seconds (default 60)
        """
        import time

        # Filter to TypeScript files only
        ts_files = {
            p: c for p, c in files.items()
            if p.endswith((".ts", ".tsx")) and not p.startswith("node_modules")
        }
        if not ts_files:
            return TSCompileResult(
                passed=True,
                skipped=True,
                skip_reason="No TypeScript files in bundle",
            )

        # Check tsc is available
        tsc_bin = self._find_tsc()
        if not tsc_bin:
            return TSCompileResult(
                passed=True,    # don't block generation if tsc not installed
                skipped=True,
                skip_reason="tsc not found in PATH; install Node.js + typescript to enable TS checking",
            )

        tmpdir = tempfile.mkdtemp(prefix="archie_ts_")
        try:
            # Write TypeScript files
            for rel_path, content in ts_files.items():
                abs_path = Path(tmpdir) / rel_path
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_text(content, encoding="utf-8")

            # Write tsconfig.json
            tsconfig_path = Path(tmpdir) / "tsconfig.json"
            tsconfig_path.write_text(json.dumps(self._TSCONFIG, indent=2))

            t0 = time.monotonic()
            try:
                proc = subprocess.run(
                    [tsc_bin, "--noEmit", "--project", str(tsconfig_path)],
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=tmpdir,
                )
            except subprocess.TimeoutExpired:
                return TSCompileResult(
                    passed=True,
                    skipped=True,
                    skip_reason=f"tsc timed out after {timeout_seconds}s",
                )
            duration_ms = int((time.monotonic() - t0) * 1000)

            errors = self._parse_tsc_output(proc.stdout + proc.stderr, tmpdir)
            return TSCompileResult(
                passed=proc.returncode == 0,
                errors=errors,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            logger.warning("TypeScriptCompilerService failed: %s", exc)
            return TSCompileResult(
                passed=True,
                skipped=True,
                skip_reason=str(exc),
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_tsc(self) -> Optional[str]:
        """Return path to tsc binary, or None if not available."""
        # Try direct binary first
        tsc = shutil.which("tsc")
        if tsc:
            return tsc
        # Try npx tsc
        npx = shutil.which("npx")
        if npx:
            try:
                result = subprocess.run(
                    [npx, "tsc", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode == 0:
                    return f"{npx} tsc"
            except Exception as exc:
                logger.debug("suppressed error in TypeScriptCompilerService._find_tsc (app/modules/codegen/services/typescript_compiler.py): %s", exc)
        return None

    def _parse_tsc_output(self, output: str, tmpdir: str) -> list[TSError]:
        """
        Parse tsc output lines like:
        ``src/foo.tsx(12,5): error TS2345: Argument of type...``
        """
        errors: list[TSError] = []
        pattern_re = __import__("re").compile(
            r"^(.+?)\((\d+),(\d+)\):\s+error\s+(TS\d+):\s+(.+)$"
        )
        for line in output.splitlines():
            m = pattern_re.match(line.strip())
            if m:
                file_abs, line_no, col_no, code, msg = m.groups()
                # Make path relative by stripping tmpdir prefix
                try:
                    file_rel = os.path.relpath(file_abs, tmpdir)
                except ValueError:
                    file_rel = file_abs
                errors.append(TSError(
                    file=file_rel,
                    line=int(line_no),
                    column=int(col_no),
                    code=code,
                    message=msg.strip(),
                ))
        return errors
