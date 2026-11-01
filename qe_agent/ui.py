"""Presentation helpers: CSS, cards, diff view, log card. Streamlit is imported lazily."""
import difflib
import html
import re
import time

CSS = """
<style>
:root {--meta:#0866FF; --line:#E2E8F0; --shadow:0 1px 3px rgba(15,23,42,.08), 0 1px 2px rgba(15,23,42,.04);}
.stApp {background:#F8FAFC;}
.block-container {padding-top:3.6rem; max-width:1280px;}
h1 {font-size:1.9rem !important; font-weight:650 !important; letter-spacing:-.01em;}
button[kind="primary"], [data-testid="stBaseButton-primary"] {background:var(--meta) !important; border-color:var(--meta) !important; color:#fff !important; box-shadow:var(--shadow);}
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {filter:brightness(1.08);}
[data-testid="stExpander"] {background:#fff; border:1px solid var(--line) !important; border-radius:10px; box-shadow:var(--shadow);}
.brand {display:inline-flex; align-items:center; gap:8px; background:rgba(8,102,255,.08); color:#0866FF; border:1px solid rgba(8,102,255,.25); padding:3px 12px; border-radius:999px; font-size:.8rem; font-weight:600; margin-bottom:.4rem;}
.brand i {width:7px; height:7px; border-radius:50%; background:#0866FF; display:inline-block;}
.status-card {display:flex; gap:12px; align-items:flex-start; background:var(--bg); border:1px solid var(--line); border-left:4px solid var(--c); border-radius:12px; padding:.9rem 1.1rem; margin-bottom:.7rem;}
.status-card .ic {flex:none; width:22px; height:22px; border-radius:50%; background:var(--c); color:#fff; font-weight:700; font-size:.8rem; display:flex; align-items:center; justify-content:center; margin-top:2px;}
.status-card .t {font-size:1.1rem; font-weight:650;}
.status-card .s {color:#475569; font-size:.9rem; margin-top:2px;}
.status-card .s b {color:#0F172A;}
.mgrid {display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:.8rem;}
.mc {display:flex; justify-content:space-between; align-items:center; background:#fff; border:1px solid var(--line); border-radius:12px; box-shadow:var(--shadow); padding:.75rem .95rem;}
.ml {font-size:.7rem; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:#64748B;}
.mv {font-size:1.8rem; font-weight:700; line-height:1.25; color:#0F172A;}
.mv.b {color:#1f6feb;} .mv.a {color:#d97706;}
.mc2 {font-size:.74rem; color:#64748B;} .mc2.g {color:#059669;} .mc2.b {color:#1f6feb;} .mc2.a {color:#d97706;}
.mi {width:34px; height:34px; border-radius:9px; display:flex; align-items:center; justify-content:center; font-weight:700;}
.mi.bl {background:#EAF2FF; color:#1f6feb;} .mi.am {background:#FEF3C7; color:#d97706;}
.steps {display:flex; gap:8px; margin:.2rem 0 .7rem;}
.step {flex:1; padding:.55rem .7rem; border:1px solid var(--line); border-radius:10px; background:#fff; font-size:.78rem; color:#64748B;}
.step b {display:block; color:#0F172A; font-size:.85rem;}
.step.done {border-color:rgba(45,164,78,.45);}
.step.done b::before {content:"✓ "; color:#2da44e;}
.step.on {border-color:var(--meta); box-shadow:0 0 0 3px rgba(8,102,255,.12); background:linear-gradient(90deg,#fff 0%,#EAF2FF 50%,#fff 100%); background-size:200% 100%; animation:shimmer 1.6s linear infinite;}
@keyframes shimmer {from {background-position:200% 0;} to {background-position:-200% 0;}}
.card {background:#fff; border:1px solid var(--line); border-radius:12px; box-shadow:var(--shadow); padding:1rem 1.2rem; margin-bottom:1rem;}
.sec {display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:.7rem;}
.sec .st {font-size:.8rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:#334155;}
.sec .ss {font-size:.8rem; color:#64748B; margin-top:2px;}
.tag {display:inline-block; padding:2px 10px; border-radius:6px; font-size:.74rem; font-weight:600; border:1px solid transparent; white-space:nowrap;}
.tag.gray {background:#F1F5F9; color:#475569; border-color:#E2E8F0;}
.tag.blue {background:#EFF6FF; color:#1d4ed8; border-color:#BFDBFE;}
.tag.red {background:#FEF2F2; color:#b91c1c; border-color:#FECACA;}
.tag.green {background:#F0FDF4; color:#047857; border-color:#BBF7D0;}
.tag.amber {background:#FFFBEB; color:#b45309; border-color:#FDE68A;}
.card.lgs {padding:0; overflow:hidden;}
details.lg {border-bottom:1px solid #EEF2F7;}
details.lg:last-child {border-bottom:none;}
details.lg summary {list-style:none; cursor:pointer; display:flex; align-items:center; gap:8px; padding:.8rem 1.1rem; font-size:.92rem;}
details.lg summary::-webkit-details-marker {display:none;}
details.lg summary::before {content:"›"; color:#94A3B8; font-size:1.15rem; transition:transform .15s;}
details.lg[open] summary::before {transform:rotate(90deg);}
details.lg .lsub {color:#1f6feb; font-size:.85rem;}
details.lg summary .tag {margin-left:auto;}
.code {background:#F8FAFC; border-top:1px solid #EEF2F7; font:.78rem/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; max-height:340px; overflow:auto; padding:.6rem 0;}
.cl {white-space:pre; padding-right:1.1rem;}
.cn {display:inline-block; width:3em; text-align:right; padding-right:.9em; color:#94A3B8; user-select:none;}
.pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:600; white-space:nowrap; border:1px solid transparent;}
.pill.fix {background:#EFF6FF; color:#1d4ed8; border-color:#BFDBFE;}
.pill.bug {background:#FEF2F2; color:#b91c1c; border-color:#FECACA;}
.pill.review {background:#FFFBEB; color:#b45309; border-color:#FDE68A;}
table.triage {width:100%; border-collapse:separate; border-spacing:0; border:1px solid var(--line); border-radius:10px; overflow:hidden; font-size:.88rem;}
table.triage th {text-align:left; font-weight:500; color:#64748B; padding:9px 12px; border-bottom:1px solid var(--line); background:#F8FAFC;}
table.triage td {padding:11px 12px; border-bottom:1px solid #EEF2F7; vertical-align:top;}
table.triage tr:last-child td {border-bottom:none;}
.tn {font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-weight:700; color:#1f6feb;}
.by {font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:.8rem; color:#64748B;}
code.num {background:#ECFDF5; color:#047857; padding:1px 6px; border-radius:5px; font-size:.82rem;}
code.err {background:#FDF2F8; color:#be185d; padding:1px 6px; border-radius:5px; font-size:.82rem;}
code.tn {background:#EFF6FF; padding:1px 6px; border-radius:5px; font-size:.8rem;}
.diff-wrap {display:grid; grid-template-columns:1fr 1fr; gap:12px;}
.diff-col {border:1px solid var(--line); border-radius:10px; overflow-x:auto; font:.82rem/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; padding-bottom:6px;}
.dh {display:flex; justify-content:space-between; padding:7px 12px; margin-bottom:6px; background:#F8FAFC; border-bottom:1px solid var(--line); font:600 .78rem sans-serif; color:#334155;}
.dh .neg {color:#dc2626;} .dh .pos {color:#059669;}
.ln {padding:0 12px 0 9px; white-space:pre; border-left:3px solid transparent;}
.ln.del {background:#FEF2F2; border-left-color:#F87171;}
.ln.add {background:#F0FDF4; border-left-color:#34D399;}
.ln.pad {background:#F1F5F9;}
.ln mark {color:inherit; border-radius:3px;}
.ln.del mark {background:#FECACA;} .ln.add mark {background:#BBF7D0;}
.sg {display:inline-block; width:1.3em; color:#94A3B8;}
.app-toast {position:fixed; top:22px; left:50%; transform:translateX(-50%); z-index:999999; background:#0F172A; color:#fff; padding:10px 18px; border-radius:10px; box-shadow:0 8px 24px rgba(15,23,42,.25); font-size:.92rem; pointer-events:none; opacity:0; animation:toast 3.2s ease forwards;}
.app-toast.ok {border-left:4px solid #2da44e;} .app-toast.warn {border-left:4px solid #d29922;}
@keyframes toast {0% {opacity:0; transform:translate(-50%,-10px);} 10%,80% {opacity:1; transform:translate(-50%,0);} 100% {opacity:0; transform:translate(-50%,-6px); visibility:hidden;}}
footer {visibility:hidden;}
</style>
"""

