# LLM Inference Read-Disturb Evaluation Project

**Date Started**: February 8, 2026
**Goal**: Demonstrate read-disturb reliability challenges in Cambricon-LLM-style in-flash LLM inference

## Research Question

**Does repetitive LLM inference cause read-disturb accumulation that creates a fundamental reliability-lifespan trade-off?**

- **Hypothesis 1**: Repetitive weight reads cause rapid read-disturb accumulation
- **Hypothesis 2**: Both outlier-protection ECC (Cambricon) and traditional BCH fail under read-disturb
- **Hypothesis 3**: Aggressive read-reclaim reduces lifespan unacceptably

---

## ✅ Phase 1: Infrastructure (COMPLETED)

### 1.1 LLM Workload Generator ✅

**Files Created**:
- `src/exec/LLM_Workload_Generator.h` - Trace generation library
- `src/exec/LLM_Trace_Generator.cpp` - Standalone tool
- `scripts/test_llm_workload.sh` - Quick test script
- `scripts/generate_llm_traces.sh` - Batch trace generation
- `wkdconf/llm_test_config.xml` - Test workload config
- `wkdconf/llm_experiment_configs/*.xml` - Experiment configs

**Key Innovation**: Compact single-iteration traces
- **Old approach**: 10GB trace file for 100K tokens
- **New approach**: 11MB trace file + `Relay_Count=100000`
- **Savings**: ~1000× reduction in trace file size

**Trace Format**:
```
# Single iteration through all model weights
# Format: timestamp(us) device_id lba size_sectors read(1)
0 0 0 32 1
30 0 32 32 1
...
```

**Usage**:
```bash
# Generate compact trace
./llm_trace_gen -m llama70b -t compact -o traces/llama70b_iter.txt

# Run simulation with N tokens
# Set <Relay_Count>N</Relay_Count> in workload XML
./mqsim -i devconf/ssdconfig.xml -w wkdconf/llm_experiment_configs/llama70b_100k.xml
```

**Supported Models**:
- Llama2-7B, 13B, 70B
- OPT-6.7B

### 1.2 Read-Disturb Tracking ✅

**Files Modified**:
- `src/ssd/Flash_Block_Manager_Base.h` - Block metadata extensions
- `src/ssd/Flash_Block_Manager_Base.cpp` - Tracking implementation

**New Block Metadata Fields**:
```cpp
class Block_Pool_Slot_Type {
    // Cumulative tracking
    unsigned int Read_count;                    // Total reads (existing)
    unsigned int Read_count_since_program;      // Since last erase
    unsigned int Read_count_since_reclaim;      // Since last reclaim
    sim_time_type Last_read_time;              // Most recent read timestamp

    // Per-page granular tracking
    std::vector<unsigned int> Page_read_counts; // Per-page read counts

    // ECC reliability tracking
    unsigned int Recent_ecc_retries;            // Recent retry count
    unsigned int Total_ecc_retries;             // Lifetime retries
    unsigned int Uncorrectable_errors;          // Uncorrectable count
    bool Has_uncorrectable_errors;              // Retirement flag
};
```

**Methods Added**:
- `Record_read(page_id, time)` - Track each read operation
- `Record_ecc_retry()` - Count retry events
- `Reset_for_reclaim()` - Reset after migration
- `Calculate_read_disturb_BER(gamma, p, q)` - Compute read-disturb BER

**Integration**:
- Automatically called in `Read_transaction_issued()`
- Per-page granularity for accurate read-disturb modeling

### 1.3 Enhanced RBER Model ✅

**Files Modified**:
- `src/ssd/NVM_PHY_ONFI_NVDDR2.cpp` - ECC integration

**RBER Model** (power-law):
```
RBER = ε + α(PE^k) + β(PE^m)(t^n) + γ(PE^p)(r^q)
       ↑   ↑         ↑              ↑
       │   │         │              └─ Read-disturb (NEW: per-page)
       │   │         └─ Retention errors
       │   └─ P/E cycle wear
       └─ Base error rate
```

