"""Yalın meal EPUB3 üreticisi: her ayette Arapça aslı + yalın Türkçe meal, açılır (popup) dipnotlar."""
import html, io, os, re, uuid, zipfile, datetime

FONT = os.path.join(os.path.dirname(__file__), "static", "font", "AmiriQuran.ttf")
CSS = """@font-face{font-family:"AmiriQuran";src:url(AmiriQuran.ttf)}
body{font-family:serif;line-height:1.6;margin:1em}
h1{text-align:center;font-size:1.5em;margin:1em 0 .2em}
h1 .ar{display:block;font-family:"AmiriQuran",serif;font-size:1.1em;margin-bottom:.2em}
.besmele{text-align:center;margin:0 0 1.6em}
.besmele .ar{display:block;font-family:"AmiriQuran",serif;font-size:1.35em;line-height:2}
.besmele .tr{font-style:italic}
.ayet{margin:0 0 1.3em}
p.ar{font-family:"AmiriQuran",serif;font-size:1.45em;text-align:right;line-height:2.1;margin:0 0 .25em}
p.tr{margin:0;text-align:justify}
p.tr.sade{margin:0 0 .7em}
.no{font-family:"AmiriQuran",serif}
a.noteref{vertical-align:super;font-size:.7em;text-decoration:none;font-weight:bold}
aside.dipnot{font-size:.9em;margin:.6em 0}
aside.dipnot a.geri{text-decoration:none;font-weight:bold}
.notlar{margin-top:2.5em;border-top:1px solid #999;padding-top:.5em}
.notlar h2{font-size:1em;font-weight:normal}"""

AR_RAKAM = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
BESMELE_AR = "بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ"

def _xhtml(baslik, govde):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops" lang="tr" xml:lang="tr"><head><meta charset="utf-8"/>'
            f'<title>{html.escape(baslik)}</title><link rel="stylesheet" href="stil.css"/></head><body>{govde}</body></html>')

def epub_yap(sureler, baslik="Kur'ân-ı Kerîm — Yalın Türkçe Meal", yazar="Dedplay", arapca=True):
    """sureler: [{"s":68, "ad":"Kalem", "ad_ar":"القلم", "ayetler":[{"a":1,"arapca":"...","meal":"...[1]..."}], "dipnotlar":{"1":"..."}}]"""
    bolumler = []
    for d in sureler:
        s = d["s"]; fid = f"s{s:03d}"; paras = []
        for ay in d["ayetler"]:
            t = html.escape(ay.get("meal") or "")
            t = re.sub(r"\[(\d+)\]", lambda m: f'<a epub:type="noteref" class="noteref" id="{fid}-r{m[1]}" href="#{fid}-n{m[1]}">{m[1]}</a>', t)
            ar = html.escape(ay["arapca"])
            # Fâtiha'nın 1. ayeti besmeledir; ayrı besmele basılmaz
            if arapca:
                paras.append(f'<div class="ayet"><p class="ar" lang="ar" dir="rtl">{ar} <span class="no">﴿{str(ay["a"]).translate(AR_RAKAM)}﴾</span></p><p class="tr">{t}</p></div>')
            else:
                paras.append(f'<p class="tr sade">{t}</p>')
        notlar = "".join(f'<aside epub:type="footnote" class="dipnot" id="{fid}-n{k}"><p><a class="geri" href="#{fid}-r{k}">{k}.</a> {html.escape(v)}</p></aside>'
                         for k, v in sorted(d.get("dipnotlar", {}).items(), key=lambda x: int(x[0])))
        besm = "" if s in (1, 9) else (f'<div class="besmele">' + (f'<span class="ar" lang="ar" dir="rtl">{BESMELE_AR}</span>' if arapca else "") + '<span class="tr">Rahmân ve Rahîm olan Allah\'ın adıyla</span></div>')
        govde = (f'<section epub:type="chapter"><h1><span class="ar" lang="ar" dir="rtl">{html.escape(d.get("ad_ar",""))}</span>'
                 f'{html.escape(d["ad"])} Sûresi</h1>{besm}{"".join(paras)}'
                 + (f'<section class="notlar" epub:type="footnotes"><h2>Dipnotlar</h2>{notlar}</section>' if notlar else "") + "</section>")
        bolumler.append((fid, f'{d["ad"]} Sûresi', _xhtml(d["ad"], govde)))
    bid = str(uuid.uuid4()); zaman = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    nav = _xhtml("İçindekiler", '<nav epub:type="toc"><h1>İçindekiler</h1><ol>' +
                 "".join(f'<li><a href="{b[0]}.xhtml">{html.escape(b[1])}</a></li>' for b in bolumler) + "</ol></nav>")
    opf = (f'<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bid" xml:lang="tr">'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bid">urn:uuid:{bid}</dc:identifier>'
           f'<dc:title>{html.escape(baslik)}</dc:title><dc:creator>{html.escape(yazar)}</dc:creator><dc:language>tr</dc:language><dc:language>ar</dc:language>'
           f'<meta property="dcterms:modified">{zaman}</meta></metadata><manifest>'
           '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="css" href="stil.css" media-type="text/css"/>'
           '<item id="font" href="AmiriQuran.ttf" media-type="font/ttf"/>'
           + "".join(f'<item id="{b[0]}" href="{b[0]}.xhtml" media-type="application/xhtml+xml"/>' for b in bolumler)
           + '</manifest><spine>' + "".join(f'<itemref idref="{b[0]}"/>' for b in bolumler) + "</spine></package>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>', compress_type=zipfile.ZIP_DEFLATED)
        for ad, icerik in [("content.opf", opf), ("nav.xhtml", nav), ("stil.css", CSS)] + [(b[0] + ".xhtml", b[2]) for b in bolumler]:
            z.writestr("OEBPS/" + ad, icerik, compress_type=zipfile.ZIP_DEFLATED)
        z.write(FONT, "OEBPS/AmiriQuran.ttf", compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()
