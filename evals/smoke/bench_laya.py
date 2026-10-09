"""Бенчмарк laya-multilingual на кейсах КТРУ. Запуск: python bench_laya.py evals/datasets/smoke_v0.json [cuda|cpu]"""
import json, os, sys, time
os.environ.setdefault("USE_TF", "0")
import laya, torch

data = json.load(open(sys.argv[1]))
device = sys.argv[2] if len(sys.argv) > 2 else "cuda"
G = data["groups"]
NONE = "НЕТ"

t = time.time()
agent = laya.load("convaiinnovations/laya", subfolder="multilingual", device=device)
print(f"load {time.time()-t:.1f}s device={device}", flush=True)

def predict(state, qs):
    t = time.perf_counter()
    r = agent.predict(state, qs)
    if device == "cuda":
        torch.cuda.synchronize()
    return r, (time.perf_counter() - t) * 1000

# разведка формата ответа
r, _ = predict("Молоток слесарный 400 г", {"q": {"type": "choice", "instructions": "Что это за товар?",
        "criteria": {"a": "Молоток", "b": "Топор", "c": "Стол"}}})
print(json.dumps(r, ensure_ascii=False, default=str)[:1500], flush=True)

def ans(r, name):
    a = r["answers"][name]
    return a

def probs(a):
    for k in ("probabilities", "probs", "distribution", "scores"):
        if k in a:
            return a[k]
    return {}

def choice_eval(k, with_none=True, desc=True):
    ok = 0; lat = []; rows = []
    for c in data["cases"]:
        cands = c["top20"][:k]
        crit = {f"o{i}": (f"{n} — {G[n]}" if desc else n) for i, n in enumerate(cands)}
        if with_none:
            crit["none"] = "ни одна из перечисленных позиций не подходит"
        q = {"g": {"type": "choice", "instructions": "К какой позиции каталога КТРУ относится этот товар?", "criteria": crit}}
        r, ms = predict(f"Товар: {c['text']}", q); lat.append(ms)
        a = ans(r, "g"); ch = a.get("choice")
        pred = NONE if ch == "none" else cands[int(ch[1:])]
        hit = pred in c["gold"]; ok += hit
        rows.append((hit, c["text"][:60], pred, a.get("confidence")))
    return ok, lat, rows

def noul_eval(k):
    """по одному бинарному вопросу на кандидата (choice из 2 — обход бага noul)"""
    ok = 0; lat = []
    for c in data["cases"]:
        cands = c["top20"][:k]
        qs = {f"q{i}": {"type": "choice", "instructions": f"Относится ли товар к позиции КТРУ «{n}» ({G[n]})?",
              "criteria": {"yes": "да, это именно такой товар", "no": "нет, это другой товар"}} for i, n in enumerate(cands)}
        r, ms = predict(f"Товар: {c['text']}", qs); lat.append(ms)
        py = []
        for i in range(len(cands)):
            a = ans(r, f"q{i}"); p = probs(a)
            py.append(p.get("yes") if isinstance(p, dict) and "yes" in p else (1.0 if a.get("choice") == "yes" else 0.0) * (a.get("confidence") or 1))
        best = max(range(len(cands)), key=lambda i: py[i])
        pred = cands[best] if py[best] >= 0.5 else NONE
        ok += pred in c["gold"]
    return ok, lat

def stat(lat):
    s = sorted(lat); return f"p50={s[len(s)//2]:.0f}ms p90={s[int(len(s)*.9)]:.0f}ms"

n = len(data["cases"])
tf1 = sum(c["top20"][0] in c["gold"] for c in data["cases"])
print(f"\nTF-IDF top1 (без 'НЕТ'): {tf1}/{n}")
for k in (5, 10, 20):
    ok, lat, rows = choice_eval(k)
    print(f"laya choice top{k}+НЕТ: {ok}/{n}  {stat(lat)}", flush=True)
    if k == 10:
        for h, t, p, cf in rows: print(f"   {'✓' if h else '✗'} {t:<60} → {p} ({cf})")
ok, lat, _ = choice_eval(10, desc=False)
print(f"laya choice top10 без ОКПД2-описаний: {ok}/{n}  {stat(lat)}")
ok, lat = noul_eval(10)
print(f"laya 10×да/нет батчем: {ok}/{n}  {stat(lat)}", flush=True)

ok = 0; lat = []
print("\nАтрибуты:")
for a in data["attrs"]:
    crit = {f"o{i}": v for i, v in enumerate(a["options"])}
    q = {"c": {"type": "choice", "instructions": f"{a['char']} товара «{a['group']}»?", "criteria": crit}}
    r, ms = predict(f"Товар: {a['text']}", q); lat.append(ms)
    x = ans(r, "c"); pred = a["options"][int(x["choice"][1:])]
    h = pred == a["gold"]; ok += h
    print(f"   {'✓' if h else '✗'} {a['text'][:45]:<45} {a['char'][:28]:<28} → {pred} (gold {a['gold']}, conf {x.get('confidence')})")
print(f"laya атрибуты: {ok}/{len(data['attrs'])}  {stat(lat)}")
if device == "cuda":
    print(f"VRAM peak {torch.cuda.max_memory_allocated()/2**20:.0f} MiB")
