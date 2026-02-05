import xml.etree.ElementTree as ET
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Load the XML file
tree = ET.parse('workload_scenario_2.xml')
root = tree.getroot()

# 1. Parse Host I/O Flow Results
host_data = []
for flow in root.findall(".//Host/Host.IO_Flow"):
    name = flow.find('Name').text
    iops = float(flow.find('IOPS').text)
    bandwidth = float(flow.find('Bandwidth').text) / (1024 * 1024) # Convert to MB/s
    avg_latency = float(flow.find('Device_Response_Time').text)
    min_latency = float(flow.find('Min_Device_Response_Time').text)
    max_latency = float(flow.find('Max_Device_Response_Time').text)
    
    host_data.append({
        'Flow': name.split('.')[-1], # Extract No_0, No_1
        'IOPS': iops,
        'Bandwidth (MB/s)': bandwidth,
        'Avg Latency (ns)': avg_latency,
        'Min Latency (ns)': min_latency,
        'Max Latency (ns)': max_latency
    })

df_host = pd.DataFrame(host_data)

# 2. Parse Flash Chip Utilization Results (Heatmap Data)
# ID format: @Channel@Chip
chip_data = []
for chip in root.findall(".//SSDDevice/SSDDevice.FlashChips"):
    chip_id = chip.get('ID')
    parts = chip_id.split('@') # ['', 'Channel', 'Chip']
    channel = int(parts[1])
    chip_no = int(parts[2])
    
    # Using 'Fraction_of_Time_in_Execution' as utilization metric
    utilization = float(chip.get('Fraction_of_Time_in_Execution')) * 100 
    
    chip_data.append({
        'Channel': channel,
        'Chip': chip_no,
        'Utilization (%)': utilization
    })

df_chips = pd.DataFrame(chip_data)
# Pivot for heatmap: Rows=Chips, Cols=Channels
heatmap_data = df_chips.pivot(index='Chip', columns='Channel', values='Utilization (%)')

# --- Plotting ---
fig = plt.figure(figsize=(18, 10))
plt.subplots_adjust(hspace=0.4)

# Plot 1: IOPS Comparison
ax1 = plt.subplot(2, 3, 1)
sns.barplot(x='Flow', y='IOPS', data=df_host, ax=ax1, palette='viridis')
ax1.set_title('IOPS per Host Flow')
ax1.set_xlabel('')
for i in ax1.containers:
    ax1.bar_label(i, fmt='%.0f')

# Plot 2: Bandwidth Comparison
ax2 = plt.subplot(2, 3, 2)
sns.barplot(x='Flow', y='Bandwidth (MB/s)', data=df_host, ax=ax2, palette='magma')
ax2.set_title('Bandwidth (MB/s) per Host Flow')
ax2.set_xlabel('')
for i in ax2.containers:
    ax2.bar_label(i, fmt='%.1f')

# Plot 3: Latency Analysis (Grouped Bar)
ax3 = plt.subplot(2, 3, 3)
df_latency = df_host.melt(id_vars='Flow', value_vars=['Min Latency (ns)', 'Avg Latency (ns)', 'Max Latency (ns)'], 
                          var_name='Metric', value_name='Time (ns)')
sns.barplot(x='Metric', y='Time (ns)', hue='Flow', data=df_latency, ax=ax3, palette='coolwarm')
ax3.set_title('Device Response Time (Latency)')
ax3.set_yscale('log') # Log scale due to difference between Min and Max
ax3.set_xlabel('')

# Plot 4: Flash Chip Utilization Heatmap
ax4 = plt.subplot(2, 1, 2)
sns.heatmap(heatmap_data, annot=True, fmt=".1f", cmap="YlOrRd", ax=ax4, cbar_kws={'label': 'Active Time (%)'})
ax4.set_title('Flash Chip Utilization Heatmap (Channel vs Chip)')
ax4.set_xlabel('Channel ID')
ax4.set_ylabel('Chip (Way) ID')

# Save and Display
plt.suptitle('MQSim Result Analysis: Scenario 1', fontsize=16)
plt.savefig('mqsim_analysis_2.png')