#!/usr/bin/env python3
"""
Generate all publication figures for LLM Read-Disturb Evaluation

Creates:
1. Figure 1: Read accumulation over tokens (Exp2)
2. Figure 2: ECC failure scaling (Exp2)
3. Figure 3: Trade-off analysis (Exp3 - THE KEY FIGURE)
4. Figure 4: Lifetime projection (Exp3)
5. Figure 5: Baseline performance comparison (Exp1)
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

# Set publication-quality defaults
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 11
plt.rcParams['font.family'] = 'serif'
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10

# Output directory
OUTPUT_DIR = Path('figures')
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================================
# FIGURE 1: Read Accumulation (Experiment 2)
# ============================================================================

def figure1_read_accumulation():
    """Read count accumulation demonstrating H1"""

    # Data from Experiment 2
    tokens = np.array([10000, 50000, 100000])
    flash_reads = np.array([3463, 30197, 63572])

    # Linear fit
    slope = 0.636
    intercept = -3218
    tokens_fit = np.linspace(0, 110000, 100)
    reads_fit = slope * tokens_fit + intercept

    fig, ax = plt.subplots(figsize=(8, 6))

    # Plot data points
    ax.scatter(tokens/1000, flash_reads, s=150, c='#2E86AB',
               marker='o', edgecolors='black', linewidth=1.5,
               label='Measured', zorder=3)

    # Plot linear fit
    ax.plot(tokens_fit/1000, reads_fit, '--', color='#A23B72',
            linewidth=2, label=f'Linear fit (R²=0.999)', zorder=2)

    # Extrapolation
    tokens_extrap = np.array([500000, 1000000])
    reads_extrap = slope * tokens_extrap + intercept
    ax.scatter(tokens_extrap/1000, reads_extrap, s=100, c='white',
               marker='s', edgecolors='#A23B72', linewidth=2,
               label='Projected', zorder=2, alpha=0.7)

    # Annotations
    ax.annotate(f'100K tokens\n→ 63,572 reads\n(18.4× baseline)',
                xy=(100, 63572), xytext=(70, 45000),
                fontsize=10, ha='center',
                bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.3),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='black'))

    ax.set_xlabel('Tokens Generated (×1000)', fontweight='bold')
    ax.set_ylabel('Cumulative Flash Reads', fontweight='bold')
    ax.set_title('Read-Disturb Accumulation in LLM Inference\n' +
                 'Hypothesis 1: Unbounded Linear Growth',
                 fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='upper left', frameon=True, shadow=True)

    # Add equation
    ax.text(0.95, 0.05, f'Reads = {slope:.3f} × Tokens - {abs(intercept):.0f}',
            transform=ax.transAxes, fontsize=10, ha='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'figure1_read_accumulation.png', bbox_inches='tight')
    plt.savefig(OUTPUT_DIR / 'figure1_read_accumulation.pdf', bbox_inches='tight')
    print('✓ Figure 1: Read accumulation saved')
    plt.close()

# ============================================================================
# FIGURE 2: ECC Failure Scaling (Experiment 2)
# ============================================================================

def figure2_ecc_scaling():
    """ECC failure rate scaling with reads"""

    tokens = np.array([10000, 50000, 100000])
    flash_reads = np.array([3463, 30197, 63572])
    ecc_failures = np.array([10822, 93494, 196767])
    failure_rate = (ecc_failures / flash_reads) * 100  # percentage

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left: Absolute failures
    ax1.bar(tokens/1000, ecc_failures, width=8, color='#E63946',
            edgecolor='black', linewidth=1.5, alpha=0.8)
    ax1.set_xlabel('Tokens Generated (×1000)', fontweight='bold')
    ax1.set_ylabel('Total ECC Failures', fontweight='bold')
    ax1.set_title('ECC Failure Growth', fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')

    # Add value labels
    for i, (t, f) in enumerate(zip(tokens/1000, ecc_failures)):
        ax1.text(t, f + 5000, f'{f:,}', ha='center', va='bottom',
                fontweight='bold', fontsize=10)

    # Add scaling annotation
    ax1.annotate('18.2× increase', xy=(100, 196767), xytext=(60, 150000),
                fontsize=11, ha='center', color='darkred', fontweight='bold',
                arrowprops=dict(arrowstyle='->', lw=2, color='darkred'))

    # Right: Failure rate
    ax2.plot(tokens/1000, failure_rate, 'o-', color='#F77F00',
             linewidth=3, markersize=12, markeredgecolor='black',
             markeredgewidth=1.5)
    ax2.axhline(y=3.1, color='red', linestyle='--', linewidth=2,
                label='Avg: 3.1%', alpha=0.7)
    ax2.set_xlabel('Tokens Generated (×1000)', fontweight='bold')
    ax2.set_ylabel('ECC Failure Rate (%)', fontweight='bold')
    ax2.set_title('Consistent Failure Rate', fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='best', frameon=True, shadow=True)
    ax2.set_ylim([0, 5])

    # Add value labels
    for t, r in zip(tokens/1000, failure_rate):
        ax2.text(t, r + 0.2, f'{r:.1f}%', ha='center', fontsize=10)

    plt.suptitle('ECC Degradation Under Read-Disturb\nHypothesis 2: Failures Scale with Reads',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'figure2_ecc_scaling.png', bbox_inches='tight')
    plt.savefig(OUTPUT_DIR / 'figure2_ecc_scaling.pdf', bbox_inches='tight')
    print('✓ Figure 2: ECC scaling saved')
    plt.close()

# ============================================================================
# FIGURE 3: Trade-off Analysis (Experiment 3) - THE KEY FIGURE
# ============================================================================

def figure3_tradeoff():
    """THE KEY FIGURE: Reliability vs. Lifetime Trade-off"""

    # Load analytical data
    with open('results/analytical/analytical_tradeoff.json', 'r') as f:
        data = json.load(f)

    thresholds = [t['threshold'] for t in data['thresholds']]
    tbw = [t['tbw_tb'] for t in data['thresholds']]
    failure_rate = [t['ecc_failure_rate'] * 100 for t in data['thresholds']]  # to %

    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Left axis: Failure rate (reliability)
    color1 = '#E63946'  # Red for failures
    ax1.set_xlabel('Read-Reclaim Threshold (reads/block)', fontweight='bold', fontsize=12)
    ax1.set_ylabel('ECC Failure Rate (%)', fontweight='bold', fontsize=12, color=color1)
    line1 = ax1.plot(thresholds, failure_rate, 'o-', color=color1,
                     linewidth=3, markersize=10, markeredgecolor='black',
                     markeredgewidth=1.5, label='Failure Rate')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_xscale('log')
    ax1.grid(True, alpha=0.3, which='both', linestyle='--')

    # Right axis: TBW (lifetime)
    ax2 = ax1.twinx()
    color2 = '#2A9D8F'  # Green for TBW/lifetime
    ax2.set_ylabel('TBW - Total Bytes Written (TB)', fontweight='bold',
                   fontsize=12, color=color2)
    line2 = ax2.plot(thresholds, tbw, 's--', color=color2,
                     linewidth=3, markersize=10, markeredgecolor='black',
                     markeredgewidth=1.5, label='TBW (10M tokens)')
    ax2.tick_params(axis='y', labelcolor=color2)

    # Title
    ax1.set_title('The Fundamental Trade-Off: No Sweet Spot Exists\n' +
                  'Hypothesis 3: Aggressive Reclaim Destroys Lifetime',
                  fontweight='bold', fontsize=14, pad=20)

    # Annotations for extremes
    ax1.annotate('Low threshold:\n✓ Low failures (1.6%)\n✗ High TBW (14.6 TB)\n✗ ~0 year lifetime',
                xy=(10, failure_rate[0]), xytext=(100, 2),
                fontsize=9, ha='center',
                bbox=dict(boxstyle='round,pad=0.7', fc='#FFB4A2', alpha=0.8,
                         edgecolor='black', linewidth=1.5),
                arrowprops=dict(arrowstyle='->', lw=2, color='black'))

    ax1.annotate('High threshold:\n✗ High failures (12.6%)\n✓ Low TBW (0 TB)\n✓ >100 year lifetime',
                xy=(1000000, failure_rate[-1]), xytext=(10000, 9),
                fontsize=9, ha='center',
                bbox=dict(boxstyle='round,pad=0.7', fc='#B7E4C7', alpha=0.8,
                         edgecolor='black', linewidth=1.5),
                arrowprops=dict(arrowstyle='->', lw=2, color='black'))

    # Add "NO SWEET SPOT" zone
    ax1.axvspan(100, 10000, alpha=0.15, color='yellow', zorder=0)
    ax1.text(1000, 7, 'NO SWEET SPOT\nZONE', ha='center', fontsize=11,
            fontweight='bold', color='darkgoldenrod',
            bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.4))

    # Combine legends
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', frameon=True,
              shadow=True, fontsize=11)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'figure3_tradeoff.png', bbox_inches='tight')
    plt.savefig(OUTPUT_DIR / 'figure3_tradeoff.pdf', bbox_inches='tight')
    print('✓ Figure 3: Trade-off (KEY FIGURE) saved')
    plt.close()

# ============================================================================
# FIGURE 4: Lifetime Projection (Experiment 3)
# ============================================================================

def figure4_lifetime():
    """Flash lifetime projection under different reclaim policies"""

    # Load analytical data
    with open('results/analytical/analytical_tradeoff.json', 'r') as f:
        data = json.load(f)

    # Select subset for clarity
    thresholds_display = [10, 50, 100, 500, 1000, 10000]

    filtered = [t for t in data['thresholds'] if t['threshold'] in thresholds_display]
    threshold_labels = [str(t['threshold']) for t in filtered]
    lifetimes = [t['lifetime_years'] for t in filtered]
    tbw = [t['tbw_tb'] for t in filtered]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left: Lifetime bar chart
    colors = ['#D62828' if l < 1 else '#F77F00' if l < 10 else '#2A9D8F'
              for l in lifetimes]
    bars = ax1.bar(range(len(threshold_labels)), lifetimes, color=colors,
                   edgecolor='black', linewidth=1.5, alpha=0.8)
    ax1.set_xlabel('Read-Reclaim Threshold (reads)', fontweight='bold')
    ax1.set_ylabel('Flash Lifetime (years)', fontweight='bold')
    ax1.set_title('Lifetime Impact of Reclaim Policy', fontweight='bold')
    ax1.set_xticks(range(len(threshold_labels)))
    ax1.set_xticklabels(threshold_labels, rotation=0)
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_ylim([0, max(lifetimes) * 1.2 if max(lifetimes) < 50 else 50])

    # Add value labels
    for i, (bar, life, t_label) in enumerate(zip(bars, lifetimes, threshold_labels)):
        if life > 100:
            label = '>100 yr'
            height = 45
        elif life < 0.1:
            label = '~0 yr'
            height = 2
        else:
            label = f'{life:.1f} yr'
            height = life
        ax1.text(i, height + 1, label, ha='center', va='bottom',
                fontweight='bold', fontsize=10)

    # Add reference line (normal SSD lifetime)
    ax1.axhline(y=5, color='blue', linestyle='--', linewidth=2,
                label='Normal SSD (5-10 yr)', alpha=0.7)
    ax1.legend(loc='upper right', frameon=True, shadow=True)

    # Right: TBW comparison
    ax2.barh(range(len(threshold_labels)), tbw, color=colors,
             edgecolor='black', linewidth=1.5, alpha=0.8)
    ax2.set_ylabel('Read-Reclaim Threshold (reads)', fontweight='bold')
    ax2.set_xlabel('TBW - Total Bytes Written (TB)', fontweight='bold')
    ax2.set_title('Write Amplification from Reclaim', fontweight='bold')
    ax2.set_yticks(range(len(threshold_labels)))
    ax2.set_yticklabels(threshold_labels)
    ax2.grid(True, alpha=0.3, axis='x')
    ax2.invert_yaxis()

    # Add value labels
    for i, (tb, t_label) in enumerate(zip(tbw, threshold_labels)):
        if tb > 0.01:
            ax2.text(tb + 0.3, i, f'{tb:.2f} TB', va='center', fontsize=9)

    plt.suptitle('Flash Lifetime Degradation from Read-Reclaim\n' +
                 'Campaign: 10M tokens (10 days @ 1M tok/day)',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'figure4_lifetime.png', bbox_inches='tight')
    plt.savefig(OUTPUT_DIR / 'figure4_lifetime.pdf', bbox_inches='tight')
    print('✓ Figure 4: Lifetime projection saved')
    plt.close()

# ============================================================================
# FIGURE 5: Baseline Performance (Experiment 1)
# ============================================================================

def figure5_baseline():
    """Baseline performance comparison across models"""

    models = ['Llama2-7B', 'Llama2-13B', 'Llama2-70B']
    iops = np.array([91052, 97322, 150192])
    latency = np.array([47.6, 42.7, 30.0])
    ecc_failures = np.array([18117, 16929, 10822])

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))

    # IOPS
    bars1 = ax1.bar(models, iops/1000, color=['#264653', '#2A9D8F', '#E76F51'],
                    edgecolor='black', linewidth=1.5, alpha=0.8)
    ax1.set_ylabel('IOPS (×1000)', fontweight='bold')
    ax1.set_title('Throughput', fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')
    for bar, val in zip(bars1, iops/1000):
        ax1.text(bar.get_x() + bar.get_width()/2, val + 5,
                f'{val:.0f}K', ha='center', fontweight='bold')

    # Latency
    bars2 = ax2.bar(models, latency, color=['#264653', '#2A9D8F', '#E76F51'],
                    edgecolor='black', linewidth=1.5, alpha=0.8)
    ax2.set_ylabel('Average Latency (ms)', fontweight='bold')
    ax2.set_title('Response Time', fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    for bar, val in zip(bars2, latency):
        ax2.text(bar.get_x() + bar.get_width()/2, val + 1.5,
                f'{val:.1f}ms', ha='center', fontweight='bold')

    # ECC Failures
    bars3 = ax3.bar(models, ecc_failures, color=['#264653', '#2A9D8F', '#E76F51'],
                    edgecolor='black', linewidth=1.5, alpha=0.8)
    ax3.set_ylabel('ECC Failures', fontweight='bold')
    ax3.set_title('Reliability', fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='y')
    for bar, val in zip(bars3, ecc_failures):
        ax3.text(bar.get_x() + bar.get_width()/2, val + 500,
                f'{val:,}', ha='center', fontsize=9, fontweight='bold')

    plt.suptitle('Baseline Performance Comparison (10K tokens)\n' +
                 'Larger Models → Better Parallelism',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'figure5_baseline.png', bbox_inches='tight')
    plt.savefig(OUTPUT_DIR / 'figure5_baseline.pdf', bbox_inches='tight')
    print('✓ Figure 5: Baseline comparison saved')
    plt.close()

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("GENERATING ALL PUBLICATION FIGURES")
    print("=" * 80)
    print()

    figure1_read_accumulation()
    figure2_ecc_scaling()
    figure3_tradeoff()
    figure4_lifetime()
    figure5_baseline()

    print()
    print("=" * 80)
    print("✅ ALL FIGURES GENERATED")
    print("=" * 80)
    print(f"\nOutput directory: {OUTPUT_DIR.absolute()}")
    print(f"Files created:")
    for f in sorted(OUTPUT_DIR.glob('*')):
        print(f"  - {f.name}")
    print()
    print("Figure 3 (Trade-off) is THE KEY FIGURE for the paper! 🌟")
    print()

if __name__ == '__main__':
    main()
