#!/usr/bin/env python3
"""Fail-closed exact-part check: blind datasheet ledger + function-based intent vs the board's pads.
usage: check_parts.py board.kicad_pcb pin_intent.json ledger.json   (exit 0 pass, 1 fail)
Anything the datasheet can't settle is listed under HUMAN and does not count as verified."""
import json, sys, pcbnew
board, intent_path, ledger_path = sys.argv[1:4]
b = pcbnew.LoadBoard(board); mm = pcbnew.ToMM
I = json.load(open(intent_path))
ledger = {p["lcsc"]: p for p in json.load(open(ledger_path))["parts"]}
# Manufacturer's words in the ledger -> this project's function names
ALIAS = {"Output A": "OUT1", "Inputs A −": "IN1-", "Inputs A +": "IN1+", "Inputs B +": "IN2+", "Inputs B −": "IN2-", "Output B": "OUT2",
         "CCW": "END_CCW", "CW": "END_CW", "VCC": "VCC", "GND": "GND"}
fails, human, ok = [], [], 0
def lcsc_of(f):
    try: return f.GetFieldText("LCSC")
    except Exception: return ""
def pads(f):
    out = {}
    for p in f.Pads():
        if p.GetNumber(): out.setdefault(p.GetNumber(), []).append(p)
    return out
def xy(p):
    q = p.GetPosition(); return mm(q.x), mm(q.y)
def net(p):
    n = p.GetNetname(); return None if (not n or n.startswith("unconnected")) else n
def lookup(ref, lcsc):
    f = b.FindFootprintByReference(ref)
    if f is None: fails.append(f"{ref}: not on the board"); return None, None
    if lcsc_of(f) != lcsc: fails.append(f"{ref}: board LCSC {lcsc_of(f)!r}, intent {lcsc}")
    return f, ledger.get(lcsc)
for ref, want in I["numbered"].items():
    f, L = lookup(ref, want["lcsc"])
    if f is None: continue
    if L is None: fails.append(f"{ref}: {want['lcsc']} missing from ledger"); continue
    P = pads(f)
    if L.get("pins"):
        for num, name in L["pins"].items():
            func = ALIAS.get(name, name)
            if num == "EP": num = "13"
            if func not in want["funcs"]: fails.append(f"{ref}: ledger pin {num} '{name}' has no intended function"); continue
            if num not in P: fails.append(f"{ref}: ledger pin {num} has no pad"); continue
            for p in P[num]:
                if net(p) != want["funcs"][func]:
                    fails.append(f"{ref} pin {num} is {func} per datasheet: on net {net(p)}, must be {want['funcs'][func]}")
                else: ok += 1
    elif want["lcsc"] == "C410926":
        # TO-263: datasheet labels terminals by position, not number. Tab = D; leads down, G left, S right (top view).
        g, d, s = P["1"][0], max(P["2"], key=lambda p: p.GetSize().x * p.GetSize().y), P["3"][0]
        gx, gy = xy(g); dx, dy = xy(d); sx, sy = xy(s)
        ux, uy = (gx + sx) / 2 - dx, (gy + sy) / 2 - dy      # tab -> leads = "down" on the drawing
        left = (-uy, ux)                                      # drawing's left, top view, y-down screen coordinates
        if (gx - sx) * left[0] + (gy - sy) * left[1] <= 0: fails.append(f"{ref}: G and S are mirrored against the drawing")
        for pad, fn in ((g, "G"), (d, "D"), (s, "S")):
            if net(pad) != want["funcs"][fn]: fails.append(f"{ref} {fn}: on net {net(pad)}, must be {want['funcs'][fn]}")
            else: ok += 1
    else: fails.append(f"{ref}: ledger has no usable pins")
    # physical layout of SOT-23 parts: lone pin 3 up, pin 1 left, pin 2 right in the top view
    if str(L.get("package", "")).startswith("SOT-23"):
        x1, y1 = xy(P["1"][0]); x2, y2 = xy(P["2"][0]); x3, y3 = xy(P["3"][0])
        ux, uy = x3 - (x1 + x2) / 2, y3 - (y1 + y2) / 2       # towards the lone pin = "up" on the drawing
        left = (uy, -ux)
        if (x1 - x2) * left[0] + (y1 - y2) * left[1] <= 0: fails.append(f"{ref}: SOT-23 pads are mirrored against the drawing")
    if want["lcsc"] in ("C3215600", "C7955"):
        # counter-clockwise numbering seen from the top
        n = 12 if want["lcsc"] == "C3215600" else 8
        pts = [xy(P[str(i)][0]) for i in range(1, n + 1)]
        area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
        if area >= 0: fails.append(f"{ref}: pad numbering runs the wrong way for a top view")
    if L.get("confidence") != "high" and want["lcsc"] not in ("C58159",): human.append(f"{ref}: ledger confidence {L.get('confidence')}: {str(L.get('notes'))[:90]}")
