import sys,re
f=sys.argv[1]; s=open(f).read()
s=s.replace("(pin unspecified ","(pin passive ")
tb='''(title_block
\t\t(title "Regen clamp + soft-start (precharge) board")
\t\t(date "2026-11-03")
\t\t(rev "E")
\t\t(company "IM6014 arm bench")
\t\t(comment 1 "Refs: ODrive Regen Clamp (brake chopper), mjbots mjpower-ss (precharge)")
\t\t(comment 2 "15-48 V, 30 A continuous / 60 A peak, 3 outputs, brake set by RV1")
\t)
'''
if "(title_block" not in s: s=re.sub(r'(\(paper "A[0-9]"\)\n)', lambda m: m.group(1)+"\t"+tb, s, count=1)
s=re.sub(r'\(symbol\s*\(lib_id "(Mechanical:MountingHole|Mechanical:Fiducial|Connector:TestPoint)"\).*?\(in_bom yes\)', lambda m: m.group(0).replace("(in_bom yes)","(in_bom no)",1), s, flags=re.S)
open(f,"w").write(s)
