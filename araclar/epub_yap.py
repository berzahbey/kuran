#!/usr/bin/env python3
"""Onaylı meal JSON'undan açılır (popup) dipnotlu EPUB3 üretir. Kullanım: epub_yap.py <json...> -o kitap.epub"""
import json, re, sys, zipfile, uuid, html
args=sys.argv[1:]; out=args[args.index('-o')+1]; files=[a for a in args if a.endswith('.json')]
CSS="""body{font-family:serif;line-height:1.6;margin:1em}h1{text-align:center;font-size:1.5em;margin:1em 0 .3em}
.besmele{text-align:center;font-style:italic;margin:0 0 1.5em}p.ayet{text-indent:0;margin:0 0 .8em;text-align:justify}
a.noteref{vertical-align:super;font-size:.7em;text-decoration:none;font-weight:bold}
aside.dipnot{font-size:.9em;margin:.6em 0;border-top:1px solid #ccc;padding-top:.4em}
aside.dipnot a.geri{text-decoration:none}
.notlar{margin-top:2.5em} .notlar h2{font-size:1em;font-weight:normal}"""
def xhtml(title,body):
    return f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="tr" xml:lang="tr"><head><meta charset="utf-8"/><title>{html.escape(title)}</title><link rel="stylesheet" href="stil.css"/></head><body>{body}</body></html>'
chap=[]
for f in files:
    d=json.load(open(f)); s=d['sure']; fid=f"s{s:03d}"
    paras=[]
    for a in d['ayetler']:
        t=html.escape(a['meal'])
        t=re.sub(r'\[(\d+)\]',lambda m:f'<a epub:type="noteref" class="noteref" id="{fid}-r{m[1]}" href="#{fid}-n{m[1]}">{m[1]}</a>',t)
        paras.append(f'<p class="ayet">{t}</p>')
    notes=''.join(f'<aside epub:type="footnote" class="dipnot" id="{fid}-n{k}"><p><a class="geri" href="#{fid}-r{k}">{k}.</a> {html.escape(v)}</p></aside>' for k,v in d.get('dipnotlar',{}).items())
    besm='' if s in (1,9) else '<p class="besmele">Rahmân ve Rahîm olan Allah\'ın adıyla</p>'
    body=f'<section epub:type="chapter"><h1>{html.escape(d["ad"])} Sûresi</h1>{besm}{"".join(paras)}<section class="notlar" epub:type="footnotes"><h2>Dipnotlar</h2>{notes}</section></section>'
    chap.append((fid,f'{d["ad"]} Sûresi',xhtml(d['ad'],body)))
bid=str(uuid.uuid4())
nav=xhtml('İçindekiler','<nav epub:type="toc"><h1>İçindekiler</h1><ol>'+''.join(f'<li><a href="{c[0]}.xhtml">{c[1]}</a></li>' for c in chap)+'</ol></nav>')
opf=f'''<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bid" xml:lang="tr"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bid">urn:uuid:{bid}</dc:identifier><dc:title>Kur'ân-ı Kerîm — Yalın Türkçe Meal</dc:title><dc:language>tr</dc:language><meta property="dcterms:modified">2026-11-14T00:00:00Z</meta></metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="css" href="stil.css" media-type="text/css"/>{"".join(f'<item id="{c[0]}" href="{c[0]}.xhtml" media-type="application/xhtml+xml"/>' for c in chap)}</manifest><spine>{"".join(f'<itemref idref="{c[0]}"/>' for c in chap)}</spine></package>'''
with zipfile.ZipFile(out,'w') as z:
    z.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED)
    z.writestr('META-INF/container.xml','<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',compress_type=zipfile.ZIP_DEFLATED)
    for n,c in [('content.opf',opf),('nav.xhtml',nav),('stil.css',CSS)]+[(c[0]+'.xhtml',c[2]) for c in chap]:
        z.writestr('OEBPS/'+n,c,compress_type=zipfile.ZIP_DEFLATED)
print('yazıldı:',out)
