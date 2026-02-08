# Evaluation Plan: Read-Retry Impact on Read Bandwidth

## Context

The ECC engine in MQSim-JW models soft-decode retries that each add `decode_latency` (5µs) to read transaction time. The hypothesis is straightforward: **more retries → higher per-read latency → lower read bandwidth**. However, there are two issues preventing evaluation today:

1. **max_retries = 0 (hardcoded)** in `FTL.cpp:46` — retries are disabled, so every page that exceeds correction_capability is marked uncorrectable with no retry overhead.
2. **correction_capability = 40 (hardcoded)** in `FTL.cpp:44` — but with `epsilon = 1.48e-3` and `page_size = 131072 bits`, fresh flash already expects ~194 bit errors, far exceeding 40. Every read is uncorrectable.
3. `FTL.cpp` ignores the XML-configurable params (`ECC_Correction_Capability`, `IFP_ECC_Max_Retries`, `IFP_ECC_Decode_Latency`) that already exist in `Flash_Parameter_Set`.

The fix is minimal: wire `FTL.cpp` to read these three params from `Flash_Parameter_Set` instead of hardcoding them, then use XML configs to sweep experiments.

## Code Change (1 file, ~5 lines)

**File: `src/ssd/FTL.cpp`**

1. Add include at top:
   ```cpp
   #include "../exec/Flash_Parameter_Set.h"
   ```

2. Replace lines 43-46 of the ECC_Engine constructor call:
   ```cpp
   // Before (hardcoded):
   page_size_bits,  // page size in bits
   40,              // correction_capability
   5000,            // decode_latency
   0                // max_retries

   // After (from XML config):
   page_size_bits,
   Flash_Parameter_Set::ECC_Correction_Capability,
   Flash_Parameter_Set::IFP_ECC_Decode_Latency,
   Flash_Parameter_Set::IFP_ECC_Max_Retries
   ```

The 9 RBER model coefficients (epsilon through q) remain hardcoded — they model a specific flash technology and are not the experiment variable.

## Experiment Design

### Controlling retry count via correction_capability

With `epsilon = 1.48e-3` and `page_size = 131072 bits`, fresh flash expects **~194 bit errors** per page. The soft-decode retry model increases effective capability by 50% per retry: `effective = CC × (1 + 0.5 × r)`. By varying CC, we force exactly r retries for fresh-flash reads:

| Config | CC | Retry 0 check | First passing retry | Forced retries |
|--------|-----|----------------|---------------------|----------------|
| retry_0 | 200 | 194 ≤ 200 ✓ | r=0 | **0** |
| retry_1 | 135 | 194 > 135 ✗ | 135×1.5 = 202.5 ≥ 194 | **1** |
| retry_2 | 100 | 194 > 100 ✗ | 100×2.0 = 200 ≥ 194 | **2** |
| retry_3 | 80  | 194 > 80 ✗  | 80×2.5 = 200 ≥ 194  | **3** |
| retry_4 | 66  | 194 > 66 ✗  | 66×3.0 = 198 ≥ 194  | **4** |
| retry_5 | 57  | 194 > 57 ✗  | 57×3.5 = 199.5 ≥ 194 | **5** |

All configs set `IFP_ECC_Max_Retries = 10` (enough headroom) and `IFP_ECC_Decode_Latency = 5000` (5µs per attempt).

### Expected latency impact

| Retries | ECC latency | Est. total read latency | Overhead vs baseline |
|---------|-------------|-------------------------|----------------------|
| 0 | 5 µs  | ~45 µs (flash) + 5 µs = ~50 µs  | — |
| 1 | 10 µs | ~55 µs | +10% |
| 2 | 15 µs | ~60 µs | +20% |
| 3 | 20 µs | ~65 µs | +30% |
| 4 | 25 µs | ~70 µs | +40% |
| 5 | 30 µs | ~75 µs | +50% |

Actual bandwidth impact may differ due to channel-level parallelism partially masking latency increases.

### Device configs (6 files)

Create `devconf/eval_retry_{0..5}.xml` — each is a copy of `devconf/ssdconfig.xml` with:
- `<Enabled_Preconditioning>true</Enabled_Preconditioning>` (so data exists to read)
- `<Ideal_Mapping_Table>true</Ideal_Mapping_Table>` (eliminate mapping-table misses as a confound)
- ECC parameters added inside `<Flash_Parameter_Set>`:
  ```xml
  <ECC_Correction_Capability>{CC value from table}</ECC_Correction_Capability>
  <IFP_ECC_Decode_Latency>5000</IFP_ECC_Decode_Latency>
  <IFP_ECC_Max_Retries>10</IFP_ECC_Max_Retries>
  <Read_Reclaim_Threshold>10000000</Read_Reclaim_Threshold>
  ```
  Read_Reclaim_Threshold set very high to prevent reclaim from interfering with the experiment.

