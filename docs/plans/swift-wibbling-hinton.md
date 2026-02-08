# Repository Restructuring Plan

## Context

The repository has grown organically across many sessions, resulting in files scattered across too many locations with inconsistent conventions. Documentation lives in 4+ places (`docs/`, `project-plans/`, `results/`, root), configs are split between `devconf/` and `wkdconf/`, scripts mix with libraries in `scripts/` and `lib/`, and results contain both raw data and narrative summaries. This makes the project hard to navigate. The goal is to reorganize into a standard, self-explanatory structure while preserving git history.

## Target Directory Structure

```
MQSim-JW/
├── README.md                    # Project overview (updated)
├── CLAUDE.md                    # AI assistant guidance (updated)
├── LICENSE
├── Makefile                     # Updated paths
├── .gitignore                   # Comprehensive (updated)
│
├── src/                         # NO CHANGES — already well-organized
│
├── configs/                     # All configuration files
│   ├── device/                  # SSD device configs (from devconf/)
│   │   ├── ssdconfig.xml
│   │   ├── ssdconfig_ifp.xml
│   │   └── eval/               # Experiment-specific device configs
│   │       ├── eval_retry_0..5.xml
│   │       ├── eval_high_threshold.xml
│   │       └── eval_low_threshold.xml
│   ├── workload/                # Workload configs (from wkdconf/)
│   │   ├── workload.xml
│   │   ├── trace_llm.xml
│   │   ├── llm_test_config.xml
│   │   ├── eval_ecc_retry_read.xml
│   │   └── eval/               # Experiment workload configs
│   │       ├── eval_high_threshold_*tok.xml
│   │       ├── eval_low_threshold_*tok.xml
│   │       ├── llama70b_10k.xml
│   │       ├── llama70b_50k.xml
│   │       └── llama70b_100k.xml
│   └── fast18/                  # Historical FAST'18 configs (from fast18/)
│       ├── README.md
│       ├── backend-contention/
│       ├── data-cache-contention/
│       └── queue-fetch-size/
│
├── traces/                      # All trace data files
│   ├── README.md                # Trace format documentation
│   ├── benchmarks/              # Standard benchmarks (from traces/)
│   │   ├── tpcc-small.trace
│   │   ├── wsrch-small.trace
│   │   └── gemv_test.trace
│   └── llm/                     # LLM model traces (from wkdconf/llm_traces/)
│       ├── llama7b_iter.txt
│       ├── llama13b_iter.txt
│       ├── llama70b_iter.txt
│       └── opt6.7b_iter.txt
│
├── tools/                       # All scripts and utilities
│   ├── README.md                # Tool documentation (from scripts/README.md)
│   ├── analysis/                # Result analysis (Python)
│   │   ├── analyze_llm_results.py
│   │   ├── compare_experiments.py
│   │   ├── analytical_tradeoff.py
│   │   ├── analyze_realistic_workloads.py
│   │   └── analyze_throughput_degradation.py
│   ├── plotting/                # Visualization (Python)
│   │   ├── plot_ecc_retries.py
│   │   ├── plot_read_counts.py
│   │   ├── plot_tradeoff.py
│   │   ├── generate_all_figures.py
│   │   └── generate_outcome_figures.py
│   ├── automation/              # Batch execution (Shell)
│   │   ├── run_experiments.sh
│   │   ├── run_ecc_eval.sh
│   │   ├── generate_llm_traces.sh
│   │   └── test_llm_workload.sh
│   └── examples/                # Usage examples
│       ├── basic_usage.sh
│       ├── run_llm_trace.sh
│       ├── run_plot_res.sh
│       ├── rber_model_example.py
│       └── llm_trace_gen.py     # Python trace generator (from lib/)
│
├── results/                     # Raw experimental data only
│   ├── README.md                # How to interpret results
│   ├── ecc_retry/               # ECC retry experiments
│   │   └── ecc_retry_0..5
│   ├── threshold_eval/          # Threshold sweep results
│   │   ├── eval_high_threshold_*tok.xml
│   │   └── eval_low_threshold_*tok.xml
│   ├── exp1_baseline/           # Keep as-is (minus summaries)
│   ├── exp2_accumulation/       # Keep as-is (minus summaries)
│   ├── exp3_tradeoff/           # Keep as-is (minus summaries)
│   └── analytical/
│       └── analytical_tradeoff.json
│
├── figures/                     # Publication figures (keep as-is)
│
├── docs/                        # Consolidated documentation
│   ├── README.md                # Documentation index
│   ├── build-and-test.md        # From TESTING_GUIDE.md
│   ├── changelog.md             # From CHANGELOG.md
│   ├── features/
│   │   ├── ecc-and-read-retry.md
│   │   └── read-reclaim.md      # From Reclaim_revision.md
│   ├── experiments/
│   │   ├── README.md            # From RESULTS_INDEX.md
│   │   ├── study-overview.md    # From PROJECT_COMPLETE.md
│   │   ├── exp1-baseline.md     # From exp1/EXPERIMENT_1_SUMMARY.md
│   │   ├── exp2-accumulation.md # From exp2/EXPERIMENT_2_SUMMARY.md
│   │   └── exp3-tradeoff.md     # From EXPERIMENT_3_ANALYTICAL.md
│   ├── plans/                   # Meaningful project plans
│   │   ├── ECC_revision.md
│   │   ├── llm-read-disturb-evaluation.md
│   │   └── read-reclaim-verification.md
│   └── references/              # Academic papers (from refs/)
│       ├── aif.pdf
│       └── cambricon-llm.pdf
│
└── archive/                     # Obsolete session logs and superseded docs
    ├── session-logs/
    │   ├── ancient-munching-beaver.md
    │   ├── hazy-swinging-puffin.md
    │   ├── joyful-bouncing-puppy.md
    │   ├── spicy-greeting-adleman.md
    │   ├── final-verification-session-log.md
    │   ├── SESSION_LOG_20260208.txt
    │   └── FINAL_SESSION_SUMMARY.md
    └── superseded/
        ├── PROGRESS_SUMMARY.md
        ├── MASTER_SUMMARY.md
        ├── DESIRED_OUTCOMES_VALIDATED.md
        └── ecc_retry_evaluation_summary.md
```

