import math
import os
import sys
import subprocess
import xml.etree.ElementTree as ET
import copy

class LLMTraceGenerator:
    def __init__(self, model_config, ssd_config, output_file):
        self.model_config = model_config
        self.ssd_config = ssd_config
        self.output_file = output_file

        self.sector_size = 512
        self.bytes_per_param = 2  # FP16

        # MQSim ASCII Format Constants
        self.OP_WRITE = 0
        self.OP_READ = 1
        self.DEVICE_NUM = 0
        self.ROBUST_SENSITIVE = 0

    def calculate_layer_params(self):
        hidden = self.model_config['hidden_size']
        interim = self.model_config['intermediate_size']
        attn_params = 4 * (hidden * hidden)
        ffn_params = 3 * (hidden * interim)
        return attn_params + ffn_params

    def generate(self, generation_length=1, prefill_model=True):
        """
        :param generation_length: number of token generation iterations
        :param prefill_model: if True, include model write trace at start
        """
        params_per_layer = self.calculate_layer_params()
        layer_size_bytes = params_per_layer * self.bytes_per_param

        total_sectors_per_layer = math.ceil(layer_size_bytes / self.sector_size)
        max_req_sectors = self.ssd_config['max_request_size_kb'] * 1024 // self.sector_size

        compute_time_per_layer_ns = self.model_config.get('layer_compute_time_ns', 10000000)

        current_time_ns = 0

        with open(self.output_file, 'w') as f:

            # Phase 1: Model Pre-fill (Write Phase)
            if prefill_model:
                print("[Phase 1] Generating Model Write (Pre-fill) trace...")
                current_lba = 0

                for layer in range(self.model_config['num_layers']):
                    sectors_remaining = total_sectors_per_layer
                    request_interval_ns = 150

                    while sectors_remaining > 0:
                        req_size = min(sectors_remaining, max_req_sectors)
                        trace_line = f"{current_time_ns} {self.DEVICE_NUM} {current_lba} {req_size} {self.OP_WRITE}\n"
                        f.write(trace_line)

                        current_lba += req_size
                        sectors_remaining -= req_size
                        current_time_ns += request_interval_ns

                print(f" -> Model Installed. End LBA: {current_lba}")
                current_time_ns += 10_000_000_000  # 10 seconds gap

            # Phase 2: Inference (Read Phase)
            print(f"[Phase 2] Generating Inference Read trace ({generation_length} tokens)...")

            for token_idx in range(generation_length):
                current_lba = 0

                for layer in range(self.model_config['num_layers']):
                    sectors_remaining = total_sectors_per_layer
                    request_interval_ns = 100

                    while sectors_remaining > 0:
                        req_size = min(sectors_remaining, max_req_sectors)
                        trace_line = f"{current_time_ns} {self.DEVICE_NUM} {current_lba} {req_size} {self.OP_READ}\n"
                        f.write(trace_line)

                        current_lba += req_size
                        sectors_remaining -= req_size
                        current_time_ns += request_interval_ns

                    current_time_ns += compute_time_per_layer_ns

        print(f"[Done] Trace saved to {self.output_file}. Total duration: {current_time_ns/1e9:.4f} sec")


# ============================================================
# Evaluation Pipeline
# ============================================================

# Project root (two levels up from tools/examples/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

llama_7b_config = {
    'hidden_size': 4096,
    'intermediate_size': 11008,
    'num_layers': 32,
    'layer_compute_time_ns': 20 * 1000 * 1000
}

ssd_config = {
    'max_request_size_kb': 256,
}

SCENARIOS = {
    'high_threshold': 1000000,
    'low_threshold': 7680,
}

MAX_TOKENS = 10


def generate_traces():
    """Generate 10 trace files: traces/llama_7b_gen_{1..10}_tok.trace"""
    print("=" * 60)
    print("Step 1: Generating trace files")
    print("=" * 60)
    traces_dir = os.path.join(PROJECT_ROOT, 'traces')
    os.makedirs(traces_dir, exist_ok=True)

    for n in range(1, MAX_TOKENS + 1):
        trace_path = os.path.join(traces_dir, f'llama_7b_gen_{n}_tok.trace')
        gen = LLMTraceGenerator(
            model_config=llama_7b_config,
            ssd_config=ssd_config,
            output_file=trace_path,
        )
        gen.generate(generation_length=n, prefill_model=True)


def generate_ssd_configs():
    """Generate 2 SSD config XMLs with different Read_Reclaim_Threshold values."""
    print("\n" + "=" * 60)
    print("Step 2: Generating SSD config XMLs")
    print("=" * 60)
    template_path = os.path.join(PROJECT_ROOT, 'devconf', 'ssdconfig_ifp.xml')
    tree = ET.parse(template_path)

    for scenario, threshold in SCENARIOS.items():
        out_path = os.path.join(PROJECT_ROOT, 'devconf', f'eval_{scenario}.xml')
        new_tree = copy.deepcopy(tree)
        root = new_tree.getroot()

        # Find Read_Reclaim_Threshold and update
        for elem in root.iter('Read_Reclaim_Threshold'):
            elem.text = str(threshold)

        # Use ideal mapping table to avoid CMT miss issues with preconditioning
        for elem in root.iter('Ideal_Mapping_Table'):
            elem.text = 'true'

        new_tree.write(out_path, encoding='us-ascii', xml_declaration=True)
        print(f"  Created {out_path} (threshold={threshold})")


