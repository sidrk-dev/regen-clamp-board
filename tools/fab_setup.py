"""Record the JLCPCB 2 oz fab limits in the project and the 2 oz stackup in the board (run on the empty board)."""
import json, sys
board, pro = sys.argv[1], sys.argv[2]
clr = float(sys.argv[3]) if len(sys.argv) > 3 else 0.16  # net-class clearance (route with extra margin, check at 0.16)
d = json.load(open(pro))
r = d["board"]["design_settings"]["rules"]
r["min_track_width"] = 0.16; r["min_clearance"] = 0.16
for c in d["net_settings"]["classes"]:
    c["clearance"] = clr
json.dump(d, open(pro, "w"), indent=2)
s = open(board).read()
stack = '''(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.07))
\t\t\t(layer "dielectric 1" (type "core") (thickness 1.44) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.07))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "HAL lead-free")
\t\t\t(dielectric_constraints no)
\t\t)
\t\t'''
if "(stackup" not in s:
    assert "(setup" in s
    i = s.index("(setup") + len("(setup")
    while s[i] in " \t\n": i += 1
    s = s[:i] + stack + s[i:]
    open(board, "w").write(s)
