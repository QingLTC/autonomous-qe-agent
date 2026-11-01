"""Autonomous QE Agent - Streamlit UI. All logic lives in the qe_agent package."""
import os
import re
import shutil

import streamlit as st

from qe_agent import llm, ui
from qe_agent.generate import apply_contract_drift, generate_tests
from qe_agent.presets import load_presets, save_presets
from qe_agent.sandbox import parse_coverage, run_pytest_suite_with_cov
from qe_agent.spec import REFERENCE, build_reference, extract_function_name, get_spec
from qe_agent.triage import align_to_spec, audit_passing_tests, changed_tests, heal_suite
from qe_agent.ui import add_log, card, render_diff_card, render_findings, render_log_card, summarize

st.set_page_config(page_title="Autonomous QE Agent", page_icon="🤖", layout="wide")
ui.inject_css()
st.markdown(ui.brand_badge(llm.MODEL_NAME), unsafe_allow_html=True)
st.title("Autonomous QE Agent")
st.caption("Generates tests with Meta Llama, checks them against the written spec, and flags suspected source bugs.")

if "presets" not in st.session_state:
    st.session_state.presets = load_presets()

preset_keys = list(st.session_state.presets.keys())
if "current_preset_key" not in st.session_state or st.session_state.current_preset_key not in preset_keys:
    st.session_state.current_preset_key = preset_keys[0]

if "pending_toast" in st.session_state:
    msg, icon = st.session_state.pending_toast
    ui.toast(msg, icon)
    del st.session_state["pending_toast"]

def on_preset_change():
    chosen = st.session_state.preset_selector
    st.session_state.current_preset_key = chosen
    st.session_state.code_editor = st.session_state.presets.get(chosen, "")

def on_save_preset():
    name = st.session_state.preset_name_input.strip()
    code = st.session_state.code_editor
    if name:
        st.session_state.presets[name] = code
        save_presets(st.session_state.presets)
        st.session_state.current_preset_key = name
        st.session_state.pending_toast = (f"Saved '{name}'", "💾")
    else:
        st.session_state.pending_toast = ("Preset name cannot be empty.", "⚠️")

def on_delete_preset():
    selected = st.session_state.current_preset_key
    if len(st.session_state.presets) <= 1:
        st.session_state.pending_toast = ("Cannot delete the last remaining preset.", "⚠️")
        return
    if selected in st.session_state.presets:
        del st.session_state.presets[selected]
        save_presets(st.session_state.presets)
        remaining = list(st.session_state.presets.keys())
        st.session_state.current_preset_key = remaining[0]
        st.session_state.code_editor = st.session_state.presets[remaining[0]]
        st.session_state.pending_toast = (f"Deleted '{selected}'", "🗑️")

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Code under test")

    current_keys = list(st.session_state.presets.keys())
    selected_index = current_keys.index(st.session_state.current_preset_key)

    selected_preset = st.selectbox(
        "Preset",
        options=current_keys,
        index=selected_index,
        key="preset_selector",
        on_change=on_preset_change
    )

    if "code_editor" not in st.session_state:
        st.session_state.code_editor = st.session_state.presets.get(st.session_state.current_preset_key, "")

    target_code = st.text_area(
        "Python function (a docstring describing the rules is used as the spec)",
        height=240,
        key="code_editor"
    )

    with st.expander("Manage Benchmark Presets (Save / Update / Delete)", expanded=False):
        st.text_input("Preset Name:", value=st.session_state.current_preset_key, key="preset_name_input")
        col_crud1, col_crud2 = st.columns(2)
        with col_crud1:
            st.button("Save / Update Preset", use_container_width=True, on_click=on_save_preset)
        with col_crud2:
            st.button("Delete Selected Preset", use_container_width=True, on_click=on_delete_preset)

    simulate_drift = st.checkbox(
        "Simulate contract drift (demo)",
        value=False,
        help="SIMULATED: rewrites some generated assertions to mimic an outdated contract, so the triage loop can be demoed."
    )
    start_btn = st.button("Run analysis", type="primary", use_container_width=True)

with col_right:
    st.subheader("Results")
    pipeline_status = st.empty()
    metrics_placeholder = st.empty()
    show_status = lambda *a: ui.show_status(pipeline_status, *a)
    show_progress = lambda n: ui.show_progress(pipeline_status, n)
    show_metrics = lambda *a: ui.show_metrics(metrics_placeholder, *a)
    if not start_btn:
        show_status("Ready", "Pick a preset or paste a function, then run the analysis.", "info")

