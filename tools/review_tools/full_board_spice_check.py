#!/usr/bin/env python3
"""Full-board SPICE verification suite (tools/review_tools/full_board_spice_check.py).

Closes the behavioural-model gaps in the standalone .cir decks by modelling every active IC
from its datasheet electrical table across 8 operating and fault scenarios:
  - U1 LM74800-Q1 (hysteretic CAP charge pump at 1.3 mA min corner, EN/UVLO, OV, VSNS-SW switch,
    DGATE 10.5 mV linear forward-drop servo + 12.3 uA reg sink + -4.5 mV fast reverse pull-down +
    both 200 mV strict comparator recovery and linear recovery, HGATE 55 uA source / 260 mA sink)
  - U2 CJ431 + Q4 BCP56-16 + D10 (1N4148WS) + D12 (BZT52C16) + R6/R7/R8/R26/C9/C10 (real 11.6 V rail)
  - U3 LM393 (U3A brake comparator + U3B LED stretcher, gated on rail power)
  - U4 UCC27517 (4.2 V / 3.9 V VDD UVLO + 2.2 V / 1.2 V input hysteresis + C19 local bypass)
  - Q1,Q7,Q2,Q8,Q3,Q9 CRSS042N10N VDMOS, Q10/Q11 interlock, Q12 thermal-open LED, Q13 BRK_FLAG, BUS_ADC

Exits 0 with "PASS" only if all 8 simulations converge and every safety/threshold assertion holds.
"""
import os, re, subprocess, sys, tempfile

