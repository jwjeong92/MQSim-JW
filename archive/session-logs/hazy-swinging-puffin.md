# In-Flash Processing (IFP) for LLM Inference -- Development Plan

## Context

MQSim-JW is a NAND flash SSD simulator. The goal is to extend it to support In-Flash Processing (IFP) for LLM inference under the In-Flash Computing paradigm. The flash chip contains PE units that perform lightweight ECC decoding and dot-product operations on-chip. The host issues GEMV requests via a vendor-specific NVMe opcode; the flash chip reads weight pages, computes partial dot products, and returns results to the SSD controller for aggregation.

Two reliability mechanisms are required: (1) read-reclaim based on per-block read count thresholds, and (2) probabilistic ECC failure with on-chip retry.

---

## Phase 1: Foundation -- Types, Opcodes, Configuration

All steps in this phase are independent and can be done in parallel.

### Step 1.1: Add IFP enums to request and transaction types

| File | Change |
|------|--------|
| `src/ssd/User_Request.h:13` | Add `IFP_GEMV` to `UserRequestType` |
| `src/ssd/NVM_Transaction.h:13` | Add `IFP_GEMV` to `Transaction_Type` |
| `src/host/Host_IO_Request.h:8` | Add `IFP_GEMV` to `Host_IO_Request_Type` |

### Step 1.2: Add NVMe vendor-specific GEMV opcode

| File | Change |
|------|--------|
| `src/ssd/Host_Interface_Defs.h` | Add `#define NVME_IFP_GEMV_OPCODE 0x00C0` |

### Step 1.3: Add flash command codes for IFP

| File | Change |
|------|--------|
| `src/nvm_chip/flash_memory/Flash_Command.h` | Add `CMD_IFP_READ_DOT_PRODUCT 0xA000` and `CMD_IFP_READ_DOT_PRODUCT_MULTIPLANE 0xA001` |

### Step 1.4: Add IFP/ECC/read-reclaim parameters to config

| File | Change |
|------|--------|
| `src/exec/Flash_Parameter_Set.h` | Add static members: `IFP_Enabled`, `IFP_Dot_Product_Latency`, `IFP_ECC_Decode_Latency`, `IFP_ECC_Retry_Latency`, `IFP_ECC_Max_Retries`, `Read_Reclaim_Threshold`, `ECC_Base_RBER`, `ECC_Read_Count_Factor`, `ECC_PE_Cycle_Factor`, `ECC_Retention_Factor`, `ECC_Correction_Capability`, `ECC_Codeword_Size`, `IFP_Aggregation_Mode` |
| `src/exec/Flash_Parameter_Set.cpp` | Add defaults, XML serialize/deserialize |

### Step 1.5: Add per-block read count tracking

| File | Change |
|------|--------|
| `src/ssd/Flash_Block_Manager_Base.h` | Add `unsigned int Read_count` to `Block_Pool_Slot_Type` |
| `src/ssd/Flash_Block_Manager_Base.cpp` | Initialize `Read_count = 0`, reset on `Erase()` |

### Step 1.6: Add IFP statistics counters

| File | Change |
|------|--------|
| `src/ssd/Stats.h` | Add `IssuedIFPGemvCMD`, `Total_read_reclaim_migrations`, `Total_ECC_failures`, `Total_ECC_retries`, `Total_ECC_uncorrectable` |
| `src/ssd/Stats.cpp` | Initialize/clear the new counters |

### Phase 1 Verification

1. **Build**: `make clean && make` -- must compile with zero errors and zero warnings related to new code
2. **Enum check**: Grep for `IFP_GEMV` across `src/` -- confirm it appears in `User_Request.h`, `NVM_Transaction.h`, `Host_IO_Request.h`
3. **Opcode check**: Grep for `NVME_IFP_GEMV_OPCODE` -- confirm `0x00C0` in `Host_Interface_Defs.h`
4. **Flash command check**: Grep for `CMD_IFP_READ_DOT_PRODUCT` -- confirm in `Flash_Command.h`
5. **Config check**: Grep for `IFP_Enabled` -- confirm in `Flash_Parameter_Set.h/.cpp` with XML serialization
6. **Block tracking check**: Grep for `Read_count` in `Flash_Block_Manager_Base` -- confirm initialized to 0 and reset on erase
7. **Stats check**: Grep for `IssuedIFPGemvCMD` -- confirm declared in `Stats.h` and initialized in `Stats.cpp`
8. **Regression**: Run existing workload (`./mqsim -i <existing_config.xml>`) -- confirm no behavioral change for standard READ/WRITE flows

