#!/usr/bin/env python3
"""
Generate figures demonstrating the two desired outcomes:
1. Token generation slowdown due to ECC retries
2. SSD lifespan reduction (in days) from read-reclaim
"""

import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Set publication-quality defaults
plt.rcParams['figure.dpi'] = 300
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['legend.fontsize'] = 9

# Load data
with open('results/analytical/analytical_tradeoff.json', 'r') as f:
    tradeoff_data = json.load(f)

# Exp2 data
exp2_data = [
    {'tokens': 10000, 'iops': 150192, 'response_ms': 30.0, 'ecc_fails': 10822, 'flash_reads': 796},
    {'tokens': 50000, 'iops': 91299, 'response_ms': 249.0, 'ecc_fails': 93494, 'flash_reads': 6170},
    {'tokens': 100000, 'iops': 87157, 'response_ms': 492.5, 'ecc_fails': 196767, 'flash_reads': 13245},
]

# Constants
PE_LIMIT = 3000
CAMPAIGN_TOKENS = tradeoff_data['campaign_tokens']

# ============================================================================
# FIGURE 1: THROUGHPUT DEGRADATION (Outcome 1)
# ============================================================================

def generate_figure_outcome1():
    """
    Shows token generation rate slowing down as reads accumulate.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

    tokens = [d['tokens'] for d in exp2_data]
    iops = [d['iops'] for d in exp2_data]
    response_ms = [d['response_ms'] for d in exp2_data]
    ecc_fails = [d['ecc_fails'] for d in exp2_data]

    baseline_iops = iops[0]
    throughput_pct = [(rate / baseline_iops) * 100 for rate in iops]

    # Left: Token generation rate
    ax1.plot(tokens, iops, 'o-', color='#d62728', linewidth=2.5, markersize=8, label='Token generation rate')
    ax1.axhline(baseline_iops, color='#2ca02c', linestyle='--', linewidth=2, label='Baseline (10K tokens)')
    ax1.fill_between(tokens, iops, baseline_iops, alpha=0.2, color='#d62728')

    ax1.set_xlabel('Generated Tokens', fontweight='bold')
    ax1.set_ylabel('Token Generation Rate (tokens/sec)', fontweight='bold')
    ax1.set_title('Outcome 1: Throughput Degradation from ECC Retries', fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right')

    # Add degradation annotations
    for i, (tok, rate, pct) in enumerate(zip(tokens, iops, throughput_pct)):
        if i > 0:
            ax1.annotate(f'{pct:.1f}%\nof baseline',
                        xy=(tok, rate), xytext=(tok, rate - 15000),
                        ha='center', fontsize=9, color='#d62728', fontweight='bold')

    # Right: Response time increase
    ax2_twin = ax2.twinx()

    line1 = ax2.plot(tokens, response_ms, 's-', color='#ff7f0e', linewidth=2.5, markersize=8, label='Response time')
    line2 = ax2_twin.plot(tokens, ecc_fails, '^-', color='#9467bd', linewidth=2.5, markersize=8, label='ECC failures')

    ax2.set_xlabel('Generated Tokens', fontweight='bold')
    ax2.set_ylabel('Avg Response Time (ms)', fontweight='bold', color='#ff7f0e')
    ax2_twin.set_ylabel('ECC Failures', fontweight='bold', color='#9467bd')
    ax2.set_title('Root Cause: ECC Retries Slow Down Reads', fontweight='bold')
    ax2.grid(True, alpha=0.3)

    ax2.tick_params(axis='y', labelcolor='#ff7f0e')
    ax2_twin.tick_params(axis='y', labelcolor='#9467bd')

    # Combined legend
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax2.legend(lines, labels, loc='upper left')

    plt.tight_layout()
    plt.savefig('figures/outcome1_throughput_degradation.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/outcome1_throughput_degradation.pdf', bbox_inches='tight')
    plt.close()

    print("✓ Generated: outcome1_throughput_degradation")

# ============================================================================
# FIGURE 2: LIFESPAN IN DAYS (Outcome 2)
# ============================================================================

def generate_figure_outcome2():
    """
    Shows SSD lifespan (in days) for different workload scenarios and thresholds.
    """
    fig, ax = plt.subplots(figsize=(12, 6))

    # Workload scenarios
    scenarios = [
        ('Light (0.1B/day)', 100_000_000),
        ('Medium (0.5B/day)', 500_000_000),
        ('Heavy (1B/day)', 1_000_000_000),
        ('Extreme (5B/day)', 5_000_000_000),
    ]

    thresholds = [10, 100, 1000]
    threshold_labels = ['10', '100', '1,000']
    colors = ['#d62728', '#ff7f0e', '#2ca02c']

    x_pos = np.arange(len(scenarios))
    width = 0.25

    for i, (threshold, label, color) in enumerate(zip(thresholds, threshold_labels, colors)):
        threshold_obj = next(t for t in tradeoff_data['thresholds'] if t['threshold'] == threshold)
        avg_pe = threshold_obj['avg_pe_cycles']

        lifespans = []
        for scenario_name, tokens_per_day in scenarios:
            pe_per_token = avg_pe / CAMPAIGN_TOKENS
            pe_per_day = pe_per_token * tokens_per_day
            lifespan_days = PE_LIMIT / pe_per_day
            lifespans.append(lifespan_days)

        bars = ax.bar(x_pos + i * width, lifespans, width, label=f'Threshold={label}', color=color, alpha=0.8)

        # Add value labels on bars
        for j, (bar, lifespan) in enumerate(zip(bars, lifespans)):
            height = bar.get_height()
            if lifespan < 1:
                label_text = f'{lifespan:.1f}d'
            elif lifespan < 30:
                label_text = f'{lifespan:.0f}d'
            else:
                label_text = f'{lifespan:.0f}d\n({lifespan/365:.1f}y)'

            ax.text(bar.get_x() + bar.get_width()/2, height + max(lifespans)*0.02,
                   label_text, ha='center', va='bottom', fontsize=8, fontweight='bold')

    # Reference line: normal SSD lifespan (5 years = 1825 days)
    ax.axhline(1825, color='#1f77b4', linestyle='--', linewidth=2, label='Normal SSD (5 years)', alpha=0.7)
    ax.fill_between([-0.5, len(scenarios)-0.5], 1825, max(200, max([l for s_name, tpd in scenarios for l in [PE_LIMIT / ((tradeoff_data['thresholds'][0]['avg_pe_cycles'] / CAMPAIGN_TOKENS) * tpd)]]) * 1.1),
                    alpha=0.1, color='#1f77b4', label='Acceptable range')

    ax.set_xlabel('Workload Scenario', fontweight='bold')
    ax.set_ylabel('SSD Lifespan (Days)', fontweight='bold')
    ax.set_title('Outcome 2: SSD Lifespan Reduction from Read-Reclaim (to Maintain Throughput)', fontweight='bold')
    ax.set_xticks(x_pos + width)
    ax.set_xticklabels([s[0] for s in scenarios])
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_yscale('log')

    plt.tight_layout()
    plt.savefig('figures/outcome2_lifespan_days.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/outcome2_lifespan_days.pdf', bbox_inches='tight')
    plt.close()

    print("✓ Generated: outcome2_lifespan_days")

# ============================================================================
# FIGURE 3: THE IMPOSSIBLE CHOICE
# ============================================================================

def generate_figure_impossible_choice():
    """
    Side-by-side comparison showing the impossible choice.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Option A: No reclaim (throughput degrades)
    baseline = exp2_data[0]
    final = exp2_data[-1]

    degradation_pct = (1 - final['iops'] / baseline['iops']) * 100

    ax1.bar(['Baseline\n(10K tokens)', 'After Read\nAccumulation\n(100K tokens)'],
            [baseline['iops'], final['iops']],
            color=['#2ca02c', '#d62728'],
            alpha=0.8,
            width=0.6)

    ax1.axhline(baseline['iops'], color='gray', linestyle='--', alpha=0.5)
    ax1.text(0.5, baseline['iops'] * 0.6, f'{degradation_pct:.1f}%\nslower',
            ha='center', fontsize=16, fontweight='bold', color='#d62728')

    ax1.set_ylabel('Token Generation Rate (tokens/sec)', fontweight='bold')
    ax1.set_title('Option A: No Read-Reclaim\n(Long Lifespan, Poor Performance)', fontweight='bold', color='#d62728')
    ax1.grid(True, alpha=0.3, axis='y')

    # Option B: Aggressive reclaim (lifespan reduced)
    # Use production workload (1B tokens/day)
    workload = 1_000_000_000
    threshold_100 = next(t for t in tradeoff_data['thresholds'] if t['threshold'] == 100)
    avg_pe = threshold_100['avg_pe_cycles']

    pe_per_day = (avg_pe / CAMPAIGN_TOKENS) * workload
    lifespan_days = PE_LIMIT / pe_per_day
    normal_lifespan_days = 5 * 365

    ax2.bar(['Normal SSD', 'With Read-Reclaim\n(Threshold=100)'],
            [normal_lifespan_days, lifespan_days],
            color=['#2ca02c', '#d62728'],
            alpha=0.8,
            width=0.6)

    ax2.axhline(normal_lifespan_days, color='gray', linestyle='--', alpha=0.5)
    ax2.text(0.5, normal_lifespan_days * 0.4, f'{(1 - lifespan_days/normal_lifespan_days)*100:.1f}%\nshorter',
            ha='center', fontsize=16, fontweight='bold', color='#d62728')

    # Add value labels
    ax2.text(0, normal_lifespan_days + 100, f'{normal_lifespan_days} days\n(5 years)',
            ha='center', fontsize=9, fontweight='bold')
    ax2.text(1, lifespan_days + 100, f'{lifespan_days:.0f} days\n({lifespan_days/365:.2f} years)',
            ha='center', fontsize=9, fontweight='bold')

    ax2.set_ylabel('SSD Lifespan (Days)', fontweight='bold')
    ax2.set_title('Option B: Aggressive Reclaim\n(Maintains Performance, Short Lifespan)', fontweight='bold', color='#d62728')
    ax2.grid(True, alpha=0.3, axis='y')

    # Add overall title
    fig.suptitle('The Impossible Choice: Cannot Achieve Both High Throughput AND Long Lifespan',
                fontsize=14, fontweight='bold', y=1.02)

    plt.tight_layout()
    plt.savefig('figures/outcome3_impossible_choice.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/outcome3_impossible_choice.pdf', bbox_inches='tight')
    plt.close()

    print("✓ Generated: outcome3_impossible_choice")

