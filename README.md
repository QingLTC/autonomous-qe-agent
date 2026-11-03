# Autonomous QE Agent
 
**An AI test engineer that does not just make tests pass.** It uses a Meta Muse model to generate tests, writes an *independent* reference implementation from the function's written spec (its docstring), and uses it to tell apart *"the test is wrong"* from *"the code is wrong"*.
 
> Track: Indie Developer (solo) - Meta Global AI Developer Hackathon, 2026

<img width="1567" height="837" alt="image" src="https://github.com/user-attachments/assets/bdeff651-8898-4d7f-80bd-e7c2e7a58e3c" />
<img width="1557" height="637" alt="image" src="https://github.com/user-attachments/assets/56f73e9d-b110-4b4b-bf42-6f1f0086ecb4" />
<img width="1557" height="547" alt="image" src="https://github.com/user-attachments/assets/88e1968e-fcce-43a2-bddb-7b83c5102273" />

*Example run on preset 6; results vary between runs.*


## Why
 
LLM-generated tests are often wrong, and a common "self-healing" fix makes it worse: when a test fails, rewrite its assertion to whatever the code currently returns. The suite turns green and **a real bug becomes "expected behaviour".** By construction, that approach can never report a bug. This agent is built to report one.

## What it does
 
1. **Generates** pytest tests for a Python function with the model and **runs** them (isolated subprocess, timeouts, coverage).
2. **Writes a reference implementation from the docstring alone.** The model never sees the function body.
3. **Triages every failing test** by comparing three things in code: the source's output, the test's expectation and the reference's output.
   - source = reference: the *test* was wrong, so it is corrected;
   - test = reference but source differs: **suspected source bug**, the test is left failing on purpose;
   - all three disagree: *needs review*, nothing is changed automatically.
4. **Audits the tests that pass.** A passing test can also encode a bug; if its expectation contradicts the spec-derived value it is flagged as a *spec conflict*.
5. **Exports a spec-aligned test suite**: conflicting tests are rewritten to the spec value, so they fail until the bug is fixed.
   
Every verdict shows who decided and on what evidence (the numbers involved). The reference the model wrote is visible in the UI, and a **Model calls** panel lists every call to the model live (purpose, model name, seconds). When the evidence is unclear the agent says so instead of guessing: crashes and negative outputs are treated as bugs, outputs without numbers are never auto-corrected, and error cases the spec does not describe are never flagged as bugs.

## Meta models used
 
| Model | Role |
|---|---|
| Muse Glimmer 30B (open-weight Meta model, 4-bit GGUF `Q4_K_M`), served with llama.cpp on a rented RTX 5090 and reached through an OpenAI-compatible endpoint | writes the tests; writes the reference implementation from the docstring |
 
Every model call the app makes at runtime goes to a Meta model, and nothing else is called. The results below were produced with Muse Glimmer 30B. Any other Meta model behind an OpenAI-compatible endpoint (for example Muse Spark Open through an API provider) can be used by changing the environment variables. The function under test and its docstring are sent to the model endpoint.

## Evaluation
 
To measure it, each benchmark function has a docstring spec, a clean version, and versions with one injected bug (wrong operator, coefficient, rounding or boundary); every bug is checked to change behaviour. A bug counts as **found** only if a flagged test uses an input that really exposes it and that input was not already flagged on the clean version of the same run. A **false alarm** is a clean version that was flagged anyway.
 
The **main set** (31 versions) is the one we looked at while building. The **held-out set** (16 versions) was written afterwards and never used for tuning.
 
Results with Muse Glimmer 30B (`Q4_K_M`, reasoning strength `low`), **one run per version**:
 
| Set | Bugs found | False alarms on clean code | Text-output bugs found | Median time per version |
|---|---|---|---|---|
| Main set (numeric outputs) | 21 / 21 (100%) | 0 / 7 | 0 / 2 | 16.3 s |
| Held-out set | 9 / 12 (75%) | 0 / 4 | - | 15.9 s |

