"""2D sheet-current solver for KiCad copper pours. usage: sheet.py board.kicad_pcb [png_prefix]"""
import sys,math,numpy as np,pcbnew,scipy.sparse as sp,scipy.sparse.linalg as spl
from PIL import Image,ImageDraw
H=0.2  # mm grid
b=pcbnew.LoadBoard(sys.argv[1]); pref=sys.argv[2] if len(sys.argv)>2 else None
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
bb=b.GetBoardEdgesBoundingBox(); X0=pcbnew.ToMM(bb.GetX()); Y0=pcbnew.ToMM(bb.GetY())
NX=int(pcbnew.ToMM(bb.GetWidth())/H)+2; NY=int(pcbnew.ToMM(bb.GetHeight())/H)+2
def px(p): return ((pcbnew.ToMM(p.x)-X0)/H,(pcbnew.ToMM(p.y)-Y0)/H)
def polyset_draw(d,ps,val):
    for i in range(ps.OutlineCount()):
        o=ps.Outline(i); d.polygon([px(o.CPoint(k)) for k in range(o.PointCount())],fill=val)
        for j in range(ps.HoleCount(i)):
            h=ps.Hole(i,j); d.polygon([px(h.CPoint(k)) for k in range(h.PointCount())],fill=0)
def copper(net,layer):
    im=Image.new("L",(NX,NY),0); d=ImageDraw.Draw(im)
    for z in b.Zones():
        if z.GetNetname()==net and z.IsOnLayer(layer): polyset_draw(d,z.GetFilledPolysList(layer),1)
    for t in b.GetTracks():
        if t.GetNetname()!=net: continue
        if t.GetClass()=="PCB_TRACK" and t.GetLayer()==layer:
            d.line([px(t.GetStart()),px(t.GetEnd())],fill=1,width=max(1,int(round(pcbnew.ToMM(t.GetWidth())/H))))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname()==net and p.IsOnLayer(layer):
                ps=pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(ps,layer,0,pcbnew.FromMM(0.005),pcbnew.ERROR_INSIDE); polyset_draw(d,ps,1)
    return np.array(im,dtype=bool)
def padmask(ref,num,layer):
    im=Image.new("L",(NX,NY),0); d=ImageDraw.Draw(im)
    f=b.FindFootprintByReference(ref)
    for p in f.Pads():
        if p.GetNumber()==num:
            ps=pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(ps,layer,0,pcbnew.FromMM(0.005),pcbnew.ERROR_INSIDE); polyset_draw(d,ps,1)
    return np.array(im,dtype=bool)
def solve(cu,sources,sinks):
    import scipy.ndimage as ndi
    lab,_=ndi.label(cu); keep=set()
    for m,_a in sources: keep|=set(np.unique(lab[m&cu]))-{0}
    cu=np.isin(lab,list(keep))
    """sources: list of (mask, amps). sinks: list of masks held at 0 V. returns V, per-sink currents, J(A/mm)"""
    idx=-np.ones(cu.shape,int); fixed=np.zeros(cu.shape,bool)
    for m in sinks: fixed|=m&cu
    free=cu&~fixed; idx[free]=np.arange(free.sum()); n=free.sum()
    rows=[];cols=[];vals=[]; diag=np.zeros(n); rhs=np.zeros(n)
    for dy,dx in ((0,1),(1,0)):
        a=cu[:cu.shape[0]-dy,:cu.shape[1]-dx]&cu[dy:,dx:]
        ia=idx[:cu.shape[0]-dy,:cu.shape[1]-dx][a]; ib=idx[dy:,dx:][a]
        for u,v in ((ia,ib),(ib,ia)):
            ok=u>=0; np.add.at(diag,u[ok],1); okb=ok&(v>=0); rows+= [u[okb]]; cols+=[v[okb]]; vals+=[-np.ones(okb.sum())]
    for m,amps in sources:
        mm=m&free; k=mm.sum(); rhs[idx[mm]]+=amps/k
    A=sp.csr_matrix((np.concatenate(vals+[diag]),(np.concatenate(rows+[np.arange(n)]),np.concatenate(cols+[np.arange(n)]))),shape=(n,n))
    x=spl.spsolve(A.tocsc(),rhs)
    V=np.zeros(cu.shape); V[free]=x
    # current per edge = dV (unit sheet). J per mm = |grad V|/H
    gx=np.zeros(cu.shape); gy=np.zeros(cu.shape)
    ex=cu[:,:-1]&cu[:,1:]; dvx=(V[:,:-1]-V[:,1:])*ex
    ey=cu[:-1,:]&cu[1:,:]; dvy=(V[:-1,:]-V[1:,:])*ey
    gx[:,:-1]+=dvx/2; gx[:,1:]+=dvx/2; gy[:-1,:]+=dvy/2; gy[1:,:]+=dvy/2
    J=np.hypot(gx,gy)/H
    sinkI=[]
    for m in sinks:
        mm=m&cu; nb=np.zeros(cu.shape)
        # current into sink = sum over edges from free neighbour into sink of V_free
        tot=0
        for dy,dx in ((0,1),(1,0),(0,-1),(-1,0)):
            sh=np.roll(np.roll(V,dy,0),dx,1); shc=np.roll(np.roll(cu&~mm,dy,0),dx,1)
            tot+=(sh*(mm&shc)).sum()
        sinkI.append(tot)
    return V,sinkI,J,cu