COMMON_LIB = r"""
* === Device Models ===
.model NFET  VDMOS(nchan Vto=3.1 Kp=120 Rd=1.6m Rs=1m Rg=2 Cgdmax=2.5n Cgdmin=33p Cgs=6.7n Cjo=7.3n M=0.5 Vj=0.8 Rb=4m Is=1e-10 N=1.1)
.model NFET_HI VDMOS(nchan Vto=3.4 Kp=120 Rd=1.6m Rs=1m Rg=2 Cgdmax=2.5n Cgdmin=33p Cgs=6.7n Cjo=7.3n M=0.5 Vj=0.8 Rb=4m Is=1e-10 N=1.1)
.model NFET_2N7002 VDMOS(nchan Vto=2.1 Kp=0.8 Rd=1.2 Rs=0.5 Rg=10 Cgdmax=40p Cgdmin=5p Cgs=50p Cjo=30p Is=1e-12)
.model DAV   D(Is=1e-14 BV=108 IBV=1m Rs=5m)
.model DSS   D(Is=5e-9 N=1.5 Rs=0.04 Cjo=150p BV=100 IBV=1m)
.model DTVS  D(Is=1e-12 BV=58 IBV=1m Rs=1.3 Cjo=1n)
.model D4148 D(Is=2.5n N=1.75 Rs=0.6 Cjo=2p BV=100 IBV=100u)
.model DZ12  D(Is=1e-12 N=1.0 BV=12.0 IBV=5m Rs=5 Cjo=80p)
.model DZ16  D(Is=1e-12 N=1.0 BV=16.2 IBV=5m Rs=8 Cjo=60p)
.model DLEDG D(Is=1e-20 N=2.1 Rs=8 Cjo=15p)
.model DLEDR D(Is=1e-18 N=1.9 Rs=8 Cjo=15p)
.model DLEDW D(Is=1e-22 N=2.4 Rs=10 Cjo=15p)
.model DLEDY D(Is=1e-19 N=2.0 Rs=8 Cjo=15p)
.model QN_3904 NPN(Is=1e-14 Bf=180 Vaf=100 Cje=8p Cjc=4p Tf=0.3n)
.model QP_5401 PNP(Is=1e-14 Bf=120 Vaf=100 Cje=12p Cjc=6p Tf=0.5n)
.model QP_8550 PNP(Is=2e-14 Bf=160 Vaf=80  Cje=15p Cjc=8p Tf=0.5n)
.model QN_BCP56 NPN(Is=5e-14 Bf=160 Vaf=80 Ikf=1.5 Rb=1 Re=0.15 Rc=0.2 Cje=60p Cjc=25p Tf=1.2n)
.model D_EB_BREAK D(Is=1e-15 BV=6.0 IBV=1m Rs=1)

* === CJ431 Programmable Shunt Regulator (Pin 1=REF, Pin 2=K, Pin 3=A) ===
.subckt CJ431 REF K A
Iref K REF 1.5u
Dka A K D4148
Bik K A I = V(K,A) > 0 ? 0.12 * ln(1 + exp(min(40, (V(REF,A) - 2.500)/0.002))) * tanh(max(0, V(K,A) - 1.8)/0.3) + V(K,A)*1e-7 : 0
Cka K A 20p
.ends CJ431

* === UCC27517 Single Gate Driver with 4.2V/3.9V UVLO & 2.2V/1.2V Hysteresis ===
.subckt UCC27517 VDD GND INP INM OUT
Rin INP GND 230k
Iq  VDD GND 100u
.model SW_UVLO SW(Vt=4.05 Vh=0.15 Ron=1 Roff=1e6)
.model SW_IN   SW(Vt=1.70 Vh=0.50 Ron=1 Roff=1e6)
V1 v1 0 1
Suv uv_n 0 VDD GND SW_UVLO
Ruv v1 uv_n 1k
Buv uv_ok 0 V = V(uv_n) < 0.5 ? 1 : 0
Sin in_n 0 INP INM SW_IN
Rpu v1 in_n 1k
Bdrv drv_ctl 0 V = (V(uv_ok) > 0.5) && (V(in_n) < 0.5) ? 1 : 0
Rdel drv_ctl drv 20
Cdel drv 0 500p
Bout_hi VDD OUT I = V(drv) * (V(VDD, OUT) / 5.0)
Bout_lo OUT GND I = (1 - V(drv)) * (V(OUT, GND) / 0.6)
.ends UCC27517

* === Pin-Accurate LM74800-Q1 Datasheet Macromodel ===
* Pins: 1:DGATE 2:A 3:VSNS 4:SW 5:OV 6:EN_UVLO 7:GND 8:HGATE 9:OUT 10:VS 11:CAP 12:C
.subckt LM74800_Q1 DGATE A VSNS SW OV EN_UVLO GND HGATE OUT VS CAP C params: ICAP_MA=2.7 IHG_UA=55 STRICT_177MV=1 VAC_FWD_MV=177
.model SW_EN   SW(Vt=0.705  Vh=0.035  Ron=10 Roff=1e7)
.model SW_UVLO SW(Vt=1.1815 Vh=0.0495 Ron=10 Roff=1e7)
.model SW_OV   SW(Vt=1.1805 Vh=0.0505 Ron=10 Roff=1e7)
.model SW_VSP  SW(Vt=2.35   Vh=0.25   Ron=10 Roff=1e7)
.model SW_VAP  SW(Vt=2.275  Vh=0.075  Ron=10 Roff=1e7)
.model SW_CP   SW(Vt=12.7   Vh=0.5    Ron=10 Roff=1e7)
.model SW_CPUV SW(Vt=6.05   Vh=0.55   Ron=10 Roff=1e7)
.model D_CLAMP D(Is=1e-13 N=1 Rs=0.5)

Ien EN_UVLO GND 52n
Iov OV GND 53n
Biq VS GND I = V(en_ok) > 0.5 ? 413u * tanh(max(0, V(VS,GND))/1.0) : 2.87u * tanh(max(0, V(VS,GND))/1.0)

V1 v1 0 1
Sen   n_en   0 EN_UVLO GND SW_EN
Ren   v1 n_en 1k
Ben   en_ok  0 V = V(n_en) < 0.5 ? 1 : 0

Suv   n_uv   0 EN_UVLO GND SW_UVLO
Ruv   v1 n_uv 1k
Buv   uv_ok  0 V = V(n_uv) < 0.5 ? 1 : 0

Sov   n_ov   0 OV GND SW_OV
Rov   v1 n_ov 1k
Bovraw ov_raw 0 V = V(n_ov) < 0.5 ? 1 : 0
Rovd  ov_raw ov_flt 4k
Covd  ov_flt 0 1n

Svsp  n_vsp  0 VS GND SW_VSP
Rvsp  v1 n_vsp 1k
Bvsp  vs_ok  0 V = V(n_vsp) < 0.5 ? 1 : 0

Svap  n_vap  0 A GND SW_VAP
Rvap  v1 n_vap 1k
Bvap  va_ok  0 V = V(n_vap) < 0.5 ? 1 : 0

Rensm en_ok en_ok_f 1k
Censm en_ok_f 0 100p IC=0
Bvsns VSNS SW I = V(VSNS, SW) * (1e-8 + max(0, min(1, V(en_ok_f))) / 19.5)

Scp   n_cp   0 CAP VS SW_CP
Rcp   v1 n_cp 1k
Bcp_run cp_run 0 V = (V(en_ok) > 0.5) && (V(vs_ok) > 0.5) && (V(n_cp) > 0.5) ? 1 : 0
Bicp VS CAP I = V(cp_run) * ({ICAP_MA} * 1m) * tanh(max(0, 14.2 - V(CAP,VS))/0.5) - (1 - V(cp_run)) * 15u * tanh(max(0, V(CAP,VS))/0.2)
Bicp_gnd VS GND I = V(cp_run) * ({ICAP_MA} * 1m)
Dcp_lo VS CAP D_CLAMP

Scpuv n_cpuv 0 CAP VS SW_CPUV
Rcpuv v1 n_cpuv 1k
Bcpuv cp_ok 0 V = V(n_cpuv) < 0.5 ? 1 : 0

* === DGATE Controller ===
Bdg_en dg_en_raw 0 V = (V(en_ok) > 0.5) && (V(vs_ok) > 0.5) && (V(va_ok) > 0.5) && (V(cp_ok) > 0.5) ? 1 : 0
Bdg_chg 0 dg_rdy I = V(dg_en_raw) > V(dg_rdy) ? (V(dg_en_raw)-V(dg_rdy))/120k : (V(dg_en_raw)-V(dg_rdy))/6k
Cdg_rdy dg_rdy 0 1n IC=0
Rdg_rdy dg_rdy 0 100meg

Brev_set rev_s 0 V = V(A,C) < -0.0045 ? 1 : 0
Brev_rst rev_r 0 V = {STRICT_177MV} > 0.5 ? (V(A,C) > ({VAC_FWD_MV}*1m) ? 1 : 0) : (V(A,C) > 0.002 ? 1 : 0)
Brev_ff 0 rev_q I = V(rev_s) > 0.5 ? (1 - V(rev_q))/350 : (V(rev_r) > 0.5 ? (0 - V(rev_q))/2000 : (V(rev_q) > 0.5 ? (1 - V(rev_q))/50k : (0 - V(rev_q))/50k))
Crev_q rev_q 0 1n IC=0
Rrev_q rev_q 0 100meg

Bdg_fast DGATE A I = ((V(dg_rdy) < 0.5) || (V(rev_q) > 0.5)) ? V(DGATE, A) / 4.1 : 0
Bdg_src CAP DGATE I = ((V(dg_rdy) >= 0.5) && (V(rev_q) <= 0.5) && (V(A,C) > 0.0105)) ? min(20m, 0.22*(V(A,C)-0.0105)) * tanh(max(0, min(V(CAP,DGATE), V(A)+11.5-V(DGATE)))/0.25) : 0
Bdg_snk DGATE A   I = ((V(dg_rdy) >= 0.5) && (V(rev_q) <= 0.5) && (V(A,C) < 0.0105)) ? min(40u, 1.17m*(0.0105-V(A,C))) * tanh(max(0, V(DGATE,A))/0.2) : 0
Ddg_lo A DGATE D_CLAMP

* === HGATE Controller ===
Bhg_en hg_en_raw 0 V = (V(uv_ok) > 0.5) && (V(vs_ok) > 0.5) && (V(cp_ok) > 0.5) && (V(ov_flt) < 0.5) ? 1 : 0
Rhd hg_en_raw hg_on 4.6k
Chd hg_on 0 1n IC=0
Bhg_src CAP HGATE I = V(hg_on) > 0.5 ? ({IHG_UA}*1u) * tanh(max(0, min(V(CAP,HGATE), V(OUT)+11.1-V(HGATE)))/0.2) : 0
Bhg_snk HGATE OUT I = V(hg_on) <= 0.5 ? min(0.26, max(0, V(HGATE,OUT))/25.0) : 0
Dhg_lo OUT HGATE D_CLAMP
.ends LM74800_Q1
"""