With 95% Wilson intervals the main set is 85-100% and the held-out set 47-91%, so the held-out number is the more honest one and is still uncertain. No clean version was flagged (0 of 12). On the held-out set the agent missed three bugs: a wrong middle tax rate, an exclusive instead of inclusive minimum-spend boundary, and tax applied before the discount. Outputs that are text instead of numbers (the letter grade function) are a known blind spot: 0 of 2 found. The injected bugs were written by us and are fairly simple, so these numbers say little about real-world bugs. Each version was run once, and a different reasoning strength or another model may behave differently.
 
Raw results of every run (generated tests, reference code, flagged tests) are in `evaluation/results/`. Print a summary without any model:

```bash
python -m evaluation.run_eval --report evaluation/results/heldout_muse.json
```

## Scope
 
- Works from a **docstring that states the rules**; without one only a low-confidence fallback runs.
- Compares **numeric results**. Text or boolean outputs are never auto-corrected; they go to *needs review*.
- Meant for **pure functions with simple arguments**.
- Generated code runs in a subprocess with timeouts. This is **not a hardened sandbox**, so do not run untrusted code.

## Run it
 
```bash
pip install -r requirements.txt
```
 
Set the model endpoint with environment variables (Windows `set`, Linux/macOS `export`), then start the app. Example with Muse Spark Open on Baseten:
 
```
set LLM_API_KEY=<your Baseten API key>
set LLM_BASE_URL=https://inference.baseten.co/v1
set LLM_MODEL=meta-models/muse-spark-open
set LLM_MAX_TOKENS=8000
streamlit run app.py
```

Never commit an API key; the app reads it only from the environment. Other settings: `LLM_TIMEOUT` (seconds, default 300) and `LLM_REASONING_EFFORT` (for reasoning models). For an open-weight Meta model served by your own OpenAI-compatible server, for example Muse Glimmer 30B with llama.cpp (a 24 GB GPU is enough for a 4-bit build with a short context):
 
```
llama-server -hf meta-models/Muse-Glimmer-30B-GGUF:Q4_K_M --jinja -ngl 99 -c 32768 --host 127.0.0.1 --port 8080 --chat-template-kwargs '{"reasoning_strength":"low"}'
set LLM_BASE_URL=http://localhost:8080/v1
set LLM_MODEL=meta-models/Muse-Glimmer-30B-GGUF:Q4_K_M
```
 
No API key is needed for localhost. The server can run on a rented GPU and be reached from your machine through an SSH tunnel (`ssh -L 8080:localhost:8080 ...`).
 
Pick a preset (preset 6 is the refund example with a seeded bug) or paste a function with a docstring spec, then press **Run analysis**.

Reproduce the evaluation (model configured as above):
 
```bash
python -m evaluation.run_eval --verify-only                  # check the benchmark itself, no model
python -m evaluation.run_eval --repeats 1 --out evaluation/results/main_muse.json
python -m evaluation.run_eval --heldout --repeats 1 --out evaluation/results/heldout_muse.json
```

## Project layout

```
autonomous-qe-agent
├──  .streamlit/
|   └──config.toml           # Light theme
├── evaluation/
|   ├──  results/            # Raw results of the runs reported above
|   |    ├── main_3b.json
|   |    ├── main_8b.json
|   |    ├── heldout_3b.json
|   |    └── heldout_8b.json
|   ├── __init__.py
|   ├── cases.py             # Main benchmark (functions, injected bugs, probes)
|   ├── heldout_cases.py     # Held-out benchmark
|   └── run_eval.py          # Evaluation harness
├── qe_agent/
|   ├── __init__.py
|   ├── generate.py          # Test generation (+ simulated contract drift for demos)
|   ├── llm.py               # Model configuration
|   ├── presets.py           # Example functions
|   ├── sandbox.py           # Subprocess execution, pytest, coverage
|   ├── spec.py              # Docstring spec, reference implementation, numeric comparison
|   ├── triage.py            # Failure triage, spec audit, healing, spec-aligned export
|   └── ui.py                # Styling and HTML components
├── .gitignore
├── LICENSE
├── README.md
├── app.py                   # Streamlit UI (flow only)
└── requirements.txt

```
