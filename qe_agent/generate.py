"""Test generation with Llama, plus the (simulated) contract-drift helper used for demos."""
import re

from . import llm


def generate_tests(target_code, func_name):
    prompt = f"""
Write a complete pytest test file for the following Python function:

{target_code}

CRITICAL RULES:
1. Always start with:
import pytest
from target_module import {func_name}

2. Write standalone test functions: `def test_case_1():`, `def test_case_2():`, etc.
3. Call `{func_name}` directly and assign to `result`:
    result = {func_name}(...)
4. Assert expected values: `assert result == ...`
5. Output raw executable Python code only. No markdown fences.
"""
    response = llm.client.chat.completions.create(
        model=llm.MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are an automated Python test generator. You output ONLY executable pytest code. Never include markdown backticks or commentary."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=2000,
    )
    code = llm.clean_code(response.choices[0].message.content or "")
    if f"from target_module import {func_name}" not in code:
        code = f"import pytest\nfrom target_module import {func_name}\n\n" + code
    return code


def apply_contract_drift(initial_test_code, target_code):
    """SIMULATED drift: rewrites some generated assertions to mimic an outdated contract."""
    drifted_code = initial_test_code
    if "process_loan_application" in target_code:
        drifted_code = drifted_code.replace('"PRIME"', '"SUPER_PRIME"').replace("'PRIME'", "'SUPER_PRIME'")
        drifted_code = drifted_code.replace('"decision": "REJECTED"', '"loan_decision": "DECLINED"')
    elif "process_user_registration" in target_code:
        drifted_code = drifted_code.replace('"success"', '"completed_success"')
    elif "calculate_discount" in target_code:
        drifted_code = drifted_code.replace("'final_price'", "'net_price'").replace('"final_price"', '"net_price"')
    elif "process_loyalty_rewards" in target_code:
        drifted_code = drifted_code.replace('"PLATINUM"', '"DIAMOND"').replace("'PLATINUM'", "'DIAMOND'")
    else:
        drifted_code = re.sub(r'(assert.*?==\s*\{.*?: )([^,}]+)', r'\1"drifted_val"', drifted_code, count=1)
    return drifted_code