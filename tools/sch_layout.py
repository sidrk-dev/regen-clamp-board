"""Hand layout of the regen clamp schematic: symbol positions and the wires between pins.

Coordinates are mm on an A1 sheet, on the 1.27 mm grid. Pin offsets come from sch_geo.json (measured from KiCad's own
symbols). build() returns a Layout; finish() grounds or labels any pin the hand layout left loose, splits wires at every
joint, lists junction dots, and refuses a layout where wiring joins two nets or a wired net has no name, before anything
reaches the schematic.
"""
import json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
GEO = json.load(open(os.path.join(HERE, "sch_geo.json")))
DIR = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}
R2 = lambda v: round(v, 2)

BLOCKS = [
    ("INPUT", "XT60 from the supply (fuse it in the supply lead). TVS D1 and bulk C17. White LED D8 = supply present.", (15, 22, 130, 160)),
    ("IDEAL DIODE + SOFT START (U1 LM74800)", "Q1||Q7 block regen into the supply. Q2||Q8 ramp the output at about 140 V/s "
     "(C4, C5, C13, C14 on CDVDT through R5). D11 clamps HGATE to VOUT + 12 V. SW1 = output on/off. UVLO ~13.5 V (R1/R2), "
     "OV ~57 V (R3/R4).", (135, 22, 460, 160)),
    ("OUTPUT BUS", "Four 470 uF 100 V bulk capacitors, ceramic C6 and TVS D2. Five XT30 outputs, 15 A each: 1-3 arm, 4 gripper, 5 spare.",
     (465, 22, 820, 160)),
    ("11.6 V CONTROL RAIL", "Made from VOUT, so it runs while the arm back-drives the bus. CJ431 (U2) sets Q4's base; "
     "D12 clamps it under 17 V; D10 guards Q4's base-emitter. Green LED D3 = output live.", (15, 165, 205, 300)),
    ("BRAKE COMPARATOR (U3A)", "Brakes when VOUT - VIN > 0.667 x V(TRIM) - 0.14 V. RV1 sets +3.0 to +7.5 V "
     "(clockwise raises it). R13 adds about 2.3 V of hysteresis.", (210, 165, 460, 300)),
    ("BRAKE DRIVER + MOSFETS", "U4 (UCC27517) drives Q3||Q9 into the external resistor on J5 (2 ohm 200 W at 36 V, Q136 "
     "fuse in series). J11 = the resistor's thermal switch: open disables the brake. D4/D7 catch the resistor's kick.",
     (465, 165, 820, 300)),
    ("BRAKE INTERLOCK", "Q10/Q11 hold CMP_OUT low while the ideal diode conducts (DGATE above VIN).", (15, 305, 165, 420)),
    ("THERM OPEN LED", "Yellow D9 lights when the J11 loop is open.", (170, 305, 285, 420)),
    ("RED BRAKE LED", "U3B keeps red D6 lit for at least 0.3 s after any brake pulse (C12, R21).", (290, 305, 590, 420)),
    ("MICROCONTROLLER HEADER", "J12: 1 GND, 2 BUS_ADC (VOUT x 0.053), 3 BRK_FLAG (open drain, low while braking).", (595, 305, 820, 420)),
    ("TEST POINTS, MOUNTING, FIDUCIALS", "", (15, 425, 640, 540)),
]


