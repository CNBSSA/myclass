import os
import sys
import subprocess
import tempfile
import resource
from pathlib import Path

DEFAULT_TIMEOUT = 8.0
MEMORY_LIMIT_MB = 512
MAX_OUTPUT_CHARS = 50_000


def _set_limits() -> None:
    bytes_limit = MEMORY_LIMIT_MB * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (bytes_limit, bytes_limit))
    except (ValueError, OSError):
        pass


def _truncate(text: str) -> str:
    if text is None:
        return ""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    head = text[:MAX_OUTPUT_CHARS]
    return head + f"\n\n[Output truncated at {MAX_OUTPUT_CHARS} characters]"


def execute_python(code: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    with tempfile.TemporaryDirectory(prefix="myclass_sandbox_") as tmpdir:
        script_path = Path(tmpdir) / "user_code.py"
        script_path.write_text(code, encoding="utf-8")

        env = os.environ.copy()
        env["MPLBACKEND"] = "Agg"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        try:
            result = subprocess.run(
                [sys.executable, "-I", str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                env=env,
                preexec_fn=_set_limits if sys.platform != "win32" else None,
            )
            return {
                "success": result.returncode == 0,
                "stdout": _truncate(result.stdout),
                "stderr": _truncate(result.stderr),
                "return_code": result.returncode,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout if isinstance(e.stdout, str) else (e.stdout.decode("utf-8", errors="replace") if e.stdout else "")
            stderr = e.stderr if isinstance(e.stderr, str) else (e.stderr.decode("utf-8", errors="replace") if e.stderr else "")
            return {
                "success": False,
                "stdout": _truncate(stdout),
                "stderr": _truncate(f"[TIMEOUT after {timeout}s]\n{stderr}"),
                "return_code": -1,
                "timed_out": True,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"[Sandbox error] {type(e).__name__}: {e}",
                "return_code": -1,
                "timed_out": False,
            }
