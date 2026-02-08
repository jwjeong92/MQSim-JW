# RBER Model Integration Plan

## Context

MQSim currently has a simplified linear RBER (Raw Bit Error Rate) model in the ECC_Engine:
```
rber = base_rber + read_factor * read_count + erase_factor * erase_count
```

The user wants to replace this with a more realistic power-law RBER model from `lib/rber_model_example.py`:
```python
total_rber = epsilon + alpha * (cycles^k) +
             beta * (cycles^m) * (time^n) +
             gamma * (cycles^p) * (reads^q)
```

This model captures three key NAND flash degradation mechanisms:
1. **Wear-out**: Non-linear degradation with PE cycles (power-law)
2. **Retention loss**: Data degradation over time, accelerated by PE cycles
3. **Read disturb**: Error rate increase from repeated reads (power-law)

**Important Model Details:**
- **Retention time** is measured in **hours** (not seconds)
- **Reads** parameter = `block_read_count / pages_per_block` (average reads per page)
- **RBER calculation is at block level**, not per-page level

The current codebase already tracks PE cycles (`Erase_count`) and read counts (`Read_count`) per block, but lacks **block-level retention time tracking** (time since block was first written after erase).

## Critical Files

### Files to Modify
1. `src/ssd/ECC_Engine.h` - Update RBER model interface
2. `src/ssd/ECC_Engine.cpp` - Implement power-law RBER calculation
3. `src/ssd/Flash_Block_Manager_Base.h` - Add page write timestamp tracking
4. `src/ssd/Flash_Block_Manager_Base.cpp` - Record timestamps on writes, allocate/deallocate timestamp arrays
5. `src/ssd/NVM_PHY_ONFI_NVDDR2.cpp` - Calculate retention time when checking ECC
6. `src/ssd/FTL.cpp` - Update ECC_Engine initialization with new parameters

### Existing Infrastructure (Reuse)
- `Block_Pool_Slot_Type` (Flash_Block_Manager_Base.h) - Already has `Erase_count` and `Read_count`
- `NVM_PHY_ONFI_NVDDR2::handle_ready_signal_from_chip()` - Already calls ECC engine for read operations (line 562-588)
- `Simulator->Time()` - Simulation time accessor for timestamps

## Implementation Plan

### 1. Update ECC_Engine Interface (ECC_Engine.h)

**Changes:**
- Replace linear coefficients with power-law coefficients:
  - Remove: `base_rber`, `read_factor`, `erase_factor`
  - Add: `epsilon`, `alpha`, `k`, `beta`, `m`, `n`, `gamma`, `p`, `q`
- Update constructor signature to accept 9 power-law parameters
- Update `Calculate_RBER()` to accept retention time in hours:
  ```cpp
  double Calculate_RBER(unsigned int pe_cycles, double retention_time_hours, double avg_reads_per_page);
  ```
- Update `Attempt_correction()` to accept retention time and average reads:
  ```cpp
  int Attempt_correction(unsigned int pe_cycles, double retention_time_hours, double avg_reads_per_page);
  ```

### 2. Implement Power-Law RBER Model (ECC_Engine.cpp)

**Changes:**
- Update constructor to initialize 9 coefficients
- Implement power-law calculation in `Calculate_RBER()`:
  ```cpp
  double ECC_Engine::Calculate_RBER(unsigned int pe_cycles, double retention_time_hours, double avg_reads_per_page)
  {
      // retention_time_hours is already in hours (expected by model)
      // avg_reads_per_page = block_read_count / pages_per_block

      double rber = epsilon
                  + alpha * pow(pe_cycles, k)
                  + beta * pow(pe_cycles, m) * pow(retention_time_hours, n)
                  + gamma * pow(pe_cycles, p) * pow(avg_reads_per_page, q);

      return rber;
  }
  ```
- Update `Attempt_correction()` to pass retention time and average reads to `Calculate_RBER()`

**Note:** Use `<cmath>` for `pow()` function (already included)

### 3. Add Block-Level Retention Time Tracking (Flash_Block_Manager_Base.h)

