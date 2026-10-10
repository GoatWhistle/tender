"""Laya-multilingual: выбор шаблона среди top-3/top-5 гибрида. Запуск: python bench_laya_hyb.py smoke_v0.json (GPU)."""
import json, os, sys, time
os.environ.setdefault("USE_TF", "0")
import laya, torch
D = json.load(open(sys.argv[1])); NONE = "НЕТ"; cases = D["cases"]
agent = laya.load("convaiinnovations/laya", subfolder="multilingual", device="cuda")
INSTR = {"plain": "К какой позиции каталога КТРУ относится этот товар?",
         "hint": "Какой вид товара описан? Выбери наиболее точную позицию каталога."}
def run(k, none, instr, show=False):
    ok = 0; lat = []; rows = []
    for c in cases:
        cands = c["hyb10"][:k]
        crit = {f"o{i}": n for i, n in enumerate(cands)}
        if none: crit["none"] = "ни одна из перечисленных позиций не подходит"
        t = time.perf_counter()
        r = agent.predict(f"Товар: {c['text']}", {"g": {"type": "choice", "instructions": INSTR[instr], "criteria": crit}})
        torch.cuda.synchronize(); lat.append((time.perf_counter() - t) * 1000)
        a = r["answers"]["g"]; ch = a["choice"]
        pred = NONE if ch == "none" else cands[int(ch[1:])]
        h = pred in c["gold"]; ok += h
        rows.append((h, c, pred, a["confidence"], cands[0] in c["gold"]))
    s = sorted(lat)
    print(f"top{k:<2} НЕТ={'да ' if none else 'нет'} instr={instr:<5}: {ok}/{len(cases)}  p50={s[len(s)//2]:.0f}ms", flush=True)
    if show:
        for h, c, p, cf, hb in rows:
            print(f"   {'✓' if h else '✗'}{'(гибрид ✓)' if hb and not h else '(гибрид ✗)' if h and not hb else '          '} {cf:.2f} {c['text'][:46]:<46} → {p[:40]}")
    return rows
hyb1 = sum(c["hyb10"][0] in c["gold"] for c in cases)
print(f"гибрид top1 без Laya: {hyb1}/{len(cases)}")
for k in (3, 5):
    for none in (False, True):
        for instr in ("plain", "hint"):
            run(k, none, instr, show=(k == 5 and not none and instr == "plain"))
