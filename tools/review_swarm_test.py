#!/usr/bin/env python3
"""Offline test of review_swarm.py with a fake model runner: no model is called and nothing leaves the computer.
It covers a usage limit that must pause and resume, a lane that dies once, a dead model whose lens must be reassigned, a report with no
JSON block, findings merging across models, a false claim being rejected, stop and resume, and API keys being scrubbed."""
import json, os, stat, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review_swarm as rs

FAKE = r'''#!/usr/bin/env python3
import json, os, sys, time
a = dict(zip(sys.argv[1::2], sys.argv[2::2]))
model, out, rec, prompt = a["--model"], a["--output"], a["--receipt"], open(a["--prompt"]).read()
state = os.path.join(os.environ["FAKE_STATE"], model + ".count")
n = int(open(state).read()) + 1 if os.path.exists(state) else 1
open(state, "w").write(str(n))
open(os.path.join(os.environ["FAKE_STATE"], "env.log"), "a").write(json.dumps({"key": os.environ.get("ANTHROPIC_API_KEY"), "cc": os.environ.get("CLAUDECODE")}) + "\n")
time.sleep(float(os.environ.get("FAKE_DELAY", "0")))
def receipt(status, error=None, cost=0):
    json.dump({"status": status, "error": error, "costUsd": cost}, open(rec, "w"))
if model == "dead":
    receipt("unauthenticated", {"message": "not signed in"}); sys.exit(1)
if model == "loggedout":
    receipt("child-failed", {"message": "child exited with status 1", "evidence": "Not logged in · Please run /login"}); sys.exit(1)
if model == "limited" and n == 1:
    receipt("usage-exhausted", {"message": "You've hit your usage limit"}); sys.exit(1)
if model == "crashy" and n == 1:
    receipt("malformed-output", {"message": "no final text"}); sys.exit(1)
if "try to prove these findings wrong" in prompt:
    ids = sorted(set(__import__("re").findall(r"### (F\d+):", prompt)))
    v = [{"id": i, "verdict": "REJECTED" if "pulls low" in prompt.split("### " + i)[1][:200] else "CONFIRMED", "reason": "checked", "evidence": "datasheet"} for i in ids]
    open(out, "w").write("Checked.\n```json\n" + json.dumps({"verdicts": v}) + "\n```\n"); receipt("complete"); sys.exit(0)
if model == "prose":
    open(out, "w").write("# Review\n### 1. HIGH: R6 runs hot at 55 V\nR6 dissipates a lot.\n"); receipt("complete"); sys.exit(0)
f = [{"severity": "high", "title": "D10 clamp missing across Q4 base and emitter", "parts": ["Q4", "D10"], "evidence": "BVebo 6 V", "confidence": "verified", "fix": "add a diode"}]
if model == "wrong":
    f = [{"severity": "critical", "title": "LM393 output pulls low when IN+ is above IN-", "parts": ["U3"], "evidence": "misread", "confidence": "verified", "fix": ""}]
open(out, "w").write("Report.\n```json\n" + json.dumps({"findings": f, "checked_ok": [], "could_not_check": []}) + "\n```\n"); receipt("complete")
'''


def run(args, env):
    return subprocess.run([sys.executable, str(HERE / "review_swarm.py")] + args, capture_output=True, text=True, env=env, timeout=120)


def wait_done(swarm, env, secs=90):
    end = time.time() + secs
    while time.time() < end:
        runs = sorted(swarm.glob("run-*"))
        if runs and (runs[-1] / "DONE").exists():
            return runs[-1]
        time.sleep(0.5)
    raise SystemExit("swarm did not finish:\n" + run(["status"], env).stdout + (sorted(swarm.glob("run-*"))[-1] / "daemon.log").read_text()[-2000:])


def env_for(tmp):
    fake = tmp / "fake-runner"
    fake.write_text(FAKE)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    state = tmp / "state"
    state.mkdir()
    swarm = tmp / "swarm"
    env = dict(os.environ, SWARM_SKIP_CHECKS="1", SWARM_RUNNER=str(fake), SWARM_DIR=str(swarm), FAKE_STATE=str(state), ANTHROPIC_API_KEY="sk-must-not-reach-lanes", CLAUDECODE="1")
    return env, swarm, state


