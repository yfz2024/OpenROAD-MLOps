"""ORFS floorplan stage — Python port of flow/scripts/floorplan.tcl.

Invocation (via `make run`):
    openroad -no_splash -python flow/python/stages/floorplan.py

Reads `1_synth.odb` + `1_synth.sdc`, initialises the floorplan (one of four
methods: FLOORPLAN_DEF / FOOTPRINT / DIE_AREA+CORE_AREA / CORE_UTILIZATION),
makes tracks, configures global-routing layers, repairs tie fanout / removes
buffers / repairs setup, then writes `2_1_floorplan.{odb,sdc}`.
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
    print(f"[floorplan.py] metrics file: {_metrics_file}", flush=True)

from openroad import Design, Tech  # noqa: E402

_tech = Tech(None, None, _metrics_file) if _metrics_file else Tech()
_design = Design(_tech)
register_design(_design)

from orfs import (  # noqa: E402
    env_var_exists_and_non_empty,
    log_cmd,
    orfs_write_db,
    orfs_write_sdc,
    set_metrics_stage,
    tcl,
)
# === End stage prelude =======================================================

RESULTS_DIR = os.environ["RESULTS_DIR"]
SCRIPTS_DIR = os.environ["SCRIPTS_DIR"]
PLATFORM_DIR = os.environ["PLATFORM_DIR"]


def main():
    set_metrics_stage("floorplan__{}")

    tcl(f"source {SCRIPTS_DIR}/util.tcl")
    tcl(f"source {SCRIPTS_DIR}/load.tcl")
    tcl(f"source {SCRIPTS_DIR}/report_metrics.tcl")

    tcl("erase_non_stage_variables floorplan")
    tcl("load_design 1_synth.odb 1_synth.sdc")
    tcl("source_step_tcl PRE FLOORPLAN")

    # report_unused_masters is a stage-local TCL proc in floorplan.tcl. Define
    # it once via tcl() — procs are global in the TCL interpreter so a single
    # source-style definition is enough.
    tcl(
        """
        proc report_unused_masters { } {
          set db [ord::get_db]
          set libs [$db getLibs]
          set masters ""
          foreach lib $libs {
            foreach master [$lib getMasters] {
              if { [$master getType] == "BLOCK" } {
                lappend masters $master
              }
            }
          }
          set block [ord::get_db_block]
          set insts [$block getInsts]
          foreach inst $insts {
            set inst_master [$inst getMaster]
            set masters [lsearch -all -not -inline $masters $inst_master]
          }
          foreach master $masters {
            puts "Master [$master getName] is loaded but not used in the design"
          }
        }
        """
    )
    tcl("report_unused_masters")

    print(
        "\n=========================================================================="
    )
    print("Floorplan check_setup")
    print(
        "--------------------------------------------------------------------------"
    )
    tcl("check_setup")

    num_instances = tcl("llength [get_cells -hier *]")
    print(f"number instances in verilog is {num_instances}", flush=True)

    additional_args = ""
    if env_var_exists_and_non_empty("ADDITIONAL_SITES"):
        additional_args = f"-additional_sites {os.environ['ADDITIONAL_SITES']}"

    # Pick exactly one of four floorplan-initialization methods (mutually exclusive).
    use_floorplan_def = env_var_exists_and_non_empty("FLOORPLAN_DEF")
    use_footprint = env_var_exists_and_non_empty("FOOTPRINT")
    use_die_and_core_area = env_var_exists_and_non_empty("DIE_AREA") and env_var_exists_and_non_empty("CORE_AREA")
    use_core_utilization = env_var_exists_and_non_empty("CORE_UTILIZATION")

    methods = sum(map(int, [use_floorplan_def, use_footprint, use_die_and_core_area, use_core_utilization]))
    if methods > 1:
        print("Error: Floorplan initialization methods are mutually exclusive, pick one.")
        sys.exit(1)
    if methods == 0:
        print("Error: No floorplan initialization method specified")
        sys.exit(1)

    if use_floorplan_def:
        log_cmd(f"read_def -floorplan_initialize {os.environ['FLOORPLAN_DEF']}")
    elif use_footprint:
        # ICeWall is a TCL namespace ensemble; we just bridge each call.
        tcl(f"ICeWall load_footprint {os.environ['FOOTPRINT']}")
        die_area = tcl("ICeWall get_die_area")
        core_area = tcl("ICeWall get_core_area")
        tcl(
            f'initialize_floorplan -die_area {{{die_area}}} '
            f'-core_area {{{core_area}}} -site {os.environ["PLACE_SITE"]}'
        )
        tcl(f"ICeWall init_footprint {os.environ['SIG_MAP_FILE']}")
    elif use_die_and_core_area:
        # DIE_AREA and CORE_AREA are 4-number lists "x1 y1 x2 y2" — wrap in
        # TCL braces so initialize_floorplan sees each as one list argument
        # (same trick as the DPO_MAX_DISPLACEMENT bug from detail_place).
        tcl(
            f'initialize_floorplan -die_area {{{os.environ["DIE_AREA"]}}} '
            f'-core_area {{{os.environ["CORE_AREA"]}}} '
            f'-site {os.environ["PLACE_SITE"]} '
            + additional_args
        )
    else:  # use_core_utilization
        tcl(
            f'initialize_floorplan -utilization {os.environ["CORE_UTILIZATION"]} '
            f'-aspect_ratio {os.environ["CORE_ASPECT_RATIO"]} '
            f'-core_space {os.environ["CORE_MARGIN"]} '
            f'-site {os.environ["PLACE_SITE"]} '
            + additional_args
        )

    # Routing tracks: explicit script, platform default, or built-in.
    if env_var_exists_and_non_empty("MAKE_TRACKS"):
        log_cmd(f"source {os.environ['MAKE_TRACKS']}")
    elif os.path.exists(f"{PLATFORM_DIR}/make_tracks.tcl"):
        log_cmd(f"source {PLATFORM_DIR}/make_tracks.tcl")
    else:
        tcl("make_tracks")

    # Global routing layers: FASTROUTE_TCL or set_*.
    if env_var_exists_and_non_empty("FASTROUTE_TCL"):
        log_cmd(f"source {os.environ['FASTROUTE_TCL']}")
    else:
        min_layer = os.environ["MIN_ROUTING_LAYER"]
        max_layer = os.environ["MAX_ROUTING_LAYER"]
        adj = os.environ["ROUTING_LAYER_ADJUSTMENT"]
        log_cmd(
            f"set_global_routing_layer_adjustment {min_layer}-{max_layer} {adj}"
        )
        log_cmd(f"set_routing_layers -signal {min_layer}-{max_layer}")

    tcl("source_env_var_if_exists FOOTPRINT_TCL")

    # Tie fanout / arithmetic operator swap / buffer cleanup / setup repair.
    # See the comment block in floorplan.tcl for why these run here and not
    # in synth_odb.tcl (regressed setup TNS 1.7-46x when moved).
    if os.environ.get("SKIP_REPAIR_TIE_FANOUT", "0") == "0":
        print("Repair tie lo fanout...", flush=True)
        # Resolve tielo pin via nested TCL (lindex/get_lib_cell/get_property)
        # in one tcl() block — re-implementing the lib/cell traversal in
        # Python would require dragging in dbSta methods that aren't worth
        # exercising here.
        tcl(
            """
            set tielo_cell_name [lindex $::env(TIELO_CELL_AND_PORT) 0]
            set tielo_lib_name [get_name [get_property [lindex [get_lib_cell $tielo_cell_name] 0] library]]
            set tielo_pin $tielo_lib_name/$tielo_cell_name/[lindex $::env(TIELO_CELL_AND_PORT) 1]
            repair_tie_fanout -separation $::env(TIE_SEPARATION) $tielo_pin
            """
        )

        print("Repair tie hi fanout...", flush=True)
        tcl(
            """
            set tiehi_cell_name [lindex $::env(TIEHI_CELL_AND_PORT) 0]
            set tiehi_lib_name [get_name [get_property [lindex [get_lib_cell $tiehi_cell_name] 0] library]]
            set tiehi_pin $tiehi_lib_name/$tiehi_cell_name/[lindex $::env(TIEHI_CELL_AND_PORT) 1]
            repair_tie_fanout -separation $::env(TIE_SEPARATION) $tiehi_pin
            """
        )

    if env_var_exists_and_non_empty("SWAP_ARITH_OPERATORS"):
        tcl("set_debug_level ODB replace_design_check_sanity 1")
        tcl("replace_arith_modules")

    if os.environ.get("REMOVE_ABC_BUFFERS", "0") != "0":
        tcl("remove_buffers")
    else:
        # Skip clone & split
        tcl(
            "repair_timing_helper -setup -skip_last_gasp "
            '-sequence "unbuffer,sizeup,swap,vt_swap"'
        )

    print("Default units for flow", flush=True)
    tcl("report_units")
    tcl("report_units_metric")
    tcl("report_layer_rc")
    tcl('report_metrics 2 "floorplan final" false false')

    tcl("source_step_tcl POST FLOORPLAN")
    tcl("source_env_var_if_exists IO_CONSTRAINTS")

    orfs_write_db(f"{RESULTS_DIR}/2_1_floorplan.odb")
    orfs_write_sdc(f"{RESULTS_DIR}/2_1_floorplan.sdc")


if __name__ == "__main__":
    main()