## Implementation Steps

### Phase 1: Create directories and update .gitignore

Create all target directories. Update `.gitignore` to cover build artifacts, large traces, Python cache, IDE files, and temporary files.

### Phase 2: Move configurations (devconf/ + wkdconf/ + fast18/ → configs/)

1. `git mv devconf/*.xml` → `configs/device/` (main configs) and `configs/device/eval/` (eval configs)
2. `git mv wkdconf/*.xml` → `configs/workload/` (main configs) and `configs/workload/eval/` (sweep configs)
3. `git mv wkdconf/llm_experiment_configs/*.xml` → `configs/workload/eval/`
4. `git mv fast18/` → `configs/fast18/`
5. Remove empty old directories

### Phase 3: Move traces

1. `git mv wkdconf/llm_traces/*` → `traces/llm/`
2. `git mv traces/tpcc-small.trace traces/wsrch-small.trace traces/gemv_test.trace` → `traces/benchmarks/`
3. Delete `traces/llama_7b_gen_*.trace` (generated files, large)
4. Delete `llm_trace.txt` (duplicate of `wkdconf/test_llm_trace.txt`, both generated)
5. Delete `wkdconf/test_llm_trace.txt`

### Phase 4: Move scripts and libraries (scripts/ + lib/ → tools/)

1. `git mv scripts/analyze_*.py scripts/compare_experiments.py scripts/analytical_tradeoff.py` → `tools/analysis/`
2. `git mv scripts/plot_*.py scripts/generate_*.py` → `tools/plotting/`
3. `git mv scripts/run_*.sh scripts/generate_llm_traces.sh scripts/test_llm_workload.sh` → `tools/automation/`
4. `git mv scripts/basic_usage.sh` → `tools/examples/`
5. `git mv lib/llm_trace_gen.py lib/rber_model_example.py` → `tools/examples/`
6. `git mv scripts/README.md` → `tools/README.md`
7. Delete `lib/test_rber_integration.cpp` and `lib/test_rber_integration` (standalone test, can be recreated)
8. Delete `lib/__pycache__/`

### Phase 5: Consolidate documentation

1. `git mv docs/ecc-and-read-retry.md` → `docs/features/`
2. `git mv results/PROJECT_COMPLETE.md` → `docs/experiments/study-overview.md`
3. `git mv results/RESULTS_INDEX.md` → `docs/experiments/README.md`
4. `git mv results/EXPERIMENT_3_ANALYTICAL.md` → `docs/experiments/exp3-tradeoff.md`
5. `git mv results/exp1_baseline/EXPERIMENT_1_SUMMARY.md` → `docs/experiments/exp1-baseline.md`
6. `git mv results/exp2_accumulation/EXPERIMENT_2_SUMMARY.md` → `docs/experiments/exp2-accumulation.md`
7. `git mv refs/*.pdf` → `docs/references/`
8. `git mv project-plans/ECC_revision.md project-plans/llm-read-disturb-evaluation.md project-plans/read-reclaim-verification.md` → `docs/plans/`
9. `git mv project-plans/Reclaim_revision.md` → `docs/features/read-reclaim.md`
10. Move root `TESTING_GUIDE.md` → `docs/build-and-test.md`
11. Move root `CHANGELOG.md` → `docs/changelog.md`

