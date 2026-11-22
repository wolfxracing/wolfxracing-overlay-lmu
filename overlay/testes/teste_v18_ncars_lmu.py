# -*- coding: utf-8 -*-
"""Build ax + ay: cabecalho da Classificacao do LMU nos DOIS layouts, nas classes reais do LMU (Qt offscreen, pixels da janela de verdade).
  Foto (ay): contador N CARS medido/reservado/desenhado pela AREA REAL do texto (tinta, italico, glifos altos); a sessao (RACE) respeita o espaco do
             contador; regra: o contador tem prioridade, o que nao cabe INTEIRO some (nada pela metade); contador sozinho maior que a barra = some.
             Larguras: 180 px (so Piloto), 210 px (Piloto + Pos) e normal (846).
  Classico (ay): tempo/volta, temperaturas e contador medidos EM CONJUNTO; prioridade tempo/volta > contador > temperaturas; reserva do contador
             liberada quando oculto (ou sem espaco).
  Itens identificados por COR (contador magenta, temperaturas verde, tempo/volta amarelo, sessao = faixa vermelha do proprio painel).
  Falha (exit 1) se uma dependencia obrigatoria do LMU nao puder ser importada. Requer NumPy, PySide6 (requirements-teste.txt)."""
import os, sys, copy, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ["WOLFX_IDIOMA"] = "pt"
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
try:                                                   # dependencias OBRIGATORIAS: sem elas o teste FALHA (nunca "passa vazio")
    import numpy                                       # noqa: F401  (declarada em requirements-teste.txt; usada pelas outras suites)
    import overlay_iracing as o
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter
    import _render_au as RA
    import overlay_lmu as _m, ov_demo_lmu as _dl, ov_janela_lmu as _jl, ov_classif_foto as _cf
except ImportError as e_imp:
    print("FALHA dependencia obrigatoria do LMU nao importada:", repr(e_imp)); sys.exit(1)
S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
RA.congelar_relogio()
app = QApplication([]); o.salvar_config = lambda c_: None
o.carregar_fontes_corrida()
falhas, _ok = [], 0
def confere(cond, msg):
    global _ok
    if cond: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)
cfg = o.carregar_config(); cfg["travado"] = True
demo = o.Telemetria(demo=True); demo.modo_previa = True
BASE = demo.ler()
D0 = dict(BASE); D0.update(_dl.DemoExtraLMU(lambda: 5000.0).ler())
MAG, VERDE, AMAR = (255, 0, 255), (0, 255, 0), (255, 255, 0)
HX = {MAG: "#ff00ff", VERDE: "#00ff00", AMAR: "#ffff00"}
VERM = (176, 40, 56)                                                  # faixa vermelha da sessao (RACE)
def dados_com(total):
    d = copy.deepcopy(D0); cl = d["classificacao"]; n = len(cl["classes"])
    base, resto = divmod(total, n)
    for i, c in enumerate(cl["classes"]): c["n_carros"] = base + (1 if i < resto else 0)
    assert sum(c["n_carros"] for c in cl["classes"]) == total
    return d
def colunas_ocultas(K, manter):
    return {g: False for g, _r, _k in K.GRUPOS if g not in K.FIXAS and g not in manter}
def janela(layout, total, estilo_n=None, oculta=False, pos_n=None, largura=None, estilos=None, extra=None):
    """largura: None = normal; 180 = so Piloto; 210 = Piloto + Pos (colunas ocultas reais da classe)."""
    c = dict(cfg); c["classificacao_layout"] = layout
    K = _jl.classe_classificacao(c); ch = K(dict(c))._chave_elementos()
    est = {"ncars": dict({"cor": HX[MAG]}, **(estilo_n or {}))}
    if layout == "classico":
        est["temperaturas"] = dict({"cor": HX[VERDE]}, **(estilos or {}).get("temperaturas", {}))
        est["contadores"] = dict({"cor": HX[AMAR]}, **(estilos or {}).get("contadores", {}))
        if estilo_n and (estilos or {}).get("ncars_igual"):
            pass
    c[ch + "_estilo"] = est
    if oculta: c[ch] = {"ncars": False}
    if pos_n: c[ch + "_pos"] = {"ncars": list(pos_n)}
    if largura == 180: c["classif_colunas"] = colunas_ocultas(K, ())
    if largura == 210: c["classif_colunas"] = colunas_ocultas(K, ("pos",))
    for k_, v_ in (extra or {}).items(): c[k_] = v_
    c[K.CHAVE_ATIVO] = False
    j = K(c); j.atualizar(dados_com(total)); return j
