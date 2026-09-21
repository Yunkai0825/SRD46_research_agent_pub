"""Build an explicitly requested parsed tree from model archives or legacy exports.

    python parse_exports.py --export Fable5_1.zip --export Opus4_7.zip --renderings Renderings.zip --out parsed
    (or: python build_renderings.py parse ...)

Consolidated model ZIPs supply their own rendered images when --renderings is
omitted. Their destination folders use <configuration>/<prompt_id>/. This
explicit command writes a new parsed tree; it does not modify the input archives.

parsed/
  <export>_<effort>/<prompt>/          e.g. Opus4_7_high/L1_8 Pourbaix diagrams for copper, zinc, and iron/
      conversation.json                the run's messages.json, unchanged
      final_answer.md                  Claude's final answer: the text (and charts, widgets, presented images,
                                       published pages) after the last working tool call of the branch claude.ai shows
      <images>                         every image final_answer.md embeds (presented outputs; charts and widgets
                                       come from Renderings)
      <report>.html                    HTML reports the run saved to its outputs, if any
  _summary/
      runs.csv                  one row per run: prompt metadata (id, level, number, title, full text), timings and shares,
                                Continues, tool calls/time/errors per tool and per category, web research, code written, answer length
      prompts.csv               one row per prompt: metadata, then every configuration's key metrics side by side (<config>__<metric>)
      metrics_long.csv          tidy table, one row per run and numeric metric (for pivoting and plotting)
      tool_calls_by_prompt.csv  one row per run and tool: calls, time, errors, share of the run's calls
      segments.csv              one row per response segment (turn), including Continues
      tools.csv                 one row per tool call
      code_files.csv            every file the run wrote visibly (create_file, cat > file << EOF), with its final length
      summary.md                tables, plots and definitions
      plots/*.png               comparisons across configurations, on the prompt levels more than one configuration ran
      plots/<config>_by_level/  for a configuration that also ran other levels: the same views across all its prompts
"""
import argparse, csv, io, json, math, os, posixpath, re, shutil, statistics, sys, zipfile, zlib
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_zip import Export, shown_branch

