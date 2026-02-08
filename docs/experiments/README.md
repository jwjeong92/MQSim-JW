# Results Index

**Project**: LLM Read-Disturb Evaluation
**Last Updated**: February 8, 2026

---

## Directory Structure

```
results/
├── MASTER_SUMMARY.md                    # Overall project summary
├── RESULTS_INDEX.md                     # This file
│
├── exp1_baseline/                       # Experiment 1: Baseline Performance
│   ├── EXPERIMENT_1_SUMMARY.md          # Detailed analysis
│   ├── llama7b_10000k.json              # Llama2-7B metrics (JSON)
│   ├── llama7b_10000k.txt               # Llama2-7B summary (text)
│   ├── llama7b_10000k_config.xml        # Workload config used
│   ├── llama7b_10000k_config_scenario_1.xml  # Full simulation output
│   ├── llama13b_10000k.json             # Llama2-13B metrics
│   ├── llama13b_10000k.txt              # Llama2-13B summary
│   ├── llama13b_10000k_config.xml
│   ├── llama13b_10000k_config_scenario_1.xml
│   ├── llama70b_10000k.json             # Llama2-70B metrics
│   ├── llama70b_10000k.txt              # Llama2-70B summary
│   ├── llama70b_10000k_config.xml
│   └── llama70b_10000k_config_scenario_1.xml
│
├── exp2_accumulation/                   # Experiment 2: Read-Disturb Accumulation
│   ├── EXPERIMENT_2_SUMMARY.md          # Detailed analysis
│   ├── llama70b_10000.json              # 10K tokens (JSON)
│   ├── llama70b_10000.txt               # 10K tokens (text)
│   ├── llama70b_10000_config.xml
│   ├── llama70b_10000_config_scenario_1.xml
│   ├── llama70b_50000.json              # 50K tokens
│   ├── llama70b_50000.txt
│   ├── llama70b_50000_config.xml
│   ├── llama70b_50000_config_scenario_1.xml
│   ├── llama70b_100000.json             # 100K tokens
│   ├── llama70b_100000.txt
│   ├── llama70b_100000_config.xml
│   └── llama70b_100000_config_scenario_1.xml
│
└── exp3_tradeoff/                       # Experiment 3: Trade-off Analysis (PENDING)
    └── (not yet run)
```

---

## Quick Reference

### Experiment 1: Baseline Performance

**Status**: ✅ Complete
**Date**: Feb 8, 2026
**Summary**: [exp1_baseline/EXPERIMENT_1_SUMMARY.md](exp1_baseline/EXPERIMENT_1_SUMMARY.md)

| Model      | IOPS    | Latency | Flash Reads | ECC Failures |
|------------|---------|---------|-------------|--------------|
| Llama2-7B  | 91,052  | 47.6 ms | 5,378       | 18,117       |
| Llama2-13B | 97,322  | 42.7 ms | 4,981       | 16,929       |
| Llama2-70B | 150,192 | 30.0 ms | 3,463       | 10,822       |

**Key Finding**: Larger models achieve higher IOPS due to better parallelism.

---

### Experiment 2: Read-Disturb Accumulation

**Status**: ✅ Complete
**Date**: Feb 8, 2026
**Summary**: [exp2_accumulation/EXPERIMENT_2_SUMMARY.md](exp2_accumulation/EXPERIMENT_2_SUMMARY.md)

| Tokens  | Flash Reads | ECC Failures | IOPS    | Latency  | Scaling  |
|---------|-------------|--------------|---------|----------|----------|
| 10K     | 3,463       | 10,822       | 150,192 | 30.0 ms  | 1.0×     |
| 50K     | 30,197      | 93,494       | 91,299  | 249.0 ms | 8.7×     |
| 100K    | 63,572      | 196,767      | 87,157  | 492.5 ms | 18.4×    |

**Key Finding**: ✅ Hypothesis 1 CONFIRMED - Read counts grow linearly without bound.

---

### Experiment 3: Trade-off Analysis

**Status**: ⏳ Pending
**Planned**: Sweep read-reclaim thresholds [10K, 50K, 100K, 500K, 1M, ∞]

**Expected Finding**: No sweet spot between reliability and lifespan.

---

## File Formats

### JSON Files (.json)

Structured metrics for programmatic analysis:
```json
{
  "host": {
    "name": "...",
    "total_requests": 10000,
    "iops": 150192.07,
    "bandwidth_mbps": 2459101264.77,
    "avg_response_time_us": 30049.0
  },
  "ftl": {
    "total_flash_reads": 3463,
    "total_ecc_failures": 10822,
    ...
  }
}
```

**Use**: Input to plotting scripts, automated analysis

