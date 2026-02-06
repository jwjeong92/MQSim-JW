# IFP for LLM Inference - Complete Implementation Log

**Date:** 2026-02-06
**Plan reference:** `project-plans/hazy-swinging-puffin.md`

---

## Phase 1: Foundation - Types, Opcodes, Configuration

**Goal:** Extend enums, data structures, configuration parameters, and statistics to support `IFP_GEMV` throughout the simulator.

### Step 1.1: IFP enums added to request and transaction types

| File | Change |
|------|--------|
| `src/ssd/User_Request.h` | Added `IFP_GEMV` to `UserRequestType` enum (alongside `READ`, `WRITE`). |
| `src/ssd/NVM_Transaction.h` | Added `IFP_GEMV` to `Transaction_Type` enum (alongside `READ`, `WRITE`, `ERASE`). |
| `src/host/Host_IO_Request.h` | Added `IFP_GEMV` to `Host_IO_Request_Type` enum. |

### Step 1.2: NVMe vendor-specific GEMV opcode

| File | Change |
|------|--------|
| `src/ssd/Host_Interface_Defs.h` | Added `#define NVME_IFP_GEMV_OPCODE 0x00C0`. |

### Step 1.3: Flash command codes for IFP

| File | Change |
|------|--------|
| `src/nvm_chip/flash_memory/Flash_Command.h` | Added `CMD_IFP_READ_DOT_PRODUCT 0xA000` (single-plane) and `CMD_IFP_READ_DOT_PRODUCT_MULTIPLANE 0xA001`. |

### Step 1.4: IFP/ECC/read-reclaim configuration parameters

| File | Change |
|------|--------|
| `src/exec/Flash_Parameter_Set.h` | Added 13 static members: `IFP_Enabled`, `IFP_Dot_Product_Latency`, `IFP_ECC_Decode_Latency`, `IFP_ECC_Retry_Latency`, `IFP_ECC_Max_Retries`, `Read_Reclaim_Threshold`, `ECC_Base_RBER`, `ECC_Read_Count_Factor`, `ECC_PE_Cycle_Factor`, `ECC_Retention_Factor`, `ECC_Correction_Capability`, `ECC_Codeword_Size`, `IFP_Aggregation_Mode`. |
| `src/exec/Flash_Parameter_Set.cpp` | Added ~93 lines: default initializations, XML serialization, XML deserialization for all 13 parameters. Defaults: dot-product latency = 5 us, ECC decode = 10 us, ECC retry = 50 us, max retries = 3, base RBER = 1e-9, correction capability = 40 bits per 1 KiB codeword. |

### Step 1.5: Per-block read count tracking

| File | Change |
|------|--------|
| `src/ssd/Flash_Block_Manager_Base.h` | Added `unsigned int Read_count` to `Block_Pool_Slot_Type`. |
| `src/ssd/Flash_Block_Manager_Base.cpp` | Initialize `Read_count = 0` in constructor, reset to 0 on `Erase()`, increment in `Read_transaction_issued()`. |

### Step 1.6: IFP statistics counters

| File | Change |
|------|--------|
| `src/ssd/Stats.h` | Added 5 counters: `IssuedIFPGemvCMD`, `Total_read_reclaim_migrations`, `Total_ECC_failures`, `Total_ECC_retries`, `Total_ECC_uncorrectable`. |
| `src/ssd/Stats.cpp` | Static zero-initialization + reset in `Init_stats()`. |

### Phase 1 Configuration File

| File | Description |
|------|-------------|
| `devconf/ssdconfig_ifp.xml` | New SSD config with all IFP/ECC parameters (TLC, 8 channels, 2 chips/channel, 686 blocks/plane, 1536 pages/block). |

### Phase 1 Verification
- Build: zero errors
- All grep checks passed (`IFP_GEMV`, `NVME_IFP_GEMV_OPCODE`, `CMD_IFP_READ_DOT_PRODUCT`, `IFP_Enabled`, `Read_count`, `IssuedIFPGemvCMD`)
- Regression: 494,080 requests, response time 2,361,880 us, delay 6,653,431 us (baseline established)

