"""utl::set/push/pop_metrics_stage thin Python wrappers."""
from .tcl import tcl


def set_metrics_stage(name):
    tcl(f'utl::set_metrics_stage "{name}"')


def push_metrics_stage(name):
    tcl(f'utl::push_metrics_stage "{name}"')


def pop_metrics_stage():
    tcl("utl::pop_metrics_stage")
