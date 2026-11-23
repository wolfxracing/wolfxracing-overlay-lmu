# -*- coding: utf-8 -*-
"""Diagnostico de FONTES do Qt (build bb): mostra o que a plataforma Qt em uso realmente fornece, para separar 'defeito do produto' de
'variacao de fonte do ambiente'. Uso: QT_QPA_PLATFORM=windows|offscreen python tools/diagnostico_fontes_qt.py [saida.json]"""
import json, os, sys
from PySide6.QtGui import QGuiApplication, QFont, QFontDatabase, QFontInfo, QFontMetricsF
app = QGuiApplication(sys.argv)
fam = QFontDatabase.families()
sonda = "PRACTICE AIR 24° Classificação 0123456789"
def medir(nome, px=12, peso=QFont.Normal):
    f = QFont(nome); f.setPixelSize(px); f.setWeight(peso)
    i = QFontInfo(f)
    return {"pedida": nome, "resolvida": i.family(), "exata": i.exactMatch(), "largura_sonda": round(QFontMetricsF(f).horizontalAdvance(sonda), 2)}
r = {"plataforma": app.platformName(), "qt": __import__("PySide6").__version__, "n_familias": len(fam),
     "QT_QPA_FONTDIR": os.environ.get("QT_QPA_FONTDIR", ""),
     "tem": {n: (n in fam) for n in ["Bahnschrift", "Segoe UI", "Arial", "Consolas", "Tahoma", "Calibri", "Rajdhani", "DejaVu Sans"]},
     "fonte_padrao": QFont().family(),
     "medidas": [medir(n) for n in ["Bahnschrift", "Segoe UI", "Arial", "Consolas", "Rajdhani"]],
     "familias": sorted(fam)[:60]}
txt = json.dumps(r, indent=1, ensure_ascii=False)
print(txt)
if len(sys.argv) > 1:
    open(sys.argv[1], "w", encoding="utf-8").write(txt)
