#!/usr/bin/env python3
"""Copper resistance and steady-state heating of the power path, straight from the board file.
usage: copper_check.py board.kicad_pcb out_dir [copper_um=35] [amps=27]
A finite-difference sheet model: every filled zone, pad and track of a power net is rasterised on both layers,
through-hole pads and vias tie the layers together, and a nodal solve gives the voltage and current density.
A second solve spreads the copper and MOSFET heat through the board (copper + FR-4 in plane, convection off both faces).
This is a calculation, not a measurement: it ignores airflow, the connectors and capacitors as heat sinks, and wiring."""
import sys, json, math, pcbnew
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spl
from PIL import Image, ImageDraw

board_path, out = sys.argv[1], sys.argv[2]
T_CU = float(sys.argv[3]) * 1e-6 if len(sys.argv) > 3 else 35e-6
AMPS = float(sys.argv[4]) if len(sys.argv) > 4 else 27.0
H = 0.2                      # grid pitch, mm
RHO = 1.72e-8 * (1 + 0.0039 * 40)   # copper at 60 C, ohm m
RS = RHO / T_CU              # ohm per square
RDS_HOT = 4.2e-3 * 1.6       # CRSS042N10N: 4.2 mohm max at 25 C, x1.6 at about 100 C
H_CONV = 10.0                # W/m2K per face: still air plus radiation
K_CU, K_FR4, T_FR4 = 390.0, 0.5, 1.6e-3

b = pcbnew.LoadBoard(board_path); mm = pcbnew.ToMM
bb = b.GetBoardEdgesBoundingBox()
X0, Y0 = mm(bb.GetX()), mm(bb.GetY()); NX, NY = int(mm(bb.GetWidth()) / H) + 1, int(mm(bb.GetHeight()) / H) + 1
LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
px = lambda x, y: ((x - X0) / H, (y - Y0) / H)

def chain(c): return [px(mm(c.CPoint(i).x), mm(c.CPoint(i).y)) for i in range(c.PointCount())]
def pad_shape(d, p, val):
    q = p.GetBoundingBox(); x0, y0 = px(mm(q.GetX()), mm(q.GetY())); x1, y1 = px(mm(q.GetRight()), mm(q.GetBottom()))
    (d.ellipse if p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE else d.rectangle)([x0, y0, x1, y1], fill=val)
def pad_on(p, layer): return p.IsOnLayer(layer)

def copper(net, layer):
    """Boolean raster of one net's copper on one layer (net=None: every net)."""
    im = Image.new("L", (NX, NY), 0); d = ImageDraw.Draw(im)
    for z in b.Zones():
        if not z.GetNetname() or (net and z.GetNetname() != net) or not z.IsOnLayer(layer): continue
        ps = z.GetFilledPolysList(layer)
        for i in range(ps.OutlineCount()):
            d.polygon(chain(ps.Outline(i)), fill=1)
            for j in range(ps.HoleCount(i)): d.polygon(chain(ps.Hole(i, j)), fill=0)
    for t in b.GetTracks():
        if net and t.GetNetname() != net: continue
        if t.GetClass() == "PCB_VIA":
            x, y = px(mm(t.GetPosition().x), mm(t.GetPosition().y)); r = mm(t.GetWidth(layer)) / 2 / H
            d.ellipse([x - r, y - r, x + r, y + r], fill=1)
        elif t.GetLayer() == layer:
            a, e = t.GetStart(), t.GetEnd()
            d.line([px(mm(a.x), mm(a.y)), px(mm(e.x), mm(e.y))], fill=1, width=max(1, round(mm(t.GetWidth()) / H)))
    for f in b.GetFootprints():
        for p in f.Pads():
            if (not net or p.GetNetname() == net) and p.GetNetname() and pad_on(p, layer): pad_shape(d, p, 1)
    return np.array(im, dtype=bool)

def pad_cells(ref, num, layer):
    im = Image.new("L", (NX, NY), 0); d = ImageDraw.Draw(im)
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num and pad_on(p, layer): pad_shape(d, p, 1)
    return np.array(im, dtype=bool)

