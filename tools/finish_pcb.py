"""finish_pcb.py stage board.kicad_pcb [args]
stage=prep  : fill zones and export DSN (arg: dsn path)
stage=import: import SES, add GND stitching vias that pass DRC, refill (arg: ses path)
"""
import json, subprocess, sys, os, tempfile
import pcbnew

stage, path = sys.argv[1], sys.argv[2]
mm = pcbnew.FromMM
OX, OY = 100.0, 100.0

def fill(b):
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())

# top-layer power pours the router must not cut (track keepouts, removed after import)
KEEPOUTS = [
    [(2, 2), (42.5, 2), (42.5, 40.0), (36, 46.5), (31, 46.5), (31, 58.5), (2, 58.5)],
    [(43.5, 2), (72.5, 2), (72.5, 39.5), (65, 39.5), (65, 45.95), (60.9, 45.95), (60.9, 44.9), (60.5, 44.9), (60.5, 39.5), (43.5, 39.5)],
    [(74, 2), (123, 2), (123, 98), (87.5, 98), (87.5, 57), (74, 57)],
    [(69.5, 57.8), (86.5, 57.8), (86.5, 99), (69.5, 99)],
]
# pads inside those pours that belong to another net: fixed stub + via, direction (dx, dy)
STUBS = [("D8", "1", (0, 1)), ("C1", "2", (1, 0)), ("C2", "2", (1, 0)), ("C6", "2", (0, 1))]