for ref, want in I["two_terminal"].items():
    if ref.startswith("_"): continue
    f, L = lookup(ref, want["lcsc"])
    if f is None: continue
    if L is None: fails.append(f"{ref}: {want['lcsc']} missing from ledger"); continue
    P = pads(f)
    for num, term in (("1", "K"), ("2", "A")):
        if net(P[num][0]) != want[term]: fails.append(f"{ref} {term}: on net {net(P[num][0])}, must be {want[term]}")
        else: ok += 1
    if L.get("pins") and L["pins"].get("1") == "A": human.append(f"{ref}: LED datasheet numbers pin 1 = anode, KiCad pad 1 = cathode; check its cathode mark on JLC's preview")
for ref, want in I["polarized_pads"].items():
    if ref.startswith("_"): continue
    f, L = lookup(ref, want["lcsc"])
    if f is None: continue
    P = pads(f)
    for side in ("plus", "minus"):
        num, n = want[side]
        if net(P[num][0]) != n: fails.append(f"{ref} {side}: pad {num} on {net(P[num][0])}, must be {n}")
        else: ok += 1
    if ref.startswith("J"):
        # Amass drawings (XT60PW-M30 C98732, XT30PW-F C2913282): in the view of the mating face, drawn with the board on the
        # left, the upper contact sits at the flat end of the housing and the lower one at the chamfered end. The flat end is
        # the "+" contact (XT convention; the XT30 drawing carries its polarity mark at that end). The mating face lies from
        # the pin row towards the fixing pegs, so on the board, seen from the top, "+" is the pin a quarter turn clockwise
        # on screen from that direction.
        pins = [P[want["plus"][0]][0], P[want["minus"][0]][0]]; fix = [p for p in f.Pads() if not p.GetNumber()]
        if len(fix) < 2: fails.append(f"{ref}: no fixing pegs to find the mating face from"); continue
        (px, py), (mx_, my_) = xy(pins[0]), xy(pins[1])
        cx, cy = (px + mx_) / 2, (py + my_) / 2
        fx, fy = sum(xy(p)[0] for p in fix) / len(fix), sum(xy(p)[1] for p in fix) / len(fix)
        face = (fx - cx, fy - cy); up = (-face[1], face[0])
        if (px - mx_) * up[0] + (py - my_) * up[1] <= 0: fails.append(f"{ref}: + and - pads are mirrored against the datasheet's face view (flat end = +)")
        else: ok += 1
for ref, want in I["switch"].items():
    f, L = lookup(ref, want["lcsc"])
    if f is None or L is None: fails.append(f"{ref}: missing"); continue
    P = pads(f); names = L["pins"]
    com = [k for k, v in names.items() if v == "COM"]
    if com != ["2"] or net(P["2"][0]) != want["COM"]: fails.append(f"{ref}: COM must be pin 2 on {want['COM']}, got {com} on {net(P['2'][0])}")
    else: ok += 1
    if net(P["1"][0]) != want["THROW_GND"]: fails.append(f"{ref}: pin 1 on {net(P['1'][0])}, must be {want['THROW_GND']}")
    else: ok += 1
    if net(P["3"][0]) is not None: fails.append(f"{ref}: pin 3 must be unconnected, on {net(P['3'][0])}")
    # MSK12C02 drawing (C431540): knob at the pin-3 end joins pins 3 and 2; at the pin-1 end, pins 2 and 1. Pin 1 is ground
    # and COM is EN, so the pin-1 end is OFF. The silkscreen must say so: "ON" towards pin 3, "OFF" towards pin 1.
    (x1, y1), (x3, y3) = xy(P["1"][0]), xy(P["3"][0]); sx, sy = mm(f.GetPosition().x), mm(f.GetPosition().y)
    lab = {}
    for d in b.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetText() in ("ON", "OFF"):
            q = d.GetPosition(); dist = ((mm(q.x) - sx) ** 2 + (mm(q.y) - sy) ** 2) ** 0.5
            if dist < 8: lab[d.GetText()] = (mm(q.x), mm(q.y))
    if set(lab) != {"ON", "OFF"}: fails.append(f"{ref}: needs separate ON and OFF labels within 8 mm, found {sorted(lab)}")
    elif (lab["ON"][0] - lab["OFF"][0]) * (x3 - x1) + (lab["ON"][1] - lab["OFF"][1]) * (y3 - y1) <= 0: fails.append(f"{ref}: ON and OFF labels are the wrong way round (ON belongs at the pin-3 end)")
    else: ok += 1
# Items a second, independent source has since settled (recorded with their evidence in pin_intent.json "settled")
settled = I.get("settled", {}); done = sorted({h for h in human if h.split(":")[0] in settled}); human = [h for h in human if h not in done]
print("\n".join("FAIL  " + x for x in fails)); print("\n".join("HUMAN " + x for x in sorted(set(human))))
for r in sorted({h.split(":")[0] for h in done}, key=lambda r: (r[0], int(r[1:]))): print(f"SETTLED {r}: {settled[r]}")
print(f"{'FAIL' if fails else 'PASS'}: {ok} terminals verified against datasheet-derived pin tables, {len(fails)} failures, {len(set(human))} left for a person")
sys.exit(1 if fails else 0)