TONES = {"ok": "#2da44e", "warn": "#d29922", "bad": "#cf222e", "info": "#1f6feb"}
VERDICTS = {"fix_test": ("Test corrected", "fix"), "report_bug": ("Suspected bug", "bug"),
            "needs_review": ("Needs review", "review"), "spec_conflict": ("Spec conflict", "bug")}


def inject_css():
    import streamlit as st
    st.markdown(CSS, unsafe_allow_html=True)


def brand_badge(model):
    return f"<div class='brand'><i></i>Powered by Meta Llama · {html.escape(model)}</div>"


def toast(msg, icon):
    """Self-dismissing message (pure CSS animation, ~3 s)."""
    import streamlit as st
    tone = "warn" if icon == "⚠️" else "ok"
    st.markdown(f"<div class='app-toast {tone}' data-n='{time.time_ns()}'>{icon} {html.escape(msg)}</div>", unsafe_allow_html=True)


def _tok(s):
    return re.findall(r"\w+|\s+|[^\w\s]", s)

def _inline(o, n):
    a, b = _tok(o), _tok(n)
    ho, hn = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        x, y = html.escape("".join(a[i1:i2])), html.escape("".join(b[j1:j2]))
        if tag == "equal":
            ho.append(x); hn.append(y)
        else:
            if x: ho.append(f"<mark>{x}</mark>")
            if y: hn.append(f"<mark>{y}</mark>")
    return "".join(ho), "".join(hn)

