#!/bin/bash
# Runs every board check in this repository. usage: tools/check_all.sh [--online]
# Fail-closed: any failing check makes the exit status 1. Items listed as HUMAN are not failures; they need a person.
# Needs KiCad 10 (kicad-cli and its pcbnew Python module) and ngspice. The copper check also needs numpy and scipy;
# --online adds the JLC catalogue and placement checks, which fetch data from jlcsearch and EasyEDA.
P="$(cd "$(dirname "$0")/.." && pwd)"
HERE="$P/tools"; T="$HERE/review_tools"; OUT="$P/build/checks"; mkdir -p "$OUT"; fail=0
quiet() { grep -v "assert\|swig\|Debug"; }
step() { echo; echo "=== $1"; }

step "ERC, DRC at all severities, schematic parity, rule canary (gate.py)"
python3 -I "$HERE/gate.py" "$P" regen_precharge "$HERE/gate_waivers.json" 2>&1 | quiet | tail -8 | tee "$OUT/gate.txt"
grep -q "^PASS" "$OUT/gate.txt" || { echo "GATE FAILED"; fail=1; }

step "Part table vs schematic vs board (check_netlist.py)"
python3 "$HERE/check_netlist.py" "$P/regen_precharge.kicad_sch" "$P/regen_precharge.kicad_pcb" "$HERE/build_sch.py" > "$OUT/netlist.txt" 2>&1 || fail=1
quiet < "$OUT/netlist.txt" | tail -4

step "Part pins, connector polarity and switch labels vs the datasheet ledger (check_parts.py)"
python3 "$HERE/check_parts.py" "$P/regen_precharge.kicad_pcb" "$HERE/pin_intent.json" "$HERE/parts-ledger.json" > "$OUT/parts.txt" 2>&1 || fail=1
quiet < "$OUT/parts.txt" | grep -E "^FAIL|^PASS|^HUMAN"

step "Copper keep-out round the screw heads"
python3 -I "$T/screw_check.py" "$P/regen_precharge.kicad_pcb" 2>&1 | quiet | tee "$OUT/screws.txt" | grep "nearest copper"
python3 -I - "$OUT/screws.txt" <<'PY' || fail=1
import re,sys
d=[float(x) for x in re.findall(r"nearest copper ([\d.]+)",open(sys.argv[1]).read())]
assert len(d)==8 and min(d)>=5.5,("copper inside the 11 mm keep-out",d)
PY

step "Bus-voltage pads to ground copper, and silkscreen to the board edge"
python3 -I "$T/bus_clearance_check.py" "$P/regen_precharge.kicad_pcb" 2>&1 | quiet | grep -E "^FAIL|^PASS" | tee "$OUT/bus_clearance.txt"
grep -q "^PASS" "$OUT/bus_clearance.txt" || fail=1
python3 -I "$T/silk_edge_check.py" "$P/regen_precharge.kicad_pcb" 2>&1 | quiet | grep -E "^FAIL|^PASS" | tee "$OUT/silk_edge.txt"
grep -q "^PASS" "$OUT/silk_edge.txt" || fail=1

step "Package bodies against neighbouring parts"
python3 -I "$T/check_bodies.py" "$P/regen_precharge.kicad_pcb" 2>&1 | quiet | grep -E "^FAIL|^PASS" | tee "$OUT/bodies.txt"
grep -q "^PASS" "$OUT/bodies.txt" || fail=1

step "Copper resistance and heating at 27 A, 1 oz (copper_check.py)"
if python3 -c "import numpy, scipy, pcbnew" 2>/dev/null; then
  mkdir -p "$P/build/copper"
  python3 "$T/copper_check.py" "$P/regen_precharge.kicad_pcb" "$P/build/copper" 35 27 2>&1 | quiet | tee "$OUT/copper.txt" | tail -2
  grep -q "^board temperature rise" "$OUT/copper.txt" || fail=1
else
  echo "skipped: needs numpy and scipy next to KiCad's Python (python3 -m venv --system-site-packages build/venv)"
fi

step "Part numbers vs JLC catalogue, and placement file vs JLC's own footprints"
if [ "${1:-}" = "--online" ]; then
  python3 -I "$T/check_bom.py" "$HERE/build_sch.py" "$OUT/bom.json" 2>&1 | tail -8 | tee "$OUT/bom.txt"
  grep -q "^PASS" "$OUT/bom.txt" || fail=1
  mkdir -p "$P/build/easyeda-cache"
  python3 -I -u "$T/check_cpl.py" "$P/regen_precharge.kicad_pcb" "$P/jlcpcb/CPL-JLCPCB.csv" "$P/jlcpcb/BOM-JLCPCB.csv" "$P/build/easyeda-cache" > "$OUT/cpl.txt" 2>&1 || fail=1
  grep -E "^FAIL|^PASS|^HUMAN" "$OUT/cpl.txt"
else
  echo "skipped: run with --online"
fi

step "ngspice decks (ideal circuit, latch test, post-layout with parasitics, hot plug and soft start)"
( cd "$OUT" && for c in sim_regen_clamp sim_brake_latch_48v sim_post_layout sim_soft_start; do echo "-- $c"; ngspice -b "$P/$c.cir" > "$OUT/$c.log" 2>&1; grep -E "^corner|^[a-z_0-9]+ += " "$OUT/$c.log" | cut -c1-70; done )
grep -q "aborted\|too small" "$OUT"/sim_*.log && { echo "SIMULATION ABORTED"; fail=1; }

echo
if [ $fail -eq 0 ]; then echo "ALL FAIL-CLOSED CHECKS PASSED. A person still has to do the items in the README's ordering list."; else echo "CHECKS FAILED"; fi
exit $fail
