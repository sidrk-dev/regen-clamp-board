"""Remove router dead-end stubs. A segment goes only if its free end touches nothing else; any new open net restores the board."""
import json, shutil, subprocess, sys, pcbnew
B, SP = sys.argv[1], sys.argv[2]
mm = pcbnew.FromMM
def drc():
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "-o", f"{SP}/prune.json", B], capture_output=True)
    return json.load(open(f"{SP}/prune.json"))
shutil.copy(B, f"{SP}/before_prune.kicad_pcb")
start = len(drc()["unconnected_items"])
for _ in range(8):
    d = drc()
    if len(d["unconnected_items"]) > start:
        shutil.copy(f"{SP}/before_prune.kicad_pcb", B); print("prune restored: it opened a net"); break
    pts = [i["pos"] for v in d["violations"] if v["type"] == "track_dangling" for i in v["items"]]
    if not pts: break
    b = pcbnew.LoadBoard(B); n = 0
    tracks = [t for t in b.Tracks() if t.Type() == pcbnew.PCB_TRACE_T]
    pads = [p for f in b.Footprints() for p in f.Pads()]
    vias = [t for t in b.Tracks() if t.Type() == pcbnew.PCB_VIA_T]
    for p in pts:
        q = pcbnew.VECTOR2I(mm(p["x"]), mm(p["y"]))
        near = lambda a: abs(a.x - q.x) < mm(0.01) and abs(a.y - q.y) < mm(0.01)
        on_pad = any(x.HitTest(q) for x in pads) or any(x.HitTest(q) for x in vias)
        for t in [t for t in tracks if (near(t.GetStart()) or near(t.GetEnd())) and not t.IsLocked()]:
            far = t.GetEnd() if near(t.GetStart()) else t.GetStart()
            # free end: the reported point itself, or (when that point is a pad) the segment's far end
            end = far if on_pad else q
            joined = [o for o in tracks if o != t and (o.GetStart() == end or o.GetEnd() == end)]
            if joined or any(x.HitTest(end) for x in pads) or any(x.HitTest(end) for x in vias): continue
            b.Delete(t); tracks.remove(t); n += 1
    if not n: break
    pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(B, b); print("pruned", n)
