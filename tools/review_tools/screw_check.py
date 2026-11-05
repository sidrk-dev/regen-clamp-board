import sys,math,pcbnew
b=pcbnew.LoadBoard(sys.argv[1]); mm=pcbnew.FromMM; to=pcbnew.ToMM
# refill zones so copper is what the fab will get
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
holes={f.GetReference():f.GetPosition() for f in b.GetFootprints() if f.GetReference().startswith("H")}
org=b.GetBoardEdgesBoundingBox()
for ref,c in sorted(holes.items()):
    for layer,name in ((pcbnew.F_Cu,"F"),(pcbnew.B_Cu,"B")):
        best=1e9; what=None
        for z in b.Zones():
            if z.GetIsRuleArea() or not z.IsOnLayer(layer): continue
            poly=z.GetFilledPolysList(layer)
            for i in range(poly.OutlineCount()):
                o=poly.Outline(i)
                for k in range(o.PointCount()):
                    p=o.CPoint(k); d=math.hypot(to(p.x-c.x),to(p.y-c.y))
                    if d<best: best=d; what="zone "+z.GetNetname()
        for t in b.GetTracks():
            if t.IsOnLayer(layer):
                for p in (t.GetStart(),t.GetEnd()):
                    d=math.hypot(to(p.x-c.x),to(p.y-c.y))-to(t.GetWidth())/2
                    if d<best: best=d; what="track/via "+t.GetNetname()
        for f in b.GetFootprints():
            if f.GetReference()==ref: continue
            for pad in f.Pads():
                if pad.IsOnLayer(layer):
                    p=pad.GetPosition(); d=math.hypot(to(p.x-c.x),to(p.y-c.y))-max(to(pad.GetSizeX()),to(pad.GetSizeY()))/2
                    if d<best: best=d; what="pad "+f.GetReference()
        print(f"{ref} {name}: nearest copper {best:.2f} mm from hole centre ({what})")
    f=[x for x in b.GetFootprints() if x.GetReference()==ref][0]; pad=list(f.Pads())
    print("   hole",[(to(p.GetDrillSizeX()),p.GetAttribute()) for p in pad])
