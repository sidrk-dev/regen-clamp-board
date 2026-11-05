"""Place footprints, assign nets, draw outline and power zones for the regen/precharge board (headless pcbnew)."""
import re, sys
import pcbnew

PROJ = "/home/sid/Documents/code/im6014Development/.claude/worktrees/regen-clamp-review-f9d0d4/hardware/regen-precharge-board"
NETLIST = sys.argv[1]
BOARD = f"{PROJ}/regen_precharge.kicad_pcb"
LIBDIRS = {"jlc": f"{PROJ}/lib/jlc.pretty"}
OX, OY = 100.0, 100.0          # board origin on the KiCad canvas
W, H = 125.0, 100.0

def sexp(text):
    tokens = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(": stack.append([])
        elif t == ")": x = stack.pop(); stack[-1].append(x)
        else: stack[-1].append(t[1:-1] if t.startswith('"') else t)
    return stack[0][0]

def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]

def val(node, key):
    f = find(node, key)
    return f[0][1] if f else None

net = sexp(open(NETLIST).read())
comps = {}
for c in find(find(net, "components")[0], "comp"):
    fields = {val(f, "name"): (f[2] if len(f) > 2 else "") for f in find(find(c, "fields")[0], "field")} if find(c, "fields") else {}
    sheet = val(find(c, "sheetpath")[0], "tstamps")
    comps[val(c, "ref")] = dict(value=val(c, "value"), footprint=val(c, "footprint"), fields=fields,
                                path=sheet.rstrip("/") + "/" + val(c, "tstamps"))
pin_net = {}
for n in find(find(net, "nets")[0], "net"):
    name = val(n, "name").lstrip("/")
    for node in find(n, "node"):
        pin_net[(val(node, "ref"), val(node, "pin"))] = name

# (x, y, rotation) in board mm; origin top-left
PLACE = {
    "R6": (12, 64, 0),
    "D11": (63.4, 47.05, 180),
    "C17": (12, 30, 0),
    "Q4": (18, 64, 0),
    "D10": (18, 66.9, 0),
    "U2": (12, 69, 0),
    "R7": (16, 70, 90),
    "R8": (18, 70, 90),
    "C9": (23, 65, 90),
    "C10": (25.5, 65, 90),
    "R9": (30, 94, 0),
    "D3": (34, 94, 0),
    "U3": (40, 79, 0),
    "C11": (40, 74, 0),
    "R10": (31, 72, 0),
    "R11": (31, 74, 0),
    "R12": (31, 76, 0),
    "R13": (46, 73, 0),
    "R14": (31, 82, 0),
    "R15": (31, 84, 0),
    "R16": (31, 86, 0),
    "D5": (47, 87, 0),
    "R20": (47, 89.5, 0),
    "C12": (43, 89.5, 90),
    "R21": (41, 89.5, 90),
    "R22": (47.5, 84, 0),
    "R23": (47.5, 82, 0),
    "R24": (40, 94, 0),
    "D6": (44, 94, 0),
    "R17": (52, 79, 0),
    "Q5": (56, 82, 0),
    "Q6": (56, 87, 0),
    "SW1": (6, 74, 90),
    "R26": (22.5, 61.5, 0),
    "RV1": (16, 81, 0),
    "R25": (21, 79, 90),
    "TP5": (27, 69, 0),
    "TP9": (22.5, 86.5, 0),
    "TP10": (35.5, 71.5, 0),
    "TP11": (35.5, 86.5, 0),
    "TP12": (52.5, 75.5, 0),
    "TP14": (51, 90.5, 0),
    "TP15": (50, 96.5, 0),
    "TP16": (4, 64, 0),
    "TP17": (58, 96.5, 0),
    "U1": (57, 46, 0),
    "C2": (63.5, 42, 90),
    "C3": (60, 44.75, 270),
    "R1": (49, 50, 0),
    "R2": (49, 52, 0),
    "R3": (49, 44, 0),
    "R4": (49, 46, 0),
    "R5": (65, 52.5, 0),
    "C4": (64.5, 55.5, 0),
    "C5": (64.5, 58, 0),
    "TP6": (52, 41.5, 0),
    "TP7": (67, 48, 0),
    "TP8": (44.5, 52, 0),
    "J1": (16.5, 53.6, 90),
    "D1": (24, 13, 0),
    "C1": (32, 20, 90),
    "TP1": (14, 6, 0),
    "Q1": (44, 14, 0),
    "Q7": (44, 32, 0),
    "Q2": (72, 14, 180),
    "Q8": (72, 32, 180),
    "TP2": (58, 5, 0),
    "C13": (65, 60.7, 0),
    "C14": (67.8, 58.5, 90),
    "C7": (83, 28, 0),
    "C15": (97, 28, 0),
    "C8": (83, 42, 0),
    "C16": (97, 42, 0),
    "D2": (85, 52, 0),
    "C6": (95, 52, 90),
    "TP3": (102, 58, 0),
    "J2": (117.0, 29.5, 270),
    "J3": (117.0, 47.5, 270),
    "J4": (117.0, 65.5, 270),
    # rev C: per-FET gate resistors between the paralleled FETs, brake interlock beside J11
    "R30": (41, 20.9, 90),
    "R31": (41, 25.1, 90),
    "R32": (75, 20.9, 90),
    "R33": (75, 25.1, 90),
    "Q10": (52, 61.2, 0),
    "R34": (55.8, 61.2, 90),
    "Q11": (52, 65, 0),
    "R35": (55.8, 65, 90),
    "J5": (84.8, 92.45, 180),
    "Q9": (70, 66, 0),
    "Q3": (70, 80, 0),
    "D4": (87, 66, 180),
    "D7": (87, 72, 180),
    "R28": (60, 63.5, 90),
    "R29": (60, 67, 90),
    "R18": (60, 77.5, 90),
    "R19": (60, 81, 90),
    "R27": (50, 68, 0),
    "J11": (44, 63, 90),
    "TP13": (60, 72, 0),
    "TP4": (75, 95, 0),
    # #8-32 holes in the four corners
    "H1": (5, 5, 0),
    "H2": (5, 95, 0),
    "H3": (120, 95, 0),
    "H4": (120, 5, 0),
    # global fiducials for assembly (three, not in line)
    "FID1": (11, 4, 0),
    "FID2": (113, 4, 0),
    "FID3": (113, 96, 0),
    # rev D debug indicators and test points
    "R36": (26, 48.5, 270),
    "D8": (26, 52, 90),
    "TP25": (27.5, 56.5, 0),
    "Q12": (39.8, 63.5, 0),
    "R37": (39.8, 67, 0),
    "R38": (35.8, 63.5, 90),
    "D9": (35.8, 67, 90),
    "TP18": (45.5, 47.5, 0),
    "TP19": (61.5, 56.0, 0),
    "TP20": (55.8, 68.3, 0),
    "TP21": (61.9, 60.5, 0),
    "TP22": (43.5, 59.8, 0),
    "TP23": (59.5, 84.5, 0),
    "TP24": (114, 84, 0),
}

