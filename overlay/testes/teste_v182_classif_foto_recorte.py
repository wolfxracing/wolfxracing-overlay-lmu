# -*- coding: utf-8 -*-
"""Build ba (1.8.2): Classificacao Foto - o texto da barra superior (sessao e contadores) nao pode perder pixels.
Compara o que a janela PINTOU com a renderizacao de referencia sem recorte (mesma fonte, mesmo ponto), borda a borda, e confere que
o espaco reservado (e o fundo da etiqueta da sessao) contem a tinta real. Estilos: padrao e michroma/orbitron/bungee em negrito+italico
ate 200 %; largura normal e minima; idiomas pt e en (PRACTICE, AIR 24 graus)."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import overlay_iracing as o
import ov_classif_foto as cf
import ov_i18n
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QImage, QColor, QFont
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
cab0 = dict((D.get("classificacao") or {}).get("cabecalho") or {})
confere(bool(D.get("classificacao")), "demo tem classificacao")

import subprocess, importlib.util
ANTIGA = None
try:
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    antigo = subprocess.run(["git", "-C", raiz, "show", "v1.8.1:overlay/ov_classif_foto.py"], capture_output=True, timeout=30)
    if antigo.returncode == 0:
        arq = Path(S) / "ov_classif_foto_az.py"; arq.write_bytes(antigo.stdout)
        spec = importlib.util.spec_from_file_location("ov_classif_foto_az", arq); m_az = importlib.util.module_from_spec(spec); spec.loader.exec_module(m_az)
        ANTIGA = m_az.construir(o)
except Exception as e:
    print("(sem a versao v1.8.1 do git para comparar o padrao:", e, ")")
orig_pintor = o.JanelaBase._pintor
MODO = {"ref": False}
PILULAS = []
TEXTOS = []                                   # (retangulo, flags, texto) do ultimo desenho, em coordenadas do item
import weakref
def pintor(self):
    p = orig_pintor(self)
    ref = weakref.ref(p)
    def grava(*a, **k):
        q = ref()
        if q is None: return None
        if len(a) >= 3 and hasattr(a[0], "x") and isinstance(a[-1], str) and a[0].y() < 40:
            r, flags, txt = QRectF(a[0]), int(a[1]), a[-1]
            if not MODO["ref"]:
                TEXTOS.append((r, flags, txt, q.transform().m31(), q.transform().m32(), QFont(q.font())))
            else:                              # referencia: o mesmo texto, no mesmo ponto, sem recorte
                dx = 80.0
                if flags & int(Qt.AlignRight): r = r.adjusted(-dx, -30, 0, 30)
                elif flags & int(Qt.AlignHCenter): r = r.adjusted(-dx, -30, dx, 30)
                else: r = r.adjusted(0, -30, dx, 30)
                return QPainter.drawText(q, r, flags | int(Qt.TextDontClip), txt)
        return QPainter.drawText(q, *a, **k)
    p.drawText = grava
    def grava_rr(*a, **k):
        q = ref()
        if q is not None and a and hasattr(a[0], 'x') and a[0].y() < 40 and not MODO['ref']:
            PILULAS.append((QRectF(a[0]), q.transform().m31()))
        return QPainter.drawRoundedRect(q, *a, **k)
    p.drawRoundedRect = grava_rr
    return p
o.JanelaBase._pintor = pintor

def renderizar(j, ref):
    MODO["ref"] = ref; TEXTOS.clear(); PILULAS.clear()
    pm = j.grab(); MODO["ref"] = False
    return pm.toImage().convertToFormat(QImage.Format_ARGB32)

BBOX = {}
def diferentes(a, b, y1=0, y2=44):
    n = 0; w = min(a.width(), b.width()); xs = []; ys = []
    for y in range(y1, min(y2, a.height(), b.height())):
        for x in range(w):
            if a.pixel(x, y) != b.pixel(x, y): n += 1; xs.append(x); ys.append(y)
    BBOX["ultimo"] = (min(xs), min(ys), max(xs), max(ys)) if xs else None
    return n

ESTILOS = (("padrao", {}),
           ("michroma 200 negrito italico", {"fonte": "michroma", "negrito": True, "italico": True, "tam": 200}),
           ("orbitron 200 negrito italico", {"fonte": "orbitron", "negrito": True, "italico": True, "tam": 200}),
           ("bungee 200 negrito italico", {"fonte": "bungee", "negrito": True, "italico": True, "tam": 200}),
           ("michroma 150", {"fonte": "michroma", "tam": 150}))
ITENS = ("sessao", "contadores")
for lang, sessao in (("en", "PRACTICE"), ("pt", "TREINO")):
    ov_i18n.definir_idioma(lang)
    for nome, est in ESTILOS:
        for rotulo, ocultas in (("largura normal", ()), ("largura minima", ("delta", "num", "pneu", "lic", "ir", "marca", "pais", "gap", "int", "melhor", "ultima", "pit", "stint"))):
            c2 = dict(cfg); c2[K.CHAVE_ATIVO] = False
            c2["elementos_classificacao_estilo"] = {i: dict(est) for i in ITENS} if est else {}
            c2["classif_colunas"] = dict(c2.get("classif_colunas") or {}, **{h: False for h in ocultas}) if ocultas else c2.get("classif_colunas", {})
            D2 = dict(D); cl = dict(D["classificacao"]); cab = dict(cab0); cab.update(sessao=sessao, ar=24.0, pista=31.0, umidade=45.0, volta=3, voltas_total=20)
            cl["cabecalho"] = cab; D2["classificacao"] = cl
            j = K(c2); j.atualizar(D2)
            tag = f"{lang}/{nome}/{rotulo}"
            img = renderizar(j, False); gravados = list(TEXTOS); pilulas = list(PILULAS)
            ref = renderizar(j, True)
            textos = [t[2] for t in gravados]
            # largura minima + estilo grande: a etiqueta nao cabe ao lado de INC/clima e some inteira (nunca se sobrepoe); no resto tem de aparecer
            sumiu_ok = (rotulo == "largura minima" and bool(est))
            confere(sessao in textos or sumiu_ok, f"{tag}: '{sessao}' desenhado ({textos})")
            if sessao not in textos and sumiu_ok:
                confere(not any(t.startswith("AIR") or t[:1].isdigit() and "/" in t and t != "0/25" for t in textos), f"{tag}: sem a etiqueta, os itens seguintes tambem somem ({textos})")
            confere(any(t.startswith("AIR 24") for t in textos) or rotulo == "largura minima" or est, f"{tag}: AIR 24 desenhado ({textos})")
            n = diferentes(img, ref)
            confere(n == 0, f"{tag}: texto pintado completo, {n} pixel(s) perdido(s) pelo recorte (area x0,y0,x1,y1 = {BBOX['ultimo']}; textos {[(t[2], round(t[0].x(), 1), round(t[0].width(), 1), t[5].family(), round(t[5].pointSizeF(), 1)) for t in gravados]})")
            if sessao not in textos:
                n_ant = None
            # espaco reservado: a tinta REAL de cada texto cabe no retangulo reservado, nao se sobrepoe ao vizinho e fica dentro da janela
            ext = []
            for r, flags, txt, tx, ty, f in gravados:
                if txt == "INC": continue
                esq, dir_, topo, base_, adv = cf.tinta_texto(f, txt)
                if flags & int(Qt.AlignRight): ox = r.right() - adv
                elif flags & int(Qt.AlignHCenter): ox = r.x() + (r.width() - adv) / 2.0
                else: ox = r.x()
                x0, x1 = tx + ox + esq, tx + ox + dir_
                ext.append((x0, x1, txt, r, tx, flags))
                if (flags & int(Qt.AlignLeft)) and not (flags & int(Qt.AlignRight)) and txt != sessao:      # a tinta pode passar ate 4 px da origem (folga entre itens); a direita (clima/INC) alinha pela borda da janela
                    confere(x0 >= tx + r.x() - 4.6 and x1 <= tx + r.right() + 0.6, f"{tag}: tinta de '{txt}' ({x0:.1f}..{x1:.1f}) cabe no retangulo reservado ({tx + r.x():.1f}..{tx + r.right():.1f})")
            ext.sort()
            for a, b in zip(ext, ext[1:]):
                confere(a[1] <= b[0] + 0.6, f"{tag}: tinta de '{a[2]}' nao toca '{b[2]}' ({a[1]:.1f} > {b[0]:.1f})")
            confere(all(e[0] >= -0.6 and e[1] <= j.width() / j.escala_x + 0.6 for e in ext), f"{tag}: tinta dentro da janela")
            # etiqueta da sessao contem a tinta (largura e altura)
            for r, flags, txt, tx, ty, f in gravados:
                if txt != sessao: continue
                esq, dir_, topo, base_, adv = cf.tinta_texto(f, txt)
                pil = min(pilulas, key=lambda e: abs(e[0].x() - 16))[0] if pilulas else None
                confere(pil is not None, f"{tag}: etiqueta da sessao desenhada")
                if pil is not None:
                    x0 = ext_x0 = [e[0] for e in ext if e[2] == txt][0] - tx
                    x1 = [e[1] for e in ext if e[2] == txt][0] - tx
                    confere(x0 >= pil.x() - 0.6 and x1 <= pil.right() + 0.6, f"{tag}: etiqueta contem '{txt}' na largura ({x0:.1f}..{x1:.1f} em {pil.x():.1f}..{pil.right():.1f})")
                    cy = r.y() + r.height() / 2.0
                    # linha de base do texto centrado na caixa da fonte: topo/base da tinta relativos ao centro de 21 px
                    from PySide6.QtGui import QFontMetricsF
                    fm = QFontMetricsF(f)
                    base_y = r.y() + (r.height() - fm.height()) / 2.0 + fm.ascent()
                    confere(base_y + topo >= pil.y() - 0.6 and base_y + base_ <= pil.bottom() + 0.6,
                            f"{tag}: etiqueta contem '{txt}' na altura (tinta {base_y + topo:.1f}..{base_y + base_:.1f}, etiqueta {pil.y():.1f}..{pil.bottom():.1f})")
            # aparencia padrao: pixel a pixel igual a da build az (antes da correcao) quando o estilo e o padrao
            if not est and ANTIGA is not None:
                ja = ANTIGA(c2); ja.atualizar(D2)
                img_a = renderizar(ja, False)
                nd = diferentes(img, img_a, 0, img.height()) if img_a.size() == img.size() else -1
                confere(nd == 0, f"{tag}: aparencia padrao identica a da build az ({nd} px; area {BBOX['ultimo']}; textos novos {[t[2] for t in gravados]})")
o.JanelaBase._pintor = orig_pintor
ov_i18n.definir_idioma("pt")
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
