#!/usr/bin/env python3
"""
Plot ECC retry statistics for LLM inference experiments

Shows how ECC retry rate increases over time due to read-disturb accumulation.
Key metrics:
  - ECC retry rate vs. tokens generated
  - Uncorrectable error rate vs. tokens generated
  - Retry rate per 1000 reads (normalized metric)
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

def plot_ecc_trends(results, output_file=None):
    """
    Plot ECC retry trends over token generation

    Args:
        results: List of dicts with keys: 'name', 'tokens', 'retry_rate', 'uncorrectable_rate'
        output_file: Path to save figure (optional)
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Sort by token count
    results = sorted(results, key=lambda x: x['tokens'])

    tokens = [r['tokens'] for r in results]
    retry_rate = [r['retry_rate'] for r in results]
    uncorrectable_rate = [r['uncorrectable_rate'] for r in results]

    # Plot 1: Retry rate over time
    ax1.plot(tokens, retry_rate, 'o-', linewidth=2, markersize=8, color='orange', label='Retry rate')
    ax1.set_xlabel('Tokens Generated', fontsize=12)
    ax1.set_ylabel('ECC Retry Rate (retries/1000 reads)', fontsize=12)
    ax1.set_title('ECC Retry Rate vs. Token Count', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.set_yscale('log')

    # Add warning threshold line
    warning_threshold = 1.0  # 1 retry per 1000 reads
    ax1.axhline(y=warning_threshold, color='r', linestyle='--', linewidth=1.5,
                label=f'Warning threshold ({warning_threshold} retries/1K reads)', alpha=0.7)
    ax1.legend(fontsize=10)

    # Plot 2: Uncorrectable error rate
    ax2.plot(tokens, uncorrectable_rate, 's-', linewidth=2, markersize=8, color='red', label='Uncorrectable rate')
    ax2.set_xlabel('Tokens Generated', fontsize=12)
    ax2.set_ylabel('Uncorrectable Error Rate (errors/1000 reads)', fontsize=12)
    ax2.set_title('Uncorrectable Error Rate vs. Token Count', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.set_yscale('log')

    # Add critical threshold line
    critical_threshold = 0.1  # 0.1 uncorrectable per 1000 reads
    ax2.axhline(y=critical_threshold, color='darkred', linestyle='--', linewidth=1.5,
                label=f'Critical threshold ({critical_threshold} errors/1K reads)', alpha=0.7)
    ax2.legend(fontsize=10)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Figure saved: {output_file}")
    else:
        plt.show()

def plot_ecc_breakdown(results, output_file=None):
    """
    Plot stacked breakdown of ECC outcomes

    Shows: successful reads, retry successes, uncorrectable errors
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    # Sort by token count
    results = sorted(results, key=lambda x: x['tokens'])

    tokens = [r['tokens'] for r in results]
    total_reads = [r['total_reads'] for r in results]
    retries = [r['retries'] for r in results]
    uncorrectable = [r['uncorrectable'] for r in results]

    # Calculate successful first-pass and successful after retries
    successful_first = [tr - ret for tr, ret in zip(total_reads, retries)]
    successful_retry = [ret - unc for ret, unc in zip(retries, uncorrectable)]

    # Stacked bar chart
    width = 0.6
    x = np.arange(len(tokens))

    ax.bar(x, successful_first, width, label='First-pass success', color='green', alpha=0.8)
    ax.bar(x, successful_retry, width, bottom=successful_first, label='Success after retry', color='orange', alpha=0.8)
    ax.bar(x, uncorrectable, width, bottom=[sf + sr for sf, sr in zip(successful_first, successful_retry)],
           label='Uncorrectable', color='red', alpha=0.8)

    ax.set_xlabel('Tokens Generated', fontsize=12)
    ax.set_ylabel('Number of Reads', fontsize=12)
    ax.set_title('ECC Outcome Breakdown', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([f'{t}K' if t >= 1000 else str(t) for t in tokens])
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Figure saved: {output_file}")
    else:
        plt.show()

def plot_comparison(result_files, output_file=None, plot_type='trends'):
    """Plot comparison across multiple experiments"""
    results = []

    for rf in result_files:
        data = load_result(rf)
        ecc = data.get('ecc_statistics', {})
        flash = data.get('flash_operations', {})

        total_reads = flash.get('flash_reads', 0)
        retries = ecc.get('ecc_retries', 0)
        uncorrectable = ecc.get('uncorrectable_errors', 0)

        # Calculate rates per 1000 reads
        retry_rate = (retries / total_reads * 1000) if total_reads > 0 else 0
        uncorrectable_rate = (uncorrectable / total_reads * 1000) if total_reads > 0 else 0

        results.append({
            'name': data.get('name', Path(rf).stem),
            'tokens': data.get('tokens_generated', 0),
            'retry_rate': retry_rate,
            'uncorrectable_rate': uncorrectable_rate,
            'total_reads': total_reads,
            'retries': retries,
            'uncorrectable': uncorrectable,
        })

    if plot_type == 'trends':
        plot_ecc_trends(results, output_file)
    elif plot_type == 'breakdown':
        plot_ecc_breakdown(results, output_file)

def main():
    parser = argparse.ArgumentParser(
        description='Plot ECC retry statistics for LLM inference experiments',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Plot retry trends
  python3 plot_ecc_retries.py results/exp1_10k.json results/exp1_50k.json results/exp1_100k.json -o figures/ecc_trends.png

  # Plot breakdown
  python3 plot_ecc_retries.py results/*.json --type breakdown -o figures/ecc_breakdown.png
        """
    )

    parser.add_argument('results', nargs='+', help='JSON result file(s) from analyze_llm_results.py')
    parser.add_argument('-o', '--output', help='Output figure file (PNG/PDF)')
    parser.add_argument('--type', choices=['trends', 'breakdown'], default='trends',
                       help='Plot type: trends (default) or breakdown')
    parser.add_argument('--show', action='store_true', help='Show interactive plot')

    args = parser.parse_args()

    plot_comparison(args.results, args.output if not args.show else None, args.type)

    if args.show and not args.output:
        plt.show()

if __name__ == '__main__':
    main()
