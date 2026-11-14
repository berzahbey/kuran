# Eski kelime tercihleri

Zahir'in mealindeki yeni ve öz Türkçe kelimeleri, Hayrat Osmanlıca meali çizgisindeki Arapça kökenli karşılıklarıyla değiştirir.
Örnekler: andolsun → yemin olsun, ad → isim, toplum → kavim, elçi → resul, çok bağışlayandır → Gafûr'dur.

- `kurallar.py`: kelime ve kök tabloları. Yeni bir tercih buraya eklenir.
- `motor.py`: ek uyumu (ünlü uyumu, kaynaştırma, "X et-" fiilleri).
- `donustur.py`: ifade kuralları (yemin, esmâ, ortak koşanlar...) ve çalıştırıcı.
- `lemma.json`: her ayetin Arapça lemma ve kökleri. Koşullu kurallar bunlara bakar (yoksul → miskin/fakir, dost → velî, uyarmak → inzar). `python lemma_kur.py /veri/kuran.db` ile yeniden üretilir.

Çalıştırma: `python donustur.py` → `degisen.json` ve `ciftler.txt` (eski → yeni kelime çiftleri) yazar; mealler/zahir.json'u değiştirmez.
