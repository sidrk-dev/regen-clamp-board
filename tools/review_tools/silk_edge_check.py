#!/usr/bin/env python3
"""Every visible silkscreen item must sit at least MIN mm inside the board outline.
usage: silk_edge_check.py board.kicad_pcb [min_mm=0.1]   (exit 0 pass, 1 fail)
KiCad's DRC only reports silkscreen that crosses the edge; a legend 0.08 mm inside it passed DRC and would have been
trimmed by the fab's routing tolerance (independent review, 15 Nov 2026). The outline is treated as its bounding box."""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM; MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1
e = b.GetBoardEdgesBoundingBox(); X0, Y0, X1, Y1 = mm(e.GetX()) + 0.05, mm(e.GetY()) + 0.05, mm(e.GetRight()) - 0.05, mm(e.GetBottom()) - 0.05
SILK = (pcbnew.F_SilkS, pcbnew.B_SilkS); bad = []; n = 0
def test(item, what):
    global n
    if item.GetLayer() not in SILK: return
    if hasattr(item, "IsVisible") and not item.IsVisible(): return
    q = item.GetBoundingBox(); n += 1
    d = min(mm(q.GetX()) - X0, mm(q.GetY()) - Y0, X1 - mm(q.GetRight()), Y1 - mm(q.GetBottom()))
    if d < MIN - 1e-6: bad.append(f"{what}: {d:.2f} mm from the board edge")
for d in b.GetDrawings(): test(d, f"{d.GetClass()} '{d.GetText().splitlines()[0][:30]}'" if d.GetClass() == "PCB_TEXT" else d.GetClass())
for f in b.GetFootprints():
    for g in f.GraphicalItems(): test(g, f"{f.GetReference()} outline")
    for t in f.GetFields(): test(t, f"{f.GetReference()} text '{t.GetText()[:20]}'")
for x in bad: print("FAIL", x)
print(("FAIL" if bad else "PASS") + f": {n} silkscreen items, {len(bad)} closer than {MIN} mm to the board edge")
sys.exit(1 if bad else 0)
