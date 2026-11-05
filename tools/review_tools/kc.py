"""Konnect stdio client. kc.py calls.json [outdir]; calls: [tool,args]; tool "@schema" args=list of names prints schemas.
Each result also saved to outdir/NN_tool.json"""
import json,subprocess,sys,os
calls=json.load(open(sys.argv[1])); od=sys.argv[2] if len(sys.argv)>2 else None
if od: os.makedirs(od,exist_ok=True)
p=subprocess.Popen([os.path.expanduser("~/.local/opt/konnect-dl/konnect")],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=open(sys.argv[1]+".err","w"),text=True,bufsize=1)
n=[0]
def rpc(method,params=None,notify=False):
    msg={"jsonrpc":"2.0","method":method}
    if params is not None: msg["params"]=params
    if not notify: n[0]+=1; msg["id"]=n[0]
    p.stdin.write(json.dumps(msg)+"\n"); p.stdin.flush()
    if notify: return None
    while True:
        line=p.stdout.readline()
        if not line: raise SystemExit("server closed")
        d=json.loads(line)
        if d.get("id")==n[0]: return d
rpc("initialize",{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"claude-script","version":"0"}})
rpc("notifications/initialized",notify=True)
lim=int(os.environ.get("KLIM","3000"))
for i,(tool,args) in enumerate(calls):
    if tool=="@schema":
        tl=rpc("tools/list",{})["result"]["tools"]
        for t in tl:
            if t["name"] in args: print("## SCHEMA",t["name"],json.dumps(t["inputSchema"].get("properties")),"req",t["inputSchema"].get("required"))
        continue
    r=rpc("tools/call",{"name":tool,"arguments":args})
    res=r.get("result") or r.get("error")
    out=[]
    if isinstance(res,dict) and "content" in res:
        for c in res["content"]: out.append(c.get("text",str(c)))
        if res.get("isError"): out.insert(0,"ERROR")
    else: out.append(json.dumps(res))
    txt="\n".join(out)
    if od: open(f"{od}/{i:02d}_{tool}.json","w").write(txt)
    if tool!="load_toolset": print(f"### {tool}\n"+txt[:lim])
p.stdin.close(); p.wait(timeout=30)