def perto(px, alvo, lim=90):
    c = QColor(px); return abs(c.red() - alvo[0]) + abs(c.green() - alvo[1]) + abs(c.blue() - alvo[2]) < lim
def caixa(im, alvo, y0=0, y1=None, lim=90):
    """(x0, y0, x1, y1, n_pixels) da cor `alvo` na faixa y0..y1, ou None."""
    xs, ys, n = [], [], 0
    for y in range(y0, min(im.height(), y1 if y1 else im.height())):
        for x in range(im.width()):
            if perto(im.pixel(x, y), alvo, lim): xs.append(x); ys.append(y); n += 1
    return (min(xs), min(ys), max(xs), max(ys), n) if xs else None
def tinta(f, texto, cor=MAG):
    """Tinta REAL do texto na fonte f desenhado sozinho, sem area limitando: (largura, altura, pixels). Referencia independente do codigo testado."""
    im = QImage(1200, 160, QImage.Format_ARGB32); im.fill(QColor(0, 0, 0)); q = QPainter(im); q.setFont(f); q.setPen(QColor(*cor))
    q.drawText(20, 100, texto); q.end(); b = caixa(im, cor); return (b[2] - b[0] + 1, b[3] - b[1] + 1, b[4])
_IM = QImage(10, 10, QImage.Format_ARGB32); _P = QPainter(_IM)
def fonte_item(layout, eid, estilo, tam, peso):
    """Fonte EFETIVA (a mesma que o painel usa) de um item com o estilo dado."""
    c = dict(cfg); c["classificacao_layout"] = layout; K = _jl.classe_classificacao(c); ch = K(dict(c))._chave_elementos()
    c[ch + "_estilo"] = {eid: dict(estilo)}; j = K(c)
    j._abre(_P, eid); f = o.fonte(tam, peso, p=_P); j._fecha(_P); return f
def inteiro(b, ref, rot):
    """Glifos inteiros: a tinta na janela tem pelo menos o tamanho e quase todos os pixels da tinta de referencia (sem corte em nenhuma borda)."""
    if b is None: confere(False, f"{rot}: nao apareceu"); return False
    w, h = b[2] - b[0] + 1, b[3] - b[1] + 1
    ok = w >= ref[0] - 1 and h >= ref[1] and (ref[1] < 14 or b[4] >= 0.80 * ref[2])      # contagem de pixels so para fontes grandes (texto pequeno varia com o hinting)
    confere(ok, f"{rot}: glifos inteiros (janela {w}x{h}, {b[4]}px; referencia {ref[0]}x{ref[1]}, {ref[2]}px)")
    return ok
BARRA = 52                                                           # a barra superior ocupa so o topo da janela
EO = {"fonte": "orbitron", "tam": 200, "negrito": True, "italico": True}
EM = {"fonte": "michroma", "tam": 200, "negrito": True, "italico": True}
EM_R = {"fonte": "michroma", "tam": 200, "negrito": False, "italico": False}

