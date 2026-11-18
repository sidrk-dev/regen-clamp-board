#!/usr/bin/env python3
"""Check each LCSC number in build_sch.py against JLC's catalogue (via jlcsearch): the value and package must match.
usage: check_bom.py build_sch.py out.json   (exit 0 pass, 1 fail). Parts the catalogue can't describe are listed for a person."""
import json, re, sys, time, urllib.request
src, out = sys.argv[1:3]
parts = {}
for m in re.finditer(r'part\("(\w+)",\s*"[^"]+",\s*"([^"]*)",\s*("[^"]*"|\w+),\s*"(C\d+)"', open(src).read()):
    ref, val, fp, c = m.groups()
    parts.setdefault(c, dict(lcsc=c, value=val, footprint=fp.strip('"'), refs=[]))["refs"].append(ref)
def lookup(c):
    for _ in range(4):
        try:
            req = urllib.request.Request(f"https://jlcsearch.tscircuit.com/api/search?q={c}&limit=5", headers={"User-Agent": "Mozilla/5.0"})
            for x in json.load(urllib.request.urlopen(req, timeout=25))["components"]:
                if x.get("lcsc") == int(c[1:]):
                    return x
        except Exception:
            pass
        time.sleep(2.5)
    return {}
PKG = {"R0603": "0603", "C0603": "0603", "C0805": "0805", "C1206": "1206", "R_1206": "1206", "R_0805": "0805", "LED_0805": "0805", "LED_0603": "0603", "SOT23": "SOT-23", "D_SOD-323": "SOD-323", "D_SMA": "SMA", "D_SMC": "SMC"}
def rvalue(v):
    m = re.match(r"([\d.]+)(R|k|M)\b", v)
    if m: return {"R": "", "k": "k", "M": "M"}[m[2]], float(m[1])
bad = 0; human = []
for c, p in parts.items():
    x = lookup(c); p.update(mfr=x.get("mfr"), package=x.get("package"), description=x.get("description"), basic=x.get("is_basic"))
    d = x.get("description") or ""
    time.sleep(1)
    if not x:
        human.append(f"{c} {p['refs']}: not found"); continue
    for k, pk in PKG.items():
        if k in p["footprint"] and pk not in (x.get("package") or ""):
            print(f"FAIL {c} {p['refs']}: footprint {p['footprint']} but catalogue package {x.get('package')}"); bad += 1
    r = rvalue(p["value"])
    if r:
        want = f"{r[1]:g}{r[0]}Ω"
        if want not in d:
            print(f"FAIL {c} {p['refs']}: wanted {want}, catalogue says {d[:80]}"); bad += 1
    mt = re.search(r"([\d.]+)%", p["value"])
    if r and mt and f"±{mt[1]}%" not in d:
        print(f"FAIL {c} {p['refs']}: wanted ±{mt[1]}%, catalogue says {d[:80]}"); bad += 1
    if r and set(p["refs"]) & {"R1", "R3", "R6", "R10", "R14", "R36", "R44"}:
        min_v = 150 if set(p["refs"]) & {"R6", "R36"} else 75
        rv_m = re.search(r"(?<![\d.])(\d+)V\b", d)
        if not rv_m or int(rv_m.group(1)) < min_v:
            print(f"FAIL {c} {p['refs']}: bus resistor needs >={min_v} V working rating, catalogue says {d[:80]}"); bad += 1
    m = re.match(r"([\d.]+)(uF|nF)", p["value"])
    if m and f"{m[1]}{m[2]}" not in d:
        print(f"FAIL {c} {p['refs']}: wanted {m[0]}, catalogue says {d[:80]}"); bad += 1
    # voltage rating of capacitors and the can size of the electrolytics (independent review, 15 Nov 2026: neither was checked)
    mv = re.search(r"(\d+)V\b", p["value"])
    if m and mv and not re.search(rf"(?<![\d.]){mv[1]}V\b", d):
        print(f"FAIL {c} {p['refs']}: wanted a {mv[1]} V part, catalogue says {d[:80]}"); bad += 1
    mc = re.search(r"CP_Radial_D([\d.]+)mm_P([\d.]+)mm", p["footprint"])
    if mc and not (f"D{float(mc[1]):g}x" in (x.get("package") or "") + d and re.search(rf"(?<![\d.]){float(mc[2]):g}mm", d)):
        print(f"FAIL {c} {p['refs']}: footprint is {mc[1]} mm diameter on {mc[2]} mm pitch, catalogue says {(x.get('package') or '')} {d[:60]}"); bad += 1
    if not r and not m and not any(w in (x.get("mfr") or "") + d for w in re.split(r"[ (]", p["value"])[:1]):
        human.append(f"{c} {p['refs']}: {p['value']} vs {x.get('mfr')}")
json.dump(list(parts.values()), open(out, "w"), indent=1, ensure_ascii=False)
for h in human: print("HUMAN", h)
print(("FAIL" if bad else "PASS") + f": {len(parts)} part numbers, {bad} mismatches, {len(human)} for a person")
sys.exit(1 if bad else 0)