def esc(s):
    return html.escape(str(s)).replace("$", "&#36;")

def card(title, inner, tag="", tone="gray", sub=""):
    t = f"<span class='tag {tone}'>{esc(tag)}</span>" if tag else ""
    s = f"<div class='ss'>{sub}</div>" if sub else ""
    return f"<div class='card'><div class='sec'><div><div class='st'>{esc(title)}</div>{s}</div>{t}</div>{inner}</div>"

def render_diff_card(old_text, new_text, names):
    a, b = old_text.splitlines(), new_text.splitlines()
    L, R = [], []
    ln = lambda cls, t, g=" ": f"<div class='ln {cls}'><span class='sg'>{g}</span>{t or '&nbsp;'}</div>"
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            for s in a[i1:i2]:
                L.append(ln("", html.escape(s))); R.append(ln("", html.escape(s)))
            continue
        old, new = a[i1:i2], b[j1:j2]
        for k in range(max(len(old), len(new))):
            o = old[k] if k < len(old) else None
            n = new[k] if k < len(new) else None
            if o is not None and n is not None:
                ho, hn = _inline(o, n)
                L.append(ln("del", ho, "-")); R.append(ln("add", hn, "+"))
            elif o is not None:
                L.append(ln("del", html.escape(o), "-")); R.append(ln("pad", ""))
            else:
                L.append(ln("pad", "")); R.append(ln("add", html.escape(n), "+"))
    n_del = sum("ln del" in x for x in L)
    n_add = sum("ln add" in x for x in R)
    lines = lambda k: f"{k} line" + ("" if k == 1 else "s")
    cols = (f"<div class='diff-wrap'><div class='diff-col'><div class='dh'><span>Original</span><span class='neg'>-{lines(n_del)}</span></div>{''.join(L)}</div>"
            f"<div class='diff-col'><div class='dh'><span>After triage</span><span class='pos'>+{lines(n_add)}</span></div>{''.join(R)}</div></div>")
    sub = "Side-by-side comparison for " + ", ".join(f"<code class='tn'>{html.escape(x)}()</code>" for x in names)
    return card("Corrected tests (before / after)", cols, sub=sub).replace("$", "&#36;")


def add_log(logs, title, sub, tag, tone, body):
    logs.append((title, sub, tag, tone, body))


def render_log_card(logs):
    rows = ""
    for title, sub, tag, tone, body in logs:
        t = f"<span class='tag {tone}'>{esc(tag)}</span>" if tag else ""
        lines = body.replace(chr(13), "").split(chr(10))
        code = "".join(f"<div class='cl'><span class='cn'>{i}</span>{html.escape(x) or '&nbsp;'}</div>" for i, x in enumerate(lines, 1))
        rows += (f"<details class='lg'><summary><span class='lt'>{esc(title)}</span><span class='lsub'>{esc(sub)}</span>{t}</summary>"
                 f"<div class='code'>{code}</div></details>").replace("$", "&#36;")
    return f"<div class='card lgs'>{rows}</div>"

