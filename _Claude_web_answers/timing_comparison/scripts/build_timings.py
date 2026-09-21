"""Read original ZIPs and build reproducible, solver-excluded comparison CSVs."""
from pathlib import Path
from datetime import datetime
import csv, json, re, sqlite3, zipfile, hashlib

HERE = Path(__file__).resolve().parents[1] / "audit"
ROOT = Path(__file__).resolve().parents[3]
LABELS = {
    "framework": "Our framework",
    "Opus4_7_high": "Opus 4.7 high",
    "Opus4_7_max": "Opus 4.7 max",
    "Fable5_1_medium": "Fable 5.1 medium",
    "Fable5_1_max": "Fable 5.1 max",
}
# Audited ordinal among ALL tool calls on the displayed conversation branch.
OPUS_CURRENT = {
 "Opus4_7_high": {
  "L1_1":[3],"L1_2":[3,5,7],"L1_3":[3,5,9],"L1_6":[3,6,10,13,19],
  "L1_7":[3,5],"L1_8":[5],"L1_9":[2,6],"L1_11":[4,15,17],
  "L2_1":[3],"L2_2":[3,5],"L2_3":[5,7],"L2_4":[1,2],"L2_6":[2],
  "L3_2":[1],"L3_5":[1],"L4_3":[1],"L4_5":[1]},
 "Opus4_7_max": {
  "L1_1":[4],"L1_2":[4,6,10,15,22,23,27],"L1_3":[2,3,4,6,7],
  "L1_4":[1,2],"L1_5":[1],"L1_6":[5,9],"L1_7":[3,5,8,13],
  "L1_8":[6,8,10,12,15,17,19,21,23,26],"L1_9":[4],
  "L1_10":[4,6,8,14],"L1_11":[4,7,13,17,23,25]}
}
# Ordinal among all exported tool calls, for alternative branches only.
OPUS_ALTERNATE = {
 ("Opus4_7_high","L1_8"):[16],
 ("Opus4_7_max","L1_1"):[8,11],
 ("Opus4_7_max","L1_10"):[19],
 ("Opus4_7_max","L1_8"):[30,33,38,41,45],
 ("Opus4_7_max","L1_11"):[33,39,41,44,52,56]
}
FABLE_EXPECTED = {
 ("Fable5_1_medium","L1_1"):84.185635,("Fable5_1_medium","L1_3"):13.941206,
 ("Fable5_1_medium","L1_4"):0.,("Fable5_1_medium","L1_9"):5.670678,
 ("Fable5_1_medium","L1_10"):86.862383,("Fable5_1_medium","L1_11"):49.859266,
 ("Fable5_1_max","L1_1"):5.571247,("Fable5_1_max","L1_3"):32.893965,
 ("Fable5_1_max","L1_4"):99.404622,("Fable5_1_max","L1_9"):12.101270,
 ("Fable5_1_max","L1_10"):22.683389,("Fable5_1_max","L1_11"):14.126126,
}

def dt(s):
    return datetime.fromisoformat(s.replace("Z","+00:00")) if s else None

def sortkey(pid):
    return tuple(map(int,re.findall(r"\d+",pid)))

