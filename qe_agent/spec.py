"""Failure triage, spec audit of passing tests, and test healing."""
import json
import re

from . import llm
from .sandbox import call_in_sandbox
from .spec import REFERENCE, _is_error, _numbers, extract_call, flat_numbers, get_spec, get_test_expected, same_numbers, show_nums

def py_literal(v):
    """Python literal with double-quoted strings, so rewritten assertions keep the style of the generated tests (cleaner diffs)."""
    if isinstance(v, dict):
        return "{" + ", ".join(f"{py_literal(k)}: {py_literal(x)}" for k, x in v.items()) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(py_literal(x) for x in v) + "]"
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return repr(v)


def analyze_signals(ok, actual, block, source):
    """Deterministic evidence used as guardrails around the LLM verdict."""
    sig = {"crash": not ok, "negative": False, "stale_literal": False, "notes": []}
    if not ok:
        sig["notes"].append(f"source failed on these inputs: {actual}")
        return sig
    if any(n < 0 for n in _numbers(actual)):
        sig["negative"] = True
        sig["notes"].append("actual output contains a negative number")
    asserts = "\n".join(l for l in block.splitlines() if l.strip().startswith("assert"))
    missing = [s for s in re.findall(r"""["']([^"']+)["']""", asserts) if s not in source]
    if missing:
        sig["stale_literal"] = True
        sig["notes"].append(f"test expects literals that never appear in the source: {missing[:3]}")
    return sig

def llm_triage(source, block, actual, notes):
    prompt = (
        "You are a senior QA engineer triaging ONE failing pytest test.\n\n"
        f"SOURCE UNDER TEST:\n{source}\n\nFAILING TEST:\n{block}\n\n"
        f"ACTUAL OUTPUT of the source for the test's inputs: {actual!r}\n"
        f"AUTOMATED SIGNALS: {'; '.join(notes) or 'none'}\n\n"
        'Decide "fix_test" if the test expectation is outdated, misnamed or simply wrong '
        "while the source behaviour is plausible and self-consistent. "
        'Decide "report_bug" if the source output itself looks wrong, inconsistent or unsafe.\n'
        'Reply with JSON only: {"verdict": "fix_test" or "report_bug", "reason": "one short sentence"}'
    )
    try:
        r = llm.chat("Triage (no-spec fallback)",
            model=llm.MODEL_NAME,
            messages=[{"role": "system", "content": "You output only a JSON object."},
                      {"role": "user", "content": prompt}],
            temperature=0, max_tokens=200)
        m = re.search(r"\{[\s\S]*\}", r.choices[0].message.content or "")
        data = json.loads(m.group(0))
        if data.get("verdict") in ("fix_test", "report_bug"):
            return data["verdict"], str(data.get("reason", ""))[:200]
    except Exception:
        pass
    return "needs_review", "model returned no valid verdict"

def audit_passing_tests(source, func_name, test_code, passing):
    """Passing tests can also encode a bug: compare their expected values with the spec-derived reference."""
    ref = REFERENCE["code"]
    if not ref:
        return []
    out = []
    for blk in re.findall(r"(def\s+test_[a-zA-Z0-9_]+\s*\(\):[\s\S]*?)(?=\ndef\s+test_|\Z)", test_code):
        name = re.match(r"def\s+(test_\w+)", blk).group(1)
        if name not in passing:
            continue
        args, expected = extract_call(blk, func_name), get_test_expected(blk)
        if args is None or expected is None or _is_error(expected) or not flat_numbers(expected):
            continue
        ok, ref_val = call_in_sandbox(ref, func_name, args)
        if ok and not same_numbers(expected, ref_val):
            out.append({"test": name, "verdict": "spec_conflict