# hand routes for the LM74800 pins the autorouter cannot fan out: (net, layer, [points]), vias at "V"
HAND = [
    ("VIN", "F", [(55.59, 45.25), (55.59, 45.75)]),
    # rev C: VIN to U1 on the top layer (no bottom-layer cut across the ground return)
    ("VIN", "F", [(55.59, 45.5), (54.3, 45.5), (53.8, 45.0), (30.0, 45.0)]),
    ("VOUT", "f", [(58.41, 46.25), (61.1, 46.25)]), ("VOUT", "V", (61.1, 46.25)),
    ("VOUT", "B", [(61.1, 46.25), (75.5, 46.25)]), ("VOUT", "V", (75.5, 46.25)),
    # rev C: gate nets on the top layer through the gaps between the VIN/MID/VOUT pours, one 10 R per FET
    ("DG1", "G", [(41.0, 20.125), (41.0, 11.5), (38.9, 11.5)]),
    ("DG7", "G", [(41.0, 25.875), (41.0, 29.5), (38.9, 29.5)]),
    ("DGATE", "G", [(41.0, 21.675), (41.0, 24.325)]),
    ("DGATE", "G", [(41.0, 23.0), (43.0, 23.0), (43.0, 39.2), (45.3, 41.5), (52.0, 41.5)]),
    ("HG2", "G", [(75.0, 20.125), (75.0, 16.5), (77.1, 16.5)]),
    ("HG8", "G", [(75.0, 25.875), (75.0, 34.5), (77.1, 34.5)]),
    ("HGATE", "G", [(75.0, 21.675), (75.0, 24.325)]),
    ("HGATE", "G", [(75.0, 23.0), (73.25, 23.0), (73.25, 39.2), (69.0, 43.45), (67.0, 45.45), (67.0, 48.0)]),
    # DGATE fan-out to TP6, then under U1 to the interlock's R34: the router sometimes leaves this one open
    ("DGATE", "F", [(55.59, 44.75), (55.0, 44.75), (55.0, 43.86), (53.70, 42.56), (53.06, 42.56), (52.0, 41.5)]),
    ("DGATE", "V", (53.70, 42.56)), ("DGATE", "b", [(53.70, 42.56), (56.63, 45.49), (56.63, 54.46)]), ("DGATE", "V", (56.63, 54.46)),
    ("DGATE", "F", [(56.63, 54.46), (56.63, 61.19), (55.80, 62.025)]),
    # D11 clamps HGATE to OUT right beside U1
    ("VOUT", "F", [(61.1, 46.25), (61.75, 47.05)]), ("HGATE", "F", [(65.05, 47.05), (67.0, 47.05)]),
    ("HGATE", "f", [(58.41, 46.75), (59.0, 46.75), (59.1, 46.85), (60.3, 46.85), (60.3, 48.3)]),
    ("HGATE", "F", [(60.3, 48.3), (65.05, 48.3), (65.05, 47.05)]), ("HGATE", "F", [(64.175, 48.3), (64.175, 52.5)]),
    # TVS returns: three vias, not one, so the clamp's pulse has a low-inductance path that a fault won't burn open
    ("GND", "W", [(27.4, 13.0), (27.4, 15.7)]), ("GND", "W", [(26.3, 15.7), (28.5, 15.7)]),
    ("GND", "V8", (26.3, 15.7)), ("GND", "V8", (27.4, 15.7)), ("GND", "V8", (28.5, 15.7)),
    ("GND", "W", [(88.4, 52.0), (88.4, 54.7)]), ("GND", "W", [(87.3, 54.7), (89.5, 54.7)]),
    ("GND", "V8", (87.3, 54.7)), ("GND", "V8", (88.4, 54.7)), ("GND", "V8", (89.5, 54.7)),
    # MID (pin 12) up and into the MID pour; CAP (pin 11) to C3 top pad; VS (pin 10) to C3 bottom pad and the pour
    ("MID", "f", [(58.41, 44.75), (58.41, 43.1), (60.8, 43.1)]),
    ("CAP", "f", [(58.41, 45.25), (58.95, 45.25), (59.2, 44.6), (59.6, 44.0)]),
    ("MID", "f", [(58.41, 45.75), (60.0, 45.75)]), ("MID", "f", [(60.0, 45.525), (61.3, 45.525), (62.0, 44.9)]),
    # small-signal VIN / VOUT taps back to the pours on the bottom layer
    ("VIN", "F", [(48.175, 50.0), (47.3, 50.0), (47.3, 45.0)]),
    # rev D: supply LED (R36 -> D8) sits inside the VIN pour, where the router may not draw tracks
    ("LEDV_A", "F", [(26.0, 49.45), (26.0, 51.21)]),
    # rev C: VIN to the interlock PNP's base (Q10 pin 1)
    ("VIN", "F", [(47.3, 50.0), (47.3, 57.0), (49.2, 58.9), (51.06, 58.9), (51.06, 60.25)]),
    ("VIN", "F", [(30.175, 82.0), (29.3, 82.0)]), ("VIN", "V", (29.3, 82.0)),
    ("VIN", "B", [(29.3, 82.0), (27.0, 84.5), (8.0, 84.5), (8.0, 60.0), (9.8, 58.2)]), ("VIN", "V", (9.8, 58.2)),
    ("VOUT", "F", [(30.175, 72.0), (29.3, 72.0)]), ("VOUT", "V", (29.3, 72.0)),
    ("VOUT", "B", [(29.3, 72.0), (44.0, 57.3), (79.0, 55.0)]), ("VOUT", "V", (79.0, 55.0)),
    ("VOUT", "F", [(21.04, 61.5), (19.9, 61.5)]), ("VOUT", "V", (19.9, 61.5)),
    ("VOUT", "B", [(19.9, 61.5), (28.0, 70.7), (29.3, 72.0)]),
    ("VOUT", "F", [(10.54, 64.0), (9.3, 64.0)]), ("VOUT", "V", (9.3, 64.0)),
    ("VOUT", "B", [(9.3, 64.0), (11.8, 61.5), (19.9, 61.5)]),
    ("GND", "F", [(33.062, 94.0), (33.062, 95.9)]), ("GND", "V", (33.062, 95.9)),
    ("GND", "F", [(18.0, 69.225), (18.0, 67.9)]), ("GND", "V", (18.0, 67.9)),
    ("GND", "F", [(67.8, 57.55), (66.4, 56.7)]), ("GND", "V", (66.4, 56.7)),
    # brake MOSFET sources: via arrays straight into the ground plane for the brake pulses
    ("GND", "W", [(64.89, 82.54), (64.89, 84.6)]),
    ("GND", "V8", (63.4, 84.6)), ("GND", "V8", (64.5, 84.6)), ("GND", "V8", (65.6, 84.6)),
    ("GND", "V8", (63.4, 85.8)), ("GND", "V8", (64.5, 85.8)), ("GND", "V8", (65.6, 85.8)),
    ("GND", "W", [(64.89, 68.54), (64.89, 70.6)]),
    ("GND", "V8", (63.4, 70.6)), ("GND", "V8", (64.5, 70.6)), ("GND", "V8", (65.6, 70.6)),
    ("GND", "V8", (63.4, 71.8)), ("GND", "V8", (64.5, 71.8)), ("GND", "V8", (65.6, 71.8)),
]