# ============================== FOTO: contador, sessao, larguras 180 / 210 / normal ===========================================
REF_VERM = None                                                      # largura/altura/pixels da faixa da sessao em janela larga (sem contador)
jr = janela("foto", 62, oculta=True); REF_VERM = caixa(jr.grab().toImage(), VERM, 0, BARRA, lim=60)
confere(REF_VERM is not None, f"foto: faixa da sessao encontrada na janela larga ({REF_VERM})")
for largura, nome in ((180, "180px"), (210, "210px"), (None, "normal")):
    for total in (62, 100):
        for est, nome_e in ((EO, "Orbitron 200% neg+ital"), (EM, "Michroma 200% neg+ital"), (EM_R, "Michroma 200% regular"), ({}, "padrao")):
            j = janela("foto", total, est, largura=largura)
            im = j.grab().toImage(); L = j._largura
            rot = f"foto {nome} {total} carros {nome_e}"
            if largura: confere(L == largura, f"{rot}: janela com {L}px (esperado {largura})")
            bn = caixa(im, MAG, 0, BARRA); bs = caixa(im, VERM, 0, BARRA, lim=60)
            f_n = fonte_item("foto", "ncars", est, 9, QFont.Bold); ref = tinta(f_n, f"{total} CARS")
            util = L - 28
            deve = ref[0] <= util - 3; nao_deve = ref[0] >= util + 3
            if deve:
                if inteiro(bn, ref, rot + " contador"):
                    confere(bn[2] <= L - 8 and bn[0] >= 8, f"{rot}: contador dentro da barra (x {bn[0]}..{bn[2]} em {L}px)")
                    confere(bn[2] >= L - 16 - 6, f"{rot}: contador alinhado a direita (x1={bn[2]})")
            elif nao_deve:
                confere(bn is None, f"{rot}: contador maior que a barra ({ref[0]} > {util}px) some inteiro, sem pedaco ({bn})")
            # sessao: inteira ou ausente, e nunca invade o contador
            if bs is not None:
                confere(bs[4] >= 0.97 * REF_VERM[4], f"{rot}: faixa da sessao inteira ({bs[4]} x {REF_VERM[4]}px)")
            if bn is not None and bs is not None:
                confere(bs[2] + 6 <= bn[0], f"{rot}: sessao nao invade o contador (sessao ate x={bs[2]}, contador desde x={bn[0]})")
            if deve and largura:
                cabem = (16 + (REF_VERM[2] - REF_VERM[0] + 1) + 10 <= L - 16 - 10 - (ref[0] + 8))
                confere((bs is not None) == cabem or abs((16 + (REF_VERM[2] - REF_VERM[0] + 1) + 10) - (L - 16 - 10 - (ref[0] + 8))) <= 14,
                        f"{rot}: regra previsivel - sessao {'aparece' if cabem else 'some'} quando {'cabe' if cabem else 'nao cabe'} ao lado do contador")
            if bn is None and bs is None and not (nao_deve and largura):
                confere(False, f"{rot}: nada apareceu na barra")
# os dois itens quando cabem: largura normal mostra sessao e contador juntos
j = janela("foto", 62, EO); im = j.grab().toImage()
confere(caixa(im, MAG, 0, BARRA) is not None and caixa(im, VERM, 0, BARRA, lim=60) is not None, "foto normal Orbitron 200% neg+ital: sessao e contador aparecem juntos")
# regra concreta pedida: 180 px, 62 CARS Orbitron 200% neg+ital => contador cabe sozinho, sessao some (nao ha espaco para os dois)
j = janela("foto", 62, EO, largura=180); im = j.grab().toImage()
confere(caixa(im, MAG, 0, BARRA) is not None and caixa(im, VERM, 0, BARRA, lim=60) is None, "foto 180px 62 CARS Orbitron 200%: contador visivel, indicador RACE removido (sem invasao)")
# contador oculto em 180 px: a sessao volta e nao sobra reserva
jo = janela("foto", 62, EO, oculta=True, largura=180); imo = jo.grab().toImage()
confere(caixa(imo, MAG, 0, BARRA) is None and caixa(imo, VERM, 0, BARRA, lim=60) is not None and jo._reserva == 0, "foto 180px contador oculto: sessao volta e a reserva e liberada")
# TREINO com fonte grande tambem precisa caber quando o contador esta oculto
# ou e grande demais para a barra (a reserva e zero nas duas situacoes).
for oculta in (True, False):
    for largura in (180, None):
        j = janela("foto", 100, EM, oculta=oculta, largura=largura)
        chave = j._chave_elementos() + "_estilo"
        j.config[chave]["sessao"] = dict(EM)
        dados = dados_com(100)
        dados["classificacao"]["tipo_sessao"] = "TREINO"
        j.atualizar(dados)
        im = j.grab().toImage()
        sessao = caixa(im, VERM, 0, BARRA, lim=60)
        if largura == 180:
            confere(caixa(im, MAG, 0, BARRA) is None, f"foto 180px, contador oculto={oculta}: sem reserva de contador")
        confere((sessao is None) == (largura == 180),
                f"foto {largura or 'normal'}px, contador oculto={oculta}: sessao grande aparece apenas quando cabe")
