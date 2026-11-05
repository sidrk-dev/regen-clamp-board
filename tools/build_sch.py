"""Build the regen clamp + precharge schematic through Konnect's MCP tools."""
import json, os, subprocess, sys
from collections import defaultdict

PROJ = "/home/sid/Documents/code/im6014Development/.claude/worktrees/regen-clamp-review-f9d0d4/hardware/regen-precharge-board"
SCH = f"{PROJ}/regen_precharge.kicad_sch"

R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
FET = "jlc:TO-263-3_L10.2-W10.7-P5.08-LS16.2-TL"
XT30 = "Connector_AMASS:AMASS_XT30PW-F_1x02_P2.50mm_Horizontal"

# ref, lib_id, value, footprint, LCSC, x, y, rotation, {pin: net}, extra fields
P = []
def part(ref, lib, val, fp, lcsc, x, y, pins, rot=0, unit=1, note=""):
    P.append(dict(ref=ref, lib=lib, val=val, fp=fp, lcsc=lcsc, x=x, y=y, rot=rot, unit=unit, pins=pins, note=note))

# ---- Block 1: input, ideal diode + soft-start (LM74800) ----
part("J1", "Connector_Generic:Conn_01x02", "XT60PW-M (from PSU)", "jlc:AMASS_XT60PW-M30_1x02_P7.20mm_Horizontal", "C98732", 25, 55, {"1": "GND", "2": "VIN"}, note="Hand-solder")
part("D1", "Device:D_Zener", "SMCJ51A TVS", "Diode_SMD:D_SMC", "C42371549", 45, 60, {"1": "VIN", "2": "GND"}, rot=90)
part("C1", "Device:C", "1uF 100V", C1206, "C13832", 60, 60, {"1": "VIN", "2": "GND"})
# C17: holds the input up when Q2/Q8 turn off under load; only C1 (1 uF) was there, and the supply lead inductance could pass U1's 70 V.
part("C17", "Device:C_Polarized", "470uF 63V", "Capacitor_THT:CP_Radial_D12.5mm_P5.00mm", "C165665", 75, 60, {"1": "VIN", "2": "GND"}, note="Hand-solder")
part("Q1", "jlc:CRSS042N10N", "CRSS042N10N", FET, "C410926", 95, 40, {"1": "DG1", "2": "MID", "3": "VIN"}, rot=90)
part("Q2", "jlc:CRSS042N10N", "CRSS042N10N", FET, "C410926", 150, 40, {"1": "HG2", "2": "MID", "3": "VOUT"}, rot=90)
part("U1", "jlc:LM74800QDRRRQ1", "LM74800QDRRRQ1", "jlc:WSON-12_L3.0-W3.0-P0.50-TL-EP-2", "C3215600", 120, 85,
     {"1": "DGATE", "2": "VIN", "3": "VIN", "4": "OV_TOP", "5": "OV", "6": "EN", "7": "GND", "8": "HGATE", "9": "VOUT", "10": "MID", "11": "CAP", "12": "MID"})
part("C2", "Device:C", "1uF 100V", C1206, "C13832", 160, 80, {"1": "MID", "2": "GND"})
part("C3", "Device:C", "470nF 25V", C0603, "C1623", 175, 80, {"1": "CAP", "2": "MID"})  # TI: VCAP >= 10 x (Ciss Q1 + Ciss Q2), four 6.77 nF MOSFETs here
part("R1", "Device:R", "1M", R0603, "C22935", 70, 95, {"1": "VIN", "2": "EN"})
part("R2", "Device:R", "100k", R0603, "C25803", 70, 115, {"1": "EN", "2": "GND"})
part("SW1", "jlc:MSK12C02", "MSK12C02 (OUTPUT ON/OFF)", "jlc:SW-TH_MSK12C02", "C431540", 85, 125, {"1": "GND", "2": "EN"})
part("R3", "Device:R", "100k", R0603, "C25803", 95, 140, {"1": "OV_TOP", "2": "OV"})
part("R4", "Device:R", "2.2k", R0603, "C4190", 110, 140, {"1": "OV", "2": "GND"})
part("R5", "Device:R", "1k", R0603, "C21190", 160, 105, {"1": "HGATE", "2": "CDVDT"})
# D11: the 400 nF on CDVDT holds HGATE up when VOUT falls fast; HGATE-OUT is 15 V absolute maximum. R5 limits the current to under 50 mA.
part("D11", "Device:D_Zener", "BZT52C12", "Diode_SMD:D_SOD-123", "C2932744", 190, 105, {"1": "HGATE", "2": "VOUT"}, rot=90)
part("C4", "Device:C", "100nF 100V", C0805, "C28233", 160, 125, {"1": "CDVDT", "2": "GND"})
part("C5", "Device:C", "100nF 100V", C0805, "C28233", 175, 125, {"1": "CDVDT", "2": "GND"})