if start_btn:
    for f in ["test_generated_cases.py", "test_healed_cases.py", "target_module.py", ".coverage"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass

    if os.path.exists("__pycache__"):
        try:
            shutil.rmtree("__pycache__")
        except OSError:
            pass

    target_code = target_code.strip()
    func_name = extract_function_name(target_code)
    if not func_name:
        st.error("No `def` found in the code under test.")
        st.stop()
    test_filename = "test_generated_cases.py"

    with open("target_module.py", "w", encoding="utf-8") as f:
        f.write(target_code)

    log_slot = st.empty()
    LOGS = []
    show_progress(0)

    try:
        initial_test_code = generate_tests(target_code, func_name)
        if simulate_drift:
            initial_test_code = apply_contract_drift(initial_test_code, target_code)

        with open(test_filename, "w", encoding="utf-8") as f:
            f.write(initial_test_code)

        add_log(LOGS, "Initial Generated Test Suite", "", f"{len(re.findall(r'def test_', initial_test_code))} Tests", "gray", initial_test_code)

    except Exception as e:
        pipeline_status.error(f"Generation error: {e}")
        st.stop()

    show_progress(1)
    result = run_pytest_suite_with_cov(test_filename)
    cov_rate = parse_coverage(result.stdout)
    REFERENCE["code"] = None
    if get_spec(target_code, func_name):
        show_progress(1)
        REFERENCE["code"] = build_reference(target_code, func_name, get_spec(target_code, func_name), initial_test_code)
        add_log(LOGS, "Spec-derived Reference Implementation", f"(written by {llm.MODEL_NAME})", "Generated" if REFERENCE["code"] else "Not available",
                "blue" if REFERENCE["code"] else "amber", REFERENCE["code"] or "# the model did not produce a runnable reference")
    audit = audit_passing_tests(target_code, func_name, initial_test_code, set(re.findall(r"::(test_\w+)\s+PASSED", result.stdout)))

    if result.returncode == 0:
        if audit:
            show_status("Passed, but spec conflicts found", f"{len(audit)} passing test(s) contradict the spec; the source may encode a bug.", "warn")
        else:
            show_status("All tests passed", "The generated tests passed on the first run.", "ok")
        show_metrics(cov_rate, 0, len(audit))

        if audit:
            st.markdown(card("Spec audit of passing tests", render_findings(audit), f"{len(audit)} inconsistenc" + ("y" if len(audit) == 1 else "ies"), "red"), unsafe_allow_html=True)
        export_code = align_to_spec(initial_test_code, func_name, audit) if audit else initial_test_code
        if audit:
            old_txt, new_txt, changed_names = changed_tests(initial_test_code, export_code)
            st.markdown(render_diff_card(old_txt, new_txt, changed_names), unsafe_allow_html=True)
        st.download_button(
            label="Download tests (spec-aligned)" if audit else "Download Validated Test Suite (.py)",
            data=export_code,
            file_name="test_generated_cases.py",
            mime="text/x-python",
            help="Spec-conflicting tests were rewritten to the spec-derived value; they fail until the source bug is fixed." if audit else None,
        )
        n_pass0 = len(set(re.findall(r"::(test_\w+)\s+PASSED", result.stdout)))
        add_log(LOGS, "Pytest Report & Coverage Log", "", f"{n_pass0} passed", "green", result.stdout)
        log_slot.markdown(render_log_card(LOGS), unsafe_allow_html=True)
    else:
        n_fail0 = len(set(re.findall(r"::(test_\w+)\s+FAILED", result.stdout)))
        add_log(LOGS, "Initial Failure Traceback (Pytest Log)", "", f"{n_fail0} Failure(s)", "red", result.stdout)

        show_progress(2)
        failing = set(re.findall(r"::(test_\w+)\s+FAILED", result.stdout)) | set(re.findall(r"FAILED\s+\S+::(test_\w+)", result.stdout))
        repaired_test_code, findings = heal_suite(target_code, func_name, initial_test_code, failing)

        with open(test_filename, "w", encoding="utf-8") as f:
            f.write(repaired_test_code)
        shutil.rmtree("__pycache__", ignore_errors=True)

        final_result = run_pytest_suite_with_cov(test_filename)
        cov_final = parse_coverage(final_result.stdout)
        n_fixed = sum(1 for x in findings if x["verdict"] == "fix_test")
        n_flagged = len(findings) - n_fixed
        all_green = final_result.returncode == 0

        if all_green and not audit:
            status, delta = "HEALED & PASSED", "Self-Healed"
            show_status("Failing tests corrected", f"{n_fixed} test expectation(s) were wrong; no source bug suspected.", "ok")
        elif n_flagged or audit:
            status, delta = "BUGS SUSPECTED", "Review needed"
            show_status("Possible source bug", summarize(n_fixed, n_flagged, len(audit)), "warn")
        else:
            status, delta = "UNRESOLVED", "Failed"
            show_status("Could not triage the failures", "See the pytest log for details.", "bad")

        show_metrics(cov_final, n_fixed, n_flagged + len(audit))

        if findings:
            st.markdown(card("Failure triage", render_findings(findings), f"{len(findings)} failing", "gray"), unsafe_allow_html=True)
        if audit:
            st.markdown(card("Spec audit of passing tests", render_findings(audit), f"{len(audit)} inconsistenc" + ("y" if len(audit) == 1 else "ies"), "red"), unsafe_allow_html=True)

        export_code = align_to_spec(repaired_test_code, func_name, audit) if audit else repaired_test_code
        if n_fixed or audit:
            old_txt, new_txt, changed_names = changed_tests(initial_test_code, export_code)
            st.markdown(render_diff_card(old_txt, new_txt, changed_names), unsafe_allow_html=True)

        if all_green:
            st.download_button(
                label="Download tests (spec-aligned)" if audit else "Download corrected tests (.py)",
                data=export_code,
                file_name="test_healed_cases.py",
                mime="text/x-python",
                help="Spec-conflicting tests were rewritten to the spec-derived value; they fail until the source bug is fixed." if audit else None,
            )
        n_fail1 = len(set(re.findall(r"::(test_\w+)\s+FAILED", final_result.stdout)))
        n_pass1 = len(set(re.findall(r"::(test_\w+)\s+PASSED", final_result.stdout)))
        add_log(LOGS, "Final Pytest Report & Coverage Log", "", f"{n_pass1} passed" if all_green else f"{n_fail1} failed", "green" if all_green else "red", final_result.stdout)
        log_slot.markdown(render_log_card(LOGS), unsafe_allow_html=True)