# aparencia padrao: borda direita e area antigas
j, im = janela("foto", 62, {}), None; im = j.grab().toImage(); b = caixa(im, MAG, 0, BARRA)
confere(b is not None and abs(b[2] - (j._largura - 16)) <= 3, "foto padrao: posicao a direita preservada")
# ajuste manual X/Y preservado (largura 210 e normal): deslocado exatamente o que foi pedido
for largura in (None, 210):
    j0 = janela("foto", 62, EO, largura=largura); j1 = janela("foto", 62, EO, pos_n=(-30, 6), largura=largura)
    b0, b1 = caixa(j0.grab().toImage(), MAG, 0, BARRA), caixa(j1.grab().toImage(), MAG, 0, BARRA)
    confere(b0 and b1 and abs((b1[0] - b0[0]) + 30) <= 2 and abs((b1[1] - b0[1]) - 6) <= 2 and (b1[2] - b1[0]) == (b0[2] - b0[0]), f"foto largura {largura or 'normal'}: ajuste manual X/Y preservado ({b0} -> {b1})")
# configuracao salva: fonte/posicao sobrevivem a recarga da janela (mesmo dicionario de config, nova instancia)
j0 = janela("foto", 62, EO, pos_n=(-12, 3)); c_salvo = dict(j0.config); K0 = type(j0); j2 = K0(dict(c_salvo)); ch = j2._chave_elementos()
confere(j2._estilo_elemento("ncars").get("fonte") == "orbitron" and j2._pos_elemento("ncars") == (-12.0, 3.0), "foto: fonte e posicao X/Y salvas do contador lidas de novo pela janela")

# ============================== CLASSICO: tres blocos em conjunto =================================================================
def blocos(j):
    im = j.grab().toImage()
    return im, caixa(im, AMAR, 0, BARRA), caixa(im, VERDE, 0, BARRA), caixa(im, MAG, 0, BARRA)
def referencia_contador_padrao(j, f, texto):
    # Usa fundo e formato de pixel da janela. Um QImage opaco muda o antialiasing
    # do Qt no Windows e produz uma mascara diferente para os mesmos glifos.
    im = QImage(j.size(), QImage.Format_ARGB32_Premultiplied)
    im.fill(Qt.transparent)
    p = QPainter(im)
    j._fundo(p)
    p.setFont(f)
    p.setPen(QColor(*MAG))
    p.drawText(QRectF(0, 5, _jl.LARGURA_LMU - 14, 18),
               Qt.AlignRight | Qt.AlignVCenter | Qt.TextDontClip, texto)
    p.end()
    return caixa(im, MAG, 0, BARRA)
