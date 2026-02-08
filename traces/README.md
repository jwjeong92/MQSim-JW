# Trace Files

## Directory Structure

- `benchmarks/` - Standard benchmark traces (tracked in git)
- `llm/` - LLM model traces (gitignored, regenerate with `tools/automation/generate_llm_traces.sh`)

## Trace Format

Each line: `arrival_time device_num LBA size_sectors type`
- `type`: 0=write, 1=read

## Generating LLM Traces

```bash
make llm_trace_gen
tools/automation/generate_llm_traces.sh
```
