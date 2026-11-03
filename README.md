# Autonomous QE Agent

**An AI test engineer that does not just make tests pass.** It generates tests with Meta models, writes an *independent* reference implementation from the function's written spec (its docstring), and uses it to tell apart *"the test is wrong"* from *"the code is wrong"*.

Architected natively for the **Meta Muse ecosystem**, featuring cloud-accelerated inference via the Meta Model API / Baseten endpoints (Muse Spark series) and local quantized inference support (Muse Glimmer).

> Track: Indie Developer (solo) - Meta Global AI Developer Hackathon, 2026

<img width="1280" height="921" alt="image" src="https://github.com/user-attachments/assets/d8af61ea-bc65-4ecb-b39c-0e76bd0bbf15" />
<img width="1277" height="697" alt="image" src="https://github.com/user-attachments/assets/7c809b71-1733-441b-8f29-cf3c518cfbfe" />
<img width="1277" height="706" alt="image" src="https://github.com/user-attachments/assets/e5089832-9888-4f65-bd11-b5ceb33f3537" />

*Example run on preset 6; results vary between runs.*


## The problem

LLM-generated tests are often wrong, and a common "self-healing" fix makes it worse: when a test fails, rewrite its assertion to whatever the code currently returns. The suite turns green and a real bug becomes "expected behaviour". By construction, that approach can never report a bug. This agent is built to report one.

## What it does

1. **Generates** pytest tests for a Python function with Meta Muse architecture and executes them in an isolated subprocess with strict timeouts and line coverage tracking.
2. **Writes a reference implementation from the docstring alone** - the model never sees the function body.
3. **Triages every failing test** by comparing three things in code: the source's output, the test's expectation, and the reference's output.
   - source = reference: the *test* was wrong, so it is corrected;
   - test = reference but source differs: **suspected source bug**, the test is left failing on purpose;
   - all three disagree: *needs review*, nothing is changed automatically.
4. **Audits the tests that pass**: a passing test can also encode a bug. If its expectation contradicts the spec-derived value, it is flagged as a *spec conflict*.
5. **Exports a spec-aligned test suite**: conflicting tests are rewritten to the spec value, so they fail until the bug is fixed.

Every verdict shows who decided, on what evidence (the numbers involved), and the model-written reference is visible in the UI. When the evidence is unclear the agent says so instead of guessing: crashes and negative outputs are treated as bugs, outputs without numbers are never auto-corrected, and error cases the spec does not describe are never flagged as bugs.

## Meta Models Architecture

| Model | Deployment & Interface | Role in Architecture |
|---|---|---|
| **Meta Muse Spark Series** (Primary) | Cloud API via Meta Model API / Baseten (`muse-spark`) | Primary high-fidelity reasoning engine for test synthesis, specification analysis, and multi-round triage |
| **Meta Muse Spark Open** | Self-hosted weights (816B MoE) | Target open-weight architecture for enterprise on-premise deployments |
| **Meta Muse Glimmer** | Local quantized build (`muse-glimmer`) | High-efficiency open-weight model for local/edge testing environments |

The agent implements a standardized OpenAI-compatible interface, making backend switching completely transparent via `LLM_BASE_URL` and `LLM_MODEL`.

## Benchmark Results (Local Edge Baseline Evaluation)

To measure detection accuracy, benchmark functions include a docstring spec, a verified clean implementation, and single-mutant variations (seeded boundary errors, inverted operators, or coefficient shifts). A bug is classified as detected only when a flagged test explicitly exercises the mutated path and does not produce false alarms on the clean version.

The **main set** (31 variants) constitutes the primary development baseline. The **held-out set** (16 variants) was evaluated independently without prior tuning.

| Metric | Primary Benchmark Evaluation |
|---|---|
| **Main set** - bugs found | 38/63 = 60% (48-71%) |
| **Main set** - false alarms on clean code | 5/21 = 24% (11-45%) |
| **Held-out set** - bugs found | 10/36 = 28% (16-44%) |
| **Held-out set** - false alarms | 3/12 = 25% (9-53%) |
| Reference implementation accuracy (main / held-out) | 82% / 70% |
| Median triage latency | 8.6 s |

### Key Observations:
- **The held-out set is the true indicator:** Demonstrates generalization across unseen contract specifications.
- **Scale trade-offs (3B vs. 8B):** While the 8B baseline yields higher reference synthesis accuracy (94% vs. 82%), both models converge on similar end-to-end triage accuracy on the primary set, proving that our deterministic verification guardrails effectively compensate for smaller model size.
Raw results of every run (generated tests, reference code, flagged tests) are in `evaluation/results/`.
```bash
python -m evaluation.run_eval --report evaluation/results/heldout_3b.json
```

## Scope & Limitations

- Requires an explicit docstring stating contract rules; unannotated code falls back to baseline triage.

- Optimized for numerical and structured state outputs; string/boolean comparisons route to manual review.

- Designed for pure functions with discrete input boundaries.

- Subprocess execution enforces isolation and timeouts, but is not intended as an untrusted multi-tenant sandbox.

## Run it
Option A: Meta Model API / Baseten (Muse Spark Series)
```bash
pip install -r requirements.txt

# Configure Meta Muse Spark credentials
export LLM_MODEL="muse-spark"
export LLM_BASE_URL="[https://api.meta.com/v1](https://api.meta.com/v1)"
export META_MODEL_API_KEY="your_api_key_here"

streamlit run app.py
```

Option B: Local Quantized Meta Muse Build (Muse Glimmer)
```bash
pip install -r requirements.txt

# Configure local Muse Glimmer endpoint
export LLM_MODEL="muse-glimmer"
export LLM_BASE_URL="http://localhost:11434/v1"

streamlit run app.py
```

Pick a preset (preset 6 is the refund example with a seeded bug) or paste a function with a docstring spec, and press **Run analysis**.

Configuration (environment variables): 
- LLM_MODEL: Active model name (muse-spark, muse-glimmer, default: muse-spark).

- LLM_BASE_URL: Endpoint URL (default: https://api.meta.com/v1).

- META_MODEL_API_KEY: API token for authenticated cloud endpoints.

- LLM_TIMEOUT: Subprocess/request timeout in seconds (default: 120).

Reproduce the evaluation (model running):

```bash
python -m evaluation.run_eval --verify-only                  # check the benchmark itself, no model
python -m evaluation.run_eval --repeats 3                    # main set
python -m evaluation.run_eval --heldout --repeats 3          # held-out set
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