# ---- Block 2: output bus ----
part("C6", "Device:C", "1uF 100V", C1206, "C13832", 205, 60, {"1": "VOUT", "2": "GND"})
part("C7", "Device:C_Polarized", "470uF 63V", "Capacitor_THT:CP_Radial_D12.5mm_P5.00mm", "C165665", 220, 60, {"1": "VOUT", "2": "GND"}, note="Hand-solder")
part("C8", "Device:C_Polarized", "470uF 63V", "Capacitor_THT:CP_Radial_D12.5mm_P5.00mm", "C165665", 235, 60, {"1": "VOUT", "2": "GND"}, note="Hand-solder")
part("D2", "Device:D_Zener", "SMCJ51A TVS", "Diode_SMD:D_SMC", "C42371549", 250, 60, {"1": "VOUT", "2": "GND"}, rot=90)
part("J2", "Connector_Generic:Conn_01x02", "XT30PW-F (out 1: arm bus)", XT30, "C2913282", 280, 40, {"1": "GND", "2": "VOUT"}, note="Hand-solder")
part("J3", "Connector_Generic:Conn_01x02", "XT30PW-F (out 2: gripper)", XT30, "C2913282", 280, 65, {"1": "GND", "2": "VOUT"}, note="Hand-solder")
part("J4", "Connector_Generic:Conn_01x02", "XT30PW-F (out 3: spare)", XT30, "C2913282", 280, 90, {"1": "GND", "2": "VOUT"}, note="Hand-solder")

# ---- Block 3: 11.6 V control rail ----
part("R6", "Device:R", "10k 1206", "Resistor_SMD:R_1206_3216Metric", "C17902", 30, 185, {"1": "VOUT", "2": "REF_K"})
# CJ431 SOT-23 is pin 1 REF, pin 2 K, pin 3 A (JCET datasheet p. 1), which is the TL432 pin order, not the TL431's.
part("U2", "Reference_Voltage:TL432DBZ", "CJ431", SOT23, "C3113", 45, 215, {"1": "REF_FB", "2": "REF_K", "3": "GND"})
part("R7", "Device:R", "39k", R0603, "C23153", 65, 200, {"1": "REF_K", "2": "REF_FB"})
part("R8", "Device:R", "10k", R0603, "C25804", 65, 230, {"1": "REF_FB", "2": "GND"})
part("Q4", "Transistor_BJT:MMBT3904", "MMBT5551", SOT23, "C2145", 85, 180, {"1": "REF_K", "2": "VREG", "3": "RAIL_C"})
# D10 stops Q4's emitter-base junction breaking down when VOUT collapses while C9 still holds the rail up (BVebo is 6 V).
part("D10", "Device:D", "1N4148WS", "Diode_SMD:D_SOD-323", "C2128", 68, 172, {"1": "REF_K", "2": "VREG"})
part("R26", "Device:R", "470R", R0603, "C23179", 110, 172, {"1": "VOUT", "2": "RAIL_C"}, rot=90)
part("C9", "Device:C", "10uF 25V", C0805, "C15850", 100, 205, {"1": "VREG", "2": "GND"})
part("C10", "Device:C", "100nF", C0603, "C14663", 112, 205, {"1": "VREG", "2": "GND"})
part("R9", "Device:R", "10k", R0603, "C25804", 125, 195, {"1": "VREG", "2": "LEDG_A"})
part("D3", "Device:LED", "GREEN (output live)", "LED_SMD:LED_0805_2012Metric", "C2297", 125, 225, {"1": "GND", "2": "LEDG_A"}, rot=90)

