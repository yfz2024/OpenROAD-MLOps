"""Minimal evalTclString smoke test.

Usage:
    cd flow
    make DESIGN_CONFIG=./designs/asap7/gcd/config.mk \\
         RUN_SCRIPT=$PWD/python/stages/_smoke.py \\
         RUN_LOG_NAME_STEM=_smoke \\
         run

This verifies whether `Design.evalTclString()` is callable at all in the
`openroad -python` build we have. It does NOT load any design file — purely
exercises the Tech/Design/TCL plumbing.
"""
from openroad import Design, Tech

print("[smoke] creating Tech() ...")
tech = Tech()
print("[smoke] creating Design(tech) ...")
design = Design(tech)
print("[smoke] calling evalTclString(\"puts hello-from-tcl\") ...")
result = design.evalTclString('puts hello-from-tcl')
print(f"[smoke] result repr: {result!r}")
print("[smoke] OK.")
