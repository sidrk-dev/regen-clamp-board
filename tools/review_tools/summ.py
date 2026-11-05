import sys,pcbnew,subprocess,re
board,out=sys.argv[1:3]
import re
LCSC={}
for m in re.finditer(r'part\("(\w+)",\s*"[^"]+",\s*"[^"]*",\s*(?:"[^"]*"|\w+),\s*"(C\d+)"',open(sys.argv[3]).read()): LCSC[m[1]]=m[2]
b=pcbnew.LoadBoard(board); to=pcbnew.ToMM; bb=b.GetBoardEdgesBoundingBox(); ox,oy=to(bb.GetX()),to(bb.GetY())
nets={}; L=[f"board {to(bb.GetWidth()):.1f} x {to(bb.GetHeight()):.1f} mm, origin at the top-left board corner, coordinates in mm"]
L2=["== footprints: ref value footprint LCSC x y rot; pad: number net x y sizeX sizeY drillX drillY"]
for f in sorted(b.GetFootprints(),key=lambda f:f.GetReference()):
    p=f.GetPosition(); lcsc=LCSC.get(f.GetReference(),"")
    L2.append(f"{f.GetReference()} | {f.GetValue()} | {f.GetFPID().GetUniStringLibId()} | {lcsc} | {to(p.x)-ox:.2f} {to(p.y)-oy:.2f} rot {f.GetOrientationDegrees():.0f}")
    for q in f.Pads():
        c=q.GetPosition(); L2.append(f"   {q.GetNumber() or '-'} {q.GetNetname() or '(none)'} {to(c.x)-ox:.2f} {to(c.y)-oy:.2f} {to(q.GetSizeX()):.2f} {to(q.GetSizeY()):.2f} {to(q.GetDrillSizeX()):.2f} {to(q.GetDrillSizeY()):.2f}")
        if q.GetNetname(): nets.setdefault(q.GetNetname(),[]).append(f"{f.GetReference()}.{q.GetNumber()}")
L2.append("== tracks: net layer x1 y1 x2 y2 width"); 
for t in b.GetTracks():
    s,e=t.GetStart(),t.GetEnd()
    if t.Type()==pcbnew.PCB_TRACE_T: L2.append(f"{t.GetNetname()} {b.GetLayerName(t.GetLayer())} {to(s.x)-ox:.2f} {to(s.y)-oy:.2f} {to(e.x)-ox:.2f} {to(e.y)-oy:.2f} {to(t.GetWidth()):.2f}")
L2.append("== via count by net")
vc={}
for t in b.GetTracks():
    if t.Type()==pcbnew.PCB_VIA_T: vc[t.GetNetname()]=vc.get(t.GetNetname(),0)+1
L2.append(str(vc))
L2.append("== zones: net layer rule_area bbox")
for z in b.Zones():
    bz=z.GetBoundingBox(); L2.append(f"{z.GetNetname()} {b.GetLayerName(z.GetLayer())} rule_area={z.GetIsRuleArea()} name={z.GetZoneName()} {to(bz.GetX())-ox:.1f} {to(bz.GetY())-oy:.1f} {to(bz.GetRight())-ox:.1f} {to(bz.GetBottom())-oy:.1f}")
open(out+"/board_summary.txt","w").write("\n".join(L+L2)+"\n")
with open(out+"/netlist.txt","w") as o:
    o.write("net: pins (reference.pad; pad numbers per the KiCad footprint)\n")
    for n,v in sorted(nets.items()): o.write(f"{n}: {' '.join(sorted(v))}\n")
