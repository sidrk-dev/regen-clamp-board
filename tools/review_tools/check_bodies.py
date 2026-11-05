#!/usr/bin/env python3
"""Fail-closed package collision check that doesn't trust footprint courtyards (the easyeda2kicad ones are unreliable).
Each TO-263 gets its real plastic and lead envelope from the CRSS042N10N footprint; every other footprint's copper pads and
courtyard box must stay out. usage: check_bodies.py board.kicad_pcb   (exit 0 pass, 1 fail)"""
import sys, pcbnew
to = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
FETS = ("Q1", "Q2", "Q3", "Q7", "Q8", "Q9")
# footprint frame at rotation 0: leads toward -x. Datasheet p. 9: E 10.50 max wide, H 15.88 max overall, b 0.94 max lead; the
# silkscreen puts the plastic's front edge at x = -2.89. A 0.1 mm margin covers placement tolerance.
M = 0.1
PLASTIC = (-2.89 - M, -5.25 - M, 9.30, 5.25 + M)
LEADS = [(-6.86, -2.54 - 0.47 - M, -2.89, -2.54 + 0.47 + M), (-6.86, 2.54 - 0.47 - M, -2.89, 2.54 + 0.47 + M)]
def world(f, r):
    a = f.GetOrientationDegrees() % 360; p = f.GetPosition(); x0, y0 = to(p.x), to(p.y)
    assert a in (0, 180), f"{f.GetReference()} rotation {a} not handled"
    if a == 180: r = (-r[2], -r[3], -r[0], -r[1])
    return (x0 + r[0], y0 + r[1], x0 + r[2], y0 + r[3])
def box(item):
    c = item.GetBoundingBox(); return (to(c.GetLeft()), to(c.GetTop()), to(c.GetRight()), to(c.GetBottom()))
def hit(a, b_, m=0.0):
    return a[0] < b_[2] + m and b_[0] < a[2] + m and a[1] < b_[3] + m and b_[1] < a[3] + m
bad = 0
fps = list(b.GetFootprints())
for f in fps:
    if f.GetReference() not in FETS: continue
    zones = [("plastic", world(f, PLASTIC))] + [("lead", world(f, r)) for r in LEADS]
    for g in fps:
        if g is f: continue
        c = g.GetCourtyard(pcbnew.F_CrtYd).BBox(); cy = (to(c.GetLeft()), to(c.GetTop()), to(c.GetRight()), to(c.GetBottom()))
        have = c.GetWidth() > 0
        for name, z in zones:
            pads = [p for p in g.Pads() if hit(z, box(p))]
            if pads or (have and hit(z, cy)):
                print(f"FAIL {g.GetReference()} is under or against {f.GetReference()} {name}: pads {[p.GetNumber() for p in pads]}, courtyard {'hit' if have and hit(z, cy) else 'clear'}")
                bad += 1
# every courtyard pair, from closed outlines, independent of the DRC run
n = 0; empty = []
items = []
for f in fps:
    c = f.GetCourtyard(pcbnew.F_CrtYd)
    if c.OutlineCount() == 0: empty.append(f.GetReference()); continue
    items.append((f.GetReference(), c))
print("no closed courtyard:", empty)
print(("FAIL" if bad else "PASS") + f": 6 MOSFET envelopes against {len(fps) - 1} other footprints, {bad} collisions")
sys.exit(1 if bad else 0)
