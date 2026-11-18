#!/usr/bin/env bash
set -euo pipefail

project="$(cd "$(dirname "$0")/.." && pwd)"
output="${1:-$project/jlcpcb}"
case "$output" in
    /*) ;;
    *) output="$PWD/$output" ;;
esac
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT

cd "$project"
kicad-cli sch erc --severity-all --exit-code-violations -o "$stage/erc.rpt" regen_precharge.kicad_sch
kicad-cli pcb drc --severity-all --schematic-parity --refill-zones --exit-code-violations \
    -o "$stage/drc.rpt" regen_precharge.kicad_pcb

kicad-cli sch export netlist --format kicadxml -o "$stage/net.xml" regen_precharge.kicad_sch
kicad-cli pcb export pos --format csv --units mm --side front --exclude-dnp \
    -o "$stage/pos.csv" regen_precharge.kicad_pcb

python3 -I - "$stage" <<'PY'
import csv
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

stage = Path(sys.argv[1])
machine = {}
hand = {}
for component in ET.parse(stage / "net.xml").getroot().find("components"):
    fields = {field.get("name"): field.text or "" for field in component.iter("field")}
    lcsc = fields.get("LCSC")
    if not lcsc:
        continue
    ref = component.get("ref")
    footprint = component.findtext("footprint").split(":", 1)[1]
    parts = hand if fields.get("Assembly") == "Hand-solder" else machine
    parts[ref] = (component.findtext("value"), footprint, lcsc)

with (stage / "pos.csv").open(newline="") as source:
    positions = list(csv.DictReader(source))
refs = [row["Ref"] for row in positions]
if len(refs) != len(set(refs)) or set(refs) != machine.keys():
    raise SystemExit(
        f"KiCad positions disagree with the schematic. "
        f"Missing: {sorted(machine.keys() - set(refs))}. "
        f"Unexpected: {sorted(set(refs) - machine.keys())}. "
        f"Duplicate rows: {len(refs) - len(set(refs))}."
    )

def ref_key(ref):
    match = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    return match[1], int(match[2])

def groups(parts):
    by_part = defaultdict(list)
    for ref, (_, footprint, lcsc) in parts.items():
        by_part[footprint, lcsc].append(ref)
    for footprint, lcsc in sorted(by_part, key=lambda part: min(map(ref_key, by_part[part]))):
        refs = sorted(by_part[footprint, lcsc], key=ref_key)
        values = [parts[ref][0] for ref in refs]
        value = values[0] if len(set(values)) == 1 else min(
            (value.split(" (", 1)[0] for value in values), key=len
        )
        yield value, footprint, lcsc, refs

with (stage / "BOM-JLCPCB.csv").open("w", newline="") as output:
    writer = csv.writer(output)
    writer.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for value, footprint, lcsc, refs in groups(machine):
        writer.writerow([value, ",".join(refs), footprint, lcsc])

with (stage / "HAND-SOLDER-parts.csv").open("w", newline="") as output:
    writer = csv.writer(output)
    writer.writerow(["Qty", "Designator", "Part", "LCSC Part #"])
    for value, _, lcsc, refs in groups(hand):
        writer.writerow([len(refs), ",".join(refs), value, lcsc])
    writer.writerow([
        2, "off-board, in brake resistor lead (1 + spare)",
        "Q136 thermal fuse, 136 C, 25 A, DC 120 V", "C22396303",
    ])

# Each offset converts a KiCad footprint orientation to the JLC library orientation.
offsets = {"SOT-23": 180, "SOT-23-5": 180, "SOT-223": 180}
with (stage / "CPL-JLCPCB.csv").open("w", newline="") as output:
    writer = csv.writer(output)
    writer.writerow(["Designator", "Mid X", "Mid Y", "Rotation", "Layer"])
    for row in positions:
        ref = row["Ref"]
        _, footprint, _ = machine[ref]
        rotation = float(row["Rot"])
        offset = 270 if footprint.startswith("SOIC-8") else offsets.get(footprint, 0)
        if offset:
            rotation = (rotation + offset) % 360
        x = float(row["PosX"])
        y = float(row["PosY"])
        writer.writerow([ref, f"{x:.4f}mm", f"{y:.4f}mm", f"{rotation:g}", "Top"])

print(f"{len(machine)} machine placements on {sum(1 for _ in groups(machine))} BOM lines")
print(f"{len(hand)} hand-solder placements")
PY

kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts \
    --subtract-soldermask --check-zones -o "$stage/gerbers/" regen_precharge.kicad_pcb
# The front stencil must contain exactly the machine-populated references.
python3 -I - "$stage" <<'PYCODE'
import csv
import re
import sys
from pathlib import Path

stage = Path(sys.argv[1])
with (stage / "CPL-JLCPCB.csv").open(newline="") as source:
    machine = {row["Designator"] for row in csv.DictReader(source)}
paste = (stage / "gerbers/regen_precharge-F_Paste.gtp").read_text()
stencilled = set(re.findall(r"^%TO\.C,([^*]+)\*%$", paste, re.MULTILINE))
if stencilled != machine:
    raise SystemExit(
        f"Front paste does not match machine placements. Missing: {sorted(machine - stencilled)}. "
        f"Unexpected: {sorted(stencilled - machine)}."
    )
PYCODE
kicad-cli pcb export drill --format excellon --excellon-separate-th \
    -o "$stage/gerbers/" regen_precharge.kicad_pcb
(cd "$stage/gerbers" && zip -q ../regen_precharge_revF_gerbers.zip *.g?? *.drl)

echo "Writing fabrication and assembly files to $output"
mkdir -p "$output"
cp "$stage/"{BOM-JLCPCB.csv,CPL-JLCPCB.csv,HAND-SOLDER-parts.csv,regen_precharge_revF_gerbers.zip} "$output/"