class Layout:
    def __init__(self, parts):
        self.unit_of, self.lib, self.net_of = {}, {}, {}
        for c in parts:
            u = c.get("unit") or 1
            self.lib[(c["ref"], u)] = c["lib"]
            for n, net in c["pins"].items():
                self.unit_of[(c["ref"], n)] = u
                self.net_of[(c["ref"], n)] = net
        self.pos, self.wires, self.labels, self.pin_labels, self.gnds = {}, [], [], [], []

    def at(self, ref, x, y, rot=0, unit=1):
        self.pos[(ref, unit)] = (R2(x), R2(y), rot)

    def geo(self, ref, n):
        n = str(n)
        u = self.unit_of.get((ref, n), 1)
        lib = self.lib[(ref, u)]
        key = f"{lib}#{u}" if u > 1 else lib
        x, y, rot = self.pos[(ref, u)]
        dx, dy, o = GEO[key][str(rot)][n]
        return (R2(x + dx), R2(y + dy)), int(round(o)) % 360

    def pt(self, p):
        return self.geo(*p)[0] if isinstance(p[0], str) else (R2(p[0]), R2(p[1]))

    def W(self, *pts):
        """Polyline through pins ('R1', 1) and points (x, y); every leg horizontal or vertical."""
        q = [self.pt(p) for p in pts]
        for a, b in zip(q, q[1:]):
            assert a[0] == b[0] or a[1] == b[1], f"diagonal wire {a} -> {b} in {pts}"
            if a != b:
                self.wires.append((a, b))
        return q

    def lbl(self, net, p, rot=0):
        """Global label anchored on a wire point; rot 0 extends right, 90 up, 180 left, 270 down."""
        self.labels.append((net, *self.pt(p), rot))

    def plabel(self, ref, n):
        """Global label on a pin through a 2.54 mm stub (Konnect's batch_connect_to_net)."""
        self.pin_labels.append((ref, str(n)))

    def gnd(self, p, rot=0):
        self.gnds.append((*self.pt(p), rot))

    def gpin(self, ref, n):
        """Ground symbol on a pin through a 2.54 mm stub."""
        (x, y), o = self.geo(ref, n)
        dx, dy = DIR[o]
        q = (R2(x + 2.54 * dx), R2(y + 2.54 * dy))
        self.wires.append(((x, y), q))
        self.gnds.append((*q, 180 if (dx, dy) == (0, -1) else 0))