**Changes to `Block_Pool_Slot_Type`:**
- Add member variable to track when block was first written after erase:
  ```cpp
  sim_time_type First_write_time; // Time when first page was written after erase
  ```
- This single timestamp per block is sufficient for block-level RBER calculation

**Changes to `Block_Pool_Slot_Type::Erase()`:**
- Initialize `First_write_time` to INVALID_TIME when block is erased

### 4. Track Block First Write Time (Flash_Block_Manager_Base.cpp)

**Changes:**

**Block initialization** (constructor where blocks are allocated):
- Initialize `First_write_time` to INVALID_TIME:
  ```cpp
  pbke->Blocks[block_id].First_write_time = INVALID_TIME;
  ```

**Update `Block_Pool_Slot_Type::Erase()`:**
- Reset `First_write_time` when block is erased:
  ```cpp
  void Block_Pool_Slot_Type::Erase()
  {
      Current_page_write_index = 0;
      Invalid_page_count = 0;
      Erase_count++;
      // ... existing code ...
      Read_count = 0;
      First_write_time = INVALID_TIME; // Reset retention timer
      // ... existing code ...
  }
  ```

**Update `Program_transaction_serviced()`:**
- Record time of first write to block (only once after erase):
  ```cpp
  void Flash_Block_Manager_Base::Program_transaction_serviced(const NVM::FlashMemory::Physical_Page_Address& page_address)
  {
      // ... existing code ...

      PlaneBookKeepingType* pbke = Get_plane_bookkeeping_entry(page_address);
      Block_Pool_Slot_Type* block = &pbke->Blocks[page_address.BlockID];

      // Record first write time if not set
      if (block->First_write_time == INVALID_TIME) {
          block->First_write_time = Simulator->Time();
      }

      // ... existing code ...
  }
  ```

### 5. Calculate Retention Time for ECC (NVM_PHY_ONFI_NVDDR2.cpp)

**Changes in `handle_ready_signal_from_chip()`** (around line 562-588):

Replace:
```cpp
int retry_count = _my_instance->ecc_engine->Attempt_correction(block->Read_count, block->Erase_count);
```

With:
```cpp
// Calculate retention time in hours
double retention_time_hours = 0.0;
if (block->First_write_time != INVALID_TIME) {
    sim_time_type retention_time_ns = Simulator->Time() - block->First_write_time;
    retention_time_hours = retention_time_ns / (3600.0 * 1e9); // ns to hours
}

// Calculate average reads per page
// Need to get pages_per_block - can access from block manager or use constant
unsigned int pages_per_block = /* get from block manager or config */;
double avg_reads_per_page = (double)block->Read_count / pages_per_block;

int retry_count = _my_instance->ecc_engine->Attempt_correction(
    block->Erase_count,
    retention_time_hours,
    avg_reads_per_page
);
```

**Note:** Need to access `pages_per_block` - can be obtained from block manager configuration or passed as parameter

### 6. Update ECC Engine Initialization (FTL.cpp)

**Changes in FTL constructor** (line 33):

Replace:
```cpp
ECC = new ECC_Engine(1e-9, 1e-10, 1e-8, page_size_bits, 40, 5000, 3);
```

With 72-layer TLC parameters from `lib/rber_model_example.py`:
```cpp
// RBER model parameters for 72-layer TLC NAND
// epsilon: base error, alpha/k: wear-out, beta/m/n: retention, gamma/p/q: read disturb
ECC = new ECC_Engine(
    1.48e-03,  // epsilon: base RBER
    3.90e-10,  // alpha: wear-out coefficient
    2.05,      // k: wear-out exponent
    6.28e-05,  // beta: retention coefficient
    0.14,      // m: retention PE cycle exponent
    0.54,      // n: retention time exponent
    3.73e-09,  // gamma: read disturb coefficient
    0.33,      // p: read disturb PE cycle exponent
    1.71,      // q: read disturb read count exponent
    page_size_bits,  // page size
    40,        // correction_capability (bits)
    5000,      // decode_latency (ns)
    3          // max_retries
);
```

**Add comments** to explain each parameter for future maintainability.

