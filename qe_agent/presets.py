"""Benchmark presets persisted in presets.json."""
import json
import os

PRESETS_FILE = "presets.json"

DEFAULT_PRESETS = {
    "1. Loan Application (Multi-branch Risk Assessment)": (
        "def process_loan_application(credit_score, income, debt_amount):\n"
        "    if credit_score < 300 or credit_score > 850:\n"
        '        return {"decision": "REJECTED", "tier": "INVALID", "rate": None}\n'
        "    \n"
        "    dti_ratio = round(debt_amount / max(income, 1), 2)\n"
        "    \n"
        "    if credit_score >= 750 and dti_ratio < 0.3:\n"
        '        return {"decision": "APPROVED", "tier": "PRIME", "rate": 0.045}\n'
        "    elif credit_score >= 650 and dti_ratio < 0.45:\n"
        '        return {"decision": "APPROVED", "tier": "STANDARD", "rate": 0.075}\n'
        "    else:\n"
        '        return {"decision": "REJECTED", "tier": "HIGH_RISK", "rate": 0.12}\n'
    ),
    "2. User Registration (Contract Drift & Auth)": (
        "def process_user_registration(username, age, email):\n"
        "    if len(username) > 20:\n"
        '        return {"status": "error", "message": "Username too long"}\n'
        "    if age < 18:\n"
        '        return {"status": "error", "message": "Underage not allowed"}\n'
        '    return {"status": "success", "user_id": 1001}\n'
    ),
    "3. E-Commerce Discount (Multi-branch Pricing)": (
        "def calculate_discount(order_amount, is_vip, coupon_code):\n"
        "    discount = 0.0\n"
        "    if order_amount >= 100:\n"
        "        discount += 0.1\n"
        "    if is_vip:\n"
        "        discount += 0.15\n"
        '    if coupon_code == "SAVE20":\n'
        "        discount += 0.2\n"
        "    \n"
        "    actual_discount = min(discount, 0.4)\n"
        "    final_price = round(order_amount * (1.0 - actual_discount), 2)\n"
        '    return {"final_price": final_price, "applied_discount": round(actual_discount, 2)}\n'
    ),
    "4. Logistics Fee Calculator (Complex Math & Sanity)": (
        "def calculate_shipping_fee(weight_kg, distance_km, is_express):\n"
        "    if weight_kg <= 0 or distance_km <= 0:\n"
        '        return {"status": "error", "message": "Invalid package dimensions"}\n'
        "    \n"
        "    base_rate = 10.0\n"
        "    weight_cost = weight_kg * 2.5\n"
        "    distance_cost = (distance_km // 50) * 1.5\n"
        "    \n"
        "    total = base_rate + weight_cost + distance_cost\n"
        "    \n"
        "    if is_express:\n"
        "        total = total * 1.3\n"
        "        \n"
        "    return {\n"
        '        "status": "success",\n'
        '        "total_fee": round(total, 2),\n'
        '        "currency": "USD"\n'
        "    }\n"
    ),
    "5. Loyalty Rewards (Tier & Settlement)": (
        "def process_loyalty_rewards(total_spent, active_months, has_penalty):\n"
        "    if has_penalty:\n"
        '        return {"status": "suspended", "tier": "NONE", "multiplier": 0.0, "bonus_points": 0}\n'
        "    \n"
        "    if total_spent < 0 or active_months < 0:\n"
        '        return {"status": "error", "message": "Invalid transaction history"}\n'
        "    \n"
        "    if total_spent >= 1000 and active_months >= 12:\n"
        '        return {"status": "success", "tier": "PLATINUM", "multiplier": 2.0, "bonus_points": 500}\n'
        "    elif total_spent >= 500 or active_months >= 6:\n"
        '        return {"status": "success", "tier": "GOLD", "multiplier": 1.5, "bonus_points": 200}\n'
        "    else:\n"
        '        return {"status": "success", "tier": "SILVER", "multiplier": 1.0, "bonus_points": 50}\n'
    ),

    "6. Calculate Refund (docstring spec, seeded bug)": '''def calculate_refund(price, days_since_purchase, is_defective):
    """Refund policy:
    - Defective items: 100% refund within 30 days.
    - Other items: 100% within 7 days, 50% within 14 days, otherwise 0.
    - A refund can never exceed the original price.
    """
    if days_since_purchase < 0:
        return {"status": "error", "refund": 0.0}
    if is_defective and days_since_purchase <= 30:
        return {"status": "ok", "refund": price}
    if days_since_purchase <= 7:
        return {"status": "ok", "refund": price}
    if days_since_purchase <= 14:
        return {"status": "ok", "refund": price * 1.5}
    return {"status": "ok", "refund": 0.0}''',
}

def load_presets():
    if not os.path.exists(PRESETS_FILE):
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_PRESETS, f, indent=2, ensure_ascii=False)
        return DEFAULT_PRESETS
    try:
        with open(PRESETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_PRESETS

def save_presets(presets_dict):
    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets_dict, f, indent=2, ensure_ascii=False)