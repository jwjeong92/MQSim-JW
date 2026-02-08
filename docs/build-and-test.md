# Testing Guide: RBER Model & Read-Reclaim

## Quick Start

### 1. Verify Compilation
```bash
cd /home/jwjeong/git_repo/MQSim-JW
make clean
make -j4
```

Expected: No errors, produces `mqsim` executable

---

## Test 1: Read-Reclaim Basic Verification

### Objective
Verify read-reclaim triggers at configurable threshold.

### Configuration
Edit your device config XML (e.g., `configs/device/ssdconfig_ifp.xml`):

```xml
<Flash_Parameter_Set>
    <!-- Set LOW threshold for quick testing -->
    <Read_Reclaim_Threshold>1000</Read_Reclaim_Threshold>

    <!-- Other parameters... -->
    <Block_No_Per_Plane>128</Block_No_Per_Plane>  <!-- Small for testing -->
    <Page_No_Per_Block>256</Page_No_Per_Block>
    <!-- ... -->
</Flash_Parameter_Set>
```

### Workload
Create a repetitive read trace or use synthetic workload that:
- Reads same LBA range repeatedly
- Accumulates 1000+ reads on same blocks
- Example: 10,000 reads to 100MB address space

### Expected Console Output
```
[READ_RECLAIM_CHECK] Block [0,0,0,0,5] read_count=100 threshold=1000
[READ_RECLAIM_CHECK] Block [0,0,0,0,5] read_count=200 threshold=1000
[READ_RECLAIM_CHECK] Block [0,0,0,0,5] read_count=300 threshold=1000
...
[READ_RECLAIM_CHECK] Block [0,0,0,0,5] read_count=900 threshold=1000
*** [READ_RECLAIM_TRIGGERED] Block [0,0,0,0,5] reached threshold! read_count=1000 threshold=1000
*** [READ_RECLAIM_EXECUTING] Migrating 128 valid pages from block [5]
```

### Expected XML Output
Check `results/` directory for output XML:
```xml
<Total_Read_Reclaim_Migrations>5</Total_Read_Reclaim_Migrations>  <!-- Should be > 0 -->
```

### Success Criteria
- ✅ See `[READ_RECLAIM_CHECK]` messages every 100 reads
- ✅ See `[READ_RECLAIM_TRIGGERED]` when read_count reaches 1000
- ✅ See `[READ_RECLAIM_EXECUTING]` with valid page count
- ✅ `Total_Read_Reclaim_Migrations > 0` in XML output
- ✅ No crashes or errors

---

## Test 2: RBER Model Verification

### Objective
Verify power-law RBER model increases error rates as expected.

### Configuration
Use default threshold (100,000) or disable read-reclaim temporarily:
```xml
<Read_Reclaim_Threshold>999999</Read_Reclaim_Threshold>  <!-- Very high -->
```

### Workload
Run workload that:
1. **Increases PE cycles:** Trigger GC multiple times
2. **Increases retention time:** Let simulation time advance
3. **Increases read count:** Read same blocks repeatedly

### Monitoring
Watch for ECC statistics in console (if enabled) or XML output:
```xml
<Total_ECC_retries>1234</Total_ECC_retries>
<Total_ECC_uncorrectable>5</Total_ECC_uncorrectable>
```

### Expected Behavior
As simulation progresses:
- **Fresh blocks (low PE, no retention, few reads):** Low RBER, few retries
- **Aged blocks (high PE):** RBER increases due to wear-out term
- **Old data (high retention time):** RBER increases due to retention term
- **Hot blocks (many reads):** RBER increases due to read disturb term

### Verification
Compare two runs:
1. **Run A:** Fresh workload (low PE cycles)
2. **Run B:** Aged workload (high PE cycles, long retention, many reads)

Expected: Run B should have more ECC retries than Run A.

---

## Test 3: Read-Reclaim Prevents Read Disturb

### Objective
Verify read-reclaim prevents excessive read disturb errors.

### Test Setup
Run **two simulations** with same workload:

#### Simulation A: Read-Reclaim ENABLED
```xml
<Read_Reclaim_Threshold>10000</Read_Reclaim_Threshold>
```

#### Simulation B: Read-Reclaim DISABLED
```xml
<Read_Reclaim_Threshold>999999</Read_Reclaim_Threshold>
```

### Workload
Create workload with:
- High read frequency to same blocks
- Enough reads to exceed 10,000 per block
- Run for extended simulation time