def build(parts, tps, holes, fids, flags):
    L = Layout(parts)
    at, W, lbl, gpin, plabel = L.at, L.W, L.lbl, L.gpin, L.plabel

    # ================= INPUT. The power path runs left to right on y = YP.
    YP = 68.58
    at("J1", 30.48, 71.12, 180)                      # pin 2 VIN (35.56, 68.58), pin 1 GND (35.56, 71.12)
    gpin("J1", 1)
    for ref, x, rot in (("D1", 48.26, 270), ("C1", 63.5, 0), ("C17", 78.74, 0), ("R36", 99.06, 0)):
        at(ref, x, YP + 7.62, rot)
        W((x, YP), (ref, 1))
        if ref != "R36":
            gpin(ref, 2)
    at("D8", 99.06, YP + 19.05, 90)                  # anode (2) up
    W(("R36", 2), ("D8", 2)); gpin("D8", 1)
    lbl("LEDV_A", (99.06, YP + 13.97), 0)
    lbl("VIN", (114.3, YP), 90)

    # ================= IDEAL DIODE: Q1||Q7 then Q2||Q8, drains joined (MID)
    YP2 = YP + 35.56
    at("Q1", 160.02, YP - 1.27, 270)                 # source left, drain right, gate up
    at("Q2", 185.42, YP + 1.27, 90)                  # drain left, source right, gate down
    at("Q7", 160.02, YP2 - 1.27, 270)
    at("Q8", 185.42, YP2 + 1.27, 90)
    W(("J1", 2), ("Q1", 3))                          # VIN
    W(("Q1", 2), ("Q2", 2))                          # MID
    W((147.32, YP), (147.32, YP2), ("Q7", 3))
    W(("Q1", 2), ("Q7", 2)); W(("Q2", 2), ("Q8", 2))
    W((198.12, YP), (198.12, YP2), ("Q8", 3))
    W((172.72, YP), (172.72, YP - 7.62)); lbl("MID", (172.72, YP - 7.62), 90)
    at("R30", 160.02, YP - 11.43, 0)                 # pin 2 (DG1) down onto Q1's gate
    W(("R30", 2), ("Q1", 1)); plabel("R30", 1); lbl("DG1", (160.02, YP - 6.35), 180)
    at("R31", 160.02, YP2 - 11.43, 180)              # pin 1 (DG7) down onto Q7's gate
    W(("R31", 1), ("Q7", 1)); plabel("R31", 2); lbl("DG7", (160.02, YP2 - 6.35), 180)
    at("R32", 185.42, YP + 11.43, 180)               # pin 2 (HG2) up onto Q2's gate
    W(("R32", 2), ("Q2", 1)); plabel("R32", 1); lbl("HG2", (185.42, YP + 6.35), 0)
    at("R33", 185.42, YP2 + 11.43, 0)                # pin 1 (HG8) up onto Q8's gate
    W(("R33", 1), ("Q8", 1)); plabel("R33", 2); lbl("HG8", (185.42, YP2 + 6.35), 0)

    # U1, left side: DGATE, VIN, OV divider, EN
    at("U1", 304.8, 101.6, 0)                        # left pins x 290.83: 1 DGATE 96.52 ... 6 EN 109.22
    W(("U1", 2), ("U1", 3)); plabel("U1", 2); plabel("U1", 1)
    at("R3", 264.16, 107.95, 0)
    at("R4", 264.16, 119.38, 0); gpin("R4", 2)
    W(("U1", 4), ("R3", 1)); W(("R3", 2), ("R4", 1)); lbl("OV_TOP", (269.24, 104.14), 90)
    W(("U1", 5), (284.48, 106.68), (284.48, 114.3), (264.16, 114.3)); lbl("OV", (284.48, 114.3), 270)
    YEN = 132.08
    W(("U1", 6), (288.29, 109.22), (288.29, YEN), (254.0, YEN))
    at("R1", 254.0, 121.92, 0); plabel("R1", 1); W(("R1", 2), (254.0, YEN))
    at("R2", 254.0, 139.7, 0); W((254.0, YEN), ("R2", 1)); gpin("R2", 2)
    at("SW1", 233.68, 142.24, 270)                   # pins point right: 2 EN (240.03, 142.24), 1 GND (240.03, 134.62)
    W(("SW1", 2), (248.92, 142.24), (248.92, YEN), (254.0, YEN)); gpin("SW1", 1)
    lbl("EN", (248.92, YEN), 90)
    # U1, right side: MID, CAP, VOUT, HGATE, GND
    at("C3", 335.28, 99.06, 90)
    W(("U1", 11), ("C3", 1)); lbl("CAP", (320.04, 99.06), 0)
    W(("U1", 12), (341.63, 96.52)); W(("U1", 10), (341.63, 101.6), (341.63, 96.52)); W(("C3", 2), (341.63, 99.06))
    W((341.63, 96.52), (349.25, 96.52)); lbl("MID", (349.25, 96.52), 0)
    at("C2", 346.71, 104.14, 0); W((346.71, 96.52), ("C2", 1)); gpin("C2", 2)
    plabel("U1", 9); plabel("U1", 8); gpin("U1", 7)
    # soft start: R5 into the CDVDT capacitors; D11 clamps HGATE
    YC = 121.92
    at("R5", 370.84, YC, 90)
    W(("R5", 1), (355.6, YC)); lbl("HGATE", (355.6, YC), 180)
    at("D11", 360.68, 129.54, 270)                   # cathode (HGATE) up
    W((360.68, YC), ("D11", 1)); plabel("D11", 2)
    for ref, x in (("C4", 383.54), ("C5", 396.24), ("C13", 408.94), ("C14", 421.64)):
        at(ref, x, 128.27, 0); W((x, YC), (ref, 1)); gpin(ref, 2)
    W(("R5", 2), (429.26, YC)); lbl("CDVDT", (429.26, YC), 0)

    # ================= OUTPUT BUS: VOUT runs straight on from Q2's source
    W((198.12, YP), (208.28, YP), (208.28, YP - 5.08)); lbl("VOUT", (208.28, YP - 5.08), 90)
    for ref, x in (("C6", 480.06), ("C7", 492.76), ("C8", 505.46), ("C15", 518.16), ("C16", 530.86), ("D2", 543.56)):
        at(ref, x, YP + 10.16, 270 if ref == "D2" else 0)
        W((x, YP), (ref, 1)); gpin(ref, 2)
    xs = [571.5 + 35.56 * i for i in range(5)]
    for x, ref in zip(xs, ("J2", "J3", "J4", "J6", "J7")):
        at(ref, x, 86.36, 180)                       # pin 2 VOUT (x+5.08, 83.82), pin 1 GND (x+5.08, 86.36)
        W((x + 10.16, YP), (x + 10.16, 83.82), (ref, 2)); gpin(ref, 1)
    W(("Q2", 3), (xs[-1] + 10.16, YP))

    # ================= CONTROL RAIL
    YR = 187.96
    W((22.86, YR), (91.44, YR)); lbl("VOUT", (22.86, YR), 180)
    at("R6", 35.56, 195.58, 0); W((35.56, YR), ("R6", 1))
    YK = 205.74
    at("Q4", 88.9, YK, 0)                            # base (83.82, YK), C (91.44, 200.66), tab (93.98, 200.66), E (91.44, 210.82)
    W(("R6", 2), (35.56, YK), ("Q4", 1)); lbl("REF_K", (40.64, YK), 90)
    at("R26", 91.44, 193.04, 0); W((91.44, YR), ("R26", 1)); W(("R26", 2), ("Q4", 2))
    W(("Q4", 4), (93.98, 198.12), (91.44, 198.12)); W((93.98, 198.12), (99.06, 198.12)); lbl("RAIL_C", (99.06, 198.12), 0)
    at("U2", 48.26, 213.36, 90)                      # K up, A down, REF left
    W((48.26, YK), ("U2", 2)); gpin("U2", 3)
    at("R7", 58.42, 215.9, 0); W((58.42, YK), ("R7", 1))
    at("R8", 58.42, 233.68, 0); W(("R7", 2), ("R8", 1)); gpin("R8", 2)
    W(("U2", 1), (43.18, 213.36), (43.18, 226.06), (58.42, 226.06))
    W((43.18, 226.06), (38.1, 226.06)); lbl("REF_FB", (38.1, 226.06), 180)
    at("D12", 68.58, 213.36, 270); W((68.58, YK), ("D12", 1)); gpin("D12", 2)
    at("D10", 78.74, 213.36, 270); W((78.74, YK), ("D10", 1))
    YG = 220.98
    W(("D10", 2), (78.74, YG), (147.32, YG)); W(("Q4", 3), (91.44, YG)); lbl("VREG", (147.32, YG), 0)
    for ref, x in (("C9", 101.6), ("C10", 116.84)):
        at(ref, x, 228.6, 0); W((x, YG), (ref, 1)); gpin(ref, 2)
    at("R9", 132.08, 227.33, 0); W((132.08, YG), ("R9", 1))
    at("D3", 132.08, 240.03, 90); W(("R9", 2), ("D3", 2)); gpin("D3", 1)
    lbl("LEDG_A", (132.08, 233.68), 0)

    # ================= BRAKE COMPARATOR
    at("U3", 337.82, 213.36, 0, 1)                    # IN+ (322.58, 210.82), IN- (322.58, 215.9), out (337.82, 213.36)
    YSP = 210.82
    W((233.68, YSP), ("U3", 3))
    at("R10", 233.68, 201.93, 0); plabel("R10", 1); W(("R10", 2), (233.68, YSP))
    at("R11", 233.68, 218.44, 0); W((233.68, YSP), ("R11", 1)); gpin("R11", 2)
    at("R12", 246.38, 218.44, 0); W((246.38, YSP), ("R12", 1)); gpin("R12", 2)
    at("R13", 259.08, 203.2, 0); plabel("R13", 1); W(("R13", 2), (259.08, YSP))
    lbl("SENSE_P", (299.72, YSP), 90)
    YSN = 259.08
    W(("U3", 2), (325.12, 215.9), (325.12, YSN), (266.7, YSN)); lbl("SENSE_N", (302.26, YSN), 270)
    at("R14", 266.7, 233.68, 0); plabel("R14", 1); W(("R14", 2), (266.7, YSN))
    at("R15", 266.7, 266.7, 0); W((266.7, YSN), ("R15", 1)); gpin("R15", 2)
    at("R16", 284.48, 237.49, 0); W(("R16", 2), (284.48, YSN))
    at("RV1", 297.18, 233.68, 180)                   # VREG top, wiper left, TRIM_LO bottom
    W(("R16", 1), ("RV1", 2)); lbl("TRIM", (288.29, 233.68), 90)
    plabel("RV1", 3)
    at("R25", 297.18, 243.84, 0); W(("RV1", 1), ("R25", 1)); gpin("R25", 2)
    lbl("TRIM_LO", (297.18, 238.76), 0)
    plabel("U3", 1)
    at("U3", 375.92, 226.06, 0, 3)                   # 8 VREG (363.22, 218.44), 4 GND (363.22, 233.68)
    at("C11", 386.08, 226.06, 0)
    W(("U3", 8), (373.38, 215.9), (386.08, 215.9), ("C11", 1)); lbl("VREG", (379.73, 215.9), 90)
    gpin("U3", 4); gpin("C11", 2)

    # ================= BRAKE DRIVER + MOSFETS
    at("R17", 482.6, 199.39, 0); plabel("R17", 1)
    at("J11", 497.84, 205.74, 0)                     # 1 PU_TH (492.76, 205.74), 2 CMP_OUT (492.76, 208.28)
    W(("R17", 2), (482.6, 205.74), ("J11", 1)); lbl("PU_TH", (487.68, 205.74), 90)
    at("U4", 568.96, 218.44, 0)                      # left: 1 VDD 215.9, 3 IN 218.44, 2 GND 220.98, 4 GND 223.52; 5 OUT right
    W(("J11", 2), (490.22, 208.28), (490.22, 218.44), ("U4", 3))
    for ref, x in (("R27", 500.38), ("C18", 510.54)):
        at(ref, x, 226.06, 0); W((x, 218.44), (ref, 1)); gpin(ref, 2)
    lbl("CMP_OUT", (548.64, 218.44), 90)
    W(("U4", 1), (556.26, 215.9), (556.26, 198.12)); lbl("VREG", (556.26, 198.12), 90)
    at("C19", 566.42, 203.2, 0); W((556.26, 199.39), ("C19", 1)); gpin("C19", 2)
    W(("U4", 2), (558.80, 220.98), (558.80, 223.52), ("U4", 4)); W((558.80, 223.52), (558.80, 226.06)); L.gnd((558.80, 226.06))
    YQ = 246.38
    W(("U4", 5), (594.36, 218.44), (594.36, YQ)); lbl("VG", (581.66, 218.44), 90)
    at("Q3", 614.68, YQ, 0); at("R18", 601.98, YQ, 90)
    W((594.36, YQ), ("R18", 1)); W(("R18", 2), ("Q3", 1)); gpin("Q3", 3)
    at("R19", 608.33, 254.0, 0); W((608.33, YQ), ("R19", 1)); gpin("R19", 2); lbl("BRK_GATE", (608.33, YQ), 90)
    at("Q9", 662.94, YQ, 0); at("R28", 650.24, YQ, 90)
    plabel("R28", 1); W(("R28", 2), ("Q9", 1)); gpin("Q9", 3)
    at("R29", 656.59, 254.0, 0); W((656.59, YQ), ("R29", 1)); gpin("R29", 2); lbl("BRK_GATE2", (656.59, YQ), 90)
    YBD = 226.06
    at("J5", 731.52, YBD, 0)                         # 1 BRK_DRAIN (726.44, YBD), 2 VOUT (726.44, YBD + 2.54)
    W(("Q3", 2), (615.95, YBD), ("J5", 1)); W(("Q9", 2), (664.21, YBD))
    W(("J5", 2), (723.90, 228.6), (723.90, 233.68)); lbl("VOUT", (723.90, 233.68), 270)
    lbl("BRK_DRAIN", (703.58, YBD), 90)
    YDV = 210.82
    for ref, x in (("D4", 680.72), ("D7", 693.42)):
        at(ref, x, 219.71, 270)                      # cathode (VOUT) up, anode down
        W((ref, 2), (x, YBD)); W((x, YDV), (ref, 1))
    W((675.64, YDV), (693.42, YDV)); lbl("VOUT", (675.64, YDV), 180)

    # ================= INTERLOCK
    at("Q10", 55.88, 350.52, 180)                    # E (53.34, 345.44) up, C (53.34, 355.6) down, B (60.96, 350.52)
    at("R34", 53.34, 337.82, 0); plabel("R34", 1); W(("R34", 2), ("Q10", 2)); lbl("ILK_E", (53.34, 342.9), 180)
    at("R41", 68.58, 340.36, 0); plabel("R41", 1)
    W(("R41", 2), (68.58, 350.52), ("Q10", 1)); lbl("ILK_BASE", (63.5, 350.52), 90)
    at("R35", 53.34, 367.03, 0); W(("Q10", 3), ("R35", 1)); gpin("R35", 2)
    at("Q11", 78.74, 360.68, 0)                      # B (73.66, 360.68), E (81.28, 365.76), C (81.28, 355.6)
    W((53.34, 360.68), ("Q11", 1)); lbl("ILK_B", (63.5, 360.68), 270)
    gpin("Q11", 2); plabel("Q11", 3)

    # ================= THERM OPEN LED
    at("Q12", 205.74, 350.52, 180)                   # E up (203.2, 345.44), B right (210.82, 350.52), C down (203.2, 355.6)
    plabel("Q12", 2)
    at("R37", 220.98, 350.52, 270); W(("R37", 2), ("Q12", 1)); plabel("R37", 1); lbl("THB", (213.36, 350.52), 270)
    at("R38", 203.2, 363.22, 0); W(("Q12", 3), ("R38", 1)); lbl("THC", (203.2, 358.14), 180)
    at("D9", 203.2, 375.92, 90); W(("R38", 2), ("D9", 2)); gpin("D9", 1); lbl("LEDT_A", (203.2, 369.57), 0)

    # ================= RED BRAKE LED
    Y0 = 345.44
    at("D5", 317.5, Y0, 180); plabel("D5", 2)        # anode (VG) left, cathode right
    at("R20", 330.2, Y0, 90); W(("D5", 1), ("R20", 1)); lbl("STR_D", (323.85, Y0), 90)
    for ref, x in (("C12", 341.63), ("R21", 351.79)):
        at(ref, x, Y0 + 7.62, 0); W((x, Y0), (ref, 1)); gpin(ref, 2)
    at("R40", 363.22, Y0, 90); W(("R20", 2), ("R40", 1)); lbl("STRETCH", (346.71, Y0), 90)
    at("U3", 398.78, 340.36, 0, 2)                   # IN+ 5 (378.46, 337.82), IN- 6 (378.46, 342.9), out 7 (393.7, 340.36)
    W(("R40", 2), (386.08, Y0), (386.08, 342.9), ("U3", 6)); lbl("STRETCH_IN", (370.84, Y0), 270)
    at("R22", 383.54, 331.47, 0); plabel("R22", 1)
    at("R23", 378.46, 337.82, 270); gpin("R23", 2)
    W(("R23", 1), ("U3", 5)); W(("R22", 2), (383.54, 337.82)); lbl("LED_REF", (388.62, 337.82), 90)
    at("D6", 414.02, 340.36, 0)                      # cathode left (to U3B out), anode right
    W(("U3", 7), ("D6", 1)); lbl("LEDR_K", (408.94, 340.36), 90)
    at("R24", 426.72, 340.36, 270); W(("D6", 2), ("R24", 2)); lbl("LEDR_A", (420.37, 340.36), 90)
    plabel("R24", 1)

    # ================= MICROCONTROLLER HEADER
    at("J12", 612.14, 353.06, 180)                   # 3 BRK_FLAG (617.22, 350.52), 2 BUS_ADC (617.22, 353.06), 1 GND (617.22, 355.6)
    gpin("J12", 1); plabel("J12", 3)
    at("R44", 680.72, 340.36, 0); plabel("R44", 1)
    at("R45", 680.72, 361.95, 0); W(("R44", 2), ("R45", 1)); gpin("R45", 2)
    W(("J12", 2), (680.72, 353.06)); lbl("BUS_ADC", (640.08, 353.06), 90)
    at("C20", 670.56, 360.68, 0); W((670.56, 353.06), ("C20", 1)); gpin("C20", 2)
    at("Q13", 650.24, 381.0, 0)                      # gate (645.16, 381), D (652.78, 375.92), S (652.78, 386.08)
    at("R42", 637.54, 381.0, 90); plabel("R42", 1); W(("R42", 2), ("Q13", 1)); lbl("FLAG_G", (643.89, 381.0), 90)
    plabel("Q13", 3); gpin("Q13", 2)

    # ================= TEST POINTS, HOLES, FIDUCIALS, FLAGS
    for i, ref in enumerate(tps[:13]):
        at(ref, 30.48 + 20.32 * i, 457.2)
    for i, ref in enumerate(tps[13:] + holes + fids + flags):
        at(ref, 30.48 + 20.32 * i, 497.84)
    return L


