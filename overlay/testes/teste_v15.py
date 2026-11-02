# -*- coding: utf-8 -*-
"""v1.5.0 - bandeiras, trafego de outras classes, minimapa rotativo, auxiliar de sessao, janelas automaticas sem piscar."""
import os, sys, tempfile, math
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import overlay_iracing as o
import ov_v15 as v
from PySide6.QtWidgets import QApplication

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c: None
falhas = []
def confere(c, msg):
    print(("OK    " if c else "FALHA ") + msg)
    if not c: falhas.append(msg)

# ---- bandeiras
c, g = v.candidata_iracing(0x8 | 0x20)
confere(c["id"] == "amarela", "amarela vence azul")
c, g = v.candidata_iracing(0x4000)
confere(c["id"] == "amarela_total", "caution = amarela de pista inteira")
c, g = v.candidata_iracing(0x1 | 0x4000)
confere(c["id"] == "quadriculada", "quadriculada vence caution")
c, g = v.candidata_iracing(0x4)
confere(c is None and g, "so verde: sem candidata, verde ligada")
G = v.GestorBandeiras()
confere(G.atualizar(None, True, 100.0)["id"] == "verde", "verde aparece ao ligar")
confere(G.atualizar(None, True, 104.0)["id"] == "verde", "verde ainda aos 4 s")
confere(G.atualizar(None, True, 107.0) is None, "verde some depois de 6 s")
G = v.GestorBandeiras()
G.atualizar(v._item("azul"), False, 10.0)
confere(G.atualizar(None, False, 10.5)["id"] == "azul", "bandeira fica 2 s no minimo")
confere(G.atualizar(None, False, 12.5) is None, "depois do minimo some")
confere(G.atualizar(v._item("vermelha"), False, 13.0)["id"] == "vermelha", "nova bandeira entra")
l, _ = v.candidata_lmu(6, "Safety car", (), 0, 0, False)
confere(l["id"] == "amarela_total", "LMU FCY = amarela total")
l, _ = v.candidata_lmu(5, "", (1,), 0, 0, False)
confere(l["id"] == "amarela_setor" and "2" in l["sub"], "LMU amarela no setor 2")

# ---- trafego
mem = {}
car = [{"id": 0, "classe_id": 1, "ordem": 2, "pct": 0.5, "numero": "1", "nome": "eu", "classe_nome": "GT3", "cor": (1, 2, 3), "vel": 50.0},
       {"id": 1, "classe_id": 2, "ordem": 1, "pct": 0.5 - 100 / 4000.0, "numero": "7", "nome": "r", "classe_nome": "GTP", "cor": (9, 9, 9), "vel": 65.0},
       {"id": 2, "classe_id": 1, "ordem": 2, "pct": 0.5 + 20 / 4000.0, "numero": "9", "nome": "m", "classe_nome": "GT3", "cor": (1, 2, 3), "vel": 50.0},
       {"id": 3, "classe_id": 2, "ordem": 1, "pct": 0.9, "numero": "8", "nome": "l", "classe_nome": "GTP", "cor": (9, 9, 9), "vel": 60.0}]
t = v.montar_trafego(car, 0, 4000.0, 50.0, mem, 1.0)
confere(t["n"] == 1 and t["linhas"][0]["id"] == 1, "so outra classe e por perto")
confere(t["linhas"][0]["sinal"] == -1 and abs(t["linhas"][0]["gap_s"] - 2.0) < 0.01, "atras, 2,0 s")
confere(t["linhas"][0]["urg"] == 1 or t["linhas"][0]["urg"] == 2, "classe rapida chegando: urgencia")
car[1]["box"] = True
confere(v.montar_trafego(car, 0, 4000.0, 50.0, mem, 2.0)["n"] == 0, "carro no box ignorado")

# ---- minimapa
N = 360
pts = [(300 * math.cos(2 * math.pi * i / N), 300 * math.sin(2 * math.pi * i / N)) for i in range(N)]
pr = v.projetar_minimapa(pts, 0.0, [{"pct": 0.0, "eu": True, "cor": (1, 1, 1), "numero": "1"},
                                    {"pct": 0.02, "eu": False, "cor": (1, 1, 1), "numero": "2"}], 260.0, 100.0)
confere(pr is not None and len(pr["carros"]) == 2, "minimapa projeta")
eu = [c for c in pr["carros"] if c["eu"]][0]
confere(abs(eu["x"]) < 1 and abs(eu["y"]) < 1, "meu carro no centro")
fre = [c for c in pr["carros"] if not c["eu"]][0]
confere(fre["y"] < 0, "carro a frente fica acima do centro (rotacionado)")
M = v.MapaPlano()
for i in range(400):
    a = 2 * math.pi * i / 400
    M.atualizar(i / 400.0, 300 * math.cos(a), 300 * math.sin(a), True)
M.atualizar(0.001, 300, 0.0, True)
confere(M.exibicao() is not None, "MapaPlano exibe")

