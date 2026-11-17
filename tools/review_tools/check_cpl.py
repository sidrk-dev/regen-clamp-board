#!/usr/bin/env python3
"""Check every row of the JLC placement file against the footprint JLC itself holds for that part number.
For each SMT part: fetch the EasyEDA/JLCEDA official-library footprint for its LCSC number (source: JLCEDA/EasyEDA Official Library,
https://easyeda.com, https://lceda.cn/), find the rotation that lays the board's KiCad pads onto it pad-number for pad-number,
and from that the rotation the CPL must carry. Also reports how far the KiCad footprint anchor is from the library origin.
usage: check_cpl.py board.kicad_pcb CPL.csv BOM.csv cache_dir   (exit 0 pass, 1 fail)"""
import csv, json, math, os, re, subprocess, sys, time
import pcbnew
board, cpl, bom, cache = sys.argv[1:5]
to = pcbnew.ToMM
def easy(c):
    p = f"{cache}/{c}.json"
    if not (os.path.exists(p) and os.path.getsize(p) > 500):
        for i in range(3):   # one polite request at a time; the API refuses bursts
            subprocess.run(["curl", "-s", "-m", "25", "-o", p, f"https://easyeda.com/api/products/{c}/components?version=6.4.19.5"])
            time.sleep(2.5)
            try:
                if json.load(open(p)).get("result"): break
            except Exception: pass
            time.sleep(20)
        else:
            if os.path.exists(p): os.remove(p)
            return None
    d = json.load(open(p))["result"]; ds = d["packageDetail"]["dataStr"]; h = ds["head"]
    pads = {}
    for s in ds["shape"]:
        f = s.split("~")
        if f[0] == "PAD" and f[8]:
            pads.setdefault(f[8], []).append(((float(f[2]) - h["x"]) * 0.254, (float(f[3]) - h["y"]) * 0.254))
    names = {}
    for s in d["dataStr"]["shape"]:
        if s.startswith("P~"):
            seg = s.split("^^")
            try: names[seg[4].split("~")[4]] = seg[3].split("~")[4]
            except IndexError: pass
    # A diode symbol that only numbers its pins: the triangle's apex, where the bar is drawn, points at the cathode pin.
    if len(names) == 2 and not all(KA.get(v.upper()) for v in names.values()):
        pins, tri = {}, None
        for s in d["dataStr"]["shape"]:
            if s.startswith("P~"):
                a = s.split("^^")[0].split("~"); pins[a[3]] = float(a[4])
            elif s.startswith("PT~"):
                xs = [float(x) for x, _ in re.findall(r"[ML] *(-?[\d.]+) (-?[\d.]+)", s.split("~")[1])]
                if len(xs) == 3: tri = xs
        if tri and len(pins) == 2 and len(set(tri)) == 2:
            base = max(set(tri), key=tri.count); apex = min(set(tri), key=tri.count)
            k = [n for n, x in pins.items() if (x - base) * (apex - base) > 0]
            if len(k) == 1:
                names = {n: ("K" if n == k[0] else "A") for n in pins}; names["_how"] = "the library symbol's drawing"
    return d["packageDetail"]["title"], {n: (sum(x for x, _ in v) / len(v), sum(y for _, y in v) / len(v)) for n, v in pads.items()}, names
KA = {"K": "K", "C": "K", "CATHODE": "K", "-": "K", "NEG": "K", "A": "A", "ANODE": "A", "+": "A", "POS": "A"}
def rot(p, deg):  # counter-clockwise as seen on screen (y down)
    a = math.radians(deg); x, y = p
    return (x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a))
lcsc = {}
for r in csv.DictReader(open(bom)):
    for ref in r["Designator"].split(","): lcsc[ref] = r["LCSC Part #"]