BOARD_NETLIST = r"""
* === Full Regen-Clamp + Soft-Start Board Netlist ===
RPSU psu p1 {RPSU_VAL}
LCAB p1 j1 {LCAB_VAL}
RJ1  j1 vin 0.5m
C17  vin c17a 470u IC={IC_VIN}
RC17 c17a 0 80m
C1   vin 0 1u IC={IC_VIN}
VD1  0 d1a 0
D1   d1a vin DTVS
R36  vin ledv_a 33k
D8   ledv_a 0 DLEDW

RVIN vin a 0.64m
R30  dgate dg1 10
R31  dgate dg7 10
VQ1S a s1 0
M1   mid dg1 s1 s1 NFET
M7   mid dg7 a  a  NFET_HI
C2   mid 0 1u IC={IC_MID}
C3   cap mid 1u IC={IC_CAP_VS}

R32  hgate hg2 10
R33  hgate hg8 10
VQ2D mid d2q 0
M2   d2q hg2 vq vq NFET
VQ8D mid d8q 0
M8   d8q hg8 vq vq NFET_HI
RVOUT vq vout 1.15m

R1   vin en 1meg
R2   en  0  100k
.model SW_SW1 SW(Vt=0.5 Vh=0.05 Ron=0.1 Roff=100meg)
Ssw1 en 0 sw1_off_ctl 0 SW_SW1
R3   ov_top ov 100k
R4   ov 0 2.2k
R5   hgate cdvdt 1k
CDVDT cdvdt 0 400n IC={IC_CDVDT}
VD11 vout d11a 0
D11  d11a hgate DZ12
XU1  dgate a vin ov_top ov en 0 hgate vout mid cap mid LM74800_Q1 ICAP_MA={ICAP_MA} IHG_UA={IHG_UA} STRICT_177MV={STRICT_177MV} VAC_FWD_MV={VAC_FWD_MV}

CBULK vout cb1 1880u IC={IC_VOUT}
RCB   cb1 0 20m
C6    vout 0 1u IC={IC_VOUT}
D2    0 vout DTVS
RMC   vout m2 16m
LMC   m2 vmot 0.7u
CMOT  vmot cm1 600u IC={IC_VOUT}
RCM   cm1 0 30m

R6   vout ref_k 10k
XU2  ref_fb ref_k 0 CJ431
D12  0 ref_k DZ16
R7   ref_k ref_fb 39k
R8   ref_fb 0 10k
R26  vout rail_c 470
Q4   rail_c ref_k vreg QN_BCP56
VDEB ref_k eb4a 0
Deb4 eb4a vreg D_EB_BREAK
VD10 vreg d10a 0
D10  d10a ref_k D4148
C9   vreg 0 10u IC={IC_VREG}
C10  vreg 0 100n IC={IC_VREG}
R9   vreg ledg_a 10k
D3   ledg_a 0 DLEDG

R10  vout sp {R10_VAL}
R11  sp 0 {R11_VAL}
R12  sp 0 {R12_VAL}
R13  vg sp {R13_VAL}
R14  vin sn {R14_VAL}
R15  sn 0 {R15_VAL}
R16  trim sn {R16_VAL}
RRV1_HI vreg trim {RRV1_HI_VAL}
RRV1_LO trim trim_lo {RRV1_LO_VAL}
R25  trim_lo 0 6.8k
VOS  sn snx {VOS_VAL}

.model OCSW SW(Vt=0.5 Vh=0.05 Ron=60 Roff=100meg)
Bcmpa cmpctl 0 V = (V(vreg) > 1.5) && (V(sp) > V(snx)) ? 0 : 1
Rcf cmpctl cmpd 1k
Ccf cmpd 0 300p IC=1
Soa cmpout 0 cmpd 0 OCSW

R17  vreg pu_th 4.7k
RJ11 pu_th cmpout {RJ11_VAL}
R27  cmpout 0 100k
C18  cmpout 0 1n IC=0
C19  vreg 0 1u IC={IC_VREG}

R34  dgate ilk_e 47k
R41  vin ilk_base 10k
Q10  ilk_b ilk_base ilk_e QP_5401
R35  ilk_b 0 100k
Q11  cmpout ilk_b 0 QN_3904

Q12  thc thb pu_th QP_8550
R37  cmpout thb 1meg
R38  thc ledt_a 2.2k
D9   ledt_a 0 DLEDY

XU4  vreg 0 cmpout 0 vg UCC27517
R18  vg g3 10
R19  g3 0 10k
R28  vg g9 10
R29  g9 0 10k
M3   drn g3 0 0 NFET
M9   drn g9 0 0 NFET_HI
DAV3 0 drn DAV
RBR  vout br1 {RBRK_VAL}
LBR  br1 drn {LBRK_VAL}
D4   drn vout DSS
D7   drn vout DSS

D5   vg str_d D4148
R20  str_d stretch 100
C12  stretch 0 100n IC=0
R21  stretch 0 2meg
R40  stretch stretch_in 100k
R22  vreg led_ref 47k
R23  led_ref 0 10k
Bcmpb ledr_ctl 0 V = (V(vreg) > 1.5) && (V(stretch_in) > V(led_ref)) ? 1 : 0
Solb ledr_k 0 ledr_ctl 0 OCSW
R24  vreg ledr_a 4.7k
D6   ledr_a ledr_k DLEDR

R44  vout bus_adc 100k
R45  bus_adc 0 5.6k
C20  bus_adc 0 100n IC=0
R42  vg flag_g 1k
M13  brk_flag flag_g 0 0 NFET_2N7002
RPU_MCU v_mcu brk_flag 10k
VMCU v_mcu 0 3.3
"""

