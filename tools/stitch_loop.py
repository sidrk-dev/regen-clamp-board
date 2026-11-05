import json, subprocess, sys
B, SP = sys.argv[1], sys.argv[2]
for _ in range(4):
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "-o", f"{SP}/drc.json", B], capture_output=True)
    d = json.load(open(f"{SP}/drc.json"))
    bad = set()
    for v in d["violations"]:
        if v["type"] in ("clearance", "hole_clearance", "hole_to_hole", "copper_edge_clearance", "via_dangling", "shorting_items", "items_not_allowed"):
            for it in v["items"]:
                if it["description"].startswith("Via [GND]"):
                    bad.add((round(it["pos"]["x"], 2), round(it["pos"]["y"], 2)))
    if not bad: break
    json.dump(sorted(bad), open(f"{SP}/bad.json", "w"))
    subprocess.run(["python3", f"{SP}/finish_pcb.py", "clean", B, f"{SP}/bad.json"], check=True, capture_output=True)
