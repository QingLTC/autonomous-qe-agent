"""Running code safely-ish: subprocess isolation with timeouts, pytest + coverage."""
import ast
import re
import subprocess
import sys

PYTEST_TIMEOUT = 60

SANDBOX_TIMEOUT = 5

class RunResult:
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout

def run_pytest_suite_with_cov(filename: str):
    cmd = [
        sys.executable, "-B", "-m", "pytest", filename,
        "-v", "--cov=target_module", "--cov-report=term-missing",
        "-p", "no:cacheprovider"
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=PYTEST_TIMEOUT)
        return RunResult(p.returncode, p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        return RunResult(1, f"Pytest timed out after {PYTEST_TIMEOUT}s (possible infinite loop in the code under test).")

def parse_coverage(stdout_text: str) -> str:
    m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+%)", stdout_text)
    if not m:
        m = re.search(r"target_module\.py\s+\d+\s+\d+\s+(\d+%)", stdout_text)
    return m.group(1) if m else "N/A"

# Process isolation + timeout (not a hardened security sandbox).
SANDBOX_RUNNER = (
    "import sys\n"
    "ns = {}\n"
    "exec(sys.argv[1], ns)\n"
    "print(repr(eval(sys.argv[2] + '(' + sys.argv[3] + ')', ns)))\n"
)

def call_in_sandbox(code, func_name, args_text):
    try:
        p = subprocess.run(
            [sys.executable, "-I", "-c", SANDBOX_RUNNER, code, func_name, args_text],
            capture_output=True, text=True, timeout=SANDBOX_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, "timed out"
    if p.returncode != 0:
        lines = p.stderr.strip().splitlines()
        return False, (lines[-1] if lines else "unknown error")
    try:
        return True, ast.literal_eval(p.stdout.strip())
    except Exception:
        return False, "output is not a plain Python literal"