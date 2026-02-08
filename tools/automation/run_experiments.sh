#!/bin/bash
#
# Batch experiment runner for LLM read-disturb evaluation
#
# Runs systematic sweeps over:
#   - Models (7B, 13B, 70B)
#   - Token counts (10K, 50K, 100K)
#   - Read-reclaim thresholds (10K, 50K, 100K, 500K, 1M, infinity)
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$TOOLS_DIR")"
RESULTS_DIR="$PROJECT_ROOT/results"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "LLM Read-Disturb Evaluation - Batch Runner"
echo "=========================================="
echo ""

# Check if mqsim binary exists
if [ ! -f "$PROJECT_ROOT/mqsim" ]; then
    echo -e "${RED}Error: mqsim binary not found!${NC}"
    echo "Please run 'make' to build the simulator first."
    exit 1
fi

# Check if traces exist
if [ ! -d "$PROJECT_ROOT/traces/llm" ] || [ -z "$(ls -A $PROJECT_ROOT/traces/llm 2>/dev/null)" ]; then
    echo -e "${YELLOW}Warning: LLM traces not found!${NC}"
    echo "Generating traces first..."
    "$SCRIPT_DIR/generate_llm_traces.sh"
fi

# ============================================================
# Experiment 1: Baseline Performance (Quick validation)
# ============================================================
run_experiment_1() {
    echo ""
    echo -e "${GREEN}=== Experiment 1: Baseline Performance ===${NC}"
    echo "Goal: Validate simulator against expected performance"
    echo "Config: Fresh flash (PE=0), 10K tokens, all models"
    echo ""

    EXP_DIR="$RESULTS_DIR/exp1_baseline"
    mkdir -p "$EXP_DIR"

    MODELS=("llama7b" "llama13b" "llama70b")
    TOKENS=10000

    for model in "${MODELS[@]}"; do
        echo -e "${YELLOW}Running $model @ ${TOKENS}K tokens...${NC}"

        # Copy and modify workload config
        CONFIG="$EXP_DIR/${model}_${TOKENS}k_config.xml"
        cp "$PROJECT_ROOT/configs/workload/llm_test_config.xml" "$CONFIG"

        # Update trace file and relay count
        sed -i "s|<File_Path>.*</File_Path>|<File_Path>$PROJECT_ROOT/traces/llm/${model}_iter.txt</File_Path>|" "$CONFIG"
        sed -i "s|<Relay_Count>.*</Relay_Count>|<Relay_Count>${TOKENS}</Relay_Count>|" "$CONFIG"

        # Run simulation
        cd "$PROJECT_ROOT"
        echo "" | timeout 600 ./mqsim -i configs/device/ssdconfig.xml -w "$CONFIG" || {
            echo -e "${RED}Simulation failed or timed out!${NC}"
            continue
        }

        # Move result
        RESULT_XML="${CONFIG%.*}_scenario_1.xml"
        if [ -f "$RESULT_XML" ]; then
            echo -e "${GREEN}✓ Complete${NC}"

            # Analyze and save JSON
            python3 "$TOOLS_DIR/analysis/analyze_llm_results.py" "$RESULT_XML" \
                --json "$EXP_DIR/${model}_${TOKENS}k.json" > "$EXP_DIR/${model}_${TOKENS}k.txt"
        fi
    done

    echo ""
    echo -e "${GREEN}Experiment 1 complete. Results in: $EXP_DIR${NC}"
}