# ---- Block 4: brake comparator, gate driver, brake FET ----
part("R10", "Device:R", "100k", R0603, "C25803", 150, 165, {"1": "VOUT", "2": "SENSE_P"})
part("R11", "Device:R", "20k", R0603, "C4184", 150, 195, {"1": "SENSE_P", "2": "GND"})
part("R12", "Device:R", "220k", R0603, "C22961", 162, 195, {"1": "SENSE_P", "2": "GND"})
part("R13", "Device:R", "510k (hysteresis)", R0603, "C23192", 190, 160, {"1": "VG", "2": "SENSE_P"}, rot=90)
part("R14", "Device:R", "100k", R0603, "C25803", 150, 225, {"1": "VIN", "2": "SENSE_N"})
part("R15", "Device:R", "20k", R0603, "C4184", 150, 255, {"1": "SENSE_N", "2": "GND"})
part("R16", "Device:R", "150k (offset)", R0603, "C22807", 165, 240, {"1": "TRIM", "2": "SENSE_N"}, rot=90)
part("RV1", "Device:R_Potentiometer", "10k trim: brake threshold", "jlc:RES-ADJ-TH_3362P", "C58159", 120, 245, {"1": "TRIM_LO", "2": "TRIM", "3": "VREG"}, note="Hand-solder")  # 3362P: pin 3 is the clockwise end, so clockwise raises the threshold
part("R25", "Device:R", "6.8k", R0603, "C23212", 135, 260, {"1": "TRIM_LO", "2": "GND"})
part("U3", "Comparator:LM393", "LM393", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "C7955", 195, 205, {"1": "CMP_OUT", "2": "SENSE_N", "3": "SENSE_P"}, unit=1)
part("U3", "Comparator:LM393", "LM393", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "C7955", 345, 220, {"5": "LED_REF", "6": "STRETCH", "7": "LEDR_K"}, unit=2)
part("U3", "Comparator:LM393", "LM393", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "C7955", 195, 255, {"8": "VREG", "4": "GND"}, unit=3)
part("C11", "Device:C", "100nF", C0603, "C14663", 210, 255, {"1": "VREG", "2": "GND"})
part("R17", "Device:R", "4.7k", R0603, "C23162", 220, 180, {"1": "VREG", "2": "PU_TH"})
part("Q5", "Transistor_BJT:MMBT3904", "MMBT3904", SOT23, "C20526", 235, 195, {"1": "CMP_OUT", "2": "VG", "3": "VREG"})
part("Q6", "Transistor_BJT:MMBT3906", "S8550", SOT23, "C105432", 235, 220, {"1": "CMP_OUT", "2": "VG", "3": "GND"})
part("R18", "Device:R", "10R", R0603, "C22859", 255, 205, {"1": "VG", "2": "BRK_GATE"}, rot=90)
part("R19", "Device:R", "10k", R0603, "C25804", 270, 225, {"1": "BRK_GATE", "2": "GND"})
part("Q3", "jlc:CRSS042N10N", "CRSS042N10N (brake)", FET, "C410926", 285, 200, {"1": "BRK_GATE", "2": "BRK_DRAIN", "3": "GND"})
part("D4", "Device:D_Schottky", "SS210", "Diode_SMD:D_SMA", "C14996", 300, 170, {"1": "VOUT", "2": "BRK_DRAIN"}, rot=90)
part("J5", "Connector_Generic:Conn_01x02", "XT60PW-F (brake resistor, 2 ohm 200 W)", "jlc:AMASS_XT60PW-F_1x02_P7.20mm_Horizontal_2.9mm", "C428722", 340, 170, {"1": "BRK_DRAIN", "2": "VOUT"}, note="Hand-solder")

# ---- Block 5: brake LED pulse stretcher ----
part("D5", "Device:D", "1N4148WS", "Diode_SMD:D_SOD-323", "C2128", 300, 230, {"1": "STR_D", "2": "VG"}, rot=180)
part("R20", "Device:R", "100R", R0603, "C22775", 315, 240, {"1": "STR_D", "2": "STRETCH"}, rot=90)
part("C12", "Device:C", "100nF", C0603, "C14663", 285, 255, {"1": "STRETCH", "2": "GND"})
part("R21", "Device:R", "2M", R0603, "C22976", 297, 255, {"1": "STRETCH", "2": "GND"})
part("R22", "Device:R", "47k", R0603, "C25819", 370, 185, {"1": "VREG", "2": "LED_REF"})
part("R23", "Device:R", "10k", R0603, "C25804", 382, 200, {"1": "LED_REF", "2": "GND"})
part("R24", "Device:R", "4.7k", R0603, "C23162", 395, 200, {"1": "VREG", "2": "LEDR_A"})
part("D6", "Device:LED", "RED (regen brake active)", "LED_SMD:LED_0603_1608Metric", "C2286", 395, 230, {"1": "LEDR_K", "2": "LEDR_A"}, rot=90)