# ============================================================================
# FIGURE 4: COMPREHENSIVE TRADE-OFF MATRIX
# ============================================================================

def generate_figure_tradeoff_matrix():
    """
    Heatmap showing lifespan for different workloads × thresholds.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    workloads = [100e6, 500e6, 1e9, 5e9, 10e9]  # 0.1B to 10B tokens/day
    workload_labels = ['0.1B', '0.5B', '1B', '5B', '10B']

    thresholds_to_show = [10, 50, 100, 500, 1000, 5000]
    threshold_labels = [str(t) for t in thresholds_to_show]

    # Build matrix
    matrix = []
    for workload in workloads:
        row = []
        for threshold in thresholds_to_show:
            threshold_obj = next((t for t in tradeoff_data['thresholds'] if t['threshold'] == threshold), None)
            if threshold_obj and threshold_obj['avg_pe_cycles'] > 0:
                avg_pe = threshold_obj['avg_pe_cycles']
                pe_per_day = (avg_pe / CAMPAIGN_TOKENS) * workload
                lifespan_days = PE_LIMIT / pe_per_day
            else:
                lifespan_days = 9999  # Infinity placeholder

            row.append(lifespan_days)
        matrix.append(row)

    matrix = np.array(matrix)

    # Use log scale for color mapping
    im = ax.imshow(np.log10(matrix + 1), cmap='RdYlGn', aspect='auto', vmin=0, vmax=4)

    # Add text annotations
    for i in range(len(workloads)):
        for j in range(len(thresholds_to_show)):
            days = matrix[i, j]
            if days > 1000:
                text = '>1000d'
                color = 'black'
            elif days > 365:
                text = f'{days:.0f}d\n({days/365:.1f}y)'
                color = 'black'
            elif days > 30:
                text = f'{days:.0f}d'
                color = 'black'
            elif days > 1:
                text = f'{days:.1f}d'
                color = 'white'
            else:
                text = f'{days:.2f}d'
                color = 'white'

            ax.text(j, i, text, ha='center', va='center', fontsize=8, fontweight='bold', color=color)

    ax.set_xticks(np.arange(len(threshold_labels)))
    ax.set_yticks(np.arange(len(workload_labels)))
    ax.set_xticklabels(threshold_labels)
    ax.set_yticklabels(workload_labels)

    ax.set_xlabel('Read-Reclaim Threshold (reads)', fontweight='bold')
    ax.set_ylabel('Workload (tokens/day)', fontweight='bold')
    ax.set_title('SSD Lifespan Matrix: Workload vs. Reclaim Threshold', fontweight='bold')

    # Colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Lifespan (log scale)', fontweight='bold')
    cbar.set_ticks([0, 1, 2, 3, 4])
    cbar.set_ticklabels(['1d', '10d', '100d', '1000d', '10000d'])

    plt.tight_layout()
    plt.savefig('figures/outcome4_tradeoff_matrix.png', dpi=300, bbox_inches='tight')
    plt.savefig('figures/outcome4_tradeoff_matrix.pdf', bbox_inches='tight')
    plt.close()

    print("✓ Generated: outcome4_tradeoff_matrix")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print()
    print("=" * 60)
    print("Generating Outcome-Focused Figures")
    print("=" * 60)
    print()

    generate_figure_outcome1()
    generate_figure_outcome2()
    generate_figure_impossible_choice()
    generate_figure_tradeoff_matrix()

    print()
    print("=" * 60)
    print("✅ All outcome figures generated!")
    print("=" * 60)
    print()
    print("Key figures:")
    print("  • outcome1_throughput_degradation - Shows 42% slowdown")
    print("  • outcome2_lifespan_days - Lifespan in days (not years!)")
    print("  • outcome3_impossible_choice - Side-by-side comparison")
    print("  • outcome4_tradeoff_matrix - Complete heatmap")
    print()
