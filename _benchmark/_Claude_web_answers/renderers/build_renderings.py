"""Refresh images inside the two self-contained model archives.

    python build_renderings.py all [--root DIR] [--export MODEL.zip ...]

Reads Fable5_1.zip and Opus4_7.zip beside renderers/ by default. Consolidated
archives contain <configuration>/<prompt_id>/run.json, original conversations,
artifacts, final-answer snapshots, figures and view_images/ together.

The default command stages files in the OS temporary directory and atomically
updates each model ZIP. Existing originals and answer snapshots are retained;
differing new figures use rendered_ names and, if needed, a content-hash suffix.
All existing archive members retain their exact bytes. No separate Renderings.zip or parsed/ is published.

Explicit low-level operations retain their existing APIs:
    plan --export MODEL.zip --out WORK
    render WORK --assets MODEL.zip
    parse --export MODEL.zip --renderings MODEL.zip --out DESTINATION
    pack WORK --zip LEGACY_RENDERINGS.zip

See README.md for optional asset downloading and standalone renderer commands.
"""
import argparse, csv, hashlib, io, json, os, posixpath, re, shutil, sys, tempfile, zipfile
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from export_zip import Export, shown_branch

AUDIT_FIELDS = ["group", "chat", "run", "chat_id", "kind", "index", "title_or_path", "turn", "in_export", "export_file",
                "render_file", "status", "notes", "message_uuid", "time"]
DEFAULT_EXPORTS = ["Fable5_1.zip", "Opus4_7.zip"]


def safe(s, n=70):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s or "").strip().rstrip(".")
    return s[:n].rstrip() or "untitled"


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def parse_input(inp):
    if isinstance(inp, str):
        try:
            return json.loads(inp)
        except Exception:
            return {}
    return inp or {}


def result_items(c):
    cont = c.get("content")
    if isinstance(cont, str):
        try:
            cont = json.loads(cont)
        except Exception:
            cont = []
    return [x for x in (cont or []) if isinstance(x, dict)]


