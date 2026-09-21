"""Build an exclusive coarse-stage breakdown of framework non-solver wall time.
Original ZIPs are read in place. The authoritative totals come from the locally
produced all_run_timings.csv. Run build_timings.py first if that CSV is absent.
No nested worker durations or parallel LLM call durations are added to parents.
"""
from pathlib import Path
import csv
import json
import re
import zipfile
from collections import defaultdict

HERE = Path(__file__).resolve().parents[1] / "audit"
ROOT = Path(__file__).resolve().parents[3]
COMPONENTS = {
    'fw_lc1': 'LC1: system and equation mapping',
    'fw_lc2': 'LC2: thermodynamic data assembly',
    'fw_lc3': 'LC3: solver configuration',
    'fw_ld': 'LD: result validation',
    'fw_other': 'Other orchestration, reporting and unresolved time',
}


def numberkey(pid):
    return tuple(int(v) for v in re.findall(r'\d+', pid))


def main():
    with (HERE/'all_run_timings.csv').open(encoding='utf-8-sig', newline='') as f:
        totals = {r['prompt_id']: r for r in csv.DictReader(f) if r['config'] == 'framework'}
    assert len(totals) == 32, len(totals)
    records = {}
    for archive in sorted((ROOT/'_benchmark').glob('*.zip')):
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            for name in names:
                if name.count('/') != 1 or not name.endswith('/manifest.json'):
                    continue
                folder = name.split('/')[0]
                pid = '_'.join(folder.split('_')[:2])
                assert pid not in records, ('duplicate manifest', pid)
                values = {k: 0.0 for k in COMPONENTS}
                sources = defaultdict(list)
                details = []
                for member in names:
                    pieces = member.split('/')
                    # Only a canonical parent summary is used. Nested restart,
                    # subagent or worker summaries would double-count elapsed.
                    if not (len(pieces) == 5 and pieces[0] == folder and pieces[1].startswith('L1_call_')
                            and pieces[2] in {'LC1', 'LC2', 'LC3'} and pieces[3] == 'summary'
                            and pieces[4] == pieces[2] + '_summary.json'):
                        continue
                    doc = json.loads(z.read(member))
                    seconds = doc.get('elapsed_s')
                    if not isinstance(seconds, (int, float)):
                        details.append({'member': member, 'reason': 'missing elapsed; left in residual'})
                        continue
                    component = 'fw_' + pieces[2].lower()
                    assert seconds >= 0, (pid, member, seconds)
                    values[component] += seconds
                    sources[component].append(str(archive.relative_to(ROOT)) + '::' + member)
                    details.append({'member': member, 'component': component, 'seconds': seconds, 'status': doc.get('status')})
                logmember = folder + '/_run.log'
                log = z.read(logmember).decode('utf-8', errors='replace')
                for lineno, line in enumerate(log.splitlines(), 1):
                    if 'Analysis.LD:' not in line:
                        continue
                    match = re.search(r'\(([0-9.]+)s\)', line)
                    if not match:
                        details.append({'member': logmember, 'line': lineno, 'reason': 'LD log without elapsed; left in residual'})
                        continue
                    seconds = float(match.group(1))
                    values['fw_ld'] += seconds
                    sources['fw_ld'].append(str(archive.relative_to(ROOT)) + '::' + logmember + ':' + str(lineno))
                    details.append({'member': logmember, 'line': lineno, 'component': 'fw_ld', 'seconds': seconds, 'log': line})
                total = float(totals[pid]['non_solver_wall_s'])
                values['fw_other'] = total - sum(values.values())
                assert values['fw_other'] >= -1e-6, (pid, total, values)
                # Do not force parent durations to fill residual or allocate by
                # token/cost proportions. Missing or unmeasured work stays Other.
                sources['fw_other'].append('all_run_timings.csv::config=framework,prompt_id=' + pid)
                records[pid] = dict(values=values, sources=dict(sources), details=details, total=total)
    assert set(records) == set(totals), (set(totals)-set(records), set(records)-set(totals))
    rows = []
    for pid in sorted(records, key=numberkey):
        rec = records[pid]
        for component, label in COMPONENTS.items():
            seconds = rec['values'][component]
            if component in {'fw_lc1', 'fw_lc2', 'fw_lc3'}:
                method = 'Sum canonical sequential LC parent elapsed_s once per pipeline call; includes child concurrency within parent wall time, without separately adding worker times.'
                quality = 'recorded_parent_stage_elapsed' if rec['sources'].get(component) else 'no_recorded_stage_elapsed'
            elif component == 'fw_ld':
                method = 'Sum separately logged Analysis.LD verdict elapsed durations; each validation attempt is counted once, precision 0.1 s.'
                quality = 'recorded_validation_elapsed_0.1s' if rec['sources'].get(component) else 'no_recorded_validation_elapsed'
            else:
                method = 'Authoritative non-solver total minus LC1, LC2, LC3 and LD; contains orchestration, report generation, remaining postprocessing, missing stage records and timing-rounding residual.'
                quality = 'unresolved_residual'
                if pid == 'L1_1':
                    method += ' Resumed-run total reconstructs retained preparation/restart preludes/final remainder and excludes interrupted solver periods and downtime.'
                    quality = 'reconstructed_run_residual'
            rows.append(dict(prompt_id=pid,component=component,component_label=label,seconds=round(seconds,9),minutes=seconds/60,
                method=method,source=' | '.join(rec['sources'].get(component, [])),quality=quality,
                total_non_solver_s=rec['total'],recorded_status=totals[pid]['recorded_status']))
    with (HERE/'framework_stage_breakdown.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    errors = {pid:sum(r['seconds'] for r in rows if r['prompt_id']==pid)-rec['total'] for pid,rec in records.items()}
    assert max(abs(v) for v in errors.values()) < 1e-6, errors
    audit = dict(
        basis='Exclusive coarse parent-stage elapsed time; numerical solver elapsed has already been removed from authoritative run totals.',
        components=COMPONENTS,
        exclusions='No token/cost share allocations; no adding nested or parallel worker durations; no invented per-agent timestamps.',
        limitations='LC1/2/3 parent elapsed includes their own orchestration and I/O. LD log timing is rounded to 0.1 s. Other is explicitly unresolved, not pure LLM time. Failed/absent stage timing remains in Other if no elapsed was recorded. L1_1 is a resumed-run reconstruction.',
        run_count=len(records),row_count=len(rows),max_abs_reconciliation_error_s=max(abs(v) for v in errors.values()),runs=records)
    (HERE/'framework_stage_breakdown_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'runs':len(records),'rows':len(rows),'max_abs_reconciliation_error_s':max(abs(v) for v in errors.values()),
        'L1_11':records['L1_11']['values'],'L1_1':records['L1_1']['values'],
        'component_totals_s':{k:sum(rec['values'][k] for rec in records.values()) for k in COMPONENTS}},indent=2))

if __name__ == '__main__':
    main()
