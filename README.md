# Autonomous QE Agent

**An AI test engineer that does not just make tests pass.** It generates tests with Meta Llama, writes an *independent* reference implementation from the function's written spec (its docstring), and uses it to tell apart *"the test is wrong"* from *"the code is wrong"*.

Everything runs locally on open-weight Meta models (Llama 3.2 3B by default, Llama 3.1 8B optional) through Ollama. Your source code never leaves your machine.

> Track: Indie Developer (solo) - Meta Global AI Developer Hackathon, 2026

<img width="1272" height="907" alt="image" src="https://github.com/user-attachments/assets/5dd224f1-390f-4eda-b7ed-0f4749d61450" />
<img width="1277" height="697" alt="image" src="https://github.com/user-attachments/assets/7c809b71-1733-441b-8f29-cf3c518cfbfe" />
<img width="1277" height="706" alt="image" src="https://github.com/user-attachments/assets/e5089832-9888-4f65-bd11-b5ceb33f3537" />

*Example run on preset 6 with Llama 3.2 3B; results vary between runs.*


## The problem

LLM-generated tests are often wrong, and a common "self-healing" fix makes it worse: when a test fails, rewrite its assertion to whatever the code currently returns. The suite turns green and a real bug becomes "expected behaviour". By construction, that approach can never report a bug. This agent is built to report one.

## What it does

1. **Generates** pytest tests for a Python function with Llama and runs them (isolated subprocess, timeouts, coverage).
2. **Writes a reference implementation from the docstring alone** - the model never sees the function body.
4. **Triages every failing test** by comparing three things in code: the source's output, the test's expectation, and the reference's output.
   - source = reference: the *test* was wrong, so it is corrected;
   - test = reference but source differs: **suspected source bug**, the test is left failing on purpose;
   - all three disagree: *needs review*, nothing is changed automatically.
5. **Audits the tests that pass**: a passing test can also encode a bug. If its expectation contradicts the spec-derived value, it is flagged as a *spec conflict*.
6. **Exports a spec-aligned test suite**: conflicting tests are rewritten to the spec value, so they fail until the bug is fixed.

Every verdict shows who decided, on what evidence (the numbers involved), and the Llama-written reference is visible in the UI. When the evidence is unclear the agent says so instead of guessing: crashes and negative outputs are treated as bugs, outputs without numbers are never auto-corrected, and error cases the spec does not describe are never flagged as bugs.

## Meta models used

| Model | Role |
|---|---|
| Llama 3.2 3B (default, via Ollama) | test generation, reference implementation |
| Llama 3.1 8B (optional, via Ollama) | same, used for the size comparison below |

Both are open-weight Meta models. The endpoint is configurable (LLM_BASE_URL) for any OpenAI-compatible server.

## Results

To measure it, each benchmark function has a docstring spec, a clean version, and versions with one injected bug (wrong operator, coefficient, rounding or boundary); every bug is checked to change behaviour. A bug counts as found only if a flagged test uses an input that really exposes it and that input was not already flagged on the clean version of the same run. A false alarm is a clean version that was flagged anyway.

The **main set** (31 versions) is the one we looked at while building. The **held-out set** (16 versions) was written afterwards, never used for tuning, and run once.

| | Llama 3.2 3B | Llama 3.1 8B |
|---|---|---|
| **Main set** - bugs found | 38/63 = 60% (48-71%) | 25/42 = 60% (44-73%) |
| **Main set** - false alarms on clean code | 5/21 = 24% (11-45%) | 3/14 = 21% (8-48%) |
| **Held-out set** - bugs found | 10/36 = 28% (16-44%) | 5/12 = 42% (19-68%) |
| **Held-out set** - false alarms | 3/12 = 25% (9-53%) | 0/4 = 0% (0-49%) |
| Reference implementation accuracy (main / held-out) | 82% / 70% | 94% / 87% |
| Median time per analysed version | 8.6 s | 23.0 s |

Samples are small and runs of the same bug are not independent, so read these as indicative (the 28% has a 95% interval of roughly 16-44%). What we take from them:

- **The held-out number is the one to trust.** On the functions we had already looked at, the 3B model found 60%; on new ones, 28%.
- **A bigger model is not automatically better.** 8B writes a more accurate reference (94% vs 82%) but found the same 60% on the main set.
- **Misses and false alarms trace back to the small model's arithmetic at boundaries.** In the 3B main-set misses, the generated tests either never used an input that exposes the bug (12 of 25) or all such tests had a wrong expected value (the other 13); the 5 false alarms were traced to wrong reference implementations. This is why every verdict shows its evidence for a human to confirm.
- **We explored a more sensitive rule** (also flag when test, source and reference all disagree).It finds more bugs but, with the 3B model, would have flagged 11 of 12 clean held-out versions, so we did not ship it.

Raw results of every run (generated tests, reference code, flagged tests) are in `evaluation/results/`.
``` bash
python -m evaluation.run_eval --report evaluation/results/heldout_3b.json
```

## Scope

- Works from a docstring that states the rules; without one only a low-confidence fallback runs.
- Compares numeric results. Text or boolean outputs are never auto-corrected; they go to needs review (0 of 6 text-output bugs were found).
- Meant for pure functions with simple arguments.
- Generated code runs in a subprocess with timeouts. This is not a hardened sandbox, so do not run untrusted code.

## Run it

```bash
pip install -r requirements.txt
ollama pull llama3.2:3b            # optional: ollama pull llama3.1:8b
streamlit run app.py
```

Pick a preset (preset 6 is the refund example with a seeded bug) or paste a function with a docstring spec, and press **Run analysis**.

Configuration (environment variables): `LLM_MODEL` (default `llama3.2:3b`), `LLM_BASE_URL` (default `http://localhost:11434/v1`), `LLM_API_KEY`, `LLM_TIMEOUT` (seconds, default 120). On Windows use `set LLM_MODEL=llama3.1:8b`.

Reproduce the evaluation (model running):

```bash
python -m evaluation.run_eval --verify-only                  # check the benchmark itself, no model
python -m evaluation.run_eval --repeats 3                    # main set
python -m evaluation.run_eval --heldout --repeats 3          # held-out set
python -m evaluation.run_eval --model llama3.1:8b --repeats 2
```

## Project layout

```
autonomous-qe-agent
├── app.py                   # Streamlit UI (flow only)
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
|   └──config.toml           # Light theme
├── qe_agent/
|   ├── __init__.py
|   ├── llm.py               # Model configuration
|   ├── generate.py          # Test generation (+ simulated contract drift for demos)
|   ├── sandbox.py           # Subprocess execution, pytest, coverage
|   ├── spec.py              # Docstring spec, reference implementation, numeric comparison
|   ├── triage.py            # Failure triage, spec audit, healing, spec-aligned export
|   ├── presets.py           # Example functions
|   └── ui.py                # Styling and HTML components
└── evaluation/
   ├── __init__.py
   ├── cases.py             # Main benchmark (functions, injected bugs, probes)
   ├── heldout_cases.py     # Held-out benchmark
   ├── run_eval.py          # Evaluation harness
   └──  results/            # Raw results of the runs reported above
        ├── main_3b.json
        ├── main_8b.json
        ├── heldout_3b.json
        └── heldout_8b.json
```
