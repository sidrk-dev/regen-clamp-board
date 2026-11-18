#!/usr/bin/env python3
"""Every pad on a net that can pass 50 V must be at least MIN mm from ground copper (pours, pads, tracks, vias).
usage: bus_clearance_check.py board.kicad_pcb [min_mm=0.5]   (exit 0 pass, 1 fail)
IPC-2221B table 6-1, uncoated terminations: 0.4 mm at 31-50 V, 0.5 mm at 51-100 V. U1's own pads are exempt: its
0.25 mm pad gaps are fixed by the package. Independent of KiCad's DRC: the pad outline is grown by MIN and
intersected with the ground copper on each layer."""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm, fm = pcbnew.ToMM, pcbnew.FromMM; MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
BUS = {"VIN", "VOUT", "MID", "BRK_DRAIN", "DGATE", "DG1", "DG7", "HGATE", "HG2", "HG8", "CAP", "CDVDT", "RAIL_C", "ILK_E", "OV_TOP"}
bad = []; n = 0; worst = 99.0
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    gnd = pcbnew.SHAPE_POLY_SET()
    for z in b.Zones():
        if z.GetNetname() == "GND" and z.IsOnLayer(layer): gnd.Append(z.GetFilledPolysList(layer))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == "GND" and p.IsOnLayer(layer): p.TransformShapeToPolygon(gnd, layer, 0, fm(0.005), pcbnew.ERROR_OUTSIDE)
    for t in b.GetTracks():
        if t.GetNetname() == "GND" and t.IsOnLayer(layer): t.TransformShapeToPolygon(gnd, layer, 0, fm(0.005), pcbnew.ERROR_OUTSIDE)
    gnd.Simplify()
    for f in b.GetFootprints():
        if f.GetReference() == "U1": continue
        for p in f.Pads():
            if p.GetNetname() not in BUS or not p.IsOnLayer(layer): continue
            n += 1
            # largest growth of the pad that still misses ground copper, searched in 0.05 mm steps from MIN downwards
            g = MIN
            while g > 0:
                s = pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(s, layer, fm(g - 0.002), fm(0.005), pcbnew.ERROR_OUTSIDE)
                s.BooleanIntersection(gnd)
                if s.Area() < 1e3: break          # under 0.001 mm2 of overlap, in nm2
                g -= 0.05
            worst = min(worst, g)
            if g < MIN - 1e-9: bad.append(f"{f.GetReference()}.{p.GetNumber()} [{p.GetNetname()}] on {b.GetLayerName(layer)}: under {g + 0.05:.2f} mm from ground copper")
for x in bad: print("FAIL", x)
print(("FAIL" if bad else "PASS") + f": {n} bus-voltage pads checked on both layers, {len(bad)} closer than {MIN} mm to ground copper")
sys.exit(1 if bad else 0)
