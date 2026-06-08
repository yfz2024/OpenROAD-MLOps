"""ORFS final-report stage — Python port of flow/scripts/final_report.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/final_report.py

Reads `6_1_fill.odb` + `6_1_fill.sdc`, runs global_connect, deletes routing
obstructions, writes `6_final.{odb,def,v}`. If RCX_RULES is set and not
SKIP_DETAILED_ROUTE, extracts parasitics, writes SPEF, and runs IR drop
analysis on PWR_NETS_VOLTAGES / GND_NETS_VOLTAGES dicts. Otherwise falls
back to global-routing-based parasitic estimation.
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
    print(f"[final_report.py] metrics file: {_metrics_file}", flush=True)

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
REPORTS_DIR = os.environ["REPORTS_DIR"]
SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]


def main():
    set_metrics_stage("finish__{}")

    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")
    tcl(f"source {SCRIPTS_DIR}/report_metrics.tcl")

    tcl("erase_non_stage_variables final")
    tcl("load_design 6_1_fill.odb 6_1_fill.sdc")
    tcl("source_step_tcl PRE FINAL_REPORT")

    tcl("set_propagated_clock [all_clocks]")

    # Ensure all OR-created (rsz/cts) instances are connected.
    tcl("global_connect")

    orfs_write_db(f"{RESULTS_DIR}/6_final.odb")

    # Delete routing obstructions before writing the final DEF.
    tcl(f"source {SCRIPTS_DIR}/deleteRoutingObstructions.tcl")
    tcl("deleteRoutingObstructions")

    tcl(f"write_def {RESULTS_DIR}/6_final.def")
    tcl(
        f"write_verilog {RESULTS_DIR}/6_final.v "
        "-remove_cells [find_physical_only_masters]"
    )

    rcx_enabled = (
        env_var_exists_and_non_empty("RCX_RULES")
        and os.environ.get("SKIP_DETAILED_ROUTE", "0") == "0"
    )
    if rcx_enabled:
        tcl("define_process_corner -ext_model_index 0 X")
        tcl(f"extract_parasitics -ext_model_file {os.environ['RCX_RULES']}")

        tcl(f"write_spef {RESULTS_DIR}/6_final.spef")
        # The .totCap dump is a build-tree artifact, not a stage product —
        # remove it like the TCL flow does.
        tcl(f'file delete {os.environ["DESIGN_NAME"]}.totCap')

        # Re-read for OpenSTA timing.
        tcl(f"read_spef {RESULTS_DIR}/6_final.spef")

        # IR-drop on power / ground nets (driven by env dicts).
        # The TCL `dict for {k v} $::env(VAR) { ... }` is easier to keep as
        # one tcl() block per net direction than to parse the dict in Python.
        if env_var_exists_and_non_empty("PWR_NETS_VOLTAGES"):
            tcl(
                f"""
                dict for {{pwrNetName pwrNetVoltage}} $::env(PWR_NETS_VOLTAGES) {{
                  set_pdnsim_net_voltage -net ${{pwrNetName}} -voltage ${{pwrNetVoltage}}
                  analyze_power_grid -net ${{pwrNetName}} \\
                    -error_file {REPORTS_DIR}/${{pwrNetName}}.rpt
                }}
                """
            )
        else:
            print(
                "IR drop analysis for power nets is skipped because "
                "PWR_NETS_VOLTAGES is undefined",
                flush=True,
            )

        if env_var_exists_and_non_empty("GND_NETS_VOLTAGES"):
            tcl(
                f"""
                dict for {{gndNetName gndNetVoltage}} $::env(GND_NETS_VOLTAGES) {{
                  set_pdnsim_net_voltage -net ${{gndNetName}} -voltage ${{gndNetVoltage}}
                  analyze_power_grid -net ${{gndNetName}} \\
                    -error_file {REPORTS_DIR}/${{gndNetName}}.rpt
                }}
                """
            )
        else:
            print(
                "IR drop analysis for ground nets is skipped because "
                "GND_NETS_VOLTAGES is undefined",
                flush=True,
            )
    else:
        print("OpenRCX is not enabled for this platform.", flush=True)
        print("Falling back to global route-based estimates.", flush=True)
        log_cmd("estimate_parasitics -global_routing")

    tcl("report_cell_usage")

    tcl('report_metrics 6 "finish"')

    tcl("source_step_tcl POST FINAL_REPORT")


if __name__ == "__main__":
    main()