def solve(net, terminals):
    """terminals: [((ref, pad), amps)], positive = current enters the copper there; the last one is the reference."""
    masks = [copper(net, l) for l in LAYERS]
    idx = [-np.ones((NY, NX), dtype=np.int64) for _ in LAYERS]; n = 0
    for k, m in enumerate(masks):
        c = int(m.sum()); idx[k][m] = np.arange(n, n + c); n += c
    rows, cols, vals = [], [], []
    def link(a, c, g):
        rows.extend([a, c, a, c]); cols.extend([c, a, a, c]); vals.extend([np.full(a.shape, -g)] * 2 + [np.full(a.shape, g)] * 2)
    G = 1 / RS
    for k in range(2):
        I = idx[k]
        for A, B in ((I[:, :-1], I[:, 1:]), (I[:-1, :], I[1:, :])):
            ok = (A >= 0) & (B >= 0); link(A[ok], B[ok], G)
    # plated holes: through-hole pads and vias join the two layers
    tie = Image.new("L", (NX, NY), 0); d = ImageDraw.Draw(tie)
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == net and p.GetDrillSizeX() > 0: pad_shape(d, p, 1)
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetname() == net:
            x, y = px(mm(t.GetPosition().x), mm(t.GetPosition().y)); r = max(1.0, mm(t.GetDrill()) / 2 / H)
            d.ellipse([x - r, y - r, x + r, y + r], fill=1)
    tie = np.array(tie, dtype=bool) & masks[0] & masks[1]
    link(idx[0][tie], idx[1][tie], 50 * G)
    cur = np.zeros(n + len(terminals))
    for ti, ((ref, num), amps) in enumerate(terminals):
        node = n + ti; cells = np.concatenate([idx[k][pad_cells(ref, num, l) & masks[k]] for k, l in enumerate(LAYERS)])
        assert len(cells), (net, ref, num)
        link(cells, np.full(cells.shape, node), 1e4 * G); cur[node] = amps
    N = n + len(terminals)
    A = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(N, N)) + sp.identity(N) * (G * 1e-9)   # tiny leak: copper islands that touch nothing stay solvable
    v = np.zeros(N); v[:-1] = spl.spsolve(A[:-1, :-1].tocsc(), cur[:-1])
    heat = np.zeros((NY, NX)); jmax = (0, None)
    for k in range(2):
        I = idx[k]; V = np.where(I >= 0, v[np.clip(I, 0, None)], np.nan)
        jx = np.zeros((NY, NX)); jy = np.zeros((NY, NX))
        dx = (V[:, :-1] - V[:, 1:]) * G; dy = (V[:-1, :] - V[1:, :]) * G      # amps through one cell edge
        dx = np.nan_to_num(dx); dy = np.nan_to_num(dy)
        heat[:, :-1] += dx ** 2 * RS / 2; heat[:, 1:] += dx ** 2 * RS / 2
        heat[:-1, :] += dy ** 2 * RS / 2; heat[1:, :] += dy ** 2 * RS / 2
        jx[:, :-1] = np.abs(dx); jy[:-1, :] = np.abs(dy)
        j = np.hypot(jx, jy) / H                                               # A per mm of width
        for (ref, num), _ in terminals:                                        # ignore the current crowding inside the terminal pads
            j[pad_cells(ref, num, LAYERS[k])] = 0
        m = np.unravel_index(np.argmax(j), j.shape)
        if j[m] > jmax[0]: jmax = (float(j[m]), (round(float(X0 + m[1] * H), 1), round(float(Y0 + m[0] * H), 1), "FB"[k]))
    tv = v[n:]; ins = [t for t in range(len(terminals)) if terminals[t][1] > 0]; outs = [t for t in range(len(terminals)) if terminals[t][1] < 0]
    itot = sum(terminals[t][1] for t in ins); p = float(sum(tv[t] * terminals[t][1] for t in range(len(terminals))))
    return dict(net=net, amps=itot, drop_mV=1e3 * p / itot, r_mohm=1e3 * p / itot ** 2, watts=p,
                j_max_A_per_mm=jmax[0], j_max_at=jmax[1], j_max_A_per_mm2=jmax[0] / (T_CU * 1e3)), heat

