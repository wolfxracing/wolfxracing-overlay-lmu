# -*- coding: utf-8 -*-
"""Build ay (correcao 2): negrito + italico VISIVEIS na personalizacao, inclusive no tema Vidro quando o Qt (Windows) desenha a Bahnschrift com o
mesmo peso ao alternar negrito. Confere a fonte e o peso efetivamente usados (QFontInfo) E os pixels desenhados.
  1) ambiente real: negrito ligado x desligado (com italico) muda familia/peso efetivos e pixels, no tema Vidro e no moderno comum;
  2) ambiente SIMULADO do problema: QFont que ignora o peso na Bahnschrift (como o Qt/Windows reportado) - a personalizacao ainda tem de mudar;
  3) aparencia padrao (sem estilo) intacta; 4) painel real (item do Telemetria) muda de pixels; 5) LMU: icone da bandeja nao herda a fonte de outro pintor.
Roda nos dois pacotes (iRacing e LMU); o item 5 so no LMU."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["WOLFX_IDIOMA"] = "pt"
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import overlay_iracing as o
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QFont, QFontInfo, QImage, QPainter
S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c_: None; o.carregar_fontes_corrida()
falhas, _ok = [], 0
def confere(cond, msg):
    global _ok
    if cond: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)
cfg = o.carregar_config(); cfg["travado"] = True
K = o.JanelaTelemetria; EID = K.ELEMENTOS[0][0]; CH = K(dict(cfg))._chave_elementos()
def abrir(est):
    c = dict(cfg); c[CH + "_estilo"] = {EID: dict(est)} if est is not None else {}
    j = K(c); im = QImage(10, 10, QImage.Format_ARGB32); p = QPainter(im); j._abre(p, EID); return j, im, p
def fonte_com(est, tam=24, peso=QFont.Normal):
    j, im, p = abrir(est); f = o.fonte(tam, peso, p=p); j._fecha(p); p.end(); return f
def tinta(f):
    im = QImage(420, 80, QImage.Format_ARGB32); im.fill(QColor(0, 0, 0)); q = QPainter(im); q.setFont(f); q.setPen(QColor(255, 255, 255))
    q.drawText(8, 52, "WOLFX Rg 0123"); q.end()
    return sum(QColor(im.pixel(x, y)).red() for y in range(80) for x in range(420))
def info(f):
    i = QFontInfo(f); return i.family(), i.weight(), i.bold(), i.italic()
LIGADO = {"negrito": True, "italico": True}; DESLIG = {"negrito": False, "italico": True}
def par(rot):
    f_on, f_off = fonte_com(LIGADO), fonte_com(DESLIG)
    t_on, t_off = tinta(f_on), tinta(f_off)
    i_on, i_off = info(f_on), info(f_off)
    confere(f_on.italic() and f_off.italic(), f"{rot}: italico aplicado nos dois")
    confere(f_on.families()[0] != f_off.families()[0] or i_on[1] != i_off[1] or f_on.weight() != f_off.weight(),
            f"{rot}: fonte/peso efetivos diferem (ligado {i_on[0]}/{i_on[1]}, desligado {i_off[0]}/{i_off[1]})")
    confere(abs(t_on - t_off) > 0.02 * max(t_on, t_off), f"{rot}: pixels desenhados diferem ({t_on} x {t_off})")
    return f_on, f_off

# 1) ambiente real
for nome, tema in (("Vidro", dict(moderno=True, sport=False, vidro=True)), ("moderno comum", dict(moderno=True, sport=False, vidro=False)),
                   ("classico", dict(moderno=False, sport=False, vidro=False))):
    o.TEMA.update(tema); getattr(o, "_SONDA_PESO", {}).clear()
    par(f"real, tema {nome}, negrito+italico")

# 2) ambiente simulado: o Qt desenha a Bahnschrift com o mesmo peso ao alternar negrito (o peso e ignorado enquanto a familia efetiva for Bahnschrift)
class QFontSemPeso(QFont):
    def _preso(self):
        try: return self.families()[0] == "Bahnschrift" if self.families() else self.family() == "Bahnschrift"
        except Exception: return False
    def __init__(self, *a):
        if len(a) >= 3 and a[0] == "Bahnschrift": a = (a[0], a[1], QFont.Normal) + tuple(a[3:])
        super().__init__(*a)
    def setWeight(self, w):
        if not self._preso(): super().setWeight(w)
    def setBold(self, b):
        if not self._preso(): super().setBold(b)
QFont_orig = o.QFont; o.QFont = QFontSemPeso
try:
    o.TEMA.update(moderno=True, sport=False, vidro=True); getattr(o, "_SONDA_PESO", {}).clear()
    # na familia Bahnschrift o negrito nao muda nada (premissa da simulacao); a personalizacao do usuario tem de continuar visivel
    f_on, f_off = par("simulado (Bahnschrift sem mudanca de peso), tema Vidro, negrito+italico")
    f_on2, f_off2 = fonte_com({"negrito": True, "italico": False}), fonte_com({"negrito": False, "italico": False})
    confere(tinta(f_on2) != tinta(f_off2), "simulado: negrito sem italico tambem muda")
finally:
    o.QFont = QFont_orig
getattr(o, "_SONDA_PESO", {}).clear()

# 3) aparencia padrao intacta (sem estilo do usuario): mesma familia/peso/italico/tamanho de sempre
o.TEMA.update(moderno=True, sport=False, vidro=True)
f0 = fonte_com(None, 10, QFont.Bold)
confere(f0.families() == ["Bahnschrift", "Segoe UI"] and f0.weight() == QFont.Bold and f0.italic() and abs(f0.pointSizeF() - 10) < 0.01, f"padrao Vidro: Bahnschrift/Segoe UI, negrito, italico, 10 pt ({f0.families()}, {f0.weight()})")
f1 = fonte_com({"tam": 150}, 10, QFont.Bold)
confere(f1.families() == ["Bahnschrift", "Segoe UI"] and abs(f1.pointSizeF() - 15) < 0.01, "so tamanho personalizado: familia do tema preservada")
o.TEMA.update(moderno=False, sport=False, vidro=False)
f2 = fonte_com(None, 10, QFont.Bold); confere(f2.families() == ["Segoe UI"] and f2.weight() == QFont.Bold and not f2.italic(), "padrao classico: Segoe UI, negrito, sem italico")
o.TEMA.update(moderno=True, sport=False, vidro=True)

# 4) painel real: o item do Telemetria desenhado com negrito x sem negrito (ambos com italico) muda de pixels
def pixels_painel(est):
    c = dict(cfg); c[CH + "_estilo"] = {EID: dict(est)}; c[K.CHAVE_ATIVO] = False; j = K(c)
    try: j.atualizar(o.Telemetria(demo=True).ler())
    except Exception: pass
    return j.grab().toImage()
a, b = pixels_painel(LIGADO), pixels_painel(DESLIG)
dif = sum(1 for y in range(0, min(a.height(), b.height()), 1) for x in range(0, min(a.width(), b.width()), 1) if a.pixel(x, y) != b.pixel(x, y))
confere(dif > 20, f"painel real (Telemetria, item {EID}): negrito+italico x italico muda os pixels ({dif} pixels)")

# 5) LMU: o icone alternativo da bandeja usa o QPainter dele (nao herda a fonte do pintor de outra janela)
try:
    import overlay_lmu as m
except ImportError:
    m = None
if m is None:
    print("pacote sem LMU: item 5 nao se aplica")
else:
    import ast
    src = Path(m.__file__).read_text(encoding="utf-8"); arv = ast.parse(src)
    sem = [n.lineno for n in ast.walk(arv) if isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", "")) in ("fonte", "fonte_titulo")
           and not any(k.arg == "p" for k in n.keywords)]
    confere(sem == [], f"overlay_lmu.py: toda chamada de fonte()/fonte_titulo() passa o QPainter (linhas sem pintor: {sem})")
    m.base.PASTA = Path(tempfile.mkdtemp())                 # sem marca/logo_wxr.png: cai no icone desenhado ("LM")
    def icone():
        pm = m.criar_icone().pixmap(64, 64); return pm.toImage()
    livre = icone()
    j, im, p = abrir({"fonte": "bungee", "tam": 60, "negrito": False, "italico": False, "cor": "#0000ff"})   # outro pintor, com item aberto e estilo proprio
    com_outro = icone()
    j._fecha(p); p.end()
    confere(livre == com_outro, "LMU: icone da bandeja identico com outro pintor aberto (nao herda fonte nem cor)")
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