def on(p, s):
    (x1, y1), (x2, y2) = s
    return (x1 == x2 == p[0] and min(y1, y2) <= p[1] <= max(y1, y2)) or (y1 == y2 == p[1] and min(x1, x2) <= p[0] <= max(x1, x2))


def finish(L, parts):
    """Ground or label loose pins, split wires at joints, find junctions; refuse shorts and unnamed wired nets."""
    pins = {}
    for c in parts:
        for n in c["pins"]:
            pins[(c["ref"], n)] = L.geo(c["ref"], n)
    auto = []
    labelled = set(L.pin_labels)
    for (ref, n), (p, o) in sorted(pins.items()):
        if (ref, n) in labelled or any(on(p, s) for s in L.wires):
            continue
        if L.net_of[(ref, n)] == "GND":
            L.gpin(ref, n)
        else:
            L.plabel(ref, n)
            if not ref.startswith(("TP", "#FLG")):
                auto.append(f"{ref}.{n}")
    stub_wires, stub_labels = [], []
    for ref, n in L.pin_labels:
        (x, y), o = L.geo(ref, n)
        dx, dy = DIR[o]
        q = (R2(x + 2.54 * dx), R2(y + 2.54 * dy))
        stub_wires.append(((x, y), q)); stub_labels.append((L.net_of[(ref, n)], q))
    # split every wire at each joint inside it, so that every connection is end to end
    points = {p for s in L.wires + stub_wires for p in s} | {p for p, o in pins.values()} \
        | {(x, y) for _, x, y, _ in L.labels} | {(x, y) for x, y, _ in L.gnds}
    split = []
    for s in dict.fromkeys(L.wires):
        x1, y1 = s[0]
        inner = sorted((p for p in points if on(p, s) and p not in s), key=lambda p: abs(p[0] - x1) + abs(p[1] - y1))
        chain = [s[0]] + inner + [s[1]]
        split += list(zip(chain, chain[1:]))
    L.wires = list(dict.fromkeys(split))
    segs = L.wires + stub_wires
    parent = {}
    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for a, b in segs:
        parent[find(a)] = find(b)
    tag, named = defaultdict(set), defaultdict(set)
    for (ref, n), (p, o) in pins.items():
        tag[find(p)].add(L.net_of[(ref, n)])
    for net, x, y, r in L.labels:
        tag[find((x, y))].add(net); named[find((x, y))].add(net)
    for net, q in stub_labels:
        tag[find(q)].add(net); named[find(q)].add(net)
    for x, y, r in L.gnds:
        tag[find((x, y))].add("GND"); named[find((x, y))].add("GND")
    bad = [sorted(g) for g in tag.values() if len(g) > 1]
    assert not bad, f"wiring joins different nets: {bad}"
    wired = {find(a) for s in segs for a in s}
    unnamed = sorted(next(iter(tag[k])) for k in wired if k in tag and not named.get(k))
    assert not unnamed, f"wired nets with no label: {unnamed}"
    ends = defaultdict(int)
    for a, b in segs:
        ends[a] += 1; ends[b] += 1
    for p, o in pins.values():
        if p in ends:
            ends[p] += 1
    junctions = sorted(p for p, k in ends.items() if k >= 3)
    return auto, junctions


