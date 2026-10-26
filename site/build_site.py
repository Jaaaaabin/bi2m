"""Rebuild site/index.html from template + base data + knowledge/hard_qa.jsonl + rules/.

python3 site/build_site.py
"""
import glob, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
base = json.load(open(os.path.join(HERE, 'data_base.json'), encoding='utf-8'))
hard = []
for line in open(os.path.join(HERE, '..', 'knowledge', 'hard_qa.jsonl'), encoding='utf-8'):
    h = json.loads(line)
    hard.append({k: h[k] for k in ['hid', 'project', 'derived_from', 'pairing', 'question_type', 'question', 'answer',
                                   'evidence', 'hidden_knowledge', 'rubric']}
                | {'basis': [{k: b[k] for k in ['book_page', 'chapter', 'quote', 'intent_id']} for b in h['basis']]})

# knowledge points + probes
HQ = os.path.join(HERE, '..', 'knowledge')
knowledge = []
def load_json(path):
    return json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
KN_EN = load_json(os.path.join(HQ, 'knowledge', '_en.json'))          # English titles / summaries / topic names
DATA_EN = load_json(os.path.join(HERE, 'data_en.json'))               # English for the project descriptions
ARCH = os.path.join(HQ, 'knowledge_probes_archived.jsonl')
KLINES = [(l, False) for l in open(os.path.join(HQ, 'knowledge_probes.jsonl'), encoding='utf-8')] + \
         ([(l, True) for l in open(ARCH, encoding='utf-8')] if os.path.exists(ARCH) else [])
for line, is_archived in KLINES:
    k = json.loads(line)
    e = KN_EN.get('points', {}).get(k['kid'], {})
    en = {'title_en': e['title_en'], 'summary_en': e['summary_en']} if e.get('title') == k['title'] else {}   # stale if the title changed
    knowledge.append({f: k[f] for f in ['kid', 'level', 'ifc', 'needs', 'models', 'topic', 'title', 'summary', 'lod', 'priority', 'question', 'answer',
                                         'accept', 'mcq', 'rubric', 'basis', 'hard_qa']} | en | ({'archived': True} if is_archived else {}))

# model results (runs/qa_probes): seed-1 run with open answers, two more mcq seeds, flagship run
RUNS = os.path.join(HERE, '..', 'runs', 'qa_probes')
RUN_SETS = [('20261002-110039', True), ('20261002-110927', False), ('20261002-111156', False), ('20261002-111505', True)]
MODELS = [('opus', 'Claude Opus 5.5'), ('sol', 'GPT-6.1 Sol'), ('sonnet', 'Claude Sonnet 5.5'), ('gemini', 'Gemini 3.8 Flash'),
          ('luna', 'GPT-6 Luna'), ('jev', 'JEV')]
results = {}
KQ = {k['kid']: k['question'] for k in knowledge}
for run, first in RUN_SETS:
    f = os.path.join(RUNS, run, 'graded.jsonl')
    if not os.path.exists(f):
        continue
    for line in open(f, encoding='utf-8'):
        r = json.loads(line)
        q, a, g = r['question'], r['answer'], r['grade']
        if KQ.get(q['qid']) != q['text']:
            continue          # the id now belongs to another knowledge point (ids after the office block were renumbered)
        cell = results.setdefault(q['qid'], {}).setdefault(a['model'], {})
        if q['format'] == 'mcq':
            cell.setdefault('m', []).append(1 if g.get('correct') else 0)
            if first:
                i = 'ABCDEFGH'.find(a.get('choice') or '?')
                cell['mc'] = q['options'][i] if 0 <= i < len(q['options']) else ''
        else:
            text = (a.get('text') or '').strip()
            cell.update(o=g['label'], a=text[:700] + ('…' if len(text) > 700 else ''), nr=1 if g.get('needs_review') else 0)
LV = json.load(open(os.path.join(HQ, 'knowledge', '_levels.json'), encoding='utf-8'))

# rules pilot (rules/): knowledge rewritten as context → requirement, plus instances found in the IFC models
RULES_DIR = os.path.join(HERE, '..', 'rules')
def load_jsonl(path):
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()] if os.path.exists(path) else []
rules = [r for f in sorted(glob.glob(os.path.join(RULES_DIR, 'rules_*.jsonl'))) for r in load_jsonl(f)]
instances = [i for f in sorted(glob.glob(os.path.join(RULES_DIR, 'instances_*.jsonl'))) for i in load_jsonl(f)]
# rules × all graphs scan (rules/match_rules.py → rules/scan370_summary.json)
scan_path = os.path.join(RULES_DIR, 'scan370_summary.json')
scan = json.load(open(scan_path, encoding='utf-8')) if os.path.exists(scan_path) else None
scenarios = load_jsonl(os.path.join(RULES_DIR, 'scenarios.jsonl'))
if_concrete = load_jsonl(os.path.join(RULES_DIR, 'if_concrete.jsonl'))
rv_path = os.path.join(RULES_DIR, '_review.json')
review = json.load(open(rv_path, encoding='utf-8')) if os.path.exists(rv_path) else None
st_path = os.path.join(RULES_DIR, '_status.json')
rstatus = json.load(open(st_path, encoding='utf-8')) if os.path.exists(st_path) else None
dec_path = os.path.join(RULES_DIR, 'decisions.json')
decisions = json.load(open(dec_path, encoding='utf-8')) if os.path.exists(dec_path) else None
data = json.dumps(dict(base, hard=hard, knowledge=knowledge, results=results, models=MODELS, levels=LV['levels'], needs=LV['needs'],
                       topics_en=KN_EN.get('topics', {}), en=DATA_EN, rules=rules, instances=instances, scan=scan, decisions=decisions, rstatus=rstatus, scenarios=scenarios, review=review, if_concrete=if_concrete), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
assert '/*__DATA__*/null' in tpl
open(os.path.join(HERE, 'index.html'), 'w', encoding='utf-8').write(tpl.replace('/*__DATA__*/null', data))
print('site rebuilt:', len(rules), 'rules,', len(instances), 'instances,', len(hard), 'hard items,', sum(not k.get('archived') for k in knowledge), 'knowledge points +', sum(bool(k.get('archived')) for k in knowledge), 'archived,', len(results), 'points with results,',
      sum('title_en' in k for k in knowledge), 'with English')
