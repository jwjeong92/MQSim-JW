# LLM Inference Experiment Configurations

This directory contains workload configurations for LLM inference experiments using **compact single-iteration traces**.

## How It Works

### Compact Traces + Relay_Count

Instead of generating massive multi-GB trace files, we use:

1. **Compact traces** (`llm_traces/*.txt`) - Single iteration through all model weights (~7MB for Llama-70B)
2. **Relay_Count** in XML - Repeats the trace N times to simulate N tokens

**File size savings**: ~1000x smaller traces!

Example:
- Full 100K token trace: ~700 GB
- Compact trace + Relay_Count: ~7 MB

## Usage

### 1. Generate Compact Traces

```bash
# Generate all model traces
./scripts/generate_llm_traces.sh

# Or generate specific model
./llm_trace_gen -m llama70b -t compact -o wkdconf/llm_traces/llama70b_iter.txt
```

### 2. Run Experiments

```bash
# Baseline (10K tokens)
./mqsim -i devconf/ssdconfig.xml -w wkdconf/llm_experiment_configs/llama70b_10k.xml

# Medium campaign (50K tokens)
./mqsim -i devconf/ssdconfig.xml -w wkdconf/llm_experiment_configs/llama70b_50k.xml

# Long campaign (100K tokens)
./mqsim -i devconf/ssdconfig.xml -w wkdconf/llm_experiment_configs/llama70b_100k.xml
```

## Configuration Files

| File | Model | Tokens | Purpose |
|------|-------|--------|---------|
| `llama70b_10k.xml` | Llama2-70B | 10,000 | Baseline performance |
| `llama70b_50k.xml` | Llama2-70B | 50,000 | Read-disturb analysis |
| `llama70b_100k.xml` | Llama2-70B | 100,000 | Stress test |

## Creating Custom Configs

To create a config for a different token count:

```xml
<Relay_Count>YOUR_TOKEN_COUNT</Relay_Count>
```

Examples:
- 1K tokens: `<Relay_Count>1000</Relay_Count>`
- 200K tokens: `<Relay_Count>200000</Relay_Count>`

## Experiment Phases

### Phase 1: Baseline Recreation
- Use 10K token configs
- Match Cambricon-LLM performance numbers

### Phase 2: Read-Disturb Analysis
- Use 50K-100K token configs
- Track ECC retry rate over time
- Measure read count accumulation

### Phase 3: ECC Comparison
- Run with different ECC schemes (outlier-protection, BCH-8, BCH-16)
- Compare retry rates and error rates

### Phase 4: Trade-off Analysis
- Vary read-reclaim thresholds
- Measure lifespan vs. reliability trade-off

## Notes

- Each compact trace represents ONE complete pass through all model weights
- MQSim's Relay_Count automatically replays the trace N times
- Time offsets are handled automatically by MQSim's trace replay mechanism
- Results are identical to full traces but with tiny file sizes
