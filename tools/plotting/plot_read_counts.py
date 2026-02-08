#!/usr/bin/env python3
"""
Plot read count accumulation for LLM inference experiments

Shows how read counts build up across blocks over inference campaign.
Key metrics:
  - Average reads per block vs. tokens generated
  - Maximum reads per block vs. tokens generated
  - Read count distribution histogram
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

def plot_read_accumulation(results, output_file=None):
    """
    Plot read count accumulation over token generation

    Args:
        results: List of dicts with keys: 'name', 'tokens', 'avg_reads', 'max_reads'
        output_file: Path to save figure (optional)
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Sort by token count
    results = sorted(results, key=lambda x: x['tokens'])

    tokens = [r['tokens'] for r in results]
    avg_reads = [r['avg_reads'] for r in results]
    max_reads = [r['max_reads'] for r in results]

    # Plot 1: Average and max reads vs tokens
    ax1.plot(tokens, avg_reads, 'o-', label='Average reads/block', linewidth=2, markersize=8)
    ax1.plot(tokens, max_reads, 's--', label='Max reads/block', linewidth=2, markersize=8)
    ax1.set_xlabel('Tokens Generated', fontsize=12)
    ax1.set_ylabel('Read Count per Block', fontsize=12)
    ax1.set_title('Read-Disturb Accumulation', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3)
    ax1.set_yscale('log')

    # Add theoretical linear line
    if len(tokens) > 1:
        # Estimate slope from data
        slope = avg_reads[-1] / tokens[-1] if tokens[-1] > 0 else 0
        theory = [slope * t for t in tokens]
        ax1.plot(tokens, theory, 'k:', label='Linear (theoretical)', linewidth=1.5, alpha=0.6)
        ax1.legend(fontsize=11)

    # Plot 2: Read count distribution for final state
    if 'read_distribution' in results[-1]:
        dist = results[-1]['read_distribution']
        bins = dist.get('bins', [])
        counts = dist.get('counts', [])
        if bins and counts:
            ax2.bar(bins[:-1], counts, width=np.diff(bins), align='edge', alpha=0.7, edgecolor='black')
            ax2.set_xlabel('Read Count', fontsize=12)
            ax2.set_ylabel('Number of Blocks', fontsize=12)
            ax2.set_title(f'Read Distribution @ {tokens[-1]} tokens', fontsize=14, fontweight='bold')
            ax2.set_xscale('log')
            ax2.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Figure saved: {output_file}")
    else:
        plt.show()

def plot_single_experiment(result_file, output_file=None):
    """Plot results from a single experiment JSON"""
    data = load_result(result_file)

    # Extract metrics
    result = {
        'name': data.get('name', 'Unknown'),
        'tokens': data.get('tokens_generated', 0),
        'avg_reads': data.get('flash_operations', {}).get('avg_reads_per_block', 0),
        'max_reads': data.get('flash_operations', {}).get('max_reads_per_block', 0),
    }

    # For single experiment, create comparison with start state
    results = [
        {'tokens': 0, 'avg_reads': 0, 'max_reads': 0, 'name': 'Start'},
        result
    ]

    plot_read_accumulation(results, output_file)

def plot_comparison(result_files, output_file=None):
    """Plot comparison across multiple experiments"""
    results = []

    for rf in result_files:
        data = load_result(rf)
        results.append({
            'name': data.get('name', Path(rf).stem),
            'tokens': data.get('tokens_generated', 0),
            'avg_reads': data.get('flash_operations', {}).get('avg_reads_per_block', 0),
            'max_reads': data.get('flash_operations', {}).get('max_reads_per_block', 0),
        })

    plot_read_accumulation(results, output_file)

def main():
    parser = argparse.ArgumentParser(
        description='Plot read count accumulation for LLM inference experiments',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single experiment
  python3 plot_read_counts.py results/exp1.json -o figures/read_accumulation.png

  # Compare multiple runs
  python3 plot_read_counts.py results/exp1_10k.json results/exp1_50k.json results/exp1_100k.json -o figures/comparison.png
        """
    )

    parser.add_argument('results', nargs='+', help='JSON result file(s) from analyze_llm_results.py')
    parser.add_argument('-o', '--output', help='Output figure file (PNG/PDF)')
    parser.add_argument('--show', action='store_true', help='Show interactive plot')

    args = parser.parse_args()

    if len(args.results) == 1:
        plot_single_experiment(args.results[0], args.output if not args.show else None)
    else:
        plot_comparison(args.results, args.output if not args.show else None)

    if args.show and not args.output:
        plt.show()

if __name__ == '__main__':
    main()