board = pcbnew.LoadBoard(BOARD)
for fp in list(board.GetFootprints()): board.Remove(fp)
for d in list(board.GetDrawings()): board.Remove(d)
for z in list(board.Zones()): board.Remove(z)
for t in list(board.GetTracks()): board.Remove(t)

nets = {}
def get_net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); nets[name] = n
    return nets[name]

mm = pcbnew.FromMM
def pt(x, y): return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))

for ref, c in sorted(comps.items()):
    lib, name = c["footprint"].split(":")
    path = LIBDIRS.get(lib, f"/usr/share/kicad/footprints/{lib}.pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None: raise SystemExit(f"missing footprint {c['footprint']}")
    fp.SetReference(ref); fp.SetValue(c["value"])
    fp.SetFPID(pcbnew.LIB_ID(lib, name)); fp.SetPath(pcbnew.KIID_PATH(c["path"]))
    for k, v in c["fields"].items():
        if k == "Footprint": continue
        if k == "Datasheet": fp.GetField(pcbnew.FIELD_T_DATASHEET).SetText(v); continue
        if k == "Description": fp.GetField(pcbnew.FIELD_T_DESCRIPTION).SetText(v); continue
        f = pcbnew.PCB_FIELD(fp, pcbnew.FIELD_T_USER, k)
        f.SetText(v); f.SetVisible(False); f.SetLayer(pcbnew.F_Fab); fp.Add(f)
    x, y, rot = PLACE[ref]
    board.Add(fp)
    fp.SetPosition(pt(x, y)); fp.SetOrientationDegrees(rot)
    if ref.startswith("TP"): fp.Value().SetPosition(pt(x, y + 1.7)); fp.Value().SetTextAngleDegrees(0)
    for pad in fp.Pads():
        n = pin_net.get((ref, pad.GetNumber()))
        if n: pad.SetNet(get_net(n))
    if ref.startswith("H") or ref.startswith("FID"): fp.SetExcludedFromBOM(True); fp.SetExcludedFromPosFiles(True)
    if ref.startswith("TP"):
        fp.SetExcludedFromBOM(True); fp.SetExcludedFromPosFiles(True)
        v = fp.Value(); v.SetLayer(pcbnew.F_SilkS); v.SetVisible(True); v.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        v.SetTextThickness(mm(0.12)); fp.Reference().SetVisible(False)
    if ref[:1] == "J" or ref in ("C7", "C8", "C15", "C16", "C17"):
        # high-current through-hole pads: solid copper to the pours, no thermal spokes
        for pad in fp.Pads(): pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    if c["fields"].get("Assembly") == "Hand-solder":
        fp.SetDNP(False); fp.SetExcludedFromBOM(False)

# outline with 2 mm corner radius
def seg(a, b):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(pt(*a)); s.SetEnd(pt(*b)); s.SetWidth(mm(0.1)); board.Add(s)
def arc(c, start, angle):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetCenter(pt(*c)); s.SetStart(pt(*start)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T)); s.SetWidth(mm(0.1)); board.Add(s)
r = 2.0
seg((r, 0), (W - r, 0)); seg((W, r), (W, H - r)); seg((W - r, H), (r, H)); seg((0, H - r), (0, r))
arc((r, r), (0, r), 90); arc((W - r, r), (W - r, 0), 90); arc((W - r, H - r), (W, H - r), 90); arc((r, H - r), (r, H), 90)

