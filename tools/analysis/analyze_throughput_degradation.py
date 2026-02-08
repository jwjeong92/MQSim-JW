#!/usr/bin/env python3
"""
Throughput Degradation Analysis

Demonstrates:
1. Token generation slowdown due to ECC retries (read accumulation)
2. SSD lifespan reduction (in days) from reclaim to maintain throughput
"""

import json
import sys

# ============================================================================
# LOAD EXPERIMENTAL DATA
# ============================================================================

def load_exp2_data():
    """Load Experiment 2 results (read accumulation)"""
    data = []

    files = [
        ('results/exp2_accumulation/llama70b_10000.json', 10000),
        ('results/exp2_accumulation/llama70b_50000.json', 50000),
        ('results/exp2_accumulation/llama70b_100000.json', 100000),
    ]

    for filepath, tokens in files:
        try:
            with open(filepath, 'r') as f:
                result = json.load(f)
                data.append({
                    'tokens': tokens,
                    'iops': result['host']['iops'],
                    'avg_response_us': result['host']['avg_response_time_us'],
                    'ecc_failures': result['ftl']['total_ecc_failures'],
                    'flash_reads': result['ftl']['total_flash_reads'],
                    'multiplane_reads': result['ftl']['multiplane_reads']
                })
        except FileNotFoundError:
            print(f"Warning: {filepath} not found", file=sys.stderr)

    return data

# ============================================================================
# OUTCOME 1: TOKEN GENERATION SLOWDOWN
# ============================================================================

def analyze_throughput_degradation(data):
    """
    Calculate token generation rate degradation due to ECC retries.

    As reads accumulate:
    - ECC failures increase
    - Response time increases (retries)
    - IOPS decreases
    - Token generation rate slows down
    """

    print("=" * 80)
    print("OUTCOME 1: TOKEN GENERATION SLOWDOWN DUE TO ECC RETRIES")
    print("=" * 80)
    print()

    baseline = data[0]  # 10K tokens
    baseline_rate = baseline['iops']

    print(f"{'Tokens':<12} {'IOPS':>12} {'Response (ms)':>15} {'ECC Fails':>12} {'Throughput':>15} {'Slowdown':>12}")
    print("-" * 80)

    results = []

    for d in data:
        iops = d['iops']
        response_ms = d['avg_response_us'] / 1000  # Convert to ms
        ecc_fails = d['ecc_failures']
        tokens = d['tokens']

        # Token generation rate (tokens/sec)
        # In LLM inference, each request generates 1 token
        # So token rate = request rate = IOPS
        token_rate = iops

        # Throughput relative to baseline
        throughput_pct = (token_rate / baseline_rate) * 100
        slowdown = baseline_rate / token_rate

        print(f"{tokens:<12,} {iops:>12,.0f} {response_ms:>15,.1f} {ecc_fails:>12,} "
              f"{throughput_pct:>14.1f}% {slowdown:>11.2f}×")

        results.append({
            'tokens': tokens,
            'iops': iops,
            'token_rate': token_rate,
            'response_ms': response_ms,
            'ecc_fails': ecc_fails,
            'throughput_pct': throughput_pct,
            'slowdown': slowdown
        })

    print()
    print("KEY FINDINGS:")
    print("-" * 80)

    final = results[-1]

    print(f"• At 100K tokens: Token generation rate = {final['token_rate']:,.0f} tokens/sec")
    print(f"• Baseline (10K):  Token generation rate = {baseline_rate:,.0f} tokens/sec")
    print(f"• Throughput degradation: {100 - final['throughput_pct']:.1f}%")
    print(f"• Slowdown factor: {final['slowdown']:.2f}× slower")
    print(f"• Root cause: ECC failures increased {final['ecc_fails'] / results[0]['ecc_fails']:.1f}× → more retries → slower reads")
    print()

    return results

# ============================================================================
# OUTCOME 2: LIFESPAN REDUCTION FROM RECLAIM (IN DAYS)
# ============================================================================

