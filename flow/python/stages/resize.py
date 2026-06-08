"""ORFS resize stage — Python port of flow/scripts/resize.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/resize.py

Reads `3_3_place_gp.odb` + `2_floorplan.sdc`, runs RC estimation,
repair_design_helper (and optional replace_arith_modules + incremental
global_placement), then reports timing/area metrics. Writes
`3_4_place_resized.odb`.
"""
# === Stage prelude ===========================================================
# See flow/python/README.md "Required stage prelude".
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orfs.stage import (  # noqa: E402
    enable_line_buffering,
    register_design,
    resolve_metrics_file,
)

enable_line_buffering()
_metrics_file = resolve_metrics_file()
if _metrics_file:
    print(f"[resize.py] metrics file: {_metrics_file}", flush=True)

from openroad import Design, Tech  # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import (  # noqa: E402
    env_var_exists_and_non_empty,
    log_cmd,
    orfs_write_db,
    set_metrics_stage,
    tcl,
)
# === End stage prelude =======================================================

RESULTS_DIR = os.environ["RESULTS_DIR"]
SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]


def main():
    set_metrics_stage("placeopt__{}")

    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")
    tcl(f"source {SCRIPTS_DIR}/report_metrics.tcl")

    tcl("erase_non_stage_variables place")
    tcl("load_design 3_3_place_gp.odb 2_floorplan.sdc")
    tcl("source_step_tcl PRE RESIZE")

    log_cmd("estimate_parasitics -placement")

    # Capture leaf counts before resize (sta::* returns ints as strings).
    instance_count_before = tcl("sta::network_leaf_instance_count")
    pin_count_before = tcl("sta::network_leaf_pin_count")

    tcl("set_dont_use $::env(DONT_USE_CELLS)")

    if env_var_exists_and_non_empty("EARLY_SIZING_CAP_RATIO"):
        log_cmd(
            "set_opt_config -set_early_sizing_cap_ratio "
            f"{os.environ['EARLY_SIZING_CAP_RATIO']}"
        )

    if env_var_exists_and_non_empty("SWAP_ARITH_OPERATORS"):
        # sanity checker on, then swap operators, then incremental GP
        tcl("set_debug_level ODB replace_design_check_sanity 1")
        tcl("replace_arith_modules")
        tcl("global_placement -incremental")

    tcl("repair_design_helper")

    # Hold violations are not repaired until after CTS

    print("Floating nets: ", flush=True)
    tcl("report_floating_nets")

    tcl('report_metrics 3 "resizer" true false')

    instance_count_after = tcl("sta::network_leaf_instance_count")
    pin_count_after = tcl("sta::network_leaf_pin_count")
    print(
        f"Instance count before {instance_count_before}, after {instance_count_after}",
        flush=True,
    )
    print(
        f"Pin count before {pin_count_before}, after {pin_count_after}",
        flush=True,
    )

    tcl("source_step_tcl POST RESIZE")

    orfs_write_db(f"{RESULTS_DIR}/3_4_place_resized.odb")


if __name__ == "__main__":
    main()