def zone(netname, layer, poly, prio=0, clearance=0.5, minw=0.25, thermal=True):
    z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(get_net(netname)); z.SetAssignedPriority(prio)
    z.SetLocalClearance(mm(clearance)); z.SetMinThickness(mm(minw))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL if thermal is None else pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(mm(0.5)); z.SetThermalReliefSpokeWidth(mm(1.0))
    o = z.Outline(); o.NewOutline()
    for x, y in poly: o.Append(mm(OX + x), mm(OY + y))
    board.Add(z); return z

F, B = pcbnew.F_Cu, pcbnew.B_Cu
# power copper on top; full-contact pads so the big pads carry current
zone("VIN", F, [(2, 2), (42.5, 2), (42.5, 40.0), (36, 46.5), (31, 46.5), (31, 58.5), (2, 58.5)], prio=3, thermal=False)
zone("MID", F, [(43.5, 2), (72.5, 2), (72.5, 39.5), (65, 39.5), (65, 45.95), (60.9, 45.95), (60.9, 44.9), (60.5, 44.9), (60.5, 39.5), (43.5, 39.5)], prio=3, thermal=False)
zone("VOUT", F, [(74, 2), (123, 2), (123, 98), (87.5, 98), (87.5, 57), (74, 57)], prio=3, thermal=False)
zone("BRK_DRAIN", F, [(69.5, 57.8), (86.5, 57.8), (86.5, 99), (69.5, 99)], prio=4, thermal=False)
# ground: solid bottom plane plus top fill in the control area
zone("GND", B, [(0.5, 0.5), (124.5, 0.5), (124.5, 99.5), (0.5, 99.5)], prio=0, clearance=0.4, thermal=None)
zone("GND", F, [(0.5, 59.5), (44, 59.5), (44, 56), (68.8, 56), (68.8, 99.5), (0.5, 99.5)], prio=1, clearance=0.4, thermal=None)

# copper keep-out under the #8-32 screw heads and washers, both layers (11 mm circle)
import math
for name in ("H1", "H2", "H3", "H4"):
    hx, hy, _ = PLACE[name]
    for layer in (F, B):
        z = pcbnew.ZONE(board); z.SetIsRuleArea(True); z.SetLayer(layer); z.SetZoneName("screw_head_" + name)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        o = z.Outline(); o.NewOutline()
        for i in range(32):
            a = 2 * math.pi * i / 32
            o.Append(mm(OX + hx + 5.5 * math.cos(a)), mm(OY + hy + 5.5 * math.sin(a)))
        board.Add(z)

ds = board.GetDesignSettings()
ds.SetCopperLayerCount(2)
ds.m_TrackMinWidth = mm(0.16); ds.m_MinClearance = mm(0.16); ds.m_ViasMinSize = mm(0.6); ds.m_MinThroughDrill = mm(0.3)
pcbnew.SaveBoard(BOARD, board)
print("footprints", len(board.GetFootprints()), "nets", len(nets))