# ---- Block 6: 30 A / 60 A peak additions ----
part("Q7", "jlc:CRSS042N10N", "CRSS042N10N", FET, "C410926", 440, 40, {"1": "DG7", "2": "MID", "3": "VIN"}, rot=90)
part("Q8", "jlc:CRSS042N10N", "CRSS042N10N", FET, "C410926", 480, 40, {"1": "HG8", "2": "MID", "3": "VOUT"}, rot=90)
part("C13", "Device:C", "100nF 100V", C0805, "C28233", 440, 75, {"1": "CDVDT", "2": "GND"})
part("C14", "Device:C", "100nF 100V", C0805, "C28233", 455, 75, {"1": "CDVDT", "2": "GND"})
part("C15", "Device:C_Polarized", "470uF 63V", "Capacitor_THT:CP_Radial_D12.5mm_P5.00mm", "C165665", 475, 75, {"1": "VOUT", "2": "GND"}, note="Hand-solder")
part("C16", "Device:C_Polarized", "470uF 63V", "Capacitor_THT:CP_Radial_D12.5mm_P5.00mm", "C165665", 490, 75, {"1": "VOUT", "2": "GND"}, note="Hand-solder")
part("R28", "Device:R", "10R", R0603, "C22859", 440, 165, {"1": "VG", "2": "BRK_GATE2"}, rot=90)
part("R29", "Device:R", "10k", R0603, "C25804", 455, 185, {"1": "BRK_GATE2", "2": "GND"})
part("Q9", "jlc:CRSS042N10N", "CRSS042N10N (brake 2)", FET, "C410926", 475, 165, {"1": "BRK_GATE2", "2": "BRK_DRAIN", "3": "GND"})
part("D7", "Device:D_Schottky", "SS210", "Diode_SMD:D_SMA", "C14996", 495, 140, {"1": "VOUT", "2": "BRK_DRAIN"}, rot=90)
part("J11", "Connector_Generic:Conn_01x02", "Brake resistor thermal switch (NC) or jumper", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "C492401", 450, 225, {"1": "PU_TH", "2": "CMP_OUT"}, note="Hand-solder")
part("R27", "Device:R", "100k", R0603, "C25803", 470, 235, {"1": "CMP_OUT", "2": "GND"})

# ---- Block 7 (rev C): individual gate resistors for the paralleled FETs ----
part("R30", "Device:R", "10R", R0603, "C22859", 78, 30, {"1": "DGATE", "2": "DG1"}, rot=90)
part("R31", "Device:R", "10R", R0603, "C22859", 423, 30, {"1": "DG7", "2": "DGATE"}, rot=90)
part("R32", "Device:R", "10R", R0603, "C22859", 133, 30, {"1": "HGATE", "2": "HG2"}, rot=90)
part("R33", "Device:R", "10R", R0603, "C22859", 497, 30, {"1": "HG8", "2": "HGATE"}, rot=90)

# ---- Block 8 (rev C): brake interlock. While the ideal diode conducts (DGATE > VIN) Q11 holds CMP_OUT low,
# so the brake can never pull the bus below the supply and draw supply current, whatever the resistor tolerances.
part("R34", "Device:R", "47k", R0603, "C25819", 515, 160, {"1": "DGATE", "2": "ILK_E"}, rot=90)
part("Q10", "Transistor_BJT:MMBT3906", "MMBT5401", SOT23, "C8326", 530, 175, {"1": "VIN", "2": "ILK_E", "3": "ILK_B"})
part("R35", "Device:R", "100k", R0603, "C25803", 530, 205, {"1": "ILK_B", "2": "GND"})
part("Q11", "Transistor_BJT:MMBT3904", "MMBT3904", SOT23, "C20526", 548, 195, {"1": "ILK_B", "2": "GND", "3": "CMP_OUT"})

