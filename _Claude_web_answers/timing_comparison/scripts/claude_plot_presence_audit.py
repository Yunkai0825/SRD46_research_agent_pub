"""Audit scientific plot presence in the 55 preserved Claude web exports.
Read-only on originals. Outputs only to this script's ignored audit directory.
Generated HTML/PNG previews are evidence of presentation only when their original
chart/widget/report or image tool calls are present; arbitrary screenshots/icons
are not used to claim a scientific plot.
"""
from pathlib import Path
import csv, json, re, zipfile
from datetime import datetime

HERE = Path(__file__).resolve().parents[1] / "audit"
ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / '_Claude_web_answers'
SCIENCE_NAME = re.compile(r'pourbaix|speciation|partition|pM_survey|epH|diagram|^fig\d|formal_potentials|oxidation_states|cu_nh3_supporting|comparison|Cu_chloride|^(?:cu|fe|joint)\.(?:png|svg)$', re.I)
VISUAL_EXTS = {'.png', '.svg', '.html', '.pdf'}


def stamp(x):
    return datetime.fromisoformat(x.replace('Z', '+00:00')) if x else None


def path_to_leaf(conv):
    by = {m['uuid']: m for m in conv['chat_messages']}
    p, seen, leaf = [], set(), conv.get('current_leaf_message_uuid')
    while leaf in by and leaf not in seen:
        seen.add(leaf); p.append(by[leaf]); leaf = by[leaf].get('parent_message_uuid')
    return list(reversed(p))


def visual_path(path):
    b = path.rsplit('/', 1)[-1]
    return Path(b).suffix.lower() in VISUAL_EXTS and bool(SCIENCE_NAME.search(b))


