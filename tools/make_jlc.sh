#!/bin/bash
# JLCPCB fab package from the saved board: Gerbers + drill (zip), SMT BOM, CPL with rotation fixes, hand-solder list.
set -eo pipefail
H=/home/sid/Documents/code/im6014Development/.claude/worktrees/regen-clamp-review-f9d0d4
P=$H/hardware/regen-precharge-board; O=$H/results/hardware/regen-precharge-board/jlcpcb
rm -rf $O && mkdir -p $O/gerbers
kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts --subtract-soldermask --check-zones -o $O/gerbers $P/regen_precharge.kicad_pcb >/dev/null
kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-map --map-format gerberx2 -o $O/gerbers/ $P/regen_precharge.kicad_pcb >/dev/null
(cd $O/gerbers && zip -q ../regen_precharge_revE_gerbers.zip *)
kicad-cli sch export netlist --format kicadxml -o $O/net.xml $P/regen_precharge.kicad_sch >/dev/null
kicad-cli pcb export pos --format csv --units mm --side front --exclude-dnp -o $O/pos.csv $P/regen_precharge.kicad_pcb >/dev/null
python3 -I - $O <<'PY'
import csv, sys, re, xml.etree.ElementTree as ET
from collections import defaultdict
O = sys.argv[1]
comps = {}
for c in ET.parse(f"{O}/net.xml").getroot().find("components"):
    f = {x.get("name"): x.text or "" for x in c.iter("field")}
    comps[c.get("ref")] = dict(val=c.findtext("value"), fp=c.findtext("footprint").split(":")[1], lcsc=f.get("LCSC", ""), hand=f.get("Assembly") == "Hand-solder")
smt = {r: c for r, c in comps.items() if c["lcsc"] and not c["hand"]}
hand = {r: c for r, c in comps.items() if c["lcsc"] and c["hand"]}
def group(d):
    g = defaultdict(list)
    for r, c in d.items(): g[(c["val"], c["fp"], c["lcsc"])].append(r)
    key = lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0))
    return sorted(((k, sorted(v, key=key)) for k, v in g.items()), key=lambda kv: key(kv[1][0]))
with open(f"{O}/BOM-JLCPCB.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (v, fp, l), refs in group(smt): w.writerow([v, ",".join(refs), fp, l])
with open(f"{O}/HAND-SOLDER-parts.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["Qty", "Designator", "Part", "LCSC Part #"])
    for (v, fp, l), refs in group(hand): w.writerow([len(refs), ",".join(refs), v, l])
    w.writerow([2, "off-board, in brake resistor lead (1 + spare)", "Q136 thermal fuse, 136 C, 25 A, DC 120 V", "C22396303"])
# JLC rotation offsets for KiCad-library footprints (the jlc: EasyEDA footprints already match JLC's models)
FIX = [(r"^SOIC-8", 270), (r"^SOT-23$", 180)]
with open(f"{O}/pos.csv") as fh, open(f"{O}/CPL-JLCPCB.csv", "w", newline="") as out:
    w = csv.writer(out); w.writerow(["Designator", "Mid X", "Mid Y", "Rotation", "Layer"]); n = 0
    for row in csv.DictReader(fh):
        ref = row["Ref"]
        if ref not in smt: continue
        rot = float(row["Rot"]); fp = smt[ref]["fp"]
        for pat, add in FIX:
            if re.search(pat, fp): rot = (rot + add) % 360
        w.writerow([ref, f'{float(row["PosX"]):.4f}mm', f'{float(row["PosY"]):.4f}mm', f"{rot:g}", "Top"]); n += 1
missing = set(smt) - {r for r in csv.DictReader(open(f"{O}/pos.csv")) for r in [r["Ref"]]}
print("BOM lines", len(group(smt)), "SMT parts", len(smt), "CPL rows", n, "hand-solder lines", len(group(hand)), "missing from CPL", sorted(missing))
PY
rm -f $O/pos.csv $O/net.xml
