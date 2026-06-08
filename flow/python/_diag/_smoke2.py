"""Step-by-step smoke that mirrors cts.py's TCL call prefix.

Runs each evalTclString in turn, printing before/after so we know
exactly which one crashes. Stop at the first one that doesn't return.

Usage:
    cd flow
    make DESIGN_CONFIG=./designs/asap7/gcd/config.mk \\
         RUN_SCRIPT=$PWD/python/stages/_smoke2.py \\
         RUN_LOG_NAME_STEM=_smoke2 \\
         run
"""
import os
import sys

from openroad import Design, Tech

# Force unbuffered stdout so prints land before a possible segfault.
sys.stdout.reconfigure(line_buffering=True)


def step(label, cmd, design):
    print(f"[step] BEFORE: {label}: {cmd!r}", flush=True)
    result = design.evalTclString(cmd)
    print(f"[step] AFTER : {label}: result={result!r}", flush=True)


print("[smoke2] Tech() ...", flush=True)
tech = Tech()
print("[smoke2] Design(tech) ...", flush=True)
design = Design(tech)

scripts_dir = os.environ["SCRIPTS_DIR"]

step("01 simple puts", "puts hello-from-tcl", design)
step("02 set_metrics_stage", 'utl::set_metrics_stage "cts__{}"', design)
step("03 source util.tcl", f"source {scripts_dir}/util.tcl", design)
step("04 source load.tcl", f"source {scripts_dir}/load.tcl", design)
step("05 source lec_check.tcl", f"source {scripts_dir}/lec_check.tcl", design)
step("06 source report_metrics.tcl", f"source {scripts_dir}/report_metrics.tcl", design)
step("07 erase_non_stage_variables", "erase_non_stage_variables cts", design)
step("08 load_design 3_place", "load_design 3_place.odb 3_place.sdc", design)

print("[smoke2] all steps passed.", flush=True)