rows = {r["Designator"]: r for r in csv.DictReader(open(cpl))}
b = pcbnew.LoadBoard(board)
POLAR = re.compile(r"^(D|Q|U|SW|LED)")
bad = warn = 0
if set(rows) != set(lcsc): print("FAIL BOM and CPL list different parts:", sorted(set(rows) ^ set(lcsc))); bad += 1
for ref in sorted(rows, key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r)))):
    f = b.FindFootprintByReference(ref); k = f.GetOrientationDegrees() % 360
    pos = f.GetPosition(); cx, cy = float(rows[ref]["Mid X"][:-2]), float(rows[ref]["Mid Y"][:-2])
    if abs(cx - to(pos.x)) > 0.01 or abs(-cy - to(pos.y)) > 0.01:
        print(f"FAIL {ref}: CPL position ({cx},{cy}) but board anchor ({to(pos.x):.3f},{-to(pos.y):.3f})"); bad += 1
    kp = {}
    for p in f.Pads():
        if not p.GetNumber() or not p.IsOnLayer(pcbnew.F_Cu): continue
        d = p.GetPosition() - pos
        kp.setdefault(p.GetNumber(), []).append(rot((to(d.x), to(d.y)), -k))   # undo the board rotation -> footprint frame
    kp = {n: (sum(x for x, _ in v) / len(v), sum(y for _, y in v) / len(v)) for n, v in kp.items()}
    e = easy(lcsc[ref])
    if not e: print(f"HUMAN {ref} {lcsc[ref]}: no library footprint fetched"); warn += 1; continue
    title, ep, names = e
    names = dict(names); how = names.pop("_how", "library pad names")
    byfunc = ""
    if ref.startswith("D") and len(kp) == 2 and len(ep) == 2:
        # KiCad diode and LED footprints: pad 1 = cathode, pad 2 = anode. The library numbers them however its symbol does, so match by function.
        fn = {n: KA.get(names.get(n, "").upper()) for n in ep}
        if sorted(fn.values(), key=str) == ["A", "K"]:
            ep = {{"K": "1", "A": "2"}[fn[n]]: xy for n, xy in ep.items()}; byfunc = f"  (matched cathode to cathode: {how} " + ",".join(f"{n}={names[n]}" for n in sorted(names)) + ")"
        else:
            print(f"HUMAN {ref} {lcsc[ref]}: library symbol doesn't name anode and cathode ({names}); polarity not checked"); warn += 1
    common = sorted(set(kp) & set(ep))
    if len(common) < 2 or set(kp) != set(ep):
        print(f"HUMAN {ref} {lcsc[ref]}: pad numbers differ, board {sorted(kp)} library {sorted(ep)} ({title})"); warn += 1
        if len(common) < 2: continue
    best = []
    for th in (0, 90, 180, 270):
        kr = {n: rot(kp[n], th) for n in common}
        tx = sum(ep[n][0] - kr[n][0] for n in common) / len(common); ty = sum(ep[n][1] - kr[n][1] for n in common) / len(common)
        res = max(math.hypot(ep[n][0] - kr[n][0] - tx, ep[n][1] - kr[n][1] - ty) for n in common)
        best.append((res, th, tx, ty))
    best.sort(); res, th, tx, ty = best[0]
    lands = ""
    if res > 0.35:
        # A different land pattern for the same package moves the pad centres a little. That is still the same orientation
        # when every other rotation fits at least three times worse and the pads stay within 0.6 mm of their own number.
        if res < 0.6 and best[1][0] > 3 * res: lands = f"  land pattern differs by {res:.2f} mm (next-best rotation is {best[1][0]:.2f} mm off)"
        else: print(f"HUMAN {ref} {lcsc[ref]}: pads don't overlay the library footprint ({title}), worst pad {res:.2f} mm off"); warn += 1
    want = (k - th) % 360; have = float(rows[ref]["Rotation"]) % 360
    polar = bool(POLAR.match(ref)); diff = (have - want) % 360
    off = math.hypot(tx, ty)
    note = f"board {k:g}, library offset {th}, CPL should be {want:g}, CPL says {have:g}  [{title}]"
    if diff == 0: tag = "ok  "
    elif diff == 180 and not polar: tag = "ok* "   # two-pad unpolarised part turned end for end
    else: tag = "FAIL"; bad += 1
    extra = f"  anchor {off:.2f} mm from library origin" if off > 0.15 else ""
    if off > 0.5: tag = "FAIL" if tag != "FAIL" else tag; bad += tag == "FAIL" and diff == 0
    if polar and not byfunc and names: extra += "  pins " + ",".join(f"{n}={names[n]}" for n in sorted(names, key=lambda x: (len(x), x)))
    print(f"{tag} {ref:4} {lcsc[ref]:10} {note}{extra}{byfunc}{lands}", flush=True)
print(("PASS" if not bad else "FAIL") + f": {len(rows)} placements, {bad} wrong, {warn} for a person")
sys.exit(1 if bad else 0)