---

## Phase 2: IFP Transaction Subclass

**Goal:** Create a flash transaction subclass for IFP GEMV operations.

### Step 2.1: NVM_Transaction_Flash_IFP (new files)

| File | Description |
|------|-------------|
| `src/ssd/NVM_Transaction_Flash_IFP.h` | Subclass of `NVM_Transaction_Flash`. Three constructor overloads (basic, with physical address, with priority class). IFP-specific fields: `Content`, `read_sectors_bitmap`, `DataTimeStamp`, `Partial_dot_product_result` (double), `ECC_retry_needed` (bool), `ECC_retry_count` (uint), `Aggregation_complete` (bool). |
| `src/ssd/NVM_Transaction_Flash_IFP.cpp` | Constructor implementations. Each calls parent with `Transaction_Type::IFP_GEMV`, initializes `Partial_dot_product_result = 0.0`, `ECC_retry_needed = false`, `ECC_retry_count = 0`, `Aggregation_complete = false`. |

### Phase 2 Verification
- Build: zero errors
- Class inherits from `NVM_Transaction_Flash` with all required fields
- Regression: identical to baseline

---

## Phase 3: Host Interface - GEMV Request Path

**Goal:** Enable trace parsing and NVMe interface to recognize, parse, and route IFP GEMV requests.

### Step 3.1: Trace format extension

| File | Change |
|------|--------|
| `src/host/ASCII_Trace_Definition.h` | Added `ASCIITraceGemvCode "2"` and `ASCIITraceGemvCodeInteger 2`. Trace format: code 0 = WRITE, 1 = READ, 2 = GEMV. |

### Step 3.2: Trace parser extension

| File | Change |
|------|--------|
| `src/host/IO_Flow_Trace_Based.cpp` | Added `else if` branch in `Generate_next_request()`: detects type "2" in trace, sets `request->Type = Host_IO_Request_Type::IFP_GEMV`. GEMV increments the read request counter. |

### Step 3.3: IO_Flow_Base SQE generation

| File | Change |
|------|--------|
| `src/host/IO_Flow_Base.cpp` | Two changes: (1) IFP_GEMV treated like reads for response-time/throughput accounting. (2) New `else if` block builds NVMe SQE with `NVME_IFP_GEMV_OPCODE`, setting LBA, LBA count, PRP entries (mirrors read SQE format). |

### Step 3.4-3.5: NVMe host interface decoding and segmentation

| File | Change |
|------|--------|
| `src/ssd/Host_Interface_NVMe.cpp` | Four changes: (1) `#include "NVM_Transaction_Flash_IFP.h"`. (2) `Handle_new_arrived_request()`: IFP_GEMV routed to read waiting queue. (3) `Handle_serviced_request()`: IFP_GEMV completions trigger `Send_read_data()`. (4) `segment_user_request()`: new branch creates `NVM_Transaction_Flash_IFP` objects. (5) `Process_pcie_read_message()`: `case NVME_IFP_GEMV_OPCODE` decodes SQE into `UserRequestType::IFP_GEMV`. |

### Phase 3 Verification
- Build: zero errors
- Trace format check: `ASCIITraceGemvCode` confirmed
- Regression: identical to baseline

---

## Phase 4: Flash Chip Layer - IFP Latency Modeling

**Goal:** Enable the flash chip to execute IFP dot-product commands with proper latency modeling.

### Step 4.1: IFP latency in Flash_Chip

| File | Change |
|------|--------|
| `src/nvm_chip/flash_memory/Flash_Chip.h` | Added `_ifpDotProductLatency` and `_ifpEccDecodeLatency` members. Extended constructor with IFP params (default = 0). Added `Get_command_execution_latency()` case returning `readLatency + eccDecodeLatency + dotProductLatency + RBSignalDelay` for `CMD_IFP_READ_DOT_PRODUCT*`. |
| `src/nvm_chip/flash_memory/Flash_Chip.cpp` | Constructor accepts/initializes IFP latencies. `Execute_simulator_event()`: added `case CMD_IFP_READ_DOT_PRODUCT*` that increments `STAT_readCount`, increments `Plane->Read_count`, reads page metadata (mirrors regular read completion). |