### Phase 6: Archive obsolete files

1. Move session logs to `archive/session-logs/`: the 4 auto-named plans, final-verification-session-log.md, SESSION_LOG_20260208.txt, FINAL_SESSION_SUMMARY.md
2. Move superseded docs to `archive/superseded/`: PROGRESS_SUMMARY.md, MASTER_SUMMARY.md, DESIRED_OUTCOMES_VALIDATED.md, ecc_retry_evaluation_summary.md

### Phase 7: Organize results/

1. `mkdir results/ecc_retry results/threshold_eval results/analytical`
2. Move `results/ecc_retry_*` → `results/ecc_retry/`
3. Move `results/eval_*_threshold_*.xml` → `results/threshold_eval/`
4. Move `results/analytical_tradeoff.json` → `results/analytical/`
5. Delete stray files from results root: `res_llm_gen_10_tok.png`, `eval_read_reclaim_bandwidth.png`, `llm_gen_10_tok.xml`, `plot_results.py` (analysis scripts belong in tools/)
6. Remove config XMLs from exp subdirs (these are simulation output copies, not original configs): `*_config.xml`, `*_config_scenario_1.xml`

### Phase 8: Delete temporary/generated files

- `COMMIT_MESSAGE.txt` (temporary)
- `llm_trace_gen` binary at root (build artifact, not tracked properly)
- `results/res_llm_gen_5_tok.png`, `results/llm_gen_5_tok.xml` (stray outputs)

### Phase 9: Update hardcoded paths in scripts

All tools/automation/ and tools/analysis/ scripts reference old paths. Update:
- `devconf/` → `configs/device/`
- `wkdconf/` → `configs/workload/`
- `wkdconf/llm_traces/` → `traces/llm/`
- `results/` paths stay the same (relative structure preserved)
- `lib/` → `tools/examples/`
- `scripts/` references in READMEs

### Phase 10: Update Makefile

The Makefile needs minimal changes:
- The `src/exec/LLM_Trace_Generator.cpp` and `LLM_Workload_Generator.h` stay in `src/exec/` (they are source code and the Makefile handles them correctly already)
- Only update `clean` target if needed for new output locations

### Phase 11: Update CLAUDE.md

Rewrite to reflect new directory structure, updated paths, and workflow guidance.

### Phase 12: Create README files

Write concise README.md files for: `docs/`, `tools/`, `results/`, `traces/`, `configs/`.

## Files to Delete (not archive)

| File | Reason |
|------|--------|
| `COMMIT_MESSAGE.txt` | Temporary file |
| `llm_trace.txt` | Duplicate (confirmed via md5sum) |
| `wkdconf/test_llm_trace.txt` | Generated test artifact |
| `llm_trace_gen` (root binary) | Build artifact |
| `lib/test_rber_integration` (binary) | Compiled test binary |
| `lib/__pycache__/` | Python cache |
| `traces/llama_7b_gen_*.trace` | Large generated files (10 files, 2-15MB each) |
| `results/res_*.png` | Stray plot outputs |
| `results/llm_gen_*.xml` | Stray simulation outputs |
| `results/plot_results.py` | Misplaced script |
| `results/eval_read_reclaim_bandwidth.png` | Stray plot |

## What Stays Unchanged

- **`src/`** — Entire source tree untouched
- **`figures/`** — Already well-organized publication figures
- **`Makefile`** — Minimal changes (LLM generator stays in src/exec/)
- **`README.md`** — Stays at root, content updated

## Verification

After restructuring:
1. `make clean && make` — Confirm build still works
2. `make llm_trace_gen` — Confirm trace generator builds
3. `./mqsim -i configs/device/ssdconfig.xml -w configs/workload/workload.xml` — Confirm simulation runs
4. `grep -r "devconf\|wkdconf\|scripts/" tools/ configs/ docs/` — Confirm no stale path references
5. `git log --follow configs/device/ssdconfig.xml` — Confirm history preserved
