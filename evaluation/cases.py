"""Evaluation cases: each function has a docstring spec, a clean version and injected-bug versions (mutants)."""
from dataclasses import dataclass, field


@dataclass
class Case:
    name: str
    func: str
    source: str
    mutants: dict            # mutant name -> (old text, new text), applied once to the clean source
    probes: list             # argument tuples used to prove that every mutant really changes behaviour
    numeric: bool = True     # False = categorical output (a known blind spot of the numeric comparison)

    def mutant_source(self, name):
        old, new = self.mutants[name]
        assert old in self.source, (self.name, name)
        return self.source.replace(old, new, 1)


CASES = [
    Case("refund", "calculate_refund", '''def calculate_refund(price, days_since_purchase, is_defective):
    """Refund policy:
    - Defective items: 100% refund within 30 days.
    - Other items: 100% within 7 days, 50% within 14 days, otherwise 0.
    - A negative number of days is invalid: status "error" with refund 0.
    """
    if days_since_purchase < 0:
        return {"status": "error", "refund": 0.0}
    if is_defective and days_since_purchase <= 30:
        return {"status": "ok", "refund": float(price)}
    if days_since_purchase <= 7:
        return {"status": "ok", "refund": float(price)}
    if days_since_purchase <= 14:
        return {"status": "ok", "refund": price * 0.5}
    return {"status": "ok", "refund": 0.0}
''', {"half_becomes_150pct": ("price * 0.5", "price * 1.5"),
      "boundary_14_exclusive": ("days_since_purchase <= 14", "days_since_purchase < 14"),
      "defective_window_20": ("days_since_purchase <= 30", "days_since_purchase <= 20")},
         [(100, 10, False), (100, 14, False), (100, 25, True), (100, 8, False)]),

    Case("shipping", "shipping_fee", '''import math


def shipping_fee(weight_kg, is_express):
    """Shipping fee policy:
    - Up to 1 kg: base fee 5.0.
    - Every additional kg, rounded up, adds 2.0.
    - Express shipping multiplies the fee by 1.5.
    - The final fee is capped at 40.0.
    - weight_kg <= 0 is invalid: status "error" with fee 0.
    """
    if weight_kg <= 0:
        return {"status": "error", "fee": 0.0}
    extra_kg = max(0, math.ceil(weight_kg - 1))
    fee = 5.0 + 2.0 * extra_kg
    if is_express:
        fee = fee * 1.5
    return {"status": "ok", "fee": min(fee, 40.0)}
''', {"cap_400": ("min(fee, 40.0)", "min(fee, 400.0)"),
      "express_1_2x": ("fee * 1.5", "fee * 1.2"),
      "floor_not_ceil": ("math.ceil(weight_kg - 1)", "int(weight_kg - 1)")},
         [(100, False), (2, True), (2.5, False)]),

    Case("late_fee", "late_fee", '''def late_fee(days_late, is_member):
    """Library late fee:
    - The first 3 days late are free.
    - After that the fee is 0.5 per day late.
    - The fee is capped at 10.0 (the cap applies before the member discount).
    - Members pay half of the resulting fee.
    - A negative number of days is invalid: status "error" with fee 0.
    """
    if days_late < 0:
        return {"status": "error", "fee": 0.0}
    billable = max(0, days_late - 3)
    fee = min(billable * 0.5, 10.0)
    if is_member:
        fee = fee * 0.5
    return {"status": "ok", "fee": fee}
''', {"grace_2_days": ("days_late - 3", "days_late - 2"),
      "cap_20": ("billable * 0.5, 10.0", "billable * 0.5, 20.0"),
      "member_80pct": ("fee = fee * 0.5", "fee = fee * 0.8")},
         [(4, False), (100, False), (10, True)]),

    Case("bulk_total", "bulk_total", '''def bulk_total(price, quantity):
    """Bulk pricing:
    - Quantity 1 to 9: no discount.
    - Quantity 10 to 49: 10% discount on the total.
    - Quantity 50 or more: 20% discount on the total.
    - total = price * quantity * (1 - discount), rounded to 2 decimals.
    - A quantity below 1 or a negative price is invalid: status "error" with total 0.
    """
    if quantity < 1 or price < 0:
        return {"status": "error", "total": 0.0}
    discount = 0.0
    if quantity >= 50:
        discount = 0.2
    elif quantity >= 10:
        discount = 0.1
    return {"status": "ok", "total": round(price * quantity * (1 - discount), 2)}
''', {"threshold_50_exclusive": ("quantity >= 50", "quantity > 50"),
      "discount_25pct": ("discount = 0.2", "discount = 0.25"),
      "threshold_10_to_20": ("quantity >= 10", "quantity >= 20")},
         [(10, 50), (10, 60), (10, 15)]),

    Case("ticket", "ticket_price", '''def ticket_price(age, is_student):
    """Cinema ticket (base price 12.0):
    - Children under 12 pay 50% of the base price.
    - Seniors aged 65 or older pay 60%.
    - Students aged 12 to 64 pay 80%.
    - Everyone else pays 100%.
    - A negative age is invalid: status "error" with price 0.
    """
    if age < 0:
        return {"status": "error", "price": 0.0}
    base = 12.0
    if age < 12:
        price = base * 0.5
    elif age >= 65:
        price = base * 0.6
    elif is_student:
        price = base * 0.8
    else:
        price = base
    return {"status": "ok", "price": round(price, 2)}
''', {"child_12_inclusive": ("age < 12", "age <= 12"),
      "senior_70pct": ("base * 0.6", "base * 0.7"),
      "student_90pct": ("base * 0.8", "base * 0.9")},
         [(12, False), (70, False), (20, True)]),

    Case("weekly_pay", "weekly_pay", '''def weekly_pay(hours, hourly_rate):
    """Weekly pay:
    - The first 40 hours are paid at the hourly rate.
    - Hours above 40, up to 60, are paid at 1.5 times the rate.
    - Hours above 60 are paid at 2 times the rate.
    - Negative hours or a rate of 0 or less is invalid: status "error" with pay 0.
    """
    if hours < 0 or hourly_rate <= 0:
        return {"status": "error", "pay": 0.0}
    regular = min(hours, 40)
    overtime = min(max(hours - 40, 0), 20)
    double = max(hours - 60, 0)
    pay = hourly_rate * (regular + 1.5 * overtime + 2 * double)
    return {"status": "ok", "pay": round(pay, 2)}
''', {"regular_cap_45": ("min(hours, 40)", "min(hours, 45)"),
      "overtime_1_25x": ("1.5 * overtime", "1.25 * overtime"),
      "double_1_5x": ("2 * double", "1.5 * double")},
         [(50, 10), (70, 10)]),

    Case("parking", "parking_fee", '''import math


def parking_fee(minutes):
    """Parking fee:
    - The first 30 minutes are free.
    - After that, 2.0 per started hour (partial hours are rounded up).
    - The fee is capped at 20.0 per day.
    - A negative number of minutes is invalid: status "error" with fee 0.
    """
    if minutes < 0:
        return {"status": "error", "fee": 0.0}
    billable = max(0, minutes - 30)
    hours = math.ceil(billable / 60)
    return {"status": "ok", "fee": min(hours * 2.0, 20.0)}
''', {"free_20_minutes": ("minutes - 30", "minutes - 20"),
      "floor_hours": ("math.ceil(billable / 60)", "billable // 60"),
      "cap_30": ("min(hours * 2.0, 20.0)", "min(hours * 2.0, 30.0)")},
         [(90,), (45,), (2000,)]),

    Case("letter_grade", "letter_grade", '''def letter_grade(score):
    """Letter grade:
    - 90 or above is "A", 80 to 89 is "B", 70 to 79 is "C", 60 to 69 is "D", below 60 is "F".
    - A score below 0 or above 100 is invalid: status "error" with grade "N/A".
    """
    if score < 0 or score > 100:
        return {"status": "error", "grade": "N/A"}
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"
    return {"status": "ok", "grade": grade}
''', {"a_exclusive": ("score >= 90", "score > 90"),
      "b_from_85": ("score >= 80", "score >= 85")},
         [(90,), (82,)], numeric=False),
]


def _call(source, func, args):
    ns = {}
    exec(source, ns)  # trusted: these are our own evaluation cases
    return ns[func](*args)


def verify_cases(cases=None):
    """Deterministic check (no model needed): every mutant must differ from its clean version on at least one probe."""
    problems = []
    for c in (CASES if cases is None else cases):
        for m in c.mutants:
            src = c.mutant_source(m)
            if not any(_call(c.source, c.func, p) != _call(src, c.func, p) for p in c.probes):
                problems.append(f"{c.name}/{m}: no probe distinguishes it from the clean version")
    return problems