def generate_workload_configs():
    """Generate 20 workload config XMLs (10 per scenario)."""
    print("\n" + "=" * 60)
    print("Step 3: Generating workload config XMLs")
    print("=" * 60)
    wkdconf_dir = os.path.join(PROJECT_ROOT, 'wkdconf')
    os.makedirs(wkdconf_dir, exist_ok=True)

    for scenario in SCENARIOS:
        for n in range(1, MAX_TOKENS + 1):
            out_path = os.path.join(wkdconf_dir, f'eval_{scenario}_{n}tok.xml')
            trace_rel = f'traces/llama_7b_gen_{n}_tok.trace'

            content = f"""<?xml version="1.0" encoding="us-ascii"?>
<MQSim_IO_Scenarios>
  <IO_Scenario>
    <IO_Flow_Parameter_Set_Trace_Based>
      <Priority_Class>HIGH</Priority_Class>
      <Device_Level_Data_Caching_Mode>WRITE_CACHE</Device_Level_Data_Caching_Mode>
      <Channel_IDs>0,1,2,3,4,5,6,7</Channel_IDs>
      <Chip_IDs>0,1</Chip_IDs>
      <Die_IDs>0</Die_IDs>
      <Plane_IDs>0,1,2,3</Plane_IDs>
      <Initial_Occupancy_Percentage>0</Initial_Occupancy_Percentage>
      <File_Path>{trace_rel}</File_Path>
      <Percentage_To_Be_Executed>100</Percentage_To_Be_Executed>
      <Relay_Count>1</Relay_Count>
      <Time_Unit>NANOSECOND</Time_Unit>
    </IO_Flow_Parameter_Set_Trace_Based>
  </IO_Scenario>
</MQSim_IO_Scenarios>
"""
            with open(out_path, 'w') as f:
                f.write(content)
            print(f"  Created {out_path}")


