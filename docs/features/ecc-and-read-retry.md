# ECC Engine and Read-Retry Architecture

## ECC Read Path

When a flash read completes on a chip, the ECC flow is triggered in `NVM_PHY_ONFI_NVDDR2.cpp` `handle_ready_signal_from_chip()` (line ~561):

```
Flash read completes on chip
  → ECC_Engine::Attempt_correction(block.Erase_count, retention_time_hours, avg_reads_per_page)
  → ECC_Engine::Get_ECC_latency(retry_count)
  → tr->STAT_execution_time += ecc_latency        // latency added to transaction
  → Stats::Total_ECC_retries / Total_ECC_uncorrectable updated
  → GC_and_WL_Unit::Check_read_reclaim_required()  // checked on EVERY read, not just failures
```

## Power-Law RBER Model

```
RBER = epsilon + alpha*(PE^k) + beta*(PE^m)*(time_hours^n) + gamma*(PE^p)*(avg_reads^q)
```

Hardcoded coefficients for 72-layer TLC (FTL.cpp lines 33-42, matching `tools/examples/rber_model_example.py`):

| Param | Value | Component |
|-------|-------|-----------|
| epsilon | 1.48e-3 | Base RBER (fresh flash) |
| alpha, k | 3.90e-10, 2.05 | Wear-out (PE cycles) |
| beta, m, n | 6.28e-05, 0.14, 0.54 | Retention loss (time in hours) |
| gamma, p, q | 3.73e-09, 0.33, 1.71 | Read disturb (avg reads/page) |

With 16KB pages (131072 bits), fresh flash alone produces **~194 expected bit errors**.

## Soft-Decode Retry Logic (ECC_Engine.cpp)

1. **Hard decode**: If `expected_errors <= correction_capability` → return 0 (success)
2. **Soft-decode retries**: Each retry r increases effective capability by 50%:
   `effective = correction_capability * (1.0 + 0.5 * r)`
3. Returns retry count (1..max_retries) on success, -1 if uncorrectable after all retries

**Latency**: `decode_latency * (1 + retry_count)`. Uncorrectable pays `decode_latency * (1 + max_retries)`.

## Parameter Configuration Gap

`Flash_Parameter_Set` (`.h` lines 33-43) defines XML-configurable ECC parameters:
- `ECC_Correction_Capability` (default: 40)
- `IFP_ECC_Decode_Latency` (default: 10000 ns)
- `IFP_ECC_Max_Retries` (default: 3)

**However**, FTL.cpp lines 43-46 **hardcode** these values (40, 5000, 0) and ignore Flash_Parameter_Set entirely. The FTL constructor does not include `Flash_Parameter_Set.h`.

To make ECC parameters XML-configurable, FTL.cpp must be modified to read from `Flash_Parameter_Set::ECC_Correction_Capability`, `Flash_Parameter_Set::IFP_ECC_Decode_Latency`, and `Flash_Parameter_Set::IFP_ECC_Max_Retries`.

## Block Metadata for RBER (Flash_Block_Manager_Base.h)

`Block_Pool_Slot_Type` tracks per-block:
- `Erase_count` — PE cycle counter (incremented on erase)
- `Read_count` — cumulative reads (incremented per read in `Read_transaction_issued()`, reset on erase)
- `First_write_time` — nanosecond timestamp of first write after erase (reset to INVALID_TIME on erase)

Retention time calculation: `(Simulator->Time() - First_write_time) / 3.6e12` (ns → hours)
Avg reads per page: `block.Read_count / pages_per_block`

## Statistics (Stats.h)

- `Total_ECC_retries` — sum of all retry counts across all reads
- `Total_ECC_failures` — same as uncorrectable
- `Total_ECC_uncorrectable` — reads that failed after all retries
- `Total_read_reclaim_migrations` — blocks migrated by read-reclaim

Reported in FTL::Report_results_in_XML() as inline XML attributes.

## Key Files

| File | Role |
|------|------|
| `src/ssd/ECC_Engine.h/cpp` | RBER model + retry logic |
| `src/ssd/FTL.cpp` lines 29-47 | ECC instantiation (hardcoded params) |
| `src/ssd/NVM_PHY_ONFI_NVDDR2.cpp` lines 561-609 | ECC invocation on read completion |
| `src/ssd/Flash_Block_Manager_Base.h` | Block_Pool_Slot_Type (Erase_count, Read_count, First_write_time) |
| `src/ssd/Flash_Block_Manager_Base.cpp` | Read_transaction_issued(), block erase/reset |
| `src/ssd/GC_and_WL_Unit_Page_Level.cpp` lines 195-260 | Read-reclaim check and execution |
| `src/exec/Flash_Parameter_Set.h/cpp` | XML-configurable ECC params (not yet wired to FTL) |
| `src/ssd/Stats.h/cpp` | ECC statistics counters |
