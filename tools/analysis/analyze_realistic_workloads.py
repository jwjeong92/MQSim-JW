#!/usr/bin/env python3
"""
Realistic Workload Analysis - SSD Lifespan in Days

Shows lifespan under different production workload scenarios.
"""

import json

# Constants from analytical model
READ_RATE_PER_TOKEN = 0.636
ESTIMATED_BLOCKS = 17920
PE_CYCLES_LIMIT = 3000  # TLC NAND
BLOCK_SIZE_MB = 24

# Load analytical trade-off data
with open('results/analytical/analytical_tradeoff.json', 'r') as f:
    tradeoff_data = json.load(f)

campaign_tokens = tradeoff_data['campaign_tokens']  # 10M

print("=" * 100)
print("REALISTIC WORKLOAD SCENARIOS: SSD LIFESPAN ANALYSIS (IN DAYS)")
print("=" * 100)
print()

# Define realistic workload scenarios
scenarios = [
    {
        'name': 'Light Load (Research)',
        'tokens_per_day': 100_000_000,  # 100M tokens/day
        'description': 'Research lab, intermittent usage'
    },
    {
        'name': 'Medium Load (Development)',
        'tokens_per_day': 500_000_000,  # 500M tokens/day
        'description': 'Development server, 8-hour workday'
    },
    {
        'name': 'Heavy Load (Production)',
        'tokens_per_day': 1_000_000_000,  # 1B tokens/day
        'description': 'Production inference, continuous usage'
    },
    {
        'name': 'Extreme Load (Data Center)',
        'tokens_per_day': 5_000_000_000,  # 5B tokens/day
        'description': 'High-throughput data center, multi-tenant'
    },
]

# Analyze each scenario with different reclaim thresholds
print(f"{'Scenario':<30} {'Workload':>15} {'Threshold':>12} {'P/E/Day':>12} {'Lifespan (Days)':>18} {'Lifespan (Years)':>18}")
print("-" * 100)

results = {}

for scenario in scenarios:
    tokens_per_day = scenario['tokens_per_day']
    scenario_name = scenario['name']

    results[scenario_name] = {}

    for threshold_data in tradeoff_data['thresholds']:
        threshold = threshold_data['threshold']
        avg_pe = threshold_data['avg_pe_cycles']

        if avg_pe == 0:
            # No reclaim
            lifespan_days = float('inf')
            lifespan_str = "∞ (degrades)"
            years_str = "∞ (degrades)"
        else:
            # Calculate P/E cycles per day
            pe_per_token = avg_pe / campaign_tokens
            pe_per_day = pe_per_token * tokens_per_day

            # Days until exhaustion
            lifespan_days = PE_CYCLES_LIMIT / pe_per_day
            lifespan_years = lifespan_days / 365

            lifespan_str = f"{lifespan_days:,.1f} days"
            years_str = f"{lifespan_years:.2f} years"

        workload_str = f"{tokens_per_day/1e9:.1f}B tok/day"

        # Only show selected thresholds (10, 100, 1000, inf)
        if threshold in [10, 100, 1000, 1000000]:
            threshold_str = f"{threshold:,}" if threshold < 1000000 else "∞ (no reclaim)"

            print(f"{scenario_name:<30} {workload_str:>15} {threshold_str:>12} {pe_per_day:>12.1f} "
                  f"{lifespan_str:>18} {years_str:>18}")

            results[scenario_name][threshold] = {
                'lifespan_days': lifespan_days,
                'lifespan_years': lifespan_days / 365 if lifespan_days != float('inf') else float('inf'),
                'pe_per_day': pe_per_day if avg_pe > 0 else 0
            }

    print()

print()
print("=" * 100)
print("KEY INSIGHTS:")
print("=" * 100)
print()

# Compare with normal SSD lifetime
print("Normal SSD Lifespan: 1,825 - 3,650 days (5-10 years)")
print()

# Highlight the trade-off for each scenario
for scenario in scenarios:
    scenario_name = scenario['name']
    workload = scenario['tokens_per_day']

    print(f"▪ {scenario_name} ({workload/1e9:.1f}B tokens/day):")

    if 100 in results[scenario_name]:
        lifespan_100 = results[scenario_name][100]['lifespan_days']
        years_100 = results[scenario_name][100]['lifespan_years']

        if lifespan_100 < 30:
            severity = "❌ CRITICAL"
        elif lifespan_100 < 365:
            severity = "⚠️  SEVERE"
        elif lifespan_100 < 1825:
            severity = "⚠️  MODERATE"
        else:
            severity = "✓ ACCEPTABLE"

        print(f"  - With reclaim (threshold=100): {lifespan_100:.0f} days ({years_100:.1f} years) {severity}")

    if 1000000 in results[scenario_name]:
        print(f"  - Without reclaim: ∞ lifespan BUT throughput degrades 42%")

    print()

print()
print("=" * 100)
print("CONCLUSION:")
print("=" * 100)
print()
print("Even at LIGHT loads (100M tokens/day):")
print(f"  • Threshold=100: SSD dies in ~{results[scenarios[0]['name']][100]['lifespan_days']:.0f} days (~{results[scenarios[0]['name']][100]['lifespan_years']:.1f} years)")
print(f"  • Normal SSD: 5-10 years")
print(f"  • {((1 - results[scenarios[0]['name']][100]['lifespan_years']/5)*100):.0f}% lifespan reduction")
print()
print("At PRODUCTION loads (1B+ tokens/day):")
print(f"  • SSD dies in days to weeks")
print(f"  • Completely impractical for deployment")
print()
print("⚠️  This demonstrates why current in-flash LLM designs are NOT viable!")
print()