### Step 4.2: Config wiring

| File | Change |
|------|--------|
| `src/exec/SSD_Device.cpp` | Passes `IFP_Dot_Product_Latency` and `IFP_ECC_Decode_Latency` from `Flash_Parameter_Set` to `Flash_Chip` constructor. |

### Phase 4 Verification
- Build: zero errors
- Latency formula: `readLatency + eccDecodeLatency + dotProductLatency + RBSignalDelay` confirmed
- Regression: identical to baseline

---

## Phase 5: FTL Layer - Address Mapping, Scheduling, PHY

**Goal:** Enable address mapping, transaction scheduling, and PHY layer to handle IFP GEMV transactions end-to-end.

### Step 5.1: Address mapping extension

| File | Change |
|------|--------|
| `src/ssd/Address_Mapping_Unit_Page_Level.cpp` | Added `#include "NVM_Transaction_Flash_IFP.h"`. Extended CMT hit/miss tracking for IFP_GEMV. Physical address translation follows read path (PPA lookup, `online_create_entry_for_reads()` on miss, casts to `NVM_Transaction_Flash_IFP*` for `read_sectors_bitmap`). |

### Step 5.2: TSU IFP transaction queues

| File | Change |
|------|--------|
| `src/ssd/TSU_OutofOrder.h` | Added `Flash_Transaction_Queue **UserIFPTRQueue` and `service_ifp_transaction()` declaration. |
| `src/ssd/TSU_OutofOrder.cpp` | ~65 lines added. Allocates/deallocates IFP queues per channel/chip. Routes `IFP_GEMV` to `UserIFPTRQueue`. Full `service_ifp_transaction()` implementation with chip status checking and suspension logic. XML stats reporting for IFP queues. |

### Step 5.3: IFP scheduling priority

| File | Change |
|------|--------|
| `src/ssd/TSU_Base.h` | Added pure virtual `service_ifp_transaction()`. Updated `process_chip_requests()` priority chain: **read > IFP > write > erase**. Added `IFP_GEMV` case in `is_dominated_by_one_stream()` returning `true`. |
| `src/ssd/TSU_Priority_OutOfOrder.h` | Declared `service_ifp_transaction()`. |
| `src/ssd/TSU_Priority_OutOfOrder.cpp` | ~30 lines added. Routes `IFP_GEMV` into read queue (`UserReadTRQueue`) by priority class (defaults to HIGH). Stub `service_ifp_transaction()` returns false (IFP serviced via read queues). |

### Step 5.4: PHY layer IFP command execution

| File | Change |
|------|--------|
| `src/ssd/NVM_PHY_ONFI_NVDDR2.h` | Added `IFP_CMD_ADDR_TRANSFERRED` to `NVDDR2_SimEventType` enum. Added `ECC_Engine*`, `Flash_Block_Manager_Base*`, `GC_and_WL_Unit_Base*` member pointers with forward declarations. |
| `src/ssd/NVM_PHY_ONFI_NVDDR2.cpp` | ~100 lines added across 6 locations: (1) Includes and NULL initialization. (2) `Send_command_to_chip()`: IFP_GEMV case sets `CMD_IFP_READ_DOT_PRODUCT` or multiplane variant, calculates transfer timing, registers `IFP_CMD_ADDR_TRANSFERRED` events, increments `Stats::IssuedIFPGemvCMD`. (3) `Execute_simulator_event()`: handles `IFP_CMD_ADDR_TRANSFERRED` -- calls `EndCMDXfer`, sets execution time, transitions chip to `READING`. (4) `handle_ready_signal()`: ECC checking via `ecc_engine->Attempt_correction()`, adds ECC latency, updates stats, triggers read-reclaim on uncorrectable errors. (5) `perform_interleaved_cmd_data_transfer()`: IFP die-interleave handling. (6) `send_resume_command_to_chip()`: sets `READING` status for IFP commands after resume. |

