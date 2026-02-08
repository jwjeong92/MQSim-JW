#!/usr/bin/env python3
"""
Compare results across multiple LLM inference experiments

Generates comparison tables and summary statistics for experiments.
"""

import json
import argparse
from pathlib import Path
from tabulate import tabulate

def load_result(result_file):
    """Load JSON result from analyzer"""
    with open(result_file, 'r') as f:
        return json.load(f)

def format_number(n, precision=2):
    """Format large numbers with K/M/G suffixes"""
    if n >= 1e9:
        return f"{n/1e9:.{precision}f}G"
    elif n >= 1e6:
        return f"{n/1e6:.{precision}f}M"
    elif n >= 1e3:
        return f"{n/1e3:.{precision}f}K"
    else:
        return f"{n:.{precision}f}"

def compare_performance(result_files):
    """Compare performance metrics across experiments"""
    headers = ["Experiment", "Tokens", "IOPS", "Bandwidth (MB/s)", "Avg Latency (μs)"]
    rows = []

    for rf in result_files:
        data = load_result(rf)
        name = data.get('name', Path(rf).stem)
        io_stats = data.get('host_io_statistics', {})

        rows.append([
            name,
            format_number(data.get('tokens_generated', 0)),
            format_number(io_stats.get('iops', 0)),
            format_number(io_stats.get('bandwidth_mbps', 0)),
            f"{io_stats.get('avg_response_time_us', 0):.2f}",
        ])

    print("\n" + "="*80)
    print("PERFORMANCE COMPARISON")
    print("="*80)
    print(tabulate(rows, headers=headers, tablefmt='grid'))

def compare_flash_operations(result_files):
    """Compare flash operation counts"""
    headers = ["Experiment", "Flash Reads", "Flash Writes", "Erases", "GC Execs", "Reclaim Ops"]
    rows = []

    for rf in result_files:
        data = load_result(rf)
        name = data.get('name', Path(rf).stem)
        flash = data.get('flash_operations', {})
        gc = data.get('gc_wl_statistics', {})

        rows.append([
            name,
            format_number(flash.get('flash_reads', 0)),
            format_number(flash.get('flash_writes', 0)),
            format_number(flash.get('flash_erases', 0)),
            format_number(gc.get('gc_executions', 0)),
            format_number(gc.get('read_reclaim_count', 0)),
        ])

    print("\n" + "="*80)
    print("FLASH OPERATIONS COMPARISON")
    print("="*80)
    print(tabulate(rows, headers=headers, tablefmt='grid'))

def compare_ecc_stats(result_files):
    """Compare ECC statistics (KEY METRICS)"""
    headers = ["Experiment", "ECC Retries", "Failures", "Uncorrectable", "Retry Rate*", "Failure Rate*"]
    rows = []

    for rf in result_files:
        data = load_result(rf)
        name = data.get('name', Path(rf).stem)
        ecc = data.get('ecc_statistics', {})
        flash = data.get('flash_operations', {})

        total_reads = flash.get('flash_reads', 0)
        retries = ecc.get('ecc_retries', 0)
        failures = ecc.get('ecc_failures', 0)
        uncorrectable = ecc.get('uncorrectable_errors', 0)

        retry_rate = (retries / total_reads * 1000) if total_reads > 0 else 0
        failure_rate = (failures / total_reads * 1000) if total_reads > 0 else 0

        rows.append([
            name,
            format_number(retries),
            format_number(failures),
            format_number(uncorrectable),
            f"{retry_rate:.2f}",
            f"{failure_rate:.2f}",
        ])

    print("\n" + "="*80)
    print("ECC STATISTICS COMPARISON (KEY METRICS)")
    print("="*80)
    print(tabulate(rows, headers=headers, tablefmt='grid'))
    print("\n* Per 1000 reads")

def compare_read_counts(result_files):
    """Compare read count statistics"""
    headers = ["Experiment", "Avg Reads/Block", "Max Reads/Block", "Blocks w/ Reads"]
    rows = []

    for rf in result_files:
        data = load_result(rf)
        name = data.get('name', Path(rf).stem)
        flash = data.get('flash_operations', {})

        rows.append([
            name,
            format_number(flash.get('avg_reads_per_block', 0)),
            format_number(flash.get('max_reads_per_block', 0)),
            format_number(flash.get('blocks_with_reads', 0)),
        ])

    print("\n" + "="*80)
    print("READ-DISTURB ACCUMULATION")
    print("="*80)
    print(tabulate(rows, headers=headers, tablefmt='grid'))

def generate_summary(result_files, output_file=None):
    """Generate comprehensive comparison report"""
    print("\n" + "="*80)
    print(f"EXPERIMENT COMPARISON REPORT ({len(result_files)} experiments)")
    print("="*80)

    compare_performance(result_files)
    compare_flash_operations(result_files)
    compare_read_counts(result_files)
    compare_ecc_stats(result_files)

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    # Find experiment with highest/lowest metrics
    all_data = [load_result(rf) for rf in result_files]

    # Highest ECC retry rate
    max_retry = max(all_data, key=lambda d: d.get('ecc_statistics', {}).get('ecc_retries', 0))
    print(f"\n⚠️  Highest ECC retries: {max_retry.get('name', 'Unknown')} "
          f"({format_number(max_retry.get('ecc_statistics', {}).get('ecc_retries', 0))})")

    # Most reclaim operations
    max_reclaim = max(all_data, key=lambda d: d.get('gc_wl_statistics', {}).get('read_reclaim_count', 0))
    print(f"🔄 Most reclaim ops: {max_reclaim.get('name', 'Unknown')} "
          f"({format_number(max_reclaim.get('gc_wl_statistics', {}).get('read_reclaim_count', 0))})")

    # Highest read counts
    max_reads = max(all_data, key=lambda d: d.get('flash_operations', {}).get('max_reads_per_block', 0))
    print(f"📖 Highest read count: {max_reads.get('name', 'Unknown')} "
          f"({format_number(max_reads.get('flash_operations', {}).get('max_reads_per_block', 0))} reads/block)")

    print("\n" + "="*80)

def main():
    parser = argparse.ArgumentParser(
        description='Compare LLM inference experiment results',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare baseline experiments
  python3 compare_experiments.py results/exp1_baseline/*.json

  # Compare read-disturb accumulation
  python3 compare_experiments.py results/exp2_accumulation/*.json

  # Compare trade-off sweep
  python3 compare_experiments.py results/exp3_tradeoff/threshold_*.json
        """
    )

    parser.add_argument('results', nargs='+', help='JSON result files to compare')
    parser.add_argument('-o', '--output', help='Save report to file')

    args = parser.parse_args()

    # Redirect output if requested
    if args.output:
        import sys
        sys.stdout = open(args.output, 'w')

    generate_summary(args.results)

    if args.output:
        sys.stdout.close()
        print(f"Report saved to: {args.output}")

if __name__ == '__main__':
    main()
