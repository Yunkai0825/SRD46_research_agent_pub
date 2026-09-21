"""Partition Claude displayed-branch time into non-overlapping activity components."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import csv, json, zipfile

HERE = Path(__file__).resolve().parents[1] / "audit"
ROOT = Path(__file__).resolve().parents[3]
def dt(s): return datetime.fromisoformat(s.replace("Z","+00:00")).timestamp() if s else None
def truth(v): return str(v).lower() in ("true","1","yes")
def read_csv(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def branch(d):
    ix={m["uuid"]:m for m in d["chat_messages"]};leaf=d["current_leaf_message_uuid"];ids=set()
    while leaf in ix and leaf not in ids:
        ids.add(leaf);leaf=ix[leaf].get("parent_message_uuid")
    return [m for m in d["chat_messages"] if m["uuid"] in ids]

def main():
    ref={(r["config"],r["prompt_id"]):r for r in read_csv(HERE/"all_run_timings.csv")}
    audited=read_csv(HERE/"solver_command_audit.csv")
    selected={(r["config"],r["prompt_id"],r["tool_use_id"]) for r in audited
              if truth(r["include_solver"]) and truth(r["current_branch"])}
    bg=json.loads((HERE/"fable_L1_10_background_bounds.json").read_text(encoding="utf-8"))
    rows=[];interval_rows=[];checks=[]
    for filename in ("Opus4_7.zip","Fable5_1.zip"):
        with zipfile.ZipFile(ROOT/"_Claude_web_answers"/filename) as z:
            for member in sorted(n for n in z.namelist() if n.endswith("/messages.json")):
                config,pid=member.split("/")[:2];r=ref[(config,pid)]
                shown=branch(json.loads(z.read(member)))
                lo=dt(next(m for m in shown if m["sender"]=="human")["created_at"])
                blocks=[c for m in shown for c in m.get("content",[])]
                results={c["tool_use_id"]:c for c in blocks if c.get("type")=="tool_result"}
                intervals=[];ends=[]
                def add(a,b,label,priority,source):
                    if a is not None and b is not None and b>a:
                        intervals.append((a,b,label,priority,source))
                for m in shown:
                    if m["sender"]!="assistant":continue
                    cc=m.get("content",[])
                    starts=[dt(c["start_timestamp"]) for c in cc if c.get("start_timestamp")]
                    stops=[dt(c["stop_timestamp"]) for c in cc if c.get("stop_timestamp")]
                    a=min(starts) if starts else dt(m["created_at"])
                    b=max(stops) if stops else dt(m["updated_at"])
                    ends.append(b);add(a,b,"web_other_overhead",0,m["uuid"])
                hi=max(ends)
                lo=min(lo,min(v[0] for v in intervals))
                for c in blocks:
                    typ=c.get("type");a=dt(c.get("start_timestamp"));b=dt(c.get("stop_timestamp"))
                    if typ in ("thinking","text","tool_use"):
                        label={"thinking":"web_thinking","text":"web_answer_writing",
                               "tool_use":"web_code_tool_input"}[typ]
                        add(a,b,label,3,c.get("id","block"))
                    if typ=="tool_use":
                        result=results.get(c.get("id"),{})
                        rs=dt(result.get("start_timestamp"));re=dt(result.get("stop_timestamp"))
                        add(b,re,"web_non_solver_tools",1,c["id"])
                        if (config,pid,c["id"]) in selected:
                            add(b,rs,"EXCLUDED_SOLVER",10,c["id"])
                        if (config,pid,c["id"])==(bg["config"],bg["prompt_id"],bg["tool_use_id"]):
                            # 44.1 s solver progress occurred within this 45.303 s tool wait.
                            # Its exact location inside that tool interval does not affect
                            # any included component: both endpoints fall in tool waiting.
                            lower=float(bg["confirmed_runtime_lower_bound_s"])
                            assert rs-b >= lower
                            add(b,b+lower,"EXCLUDED_SOLVER",10,c["id"]+":lower_bound")
                points=sorted({lo,hi,*[x for a,b,*_ in intervals for x in (max(lo,a),min(hi,b)) if lo<=x<=hi]})
                totals=defaultdict(float);overlap=0.
                for a,b in zip(points,points[1:]):
                    if b<=a:continue
                    mid=(a+b)/2
                    hit=[v for v in intervals if v[0]<=mid<v[1]]
                    chosen=max(hit,key=lambda x:x[3]) if hit else None
                    label=chosen[2] if chosen else "EXCLUDED_BETWEEN_TURNS"
                    totals[label]+=b-a
                    if len({v[2] for v in hit if v[3]==3})>1:overlap+=b-a
                    interval_rows.append(dict(config=config,prompt_id=pid,start_epoch_s=a,end_epoch_s=b,
                        duration_s=b-a,component=label,source=chosen[4] if chosen else "gap between response segments"))
                included=sum(v for k,v in totals.items() if not k.startswith("EXCLUDED"))
                expected=float(r["non_solver_active_s"])
                assert abs(included-expected)<0.005,(config,pid,included,expected)
                assert abs(totals["EXCLUDED_SOLVER"]-float(r["solver_current_s"]))<0.005,(config,pid,"solver mismatch")
                for key in ("web_thinking","web_answer_writing","web_code_tool_input","web_non_solver_tools","web_other_overhead"):
                    rows.append(dict(prompt_id=pid,config=config,component=key,seconds=totals[key],minutes=totals[key]/60,
                        method="Exclusive current-branch timestamp intervals; excludes between-turn gaps and recorded solver execution.",
                        quality="upper_bound" if truth(r["upper_bound"]) else "timestamp_partition",
                        source_archive=filename,source_member=member))
                checks.append(dict(config=config,prompt_id=pid,stack_s=included,expected_s=expected,
                    excluded_between_turns_s=totals["EXCLUDED_BETWEEN_TURNS"],excluded_solver_s=totals["EXCLUDED_SOLVER"],
                    overlapping_explicit_blocks_s=overlap))
    write_csv(HERE/"web_stage_breakdown.csv",rows)
    write_csv(HERE/"web_time_intervals.csv",interval_rows)
    (HERE/"web_stage_validation.json").write_text(json.dumps(checks,indent=2),encoding="utf-8")
    print(json.dumps({"runs":len(checks),"max_stack_error_s":max(abs(r["stack_s"]-r["expected_s"]) for r in checks),
        "explicit_overlap_s":sum(r["overlapping_explicit_blocks_s"] for r in checks)},indent=2))

if __name__=="__main__":main()

