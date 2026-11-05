#!/usr/bin/env python3
"""Minimal KiCad gate: python3 gate.py PROJECT_DIR NAME [waivers.json]. Exit 0 pass, 1 fail, 2 tool error."""
import json, pathlib, shutil, subprocess, sys, tempfile
d, name = pathlib.Path(sys.argv[1]), sys.argv[2]
w = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
allow_ignored = set(w.get("ignored_checks", []))   # checks allowed to be set to Ignore
allow_types = set(w.get("violation_types", []))    # reviewed warning types, with reasons kept in the file
fails = []
def run(*a):
    r = subprocess.run(a, capture_output=True, text=True)
    if r.returncode not in (0, 5):
        print("TOOL ERROR", a, r.returncode, r.stderr[-400:]); sys.exit(2)
    return r.returncode
def judge(tag, rep, keys):
    for c in rep["ignored_checks"]:
        if c["key"] not in allow_ignored: fails.append(f"{tag}: check disabled: {c['key']}")
    for v in [x for k in keys for x in rep.get(k, [])] + [x for s in rep.get("sheets", []) for x in s["violations"]]:
        if v["type"] not in allow_types: fails.append(f"{tag}: {v['severity']}: {v['type']}: {v['description']}")
with tempfile.TemporaryDirectory() as t:
    t = pathlib.Path(t); e, o = t/"erc.json", t/"drc.json"
    run("kicad-cli","sch","erc","--format","json","--severity-all","-o",str(e),str(d/f"{name}.kicad_sch"))
    judge("ERC", json.load(open(e)), [])
    run("kicad-cli","pcb","drc","--format","json","--severity-all","--schematic-parity","--refill-zones",
        "-o",str(o),str(d/f"{name}.kicad_pcb"))
    judge("DRC", json.load(open(o)), ["violations","unconnected_items","schematic_parity"])
    # Canary: a syntax error in .kicad_dru is silent, so prove the rule file still loads.
    c = t/"canary"; shutil.copytree(d, c, ignore=shutil.ignore_patterns("~*"))
    dru = c/f"{name}.kicad_dru"
    dru.write_text((dru.read_text() if dru.exists() else "(version 1)\n") +
        "\n(rule gate_canary (condition \"A.Type == 'track'\") (constraint track_width (min 50mm)))\n")
    run("kicad-cli","pcb","drc","--format","json","--severity-error","-o",str(t/"c.json"),str(c/f"{name}.kicad_pcb"))
    if not any(v["type"]=="track_width" and "gate_canary" in v["description"] for v in json.load(open(t/"c.json"))["violations"]):
        fails.append("CANARY: custom rules did not load (.kicad_dru broken?)")
print("\n".join(fails[:40])); print(f"{'FAIL' if fails else 'PASS'}: {len(fails)} finding(s)")
sys.exit(1 if fails else 0)
