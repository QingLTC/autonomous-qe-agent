# Autonomous QE Agent

**An AI test engineer that does not just make tests pass.** It generates tests with Meta Llama, writes an *independent* reference implementation from the function's written spec (its docstring), and uses it to tell apart *"the test is wrong"* from *"the code is wrong"*.

Everything runs locally on open-weight Meta models (Llama 3.2 3B by default, Llama 3.1 8B optional) through Ollama. Your source code never leaves your machine.

> Track: Indie Developer (solo) - Meta Global AI Developer Hackathon, 2026

## The problem

LLM-generated tests are often wrong, and a common "self-healing" fix makes things worse: when a test fails, rewrite its assertion to whatever the code currently returns. The suite turns green and **a real bug is silently turned into "expected behaviour".**

In our own measurements (Llama 3.2 3B), in every run where an injected bug was **missed**, all 78 tests whose input exposed the bug had a wrong expected value (see *Evaluation*). Naively rewriting those tests to match the code would have hidden every one of those bugs.

## What it does

1. **Generates** pytest tests for a Python function with Llama.
2. **Runs** them (isolated subprocess, timeouts, coverage).
3. **Writes a reference implementation from the docstring alone** - the model never sees the function body.
4. **Triages every failing test** by comparing three things in code: the source's output, the test's expectation, and the reference's output.
   - source = reference -> the *test* was wrong -> corrected;
   - test = reference but source differs -> **suspected source bug**, the test is left failing on purpose;
   - all three disagree -> *needs review* (no auto-fix).
5. **Audits the tests that pass**: a passing test can also encode a bug. If its expectation contradicts the spec-derived value, it is flagged as a *spec conflict*.
6. **Exports a spec-aligned test suite**: conflicting tests are rewritten to the spec value, so they fail until the bug is fixed.

Guardrails: crashes and negative numeric outputs are treated as bugs, not healed; outputs without numbers are never auto-corrected (they are sent to *needs review*); error-handling cases the spec does not describe are never flagged as bugs.

The UI shows the Llama-written reference, a verdict table with *who decided and why*, and a side-by-side diff of every changed test.

## Meta models used

| Model | Role |
|---|---|
| Llama 3.2 3B (default, via Ollama) | test generation, reference implementation |
| Llama 3.1 8B (optional, via Ollama) | same, used for the size comparison below |

## Evaluation

We built a small benchmark: each function has a docstring spec, a clean version and several versions with one injected bug (wrong operator, wrong coefficient, wrong rounding, shifted boundary...). Every injected bug is verified to change behaviour. We then ran the full pipeline and counted:

- **Reference accuracy** - share of test inputs on which the Llama-written reference returns the same numbers as the true (clean) function.
- **Bugs found** - an injected bug counts only if a flagged test uses an input that really exposes it **and** that input was not already flagged on the clean version of the same run (so a wrong reference cannot get credit twice).
- **False alarms** - clean versions that were flagged anyway.

Main set: 7 numeric functions x (clean + 3 bugs) + 1 text-output function (clean + 2 bugs). Held-out set: 4 numeric functions x (clean + 3 bugs), **written after looking at the first results and never used for tuning**, run once at the end. 95% intervals are Wilson intervals; runs of the same bug are not independent, so treat them as optimistic.

| | Llama 3.2 3B | Llama 3.1 8B |
|---|---|---|
| **Main set** - bugs found | 38/63 = 60% (48-71%) | 25/42 = 60% (44-73%) |
| **Main set** - false alarms on clean code | 5/21 = 24% (11-45%) | 3/14 = 21% (8-48%) |
| **Held-out set** - bugs found | 10/36 = 28% (16-44%) | 5/12 = 42% (19-68%) |
| **Held-out set** - false alarms | 3/12 = 25% (9-53%) | 0/4 = 0% (0-49%) |
| Reference implementation accuracy (main / held-out) | 82% / 70% | 94% / 87% |
| Median time per analysed version | 8.6 s | 23.0 s |

