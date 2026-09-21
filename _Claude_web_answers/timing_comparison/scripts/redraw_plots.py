"""Redraw the requested stacked comparisons from CSVs only (no archive access)."""
from pathlib import Path
from collections import defaultdict
import argparse,csv,json,math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch,Rectangle
from matplotlib.ticker import MultipleLocator,MaxNLocator

HERE = Path(__file__).resolve().parents[1]
AUDIT = HERE / "audit"
EXPORTS = HERE / "exports"
CONFIGS=["framework","Opus4_7_high","Opus4_7_max","Fable5_1_medium","Fable5_1_max"]
CODES=dict(zip(CONFIGS,["FW","OH","OM","FM","FX"]))
COMPONENTS={
 "fw_lc1":("LC1: system / equation mapping","#43A56D"),
 "fw_lc2":("LC2: thermodynamic data assembly","#2C75B6"),
 "fw_lc3":("LC3: solver configuration","#FFA261"),
 "fw_ld":("LD: validation","#C799DF"),
 "fw_other":("Orchestration, reporting / other","#7E43A8"),
 "web_thinking":("Thinking","#56428E"),
 "web_code_tool_input":("Code / tool-input generation","#8B9ED5"),
 "web_answer_writing":("Answer writing","#D7C4E8"),
 "web_non_solver_tools":("Non-solver tool execution","#E9A76C"),
 "web_other_overhead":("Other within-turn overhead","#AAB6C1"),
}
FW=list(COMPONENTS)[:5];WEB=list(COMPONENTS)[5:]
def truth(v):return str(v).lower() in ("true","1","yes")
def read_csv(name, folder=HERE):
    with (folder/name).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(name,rows,folder=HERE):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (folder/name).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def key(pid):return tuple(int(x) for x in pid.replace("L","").split("_"))

def assemble():
    data=read_csv("all_run_timings.csv", AUDIT)
    groups=defaultdict(dict)
    for filename in ("framework_stage_breakdown.csv","web_stage_breakdown.csv"):
        for r in read_csv(filename, AUDIT):
            config=r.get("config") or "framework"
            comp=r["component"]
            assert comp in COMPONENTS,comp
            groups[(r["prompt_id"],config)][comp]=float(r["seconds"])/60
    allrows=[]
    for r in data:
        values=groups[(r["prompt_id"],r["config"])]
        expected=float(r["plotted_non_solver_min"])
        assert abs(sum(values.values())-expected)<0.003,(r["prompt_id"],r["config"],sum(values.values()),expected)
        row=dict(r)
        row.update({c+"_min":values.get(c,0.) for c in COMPONENTS})
        row["stack_total_min"]=sum(values.values())
        allrows.append(row)
    l1=[r for r in allrows if r["level"]=="L1"]
    full=[r for r in allrows if r["config"] in ("framework","Opus4_7_high")]
    write_csv("L1_stacked_bars.csv",l1)
    write_csv("all_prompts_stacked_bars.csv",full)
    long=[]
    for r in allrows:
        for c in (FW if r["config"]=="framework" else WEB):
            long.append(dict(prompt_id=r["prompt_id"],config=r["config"],series=r["series"],
                component=c,component_label=COMPONENTS[c][0],minutes=r[c+"_min"],
                seconds=r[c+"_min"]*60,bar_total_min=r["stack_total_min"],web_flags=r["web_flags"],
                recorded_status=r["recorded_status"],upper_bound=r["upper_bound"]))
    write_csv("all_stacked_components_long.csv",long,AUDIT)
    return allrows

def add_legend(fig,x):
    handles=[Patch(facecolor=COMPONENTS[c][1],edgecolor="#444",linewidth=.4,label=COMPONENTS[c][0]) for c in FW[::-1]]
    legend=fig.legend(handles=handles,loc="upper left",bbox_to_anchor=(x,.91),frameon=False,
        title="Framework stages",fontsize=9.2,title_fontsize=10.5,handlelength=1.5,labelspacing=.6)
    fig.add_artist(legend)
    handles=[Patch(facecolor=COMPONENTS[c][1],edgecolor="#444",linewidth=.4,label=COMPONENTS[c][0]) for c in WEB[::-1]]
    fig.legend(handles=handles,loc="upper left",bbox_to_anchor=(x,.66),frameon=False,
        title="Web activity",fontsize=9.2,title_fontsize=10.5,handlelength=1.5,labelspacing=.6)
    fig.text(x+.009,.37,
        "Web output flags\nP  No plot anywhere in saved history\nS  No recorded solver execution\nH  Plot only in history, not the answer\n—  No exported run\n\n"
        "Hatched FW bars: recorded as\nincomplete, timed out, or failed.\n"
        "*  Reconstructed resumed run\n≤  Upper bound: interrupted solver",
        fontsize=9.1,va="top",linespacing=1.45,color="#333333")

