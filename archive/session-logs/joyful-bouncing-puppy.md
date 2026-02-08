# IFP Read Reclaim Evaluation Plan (Revised)

## Context

We're evaluating how the read reclaim threshold affects read bandwidth during LLM inference (Llama-7B, 10 token generation). Previous attempts crashed due to workaround fixes layered onto a fundamentally broken preconditioning setup:

**Root cause of all crashes:** With `Enabled_Preconditioning=false` and `prefill_model=False`, the SSD started empty. Reads triggered `online_create_entry_for_reads` which called `Allocate_block_and_page_in_plane_for_user_write` — this incremented `Ongoing_user_program_count` but never decremented it (no real flash program transaction), and created pages with uninitialized flash metadata (NO_LPA). This caused:
1. `is_safe_gc_wl_candidate` always returning false (stale `Ongoing_user_program_count > 0`)
2. Segfaults in `Set_barrier_for_accessing_physical_block` (NO_LPA → out-of-bounds GlobalMappingTable access)
3. Cascading failures in the deferred GC handler

**Solution:** Use `prefill_model=True` to load model data through the **normal I/O write path** before inference reads. This ensures all counters are properly managed (write → `Program_transaction_serviced`) and all pages have valid LPA metadata. Then revert ALL workarounds and use standard GC/WL mechanisms.

**Key verification from code analysis:**
- `Allocate_block_and_page_in_plane_for_user_write` (Flash_Block_Manager.cpp:27) calls `program_transaction_issued` → increments counter
- `Allocate_Pages_in_block_and_invalidate_remaining_for_preconditioning` (Flash_Block_Manager.cpp:57-89) does NOT → no counter issue
- With `prefill_model=True`, writes go through normal path, `Program_transaction_serviced` is called on completion, counters settle to 0

## Evaluation Design

**Two scenarios:**
1. **Scenario A** (No Reclaim): `Read_Reclaim_Threshold = 1,000,000` — never reached in 10 tokens
2. **Scenario B** (With Reclaim): `Read_Reclaim_Threshold = 7,680` (5 x 1536 pages_per_block) — triggers at tokens 5 and 10

**Why threshold = 7,680:** With `prefill_model=True` and no preconditioning, model blocks contain 1,536 valid pages each (100% fill). Each token reads all 1,536 pages per block. After 5 tokens: Read_count = 5 x 1,536 = 7,680.

**Incremental simulation:** Run 10 sims per scenario (1..10 tokens). Per-token bandwidth = bytes_per_token / (sim_time(n) - sim_time(n-1)).

**Config:** `Enabled_Preconditioning=false`, `Ideal_Mapping_Table=true`, `Initial_Occupancy_Percentage=0`, `max_retries=0`

**Expected result:** Scenario A shows flat bandwidth; Scenario B shows dips at tokens 5 and 10.

## Implementation Steps

### Step 1: Revert workarounds in GC_and_WL_Unit_Base.cpp

**File:** `src/ssd/GC_and_WL_Unit_Base.cpp`

Two NO_LPA workarounds to remove:

**1a.** Lines 81-83 — Remove NO_LPA skip in deferred page movement loop:
```cpp
// DELETE these 3 lines:
if (page_lpa == NO_LPA) {
    continue; // Skip pages with uninitialized metadata
}
```

**1b.** Lines 133-138 — Remove NO_LPA guard in GC read completion handler:
```cpp
// DELETE these 6 lines:
if (transaction->LPA == NO_LPA) {
    // Page has uninitialized metadata; skip page movement
    ((NVM_Transaction_Flash_RD*)transaction)->RelatedWrite->RelatedRead = NULL;
    pbke->Blocks[((NVM_Transaction_Flash_RD*)transaction)->RelatedWrite->RelatedErase->Address.BlockID].Erase_transaction->Page_movement_activities.remove(((NVM_Transaction_Flash_RD*)transaction)->RelatedWrite);
    break;
}
```

### Step 2: Revert workarounds in Address_Mapping_Unit_Page_Level.cpp

**File:** `src/ssd/Address_Mapping_Unit_Page_Level.cpp`

