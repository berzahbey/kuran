# Dedplay Kur'ân-ı Kerîm Çalışma

<img src="app/static/ikon.png" width="96" alt="ikon">

Merkezinde Kur'an-ı Kerîm'in olduğu, tüm meal, tefsir, hadis ve lügat çalışmalarına ulaşılabilen kişisel kaynak ve çalışma platformu (ticari olmayan proje).

## Ana gövde: yalın meal
Uygulama açılınca okunan metin **en yalın Türkçe meal**dir. Uzun açıklama gereken yerlerde numara vardır, numaraya dokununca dipnot açılır. Arapça aslı üstteki **ع Arapça** düğmesiyle açılıp kapanır (tercih hatırlanır). E-kitap (EPUB) da aynı meali verir; istenirse Arapça aslı eklenir.

### Türkçe ⇄ Osmanlıca
Başlıktaki **Türkçe ⇄ عثمانلیجه** düğmesi ana meali Osmanlıcaya çevirir (dipnotlar dahil). Osmanlıca metin Zahir'in **osmanlica-cevirici** servisinden gelir (Hayrat imlâsı):
- Değişmemiş ayetler: `mealler/zahir_osm.json` (mealin tamamı çeviriciden toplu geçirildi).
- Onaylanan/düzenlenen ayetler: uygulama Türkçe metni kendiliğinden çeviriciye gönderir (`OSM_CEVIRICI_URL`, varsayılan `http://host.docker.internal:8089`) ve sonucu saklar.
- Çeviricinin hataları denetlenip düzeltilir; düzeltilmiş Osmanlıca `onayli/sure_XXX.json` içinde `meal_osm` / `dipnotlar_osm` olarak durur (ör. Kalem).
E-Kitap'ta "Osmanlıca" seçilirse kitap Osmanlıca basılır (Amiri fontu gömülü).

## Bir ayete tıklayınca: çalışma paneli
Panelde ayetin Arapçası ve yalın meali (✎ ile düzenlenir), altında 5 bölüm:

