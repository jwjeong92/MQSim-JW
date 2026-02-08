# Read-Reclaim Operation Verification Plan

## Context

Read-reclaim is a proactive NAND flash management technique that prevents read disturb errors. When a block is read repeatedly, charge leakage in neighboring cells can cause bit errors. Read-reclaim **proactively** relocates valid pages **before** errors occur, triggered solely by reaching a read count threshold.

**Current Implementation Issue:**
The current code only calls `Check_read_reclaim_required()` when **ECC correction fails** (line 574-580 in `NVM_PHY_ONFI_NVDDR2.cpp`). This is **incorrect** - read-reclaim should trigger based on read count alone, regardless of ECC status.

**Correct Behavior:**
- Read-reclaim should check **every time** a read completes
- Trigger when `block->Read_count >= threshold`
- Threshold should be **configurable** via device XML config

**Verification Goal:**
1. Fix the trigger mechanism to check read count on every read
2. Make threshold configurable
3. Run test with low threshold (e.g., 1000 reads) and repetitive workload
4. Confirm read-reclaim executes correctly

## Critical Files

### Read-Reclaim Implementation
1. `src/ssd/GC_and_WL_Unit_Page_Level.cpp` (line 194-243) - Read-reclaim execution logic
2. `src/ssd/GC_and_WL_Unit_Base.h` (line 55) - Interface declaration
3. `src/ssd/NVM_PHY_ONFI_NVDDR2.cpp` (line 562-588) - **NEEDS FIX**: Should call check on every read, not just ECC failure

### Configuration
1. `src/exec/Flash_Parameter_Set.h/cpp` - Add read_reclaim_threshold parameter
2. `devconf/ssdconfig_ifp.xml` or similar - Add configuration entry

### Read Count Tracking
1. `src/ssd/Flash_Block_Manager_Base.cpp` (line 209-214) - `Read_transaction_issued()` increments `Read_count`
2. `src/ssd/Flash_Block_Manager_Base.h` (line 46) - `Block_Pool_Slot_Type::Read_count` member

### Statistics
1. `src/ssd/Stats.h` (line 42) - `Total_read_reclaim_migrations`
2. `src/ssd/Stats.cpp` - Initialization and reporting

## Implementation Plan

### Step 1: Make Read-Reclaim Threshold Configurable

**Add to `Flash_Parameter_Set.h`:**
```cpp
class Flash_Parameter_Set
{
public:
    // ... existing members ...
    unsigned int Read_reclaim_threshold; // Add this
};
```

**Add to `Flash_Parameter_Set.cpp` XML parsing:**
```cpp
// In the XML parsing section
if (strcmp(child_node->name(), "Read_Reclaim_Threshold") == 0) {
    params->Read_reclaim_threshold = std::stoul(child_node->value());
}
```

**Add to device XML config (e.g., `devconf/ssdconfig_ifp.xml`):**
```xml
<Read_Reclaim_Threshold>1000</Read_Reclaim_Threshold>
```

**Pass to GC_and_WL_Unit:**
Modify constructor to accept and store the threshold parameter.

**Update `GC_and_WL_Unit_Page_Level.h`:**
```cpp
class GC_and_WL_Unit_Page_Level : public GC_and_WL_Unit_Base
{
public:
    // Update constructor to accept read_reclaim_threshold
    GC_and_WL_Unit_Page_Level(..., unsigned int read_reclaim_threshold = 100000);

private:
    unsigned int read_reclaim_threshold; // Store as member variable
};
```

**Update `GC_and_WL_Unit_Page_Level.cpp`:**
```cpp
// Constructor
GC_and_WL_Unit_Page_Level::GC_and_WL_Unit_Page_Level(..., unsigned int read_reclaim_threshold)
    : GC_and_WL_Unit_Base(...), read_reclaim_threshold(read_reclaim_threshold)
{
}

// In Check_read_reclaim_required() - remove hardcoded constant
void GC_and_WL_Unit_Page_Level::Check_read_reclaim_required(...)
{
    // Remove: const unsigned int READ_RECLAIM_THRESHOLD = 100000;
    // Use: this->read_reclaim_threshold instead

    if (read_count < this->read_reclaim_threshold) {
        return;
    }
    // ... rest of function
}
```

### Step 2: Fix Read-Reclaim Trigger Mechanism

**Current (WRONG) - Only triggers on ECC failure:**
```cpp
// NVM_PHY_ONFI_NVDDR2.cpp lines 574-580
if (retry_count < 0) {  // Only when ECC fails!
    Stats::Total_ECC_uncorrectable++;
    Stats::Total_ECC_failures++;
    if (_my_instance->gc_wl_unit_ref != NULL) {
        _my_instance->gc_wl_unit_ref->Check_read_reclaim_required(tr->Address, block->Read_count);
    }
}
```

