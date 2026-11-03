# -*- coding: utf-8 -*-
"""v1.6.2 - reconhecimento de marca: Corvette com emblema proprio, Duqueine, nomes de equipe nunca viram marca (LMU)
e limpeza da lista de emblemas faltando ao abrir o overlay."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import overlay_iracing as o

falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

# ---- iRacing (primeira palavra vale como reserva)
for texto, esperado in (("Porsche 911 GT3 R (992)", "Porsche"), ("Chevrolet Corvette C8.R GTD", "Corvette"),
                        ("Chevrolet Camaro ZL1", "Chevrolet"), ("Duqueine D08", "Duqueine"),
                        ("Mercedes-AMG GT3 2020", "Mercedes-AMG"), ("Ligier JS P320", "Ligier")):
    confere(o.marca_do_carro(texto) == esperado, f"{texto!r} -> {esperado} ({o.marca_do_carro(texto)})")

# ---- LMU (fallback=False): a primeira palavra e a equipe, nunca a marca
lmu = (("Manthey EMA #92 Porsche 911 GT3 R LMGT3", "Porsche"), ("Kessel Racing #57 Ferrari 296 GT3", "Ferrari"),
       ("Heart of Racing #27 Aston Martin Vantage AMR LMGT3 Evo", "Aston Martin"),
       ("Inter Europol Competition #34 Oreca 07 Gibson", "Oreca"), ("United Autosports #22 Oreca 07", "Oreca"),
       ("TF Sport #81 Chevrolet Corvette Z06 GT3.R", "Corvette"), ("Garage 59 #59 McLaren 720S GT3 Evo", "McLaren"),
       ("Vista AF Corse #21 Ferrari 499P", "Ferrari"), ("Peugeot TotalEnergies #93 9X8", "Peugeot"),
       ("Duqueine Team #5 Duqueine D08", "Duqueine"))
for texto, esperado in lmu:
    confere(o.marca_do_carro(texto, fallback=False) == esperado, f"LMU {texto!r} -> {esperado}")
for equipe in ("Nielsen Racing", "13 Autosport", "CrowdStrike by Riley", "CLX Motorsport", "Forestier Racing"):
    confere(o.marca_do_carro(equipe, fallback=False) == "--", f"LMU equipe sem marca {equipe!r} -> '--' (nao vira emblema)")

# ---- limpeza da lista de emblemas faltando
S = Path(tempfile.mkdtemp()); o.ARQ_EMBLEMAS_FALTANDO = S / "emblemas_faltando.txt"
o.ARQ_EMBLEMAS_FALTANDO.write_text("13.png (marca: 13)\n", encoding="utf-8")
o._emblemas_faltando["13"] = "13.png"
o.limpar_emblemas_faltando()
confere(not o.ARQ_EMBLEMAS_FALTANDO.exists() and not o._emblemas_faltando, "lista antiga apagada ao abrir o overlay")
o.limpar_emblemas_faltando()
confere(True, "limpar sem arquivo nao falha")

print("\n" + ("TODOS OS TESTES DE MARCAS (v1.6.2) PASSARAM" if not falhas else f"{len(falhas)} FALHA(S)"))
sys.exit(1 if falhas else 0)