### Workload config (1 file)

Create `wkdconf/eval_ecc_retry_read.xml` — 100% read, synthetic, saturating:

```xml
<MQSim_IO_Scenarios>
  <IO_Scenario>
    <IO_Flow_Parameter_Set_Synthetic>
      <Priority_Class>HIGH</Priority_Class>
      <Device_Level_Data_Caching_Mode>TURNED_OFF</Device_Level_Data_Caching_Mode>
      <Channel_IDs>0,1,2,3,4,5,6,7</Channel_IDs>
      <Chip_IDs>0,1</Chip_IDs>
      <Die_IDs>0</Die_IDs>
      <Plane_IDs>0,1,2,3</Plane_IDs>
      <Initial_Occupancy_Percentage>80</Initial_Occupancy_Percentage>
      <Working_Set_Percentage>80</Working_Set_Percentage>
      <Synthetic_Generator_Type>QUEUE_DEPTH</Synthetic_Generator_Type>
      <Read_Percentage>100</Read_Percentage>
      <Address_Distribution>RANDOM_UNIFORM</Address_Distribution>
      <Percentage_of_Hot_Region>0</Percentage_of_Hot_Region>
      <Generated_Aligned_Addresses>true</Generated_Aligned_Addresses>
      <Address_Alignment_Unit>32</Address_Alignment_Unit>
      <Request_Size_Distribution>FIXED</Request_Size_Distribution>
      <Average_Request_Size>32</Average_Request_Size>
      <Variance_Request_Size>0</Variance_Request_Size>
      <Seed>12345</Seed>
      <Average_No_of_Reqs_in_Queue>128</Average_No_of_Reqs_in_Queue>
      <Stop_Time>10000000000</Stop_Time>
      <Total_Requests_To_Generate>0</Total_Requests_To_Generate>
    </IO_Flow_Parameter_Set_Synthetic>
  </IO_Scenario>
</MQSim_IO_Scenarios>
```

Key choices:
- **100% read** — isolates ECC retry overhead from write behavior
- **TURNED_OFF caching** — prevents cache hits from masking read latency differences
- **32-sector (16KB) request size** — one flash page per request, so each request hits ECC exactly once
- **QD=128** — saturates all 16 chips (8 channels × 2 chips)
- **RANDOM_UNIFORM** — spreads reads evenly, avoids hotspot effects
- **10s stop time** — long enough for steady state

## Execution

```bash
make   # rebuild after code change

for N in 0 1 2 3 4 5; do
    ./mqsim -i devconf/eval_retry_${N}.xml \
            -w wkdconf/eval_ecc_retry_read.xml \
            -o results/ecc_retry_${N}
done
```

## Metrics to Extract from Output XML

From each `results/ecc_retry_N_scenario_1.xml`:

| Metric | XML Path | Purpose |
|--------|----------|---------|
| `Bandwidth_Read` | Host → IO_Flow | **Primary metric** (bytes/sec) |
| `IOPS_Read` | Host → IO_Flow | Throughput |
| `Device_Response_Time` | Host → IO_Flow | Average latency (ns) |
| `Total_ECC_Retries` | SSDDevice.FTL (attribute) | Validate retry count |
| `Total_ECC_Uncorrectable` | SSDDevice.FTL (attribute) | Must be 0 |
| `Read_Request_Count` | Host → IO_Flow | Total completed reads |

### Validation checks
- `Total_ECC_Retries ≈ N × Read_Request_Count` for retry-N config
- `Total_ECC_Uncorrectable = 0` for all configs (if non-zero, max_retries too low)
- `Bandwidth_Read` decreases monotonically from retry_0 to retry_5

## Summary of files to create/modify

| Action | File |
|--------|------|
| **Modify** | `src/ssd/FTL.cpp` (add include + wire 3 params from Flash_Parameter_Set) |
| **Create** | `devconf/eval_retry_0.xml` through `devconf/eval_retry_5.xml` |
| **Create** | `wkdconf/eval_ecc_retry_read.xml` |
