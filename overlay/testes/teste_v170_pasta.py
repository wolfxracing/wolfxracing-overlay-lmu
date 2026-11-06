# -*- coding: utf-8 -*-
"""1.7.0 - a pasta de telemetria .ibt e relida durante a sessao quando chega arquivo novo (checa a cada 2 min)."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
from types import SimpleNamespace
import overlay_iracing as o

falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

chamadas = []
o.ov_ibt.melhor_volta_da_pasta = lambda pasta, pista, carro, comp, **kw: (chamadas.append(time.time()) or None)
def esperar(n, s=3.0):
    t0 = time.time()
    while len(chamadas) < n and time.time() - t0 < s: time.sleep(0.02)
    time.sleep(0.1)

with tempfile.TemporaryDirectory() as d:
    coach = SimpleNamespace(pista="Fuji", carro="BMW M4 GT3", comprimento=4563.0, definir_propria=lambda r: False)
    tele = SimpleNamespace(v17_ibt_pasta=Path(d), v17_coach=coach, config_coach_ibt_auto=True)
    o._carregar_ibt_se_preciso(tele); esperar(1)
    confere(len(chamadas) == 1, "procura ao entrar na pista")
    o._carregar_ibt_se_preciso(tele); esperar(2, 0.4)
    confere(len(chamadas) == 1, "nao repete antes de 2 min")
    tele.v17_ibt_ult = -1000.0
    o._carregar_ibt_se_preciso(tele); esperar(2, 0.4)
    confere(len(chamadas) == 1, "passou 2 min mas a pasta nao mudou: nao le de novo")
    (Path(d) / "novo.ibt").write_bytes(b"x")
    tele.v17_ibt_ult = -1000.0
    o._carregar_ibt_se_preciso(tele); esperar(2)
    confere(len(chamadas) == 2, "chegou .ibt novo: procura de novo")
    tele.v17_ibt_ult = -1000.0
    o._carregar_ibt_se_preciso(tele); esperar(3, 0.4)
    confere(len(chamadas) == 2, "sem novidade depois: nao repete")

print("\n" + ("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")); sys.exit(1 if falhas else 0)
