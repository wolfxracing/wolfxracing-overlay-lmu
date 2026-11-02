# -*- coding: utf-8 -*-
"""v1.6.0 - Minimapa rotativo fluido: geometria continua, estimativa entre leituras, equivalencia com a projecao antiga."""
import os, sys, math, tempfile, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import overlay_iracing as o
import ov_v15 as v15
from PySide6.QtWidgets import QApplication

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c: None
falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

# pista sintetica: oval com curvas (360 trechos, ~5 km)
N = 360
pontos = [(1100 * math.cos(2 * math.pi * i / N) + 90 * math.cos(3 * 2 * math.pi * i / N),
           450 * math.sin(2 * math.pi * i / N) + 70 * math.sin(3 * 2 * math.pi * i / N)) for i in range(N)]
def dados(pct, outros=((0.31, (80, 160, 255)),)):
    d = o.Telemetria._vazio(); d["conectado"] = True
    carros = [{"pct": pct, "numero": "1", "cor": (255, 255, 255), "eu": True}] + \
             [{"pct": q, "numero": str(i + 2), "cor": cor, "eu": False} for i, (q, cor) in enumerate(outros)]
    d["mapa"] = {"completo": True, "pontos": pontos, "progresso": 1.0, "versao": 1, "carros": carros}
    return d

cfg = o.carregar_config(); cfg["travado"] = True
j = o.JanelaMinimapa(cfg); j.show()
confere(j.TAXA_HZ >= 60 and j.QUADRO_MS <= 17, "desenho a ~60 quadros por segundo")
j.atualizar(dados(0.10))
confere(j._amostra is not None and j._caminho is not None, "mapa completo monta o caminho uma unica vez")
ref = j._ref_mapa
caminho = j._caminho
j.atualizar(dados(0.101)); confere(j._caminho is caminho and j._ref_mapa == ref, "caminho nao e recalculado a cada leitura")
j.repaint(); confere(not j.grab().isNull(), "desenha")

# equivalencia com a projecao antiga quando a posicao cai exatamente num trecho (sem fracao)
pct = 100 / N
ex, ey, tx, ty = j.geometria(pct)
antigo = v15.projetar_minimapa(pontos, pct, [{"pct": 0.31, "cor": (1, 2, 3), "eu": False}], 260.0, 96.0)
esc = 96.0 / 260.0
cx, cy = j._xy(0.31 * N)
sx, sy = ((cx - ex) * ty - (cy - ey) * tx) * esc, -((cx - ex) * tx + (cy - ey) * ty) * esc
car = antigo["carros"][0] if antigo["carros"] else None
confere(car is not None and abs(car["x"] - sx) < 1e-6 and abs(car["y"] - sy) < 1e-6, "mesma posicao dos carros que a projecao antiga")
norte = math.degrees(math.atan2(-tx, ty))
confere(abs(((norte - antigo["norte"] + 180) % 360) - 180) < 1e-6, "mesmo norte que a projecao antiga")

# continuidade: rumo a cada 1/60 s a 250 km/h (~70 m/s numa pista de 5 km) nao pode dar saltos
L = 5000.0
passo = 70.0 / 60.0 / L
def ang(pct):
    g = j.geometria(pct); return math.degrees(math.atan2(g[3], g[2]))
def dif(a, b): return abs(((a - b + 180) % 360) - 180)
passos = [dif(ang(i * passo), ang((i + 1) * passo)) for i in range(int(1.0 / passo))]
confere(max(passos) < 1.2, f"rumo gira continuo: maior passo por quadro {max(passos):.2f} graus")
# o metodo antigo (tangente em indices inteiros) dava degraus; mede o mesmo trajeto
def ang_antigo(pct):
    pos = pct * N; i0 = int(pos) % N; k = max(2, N // 120)
    s = j._suave; a, b = s[(i0 - k) % N], s[(i0 + k + 1) % N]
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
pa = [dif(ang_antigo(i * passo), ang_antigo((i + 1) * passo)) for i in range(int(1.0 / passo))]
confere(max(pa) > max(passos) * 1.5, f"antes: degraus de ate {max(pa):.2f} graus por quadro (agora {max(passos):.2f})")

# estimativa entre leituras
j2 = o.JanelaMinimapa(cfg); j2.show()
t0 = time.monotonic()
j2.atualizar(dados(0.200)); time.sleep(0.05); j2.atualizar(dados(0.200 + 0.0167 * 0.05 / 1.0 * 1.0))
confere(0.0 < j2._taxa_pct < 0.08, f"taxa de progresso estimada ({j2._taxa_pct:.4f} volta/s)")
j2.atualizar(dados(0.20)); j2.atualizar(dados(0.60))
confere(j2._taxa_pct == 0.0, "salto de posicao (box/reinicio) nao e extrapolado")
j2.atualizar(dados(0.60)); j2.repaint()
confere(True, "parado: desenha sem erro")

# estados sem dados
d = o.Telemetria._vazio(); d["conectado"] = True; d["mapa"] = {"completo": False, "progresso": 0.4, "pontos": [None] * N, "carros": []}
j.atualizar(d); j.repaint(); confere(j._amostra is None and j._prog == 0.4, "aprendendo o traco: mostra o progresso")
d["conectado"] = False; j.atualizar(d); j.repaint(); confere(True, "sem conexao")
j.atualizar(dados(0.5, outros=[(0.51, (200, 50, 50)), (0.49, (50, 200, 50))])); j.repaint()
if os.environ.get("OVERLAY_PREVIAS"):
    j.grab().save(os.path.join(os.environ["OVERLAY_PREVIAS"], "minimapa_fluido.png"))
# custo de desenho por quadro
t = time.perf_counter(); 
for _ in range(120): j.grab()
ms = (time.perf_counter() - t) / 120 * 1000
confere(ms < 8.0, f"custo por quadro: {ms:.2f} ms (offscreen)")
print()
print("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
