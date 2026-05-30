import json, os, re, hashlib, sys
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI

client = OpenAI()  # real OPENAI_API_KEY, default base_url
MODEL = "gpt-4o-mini"

STOP = set("the a an and or of to in on for with at by from as is are was were be been "
           "this that these those it its their his her your you i we they he she my our "
           "what when where which who how why do does did had has have will would should "
           "could can about into over under more most than then them me us also if not no "
           "yes any some all each per via using used use".split())

def content_tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(t) > 2 and t not in STOP}

def gold_coverage(gold, ctx):
    g = content_tokens(gold)
    if not g: return 1.0
    c = content_tokens(ctx)
    return len(g & c) / len(g)

RUBRIC = """You audit why a long-term-memory QA system gave a WRONG answer even though a memory
derived from the gold turn was retrieved (turn_hit=1 proves provenance coverage, NOT that the
answer text survived extraction). Classify the failure into EXACTLY ONE label:

A = reasoning/evidence-use failure: the specific facts needed are PRESENT and faithful in the
    context, but the reader computed/aggregated/selected/grounded wrong (e.g. temporal
    arithmetic error, cross-session miscount/sum, picked a stale value though the update is
    present, gave a generic answer though the preference is present).
B = compression/fidelity/span-loss: the specific value/span needed to answer is ABSENT from the
    context. A memory about the topic is present, but extraction paraphrased/compressed away the
    exact fact, so the reader literally cannot read off the answer. (For derived answers like
    temporal math, the SOURCE facts being absent also counts as B; if the source facts ARE
    present and only the arithmetic is wrong, that is A.)
C = ordering/noise/conflict: the answer IS present but buried among many distractors or
    conflicting entries, and the reader latched onto a wrong but plausible nearby item.
D = unclear / possible judge false-negative: cannot tell, or the model response looks arguably
    correct or the gold is ambiguous.

Return ONLY compact JSON: {"label":"A|B|C|D","reason":"<=20 words"}"""

def classify(item):
    ctx = (item["context"] or "")[:80000]
    user = (f'QUESTION_TYPE: {item["type"]}\nQUESTION: {item["question"]}\n'
            f'GOLD_ANSWER: {item["gold"]}\nMODEL_ANSWER(wrong): {item["hypothesis"]}\n\n'
            f'RETRIEVED_CONTEXT:\n{ctx}')
    try:
        r = client.chat.completions.create(
            model=MODEL, temperature=0, max_tokens=120,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": RUBRIC},
                      {"role": "user", "content": user}])
        out = json.loads(r.choices[0].message.content)
        lab = out.get("label", "D").strip().upper()[:1]
        return lab if lab in "ABCD" else "D", out.get("reason", "")
    except Exception as e:
        return "D", f"ERR:{e}"

for run in ["task18-flat-500", "task19-retain-500"]:
    items = json.load(open(f"runs/_hit1wrong_{run}.json"))
    for it in items:
        it["cov"] = gold_coverage(it["gold"], it["context"])
    with ThreadPoolExecutor(max_workers=8) as ex:
        labs = list(ex.map(classify, items))
    for it, (lab, reason) in zip(items, labs):
        it["label"], it["reason"] = lab, reason
    json.dump([{k: it[k] for k in ("qid","type","cov","label","reason","gold","hypothesis")}
               for it in items], open(f"runs/_hit1_triage_{run}.json", "w"), indent=1)
    from collections import Counter
    cnt = Counter(it["label"] for it in items)
    low = sum(1 for it in items if it["cov"] < 0.5)
    print(f"=== {run}: n={len(items)} hit=1 wrong ===")
    for L in "ABCD":
        print(f"   {L}: {cnt.get(L,0)}")
    print(f"   [det cross-check] gold-term coverage <50% in context: {low}/{len(items)}")
    # label x type
    bt = {}
    for it in items:
        bt.setdefault(it["type"], Counter())[it["label"]] += 1
    for t, c in sorted(bt.items()):
        print(f"   {t:28s} " + " ".join(f"{L}={c.get(L,0)}" for L in "ABCD"))

# judge prompt hash
import importlib.util
spec = importlib.util.spec_from_file_location("judge", "longmemeval_harness/judge.py")
j = importlib.util.module_from_spec(spec); spec.loader.exec_module(j)
blob = j.JUDGE_SYSTEM + j._ABSTENTION + j._PREFERENCE + j._DEFAULT + "".join(sorted(j._NOTES.values()))
print("\nJUDGE_PROMPT_SHA256:", hashlib.sha256(blob.encode()).hexdigest())