OUTS = "/mnt/user-data/outputs/"
HOME = "/home/claude/"
DISPLAY_TOOLS = {"present_files", "chart_display_v0", "visualize:show_widget", "visualize:read_me", "Artifact"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
HTML_EXT = {".html", ".htm"}
CT = timedelta(hours=-5)


# ------------------------------------------------------------------ helpers
def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def ct_str(d):
    d = d + CT
    return d.strftime("%b %d %Y, ") + d.strftime("%I:%M %p").lstrip("0") + " CT"


def inp_of(b):
    i = b.get("input")
    if isinstance(i, str):
        try:
            return json.loads(i)
        except Exception:
            return {}
    return i or {}


def result_text(b):
    parts = []
    for it in b.get("content") or []:
        if isinstance(it, dict) and it.get("type") == "text":
            parts.append(it.get("text", ""))
    return "\n".join(parts)


def md_link(name):
    return name.replace(" ", "%20").replace("(", "%28").replace(")", "%29")


class RenderingsSource:
    """Renderings.zip or a rendered folder; find('Opus4_7/<prompt>/<run>/chart_1_') -> (name, bytes)."""

    def __init__(self, path):
        self.zip = self.dir = None
        self.names = []
        if not path:
            return
        p = Path(path)
        if p.is_dir():
            self.dir = p
            self.names = [f.relative_to(p).as_posix() for f in p.rglob("*") if f.is_file()]
        elif p.exists():
            self.zip = zipfile.ZipFile(p)
            self.names = [n[len("Renderings/"):] if n.startswith("Renderings/") else n for n in self.zip.namelist()]
            self._full = dict(zip(self.names, self.zip.namelist()))

    def find(self, prefix, suffix=".png"):
        hits = sorted(n for n in self.names if n.startswith(prefix) and n.endswith(suffix) and "_standalone" not in n)
        if not hits:
            return None
        n = hits[0]
        data = (self.dir / n).read_bytes() if self.dir else self.zip.read(self._full[n])
        return posixpath.basename(n), data


    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.zip:
            self.zip.close()


# ------------------------------------------------------------------ final answer
def final_answer_items(conv, shown):
    """Items after the last working tool call on the shown branch: ('text', s) / ('tool', block, chart_or_widget_no)."""
    counters = Counter()
    numbered = {}
    for m in conv["chat_messages"]:  # export order = numbering used by transcripts and Renderings
        for b in m["content"]:
            if b["type"] == "tool_use" and b.get("name") in ("chart_display_v0", "visualize:show_widget"):
                counters[b["name"]] += 1
                numbered[b.get("id")] = counters[b["name"]]
    blocks = [b for m in shown if m["sender"] == "assistant" for b in m["content"]]
    last = -1
    for i, b in enumerate(blocks):
        if b["type"] == "tool_use" and b.get("name") not in DISPLAY_TOOLS:
            last = i
    items = []
    results = {b.get("tool_use_id"): b for b in blocks if b["type"] == "tool_result"}
    for b in blocks[last + 1:]:
        if b["type"] == "text" and b.get("text", "").strip():
            items.append(("text", b["text"]))
        elif b["type"] == "tool_use" and b.get("name") in DISPLAY_TOOLS - {"visualize:read_me"}:
            items.append(("tool", b, numbered.get(b.get("id")), results.get(b.get("id"))))
    return items


def locate(run, path):
    """export-relative file for a sandbox path, or None."""
    files = run.files("artifacts/")
    if path.startswith(OUTS) and "artifacts/" + path[len(OUTS):] in files:
        return "artifacts/" + path[len(OUTS):]
    if path.startswith(HOME) and "artifacts/sandbox/" + path[len(HOME):] in files:
        return "artifacts/sandbox/" + path[len(HOME):]
    base = posixpath.basename(path)
    for rel in sorted(files, key=lambda r: ("/sandbox/" in r, r)):
        if posixpath.basename(rel) == base:
            return rel
    return None


def write_run_folder(run, conv, shown, rend, dst, tm):
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    (dst / "conversation.json").write_bytes(run.read("messages.json"))
    used = {}

    def put(name, data):
        name = re.sub(r'[<>:"/\\|?*]', "_", name)
        stem, ext = posixpath.splitext(name)
        k = 1
        while name in used and used[name] != data:
            k += 1
            name = f"{stem}_{k}{ext}"
        used[name] = data
        (dst / name).write_bytes(data)
        return name

    body, images, htmls, missing = [], [], [], []
    for it in final_answer_items(conv, shown):
        if it[0] == "text":
            body.append(it[1])
            continue
        _, b, num, res = it
        name, inp = b.get("name"), inp_of(b)
        if name in ("chart_display_v0", "visualize:show_widget"):
            kind = "chart" if name == "chart_display_v0" else "widget"
            hit = rend.find(f"{run.render_prefix}/{kind}_{num}_") if num else None
            title = inp.get("title", kind)
            if hit:
                fn = put(hit[0], hit[1])
                images.append(fn)
                body.append(f"![{title}]({md_link(fn)})")
            else:
                missing.append(f"{kind} {num}")
                body.append(f"*[{kind}: {title} — no rendering available]*")
        elif name == "present_files":
            paths = inp.get("filepaths") or [x.get("file_path") for x in (res or {}).get("content", []) if isinstance(x, dict) and x.get("type") == "local_resource"]
            lines = []
            for p in paths or []:
                rel = locate(run, p)
                ext = posixpath.splitext(p)[1].lower()
                if rel and ext in IMAGE_EXT:
                    fn = put(posixpath.basename(rel), run.read(rel))
                    images.append(fn)
                    lines.append(f"![{posixpath.basename(p)}]({md_link(fn)})")
                elif rel and ext in HTML_EXT:
                    fn = put(posixpath.basename(rel), run.read(rel))
                    htmls.append(fn)
                    lines.append(f"[{fn}]({md_link(fn)})")
                else:
                    if not rel:
                        missing.append(posixpath.basename(p))
                    lines.append(f"*Presented file: `{posixpath.basename(p)}`*" + ("" if rel else " *(not in the export)*"))
            body.append("\n\n".join(lines))
        elif name == "Artifact" and inp.get("file_path"):
            rel = locate(run, inp["file_path"])
            if rel:
                fn = put(posixpath.basename(rel), run.read(rel))
                htmls.append(fn)
                body.append(f"[{inp.get('title') or fn}]({md_link(fn)})")
    # HTML reports saved to outputs but not shown in the answer tail
    for rel in run.files("artifacts/"):
        if rel.startswith("artifacts/sandbox/") or posixpath.splitext(rel)[1].lower() not in HTML_EXT or posixpath.basename(rel).startswith("widget_"):
            continue
        data = run.read(rel)
        if any(used.get(n) == data for n in used):
            continue
        fn = put(posixpath.basename(rel), data)
        htmls.append(fn)
        body.append(f"*HTML report saved by this run: [{fn}]({md_link(fn)})*")
    fm = ["---", f"export: {run.group}", f"model: {conv.get('model')}", f"effort: {run.effort}", f"run: {run.run_name}",
          f"prompt: {json.dumps(run.prompt, ensure_ascii=False)}", f"conversation: https://claude.ai/chat/{conv['uuid']}",
          f"started: {tm['started'].isoformat()}", f"finished: {tm['finished'].isoformat() if tm['finished'] else ''}",
          f"stop_reason: {tm['stop_reasons'][-1] if tm['stop_reasons'] else ''}", "---", ""]
    text = "\n".join(fm) + "\n\n".join(body).strip() + "\n"
    (dst / "final_answer.md").write_text(text, encoding="utf-8")
    words = len(re.findall(r"\S+", "\n".join(x for x in body if not x.startswith(("![", "*Presented", "*HTML report", "[")))))
    return dict(images=len(images), html_reports=len(htmls), final_answer_chars=sum(len(x) for x, in [(t,) for t in body]),
                final_answer_words=words, answer_missing="; ".join(missing))


# ------------------------------------------------------------------ statistics
def run_stats(run, conv, shown):
    """Timing definitions match the exports' runs.csv."""
    think = text = 0.0
    tools, tool_time = Counter(), Counter()
    uses, tool_rows, seg_rows = {}, [], []
    stop_reasons = []
    last = None
    thinking_blocks = summaries = text_blocks = tool_errors = bash_nonzero = 0
    human = shown[0]
    started = ts(human["created_at"])
    prev_end = started
    prev_msg = human
    seg_no = 0
    for m in shown[1:]:
        if m["sender"] == "human":
            prev_msg = m
            continue
        seg_no += 1
        stop_reasons.append(m.get("stop_reason"))
        starts = [ts(b["start_timestamp"]) for b in m["content"] if b.get("start_timestamp")]
        stops = [ts(b["stop_timestamp"]) for b in m["content"] if b.get("stop_timestamp")]
        s_start = min(starts) if starts else ts(m["created_at"])
        s_end = max(stops) if stops else ts(m["updated_at"])
        parent_is_human = prev_msg["sender"] == "human"
        trigger = "prompt" if prev_msg is human else ("typed continue" if parent_is_human else "auto continue")
        seg = dict(segment=seg_no, trigger=trigger, message_uuid=m["uuid"], start_utc=s_start.isoformat(), end_utc=s_end.isoformat(),
                   duration_s=round((s_end - s_start).total_seconds(), 1), wait_before_s=round((s_start - prev_end).total_seconds(), 1),
                   user_wait_s=round((ts(prev_msg["created_at"]) - prev_end).total_seconds(), 1) if trigger == "typed continue" else "",
                   stop_reason=m.get("stop_reason"))
        st = Counter()
        for b in m["content"]:
            s0, s1 = ts(b.get("start_timestamp")), ts(b.get("stop_timestamp"))
            if s1:
                last = s1 if last is None or s1 > last else last
            dur = (s1 - s0).total_seconds() if (s0 and s1) else 0.0
            t = b["type"]
            if t == "thinking":
                think += dur; st["thinking_s"] += dur
                thinking_blocks += 1
                summaries += len(b.get("summaries") or [])
            elif t == "text":
                text += dur; st["text_s"] += dur
                text_blocks += 1
            elif t == "tool_use":
                tools[b.get("name")] += 1
                st["tool_calls"] += 1
                uses[b.get("id")] = (b.get("name"), s0, b, seg_no)
            elif t == "tool_result":
                u = uses.get(b.get("tool_use_id"))
                if u and s1 and u[1]:
                    d = (s1 - u[1]).total_seconds()
                    tool_time[u[0]] += d; st["tool_s"] += d
                    rt = result_text(b)
                    code = ""
                    if u[0] == "bash_tool":
                        mm = re.match(r'\s*\{"returncode":\s*(-?\d+)', rt)
                        code = int(mm.group(1)) if mm else ""
                        if code not in ("", 0):
                            bash_nonzero += 1
                    if b.get("is_error"):
                        tool_errors += 1
                    ui = inp_of(u[2])
                    tool_rows.append(dict(segment=u[3], tool=u[0], start_utc=u[1].isoformat(), duration_s=round(d, 2),
                                          is_error=bool(b.get("is_error")), exit_code=code,
                                          input_chars=len(json.dumps(ui, ensure_ascii=False)), output_chars=len(rt),
                                          description=(ui.get("description") or ui.get("query") or ui.get("path") or ui.get("url") or "")[:120]))
        seg.update({k: round(st[k], 1) for k in ("thinking_s", "text_s", "tool_s")}, tool_calls=st["tool_calls"])
        seg_rows.append(seg)
        prev_end, prev_msg = s_end, m
    wall = (last - started).total_seconds() if last else 0.0
    active = sum(s["duration_s"] for s in seg_rows)
    tool_s = sum(tool_time.values())
    alt = [m for m in conv["chat_messages"] if m["uuid"] not in {x["uuid"] for x in shown}]
    alt_active = 0.0
    for m in alt:
        if m["sender"] != "assistant":
            continue
        a = [ts(b["start_timestamp"]) for b in m["content"] if b.get("start_timestamp")]
        z = [ts(b["stop_timestamp"]) for b in m["content"] if b.get("stop_timestamp")]
        if a and z:
            alt_active += (max(z) - min(a)).total_seconds()
    prompt_text = " ".join(b.get("text", "") for b in human["content"] if b["type"] == "text")
    row = dict(started=started, finished=last, wall_s=wall, active_s=active, waiting_s=max(wall - active, 0.0), thinking_s=think, text_s=text,
               tool_s=tool_s, other_s=max(active - think - text - tool_s, 0.0), segments=len(seg_rows),
               typed_continues=sum(1 for s in seg_rows if s["trigger"] == "typed continue"),
               auto_continues=sum(1 for s in seg_rows if s["trigger"] == "auto continue"),
               stop_reasons=stop_reasons, incomplete=bool(stop_reasons and stop_reasons[-1] != "end_turn"),
               tool_calls=sum(tools.values()), tools=tools, tool_time=tool_time, tool_errors=tool_errors, bash_nonzero_exit=bash_nonzero,
               thinking_blocks=thinking_blocks, thinking_summaries=summaries, text_blocks=text_blocks,
               prompt_chars=len(prompt_text), prompt_text=prompt_text, alternate_messages=len(alt), alternate_active_s=alt_active)
    return row, seg_rows, tool_rows


# ------------------------------------------------------------------ activity: tool categories, web research, code written
CATEGORIES = [("literature search", {"web_search", "web_fetch"}),
              ("build/edit scripts", {"create_file", "str_replace"}),
              ("commands", {"bash_tool"}),
              ("inspect files/images", {"view"}),
              ("present results", {"present_files", "chart_display_v0", "visualize:show_widget", "visualize:read_me", "Artifact"})]
CAT_KEYS = {"literature search": "lit", "build/edit scripts": "build", "commands": "cmd", "inspect files/images": "inspect",
            "present results": "present", "other": "other"}
CODE_EXT = {".py", ".js", ".mjs", ".ts", ".sh", ".bash", ".r", ".jl", ".m", ".c", ".cc", ".cpp", ".h", ".f90", ".for", ".gp"}
HTML_DOC_EXT = {".html", ".htm"}
HEREDOC = re.compile(r"(?P<pre>[^\n]*?)<<-?\s*(['\"]?)(?P<tag>[A-Za-z_]\w*)\2[^\n]*\n(?P<body>.*?)\n[ \t]*(?P=tag)[ \t]*(?=\n|$)", re.S)
CD = re.compile(r"(?:^|[;&|(]\s*|\n\s*)cd\s+([^\s;&|)]+)")


def category(tool):
    for name, members in CATEGORIES:
        if tool in members:
            return name
    return "other"


def nlines(t):
    return 0 if not t else t.count("\n") + (0 if t.endswith("\n") else 1)


def _abs(path, cwd):
    path = path.strip("'\"")
    if path.startswith("~/"):
        path = HOME + path[2:]
    return posixpath.normpath(path if path.startswith("/") else posixpath.join(cwd, path))


def activity_stats(shown):
    uses = {}
    results = {}
    order = []
    for m in shown:
        if m["sender"] != "assistant":
            continue
        for b in m["content"]:
            if b["type"] == "tool_use":
                uses[b.get("id")] = b
                order.append(b)
            elif b["type"] == "tool_result":
                results[b.get("tool_use_id")] = b
    cats = Counter(category(b.get("name")) for b in order)
    total = sum(cats.values())
    search_urls, fetched_ok, domains = set(), set(), set()
    fetch_failed = 0
    files = {}  # path -> dict(content, created_by, writes, edits, unmatched)
    written_lines = inline_lines = cmd_lines = edits_ok = edits_unmatched = 0

    def write(path, content, how, append=False):
        f = files.setdefault(path, dict(content="", created_by=how, writes=0, edits=0))
        f["content"] = (f["content"] + content) if append else content
        f["writes"] += 1

    for b in order:
        name, inp, res = b.get("name"), inp_of(b), results.get(b.get("id")) or {}
        err = bool(res.get("is_error"))
        if name == "web_search":
            for it in res.get("content") or []:
                if isinstance(it, dict) and it.get("url"):
                    search_urls.add(it["url"])
        elif name == "web_fetch":
            if err or not res:
                fetch_failed += 1
            elif inp.get("url"):
                fetched_ok.add(inp["url"])
        elif name == "create_file" and not err and inp.get("path"):
            write(posixpath.normpath(inp["path"]), inp.get("file_text", ""), "create_file")
            if posixpath.splitext(inp["path"])[1].lower() in CODE_EXT:
                written_lines += nlines(inp.get("file_text", ""))
        elif name == "str_replace" and not err and inp.get("path"):
            pth = posixpath.normpath(inp["path"])
            f = files.get(pth)
            if f is not None and inp.get("old_str", "") and inp["old_str"] in f["content"]:
                f["content"] = f["content"].replace(inp["old_str"], inp.get("new_str", ""), 1)
                f["edits"] += 1
                edits_ok += 1
            else:
                edits_unmatched += 1
            if posixpath.splitext(pth)[1].lower() in CODE_EXT:
                written_lines += nlines(inp.get("new_str", ""))
        elif name == "bash_tool":
            cmd = inp.get("command", "") or ""
            cmd_lines += nlines(cmd)
            for hd in HEREDOC.finditer(cmd):
                pre, body = hd.group("pre"), hd.group("body")
                before = cmd[:hd.start("pre") + len(pre)]
                cds = CD.findall(before)
                cwd = HOME.rstrip("/")
                for d in cds:
                    cwd = _abs(d, cwd)
                mw = re.search(r"(?:cat|tee)\s*(-a\s*)?(>>?)?\s*([^\s;&|<>]+)\s*$", pre)
                if re.search(r"\bpython3?\s*(-\s*)?$", pre) or re.search(r"\b(node|Rscript|julia|bash|sh)\s*(-\s*)?$", pre):
                    inline_lines += nlines(body)
                elif mw and mw.group(3) not in ("EOF",):
                    pth = _abs(mw.group(3), cwd)
                    write(pth, body + "\n", "bash heredoc", append=(mw.group(2) == ">>" or bool(mw.group(1))))
                    if posixpath.splitext(pth)[1].lower() in CODE_EXT:
                        written_lines += nlines(body)
            for mc in re.finditer(r"\bpython3?\s+-c\s+(\"(?:[^\"\\]|\\.)*\"|'[^']*')", cmd):
                inline_lines += nlines(mc.group(1)[1:-1])
    for u in search_urls | fetched_ok:
        try:
            from urllib.parse import urlparse
            h = urlparse(u).hostname or ""
            domains.add(h[4:] if h.startswith("www.") else h)
        except Exception:
            pass
    code_files = []
    for pth, f in sorted(files.items()):
        ext = posixpath.splitext(pth)[1].lower()
        kind = "code" if ext in CODE_EXT else ("html" if ext in HTML_DOC_EXT else "other")
        code_files.append(dict(path=pth, kind=kind, created_by=f["created_by"], writes=f["writes"], edits=f["edits"],
                               final_lines=nlines(f["content"]), final_chars=len(f["content"])))
    code = [c for c in code_files if c["kind"] == "code"]
    html = [c for c in code_files if c["kind"] == "html"]
    row = {f"calls_{CAT_KEYS[c]}": cats.get(c, 0) for c in CAT_KEYS}
    row.update({f"frac_{CAT_KEYS[c]}": round(cats.get(c, 0) / total, 3) if total else 0 for c in CAT_KEYS})
    row.update(web_searches=sum(1 for b in order if b.get("name") == "web_search"), search_result_urls=len(search_urls),
               pages_fetched=len(fetched_ok), fetch_failed=fetch_failed, pages_reached=len(search_urls | fetched_ok), web_domains=len(domains),
               scripts_written=len(code), final_code_lines=sum(c["final_lines"] for c in code), final_code_chars=sum(c["final_chars"] for c in code),
               code_lines_written=written_lines, str_replace_applied=edits_ok, str_replace_untracked=edits_unmatched,
               inline_script_lines=inline_lines, command_lines=cmd_lines, html_files_written=len(html),
               final_html_lines=sum(c["final_lines"] for c in html))
    return row, code_files


TOOL_COLS = ["bash_tool", "create_file", "str_replace", "view", "web_search", "web_fetch", "present_files", "chart_display_v0",
             "visualize:show_widget", "visualize:read_me", "Artifact"]


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ------------------------------------------------------------------ plots
TOOL_COLORS = {"web_search": "#6baed6", "web_fetch": "#2171b5", "create_file": "#fd8d3c", "str_replace": "#d94801", "bash_tool": "#525252",
               "view": "#41ab5d", "present_files": "#bcbddc", "chart_display_v0": "#9e9ac8", "visualize:show_widget": "#807dba",
               "visualize:read_me": "#dadaeb", "Artifact": "#54278f"}
CAT_COLORS = {"literature search": "#2b8cbe", "build/edit scripts": "#e6550d", "commands": "#636363", "inspect files/images": "#31a354",
              "present results": "#9e9ac8", "other": "#d9d9d9"}
TIME_PARTS = [("thinking_s", "thinking", "#6a51a3"), ("text_s", "writing text", "#9e9ac8"), ("tool_s", "tools", "#e6550d"),
              ("other_s", "other model time", "#bdbdbd"), ("waiting_s", "between segments", "#fdd0a2")]
EFFORT_ORDER = {"max": 0, "high": 1, "medium": 2, "low": 3}


def config_order(configs):
    return sorted(configs, key=lambda c: (c.split("_")[0], EFFORT_ORDER.get(c.split("_")[-1], 9)))


def pkey(p):
    m = re.match(r"L(\d+)_(\d+)", p)
    return (int(m.group(1)), int(m.group(2))) if m else (99, 99)


def comparison_levels(runs):
    """Prompt levels that more than one configuration ran; cross-configuration plots use only these."""
    by_level = defaultdict(set)
    for r in runs:
        by_level[r["level"]].add(r["config"])
    return sorted(lv for lv, cs in by_level.items() if len(cs) > 1)


def short_config(c):
    exp, _, eff = c.rpartition("_")
    return f"{exp.split('_')[0].rstrip('0123456789')} {eff}"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    return plt


class PlotSet:
    def __init__(self, plot_dir, rel=""):
        self.dir, self.rel, self.files = plot_dir, rel, []
        plot_dir.mkdir(parents=True, exist_ok=True)

    def save(self, fig, name, title):
        plt = _plt()
        fig.tight_layout()
        fig.savefig(self.dir / name, dpi=150)
        plt.close(fig)
        self.files.append((self.rel + name, title))


def grouped_segmented(ax, groups, slots, get, parts, slot_color, share=False, group_label=None, gap=0.8):
    """Segmented (stacked) bars: one bar per slot (configuration) that has data, grouped by group (prompt).
    parts = [(value_fn, label, color)]. Returns the part labels that were drawn, in parts order."""
    width = 0.8
    x = 0.0
    xs, labels, colors, centers = [], [], [], []
    drawn = set()
    ymax = 0.0
    for g in groups:
        start = x
        for s in slots:
            r = get(g, s)
            if r is None:
                continue
            vals = [max(fn(r), 0.0) for fn, _, _ in parts]
            tot = sum(vals)
            if share and tot:
                vals = [100 * v / tot for v in vals]
            bottom = 0.0
            for (fn, label, col), v in zip(parts, vals):
                if v:
                    ax.bar(x, v, width, bottom=bottom, color=col, edgecolor="white", linewidth=0.3)
                    drawn.add(label)
                bottom += v
            ymax = max(ymax, bottom)
            if not tot:
                ax.text(x, 0, "0", ha="center", va="bottom", fontsize=7, color="#777777")
            xs.append(x); labels.append(short_config(s)); colors.append(slot_color(s))
            x += 1.0
        if x > start:
            centers.append(((start + x - 1.0) / 2, g))
            x += gap
    ax.set_xticks(xs, labels, rotation=90, fontsize=6.5)
    for t, c in zip(ax.get_xticklabels(), colors):
        t.set_color(c)
    for cx, g in centers:
        ax.text(cx, -0.30, group_label(g) if group_label else g, transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=8.5, fontweight="bold")
    ax.set_xlim(-0.8, x - gap + 0.2)
    return [label for _, label, _ in parts if label in drawn]


def legend_for(ax, parts, labels, **kw):
    from matplotlib.patches import Patch
    col = {label: c for _, label, c in parts}
    ax.legend(handles=[Patch(color=col[l], label=l) for l in labels], frameon=False, **kw)


def make_plots(runs, segs, tools, plot_dir):
    plt = _plt()
    import zlib as _z
    levels_cmp = comparison_levels(runs)
    cmp_runs = [r for r in runs if r["level"] in levels_cmp]
    cmp_keys = {(r["config"], r["prompt_id"]) for r in cmp_runs}
    cmp_segs = [s for s in segs if (s["config"], s["prompt_id"]) in cmp_keys]
    cmp_tools = [t for t in tools if (t["config"], t["prompt_id"]) in cmp_keys]
    scope = "+".join(levels_cmp) + " prompts"
    configs = config_order({r["config"] for r in runs})
    palette = ["#1f5f99", "#7fb3e0", "#b3541e", "#f0a868", "#4d8a3c", "#a7d49b", "#7b4fa0", "#c9a9e3"]
    color = {c: palette[i % len(palette)] for i, c in enumerate(configs)}
    P = PlotSet(plot_dir)
    runs_all = runs
    runs = cmp_runs
    prompts = sorted({r["prompt_id"] for r in runs}, key=pkey)
    by = {(r["prompt_id"], r["config"]): r for r in runs}

    # 1 wall time by prompt
    fig, ax = plt.subplots(figsize=(max(8, len(prompts) * 0.9), 4.2))
    w = 0.8 / len(configs)
    for i, c in enumerate(configs):
        xs = [k + (i - (len(configs) - 1) / 2) * w for k, p in enumerate(prompts) if (p, c) in by]
        ys = [by[(p, c)]["wall_s"] / 60 for p in prompts if (p, c) in by]
        ax.bar(xs, ys, w, label=c, color=color[c])
    ax.set_xticks(range(len(prompts)), prompts, rotation=45, ha="right")
    ax.set_ylabel("wall time (min)")
    ax.set_title(f"Wall time per prompt, {scope} (prompt sent → last saved step)")
    ax.legend(frameon=False, ncol=len(configs))
    P.save(fig, "01_wall_time_by_prompt.png", f"Wall time per prompt and configuration ({scope})")

    # 2 time breakdown per run
    order = sorted(runs, key=lambda r: (pkey(r["prompt_id"]), configs.index(r["config"])))
    fig, ax = plt.subplots(figsize=(9, max(4, len(order) * 0.19)))
    y = list(range(len(order)))[::-1]
    left = [0.0] * len(order)
    for key, label, col in TIME_PARTS:
        vals = [r[key] / 60 for r in order]
        ax.barh(y, vals, left=left, color=col, label=label, height=0.75)
        left = [a + b for a, b in zip(left, vals)]
    ax.set_yticks(y, [f"{r['prompt_id']}  {r['config']}" for r in order], fontsize=7)
    for tick, r in zip(ax.get_yticklabels(), order):
        tick.set_color(color[r["config"]])
    ax.set_xlabel("minutes")
    ax.set_title(f"Where each run's wall time went ({scope})")
    ax.legend(frameon=False, loc="lower right")
    P.save(fig, "02_time_breakdown.png", f"Time breakdown per run ({scope})")

    # 3 distributions by config
    metrics = [("wall_s", "wall time (min)", 1 / 60), ("thinking_s", "thinking (min)", 1 / 60), ("tool_s", "time in tools (min)", 1 / 60),
               ("tool_calls", "tool calls", 1), ("segments", "response segments", 1), ("final_answer_words", "final answer (words)", 1)]

    def distributions(subset, groups, key_of, col_of, name, title, save_to=P):
        fig, axes = plt.subplots(2, 3, figsize=(11, 6.5))
        for ax, (key, label, k) in zip(axes.flat, metrics):
            data = [[r[key] * k for r in subset if key_of(r) == g] for g in groups]
            ax.boxplot(data, widths=0.5, showfliers=False)
            for i, (g, d) in enumerate(zip(groups, data), 1):
                ax.scatter([i + ((j % 7) - 3) * 0.04 for j in range(len(d))], d, s=14, color=col_of(g), alpha=0.85, zorder=3)
            ax.set_xticks(range(1, len(groups) + 1), [f"{g}\n(n={len(d)})" for g, d in zip(groups, data)], fontsize=8)
            ax.set_title(label)
        fig.suptitle(title)
        save_to.save(fig, name, title)

    distributions(runs, configs, lambda r: r["config"], color.get, "03_distributions_by_config.png", f"Per-run distributions by configuration, {scope}")
    common = [p for p in prompts if all((p, c) in by for c in configs)]
    if common and len(common) < len(prompts):
        distributions([r for r in runs if r["prompt_id"] in common], configs, lambda r: r["config"], color.get, "03b_distributions_common_prompts.png",
                      f"Per-run distributions on the {len(common)} prompts every configuration ran ({', '.join(common)})")

    # 4 turns
    segs_c = cmp_segs
    marker = {"prompt": "o", "auto continue": "^", "typed continue": "s"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [3, 2]})
    ax = axes[0]
    for i, c in enumerate(configs, 1):
        for s in [s for s in segs_c if s["config"] == c]:
            j = (_z.crc32((s["prompt_id"] + str(s["segment"])).encode()) % 9 - 4) * 0.05
            ax.scatter(i + j, s["duration_s"] / 60, marker=marker.get(s["trigger"], "o"), color=color[c], s=26, alpha=0.85)
    ax.set_xticks(range(1, len(configs) + 1), configs, rotation=15)
    ax.set_ylabel("segment duration (min)")
    ax.set_title(f"Response segments (turns), {scope}: each point is one segment")
    ax.legend(handles=[plt.Line2D([], [], marker=m, ls="", color="k", label=t) for t, m in marker.items()], frameon=False)
    ax = axes[1]
    cats = ["auto continue", "typed continue"]
    w2 = 0.35
    for k, cat in enumerate(cats):
        vals = [sum(1 for s in segs_c if s["config"] == c and s["trigger"] == cat) for c in configs]
        ax.bar([i + (k - 0.5) * w2 for i in range(len(configs))], vals, w2, label=cat, color=["#9ecae1", "#3182bd"][k])
    top = max([sum(1 for s in segs_c if s["config"] == c and s["trigger"] == cat) for c in configs for cat in cats] + [1])
    for i, c in enumerate(configs):
        wv = [s["user_wait_s"] for s in segs_c if s["config"] == c and s["trigger"] == "typed continue"]
        if wv:
            ax.text(i + 0.5 * w2, len(wv) + top * 0.03, f"median wait\nbefore typing\n{statistics.median(wv) / 60:.1f} min", ha="center", va="bottom", fontsize=7)
    ax.set_ylim(0, top * 1.35)
    ax.set_xticks(range(len(configs)), configs, rotation=15)
    ax.set_ylabel("count")
    ax.set_title("Continuations after hitting the output limit")
    ax.legend(frameon=False)
    P.save(fig, "04_turns_and_continues.png", f"Turn (segment) durations and Continue counts ({scope})")

    # 5 tool mix
    fig, ax = plt.subplots(figsize=(8, 4))
    bottoms = [0.0] * len(configs)
    tool_names = [t for t in TOOL_COLS if any(r["tools"].get(t) for r in runs)]
    for t in tool_names:
        vals = [statistics.mean([r["tools"].get(t, 0) for r in runs if r["config"] == c]) for c in configs]
        ax.bar(configs, vals, bottom=bottoms, label=t, color=TOOL_COLORS.get(t, "#cccccc"))
        bottoms = [a + b for a, b in zip(bottoms, vals)]
    ax.set_ylabel("mean tool calls per run")
    ax.set_title(f"Tool mix by configuration ({scope})")
    ax.legend(frameon=False, fontsize=7, bbox_to_anchor=(1.01, 1), loc="upper left")
    P.save(fig, "05_tool_mix.png", f"Mean tool calls per run by tool ({scope})")

    # 6 tool call durations
    names = [t for t in TOOL_COLS if any(x["tool"] == t for x in cmp_tools)]
    fig, ax = plt.subplots(figsize=(9, 4))
    data = [[max(x["duration_s"], 0.01) for x in cmp_tools if x["tool"] == t] for t in names]
    ax.boxplot(data, widths=0.5, showfliers=True, flierprops={"markersize": 3})
    ax.set_yscale("log")
    ax.set_xticks(range(1, len(names) + 1), [f"{t} (n={len(d)})" for t, d in zip(names, data)], fontsize=7, rotation=30, ha="right")
    ax.set_ylabel("seconds (tool call → result)")
    ax.set_title(f"Tool call durations, {scope}, all configurations")
    P.save(fig, "06_tool_call_durations.png", f"Tool call durations by tool ({scope})")

    # 7 wall vs tool calls
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for c in configs:
        rr = [r for r in runs if r["config"] == c]
        ax.scatter([r["tool_calls"] for r in rr], [r["wall_s"] / 60 for r in rr], s=[18 + 14 * r["segments"] for r in rr], color=color[c], alpha=0.75, label=c)
    ax.set_xlabel("tool calls")
    ax.set_ylabel("wall time (min)")
    ax.set_title(f"Wall time vs tool calls, {scope} (marker size = segments)")
    ax.legend(frameon=False)
    P.save(fig, "07_wall_vs_tool_calls.png", f"Wall time vs tool calls ({scope})")

    # 8 shared prompts
    shared = [p for p in prompts if sum((p, c) in by for c in configs) > 1]
    if shared:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        for ax, (key, label) in zip(axes, [("wall_s", "wall time (min)"), ("thinking_s", "thinking (min)")]):
            for c in configs:
                ys = [by[(p, c)][key] / 60 if (p, c) in by else float("nan") for p in shared]
                ax.plot(range(len(shared)), ys, marker="o", color=color[c], label=c, lw=1.2)
            ax.set_xticks(range(len(shared)), shared, rotation=45)
            ax.set_ylabel(label)
            ax.set_title(f"{label.split(' (')[0].capitalize()}, prompts run in 2+ configurations (gap = not run)")
        axes[0].legend(frameon=False)
        P.save(fig, "08_shared_prompts.png", "Prompts run in more than one configuration")

    # 9 tool calls by category
    cat_names = [c for c, _ in CATEGORIES] + ["other"]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2))
    for ax, share in zip(axes, (False, True)):
        bottoms = [0.0] * len(configs)
        for cat in cat_names:
            key = "calls_" + CAT_KEYS[cat]
            vals = []
            for c in configs:
                rr = [r for r in runs if r["config"] == c]
                tot = sum(r["tool_calls"] for r in rr)
                n = sum(r[key] for r in rr)
                vals.append(100 * n / tot if share and tot else (n / len(rr) if rr else 0))
            if not any(vals):
                continue
            ax.bar(configs, vals, bottom=bottoms, color=CAT_COLORS[cat], label=cat)
            if share:
                for i, v in enumerate(vals):
                    if v >= 6:
                        ax.text(i, bottoms[i] + v / 2, f"{v:.0f}%", ha="center", va="center", fontsize=7, color="white")
            bottoms = [a + b for a, b in zip(bottoms, vals)]
        ax.set_ylabel("share of all tool calls (%)" if share else "mean tool calls per run")
        ax.set_title(("Tool call mix by category" if share else "Tool calls per run by category") + f" ({scope})")
        ax.tick_params(axis="x", rotation=15)
    axes[1].legend(frameon=False, fontsize=7, bbox_to_anchor=(1.01, 1), loc="upper left")
    P.save(fig, "09_tool_categories.png", f"Tool calls by category ({scope})")

    # 10 code and web
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, (key, label) in zip(axes, [("final_code_lines", "final code lines (visible scripts)"), ("code_lines_written", "code lines written incl. rewrites and edits"),
                                       ("pages_reached", "web pages reached (search results + fetched)")]):
        data = [[r[key] for r in runs if r["config"] == c] for c in configs]
        ax.boxplot(data, widths=0.5, showfliers=False)
        for i, (c, d) in enumerate(zip(configs, data), 1):
            ax.scatter([i + ((j % 7) - 3) * 0.04 for j in range(len(d))], d, s=14, color=color[c], alpha=0.85, zorder=3)
        ax.set_xticks(range(1, len(configs) + 1), configs, rotation=15, fontsize=8)
        ax.set_title(label, fontsize=9)
    fig.suptitle(scope)
    P.save(fig, "10_code_and_web.png", f"Code written in the visible session and web pages reached, per run ({scope})")

    # 11-13 segmented bars grouped by configuration within each prompt
    get = lambda p, c: by.get((p, c))
    tool_names = [t for t in TOOL_COLS if any(r["tools"].get(t) for r in runs)]
    tool_parts = [((lambda r, t=t: r["tools"].get(t, 0)), t, TOOL_COLORS.get(t, "#cccccc")) for t in tool_names]
    cat_parts = [((lambda r, k=CAT_KEYS[cat]: r["calls_" + k]), cat, CAT_COLORS[cat]) for cat in cat_names if any(r["calls_" + CAT_KEYS[cat]] for r in runs)]
    time_parts = [((lambda r, k=k: r[k] / 60), label, col) for k, label, col in TIME_PARTS]
    width = max(10, len(prompts) * len(configs) * 0.3 + 2)
    for name, parts, ylabel, title, share_panel in [
            ("11_tool_types_by_prompt.png", tool_parts, "tool calls", f"Tool calls by type, per prompt and configuration ({scope})", True),
            ("12_tool_categories_by_prompt.png", cat_parts, "tool calls", f"Tool calls by category, per prompt and configuration ({scope})", True),
            ("13_time_breakdown_by_prompt.png", time_parts, "minutes", f"Where the wall time went, per prompt and configuration ({scope})", True)]:
        fig, axes = plt.subplots(2 if share_panel else 1, 1, figsize=(width, 8.4 if share_panel else 4.6))
        axes = list(axes) if share_panel else [axes]
        shown_labels = []
        for ax, share in zip(axes, [False, True][:len(axes)]):
            shown_labels = grouped_segmented(ax, prompts, configs, get, parts, color.get, share=share)
            ax.set_ylabel(("share of " + (ylabel if ylabel != "minutes" else "wall time") + " (%)") if share else ylabel)
        axes[0].set_title(title)
        legend_for(axes[0], parts, shown_labels, fontsize=7, bbox_to_anchor=(1.005, 1), loc="upper left")
        fig.tight_layout(h_pad=3.2)
        P.save(fig, name, title)

    level_sets = level_plots(runs_all, segs, tools, plot_dir, levels_cmp, color)
    return P.files, level_sets