DEFAULT_PARAMS = dict(
    RPSU_VAL="20m", LCAB_VAL="1u",
    IC_VIN=0, IC_MID=0, IC_CAP_VS=0, IC_VOUT=0, IC_CDVDT=0, IC_VREG=0,
    ICAP_MA=2.7, IHG_UA=55, STRICT_177MV=1, VAC_FWD_MV=177,
    R10_VAL="100k", R11_VAL="20k", R12_VAL="220k", R13_VAL="510k",
    R14_VAL="100k", R15_VAL="20k", R16_VAL="150k",
    RV1_POS=0.258, VOS_VAL=0.0, RJ11_VAL="0.01",
    RBRK_VAL=2.0, LBRK_VAL="1u",
)

def make_param_line(overrides):
    p = dict(DEFAULT_PARAMS)
    p.update(overrides)
    pos = float(p.pop("RV1_POS"))
    p["RRV1_HI_VAL"] = max(1.0, (1.0 - pos) * 10000.0)
    p["RRV1_LO_VAL"] = max(1.0, pos * 10000.0)
    return ".param " + " ".join(f"{k}={v}" for k, v in p.items())

def run_deck(name, extra_params, stim_and_meas, checks):
    deck = "\n".join([
        f"* {name}",
        make_param_line(extra_params),
        COMMON_LIB,
        BOARD_NETLIST,
        stim_and_meas,
        ".end\n"
    ])
    with tempfile.NamedTemporaryFile("w", suffix=".cir", delete=False) as f:
        f.write(deck)
        path = f.name
    try:
        r = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True, timeout=120)
        out = r.stdout + "\n" + r.stderr
        if "Simulation interrupted" in out or "timestep too small" in out or r.returncode != 0:
            print(f"FAIL: {name} aborted")
            print("\n".join(out.splitlines()[-30:]))
            return False
        meas = {}
        for line in out.splitlines():
            m = re.match(r"^\s*([a-zA-Z0-9_]+)\s*=\s*([-+0-9.eE]+)", line)
            if m:
                meas[m.group(1)] = float(m.group(2))
        errs = []
        for key, lo, hi, desc in checks:
            if key not in meas:
                errs.append(f"missing {key} ({desc})")
                continue
            val = meas[key]
            if not (lo <= val <= hi):
                errs.append(f"{key}={val:.4g} outside [{lo}, {hi}] ({desc})")
        if errs:
            print(f"FAIL: {name}: " + "; ".join(errs))
            return False
        summary = ", ".join(f"{k}={meas[k]:.4g}" for k, _, _, _ in checks)
        print(f"  ok  {name}: {summary}")
        return True
    finally:
        if os.path.exists(path):
            os.unlink(path)

