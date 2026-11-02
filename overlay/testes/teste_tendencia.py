# -*- coding: utf-8 -*-
"""v1.6.0 - Tendencia de ritmo: logica (voltas limpas, stints, inclinacao, previsao), janela, demo, Central."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
from types import SimpleNamespace
import overlay_iracing as o
import ov_v16 as v
import ov_central as c
from PySide6.QtWidgets import QApplication

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"; o.ARQ_PIT = S / "pit.json"
app = QApplication([]); o.salvar_config = lambda c: None
falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

def correr(t, tempos, melhor=None, box_em=(), bandeira_em=()):
    """simula voltas: cada item de `tempos` e a volta recem fechada."""
    for i, tempo in enumerate(tempos, start=1):
        na_box = i in box_em
        t.atualizar("pista", i, tempo, melhor, na_box, "amarela" if i in bandeira_em else None)

# ---- voltas limpas e inclinacao
t = v.TendenciaRitmo()
t.atualizar("pista", 0, None, None, False)
for n in range(1, 9):                                        # piorando 0,10 s por volta
    t.atualizar("pista", n, 90.0 + 0.10 * n, 90.0, False)
r = t.resumo(90.0)
confere(len(r["voltas"]) == 8, f"8 voltas limpas registradas ({len(r['voltas'])})")
confere(abs(r["inclinacao"] - 0.10) < 1e-6, f"inclinacao +0,10 s/volta ({r['inclinacao']:.4f})")
confere(abs(r["previsao"] - 90.9) < 1e-6, f"previsao da proxima volta ~90,90 ({r['previsao']:.3f})")
confere(v.estado_tendencia(r["inclinacao"])[0] == "piorando", "estado: piorando")
confere(v.estado_tendencia(-0.2)[0] == "melhorando" and v.estado_tendencia(0.01)[0] == "estável", "estados melhorando e estavel")
confere(abs(r["ritmo5"] - sum(90.0 + 0.10 * n for n in range(4, 9)) / 5) < 1e-6, "ritmo = media das 5 ultimas limpas")

# ---- poucas voltas: sem inclinacao
t = v.TendenciaRitmo(); t.atualizar("p", 0, None, None, False)
for n in (1, 2, 3):
    t.atualizar("p", n, 91.0, 90.0, False)
r = t.resumo(90.0)
confere(r["inclinacao"] is None and r["previsao"] is None, "com 3 voltas ainda nao calcula inclinacao")
confere(t.resumo(None) is not None and v.TendenciaRitmo().resumo() is None, "sem voltas: resumo vazio")

# ---- sujeira: boxes, bandeira, volta lenta
t = v.TendenciaRitmo(); t.atualizar("p", 0, None, None, False)
t.atualizar("p", 1, 91.0, 90.0, False)
t.atualizar("p", 2, 91.2, 90.0, True)                        # entrou nos boxes na volta 2: nao conta
t.atualizar("p", 3, 130.0, 90.0, False)                      # volta de saida (ainda suja pelo box)
t.atualizar("p", 4, 91.1, 90.0, False)
confere([x[0] for x in t.voltas] == [1, 4], f"volta com box e volta de saida ficam de fora ({[x[0] for x in t.voltas]})")
confere(t.voltas[-1][2] == 2 and t.voltas[0][2] == 1, "passar pelos boxes inicia um novo stint")
t.atualizar("p", 5, 91.0, 90.0, False, "amarela")             # bandeira amarela durante a volta 5
t.atualizar("p", 6, 91.0, 90.0, False)
confere(5 not in [x[0] for x in t.voltas], "volta fechada com amarela fica de fora")
confere(6 in [x[0] for x in t.voltas], "volta seguinte, sem amarela, volta a contar")
t.atualizar("p", 6, 91.0, 90.0, False, "amarela")             # amarela que continua na volta 6->7
t.atualizar("p", 7, 91.0, 90.0, False)
t.atualizar("p", 8, 140.0, 90.0, False)                      # > 130% da melhor
confere(8 not in [x[0] for x in t.voltas], "volta acima de 130% da melhor nao entra")
t.atualizar("p", 10, 91.0, 90.0, False)                      # salto de contagem
confere(10 not in [x[0] for x in t.voltas], "salto na contagem de voltas nao e confiavel")
t.atualizar("p", 2, 91.0, 90.0, False)                       # sessao reiniciou
confere(t.voltas == [], "contagem voltou: historico zerado")
t2 = v.TendenciaRitmo(); t2.atualizar("A", 0, None, None, False); t2.atualizar("A", 1, 91.0, 90.0, False)
t2.atualizar("B", 5, 91.0, 90.0, False)
confere(t2.voltas == [], "trocar de pista zera o historico")

# ---- inclinacao so do stint atual
t = v.TendenciaRitmo(); t.atualizar("p", 0, None, None, False)
for n in range(1, 7): t.atualizar("p", n, 95.0 - 0.1 * n, 90.0, False)    # stint 1 melhorando
t.atualizar("p", 7, 100.0, 90.0, True); t.atualizar("p", 8, 100.0, 90.0, False)
for n in range(9, 15): t.atualizar("p", n, 91.0 + 0.2 * (n - 9), 90.0, False)   # stint 2 piorando
r = t.resumo(90.0)
confere(r["stint_atual"] == 2 and abs(r["inclinacao"] - 0.2) < 1e-6, f"inclinacao usa so o stint atual ({r['inclinacao']:.3f})")
confere(r["consistencia"] is not None and r["consistencia"] > 0, "consistencia calculada")

# ---- integracao com a telemetria (leitura real simulada)
fake = SimpleNamespace(v16_ritmo=v.TendenciaRitmo(), _chave_pista="Spa",
                       _var=lambda nome, padrao=None: {"LapCompleted": 3, "OnPitRoad": False}.get(nome, padrao))
dados = {"ultima_volta": 91.5, "melhor_volta": 90.8, "bandeira": None}
fake.v16_ritmo.atualizar("Spa", 2, None, None, False)
o.Telemetria._montar_tendencia(fake, dados)
confere(dados["tendencia"] and dados["tendencia"]["voltas"][-1][1] == 91.5, "Telemetria monta dados['tendencia'] a partir do jogo")

# ---- janela
cfg = o.carregar_config(); cfg["travado"] = True
confere(cfg.get("mostrar_tendencia") is True and "x_tendencia" in cfg and "escala_x_tendencia" in cfg, "config da janela existe")
j = o.JanelaTendencia(cfg); j.show()
confere((j.width(), j.height()) == (o.JanelaTendencia.LARG, o.JanelaTendencia.ALT), f"tamanho {j.width()}x{j.height()}")
d = o.Telemetria(demo=True).ler()
confere(d.get("tendencia") and d["tendencia"]["inclinacao"] is not None, "demo traz tendencia")
j.atualizar(d); j.repaint(); img = j.grab()
confere(not img.isNull(), "desenha com dados")
d2 = dict(d); d2["tendencia"] = None; j.atualizar(d2); j.repaint()
confere(True, "desenha sem voltas limpas (mensagem de espera)")
d3 = dict(d); d3["conectado"] = False; j.atualizar(d3); j.repaint()
confere(True, "desenha sem conexao")
d4 = dict(d); tt = dict(d["tendencia"]); tt.update(inclinacao=None, previsao=None, consistencia=None, melhor=None, delta_ritmo=None, voltas=tt["voltas"][:2])
d4["tendencia"] = tt; j.atualizar(d4); j.repaint()
confere(True, "desenha com poucas voltas e sem melhor volta")
if os.environ.get("OVERLAY_PREVIAS"):
    j.atualizar(d); j.repaint(); j.grab().save(os.path.join(os.environ["OVERLAY_PREVIAS"], "janela_tendencia.png"))

# ---- Central
confere("tendencia" in c.PAINEIS and c.PAINEIS["tendencia"][2] == "Corrida", "Central lista a Tendencia de ritmo em 'Corrida'")
print()
print("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
