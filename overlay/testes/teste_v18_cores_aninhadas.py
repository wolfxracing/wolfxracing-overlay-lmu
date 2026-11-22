# -*- coding: utf-8 -*-
"""Build av (P1.1): cor por item com elementos aninhados, QPainter real em Qt offscreen."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["WOLFX_IDIOMA"] = "pt"
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import overlay_iracing as o
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QLinearGradient, QBrush, QPen
from PySide6.QtWidgets import QApplication
S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c_: None
falhas, _ok = [], 0
def confere(cond, msg):
    global _ok
    if cond: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)
K = o.JanelaTelemetria
cfg = o.carregar_config(); cfg["travado"] = True; cfg[K.CHAVE_ATIVO] = False
ch = K(dict(cfg))._chave_elementos()
def janela(estilos):
    c = dict(cfg); c[ch + "_estilo"] = estilos; return K(c)
def novo():
    im = QImage(300, 300, QImage.Format_ARGB32); im.fill(QColor(0, 0, 0, 255))
    p = QPainter(im); p.setPen(QColor(255, 255, 255)); p.setFont(QFont("Arial", 20)); return im, p
def dominante(im, y0, y1):
    """Cor (r,g,b) mais forte entre os pixels claros da faixa."""
    melhor, mc = 0, (0, 0, 0)
    for y in range(y0, y1):
        for x in range(0, im.width(), 2):
            c = QColor(im.pixel(x, y)); s = c.red() + c.green() + c.blue()
            if s > melhor: melhor, mc = s, (c.red(), c.green(), c.blue())
    return mc
def vermelho(c): return c[0] > 150 and c[1] < 80 and c[2] < 80
def azul(c): return c[2] > 150 and c[0] < 80 and c[1] < 80
def verde(c): return c[1] > 150 and c[0] < 80 and c[2] < 80
def branco(c): return min(c) > 200
ids = [e for e, _r in K.ELEMENTOS][:4]
A, B, C, D = ids
j = janela({A: {"cor": "#ff0000"}, B: {"cor": "#0000ff"}, D: {"cor": "#00ff00"}})   # C sem cor
im, p = novo()
if j._abre(p, A):
    p.drawText(QRectF(0, 0, 300, 40), Qt.AlignLeft, "AAAA")
    if j._abre(p, B):
        p.drawText(QRectF(0, 50, 300, 40), Qt.AlignLeft, "BBBB")
        if j._abre(p, C):                                   # sem cor propria: herda a de B
            p.drawText(QRectF(0, 100, 300, 40), Qt.AlignLeft, "CCCC")
            if j._abre(p, D):
                p.drawText(QRectF(0, 150, 300, 40), Qt.AlignLeft, "DDDD")
                j._fecha(p)
            p.drawText(QRectF(0, 200, 300, 40), Qt.AlignLeft, "CCCC")     # depois de fechar D: volta a cor de B
            j._fecha(p)
        p.drawText(QRectF(0, 250, 50, 40), Qt.AlignLeft, "BB")           # depois de fechar C: ainda B
        j._fecha(p)
    p.setPen(QColor(255, 255, 255)); p.drawText(QRectF(100, 250, 100, 40), Qt.AlignLeft, "AA")   # depois de fechar B: volta a de A
    j._fecha(p)
p.setPen(QColor(255, 255, 255)); p.drawText(QRectF(200, 250, 100, 40), Qt.AlignLeft, "ZZ")       # fora de tudo: cor original
p.end()
confere(vermelho(dominante(im, 0, 40)), "nivel 1: vermelho")
confere(azul(dominante(im, 50, 90)), "nivel 2 (aninhado): azul, nao herda o vermelho")
confere(azul(dominante(im, 100, 140)), "nivel 3 sem cor propria herda a do pai (azul)")
confere(verde(dominante(im, 150, 190)), "nivel 4 (cor propria): verde")
confere(azul(dominante(im, 200, 240)), "apos fechar o nivel 4: volta o azul")
confere(azul(dominante(im.copy(0, 250, 60, 50), 0, 50)), "apos fechar o nivel 3: ainda azul")
confere(vermelho(dominante(im.copy(100, 250, 100, 50), 0, 50)), "apos fechar o nivel 2 (ainda dentro de A): volta o vermelho")
confere(branco(dominante(im.copy(200, 250, 100, 50), 0, 50)), "fora de todos os itens: cor original")
confere(o._ELEM_PILHA == [], "pilha vazia")
# o painter nao ficou com metodos trocados
im, p = novo()
confere("drawText" not in p.__dict__ and "setBrush" not in p.__dict__, "QPainter novo sem substituicoes")
j = janela({A: {"cor": "#ff0000"}, B: {"cor": "#0000ff"}})
j._abre(p, A); j._abre(p, B)
confere("drawText" in p.__dict__, "dentro: metodos substituidos")
j._fecha(p)
# depois de fechar B, ainda dentro de A: o texto volta a ser vermelho (A) e o metodo continua substituido
p.setPen(QColor(255, 255, 255)); p.drawText(QRectF(0, 0, 300, 40), Qt.AlignLeft, "AAAA")
confere("drawText" in p.__dict__, "fechou o interno: o externo continua com a substituicao")
j._fecha(p); p.end()
confere(vermelho(dominante(im, 0, 40)), "texto de A depois de fechar B e vermelho")
confere("drawText" not in p.__dict__ and "setBrush" not in p.__dict__, "fechou o externo: metodos originais de volta")
# preenchimentos solidos, transparencia e degrade
im, p = novo()
j = janela({A: {"cor": "#ff0000"}, B: {"cor": "#0000ff"}})
j._abre(p, A)
p.setPen(Qt.NoPen); p.setBrush(QColor(0, 255, 0, 255)); p.drawRect(0, 0, 100, 50)                      # sólido -> vermelho
j._abre(p, B)
p.setBrush(QColor(0, 255, 0, 255)); p.drawRect(100, 0, 100, 50)                                       # sólido interno -> azul
p.setBrush(QColor(0, 255, 0, 128)); p.drawRect(0, 60, 100, 50)                                        # alpha 128 preservado -> azul meio
g = QLinearGradient(0, 0, 100, 0); g.setColorAt(0, QColor(0, 255, 0)); g.setColorAt(1, QColor(0, 255, 0)); p.setBrush(QBrush(g)); p.drawRect(100, 60, 100, 50)   # degrade intacto (verde)
j._fecha(p)
p.setBrush(QColor(0, 255, 0, 255)); p.drawRect(0, 120, 100, 50)                                       # volta a A -> vermelho
j._fecha(p)
p.setBrush(QColor(0, 255, 0, 255)); p.drawRect(100, 120, 100, 50); p.end()
px = lambda x, y: (lambda c: (c.red(), c.green(), c.blue()))(QColor(im.pixel(x, y)))
confere(vermelho(px(50, 25)), "preenchimento solido de A = vermelho")
confere(azul(px(150, 25)), "preenchimento solido aninhado de B = azul")
m = px(50, 85)
confere(m[2] > 90 and m[2] < 160 and m[1] < 20, f"transparencia 50% preservada no interno ({m})")
confere(verde(px(150, 85)), "degrade nao e recolorido")
confere(vermelho(px(50, 145)), "depois de fechar B, preenchimento de A volta a vermelho")
confere(verde(px(150, 145)), "fora dos itens o preenchimento e original")
# excecao no meio do desenho: o pintor que falhou e destruido; o que sobrou na pilha nao vaza para os outros
im, p = novo(); j = janela({A: {"cor": "#ff0000"}, B: {"cor": "#0000ff"}})
try:
    j._abre(p, A); j._abre(p, B); raise RuntimeError("falha de desenho")
except RuntimeError:
    pass
p.end()
confere(len(o._ELEM_PILHA) == 2, "excecao deixa sobra de um pintor ja encerrado na pilha")
confere(o._cor_do_elemento() is None and o._estilo_do_elemento() is None, "sobra de pintor encerrado nao afeta cor/fonte de quem desenha depois")
im2, p2 = novo(); j2 = janela({A: {"cor": "#00ff00"}})
if j2._abre(p2, A):
    p2.drawText(QRectF(0, 0, 300, 40), Qt.AlignLeft, "XXXX"); j2._fecha(p2)
p2.end()
confere(o._ELEM_PILHA == [], "novo desenho limpa a sobra e termina com a pilha vazia")
confere(verde(dominante(im2, 0, 40)), "desenho depois da excecao sai com a cor certa")
# dois pintores/janelas em sequencia
im1, pa = novo(); im2, pb = novo()
ja = janela({A: {"cor": "#ff0000"}}); jb = janela({A: {"cor": "#0000ff"}})
ja._abre(pa, A); pa.drawText(QRectF(0, 0, 300, 40), Qt.AlignLeft, "PA"); ja._fecha(pa)
jb._abre(pb, A); pb.drawText(QRectF(0, 0, 300, 40), Qt.AlignLeft, "PB"); jb._fecha(pb)
pa.end(); pb.end()
confere(vermelho(dominante(im1, 0, 40)) and azul(dominante(im2, 0, 40)), "janelas/pintores em sequencia nao interferem")

# ---- build aw (P2.2): pintores INTERCALADOS / reentrantes --------------------------------------------------------
def txt(p, y, t="XXXX"):
    p.setPen(QColor(255, 255, 255)); p.drawText(QRectF(0, y, 300, 40), Qt.AlignLeft, t)
# 1) A abre vermelho; B abre azul; B fecha; A continua e deve seguir vermelho (cenario da auditoria)
imA, pa = novo(); imB, pb = novo()
ja = janela({A: {"cor": "#ff0000"}}); jb = janela({A: {"cor": "#0000ff"}})
ja._abre(pa, A); jb._abre(pb, A)
txt(pb, 0); jb._fecha(pb)
txt(pa, 0)                                              # A continua dentro do elemento vermelho
confere("drawText" in pa.__dict__, "A manteve a substituicao depois de B abrir e fechar")
ja._fecha(pa)
txt(pa, 60)                                             # fora do item: original
pa.end(); pb.end()
confere(azul(dominante(imB, 0, 40)), "B: azul dentro do seu item")
confere(vermelho(dominante(imA, 0, 40)), "A: continua vermelho depois do ciclo completo de B")
confere(branco(dominante(imA, 60, 100)), "A: fora do item, cor original")
confere(o._ELEM_PILHA == [], "pilha vazia ao final")
# 2) totalmente intercalado: A abre, B abre, A fecha, B continua azul
imA, pa = novo(); imB, pb = novo()
ja._abre(pa, A); jb._abre(pb, A)
txt(pa, 0); ja._fecha(pa)
confere("drawText" not in pa.__dict__ and "drawText" in pb.__dict__, "fechar A restaura so o pintor A")
txt(pb, 0); jb._fecha(pb); pa.end(); pb.end()
confere(vermelho(dominante(imA, 0, 40)) and azul(dominante(imB, 0, 40)), "intercalado A-B-A-B: cada um com a sua cor")
confere(o._ELEM_PILHA == [], "pilha vazia ao final (intercalado)")
# 3) aninhado em dois pintores ao mesmo tempo: A1 B1 A2 B2 fecha A2 B2 B1 A1
j4a = janela({A: {"cor": "#ff0000"}, B: {"cor": "#00ff00"}}); j4b = janela({A: {"cor": "#0000ff"}, B: {"cor": "#ffff00"}})
imA, pa = novo(); imB, pb = novo()
j4a._abre(pa, A); j4b._abre(pb, A); j4a._abre(pa, B); j4b._abre(pb, B)
txt(pa, 0, "A2"); txt(pb, 0, "B2")
j4a._fecha(pa); txt(pa, 60, "A1")
j4b._fecha(pb); txt(pb, 60, "B1")
j4b._fecha(pb); j4a._fecha(pa); txt(pa, 120, "A0"); txt(pb, 120, "B0"); pa.end(); pb.end()
amarelo = lambda c: c[0] > 150 and c[1] > 150 and c[2] < 80
confere(verde(dominante(imA, 0, 40)) and vermelho(dominante(imA, 60, 100)) and branco(dominante(imA, 120, 160)), "A: verde (nivel 2), vermelho (nivel 1), original (fora)")
confere(amarelo(dominante(imB, 0, 40)) and azul(dominante(imB, 60, 100)) and branco(dominante(imB, 120, 160)), "B: amarelo (nivel 2), azul (nivel 1), original (fora)")
confere(o._ELEM_PILHA == [], "pilha vazia ao final (aninhado em dois pintores)")
# 4) preenchimentos solidos, transparencia e degrade em pintores intercalados
imA, pa = novo(); imB, pb = novo()
ja._abre(pa, A); jb._abre(pb, A)
pa.setPen(Qt.NoPen); pb.setPen(Qt.NoPen)
pa.setBrush(QColor(0, 255, 0, 255)); pb.setBrush(QColor(0, 255, 0, 128))
pa.drawRect(0, 0, 50, 50); pb.drawRect(0, 0, 50, 50)
g = QLinearGradient(0, 0, 100, 0); g.setColorAt(0, QColor(0, 255, 0)); g.setColorAt(1, QColor(0, 255, 0))
pa.setBrush(QBrush(g)); pa.drawRect(60, 0, 50, 50)
jb._fecha(pb); ja._fecha(pa); pa.end(); pb.end()
pxa = QColor(imA.pixel(20, 20)); pxb = QColor(imB.pixel(20, 20)); pg = QColor(imA.pixel(80, 20))
confere(pxa.red() > 200 and pxa.green() < 30, "A: preenchimento solido vermelho")
confere(pxb.blue() > 90 and pxb.blue() < 160 and pxb.green() < 20, f"B: transparencia 50% preservada ({pxb.blue()})")
confere(pg.green() > 200 and pg.red() < 30, "A: degrade nao e recolorido")
# 5) excecao em A no meio, B segue sem perder nada
imA, pa = novo(); imB, pb = novo()
ja._abre(pa, A); jb._abre(pb, A)
try:
    raise RuntimeError("falha de A")
except RuntimeError:
    pass
pa.end()
txt(pb, 0); confere(o._cor_do_elemento() == "#0000ff", "pintor A encerrado: o contexto e o do B")
jb._fecha(pb); pb.end()
confere(azul(dominante(imB, 0, 40)), "B: continua azul apos o encerramento de A")
im3, pc = novo(); jc = janela({A: {"cor": "#00ff00"}})
jc._abre(pc, A); txt(pc, 0); jc._fecha(pc); pc.end()
confere(o._ELEM_PILHA == [] and verde(dominante(im3, 0, 40)), "proximo desenho limpa a sobra e sai correto")
# 6) build ax: fonte e cor ISOLADAS por QPainter. Dois pintores reais, fonte base de 20 pt, A = Orbitron 150% negrito italico vermelho,
#    B = Bungee 60% regular azul. Com os dois abertos, medir e desenhar em ambos: A usa o seu (30 pt), B o seu (12 pt).
from PySide6.QtGui import QFontMetrics
try: o.carregar_fontes_corrida()
except Exception: pass
def _com_pintor(f, *a, p=None, **k):
    """Chama f(*a, p=p); na API antiga (build aw, sem pintor) cai no contexto global - assim o MESMO teste roda nas duas builds."""
    try: return f(*a, p=p, **k)
    except TypeError: return f(*a, **k)
def _consulta(f, p):
    try: return f(p)
    except TypeError: return f()
def fonte_(t, p, peso=None):  return _com_pintor(o.fonte, t, *( [peso] if peso is not None else []), p=p)
def fonte_tit(t, p):          return _com_pintor(o.fonte_titulo, t, p=p)
def cor_de(p):                return _consulta(o._cor_do_elemento, p)
def estilo_de(p):             return _consulta(o._estilo_do_elemento, p)
EA = {"fonte": "orbitron", "tam": 150, "negrito": True, "italico": True, "cor": "#ff0000"}
EB = {"fonte": "bungee", "tam": 60, "negrito": False, "italico": False, "cor": "#0000ff"}
def caso6(ordem_fecha):
    rot = "fecha " + ordem_fecha
    ja = janela({A: dict(EA)}); jb = janela({A: dict(EB)})
    imA, pa = novo(); imB, pb = novo()
    ja._abre(pa, A); jb._abre(pb, A)                                    # os dois abertos ao mesmo tempo (B abriu por ultimo)
    fa, fb = fonte_(20, pa), fonte_(20, pb)
    confere(abs(fa.pointSizeF() - 30.0) < 0.01, f"[{rot}] A: 20 pt base x 150% = 30 pt (veio {fa.pointSizeF()})")
    confere(abs(fb.pointSizeF() - 12.0) < 0.01, f"[{rot}] B: 20 pt base x 60% = 12 pt (veio {fb.pointSizeF()})")
    confere(fa.family() != fb.family(), f"[{rot}] familias diferentes ({fa.family()} / {fb.family()})")
    confere(fa.italic() and not fb.italic(), f"[{rot}] italico so em A")
    confere(fa.bold() and not fb.bold(), f"[{rot}] negrito so em A (regular em B)")
    ft_a, ft_b = fonte_tit(20, pa), fonte_tit(20, pb)
    confere(abs(ft_a.pointSizeF() - 30.0) < 0.01 and abs(ft_b.pointSizeF() - 12.0) < 0.01, f"[{rot}] fonte_titulo tambem por pintor (30 / 12)")
    la, lb = QFontMetrics(fa).horizontalAdvance("WOLFX 123"), QFontMetrics(fb).horizontalAdvance("WOLFX 123")
    confere(la > lb * 1.5, f"[{rot}] medicao por pintor: A {la}px, B {lb}px")
    confere(cor_de(pa) == "#ff0000" and cor_de(pb) == "#0000ff", f"[{rot}] cor consultada por pintor (A vermelho, B azul)")
    confere((estilo_de(pa) or {}).get("tam") == 150 and (estilo_de(pb) or {}).get("tam") == 60, f"[{rot}] estilo consultado por pintor")
    pa.setFont(fa); pb.setFont(fb)
    txt(pb, 0, "BB"); txt(pa, 0, "AA")                                  # desenha em B e depois em A (A nao e o ultimo aberto)
    confere(vermelho(dominante(imA, 0, 60)), f"[{rot}] cor desenhada em A: vermelho")
    confere(azul(dominante(imB, 0, 60)), f"[{rot}] cor desenhada em B: azul")
    if ordem_fecha == "A,B":
        ja._fecha(pa)
        confere(estilo_de(pa) is None and "drawText" not in pa.__dict__ and "setBrush" not in pa.__dict__, f"[{rot}] A fechado: sem estilo e sem metodos trocados")
        confere((estilo_de(pb) or {}).get("tam") == 60 and cor_de(pb) == "#0000ff" and "drawText" in pb.__dict__, f"[{rot}] B segue com o seu estilo")
        confere(abs(fonte_(20, pb).pointSizeF() - 12.0) < 0.01, f"[{rot}] B ainda mede 12 pt")
        jb._fecha(pb)
    else:
        jb._fecha(pb)
        confere(estilo_de(pb) is None and "drawText" not in pb.__dict__ and "setBrush" not in pb.__dict__, f"[{rot}] B fechado: sem estilo e sem metodos trocados")
        confere((estilo_de(pa) or {}).get("tam") == 150 and cor_de(pa) == "#ff0000" and "drawText" in pa.__dict__, f"[{rot}] A segue com o seu estilo")
        confere(abs(fonte_(20, pa).pointSizeF() - 30.0) < 0.01, f"[{rot}] A ainda mede 30 pt")
        ja._fecha(pa)
    confere(estilo_de(pa) is None and estilo_de(pb) is None and cor_de(pa) is None and cor_de(pb) is None, f"[{rot}] tudo fechado: sem estilo")
    confere(o._ELEM_PILHA == [] and "drawText" not in pa.__dict__ and "drawText" not in pb.__dict__, f"[{rot}] pilha vazia e pintores restaurados")
    confere(abs(fonte_(20, pa).pointSizeF() - 20.0) < 0.01, f"[{rot}] fora do item a fonte volta ao tamanho base (20 pt)")
    pa.end(); pb.end()
caso6("A,B"); caso6("B,A")
# pintor sem item aberto nao herda o estilo de OUTRO pintor aberto
ja = janela({A: dict(EA)}); imA, pa = novo(); imB, pb = novo()
ja._abre(pa, A)
confere(estilo_de(pb) is None and cor_de(pb) is None and abs(fonte_(20, pb).pointSizeF() - 20.0) < 0.01, "pintor sem item aberto nao herda o estilo de outro pintor")
ja._fecha(pa); pa.end(); pb.end()
confere(o._estilo_do_elemento() is None, "sem itens abertos: sem contexto")
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