ICONS = {"ok": "✓", "warn": "!", "bad": "✕", "info": "i"}

BGS = {"ok": "#F0FDF4", "warn": "#FFFBEB", "bad": "#FEF2F2", "info": "#EFF6FF"}

def status_card(title, subtitle, tone):
    sub = re.sub(r"\b(\d+)\b", r"<b>\1</b>", esc(subtitle))
    return (f"<div class='status-card' style='--c:{TONES[tone]};--bg:{BGS[tone]}'><div class='ic'>{ICONS[tone]}</div>"
            f"<div><div class='t'>{esc(title)}</div><div class='s'>{sub}</div></div></div>")


def show_status(slot, title, subtitle, tone):
    slot.markdown(status_card(title, subtitle, tone), unsafe_allow_html=True)


def show_progress(slot, active):
    names = ["Generate tests", "Run & verify", "Triage & audit"]
    subs = ["Llama writes pytest cases", "Sandboxed pytest + spec reference", "Compare against the spec"]
    cards = "".join(f"<div class='step {'done' if i < active else 'on' if i == active else ''}'><b>{names[i]}</b>{subs[i]}</div>" for i in range(3))
    slot.markdown(f"<div class='steps'>{cards}</div>", unsafe_allow_html=True)


def show_metrics(slot, coverage, corrected, review):
    try:
        pct = max(0, min(100, int(str(coverage).rstrip("%"))))
        ring = ("<svg width='46' height='46' viewBox='0 0 40 40'><circle cx='20' cy='20' r='15' fill='none' stroke='#E2E8F0' stroke-width='5'/>"
                f"<circle cx='20' cy='20' r='15' fill='none' stroke='#10B981' stroke-width='5' stroke-linecap='round' "
                f"stroke-dasharray='{pct * 0.9425:.1f} 94.25' transform='rotate(-90 20 20)'/></svg>")
    except ValueError:
        ring = ""
    cards = (f"<div class='mc'><div><div class='ml'>Coverage</div><div class='mv'>{esc(coverage)}</div><div class='mc2 g'>Line coverage</div></div>{ring}</div>"
             f"<div class='mc'><div><div class='ml'>Tests corrected</div><div class='mv b'>{corrected}</div><div class='mc2 b'>Expectations updated</div></div><div class='mi bl'>✓</div></div>"
             f"<div class='mc'><div><div class='ml'>Need review</div><div class='mv {'a' if review else ''}'>{review}</div><div class='mc2 {'a' if review else ''}'>Needs a human look</div></div><div class='mi am'>!</div></div>")
    slot.markdown(f"<div class='mgrid'>{cards}</div>", unsafe_allow_html=True)

def summarize(n_fixed, n_flagged, n_audit):
    parts = []
    if n_fixed:
        parts.append(f"{n_fixed} failing test(s) corrected")
    if n_flagged:
        parts.append(f"{n_flagged} failing test(s) need review")
    if n_audit:
        parts.append(f"{n_audit} passing test(s) contradict the spec")
    return "; ".join(parts) + "."

def chip(text):
    s = esc(text)
    s = re.sub(r"\((\w*Error:[^)]*)\)", lambda m: f"(<code class='err'>{m.group(1)}</code>)", s)
    return re.sub(r"\b(\w+=-?\d+(?:\.\d+)?)", r"<code class='num'>\1</code>", s)

def render_findings(rows):
    body = ""
    for r in rows:
        label, cls = VERDICTS.get(r["verdict"], (r["verdict"], "review"))
        who = r["decided by"] + (f" · {r['basis']}" if r.get("basis") else "")
        body += (f"<tr><td><span class='tn'>{esc(r['test'])}</span></td><td><span class='pill {cls}'>{label}</span></td>"
                 f"<td class='by'>{esc(who)}</td><td>{chip(r['reason'])}</td></tr>")
    return ("<table class='triage'><thead><tr><th>Test</th><th>Verdict</th><th>Decided by</th><th>Reason</th></tr></thead>"
            f"<tbody>{body}</tbody></table>")