# ---- Block 9 (rev D): debug indicators ----
# D8 white: supply present at the input (lit even with SW1 off)
part("R36", "Device:R", "33k 0805", "Resistor_SMD:R_0805_2012Metric", "C17633", 60, 140, {"1": "VIN", "2": "LEDV_A"}, rot=90)
part("D8", "Device:LED", "WHITE (supply present)", "LED_SMD:LED_0603_1608Metric", "C2290", 60, 160, {"1": "GND", "2": "LEDV_A"}, rot=90)
# D9 yellow: J11 thermal loop open (brake disabled). Q12 sees a voltage across J11 only when the loop is open;
# its 1M base resistor lifts CMP_OUT by at most about 0.75 V (lowest-gain Q12), far below the 3 V or more the brake needs.
part("Q12", "Transistor_BJT:MMBT3906", "S8550", SOT23, "C105432", 500, 250, {"1": "THB", "2": "PU_TH", "3": "THC"})
part("R37", "Device:R", "1M", R0603, "C22935", 485, 260, {"1": "CMP_OUT", "2": "THB"})
part("R38", "Device:R", "2.2k", R0603, "C4190", 515, 262, {"1": "THC", "2": "LEDT_A"}, rot=90)
part("D9", "Device:LED", "YELLOW (thermal loop open)", "LED_SMD:LED_0805_2012Metric", "C2296", 515, 280, {"1": "GND", "2": "LEDT_A"}, rot=90)

HOLES = [("H1", 25, 270), ("H2", 37, 270), ("H3", 49, 270), ("H4", 61, 270)]  # #8-32 clearance (4.5 mm)
TPS = [("TP1", "VIN"), ("TP2", "MID"), ("TP3", "VOUT"), ("TP4", "BRK_DRAIN"), ("TP5", "VREG"), ("TP6", "DGATE"),
       ("TP7", "HGATE"), ("TP8", "EN"), ("TP9", "TRIM"), ("TP10", "SENSE_P"), ("TP11", "SENSE_N"), ("TP12", "CMP_OUT"),
       ("TP13", "BRK_GATE"), ("TP14", "STRETCH"), ("TP15", "GND"), ("TP16", "GND"), ("TP17", "GND"),
       ("TP18", "OV"), ("TP19", "CDVDT"), ("TP20", "ILK_B"), ("TP21", "BRK_GATE2"), ("TP22", "PU_TH"),
       ("TP23", "VG"), ("TP24", "GND"), ("TP25", "GND")]
FLAGS = [("VIN", 45, 40), ("GND", 60, 75), ("MID", 175, 65), ("VREG", 100, 185), ("VOUT", 205, 40)]
TEXT = [
    ("POWER PATH: LM74800 ideal diode (Q1||Q7 block regen into the PSU) + soft-start (Q2||Q8, CdVdT = C4,C5,C13,C14)", 20, 20),
    ("OUTPUT BUS: bulk caps, TVS backstop, 3 x XT30 outputs (each sized for the full 25 A supply)", 200, 20),
    ("30 A CONT / 60 A PEAK: paralleled MOSFETs, 2nd brake FET, thermal cut-off", 430, 20),
    ("J11: normally-closed thermal switch on the brake resistors opens -> brake disabled", 430, 210),
    ("11.6 V CONTROL RAIL (CJ431 + MMBT5551 follower)", 20, 160),
    ("REGEN CLAMP: brake ON at VOUT - VIN = 0.667 x V(TRIM) - 0.14 V (RV1 sets 3.0 to 7.6 V), OFF 2 V lower", 140, 150),
    ("LED STRETCHER: red LED stays on >= 0.3 s after any brake pulse", 295, 150),
    ("TEST POINTS (bare pads, not assembled)", 80, 268),
    ("GATE RESISTORS R30-R33: one per paralleled FET (stops parasitic oscillation in linear soft start)", 20, 30),
    ("BRAKE INTERLOCK (Q10, Q11): brake held off while the ideal diode conducts", 505, 150),
    ("DEBUG LEDS: D8 white = supply present, D9 yellow = J11 thermal loop open (brake disabled)", 430, 240),
    ("SW1 OFF disconnects the output: plug motors with SW1 OFF. Supply 15-48 V.", 20, 145),
]