# ============================================================
# Experiment 2: Read-Disturb Accumulation
# ============================================================
run_experiment_2() {
    echo ""
    echo -e "${GREEN}=== Experiment 2: Read-Disturb Accumulation ===${NC}"
    echo "Goal: Show read counts build up over inference campaign"
    echo "Config: Llama2-70B, 10K/50K/100K tokens"
    echo ""

    EXP_DIR="$RESULTS_DIR/exp2_accumulation"
    mkdir -p "$EXP_DIR"

    MODEL="llama70b"
    TOKEN_COUNTS=(10000 50000 100000)

    for tokens in "${TOKEN_COUNTS[@]}"; do
        echo -e "${YELLOW}Running ${MODEL} @ ${tokens} tokens...${NC}"

        CONFIG="$EXP_DIR/${MODEL}_${tokens}_config.xml"
        cp "$PROJECT_ROOT/configs/workload/llm_test_config.xml" "$CONFIG"

        sed -i "s|<File_Path>.*</File_Path>|<File_Path>$PROJECT_ROOT/traces/llm/${MODEL}_iter.txt</File_Path>|" "$CONFIG"
        sed -i "s|<Relay_Count>.*</Relay_Count>|<Relay_Count>${tokens}</Relay_Count>|" "$CONFIG"

        cd "$PROJECT_ROOT"
        echo "" | timeout 3600 ./mqsim -i configs/device/ssdconfig.xml -w "$CONFIG" || {
            echo -e "${RED}Simulation failed or timed out!${NC}"
            continue
        }

        RESULT_XML="${CONFIG%.*}_scenario_1.xml"
        if [ -f "$RESULT_XML" ]; then
            echo -e "${GREEN}✓ Complete${NC}"
            python3 "$TOOLS_DIR/analysis/analyze_llm_results.py" "$RESULT_XML" \
                --json "$EXP_DIR/${MODEL}_${tokens}.json" > "$EXP_DIR/${MODEL}_${tokens}.txt"
        fi
    done

    # Generate plots
    echo ""
    echo "Generating plots..."
    python3 "$TOOLS_DIR/plotting/plot_read_counts.py" "$EXP_DIR"/*.json -o "$EXP_DIR/read_accumulation.png"
    python3 "$TOOLS_DIR/plotting/plot_ecc_retries.py" "$EXP_DIR"/*.json -o "$EXP_DIR/ecc_trends.png"

    echo ""
    echo -e "${GREEN}Experiment 2 complete. Results in: $EXP_DIR${NC}"
}

# ============================================================
# Experiment 3: Trade-off Analysis (THE KEY EXPERIMENT)
# ============================================================
run_experiment_3() {
    echo ""
    echo -e "${GREEN}=== Experiment 3: Read-Reclaim Trade-off Analysis ===${NC}"
    echo "Goal: Demonstrate reliability vs. lifespan trade-off"
    echo "Config: Llama2-70B, 100K tokens, sweep reclaim thresholds"
    echo ""

    EXP_DIR="$RESULTS_DIR/exp3_tradeoff"
    mkdir -p "$EXP_DIR"

    MODEL="llama70b"
    TOKENS=100000
    THRESHOLDS=(10 50 100 500 1000 999999999)  # Last = infinity (no reclaim)
    THRESHOLD_NAMES=("10" "50" "100" "500" "1K" "inf")

    for i in "${!THRESHOLDS[@]}"; do
        threshold="${THRESHOLDS[$i]}"
        name="${THRESHOLD_NAMES[$i]}"

        echo -e "${YELLOW}Running threshold=${name}...${NC}"

        # Copy device config and modify reclaim threshold
        DEV_CONFIG="$EXP_DIR/ssdconfig_threshold_${name}.xml"
        cp "$PROJECT_ROOT/configs/device/ssdconfig.xml" "$DEV_CONFIG"
        sed -i "s|<Read_Reclaim_Threshold>.*</Read_Reclaim_Threshold>|<Read_Reclaim_Threshold>${threshold}</Read_Reclaim_Threshold>|" "$DEV_CONFIG"

        # Workload config
        CONFIG="$EXP_DIR/${MODEL}_threshold_${name}_config.xml"
        cp "$PROJECT_ROOT/configs/workload/llm_test_config.xml" "$CONFIG"
        sed -i "s|<File_Path>.*</File_Path>|<File_Path>$PROJECT_ROOT/traces/llm/${MODEL}_iter.txt</File_Path>|" "$CONFIG"
        sed -i "s|<Relay_Count>.*</Relay_Count>|<Relay_Count>${TOKENS}</Relay_Count>|" "$CONFIG"
        # CRITICAL: Set initial occupancy to simulate pre-loaded LLM weights
        sed -i "s|<Initial_Occupancy_Percentage>.*</Initial_Occupancy_Percentage>|<Initial_Occupancy_Percentage>70</Initial_Occupancy_Percentage>|" "$CONFIG"

        cd "$PROJECT_ROOT"
        echo "" | timeout 7200 ./mqsim -i "$DEV_CONFIG" -w "$CONFIG" || {
            echo -e "${RED}Simulation failed or timed out!${NC}"
            continue
        }

        RESULT_XML="${CONFIG%.*}_scenario_1.xml"
        if [ -f "$RESULT_XML" ]; then
            echo -e "${GREEN}✓ Complete${NC}"
            python3 "$TOOLS_DIR/analysis/analyze_llm_results.py" "$RESULT_XML" \
                --json "$EXP_DIR/threshold_${name}.json" > "$EXP_DIR/threshold_${name}.txt"
        fi
    done

    # Generate THE trade-off plot
    echo ""
    echo "Generating trade-off plots..."
    python3 "$TOOLS_DIR/plotting/plot_tradeoff.py" "$EXP_DIR"/threshold_*.json -o "$EXP_DIR/tradeoff.png"
    python3 "$TOOLS_DIR/plotting/plot_tradeoff.py" "$EXP_DIR"/threshold_*.json --type lifetime -o "$EXP_DIR/lifetime_projection.png"

    echo ""
    echo -e "${GREEN}Experiment 3 complete. Results in: $EXP_DIR${NC}"
    echo -e "${GREEN}KEY FIGURE: $EXP_DIR/tradeoff.png${NC}"
}

# ============================================================
# Main menu
# ============================================================
show_menu() {
    echo ""
    echo "Select experiment to run:"
    echo "  1) Experiment 1 - Baseline Performance (~10 min)"
    echo "  2) Experiment 2 - Read-Disturb Accumulation (~30 min)"
    echo "  3) Experiment 3 - Trade-off Analysis (~2 hours)"
    echo "  4) Run all experiments"
    echo "  q) Quit"
    echo ""
}

# Parse arguments
if [ $# -eq 0 ]; then
    # Interactive mode
    while true; do
        show_menu
        read -p "Choice: " choice
        case $choice in
            1) run_experiment_1 ;;
            2) run_experiment_2 ;;
            3) run_experiment_3 ;;
            4)
                run_experiment_1
                run_experiment_2
                run_experiment_3
                ;;
            q|Q) exit 0 ;;
            *) echo -e "${RED}Invalid choice${NC}" ;;
        esac
    done
else
    # Command-line mode
    case "$1" in
        exp1|1) run_experiment_1 ;;
        exp2|2) run_experiment_2 ;;
        exp3|3) run_experiment_3 ;;
        all) run_experiment_1; run_experiment_2; run_experiment_3 ;;
        *) echo "Usage: $0 [exp1|exp2|exp3|all]"; exit 1 ;;
    esac
fi

echo ""
echo -e "${GREEN}=========================================="
echo "All requested experiments complete!"
echo "==========================================${NC}"
echo ""
echo "Results saved in: $RESULTS_DIR"
echo ""
echo "Next steps:"
echo "  - Review result summaries (*.txt files)"
echo "  - Check generated plots (*.png files)"
echo "  - Compare across experiments"
echo ""