def run_simulations():
    """Run 20 simulations (10 per scenario)."""
    print("\n" + "=" * 60)
    print("Step 4: Running simulations")
    print("=" * 60)
    results_dir = os.path.join(PROJECT_ROOT, 'results')
    os.makedirs(results_dir, exist_ok=True)

    mqsim_bin = os.path.join(PROJECT_ROOT, 'mqsim')
    total = 2 * MAX_TOKENS
    count = 0

    for scenario in SCENARIOS:
        for n in range(1, MAX_TOKENS + 1):
            count += 1
            ssd_cfg = os.path.join(PROJECT_ROOT, 'devconf', f'eval_{scenario}.xml')
            wkd_cfg = os.path.join(PROJECT_ROOT, 'wkdconf', f'eval_{scenario}_{n}tok.xml')
            out_xml = os.path.join(results_dir, f'eval_{scenario}_{n}tok.xml')

            print(f"  [{count}/{total}] Running: {scenario} {n}tok ...", end=' ', flush=True)
            result = subprocess.run(
                [mqsim_bin, '-i', ssd_cfg, '-w', wkd_cfg, '-o', out_xml],
                cwd=PROJECT_ROOT,
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                print(f"FAILED (rc={result.returncode})")
                print(f"  stderr: {result.stderr[:500]}")
            else:
                print("OK")


def parse_results_and_plot():
    """Parse result XMLs and generate comparison plot."""
    print("\n" + "=" * 60)
    print("Step 5: Parsing results and generating plot")
    print("=" * 60)

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("ERROR: matplotlib not installed. Install with: pip install matplotlib")
        return

    results_dir = os.path.join(PROJECT_ROOT, 'results')

    # Calculate bytes_per_token (constant for all tokens)
    params_per_layer = 4 * (4096 * 4096) + 3 * (4096 * 11008)
    layer_size_bytes = params_per_layer * 2  # FP16
    bytes_per_token = layer_size_bytes * 32  # 32 layers
    print(f"  Bytes per token: {bytes_per_token / 1e9:.4f} GB")

    scenario_data = {}

    for scenario in SCENARIOS:
        sim_times = []  # sim_time for n=1..10
        for n in range(1, MAX_TOKENS + 1):
            out_xml = os.path.join(results_dir, f'eval_{scenario}_{n}tok.xml')
            if not os.path.exists(out_xml):
                print(f"  WARNING: {out_xml} not found, skipping")
                sim_times.append(None)
                continue

            tree = ET.parse(out_xml)
            root = tree.getroot()

            # Find Host.IO_Flow element
            io_flow = root.find('.//Host.IO_Flow')
            if io_flow is None:
                # Try alternative: iterate to find it
                for elem in root.iter():
                    if 'IO_Flow' in elem.tag:
                        io_flow = elem
                        break

            bytes_transferred = float(io_flow.find('Bytes_Transferred_Read').text)
            bandwidth = float(io_flow.find('Bandwidth_Read').text)

            if bandwidth > 0:
                sim_time = bytes_transferred / bandwidth  # seconds
            else:
                sim_time = 0.0

            sim_times.append(sim_time)
            print(f"  {scenario} {n}tok: bytes={bytes_transferred:.0f}, bw={bandwidth:.0f}, sim_time={sim_time:.6f}s")

        # Compute per-token bandwidth
        token_bws = []  # GB/s for each token
        cumulative_times = []  # x-axis: cumulative sim time at end of each token
        for n in range(MAX_TOKENS):
            if sim_times[n] is None:
                token_bws.append(None)
                cumulative_times.append(None)
                continue

            cumulative_times.append(sim_times[n])

            if n == 0:
                delta_t = sim_times[0]
            else:
                if sim_times[n - 1] is None:
                    token_bws.append(None)
                    continue
                delta_t = sim_times[n] - sim_times[n - 1]

            if delta_t > 0:
                bw = bytes_per_token / delta_t  # bytes/sec
                token_bws.append(bw / 1e9)  # GB/s
            else:
                token_bws.append(0.0)

        scenario_data[scenario] = {
            'sim_times': sim_times,
            'cumulative_times': cumulative_times,
            'token_bws': token_bws,
        }

    # Print summary table
    print("\n  Per-token bandwidth (GB/s):")
    print(f"  {'Token':<8}", end='')
    for scenario in SCENARIOS:
        print(f"{scenario:<20}", end='')
    print()
    for i in range(MAX_TOKENS):
        print(f"  {i+1:<8}", end='')
        for scenario in SCENARIOS:
            bw = scenario_data[scenario]['token_bws'][i]
            if bw is not None:
                print(f"{bw:<20.4f}", end='')
            else:
                print(f"{'N/A':<20}", end='')
        print()

    # Plot
    fig, ax = plt.subplots(figsize=(10, 6))

    labels = {
        'high_threshold': 'Scenario A: No Reclaim (threshold=1,000,000)',
        'low_threshold': 'Scenario B: With Reclaim (threshold=7,680)',
    }
    colors = {
        'high_threshold': '#2196F3',
        'low_threshold': '#F44336',
    }
    markers = {
        'high_threshold': 'o',
        'low_threshold': 's',
    }

    for scenario in SCENARIOS:
        data = scenario_data[scenario]
        x_vals = []
        y_vals = []
        for i in range(MAX_TOKENS):
            ct = data['cumulative_times'][i]
            bw = data['token_bws'][i]
            if ct is not None and bw is not None:
                x_vals.append(ct)
                y_vals.append(bw)

        ax.plot(x_vals, y_vals,
                label=labels[scenario],
                color=colors[scenario],
                marker=markers[scenario],
                linewidth=2, markersize=8)

    ax.set_xlabel('Cumulative Simulation Time (seconds)', fontsize=12)
    ax.set_ylabel('Per-Token Read Bandwidth (GB/s)', fontsize=12)
    ax.set_title('Read Reclaim Impact on LLM Inference Bandwidth\n(Llama-7B, 10 Token Generation)', fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Add token number annotations
    for scenario in SCENARIOS:
        data = scenario_data[scenario]
        for i in range(MAX_TOKENS):
            ct = data['cumulative_times'][i]
            bw = data['token_bws'][i]
            if ct is not None and bw is not None:
                ax.annotate(f'T{i+1}', (ct, bw),
                           textcoords="offset points", xytext=(0, 10),
                           ha='center', fontsize=8, alpha=0.7)

    plt.tight_layout()
    plot_path = os.path.join(results_dir, 'eval_read_reclaim_bandwidth.png')
    plt.savefig(plot_path, dpi=150)
    print(f"\n  Plot saved to {plot_path}")


def main():
    """Run the full evaluation pipeline."""
    if len(sys.argv) > 1:
        # Legacy mode: generate single trace file
        gen_len = int(sys.argv[1])
        generator = LLMTraceGenerator(
            model_config=llama_7b_config,
            ssd_config=ssd_config,
            output_file=f"llama_7b_gen_{gen_len}_tok.trace"
        )
        generator.generate(generation_length=gen_len, prefill_model=False)
        return

    # Full evaluation pipeline
    print("IFP Read Reclaim Evaluation Pipeline")
    print("=" * 60)
    print(f"Scenarios: {list(SCENARIOS.keys())}")
    print(f"Tokens: 1..{MAX_TOKENS}")
    print(f"Total simulations: {2 * MAX_TOKENS}")
    print()

    generate_traces()
    generate_ssd_configs()
    generate_workload_configs()
    run_simulations()
    parse_results_and_plot()

    print("\n" + "=" * 60)
    print("Evaluation complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