---

## Phase 2: IFP Transaction Subclass

**Depends on:** Phase 1

### Step 2.1: Create NVM_Transaction_Flash_IFP

| File | Change |
|------|--------|
| `src/ssd/NVM_Transaction_Flash_IFP.h` | **New file.** Subclass of `NVM_Transaction_Flash` (pattern: `NVM_Transaction_Flash_RD`). Adds: `Content`, `read_sectors_bitmap`, `DataTimeStamp`, `Partial_dot_product_result`, `ECC_retry_needed`, `ECC_retry_count`, `Aggregation_complete` |
| `src/ssd/NVM_Transaction_Flash_IFP.cpp` | **New file.** Constructor implementations |

No Makefile change needed -- `src/ssd/*.cpp` is auto-collected.

### Phase 2 Verification

1. **Build**: `make clean && make` -- must compile with zero errors
2. **Class check**: Grep for `NVM_Transaction_Flash_IFP` -- confirm new header/source files exist under `src/ssd/`
3. **Inheritance check**: Read `NVM_Transaction_Flash_IFP.h` -- confirm it inherits from `NVM_Transaction_Flash` and has all required fields (`Partial_dot_product_result`, `ECC_retry_needed`, `ECC_retry_count`, etc.)
4. **Regression**: Run existing workload -- confirm no behavioral change

---

## Phase 3: Host Interface -- GEMV Request Path

**Depends on:** Phases 1, 2

### Step 3.1: Extend trace format for GEMV

| File | Change |
|------|--------|
| `src/host/ASCII_Trace_Definition.h` | Add `ASCIITraceGemvCode "2"` and `ASCIITraceGemvCodeInteger 2` |

### Step 3.2: Extend trace parser

| File | Change |
|------|--------|
| `src/host/IO_Flow_Trace_Based.cpp` | In `Generate_next_request()`, add branch for GEMV trace code |

### Step 3.3: Extend IO_Flow_Base for GEMV SQE opcode

| File | Change |
|------|--------|
| `src/host/IO_Flow_Base.cpp` | In `Submit_io_request()`, map `IFP_GEMV` to `NVME_IFP_GEMV_OPCODE` |

### Step 3.4: Decode GEMV in NVMe host interface

| File | Change |
|------|--------|
| `src/ssd/Host_Interface_NVMe.cpp` | In `Request_Fetch_Unit_NVMe::Process_pcie_read_message()`, add case for `NVME_IFP_GEMV_OPCODE` creating `UserRequestType::IFP_GEMV` |

### Step 3.5: Segment GEMV user requests into IFP transactions

| File | Change |
|------|--------|
| `src/ssd/Host_Interface_NVMe.cpp` | In `Input_Stream_Manager_NVMe::segment_user_request()`, add branch creating `NVM_Transaction_Flash_IFP` objects. In `Handle_new_arrived_request()`, handle `IFP_GEMV` like READ. In `Handle_serviced_request()`, treat `IFP_GEMV` as READ for response path. |

### Phase 3 Verification

1. **Build**: `make clean && make` -- must compile with zero errors
2. **Trace format check**: Grep for `ASCIITraceGemvCode` -- confirm in `ASCII_Trace_Definition.h`
3. **GEMV trace test**: Create a minimal trace file with a single GEMV entry (type `2`) and run: `./mqsim -i <ifp_config.xml>` -- confirm simulator accepts the trace without crash/assertion
4. **Host path check**: Add temporary `PRINT_MESSAGE` in `segment_user_request()` IFP branch and confirm it fires when processing the GEMV trace entry (remove after verification)
5. **Regression**: Run existing READ/WRITE-only trace -- confirm no behavioral change

