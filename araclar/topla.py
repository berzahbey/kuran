#!/usr/bin/env python3
"""Bir sure için Arapça metin, kelime morfolojisi, tüm mealler ve tüm tefsirleri toplar.
Kullanım: python3 topla.py <sure_no> <cikti_klasoru>"""
import json, sys, os, urllib.request, concurrent.futures as cf
S = int(sys.argv[1]); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
RAW = "https://raw.githubusercontent.com"
def get(url, tries=3):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r: return r.read().decode()
        except Exception as e: err = e
    return None
# 1) morfoloji
morf = [l.split("\t") for l in get(f"{RAW}/mustafa0x/quran-morphology/master/quran-morphology.txt").splitlines() if l.startswith(f"{S}:")]
# 2) mealler (sure bazında)
eds = json.loads(get(f"{RAW}/fawazahmed0/quran-api/1/editions.json"))
def meal(item):
    k, v = item
    t = get(f"{RAW}/fawazahmed0/quran-api/1/editions/{v["name"]}/{S}.json")
    if not t: return None
    try: ch = json.loads(t)["chapter"]
    except Exception: return None
    return {"id": v["name"], "dil": v["language"], "yazar": v["author"], "ayetler": {c["verse"]: c["text"] for c in ch}}
with cf.ThreadPoolExecutor(32) as ex: mealler = [m for m in ex.map(meal, eds.items()) if m]
arapca = next((m for m in mealler if m["id"] == "ara-quranuthmanihaf"), mealler[0])["ayetler"]
n = len(arapca)
# 3) tefsirler (ayet bazında)
tef_eds = json.loads(get(f"{RAW}/spa5k/tafsir_api/main/tafsir/editions.json"))
def tefsir(args):
    e, a = args
    t = get(f"{RAW}/spa5k/tafsir_api/main/tafsir/{e['slug']}/{S}/{a}.json")
    try: return e["slug"], a, json.loads(t)["text"]
    except Exception: return e["slug"], a, None
tef = {}
with cf.ThreadPoolExecutor(48) as ex:
    for slug, a, txt in ex.map(tefsir, [(e, a) for e in tef_eds for a in range(1, n+1)]):
        if txt: tef.setdefault(str(a), {})[slug] = txt
meta = {e["slug"]: {"dil": e.get("language_name"), "yazar": e.get("author_name"), "ad": e.get("name")} for e in tef_eds}
json.dump({"sure": S, "arapca": arapca, "morfoloji": morf, "mealler": mealler,
           "tefsirler": tef, "tefsir_meta": meta}, open(f"{OUT}/sure_{S:03d}.json", "w"), ensure_ascii=False)
print(f"sure {S}: {n} ayet, {len(mealler)} meal, {len({s for d in tef.values() for s in d})} tefsir, {len(morf)} morfoloji satırı")