### Phase 5 Verification
- Build: zero errors
- Address mapping, TSU queue, priority chain, PHY execution all confirmed via grep
- Regression: identical to baseline

---

## Phase 6: Data Cache Manager - GEMV Handling

**Goal:** IFP_GEMV bypasses DRAM cache, dispatches directly to FTL.

### Step 6.1: Cache manager bypass

| File | Change |
|------|--------|
| `src/ssd/Data_Cache_Manager_Flash_Advanced.cpp` | Added `IFP_GEMV` bypass in `process_new_user_request()` (~line 240): dispatches directly to FTL without cache interaction. Added `IFP_GEMV` completion handler in `handle_transaction_serviced_signal_from_PHY()` (~line 446): removes from list, signals completion. |
| `src/ssd/Data_Cache_Manager_Flash_Simple.cpp` | Same two changes (~lines 105 and 246). |

### Phase 6 Verification
- Build: zero errors
- Grep check: `IFP_GEMV` found at correct locations in both files
- Regression: 494,080 requests, response time 2,361,880 us, delay 6,653,431 us (identical to baseline)

---

## Phase 7: ECC, Read-Reclaim, and Aggregation

**Goal:** Implement probabilistic ECC engine, threshold-based read-reclaim, and controller/chip-level partial result aggregation.

### Step 7.1: ECC Engine (new files)

| File | Description |
|------|-------------|
| `src/ssd/ECC_Engine.h` | ECC engine class. RBER model: `base + read_factor * read_count + erase_factor * erase_count`. `Attempt_correction()` returns retry count (0=first pass, -1=uncorrectable). `Get_ECC_latency()` returns `decode_latency * (1 + retry_count)`. Parameters: base_rber, read_factor, erase_factor, page_size_in_bits, correction_capability, decode_latency, max_retries. |
| `src/ssd/ECC_Engine.cpp` | Implementation. First-pass hard decode checks `expected_errors <= correction_capability`. Soft-decode retries increase effective capability by 50% per retry. Uncorrectable returns `decode_latency * (1 + max_retries)`. |

### Step 7.2: ECC Integration into PHY

| File | Change |
|------|--------|
| `src/ssd/NVM_PHY_ONFI_NVDDR2.h` | Added `ECC_Engine*`, `Flash_Block_Manager_Base*`, `GC_and_WL_Unit_Base*` member pointers (with forward declarations and `#include "ECC_Engine.h"`). |
| `src/ssd/NVM_PHY_ONFI_NVDDR2.cpp` | Added ECC checking block in `handle_ready_signal_from_chip()` after `WAIT_FOR_DATA_OUT` and before transaction queuing. For each READ/IFP_GEMV transaction: queries block `Read_count`/`Erase_count` via block manager, calls `Attempt_correction`, adds ECC latency to `STAT_execution_time`, updates `Stats::Total_ECC_retries`/`Total_ECC_uncorrectable`/`Total_ECC_failures`, triggers `Check_read_reclaim_required()` on uncorrectable errors. For IFP transactions, populates `ECC_retry_count` and `ECC_retry_needed` fields. |

### Step 7.3: Read-Reclaim Mechanism

| File | Change |
|------|--------|
| `src/ssd/GC_and_WL_Unit_Base.h` | Added pure virtual `Check_read_reclaim_required(const Physical_Page_Address&, unsigned int read_count)`. |
| `src/ssd/GC_and_WL_Unit_Page_Level.h` | Added override declaration. |
| `src/ssd/GC_and_WL_Unit_Page_Level.cpp` | Implemented threshold-based read-reclaim (`READ_RECLAIM_THRESHOLD = 100000`). Checks for ongoing GC/WL, then initiates GC-style page movement (read valid pages, write to new block, erase old block). Increments `Stats::Total_read_reclaim_migrations`. |

### Step 7.4: IFP Aggregation Unit (new files)

