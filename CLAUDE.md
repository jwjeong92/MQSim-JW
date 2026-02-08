# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MQSim-JW is a C++ discrete-event SSD simulator (based on the FAST 2018 MQSim paper) extended with power-law RBER modeling, ECC engine, read-reclaim, and IFP (In-Flash Processing) support. It models NVMe and SATA SSDs with realistic flash memory behavior.

## Build and Run

```bash
make              # Build (g++, C++11, -O3). Output: ./mqsim
make llm_trace_gen # Build LLM trace generator
make clean        # Clean build artifacts

# Run simulation
./mqsim -i <device_config.xml> -w <workload_config.xml> [-o <output_path>]

# Example
./mqsim -i configs/device/ssdconfig.xml -w configs/workload/trace_llm.xml
```

Output XML files are written to the workload file's directory by default. Note: the program waits for keypress after completion (`cin.get()` in main.cpp:335).

There is no automated test suite. Testing is done by running simulations with specific workload configs and checking output XML for expected statistics.

## Repository Structure

```
src/              Source code (DO NOT restructure)
configs/          All configuration files
  device/         SSD device configs (geometry, timing, ECC, GC thresholds)
  workload/       Workload definitions (synthetic + trace-based)
  fast18/         Historical FAST'18 experiment configs
traces/           I/O trace files
  llm/            LLM model traces (gitignored, regenerate with tools/)
  benchmarks/     Standard benchmark traces (tpcc, wsrch, gemv)
tools/            Scripts and utilities
  analysis/       Result parsing and analysis (Python)
  plotting/       Visualization scripts (Python)
  automation/     Batch execution scripts (Shell)
  examples/       Usage examples
results/          Raw experimental data
  exp1_baseline/  Baseline performance results
  exp2_accumulation/  Read-disturb accumulation results
  exp3_tradeoff/  Threshold trade-off results
figures/          Publication-quality figures
docs/             Consolidated documentation
  features/       Feature docs (ECC, read-reclaim)
  experiments/    Experiment summaries
  plans/          Project plans
  references/     Academic papers
archive/          Obsolete session logs and superseded docs
```

## Architecture

### Simulation Flow

```
Host_Interface → Data_Cache_Manager → FTL (Address Mapping + Block Manager + GC/WL) → TSU → NVM_PHY → Flash Chips
```

All components inherit from `Sim_Object` and interact through the discrete-event `Engine` (singleton). Events are managed in a red-black tree ordered by simulation time.

### Source Layout (`src/`)

- **`sim/`** - Simulation engine: `Engine` (singleton), `EventTree` (red-black tree), `Sim_Object` (base class), `Sim_Event`
- **`exec/`** - Configuration and orchestration: `SSD_Device` wires up all components, parameter sets deserialize from XML. Also contains `LLM_Trace_Generator.cpp` and `LLM_Workload_Generator.h` (standalone trace generator, built separately via `make llm_trace_gen`)
- **`host/`** - Host-side: `IO_Flow_Synthetic`, `IO_Flow_Trace_Based`, PCIe/SATA interfaces
- **`ssd/`** - SSD controller (largest module):
  - `FTL.cpp` - Flash Translation Layer coordinator
  - `Address_Mapping_Unit_Page_Level.cpp` - LHA→PPA translation (~111KB, the largest file)
  - `Flash_Block_Manager.cpp` - Block allocation, validity tracking, read counts
  - `GC_and_WL_Unit_Page_Level.cpp` - Garbage collection, wear leveling, **read-reclaim**
  - `TSU_OutofOrder.cpp` / `TSU_FLIN.cpp` - Transaction scheduling
  - `Data_Cache_Manager_Flash_Advanced.cpp` - DRAM cache management
  - `Host_Interface_NVMe.cpp` / `Host_Interface_SATA.cpp` - Device-side host interface
  - `ECC_Engine.cpp` - Power-law RBER model with soft-decode retries
  - `IFP_Aggregation_Unit.cpp` - In-Flash Processing aggregation
- **`nvm_chip/flash_memory/`** - Flash hierarchy: Chip → Die → Plane → Block → Page
- **`utils/`** - XML parsing (rapidxml), random generators, helper functions

### Key Extension Points

The codebase uses base class + derived class patterns for extensibility:
- `Address_Mapping_Unit_Base` → `Page_Level` (also supports Hybrid)
- `GC_and_WL_Unit_Base` → `Page_Level`
- `Host_Interface_Base` → `NVMe` / `SATA`
- `TSU_Base` → `OutofOrder` / `FLIN`
- `Data_Cache_Manager_Base` → `Flash_Simple` / `Flash_Advanced`

### RBER / ECC / Read-Reclaim (Recent Extensions)

The ECC engine uses a power-law RBER model: `RBER = ε + α(PE^k) + β(PE^m)(t^n) + γ(PE^p)(r^q)` where PE = program/erase cycles, t = retention time (hours), r = avg reads per page. ECC returns retry count (0 = first-pass success, -1 = uncorrectable).

Read-reclaim in `GC_and_WL_Unit_Page_Level` triggers block migration when `block.Read_count` exceeds a configurable threshold, preventing read-disturb errors. Block metadata tracks `Read_count`, `Erase_count`, and `First_write_time`.

### Configuration

- **Device config** (`configs/device/*.xml`): SSD geometry (channels, chips, dies, planes, blocks, pages), flash timing, cache size, GC thresholds, wear-leveling settings
- **Workload config** (`configs/workload/*.xml`): I/O scenarios with synthetic or trace-based flows. Trace format: `arrival_time device_num LBA size_sectors type(0=write,1=read)`

## Project Organization

- Store project knowledge in `docs/` - Reference with @docs/filename.md when needed
- Save the results of planning in `docs/plans/`
- Tools and scripts go in `tools/` organized by purpose
- Experiment results go in `results/` organized by experiment
