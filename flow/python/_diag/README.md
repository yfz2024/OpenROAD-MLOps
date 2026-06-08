# Diagnostics

Sandbox scripts kept for re-running if a future stage hits the same
SIGSEGV-on-Tech-construction class of bugs we hit while bringing up
`cts.py`. **Not part of the flow.**

| Script | What it proves | When to re-run |
|---|---|---|
| `_smoke.py` | `Tech()` + `Design(tech)` + a single `evalTclString('puts ...')` work in the current build | If you suspect the Python binding is fundamentally broken |
| `_smoke2.py` | The first 8 commands of a stage (set_metrics_stage, sourcing util.tcl/load.tcl/lec_check.tcl/report_metrics.tcl, `load_design`) execute | If `load_design` starts failing after a platform/design change |
| `_smoke3.py` | The full cts.py command sequence (23 evalTclString steps including `clock_tree_synthesis`, `repair_timing_helper`, `detailed_placement`) works **when Tech/Design is constructed at module top level** | If a new stage segfaults and you want to bisect which command crashed |

## Invocation

Same as a real stage — go through `make run`:

```
cd flow
make DESIGN_CONFIG=./designs/asap7/gcd/config.mk \
     RUN_SCRIPT=$PWD/python/_diag/_smoke3.py \
     RUN_LOG_NAME_STEM=_smoke3 \
     run
```

Needs `results/asap7/gcd/base/3_place.odb` to already exist.
