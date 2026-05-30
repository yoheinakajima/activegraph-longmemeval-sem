import sqlite3, json, os, math, hashlib

def load(r):
    c = sqlite3.connect(f'runs/{r}/store.sqlite'); c.row_factory = sqlite3.Row
    d = {x['question_id']: dict(x) for x in c.execute('select * from questions').fetchall()}
    c.close(); return d

def mcnemar(b, c):
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
    return min(p, 1.0)

det = load('full-s-sonnet'); flat = load('task18-flat-500')
ag = load('task18-agentic-500'); ret = load('task19-retain-500')

print('=== ITEM 1: matched-hit subset (det=full-s-sonnet vs flat=task18-flat-500) ===')
ids = set(det) & set(flat)
sub = [q for q in ids if not det[q]['is_abstention'] and not flat[q]['is_abstention']
       and det[q]['turn_hit'] == 1 and flat[q]['turn_hit'] == 1]
nd = sum(det[q]['judge_correct'] for q in sub); nf = sum(flat[q]['judge_correct'] for q in sub)
b = sum(1 for q in sub if det[q]['judge_correct'] and not flat[q]['judge_correct'])
c = sum(1 for q in sub if flat[q]['judge_correct'] and not det[q]['judge_correct'])
print(f'  n(both answerable & both turn_hit=1) = {len(sub)}')
print(f'  det  acc = {nd}/{len(sub)} = {nd/len(sub):.3f}')
print(f'  flat acc = {nf}/{len(sub)} = {nf/len(sub):.3f}')
print(f'  McNemar b(det-correct, flat-wrong)={b}  c(flat-correct, det-wrong)={c}  net(flat-det)={c-b}  p={mcnemar(b,c):.4f}')
print()

print('=== ITEM 2: abstention accuracy (is_abstention=1) ===')
for name, d in [('full-s-sonnet', det), ('task18-flat-500', flat),
                ('task18-agentic-500', ag), ('task19-retain-500', ret)]:
    ab = [q for q in d if d[q]['is_abstention']]
    cor = sum(d[q]['judge_correct'] for q in ab); fp = len(ab) - cor
    print(f'  {name:22s} n={len(ab)} correct={cor} acc={cor/len(ab):.3f} failed_to_abstain(answered)={fp}')
print()

print('=== ITEM 5: ssa flat-correct & retain-wrong ===')
ssa = [q for q in (set(flat) & set(ret)) if flat[q]['question_type'] == 'single-session-assistant']
b_set = [q for q in ssa if flat[q]['judge_correct'] and not ret[q]['judge_correct']]
c_cnt = sum(1 for q in ssa if ret[q]['judge_correct'] and not flat[q]['judge_correct'])
print(f'  ssa n={len(ssa)}  c(retain-correct, flat-wrong)={c_cnt}')
print(f'  b set (flat-correct, retain-wrong) = {b_set}')
print()

print('=== ITEM 6: write/read cost (store + file only) ===')
def agg(d, k):
    vs = [d[q][k] for q in d if d[q][k] is not None]
    return sum(vs), (sum(vs)/len(vs) if vs else 0)
for name, d in [('task18-flat-500', flat), ('task19-retain-500', ret)]:
    sz = os.path.getsize(f'runs/{name}/store.sqlite')
    rp_s, rp_m = agg(d, 'reader_prompt_tokens')
    rc_s, rc_m = agg(d, 'reader_completion_tokens')
    cl_s, cl_m = agg(d, 'ingest_n_claims')
    ob_s, ob_m = agg(d, 'ingest_n_obs')
    print(f'  {name}: store.sqlite={sz/1e6:.1f}MB')
    print(f'    reader_prompt(context) tokens: sum={rp_s:,} mean={rp_m:.0f}')
    print(f'    reader_completion(output) tokens: sum={rc_s:,} mean={rc_m:.1f}')
    print(f'    ingest_n_claims (final, post-consolidation): sum={cl_s:,} mean={cl_m:.1f}')
    print(f'    ingest_n_obs: sum={ob_s:,} mean={ob_m:.1f}')
print('  NOT recorded in store/manifest: extractor calls, extractor in/out tokens,')
print('  embedding calls/tokens, pre-consolidation memory count (only final n_claims kept).')
print()

print('=== ITEM 3 data: hit=1 evidence-present WRONG answerable items (flat & retain) ===')
for name, d in [('task18-flat-500', flat), ('task19-retain-500', ret)]:
    wrong = [q for q in d if not d[q]['is_abstention'] and d[q]['turn_hit'] == 1 and not d[q]['judge_correct']]
    print(f'  {name}: {len(wrong)} hit=1 wrong')
    rows = []
    for q in wrong:
        r = d[q]
        rows.append({'qid': q, 'type': r['question_type'], 'question': r['question'],
                     'gold': r['gold_answer'], 'hypothesis': r['hypothesis'],
                     'context': r['assembled_context']})
    json.dump(rows, open(f'runs/_hit1wrong_{name}.json', 'w'))
print()

print('=== ITEM 7: reproduction metadata ===')
for name in ['full-s-sonnet', 'task18-flat-500', 'task19-retain-500', 'scaffold-50', 'pref-extract-s']:
    m = json.load(open(f'runs/{name}/manifest.json'))
    print(f'  -- {name}')
    print('     keys:', sorted(m.keys()))