TWO_PIN = {"Device:R": 0, "Device:C": 0, "Device:C_Polarized": 0, "Device:D": 90, "Device:D_Zener": 90,
           "Device:D_Schottky": 90, "Device:LED": 90}   # rotation at which the pins are vertical (mod 180)
FIELD_SIDE = {"R6": "L", "R16": "L", "R17": "L", "R22": "L"}   # ref -> "L" to put the text left of a vertical part
# ref -> ((ref dx, dy), (value dx, dy)) from the symbol origin; text horizontal and centred
FIELD_POS = {"C3": ((0, -4.4), (0, -6.2)), "RV1": ((4.5, -1.4), ("w", 1.4)), "J11": ((-0.5, -5.0), ("w", 6.2)),
             "Q3": ((7.5, -1.4), (15.5, 1.4)), "Q9": ((7.5, -1.4), (16.5, 1.4)), "U4": ((10.0, 4.5), (2.0, 9.0)),
             "D6": ((0, -3.0), (2.0, 5.5)), "R23": ((0, 2.4), (0, 4.2)),
             "J12": ((0, -6.0), (0, 8.5))}


def place_fields(text):
    """Reference and value of two-pin parts: horizontal text beside a vertical part, above and below a horizontal one."""
    import re
    out, pos = [], 0
    for m in re.finditer(r'\n\t\(symbol\n\t\t\(lib_id "([^"]+)"\)\n\t\t\(at ([\d.\-]+) ([\d.\-]+) (\d+)\)', text):
        lib, x, y, rot = m.group(1), float(m.group(2)), float(m.group(3)), int(m.group(4))
        if lib not in TWO_PIN and not re.search(r'\(property "Reference" "(%s)"' % "|".join(FIELD_POS), text[m.end():m.end() + 400]):
            continue
        end = text.index("\n\t)", m.end())
        block = text[m.start():end]
        ref = re.search(r'\(property "Reference" "([^"]+)"', block).group(1)
        val = re.search(r'\(property "Value" "([^"]*)"', block).group(1)
        ang = 90 if rot in (90, 270) else 0
        vertical = lib in TWO_PIN and (rot - TWO_PIN[lib]) % 180 == 0
        w = lambda t, size: 0.95 * size * len(t)
        if ref in FIELD_POS:
            (a, b), (c, d) = FIELD_POS[ref]
            rx, ry = x + a, y + b
            vx, vy = x + (3.0 + w(val, 1.0) / 2 if c == "w" else c), y + d
        elif vertical:
            sgn = -1 if FIELD_SIDE.get(ref) == "L" else 1
            gap = 2.2 if lib.startswith("Device:D") or lib.startswith("Device:LED") else 1.6
            rx, ry = x + sgn * (gap + w(ref, 1.27) / 2), y - 1.4
            vx, vy = x + sgn * (gap + w(val, 1.0) / 2), y + 1.4
        else:
            gap = 3.0 if lib.startswith(("Device:D", "Device:LED")) else 2.4
            rx, ry, vx, vy = x, y - gap, x, y + gap
        def put(b, name, px, py, size):
            return re.sub(r'(\(property "%s" "[^"]*"\n\t\t\t\(at )[\d.\-]+ [\d.\-]+ \d+(\)\n\t\t\t\(effects\n\t\t\t\t\(font\n\t\t\t\t\t\(size )[\d.]+ [\d.]+' % name,
                          lambda k: f"{k.group(1)}{px:.2f} {py:.2f} {ang}{k.group(2)}{size} {size}", b, count=1)
        block = put(block, "Reference", rx, ry, 1.27)
        block = put(block, "Value", vx, vy, 1.0)
        out.append(text[pos:m.start()]); out.append(block); pos = end
    out.append(text[pos:])
    return "".join(out)