**2a.** Lines 1389-1391 — Remove `Program_transaction_serviced` call in `online_create_entry_for_reads`:
```cpp
// DELETE these 2 lines (after Allocate_block_and_page_in_plane_for_user_write):
// Undo the Ongoing_user_program_count increment from Allocate_block_and_page_in_plane_for_user_write,
// since this is an on-the-fly mapping entry creation for reads, not an actual program transaction.
block_manager->Program_transaction_serviced(read_address);
```

**2b.** Lines 1794-1796 — Remove NO_LPA guard in `Set_barrier_for_accessing_physical_block`:
```cpp
// DELETE these 3 lines:
if (lpa == NO_LPA) {
    continue; // Skip pages with uninitialized metadata (e.g., from preconditioning edge cases)
}
```

### Step 3: Rewrite Check_read_reclaim_required

**File:** `src/ssd/GC_and_WL_Unit_Page_Level.cpp`

Replace current implementation (which has a custom inline safety check bypassing `Ongoing_user_program_count`) with standard mechanisms. Key changes:
- Use `is_safe_gc_wl_candidate(pbke, block_address.BlockID)` instead of custom inline write-frontier-only check
- Remove NO_LPA skip in page movement loop (not needed with proper writes)
- Follow exact same pattern as `Check_gc_required` and `run_static_wearleveling`

```cpp
void GC_and_WL_Unit_Page_Level::Check_read_reclaim_required(
    const NVM::FlashMemory::Physical_Page_Address& block_address, unsigned int read_count)
{
    if (read_count < this->read_reclaim_threshold) {
        return;
    }

    PlaneBookKeepingType* pbke = block_manager->Get_plane_bookkeeping_entry(block_address);

    if (pbke->Ongoing_erase_operations.find(block_address.BlockID) != pbke->Ongoing_erase_operations.end()) {
        return;
    }
    if (pbke->Ongoing_erase_operations.size() >= max_ongoing_gc_reqs_per_plane) {
        return;
    }
    if (!is_safe_gc_wl_candidate(pbke, block_address.BlockID)) {
        return;
    }

    NVM::FlashMemory::Physical_Page_Address reclaim_address(block_address);
    Block_Pool_Slot_Type* block = &pbke->Blocks[block_address.BlockID];

    // No valid pages to move
    if (block->Current_page_write_index == 0 || block->Invalid_page_count == block->Current_page_write_index) {
        return;
    }

    block_manager->GC_WL_started(reclaim_address);
    pbke->Ongoing_erase_operations.insert(block_address.BlockID);
    address_mapping_unit->Set_barrier_for_accessing_physical_block(reclaim_address);

    if (block_manager->Can_execute_gc_wl(reclaim_address)) {
        Stats::Total_read_reclaim_migrations++;
        tsu->Prepare_for_transaction_submit();

        NVM_Transaction_Flash_ER* erase_tr = new NVM_Transaction_Flash_ER(
            Transaction_Source_Type::GC_WL, block->Stream_id, reclaim_address);

        if (block->Current_page_write_index - block->Invalid_page_count > 0) {
            for (flash_page_ID_type pageID = 0; pageID < block->Current_page_write_index; pageID++) {
                if (block_manager->Is_page_valid(block, pageID)) {
                    Stats::Total_page_movements_for_gc++;
                    reclaim_address.PageID = pageID;
                    NVM_Transaction_Flash_RD* gc_read = new NVM_Transaction_Flash_RD(
                        Transaction_Source_Type::GC_WL, block->Stream_id,
                        sector_no_per_page * SECTOR_SIZE_IN_BYTE,
                        NO_LPA, address_mapping_unit->Convert_address_to_ppa(reclaim_address),
                        reclaim_address, NULL, 0, NULL, 0, INVALID_TIME_STAMP);
                    NVM_Transaction_Flash_WR* gc_write = new NVM_Transaction_Flash_WR(
                        Transaction_Source_Type::GC_WL, block->Stream_id,
                        sector_no_per_page * SECTOR_SIZE_IN_BYTE,
                        NO_LPA, NO_PPA, reclaim_address, NULL, 0, gc_read, 0, INVALID_TIME_STAMP);
                    gc_write->ExecutionMode = WriteExecutionModeType::SIMPLE;
                    gc_write->RelatedErase = erase_tr;
                    gc_read->RelatedWrite = gc_write;
                    tsu->Submit_transaction(gc_read);
                    erase_tr->Page_movement_activities.push_back(gc_write);
                }
            }
        }
        block->Erase_transaction = erase_tr;
        tsu->Submit_transaction(erase_tr);
        tsu->Schedule();
    }
}
```