### Text Files (.txt)

Human-readable summaries:
```
======================================================================
LLM Inference Simulation Results: llama70b_10000_config_scenario_1
======================================================================

📊 Host I/O Statistics:
  Total Requests:      10,000
  IOPS:                150,192.07
  ...
```

**Use**: Quick reference, manual review

### Config Files (*_config.xml)

Workload configurations used for each run:
```xml
<MQSim_IO_Scenarios>
  <IO_Scenario>
    <IO_Flow_Parameter_Set_Trace_Based>
      <File_Path>traces/llm/llama70b_iter.txt</File_Path>
      <Relay_Count>10000</Relay_Count>
      ...
```

**Use**: Reproducibility, parameter reference

### Scenario Files (*_scenario_1.xml)

Full simulation output (MQSim format):
```xml
<MQSimOutput>
  <IO_Flow_Detailed_Stats>
    <Total_Host_Requests>10000</Total_Host_Requests>
    ...
  </IO_Flow_Detailed_Stats>
  ...
```

**Use**: Complete raw data, advanced analysis

---

## Analysis Scripts

### Located in `tools/analysis/` and `tools/plotting/`

1. **analyze_llm_results.py**
   ```bash
   python3 tools/analysis/analyze_llm_results.py results/exp1_baseline/llama70b_10000k_config_scenario_1.xml
   ```
   - Parses XML → JSON + text summary

2. **plot_read_counts.py** (requires matplotlib)
   ```bash
   python3 tools/plotting/plot_read_counts.py results/exp2_accumulation/*.json -o figures/accumulation.png
   ```
   - Generates read accumulation plots

3. **plot_ecc_retries.py** (requires matplotlib)
   ```bash
   python3 tools/plotting/plot_ecc_retries.py results/exp2_accumulation/*.json -o figures/ecc_trends.png
   ```
   - Generates ECC retry rate plots

4. **plot_tradeoff.py** (requires matplotlib)
   ```bash
   python3 tools/plotting/plot_tradeoff.py results/exp3_tradeoff/*.json -o figures/tradeoff.png
   ```
   - Generates THE KEY FIGURE (trade-off plot)

5. **compare_experiments.py** (requires tabulate)
   ```bash
   python3 tools/analysis/compare_experiments.py results/exp1_baseline/*.json
   ```
   - Generates comparison tables

---

## Reproducing Results

### Experiment 1
```bash
./tools/automation/run_experiments.sh exp1
```
Output: `results/exp1_baseline/`

### Experiment 2
```bash
./tools/automation/run_experiments.sh exp2
```
Output: `results/exp2_accumulation/`

### Experiment 3 (not yet run)
```bash
./tools/automation/run_experiments.sh exp3
```
Output: `results/exp3_tradeoff/`

### All Experiments
```bash
./tools/automation/run_experiments.sh all
```

---

## Key Metrics Glossary

### Performance Metrics

- **IOPS**: I/O Operations Per Second (higher is better)
- **Bandwidth**: Data throughput in MB/s
- **Avg Response Time**: Average I/O latency in microseconds
- **Total Requests**: Number of host I/O requests issued

### Flash Operations

- **Flash Reads**: Number of read operations to flash chips
  - Single: Single-page reads
  - Multiplane: Multiplane parallel reads
- **Flash Writes**: Number of write operations (from GC/reclaim)
- **Flash Erases**: Number of block erases (from GC/reclaim)
- **GC Executions**: Garbage collection invocations
- **Read-Reclaim Ops**: Read-reclaim migrations

### ECC Statistics

- **ECC Retries**: Soft-decode retry attempts
- **ECC Failures**: Total ECC failures (soft + hard)
- **Uncorrectable**: Hard failures (cannot be corrected)
- **Retry Rate**: Retries per 1000 reads (%)
- **Failure Rate**: Failures per 1000 reads (%)
- **Uncorrectable Rate**: Uncorrectable errors per 1000 reads (%)

---

## Status Summary

| Experiment | Status | Duration | Key Metric | Result |
|------------|--------|----------|------------|--------|
| Exp1       | ✅ Done | 3s      | Baseline   | 150K IOPS (70B) |
| Exp2       | ✅ Done | 3s      | Accumulation | 18.4× read growth |
| Exp3       | ⏳ Pending | ~2h | Trade-off | TBD |

---

## Next Actions

1. ⏳ Run Experiment 3 (trade-off analysis)
2. ⏳ Install matplotlib for plotting
3. ⏳ Generate publication figures
4. ⏳ Write paper results section

---

**For Questions**: See project plan at `docs/plans/llm-read-disturb-evaluation.md`
