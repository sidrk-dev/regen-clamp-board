"""Move each footprint's reference text to the nearby spot that overlaps the least silkscreen, pads and board edge."""
import sys, pcbnew
B = sys.argv[1]; mm = pcbnew.FromMM
b = pcbnew.LoadBoard(B)
edge = b.GetBoardEdgesBoundingBox(); edge.Inflate(-mm(0.6))
pads = [p.GetBoundingBox() for fp in b.Footprints() for p in fp.Pads()]
for p in pads: p.Inflate(mm(0.2))
def silk_boxes(fp):
    out = []
    for g in fp.GraphicalItems():
        if g.GetLayer() == pcbnew.F_SilkS and g.Type() != pcbnew.PCB_TEXT_T:
            bb = g.GetBoundingBox(); bb.Inflate(mm(0.15)); out.append(bb)
    return out
fixed = [bb for fp in b.Footprints() for bb in silk_boxes(fp)]
for d in b.GetDrawings():
    if d.GetLayer() == pcbnew.F_SilkS: bb = d.GetBoundingBox(); bb.Inflate(mm(0.15)); fixed.append(bb)
# plain-language labels for the things you plug in, switch or watch (board mm from the top-left corner)
LABELS = [("PSU IN 15-48V", 9.5, 40.0), ("OUT1 ARM", 107.4, 30.75, 90), ("OUT2 GRIP", 107.4, 48.75, 90), ("OUT3 SPARE", 107.4, 66.75, 90),
          ("SUPPLY", 29.6, 51.6, 90), ("THERM OPEN", 35.8, 69.7),
          ("BRAKE RES", 104.0, 91.0), ("ON/OFF", 6.5, 80.6), ("BRAKE TRIM", 15.5, 87.6), ("THERM SW", 44.5, 66.2),
          ("LIVE", 34.0, 96.4), ("BRAKE", 44.0, 96.4)]
for t, x, y, *a in LABELS:
    if any(isinstance(d, pcbnew.PCB_TEXT) and d.GetText() == t for d in b.GetDrawings()): continue
    txt = pcbnew.PCB_TEXT(b); txt.SetText(t); txt.SetLayer(pcbnew.F_SilkS)
    txt.SetPosition(pcbnew.VECTOR2I(mm(100 + x), mm(100 + y)))
    txt.SetTextSize(pcbnew.VECTOR2I(mm(0.9), mm(0.9))); txt.SetTextThickness(mm(0.15)); txt.SetTextAngleDegrees(a[0] if a else 0); b.Add(txt); bb = txt.GetBoundingBox(); bb.Inflate(mm(0.2)); fixed.append(bb)
placed = []
def overlap(a, c):
    if not a.Intersects(c): return 0
    i = a.Intersect(c); return i.GetWidth() * 1e-6 * i.GetHeight() * 1e-6
def cost(bb):
    c = sum(overlap(bb, x) for x in pads) * 4 + sum(overlap(bb, x) for x in fixed) + sum(overlap(bb, x) for x in placed) * 4
    if not edge.Contains(bb.GetOrigin()) or not edge.Contains(bb.GetEnd()): c += 100
    return c
fps = sorted(b.Footprints(), key=lambda f: -f.GetBoundingBox(False).GetArea())
for fp in fps:
    r = fp.Value() if fp.GetReference().startswith("TP") else fp.Reference()
    if not r.IsVisible() or r.GetLayer() != pcbnew.F_SilkS: continue
    body = fp.GetBoundingBox(False); c = body.GetCenter()
    w, h = body.GetWidth(), body.GetHeight()
    best = None
    for horiz in (True, False):
        r.SetTextAngleDegrees(0 if horiz else 90)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1), (0, 0)):
            for gap in (0.7, 1.4, 2.4):
                tb = r.GetBoundingBox()
                x = c.x + dx * (w // 2 + tb.GetWidth() // 2 + mm(gap))
                y = c.y + dy * (h // 2 + tb.GetHeight() // 2 + mm(gap))
                r.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                k = cost(r.GetBoundingBox()) + gap * 0.01 + (0 if horiz else 0.005)
                if best is None or k < best[0]: best = (k, r.GetPosition(), r.GetTextAngleDegrees())
    r.SetTextAngleDegrees(best[2]); r.SetPosition(best[1]); placed.append(r.GetBoundingBox())
pcbnew.SaveBoard(B, b); print("placed", len(placed))