**Correct (FIX) - Check on every read completion:**
```cpp
// NVM_PHY_ONFI_NVDDR2.cpp - Move read-reclaim check outside ECC failure block
// Should be at line ~562, after getting block reference

if (_my_instance->ecc_engine != NULL && _my_instance->block_manager_ref != NULL) {
    for (auto ecc_it = dieBKE->ActiveTransactions.begin(); ecc_it != dieBKE->ActiveTransactions.end(); ecc_it++) {
        NVM_Transaction_Flash* tr = *ecc_it;
        if (tr->Type == Transaction_Type::READ || tr->Type == Transaction_Type::IFP_GEMV) {
            PlaneBookKeepingType* pbke = _my_instance->block_manager_ref->Get_plane_bookkeeping_entry(tr->Address);
            Block_Pool_Slot_Type* block = &pbke->Blocks[tr->Address.BlockID];

            // ECC checking
            int retry_count = _my_instance->ecc_engine->Attempt_correction(block->Read_count, block->Erase_count);
            sim_time_type ecc_latency = _my_instance->ecc_engine->Get_ECC_latency(retry_count);
            tr->STAT_execution_time += ecc_latency;

            if (retry_count > 0) {
                Stats::Total_ECC_retries += (unsigned long)retry_count;
            }
            if (retry_count < 0) {
                Stats::Total_ECC_uncorrectable++;
                Stats::Total_ECC_failures++;
            }

            // **NEW**: Check read-reclaim on EVERY read, regardless of ECC result
            if (_my_instance->gc_wl_unit_ref != NULL) {
                _my_instance->gc_wl_unit_ref->Check_read_reclaim_required(tr->Address, block->Read_count);
            }

            // IFP-specific handling
            if (tr->Type == Transaction_Type::IFP_GEMV) {
                ((NVM_Transaction_Flash_IFP*)tr)->ECC_retry_count = (retry_count > 0) ? (unsigned int)retry_count : 0;
                ((NVM_Transaction_Flash_IFP*)tr)->ECC_retry_needed = (retry_count != 0);
            }
        }
    }
}
```

**Key Change:** Move `Check_read_reclaim_required()` call **outside** the `if (retry_count < 0)` block so it executes on every read.

### Step 3: Add Debug Instrumentation

**Add to `GC_and_WL_Unit_Page_Level::Check_read_reclaim_required()`:**
```cpp
void GC_and_WL_Unit_Page_Level::Check_read_reclaim_required(
    const NVM::FlashMemory::Physical_Page_Address& block_address,
    unsigned int read_count)
{
    // Debug output every 100 reads
    if (read_count % 100 == 0) {
        std::cout << "[READ_RECLAIM_CHECK] Block ["
                  << block_address.ChannelID << "," << block_address.ChipID << ","
                  << block_address.DieID << "," << block_address.PlaneID << ","
                  << block_address.BlockID << "] read_count=" << read_count
                  << " threshold=" << this->read_reclaim_threshold << std::endl;
    }

    if (read_count < this->read_reclaim_threshold) {
        return;
    }

    std::cout << "*** [READ_RECLAIM_TRIGGERED] Block ["
              << block_address.ChannelID << "," << block_address.ChipID << ","
              << block_address.DieID << "," << block_address.PlaneID << ","
              << block_address.BlockID << "] reached threshold! read_count="
              << read_count << " threshold=" << this->read_reclaim_threshold << std::endl;

    // ... existing safety checks ...

    if (block_manager->Can_execute_gc_wl(reclaim_address)) {
        Stats::Total_read_reclaim_migrations++;

        std::cout << "*** [READ_RECLAIM_EXECUTING] Migrating "
                  << (block->Current_page_write_index - block->Invalid_page_count)
                  << " valid pages from block [" << block_address.BlockID << "]" << std::endl;

        // ... rest of execution logic ...
    }
}
```

### Step 4: Verify Statistics Reporting

**Check `Stats.cpp` initialization:**
```cpp
void Stats::Init_stats(...)
{
    // ... existing code ...
    Total_read_reclaim_migrations = 0;
    Total_ECC_failures = 0;
    Total_ECC_retries = 0;
    Total_ECC_uncorrectable = 0;
}
```

**Check `Stats.cpp` XML reporting:**
```cpp
void Stats::Report_results_in_XML(...)
{
    // Should include:
    xmlwriter.Write_attribute_string("Total_read_reclaim_migrations", std::to_string(Total_read_reclaim_migrations));
    xmlwriter.Write_attribute_string("Total_ECC_failures", std::to_string(Total_ECC_failures));
    xmlwriter.Write_attribute_string("Total_ECC_retries", std::to_string(Total_ECC_retries));
    xmlwriter.Write_attribute_string("Total_ECC_uncorrectable", std::to_string(Total_ECC_uncorrectable));
}
```