def level_plots(runs, segs, tools, plot_dir, levels_cmp, config_color):
    """For configurations that also ran prompt levels no other configuration ran: plots across all their levels."""
    plt = _plt()
    out = []
    for c in config_order({r["config"] for r in runs}):
        rr = [r for r in runs if r["config"] == c]
        levels = sorted({r["level"] for r in rr}, key=lambda lv: int(lv[1:]) if lv[1:].isdigit() else 99)
        if len(levels) < 2 or set(levels) <= set(levels_cmp):
            continue
        sub = f"{c}_by_level"
        P = PlotSet(plot_dir / sub, rel=sub + "/")
        lvl_cols = dict(zip(levels, ["#08519c", "#3182bd", "#6baed6", "#9ecae1", "#c6dbef"]))
        prompts = sorted({r["prompt_id"] for r in rr}, key=pkey)
        byp = {r["prompt_id"]: r for r in rr}
        lv_prompts = {lv: [p for p in prompts if p.startswith(lv + "_")] for lv in levels}

        # 1 wall and thinking time per prompt
        fig, axes = plt.subplots(2, 1, figsize=(max(9, len(prompts) * 0.35), 6.5))
        for ax, (key, label) in zip(axes, [("wall_s", "wall time (min)"), ("tool_calls", "tool calls")]):
            ax.bar(range(len(prompts)), [byp[p][key] / (60 if key.endswith("_s") else 1) for p in prompts], color=[lvl_cols[byp[p]["level"]] for p in prompts])
            ax.set_xticks(range(len(prompts)), prompts, rotation=60, ha="right", fontsize=7.5)
            ax.set_ylabel(label)
        axes[0].set_title(f"{c}: every prompt, colored by level")
        axes[0].legend(handles=[plt.Rectangle((0, 0), 1, 1, color=lvl_cols[lv], label=f"{lv} ({len(lv_prompts[lv])} prompts)") for lv in levels], frameon=False)
        P.save(fig, "01_wall_time_and_tool_calls_by_prompt.png", f"{c}: wall time and tool calls per prompt")

        # 2 distributions by level
        metrics = [("wall_s", "wall time (min)", 1 / 60), ("thinking_s", "thinking (min)", 1 / 60), ("tool_s", "time in tools (min)", 1 / 60),
                   ("tool_calls", "tool calls", 1), ("final_code_lines", "final code lines", 1), ("final_answer_words", "final answer (words)", 1)]
        fig, axes = plt.subplots(2, 3, figsize=(11, 6.5))
        for ax, (key, label, k) in zip(axes.flat, metrics):
            data = [[r[key] * k for r in rr if r["level"] == lv] for lv in levels]
            ax.boxplot(data, widths=0.5, showfliers=False)
            for i, (lv, d) in enumerate(zip(levels, data), 1):
                ax.scatter([i + ((j % 7) - 3) * 0.04 for j in range(len(d))], d, s=16, color=lvl_cols[lv], alpha=0.9, zorder=3)
            ax.set_xticks(range(1, len(levels) + 1), [f"{lv}\n(n={len(d)})" for lv, d in zip(levels, data)], fontsize=8)
            ax.set_title(label)
        fig.suptitle(f"{c}: per-run distributions by prompt level")
        P.save(fig, "02_distributions_by_level.png", f"{c}: distributions by prompt level")

        # 3-5 segmented bars per prompt grouped by level
        get = lambda lv, p: byp.get(p)
        tool_names = [t for t in TOOL_COLS if any(r["tools"].get(t) for r in rr)]
        cat_names = [cat for cat, _ in CATEGORIES] + ["other"]
        specs = [("03_tool_types_by_prompt.png", [((lambda r, t=t: r["tools"].get(t, 0)), t, TOOL_COLORS.get(t, "#cccccc")) for t in tool_names], "tool calls", "Tool calls by type"),
                 ("04_tool_categories_by_prompt.png", [((lambda r, k=CAT_KEYS[cat]: r["calls_" + k]), cat, CAT_COLORS[cat]) for cat in cat_names if any(r["calls_" + CAT_KEYS[cat]] for r in rr)], "tool calls", "Tool calls by category"),
                 ("05_time_breakdown_by_prompt.png", [((lambda r, k=k: r[k] / 60), label, col) for k, label, col in TIME_PARTS], "minutes", "Where the wall time went")]
        for name, parts, ylabel, title in specs:
            fig, axes = plt.subplots(2, 1, figsize=(max(10, len(prompts) * 0.38 + 2), 7.5))
            for ax, share in zip(axes, (False, True)):
                # one bar per prompt, prompts grouped by level with a gap between levels
                x = 0.0
                ticks, labels = [], []
                drawn = set()
                for lv in levels:
                    start = x
                    for p in lv_prompts[lv]:
                        r = byp[p]
                        vals = [max(fn(r), 0.0) for fn, _, _ in parts]
                        tot = sum(vals)
                        if share and tot:
                            vals = [100 * v / tot for v in vals]
                        bottom = 0.0
                        for (fn, label, col), v in zip(parts, vals):
                            if v:
                                ax.bar(x, v, 0.8, bottom=bottom, color=col, edgecolor="white", linewidth=0.3)
                                drawn.add(label)
                            bottom += v
                        if not tot:
                            ax.text(x, 0, "0", ha="center", va="bottom", fontsize=7, color="#777777")
                        ticks.append(x); labels.append(p)
                        x += 1
                    ax.text((start + x - 1) / 2, 1.0, lv, transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=9, fontweight="bold", color=lvl_cols[lv])
                    x += 0.8
                ax.set_xticks(ticks, labels, rotation=60, ha="right", fontsize=7)
                ax.set_xlim(-0.8, x - 0.6)
                ax.set_ylabel(("share of " + (ylabel if ylabel != "minutes" else "wall time") + " (%)") if share else ylabel)
            axes[0].set_title(f"{c}: {title.lower()}, per prompt grouped by level", pad=16)
            legend_for(axes[0], parts, [l for _, l, _ in parts if l in drawn], fontsize=7, bbox_to_anchor=(1.005, 1), loc="upper left")
            fig.tight_layout(h_pad=2.5)
            P.save(fig, name, f"{c}: {title.lower()} per prompt, grouped by level")

        # 6 means by level: category mix and time split
        fig, axes = plt.subplots(1, 3, figsize=(12, 4.8))
        tick = [f"{lv}\n{len(lv_prompts[lv])} prompts\n{sum(r['tool_calls'] for r in rr if r['level'] == lv)} calls" for lv in levels]
        cat_names_present = [cat for cat in cat_names if any(r["calls_" + CAT_KEYS[cat]] for r in rr)]
        for ax, share in zip(axes[:2], (False, True)):
            bottoms = [0.0] * len(levels)
            for cat in cat_names_present:
                vals = []
                for lv in levels:
                    lr = [r for r in rr if r["level"] == lv]
                    tot = sum(r["tool_calls"] for r in lr)
                    n = sum(r["calls_" + CAT_KEYS[cat]] for r in lr)
                    vals.append(100 * n / tot if share and tot else n / len(lr))
                ax.bar(range(len(levels)), vals, bottom=bottoms, color=CAT_COLORS[cat], label=cat)
                bottoms = [a + b for a, b in zip(bottoms, vals)]
            ax.set_xticks(range(len(levels)), tick, fontsize=7.5)
            ax.set_ylabel("share of tool calls (%)" if share else "mean tool calls per run")
            ax.set_title("Tool call mix" if share else "Tool calls per run")
        axes[0].legend(frameon=False, fontsize=7, loc="upper right")
        ax = axes[2]
        bottoms = [0.0] * len(levels)
        for key, label, col in TIME_PARTS:
            vals = [statistics.mean([r[key] / 60 for r in rr if r["level"] == lv]) for lv in levels]
            ax.bar(range(len(levels)), vals, bottom=bottoms, color=col, label=label)
            bottoms = [a + b for a, b in zip(bottoms, vals)]
        ax.set_xticks(range(len(levels)), [f"{lv}\n{len(lv_prompts[lv])} prompts" for lv in levels], fontsize=7.5)
        ax.set_ylabel("mean minutes per run")
        ax.set_title("Time per run")
        ax.legend(frameon=False, fontsize=7, loc="upper right")
        fig.suptitle(f"{c}: averages by prompt level")
        P.save(fig, "06_level_means.png", f"{c}: mean tool mix and time split by level")
        out.append((c, levels, P.files))
    return out


