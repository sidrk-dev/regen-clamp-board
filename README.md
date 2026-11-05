# Regen clamp + soft-start board (rev E)

**DO NOT ORDER OR POWER THIS REVISION YET.** Rev E fixes the reversed CJ431 and the
other faults listed below, but [Open decisions](#open-decisions) still lists order
blockers, and nothing here has been built or measured. The control rail and braking
behaviour below are design targets.

A 125 × 100 mm two-layer board that sits between a bench supply and the arm.
The supply plugs into an XT60 in the middle of the left edge; three XT30
outputs sit in the middle of the right edge, and any one of them can carry the
whole supply: output 1 feeds the arm's IM6014 bus (all seven motors on one XT30
2+2 run), output 2 feeds the gripper's moteus controller, and output 3 is a
spare. A #8-32 mounting hole sits in each corner. It does two jobs:

1. **Regen clamp.** An ideal diode stops motor regeneration from flowing back
   into the supply. When braking pushes the motor bus a set amount above the
   supply, two MOSFETs dump the energy into an external brake resistor. A red
   LED stretches the brake indication by roughly 0.3 s under the simulated conditions.
2. **Soft start (precharge).** The output turns on at about 140 V/s, to reduce inrush when enabling a discharged output. It does not prevent
   sparks when connecting a load to an already charged output bus.