def find_exports(root, given):
    if given:
        return [Path(p) for p in given]
    root = Path(root)
    found = [root / n for n in DEFAULT_EXPORTS if (root / n).exists()]
    if found:
        return found
    out = []
    for z in sorted(root.glob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                if any(n.endswith("/messages.json") for n in zf.namelist()):
                    out.append(z)
        except zipfile.BadZipFile:
            pass
    return out


# ---------------------------------------------------------------- plan
def plan(args):
    out = Path(args.out)
    src_dir = out / "_plan" / "sources"
    src_dir.mkdir(parents=True, exist_ok=True)
    rows, jobs, fetch = [], [], {"view_images": [], "outputs": []}
    for ep in args.export:
        with Export(ep) as exp:
            for run in exp.runs():
                group = run.group
                conv = run.messages()
                cid = conv["uuid"]
                shown = {m["uuid"] for m in shown_branch(conv)}
                arts = {rel: n for rel, n in run.files("artifacts/").items() if not rel.startswith("artifacts/sandbox/")}
                by_base = {}
                for rel in arts:
                    by_base.setdefault(posixpath.basename(rel), rel)
                saved = {o["path"] for o in run.manifest().get("saved_outputs", [])}
                run_dir = run.render_prefix
                source_dir = run.prefix.rstrip("/") if exp.is_consolidated else run.rel
                counters = defaultdict(int)
                uses = {}
                for m in conv["chat_messages"]:  # export order: shown branch first, then alternate continuations
                    turn = "run" if m["uuid"] in shown else "alternate continuation"

                    def row(kind, title, **kw):
                        r = dict(group=group, chat=run.prompt, run=run.run_name, chat_id=cid, kind=kind, title_or_path=title, turn=turn,
                                 message_uuid=m["uuid"], time=m.get("created_at", ""))
                        r.update(kw)
                        rows.append(r)
                        return r

                    for c in m["content"]:
                        if c["type"] == "tool_use":
                            inp = parse_input(c.get("input"))
                            uses[c.get("id")] = (c.get("name"), inp)
                            name = c.get("name")
                            if name in ("chart_display_v0", "visualize:show_widget"):
                                kind = "chart" if name == "chart_display_v0" else "widget"
                                counters[kind] += 1
                                n = counters[kind]
                                ext = ".json" if kind == "chart" else ".html"
                                exist = next((rel for rel in arts if posixpath.basename(rel).startswith(f"{kind}_{n}_") and rel.endswith(ext)), None)
                                stem = posixpath.splitext(posixpath.basename(exist))[0] if exist else f"{kind}_{n}_{safe(inp.get('title'))}"
                                src = src_dir / (hashlib.md5((cid + c.get("id", "")).encode()).hexdigest() + ext)
                                if kind == "chart":
                                    src.write_text(json.dumps(inp, ensure_ascii=False, indent=1), encoding="utf-8")
                                else:
                                    src.write_text(inp.get("widget_code", ""), encoding="utf-8")
                                r = row(kind, inp.get("title", ""), index=n, in_export=("json only" if kind == "chart" else "code only") if exist else "no",
                                        export_file=f"{source_dir}/{exist}" if exist else "", render_file=f"{run_dir}/{stem}.png")
                                jobs.append({"kind": kind, "src": str(src), "title": inp.get("title", ""), "out": r["render_file"], "row": len(rows) - 1})
                            elif name == "Artifact" and inp.get("action", "publish") == "publish" and inp.get("file_path"):
                                fp = inp["file_path"]
                                rel = by_base.get(posixpath.basename(fp))
                                r = row("artifact page", fp, in_export="html only" if rel else "no", export_file=f"{source_dir}/{rel}" if rel else "",
                                        render_file=f"{run_dir}/page_{safe(Path(fp).stem)}.png")
                                add_page_job(jobs, rows, r, run, rel, cid, fp, src_dir, fetch)
                        elif c["type"] == "tool_result":
                            for x in result_items(c):
                                if x.get("type") == "image" and x.get("file_uuid"):
                                    counters["view"] += 1
                                    n = counters["view"]
                                    viewed = uses.get(c.get("tool_use_id"), (None, {}))[1].get("path", "")
                                    r = row("view image", viewed, index=n, in_export="[image] placeholder",
                                            render_file=f"{run_dir}/view_images/{n:02d}_{safe(Path(viewed).stem, 50)}.png",
                                            notes=f"file_uuid {x['file_uuid']}")
                                    jobs.append({"kind": "view", "file_uuid": x["file_uuid"], "out": r["render_file"], "row": len(rows) - 1})
                                elif x.get("type") == "local_resource":
                                    fp = x.get("file_path", "")
                                    rel = by_base.get(posixpath.basename(fp))
                                    note = "" if rel else ("no longer in the chat's outputs" if saved and fp not in saved else "")
                                    r = row("presented file", fp, in_export="yes" if rel else "no", export_file=f"{source_dir}/{rel}" if rel else "", notes=note)
                                    if fp.lower().endswith((".html", ".htm")):
                                        r["render_file"] = f"{run_dir}/page_{safe(Path(fp).stem)}.png"
                                        if not any(j.get("out") == r["render_file"] for j in jobs):
                                            add_page_job(jobs, rows, r, run, rel, cid, fp, src_dir, fetch)
                        elif c["type"] == "text" and m["sender"] == "assistant" and re.search(r"\$\$|\\\[|\\\(", c.get("text", "")):
                            row("math in text", "", in_export="raw LaTeX in transcript", notes="rendered as math in the chat; transcripts keep the LaTeX source")
    fetch["view_images"] = sorted({j["file_uuid"] for j in jobs if j["kind"] == "view"})
    fetch["outputs"] = sorted({tuple(x) for x in fetch["outputs"]})
    (out / "_plan" / "plan.json").write_text(json.dumps({"rows": rows, "jobs": jobs, "exports": [str(Path(e).resolve()) for e in args.export],
                                                          "planned_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                                                         ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "_plan" / "fetch_list.json").write_text(json.dumps(fetch, indent=1), encoding="utf-8")
    write_audit(out, rows)
    kinds = Counter((r["group"], r["kind"], r["turn"]) for r in rows)
    for k, v in sorted(kinds.items()):
        print(k, v)
    print(f"{len(jobs)} render jobs; {len(fetch['view_images'])} view images and {len(fetch['outputs'])} output files come from claude.ai")
    return out / "_plan" / "fetch_list.json"


def PurePath_join(*parts):
    return "/".join(p.strip("/") for p in parts if p)


def add_page_job(jobs, rows, r, run, rel, cid, fp, src_dir, fetch):
    src = ""
    if rel:
        d = src_dir / hashlib.md5((cid + rel).encode()).hexdigest()
        d.mkdir(parents=True, exist_ok=True)
        dst = d / posixpath.basename(rel)
        dst.write_bytes(run.read(rel))
        src = str(dst)
    else:
        fetch["outputs"].append([cid, fp])
    jobs.append({"kind": "page", "src": src, "chat_id": cid, "path": fp, "out": r["render_file"], "row": len(rows) - 1})


def write_audit(out, rows):
    with open(Path(out) / "renderings_audit.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=AUDIT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in AUDIT_FIELDS})


# ---------------------------------------------------------------- assets (dir or zip)
class Assets:
    def __init__(self, path):
        self.dir = self.zip = None
        self.names = []
        self.run_prefixes = {}
        if path:
            p = Path(path)
            if p.is_dir():
                self.dir = p
                self.names = [f.relative_to(p).as_posix() for f in p.rglob("*") if f.is_file()]
            elif p.exists():
                self.zip = zipfile.ZipFile(p)
                self.names = self.zip.namelist()
            for name in self.names:
                if name.count("/") == 2 and name.endswith("/run.json"):
                    meta = json.loads(self.read(name).decode("utf-8"))
                    self.run_prefixes[meta["chat_id"]] = name[:-len("run.json")]

    def read(self, name):
        return (self.dir / name).read_bytes() if self.dir else self.zip.read(name)

    def view_image(self, file_uuid):
        """(extension, original preview bytes), from a combined archive or asset bundle."""
        starts = [f"view_images/{file_uuid}."] + [f"{p}view_images/{file_uuid}." for p in self.run_prefixes.values()]
        hits = sorted(n for n in self.names if any(n.startswith(prefix) for prefix in starts))
        if not hits:
            return None
        data = self.read(hits[0])
        if any(self.read(n) != data for n in hits[1:]):
            raise ValueError(f"Conflicting downloaded previews for {file_uuid}")
        return hits[0].rsplit(".", 1)[-1], data

    def output(self, chat_id, path, dst_dir):
        names = [f"outputs/{chat_id}/{path.lstrip('/')}"]
        prefix = self.run_prefixes.get(chat_id)
        if prefix:
            if path.startswith("/mnt/user-data/outputs/"):
                rel = "artifacts/" + path[len("/mnt/user-data/outputs/"):]
            elif path.startswith("/home/claude/"):
                rel = "artifacts/sandbox/" + path[len("/home/claude/"):]
            else:
                rel = "artifacts/fetched/" + path.lstrip("/")
            names.insert(0, prefix + rel)
        for name in names:
            if name not in self.names:
                continue
            if self.dir:
                return str(self.dir / name)
            dst = Path(dst_dir) / hashlib.md5(name.encode()).hexdigest() / posixpath.basename(path)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(self.read(name))
            return str(dst)
        return ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.zip:
            self.zip.close()


# ---------------------------------------------------------------- render
def render(args):
    out = Path(args.renderings)
    p = load_json(out / "_plan" / "plan.json")
    rows, jobs = p["rows"], p["jobs"]
    with Assets(args.assets) as assets, Assets(getattr(args, "fallback_assets", None)) as fallback:
        import render_chart, render_widget, render_page
        ch = [j for j in jobs if j["kind"] == "chart"]
        if ch:
            render_chart.render([(load_json(j["src"]), out / j["out"]) for j in ch], args.theme)
            for j in ch:
                rows[j["row"]]["status"] = "rendered"
        wd = [j for j in jobs if j["kind"] == "widget"]
        if wd:
            render_widget.render([(Path(j["src"]).read_text(encoding="utf-8"), j.get("title", ""), out / j["out"]) for j in wd], args.theme, keep_html=True)
            for j in wd:
                rows[j["row"]]["status"] = "rendered (+ _standalone.html)"
        pg = []
        for j in [j for j in jobs if j["kind"] == "page"]:
            src = (j["src"] or assets.output(j["chat_id"], j["path"], out / "_plan" / "fetched")
                   or fallback.output(j["chat_id"], j["path"], out / "_plan" / "fetched"))
            if src:
                pg.append((src, out / j["out"], j))
            else:
                rows[j["row"]]["status"] = "source html not available"
        if pg:
            render_page.render([(s, o) for s, o, _ in pg], offline_dir=args.offline_assets)
            for _, _, j in pg:
                rows[j["row"]]["status"] = "rendered"
        vw = [j for j in jobs if j["kind"] == "view"]
        for j in vw:
            got = assets.view_image(j["file_uuid"]) or fallback.view_image(j["file_uuid"])
            if got is None:
                rows[j["row"]]["status"] = "image not downloaded"
                continue
            ext, data = got
            dst = out / j["out"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if getattr(args, "view_png", False) and ext.lower() != "png":
                from PIL import Image
                Image.open(io.BytesIO(data)).save(dst)
            else:  # keep the preview exactly as claude.ai served it (WebP); converting adds size, not detail
                dst = dst.with_suffix("." + ext)
                dst.write_bytes(data)
            rows[j["row"]]["render_file"] = dst.relative_to(out).as_posix()
            rows[j["row"]]["status"] = "saved (chat preview copy)"
        for r in rows:
            if r["kind"] in ("presented file", "math in text") and not r.get("status"):
                r["status"] = "audit only"
        write_audit(out, rows)
        (out / "_plan" / "plan.json").write_text(json.dumps(dict(p, rows=rows), ensure_ascii=False, indent=1), encoding="utf-8")
        done = sum(1 for r in rows if str(r.get("status", "")).startswith(("rendered", "saved")))
        missing = sum(1 for r in rows if r.get("status") == "image not downloaded")
        print(f"done: {done} files written" + (f"; {missing} view images not downloaded (see _plan/fetch_list.json)" if missing else "")
              + f"; audit at {out / 'renderings_audit.csv'}")


# ---------------------------------------------------------------- pack
def readme_text(rows, planned):
    groups = sorted({r["group"] for r in rows})
    kinds = [("chart", "Inline charts", "`chart_N_<title>.png`", "JSON only"),
             ("widget", "Visualize widgets", "`widget_N_<title>.png` + `_standalone.html`", "code only"),
             ("artifact page", "Published artifact pages", "`page_<name>.png`", "HTML only"),
             ("presented file", "Presented .html files", "`page_<name>.png`", "HTML only"),
             ("view image", "Images Claude opened with `view`", "`view_images/NN_<file>.webp`", "`[image]` placeholder")]
    L = ["# Renderings of what the chats showed in the browser", "",
         f"Pictures of items that claude.ai displayed as pictures but the exports keep only as code, data or a placeholder (PNG renders, plus claude.ai's WebP preview copies of viewed images), "
         f"for the exports {', '.join('`' + g + '.zip`' for g in groups)}. Built {planned} by `renderers/build_renderings.py`.", "",
         "Folders follow the export layout: `<export>/<prompt>/<run>/`. `renderings_audit.csv` lists every item, including the ones the exports already cover.", "",
         "| Item shown in the chat | What the export keeps | " + " | ".join(groups) + " | Rendered here as |",
         "|---|---|" + "---|" * len(groups) + "---|"]
    for kind, label, fname, keeps in kinds:
        sel = [r for r in rows if r["kind"] == kind and (kind != "presented file" or r.get("render_file"))]
        if not sel:
            continue
        cells = []
        for g in groups:
            gs = [r for r in sel if r["group"] == g]
            done = sum(1 for r in gs if str(r.get("status", "")).startswith(("rendered", "saved")))
            cells.append(f"{done}" + (f" of {len(gs)}" if done != len(gs) else ""))
        L.append(f"| {label} | {keeps} | " + " | ".join(cells) + f" | {fname} |")
    alt = sum(1 for r in rows if r["turn"] != "run" and r["kind"] in ("chart", "widget", "artifact page", "view image"))
    math = Counter(r["group"] for r in {(r["group"], r["chat"], r["run"]): r for r in rows if r["kind"] == "math in text"}.values())
    L += ["", "## Notes", ""]
    if alt:
        L.append(f"- {alt} of these items come from alternate continuations (a second branch claude.ai kept in the same chat); the audit marks them in the `turn` column.")
    L.append("- View images are claude.ai's own preview copies, saved as served (WebP, about 1200 px wide). They show each file as it looked when Claude checked it, including intermediate versions.")
    L.append("- Charts and widgets are redrawn from the saved data and code in claude.ai's light theme, with a system sans font instead of Anthropic Sans.")
    L.append("- Pages are full-page screenshots at 1280 px wide.")
    if math:
        L.append("- Math: Claude's replies in " + ", ".join(f"{v} {k} run{'s' if v != 1 else ''}" for k, v in sorted(math.items())) + " contain equations the chat shows as formatted math; the transcripts keep the LaTeX source, so nothing is rendered for them.")
    missing = [r for r in rows if not str(r.get("status", "")).startswith(("rendered", "saved", "audit only"))]
    if missing:
        L.append(f"- Not rendered: {len(missing)} item(s); see the `status` column ({', '.join(sorted({r.get('status', '') for r in missing}))}).")
    L += ["", "## renderings_audit.csv columns", "", "| Column | Meaning |", "|---|---|",
          "| `group`, `chat`, `run` | export, prompt folder and run folder |",
          "| `kind` | chart, widget, artifact page, presented file, view image, math in text |",
          "| `turn` | `run` (the branch claude.ai shows) or `alternate continuation` |",
          "| `in_export` | what the export has: `json only`, `code only`, `html only`, `[image] placeholder`, `yes`, `no` |",
          "| `export_file` | the matching file in the export, if any |",
          "| `render_file` | the file in this folder |",
          "| `status` | `rendered`, `saved (chat preview copy)`, `audit only`, or why it wasn't rendered |",
          "| `notes`, `message_uuid`, `time` | extra context; `notes` holds the claude.ai file id for view images |", ""]
    return "\n".join(L)


def pack(args):
    out = Path(args.renderings)
    p = load_json(out / "_plan" / "plan.json")
    (out / "README.md").write_text(readme_text(p["rows"], p.get("planned_utc", "")[:10]), encoding="utf-8")
    dst = Path(args.zip)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".zip.tmp")
    n = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(out.rglob("*")):
            rel = f.relative_to(out).as_posix()
            if rel.startswith("_plan") or f.is_dir():
                continue
            z.write(f, "Renderings/" + rel)
            n += 1
    os.replace(tmp, dst)
    print(f"packed {n} files into {dst} ({dst.stat().st_size / 1e6:.1f} MB)")


# ---------------------------------------------------------------- update model archives

def _digest(data):
    return hashlib.sha256(data).hexdigest()


def merge_renderings(archive, work):
    """Atomically add derivatives while preserving every existing archive member byte for byte."""
    archive, work = Path(archive), Path(work)
    before = archive.stat()
    signature = (before.st_size, before.st_mtime_ns)
    rows = load_json(work / "_plan" / "plan.json")["rows"]
    updates, renames, expected = {}, {}, {}
    with Export(archive) as exp:
        if not exp.is_consolidated:
            raise ValueError("Merge requires a self-contained model archive")
        prefixes = {r.prefix for r in exp.runs()}
    with zipfile.ZipFile(archive) as source:
        infos = source.infolist()
        names = {i.filename for i in infos}
        if len(names) != len(infos):
            raise ValueError(f"Duplicate ZIP members in {archive}; refusing an ambiguous rewrite")
        for file in sorted(work.rglob("*")):
            if not file.is_file():
                continue
            name = file.relative_to(work).as_posix()
            if name.startswith("_plan/") or name in {"renderings_audit.csv", "README.md"}:
                continue
            if not any(name.startswith(prefix) for prefix in prefixes):
                raise ValueError(f"Generated file is outside the archive's runs: {name}")
            data = file.read_bytes()
            target = name
            if name in names and source.read(name) != data:
                parent, base = posixpath.split(name)
                target = f"{parent}/rendered_{base}"
                if target in names and source.read(target) != data:
                    stem, ext = posixpath.splitext(target)
                    target = f"{stem}_{_digest(data)[:12]}{ext}"
                if target in names and source.read(target) != data:
                    raise ValueError(f"Content-hash filename collision: {target}")
            if target in updates and updates[target] != data:
                raise ValueError(f"Conflicting generated files: {target}")
            updates[target] = data
            renames[name] = target
        for row in rows:
            if row.get("render_file") in renames:
                row["render_file"] = renames[row["render_file"]]
        audit = io.StringIO(newline="")
        writer = csv.DictWriter(audit, fieldnames=AUDIT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({k: row.get(k, "") for k in AUDIT_FIELDS} for row in rows)
        updates["renderings_audit.csv"] = audit.getvalue().encode("utf-8-sig")
        updates["regenerated_fetch_list.json"] = (work / "_plan" / "fetch_list.json").read_bytes()
        for name in ("renderings_audit.csv", "regenerated_fetch_list.json"):
            if name in names and source.read(name) != updates[name]:
                data = updates.pop(name)
                stem, ext = posixpath.splitext(name)
                target = f"{stem}__{_digest(data)[:12]}{ext}"
                if target in names and source.read(target) != data:
                    raise ValueError(f"Content-hash filename collision: {target}")
                updates[target] = data
        fd, temporary = tempfile.mkstemp(prefix=archive.stem + "_", suffix=".tmp", dir=archive.parent)
        os.close(fd)
        temporary = Path(temporary)
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as dest:
                dest.comment = source.comment
                for info in infos:
                    data = source.read(info)
                    name = info.filename
                    if name in updates and updates[name] != data:
                        raise ValueError(f"Refusing to replace existing archive member: {name}")
                    updates.pop(name, None)
                    dest.writestr(info, data)
                    expected[name] = _digest(data)
                for name, data in updates.items():
                    dest.writestr(name, data)
                    expected[name] = _digest(data)
            if temporary.stat().st_size > 100 * 1024 * 1024:
                raise ValueError("Updated archive exceeds the 100 MiB publication limit; original archive retained")
            with zipfile.ZipFile(temporary) as check:
                if set(check.namelist()) != set(expected):
                    raise ValueError("Archive rewrite changed the member inventory")
                for name, digest in expected.items():
                    if _digest(check.read(name)) != digest:
                        raise ValueError(f"Archive rewrite verification failed: {name}")
            source.close()
            current = archive.stat()
            if (current.st_size, current.st_mtime_ns) != signature:
                raise RuntimeError("The archive changed during rendering; no update was installed")
            os.replace(temporary, archive)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"updated {archive}; verified {len(expected)} members; original answer snapshots retained")


def stage_downloaded_assets(archive, asset_path, work):
    """Keep freshly downloaded source bytes beside their own run, before rendering."""
    work = Path(work)
    jobs = load_json(work / "_plan" / "plan.json")["jobs"]
    with Export(archive) as exp, Assets(asset_path) as assets:
        by_chat = {run.messages()["uuid"]: run.prefix for run in exp.runs()}
        for job in jobs:
            if job["kind"] == "view":
                got = assets.view_image(job["file_uuid"])
                if got:
                    ext, data = got
                    parent = posixpath.dirname(job["out"])
                    dst = work / parent / (job["file_uuid"] + "." + ext)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(data)
            elif job["kind"] == "page" and not job["src"]:
                src = assets.output(job["chat_id"], job["path"], work / "_plan" / "fetched")
                if src:
                    path = job["path"]
                    if path.startswith("/mnt/user-data/outputs/"):
                        rel = "artifacts/" + path[len("/mnt/user-data/outputs/"):]
                    elif path.startswith("/home/claude/"):
                        rel = "artifacts/sandbox/" + path[len("/home/claude/"):]
                    else:
                        rel = "artifacts/fetched/" + path.lstrip("/")
                    if ".." in rel.split("/"):
                        raise ValueError(f"Unsafe downloaded asset path: {path}")
                    dst = work / by_chat[job["chat_id"]] / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(Path(src).read_bytes())


def _render_options(args, work, assets):
    return argparse.Namespace(renderings=str(work), assets=assets, fallback_assets=None,
                              offline_assets=args.offline_assets, theme=args.theme, view_png=args.view_png)


def run_all(args):
    root = Path(args.root) if args.root else HERE.parent
    exports = find_exports(root, args.export)
    if not exports:
        raise SystemExit(f"no model archives found in {root}")
    base = Path(args.work) if args.work else None
    if base:
        base.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="claude_renderings_", dir=base))
    try:
        kinds = []
        for ep in exports:
            with Export(ep) as exp:
                kinds.append(exp.is_consolidated)
        if not all(kinds):
            if any(kinds):
                raise ValueError("Use consolidated archives or original exports in one invocation, not a mixture")
            return run_legacy_exports(args, exports, work, root)
        fetch = {"view_images": set(), "outputs": set()}
        for i, ep in enumerate(exports):
            run_work = work / str(i)
            fl = plan(argparse.Namespace(export=[str(ep)], out=str(run_work)))
            missing = load_json(fl)
            fetch["view_images"].update(missing["view_images"])
            fetch["outputs"].update(tuple(x) for x in missing["outputs"])
            options = _render_options(args, run_work, args.assets or str(ep))
            if args.assets:
                options.fallback_assets = str(ep)
                stage_downloaded_assets(ep, args.assets, run_work)
            render(options)
            merge_renderings(ep, run_work)
        if args.fetch_list:
            target = Path(args.fetch_list)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps({k: sorted(v) for k, v in fetch.items()}, indent=1), encoding="utf-8")
    finally:
        if args.keep_work:
            print("temporary work retained:", work)
        else:
            shutil.rmtree(work)


def run_legacy_exports(args, exports, work, root):
    """Explicit legacy exports still publish only one self-contained ZIP per model."""
    import parse_exports
    from consolidate_archive import consolidate
    for ep in exports:
        with Export(ep) as exp:
            target = root / (exp.group + ".zip")
        if target.exists():
            raise ValueError(f"Legacy input conversion requires an unused output path: {target}; "
                             "pass --root NEW_DIRECTORY with --export ORIGINAL.zip")
    rendered, parsed = work / "rendered", work / "parsed"
    signatures = {Path(e): (Path(e).stat().st_size, Path(e).stat().st_mtime_ns) for e in exports}
    assets = args.assets or (str(root / "claude_assets.zip") if (root / "claude_assets.zip").exists() else None)
    fetch_list = plan(argparse.Namespace(export=[str(e) for e in exports], out=str(rendered)))
    render(_render_options(args, rendered, assets))
    parse_exports.build([str(e) for e in exports], str(rendered), str(parsed))
    staged = work / "archives"
    reports = consolidate(work, staged, exports=exports, renderings=rendered, parsed=parsed,
                          assets=assets or work / "no_downloaded_assets", fetch_list=fetch_list)["archives"]
    for source, signature in signatures.items():
        now = source.stat()
        if (now.st_size, now.st_mtime_ns) != signature:
            raise RuntimeError(f"Source changed during rendering: {source}; no archives installed")
    for report in reports:
        source = Path(report["archive"])
        target = root / source.name
        if target.exists():
            raise ValueError(f"Output already exists: {target}; no existing archive will be replaced")
    for report in reports:
        source = Path(report["archive"])
        target = root / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=source.stem + "_", suffix=".tmp", dir=target.parent)
        os.close(fd)
        temporary = Path(temporary)
        try:
            shutil.copyfile(source, temporary)
            if _digest(temporary.read_bytes()) != report["sha256"]:
                raise ValueError(f"Archive copy verification failed: {target}")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        print("built self-contained model archive:", target)
    if args.fetch_list:
        target = Path(args.fetch_list)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fetch_list, target)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("--export", action="append", required=True, help="export zip or unzipped export folder (repeat)")
    a.add_argument("--out", required=True)
    b = sub.add_parser("render")
    b.add_argument("renderings")
    b.add_argument("--assets", help="claude_assets.zip or its unzipped folder")
    b.add_argument("--offline-assets")
    b.add_argument("--theme", default="light", choices=["light", "dark"])
    b.add_argument("--view-png", action="store_true", help="convert view images to PNG instead of keeping claude.ai's WebP")
    c = sub.add_parser("pack")
    c.add_argument("renderings")
    c.add_argument("--zip", required=True)
    d = sub.add_parser("parse")
    d.add_argument("--export", action="append", required=True)
    d.add_argument("--renderings", help="Renderings.zip or a rendered work folder (for chart/widget images)")
    d.add_argument("--out", required=True)
    e = sub.add_parser("all")
    e.add_argument("--root", help="folder containing Fable5_1.zip and Opus4_7.zip (default: above renderers/)")
    e.add_argument("--export", action="append")
    e.add_argument("--assets")
    e.add_argument("--offline-assets")
    e.add_argument("--theme", default="light", choices=["light", "dark"])
    e.add_argument("--view-png", action="store_true")
    e.add_argument("--work", help="parent for a new temporary staging directory; existing contents are retained")
    e.add_argument("--fetch-list", help="optional explicit destination for the combined fetch request list")
    e.add_argument("--keep-work", action="store_true")
    args = ap.parse_args()
    if args.cmd == "plan":
        plan(args)
    elif args.cmd == "render":
        render(args)
    elif args.cmd == "pack":
        pack(args)
    elif args.cmd == "parse":
        import parse_exports
        parse_exports.build(args.export, args.renderings, args.out)
    else:
        run_all(args)


if __name__ == "__main__":
    main()
