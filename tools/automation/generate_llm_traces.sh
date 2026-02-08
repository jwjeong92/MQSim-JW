#!/bin/bash

# Generate LLM inference traces for experiments

echo "=== LLM Trace Generation Script ==="
echo "This will generate traces for all experimental phases"
echo ""

# Build the generator
echo "Building llm_trace_gen..."
make llm_trace_gen

if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

# Create output directory
mkdir -p traces/llm

echo ""
echo "Generating LLM inference traces..."
echo "This may take several minutes..."
echo ""

# ============================================================
# Generate compact single-iteration traces
# Use Relay_Count in XML to simulate N tokens
# ============================================================
echo ">>> Generating compact single-iteration traces"
echo "    (Set Relay_Count in workload XML to simulate multiple tokens)"

echo "  - Llama2-7B..."
./llm_trace_gen -m llama7b -n 10000 -t compact -o traces/llm/llama7b_iter.txt

echo "  - Llama2-13B..."
./llm_trace_gen -m llama13b -n 10000 -t compact -o traces/llm/llama13b_iter.txt

echo "  - Llama2-70B..."
./llm_trace_gen -m llama70b -n 10000 -t compact -o traces/llm/llama70b_iter.txt

echo "  - OPT-6.7B..."
./llm_trace_gen -m opt6.7b -n 10000 -t compact -o traces/llm/opt6.7b_iter.txt


echo ""
echo "=== Trace Generation Complete ==="
echo ""
echo "Generated compact single-iteration traces:"
ls -lh traces/llm/
echo ""
echo "Total disk usage:"
du -sh traces/llm/
echo ""
echo "Usage:"
echo "  Each trace represents ONE token generation (one complete weight read)"
echo "  To simulate N tokens, set <Relay_Count>N</Relay_Count> in workload XML"
echo ""
echo "Examples:"
echo "  10K tokens:  <Relay_Count>10000</Relay_Count>"
echo "  50K tokens:  <Relay_Count>50000</Relay_Count>"
echo "  100K tokens: <Relay_Count>100000</Relay_Count>"
echo ""
echo "All traces saved to traces/llm/"
