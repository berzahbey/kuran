# -*- coding: utf-8 -*-
"""Eski (Arapça kökenli) kelime tercihleri motoru.
Zahir'in mealindeki yeni/öz Türkçe kelimeleri Hayrat çizgisindeki karşılıklarıyla değiştirir.
Kurallar: KOK (isim/fiil kökü dönüşümleri, ek uyumu otomatik), IFADE (kalıp regex), KOSUL (Arapça köke bağlı)."""
import re, json

ON = set("eiöüî")          # ön ünlüler
YUV = set("oöuüû")          # yuvarlak
UNLU = set("aeıioöuüâîû")
SERT = set("çfhkpsştÇFHKPSŞT")

def son_unlu(s):
    for ch in reversed(s):
        if ch in UNLU: return ch
    return 'e'

def uyum(ek, onceki):
    """ek'in ünlülerini 'onceki' ünlüye göre uyumlar."""
    on = onceki in ON; yv = onceki in YUV
    out = []
    i = 0
    while i < len(ek):
        ch = ek[i]
        if ek[i:i+3] == 'yor':
            out.append('yor'); on, yv = False, True; i += 3; continue
        if ek[i:i+3] == 'ken' and i > 0:
            out.append('ken'); i += 3; continue
        if ch in 'ae':
            ch = 'e' if on else 'a'; yv = False
        elif ch in 'ıiuü':
            ch = ('ü' if yv else 'i') if on else ('u' if yv else 'ı')
        out.append(ch); i += 1
    return ''.join(out)

def bas_ses(ek, kok):
    """d/t, c/ç uyumu"""
    if not ek: return ek
    sert = kok[-1] in SERT
    if ek[0] in 'dt': return ('t' if sert else 'd') + ek[1:]
    if ek[0] in 'cç': return ('ç' if sert else 'c') + ek[1:]
    return ek

def isim(yeni, ek, unlu=None, dusen=None, yumusak=None, eski_unlu_son=False):
    """yeni: yeni kök; ek: eski kelimeden kalan ek (ham).
    unlu: yeni kökün uyum ünlüsü (verilmezse son ünlü). dusen: ünlü düşmeli hali (kavm). yumusak: ünlüyle başlayan ekten önceki hali (şahid)."""
    u = unlu or son_unlu(yeni)
    yeni_unlu_son = yeni[-1] in UNLU
    if eski_unlu_son and not yeni_unlu_son:
        # kaynaştırma harfi düşer: süre-ye → müddet-e, süre-si → müddet-i, süre-nin → müddet-in
        if len(ek) >= 2 and ek[0] in 'ysn' and ek[1] in UNLU:
            ek = ek[1:]
    if not eski_unlu_son and yeni_unlu_son:
        if ek and ek[0] in UNLU:
            # 3. tekil iyelik/belirtme/yönelme: kaynaştırma gerekir — bunlar elle
            return None
    ek2 = uyum(ek, u)
    if ek2 and ek2[0] in UNLU:
        kok = dusen or yumusak or yeni
    else:
        kok = yeni
        ek2 = bas_ses(ek2, kok)
    return kok + ek2

def et_fiil(on_ek, ek, kok_unlu_son, edil='edil'):
    """'X et-' fiili. ek: eski fiil kökünden sonraki kısım."""
    e = ek
    if kok_unlu_son and e[:1] == 'n':
        # edilgen: yalanla-n-dı → tekzip edil-di ; yalanla-n-ır → edil-ir
        rest = e[1:]
        if rest[:2] in ('ır','ir','ur','ür'):
            rest = 'ir' + rest[2:]
        r2 = uyum(rest, 'i')
        if r2 and r2[0] not in UNLU: r2 = bas_ses(r2, 'edil')
        return on_ek + ' ' + edil + r2
    if kok_unlu_son and e[:1] == 'r':
        e = 'er' + e[1:]             # geniş zaman: yalanla-r → ed-er
    elif not kok_unlu_son and re.match(r'^[aeıiuü]r([^aeıiuü]|$)', e):
        e = 'er' + e[2:]
    elif not kok_unlu_son and re.match(r'^[ıiuü]l', e):
        r2 = uyum(e[2:], 'i')
        if r2 and r2[0] not in UNLU: r2 = bas_ses(r2, 'edil')
        return on_ek + ' ' + edil + r2
    if len(e) >= 2 and e[0] == 'y' and e[1] in UNLU:
        e = e[1:]
    if e[:1] in UNLU:
        return on_ek + ' ed' + uyum(e, 'e')
    e2 = uyum(e, 'e')
    return on_ek + ' et' + bas_ses(e2, 'et')