GAP = 8
for total in (9, 62, 100):
    for nome_e, est in (("Orbitron 200% neg+ital (3 blocos)", EO), ("Michroma 200% neg+ital", EM), ("Orbitron 150%", {"fonte": "orbitron", "tam": 150}),
                        ("Bungee 150%", {"fonte": "bungee", "tam": 150}), ("padrao", {})):
        j = janela("classico", total, est, estilos={"contadores": est, "temperaturas": est})
        im, bc, bt, bn = blocos(j)
        rot = f"classico {total} carros {nome_e}"
        f_c = fonte_item("classico", "contadores", est, 9, QFont.DemiBold); f_t = fonte_item("classico", "temperaturas", est, 8, QFont.DemiBold)
        f_n = fonte_item("classico", "ncars", est, 8, QFont.DemiBold)
        refs = {"c": tinta(f_c, "01:02:03 / 06:00:00    VOLTA 11/--", AMAR), "t": tinta(f_t, "PISTA 31°C    AR 24°C", VERDE), "n": tinta(f_n, f"{total} CARROS", MAG)}
        # glifos inteiros de tudo o que apareceu (tempo/volta tem texto proprio da demo: compara so altura e a regra de nao-corte horizontal pela altura)
        if bn is not None and est:
            inteiro(bn, refs["n"], rot + " contador")
        if bt is not None: inteiro(bt, refs["t"], rot + " temperaturas")
        if bc is not None:
            confere(bc[3] - bc[1] + 1 >= tinta(f_c, "01:02:03", AMAR)[1], f"{rot}: tempo/volta inteiro na vertical ({bc[3] - bc[1] + 1}px)")
        # nenhuma sobreposicao entre blocos e nenhum bloco fora da janela/barra
        lista = [(n_, b_) for n_, b_ in (("tempo/volta", bc), ("temperaturas", bt), ("contador", bn)) if b_ is not None]
        lista.sort(key=lambda t: t[1][0])
        for (n1, b1_), (n2, b2_) in zip(lista, lista[1:]):
            confere(b1_[2] + GAP <= b2_[0], f"{rot}: {n1} nao sobrepoe {n2} (ate x={b1_[2]}, desde x={b2_[0]})")
        for n_, b_ in lista: confere(b_[2] <= _jl.LARGURA_LMU - 8, f"{rot}: {n_} dentro da janela (x1={b_[2]})")
        if not est:
            confere(bc is not None and bt is not None and bn is not None, f"{rot}: com a fonte padrao os tres blocos cabem e aparecem")
            ref_contador = referencia_contador_padrao(j, f_n, f"{total} CARROS")
            confere(bn == ref_contador and ref_contador is not None,
                    f"{rot}: contador padrao conserva a tinta e a ancora ({bn} x {ref_contador})")
# regra pedida: Orbitron 200% neg+ital nos tres blocos, 62 carros: sem sobreposicao (na ax as temperaturas cobriam tempo/volta)
j = janela("classico", 62, EO, estilos={"contadores": EO, "temperaturas": EO}); im, bc, bt, bn = blocos(j)
if bc and bt: confere(bc[2] + GAP <= bt[0], f"classico 62 carros Orbitron 200% nos 3 blocos: temperaturas nao sobrepoem tempo/volta ({bc[2]} < {bt[0]})")
else: confere(bc is not None, "classico 62 carros Orbitron 200% nos 3 blocos: tempo/volta aparece (prioridade) e o que nao coube sumiu inteiro")
# Prioridade por espaco preserva itens independentes quando um de maior
# prioridade esta desativado.
chave_classico = j._chave_elementos()
j = janela("classico", 62, {}, extra={chave_classico: {"contadores": False}})
im, bc, bt, bn = blocos(j)
confere(bc is None and bt is not None and bn is not None,
        "classico: desativar tempo/volta nao oculta temperaturas nem contador")
# reserva liberada: contador oculto => as temperaturas vao ate a borda (quando cabem)
for est in ({"fonte": "orbitron", "tam": 150, "negrito": True, "italico": True}, {}):
    j = janela("classico", 62, est, oculta=True, estilos={"contadores": est if est else {}, "temperaturas": est if est else {}}); im, bc, bt, bn = blocos(j)
    confere(bn is None, f"classico contador oculto ({est.get('tam', 'padrao')}): sem pixel do contador")
    confere(bt is not None and abs(bt[2] - (_jl.LARGURA_LMU - 14)) <= 6, f"classico contador oculto ({est.get('tam', 'padrao')}): reserva liberada, temperaturas na borda direita ({bt})")
# ajuste manual X/Y do contador preservado e as outros blocos intactos
b0 = blocos(janela("classico", 62, {"fonte": "orbitron", "tam": 150}))
b1 = blocos(janela("classico", 62, {"fonte": "orbitron", "tam": 150}, pos_n=(-25, 4)))
confere(b0[3] and b1[3] and abs((b1[3][0] - b0[3][0]) + 25) <= 2 and abs((b1[3][1] - b0[3][1]) - 4) <= 2 and b0[2][:4] == b1[2][:4] and b0[1][:4] == b1[1][:4], f"classico: X/Y do contador preservado, temperaturas e tempo/volta intactos ({b0[3]} -> {b1[3]})")
_P.end()
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