---

## Phase 4: Flash Chip Layer -- IFP Latency Modeling

**Depends on:** Phase 1 (can run in parallel with Phase 3)

### Step 4.1: Add IFP latency to Flash_Chip

| File | Change |
|------|--------|
| `src/nvm_chip/flash_memory/Flash_Chip.h` | Add `_ifpDotProductLatency`, `_ifpEccDecodeLatency` members. Extend `Get_command_execution_latency()` for `CMD_IFP_READ_DOT_PRODUCT*` returning `readLatency + eccDecodeLatency + dotProductLatency + RBSignalDelay` |
| `src/nvm_chip/flash_memory/Flash_Chip.cpp` | Extend constructor to accept IFP latency params. Handle IFP commands in `finish_command_execution()` alongside reads. |

### Step 4.2: Wire config to Flash_Chip construction

| File | Change |
|------|--------|
| `src/exec/SSD_Device.cpp` (or ONFI channel construction) | Pass `Flash_Parameter_Set::IFP_Dot_Product_Latency` and `IFP_ECC_Decode_Latency` to Flash_Chip constructor |

### Phase 4 Verification

1. **Build**: `make clean && make` -- must compile with zero errors
2. **Latency model check**: Grep for `_ifpDotProductLatency` and `_ifpEccDecodeLatency` in `Flash_Chip.h/.cpp` -- confirm they are declared, initialized from constructor args, and used in `Get_command_execution_latency()`
3. **Config wiring check**: Grep for `IFP_Dot_Product_Latency` in `SSD_Device.cpp` -- confirm it is passed to `Flash_Chip` constructor
4. **Latency formula audit**: Read the `Get_command_execution_latency()` IFP branch -- confirm it returns `readLatency + eccDecodeLatency + dotProductLatency + RBSignalDelay`
5. **Regression**: Run existing workload -- confirm no behavioral change for standard commands

---

## Phase 5: FTL Layer -- Address Mapping, Scheduling, PHY

**Depends on:** Phases 1, 2, 4

### Step 5.1: Extend address mapping for IFP_GEMV

| File | Change |
|------|--------|
| `src/ssd/Address_Mapping_Unit_Page_Level.cpp` | In `Translate_lpa_to_ppa_and_dispatch()`, handle `Transaction_Type::IFP_GEMV` alongside `READ` |

### Step 5.2: Add IFP transaction queue to TSU

| File | Change |
|------|--------|
| `src/ssd/TSU_OutofOrder.h` | Add `Flash_Transaction_Queue **UserIFPTRQueue` |
| `src/ssd/TSU_OutofOrder.cpp` | Allocate IFP queue in constructor. In `Schedule()`, route `IFP_GEMV` to `UserIFPTRQueue`. Implement `service_ifp_transaction()`. |

### Step 5.3: Set IFP scheduling priority

| File | Change |
|------|--------|
| `src/ssd/TSU_Base.h` | Add `virtual bool service_ifp_transaction()`. Update `process_chip_requests()` to priority: **read > ifp > write > erase**. Add `IFP_GEMV` case in `transaction_is_ready()` returning `true`. |

### Step 5.4: Extend PHY layer for IFP commands

| File | Change |
|------|--------|
| `src/ssd/NVM_PHY_ONFI_NVDDR2.h` | Add `IFP_CMD_ADDR_TRANSFERRED` to `NVDDR2_SimEventType`. Add `ECC_Engine*` and `Flash_Block_Manager_Base*` members. |
| `src/ssd/NVM_PHY_ONFI_NVDDR2.cpp` | In `Send_command_to_chip()`: add `IFP_GEMV` case using `CMD_IFP_READ_DOT_PRODUCT`. In `Execute_simulator_event()`: handle `IFP_CMD_ADDR_TRANSFERRED`. In `handle_ready_signal_from_chip()`: handle IFP command codes alongside reads. In `transfer_read_data_from_chip()`: if chip-level aggregation mode, transfer only 8 bytes (partial scalar) instead of full page. |

### Step 5.5: Increment per-block read count