def main():
    ok = True

    # 1 & 2: 48V cold power-up, min 1.3mA CAP charge pump, soft-start, 27A resistive load, then live SW1 turn-off
    ok &= run_deck(
        "cold_startup_and_27a_turnoff_48v",
        dict(ICAP_MA=1.3, IHG_UA=55, LCAB_VAL="2u"),
        r"""
VPSU psu 0 48
VSW1 sw1_off_ctl 0 PWL(0 1 15m 1 15.2m 0 600m 0 600.2m 1)
* Switch in a 1.778 ohm resistive load (27 A at 48 V) at t=480 ms
.model SW_LD SW(Vt=0.5 Vh=0.05 Ron=1.778 Roff=10meg)
VLD ld_ctl 0 PWL(0 0 480m 0 482m 1 700m 1)
SLD vmot 0 ld_ctl 0 SW_LD
.option method=gear reltol=2e-3 abstol=1e-7 vntol=1e-4
.tran 20u 650m 0 100u uic
.control
run
let vcap_vs = v(cap) - v(mid)
let vgs_hg  = v(hgate) - v(vout)
let vgs_dg  = v(dgate) - v(a)
meas tran vout_sw_off    MAX v(vout)   from=0 to=14.9m
meas tran vcap_min_on    MIN vcap_vs   from=50m to=599m
meas tran vreg_steady    AVG v(vreg)   from=450m to=590m
meas tran vg_false_max   MAX v(vg)     from=0 to=645m
meas tran dgate_0a       AVG vgs_dg    from=440m to=475m
meas tran dgate_27a      AVG vgs_dg    from=500m to=590m
meas tran vgs_hg_max     MAX vgs_hg    from=15m to=645m
meas tran vgs_hg_min     MIN vgs_hg    from=599m to=645m
meas tran vin_27a_off_pk MAX v(vin)    from=599m to=620m
meas tran vout_after_off FIND v(vout)  AT=645m
.endc
""",
        [
            ("vout_sw_off",    -0.05, 0.05,  "output off while SW1=OFF"),
            ("vcap_min_on",    11.5,  14.0,  "CAP-VS stays regulated at min 1.3mA pump"),
            ("vreg_steady",    11.3,  11.9,  "CJ431/BCP56 11.6V rail in regulation"),
            ("vg_false_max",   -0.1,  0.2,   "no false brake pulse during startup/load/turnoff"),
            ("dgate_0a",       2.0,   4.5,   "LM74800 linear servo near Vth at 0A"),
            ("dgate_27a",      10.0,  13.5,  "LM74800 full gate drive at 27A"),
            ("vgs_hg_max",     10.5,  13.5,  "HGATE-OUT clamped <=15V abs max by D11"),
            ("vgs_hg_min",     -0.25, 0.2,   "HGATE-OUT stays >=-0.3V abs max on turnoff"),
            ("vin_27a_off_pk", 48.0,  55.0,  "C17 holds 27A turnoff spike <<65V U1 limit"),
            ("vout_after_off", -0.05, 0.1,   "output discharges cleanly to 0V after SW1=OFF"),
        ],
    )

    # 3: Input overvoltage cutoff & automatic recovery
    ok &= run_deck(
        "ov_cutoff_and_recovery",
        dict(IC_VIN=36, IC_MID=36, IC_CAP_VS=12.8, IC_VOUT=36, IC_CDVDT=47, IC_VREG=11.6),
        r"""
VPSU psu 0 PWL(0 36 5m 36 25m 61 30m 61 50m 48 250m 48)
VSW1 sw1_off_ctl 0 0
RLOAD vmot 0 18
.option method=gear reltol=2e-3 abstol=1e-7 vntol=1e-4
.tran 10u 250m 0 100u uic
.control
run
let vgs_hg = v(hgate) - v(vout)
meas tran vin_at_ov_trip FIND v(vin) WHEN vgs_hg=2.0 FALL=1
meas tran vout_max_ov    MAX v(vout) from=0 to=250m
meas tran vout_recovered FIND v(vout) AT=248m
.endc
""",
        [
            ("vin_at_ov_trip", 55.5, 58.5, "OV trips around 57.2V"),
            ("vout_max_ov",    45.0, 58.5, "VOUT disconnected before OV surge passes"),
            ("vout_recovered", 47.5, 48.2, "VOUT soft-starts back to 48V after OV clears"),
        ],
    )

    # 4: Slow regen zero-crossing ramp (+5A -> -15A -> +0.5A)
    ok &= run_deck(
        "slow_regen_zero_crossing_36v",
        dict(IC_VIN=36, IC_MID=36, IC_CAP_VS=12.8, IC_VOUT=36, IC_CDVDT=47, IC_VREG=11.6, STRICT_177MV=1, VAC_FWD_MV=177),
        r"""
VPSU psu 0 36
VSW1 sw1_off_ctl 0 0
IARM 0 vmot PWL(0 -5 5m -5 15m 15 35m 15 40m -0.5 85m -0.5)
.option method=gear reltol=2e-3 abstol=1e-7 vntol=1e-4
.tran 2u 85m 0 20u uic
.control
run
let vgs_dg = v(dgate) - v(a)
meas tran irev_into_psu  MAX i(VPSU) from=5m to=40m
meas tran vmot_peak      MAX v(vmot) from=5m to=40m
meas tran vreg_min       MIN v(vreg) from=2m to=85m
meas tran vg_end         FIND v(vg)  AT=83m
meas tran dgate_end_0p5a FIND vgs_dg AT=83m
meas tran bus_adc_at_40v MAX v(bus_adc) from=10m to=35m
.endc
""",
        [
            ("irev_into_psu",  -10.0, 0.05,  "zero reverse current into PSU on slow regen ramp"),
            ("vmot_peak",      39.5,  41.0,  "motor bus clamped ~40.4V (<44V moteus limit)"),
            ("vreg_min",       11.2,  11.8,  "control rail steady under 1 kHz gate drive load"),
            ("vg_end",         -0.05, 0.05,  "brake off once forward load resumes"),
            ("dgate_end_0p5a", 2.5,   6.0,   "DGATE re-engages cleanly at 0.5A forward"),
            ("bus_adc_at_40v", 2.0,   2.2,   "BUS_ADC telemetry scaled <3.3V"),
        ],
    )

    # 5A & 5B: Worst-case 48V brake-latch corner under both VAC_FWD=200mV strict latch and linear recovery
    for mode, tag in [(1, "strict_200mv"), (0, "linear_10mv")]:
        ok &= run_deck(
            f"brake_latch_48v_{tag}",
            dict(
                IC_VIN=48, IC_MID=48, IC_CAP_VS=12.8, IC_VOUT=47.9, IC_CDVDT=59, IC_VREG=11.6,
                STRICT_177MV=mode, VAC_FWD_MV=200,
                R10_VAL="99000", R11_VAL="20200", R12_VAL="222200", R13_VAL="504900",
                R14_VAL="101000", R15_VAL="19800", R16_VAL="148500",
                RV1_POS=0.0, VOS_VAL=-0.009, LBRK_VAL="10u", RBRK_VAL=2.5
            ),
            r"""
VPSU psu 0 48
VSW1 sw1_off_ctl 0 0
IREGEN 0 vmot PWL(0 0 5m 0 5.1m 15 30m 15 30.1m 0)
.option method=gear reltol=2e-3 abstol=1e-7 vntol=1e-4
.tran 1u 80m 0 10u uic
.control
run
let ipsu_draw = -i(VPSU)
meas tran ipsu_after AVG ipsu_draw from=50m to=80m
meas tran vg_after   MAX v(vg)     from=50m to=80m
.endc
""",
            [
                ("ipsu_after", 0.0,   0.05, "PSU draw drops to milliamps (no 24A brake latch)"),
                ("vg_after",   -0.05, 0.05, "brake gate completely off after regen ends"),
            ],
        )

    # 6: Unplugged PSU (J1 open) + 8A backdrive from 0V dead board
    ok &= run_deck(
        "unplugged_psu_backdrive_8a",
        dict(RPSU_VAL="100meg", IC_VIN=0, IC_MID=0, IC_CAP_VS=0, IC_VOUT=0, IC_CDVDT=0, IC_VREG=0),
        r"""
VPSU psu 0 0
VSW1 sw1_off_ctl 0 1
IREGEN 0 vmot PWL(0 0 2m 0 5m 8 80m 8 82m 0)
.option method=gear reltol=2e-3 abstol=1e-7 vntol=1e-4
.tran 5u 100m 0 50u uic
.control
run
meas tran vout_unplug_pk MAX v(vout) from=0 to=100m
meas tran vin_leak_pk    MAX v(vin)  from=0 to=100m
meas tran ibrk_unplug_pk MAX i(LBR)  from=0 to=100m
.endc
""",
        [
            ("vout_unplug_pk", 14.0, 18.0, "self-powered brake clamps 8A backdrive at ~16V"),
            ("vin_leak_pk",    -0.1, 0.05, "unplugged J1 male pins stay isolated at 0V"),
            ("ibrk_unplug_pk", 7.5,  8.5,  "brake resistor absorbs full 8A backdrive"),
        ],
    )

    # 7: Sudden VOUT dead-short from 48V (D10 Q4 E-B protection & D11 HGATE clamp)
    ok &= run_deck(
        "vout_short_circuit_48v",
        dict(IC_VIN=48, IC_MID=48, IC_CAP_VS=12.8, IC_VOUT=48, IC_CDVDT=59, IC_VREG=11.6),
        r"""
VPSU psu 0 48
VSW1 sw1_off_ctl 0 PWL(0 0 1.99m 0 2.00m 1)
.model SW_SHORT SW(Vt=0.5 Vh=0.05 Ron=0.05 Roff=100meg)
VSH sh_ctl 0 PWL(0 0 2.00m 0 2.001m 1)
SSH vout 0 sh_ctl 0 SW_SHORT
.option method=gear reltol=2e-3 abstol=1e-7 vntol=1e-4
.tran 500n 10m 0 5u uic
.control
run
let veb_q4 = v(vreg) - v(ref_k)
let vgs_hg = v(hgate) - v(vout)
meas tran q4_veb_rev_max MAX veb_q4  from=1.9m to=10m
meas tran q4_ieb_brk_max MAX i(VDEB) from=1.9m to=10m
meas tran vgs_hg_short   MAX vgs_hg  from=1.9m to=10m
.endc
""",
        [
            ("q4_veb_rev_max", 0.5,  1.2,  "D10 clamps Q4 reverse Veb << 5V BVebo"),
            ("q4_ieb_brk_max", -1e-3, 1e-3, "zero Q4 E-B avalanche current"),
            ("vgs_hg_short",   9.0,  13.5, "D11 + R5 keep HGATE-OUT < 15V abs max"),
        ],
    )

    # 8: Fast 1 us input micro-short (VIN 48V -> 0V while VOUT=48V)
    ok &= run_deck(
        "input_microshort_48v",
        dict(IC_VIN=48, IC_MID=48, IC_CAP_VS=12.8, IC_VOUT=48, IC_CDVDT=59, IC_VREG=11.6),
        r"""
VPSU psu 0 PWL(0 48 1m 48 1.001m 0 10m 0)
VSW1 sw1_off_ctl 0 0
RLOAD vmot 0 48
.option method=gear reltol=2e-3 abstol=1e-7 vntol=1e-4
.tran 200n 6m 0 2u uic
.control
run
meas tran irev_q1_peak   MIN i(VQ1S) from=0.99m to=2m
meas tran vout_holdup_5m FIND v(vout) AT=5m
.endc
""",
        [
            ("irev_q1_peak",   -6.0, 0.0,  "fast DGATE turnoff bounds reverse current spike"),
            ("vout_holdup_5m", 18.0, 48.0, "ideal diode holds up output bus during VIN short"),
        ],
    )

    print("PASS: all 8 full-board IC macromodel SPICE checks passed" if ok else "FAIL: full-board SPICE checks failed")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