def report(name,cu,sources,sinks,exclude_r=4.0,oz=(1,2)):
    V,si,J,cu=solve(cu,sources,sinks)
    I=sum(a for _,a in sources)
    yy,xx=np.mgrid[0:cu.shape[0],0:cu.shape[1]]
    ex=np.zeros(cu.shape,bool)
    for m in [m for m,_ in sources]+sinks:
        ys,xs=np.nonzero(m)
        if len(ys)==0: continue
        cy,cx=ys.mean(),xs.mean(); r=exclude_r/H+max(np.ptp(ys),np.ptp(xs))/2
        ex|=(yy-cy)**2+(xx-cx)**2<r*r
    Jin=J[cu&~ex]
    Rsq=sum(V[m&cu].mean()*a for m,a in sources)/I/I  # squares (source-weighted)
    out=f"{name}: I={I:.1f}A  Jmax(away from pads)={Jin.max():.2f} A/mm  J99.9%={np.percentile(Jin,99.9):.2f}  -> eq width {I/Jin.max():.1f} mm ; squares={Rsq:.2f}"
    for o in oz:
        r=Rsq*0.5e-3/o*1.25; out+=f" | {o}oz: R={r*1e3:.2f} mOhm, P={I*I*r:.2f} W"
    if len(sinks)>1: out+="  sink split "+", ".join(f"{s/I*100:.1f}%" for s in si)
    print(out)
    if pref:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        Jm=np.where(cu,J,np.nan); fig=plt.figure(figsize=(12,9.6))
        plt.imshow(Jm,cmap="inferno",vmin=0,vmax=max(3,np.percentile(Jin,99.9)),extent=(X0,X0+NX*H,Y0+NY*H,Y0))
        plt.colorbar(label="A per mm of width"); plt.title(name); fig.savefig(f"{pref}_{name}.png",dpi=70,bbox_inches="tight"); plt.close(fig)
    return Jin.max()
F,B=pcbnew.F_Cu,pcbnew.B_Cu
outs=["J2","J3","J4"]
def R2(net,layer,a,b):
    cu=copper(net,layer); V,si,J,cu2=solve(cu,[(a,1.0)],[b]); return V[a&cu2].mean()
def share(net,layer,src,fets,rds=4.2e-3,oz=2):
    rsq=0.5e-3/oz*1.25; R=[R2(net,layer,src,f)*rsq for f in fets]; g=[1/(r+rds) for r in R]; return [x/sum(g) for x in g]
gnd=copper("GND",B); vout=copper("VOUT",F)
report("GND_30A_3outs",gnd,[(padmask(m,"1",B),10.0) for m in outs],[padmask("J1","1",B)])
for m in outs: report(f"GND_25A_{m}",gnd,[(padmask(m,"1",B),25.0)],[padmask("J1","1",B)])
report("VIN_30A",copper("VIN",F),[(padmask("J1","2",F),30.0)],[padmask("Q1","3",F),padmask("Q7","3",F)])
report("MID_30A",copper("MID",F),[(padmask("Q1","2",F),15.0),(padmask("Q7","2",F),15.0)],[padmask("Q2","2",F),padmask("Q8","2",F)])
report("VOUT_30A_3outs",vout,[(padmask(m,"2",F),10.0) for m in outs],[padmask("Q2","3",F),padmask("Q8","3",F)])
for m in outs: report(f"VOUT_25A_{m}",vout,[(padmask(m,"2",F),25.0)],[padmask("Q2","3",F),padmask("Q8","3",F)])
report("BRK_DRAIN_25A",copper("BRK_DRAIN",F),[(padmask("J5","1",F),25.0)],[padmask("Q3","2",F),padmask("Q9","2",F)])
report("VOUT_caps_to_brake_25A",vout,[(padmask(c,"1",F),25.0/4) for c in ("C7","C8","C15","C16")],[padmask("J5","2",F)])
print("share Q1/Q7",share("VIN",F,padmask("J1","2",F),[padmask("Q1","3",F),padmask("Q7","3",F)]))
print("share Q3/Q9",share("BRK_DRAIN",F,padmask("J5","1",F),[padmask("Q3","2",F),padmask("Q9","2",F)]))
for m in outs: print("share Q2/Q8 from",m,share("VOUT",F,padmask(m,"2",F),[padmask("Q2","3",F),padmask("Q8","3",F)]))