Design inspiration: the [ODrive Regen Clamp](https://docs.odriverobotics.com/v/latest/hardware/regen-clamp-datasheet.html)
(ideal diode plus a brake chopper whose threshold is relative to the input) and
the [mjbots mjpower-ss](https://github.com/mjbots/power_dist/tree/main/hw/mjpower-ss)
(a high-side FET ramped slowly to precharge the load, with an output on/off switch).

## Revisions

None of these has been ordered.

Rev E (current), changes from rev D. Most of these were found by independent reviews:

- **U2 CJ431 pins corrected.** The board used TL431 numbering, but this part's SOT-23
  is pin 1 REF, pin 2 K, pin 3 A. The control rail could not have worked.
- **RV1 ends swapped**, so clockwise raises the brake threshold.
- **J1 and J5 holes enlarged** to 2.9 mm with 0.8 × 1.9 mm fixing slots, per the
  XT60PW-M30 drawing served for C98732. The old 2.7 mm holes and 0.6 × 1.7 mm slots
  could not take the connector. The XT60PW-F PDF gives no PCB holes, so J5 uses the
  same sizes.
- **C13 moved out from under Q9, and R30–R33 moved clear of the MOSFET plastic.**
  C13 sat under Q9's body and gate lead, which would have stopped assembly. A DRC
  warning showed it, and it had been wrongly waived as cosmetic.
- **Copper kept out of an 11 mm circle round each corner hole**, both layers, so a
  metal screw head or washer can't short VIN or VOUT to a grounded standoff.
- **D10 (1N4148WS) added across Q4's base and emitter.** When VOUT collapses while C9
  still holds the rail up, the junction no longer breaks down in reverse.
- **D11 (BZT52C12, 12 V) clamps HGATE to VOUT.** The 400 nF soft-start capacitor holds
  HGATE up when VOUT falls, and with no clamp HGATE minus OUT could pass U1's 15 V
  absolute maximum and the MOSFETs' 20 V gate limit: 18 V or more after long regen, far
  more on a supply removal or output short. R5 limits the clamp current to under 50 mA.
  Not modelled in the sim decks, so scope HGATE minus OUT at bring-up.
- **C3 raised to 470 nF**, from TI's VCAP ≥ 10 × (Ciss Q1 + Ciss Q2) with four MOSFETs.
- **C17 (470 µF 63 V) added on VIN.** Only 1 µF sat there, so turning Q2/Q8 off under load
  could spike VIN past U1's 70 V through the supply lead's inductance. Connect the supply with it off.
- **J2–J5 moved out** so each connector's nose hangs off the board edge. The mating plug's
  shell wraps the nose and could have hit the PCB and stopped short of full mating.
- **D1 and D2 ground returns strengthened** from one via to three.
- **U1's exposed pad paste reduced to about 81 %**, per TI's stencil example.

Rev D, changes from rev C:

- XT60 input centred on the left edge and the three XT30 outputs centred on the
  right edge, so the four corners are free for #8-32 holes (4.5 mm, 5 mm in from
  each edge).
- Two debug LEDs: D8 (white, SUPPLY) shows the PSU is connected even with SW1
  off; D9 (yellow, THERM OPEN) shows, while the output bus is up, that the J11
  thermal loop is open, which is the usual reason the brake never fires.
- Eight more test points (TP18–TP25): OV, CDVDT, interlock, second brake gate,
  thermal loop, driver output, and two more GND holes by the input and outputs.
- The VIN pour now fills the area beside U1, which keeps input current density
  down with the XT60 in its new place.
- Design rules raised to JLCPCB's 2-layer 2 oz limits, 0.16 mm track and
  clearance (earlier revisions used 1 oz limits, 0.127/0.15 mm, and 51 tracks
  were too thin for 2 oz). The 2 oz stackup is now recorded in the board file.
- Three fiducials added, and the router's dead-end stubs removed.

Rev C, changes from rev B:

- XT60 input instead of XT90, and 3 outputs instead of 7.
- Brake interlock (Q10, Q11): the brake is intended to be held off while the ideal diode
  conducts. The behavioral latch test covers one tolerance corner; it does not
  prove that every transient and component fault avoids supply-fed braking. In rev B, worst-case
  1 % resistor tolerances at the lowest trim setting could put the brake's
  release point below the supply at 36–48 V, and the brake would then latch on
  and pass about 24 A from the PSU into the resistor.
- One 10 Ω gate resistor per paralleled MOSFET (R30–R33), to stop parasitic
  oscillation while the soft-start pair runs in its linear region.
- Gate drive nets run on the top layer between the power pours, so no gate
  traces cut the bottom ground plane.
- R26 470 Ω (was 1 kΩ): the intended emitter follower has more collector headroom. The
  earlier claim of a guaranteed 11.3 V rail at 15 V is withdrawn; CJ431 bias
  current and the exact U2 pinout must be corrected.
- TVS diodes D1/D2 use JLC's Preferred SMCJ51A (C42371549): same part, no
  extended-part fee.

## Ratings

These are board design targets. Each attached controller must tolerate the maximum
bus voltage, including regen and transients. Unitree's public N6014B-12.6 page
lists 24–75 V input, so 15 V is outside that motor's published range. Moteus
limits depend on the exact model: r4 is 44 V absolute maximum, c1 is 51 V,
and n1/x1 are 54 V. A generic "moteus" output is not validated for 48 V plus regen.
See the manufacturer [Unitree specification](https://www.unitree.com/IM6014/)
and [moteus electrical limits](https://mjbots.github.io/moteus/reference/hardware/).

| Item | Value |
|---|---|
| Supply | 15–48 V DC, any voltage in that range without changing parts. UVLO on at ≈13.5 V; input over-voltage cut-off ≈57 V |
| Current | Design targets of 30 A continuous and 60 A peak; neither is thermally validated. **Order with 2 oz copper.** Minimum track and clearance 0.16 mm |
| Outputs | 3 × XT30PW-F. The copper to each one carries the full 25 A supply. The XT30 itself is rated 15 A continuous (30 A burst), so the arm cable, not the board, limits a single output |
| Input | XT60PW-M (30 A continuous) |
| Mounting | 4 × #8-32, corners, 115 × 90 mm hole spacing. No copper within 5.5 mm of each hole centre on either layer, so the screw head or washer must be under 11 mm across |
| Ambient | U3 is rated 0–70 °C. By calculation Q4's junction reaches about 114 °C at 48 V and 40 °C ambient, and passes its 150 °C limit at 55 V and 70 °C. Don't run it in a hot enclosure |
| Brake threshold | Set with RV1: brake turns on at 3.0 to 7.5 V above the supply and off about 2 V lower |
| Brake | Two paralleled MOSFETs into one external resistor on an XT60. Peak brake current = (supply + trip) ÷ R; keep it at or below 25 A |
| Brake resistor | 2 Ω 200 W at 36 V (or two 4 Ω 100 W in parallel); 1.5 Ω at 24 V; 2.5 Ω at 48 V |
| Resistor over-temperature | J11: a normally-closed thermal switch on the resistor disables the brake when it opens. Fit a jumper if unused. |
| Last-resort protection | One Q136 thermal fuse clamped to the resistor, wired in one resistor lead (see Brake resistor wiring). Required: a shorted brake MOSFET can't be stopped any other way |
| Soft start | 0.26 s from 0 to 36 V; ≈0.55 A inrush into 4000 µF (0.355–0.833 A including HGATE current and ±10 % capacitor tolerance, before DC bias) |
| Backstop | SMCJ51A TVS on input and output. These catch short transients only; they are not a backup for the brake |

At 48 V, +6 V is only a nominal trim ceiling. Source tolerance, divider errors and
switching overshoot must all fit below the selected component limits. This has
not been demonstrated; SMCJ51A breakdown begins at 56.7 V and its rated clamp
voltage is 82.4 V, above the 63 V capacitors and 70 V absolute maximum of U1.

The board passes current, it doesn't make it: running 30 A needs a supply that
can deliver 30 A. The 25 A bench supply limits the whole arm to 25 A.

## Setting the brake threshold

The brake compares the motor bus (VOUT) with the supply (VIN), so it follows the
supply automatically. RV1 sets how far above the supply it trips:

    trip voltage above supply ≈ 0.667 × V(TP9 TRIM) − 0.14 V
    release voltage           ≈ trip − 2.0 V

Measure TP9 to a GND test point and turn RV1: clockwise raises the threshold. 6.2 V at TP9 gives a +4.0 V trip
and +1.9 V release. The range is 4.7–11.6 V at TP9, giving a +3.0 to +7.5 V trip.

These are nominal values. With 1 % resistors the actual trip can be up to about
±0.7 V off at 15 V and ±1.8 V off at 48 V, so measure the actual switching thresholds during corrected-revision bring-up.
The behavioral interlock model prevents supply-fed latching at the tested corner.
Its real DGATE loading, linear regulation, startup and supply-off behavior remain
unverified. A low trim setting is not a general safety guarantee.

## Connections

| Ref | Connector | Where | Use |
|---|---|---|---|
| J1 | XT60PW-M | Left edge, centre | From the PSU (pin 2 +, pin 1 −; check which contact that is, see Bring-up), through a 30 A fuse rated for at least 60 V DC (common MIDI and MAXI automotive fuses are only 32 V) |
| J2 | XT30PW-F | Right edge, top | Output 1: arm IM6014 bus (pin 2 +, pin 1 −; check with a meter before connecting anything, see Bring-up) |
| J3 | XT30PW-F | Right edge, middle | Output 2: gripper moteus controller |
| J4 | XT30PW-F | Right edge, bottom | Output 3: spare |
| J5 | XT60PW-F | Bottom edge | Brake resistor (either way round) |
| J11 | 2-pin header | Middle | Normally-closed thermal switch (e.g. KSD9700, 70–90 °C) on the brake resistor, or a jumper. Twist its two wires together and keep them away from the brake resistor leads |
| SW1 | slide switch | Left edge | Output on/off; check which slider position is on (see Bring-up). Plug or unplug loads only with SW1 off. |
| RV1 | 3362P trimmer | Bottom left | Brake threshold |

## Brake resistor wiring

    J5 pin 2 (VOUT) ── Q136 thermal fuse ── brake resistor ── J5 pin 1 (BRK_DRAIN)

J11 turns the brake off by removing gate drive, so it can't help if a brake
MOSFET has failed short. The resistor then sits across the bus: 16 A and 384 W at
24 V with 1.5 Ω, 18 A and 648 W at 36 V with 2 Ω, 19.2 A and 922 W at 48 V with
2.5 Ω, far above its 200 W rating. Neither the 30 A supply fuse nor a 25 A supply
limit stops that. A correctly selected and installed thermal fuse can open that resistor branch.
Its DC rating does not prove that it opens before the resistor or wiring fails,
or protect against a short that bypasses the fuse.

**Part:** SETfuse Q136, LCSC C22396303. One-shot alloy fuse, opens at 136 °C
(131 ± 2 °C fusing), 25 A, listed for DC 120 V (TÜV-certified for DC per the
datasheet). Hold temperature 102 °C, maximum 200 °C. Buy spares: each one that
opens must be replaced.

**Why this one:** the manufacturer explicitly lists Q136 for 25 A at 120 V DC.
An AC-only rating would not establish DC interruption capability. Peak current
must stay within the selected fuse and resistor limits at the actual bus voltage. The hold temperature sits
above the 70–90 °C J11 switch, so an ordinary overheat trips J11 first and the
fuse is left intact.

**Fitting it:**

- Put it on the resistor body, not on this board: it has to feel the resistor's
  temperature. Clamp it flat against the case with thermal paste. Don't load the
  leads; the datasheet warns against pulling or twisting them.
- Join the leads with crimps, which the datasheet allows, using low-resistance
  connections and wire sized for 25 A. A poor joint heats up and opens the fuse
  early. If you solder, stay within the datasheet's limits: for example 3 s with
  at least 10 mm of lead, using a heat sink.
- Its leads carry bus voltage, so insulate them and keep them off the case.
- Keep it away from heavy vibration, so mount the resistor on the bench, not the arm.

**Limits, so you don't over-trust it:**

- It is slow. The datasheet's oil-bath curve shows about 35 s at 140 °C and 15 s
  at 150 °C, and the resistor's case has to heat up first. My rough estimate is
  20 s or more to bring a 150 g aluminium case up 100 K at 648 W, so expect the
  resistor to be badly overloaded for up to a minute or so. It may fail open first.
  This has not been measured. Keep the resistor on a non-flammable surface.
- Before relying on it, measure the case temperature with a thermocouple during
  your hardest braking. It must stay below 102 °C. Check the J11 switch opens
  first.
- If it opens, the brake is gone and the next regen event will overvolt the bus.
  Stop, find out why, and test Q3/Q9 before fitting a new one (see below).

## LEDs

| LED | Colour | Label | On means |
|---|---|---|---|
| D8 | White | SUPPLY | The PSU is connected. Independent of SW1; dim at 15 V, bright at 48 V |
| D3 | Green | LIVE | The control rail is up, which means the output bus has voltage on it: SW1 is on (it lights during the ramp, not only at the end), or the arm is back-driving the bus |
| D6 | Red | BRAKE | The brake fired in the last 0.3 s |
| D9 | Yellow | THERM OPEN | The J11 loop is open (no jumper, or the resistor's thermal switch has tripped), so the brake is disabled. It shares the control rail with the green LED; visibility is not a rail-voltage guarantee |

## Test points

Bare 1.5 mm pads labelled with their signal on the silkscreen. The GND points
(TP15–TP17, TP24, TP25) are 2 mm plated holes for a scope clip or wire loop: TP25
sits by the input, TP24 by the outputs, the others in the control area.

| TP | Net | What to expect |
|---|---|---|
| TP1 | VIN | Supply voltage |
| TP2 | MID | ≈ VIN when running (drains of Q1/Q7 and Q2/Q8) |
| TP3 | VOUT | ≈ VIN when enabled; nominal ramp ≈0.26 s to 36 V or ≈0.35 s to 48 V |
| TP4 | BRK_DRAIN | ≈ VOUT when idle; drops to ≈0 V while braking |
| TP5 | VREG | Intended ≈11.6 V at adequate supply; low-voltage rail unvalidated |
| TP6 | DGATE | VIN + about 10–13 V at full drive; lower below about 5 A, because U1 regulates 10.5 mV across the MOSFETs; near VIN when off |
| TP7 | HGATE | Ramps toward VOUT + 11 V during soft start; measure HGATE − VOUT to check turn-off, not HGATE to ground. Equals VOUT with SW1 off and a charged bus |
| TP8 | EN | ≈ 0.09 × VIN when on; 0 V with SW1 off |
| TP9 | TRIM | 4.7–11.6 V; sets the brake threshold |
| TP10 | SENSE_P | ≈ 0.15 × VOUT (comparator + input) |
| TP11 | SENSE_N | ≈ 0.15 × VIN plus the trim offset (comparator − input) |
| TP12 | CMP_OUT | 0 V idle, ≈ VREG while braking; stays 0 V if J11 is open or the ideal diode is conducting |
| TP13 | BRK_GATE | Gate of Q3: 0 V idle, ≈ 10 V pulses while braking |
| TP14 | STRETCH | Above 2 V while the red LED is lit |
| TP15–17 | GND | Ground |
| TP18 | OV | With SW1 on, ≈ 0.021 × VIN; SW1 off disconnects this ladder. Rising threshold ≈1.23 V |
| TP19 | CDVDT | Soft-start capacitor: ramps with HGATE at switch-on, then sits near VOUT + 11 V |
| TP20 | ILK_B | Interlock: ≈ 0.6 V while the ideal diode conducts (brake held off); 0 V while it blocks regen |
| TP21 | BRK_GATE2 | Gate of Q9: same as TP13 |
| TP22 | PU_TH | Thermal-loop supply side: equals TP12 with J11 closed; ≈ 7 V with J11 open |
| TP23 | VG | Gate-driver output before R18/R28: ≈ 0 V idle, ≈ 10.5 V while braking |
| TP24, TP25 | GND | Ground by the outputs and by the input |

## When something goes wrong

| Symptom | Check |
|---|---|
| No LEDs at all | PSU, fuse and J1 polarity; TP1 should read the supply |
| White on, green stays off | SW1 on? TP8 above 1.23 V (else UVLO or SW1)? TP18 below 1.23 V (else input over-voltage)? Then TP7/TP19 should ramp |
| Green on, output voltage low or ramping slowly | Soft start into a heavy load: look at TP7 and TP3 together; unplug loads and retry |
| Red stays on with nothing moving | TP10 is above TP11: turn RV1 up (raise TP9) |
| Brake never fires | Yellow lit means J11 is open. Otherwise watch TP12 and TP20 during regen: TP20 must drop to 0 V when the bus rises above the supply |
| Brake fires but the bus still climbs | Brake resistor too large or open, or the thermal fuse has opened (TP4 ≈ 0 V or floating; check the fuse with a meter, power off). TP4 should drop to ≈0 V during braking; check TP13 and TP21 both pulse |
| Resistor hot with no braking, TP4 stuck near 0 V, TP13 at 0 V | A brake MOSFET has failed short: turn the supply off at once. Replace Q3/Q9 before fitting a new thermal fuse |

## Current handling

- Power flows on top-layer pours; the bottom layer is a ground plane. The gate
  drive nets run on the top layer, so no gate traces cut the ground plane.
- Current density from a 2D resistive-sheet solve of each pour (99.9th
  percentile, away from pad edges), at 30 A shared over the outputs or 25 A
  through a single output:

  | Path | A per mm of width |
  |---|---|
  | Ground return, bottom layer (outputs → XT60) | 1.1–1.4 |
  | VIN (XT60 → Q1/Q7) | 1.7 |
  | MID (between the MOSFET pairs) | 0.9 |
  | VOUT (Q2/Q8 → outputs) | 1.3–1.7 |
  | Brake drain (XT60 → Q3/Q9), 25 A | 1.0 |
  | Bulk capacitors → brake XT60, 25 A pulses | 1.7 |

- These are electrical sheet-current estimates, not temperature predictions.
  IPC-2221 current estimates depend on trace cross-section and temperature rise;
  there is no universal A/mm limit that proves these pours safe. The solver
  excludes pad regions and uses a 0.2 mm grid. It does not validate pad necks,
  via heating, connector contacts, airflow or a 30 A continuous rating. Keep the
  intended 2 oz stackup and validate the complete assembly thermally.
- Two MOSFETs share each power position (Q1‖Q7 ideal diode, Q2‖Q8 soft start,
  Q3‖Q9 brake). The electrical model predicts about 49–51 % sharing with equal
  4.2 mΩ channel resistance. Real part and temperature variation are excluded.
  Equal sharing is especially unproven during linear soft start. At 15 A per
  MOSFET, 4.2 mΩ gives 0.95 W at the specified cold gate drive; hot losses rise.
- Each brake MOSFET's source has six 0.4 mm vias into the ground plane.
  Connector and bulk-capacitor pads connect solidly, with no thermal spokes.

## How it works

- **U1 LM74800-Q1** drives two back-to-back pairs of N-MOSFETs (common drain).
  Q1‖Q7 are the ideal diode. TI specifies about 0.5 µs typical turn-off for a
  defined 10 nF gate load; that timing is not verified for this parallel pair. Q2‖Q8 are the soft-start switch: C4, C5, C13, C14
  (400 nF) on HGATE through R5 set the ramp. Each MOSFET has its own 10 Ω gate
  resistor (R30–R33). R1/R2 set UVLO; R3/R4 set the input over-voltage
  cut-off. SW1 pulls EN low to turn the output off.
- **Control rail.** CJ431 + MMBT5551 make ≈11.6 V from the output bus, so the
  clamp keeps working when the supply is unplugged and the arm is back-driven.
  CJ431 needs up to 1 mA to regulate, which R6 can only supply above about 26 V.
  Below that, R6, R7 and R8 set Q4's base instead: about 10.9–11.3 V on the rail at
  15 V by hand calculation with 1 % resistors and full rail load. The trim voltage
  scales with the rail, so that moves the threshold by a few percent. Measure it.
  D10 protects Q4's base and emitter when VOUT falls faster than the rail.
- **Brake comparator (U3A, LM393).** Compares VOUT (R10/R11/R12) with VIN plus
  an offset from RV1 through R16 (R14/R15/R16). The two dividers are balanced,
  so the threshold does not depend on the supply voltage. R13 adds 2 V of
  hysteresis. Q5/Q6 drive both brake MOSFETs through R18 and R28; D4/D7 clamp
  the resistor's inductive kick. The comparator's pull-up runs through J11, and
  R27 holds the brake off when the thermal switch opens.
- **Brake interlock (Q10, Q11).** DGATE can sit about 11 V above VIN at full gate drive.
  LM74800 also regulates its gate linearly to hold about 10.5 mV forward drop.
  DGATE is not a digital current-direction output. Q10
  (MMBT5401) turns that into base current for Q11, which holds CMP_OUT low.
  The behavioral latch test supports this intended logic, but real gate
  dynamics, faults and all power-state transitions have not been verified.
- **Thermal-loop indicator (Q12, D9).** With J11 closed both of its pins sit at
  the same voltage and Q12 (S8550) stays off. With J11 open, R17 pulls PU_TH up
  while R27 holds CMP_OUT low, Q12 turns on and lights D9 through R38. Its base
  resistor R37 is 1 MΩ, so it can lift CMP_OUT to only about 0.75 V with the lowest-gain
  Q12, far below the 3 V or more that Q5 and the brake MOSFETs need.
- **Supply indicator (D8).** Lit from VIN through R36 (33 kΩ, 0.4–1.4 mA over
  15–48 V), before SW1 and the soft start.
- **LED stretcher (U3B).** D5/R20 charge C12 on every brake pulse; R21 bleeds it
  over about 0.3 s, and U3B lights D6 (red) while C12 is above 2 V. D3 (green)
  shows that the output bus is live.

## Files

- `regen_precharge.kicad_sch`, `regen_precharge.kicad_pcb`, `regen_precharge.kicad_pro`: KiCad 10 project.
- `lib/`: JLCPCB symbols, footprints and 3D models (LM74800, CRSS042N10N, MSK12C02, 3362P) imported with easyeda2kicad.
- `sim_regen_clamp.cir`: ngspice deck for the brake comparator, the two-MOSFET brake, the interlock, the thermal-loop indicator and the LED stretcher, with a behavioural model of the ideal diode.
- `sim_brake_latch_48v.cir`: the worst-case latch test at 48 V (delete the interlock lines to reproduce the rev B latch).
- `tools/review_swarm.py`: runs every AI model on this computer against the design, then has other models check each finding. It keeps running on its own and waits out usage limits. Run `tools/review_swarm.py models`, then `start`. `tools/review_swarm_test.py` tests it offline with a fake model runner.

`jlcpcb/` holds the Gerbers, BOM, placement and hand-solder lists for this revision, and `docs/` the schematic PDF.
`tools/` holds the scripts that generate and check the board. It's generated, so edit the scripts rather than the board by hand.
They were copied from the original workspace as they are: their paths still point there, so edit those before running them.

## Verification status

These checks show the design agrees with itself, its rules and its datasheets. They do not
show it is right: several real faults on this board passed every one of them, and were
found only by independent reviewers. Treat Konnect's "READY" as a prompt for review.

Run on the final rev E files with `tools/check_all.sh --online`:

- `gate.py`: ERC and DRC at all severities with parity, zone refill and a rule canary. PASS,
  with reviewed waivers in `gate_waivers.json`. DRC: 0 errors, 0 unconnected, parity clean.
- `check_netlist.py`: 233 pins compared between generator table, schematic and board, 0 differences.
- `check_parts.py`: 105 terminals against a datasheet pin ledger written blind by a separate
  model, 0 failures, 15 left for a person. It fails on the rev D backup (U2, RV1) and on a
  deliberately swapped Q5, as it should. D11's entry was added by the designer, not blind.
- `check_bodies.py`: six MOSFET package envelopes against every other footprint, 0 collisions.
- `screw_check.py`: no copper within 5.47 mm of any corner hole centre, both layers.
- `check_bom.py`: 47 part numbers against JLC's catalogue (via jlcsearch), 0 value or package mismatches.
- Konnect: ERC 0, DRC 0 errors, `validate_for_manufacturing` READY, 0 DFM findings.

The JLC limits come from a research report; confirm them on the live quote and DFM. Konnect's CPL
differs from ours on SOT-23 rotation and TO-263 origin, and neither is proven until JLC's preview
confirms it: check every polarized part and pay for Confirm Parts Placement.

Simulated with ngspice:

- `sim_regen_clamp.cir`, 15 A regen for 40 ms into 36 V with 2 Ω: bus held
  between +2.0 and +4.0 V above the supply, brake current 15 A average and 20 A
  peak, no current back into the supply, LED went out at 0.368 s simulation time, about 0.318 s after regen ended. The
  interlock and thermal-loop indicator do not change any of these numbers.
- Same run with J11 open: the brake stays off (CMP_OUT at most 0.6 V, gate below
  1 V) and D9 carries 0.9 mA. With J11 closed D9 carries no current.
- `sim_brake_latch_48v.cir`, 48 V, RV1 at minimum, sense resistors at their
  worst-case 1 % limits: without the interlock the brake stays latched and the
  PSU feeds 24 A into the resistor; with it the brake lets go and supply current
  drops to 0.8 mA.

Calculated, not simulated:

- Soft start: inrush 0.355–0.833 A into 4000 µF including ±10 % ramp-capacitor
  tolerance, before capacitor DC bias and nonlinear MOSFET capacitance. At 48 V
  the nominal ramp lasts 0.349 s and the pair dissipates 4.61 J for that
  capacitance alone. This does not prove hot-case SOA, equal sharing or startup
  with motor electronics drawing power.
- Control rail at 15 V: R6 has only 0.275 mA available at a 12.25 V reference node and
  R7/R8 take 0.25 mA, so CJ431 is out of regulation and the divider sets Q4's base.
  Worst-case hand calculation gives a rail of about 10.9–11.3 V. This is not measured.
- Soft-start MOSFET SOA, against the datasheet's Fig 11 at Tc = 25 °C: the DC limit at
  48 V is about 4.8 A, or about 3 A derated to a 70 °C case. 0.83 A for 0.35 s is inside
  it even if one MOSFET takes it all. That covers capacitor charging only, not motor
  electronics drawing current during the ramp. The chart shows no linear-mode derating.
- Bus capacitor ripple during sustained braking: about sqrt(I_regen × (I_brake − I_regen)),
  so 8.5 A rms at 3 A regen and 24 A brake current, or about 2.1 A per capacitor at roughly
  2 kHz. That's over the 1.69 A rating at 100 kHz. Ripple limits are thermal, so this
  matters for sustained braking, not bursts of a few seconds.

Not done: no SPICE model of the LM74800 itself (the decks use a behavioural
ideal diode), soft start not simulated, avalanche data not reviewed, no thermal
simulation, no creepage review at 48 V, and no board has been built or tested. Have an experienced person review the power
stage before ordering.

## Open decisions

These block ordering. They're yours to decide, or they need a person with the part in hand:

1. **Minimum supply: 15 V or 24 V?** The IM6014 is listed for 24–75 V. Dropping 15 V would
   let R26 and R6 change to reduce Q4's heat and keep CJ431 in regulation.
2. **Which moteus controller, at what bus voltage?** Limits are r4 44 V, c1 51 V, n1/x1
   54 V absolute maximum. At 48 V plus the brake threshold, an r4 on output 2 is over its limit.
3. **Are the bus parts safe at the TVS clamp voltage?** The SMCJ51A can reach 82.4 V at rated
   current; the bulk capacitors are 63 V and the LM74800 is 70 V.
4. **Which exact brake resistor, and is its fuse fast enough?** How long the resistor stays
   overloaded before the Q136 opens hasn't been measured (see Brake resistor wiring).
5. **What current does the arm really draw through one XT30?** The drawing's rating is 15 A
   continuous. Estimate the arm's current, then choose a limit, fuse or connector.
6. **Which screw hardware?** The head or washer must be under 11 mm across.
7. **What stops regen when the brake is off?** J11 or the Q136 opening removes the brake, so the next
   regen climbs to D2, which lasts milliseconds at 1 kW and fails short. This needs a system answer,
   such as the motor controllers' own over-voltage limit, confirmed before relying on the board.
8. **Experienced review of the power stage.** Several real faults here passed every automated
   check. A person who has built boards like this should review it before ordering.

Left for a person, because no datasheet settles them:

- **LED polarity on the placed board.** Datasheets number pin 1 as anode, KiCad numbers pad 1 as
  cathode, and JLC's library orientation decides how the part lands. Check D3, D6, D8 and D9
  on JLC's preview and pay for Confirm Parts Placement. A reversed LED stays dark and is easy to re-solder.
- **XT connector polarity.** No datasheet says which contact is +. Check it with a meter (see Bring-up).
- **SW1 direction.** The datasheet doesn't say which slider position joins COM to pin 1.

## Bring-up

This sequence is a proposed test. Don't start it until the open decisions above are settled.

1. Inspect the board. Check Q1–Q12, D1–D10 and the LEDs against the silkscreen. Before
   connecting anything, unpowered, use a meter to find which contact of each XT connector
   reaches pad 2 and which reaches pad 1, then compare with your mating cables. The board
   expects pad 2 positive. A mismatch reverses the motor supply.
2. Leave J11 open for now. SW1 off, J1 only. A reversed supply forward-biases D1, so the
   supply goes into current limit at about 1 V and the board stays dark: stop and rewire if so.
   The LM74800's reverse protection doesn't help here, because D1 conducts first. Set a 0.5 A current limit and raise
   the supply in steps (5, 12, 15, 24, then 36 V), checking the current at each
   step. Only white (SUPPLY) lights. TP1 = supply, TP3 ≈ 0 V. Stop on anything
   you did not predict.
3. SW1 on. If nothing happens, try the slider's other position: with it off, TP8 reads 0 V.
   Green lights and TP3 rises at the intended soft-start rate. Yellow
   (THERM OPEN) also lights, because J11 is open. TP20 sits near 0.6 V.
4. SW1 off, fit a jumper on J11 (or the thermal switch), SW1 on. Green lights,
   yellow stays off, and TP12 stays at 0 V.
5. Set TP9 to about 6.2 V with RV1 (+4 V trip). Clockwise should raise TP9. If it lowers TP9,
   stop: RV1 isn't wired as intended.
6. Fit the brake resistor with its thermal fuse in series. This step stores real energy: about 20 A comes from
   the capacitors, and the supply's current limit does not reduce it. Wear eye
   protection. Raise the supply to 40 V, then quickly set it to 34 V.
   The ideal diode holds the output at 40 V, 6 V above the supply, so the red LED
   flashes while the output capacitors discharge. Use a scope to measure TP3
   at the falling edge of the actual brake gate on TP13 or TP21. The red LED is
   stretched and goes out later, so it cannot mark the release threshold.
   Confirm that VIN actually falls: a bench supply may not sink current.
   Compare the measured release against the resistor and rail tolerances.
7. Remove input power, support the arm, and measure VOUT before connecting loads.
   SW1 off does not discharge the bus. After a separate load and SOA review,
   connect the arm and gripper with the bus discharged, then enable the output
   under a validated supply current limit.

The board has no output current limit of its own. Keep the supply's limit and a
voltage-rated fuse in the supply lead. A dark LED does not prove the bus is discharged. Before touching the board, turn the supply
off and measure VOUT: with SW1 off the bulk capacitors can stay charged. Connect
the motors last, as a separate decision.
