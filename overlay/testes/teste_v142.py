# -*- coding: utf-8 -*-
"""v1.4.2 - radar automatico e carro ao lado, posicoes ganhas/perdidas na classificacao."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import overlay_iracing as o
from PySide6.QtWidgets import QApplication

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c: None
falhas = []
def confere(c, msg):
    print(("OK    " if c else "FALHA ") + msg)
    if not c: falhas.append(msg)

cfg = o.carregar_config(); cfg["travado"] = True
confere(cfg["radar_auto"] is True, "radar automatico ligado por padrao")
P = {0: {"numero": "1"}, 1: {"numero": "21"}}
def radar(pct_outro, lado, t):
    return o.montar_radar(P, 0, [0.5, pct_outro], [3, 3], [False, False], lado, 4000.0, memoria={}, agora=t)
d = o.Telemetria(demo=True).ler()
r = o.JanelaRadar(cfg); r.show()

# --- 1) aparece so com carro por perto
d["radar"] = radar(0.6, 0, 1.0)                       # outro carro a 400 m
r._visto_t = 0.0; r.atualizar(d)
confere(not r.auto_visivel, "sem carro por perto: radar escondido")
d["radar"] = radar(0.5030, 0, 2.0)                    # 12 m a frente
r.atualizar(d)
confere(r.auto_visivel, "carro a 12 m: radar aparece")
d["radar"] = radar(0.6, 0, 3.0); r.atualizar(d)
confere(r.auto_visivel, "carro acabou de se afastar: continua ~1,5 s (nao pisca)")
r._visto_t -= 2.0; r.atualizar(d)
confere(not r.auto_visivel, "depois de 1,5 s sem carro: escondido")
d["radar"] = radar(0.5, 2, 4.0); r.atualizar(d)
confere(r.auto_visivel, "SDK acusa carro ao lado: aparece")
cfg["travado"] = False; d["radar"] = radar(0.6, 0, 5.0); r._visto_t = 0.0; r.atualizar(d)
confere(r.auto_visivel, "destravado (modo mover): sempre visivel")
cfg["travado"] = True; cfg["radar_auto"] = False; r.atualizar(d)
confere(r.auto_visivel, "radar automatico desligado: sempre visivel")
cfg["radar_auto"] = True

# --- 2) carro ao lado: encostado, AO LADO, faixa de alerta
rad = radar(0.5, 2, 6.0)
c = rad["carros"][0]
confere(c["urgencia"] == 3 and c["lado_fonte"] == "inferido" and c["faixa"] == -1.0, "carro ao lado confirmado: urgencia 3, esquerda")
d["radar"] = rad; r.atualizar(d); r.repaint()
img = r.grab()
confere(not img.isNull(), "radar com carro ao lado desenha sem erro")
rad_dir = radar(0.5, 3, 7.0); d["radar"] = rad_dir; r.atualizar(d); r.repaint()
rad_2 = o.montar_radar({0: {}, 1: {}, 2: {}}, 0, [0.5, 0.5, 0.5], [3, 3, 3], [False] * 3, 4, 4000.0, memoria={}, agora=8.0)
d["radar"] = rad_2; r.atualizar(d); r.repaint()
confere(rad_2["esq"] == 1 and rad_2["dir"] == 1, "carros dos dois lados")
d["radar"] = radar(0.6, 0, 9.0); r.atualizar(d); r.repaint()
confere(True, "luz lateral some com fade (sem erro)")

# --- 3) classificacao: posicoes ganhas/perdidas
pil = {i: {"numero": str(i), "marca": "Ford", "nome": f"P{i}", "pais": "BRA", "classe_id": 1, "classe_nome": "A",
           "classe_cor": (255, 200, 60), "classe_ordem": 0.0, "irating": 2000} for i in range(4)}
posc = [2, 1, 4, 3]                      # agora
base = {0: 4, 1: 1, 2: 3, 3: 3}          # na largada
cl = o.montar_classificacao(pil, 0, posc, [None] * 4, [None] * 4, [False] * 4, base=base)
dl = {l["numero"]: l["delta"] for l in cl["classes"][0]["linhas"]}
confere(dl == {"0": 2, "1": 0, "2": -1, "3": 0}, f"delta = posicao na largada - posicao agora {dl}")
cl0 = o.montar_classificacao(pil, 0, posc, [None] * 4, [None] * 4, [False] * 4)
confere(all(l["delta"] is None for l in cl0["classes"][0]["linhas"]), "sem base: sem seta")
j = o.JanelaClassificacao(cfg); j.show(); d["classificacao"] = cl; j.atualizar(d); j.repaint()
confere(j.width() == o.LARGURA_CLASS == 678, "janela de classificacao 678 px (com SR e iR)")

# --- 4) base de largada (Telemetria)
t = o.Telemetria(demo=True)
t._pilotos = pil; t._tipo_sessao = "CORRIDA"
estado = {"s": 3, "num": 1}
t._var = lambda nome, padrao=None: {"SessionState": estado["s"], "SessionNum": estado["num"], "SessionUniqueID": 7}.get(nome, padrao)
b = t._base_largada([4, 1, 3, 2]); confere(b == {0: 4, 1: 1, 2: 3, 3: 2}, "antes da largada guarda o grid")
b = t._base_largada([3, 1, 4, 2]); confere(b == {0: 3, 1: 1, 2: 4, 3: 2}, "ainda no grid: acompanha a ultima ordem")
estado["s"] = 4
b = t._base_largada([3, 1, 4, 2]); b = t._base_largada([1, 2, 3, 4])
confere(b == {0: 3, 1: 1, 2: 4, 3: 2}, "bandeira verde: congela a ordem de largada")
t._tipo_sessao = "TREINO"; t._var = lambda n, pd=None: {"SessionState": 4, "SessionNum": 2, "SessionUniqueID": 8}.get(n, pd)
confere(t._base_largada([1, 2, 3, 4]) is None, "fora de corrida: sem base")
t._tipo_sessao = "CORRIDA"
estado2 = {"SessionState": 4, "SessionNum": 3, "SessionUniqueID": 9}
t._var = lambda n, pd=None: estado2.get(n, pd)
confere(t._base_largada([2, 1, 3, 4]) == {0: 2, 1: 1, 2: 3, 3: 4}, "overlay aberto depois da largada: usa a primeira ordem vista")
estado2["SessionNum"] = 4
confere(t._base_largada([4, 3, 2, 1]) == {0: 4, 1: 3, 2: 2, 3: 1}, "sessao nova: base zerada")
conf = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "overlay_iracing.py"), encoding="utf-8").read()
confere('"overlay": "1.6.0' in conf, "versao 1.6.0")
print()
print("TODOS OS TESTES DA 1.4.2 PASSARAM" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
