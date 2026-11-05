import json, sys, pcbnew
B, drc = sys.argv[1], sys.argv[2]
mm = pcbnew.FromMM
d = json.load(open(drc))
bad = {(round(i["pos"]["x"], 2), round(i["pos"]["y"], 2)) for v in d["violations"] if v["type"] == "via_dangling" for i in v["items"]}
b = pcbnew.LoadBoard(B)
for fp in b.Footprints():
    r = fp.Reference()
    r.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); r.SetTextThickness(mm(0.12))
    if fp.GetReference().startswith("H") or fp.GetReference().startswith("FID"): r.SetVisible(False)
for t in [t for t in b.Tracks() if t.Type() == pcbnew.PCB_VIA_T and not t.IsLocked()
          and (round(pcbnew.ToMM(t.GetPosition().x), 2), round(pcbnew.ToMM(t.GetPosition().y), 2)) in bad]:
    b.Delete(t)
# dangling stubs the router left behind
for i in [i for v in d["violations"] if v["type"] == "track_dangling" for i in v["items"]]:
    x, y = mm(i["pos"]["x"]), mm(i["pos"]["y"])
    near = lambda q: abs(q.x - x) < mm(0.01) and abs(q.y - y) < mm(0.01)
    for t in [t for t in b.Tracks() if t.Type() == pcbnew.PCB_TRACE_T and not t.IsLocked() and (near(t.GetStart()) or near(t.GetEnd()))]:
        b.Delete(t)
# board label on the bottom silkscreen
txt = pcbnew.PCB_TEXT(b); txt.SetText("REGEN CLAMP + SOFT START  rev E\n15-48V, 30A board target, XT30 15A each, brake R >= Vin/20A\nSW1 OFF before plugging motors\nRV1 sets brake: VOUT-VIN = 0.667 x TP9 - 0.14V")
txt.SetLayer(pcbnew.B_SilkS); txt.SetPosition(pcbnew.VECTOR2I(mm(130), mm(112))); txt.SetMirrored(True)
txt.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2))); txt.SetTextThickness(mm(0.18)); b.Add(txt)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(B, b); print("removed", len(bad))
