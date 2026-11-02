#!/usr/bin/env python3
"""Gera dist/<repo>-vX.Y.Z.zip com o conteudo publico do repositorio (sem arquivos pessoais ou gerados em uso)."""
import os, re, sys, zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOME = os.path.basename(RAIZ)
versao = (re.search(r"## \[(\d+\.\d+\.\d+)\]", open(os.path.join(RAIZ, "CHANGELOG.md"), encoding="utf-8").read()) or [0, "0.0.0"])[1]
EXC_DIRS = {".git", "__pycache__", "dist", ".venv", "out_sport", "thumbs"}
EXC_ARQ = {"config.json", "config_lmu.json", "historico_projecoes.csv", "recordes_pessoais.json", "calibracao_pneus.json", "mapas_pistas.json", "pit_entradas.json", "jogo_iracing.png", "jogo_lmu.png",
           "diagnostico_lmu.txt", "emblemas_faltando.txt", "emblemas_faltando_lmu.txt"}
os.makedirs(os.path.join(RAIZ, "dist"), exist_ok=True)
destino = os.path.join(RAIZ, "dist", f"{NOME}-v{versao}.zip")
n = 0
with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
    for pasta, dirs, arqs in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in EXC_DIRS]
        for a in arqs:
            rel = os.path.relpath(os.path.join(pasta, a), RAIZ).replace(os.sep, "/")
            if a in EXC_ARQ or a.endswith((".pyc", ".lock")) or a.startswith("overlay_log") or a.endswith("_ajustado.streamDeckProfile"):
                continue
            if rel.startswith("overlay/emblemas/") and not rel.endswith("LEIA-ME.txt"):
                continue
            z.write(os.path.join(pasta, a), f"{NOME}/{rel}")
            n += 1
print(f"{n} arquivos -> {destino}")