| File | Change |
|------|--------|
| `src/ssd/Flash_Block_Manager_Base.cpp` | In `Read_transaction_issued()`, also increment `block.Read_count` |

### Phase 5 Verification

1. **Build**: `make clean && make` -- must compile with zero errors
2. **Address mapping check**: Grep for `IFP_GEMV` in `Address_Mapping_Unit_Page_Level.cpp` -- confirm it is handled in `Translate_lpa_to_ppa_and_dispatch()`
3. **TSU queue check**: Grep for `UserIFPTRQueue` in `TSU_OutofOrder.h/.cpp` -- confirm allocation, routing, and servicing
4. **Priority check**: Read `TSU_Base.h` `process_chip_requests()` -- confirm priority order: read > ifp > write > erase
5. **PHY check**: Grep for `IFP_CMD_ADDR_TRANSFERRED` in `NVM_PHY_ONFI_NVDDR2.cpp` -- confirm handling in `Send_command_to_chip()`, `Execute_simulator_event()`, and `handle_ready_signal_from_chip()`
6. **Read count increment check**: Read `Flash_Block_Manager_Base.cpp` `Read_transaction_issued()` -- confirm `Read_count` is incremented
7. **End-to-end GEMV flow test**: Run GEMV trace with `PRINT_MESSAGE` debug output at key points (TSU enqueue, PHY send, chip complete) -- confirm full transaction flow: FTL -> TSU -> PHY -> Flash_Chip -> completion (remove debug prints after verification)
8. **Regression**: Run existing READ/WRITE workload -- confirm no behavioral change

---

## Phase 6: Data Cache Manager -- GEMV Handling

**Depends on:** Phase 1 (can run in parallel with Phase 5)

### Step 6.1: Handle IFP_GEMV in cache managers

| File | Change |
|------|--------|
| `src/ssd/Data_Cache_Manager_Flash_Advanced.cpp` | Treat `IFP_GEMV` the same as `READ` in `process_new_user_request()` and transaction completion handler |
| `src/ssd/Data_Cache_Manager_Flash_Simple.cpp` | Same treatment |

### Phase 6 Verification

1. **Build**: `make clean && make` -- must compile with zero errors
2. **Cache handling check**: Grep for `IFP_GEMV` in `Data_Cache_Manager_Flash_Advanced.cpp` and `Data_Cache_Manager_Flash_Simple.cpp` -- confirm it is handled alongside `READ`
3. **End-to-end GEMV flow test**: Run GEMV trace with IFP enabled config -- confirm transactions pass through cache manager without assertion/crash
4. **Regression**: Run existing READ/WRITE workload -- confirm no behavioral change

---

## Phase 7: ECC Failure Model, Read-Reclaim, Aggregation

**Depends on:** Phases 1, 5, 6

### Step 7.1: Implement probabilistic ECC engine

| File | Change |
|------|--------|
| `src/ssd/ECC_Engine.h` | **New file.** `Attempt_correction(read_count, erase_count)` using RBER model: `RBER = base + read_factor * read_count + erase_factor * erase_count`. Returns success/failure. `Get_ECC_latency()` returns total latency including retries. |
| `src/ssd/ECC_Engine.cpp` | **New file.** Implementation. |

### Step 7.2: Integrate ECC into PHY ready-signal handler

| File | Change |
|------|--------|
| `src/ssd/NVM_PHY_ONFI_NVDDR2.cpp` | In `handle_ready_signal_from_chip()`, after read/IFP command finishes: query block read_count/erase_count via block manager, call `ECC_Engine::Get_ECC_latency()`, add retry latency to finish time. If uncorrectable, flag transaction for read-reclaim. Update `Stats::Total_ECC_retries`, `Total_ECC_failures`. |

### Step 7.3: Implement read-reclaim mechanism

