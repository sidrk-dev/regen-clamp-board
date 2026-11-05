"""Give every top-layer GND fill island at least one via to the bottom plane."""
import sys, pcbnew
B = sys.argv[1]; mm = pcbnew.FromMM
b = pcbnew.LoadBoard(B)
gnd = b.FindNet("GND")
tracks = list(b.Tracks()); pads = [p for fp in b.Footprints() for p in fp.Pads()]
anchors = [t.GetPosition() for t in tracks if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND"]
anchors += [p.GetPosition() for p in pads if p.GetNetname() == "GND" and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
def clear(p, gap):
    if any(t.HitTest(p, gap + (t.GetWidth(pcbnew.F_Cu) if t.Type() == pcbnew.PCB_VIA_T else t.GetWidth()) // 2) for t in tracks): return False
    return not any(q.HitTest(p, gap) for q in pads)
bottom = [z for z in b.Zones() if z.GetNetname() == "GND" and z.GetLayer() == pcbnew.B_Cu][0].GetFilledPolysList(pcbnew.B_Cu)
added = 0
for z in [z for z in b.Zones() if z.GetNetname() == "GND" and z.GetLayer() == pcbnew.F_Cu]:
    polys = z.GetFilledPolysList(pcbnew.F_Cu)
    for i in range(polys.OutlineCount()):
        one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(polys.Outline(i))
        if any(one.Contains(a) for a in anchors): continue
        bb = polys.Outline(i).BBox(); done = False
        for x in range(bb.GetLeft(), bb.GetRight(), mm(0.25)):
            for y in range(bb.GetTop(), bb.GetBottom(), mm(0.25)):
                p = pcbnew.VECTOR2I(x, y)
                if one.Contains(p) and bottom.Contains(p) and clear(p, mm(0.6)):
                    v = pcbnew.PCB_VIA(b); v.SetPosition(p); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(gnd); b.Add(v)
                    added += 1; done = True; break
            if done: break
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(B, b); print("island vias", added)