### Step 4: Update lib/llm_trace_gen.py

**File:** `lib/llm_trace_gen.py`

**4a.** Line 136: Change `prefill_model=False` to `True`:
```python
gen.generate(generation_length=n, prefill_model=True)
```

**4b.** Line 187: Set `Initial_Occupancy_Percentage=0` in workload configs:
```xml
<Initial_Occupancy_Percentage>0</Initial_Occupancy_Percentage>
```

**4c.** Line 66 (in LLMTraceGenerator.generate): Reduce write-to-read gap from 1,000s to 10s:
```python
current_time_ns += 10_000_000_000  # 10 seconds gap (was 1000s)
```

**4d.** Remove `if os.path.exists(trace_path): continue` skip logic (lines 128-130), or add a `--force` mechanism to force regeneration of all traces, configs, and results.

### Step 5: Clean artifacts, build, and run

```bash
# Clean old artifacts
rm -f traces/llama_7b_gen_*_tok.trace
rm -f results/eval_*
rm -f devconf/eval_*.xml
rm -f wkdconf/eval_*.xml

# Build
make -j$(nproc)

# Run evaluation
cd lib && /home/jwjeong/miniconda3/bin/python3 llm_trace_gen.py
```

## Files Modified

| File | Change | Type |
|------|--------|------|
| `src/ssd/GC_and_WL_Unit_Base.cpp` | Remove 2 NO_LPA workarounds (lines 81-83, 133-138) | REVERT |
| `src/ssd/Address_Mapping_Unit_Page_Level.cpp` | Remove Program_transaction_serviced fix (1389-1391) + NO_LPA guard (1794-1796) | REVERT |
| `src/ssd/GC_and_WL_Unit_Page_Level.cpp` | Replace custom safety check with `is_safe_gc_wl_candidate` | REWRITE |
| `lib/llm_trace_gen.py` | prefill_model=True, Initial_Occupancy_Percentage=0, reduce gap time | MODIFY |

## Files Unchanged (essential infrastructure, keep as-is)

| File | What's kept |
|------|-------------|
| `src/ssd/FTL.cpp` | max_retries=0 (line 46) |
| `src/ssd/Flash_Block_Manager.cpp` | stream_id assertion removed from Invalidate_page_in_block |
| `src/ssd/Flash_Block_Manager_Base.cpp` | First_write_time tracking in Program_transaction_serviced |
| `src/ssd/Flash_Block_Manager_Base.h` | Read_count and First_write_time fields in Block_Pool_Slot_Type |
| `src/ssd/NVM_PHY_ONFI_NVDDR2.cpp` | Read reclaim trigger (line 599-601) after read completion |
| `src/ssd/ECC_Engine.cpp/.h` | Power-law RBER model |

## Verification

### Smoke Test (before full run)
1. Build MQSim
2. Run a single 1-token high_threshold simulation manually
3. Verify: completes without crash, output XML has `Bytes_Transferred_Read > 0`

### Full Evaluation
1. Run all 20 simulations via pipeline
2. ALL must complete without crashes (rc=0, no stderr errors)
3. Scenario A (high_threshold): flat bandwidth across all 10 tokens, `Total_read_reclaim_migrations=0`
4. Scenario B (low_threshold): bandwidth dips at tokens 5 and 10, `Total_read_reclaim_migrations > 0` for n >= 5
5. No "Inconsistency" errors in any simulation output

### Sanity Checks
- Per-token bandwidth should be in the range of ~3-8 GB/s (reasonable for 8-channel SSD)
- Simulation time increases roughly linearly with token count for Scenario A
- The generated plot clearly shows the read reclaim bandwidth impact
