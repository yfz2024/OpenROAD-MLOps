"""ORFS global-route stage — Python port of flow/scripts/global_route.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/global_route.py

Reads `4_cts.odb` + `4_cts.sdc`. Runs pin_access then global_route, then a
three-pass incremental repair (design → timing → power) that interleaves
global_route -start_incremental / -end_incremental with detailed_placement
and repair_design_helper / repair_timing_helper / recover_power_helper.
Optional antenna repair pass. Writes `5_1_grt.{odb,sdc}`.
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
    print(f"[global_route.py] metrics file: {_metrics_file}", flush=True)

from openroad import Design, Tech  # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import (  # noqa: E402
    append_env_var,
    env_var_exists_and_non_empty,
    log_cmd,
    orfs_write_db,
    orfs_write_sdc,
    set_metrics_stage,
    tcl,
)
# === End stage prelude =======================================================

RESULTS_DIR = os.environ["RESULTS_DIR"]
REPORTS_DIR = os.environ["REPORTS_DIR"]
SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]


def do_global_route(res_aware):
    """Mirror of the `do_global_route` proc inside global_route.tcl.

    `$::global_route_congestion_report` is a TCL global set in util.tcl —
    we read it back through tcl() so the path matches the TCL flow exactly.
    """
    congestion_report = tcl("set ::global_route_congestion_report")
    all_args = [
        "-congestion_report_file",
        congestion_report,
    ]
    if env_var_exists_and_non_empty("GLOBAL_ROUTE_ARGS"):
        all_args += os.environ["GLOBAL_ROUTE_ARGS"].split()
    all_args += res_aware
    log_cmd("global_route " + " ".join(all_args))


def main():
    set_metrics_stage("globalroute__{}")

    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")
    tcl(f"source {SCRIPTS_DIR}/report_metrics.tcl")

    tcl("erase_non_stage_variables grt")
    tcl("load_design 4_cts.odb 4_cts.sdc")
    tcl("source_step_tcl PRE GLOBAL_ROUTE")

    res_aware = []
    append_env_var(
        res_aware, "ENABLE_RESISTANCE_AWARE", "-resistance_aware", False
    )

    additional_args = []
    append_env_var(additional_args, "dbProcessNode", "-db_process_node", True)
    append_env_var(
        additional_args,
        "VIA_IN_PIN_MIN_LAYER",
        "-via_in_pin_bottom_layer",
        True,
    )
    append_env_var(
        additional_args,
        "VIA_IN_PIN_MAX_LAYER",
        "-via_in_pin_top_layer",
        True,
    )

    log_cmd("pin_access " + " ".join(additional_args))

    try:
        do_global_route(res_aware)
    except RuntimeError as e:
        if os.environ.get("GENERATE_ARTIFACTS_ON_FAILURE", "0") == "0":
            orfs_write_db(f"{RESULTS_DIR}/5_1_grt-failed.odb")
            raise
        orfs_write_sdc(f"{RESULTS_DIR}/5_1_grt.sdc")
        orfs_write_db(f"{RESULTS_DIR}/5_1_grt.odb")
        # Early-return like the TCL `return` inside global_route_helper.
        print(f"[global_route.py] global_route failed, artifacts written: {e}",
              flush=True)
        return

    pad = os.environ["CELL_PAD_IN_SITES_DETAIL_PLACEMENT"]
    tcl(f"set_placement_padding -global -left {pad} -right {pad}")

    tcl("set_propagated_clock [all_clocks]")
    log_cmd("estimate_parasitics -global_routing")

    if env_var_exists_and_non_empty("DONT_USE_CELLS"):
        tcl("set_dont_use $::env(DONT_USE_CELLS)")

    if os.environ.get("SKIP_INCREMENTAL_REPAIR", "0") == "0":
        if os.environ.get("DETAILED_METRICS", "0") != "0":
            tcl('report_metrics 5 "global route pre repair design"')

        # Repair design using global route parasitics.
        tcl("repair_design_helper")
        if os.environ.get("DETAILED_METRICS", "0") != "0":
            tcl('report_metrics 5 "global route post repair design"')

        # DPL to fix overlaps introduced by repair_design.
        dpl_args = []
        append_env_var(dpl_args, "USE_NEGOTIATION", "-use_negotiation", False)
        dpl_cmd = "detailed_placement " + " ".join(dpl_args)

        log_cmd("global_route -start_incremental")
        log_cmd(dpl_cmd)
        log_cmd(
            "global_route -end_incremental "
            + " ".join(res_aware)
            + f" -congestion_report_file {REPORTS_DIR}/congestion_post_repair_design.rpt"
        )

        # Timing repair.
        print("Repair setup and hold violations...", flush=True)
        log_cmd("estimate_parasitics -global_routing")
        tcl("repair_timing_helper")
        if os.environ.get("DETAILED_METRICS", "0") != "0":
            tcl('report_metrics 5 "global route post repair timing"')

        log_cmd("global_route -start_incremental")
        log_cmd(dpl_cmd)
        tcl("check_placement -verbose")
        log_cmd(
            "global_route -end_incremental "
            + " ".join(res_aware)
            + f" -congestion_report_file {REPORTS_DIR}/congestion_post_repair_timing.rpt"
        )

    # Power recovery — emits its own global_route -start/-end pair.
    log_cmd("global_route -start_incremental")
    tcl("recover_power_helper")
    log_cmd(
        "global_route -end_incremental "
        + " ".join(res_aware)
        + f" -congestion_report_file {REPORTS_DIR}/congestion_post_recover_power.rpt"
    )

    if (
        os.environ.get("SKIP_ANTENNA_REPAIR", "0") == "0"
        and env_var_exists_and_non_empty("MAX_REPAIR_ANTENNAS_ITER_GRT")
    ):
        print("Repair antennas...", flush=True)
        tcl(
            "repair_antennas -iterations "
            f"{os.environ['MAX_REPAIR_ANTENNAS_ITER_GRT']}"
        )
        # repair_antennas calls DPL internally
        tcl("check_placement -verbose")
        tcl(f"check_antennas -report_file {REPORTS_DIR}/grt_antennas.log")

    print("Estimate parasitics...", flush=True)
    log_cmd("estimate_parasitics -global_routing")

    tcl('report_metrics 5 "global route"')

    # Write reference SDC with relaxed clock periods.
    tcl(f'source [file join {SCRIPTS_DIR} "write_ref_sdc.tcl"]')

    tcl(f"write_guides {RESULTS_DIR}/route.guide")
    tcl("source_step_tcl POST GLOBAL_ROUTE")
    orfs_write_db(f"{RESULTS_DIR}/5_1_grt.odb")
    orfs_write_sdc(f"{RESULTS_DIR}/5_1_grt.sdc")


if __name__ == "__main__":
    main()
