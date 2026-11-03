"""Print a markdown results table from saved result files (no model needed).

    python -m evaluation.make_table main=evaluation/results/main_muse.json heldout=evaluation/results/heldout_muse.json
"""
import json
import sys


def pct(a, b):
    return f"{a} / {b} ({100 * a / b:.0f}%)" if b else "n/a"


def main(args):
    rows = []
    for arg in args:
        label, path = arg.split("=", 1)
        runs = [r for r in json.load(open(path, encoding="utf-8"))]
        ok = [r for r in runs if not r["error"]]
        num = [r for r in ok if r["numeric"]]
        mut = [r for r in num if r["variant"] != "clean"]
        cln = [r for r in num if r["variant"] == "clean"]
        txt = [r for r in ok if not r["numeric"] and r["variant"] != "clean"]
        secs = sorted(r["seconds"] for r in ok)
        rows.append((label, pct(sum(r["targeted"] for r in mut), len(mut)), pct(sum(r["flagged"] for r in cln), len(cln)),
                     pct(sum(r["targeted"] for r in txt), len(txt)) if txt else "-", f"{secs[len(secs) // 2]:.1f} s", f"{len(runs) - len(ok)}"))
    print("| Set | Bugs found | False alarms on clean code | Text-output bugs found | Median time per version | Errors |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(r) + " |")


if __name__ == "__main__":
    main(sys.argv[1:])
