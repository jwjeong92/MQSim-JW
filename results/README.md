# Experimental Results

Raw experimental data from simulations.

## Directory Structure

- `exp1_baseline/` - Baseline performance (fresh flash, 10K tokens, multiple models)
- `exp2_accumulation/` - Read accumulation study (10K/50K/100K tokens)
- `exp3_tradeoff/` - Threshold trade-off analysis (various reclaim thresholds)
- `ecc_retry/` - ECC retry sweep experiments
- `threshold_eval/` - Threshold evaluation sweep results
- `analytical/` - Analytical scaling predictions

## File Types

- `.json` - Parsed metrics (key statistics)
- `.txt` - Human-readable summary
- `*_scenario_1.xml` - Full simulation output

## Analysis

See `docs/experiments/` for interpretation. Use `tools/analysis/` to parse and analyze.
