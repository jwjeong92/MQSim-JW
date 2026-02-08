#!/usr/bin/env python3
"""
Plot the read-reclaim trade-off: reliability vs. lifespan

This is THE KEY FIGURE for the paper. Shows that read-reclaim creates
a fundamental trade-off between reliability and flash lifetime.

  - Low reclaim threshold → Low ECC retries BUT high P/E cycles (short life)
  - High reclaim threshold → High ECC retries BUT low P/E cycles
  - NO sweet spot that satisfies both!
"""

import sys
import json
import argparse
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

def load_result(result_file):
    """Load JSON result from analyzer"""
    with open(result_file, 'r') as f:
        return json.load(f)

def plot_tradeoff(results, output_file=None):
    """
    Plot the fundamental trade-off between reliability and lifespan

    Args:
        results: List of dicts with keys: 'threshold', 'retry_rate', 'pe_cycles', 'reclaim_ops'
        output_file: Path to save figure (optional)
    """
    # Sort by threshold
    results = sorted(results, key=lambda x: x['threshold'])

    thresholds = [r['threshold'] for r in results]
    retry_rates = [r['retry_rate'] for r in results]
    pe_cycles = [r['pe_cycles'] for r in results]
    reclaim_ops = [r['reclaim_ops'] for r in results]

    # Create dual-axis plot
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Plot retry rate (reliability) on left axis
    color1 = 'tab:red'
    ax1.set_xlabel('Read-Reclaim Threshold (reads/block)', fontsize=12)
    ax1.set_ylabel('ECC Retry Rate (retries/1000 reads)', fontsize=12, color=color1)
    line1 = ax1.plot(thresholds, retry_rates, 'o-', linewidth=2.5, markersize=10,
                     color=color1, label='ECC Retry Rate')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_yscale('log')
    ax1.grid(True, alpha=0.3, which='both')

    # Plot P/E cycles (lifespan proxy) on right axis
    ax2 = ax1.twinx()
    color2 = 'tab:blue'
    ax2.set_ylabel('Extra P/E Cycles (from reclaim)', fontsize=12, color=color2)
    line2 = ax2.plot(thresholds, pe_cycles, 's--', linewidth=2.5, markersize=10,
                     color=color2, label='P/E Cycles (Reclaim)')
    ax2.tick_params(axis='y', labelcolor=color2)

    # Title and legend
    ax1.set_title('The Read-Reclaim Trade-Off:\nReliability vs. Flash Lifetime',
                  fontsize=14, fontweight='bold', pad=20)

    # Combine legends
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper center', bbox_to_anchor=(0.5, -0.12),
              ncol=2, fontsize=11, frameon=True, fancybox=True, shadow=True)

    # Add annotations for key zones
    if len(thresholds) >= 3:
        # Low threshold zone
        ax1.annotate('Low threshold:\nLow retries\nHIGH wear\n(short life)',
                    xy=(thresholds[0], retry_rates[0]),
                    xytext=(thresholds[0]*2, retry_rates[0]*10),
                    fontsize=9, ha='left',
                    bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.3),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.3'))

        # High threshold zone
        ax1.annotate('High threshold:\nHIGH retries\nLow wear',
                    xy=(thresholds[-1], retry_rates[-1]),
                    xytext=(thresholds[-1]*0.5, retry_rates[-1]*0.1),
                    fontsize=9, ha='right',
                    bbox=dict(boxstyle='round,pad=0.5', fc='lightblue', alpha=0.3),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=-0.3'))

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Figure saved: {output_file}")
    else:
        plt.show()

def plot_lifetime_projection(results, base_pe_limit=3000, output_file=None):
    """
    Plot projected flash lifetime under different reclaim policies

    Args:
        results: List of dicts with keys: 'threshold', 'pe_cycles', 'tokens'
        base_pe_limit: P/E cycle endurance limit (default 3000 for TLC)
        output_file: Path to save figure
    """
    # Sort by threshold
    results = sorted(results, key=lambda x: x['threshold'])

    thresholds = [r['threshold'] for r in results]
    pe_cycles = [r['pe_cycles'] for r in results]
    tokens = [r['tokens'] for r in results]

    # Calculate projected lifetime
    # Assume experiment ran for 'tokens' tokens, extrapolate to P/E limit
    avg_pe = np.mean(pe_cycles) if pe_cycles else 1  # Average P/E used in experiment
    experiment_tokens = tokens[0] if tokens else 100000  # Tokens in this experiment

    # Projected total tokens = (base_pe_limit / avg_pe_per_token) * experiment_tokens
    projected_tokens = []
    for pe in pe_cycles:
        if pe > 0:
            pe_per_token = pe / experiment_tokens
            total_tokens_possible = base_pe_limit / pe_per_token
            projected_tokens.append(total_tokens_possible)
        else:
            projected_tokens.append(float('inf'))

    # Convert to years (assume 1M tokens/day for high-usage scenario)
    tokens_per_day = 1_000_000
    projected_years = [t / tokens_per_day / 365 for t in projected_tokens]

    # Plot
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.bar(range(len(thresholds)), projected_years, color='steelblue', alpha=0.7, edgecolor='black')
    ax.set_xlabel('Read-Reclaim Threshold (reads/block)', fontsize=12)
    ax.set_ylabel('Projected Flash Lifetime (years)', fontsize=12)
    ax.set_title(f'Flash Lifetime Projection\n(PE limit: {base_pe_limit}, Usage: {tokens_per_day/1000:.0f}K tokens/day)',
                fontsize=14, fontweight='bold')
    ax.set_xticks(range(len(thresholds)))
    ax.set_xticklabels([f'{t/1000:.0f}K' if t >= 1000 else str(t) for t in thresholds], rotation=45)
    ax.grid(True, alpha=0.3, axis='y')

    # Add value labels on bars
    for i, (y, pe) in enumerate(zip(projected_years, pe_cycles)):
        label = f'{y:.1f} yr\n({pe} PE)' if y < 100 else f'>100 yr'
        ax.text(i, y, label, ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Figure saved: {output_file}")
    else:
        plt.show()

def extract_metrics(result_files):
    """Extract trade-off metrics from result files"""
    results = []

    for rf in result_files:
        data = load_result(rf)
        ecc = data.get('ecc_statistics', {})
        flash = data.get('flash_operations', {})
        gc = data.get('gc_wl_statistics', {})

        # Extract threshold from filename or config
        # Assume filename format: *_threshold_100K.json
        threshold = 100000  # default
        stem = Path(rf).stem
        if 'threshold' in stem:
            parts = stem.split('threshold_')
            if len(parts) > 1:
                threshold_str = parts[1].split('_')[0]
                if threshold_str.endswith('K'):
                    threshold = int(float(threshold_str[:-1]) * 1000)
                elif threshold_str.endswith('M'):
                    threshold = int(float(threshold_str[:-1]) * 1000000)
                else:
                    threshold = int(threshold_str)

        total_reads = flash.get('flash_reads', 0)
        retries = ecc.get('ecc_retries', 0)
        retry_rate = (retries / total_reads * 1000) if total_reads > 0 else 0

        # P/E cycles from reclaim (approximation)
        reclaim_ops = gc.get('read_reclaim_count', 0)
        # Each reclaim migrates a block, causing 1 erase + reprogramming
        pe_cycles = reclaim_ops  # Simplified: 1 reclaim ≈ 1 P/E cycle

        results.append({
            'threshold': threshold,
            'retry_rate': retry_rate,
            'pe_cycles': pe_cycles,
            'reclaim_ops': reclaim_ops,
            'tokens': data.get('tokens_generated', 0),
        })

    return results

def main():
    parser = argparse.ArgumentParser(
        description='Plot the read-reclaim trade-off analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Plot trade-off from sweep results
  python3 plot_tradeoff.py results/sweep_threshold_*.json -o figures/tradeoff.png

  # Plot lifetime projection
  python3 plot_tradeoff.py results/sweep_*.json --type lifetime -o figures/lifetime.png --pe-limit 3000
        """
    )

    parser.add_argument('results', nargs='+', help='JSON result file(s) from threshold sweep')
    parser.add_argument('-o', '--output', help='Output figure file (PNG/PDF)')
    parser.add_argument('--type', choices=['tradeoff', 'lifetime'], default='tradeoff',
                       help='Plot type: tradeoff (default) or lifetime projection')
    parser.add_argument('--pe-limit', type=int, default=3000,
                       help='P/E cycle endurance limit (default: 3000 for TLC)')
    parser.add_argument('--show', action='store_true', help='Show interactive plot')

    args = parser.parse_args()

    results = extract_metrics(args.results)

    if args.type == 'tradeoff':
        plot_tradeoff(results, args.output if not args.show else None)
    elif args.type == 'lifetime':
        plot_lifetime_projection(results, args.pe_limit, args.output if not args.show else None)

    if args.show and not args.output:
        plt.show()

if __name__ == '__main__':
    main()