**Key Improvement**:
- **Before**: Used block-average read count `block->Read_count / pages_per_block`
- **Now**: Uses actual per-page read count `Page_read_counts[page_id]`
- **Impact**: Much more accurate read-disturb modeling

**ECC Retry Tracking**:
- Retries recorded per block: `block->Record_ecc_retry()`
- Uncorrectable errors marked: `block->Has_uncorrectable_errors = true`
- Statistics exported in XML results

### 1.4 Build System ✅

**Makefile Updates**:
- Exclude `LLM_Trace_Generator.cpp` from main build (has own `main()`)
- Added `llm_trace_gen` target for standalone tool
- Fixed compilation and linking

**Build Commands**:
```bash
make                # Build mqsim
make llm_trace_gen  # Build trace generator
make clean          # Clean all
```

---

## 🔨 Phase 2: Analysis Tools (IN PROGRESS)

### 2.1 Result Parsing (50% DONE)

**Created**:
- `scripts/analyze_llm_results.py` - XML result parser

**Extracts**:
- Host I/O stats (IOPS, bandwidth, latency)
- Flash operation counts (reads, writes, erases)
- **ECC statistics** (retries, failures, uncorrectable)
- GC/WL execution counts
- Read-reclaim operation counts

**TODO**:
- Test the analyzer script
- Add comparison between experiments
- Add statistical analysis (mean, stddev, confidence intervals)

### 2.2 Visualization (NOT STARTED)

**Need to Create**:
- `scripts/plot_read_counts.py` - Plot read count accumulation
- `scripts/plot_ecc_retries.py` - Plot ECC retry rate over time
- `scripts/plot_tradeoff.py` - Visualize reclaim threshold vs. reliability/lifespan
- `scripts/compare_experiments.py` - Compare multiple runs

**Key Plots Needed**:
1. **Read-disturb accumulation**: Read counts vs. tokens generated
2. **ECC retry rate**: Retries per 1000 reads vs. time
3. **Trade-off analysis**: Reclaim threshold vs. (retry rate, P/E cycles)
4. **Block distribution**: Histogram of read counts across blocks
5. **Lifetime projection**: Flash lifetime under different policies

### 2.3 Batch Experimentation (NOT STARTED)

**Need to Create**:
- `scripts/run_experiments.sh` - Automate experiment sweeps
- `scripts/sweep_parameters.py` - Parameter space exploration

**Parameter Sweeps Needed**:
- **Models**: 7B, 13B, 70B
- **Token counts**: 10K, 50K, 100K, 200K
- **Read-reclaim thresholds**: 10K, 50K, 100K, 500K, 1M reads
- **RBER parameters**: γ (read-disturb coefficient) ±50%
- **ECC schemes**: (Future) outlier-protection, BCH-8, BCH-16

---

## 📊 Phase 3: Experiments (NOT STARTED)

### Experiment 1: Baseline Performance
**Goal**: Validate against Cambricon-LLM results

**Configuration**:
- Models: Llama2-7B, 13B, 70B
- Tokens: 10K (short run)
- Fresh flash (PE=0)
- Current RBER parameters

**Expected Output**:
- Throughput (tokens/s)
- IOPS
- Latency

**Success Criteria**: Match or explain differences from paper

### Experiment 2: Read-Disturb Accumulation
**Goal**: Show read counts build up over inference campaign

**Configuration**:
- Model: Llama2-70B (most stress)
- Tokens: 10K, 50K, 100K
- Track per-block read counts

**Key Metrics**:
- Average reads per block
- Maximum reads per block
- Distribution of read counts
- Read count vs. token count (linear relationship)

**Expected Finding**: Blocks storing weight matrices accumulate 100K+ reads in 100K token generation

### Experiment 3: ECC Degradation
**Goal**: Show ECC retry rate increases over time

**Configuration**:
- Model: Llama2-70B
- Tokens: 100K (long campaign)
- No read-reclaim initially
- Track ECC retries over time

**Key Metrics**:
- ECC retry rate vs. tokens generated
- Uncorrectable error rate vs. tokens generated
- Block-level retry distribution