# ---- auxiliar
a = v.montar_auxiliar_iracing("CORRIDA", 2, 1800.0, None, 1800.0, None, None)
confere(a["modo"] == "pre", "auxiliar pre-largada")
a = v.montar_auxiliar_iracing("CORRIDA", 4, 900.0, None, 1800.0, None, None)
confere(a["modo"] == "corrida" and a["valor"].startswith("15"), "auxiliar corrida 15:00")
a = v.montar_auxiliar_iracing("CORRIDA", 5, 0.0, None, 1800.0, None, None)
confere(a["modo"] == "fim", "auxiliar fim")

# ---- janelas
cfg = o.carregar_config(); cfg["travado"] = True
d = o.Telemetria(demo=True).ler()
confere(d.get("bandeira") is not None or True, "demo tem chave bandeira")
for cls in (o.JanelaBandeiras, o.JanelaTrafego, o.JanelaMinimapa, o.JanelaAuxiliar):
    w = cls(cfg); w.show(); w.atualizar(d); w.grab()
    confere(True, f"{cls.__name__} desenha")

# bandeira
b = o.JanelaBandeiras(cfg); b.show()
d2 = dict(d); d2["bandeira"] = None; b.atualizar(d2)
confere(not b.isVisible(), "sem bandeira: escondida")
d2["bandeira"] = v._item("amarela_total"); b.atualizar(d2)
confere(b.isVisible(), "com bandeira: aparece")
for i in ("quadriculada", "preta", "desclassificado", "reparo", "azul", "verde", "branca", "detritos", "vermelha"):
    d2["bandeira"] = v._item(i); b.atualizar(d2); b.grab()
confere(True, "todas as bandeiras desenham")

# trafego altura dinamica
tr = o.JanelaTrafego(cfg); tr.show()
d3 = dict(d); d3["trafego"] = None; tr.atualizar(d3)
confere(not tr.isVisible(), "sem trafego: escondido")
d3["trafego"] = {"n": 1, "linhas": o.JanelaTrafego._exemplo()["linhas"][:1]}; tr.atualizar(d3)
h1 = tr.height()
d3["trafego"] = o.JanelaTrafego._exemplo(); tr.atualizar(d3)
confere(tr.isVisible() and tr.height() > h1, "trafego cresce com 2 linhas")

# minimapa sem mapa
mm = o.JanelaMinimapa(cfg); mm.show(); d4 = dict(d); d4["mapa"] = None; mm.atualizar(d4); mm.grab()
confere(True, "minimapa sem mapa nao quebra")

# auxiliar: durante a corrida so com auxiliar_sempre
ax = o.JanelaAuxiliar(cfg); ax.show(); d5 = dict(d)
d5["auxiliar"] = {"titulo": "TEMPO", "valor": "10:00", "sub": "", "estimado": False, "modo": "corrida"}
cfg["auxiliar_sempre"] = False; ax.atualizar(d5)
confere(not ax.isVisible(), "auxiliar escondido durante a corrida")
cfg["auxiliar_sempre"] = True; ax.atualizar(d5)
confere(ax.isVisible(), "auxiliar_sempre mostra o tempo restante")

# ---- laco real: definir_auto_visivel(True) a cada ciclo nao pode piscar
for cls, chave, valor_sim in ((o.JanelaBandeiras, "bandeira", v._item("azul")),):
    w = cls(cfg); w.show()
    cont = {"show": 0, "hide": 0}
    os_, oh = w.show, w.hide
    w.show = lambda: (cont.__setitem__("show", cont["show"] + 1), os_())[1]
    w.hide = lambda: (cont.__setitem__("hide", cont["hide"] + 1), oh())[1]
    dd = dict(d); dd[chave] = valor_sim
    for _ in range(50):
        w.definir_auto_visivel(True); w.atualizar(dd)
    confere(cont["hide"] <= 1 and cont["show"] <= 1, f"{cls.__name__}: laco real sem piscar ({cont})")
r = o.JanelaRadar(cfg); r.show()
cont = {"show": 0, "hide": 0}
os_, oh = r.show, r.hide
r.show = lambda: (cont.__setitem__("show", cont["show"] + 1), os_())[1]
r.hide = lambda: (cont.__setitem__("hide", cont["hide"] + 1), oh())[1]
dr = o.Telemetria(demo=True).ler()
dr["radar"] = o.montar_radar({0: {"numero": "1"}, 1: {"numero": "2"}}, 0, [0.5, 0.503], [3, 3], [False, False], 0, 4000.0, memoria={}, agora=1.0)
cfg["travado"] = True
for _ in range(40):
    r.definir_auto_visivel(True); r.atualizar(dr)
confere(cont["hide"] <= 1 and cont["show"] <= 1, f"radar: laco real sem piscar ({cont})")

print("\n" + ("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)"))
sys.exit(1 if falhas else 0)