def roster(tmp, models):
    p = tmp / "roster.json"
    p.write_text(json.dumps([dict(provider=prov, model=m, effort="default", basis="test") for prov, m in models]))
    return str(p)


def test_full_run():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        env, swarm, state = env_for(tmp)
        r = roster(tmp, [("fake", "good"), ("fake", "limited"), ("fake", "crashy"), ("fake", "dead"), ("fake", "loggedout"), ("fake", "wrong"), ("fake", "prose"), ("opencode", "free-a")])
        out = run(["start", "--roster", r, "--budget", "normal", "--backoff-scale", "0.002", "--poll", "0.2", "--passes", "2"], env)
        assert out.returncode == 0, out.stderr
        rundir = wait_done(swarm, env)
        st = json.loads((rundir / "state.json").read_text())
        statuses = {j["id"]: j["status"] for j in st["jobs"]}
        assert not [s for s in statuses.values() if s in ("queued", "running")], statuses
        assert "fake:dead" in st["dead"] and "fake:loggedout" in st["dead"]
        assert all(j["attempts"] <= 1 for j in st["jobs"] if j["model"] == "loggedout"), "a signed-out model must not be retried"
        assert any(j["model"] == "limited" and j["status"] == "done" for j in st["jobs"]), "limit lane must finish after the pause"
        assert any(j["model"] == "crashy" and j["status"] == "done" for j in st["jobs"]), "crashed lane must retry"
        lens_ok = [l for l in rs.LENSES if sum(j["kind"] == "review" and j["lens"] == l and j["status"] in ("done", "unstructured") for j in st["jobs"]) >= 1]
        assert len(lens_ok) == len(rs.LENSES), "every lens must stay covered despite the dead model"
        clusters = st["clusters"]
        by_title = {c["title"]: c for c in clusters}
        same = by_title["D10 clamp missing across Q4 base and emitter"]
        assert len({r["by"] for r in same["reports"]}) >= 3, "the same finding from several models must merge into one"
        assert rs.standing(same) == "confirmed", rs.standing(same)
        wrong = [c for c in clusters if "pulls low" in c["title"]][0]
        assert rs.standing(wrong) == "rejected", rs.standing(wrong)
        assert any("R6 runs hot" in c["title"] for c in clusters), "a report with no JSON must still yield its findings"
        assert any(j["lens"] == "gaps" for j in st["jobs"]), "second pass must hunt for gaps"
        report = (rundir / "REPORT.md").read_text()
        assert "Rejected by the checkers" in report and "pulls low" in report and "AI agreement is a lead" in report
        for line in (state / "env.log").read_text().splitlines():
            d = json.loads(line)
            assert d["key"] is None and d["cc"] is None, "API keys and CLAUDECODE must not reach a lane"
        pack = rundir / "pack"
        assert pack.is_dir() and not os.access(pack, os.W_OK), "the pack must be read-only"


def test_stop_and_resume():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        env, swarm, state = env_for(tmp)
        env["FAKE_DELAY"] = "2"
        r = roster(tmp, [("fake", "good"), ("fake", "good2")])
        assert run(["start", "--roster", r, "--budget", "light", "--poll", "0.2", "--passes", "1"], env).returncode == 0
        time.sleep(3)
        assert run(["stop"], env).returncode == 0
        end = time.time() + 40
        while time.time() < end and rs_pid(swarm):
            time.sleep(0.3)
        assert not rs_pid(swarm), "stop must end the swarm"
        rundir = sorted(swarm.glob("run-*"))[-1]
        assert not (rundir / "DONE").exists()
        env["FAKE_DELAY"] = "0"
        assert run(["resume"], env).returncode == 0
        rundir = wait_done(swarm, env)
        st = json.loads((rundir / "state.json").read_text())
        assert all(j["status"] == "done" for j in st["jobs"] if j["kind"] == "review"), [j["status"] for j in st["jobs"]]


def rs_pid(swarm):
    try:
        pid = int((swarm / "swarm.pid").read_text())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None


