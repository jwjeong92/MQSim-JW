# LLM Read-Disturb Analysis Tools

Analysis, visualization, and automation tools for the LLM inference read-disturb evaluation project.

## Overview

```
Traces → Simulation → Results → Analysis → Visualization
  ↓          ↓           ↓          ↓           ↓
llm_trace_ mqsim    result.xml  analysis/  plotting/
gen (C++)                       *.py       *.py
```

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| `analysis/` | Result parsing and analysis (Python) |
| `plotting/` | Visualization and figure generation (Python) |
| `automation/` | Batch execution and experiment runners (Shell) |
| `examples/` | Usage examples and utilities |

---

## Trace Generation

### `llm_trace_gen` (C++ binary, built from src/exec/)
Generate compact LLM inference traces.

**Build & Usage:**
```bash
make llm_trace_gen

./llm_trace_gen -m <model> -n <tokens> -t compact -o <output.txt>

# Examples:
./llm_trace_gen -m llama70b -n 10000 -t compact -o traces/llm/llama70b_iter.txt
./llm_trace_gen -m llama13b -n 100000 -t compact -o traces/llm/llama13b_iter.txt
```

**Supported models:** `llama7b`, `llama13b`, `llama70b`, `opt6.7b`

### `automation/generate_llm_traces.sh`
Batch generate traces for all models.

```bash
tools/automation/generate_llm_traces.sh
```

Creates traces in `traces/llm/`:
- `llama7b_iter.txt` (~11 MB)
- `llama13b_iter.txt` (~20 MB)
- `llama70b_iter.txt` (~112 MB)
- `opt6.7b_iter.txt` (~11 MB)

---

## Simulation

Run MQSim with LLM workload:

```bash
./mqsim -i configs/device/ssdconfig.xml -w configs/workload/llm_test_config.xml
```

Output: `configs/workload/llm_test_config_scenario_1.xml` (result XML)

---

## Analysis

### `analysis/analyze_llm_results.py`
Parse simulation result XML and extract key metrics.

```bash
python3 tools/analysis/analyze_llm_results.py result.xml
python3 tools/analysis/analyze_llm_results.py result.xml --json output.json
```

### `analysis/compare_experiments.py`
Generate comparison tables across experiments.

```bash
python3 tools/analysis/compare_experiments.py results/exp1_baseline/*.json
```

---

## Visualization

All plotting scripts accept JSON files from `analyze_llm_results.py`.

### `plotting/plot_read_counts.py`
Plot read-disturb accumulation over token generation.

```bash
python3 tools/plotting/plot_read_counts.py results/exp1.json -o figures/reads.png
```

### `plotting/plot_ecc_retries.py`
Plot ECC retry rate trends (reliability degradation).

```bash
python3 tools/plotting/plot_ecc_retries.py results/*.json -o figures/ecc_trends.png
```

### `plotting/plot_tradeoff.py` (KEY FIGURE)
Plot the fundamental read-reclaim trade-off.

```bash
python3 tools/plotting/plot_tradeoff.py results/exp3_tradeoff/threshold_*.json -o figures/tradeoff.png
python3 tools/plotting/plot_tradeoff.py results/exp3_tradeoff/threshold_*.json --type lifetime -o figures/lifetime.png
```

---

## Batch Experimentation

### `automation/run_experiments.sh`
Automated batch experiment runner.

```bash
tools/automation/run_experiments.sh exp1    # Baseline performance
tools/automation/run_experiments.sh exp2    # Read-disturb accumulation
tools/automation/run_experiments.sh exp3    # Trade-off analysis
tools/automation/run_experiments.sh all     # Run all experiments
```

---

## Quick Start

```bash
# 1. Build
make clean && make && make llm_trace_gen

# 2. Generate traces
tools/automation/generate_llm_traces.sh

# 3. Run experiments
tools/automation/run_experiments.sh all

# 4. Review results
python3 tools/analysis/compare_experiments.py results/exp1_baseline/*.json
```

---

## Dependencies

```bash
pip install matplotlib numpy tabulate
```

## Troubleshooting

**"Trace file not found"** — Run `tools/automation/generate_llm_traces.sh`

**"Simulation timed out"** — Increase timeout in `automation/run_experiments.sh`

**"No module named matplotlib"** — Run `pip install matplotlib numpy tabulate`

For issues, see `docs/plans/llm-read-disturb-evaluation.md`