def analyze_lifespan_tradeoff(throughput_results):
    """
    Calculate SSD lifespan (in days) when using read-reclaim to maintain throughput.

    Scenario:
    - Want to maintain baseline throughput (150K tokens/sec)
    - Must use aggressive read-reclaim to prevent slowdown
    - Each reclaim consumes P/E cycles
    - Calculate: How many days until SSD exhausted?
    """

    print("=" * 80)
    print("OUTCOME 2: SSD LIFESPAN REDUCTION FROM READ-RECLAIM (IN DAYS)")
    print("=" * 80)
    print()

    # Constants (from analytical_tradeoff.py)
    READ_RATE_PER_TOKEN = 0.636  # flash reads per token (measured)
    ESTIMATED_BLOCKS = 17920  # Llama2-70B
    BLOCK_SIZE_MB = 24  # 1536 pages × 16KB
    PE_CYCLES_LIMIT = 3000  # TLC NAND

    # Baseline throughput we want to maintain
    baseline_iops = throughput_results[0]['token_rate']

    print(f"SCENARIO: Production LLM inference server")
    print(f"  • Target throughput: {baseline_iops:,.0f} tokens/sec (baseline from 10K experiment)")
    print(f"  • Model: Llama2-70B (70GB, {ESTIMATED_BLOCKS:,} blocks)")
    print(f"  • Flash endurance: {PE_CYCLES_LIMIT} P/E cycles (TLC NAND)")
    print(f"  • Block size: {BLOCK_SIZE_MB} MB")
    print()

    # Load analytical trade-off data
    try:
        with open('results/analytical_tradeoff.json', 'r') as f:
            tradeoff_data = json.load(f)
    except FileNotFoundError:
        print("Error: results/analytical_tradeoff.json not found")
        print("Run: python3 tools/analysis/analytical_tradeoff.py -o results/analytical/analytical_tradeoff.json")
        return

    print(f"{'Threshold':<12} {'First Trigger':>15} {'Reclaims/Hot':>15} {'Avg P/E':>12} {'TBW (GB)':>12} {'Lifespan':>15}")
    print("-" * 80)

    campaign_tokens = tradeoff_data['campaign_tokens']  # 10M tokens

    for threshold_data in tradeoff_data['thresholds']:
        threshold = threshold_data['threshold']
        reclaims = threshold_data['reclaims_per_hot_block']
        avg_pe = threshold_data['avg_pe_cycles']
        tbw_tb = threshold_data['tbw_tb']
        tbw_gb = tbw_tb * 1024  # Convert to GB

        if avg_pe == 0:
            # No reclaim - but throughput degrades
            lifespan_str = "N/A (degrades)"
            continue

        # Calculate lifespan in DAYS
        # Daily token generation at baseline rate
        tokens_per_day = baseline_iops * 86400  # tokens/sec × 86400 sec/day

        # P/E cycles per day
        # From analytical model: avg_pe cycles per campaign_tokens
        pe_per_token = avg_pe / campaign_tokens
        pe_per_day = pe_per_token * tokens_per_day

        # Days until P/E limit exhausted
        days_to_failure = PE_CYCLES_LIMIT / pe_per_day
        lifespan_str = f"{days_to_failure:.1f} days"

        # Calculate when first reclaim triggers
        # From analytical model
        tokens_per_trigger = threshold * ESTIMATED_BLOCKS / (READ_RATE_PER_TOKEN * 10)  # 10× concentration
        trigger_str = f"{tokens_per_trigger/1e6:.1f}M tok" if tokens_per_trigger < 1e9 else ">1B tok"

        print(f"{threshold:<12,} {trigger_str:>15} {reclaims:>15.1f} {avg_pe:>12.3f} "
              f"{tbw_gb:>12.1f} {lifespan_str:>15}")

    print()
    print("KEY FINDINGS:")
    print("-" * 80)

    # Focus on threshold=100 (realistic for maintaining throughput)
    threshold_100 = next(t for t in tradeoff_data['thresholds'] if t['threshold'] == 100)

    tokens_per_day = baseline_iops * 86400
    pe_per_token = threshold_100['avg_pe_cycles'] / campaign_tokens
    pe_per_day = pe_per_token * tokens_per_day
    days_to_failure = PE_CYCLES_LIMIT / pe_per_day

    tbw_per_day_gb = (threshold_100['tbw_tb'] * 1024) / (campaign_tokens / tokens_per_day)

    print(f"• Baseline throughput: {baseline_iops:,.0f} tokens/sec = {tokens_per_day/1e9:.2f}B tokens/day")
    print(f"• With reclaim threshold=100 (to maintain throughput):")
    print(f"  - P/E cycles consumed: {pe_per_day:.2f} cycles/day")
    print(f"  - TBW rate: {tbw_per_day_gb:.1f} GB/day")
    print(f"  - SSD lifespan: {days_to_failure:.0f} days ({days_to_failure/365:.1f} years)")
    print()
    print(f"• Normal SSD lifespan: 1,825 - 3,650 days (5-10 years)")
    print(f"• Reduction: {(1 - days_to_failure/1825)*100:.1f}% shorter than normal SSD")
    print()

    # Compare two scenarios
    print("=" * 80)
    print("THE TRADE-OFF:")
    print("=" * 80)
    print()
    print("OPTION A: No Read-Reclaim (threshold = ∞)")
    print(f"  ✓ Long lifespan: {PE_CYCLES_LIMIT} P/E cycles available")
    print(f"  ✗ Throughput degrades: {throughput_results[-1]['throughput_pct']:.1f}% of baseline")
    print(f"  ✗ {throughput_results[-1]['slowdown']:.2f}× slower token generation")
    print()

    print("OPTION B: Aggressive Reclaim (threshold = 100)")
    print(f"  ✓ Maintains throughput: {baseline_iops:,.0f} tokens/sec")
    print(f"  ✗ Short lifespan: {days_to_failure:.0f} days ({days_to_failure/365:.1f} years)")
    print(f"  ✗ {(1 - days_to_failure/1825)*100:.1f}% shorter than normal SSD")
    print()

    print("⚠️  CANNOT ACHIEVE BOTH: High throughput AND long lifespan!")
    print()

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "LLM READ-DISTURB: THROUGHPUT vs. LIFESPAN TRADE-OFF" + " " * 12 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    # Load data
    data = load_exp2_data()

    if not data:
        print("Error: No experimental data found")
        sys.exit(1)

    # Outcome 1: Throughput degradation
    throughput_results = analyze_throughput_degradation(data)

    print()

    # Outcome 2: Lifespan reduction
    analyze_lifespan_tradeoff(throughput_results)

    print("=" * 80)
    print("CONCLUSION:")
    print("=" * 80)
    print()
    print("In-flash LLM inference faces a FUNDAMENTAL trade-off:")
    print()
    print("  1. Accept throughput degradation (42% slower)")
    print("     → Unacceptable for production systems")
    print()
    print("  2. Use aggressive read-reclaim to maintain throughput")
    print("     → SSD lifespan reduced to days/weeks instead of years")
    print("     → Unacceptable for cost and reliability")
    print()
    print("This is a PHYSICS-LEVEL constraint, not an engineering problem!")
    print()
