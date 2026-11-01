"""Failure triage, spec audit of passing tests, and test healing."""
import json
import re

from . import llm
from .sandbox import call_in_sandbox
from .spec import REFERENCE, _is_error, _numbers, extract_call, flat_numbers, get_spec, get_test_expected, same_numbers, show_nums

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
        r = llm.client.chat.completions.create(
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
            out.append({"test": name, "verdict": "spec_conflict", "decided by": "Llama reference + code compare", "basis": "spec", "args": args, "spec_value": ref_val,
                        "reason": f"passes, but the test expects {show_nums(expected)} while the spec-derived reference returns {show_nums(ref_val)}"})
    return out

def triage_failure(source, func_name, block):
    args = extract_call(block, func_name)
    if args is None:
        return {"verdict": "needs_review", "by": "rules", "basis": "-", "reason": "could not parse the call", "args": None, "actual": None}
    ok, actual = call_in_sandbox(source, func_name, args)
    sig = analyze_signals(ok, actual, block, source)
    base = {"args": args, "actual": actual}
    if sig["crash"] or sig["negative"]:
        return {**base, "verdict": "report_bug", "by": "guardrail", "basis": "rule", "reason": "; ".join(sig["notes"])}

    ref = REFERENCE["code"]
    if ref:
        ref_ok, ref_val = call_in_sandbox(ref, func_name, args)
        by = "Llama reference + code compare"
        if not flat_numbers(actual):
            return {**base, "verdict": "needs_review", "by": by, "basis": "spec",
                    "reason": "the output has no numeric values, so it cannot be compared with the reference"}
        if sig["stale_literal"] and (not ref_ok or same_numbers(actual, ref_val)):
            return {**base, "verdict": "fix_test", "by": "guardrail", "basis": "spec + rule",
                    "reason": "test expects values the source can never produce (contract drift)"}
        if not ref_ok:
            return {**base, "verdict": "needs_review", "by": by, "basis": "spec",
                    "reason": f"the spec-derived reference has no defined behaviour for these inputs ({ref_val})"}
        if same_numbers(actual, ref_val):
            return {**base, "verdict": "fix_test", "by": by, "basis": "spec",
                    "reason": f"source matches the spec-derived reference ({show_nums(ref_val)}); the test expectation is wrong"}
        expected = get_test_expected(block)
        if _is_error(actual) or _is_error(expected):
            return {**base, "verdict": "needs_review", "by": by, "basis": "spec",
                    "reason": "error-handling case that the spec does not describe"}
        if expected is not None and same_numbers(expected, ref_val):
            return {**base, "verdict": "report_bug", "by": by, "basis": "spec",
                    "reason": f"source returns {show_nums(actual)}, spec-derived reference returns {show_nums(ref_val)}"}
        return {**base, "verdict": "needs_review", "by": by, "basis": "spec",
                "reason": f"source returns {show_nums(actual)}, reference returns {show_nums(ref_val)}, test expects {show_nums(expected)}"}

    # No usable reference (no docstring, or the model failed to write one) -> low-confidence fallback
    verdict, reason = llm_triage(source, block, actual, sig["notes"])
    by = "Llama"
    if verdict == "report_bug" and sig["stale_literal"]:
        verdict, by = "fix_test", "guardrail"
        reason = "test expects values the source can never produce (contract drift)"
    basis = "NO SPEC (low confidence)" if not get_spec(source, func_name) else "NO REFERENCE (low confidence)"
    return {**base, "verdict": verdict, "by": by, "basis": basis, "reason": reason}

def heal_suite(source, func_name, test_code, failing):
    blocks = re.findall(r"(def\s+test_[a-zA-Z0-9_]+\s*\(\):[\s\S]*?)(?=\ndef\s+test_|\Z)", test_code)
    out, findings = [], []
    for blk in blocks:
        name = re.match(r"def\s+(test_\w+)", blk).group(1)
        if name not in failing:
            out.append(blk.strip())
            continue
        t = triage_failure(source, func_name, blk)
        findings.append({"test": name, "verdict": t["verdict"], "decided by": t["by"], "basis": t["basis"], "reason": t["reason"], "args": t.get("args")})
        if t["verdict"] == "fix_test":
            header = blk.strip().splitlines()[0]
            out.append(f"{header}\n    result = {func_name}({t['args']})\n    assert result == {t['actual']!r}")
        else:
            out.append(blk.strip())  # keep failing on purpose: do not hide a suspected bug
    header = f"import pytest\nfrom target_module import {func_name}\n\n"
    return header + "\n\n".join(out) + "\n", findings

def changed_tests(old_code, new_code):
    pat = r"(def\s+test_[a-zA-Z0-9_]+\s*\(\):[\s\S]*?)(?=\ndef\s+test_|\Z)"
    grab = lambda code: {re.match(r"def\s+(test_\w+)", b).group(1): b.strip() for b in re.findall(pat, code)}
    old, new = grab(old_code), grab(new_code)
    names = [n for n in new if n in old and old[n] != new[n]]
    return "\n\n".join(old[n] for n in names), "\n\n".join(new[n] for n in names), names


def with_spec_numbers(expected, spec_val):
    """Keep the test's own structure/status strings, but take the numbers from the spec-derived value."""
    if isinstance(expected, dict) and isinstance(spec_val, dict):
        out = dict(expected)
        for k, v in expected.items():
            sv = spec_val.get(k)
            if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (v, sv)):
                out[k] = sv
        return out
    return spec_val


def align_to_spec(test_code, func_name, rows):
    """Rewrite spec-conflicting tests to the spec-derived value. They then FAIL on a buggy source, which is the point."""
    by_name = {r["test"]: r for r in rows if r.get("args") is not None and "spec_value" in r}
    out = []
    for blk in re.findall(r"(def\s+test_[a-zA-Z0-9_]+\s*\(\):[\s\S]*?)(?=\ndef\s+test_|\Z)", test_code):
        name = re.match(r"def\s+(test_\w+)", blk).group(1)
        r = by_name.get(name)
        expected = get_test_expected(blk) if r else None
        if r is None or expected is None:
            out.append(blk.strip())
            continue
        new = with_spec_numbers(expected, r["spec_value"])
        header = blk.strip().splitlines()[0]
        out.append(f"{header}\n    # spec-aligned: was {show_nums(expected)}; fails until the source bug is fixed\n"
                   f"    result = {func_name}({r['args']})\n    assert result == {new!r}")
    return f"import pytest\nfrom target_module import {func_name}\n\n" + "\n\n".join(out) + "\n"