### Expected Results
| Metric | Sim A (Enabled) | Sim B (Disabled) |
|--------|----------------|------------------|
| `Total_Read_Reclaim_Migrations` | > 0 | 0 |
| `Total_ECC_retries` | Lower | Higher |
| `Total_ECC_uncorrectable` | Lower | Higher |
| Max block read_count | ~10,000 | > 10,000 |

**Conclusion:** Read-reclaim keeps read counts low, preventing read disturb errors.

---

## Test 4: Retention Time Tracking

### Objective
Verify retention time increases correctly.

### Debug Instrumentation
Add temporary debug output in `NVM_PHY_ONFI_NVDDR2.cpp`:

```cpp
// After calculating retention_time_hours
if (block->Read_count % 1000 == 0 && retention_time_hours > 0) {
    std::cout << "[RETENTION_DEBUG] Block [" << tr->Address.BlockID
              << "] retention=" << retention_time_hours << " hours, "
              << "PE=" << block->Erase_count << ", "
              << "reads=" << block->Read_count << std::endl;
}
```

### Expected Output
```
[RETENTION_DEBUG] Block [5] retention=0.5 hours, PE=10, reads=1000
[RETENTION_DEBUG] Block [5] retention=1.2 hours, PE=10, reads=2000
[RETENTION_DEBUG] Block [5] retention=2.8 hours, PE=10, reads=3000
```

### Verification
- ✅ Retention time increases monotonically
- ✅ Retention time resets to 0 after block erase
- ✅ Different blocks have different retention times

---

## Test 5: Multi-Block Read-Reclaim

### Objective
Verify read-reclaim works on multiple blocks simultaneously.

### Configuration
```xml
<Read_Reclaim_Threshold>5000</Read_Reclaim_Threshold>
<Block_No_Per_Plane>512</Block_No_Per_Plane>
```

### Workload
Distribute reads across **multiple LBA ranges** to stress multiple blocks:
- Range 1: LBA 0-100MB
- Range 2: LBA 100-200MB
- Range 3: LBA 200-300MB

### Expected Output
```
*** [READ_RECLAIM_TRIGGERED] Block [0,0,0,0,5] reached threshold! read_count=5000
*** [READ_RECLAIM_EXECUTING] Migrating 200 valid pages from block [5]
*** [READ_RECLAIM_TRIGGERED] Block [0,0,0,0,12] reached threshold! read_count=5000
*** [READ_RECLAIM_EXECUTING] Migrating 180 valid pages from block [12]
*** [READ_RECLAIM_TRIGGERED] Block [0,0,0,1,7] reached threshold! read_count=5000
*** [READ_RECLAIM_EXECUTING] Migrating 256 valid pages from block [7]
```

### Success Criteria
- ✅ Multiple different blocks trigger read-reclaim
- ✅ `Total_Read_Reclaim_Migrations` matches number of triggers
- ✅ No concurrent read-reclaim conflicts (deadlocks)

---

## Test 6: Integration with LLM Workload

### Objective
Test with realistic workload.

### Configuration
```xml
<Read_Reclaim_Threshold>100000</Read_Reclaim_Threshold>  <!-- Default -->
```

### Workload
Use existing LLM trace:
```bash
./mqsim -i configs/workload/trace_llm_scenario_1.xml
```

### Monitoring
- Check if any blocks reach 100,000 reads during workload
- Observe ECC retry patterns
- Look for any read-reclaim triggers (may or may not happen depending on workload)

### Analysis
```bash
# Check XML output
grep "Total_Read_Reclaim_Migrations" results/*.xml
grep "Total_ECC_retries" results/*.xml
grep "Total_ECC_uncorrectable" results/*.xml
```

### Interpretation
- If `Total_Read_Reclaim_Migrations == 0`: Workload doesn't stress read disturb
- If `Total_Read_Reclaim_Migrations > 0`: Read-reclaim is actively working
- If `Total_ECC_uncorrectable > 0`: RBER model is predicting errors (expected with aging)

---

## Debugging Tips

### Issue: No Read-Reclaim Triggers
**Possible Causes:**
1. Threshold too high for workload duration
2. Workload doesn't repeatedly read same blocks
3. Read-reclaim check not being called

**Solutions:**
1. Lower threshold to 1000 for testing
2. Use repetitive read trace
3. Check console for `[READ_RECLAIM_CHECK]` messages

### Issue: Too Many ECC Failures
**Possible Causes:**
1. RBER model parameters too aggressive
2. Workload has extremely high PE cycles
3. Correction capability too low

**Solutions:**
1. Verify RBER parameters match model
2. Check PE cycle distribution in workload
3. Increase ECC correction capability in config

