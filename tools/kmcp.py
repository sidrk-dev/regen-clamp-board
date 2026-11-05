"""Tiny MCP stdio client for Konnect. usage: kmcp.py calls.json  (list of [tool, args])"""
import json,subprocess,sys,os
calls=json.load(open(sys.argv[1]))
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
for tool,args in calls:
    r=rpc("tools/call",{"name":tool,"arguments":args})
    res=r.get("result") or r.get("error")
    out=[]
    if isinstance(res,dict) and "content" in res:
        for c in res["content"]:
            out.append(c.get("text",str(c)))
        if res.get("isError"): out.insert(0,"ERROR")
    else: out.append(json.dumps(res))
    lim=int(os.environ.get("KLIM","4000"))
    print(f"### {tool}\n"+"\n".join(out)[:lim])
p.stdin.close(); p.wait(timeout=10)
