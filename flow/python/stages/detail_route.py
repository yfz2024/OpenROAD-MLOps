"""ORFS detail-route stage — Python port of flow/scripts/detail_route.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/detail_route.py

Reads `5_1_grt.odb` + `5_1_grt.sdc`. If global routing failed (no routes),
errors out. If SKIP_DETAILED_ROUTE just dumps the input and exits.
Otherwise runs `detailed_route` with the platform-tuned arg vector, then
optionally repairs antennas in a loop. Writes `5_2_route.odb`.
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
    print(f"[detail_route.py] metrics file: {_metrics_file}", flush=True)

from openroad import Design, Tech  # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import (  # noqa: E402
    append_env_var,
    env_var_exists_and_non_empty,
    log_cmd,
    orfs_write_db,
    set_metrics_stage,
    tcl,
)
# === End stage prelude =======================================================

RESULTS_DIR = os.environ["RESULTS_DIR"]
REPORTS_DIR = os.environ["REPORTS_DIR"]
SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]


def main():
    set_metrics_stage("detailedroute__{}")

    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")
    tcl(f"source {SCRIPTS_DIR}/report_metrics.tcl")

    tcl("load_design 5_1_grt.odb 5_1_grt.sdc")
    tcl("source_step_tcl PRE DETAIL_ROUTE")

    if tcl("grt::have_routes") != "1":
        raise RuntimeError(
            "Global routing failed, run `make gui_grt` and load the "
            "congestion report in DRC viewer to view congestion"
        )

    if os.environ.get("SKIP_DETAILED_ROUTE", "0") != "0":
        orfs_write_db(f"{RESULTS_DIR}/5_2_route.odb")
        return

    tcl("erase_non_stage_variables route")
    tcl("set_propagated_clock [all_clocks]")

    additional_args = []
    append_env_var(additional_args, "dbProcessNode", "-db_process_node", True)
    append_env_var(additional_args, "OR_SEED", "-or_seed", True)
    append_env_var(additional_args, "OR_K", "-or_k", True)
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
    append_env_var(additional_args, "DISABLE_VIA_GEN", "-disable_via_gen", False)
    append_env_var(
        additional_args, "REPAIR_PDN_VIA_LAYER", "-repair_pdn_vias", True
    )
    append_env_var(
        additional_args,
        "DETAILED_ROUTE_END_ITERATION",
        "-droute_end_iter",
        True,
    )

    additional_args += ["-verbose", "1"]

    # See the comment block in detail_route.tcl: if DETAILED_ROUTE_ARGS is set
    # use it verbatim; otherwise default to additional_args + a progress
    # cadence flag that gives readable .drc reports a few iters in.
    if env_var_exists_and_non_empty("DETAILED_ROUTE_ARGS"):
        arguments = os.environ["DETAILED_ROUTE_ARGS"].split()
    else:
        arguments = additional_args + ["-drc_report_iter_step", "5"]

    all_args = [
        "-output_drc",
        f"{REPORTS_DIR}/5_route_drc.rpt",
        "-output_maze",
        f"{RESULTS_DIR}/maze.log",
    ] + arguments
    log_cmd("detailed_route " + " ".join(all_args))
    detailed_route_cmd = "detailed_route " + " ".join(all_args)

    if (
        os.environ.get("SKIP_ANTENNA_REPAIR_POST_DRT", "0") == "0"
        and env_var_exists_and_non_empty("MAX_REPAIR_ANTENNAS_ITER_DRT")
    ):
        repair_iters = 1
        max_iters = int(os.environ["MAX_REPAIR_ANTENNAS_ITER_DRT"])
        # First repair pass: only re-route if repair_antennas reported changes.
        # repair_antennas returns "1" (true) when it made changes, "0" otherwise.
        if tcl("repair_antennas") == "1":
            tcl(detailed_route_cmd)
        # Iterate: re-check antennas, repair, re-route. check_antennas returns
        # "1" if violations remain.
        while tcl("check_antennas") == "1" and repair_iters < max_iters:
            tcl("repair_antennas")
            tcl(detailed_route_cmd)
            repair_iters += 1
    else:
        tcl('utl::metric_int "antenna_diodes_count" -1')

    tcl("source_step_tcl POST DETAIL_ROUTE")

    tcl(f"check_antennas -report_file {REPORTS_DIR}/drt_antennas.log")

    if tcl("design_is_routed") != "1":
        raise RuntimeError("Design has unrouted nets.")

    tcl("report_design_area")

    # No report_metrics here — parasitics aren't extracted yet, that happens
    # in finish.

    orfs_write_db(f"{RESULTS_DIR}/5_2_route.odb")


if __name__ == "__main__":
    main()