| File | Description |
|------|-------------|
| `src/ssd/IFP_Aggregation_Unit.h` | `IFP_Aggregation_Mode` enum: `CONTROLLER_LEVEL` (DRAM accumulation), `CHIP_LEVEL` (on-chip). `Aggregate_partial_result()` tracks per-user-request state. `Get_aggregation_latency()` returns mode-dependent latency. Internal `AggregationState` struct: `accumulated_result`, `completed_count`, `total_count`. |
| `src/ssd/IFP_Aggregation_Unit.cpp` | Tracks state via `std::map<User_Request*, AggregationState>`. Controller-level: each partial result transferred to DRAM (accumulates, returns DRAM access latency). Chip-level: negligible extra latency. Cleans up state on completion. |

### Step 7.5: FTL Wiring

| File | Change |
|------|--------|
| `src/ssd/FTL.h` | Added `#include "ECC_Engine.h"`, `#include "IFP_Aggregation_Unit.h"`. Added public members: `ECC_Engine* ECC`, `IFP_Aggregation_Unit* Aggregation_Unit`. |
| `src/ssd/FTL.cpp` | Constructor: instantiates ECC engine (`base_rber=1e-9, read_factor=1e-10, erase_factor=1e-8, page_size_bits, capability=40, decode_latency=5000, max_retries=3`) and Aggregation_Unit (`CONTROLLER_LEVEL`, `100ns DRAM access`). Destructor: `delete ECC; delete Aggregation_Unit;`. |
| `src/exec/SSD_Device.cpp` | After GC setup, wires into PHY: `ecc_engine = ftl->ECC`, `block_manager_ref = fbm`, `gc_wl_unit_ref = gcwl`. |

### Phase 7 Verification
- Build: zero errors
- All grep checks passed for new symbols
- Regression: 494,080 requests, identical timing to baseline

---

## Final Integration Verification

### Bug Fix

| File | Issue | Fix |
|------|-------|-----|
| `src/ssd/GC_and_WL_Unit_Base.cpp` (line 52) | `handle_transaction_serviced_signal_from_PHY()` switch on `transaction->Type` only handled READ and WRITE. IFP_GEMV hit `default:` causing runtime crash: `"Unexpected situation in the GC_and_WL_Unit_Base function!"` | Added `case Transaction_Type::IFP_GEMV:` as fall-through to READ case (both service a flash read operation). |

### Enhancement

| File | Change |
|------|--------|
| `src/ssd/FTL.cpp` (`Report_results_in_XML()`) | Added XML output for all 5 IFP statistics: `Issued_IFP_GEMV_CMD`, `Total_ECC_Retries`, `Total_ECC_Failures`, `Total_ECC_Uncorrectable`, `Total_Read_Reclaim_Migrations`. |

### Test Artifacts Created

| File | Description |
|------|-------------|
| `traces/gemv_test.trace` | 1000 trace entries: 334 GEMV (type 2), 333 READ (type 1), 333 WRITE (type 0). Format: `timestamp 0 lba 8 type_code` with 1000ns intervals. |
| `wkdconf/trace_gemv_test.xml` | Workload config pointing to `traces/gemv_test.trace`. |

### GEMV End-to-End Test Results
```
Trace:     traces/gemv_test.trace
Requests:  1000 generated, 1000 serviced
Response:  1,101 us
Delay:     1,101 us
```

**IFP Statistics (from `wkdconf/trace_gemv_test_scenario_1.xml`):**

| Statistic | Value | Notes |
|-----------|-------|-------|
| `Issued_IFP_GEMV_CMD` | **120** | 334 GEMV requests batched into 120 multiplane commands |
| `Total_ECC_Retries` | 0 | Expected: fresh blocks, extremely low RBER with default params |
| `Total_ECC_Failures` | 0 | Expected |
| `Total_ECC_Uncorrectable` | 0 | Expected |
| `Total_Read_Reclaim_Migrations` | 0 | Expected: read counts far below 100,000 threshold |

### Regression Test Results (READ/WRITE Only)
```
Trace:     traces/llama_7b_gen_10_tok.trace
Requests:  494,080 generated, 494,080 serviced
Response:  2,361,880 us
Delay:     6,653,431 us
```