def write_csv(name, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (HERE/name).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

def truth(x):
    return str(x).lower() in ("true","1","yes")

def framework_rows():
    rows=[]
    for archive in sorted((ROOT/"_benchmark").glob("*.zip")):
        with zipfile.ZipFile(archive) as z:
            names=set(z.namelist())
            for n in sorted(names):
                if not (n.count("/")==1 and n.endswith("/manifest.json")): continue
                folder=n.split("/")[0]; pid="_".join(folder.split("_")[:2])
                m=json.loads(z.read(n)); log=z.read(folder+"/_run.log").decode("utf-8",errors="replace")
                hist=[json.loads(x) for x in z.read(folder+"/run_history.jsonl").decode("utf-8").splitlines() if x.strip()]
                solver=[float(x) for x in re.findall(r"\[(?:pH_sweep|freeform_sweep|titration_sweep)\] Coarse solve: [^\r\n]*?\(([0-9.]+)s\)",log)]
                solverlogs=[]
                for sp in sorted(names):
                    if sp.startswith(folder+"/L1_call_") and sp.endswith("/solver/sweep_log.txt"):
                        solverlogs.append(sp)
                        text=z.read(sp).decode("utf-8",errors="replace")
                        solver.extend(float(x) for x in re.findall(r"Solver pipeline done \([^\r\n]*?, ([0-9.]+)s,",text))
                expected=0
                for sp in names:
                    if sp.startswith(folder+"/L1_call_") and sp.endswith("/pipeline_status.json"):
                        expected+=json.loads(z.read(sp)).get("status")=="ok"
                assert expected==len(solver),(pid,expected,solver)
                wall=float(m["elapsed_s"]); deduction=sum(solver); interruption=0.
                non_solver=wall-deduction; estimated=False; notes=""
                if pid=="L1_1":
                    # Read checkpoint event times entirely in memory, no extraction.
                    cp=folder+"/L1_call_01/_checkpoints/solver_result.sqlite3"
                    db=sqlite3.connect(":memory:");db.deserialize(z.read(cp))
                    starts=[r[0] for r in db.execute("SELECT committed_at FROM checkpoint_events WHERE event='solver_started' ORDER BY seq")]
                    db.close()
                    l0s=[e["ts"] for e in hist if e["event"]=="L0_start"]
                    l1s=[e["ts"] for e in hist if e["event"]=="L1_start"]
                    end=[e["ts"] for e in hist if e["event"]=="L0_end"][-1]
                    assert len(starts)==len(l1s)==3
                    non_solver=(starts[0]-l0s[0])+sum(starts[i]-l1s[i] for i in (1,2))+(end-starts[-1]-deduction)
                    wall=end-l0s[0];interruption=wall-deduction-non_solver;estimated=True
                    notes="Resumed run: reconstruct preparation + restart preludes + final remainder; excludes interrupted solver windows and unmeasured downtime."
                assert non_solver>=0
                rows.append(dict(prompt_id=pid,level=pid.split("_")[0],config="framework",series=LABELS["framework"],
                    total_wall_s=wall,active_response_s="",continuation_wait_s=0,solver_current_s=deduction,
                    solver_all_history_command_s=deduction,excluded_interrupted_solver_or_downtime_s=interruption,
                    non_solver_wall_s=non_solver,non_solver_wall_min=non_solver/60,
                    non_solver_active_s=non_solver,non_solver_active_min=non_solver/60,
                    timing_kind="reconstructed" if estimated else "recorded",
                    upper_bound=False,estimated=estimated,recorded_status=m.get("completion_status",""),
                    plot_in_answer="",plot_anywhere="",solver_anywhere=bool(solver),web_flags="",
                    source_archive=str(archive.relative_to(ROOT)),source_member=n,
                    source_sha256=hashlib.sha256(z.read(n)).hexdigest(),timing_notes=notes))
    assert len(rows)==32
    return sorted(rows,key=lambda r:sortkey(r["prompt_id"]))

def get_branch(d):
    lookup={m["uuid"]:m for m in d["chat_messages"]}; leaf=d["current_leaf_message_uuid"]; ids=set()
    while leaf in lookup and leaf not in ids:
        ids.add(leaf);leaf=lookup[leaf].get("parent_message_uuid")
    assert ids
    return [m for m in d["chat_messages"] if m["uuid"] in ids], ids

def web_rows():
    with (HERE/"claude_plot_presence.csv").open(encoding="utf-8-sig",newline="") as f:
        plots={(r["config"],r["prompt_id"]):r for r in csv.DictReader(f)}
    with (HERE/"fable_solver_calls.csv").open(encoding="utf-8-sig",newline="") as f:
        fable_rows=list(csv.DictReader(f))
    fable_ids={(r["config"],r["prompt_id"],r["tool_use_id"]) for r in fable_rows if truth(r.get("include","true")) and not truth(r.get("background_runtime_unknown","false"))}
    rows=[]; audit=[]
    for archive in [ROOT/"_Claude_web_answers"/"Opus4_7.zip", ROOT/"_Claude_web_answers"/"Fable5_1.zip"]:
        with zipfile.ZipFile(archive) as z:
            for member in sorted(n for n in z.namelist() if n.endswith("/messages.json")):
                config,pid=member.split("/")[:2]; d=json.loads(z.read(member)); shown,ids=get_branch(d)
                human=next(m for m in shown if m["sender"]=="human")
                start=dt(human["created_at"]); ends=[]; active=0.
                for m in shown:
                    if m["sender"]!="assistant":continue
                    starts=[dt(c["start_timestamp"]) for c in m.get("content",[]) if c.get("start_timestamp")]
                    stops=[dt(c["stop_timestamp"]) for c in m.get("content",[]) if c.get("stop_timestamp")]
                    s=min(starts) if starts else dt(m["created_at"])
                    e=max(stops) if stops else dt(m["updated_at"])
                    active+=(e-s).total_seconds(); ends.append(e)
                wall=(max(ends)-start).total_seconds()
                blocks=[(c,m["uuid"] in ids) for m in d["chat_messages"] for c in m.get("content",[])]
                results={c["tool_use_id"]:c for c,_ in blocks if c.get("type")=="tool_result"}
                ci=ai=0;selected=[]; unknown=0
                for c,current in blocks:
                    if c.get("type")!="tool_use":continue
                    ai+=1
                    if current:ci+=1
                    if c.get("name")!="bash_tool":continue
                    result=results.get(c["id"],{})
                    include=(
                        current and ci in OPUS_CURRENT.get(config,{}).get(pid,[]) or
                        not current and ai in OPUS_ALTERNATE.get((config,pid),[]) or
                        (config,pid,c["id"]) in fable_ids)
                    a=dt(c.get("stop_timestamp")); b=dt(result.get("start_timestamp"))
                    duration=(b-a).total_seconds() if a and b else None
                    if duration is None:unknown+=1
                    if include:assert duration is not None and duration>=0
                    rec=dict(config=config,prompt_id=pid,tool_use_id=c["id"],current_branch=current,
                        current_tool_ordinal=ci if current else "",all_tool_ordinal=ai,
                        include_solver=include,execution_s=duration,
                        command_generation_s=(a-dt(c["start_timestamp"])).total_seconds() if a else "",
                        execution_start=c.get("stop_timestamp"),execution_end=result.get("start_timestamp"),
                        description=c.get("input",{}).get("description",c.get("message","")),
                        command=c.get("input",{}).get("command",""),
                        source_archive=str(archive.relative_to(ROOT)),source_member=member)
                    audit.append(rec)
                    if include:selected.append(rec)
                all_solver=sum(r["execution_s"] for r in selected)
                current_solver=sum(r["execution_s"] for r in selected if r["current_branch"])
                if (config,pid) in FABLE_EXPECTED:
                    assert abs(current_solver-FABLE_EXPECTED[config,pid])<0.001,(config,pid,current_solver,FABLE_EXPECTED[config,pid])
                bound=(config,pid)==("Fable5_1_max","L1_10")
                background_lower=44.1 if bound else 0.
                current_solver+=background_lower; all_solver+=background_lower
                presence=plots[(config,pid)]
                pa=truth(presence["plot_in_answer"]); ph=truth(presence["plot_anywhere"])
                solver_any=bool(selected) or bound
                flags=([("P" if not ph else "H")] if not pa else [])+([] if solver_any else ["S"])
                notes="Solver-running command elapsed time; includes inseparable startup/rendering. Timings use displayed branch only."
                if bound: notes+=" Interrupted background solver has >=44.1 s of progress; non-solver time is an upper bound, not an exact measurement."
                if unknown:notes+=f" {unknown} untimed/truncated shell command(s); total includes identifiable recorded solver executions only."
                rows.append(dict(prompt_id=pid,level=pid.split("_")[0],config=config,series=LABELS[config],
                    total_wall_s=wall,active_response_s=active,continuation_wait_s=max(0.,wall-active),
                    timestamp_clock_skew_s=max(0.,active-wall),final_stop_reason=shown[-1].get("stop_reason",""),
                    export_has_truncation=any(m.get("truncated") for m in d["chat_messages"]),
                    solver_current_s=current_solver,solver_all_history_command_s=all_solver,
                    background_solver_lower_bound_s=background_lower,
                    excluded_interrupted_solver_or_downtime_s=0,
                    non_solver_wall_s=wall-current_solver,non_solver_wall_min=(wall-current_solver)/60,
                    non_solver_active_s=active-current_solver,non_solver_active_min=(active-current_solver)/60,
                    timing_kind="upper_bound" if bound else "execution_proxy",upper_bound=bound,estimated=True,
                    recorded_status="truncated_final_message" if shown[-1].get("truncated") else "recorded",
                    plot_in_answer=pa,plot_anywhere=ph,solver_anywhere=solver_any,web_flags="+".join(flags),
                    plot_evidence=presence.get("plot_evidence",presence.get("evidence","")),
                    untimed_shell_commands=unknown,alternate_messages=sum(m["uuid"] not in ids for m in d["chat_messages"]),
                    source_archive=str(archive.relative_to(ROOT)),source_member=member,
                    source_sha256=hashlib.sha256(z.read(member)).hexdigest(),timing_notes=notes))
                assert wall-current_solver>=0 and active-current_solver>=0
    assert len(rows)==55
    write_csv("solver_command_audit.csv",audit)
    return sorted(rows,key=lambda r:(sortkey(r["prompt_id"]),list(LABELS).index(r["config"])))

def main():
    framework=framework_rows(); web=web_rows(); rows=framework+web
    for r in rows:
        r["plotted_non_solver_s"]=r["non_solver_active_s"]
        r["plotted_non_solver_min"]=r["non_solver_active_min"]
        r["excluded_between_turns_s"]=r.get("continuation_wait_s",0) if r["config"]!="framework" else 0
    write_csv("all_run_timings.csv",rows)
    lookup={(r["prompt_id"],r["config"]):r for r in rows}
    l1=[]
    for j in range(1,12):
        for config,label in LABELS.items():
            pid=f"L1_{j}"
            l1.append(lookup.get((pid,config),dict(prompt_id=pid,level="L1",config=config,series=label,
                recorded_status="no_exported_run",non_solver_wall_min="",non_solver_active_min="",web_flags="")))
    full=[lookup[(r["prompt_id"],config)] for r in framework for config in ("framework","Opus4_7_high")]
    write_csv("L1_comparison.csv",l1);write_csv("all_prompts_framework_vs_opus_high.csv",full)
    for filename,data in [("L1_comparison_wide.csv",l1),("all_prompts_comparison_wide.csv",full)]:
        wide={}
        for r in data:
            p=wide.setdefault(r["prompt_id"],dict(prompt_id=r["prompt_id"]))
            prefix=r["config"]
            for field in ("plotted_non_solver_min","non_solver_wall_min","non_solver_active_min","web_flags","recorded_status","upper_bound"):
                p[prefix+"__"+field]=r.get(field,"")
        write_csv(filename,list(wide.values()))
    summary={"framework_runs":len(framework),"web_runs":len(web),"l1_slots":len(l1),"full_comparison_rows":len(full),
        "timing_basis":"Framework recorded elapsed minus numerical solver; web displayed-branch active response spans minus same-branch solver command execution, excluding gaps between turns",
        "no_plot_anywhere":sum(not r["plot_anywhere"] for r in web),
        "no_solver_anywhere":sum(not r["solver_anywhere"] for r in web),
        "plot_only_in_history":sum(r["plot_anywhere"] and not r["plot_in_answer"] for r in web),
        "uncertain_runs":[{"config":r["config"],"prompt_id":r["prompt_id"],"kind":r["timing_kind"]} for r in rows if r.get("upper_bound") or r["timing_kind"]=="reconstructed"],
    }
    (HERE/"validation.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()