def hand_routes(b):
    for net, layer, pts in HAND:
        n = b.FindNet(net)
        if layer in ("V", "V8"):
            big = layer == "V8"
            v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(mm(OX + pts[0]), mm(OY + pts[1])))
            v.SetWidth(mm(0.8 if big else 0.6)); v.SetDrill(mm(0.4 if big else 0.3)); v.SetNet(n); v.SetLocked(True); b.Add(v); continue
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(OX + x0), mm(OY + y0)))
            t.SetEnd(pcbnew.VECTOR2I(mm(OX + x1), mm(OY + y1))); t.SetWidth({"F": mm(0.2), "f": mm(0.16), "B": mm(0.4), "b": mm(0.2), "W": mm(1.5), "G": mm(0.3)}[layer])
            t.SetLayer(pcbnew.B_Cu if layer in "Bb" else pcbnew.F_Cu); t.SetNet(n); t.SetLocked(True); b.Add(t)

def prep(b):
    hand_routes(b)
    for ref, padnum, (dx, dy) in STUBS:
        pad = b.FindFootprintByReference(ref).FindPadByNumber(padnum)
        c = pad.GetPosition(); bb = pad.GetBoundingBox()
        half = (bb.GetWidth() if dx else bb.GetHeight()) / 2
        off = half + mm(0.9)
        end = pcbnew.VECTOR2I(int(c.x + dx * off), int(c.y + dy * off))
        t = pcbnew.PCB_TRACK(b); t.SetStart(c); t.SetEnd(end); t.SetWidth(mm(0.5)); t.SetLayer(pcbnew.F_Cu)
        t.SetNet(pad.GetNet()); t.SetLocked(True); b.Add(t)
        v = pcbnew.PCB_VIA(b); v.SetPosition(end); v.SetWidth(mm(0.8)); v.SetDrill(mm(0.4)); v.SetNet(pad.GetNet())
        v.SetLocked(True); b.Add(v)
    for poly in KEEPOUTS:
        z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetLayer(pcbnew.F_Cu)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(False); z.SetDoNotAllowPads(False)
        z.SetDoNotAllowZoneFills(False); z.SetDoNotAllowFootprints(False); z.SetZoneName("router_keepout")
        o = z.Outline(); o.NewOutline()
        for x, y in poly: o.Append(mm(OX + x), mm(OY + y))
        b.Add(z)

if stage == "prep":
    b = pcbnew.LoadBoard(path); prep(b); fill(b); pcbnew.SaveBoard(path, b)
    assert pcbnew.ExportSpecctraDSN(b, sys.argv[3])
    sys.exit(0)

if stage == "import":
    b = pcbnew.LoadBoard(path)
    assert pcbnew.ImportSpecctraSES(b, sys.argv[3])
    for t in list(b.Tracks()):
        if t.Type() == pcbnew.PCB_TRACE_T and t.GetWidth() < mm(0.16): t.SetWidth(mm(0.16))
    for z in [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() == "router_keepout"]:
        b.Remove(z)
    pcbnew.SaveBoard(path, b)
    sys.exit(0)

if stage == "stitch":
    # stitch the top ground fill (control area) and the board margins to the bottom plane
    b = pcbnew.LoadBoard(path)
    gnd = b.FindNet("GND")
    cands = [(x / 2, y / 2) for x in range(5, 136, 5) for y in range(123, 198, 5)]
    cands += [(x, 98.0) for x in range(70, 121, 5)] + [(1.6, y) for y in range(8, 96, 6)]
    tracks = list(b.Tracks()); pads = [p for fp in b.Footprints() for p in fp.Pads()]
    def clear_of_copper(p, gap):
        if any(t.HitTest(p, gap + t.GetWidth() // 2) for t in tracks): return False
        return not any(pad.HitTest(p, gap) for pad in pads)
    n = 0
    for x, y in cands:
        p = pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
        if not clear_of_copper(p, mm(0.75)): continue
        v = pcbnew.PCB_VIA(b); v.SetPosition(p); v.SetWidth(mm(0.7)); v.SetDrill(mm(0.35)); v.SetNet(gnd); b.Add(v); n += 1
    fill(b); pcbnew.SaveBoard(path, b); print("stitching vias added:", n)
    sys.exit(0)

if stage == "clean":
    # remove GND stitching vias listed by the DRC pass, then refill
    bad = {tuple(x) for x in json.load(open(sys.argv[3]))}
    b = pcbnew.LoadBoard(path)
    for t in list(b.Tracks()):
        if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND" and not t.IsLocked():
            p = t.GetPosition()
            if (round(pcbnew.ToMM(p.x), 2), round(pcbnew.ToMM(p.y), 2)) in bad: b.Delete(t)
    fill(b); pcbnew.SaveBoard(path, b); print("removed", len(bad))
