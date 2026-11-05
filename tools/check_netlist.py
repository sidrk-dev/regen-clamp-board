#!/usr/bin/env python3
"""Pin-by-pin diff: the part table in build_sch.py (intent) vs kicad-cli's netlist of the saved schematic and the saved board pads."""
import ast, re, subprocess, sys, tempfile, pathlib, xml.etree.ElementTree as ET
sch, pcb, gen = sys.argv[1:4]
src = open(gen).read()
intent = {}
for m in re.finditer(r'^part\("(\w+)",.*?(\{[^{}]*\})', src, re.S | re.M):
    for pin, net in ast.literal_eval(m.group(2)).items(): intent[(m.group(1), pin)] = net
for ref, net in re.findall(r'\("(TP\d+)", "(\w+)"\)', src): intent[(ref, "1")] = net
with tempfile.TemporaryDirectory() as t:
    x = pathlib.Path(t)/"n.xml"
    subprocess.run(["kicad-cli","sch","export","netlist","--format","kicadxml","-o",str(x),sch],capture_output=True,check=True)
    actual = {(n.get("ref"),n.get("pin")): net.get("name").lstrip("/") for net in ET.parse(x).getroot().find("nets") for n in net}
import pcbnew
b = pcbnew.LoadBoard(pcb)
board = {(f.GetReference(),p.GetNumber()): p.GetNetname() for f in b.GetFootprints() for p in f.Pads() if p.GetNumber()}
bad = []
for k, n in sorted(intent.items()):
    if actual.get(k) != n: bad.append(f"SCH {k}: intent {n}, schematic {actual.get(k)}")
    if board.get(k) != n: bad.append(f"PCB {k}: intent {n}, board {board.get(k)}")
for k, n in sorted(actual.items()):
    if k not in intent and not k[0].startswith("#") and not n.startswith("unconnected"): bad.append(f"SCH extra {k} on {n}")
print("\n".join(bad[:40])); print(f"{'FAIL' if bad else 'PASS'}: {len(intent)} intended pins compared, {len(bad)} differences")
sys.exit(1 if bad else 0)
