#!/usr/bin/env python3
"""
LLM Inference Simulation Result Analyzer

Parses MQSim output XML files and extracts key metrics for read-disturb analysis.
"""

import xml.etree.ElementTree as ET
import json
import sys
import os
from pathlib import Path

class LLM_Result_Analyzer:
    def __init__(self, result_xml_path):
        self.result_path = Path(result_xml_path)
        if not self.result_path.exists():
            raise FileNotFoundError(f"Result file not found: {result_xml_path}")

        self.tree = ET.parse(self.result_path)
        self.root = self.tree.getroot()
        self.metrics = {}

    def parse_host_metrics(self):
        """Extract host-level I/O metrics"""
        host = self.root.find('.//Host.IO_Flow')
        if host is None:
            return {}

        metrics = {
            'name': host.find('Name').text if host.find('Name') is not None else 'Unknown',
            'total_requests': int(host.find('Request_Count').text),
            'read_requests': int(host.find('Read_Request_Count').text),
            'write_requests': int(host.find('Write_Request_Count').text),
            'iops': float(host.find('IOPS').text),
            'bandwidth_mbps': float(host.find('Bandwidth').text),
            'avg_response_time_us': float(host.find('Device_Response_Time').text),
        }

        return metrics

    def parse_ftl_metrics(self):
        """Extract FTL-level metrics including ECC statistics"""
        ftl = self.root.find('.//SSDDevice.FTL')
        if ftl is None:
            return {}

        attrs = ftl.attrib
        metrics = {
            # Flash command statistics
            'total_flash_reads': int(attrs.get('Issued_Flash_Read_CMD', 0)),
            'multiplane_reads': int(attrs.get('Issued_Flash_Multiplane_Read_CMD', 0)),
            'total_flash_writes': int(attrs.get('Issued_Flash_Program_CMD', 0)),
            'total_flash_erases': int(attrs.get('Issued_Flash_Erase_CMD', 0)),

            # GC/WL statistics
            'total_gc_executions': int(attrs.get('Total_GC_Executions', 0)),
            'total_wl_executions': int(attrs.get('Total_WL_Executions', 0)),
            'total_read_reclaim': int(attrs.get('Total_Read_Reclaim_Migrations', 0)),

            # ECC statistics (KEY METRICS)
            'total_ecc_retries': int(attrs.get('Total_ECC_Retries', 0)),
            'total_ecc_failures': int(attrs.get('Total_ECC_Failures', 0)),
            'total_ecc_uncorrectable': int(attrs.get('Total_ECC_Uncorrectable', 0)),

            # Cache statistics
            'cmt_hits_read': int(attrs.get('CMT_Hits_For_Read', 0)),
            'cmt_misses_read': int(attrs.get('CMT_Misses_For_Read', 0)),
        }

        # Calculate derived metrics
        total_reads = metrics['total_flash_reads'] + metrics['multiplane_reads']
        if total_reads > 0:
            metrics['ecc_retry_rate'] = metrics['total_ecc_retries'] / total_reads
            metrics['ecc_failure_rate'] = metrics['total_ecc_failures'] / total_reads
            metrics['uncorrectable_rate'] = metrics['total_ecc_uncorrectable'] / total_reads
        else:
            metrics['ecc_retry_rate'] = 0.0
            metrics['ecc_failure_rate'] = 0.0
            metrics['uncorrectable_rate'] = 0.0

        return metrics

    def analyze_all(self):
        """Parse all metrics and return comprehensive results"""
        self.metrics['host'] = self.parse_host_metrics()
        self.metrics['ftl'] = self.parse_ftl_metrics()

        # Add metadata
        self.metrics['source_file'] = str(self.result_path)
        self.metrics['experiment_name'] = self.result_path.stem

        return self.metrics

    def print_summary(self):
        """Print human-readable summary"""
        metrics = self.analyze_all()

        print("=" * 70)
        print(f"LLM Inference Simulation Results: {metrics['experiment_name']}")
        print("=" * 70)

        print("\n📊 Host I/O Statistics:")
        host = metrics['host']
        print(f"  Total Requests:      {host['total_requests']:,}")
        print(f"  Read Requests:       {host['read_requests']:,}")
        print(f"  IOPS:                {host['iops']:,.2f}")
        print(f"  Bandwidth:           {host['bandwidth_mbps']:.2f} MB/s")
        print(f"  Avg Response Time:   {host['avg_response_time_us']:.2f} μs")

        print("\n🔧 Flash Operations:")
        ftl = metrics['ftl']
        print(f"  Flash Reads:         {ftl['total_flash_reads']:,} single + {ftl['multiplane_reads']:,} multiplane")
        print(f"  Flash Writes:        {ftl['total_flash_writes']:,}")
        print(f"  Flash Erases:        {ftl['total_flash_erases']:,}")
        print(f"  GC Executions:       {ftl['total_gc_executions']:,}")
        print(f"  Read-Reclaim Ops:    {ftl['total_read_reclaim']:,}")

        print("\n⚠️  ECC Statistics (KEY METRICS):")
        print(f"  ECC Retries:         {ftl['total_ecc_retries']:,}")
        print(f"  ECC Failures:        {ftl['total_ecc_failures']:,}")
        print(f"  Uncorrectable:       {ftl['total_ecc_uncorrectable']:,}")
        print(f"  Retry Rate:          {ftl['ecc_retry_rate']:.4f} ({ftl['ecc_retry_rate']*100:.2f}%)")
        print(f"  Failure Rate:        {ftl['ecc_failure_rate']:.4f} ({ftl['ecc_failure_rate']*100:.2f}%)")
        print(f"  Uncorrectable Rate:  {ftl['uncorrectable_rate']:.4f} ({ftl['uncorrectable_rate']*100:.2f}%)")

        print("\n" + "=" * 70)

    def export_json(self, output_path):
        """Export metrics as JSON for further analysis"""
        metrics = self.analyze_all()
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"✅ Exported metrics to {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_llm_results.py <result_xml_file> [--json output.json]")
        print("\nExample:")
        print("  python3 analyze_llm_results.py configs/workload/llm_test_config_scenario_1.xml")
        print("  python3 analyze_llm_results.py configs/workload/llm_test_config_scenario_1.xml --json results.json")
        sys.exit(1)

    result_file = sys.argv[1]

    try:
        analyzer = LLM_Result_Analyzer(result_file)
        analyzer.print_summary()

        # Check if JSON export requested
        if '--json' in sys.argv:
            json_idx = sys.argv.index('--json')
            if json_idx + 1 < len(sys.argv):
                output_path = sys.argv[json_idx + 1]
                analyzer.export_json(output_path)

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
