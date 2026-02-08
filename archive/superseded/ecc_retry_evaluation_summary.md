# ECC Read-Retry Impact on Read Bandwidth: Evaluation Summary

## Objective

Evaluate how ECC soft-decode retries affect SSD read bandwidth. Each retry adds `decode_latency` (5 us) to read transaction time.

## Code Changes (commit 95a2a59)

### 1. Wire ECC params from XML config (`src/ssd/FTL.cpp`)

Replaced hardcoded ECC parameters with XML-configurable values from `Flash_Parameter_Set`:

| Parameter | Before (hardcoded) | After (from XML) |
|-----------|-------------------|-------------------|
| `correction_capability` | 40 | `Flash_Parameter_Set::ECC_Correction_Capability` |
| `decode_latency` | 5000 ns | `Flash_Parameter_Set::IFP_ECC_Decode_Latency` |
| `max_retries` | 0 (disabled) | `Flash_Parameter_Set::IFP_ECC_Max_Retries` |

### 2. Make ECC latency actually delay simulation events (`NVM_PHY_ONFI_NVDDR2.cpp`)

**Bug found:** ECC decode latency was only added to `STAT_execution_time` (a statistics counter) but did NOT delay the `READ_DATA_TRANSFERRED` simulation event. Data transfer started immediately after flash read completion, ignoring ECC decode time. Read bandwidth was identical regardless of retry count.

**Fix:** Added `ECC_decode_latency` field to `NVM_Transaction_Flash`. After ECC check, the latency is stored per-transaction and added to the event scheduling time in `transfer_read_data_from_chip()`:

```
Before: event_time = Simulator->Time() + data_transfer_time
After:  event_time = Simulator->Time() + ecc_latency + data_transfer_time
```

### 3. Files modified

| File | Change |
|------|--------|
| `src/ssd/FTL.cpp` | Wire 3 ECC params from `Flash_Parameter_Set` instead of hardcoding |
| `src/ssd/NVM_Transaction_Flash.h` | Add `ECC_decode_latency` field |
| `src/ssd/NVM_Transaction_Flash.cpp` | Initialize `ECC_decode_latency = 0` in both constructors |
| `src/ssd/NVM_PHY_ONFI_NVDDR2.cpp` | Store ECC latency per-transaction; add it to data transfer event timing |

## Experiment Design

### Controlling retry count via correction_capability (CC)

With `epsilon = 1.48e-3` and `page_size = 131072 bits`, fresh flash expects **~194 bit errors** per page. The soft-decode model increases effective capability by 50% per retry: `effective = CC * (1 + 0.5 * r)`.

| Config | CC | Effective at first pass | First passing retry | Forced retries |
|--------|-----|------------------------|---------------------|----------------|
| `eval_retry_0` | 200 | 200 >= 194 | r=0 | **0** |
| `eval_retry_1` | 135 | 135 < 194, 202.5 >= 194 | r=1 | **1** |
| `eval_retry_2` | 100 | 100 < 194, 200 >= 194 | r=2 | **2** |
| `eval_retry_3` | 80 | 80 < 194, 200 >= 194 | r=3 | **3** |
| `eval_retry_4` | 66 | 66 < 194, 198 >= 194 | r=4 | **4** |
| `eval_retry_5` | 57 | 57 < 194, 199.5 >= 194 | r=5 | **5** |

All configs: `IFP_ECC_Max_Retries = 10`, `IFP_ECC_Decode_Latency = 5000 ns`, `Read_Reclaim_Threshold = 10000000` (disabled).

### Expected latency impact per read

| Retries | ECC latency | Est. total read latency | Overhead vs baseline |
|---------|-------------|-------------------------|----------------------|
| 0 | 5 us | ~42 us | baseline |
| 1 | 10 us | ~47 us | +12% |
| 2 | 15 us | ~52 us | +24% |
| 3 | 20 us | ~57 us | +36% |
| 4 | 25 us | ~62 us | +48% |
| 5 | 30 us | ~67 us | +60% |

Actual bandwidth impact depends on channel-level parallelism partially masking latency increases.

### Config files

**Device configs** (`devconf/eval_retry_{0..5}.xml`):
- Based on `ssdconfig.xml` (8ch x 2chip, TLC, 686 blocks x 1536 pages)
- `Enabled_Preconditioning = false` (reads use on-the-fly page allocation)
- `Ideal_Mapping_Table = true` (eliminates mapping-table misses)
- ECC parameters vary per config (CC values above)

**Workload config** (`wkdconf/eval_ecc_retry_read.xml`):
- 100% read, synthetic, QUEUE_DEPTH generator
- Caching disabled (`TURNED_OFF`)
- 32-sector (16KB) requests = one flash page per request
- QD=128, RANDOM_UNIFORM, 10s stop time

### Preconditioning note

Preconditioning was disabled because the algorithm has a fundamental issue with this geometry (1536 pages/block creates too many distribution levels for the integer truncation in `Allocate_address_for_preconditioning`). Without preconditioning, reads to unmapped LPAs are handled by `online_create_entry_for_reads()` which allocates physical pages on-the-fly. The ECC engine still processes every read with the same fresh-flash RBER.

## Running the experiments

```bash
make   # rebuild

for N in 0 1 2 3 4 5; do
    ./mqsim -i devconf/eval_retry_${N}.xml \
            -w wkdconf/eval_ecc_retry_read.xml \
            -o results/ecc_retry_${N}
done
```

## Metrics to extract from output XML

From each output XML:

| Metric | XML Path | Purpose |
|--------|----------|---------|
| `Bandwidth_Read` | Host > IO_Flow | **Primary metric** (bytes/sec) |
| `IOPS_Read` | Host > IO_Flow | Throughput |
| `Device_Response_Time` | Host > IO_Flow | Average latency (ns) |
| `Total_ECC_Retries` | SSDDevice.FTL | Validate retry count |
| `Total_ECC_Uncorrectable` | SSDDevice.FTL | Must be 0 |

### Validation checks
- `Total_ECC_Retries ~ N * Read_Count` for retry-N config
- `Total_ECC_Uncorrectable = 0` for all configs
- `Bandwidth_Read` decreases monotonically from retry_0 to retry_5
