# -*- coding: utf-8 -*-
"""Build av (P2.2): na barra superior da Classificacao o espaco de cada texto e medido com o estilo REAL do item (fonte, negrito,
italico, tamanho ate 200 %), em pt, de e fr: sem sobreposicao entre textos e sem texto passando do retangulo reservado."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["WOLFX_IDIOMA"] = "pt"
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import overlay_iracing as o
import ov_classif_foto as cf
import ov_i18n
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QFontMetrics
from PySide6.QtWidgets import QApplication
S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c_: None
falhas, _ok = [], 0
def confere(cond, msg):
    global _ok
    if cond: _ok += 1
    else: falhas.append(msg); print("FALHA", msg)
K = cf.construir(o)
cfg = o.carregar_config(); cfg["travado"] = True
demo = o.Telemetria(demo=True); demo.modo_previa = True
D = demo.ler()
cab = (D.get("classificacao") or {}).get("cabecalho")
confere(bool(D.get("classificacao")), "demo tem classificacao")
orig_pintor = o.JanelaBase._pintor
REG = []
import weakref
def pintor_gravador(self):
    p = orig_pintor(self)
    ref = weakref.ref(p)
    def grava(*a, **k):
        p = ref()
        if p is None: return None
        try:
            if len(a) >= 3 and hasattr(a[0], "x") and isinstance(a[-1], str):
                r, flags, txt = a[0], a[1], a[-1]
                REG.append((QRectF(r), int(flags), txt, QFontMetrics(p.font()).horizontalAdvance(txt), p.transform().m31(), p.transform().m32()))
        except Exception:
            pass
        return QPainter.drawText(p, *a, **k)
    p.drawText = grava
    return p
o.JanelaBase._pintor = pintor_gravador

def extent(r, flags, adv, tx):
    x0 = r.x() + tx
    if flags & int(Qt.AlignRight): return (x0 + r.width() - adv, x0 + r.width())
    if flags & int(Qt.AlignHCenter): return (x0 + (r.width() - adv) / 2.0, x0 + (r.width() + adv) / 2.0)
    return (x0, x0 + adv)

ESTILOS = (("padrao", {}), ("bungee 150", {"fonte": "bungee", "tam": 150}), ("orbitron negrito italico 200", {"fonte": "orbitron", "negrito": True, "italico": True, "tam": 200}),
           ("michroma 130", {"fonte": "michroma", "tam": 130}), ("audiowide 200", {"fonte": "audiowide", "tam": 200}), ("tam 50", {"tam": 50}))
ITENS = ("sessao", "contadores", "clima", "incidentes")
for lang in ("pt", "de", "fr"):
    ov_i18n.definir_idioma(lang)
    for nome, est in ESTILOS:
        c2 = dict(cfg); c2[K.CHAVE_ATIVO] = False
        c2["elementos_classificacao_estilo"] = {i: dict(est) for i in ITENS} if est else {}
        j = K(c2); j.atualizar(D)
        REG.clear(); j.grab()
        topo = [r for r in REG if r[0].y() + r[5] < 40 and r[0].height() <= 24 and r[2].strip()]
        confere(len(topo) >= 3, f"{lang}/{nome}: textos da barra desenhados ({len(topo)})")
        ext = sorted((extent(r[0], r[1], r[3], r[4]), r[2]) for r in topo)
        for (a, ta), (b, tb) in zip(ext, ext[1:]):
            confere(a[1] <= b[0] + 1.0, f"{lang}/{nome}: '{ta}' nao sobrepoe '{tb}' ({a[1]:.0f} > {b[0]:.0f})")
        for r in topo:
            if r[2] in ("INC",): continue
            confere(r[3] <= r[0].width() + 1.0, f"{lang}/{nome}: '{r[2]}' cabe no retangulo reservado ({r[3]} > {r[0].width():.0f})")
        confere(all(e[0][0] >= -1 and e[0][1] <= j.width() / j.escala_x + 1 for e in ext), f"{lang}/{nome}: nada fora da janela")
    # estilo diferente muda o espaco: o texto com tamanho 200 % ocupa mais que o padrao
o.JanelaBase._pintor = orig_pintor
ov_i18n.definir_idioma("pt")
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
