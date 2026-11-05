#!/bin/bash
# Runs every board check and stops the verdict at the first failure. usage: check_all.sh [--online]
# gate, netlist and parts are fail-closed; Konnect's verdict is reported, never treated as approval.
HERE="$(cd "$(dirname "$0")" && pwd)"
R="$(cd "$HERE/.." && pwd)"
P="$(cd "$R/../../../hardware/regen-precharge-board" && pwd)"
T="$HERE/review_tools"; OUT="$R/build/checks"; mkdir -p "$OUT"; fail=0
quiet() { grep -v "assert\|swig\|Debug"; }
step() { echo; echo "=== $1"; }

step "ERC, DRC, parity, rule canary (gate.py)"
python3 -I "$HERE/gate.py" "$P" regen_precharge "$HERE/gate_waivers.json" 2>&1 | quiet | tail -8 || true
python3 -I "$HERE/gate.py" "$P" regen_precharge "$HERE/gate_waivers.json" >/dev/null 2>&1 || { echo "GATE FAILED"; fail=1; }

step "Generator table vs schematic vs board (check_netlist.py)"
python3 "$HERE/check_netlist.py" "$P/regen_precharge.kicad_sch" "$P/regen_precharge.kicad_pcb" "$HERE/build_sch.py" > "$OUT/netlist.txt" 2>&1 || fail=1
quiet < "$OUT/netlist.txt" | tail -4

step "Exact-part pins vs blind datasheet ledger (check_parts.py)"
python3 "$HERE/check_parts.py" "$P/regen_precharge.kicad_pcb" "$HERE/pin_intent.json" "$R/parts-ledger/ledger.json" > "$OUT/parts.txt" 2>&1 || fail=1
quiet < "$OUT/parts.txt" | grep -E "^FAIL|^PASS|^HUMAN"

step "Copper keep-out round the screw heads"
python3 -I "$T/screw_check.py" "$P/regen_precharge.kicad_pcb" 2>&1 | quiet | tee "$OUT/screws.txt" | grep "nearest copper"
python3 -I - "$OUT/screws.txt" <<'PY' || fail=1
import re,sys
d=[float(x) for x in re.findall(r"nearest copper ([\d.]+)",open(sys.argv[1]).read())]
assert len(d)==8 and min(d)>=5.4,("copper inside the 11 mm keep-out",d)
PY

step "Package bodies against neighbouring parts"
python3 -I "$T/check_bodies.py" "$P/regen_precharge.kicad_pcb" 2>&1 | quiet | grep -E "^FAIL|^PASS" | tee "$OUT/bodies.txt"
grep -q "^PASS" "$OUT/bodies.txt" || fail=1

step "Part numbers vs JLC catalogue"
if [ "${1:-}" = "--online" ]; then
  python3 -I "$T/check_bom.py" "$HERE/build_sch.py" "$OUT/bom.json" 2>&1 | tail -6 || fail=1
else
  echo "skipped: run with --online"
fi

step "Konnect ERC, DRC, design review, manufacturing audits, BOM health"
KICAD_API_SOCKET=ipc:///tmp/kicad/api.sock KLIM=600 python3 -I "$T/kc.py" "$T/c17.json" "$OUT/konnect" > "$OUT/konnect.log" 2>&1 || fail=1
python3 -I - "$OUT/konnect" <<'PY'
import json,glob,os,sys
for f in sorted(glob.glob(sys.argv[1]+"/0[1-6]*.json")):
    d=json.load(open(f)); n=os.path.basename(f)[3:-5]
    print(n, {k:d[k] for k in ("errors","warnings","unconnected_items","schematic_parity","verdict","summary") if k in d} or d.get("design_review",{}).get("verdict"))
PY

step "ngspice decks"
( cd "$OUT" && for c in sim_regen_clamp sim_brake_latch_48v; do ngspice -b "$P/$c.cir" 2>&1 | grep -E "^[a-z_0-9]+ += " | cut -c1-70; done )

echo
if [ $fail -eq 0 ]; then echo "ALL FAIL-CLOSED CHECKS PASSED. This does not mean ready to order: see the human list above and the README."; else echo "CHECKS FAILED"; fi
exit $fail