def client():
    p = subprocess.Popen([os.path.expanduser("~/.local/opt/konnect-dl/konnect")], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    n = [0]
    def rpc(method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None: msg["params"] = params
        if not notify: n[0] += 1; msg["id"] = n[0]
        p.stdin.write(json.dumps(msg) + "\n"); p.stdin.flush()
        if notify: return None
        while True:
            d = json.loads(p.stdout.readline())
            if d.get("id") == n[0]: return d
    rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "build", "version": "0"}})
    rpc("notifications/initialized", notify=True)
    for ts in ["sch_components", "sch_wiring", "sch_batch", "sch_analysis", "sch_export", "library", "sch_hierarchy"]:
        rpc("tools/call", {"name": "load_toolset", "arguments": {"name": ts}})
    def call(tool, **args):
        r = rpc("tools/call", {"name": tool, "arguments": args})
        res = r.get("result") or {}
        text = "\n".join(c.get("text", "") for c in res.get("content", []))
        if res.get("isError") or "error" in r:
            print(f"!! {tool} {json.dumps(args)[:200]}\n{text[:800]} {r.get('error')}")
            sys.exit(1)
        return text
    return call

call = client()
call("register_symbol_library", library_path=f"{PROJ}/lib/jlc.kicad_sym", nickname="jlc", project=PROJ, scope="project")
call("register_footprint_library", library_path=f"{PROJ}/lib/jlc.pretty", nickname="jlc", project=PROJ, scope="project")
call("set_schematic_page", schematic=SCH, size="A2")
for t, x, y in TEXT:
    call("add_schematic_text", schematic=SCH, text=t, x=x, y=y, bold=True)
for c in P:
    call("add_schematic_component", schematic=SCH, lib_id=c["lib"], x=c["x"], y=c["y"], rotation=c["rot"], unit=c["unit"],
         reference=c["ref"], value=c["val"], footprint=c["fp"])
for ref, x, y in HOLES:
    call("add_schematic_component", schematic=SCH, lib_id="Mechanical:MountingHole", x=x, y=y, reference=ref,
         value="#8-32", footprint="MountingHole:MountingHole_4.5mm")
for i, ref in enumerate(("FID1", "FID2", "FID3")):
    call("add_schematic_component", schematic=SCH, lib_id="Mechanical:Fiducial", x=73 + 12 * i, y=270, reference=ref,
         value="Fiducial", footprint="Fiducial:Fiducial_1mm_Mask2mm")
for i, (ref, net) in enumerate(TPS):
    fp = "TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm" if net == "GND" else "TestPoint:TestPoint_Pad_D1.5mm"
    call("add_schematic_component", schematic=SCH, lib_id="Connector:TestPoint", x=80 + 12 * i, y=280, reference=ref,
         value=net, footprint=fp)
    P.append(dict(ref=ref, pins={"1": net}))
for i, (net, x, y) in enumerate(FLAGS):
    call("add_schematic_component", schematic=SCH, lib_id="power:PWR_FLAG", x=x, y=y, reference=f"#FLG0{i+1}")
    P.append(dict(ref=f"#FLG0{i+1}", pins={"1": net}))
nets = defaultdict(list)
for c in P:
    for pin, net in c["pins"].items():
        nets[net].append({"reference": c["ref"], "pin_number": pin})
for net, pins in nets.items():
    call("batch_connect_to_net", schematic=SCH, net_name=net, pins=pins, stub_length=2.54, label_type="global_label")
edits, seen = [], set()
for c in P:
    if "lcsc" not in c or c["ref"] in seen: continue
    seen.add(c["ref"])
    fields = {"LCSC": c["lcsc"]}
    if c["note"]: fields["Assembly"] = c["note"]
    edits.append({"reference": c["ref"], "fields": fields})
call("batch_edit_schematic_components", schematic=SCH, edits=edits, create_missing=True)
call("batch_add_no_connect", schematic=SCH, positions=[{"x": 87.63, "y": 118.11}, {"x": 95.25, "y": 125.73}, {"x": 133.35, "y": 77.47}])
print("placed", len(seen), "parts on", len(nets), "nets")
