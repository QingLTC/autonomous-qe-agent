"""Spec handling: docstring as the spec, Llama-written reference implementation, numeric comparison."""
import ast
import math
import re

from . import llm
from .sandbox import call_in_sandbox

def extract_function_name(code_text: str):
    match = re.search(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", code_text)
    return match.group(1) if match else None

def extract_call(block, func_name):
    m = re.search(rf"{re.escape(func_name)}\s*\(", block)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(block) and depth:
        depth += {"(": 1, ")": -1}.get(block[i], 0)
        i += 1
    return " ".join(block[m.end():i - 1].split()) if depth == 0 else None

def _numbers(o):
    if isinstance(o, dict):
        return [n for v in o.values() for n in _numbers(v)]
    if isinstance(o, (list, tuple)):
        return [n for v in o for n in _numbers(v)]
    return [o] if isinstance(o, (int, float)) and not isinstance(o, bool) else []

def get_spec(source, func_name):
    try:
        for n in ast.walk(ast.parse(source)):
            if isinstance(n, ast.FunctionDef) and n.name == func_name:
                return ast.get_docstring(n)
    except SyntaxError:
        pass
    return None

def get_test_expected(block):
    m = re.search(r"assert\s+result\s*==\s*([\s\S]+)$", block.strip())
    if not m:
        return None
    try:
        return ast.literal_eval(m.group(1).strip())
    except Exception:
        return None

def show_nums(o):
    if isinstance(o, dict):
        parts = [f"{k}={v}" for k, v in sorted(o.items(), key=lambda kv: str(kv[0])) if isinstance(v, (int, float)) and not isinstance(v, bool)]
        return ", ".join(parts) or "(no numeric values)"
    return repr(o)

def shape_of(v):
    if isinstance(v, dict):
        return {k: shape_of(x) for k, x in v.items()}
    if isinstance(v, bool):
        return "<bool>"
    if isinstance(v, (int, float)):
        return "<number>"
    return "<text>"

def flat_numbers(o):
    if isinstance(o, dict):
        return [n for k in sorted(o, key=str) for n in flat_numbers(o[k])]
    return _numbers(o)

def same_numbers(a, b):
    """Deterministic comparison of the numeric content (statuses/strings are not compared)."""
    x, y = flat_numbers(a), flat_numbers(b)
    return len(x) == len(y) and all(math.isclose(i, j, abs_tol=0.011) for i, j in zip(x, y))

def _is_error(o):
    return isinstance(o, dict) and any(isinstance(v, str) and "error" in v.lower() for v in o.values())

REFERENCE = {"code": None}

def build_reference(source, func_name, spec, test_code):
    """Llama writes an independent reference implementation from the spec ALONE (it never sees the source body)."""
    try:
        fn = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == func_name)
    except Exception:
        return None
    names = [x.arg for x in fn.args.args]
    sample_args, sample_out = None, None
    for blk in re.findall(r"(def\s+test_[a-zA-Z0-9_]+\s*\(\):[\s\S]*?)(?=\ndef\s+test_|\Z)", test_code):
        args = extract_call(blk, func_name)
        if args is None:
            continue
        ok, out = call_in_sandbox(source, func_name, args)
        if ok:
            sample_args, sample_out = args, out
            break
    if sample_args is None:
        return None
    shape = f" The returned value must have the same structure and keys as {shape_of(sample_out)!r}, with real values." if isinstance(sample_out, dict) else ""
    prompt = (f"Write a Python function named {func_name} with parameters ({', '.join(names)}) that implements EXACTLY the specification below. "
              "Follow every rule literally and do not add behaviour the spec does not state." + shape +
              " Output only the code, no explanation.\n\nSPEC:\n" + spec)
    for temp in (0, 0.3):
        try:
            r = llm.client.chat.completions.create(model=llm.MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=temp, max_tokens=1200)
            code = llm.clean_code(r.choices[0].message.content or "")
            if f"def {func_name}" in code and call_in_sandbox(code, func_name, sample_args)[0]:
                return code
        except Exception:
            pass
    return None