### Issue: Compilation Errors
**Check:**
1. All modified files saved correctly
2. Constructor parameter order matches
3. Include statements for `<iostream>`, `<cmath>`

**Clean build:**
```bash
make clean
make -j4
```

### Issue: No Console Output
**Possible Causes:**
1. Output buffering
2. Threshold not reached

**Solutions:**
1. Flush stdout: `std::cout << ... << std::flush;`
2. Check simulation actually runs long enough
3. Verify threshold setting in parsed config

---

## Performance Testing

### Measure Overhead
Compare simulation time before/after changes:

```bash
# Baseline (old code)
time ./mqsim -i config.xml

# New code
time ./mqsim -i config.xml
```

**Expected:** <5% slowdown due to:
- pow() calculations in RBER model
- Additional read-reclaim checks

### Memory Profiling
Check memory usage:
```bash
/usr/bin/time -v ./mqsim -i config.xml
```

Look for "Maximum resident set size" - should be negligible increase.

---

## Test Matrix

| Test | Threshold | Workload | Duration | Expected Result |
|------|-----------|----------|----------|-----------------|
| 1 | 1,000 | Repetitive reads | Short | Reclaim triggers |
| 2 | 999,999 | Aging workload | Long | High ECC retries |
| 3a | 10,000 | High read freq | Medium | Reclaim prevents errors |
| 3b | 999,999 | High read freq | Medium | ECC errors increase |
| 4 | 10,000 | Mixed R/W | Medium | Retention tracked |
| 5 | 5,000 | Multi-range | Medium | Multi-block reclaim |
| 6 | 100,000 | LLM trace | Full | Realistic behavior |

---

## Validation Checklist

Before declaring success, verify:

### Functionality
- [ ] Read-reclaim triggers at configured threshold
- [ ] Read-reclaim resets block read count after erase
- [ ] RBER increases with PE cycles
- [ ] RBER increases with retention time
- [ ] RBER increases with read count
- [ ] ECC retries correlate with RBER
- [ ] Statistics properly reported in XML

### Correctness
- [ ] C++ RBER values match Python model
- [ ] Retention time calculation correct (ns → hours)
- [ ] Average reads per page calculated correctly
- [ ] No integer overflow in calculations
- [ ] No division by zero errors

### Performance
- [ ] Simulation completes without crashes
- [ ] Overhead < 5% compared to baseline
- [ ] Memory usage within acceptable limits

### Integration
- [ ] Works with existing traces
- [ ] Compatible with GC/WL operations
- [ ] No conflicts with IFP operations
- [ ] XML configuration properly parsed

---

## Troubleshooting Common Issues

### Assertion Failure: "Inconsistent status in plane bookkeeping"
**Cause:** Page counts don't match during read-reclaim
**Fix:** Verify block is safe GC candidate before initiating reclaim

### Segmentation Fault
**Likely locations:**
1. Block pointer null check
2. Array index out of bounds
3. Uninitialized First_write_time

**Debug:**
```bash
gdb ./mqsim
run -i config.xml
backtrace
```

### RBER Values Seem Wrong
**Verify:**
1. Retention time units (should be hours)
2. Average reads per page calculation
3. Parameter values match Python model
4. No premature integer truncation

**Test:**
Add debug output in `Calculate_RBER()`:
```cpp
std::cout << "RBER: PE=" << pe_cycles
          << " ret=" << retention_time_hours
          << " reads=" << avg_reads_per_page
          << " => " << rber << std::endl;
```

---

## Success Criteria Summary

✅ **Core Functionality**
- Read-reclaim triggers at threshold
- RBER model produces realistic values
- Statistics tracked correctly

✅ **Integration**
- Works with existing workloads
- Compatible with all simulator features
- No performance degradation

✅ **Verification**
- Console output shows expected behavior
- XML output has correct statistics
- Debug instrumentation confirms operation

✅ **Quality**
- No crashes or errors
- Code compiles cleanly
- Results match expectations

---

## Next Steps After Testing

1. **Tune threshold:** Based on workload characteristics
2. **Disable debug output:** Comment out std::cout in production
3. **Document findings:** Record test results and observations
4. **Optimize if needed:** Profile hot paths, consider caching RBER calculations
5. **Extend testing:** Try different NAND types, workloads, configurations

---

## Support

If you encounter issues:
1. Check CHANGELOG.md for implementation details
2. Review docs/plans/read-reclaim-verification.md for design rationale
3. Examine tools/examples/rber_model_example.py for model reference
4. Add more debug output to trace execution

---

**Happy Testing! 🚀**