| File | Change |
|------|--------|
| `src/ssd/GC_and_WL_Unit_Base.h` | Add `virtual void Check_read_reclaim_required(Physical_Page_Address&)` |
| `src/ssd/GC_and_WL_Unit_Page_Level.h` | Override `Check_read_reclaim_required()` |
| `src/ssd/GC_and_WL_Unit_Page_Level.cpp` | Implementation: if `block.Read_count >= Read_Reclaim_Threshold`, copy valid pages to free block and erase (reuse GC page-movement logic). Called from `handle_transaction_serviced_signal_from_PHY()` after read/IFP transactions. |

### Step 7.4: Implement aggregation unit

| File | Change |
|------|--------|
| `src/ssd/IFP_Aggregation_Unit.h` | **New file.** Tracks partial results per user request. `Aggregate_partial_result()` returns true when all transactions complete. |
| `src/ssd/IFP_Aggregation_Unit.cpp` | **New file.** Controller-level: models DRAM dot-product via `estimate_dram_access_time()`. Chip-level: sums partial scalars (negligible latency). |

### Step 7.5: Wire new components into FTL

| File | Change |
|------|--------|
| `src/ssd/FTL.h` | Add `ECC_Engine*`, `IFP_Aggregation_Unit*` pointers |
| `src/ssd/FTL.cpp` | Instantiate in constructor |

### Phase 7 Verification

1. **Build**: `make clean && make` -- must compile with zero errors
2. **ECC engine check**: Grep for `ECC_Engine` -- confirm new files `ECC_Engine.h/.cpp` exist and `Attempt_correction()` uses the RBER model formula
3. **ECC integration check**: Grep for `ECC_Engine` in `NVM_PHY_ONFI_NVDDR2.cpp` -- confirm it is called in `handle_ready_signal_from_chip()`
4. **Read-reclaim check**: Grep for `Check_read_reclaim_required` in `GC_and_WL_Unit_Page_Level.cpp` -- confirm threshold-based trigger logic
5. **Aggregation check**: Grep for `IFP_Aggregation_Unit` -- confirm new files exist and `Aggregate_partial_result()` handles both controller-level and chip-level modes
6. **FTL wiring check**: Read `FTL.h`/`FTL.cpp` -- confirm `ECC_Engine*` and `IFP_Aggregation_Unit*` are declared and instantiated
7. **ECC stress test**: Run GEMV trace with aggressive ECC params (`ECC_Base_RBER=0.01`, low `ECC_Correction_Capability`) -- confirm `Stats::Total_ECC_retries > 0` and `Total_ECC_failures > 0` in output
8. **Read-reclaim test**: Run GEMV trace with low `Read_Reclaim_Threshold` (e.g., 100) -- confirm `Stats::Total_read_reclaim_migrations > 0` in output
9. **Aggregation mode test**: Run same GEMV trace twice with `IFP_Aggregation_Mode=0` (controller) and `=1` (chip) -- compare data transfer volumes and confirm chip-level transfers significantly less data
10. **Full regression**: Run existing READ/WRITE workload with IFP disabled (`IFP_Enabled=false`) -- confirm identical behavior to pre-modification baseline

---

## New Files Summary

| File | Purpose |
|------|---------|
| `src/ssd/NVM_Transaction_Flash_IFP.h/.cpp` | IFP transaction subclass with partial result, ECC state |
| `src/ssd/ECC_Engine.h/.cpp` | Probabilistic ECC failure model with retry logic |
| `src/ssd/IFP_Aggregation_Unit.h/.cpp` | Controller-level / chip-level result aggregation |

## Final Integration Verification (after all phases)

1. **Clean build**: `make clean && make` -- zero errors, zero warnings
2. **Full GEMV end-to-end**: Run GEMV trace through entire pipeline (trace -> host -> FTL -> TSU -> PHY -> Flash_Chip -> aggregation -> completion) and confirm simulator completes without crash/assertion
3. **Statistics validation**: Confirm all IFP stats are non-zero in output XML: `IssuedIFPGemvCMD`, `Total_ECC_retries`, `Total_read_reclaim_migrations`
4. **Aggregation modes**: Run with `IFP_Aggregation_Mode=0` (controller) and `=1` (chip) -- compare data transfer volumes
5. **Full regression**: Run original READ/WRITE workloads with `IFP_Enabled=false` -- confirm identical results to pre-modification baseline
