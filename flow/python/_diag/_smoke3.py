"""Continue past _smoke2 to find which command in cts.py's full sequence crashes.

Steps 1-8 are identical to _smoke2 (proven to pass). Steps 9+ walk the rest
of cts.py's command sequence one at a time with flushed prints, so the
last BEFORE without an AFTER pinpoints the segfault.

Usage:
    cd flow
    make DESIGN_CONFIG=./designs/asap7/gcd/config.mk \\
         RUN_SCRIPT=$PWD/python/stages/_smoke3.py \\
         RUN_LOG_NAME_STEM=_smoke3 \\
         run
"""
import os
import sys

from openroad import Design, Tech

sys.stdout.reconfigure(line_buffering=True)


def step(label, cmd, design):
    print(f"[step] BEFORE: {label}: {cmd!r}", flush=True)
    result = design.evalTclString(cmd)
    print(f"[step] AFTER : {label}: result={result!r}", flush=True)


tech = Tech()
design = Design(tech)
SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]
RESULTS_DIR = os.environ["RESULTS_DIR"]
PAD = os.environ["CELL_PAD_IN_SITES_DETAIL_PLACEMENT"]

# === Steps 1-8: same as _smoke2 (already proven to pass) ===
step("01 simple puts", "puts hello-from-tcl", design)
step("02 set_metrics_stage", 'utl::set_metrics_stage "cts__{}"', design)
step("03 source util.tcl", f"source {SCRIPTS_DIR}/util.tcl", design)
step("04 source load.tcl", f"source {SCRIPTS_DIR}/load.tcl", design)
step("05 source lec_check.tcl", f"source {SCRIPTS_DIR}/lec_check.tcl", design)
step("06 source report_metrics.tcl", f"source {SCRIPTS_DIR}/report_metrics.tcl", design)
step("07 erase_non_stage_variables", "erase_non_stage_variables cts", design)
step("08 load_design 3_place", "load_design 3_place.odb 3_place.sdc", design)

# === Steps 9+: rest of cts.py ===
step("09 source_step_tcl PRE CTS", "source_step_tcl PRE CTS", design)
step("10 repair_clock_inverters", "repair_clock_inverters", design)
step("11 set_dont_use", "set_dont_use $::env(DONT_USE_CELLS)", design)
step(
    "12 clock_tree_synthesis",
    "clock_tree_synthesis -sink_clustering_enable -repair_clock_nets",
    design,
)
step(
    "13 push_metrics_stage",
    'utl::push_metrics_stage "cts__{}__pre_repair_timing"',
    design,
)
step("14 estimate_parasitics", "estimate_parasitics -placement", design)
step("15 pop_metrics_stage", "utl::pop_metrics_stage", design)
step(
    "16 set_placement_padding",
    f"set_placement_padding -global -left {PAD} -right {PAD}",
    design,
)
step("17 detailed_placement", "detailed_placement", design)
step("18 estimate_parasitics #2", "estimate_parasitics -placement", design)
step("19 repair_timing_helper", "repair_timing_helper", design)
step("20 detailed_placement #2", "detailed_placement", design)
step("21 check_placement", "check_placement -verbose", design)
step("22 report_metrics", 'report_metrics 4 "cts final"', design)
step("23 source_step_tcl POST CTS", "source_step_tcl POST CTS", design)

print("[smoke3] all steps passed.", flush=True)