half = AMPS / 2
cases = [
    ("VIN: J1+ to Q1/Q7 source", "VIN", [(("J1", "2"), AMPS), (("Q1", "3"), -half), (("Q7", "3"), -half)]),
    ("MID: Q1/Q7 tab to Q2/Q8 tab", "MID", [(("Q1", "2"), half), (("Q7", "2"), half), (("Q2", "2"), -half), (("Q8", "2"), -half)]),
    ("VOUT: Q2/Q8 source to J6+J7 (farthest pair)", "VOUT", [(("Q2", "3"), half), (("Q8", "3"), half), (("J6", "2"), -half), (("J7", "2"), -half)]),
    ("GND: J6+J7 back to J1-", "GND", [(("J6", "1"), half), (("J7", "1"), half), (("J1", "1"), -AMPS)]),
]
brake = [   # 20 A brake pulse, for the loop resistance only (not added to the steady heat)
    ("VOUT: J6+J7 to J5 (brake resistor +)", "VOUT", [(("J6", "2"), 10), (("J7", "2"), 10), (("J5", "2"), -20)]),
    ("BRK_DRAIN: J5 to Q3/Q9 tab", "BRK_DRAIN", [(("J5", "1"), 20), (("Q3", "2"), -10), (("Q9", "2"), -10)]),
    ("GND: Q3/Q9 source to J6+J7", "GND", [(("Q3", "3"), 10), (("Q9", "3"), 10), (("J6", "1"), -10), (("J7", "1"), -10)]),
]
report = dict(copper_um=T_CU * 1e6, amps=AMPS, sheet_mohm_per_sq=RS * 1e3, through=[], brake=[])
heat = np.zeros((NY, NX))
for name, net, term in cases:
    r, hmap = solve(net, term); r["path"] = name; report["through"].append(r); heat += hmap
    print(f'{name:46s} {r["r_mohm"]:.3f} mohm  {r["drop_mV"]:.1f} mV  {r["watts"]:.2f} W  peak {r["j_max_A_per_mm"]:.1f} A/mm ({r["j_max_A_per_mm2"]:.0f} A/mm2) at {r["j_max_at"]}')
for name, net, term in brake:
    r, _ = solve(net, term); r["path"] = name; report["brake"].append(r)
    print(f'{name:46s} {r["r_mohm"]:.3f} mohm at 20 A  peak {r["j_max_A_per_mm"]:.1f} A/mm ({r["j_max_A_per_mm2"]:.0f} A/mm2) at {r["j_max_at"]}')
cu_w = sum(r["watts"] for r in report["through"]); fet_w = 4 * half ** 2 * RDS_HOT
# MOSFET loss enters the board through the four tab pads
for ref in ("Q1", "Q7", "Q2", "Q8"):
    m = pad_cells(ref, "2", pcbnew.F_Cu); heat[m] += half ** 2 * RDS_HOT / m.sum()
# thermal: sheet conduction (copper where present on each layer + FR-4), convection from both faces
allcu = [copper(None, l) for l in LAYERS]
K = K_FR4 * T_FR4 + K_CU * T_CU * (allcu[0].astype(float) + allcu[1].astype(float))
n = NX * NY; I = np.arange(n).reshape(NY, NX); rows, cols, vals = [], [], []
for A, B, Ka, Kb in ((I[:, :-1], I[:, 1:], K[:, :-1], K[:, 1:]), (I[:-1, :], I[1:, :], K[:-1, :], K[1:, :])):
    g = (2 * Ka * Kb / (Ka + Kb)).ravel(); a = A.ravel(); c = B.ravel()
    rows += [a, c, a, c]; cols += [c, a, a, c]; vals += [-g, -g, g, g]
conv = 2 * H_CONV * (H * 1e-3) ** 2
rows.append(I.ravel()); cols.append(I.ravel()); vals.append(np.full(n, conv))
A = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsc()
T = spl.spsolve(A, heat.ravel()).reshape(NY, NX)
m = np.unravel_index(np.argmax(T), T.shape)
report.update(copper_watts=cu_w, mosfet_watts=fet_w, total_watts=cu_w + fet_w, through_mohm=sum(r["r_mohm"] for r in report["through"]),
              rise_max_K=float(T.max()), rise_max_at=(round(float(X0 + m[1] * H), 1), round(float(Y0 + m[0] * H), 1)), rise_mean_K=float(T.mean()))
print(f'copper {RS*1e3:.2f} mohm/sq ({T_CU*1e6:.0f} um, 60 C)  through path {report["through_mohm"]:.2f} mohm  copper heat {cu_w:.2f} W  four MOSFETs {fet_w:.2f} W at {AMPS:g} A')
print(f'board temperature rise over ambient: hottest {T.max():.0f} K at {report["rise_max_at"]}, average {T.mean():.0f} K (still air, {H_CONV:g} W/m2K per face)')
tag = f'{T_CU*1e6:.0f}um_{AMPS:g}A'
json.dump(report, open(f"{out}/copper_{tag}.json", "w"), indent=1)
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 5)); ext = [X0, X0 + NX * H, Y0 + NY * H, Y0]
    a = ax[0].imshow(np.log10(heat / (H * H) * 1e3 + 1e-3), extent=ext, cmap="inferno", vmin=-2, vmax=2); ax[0].set_title(f"heat input, log10 mW/mm2 ({tag})"); fig.colorbar(a, ax=ax[0])
    a = ax[1].imshow(T, extent=ext, cmap="turbo"); ax[1].set_title("temperature rise over ambient, K"); fig.colorbar(a, ax=ax[1])
    fig.tight_layout(); fig.savefig(f"{out}/copper_{tag}.png", dpi=110)
except Exception as e:
    print("no plot:", e)