def save_csv(name, rows):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def plot_audit():
    rows = []
    for archive in ['Opus4_7.zip', 'Fable5_1.zip']:
        with zipfile.ZipFile(SOURCE / archive) as z:
            members = z.namelist()
            for n in members:
                if not n.endswith('/conversation.json'): continue
                config, prompt = n.split('/')[:2]; prefix = config + '/' + prompt + '/'
                conv = json.loads(z.read(n)); shown = path_to_leaf(conv); shown_ids = {m['uuid'] for m in shown}
                all_blocks = [b for m in conv['chat_messages'] for b in m.get('content', [])]
                results = {b['tool_use_id']: b for b in all_blocks if b.get('type') == 'tool_result'}
                original_visuals = [p[len(prefix):] for p in members if p.startswith(prefix + 'artifacts/') and visual_path(p)]
                shown_evidence, history_evidence, view_evidence = [], [], []
                chart_count = widget_count = 0
                for m in conv['chat_messages']:
                    for b in m.get('content', []):
                        if b.get('type') != 'tool_use': continue
                        name, inp = b.get('name'), b.get('input') or {}
                        result = results.get(b.get('id'))
                        ok = bool(result) and not result.get('is_error')
                        desc = ''
                        if name == 'chart_display_v0' and ok:
                            chart_count += 1
                            desc = 'chart_display_v0: ' + str(inp.get('title', 'scientific chart'))
                        elif name == 'visualize:show_widget' and ok:
                            # Only widget in these exports: Cu-ammonia Pourbaix diagram.
                            title = str(inp.get('title', ''))
                            if SCIENCE_NAME.search(title):
                                widget_count += 1; desc = 'scientific widget: ' + title
                        elif name == 'present_files' and ok:
                            paths = [p for p in inp.get('filepaths', []) if visual_path(p)]
                            if paths: desc = 'present_files: ' + '; '.join(paths)
                        elif name == 'Artifact' and inp.get('action') == 'publish' and ok:
                            p = inp.get('file_path', '')
                            if visual_path(p): desc = 'published scientific HTML report: ' + p
                        elif name == 'view' and ok and visual_path(inp.get('path', '')):
                            view_evidence.append('model viewed scientific plot: ' + inp['path'])
                        if desc:
                            history_evidence.append(desc)
                            if m['uuid'] in shown_ids: shown_evidence.append(desc)
                any_plot = bool(original_visuals or history_evidence or view_evidence)
                answer_plot = bool(shown_evidence)
                evidence = shown_evidence or history_evidence or (['saved original scientific figure: ' + original_visuals[0]] if original_visuals else view_evidence)
                if not evidence:
                    evidence = ['No scientific image/SVG/HTML artifact, chart/widget, plot presentation, or plot-view evidence in the preserved export.']
                notes = ''
                if config == 'Opus4_7_high' and prompt == 'L2_3':
                    notes = 'pM_survey.png exists and was viewed by the model; final answer only names its sandbox path in code formatting, with no attached/embed/published plot.'
                if config == 'Fable5_1_max' and prompt == 'L1_10':
                    notes = 'joint/cu/fe scientific plots exist and were viewed; final response says figures are rendered but publication remains; final stop_reason=tool_use_limit.'
                assistants = [m for m in shown if m.get('sender') == 'assistant']
                truncated = sum(bool(m.get('truncated')) for m in conv['chat_messages'])
                rows.append(dict(config=config, prompt_id=prompt, plot_in_answer=answer_plot, plot_anywhere=any_plot,
                    no_plot_in_answer=not answer_plot, no_plot_anywhere=not any_plot,
                    plot_only_in_history=any_plot and not answer_plot,
                    plot_evidence=' | '.join(evidence), notes=notes,
                    original_scientific_visual_members=' | '.join(original_visuals),
                    chart_calls=chart_count, widget_calls=widget_count,
                    final_stop_reason=assistants[-1].get('stop_reason', '') if assistants else '',
                    truncated_messages=truncated, alternate_messages=sum(m['uuid'] not in shown_ids for m in conv['chat_messages']),
                    source_archive=archive, source_conversation_member=n))
    rows.sort(key=lambda r:(r['config'], [int(x) for x in re.findall(r'\d+', r['prompt_id'])]))
    save_csv('claude_plot_presence.csv', rows)
    summary = {}
    for c in sorted({r['config'] for r in rows}):
        rr=[r for r in rows if r['config']==c]
        summary[c] = dict(runs=len(rr), plot_in_answer=sum(r['plot_in_answer'] for r in rr), plot_anywhere=sum(r['plot_anywhere'] for r in rr),
            no_plot_anywhere=[r['prompt_id'] for r in rr if r['no_plot_anywhere']],
            history_only=[r['prompt_id'] for r in rr if r['plot_only_in_history']])
    data = dict(definitions={
        'plot_in_answer':'Scientific plot attached/published or chart/widget displayed on the current leaf branch; naming a sandbox file is not a displayed/attached plot.',
        'plot_anywhere':'Scientific visual in preserved original artifacts or any branch tool history, including model-only view; arbitrary icons/screenshots do not qualify.',
        'no_plot_anywhere':'No plot found in the preserved export; not proof that an unrecorded/deleted historical item never existed.',
        'science_validity':'Presence does not establish correctness, valid solver execution, or completion of the requested scientific task.'},
        timing_methodology={
        'parser_source':'_Claude_web_answers/renderers/parse_exports.py:236-325',
        'wall_s':'Current-leaf prompt created_at to latest block stop_timestamp, including waits for typed Continue.',
        'active_s':'Sum of per-assistant-message first block start to last block stop intervals; excludes between-message waits.',
        'tool_s_warning':'Existing parsed tool_s is tool_use START to tool_result STOP; it includes code/argument generation, so is not solver execution time.',
        'recommended_comparison':'Use current-leaf wall_s minus current-leaf solver execution interval union; preserve code/command generation. Use tool_use STOP to tool_result START for synchronous commands as an execution proxy.',
        'branches':'Do not subtract all-history solver time from current-leaf wall time. Alternate branches can overlap and should be separately reported.',
        'unknowns':'Unmatched tool calls and background jobs need explicit bounds/unknown markers; source exports can be truncated.'}, summary=summary, runs=rows)
    (HERE/'claude_plot_presence.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return rows


FABLE_INCLUDE = {
 ('medium','L1_1'):[1,2], ('medium','L1_3'):[1,2], ('medium','L1_4'):[], ('medium','L1_9'):[1,2], ('medium','L1_10'):[1,2], ('medium','L1_11'):[1],
 ('max','L1_1'):[3,4,5,6,7], ('max','L1_3'):[3,4,5], ('max','L1_4'):[1,2,3,4,5], ('max','L1_9'):[2,3,4], ('max','L1_10'):[9,10,13,14,15,16], ('max','L1_11'):[3,5],
}

def fable_calls():
    rows=[]
    with zipfile.ZipFile(SOURCE/'Fable5_1.zip') as z:
        for n in z.namelist():
            if not n.endswith('/conversation.json'):continue
            config,prompt=n.split('/')[:2]; effort=config.rsplit('_',1)[1]; conv=json.loads(z.read(n)); shown_ids={m['uuid'] for m in path_to_leaf(conv)}
            blocks=[b for m in conv['chat_messages'] for b in m.get('content',[])]; results={b['tool_use_id']:b for b in blocks if b.get('type')=='tool_result'}
            bash_idx=tool_idx=0
            for m in conv['chat_messages']:
                for b in m.get('content',[]):
                    if b.get('type')!='tool_use':continue
                    tool_idx+=1
                    if b.get('name')!='bash_tool':continue
                    bash_idx+=1; r=results.get(b.get('id'),{}); start=b.get('stop_timestamp'); end=r.get('start_timestamp')
                    sec=(stamp(end)-stamp(start)).total_seconds() if start and end else None
                    incl=bash_idx in FABLE_INCLUDE[(effort,prompt)]
                    background=(effort,prompt,bash_idx)==('max','L1_10',10)
                    reason='Executes numerical solver/check/sweep, including inseparable rerendering and reruns.' if incl else 'Does not execute solver: setup/source lookup, stored-data plotting/reporting, or failed pre-execution time wrapper.'
                    if background:reason='Interrupted background grid: last progress confirms 44.1 s; complete duration unknown. Do not treat surrounding sleep/poll commands as solver time.'
                    rows.append(dict(config=config,prompt_id=prompt,tool_ordinal=tool_idx,bash_ordinal=bash_idx,tool_use_id=b['id'],message_uuid=m['uuid'],on_current_branch=m['uuid'] in shown_ids,
                        include=incl,reason=reason,description=b.get('message',''),execution_start_utc=start or '',execution_result_utc=end or '',
                        command_execution_proxy_s=sec if sec is not None else '',
                        numerical_execution_s='' if background or not incl else sec,
                        numerical_execution_lower_bound_s=44.1 if background else '',
                        background_runtime_unknown=background,
                        source_conversation_member=n))
    save_csv('fable_solver_calls.csv',rows)
    bg=[r for r in rows if r['background_runtime_unknown']][0]
    ps=next(r for r in rows if r['config']=='Fable5_1_max' and r['prompt_id']=='L1_10' and r['bash_ordinal']==13)
    bounds=dict(config='Fable5_1_max',prompt_id='L1_10',tool_use_id=bg['tool_use_id'],
        dispatch_stop_utc=bg['execution_start_utc'],last_progress_observed_by_utc=bg['execution_result_utc'],confirmed_runtime_lower_bound_s=44.1,
        process_absent_observed_by_utc=ps['execution_result_utc'],
        dispatch_to_absence_upper_bound_s=(stamp(ps['execution_result_utc'])-stamp(bg['execution_start_utc'])).total_seconds(),
        caveat='44.1 s is the internal elapsed at the last logged completed pH column. Dispatch/absence envelope includes startup and possibly idle waiting, not an exact runtime. The process was absent in ps output and no completed grid existed. No rerun performed.')
    (HERE/'fable_L1_10_background_bounds.json').write_text(json.dumps(bounds,indent=2)+'\n',encoding='utf-8')
    print('fable_solver_calls',len(rows),'rows',sum(r['include'] for r in rows),'included; bounds',bounds)

if __name__=='__main__':
    plot_audit(); fable_calls()