| Bölüm | İçerik |
|---|---|
| **Kelime & Lügat** | Her kelimenin kökü, kalıbı ve i'râbı Türkçe terimlerle. Köke tıklayınca Lane lügat maddesi (Lisânü'l-Arab, Tâc, Kâmûs, Sıhâh derlemesi) ve kökün Kur'an'daki tüm geçişleri. Kıraat farkı varsa (8 rivayet) burada. |
| **Mealler** | "Herkes böyle mi anlamış?" Tüm mealler yan yana: ortak anlam, ayrışan kelime tercihleri (kaç meal hangisini seçmiş), parantez içi eklemeler, benzer çizgideki meal grupları, renkli vurgular. Türkçe, İngilizce, Arapça vb.; ~90 dilde 492 meal tek tıkla. |
| **Tefsir & İniş** | Üstte nerede indiği (Mekkî/Medenî), iniş sırası, sebeb-i nüzûl (Vâhidî + rivâyet tefsirleri). Altında en eskiden günümüze 123 tefsir; türe (rivâyet, dirâyet, lügat/i'râb, işârî, kıraat, modern) ve dile göre süzülür. |
| **Hadis** | Kütüb-i Sitte + Muvatta (Arapça, Türkçe, İngilizce; ~100 bin metin). Ayetin metnini içeren rivayetler otomatik bağlanır. |
| **Notlarım** | Ayet veya sure bazında etiketli notlar. Tüm notlar aranır, Markdown olarak dışa aktarılır. Tefsirden alıntıyla not alınabilir. |

Klavye: ↑ ↓ ayetler arası, Esc kapat. Arama kutusu: Arapça, Türkçe veya `68:4` gibi ayet numarası.

## Kurulum (dedplay / ZimaOS)
1. ZimaOS → App Store → **Custom Install** → **Import** → bu depodaki `docker-compose.yml` içeriğini yapıştırın → Install.
   Komut satırından: `curl -O https://raw.githubusercontent.com/berzahbey/kuran/main/docker-compose.yml && docker compose up -d`
2. `http://dedplay:8120` açın. İlk açılışta tüm külliyat arka planda iner (~20 dk, ~2.3 GB). Durum: **Kaynaklar**.
3. İlk derlemeden sonra GitHub'da **Packages → kuran → Package settings → Change visibility → Public** yapın (yoksa sunucu imajı indiremez).

**Güncelleme:** `main`'e her gönderimde GitHub Actions yeni imajı `ghcr.io/berzahbey/kuran:latest` olarak derler.
Sunucuda `docker compose pull && docker compose up -d` (ZimaOS'ta uygulamanın "Update" düğmesi). Veriler `/DATA/AppData/kuran-calisma/veri` içinde kalır.

## Kaynaklar yerelde, eksikler internetten
Her şey uygulamanın kendi veritabanındadır, internetsiz çalışır. İnmemiş bir şey açılırsa o an internetten çekilir ve kaydedilir.

## Mealler
- **Zahir'in meali** (`mealler/zahir.json`): ana gövdenin temeli. Onaylı/yeni yalın meal olmayan her ayette okunan metin budur. Parantez içindeki Arapça çeviriyazılar çıkarıldı, Türkçe açıklamalar korundu. Standart numaralamadan ayrıldığı 6 yerde (iki kısa ayetin birlikte çevrildiği yerler) standart numaraya hizalandı.
- **Osmanlıca meal (OCR taslağı)** (`mealler/osmanlica_ocr.json`): taranmış 605 sayfalık PDF'ten OCR ile çıkarıldı; ayetlerin ~%83'ü ayrı, kalanı önceki ayetle birlikte. Her ayette "kitapta s. N" ile kitabın aslı açılır; bunun için PDF'i sunucuda `veri/ozel/Kuran_Osmanlica_Meal.pdf` olarak koyun.
- Hayrat Osmanlıca meali: ayet resimleri `mealler/osm-ocr/SSS_AAA.webp` olarak depoda; PDF gerekmez.
- Yeni meal eklemek: aynı biçimde bir JSON'u `mealler/` (depo) veya `veri/ozel/` (sunucu) klasörüne koymak yeterli.

## Meal
Uygulamanın meali Zahir'in mealidir (`mealler/zahir.json`, Osmanlıcası `mealler/zahir_osm.json`). Yapay zekâ meal yazmaz.
- **İnceleme:** Sure başlığındaki **inceleme dosyası ⇩** ile surenin JSON'unu indirin; düzeltilmiş dosya `onayli/sure_XXX.json` olarak depoya eklenir.
- **Onay:** Uygulama güncellenince `onayli/` klasöründeki dosyaları kendiliğinden yükler. Elle yüklemek için: **Kaynaklar → Meal dosyası → içe aktar**.

## Yapay zekâ (isteğe bağlı)
Yalnız çeviri için kullanılır (ör. nüzul rivayetlerinin Türkçesi). `docker-compose.yml` içinde `YZ_ANAHTAR`'a ücretsiz bir anahtar girin (ör. https://aistudio.google.com → *Get API key*).
Desteklenenler: Gemini (varsayılan), OpenAI uyumlu her uç nokta (OpenRouter, Groq, Cerebras, yerel Ollama), Anthropic.

## Veri kaynakları
- Arapça metin, 8 kıraat, 492 meal: github.com/fawazahmed0/quran-api
- Morfoloji/kök: github.com/mustafa0x/quran-morphology (Quranic Arabic Corpus tabanlı)
- Lügat: Lane, *An Arabic-English Lexicon*: github.com/laneslexicon/xml (kamu malı)
- Tefsirler: github.com/spa5k/tafsir_api
- Hadisler: github.com/fawazahmed0/hadith-api
- Font: Amiri Quran (SIL OFL)

Mealler ve modern tefsirlerin bir kısmı telif hakkına tabidir; uygulama kişisel çalışma içindir.

## Depo yapısı
- `app/`: uygulama (FastAPI + SQLite + web arayüzü), `kur.py` veri kurulumu, `kitap.py` EPUB, `yz.py` yapay zekâ sağlayıcıları
- `onayli/`: Claude ile incelenip onaylanmış yalın mealler (`sure_068.json` …); uygulama kendiliğinden yükler
- `araclar/`: komut satırı araçları
