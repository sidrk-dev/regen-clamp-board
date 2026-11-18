#!/usr/bin/env python3
"""Apply the agreed rev F review fixes and return the six TO-263 MOSFETs to JLCPCB SMT assembly:
1. J1 and J5 (XT60PW-M / XT60PW-F): contact drills 2.9 -> 3.0 mm; fixing slots 0.8x1.9 -> 0.9x2.0 mm with
   slot pads 1.4x2.5 -> 1.5x2.6 mm (matching the updated lib/jlc.pretty footprints).
2. Q1, Q2, Q3, Q7, Q8, Q9 (CRSS042N10N): clear Hand-solder Assembly attribute, re-include in position files,
   and restore front stencil paste openings.
3. Thermal reliefs on pads 1 and 2 of C7, C8, C15, C16, C17 and on J12 pad 1, followed by zone refill.
4. Move C8's silkscreen reference designator out from under D2's body to (177.2, 144.5) mm.
5. Update schematic title block and notes: rev F, 27 A supply, four 470 uF output capacitors, D12 under 17 V.

Usage: python3 -I tools/rev_f_review_fixes.py <board.kicad_pcb> <schematic.kicad_sch> <build_sch.py>
"""
import re
import sys
import pcbnew

mm, fm = pcbnew.ToMM, pcbnew.FromMM
board_path, sch_path, gen_path = sys.argv[1:4]

FETS = ("Q1", "Q2", "Q3", "Q7", "Q8", "Q9")
CAPS = ("C7", "C8", "C15", "C16", "C17")

b = pcbnew.LoadBoard(board_path)

# 1. Update J1 and J5 pad & drill dimensions to match lib/jlc.pretty
j1 = b.FindFootprintByReference("J1")
j1.SetLibDescription(
    "XT60PW-M horizontal PCB connector. Holes centred in the Amass XT60PW-M30.G.Y.T window served for LCSC C98732: "
    "contacts 3.0 mm, fixing slots 0.9 x 2.0 mm"
)
for ref in ("J1", "J5"):
    f = b.FindFootprintByReference(ref)
    slots = contacts = 0
    for p in f.Pads():
        if p.GetNumber() in ("1", "2"):
            assert abs(mm(p.GetDrillSizeX()) - 2.9) < 1e-4, (ref, p.GetNumber(), mm(p.GetDrillSizeX()))
            p.SetDrillSize(pcbnew.VECTOR2I(fm(3.0), fm(3.0)))
            contacts += 1
        elif p.GetNumber() == "":
            assert abs(mm(p.GetDrillSizeX()) - 0.8) < 1e-4 and abs(mm(p.GetDrillSizeY()) - 1.9) < 1e-4, ref
            assert abs(mm(p.GetSizeX()) - 1.4) < 1e-4 and abs(mm(p.GetSizeY()) - 2.5) < 1e-4, ref
            p.SetDrillSize(pcbnew.VECTOR2I(fm(0.9), fm(2.0)))
            p.SetSize(pcbnew.VECTOR2I(fm(1.5), fm(2.6)))
            slots += 1
    assert contacts == 2 and slots == 2, (ref, contacts, slots)

# 2. Return Q1, Q2, Q3, Q7, Q8, Q9 to machine SMT placement & restore paste
for ref in FETS:
    f = b.FindFootprintByReference(ref)
    f.SetExcludedFromPosFiles(False)
    f.SetLocalSolderPasteMarginRatio(None)
    for fld in f.GetFields():
        if fld.GetName() == "Assembly":
            fld.SetText("")

# 3. Thermal spokes on both pads of C7, C8, C15, C16, C17 and on J12.1
spoked = 0
for ref in CAPS:
    f = b.FindFootprintByReference(ref)
    for p in f.Pads():
        if p.GetNumber() in ("1", "2"):
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            spoked += 1
for p in b.FindFootprintByReference("J12").Pads():
    if p.GetNumber() == "1":
        p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        spoked += 1
assert spoked == 11, spoked

# 4. Move C8 reference out from under D2
c8_ref = b.FindFootprintByReference("C8").Reference()
c8_ref.SetPosition(pcbnew.VECTOR2I(fm(177.2), fm(144.5)))

# Refill zones and save PCB
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(board_path)

# Verify paste_margin_ratio -1 is gone on all 6 FETs
pcb_txt = open(board_path).read()
for ref in FETS:
    k = pcb_txt.index(f'(property "Reference" "{ref}"')
    end = pcb_txt.index("\n\t\t(pad ", k)
    assert "solder_paste_margin_ratio" not in pcb_txt[k:end], f"{ref} still has solder_paste_margin_ratio"

# 5. Schematic edits: title block, block notes, and removing Hand-solder from the six FETs
sch = open(sch_path).read()
assert '(rev "E")' in sch, "expected rev E in schematic"
assert "25 A supply" in sch, "expected 25 A supply in schematic"
assert "Five 470 uF 100 V bulk capacitors" in sch, "expected Five 470 uF in schematic"
assert "D12 clamps it under 15 V" in sch, "expected under 15 V in schematic"

sch = sch.replace('(date "2026-11-09")', '(date "2026-11-17")', 1)
sch = sch.replace('(rev "E")', '(rev "F")', 1)
sch = sch.replace("25 A supply", "27 A supply", 1)
sch = sch.replace("Five 470 uF 100 V bulk capacitors", "Four 470 uF 100 V bulk capacitors", 1)
sch = sch.replace("D12 clamps it under 15 V", "D12 clamps it under 17 V", 1)

removed_sch = 0
for ref in FETS:
    k = sch.index(f'(reference "{ref}")')
    i = sch.rindex("\n\t(symbol\n", 0, k)
    j = sch.index("\t\t(instances", i)
    blk = sch[i:j]
    blk2, cnt = re.subn(
        r'\t\t\(property "Assembly" "Hand-solder"\n(?:\t\t\t.*\n)*?\t\t\)\n',
        "",
        blk,
    )
    assert cnt == 1, (ref, cnt)
    sch = sch[:i] + blk2 + sch[j:]
    removed_sch += cnt
assert removed_sch == 6, removed_sch
open(sch_path, "w").write(sch)

# 6. Generator table (build_sch.py): remove note="Hand-solder" from the six FETs
gen_lines = open(gen_path).read().splitlines()
removed_gen = 0
for idx, line in enumerate(gen_lines):
    m = re.match(r'^part\("(Q[123789])",', line)
    if m:
        assert ', note="Hand-solder"' in line, line
        gen_lines[idx] = line.replace(', note="Hand-solder"', "")
        removed_gen += 1
assert removed_gen == 6, removed_gen
open(gen_path, "w").write("\n".join(gen_lines) + "\n")

print("Applied rev F fixes: J1/J5 holes & slots enlarged, 6 MOSFETs on SMT, 11 pads spoked, C8 label moved, schematic text updated.")
