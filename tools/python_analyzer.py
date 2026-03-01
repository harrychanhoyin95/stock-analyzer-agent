import json
import subprocess
import tempfile
from pathlib import Path

from langchain_core.tools import tool

from pydantic import ValidationError
from .validate import AnalyzerInput

SANDBOX_IMAGE = "stock-analyzer-sandbox"
TIMEOUT_SECONDS = 15
MAX_OUTPUT_BYTES = 20_000


@tool
def python_analyzer(code: str, data: str = "") -> dict:
    """Execute Python code to analyze stock data in a sandboxed Docker container.
    Use this tool to perform custom analysis on stock data using pandas and numpy.
    The data from other tools can be passed as a JSON string.

    IMPORTANT: Your code must use print() to produce output. Expression values
    are not captured automatically — only what is explicitly printed is returned.

    Args:
        code: Python code to execute. pandas (pd) and numpy (np) are available.
              Must use print() to produce any output.
        data: Optional JSON string from other tools, available as 'data' variable.
              Use json.loads(data) inside your code to parse it.

    Returns:
        Dict with 'result' (stdout output) or 'error' if execution failed.
        May also include 'warnings' if the code produced stderr output despite succeeding.

    Example:
        code = '''
        import json
        stock = json.loads(data)
        prices = [d["close"] for d in stock["data"].values()]
        print(f"Average: {sum(prices)/len(prices):.2f}")
        '''
        data = '{"symbol": "AAPL", "data": {...}}'
    """
    if data:
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                return {"error": "invalid input data: expected a JSON object"}
            AnalyzerInput(**parsed)
        except json.JSONDecodeError as e:
            return {"error": f"invalid input data: {e}"}
        except ValidationError as e:
            messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
            return {"error": "invalid input data: " + ", ".join(messages)}

    run_script = f"data = {data if data else 'None'}\n\n{code}"

    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "run.py"
        script_path.write_text(run_script, encoding="utf-8")

        try:
            result = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "--network", "none",
                    "--memory", "128m",
                    "--cpus", "0.5",
                    "-v", f"{tmpdir}:/sandbox:ro",
                    SANDBOX_IMAGE,
                    "python", "/sandbox/run.py",
                ],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {"error": f"Code execution timed out after {TIMEOUT_SECONDS}s"}
        except FileNotFoundError:
            return {"error": "Docker is not installed or not in PATH"}

        if result.returncode == 0:
            stdout = result.stdout
            if len(stdout) > MAX_OUTPUT_BYTES:
                stdout = stdout[:MAX_OUTPUT_BYTES] + "\n... [output truncated]"
            if not stdout.strip():
                stdout = "(no output — code ran successfully but printed nothing)"
            response = {"result": stdout}
            if result.stderr.strip():
                response["warnings"] = result.stderr.strip()
            return response
        else:
            return {"error": result.stderr or f"Container exited with code {result.returncode}"}