## Edge Cases and Considerations

### 1. Unwritten Blocks
- Blocks that haven't been written yet will have `First_write_time == INVALID_TIME`
- When reading such blocks (shouldn't happen in normal operation), treat retention time as 0
- The model will still calculate RBER based on block PE cycles and read count

### 2. Memory Overhead
- Each block needs only one additional `sim_time_type` (8 bytes)
- For large SSDs (e.g., 10,000 blocks): only ~80KB additional memory
- Negligible overhead compared to per-page tracking

### 3. Retention Time Units
- MQSim uses nanoseconds for `sim_time_type`
- The RBER model expects **hours** for retention time
- Convert: `retention_time_hours = retention_time_ns / (3600.0 * 1e9)`

### 4. Numerical Stability
- Power-law terms can produce very large or small numbers
- Use `double` precision throughout RBER calculations
- For extremely high PE cycles or long retention times, ensure no overflow

### 4. Average Reads Per Page
- The model expects average reads per page, not total block reads
- Calculate: `avg_reads_per_page = block->Read_count / pages_per_block`
- Need to access `pages_per_block` configuration in NVM_PHY layer

### 5. Block Erase Reset
- When a block is erased, `First_write_time` must be reset to INVALID_TIME
- Read_count is already reset to 0 in existing `Erase()` method
- Erase_count is incremented

## Verification Plan

### Unit Testing
1. **Test RBER calculation with known inputs:**
   - Create test case with cycles=1000, time=1000s, reads=100
   - Compare output with Python model result
   - Verify all four terms (epsilon + wear-out + retention + read disturb)

2. **Test edge cases:**
   - Zero PE cycles (fresh flash): should return epsilon
   - Zero retention time: only epsilon + wear-out + read disturb
   - Zero read count: only epsilon + wear-out + retention

### Integration Testing
1. **Run existing trace workload:**
   - Use `wkdconf/trace_llm.xml` or similar
   - Verify ECC statistics are collected (retries, uncorrectable errors)
   - Check that retention time increases as simulation progresses

2. **Verify timestamp tracking:**
   - Add debug prints to confirm timestamps are set on writes
   - Confirm retention time increases when reading old data
   - Verify timestamps reset on block erase

### Output Validation
1. **Check ECC statistics in results:**
   - `Stats::Total_ECC_retries` should increase as blocks age
   - `Stats::Total_ECC_uncorrectable` should remain low for reasonable PE cycles
   - RBER should increase with PE cycles, retention time, and read count

2. **Compare with baseline:**
   - Run same workload with old linear model vs new power-law model
   - Expect higher RBER values with power-law model (more realistic)
   - Document differences in error rates

### Parameter Validation
1. **Verify coefficient values:**
   - Confirm epsilon = 1.48e-03 matches Python model
   - Check all 9 parameters match `lib/rber_model_example.py`

2. **Test parameter sensitivity:**
   - Increase PE cycles dramatically (e.g., 10,000 cycles)
   - Verify RBER increases as expected
   - Ensure model produces reasonable error rates

## Future Enhancements (Out of Scope)

1. **XML Configuration Support:**
   - Add RBER model parameters to `ssdconfig.xml`
   - Allow users to customize coefficients for different flash types
   - Currently hardcoded in FTL.cpp for simplicity

2. **Per-Page PE Cycle Tracking:**
   - Current model uses block-level Erase_count
   - Could track per-page write counts for finer granularity
   - Requires more memory and complexity

3. **Temperature Effects:**
   - RBER models can include temperature acceleration
   - Requires temperature tracking in simulator
   - Significant scope expansion

4. **Multiple NAND Types:**
   - Support SLC/MLC/TLC/QLC with different coefficients
   - Requires architecture changes to ECC_Engine
   - Beyond current requirements

## Summary

This plan replaces MQSim's simplified linear RBER model with a realistic power-law model that captures wear-out, retention loss, and read disturb effects. The implementation leverages existing PE cycle and read count tracking, and adds page-level write timestamp tracking to calculate retention time. All modifications are localized to 6 files with minimal disruption to existing code architecture.
