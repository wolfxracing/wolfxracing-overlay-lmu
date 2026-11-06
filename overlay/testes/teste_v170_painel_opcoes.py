# -*- coding: utf-8 -*-
"""Build l - opcoes por painel com previa ao vivo: colunas da Classificacao, numeracao do Minimapa e imagem do volante.
Tudo em tela offscreen e dados de demonstracao (sem jogo)."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if len(sys.argv) > 1 and os.path.isdir(sys.argv[-1]) and os.path.exists(os.path.join(sys.argv[-1], "ov_central.py")):
    PASTA = sys.argv[-1]
sys.path.insert(0, PASTA)
from pathlib import Path
import overlay_iracing as o
import ov_central as c
import ov_classif_foto as foto
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QMenu

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); salvos = []; o.salvar_config = lambda c_: salvos.append(1)
falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

def img(w):
    return w.grab().toImage()

cfg = o.carregar_config(); cfg["travado"] = True
demo = o.Telemetria(demo=True)
dados = demo.ler()

# ===================================================================================================================
print("== 1) Classificacao: colunas personalizaveis (layout padrao)")
Foto = foto.construir(o)
cfg1 = dict(cfg); cfg1["mostrar_classificacao"] = False; cfg1["classif_colunas"] = {}
j = Foto(cfg1)
j.atualizar(dados)
confere(j.width() == foto.LARGURA_FOTO == 846, f"todas as colunas ligadas: largura original 846 ({j.width()})")
base_img = img(j)
ids = [g for g, _r, _k in Foto.GRUPOS]
confere("piloto" in Foto.FIXAS and len(ids) == 15, f"15 grupos de colunas, o piloto e fixo ({len(ids)})")
larg0 = j.width()
espacos = {}
for g in ids:
    if g in Foto.FIXAS:
        continue
    cfg1["classif_colunas"] = {g: False}
    j.opcoes_mudaram()
    espacos[g] = larg0 - j.width()
    confere(espacos[g] > 0 and g not in j._visiveis, f"esconder '{g}' encolhe a janela em {espacos[g]} px")
    confere(img(j) != base_img, f"esconder '{g}' muda o desenho")
    # nada sai da janela: a ultima coluna ainda cabe
    xs = [j.X[k] for gg, _r, ks in Foto.GRUPOS if gg in j._visiveis for k in ks]
    confere(max(xs) < j.width(), f"'{g}' oculta: as colunas restantes cabem na largura ({max(xs)} < {j.width()})")
# esconder varias: as de direita deslocam so pelas ocultas a esquerda
cfg1["classif_colunas"] = {"pos": False, "pais": False, "stint": False}
j.opcoes_mudaram()
confere(j.width() == larg0 - espacos["pos"] - espacos["pais"] - espacos["stint"], f"varias ocultas somam os espacos ({j.width()})")
confere(j.X["delta"] == Foto.X_BASE["delta"] - espacos["pos"] and j.X["piloto"] == Foto.X_BASE["piloto"] - espacos["pos"] - espacos["pais"],
        "cada coluna desloca apenas pelo que sumiu a esquerda dela")
# o piloto nunca some, mesmo se o config pedir
cfg1["classif_colunas"] = {g: False for g in ids}
j.opcoes_mudaram()
confere(j._visiveis == frozenset(Foto.FIXAS) and j.width() > 100, f"com tudo desligado sobra o piloto ({j.width()} px)")
j.grab()
# voltar ao padrao devolve o desenho original, pixel a pixel
cfg1["classif_colunas"] = {}
j.opcoes_mudaram()
confere(j.width() == 846 and img(j) == base_img, "religar tudo devolve exatamente o desenho original")
# atualizar() tambem percebe a mudanca (opcao trocada pelo menu/perfil, sem passar pela Central)
cfg1["classif_colunas"] = {"gap": False}
j.atualizar(dados)
confere("gap" not in j._visiveis and j.width() < 846, "atualizar() reaplica as colunas sozinho")
# valores estranhos no config nao derrubam
for lixo in (None, [], "x", {"pos": "nao", "gap": 0}):
    cfg1["classif_colunas"] = lixo
    try:
        j.opcoes_mudaram(); j.grab(); ok = True
    except Exception as e:
        ok = False
    confere(ok, f"config de colunas invalido ({lixo!r}) e tolerado")

# ===================================================================================================================
print("== 2) Minimapa: numero da posicao no marcador de cada carro")
pil = {0: {"numero": "7", "classe_cor": (255, 0, 0)}, 1: {"numero": "8", "classe_cor": (0, 0, 255)}, 2: {"numero": "9", "classe_cor": (255, 0, 0)}}
car = o.montar_mapa_carros(pil, 0, [0.5, 0.4, 0.3], [3, 3, 3], posc=[1, 1, 2], pos_geral=[2, 1, 3])
por_num = {k["numero"]: k for k in car}
confere(por_num["7"]["pos_classe"] == 1 and por_num["7"]["pos"] == 2 and por_num["9"]["pos_classe"] == 2 and por_num["9"]["pos"] == 3,
        "montar_mapa_carros leva posicao na classe e geral")
car2 = o.montar_mapa_carros(pil, 0, [0.5, 0.9, 0.3], [3, 3, 3], posc=[1, 1, 2], pos_geral=None, voltas=[3, 3, 3])
por_num2 = {k["numero"]: k["pos"] for k in car2}
confere(por_num2 == {"8": 1, "7": 2, "9": 3}, f"sem a posicao geral do jogo, ordena por voltas + progresso ({por_num2})")
car3 = o.montar_mapa_carros(pil, 0, [0.5, 0.4, 0.3], [3, 3, 3])
confere(all(k["pos"] is None and k["pos_classe"] is None for k in car3), "sem nenhum dado de posicao: None (nada inventado)")
car4 = o.montar_mapa_carros(pil, 0, [0.5, 0.4, 0.3], [3, 3, 3], posc=[0, -1, None], pos_geral=[0, 0, 0])
confere(all(k["pos"] is None and k["pos_classe"] is None for k in car4), "posicao 0/negativa/ausente nao vira numero")
MM = o.JanelaMinimapa
confere(MM.numero_do_carro({"pos_classe": 3, "pos": 8}, "classe") == 3 and MM.numero_do_carro({"pos_classe": 3, "pos": 8}, "geral") == 8,
        "modo classe x geral escolhe o numero certo")
confere(MM.numero_do_carro({"pos": 8}, "classe") == 8 and MM.numero_do_carro({}, "geral") is None and MM.numero_do_carro({"pos": 1}, "") is None,
        "sem o dado da classe usa o geral; desligado ou sem dado = nada")
cfg2 = dict(cfg); cfg2["mostrar_minimapa"] = False
m = MM(cfg2)
t0 = o.Telemetria(demo=True)
for _ in range(3):
    m.atualizar(t0.ler())
conf_m = m._amostra is not None
confere(conf_m and any(k.get("pos") for k in m._amostra[2]), "a pre-visualizacao (demo) traz posicoes nos carros do minimapa")
imgs = {}
for modo in ("off", "classe", "geral"):
    cfg2["minimapa_numeros"] = modo
    m.opcoes_mudaram()
    imgs[modo] = img(m)
confere(m.modo_numeracao() == "geral", "modo_numeracao le o config")
confere(imgs["off"] != imgs["classe"] and imgs["off"] != imgs["geral"], "ligar a numeracao muda o desenho do minimapa")
confere(imgs["classe"] != imgs["geral"], "classe e geral desenham numeros diferentes")
cfg2["minimapa_numeros"] = "qualquer coisa"
confere(m.modo_numeracao() == "", "valor desconhecido = desligado")

# ===================================================================================================================
print("== 3) Volante com imagem escolhida pelo piloto")
cfg3 = dict(cfg); cfg3["mostrar_grafico"] = False; cfg3["volante_imagem"] = ""
t3 = JanelaT = o.JanelaTelemetria(cfg3)
d3 = o.Telemetria(demo=True).ler()
d3["volante"] = 90.0
t3.atualizar(d3)
sem_img = img(t3)
# imagem de teste: um volante "diferente" (assimetrico, para se ver a rotacao)
orig = S / "meu_volante.png"
q = QImage(300, 200, QImage.Format_ARGB32); q.fill(Qt.transparent)
p = QPainter(q); p.setBrush(QColor(0, 200, 0)); p.drawEllipse(10, 10, 180, 180); p.setBrush(QColor(255, 0, 255)); p.drawRect(240, 80, 50, 40); p.end()
q.save(str(orig), "PNG")
rel = o.importar_imagem_volante(orig)
confere(rel == "volante/volante_personalizado.png" and (S / rel).is_file(), f"importar copia a imagem para a pasta do overlay ({rel})")
grande = S / "grande.png"; qg = QImage(2000, 1500, QImage.Format_ARGB32); qg.fill(QColor(10, 200, 10)); qg.save(str(grande), "PNG")
o.importar_imagem_volante(grande)
copia = QImage(str(S / rel))
confere(max(copia.width(), copia.height()) <= 512, f"imagem grande e reduzida para no maximo 512 px ({copia.width()}x{copia.height()})")
o.importar_imagem_volante(orig)
for ruim, msg in (((S / "nao_existe.png"), "arquivo inexistente"), ):
    try:
        o.importar_imagem_volante(ruim); ok = False
    except ValueError as e:
        ok = "imagem" in str(e).lower()
    confere(ok, f"{msg}: erro claro para o piloto (ValueError)")
txt = S / "texto.png"; txt.write_text("isto nao e uma imagem")
try:
    o.importar_imagem_volante(txt); ok = False
except ValueError:
    ok = True
confere(ok, "arquivo que nao e imagem (mesmo com extensao .png): recusado")
confere(o.imagem_volante({"volante_imagem": rel}) is not None and o.imagem_volante({"volante_imagem": ""}) is None
        and o.imagem_volante({"volante_imagem": "volante/nao_tem.png"}) is None and o.imagem_volante({}) is None,
        "imagem_volante: so devolve imagem quando ha arquivo valido")
cfg3["volante_imagem"] = rel; t3.opcoes_mudaram()
com_img = img(t3)
confere(com_img != sem_img, "com a imagem escolhida o painel desenha outro volante")
d3["volante"] = -60.0; t3.atualizar(d3)
girou = img(t3)
confere(girou != com_img, "a imagem gira com o volante (angulo diferente, desenho diferente)")
# regiao do volante acima do texto dos graus (o texto fica abaixo do centro)
reg = lambda im: im.copy(t3.width() - 54 - 44, 74 - 44, 88, 60)
d3["volante"] = 30.0; t3.atualizar(d3); giro_a = reg(img(t3))
d3["volante"] = 110.0; t3.atualizar(d3); giro_b = reg(img(t3))
confere(giro_a != giro_b, "com giro ligado a imagem do volante muda de angulo")
cfg3["volante_imagem_giro"] = False; t3.opcoes_mudaram()
d3["volante"] = 30.0; t3.atualizar(d3); fixa_a = reg(img(t3))
d3["volante"] = 110.0; t3.atualizar(d3); fixa_b = reg(img(t3))
confere(fixa_a == fixa_b, "com giro desligado a imagem fica parada (so o numero de graus muda)")
cfg3["volante_imagem_giro"] = True
cfg3["volante_imagem_tamanho"] = 50; t3.opcoes_mudaram(); pequeno = img(t3)
cfg3["volante_imagem_tamanho"] = 200; t3.opcoes_mudaram(); grande_i = img(t3)
confere(pequeno != grande_i, "o slider de tamanho muda o desenho")
# layout em barra tambem usa a imagem
cfg3["telemetria_barra"] = True; t3.recarregar_layout() if hasattr(t3, "recarregar_layout") else None
barra_com = img(t3)
cfg3["volante_imagem"] = ""; barra_sem = img(t3)
confere(barra_com != barra_sem, "o layout em barra tambem desenha a imagem")
cfg3["telemetria_barra"] = False
o.remover_imagem_volante()
confere(not (S / rel).exists() and o.imagem_volante({"volante_imagem": rel}) is None, "remover apaga a copia e volta ao volante desenhado")
o.importar_imagem_volante(orig)

# ===================================================================================================================
print("== 4) Central: as opcoes mudam a PREVIA NA HORA (sem esperar o ciclo de 500 ms)")
cfg4 = o.carregar_config(); cfg4["travado"] = True; cfg4["volante_imagem"] = ""
janelas = [o.JanelaTelemetria(cfg4), Foto(dict(cfg4, mostrar_classificacao=False)), o.JanelaMinimapa(cfg4), o.JanelaRelativo(cfg4), o.JanelaDeltaTrace(cfg4)]
# a janela real da classificacao usa o MESMO config da Central
janelas[1] = Foto(cfg4)
menu = QMenu(); acoes = {}
for jj in janelas:
    a = QAction(jj.CHAVE_ATIVO, menu); a.setCheckable(True); a.setChecked(bool(cfg4.get(jj.CHAVE_ATIVO, True)))
    a.toggled.connect(lambda v, k=jj.CHAVE_ATIVO: cfg4.__setitem__(k, bool(v))); acoes[jj.CHAVE_ATIVO] = a
def previa(jj):
    c2 = dict(cfg4); c2[jj.CHAVE_ATIVO] = False; c2["travado"] = True
    return type(jj)(c2)
escolhido = {"arq": None}
g = {"salvar": lambda: salvos.append(1), "importar_volante": o.importar_imagem_volante, "remover_volante": o.remover_imagem_volante}
cen = c.Central(janelas, acoes, cfg4, g, demo.ler, previa, "iRacing", "1.7.0")
cen._arquivo_volante = lambda: escolhido["arq"]
cen.mostrar()

# 4a) classificacao
n0 = len(salvos)
cen.abrir_detalhe("classificacao")
confere(len(cen._interruptores_colunas) == 15, "a pagina da Classificacao lista as 15 colunas")
confere(not cen._interruptores_colunas["piloto"].isEnabled(), "a coluna do piloto nao pode ser desligada")
antes = cen.det_previa._pix.toImage() if cen.det_previa._pix else None
prev = cen._previas["classificacao"]
w_antes = prev.width()
cen._interruptores_colunas["gap"].setChecked(False)
depois = cen.det_previa._pix.toImage()
confere(cfg4["classif_colunas"].get("gap") is False, "o config guarda a coluna oculta")
confere(prev.width() < w_antes, f"a previa encolheu na hora ({w_antes} -> {prev.width()})")
confere(depois != antes, "a imagem da previa mudou imediatamente")
confere(janelas[1].width() < 846 and "gap" not in janelas[1]._visiveis, "a janela REAL da Classificacao tambem mudou")
confere(len(salvos) > n0, "a mudanca foi salva no config")
cen._interruptores_colunas["gap"].setChecked(True)
confere(cfg4["classif_colunas"].get("gap") is None and prev.width() == w_antes, "religar a coluna volta ao normal")
cen._interruptores_colunas["pais"].setChecked(False); cen._interruptores_colunas["lic"].setChecked(False)
cen._todas_colunas("classificacao")
confere(cfg4["classif_colunas"] == {} and prev.width() == w_antes and all(i.isChecked() for i in cen._interruptores_colunas.values()),
        "'Mostrar todas as colunas' restaura tudo")

# 4a) delta trace: layout do painel (build r)
cen.abrir_detalhe("delta_trace")
for _ in range(3):
    cen._ciclo(forcar=True)
confere(set(cen._chips_layout_delta) == {"grafico", "racelab"}, "delta trace: duas opcoes de layout na Central")
cen._chips_layout_delta["racelab"].click()
confere(cfg4["delta_trace_layout"] == "racelab" and cen._previas["delta_trace"].config["delta_trace_layout"] == "racelab", "layout RaceLab vai para o config real e para a previa")
cen._chips_layout_delta["grafico"].click()
confere(cfg4["delta_trace_layout"] == "grafico", "voltar ao layout em grafico")

cen._interruptores_delta["blocos"].setChecked(False)
confere(cfg4["delta_trace_elementos"].get("blocos") is False and cen._previas["delta_trace"].config["delta_trace_elementos"].get("blocos") is False, "elemento desligado vai para o config real e para a previa")
confere(janelas[4].height() < 200, "a janela real do Delta Trace encolheu (sem blocos)")
cen._interruptores_delta["mapa"].setChecked(False)
cen._todos_elementos_delta("delta_trace")
confere(cfg4["delta_trace_elementos"] == {} and all(i.isChecked() for i in cen._interruptores_delta.values()) and janelas[4].height() == 200, "'Mostrar todos os elementos' restaura tudo")

# 4b) minimapa
cen.abrir_detalhe("minimapa")
cen._ciclo(forcar=True)
for _ in range(3):
    cen._ciclo(forcar=True)
confere(set(cen._chips_numeracao) == {"off", "classe", "geral"}, "tres opcoes de numeracao")
cen._chips_numeracao["off"].click()
p_off = cen.det_previa._pix.toImage()
cen._chips_numeracao["geral"].click()
p_ger = cen.det_previa._pix.toImage()
confere(cfg4["minimapa_numeros"] == "geral" and cen._previas["minimapa"].config["minimapa_numeros"] == "geral",
        "a escolha vai para o config real e para a previa")
confere(p_off != p_ger, "a previa do minimapa muda na hora ao ligar a numeracao")
confere(janelas[2].modo_numeracao() == "geral", "a janela real tambem")

# 4c) volante
cen.abrir_detalhe("principal")
confere(hasattr(cen, "_lb_volante") and "desenhado" in cen._lb_volante.text(), "pagina da Telemetria mostra o volante desenhado como padrao")
confere(not cen._sl_tam_volante.isEnabled() and not cen._bt_remover_volante.isEnabled(), "sem imagem, os ajustes ficam desabilitados")
p_sem = cen.det_previa._pix.toImage()
escolhido["arq"] = None
cen._ao_escolher_volante("principal")
confere(not cfg4.get("volante_imagem"), "cancelar a escolha do arquivo nao muda nada")
escolhido["arq"] = str(txt)
import ov_central
caixas = []
ov_central.QMessageBox.warning = staticmethod(lambda *a, **k: caixas.append(a[2]))
cen._ao_escolher_volante("principal")
confere(len(caixas) == 1 and not cfg4.get("volante_imagem"), "arquivo invalido: mensagem ao piloto e nada muda")
escolhido["arq"] = str(orig)
cen._ao_escolher_volante("principal")
confere(cfg4.get("volante_imagem") == "volante/volante_personalizado.png" and "volante_personalizado.png" in cen._lb_volante.text(), "escolher a imagem grava no config")
p_img = cen.det_previa._pix.toImage()
confere(p_img != p_sem, "a previa mostra a nova imagem na hora")
confere(cen._sl_tam_volante.isEnabled() and cen._bt_remover_volante.isEnabled(), "com imagem, os ajustes ficam habilitados")
cen._sl_tam_volante.setValue(160)
confere(cfg4["volante_imagem_tamanho"] == 160 and cen.det_previa._pix.toImage() != p_img, "o slider de tamanho atualiza a previa na hora")
cen._it_giro.setChecked(False)
confere(cfg4["volante_imagem_giro"] is False, "a chave de giro e gravada")
cen._ao_remover_volante("principal")
confere(cfg4["volante_imagem"] == "" and cen._previas["principal"].config["volante_imagem"] == "" and cen.det_previa._pix.toImage() != p_img,
        "'Voltar ao desenhado' remove a imagem e a previa volta ao volante desenhado")
confere("desenhado" in cen._lb_volante.text(), "o texto volta a 'volante desenhado'")

# 4d) outros paineis nao ganham blocos extras e continuam abrindo
for chave in ("relativo",):
    cen.abrir_detalhe(chave)
    confere(cen.paginas.currentIndex() == 2, f"o painel '{chave}' continua abrindo normalmente")
cen.close()

# ===================================================================================================================
try:
    import ov_janela_lmu as jl
    print("== 5) LMU: colunas da Classificacao")
    Lmu = jl.construir_foto_lmu()
    cfg5 = dict(cfg); cfg5["mostrar_classificacao"] = False; cfg5["classif_colunas"] = {}
    l = Lmu(cfg5)
    confere(l.width() == 846 and len(Lmu.GRUPOS) == 13, f"LMU: 13 grupos, largura original 846 ({l.width()})")
    try:
        import overlay_lmu as ol
        d5 = ol.TelemetriaLMU(demo=True).ler()
        l.atualizar(d5)
        base5 = img(l)
        for gid in [g for g, _r, _k in Lmu.GRUPOS if g not in Lmu.FIXAS]:
            cfg5["classif_colunas"] = {gid: False}; l.opcoes_mudaram()
            confere(l.width() < 846 and img(l) != base5, f"LMU: esconder '{gid}' encolhe ({846 - l.width()} px) e muda o desenho")
        cfg5["classif_colunas"] = {}; l.opcoes_mudaram()
        confere(l.width() == 846 and img(l) == base5, "LMU: religar tudo devolve o desenho original")
    except Exception as e:
        confere(False, f"LMU: desenho com dados de demo falhou ({e!r})")
    import ov_classif_foto as _foto7
    try:
        print("== 7) LMU: ordem das colunas e cabecalho")
        cfg7 = dict(cfg); cfg7["mostrar_classificacao"] = False; cfg7["classif_colunas"] = {}; cfg7["classif_ordem"] = []; cfg7["classif_cabecalho"] = {}
        l7 = Lmu(cfg7); import overlay_lmu as ol7
        d7 = ol7.TelemetriaLMU(demo=True).ler(); l7.atualizar(d7); b7 = img(l7); w7, h7 = l7.width(), l7.height()
        idl = [g for g, _r, _k in Lmu.GRUPOS]
        cfg7["classif_ordem"] = list(reversed(idl)); l7.opcoes_mudaram(); l7.atualizar(d7)
        confere(l7.width() == w7 and img(l7) != b7 and l7.X["comb"] < l7.X["pos"], "LMU: ordem invertida cabe na janela e muda o desenho")
        cfg7["classif_ordem"] = []; l7.opcoes_mudaram(); l7.atualizar(d7)
        confere(img(l7) == b7, "LMU: ordem original restaurada identica")
        cfg7["classif_cabecalho"] = {"ncars": False}; l7.opcoes_mudaram(); l7.atualizar(d7)
        confere(img(l7) != b7 and l7._reserva == 0, "LMU: esconder 'N CARS' muda o desenho e libera a reserva da barra")
        cfg7["classif_cabecalho"] = {"barra": False}; l7.opcoes_mudaram(); l7.atualizar(d7)
        confere(l7.height() == h7 - _foto7.ALTURA_BARRA, "LMU: sem a barra superior a janela encolhe")
        cfg7["classif_cabecalho"] = {"titulos": False}; l7.opcoes_mudaram(); l7.atualizar(d7)
        confere(l7.height() == h7 - _foto7.ALTURA_ROTULOS and img(l7) != b7, "LMU: sem os titulos das colunas a janela encolhe")
        cfg7["classif_cabecalho"] = {}; l7.opcoes_mudaram(); l7.atualizar(d7)
        confere(img(l7) == b7 and l7.height() == h7, "LMU: cabecalho restaurado identico")
    except Exception as e:
        confere(False, f"LMU 7: falhou ({e!r})")
except ImportError:
    print("(arvore iRacing: sem ov_janela_lmu, secao 5 ignorada)")

# ===================================================================================================================
print("== 6) Build m: ordem das colunas e itens do cabecalho (layout padrao da Classificacao)")
cfg6 = dict(cfg); cfg6["mostrar_classificacao"] = False; cfg6["classif_colunas"] = {}; cfg6["classif_ordem"] = []; cfg6["classif_cabecalho"] = {}
j6 = Foto(cfg6); j6.atualizar(dados)
base6 = img(j6); w6, h6 = j6.width(), j6.height()
ids6 = [g for g, _r, _k in Foto.GRUPOS]
confere(j6._ordem() == tuple(ids6), "ordem padrao = ordem original dos grupos")
def reaplica(j):
    j.opcoes_mudaram(); j.atualizar(dados)
# troca pos <-> delta
cfg6["classif_ordem"] = ["delta", "pos"] + [g for g in ids6 if g not in ("pos", "delta")]
reaplica(j6)
confere(j6.X["delta"] < j6.X["pos"] and j6.width() == w6, f"trocar 'pos' e 'delta' inverte as posicoes sem mudar a largura (delta x={j6.X['delta']}, pos x={j6.X['pos']})")
confere(img(j6) != base6, "a troca muda o desenho")
# piloto em primeiro
cfg6["classif_ordem"] = ["piloto"]
reaplica(j6)
confere(j6.X["piloto"] == min(j6.X.values()) and j6._ordem()[0] == "piloto" and len(j6._ordem()) == 15, "piloto movido para a primeira posicao; o resto segue na ordem original")
# ordem invertida: sem sobreposicao e dentro da janela
cfg6["classif_ordem"] = list(reversed(ids6))
reaplica(j6)
vis = sorted(((min(j6.X[k] for k in ks), g) for g, _r, ks in Foto.GRUPOS))
confere(j6.width() == w6 and vis[0][0] == 12 and all(0 <= x < j6.width() for x, _g in vis), "ordem invertida: tudo dentro da janela e na mesma largura")
trechos = {g: (min(Foto.X_BASE[k] for k in ks)) for g, _r, ks in Foto.GRUPOS}
ordenados = sorted(trechos.items(), key=lambda t: t[1])
larg_trecho = {g: ((ordenados[n + 1][1] if n + 1 < len(ordenados) else Foto.FIM_COLUNAS) - x0) for n, (g, x0) in enumerate(ordenados)}
pos_x = sorted((min(j6.X[k] for k in ks), g) for g, _r, ks in Foto.GRUPOS)
confere(all(pos_x[n + 1][0] - pos_x[n][0] == larg_trecho[pos_x[n][1]] for n in range(len(pos_x) - 1)), "ordem invertida: cada coluna ocupa exatamente o seu trecho (sem sobrepor)")
# ordem + ocultas
cfg6["classif_colunas"] = {"gap": False}
reaplica(j6)
confere(j6.width() == w6 - larg_trecho["gap"], f"ordem invertida + 'gap' oculta: largura {w6} -> {j6.width()}")
cfg6["classif_colunas"] = {}
# configuracoes invalidas nao quebram
for lixo in ("abc", 7, None, ["x", "x", "pos", "pos", 3, None, "gap"], {"a": 1}):
    cfg6["classif_ordem"] = lixo
    try:
        reaplica(j6); o_ = j6._ordem()
        ok_ = sorted(o_) == sorted(ids6) and len(o_) == 15
    except Exception:
        ok_ = False
    confere(ok_, f"classif_ordem invalida {lixo!r} e ignorada com seguranca")
cfg6["classif_ordem"] = ["gap", "gap", "pos"]
reaplica(j6)
confere(j6._ordem()[:2] == ("gap", "pos"), "ids repetidos contam uma vez")
cfg6["classif_ordem"] = []
reaplica(j6)
confere(img(j6) == base6 and j6.width() == w6, "ordem original restaurada: desenho identico ao inicial")
# cabecalho
cab = (dados.get("classificacao") or {}).get("cabecalho") or {}
temdado = {"sessao": bool((dados.get("classificacao") or {}).get("tipo_sessao") or cab.get("sessao")), "volta": cab.get("volta") is not None,
           "tempo": cab.get("decorrido") is not None and bool(cab.get("total")), "ar": cab.get("ar") is not None, "pista": cab.get("pista") is not None,
           "umidade": cab.get("umidade") is not None, "inc": cab.get("inc") is not None, "clima": bool(cab.get("clima"))}
for iid, _r in Foto.CABECALHO:
    if iid in ("barra", "titulos"):
        continue
    cfg6["classif_cabecalho"] = {iid: False}
    reaplica(j6)
    if temdado.get(iid):
        confere(img(j6) != base6 and j6.width() == w6 and j6.height() == h6, f"cabecalho: esconder '{iid}' muda o desenho sem mexer no tamanho")
    else:
        confere(j6.width() == w6, f"cabecalho: '{iid}' sem dado na demo; esconder nao quebra")
cfg6["classif_cabecalho"] = {"barra": False}; reaplica(j6)
confere(j6.height() == h6 - foto.ALTURA_BARRA, f"sem a barra superior a janela perde {foto.ALTURA_BARRA} px ({h6} -> {j6.height()})")
cfg6["classif_cabecalho"] = {"titulos": False}; reaplica(j6)
confere(j6.height() == h6 - foto.ALTURA_ROTULOS, f"sem os titulos das colunas a janela perde {foto.ALTURA_ROTULOS} px ({h6} -> {j6.height()})")
cfg6["classif_cabecalho"] = {"barra": False, "titulos": False}; reaplica(j6)
confere(j6.height() == h6 - foto.ALTURA_BARRA - foto.ALTURA_ROTULOS, "sem barra e sem titulos: perde os dois")
cfg6["classif_cabecalho"] = "lixo"; reaplica(j6)
confere(img(j6) == base6, "classif_cabecalho invalido e ignorado")
cfg6["classif_cabecalho"] = {}; reaplica(j6)
confere(img(j6) == base6 and j6.height() == h6, "cabecalho restaurado: desenho identico ao inicial")

print("== 6b) Central: setas de ordem e itens do cabecalho com previa ao vivo")
cen.abrir_detalhe("classificacao")
jreal = cen._janela("classificacao")
prev = cen._previas["classificacao"]
ordem0 = list(cen._interruptores_colunas.keys())
confere(ordem0 == ids6, "a lista da Central comeca na ordem original")
img0 = cen.det_previa._pix.toImage()
cen._mover_coluna("classificacao", jreal, "pos", 1)
confere(cfg4["classif_ordem"][:2] == ["delta", "pos"], f"seta para baixo grava a nova ordem {cfg4['classif_ordem'][:3]}")
confere(list(cen._interruptores_colunas.keys())[:2] == ["delta", "pos"], "a lista da Central se reordena na hora")
confere(cen.det_previa._pix.toImage() != img0, "a previa ao vivo mudou na hora com a nova ordem")
confere(prev.X["delta"] < prev.X["pos"] and jreal.X["delta"] < jreal.X["pos"], "previa e janela real usam a mesma ordem")
cen._mover_coluna("classificacao", jreal, "pos", -1)
confere(cfg4["classif_ordem"][:2] == ["pos", "delta"], "seta para cima desfaz")
cen._mover_coluna("classificacao", jreal, "pos", -1)
confere(cfg4["classif_ordem"][0] == "pos", "mover alem do inicio nao faz nada")
cen._mover_coluna("classificacao", jreal, "piloto", -3)
cen._ordem_original("classificacao", jreal)
confere(cfg4["classif_ordem"] == [] and list(cen._interruptores_colunas.keys()) == ids6, "'Ordem original' restaura config e lista")
confere(cen.det_previa._pix.toImage() == img0, "e a previa volta exatamente ao desenho inicial")
h_prev = prev.height()
cen._interruptores_cab["barra"].setChecked(False)
confere(cfg4["classif_cabecalho"].get("barra") is False and prev.height() == h_prev - foto.ALTURA_BARRA, "interruptor 'Barra superior' encolhe a previa na hora")
cen._interruptores_cab["ar"].setChecked(False)
cen._todo_cabecalho("classificacao")
confere(cfg4["classif_cabecalho"] == {} and all(i.isChecked() for i in cen._interruptores_cab.values()) and prev.height() == h_prev,
        "'Mostrar todo o cabecalho' restaura tudo")
confere(cen.det_previa._pix.toImage() == img0, "previa identica ao inicial depois de restaurar")
cen.abrir_detalhe("minimapa"); cen.abrir_detalhe("classificacao")
confere(list(cen._interruptores_colunas.keys()) == ids6 and len(cen._interruptores_cab) == len(Foto.CABECALHO), "reabrir a pagina reconstroi lista e cabecalho")

# ===================================================================================================================
print("== 8) Build n: altura sem dados com barra/titulos escondidos; erro da Central vai para o log")
cfg8 = dict(cfg); cfg8["mostrar_classificacao"] = False; cfg8["classif_colunas"] = {}; cfg8["classif_ordem"] = []; cfg8["classif_cabecalho"] = {}
j8 = Foto(cfg8)                                    # sem nenhum atualizar(): estado "sem dados"
pad = j8.ALTURA_PADRAO
confere(j8._altura_necessaria() == pad == 170 and j8.height() == 170, f"sem dados e tudo visivel: altura original {pad} preservada ({j8.height()})")
for cab8, esperado in (({"barra": False}, pad - foto.ALTURA_BARRA), ({"titulos": False}, pad - foto.ALTURA_ROTULOS),
                       ({"barra": False, "titulos": False}, pad - foto.ALTURA_BARRA - foto.ALTURA_ROTULOS)):
    cfg8["classif_cabecalho"] = cab8; j8.opcoes_mudaram()
    confere(j8._altura_necessaria() == esperado and j8.height() == esperado and j8.height() >= 80, f"sem dados, cabecalho {sorted(cab8)} escondido: altura {esperado} ({j8.height()})")
    img(j8)                                         # a mensagem 'sem dados' desenha sem erro
cfg8["classif_cabecalho"] = {}; j8.opcoes_mudaram()
confere(j8.height() == pad, "sem dados: restaurar o cabecalho devolve a altura original")
j8.atualizar(dados); com_dados = j8.height()
cfg8["classif_cabecalho"] = {"barra": False, "titulos": False}; j8.opcoes_mudaram()
confere(j8.height() == com_dados - foto.ALTURA_BARRA - foto.ALTURA_ROTULOS, "com dados a conta continua a mesma (build m)")
# erro dentro de opcoes_mudaram(): registrado no log, Central continua
erros = []
cen8 = c.Central(janelas, acoes, cfg4, dict(g, registrar_erro=lambda ctx: erros.append(ctx)), demo.ler, previa, "iRacing", "1.7.0")
cen8.abrir_detalhe("classificacao")
class Quebrada:
    def opcoes_mudaram(self): raise RuntimeError("falha simulada")
orig = cen8._previas["classificacao"]
cen8._previas["classificacao"] = Quebrada()
try:
    cen8._aplicar_opcao("classificacao"); seguiu = True
except Exception as e:
    seguiu = False
confere(seguiu, "falha em opcoes_mudaram() nao interrompe a Central")
confere(any("classificacao" in e and "Quebrada" in e for e in erros), f"o erro foi entregue ao log com contexto ({erros})")
cen8._previas["classificacao"] = orig
n_erros = len(erros)
cen8._aplicar_opcao("classificacao")
confere(len(erros) == n_erros, "sem falha, nada novo e registrado")
# sem gancho: cai no stderr, sem levantar
import io, contextlib
cen9 = c.Central(janelas, acoes, cfg4, dict(g), demo.ler, previa, "iRacing", "1.7.0")
cen9._previas["classificacao"] = Quebrada()
buf = io.StringIO()
with contextlib.redirect_stderr(buf):
    try:
        cen9._aplicar_opcao("classificacao"); ok9 = True
    except Exception:
        ok9 = False
confere(ok9 and "falha simulada" in buf.getvalue(), "sem gancho de log, o erro vai para o stderr e a Central segue")
# o log real: registrar_erro grava no overlay_log
try:
    raise ValueError("teste de log")
except ValueError:
    o.registrar_erro("Central: teste n")
log = (S / "l.txt").read_text(encoding="utf-8", errors="replace") if (S / "l.txt").exists() else ""
confere("teste n" in log, "registrar_erro do overlay grava no overlay_log.txt")

print()
print("RESULTADO:", "OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
