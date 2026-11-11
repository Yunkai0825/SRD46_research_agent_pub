"""Preserve existing Claude files in one self-contained ZIP per model.

Run folders are <model_effort>/<prompt_id>/; figures are beside final_answer.md.
The provenance manifest audits byte preservation; it is not a runtime alias map.
This command only reorganizes existing files and never executes scientific code.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import quote, unquote
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_zip import Export, _zip_name
LIMIT = 100 * 1024 * 1024


def io_path(path):
    value = str(Path(path).absolute())
    if os.name == 'nt' and not value.startswith('\\\\?\\'):
        value = '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value
    return Path(value)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def safe_name(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or not p.parts:
        raise ValueError(f'Unsafe archive member: {name!r}')
    return name


def verify_archive(path):
    with zipfile.ZipFile(io_path(path)) as z:
        names = [i.filename for i in z.infolist() if not i.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP members')
        for n in names:
            safe_name(n)
        provenance = json.loads(z.read('provenance.json'))
        hashes = {}
        for row in provenance['files']:
            for name in row['destinations']:
                if name not in hashes:
                    data = z.read(name)
                    hashes[name] = (len(data), sha(data))
                if hashes[name] != (row['size'], row['sha256']):
                    raise ValueError(f'Changed original bytes: {row["source"]}:{row["member"]} -> {name}')
        runs = []
        for n in names:
            if not re.fullmatch(r'[^/]+/[^/]+/run\.json', n):
                continue
            base = n.rsplit('/', 1)[0]
            meta = json.loads(z.read(n))
            raw = z.read(base + '/messages.json')
            if z.read(base + '/conversation.json') != raw or json.loads(raw)['uuid'] != meta['chat_id']:
                raise ValueError(f'Conversation or identity mismatch: {base}')
            answer = z.read(base + '/final_answer.md').decode('utf-8')
            for target in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', answer):
                if '://' in target or target.startswith('data:'):
                    continue
                local = base + '/' + unquote(target.split('#', 1)[0])
                if local not in names:
                    raise ValueError(f'Missing final-answer image: {local}')
            runs.append(meta)
        bad = z.testzip()
        if bad:
            raise ValueError(f'Corrupt ZIP member: {bad}')
        return dict(archive=str(path), size=io_path(path).stat().st_size, files=len(names),
                    preserved_source_files=len(provenance['files']), runs=len(runs),
                    configurations=dict(sorted(Counter(r['config'] for r in runs).items())),
                    sha256=sha(io_path(path).read_bytes()))


def consolidate(root, out, *, exports=None, renderings=None, parsed=None, assets=None, fetch_list=None):
    """Build model archives under out from legacy exports and existing rendered files.

    All source files are read and hashed before either destination is replaced.
    Sources are never moved or removed. Use a staging out directory when migrating.
    Optional paths allow the renderer to use an operating-system temporary tree.
    """
    root, out = io_path(root), io_path(out)
    eps = [io_path(p) for p in (exports or [root/'Opus4_7.zip', root/'Fable5_1.zip'])]
    renderings = io_path(renderings or root/'Renderings.zip')
    parsed = io_path(parsed or root/'parsed')
    assets = io_path(assets or root/'claude_assets.zip')
    fetch_list = io_path(fetch_list or root/'claude_fetch_list.json')
    blobs, records, metas = defaultdict(dict), defaultdict(list), defaultdict(list)
    containers, coverage, runs = [], set(), []
    image_runs, chat_runs = defaultdict(set), defaultdict(set)

    def put(model, name, data):
        safe_name(name)
        old = blobs[model].get(name)
        if old is not None and old != data:
            raise ValueError(f'Different files collide: {model}:{name}')
        blobs[model][name] = data
        return name

    def preserve(source, member, data, targets, category):
        if not targets:
            raise ValueError(f'Unassigned source file: {source}:{member}')
        coverage.add((source, member))
        for model, dests in targets.items():
            for dest in dests:
                put(model, dest, data)
            records[model].append(dict(source=source, member=member, category=category,
                destinations=dests, size=len(data), sha256=sha(data)))

    def container(path):
        if path.is_file():
            containers.append(dict(source=path.name, size=path.stat().st_size, sha256=sha(path.read_bytes())))

    exports_open = []
    for ep in eps:
        exp = Export(ep)
        exports_open.append(exp)
        model = exp.group
        if getattr(exp, 'is_consolidated', False):
            exp.close()
            raise ValueError('Input is already self-contained; use build_renderings.py all to add renderings')
        if (out / (model + '.zip')).exists():
            exp.close()
            raise ValueError(f'Refusing to overwrite an existing {model}.zip in {out}')
        container(ep)
        for run in exp.runs():
            dest = f'{run.config}/{run.prompt_id}'
            if dest + '/run.json' in blobs[model]:
                raise ValueError(f'Duplicate run identity: {dest}')
            conv = run.messages()
            meta = dict(schema_version=1, export=model, config=run.config, prompt_id=run.prompt_id,
                prompt=run.prompt, effort=run.effort, run_name=run.run_name, run_no=run.run_no,
                chat_id=conv['uuid'], original_prefix=run.prefix)
            metas[model].append(meta)
            runs.append((exp, run, dest))
            put(model, dest+'/run.json', encoded(meta))
            chat_runs[conv['uuid']].add((model, dest))
            def scan(value):
                if isinstance(value, dict):
                    if value.get('file_uuid'):
                        image_runs[value['file_uuid']].add((model, dest))
                    for v in value.values(): scan(v)
                elif isinstance(value, list):
                    for v in value: scan(v)
            scan(conv)
            for rel, name in run.files().items():
                item = exp._names[name]
                member = item.filename if isinstance(item, zipfile.ZipInfo) else name
                preserve(ep.name, member, run.read(rel), {model:[dest+'/'+rel]}, 'original export')
        prefixes = [r.prefix for r in exp.runs()]
        for name in exp._names:
            if name.endswith('/') or any(name.startswith(p) for p in prefixes): continue
            rel = name[len(exp.top):] if exp.top and name.startswith(exp.top) else name
            item = exp._names[name]
            member = item.filename if isinstance(item, zipfile.ZipInfo) else name
            preserve(ep.name, member, exp._read(name), {model:['original_export__'+rel.replace('/','__')]}, 'original export metadata')

    models = sorted(blobs)
    def shared(dest): return {model:[dest] for model in models}
    prefixes = {f'{r.config}/{r.prompt}/':(exp.group,dest+'/') for exp,r,dest in runs}
    if parsed.exists():
        for p in sorted(parsed.rglob('*')):
            if not p.is_file(): continue
            rel = p.relative_to(parsed).as_posix()
            prefix = next((s for s in prefixes if rel.startswith(s)), None)
            if prefix:
                model, base = prefixes[prefix]
                targets = {model:[base+rel[len(prefix):]]}
            elif rel.startswith('_summary/'):
                targets = shared(rel.lstrip('_').replace('/','__'))
            else:
                targets = shared('original_parsed__'+rel.replace('/','__'))
            preserve('parsed', rel, p.read_bytes(), targets, 'parsed answer or statistics')

    def items(path):
        if path.is_dir():
            for p in sorted(path.rglob('*')):
                if p.is_file() and not p.relative_to(path).as_posix().startswith('_plan/'):
                    rel = p.relative_to(path).as_posix()
                    yield rel, rel, p.read_bytes()
        elif path.exists():
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    if not info.is_dir(): yield info.filename, _zip_name(info), z.read(info)

    container(renderings)
    prefixes = {f'{exp.group}/{r.rel}/':(exp.group,dest+'/') for exp,r,dest in runs}
    for original, name, data in items(renderings):
        name = name.removeprefix('Renderings/')
        prefix = next((s for s in prefixes if name.startswith(s)), None)
        if prefix:
            model, base = prefixes[prefix]
            dest = base+name[len(prefix):]
            if dest in blobs[model] and blobs[model][dest] != data:
                parent, basename = dest.rsplit('/',1)
                dest = parent+'/rendered_'+basename
            targets = {model:[dest]}
        else:
            targets = shared('original_renderings__'+name.replace('/','__'))
        preserve(renderings.name, original, data, targets, 'existing rendering')

    container(assets)
    unmapped = []
    for original, name, data in items(assets):
        targets = defaultdict(list)
        if name.startswith('view_images/'):
            for model, dest in sorted(image_runs.get(PurePosixPath(name).stem, set())):
                targets[model].append(dest+'/'+name)
        elif name.startswith('outputs/'):
            _, cid, sandbox = name.split('/',2)
            rel = sandbox.removeprefix('mnt/user-data/outputs/')
            if sandbox.startswith('home/claude/'):
                rel = 'sandbox/'+sandbox.removeprefix('home/claude/')
            elif rel == sandbox:
                rel = 'fetched/'+sandbox
            for model, dest in sorted(chat_runs.get(cid,set())):
                targets[model].append(dest+'/artifacts/'+rel)
        else:
            targets = shared('original_fetch__'+name.replace('/','__'))
        if not targets:
            targets = shared('unmatched_asset__'+name.replace('/','__'))
            unmapped.append(name)
        preserve(assets.name, original, data, targets, 'fetched original asset')
    if fetch_list.exists():
        container(fetch_list)
        preserve(fetch_list.name, fetch_list.name, fetch_list.read_bytes(),
            shared(fetch_list.name), 'original fetch request')

    for model in models:
        for meta in metas[model]:
            base = f'{meta["config"]}/{meta["prompt_id"]}'
            if base+'/conversation.json' not in blobs[model]:
                put(model, base+'/conversation.json', blobs[model][base+'/messages.json'])
            if base+'/final_answer.md' not in blobs[model]:
                raise ValueError(f'No parsed answer supplied for {base}; parse into temporary storage first')
            figures = [n[len(base)+1:] for n in blobs[model] if n.startswith(base+'/')
                and n.count('/')==2 and PurePosixPath(n).suffix.lower() in {'.png','.webp','.html','.svg','.jpg'}]
            lines = [f'# {meta["config"]}: {meta["prompt"]}', '',
                '[Final answer](final_answer.md) | [Conversation JSON](conversation.json) | [Original transcript](transcript.md)', '',
                'Original export files and `artifacts/` retain their exact bytes. All figures and HTML reports are beside the answer. `view_images/` contains saved chat previews, including intermediate versions.', '',
                f'Conversation: `{meta["chat_id"]}`. Effort: `{meta["effort"]}`. Original run: `{meta["run_name"]}`.', '',
                'Available figures and HTML reports:', '']
            lines += [f'- [{n}]({quote(n)})' for n in sorted(figures)] or ['- See `artifacts/` and `view_images/` for saved files.']
            put(model, base+'/README.md', ('\n'.join(lines)+'\n').encode('utf-8'))
        counts = Counter(m['config'] for m in metas[model])
        lines = [f'# {model} web reference answers', '',
            'Each `<model_effort>/<prompt_id>/` folder contains the complete saved run: original exports, conversation, final answer, original artifacts, existing figures and HTML, and fetched view images. Figures are beside the answer; there is no separate renderings archive.', '',
            '| Configuration | Runs |', '|---|---:|']
        lines += [f'| {c} | {n} |' for c,n in sorted(counts.items())]
        lines += ['', 'Root files beginning with `summary__` preserve the original cross-model statistics and plots, duplicated in both model archives. Other clearly named root files preserve the original global metadata and fetch reports. `provenance.json` records SHA-256 and the original path of every source file. Original statistics retain historical paths; `run.json` retains the full prompt title and conversation identity. All run-specific files are inside their prompt folders.', '',
            'No calculations or figures were regenerated during consolidation. Chat previews may include intermediate states.', '', '## Runs', '']
        lines += [f'- [{m["config"]} / {m["prompt"]}]({m["config"]}/{m["prompt_id"]}/README.md)' for m in metas[model]]
        put(model, 'README.md', ('\n'.join(lines)+'\n').encode('utf-8'))
        put(model, 'runs_index.json', encoded(metas[model]))
        put(model, 'provenance.json', encoded(dict(schema_version=1,
            created_utc=datetime.now(timezone.utc).isoformat(),
            description='Original source bytes preserved; provenance is not a runtime alias.',
            model=model, source_containers=containers, unmapped_assets=unmapped, files=records[model])))
    for exp in exports_open:
        if exp._zip: exp._zip.close()
    out.mkdir(parents=True, exist_ok=True)
    reports = []
    for model in models:
        dst = out/(model+'.zip')
        tmp = dst.with_name(dst.name+'.consolidating-tmp')
        try:
            with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
                for name,data in sorted(blobs[model].items()): z.writestr(name,data)
            if tmp.stat().st_size > LIMIT: raise ValueError(f'{model} exceeds 100 MiB')
            report = verify_archive(tmp)
            os.replace(tmp,dst)
            report['archive']=str(dst)
            reports.append(report)
        finally:
            if tmp.exists(): tmp.unlink()
    return dict(archives=reports, unique_preserved_source_files=len(coverage), unmapped_assets=unmapped)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    ap.add_argument('--out',type=Path,help='Staging directory for the two rebuilt model ZIPs')
    ap.add_argument('--verify',type=Path,help='Verify an existing model archive without changing it')
    args=ap.parse_args()
    if not args.verify and not args.out: ap.error('--out is required when building; originals are retained')
    print(json.dumps(verify_archive(args.verify) if args.verify else consolidate(args.root,args.out),indent=2))


if __name__=='__main__': main()
