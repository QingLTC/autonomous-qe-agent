"""HELD-OUT cases: written after the first evaluation round and NOT used for any tuning.
Run them once, at the very end:  python -m evaluation.run_eval --heldout --repeats 3
"""
from evaluation.cases import Case

HELDOUT = [
    Case("tax", "tax_due", '''def tax_due(income):
    """Progressive income tax:
    - The first 10000 is untaxed.
    - The part from 10000 up to 40000 is taxed at 10%.
    - The part above 40000 is taxed at 20%.
    - A negative income is invalid: status "error" with tax 0.
    """
    if income < 0:
        return {"status": "error", "tax": 0.0}
    band1 = max(0, min(income, 40000) - 10000)
    band2 = max(0, income - 40000)
    return {"status": "ok", "tax": round(band1 * 0.10 + band2 * 0.20, 2)}
''', {"untaxed_12000": ("min(income, 40000) - 10000", "min(income, 40000) - 12000"),
      "mid_rate_15pct": ("band1 * 0.10", "band1 * 0.15"),
      "top_rate_25pct": ("band2 * 0.20", "band2 * 0.25")},
         [(20000,), (50000,), (45000,)]),

    Case("data_plan", "data_plan_cost", '''import math


def data_plan_cost(gb_used):
    """Mobile data plan:
    - The base price is 20.0 and includes 5 GB.
    - Each additional GB (a partial GB is rounded up) costs 3.0.
    - The total is capped at 50.0.
    - Negative usage is invalid: status "error" with cost 0.
    """
    if gb_used < 0:
        return {"status": "error", "cost": 0.0}
    extra = max(0, math.ceil(gb_used - 5))
    return {"status": "ok", "cost": min(20.0 + 3.0 * extra, 50.0)}
''', {"included_6gb": ("gb_used - 5", "gb_used - 6"),
      "rate_4": ("3.0 * extra", "4.0 * extra"),
      "cap_60": ("extra, 50.0)", "extra, 60.0)")},
         [(7,), (7.5,), (40,)]),

    Case("checkout", "checkout_total", '''def checkout_total(subtotal, coupon_percent, min_spend):
    """Checkout total:
    - The coupon applies only when the subtotal is at least min_spend.
    - The coupon discount is coupon_percent percent of the subtotal, but never more than 25.0.
    - Tax of 8% is added on the discounted amount.
    - The total is rounded to 2 decimals.
    - A negative subtotal is invalid: status "error" with total 0.
    """
    if subtotal < 0:
        return {"status": "error", "total": 0.0}
    discount = 0.0
    if subtotal >= min_spend:
        discount = min(subtotal * coupon_percent / 100, 25.0)
    total = (subtotal - discount) * 1.08
    return {"status": "ok", "total": round(total, 2)}
''', {"min_spend_exclusive": ("subtotal >= min_spend", "subtotal > min_spend"),
      "discount_cap_30": ("/ 100, 25.0)", "/ 100, 30.0)"),
      "tax_before_discount": ("(subtotal - discount) * 1.08", "subtotal * 1.08 - discount")},
         [(100, 10, 100), (500, 20, 100), (100, 10, 50)]),

    Case("loyalty", "loyalty_points", '''def loyalty_points(spend):
    """Loyalty points:
    - 1 point for every full 10.0 spent on the first 500.0.
    - 2 points for every full 10.0 spent above 500.0.
    - A bonus of 50 points when spend is at least 1000.0.
    - Negative spend is invalid: status "error" with points 0.
    """
    if spend < 0:
        return {"status": "error", "points": 0}
    base = int(min(spend, 500.0) // 10)
    extra = int(max(spend - 500.0, 0) // 10) * 2
    bonus = 50 if spend >= 1000.0 else 0
    return {"status": "ok", "points": base + extra + bonus}
''', {"bonus_exclusive": ("spend >= 1000.0", "spend > 1000.0"),
      "double_becomes_triple": ("// 10) * 2", "// 10) * 3"),
      "first_tier_400": ("min(spend, 500.0)", "min(spend, 400.0)")},
         [(1000,), (700,), (450,)]),
]