def draw(rows,configs,prompts,filename,title,sectioned=False):
    fig=plt.figure(figsize=(23,8.6) if sectioned else (19,8.6))
    ax=fig.add_axes([.055,.245,.75,.655])
    lookup={(r["prompt_id"],r["config"]):r for r in rows}
    totals=[float(r["stack_total_min"]) for r in rows if r["prompt_id"] in prompts and r["config"] in configs]
    ymax=math.ceil(max(totals)*1.20/5)*5
    ax.set_ylim(0,ymax)
    step=len(configs)+.85
    allpos=[];ticks=[];groupcenters=[]
    for i,pid in enumerate(prompts):
        center=i*step+(len(configs)-1)/2
        groupcenters.append(center)
        for j,config in enumerate(configs):
            x=i*step+j;allpos.append(x);ticks.append(CODES[config])
            r=lookup.get((pid,config))
            if r is None:
                ax.text(x,ymax*.008,"—",ha="center",va="bottom",fontsize=8.5,color="#A6A6A6")
                continue
            bottom=0.
            for comp in FW if config=="framework" else WEB:
                height=float(r[comp+"_min"])
                ax.bar(x,height,bottom=bottom,width=.81,color=COMPONENTS[comp][1],
                    edgecolor="white",linewidth=.33,zorder=3)
                bottom+=height
            hatched=config=="framework" and r["recorded_status"]!="complete"
            ax.add_patch(Rectangle((x-.405,0),.81,bottom,fill=False,
                edgecolor="#333333",linewidth=.65,hatch="///" if hatched else None,zorder=4))
            label=f"{bottom:.1f}"
            if truth(r["upper_bound"]):label="≤"+label
            if config=="framework" and truth(r["estimated"]):label+="*"
            flags=r.get("web_flags","") if config!="framework" else ""
            ax.text(x,bottom+ymax*.009,label,rotation=90 if sectioned else 0,
                    ha="center",va="bottom",fontsize=7 if sectioned else 7.6,color="#242424")
            if flags:
                offset=ymax*(.054 if sectioned else .043)
                ax.text(x,bottom+offset,flags,rotation=90 if sectioned else 0,
                    ha="center",va="bottom",fontsize=7 if sectioned else 7.5,
                    color="#A22522",fontweight="bold")
        ax.text(center,-.09,pid,transform=ax.get_xaxis_transform(),ha="right" if sectioned else "center",
                va="top",fontsize=9.1 if sectioned else 10,rotation=55 if sectioned else 0,clip_on=False)
        if i<len(prompts)-1:
            ax.axvline(i*step+len(configs)-.075,color="#E3E3E3",linewidth=.55,zorder=0)
    if sectioned:
        labels={"L1":"Diagram construction","L2":"Multistep research","L3":"Hypothesis tests","L4":"Scope / limits"}
        for level in ("L1","L2","L3","L4"):
            indices=[i for i,p in enumerate(prompts) if p.startswith(level+"_")]
            center=(groupcenters[min(indices)]+groupcenters[max(indices)])/2
            ax.text(center,ymax*.975,level+" · "+labels[level],ha="center",va="top",fontsize=11,color="#343434")
            if level!="L4":
                border=max(indices)*step+len(configs)-.075
                ax.axvline(border,color="#888888",linewidth=.95,zorder=1)
    ax.set_xlim(-.8,(len(prompts)-1)*step+len(configs)-.2)
    ax.set_xticks(allpos,ticks,rotation=90,fontsize=7.5 if sectioned else 8)
    ax.tick_params(axis="x",length=0,pad=4)
    ax.set_ylabel("Time excluding solver (min)",fontsize=12)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6,integer=True))
    ax.grid(axis="y",color="#D7DCE0",linewidth=.6,zorder=0)
    for spine in ax.spines.values():spine.set_color("#4B4B4B");spine.set_linewidth(.8)
    fig.suptitle(title,x=.055,y=.973,ha="left",fontsize=16,fontweight="bold")
    modes="FW  Our framework     OH  Opus 4.7 high"
    if len(configs)>2:modes+="     OM  Opus 4.7 max     FM  Fable 5.1 medium     FX  Fable 5.1 max"
    fig.text(.055,.926,modes,ha="left",fontsize=10.5,color="#444444")
    add_legend(fig,.823)
    fig.text(.055,.085,
        "Web bars exclude waiting between turns and use the displayed conversation branch. Output flags inspect the entire saved history.",
        fontsize=9.8,color="#444444")
    fig.text(.055,.052,
        "Solver-running web commands may include inseparable rendering/startup; those commands are excluded. Bar heights are timing estimates, not quality scores.",
        fontsize=9.3,color="#555555")
    fig.text(.055,.020,"Each stack sums to the bar total. Missing exports are shown as —, not zero-time runs.",fontsize=9.3,color="#555555")
    for ext in ("png","pdf","svg"):
        fig.savefig((HERE if ext=="png" else EXPORTS)/(filename+"."+ext),dpi=300,facecolor="white",metadata={"Creator":"SRD46 timing comparison"} if ext!="png" else None)
    plt.close(fig)

def main():
    EXPORTS.mkdir(exist_ok=True)
    parser=argparse.ArgumentParser()
    parser.add_argument("--from-plot-csv",action="store_true",help="Redraw from existing stacked CSVs without rebuilding tables.")
    args=parser.parse_args()
    plt.rcParams.update({"font.family":"DejaVu Sans","pdf.fonttype":42,"ps.fonttype":42,"svg.fonttype":"none",
                         "axes.axisbelow":True,"hatch.linewidth":.35})
    if args.from_plot_csv:
        l1=read_csv("L1_stacked_bars.csv");full=read_csv("all_prompts_stacked_bars.csv")
    else:
        allrows=assemble();l1=[r for r in allrows if r["level"]=="L1"]
        full=[r for r in allrows if r["config"] in ("framework","Opus4_7_high")]
    draw(l1,CONFIGS,[f"L1_{i}" for i in range(1,12)],"L1_framework_vs_web_stacked",
         "L1 prompts · framework versus web harness")
    prompts=sorted({r["prompt_id"] for r in full},key=key)
    draw(full,CONFIGS[:2],prompts,"all_prompts_framework_vs_opus_high_stacked",
         "All benchmark prompts · framework versus Opus 4.7 high",sectioned=True)
    print("Created both comparisons as PNG, PDF, SVG; stacked CSVs support direct redrawing.")

if __name__=="__main__":main()

