"""How many injected bugs does the agent flag, and how often does it cry wolf on clean code?

Usage (from the project root, with the model endpoint running and pytest + pytest-cov installed):
    python -m evaluation.run_eval --repeats 3
    python -m evaluation.run_eval --cases refund,parking --repeats 1
    python -m evaluation.run_eval --verify-only          # no model needed
    python -m evaluation.run_eval --report evaluation/results/main_3b.json   # summary of a saved run, no model needed
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evaluation.cases import CASES, verify_cases  # noqa: E402
from evaluation.heldout_cases import HELDOUT  # noqa: E402


def run_variant(source, func, pytest_runner=None):
    """Full pipeline on one source version. Returns the raw findings (flags) of the agent."""
    from qe_agent.generate import generate_tests
    from qe_agent.sandbox import run_pytest_suite_with_cov
    from qe_agent.spec import REFERENCE, build_reference, get_spec
    from qe_agent.triage import audit_passing_tests, heal_suite

    runner = pytest_runner or run_pytest_suite_with_cov
    work, old = tempfile.mkdtemp(prefix="qe_eval_"), os.getcwd()
    os.chdir(work)
    try:
        with open("target_module.py", "w", encoding="utf-8") as f:
            f.write(source)
        tests = generate_tests(source, func)
        with open("test_generated_cases.py", "w", encoding="utf-8") as f:
            f.write(tests)
        res = runner("test_generated_cases.py")
        if "timed out" in res.stdout:
            raise RuntimeError("pytest timed out (machine too busy?)")  # recorded as an error, not as a miss
        REFERENCE["code"] = build_reference(source, func, get_spec(source, func), tests)
        passing = set(re.findall(r"::(test_\w+)\s+PASSED", res.stdout))
        failing = set(re.findall(r"::(test_\w+)\s+FAILED", res.stdout)) | set(re.findall(r"FAILED\s+\S+::(test_\w+)", res.stdout))
        audit = audit_passing_tests(source, func, tests, passing)
        _, findings = heal_suite(source, func, tests, failing)
        return {"n_pass": len(passing), "n_fail": len(failing), "reference_ok": bool(REFERENCE["code"]),
                "bug_flags": [f for f in findings if f["verdict"] == "report_bug"] + audit,
                "needs_review": sum(1 for f in findings if f["verdict"] == "needs_review"),
                "tests": tests, "reference": REFERENCE["code"]}
    finally:
        os.chdir(old)
        shutil.rmtree(work, ignore_errors=True)


def targeted(flags, clean_source, mutant_source, func, exclude=()):
    """A flag is 'targeted' when the flagged test's input really exposes the injected bug.
    `exclude`: inputs that were already flagged on the CLEAN version (noise) do not count."""
    from qe_agent.sandbox import call_in_sandbox
    for fl in flags:
        if fl.get("args") is None or fl.get("args") in exclude:
            continue
        ok1, v1 = call_in_sandbox(clean_source, func, fl["args"])
        ok2, v2 = call_in_sandbox(mutant_source, func, fl["args"])
        if ok1 and ok2 and v1 != v2:
            return True
    return False


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "n/a"


RUNS = []


def save(runs, out):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2, ensure_ascii=False)


def report(runs):
    ok = [r for r in runs if not r["error"]]
    for title, num in (("NUMERIC-OUTPUT CASES", True), ("CATEGORICAL-OUTPUT CASE (known blind spot)", False)):
        sel = [r for r in ok if r["numeric"] == num]
        mut, cln = [r for r in sel if r["variant"] != "clean"], [r for r in sel if r["variant"] == "clean"]
        if not sel:
            continue
        print(f"\n== {title} ==")
        print("bugs flagged on a test that exposes them (net of clean-run noise):", pct(sum(r["targeted"] for r in mut), len(mut)))
        print("   same, without the noise filter (old definition)               :", pct(sum(r["targeted_raw"] for r in mut), len(mut)))
        print("injected bugs flagged at all (incl. unrelated)    :", pct(sum(r["flagged"] for r in mut), len(mut)))
        print("clean versions wrongly flagged (false positives)   :", pct(sum(r["flagged"] for r in cln), len(cln)))
        print("runs where Llama produced a usable reference       :", pct(sum(r["reference_ok"] for r in sel), len(sel)))
        print("runs with 'needs review' items                     :", pct(sum(r["needs_review"] > 0 for r in sel), len(sel)))
    print(f"\nerrors (not counted): {len(runs) - len(ok)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--cases", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--out", default="", help="default: evaluation/results_<timestamp>.json")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--report", default="", help="print the summary of a saved results file (no model needed)")
    ap.add_argument("--heldout", action="store_true", help="run the held-out cases (use once, at the very end)")
    a = ap.parse_args()
    a.out = a.out or time.strftime("evaluation/results_%Y%m%d_%H%M%S.json")

    if a.report:
        with open(a.report, encoding="utf-8") as f:
            report(json.load(f))
        return
    problems = verify_cases() + verify_cases(HELDOUT)
    print("case check:", "OK - every mutant changes behaviour" if not problems else problems)
    if a.verify_only or problems:
        return
    if a.model:
        os.environ["LLM_MODEL"] = a.model

    chosen = [c for c in (HELDOUT if a.heldout else CASES) if not a.cases or c.name in a.cases.split(",")]
    runs = RUNS
    for c in chosen:
        variants = [("clean", c.source)] + [(m, c.mutant_source(m)) for m in c.mutants]
        for rep in range(a.repeats):
            clean_args = set()
            for vname, src in variants:
                t0 = time.time()
                try:
                    r = run_variant(src, c.func)
                    r["targeted_raw"] = vname != "clean" and targeted(r["bug_flags"], c.source, src, c.func)
                    r["targeted"] = vname != "clean" and targeted(r["bug_flags"], c.source, src, c.func, exclude=clean_args)
                    if vname == "clean":
                        clean_args = {f.get("args") for f in r["bug_flags"]}
                    r["error"] = None
                except Exception as e:  # model/endpoint problems are recorded, not counted as misses
                    r = {"error": str(e)[:200], "bug_flags": [], "targeted": False, "targeted_raw": False, "reference_ok": False, "needs_review": 0}
                r.update(case=c.name, variant=vname, rep=rep, numeric=c.numeric, flagged=bool(r["bug_flags"]), seconds=round(time.time() - t0, 1))
                r["bug_flags"] = [{k: v for k, v in f.items() if k in ("test", "verdict", "reason", "args", "spec_value")} for f in r["bug_flags"]]
                runs.append(r)
                save(runs, a.out)  # checkpoint after every variant
                tag = "clean " if vname == "clean" else "mutant"
                print(f"[{c.name:12}] {tag} {vname:24} flagged={r['flagged']!s:5} targeted={r['targeted']!s:5} {r['seconds']}s" + (f"  ERROR {r['error']}" if r["error"] else ""))

    report(runs)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2, ensure_ascii=False)
    print("raw results ->", a.out)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\ninterrupted - summarising the runs that finished (they are also saved in the output file)")
        report(RUNS)