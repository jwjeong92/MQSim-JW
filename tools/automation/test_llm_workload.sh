#!/bin/bash

echo "=== Testing LLM Workload Generator ==="

# Build the generator
echo "Building llm_trace_gen..."
make llm_trace_gen

if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p traces

# Generate a compact single-iteration trace
echo ""
echo "Generating compact trace (Llama2-7B, single iteration)..."
echo "This represents ONE token generation. Use Relay_Count in XML for multiple tokens."
./llm_trace_gen -m llama7b -n 100 -t compact -o traces/test_llm_trace.txt

if [ $? -ne 0 ]; then
    echo "Trace generation failed!"
    exit 1
fi

# Check output
echo ""
echo "First 20 lines of generated trace:"
head -n 20 traces/test_llm_trace.txt

echo ""
echo "Last 10 lines:"
tail -n 10 traces/test_llm_trace.txt

echo ""
echo "Trace statistics:"
echo "Total lines: $(wc -l < traces/test_llm_trace.txt)"
echo "Comment lines: $(grep -c '^#' traces/test_llm_trace.txt)"
echo "Total read operations: $(grep -c ' 1$' traces/test_llm_trace.txt)"
echo "Total write operations: $(grep -c ' 0$' traces/test_llm_trace.txt)"

echo ""
echo "Test complete! Trace saved to traces/test_llm_trace.txt"