# ------------------------------------------------------------------ summary
def med(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else 0


def mmss(sec):
    sec = int(round(sec))
    return f"{sec // 60}m {sec % 60:02d}s"


def summary_md(runs, segs, tools, plots, level_sets, exports):
    configs = config_order({r["config"] for r in runs})
    levels_cmp = comparison_levels(runs)
    scope = "+".join(levels_cmp) + " prompts"
    all_runs = runs
    cmp = [r for r in runs if r["level"] in levels_cmp]
    L = ["# Run statistics", "",
         f"Built {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from {', '.join('`' + e + '`' for e in exports)}: {len(runs)} runs, "
         f"{len(segs)} response segments, {len(tools)} tool calls. Timings come from claude.ai's saved block timestamps and cover the branch claude.ai shows.", "",
         f"Comparisons across configurations use only the prompt levels more than one configuration ran ({', '.join(levels_cmp)}). "
         + "; ".join(f"{c} also ran {', '.join(lv for lv in lvs if lv not in levels_cmp)}, summarized in its own section and plot folder" for c, lvs, _ in level_sets)
         + ("." if level_sets else "")]

    def config_table(subset, heading):
        L.extend(["", heading, "",
                  "| Config | Runs | Wall | Active | Thinking | Tools | Tool calls | Segments | Typed / auto continues (total) | Incomplete | Alternate branches | Answer words |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"])
        for c in configs:
            rr = [r for r in subset if r["config"] == c]
            if rr:
                L.append(config_row(c, rr))

    def config_row(c, rr):
        return (f"| {c} | {len(rr)} | {mmss(med([r['wall_s'] for r in rr]))} | {mmss(med([r['active_s'] for r in rr]))} | {mmss(med([r['thinking_s'] for r in rr]))} | "
                 f"{mmss(med([r['tool_s'] for r in rr]))} | {med([r['tool_calls'] for r in rr]):g} | {med([r['segments'] for r in rr]):g} | "
                 f"{sum(r['typed_continues'] for r in rr)} / {sum(r['auto_continues'] for r in rr)} | {sum(r['incomplete'] for r in rr)} | "
                 f"{sum(1 for r in rr if r['alternate_messages'])} | {med([r['final_answer_words'] for r in rr]):g} |")

    config_table(cmp, f"## By configuration, {scope} (medians unless noted)")
    pids = {}
    for r in cmp:
        pids.setdefault(r["prompt_id"], set()).add(r["config"])
    common = sorted((p for p, cs in pids.items() if cs == set(configs)), key=lambda p: [int(x) for x in re.findall(r"\d+", p)])
    if common and len(common) < len(pids):
        config_table([r for r in cmp if r["prompt_id"] in common],
                     f"## By configuration, only the {len(common)} prompts every configuration ran ({', '.join(common)})")
    for c, lvs, _ in level_sets:
        L += ["", f"## {c} by prompt level (medians unless noted)", "",
              "| Level | Runs | Wall | Thinking | Tools | Tool calls | Literature / build / commands / inspect / present (share of calls) | Final code lines | Pages reached (total) | Answer words |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for lv in lvs:
            rr = [r for r in all_runs if r["config"] == c and r["level"] == lv]
            tot = sum(r["tool_calls"] for r in rr) or 1
            shares = " / ".join(f"{100 * sum(r['calls_' + k] for r in rr) / tot:.0f}%" for k in ("lit", "build", "cmd", "inspect", "present"))
            L.append(f"| {lv} | {len(rr)} | {mmss(med([r['wall_s'] for r in rr]))} | {mmss(med([r['thinking_s'] for r in rr]))} | {mmss(med([r['tool_s'] for r in rr]))} | "
                     f"{med([r['tool_calls'] for r in rr]):g} | {shares} | {med([r['final_code_lines'] for r in rr]):g} | {sum(r['pages_reached'] for r in rr)} | "
                     f"{med([r['final_answer_words'] for r in rr]):g} |")
    runs = cmp
    L += ["", "## Longest runs (all prompts)", "", "| Run | Wall | Thinking | Tools | Tool calls | Segments | Stop reasons |", "|---|---|---|---|---|---|---|"]
    for r in sorted(all_runs, key=lambda r: -r["wall_s"])[:8]:
        L.append(f"| {r['prompt_id']} {r['config']} | {mmss(r['wall_s'])} | {mmss(r['thinking_s'])} | {mmss(r['tool_s'])} | {r['tool_calls']} | {r['segments']} | {', '.join(str(x) for x in r['stop_reasons'])} |")
    tn = Counter(x["tool"] for x in tools)
    L += ["", "## Tool calls (all runs)", "", "| Tool | Calls | Median duration | Errors | Share of tool time |", "|---|---|---|---|---|"]
    tot = sum(x["duration_s"] for x in tools) or 1
    for t, n in tn.most_common():
        xs = [x for x in tools if x["tool"] == t]
        L.append(f"| {t} | {n} | {med([x['duration_s'] for x in xs]):.1f} s | {sum(1 for x in xs if x['is_error'])} | {100 * sum(x['duration_s'] for x in xs) / tot:.0f}% |")
    L += ["", f"## Tool calls by category, {scope} (totals; share of that configuration's tool calls)", "",
          "Categories: literature search = `web_search`, `web_fetch`; build/edit scripts = `create_file`, `str_replace`; commands = `bash_tool`; "
          "inspect = `view`; present = `present_files`, `chart_display_v0`, `visualize:*`, `Artifact`.", "",
          "| Config | Tool calls | Per run (mean) | Literature search | Build/edit scripts | Commands | Inspect files/images | Present results |",
          "|---|---|---|---|---|---|---|---|"]
    for c in configs:
        rr = [r for r in runs if r["config"] == c]
        tot = sum(r["tool_calls"] for r in rr)
        cells = []
        for cat, _ in CATEGORIES:
            n = sum(r["calls_" + CAT_KEYS[cat]] for r in rr)
            cells.append(f"{n} ({100 * n / tot:.0f}%)" if tot else "0")
        L.append(f"| {c} | {tot} | {tot / len(rr):.1f} | " + " | ".join(cells) + " |")
    L += ["", f"## Web research, {scope}", "",
          "| Config | Runs that searched | Searches | Search result URLs (distinct per run, summed) | Pages fetched | Fetches failed | Pages reached | Domains (median per searching run) |",
          "|---|---|---|---|---|---|---|---|"]
    for c in configs:
        rr = [r for r in runs if r["config"] == c]
        srch = [r for r in rr if r["web_searches"] or r["pages_fetched"] or r["fetch_failed"]]
        L.append(f"| {c} | {len(srch)} of {len(rr)} | {sum(r['web_searches'] for r in rr)} | {sum(r['search_result_urls'] for r in rr)} | "
                 f"{sum(r['pages_fetched'] for r in rr)} | {sum(r['fetch_failed'] for r in rr)} | {sum(r['pages_reached'] for r in rr)} | "
                 f"{med([r['web_domains'] for r in srch]):g} |")
    L += ["", f"## Code written in the visible session, {scope}", "",
          "Rebuilt from the conversation: each script's final text is its last `create_file` or `cat > file << EOF` write with later `str_replace` edits applied. "
          "Edits made by other commands (for example `sed -i`) aren't visible, so a few final lengths are approximate; `code_files.csv` lists every file.", "",
          "| Config | Scripts written | Final code lines (total) | Final code lines per run (median) | Lines written incl. rewrites | str_replace edits | Inline script lines | Command lines | HTML files |",
          "|---|---|---|---|---|---|---|---|---|"]
    for c in configs:
        rr = [r for r in runs if r["config"] == c]
        L.append(f"| {c} | {sum(r['scripts_written'] for r in rr)} | {sum(r['final_code_lines'] for r in rr)} | {med([r['final_code_lines'] for r in rr]):g} | "
                 f"{sum(r['code_lines_written'] for r in rr)} | {sum(r['str_replace_applied'] + r['str_replace_untracked'] for r in rr)} | "
                 f"{sum(r['inline_script_lines'] for r in rr)} | {sum(r['command_lines'] for r in rr)} | {sum(r['html_files_written'] for r in rr)} |")
    L += ["", f"## Plots comparing configurations ({scope})", ""]
    for fn, title in plots:
        L += [f"### {title}", "", f"![{title}](plots/{fn})", ""]
    for c, lvs, files in level_sets:
        L += [f"## Plots for {c} across prompt levels ({', '.join(lvs)})", ""]
        for fn, title in files:
            L += [f"### {title}", "", f"![{title}](plots/{fn})", ""]
    L += ["## Definitions", "",
          "- **wall_s**: prompt sent → last saved step of the shown branch. Includes any wait before a typed \"Continue\". Matches the exports' `runs.csv`.",
          "- **active_s**: sum of response segment durations (first block start → last block stop in each assistant message).",
          "- **waiting_s**: wall_s − active_s: time between segments (a typed Continue waits for you; an automatic one only for the server).",
          "- **thinking_s / text_s**: summed thinking and text block durations. **tool_s**: summed tool call → tool result time.",
          "- **other_s**: active_s − thinking − text − tools (gaps between blocks inside a segment).",
          "- **segment trigger**: `prompt`, `auto continue` (claude.ai continued after the output limit) or `typed continue` (a \"Continue\" message). "
          "**user_wait_s**: previous segment end → the typed Continue.",
          "- **alternate_messages / alternate_active_s**: messages and active time on branches claude.ai doesn't show (they ran in parallel in the same sandbox and aren't in the timings).",
          "- **final_answer_words**: words of text after the last working tool call (charts, images and file cards excluded).",
          "- **calls_* / frac_***: tool calls per category (lit, build, cmd, inspect, present, other) and their share of the run's tool calls. "
          "**n_<tool> / tool_s_<tool> / errors_<tool>**: calls, seconds and error results per tool. **time_<category>_s**: tool seconds per category.",
          "- **thinking_share / text_share / tool_share / waiting_share**: those times divided by wall_s. **mean_segment_s / max_segment_s**: response segment lengths. "
          "**user_wait_total_s**: summed waits before typed Continues. **median_tool_call_s**: median tool call duration.",
          "- **in_comparison**: the run's prompt level was run by more than one configuration, so it's included in the cross-configuration tables and plots.",
          "- **search_result_urls**: distinct URLs returned by the run's web searches. **pages_fetched**: distinct URLs fetched successfully. "
          "**pages_reached**: the union of the two. **web_domains**: distinct domains among them.",
          "- **final_code_lines / final_code_chars**: summed final size of the code files (.py, .js, .sh, …) the run wrote, as visible in the conversation. "
          "**code_lines_written**: every line written to code files, counting rewrites and `str_replace` new text. **inline_script_lines**: `python - << EOF` and `python -c` code run without saving a file. "
          "**command_lines**: lines of all `bash_tool` commands, heredocs included.", "",
          "## CSV files", "",
          "| File | One row per | Use it for |", "|---|---|---|",
          "| `runs.csv` | run | everything above plus prompt metadata (`prompt_id`, `level`, `prompt_number`, `prompt_title`, `prompt_text`, chat link) |",
          "| `prompts.csv` | prompt | prompt metadata and each configuration's key metrics side by side, as `<config>__<metric>` columns |",
          "| `metrics_long.csv` | run × numeric metric | pivoting and plotting any metric by config, level or prompt |",
          "| `tool_calls_by_prompt.csv` | run × tool | tool mix per prompt: calls, seconds, errors, share of the run's calls |",
          "| `segments.csv` | response segment | turn-level durations, triggers and waits |",
          "| `tools.csv` | tool call | per-call durations, errors, exit codes and sizes |",
          "| `code_files.csv` | file written | final length of each visibly written script |", ""]
    return "\n".join(L)


# ------------------------------------------------------------------ main build
def build(exports, renderings, out):
    with ExitStack() as stack:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        rend = stack.enter_context(RenderingsSource(renderings))
        runs, segs, tools, code_files = [], [], [], []
        for ep in exports:
            exp = stack.enter_context(Export(ep))
            run_rend = rend
            if exp.is_consolidated and not renderings:
                run_rend = stack.enter_context(RenderingsSource(ep))
            csv_extra = {}
            top = exp.read_top("original_export__runs.csv" if exp.is_consolidated else "runs.csv")
            if top:
                for r in csv.DictReader(io.StringIO(top.decode("utf-8-sig"))):
                    csv_extra[r.get("folder")] = r
            for run in exp.runs():
                conv = run.messages()
                shown = shown_branch(conv)
                st, seg_rows, tool_rows = run_stats(run, conv, shown)
                act, code_rows = activity_stats(shown)
                tm = dict(started=st["started"], finished=st["finished"], stop_reasons=st["stop_reasons"])
                fa = write_run_folder(run, conv, shown, run_rend, out / run.config / (run.prompt_id if exp.is_consolidated else run.prompt), tm)
                ex = csv_extra.get(run.rel, {})
                base = dict(export=run.group, config=run.config, model=conv.get("model"), effort=run.effort, run=run.run_name,
                            prompt_id=run.prompt_id, level=run.prompt_id.split("_")[0], prompt=run.prompt, chat_id=conv["uuid"])
                row = dict(base, **st, **fa, **act)
                for c in code_rows:
                    code_files.append(dict(base, **c))
                row.update(started_utc=st["started"].isoformat(), finished_utc=st["finished"].isoformat() if st["finished"] else "",
                           stop_reasons_str="|".join(str(s) for s in st["stop_reasons"]),
                           artifacts=ex.get("artifacts", ""), sandbox_files=ex.get("sandbox_files", ""),
                           parsed_folder=f"{run.config}/{run.prompt_id if exp.is_consolidated else run.prompt}")
                for t in TOOL_COLS:
                    row["n_" + t] = st["tools"].get(t, 0)
                for k in ("wall_s", "active_s", "waiting_s", "thinking_s", "text_s", "tool_s", "other_s", "alternate_active_s"):
                    row[k] = round(row[k], 1)
                add_run_details(row, seg_rows, tool_rows)
                runs.append(row)
                for s in seg_rows:
                    segs.append(dict(base, **s))
                for t in tool_rows:
                    tools.append(dict(base, **t))
                print(f"parsed {run.config}/{run.prompt}: images={fa['images']} html={fa['html_reports']}" + (f" missing={fa['answer_missing']}" if fa["answer_missing"] else ""))
        levels_cmp = comparison_levels(runs)
        for r in runs:
            r["in_comparison"] = r["level"] in levels_cmp
        sd = out / "_summary"
        if sd.exists():
            shutil.rmtree(sd)
        sd.mkdir(parents=True)
        base_f = ["export", "config", "model", "effort", "run", "level", "prompt_id", "prompt", "chat_id"]
        run_fields = (base_f + ["prompt_number", "prompt_title", "in_comparison", "chat_url", "started_ct", "prompt_words"] + ["started_utc", "finished_utc", "wall_s", "active_s", "waiting_s", "thinking_s", "text_s", "tool_s", "other_s",
                                                   "segments", "typed_continues", "auto_continues", "stop_reasons_str", "incomplete", "tool_calls"]
                  + ["n_" + t for t in TOOL_COLS] + ["tool_errors", "bash_nonzero_exit", "thinking_blocks", "thinking_summaries", "text_blocks",
                                                     "prompt_chars", "final_answer_words", "final_answer_chars", "images", "html_reports", "artifacts",
                                                     "sandbox_files", "alternate_messages", "alternate_active_s"]
                  + [f"calls_{k}" for k in CAT_KEYS.values()] + [f"frac_{k}" for k in CAT_KEYS.values()]
                  + ["web_searches", "search_result_urls", "pages_fetched", "fetch_failed", "pages_reached", "web_domains",
                     "scripts_written", "final_code_lines", "final_code_chars", "code_lines_written", "str_replace_applied", "str_replace_untracked",
                     "inline_script_lines", "command_lines", "html_files_written", "final_html_lines",
                     "thinking_share", "text_share", "tool_share", "waiting_share", "mean_segment_s", "max_segment_s", "user_wait_total_s", "median_tool_call_s"]
                  + [f"tool_s_{t}" for t in TOOL_COLS] + [f"errors_{t}" for t in TOOL_COLS] + [f"time_{k}_s" for k in CAT_KEYS.values()]
                  + ["parsed_folder", "prompt_text"])
        write_csv(sd / "runs.csv", runs, run_fields)
        write_prompt_tables(sd, runs, run_fields)
        write_csv(sd / "code_files.csv", code_files, base_f + ["path", "kind", "created_by", "writes", "edits", "final_lines", "final_chars"])
        write_csv(sd / "segments.csv", segs, base_f + ["segment", "trigger", "start_utc", "end_utc", "duration_s", "wait_before_s", "user_wait_s",
                                                       "thinking_s", "text_s", "tool_s", "tool_calls", "stop_reason", "message_uuid"])
        write_csv(sd / "tools.csv", tools, base_f + ["segment", "tool", "start_utc", "duration_s", "is_error", "exit_code", "input_chars", "output_chars", "description"])
        plots, level_sets = make_plots(runs, segs, tools, sd / "plots")
        (sd / "summary.md").write_text(summary_md(runs, segs, tools, plots, level_sets, [Path(e).name for e in exports]), encoding="utf-8")
        (out / "README.md").write_text(readme(runs), encoding="utf-8")
        print(f"parsed {len(runs)} runs into {out}; statistics in {sd}")
        return runs


NON_METRIC = {"export", "config", "model", "effort", "run", "level", "prompt_id", "prompt", "chat_id", "prompt_title", "chat_url", "started_ct",
              "started_utc", "finished_utc", "stop_reasons_str", "parsed_folder", "prompt_text", "prompt_number", "in_comparison"}
WIDE_METRICS = ["chat_id", "wall_s", "active_s", "waiting_s", "thinking_s", "text_s", "tool_s", "other_s", "segments", "typed_continues", "auto_continues",
                "incomplete", "stop_reasons_str", "tool_calls"] + [f"calls_{k}" for k in ("lit", "build", "cmd", "inspect", "present", "other")] + \
               ["n_" + t for t in TOOL_COLS] + ["tool_errors", "web_searches", "pages_fetched", "pages_reached", "web_domains", "scripts_written",
                "final_code_lines", "code_lines_written", "inline_script_lines", "command_lines", "final_answer_words", "images", "html_reports",
                "artifacts", "sandbox_files", "alternate_messages"]


def add_run_details(row, seg_rows, tool_rows):
    m = re.match(r"L(\d+)_(\d+)\s*(.*)", row["prompt"])
    row["prompt_number"] = int(m.group(2)) if m else ""
    row["prompt_title"] = m.group(3) if m else row["prompt"]
    row["prompt_words"] = len(row["prompt_text"].split())
    row["chat_url"] = f"https://claude.ai/chat/{row['chat_id']}"
    row["started_ct"] = ct_str(row["started"])
    wall = row["wall_s"] or 0
    for k in ("thinking", "text", "tool", "waiting"):
        row[f"{k}_share"] = round(row[f"{k}_s"] / wall, 3) if wall else 0
    durs = [s["duration_s"] for s in seg_rows]
    row["mean_segment_s"] = round(statistics.mean(durs), 1) if durs else 0
    row["max_segment_s"] = round(max(durs), 1) if durs else 0
    row["user_wait_total_s"] = round(sum(s["user_wait_s"] for s in seg_rows if s["user_wait_s"] != ""), 1)
    row["median_tool_call_s"] = round(statistics.median([t["duration_s"] for t in tool_rows]), 2) if tool_rows else 0
    for t in TOOL_COLS:
        row[f"tool_s_{t}"] = round(row["tool_time"].get(t, 0.0), 1)
        row[f"errors_{t}"] = sum(1 for x in tool_rows if x["tool"] == t and x["is_error"])
    for cat, key in CAT_KEYS.items():
        row[f"time_{key}_s"] = round(sum(v for t, v in row["tool_time"].items() if category(t) == cat), 1)


def write_prompt_tables(sd, runs, run_fields):
    """prompts.csv (one row per prompt, metrics per configuration side by side), metrics_long.csv (one row per run and metric),
    tool_calls_by_prompt.csv (one row per run and tool)."""
    configs = config_order({r["config"] for r in runs})
    by_prompt = defaultdict(dict)
    for r in runs:
        by_prompt[r["prompt_id"]][r["config"]] = r
    rows = []
    for pid in sorted(by_prompt, key=pkey):
        cs = by_prompt[pid]
        first = next(iter(cs.values()))
        row = dict(prompt_id=pid, level=first["level"], prompt_number=first["prompt_number"], prompt_title=first["prompt_title"],
                   prompt_chars=first["prompt_chars"], prompt_words=first["prompt_words"], in_comparison=first["in_comparison"],
                   n_configs=len(cs), configs="|".join(c for c in configs if c in cs), prompt_text=first["prompt_text"])
        for c in configs:
            for m in WIDE_METRICS:
                row[f"{c}__{m}"] = cs[c][m] if c in cs else ""
        rows.append(row)
    write_csv(sd / "prompts.csv", rows, ["prompt_id", "level", "prompt_number", "prompt_title", "prompt_chars", "prompt_words", "in_comparison",
                                         "n_configs", "configs"] + [f"{c}__{m}" for c in configs for m in WIDE_METRICS] + ["prompt_text"])
    ids = ["export", "config", "model", "effort", "level", "prompt_id", "prompt_number", "in_comparison"]
    metrics = [f for f in run_fields if f not in NON_METRIC]
    long_rows = [dict({k: r[k] for k in ids}, metric=m, value=(int(r[m]) if isinstance(r[m], bool) else r[m])) for r in runs for m in metrics]
    write_csv(sd / "metrics_long.csv", long_rows, ids + ["metric", "value"])
    tool_rows = []
    for r in runs:
        for t in TOOL_COLS:
            n = r["tools"].get(t, 0)
            if n:
                tool_rows.append(dict({k: r[k] for k in ids}, tool=t, category=category(t), calls=n, time_s=round(r["tool_time"].get(t, 0.0), 1),
                                      errors=r[f"errors_{t}"], share_of_run_calls=round(n / r["tool_calls"], 3) if r["tool_calls"] else 0))
    write_csv(sd / "tool_calls_by_prompt.csv", tool_rows, ids + ["tool", "category", "calls", "time_s", "errors", "share_of_run_calls"])


def readme(runs):
    configs = Counter(r["config"] for r in runs)
    L = ["# Parsed runs", "",
         "One folder per configuration (`<export>_<effort>`) and prompt, built by `renderers/parse_exports.py` from the export zips.", "",
         "| Configuration | Runs |", "|---|---|"] + [f"| {c} | {n} |" for c, n in sorted(configs.items())] + [
         "", "Each prompt folder has:",
         "- `conversation.json`: the run's `messages.json` from the export, unchanged (shown branch first, then any alternate continuation).",
         "- `final_answer.md`: Claude's final answer, taken from the branch claude.ai shows: everything after the last working tool call "
         "(text, charts, widgets, presented images and published pages, in order). Front matter holds the model, effort and times.",
         "- the images `final_answer.md` embeds: presented output images from the export, and chart/widget PNGs from Renderings.",
         "- HTML reports the run saved to its outputs, when there are any.", "",
         "`_summary/` holds the statistics:",
         "- `runs.csv`: one row per run, with prompt metadata, timings, Continues, tool calls by tool and category, web pages reached and code written.",
         "- `prompts.csv`: one row per prompt, with every configuration's metrics side by side.",
         "- `metrics_long.csv`: one row per run and metric, for plotting any way you like.",
         "- `tool_calls_by_prompt.csv`: one row per run and tool.",
         "- `segments.csv` (turns), `tools.csv` (tool calls) and `code_files.csv` (scripts written).",
         "- `summary.md`: tables, plots and definitions.",
         "- `plots/`: comparisons across configurations, using only prompt levels that more than one configuration ran.",
         "- `plots/<config>_by_level/`: the same views across every prompt of a configuration that also ran other levels.", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", action="append", required=True)
    ap.add_argument("--renderings")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    build(a.export, a.renderings, a.out)


if __name__ == "__main__":
    main()