**Expected Finding**: Retry rate increases exponentially due to read-disturb

### Experiment 4: Trade-off Analysis
**Goal**: Demonstrate reclaim threshold vs. reliability/lifespan trade-off

**Configuration**:
- Model: Llama2-70B
- Tokens: 100K
- Read-reclaim thresholds: [10K, 50K, 100K, 500K, 1M, ∞]

**Key Metrics**:
- ECC retry rate per threshold
- Total reclaim operations per threshold
- Extra P/E cycles consumed
- Projected flash lifetime

**Expected Finding**:
- Low threshold → Low retries but HIGH P/E cycles (short life)
- High threshold → High retries but LOW P/E cycles
- **No sweet spot** that satisfies both!

### Experiment 5: RBER Parameter Sensitivity
**Goal**: Show robustness of findings

**Configuration**:
- Vary γ (read-disturb coefficient): ±25%, ±50%
- Repeat key experiments

**Expected Finding**: Trade-off exists across parameter ranges

---

## 🎯 Phase 4: Paper Contributions (NOT STARTED)

### Main Figures to Generate

**Figure 1**: Read-Disturb Accumulation
- X-axis: Tokens generated
- Y-axis: Average block read count
- Shows linear growth

**Figure 2**: ECC Retry Rate Over Time
- X-axis: Tokens generated (or time)
- Y-axis: ECC retry rate (retries per 1000 reads)
- Multiple lines: Different ECC schemes
- Shows exponential growth

**Figure 3**: The Trade-Off (MAIN RESULT)
- X-axis: Read-reclaim threshold
- Left Y-axis: ECC retry rate (log scale)
- Right Y-axis: Extra P/E cycles consumed
- Shows opposing trends → no solution

**Figure 4**: Lifetime Projection
- X-axis: Read-reclaim policy
- Y-axis: Projected flash lifetime (years)
- Shows dramatic reduction (5 years → 6 months)

### Key Tables

**Table 1**: Baseline Performance Comparison
- Compare to Cambricon-LLM results

**Table 2**: Read-Disturb Accumulation Statistics
- Per model size, per token count

**Table 3**: ECC Scheme Comparison
- Retry rates, failure rates across schemes

---

## 🔧 Known Limitations & Future Work

### Current Limitations

1. **No time-series output**: MQSim only outputs final statistics
   - **Solution needed**: Add periodic stats dumping or live monitoring
   - **Workaround**: Run multiple short experiments at different time points

2. **Single ECC scheme**: Only power-law model implemented
   - **Solution**: Implement outlier-protection and BCH variants

3. **Simplified reclaim**: Current read-reclaim is basic
   - **Enhancement**: Add different reclaim policies (threshold-based, BER-based, hybrid)

4. **No block wear variation**: All blocks start fresh
   - **Enhancement**: Add pre-conditioning with varied P/E cycles

### Future Enhancements

1. **Real-time monitoring**: Add `--stats-interval` flag to dump periodic stats
2. **Block-level trace**: Export per-block read counts to CSV
3. **Multiple ECC modes**: Command-line switch for ECC type
4. **Reclaim policies**: XML-configurable reclaim strategies

---

## 📁 File Organization

