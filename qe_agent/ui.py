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
.tn {font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-weight:700
