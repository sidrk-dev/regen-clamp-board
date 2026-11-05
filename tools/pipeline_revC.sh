#!/bin/bash
# Rebuild rev C from the generator scripts: schematic (Konnect) -> netlist -> placement -> Freerouting (Konnect) -> stitching.
set -eo pipefail
H=/home/sid/Documents/code/im6014Development/.claude/worktrees/regen-clamp-review-f9d0d4
P=$H/hardware/regen-precharge-board
D=$H/results/hardware/regen-precharge-board/build-scripts
SP=$H/results/hardware/regen-precharge-board/build
B=$P/regen_precharge.kicad_pcb
mkdir -p $SP && rm -rf $SP/route && mkdir -p $SP/route
cp $D/empty_sch.bak $P/regen_precharge.kicad_sch
python3 -I $D/build_sch.py
python3 -I $D/post_sch.py $P/regen_precharge.kicad_sch
kicad-cli sch export netlist -o $SP/net.net $P/regen_precharge.kicad_sch >/dev/null
cp $D/empty_pcb.bak $B
python3 -I $D/fab_setup.py $B $P/regen_precharge.kicad_pro 0.18
python3 $D/build_pcb.py $SP/net.net
python3 $D/finish_pcb.py prep $B $SP/route/board.dsn
echo "[[\"load_toolset\",{\"name\":\"integration\"}],[\"route_specctra_dsn\",{\"dsn_path\":\"$SP/route/board.dsn\",\"ses_output_path\":\"$SP/route/board.ses\",\"jar_path\":\"/home/sid/.local/opt/freerouting/freerouting-2.5.0.jar\",\"max_passes\":60,\"optimizer_enabled\":true,\"overall_timeout_seconds\":900}]]" > $SP/route/c.json
JAVA_TOOL_OPTIONS="-Xlog:disable -Xlog:all=off" KLIM=3000 python3 -I $D/kmcp.py $SP/route/c.json | grep -o '"final_state":"[A-Z]*"\|"success":[a-z]*\|ERROR' || true
python3 $D/finish_pcb.py import $B $SP/route/board.ses
python3 -I $D/fab_setup.py $B $P/regen_precharge.kicad_pro 0.16
python3 $D/finish_pcb.py stitch $B
cp $D/finish_pcb.py $SP/finish_pcb.py
python3 $D/stitch_loop.py $B $SP
python3 $D/island_stitch.py $B
python3 $D/stitch_loop.py $B $SP
kicad-cli pcb drc --format json --severity-all -o $SP/drc.json $B >/dev/null 2>&1 || true
python3 $D/polish.py $B $SP/drc.json
python3 $D/prune_dangling.py $B $SP
python3 $D/silk_place.py $B
kicad-cli pcb drc --format json --severity-all --schematic-parity -o $SP/drc.json $B >/dev/null 2>&1 || true
python3 -I - $SP/drc.json <<'PY'
import json,sys,collections
d=json.load(open(sys.argv[1]))
v=d["violations"]; u=d["unconnected_items"]
print("violations",len(v),"unconnected",len(u),"parity",len(d["schematic_parity"]))
print(collections.Counter((x["severity"],x["type"]) for x in v))
for x in v:
    if x["severity"]=="error": print("ERR",x["type"],[i["description"][:60] for i in x["items"]][:2], x["items"][0]["pos"])
for x in u[:30]: print("UNCONN",[i["description"][:70] for i in x["items"]])
for x in d["schematic_parity"][:20]: print("PARITY",x.get("description"),[i["description"][:60] for i in x.get("items",[])])
PY
