"""Поиск шаблона КТРУ: TF-IDF, bge-m3 (llama.cpp /v1/embeddings) и их RRF-гибрид.

Запуск: python bench_emb.py evals/datasets/smoke_v0.json http://<host>:8089/v1/embeddings
Дописывает в датасет поле hyb10 — top-10 гибрида (вход для bench_laya_hyb.py).
"""
import json, sys, time, urllib.request
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

D = json.load(open(sys.argv[1])); URL = sys.argv[2]
G = D["groups"]; names = list(G); NONE = "НЕТ"
cases = D["cases"]

def bge(texts, bs=64):
    out = []
    for i in range(0, len(texts), bs):
        req = urllib.request.Request(URL, json.dumps({"input": texts[i:i+bs]}).encode(), {"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req))
        out += [d["embedding"] for d in sorted(r["data"], key=lambda d: d["index"])]
    a = np.array(out, dtype=np.float32); return a / np.linalg.norm(a, axis=1, keepdims=True)

vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
Xt = vec.fit_transform([f"{n} {n} {G[n]}".lower() for n in names])
def tfidf_scores(q): return (vec.transform([q.lower()]) @ Xt.T).toarray()[0]

def evaluate(label, S):  # S: [n_cases, n_groups]
    r = {1: 0, 5: 0, 10: 0}; pos = [c for c in cases if c["gold"] != [NONE]]
    for c, s in zip(cases, S):
        if c["gold"] == [NONE]: continue
        top = [names[i] for i in s.argsort()[::-1][:10]]
        for k in r: r[k] += any(g in top[:k] for g in c["gold"])
    print(f"{label:<42} R@1 {r[1]:>2}/{len(pos)}  R@5 {r[5]:>2}/{len(pos)}  R@10 {r[10]:>2}/{len(pos)}")
    return S

def rrf(*Ss, k=60):
    out = np.zeros_like(Ss[0])
    for S in Ss:
        rank = np.argsort(np.argsort(-S, axis=1), axis=1)
        out += 1 / (k + rank)
    return out

Q = [c["text"] for c in cases]
St = np.array([tfidf_scores(q) for q in Q]); evaluate("TF-IDF char 3-5", St)

t = time.time(); Gb_name = bge(names); Gb_full = bge([f"{n}. {G[n]}" for n in names]); tg = time.time() - t
t = time.time(); Qb = bge(Q); tq = (time.time() - t) / len(Q) * 1000
Sb = evaluate("bge-m3 (название)", Qb @ Gb_name.T)
Sbf = evaluate("bge-m3 (название + ОКПД2)", Qb @ Gb_full.T)
Sbm = evaluate("bge-m3 max(название, +ОКПД2)", np.maximum(Qb @ Gb_name.T, Qb @ Gb_full.T))
evaluate("RRF: TF-IDF + bge-m3", rrf(St, Sbm))
print(f"   bge-m3: индекс 2×{len(names)} групп {tg:.1f}s, запрос {tq:.0f} мс (по сети, по одному)")

print("\nbge-m3 top-3 и косинус top-1 (для порога «нет в КТРУ»):")
for c, s in zip(cases, Sbm):
    o = s.argsort()[::-1][:3]; top = names[o[0]]
    mark = "∅" if c["gold"] == [NONE] else ("✓" if top in c["gold"] else ("~" if any(names[i] in c["gold"] for i in o) else "✗"))
    print(f" {mark} {s[o[0]]:.3f} {c['text'][:48]:<48} → {' | '.join(names[i][:28] for i in o)}")

H = rrf(St, Sbm)
for c, s in zip(cases, H):
    c["hyb10"] = [names[i] for i in s.argsort()[::-1][:10]]
json.dump(D, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print(f"hyb10 записан в {sys.argv[1]}")