## Verification Test Plan

### Test 1: Simple Repetitive Read Workload

**Goal:** Quickly verify read-reclaim triggers with low threshold.

**Configuration:**
- Set `Read_Reclaim_Threshold` to **1000** in XML config
- Use small address space (e.g., 1GB)
- Run trace with repetitive reads to same LBA range

**Expected Behavior:**
1. Block read counts increase with each read
2. Debug output shows: `[READ_RECLAIM_CHECK]` every 100 reads
3. When read_count reaches 1000:
   - `[READ_RECLAIM_TRIGGERED]` message appears
   - `[READ_RECLAIM_EXECUTING]` message appears
   - Valid pages are migrated
   - Block is erased
   - `Read_count` resets to 0

**Success Criteria:**
- See read-reclaim execute within reasonable simulation time
- `Stats::Total_read_reclaim_migrations > 0` in output
- No crashes or errors during execution

### Test 2: Verify Read Count Resets After Erase

**Goal:** Confirm `Read_count` resets after read-reclaim erase.

**Method:**
1. Monitor a specific block as it accumulates reads
2. Observe read-reclaim execution
3. Verify `Read_count` returns to 0 after erase
4. Confirm no repeated reclaims on same block immediately

**Expected:**
- `Block_Pool_Slot_Type::Erase()` resets `Read_count = 0`
- Block can accumulate reads again after reclaim
- Read-reclaim doesn't trigger repeatedly on same block

### Test 3: Multiple Blocks Reaching Threshold

**Goal:** Verify read-reclaim works across multiple blocks.

**Configuration:**
- Distribute reads across multiple LBA ranges
- Run longer simulation
- Multiple blocks should reach threshold

**Expected:**
- See multiple `[READ_RECLAIM_TRIGGERED]` messages for different blocks
- `Total_read_reclaim_migrations` increments for each execution
- No interference between concurrent read-reclaim operations

### Test 4: Read-Reclaim Under Normal Workload

**Goal:** Observe read-reclaim in realistic conditions.

**Configuration:**
- Use existing LLM trace (`wkdconf/trace_llm.xml`)
- Set moderate threshold (e.g., 10,000)
- Run full workload

**Expected:**
- Some blocks may reach threshold depending on workload
- Read-reclaim should not interfere with normal I/O
- Performance impact should be minimal

## Validation Checklist

- [ ] Add `Read_reclaim_threshold` parameter to `Flash_Parameter_Set`
- [ ] Update XML config parsing to read threshold
- [ ] Pass threshold to `GC_and_WL_Unit_Page_Level` constructor
- [ ] Store threshold as member variable
- [ ] Remove hardcoded `READ_RECLAIM_THRESHOLD = 100000`
- [ ] Fix trigger in `NVM_PHY_ONFI_NVDDR2.cpp` to check on every read
- [ ] Add debug output to `Check_read_reclaim_required()`
- [ ] Add debug output when read-reclaim executes
- [ ] Verify `Total_read_reclaim_migrations` initialized in `Stats::Init_stats()`
- [ ] Verify statistics reported in XML output
- [ ] Create test XML config with threshold=1000
- [ ] Create simple repetitive read trace
- [ ] Run simulation and observe console output
- [ ] Verify `[READ_RECLAIM_TRIGGERED]` appears
- [ ] Verify `[READ_RECLAIM_EXECUTING]` appears
- [ ] Check XML output: `Total_read_reclaim_migrations > 0`
- [ ] Verify no crashes or errors

## Expected Console Output (Success)

```
[READ_RECLAIM_CHECK] Block [0,0,0,0,5] read_count=100 threshold=1000
[READ_RECLAIM_CHECK] Block [0,0,0,0,5] read_count=200 threshold=1000
...
[READ_RECLAIM_CHECK] Block [0,0,0,0,5] read_count=900 threshold=1000
*** [READ_RECLAIM_TRIGGERED] Block [0,0,0,0,5] reached threshold! read_count=1000 threshold=1000
*** [READ_RECLAIM_EXECUTING] Migrating 128 valid pages from block [5]
...
```

## Summary

This plan focuses on **fixing** the read-reclaim trigger mechanism and making it **easily testable**:

1. **Fix**: Move trigger check outside ECC failure condition
2. **Configure**: Make threshold adjustable via XML
3. **Test**: Lower threshold to 1000 for quick verification
4. **Observe**: Add debug output to track execution
5. **Validate**: Confirm statistics and behavior are correct

Once verified working, the threshold can be tuned based on realistic workload analysis and RBER modeling.