FAKE_VIBE = r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
if "--version" in a: sys.exit(0)
model = a[a.index("--model") + 1]
if model == "__list__":
    print("Error: Unknown model: __list__. Available: m1, m2"); sys.exit(1)
assert "--auto-approve" not in a, "auto-approve would let Vibe read outside the pack"
assert a.count("--enabled-tools") == 2 and "write_file" not in a and "bash" not in a
open(os.environ["FAKE_STATE"] + "/vibe-args.log", "a").write(" ".join(a) + "\\n")
out = a[a.index("--output-dir") + 1]; os.makedirs(out, exist_ok=True)
json.dump({"outcome": "finished", "cost_usd": 0.6, "error": None}, open(os.path.join(out, "export.json"), "w"))
print("Report\\n```json\\n" + json.dumps({"findings": [{"severity": "low", "title": "vibe saw R6 " + model, "parts": ["R6"], "evidence": "e", "confidence": "verified", "fix": ""}], "verdicts": []}) + "\\n```")
'''


def test_vibe_lanes_and_budget():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        env, swarm, state = env_for(tmp)
        fake = tmp / "fake-vibe"
        fake.write_text(FAKE_VIBE)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        env["SWARM_VIBE"] = str(fake)
        r = roster(tmp, [("vibe", "m1"), ("vibe", "m2"), ("fake", "good")])
        out = run(["start", "--roster", r, "--budget", "normal", "--poll", "0.2", "--passes", "1", "--vibe-budget", "1"], env)
        assert out.returncode == 0, out.stderr
        rundir = wait_done(swarm, env)
        st = json.loads((rundir / "state.json").read_text())
        assert st["vibe_spent"] >= 1 and "vibe:m1" in st["dead"], "the Vibe budget must stop its lanes"
        assert sum(j["provider"] == "vibe" and j["status"] == "done" for j in st["jobs"]) == 2, "no lane may start after the budget is used"
        assert (swarm / "LATEST_REPORT.md").exists(), "a finished run must leave the report at a stable path"


def test_vibe_has_no_cap_by_default():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        env, swarm, state = env_for(tmp)
        fake = tmp / "fake-vibe"
        fake.write_text(FAKE_VIBE)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        env["SWARM_VIBE"] = str(fake)
        r = roster(tmp, [("vibe", "m1"), ("vibe", "m2"), ("fake", "good")])
        assert run(["start", "--roster", r, "--budget", "normal", "--poll", "0.2", "--passes", "1"], env).returncode == 0
        rundir = wait_done(swarm, env)
        st = json.loads((rundir / "state.json").read_text())
        assert not [k for k in st["dead"] if k.startswith("vibe")], st["dead"]
        assert "--max-price" not in (state / "vibe-args.log").read_text()


def test_limit_time_parsing():
    assert 3000 < rs.reset_time("Try again in 1 hour") < 3700
    assert 80 < rs.reset_time("retry after 90 seconds") < 100
    assert 0 < rs.reset_time("You've hit your usage limit. Try again at 1:20 AM") <= 86400
    assert 0 < rs.reset_time("purchase more credits or try again at Nov 5th, 2026 1:20 AM.") <= 86400
    assert rs.reset_time("something else broke") is None


def test_extract_and_merge():
    assert rs.extract_json('x\n```json\n{"findings": [1]}\n```\n', "findings") == {"findings": [1]}
    assert rs.extract_json('text {"findings": [2]} more', "findings") == {"findings": [2]}
    assert rs.extract_json("nothing here", "findings") is None
    assert rs.headings_as_findings("### 1. CRITICAL — thing wrong\nbody\n### What I checked\nok\n")[0]["severity"] == "critical"
    c = []
    rs.merge_finding(c, dict(severity="low", title="Q4 runs hot at 55 V", parts=["Q4"]), "a:b")
    rs.merge_finding(c, dict(severity="high", title="Q4 runs too hot at 55 V input", parts=["Q4"]), "c:d")
    rs.merge_finding(c, dict(severity="low", title="J1 slot too small", parts=["J1"]), "c:d")
    assert len(c) == 2 and c[0]["severity"] == "high" and len(c[0]["reports"]) == 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name, flush=True)