Raw results of every run (generated tests, reference code, flagged tests) are in `evaluation/results/`.

What we learned:

- **The numbers on the set we looked at were optimistic.** On the held-out functions the 3B model found 28% instead of 60%. Those functions are not identical in difficulty, but we report the lower number as the honest estimate.
- **The 8B model writes a better reference (94% vs 82%) but did not improve end-to-end results** on the main set (60% in both). In the 3B main-set misses, the generated *tests* were the problem: they did not use an input that exposes the bug (12 of 25 misses) or all such tests had a wrong expected value (the other 13).
- **False alarms are systematic, not random.** In the 3B main set all 5 were traced to a wrong reference implementation, on the same two functions (parking fee with "started hours": wrong in 3 of 3 runs; ticket price with overlapping age/student rules: 2 of 3). We did not trace the false alarms of the other runs.
- **We explored a more sensitive rule** (also flag when test, source and reference all disagree). Replayed on the saved runs it finds more bugs, but its false-alarm cost grows quickly as the reference gets worse:

  | Rule | 3B main | 8B main | 3B held-out | 8B held-out (n=4 clean) |
  |---|---|---|---|---|
  | shipped (precision first): bugs / false alarms | 60% / 24% | 60% / 21% | 28% / 25% | 42% / 0% |
  | + "all three disagree": bugs / false alarms | 75% / 38% | 76% / 21% | 75% / 92% | 92% / 50% |

  We did **not** ship it: with the 3B model it would flag 11 of 12 clean held-out versions.

## Limitations

- Needs a **docstring that states the rules**; without it only a low-confidence fallback runs.
- Compares **numeric outputs only**. Text or boolean results cannot be checked (0 of 6 injected bugs found with 3B, 0 of 4 with 8B); where such tests fail they go to *needs review* and are never auto-corrected.
- Small local models make arithmetic mistakes, especially at boundaries. A wrong reference causes false alarms and missed bugs, so every verdict shows its evidence for a human to confirm.
- Designed for pure functions with simple arguments.
- Generated code is executed in a subprocess with timeouts. This is **not a hardened sandbox**; do not run untrusted code.
- Local demo only (no hosted instance), because the models run on your machine.

## Run it

```bash
pip install -r requirements.txt
ollama pull llama3.2:3b            # optional: ollama pull llama3.1:8b
streamlit run app.py
```

Paste a function with a docstring spec, or pick a preset, and press **Run analysis**.

Configuration (environment variables): `LLM_MODEL` (default `llama3.2:3b`), `LLM_BASE_URL` (default `http://localhost:11434/v1`), `LLM_API_KEY`, `LLM_TIMEOUT` (seconds, default 120). On Windows use `set LLM_MODEL=llama3.1:8b`.

Reproduce the evaluation (model running):

```bash
python -m evaluation.run_eval --verify-only                 # no model needed
python -m evaluation.run_eval --repeats 3                    # main set
python -m evaluation.run_eval --heldout --repeats 3          # held-out set
python -m evaluation.run_eval --model llama3.1:8b --repeats 2
```

## Project layout

```
autonomous-qe-agent
├── app.py                   # Streamlit UI (flow only)
├── qe_agent/
|   ├── llm.py               # Model configuration
|   ├── generate.py          # Test generation (+ simulated contract drift for demos)
|   ├── sandbox.py           # Subprocess execution, pytest, coverage
|   ├── spec.py              # Docstring spec, reference implementation, numeric comparison
|   ├── triage.py            # Failure triage, spec audit, healing, spec-aligned export
|   ├── ui.py                # Styling and HTML components
|   └── presets.py           # Presets
├── evaluation/
|   ├── cases.py             # Main benchmark (functions, injected bugs, probes)
|   ├── heldout_cases.py     # Held-out benchmark
|   └── run_eval.py          # Evaluation harness
└──  results/                # Raw results of the runs reported above
```