```
MQSim-JW/
├── src/
│   ├── exec/
│   │   ├── LLM_Workload_Generator.h          ✅ Created
│   │   └── LLM_Trace_Generator.cpp           ✅ Created
│   └── ssd/
│       ├── Flash_Block_Manager_Base.h        ✅ Modified (read-disturb tracking)
│       ├── Flash_Block_Manager_Base.cpp      ✅ Modified
│       ├── NVM_PHY_ONFI_NVDDR2.cpp          ✅ Modified (per-page RBER)
│       └── ECC_Engine.cpp                    ✅ Existing (power-law model)
├── scripts/
│   ├── test_llm_workload.sh                 ✅ Created
│   ├── generate_llm_traces.sh               ✅ Created
│   ├── analyze_llm_results.py               ✅ Created (needs testing)
│   ├── plot_read_counts.py                  ⏭️ TODO
│   ├── plot_ecc_retries.py                  ⏭️ TODO
│   ├── plot_tradeoff.py                     ⏭️ TODO
│   └── run_experiments.sh                   ⏭️ TODO
├── wkdconf/
│   ├── llm_test_config.xml                  ✅ Created
│   ├── llm_traces/                          📁 For generated traces
│   │   ├── llama7b_iter.txt                 ⏭️ To generate
│   │   ├── llama13b_iter.txt                ⏭️ To generate
│   │   └── llama70b_iter.txt                ⏭️ To generate
│   └── llm_experiment_configs/              📁 Experiment configs
│       ├── llama70b_10k.xml                 ✅ Created
│       ├── llama70b_50k.xml                 ✅ Created
│       └── llama70b_100k.xml                ✅ Created
├── results/                                  📁 For experiment results
│   ├── exp1_baseline/                       ⏭️ TODO
│   ├── exp2_accumulation/                   ⏭️ TODO
│   ├── exp3_degradation/                    ⏭️ TODO
│   └── exp4_tradeoff/                       ⏭️ TODO
└── project-plans/
    └── llm-read-disturb-evaluation.md       ✅ This file
```

---

## 🚀 Next Steps (Priority Order)

### Immediate (Next Session)

1. **Test analyzer script**: `python3 scripts/analyze_llm_results.py wkdconf/llm_test_config_scenario_1.xml`
2. **Generate model traces**: Run `./scripts/generate_llm_traces.sh`
3. **Create plotting scripts**: Start with `plot_read_counts.py`

### Short-term (This Week)

4. **Run Experiment 1**: Baseline validation
5. **Run Experiment 2**: Read-disturb accumulation (10K, 50K tokens)
6. **Create comparison visualizations**

### Medium-term (Next Week)

7. **Implement time-series stats dumping** (if needed)
8. **Run Experiment 3**: ECC degradation (100K tokens)
9. **Run Experiment 4**: Trade-off analysis (sweep reclaim thresholds)
10. **Generate all paper figures**

### Long-term (Future)

11. **Implement alternative ECC schemes** (outlier-protection, BCH)
12. **Add reclaim policy variants**
13. **Write paper draft**

---

## 💡 Key Insights So Far

1. **Compact traces work**: 11MB files can simulate 100K+ tokens via Relay_Count
2. **Per-page tracking is critical**: Block-average read counts hide read-disturb hotspots
3. **ECC system is active**: Already seeing 95 ECC failures in test run (good for experiments!)
4. **Infrastructure is solid**: Build system works, integration is clean

---

## 📝 Commands Cheat Sheet

```bash
# Generate traces
./llm_trace_gen -m llama70b -n 100000 -t compact -o wkdconf/llm_traces/llama70b_iter.txt

# Run simulation
./mqsim -i devconf/ssdconfig.xml -w wkdconf/llm_experiment_configs/llama70b_100k.xml

# Analyze results
python3 scripts/analyze_llm_results.py wkdconf/llm_experiment_configs/llama70b_100k_scenario_1.xml

# Export as JSON
python3 scripts/analyze_llm_results.py result.xml --json results/exp1.json

# Batch trace generation
./scripts/generate_llm_traces.sh

# Quick test
./scripts/test_llm_workload.sh
```

---

## 📊 Expected Paper Outline

1. **Introduction**: Cambricon-LLM and read-disturb challenges
2. **Background**: LLM inference, read-disturb, ECC
3. **Methodology**: MQSim extensions, workload modeling
4. **Experiments**:
   - 4.1: Read-disturb accumulation
   - 4.2: ECC degradation
   - 4.3: Trade-off analysis
   - 4.4: Sensitivity study
5. **Discussion**: Implications for Cambricon-LLM viability
6. **Related Work**
7. **Conclusion**: Fundamental reliability-lifespan trade-off exists

---

**Status**: Infrastructure complete, ready for experiments
**Next Session**: Testing analysis tools and running first experiments