**IFP Statistics:** All zero (no GEMV in trace) - confirms no regression.

---

## Known Limitation

| File | Issue | Impact |
|------|-------|--------|
| `src/ssd/TSU_FLIN.cpp` (line 209) | FLIN scheduler's `Schedule()` silently drops IFP_GEMV transactions (`default: break`). | **None currently** - config uses `PRIORITY_OUT_OF_ORDER` which handles IFP_GEMV. Would need fixing if FLIN scheduler is used. |

---

## Complete File Inventory

### New Files (7)

| File | Phase | Lines |
|------|-------|-------|
| `src/ssd/NVM_Transaction_Flash_IFP.h` | 2 | 36 |
| `src/ssd/NVM_Transaction_Flash_IFP.cpp` | 2 | 36 |
| `src/ssd/ECC_Engine.h` | 7.1 | ~50 |
| `src/ssd/ECC_Engine.cpp` | 7.1 | ~60 |
| `src/ssd/IFP_Aggregation_Unit.h` | 7.4 | ~50 |
| `src/ssd/IFP_Aggregation_Unit.cpp` | 7.4 | ~60 |
| `devconf/ssdconfig_ifp.xml` | 1 | 83 |

### Modified Files (35)

| File | Phase(s) |
|------|----------|
| `src/exec/Flash_Parameter_Set.h` | 1 |
| `src/exec/Flash_Parameter_Set.cpp` | 1 |
| `src/exec/SSD_Device.cpp` | 4, 7.5 |
| `src/host/ASCII_Trace_Definition.h` | 3 |
| `src/host/Host_IO_Request.h` | 1 |
| `src/host/IO_Flow_Base.cpp` | 3 |
| `src/host/IO_Flow_Trace_Based.cpp` | 3 |
| `src/nvm_chip/flash_memory/Flash_Chip.h` | 4 |
| `src/nvm_chip/flash_memory/Flash_Chip.cpp` | 4 |
| `src/nvm_chip/flash_memory/Flash_Command.h` | 1 |
| `src/ssd/Address_Mapping_Unit_Page_Level.cpp` | 5 |
| `src/ssd/Data_Cache_Manager_Flash_Advanced.cpp` | 6 |
| `src/ssd/Data_Cache_Manager_Flash_Simple.cpp` | 6 |
| `src/ssd/FTL.h` | 7.5 |
| `src/ssd/FTL.cpp` | 7.5, Final |
| `src/ssd/Flash_Block_Manager_Base.h` | 1 |
| `src/ssd/Flash_Block_Manager_Base.cpp` | 1 |
| `src/ssd/GC_and_WL_Unit_Base.h` | 7.3 |
| `src/ssd/GC_and_WL_Unit_Base.cpp` | Final (bug fix) |
| `src/ssd/GC_and_WL_Unit_Page_Level.h` | 7.3 |
| `src/ssd/GC_and_WL_Unit_Page_Level.cpp` | 7.3 |
| `src/ssd/Host_Interface_Defs.h` | 1 |
| `src/ssd/Host_Interface_NVMe.cpp` | 3 |
| `src/ssd/NVM_PHY_ONFI_NVDDR2.h` | 5, 7.2 |
| `src/ssd/NVM_PHY_ONFI_NVDDR2.cpp` | 5, 7.2 |
| `src/ssd/NVM_Transaction.h` | 1 |
| `src/ssd/Stats.h` | 1 |
| `src/ssd/Stats.cpp` | 1 |
| `src/ssd/TSU_Base.h` | 5 |
| `src/ssd/TSU_OutofOrder.h` | 5 |
| `src/ssd/TSU_OutofOrder.cpp` | 5 |
| `src/ssd/TSU_Priority_OutOfOrder.h` | 5 |
| `src/ssd/TSU_Priority_OutOfOrder.cpp` | 5 |
| `src/ssd/User_Request.h` | 1 |
| `wkdconf/trace_llm.xml` | Config |

### Total: 572 lines added, 40 lines removed across 35 modified files + 7 new files
