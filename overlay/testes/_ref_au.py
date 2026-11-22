# -*- coding: utf-8 -*-
"""Build aw: desenha casos com os arquivos CONGELADOS da build au (testes/referencia_au/referencia_au.zip) em outro processo.
Confere o hash de cada arquivo antes de usar. Devolve {id: QImage}."""
import os
import sys
import shutil
import hashlib
import pickle
import tempfile
import zipfile
import subprocess

AQUI = os.path.dirname(os.path.abspath(__file__))
OVERLAY = os.path.dirname(AQUI)
PASTA_REF = os.path.join(AQUI, "referencia_au")
ZIP = os.path.join(PASTA_REF, "referencia_au.zip")
SHA = os.path.join(PASTA_REF, "SHA256_referencia_au.txt")


def hashes_esperados():
    out = {}
    with open(SHA, encoding="utf-8") as f:
        for ln in f:
            partes = ln.split()
            if len(partes) == 2:
                out[partes[1]] = partes[0]
    return out


def conferir_zip():
    """(ok, mensagem): o zip tem exatamente os arquivos e os hashes registrados."""
    esperado = hashes_esperados()
    with zipfile.ZipFile(ZIP) as z:
        nomes = sorted(z.namelist())
        if nomes != sorted(esperado):
            return False, f"arquivos do zip {nomes} != {sorted(esperado)}"
        for n in nomes:
            h = hashlib.sha256(z.read(n)).hexdigest()
            if h != esperado[n]:
                return False, f"hash de {n} nao confere"
    return True, "ok"


def _rodar(casos, pasta_codigo, tempo_limite=600):
    """Desenha os casos num PROCESSO NOVO que usa os arquivos de pasta_codigo (primeiro no caminho de importacao). {id: QImage}."""
    from PySide6.QtGui import QImage
    tmp = tempfile.mkdtemp(prefix="ref_proc_")
    try:
        saida = os.path.join(tmp, "saida")
        os.makedirs(saida)
        entrada = os.path.join(tmp, "casos.pkl")
        with open(entrada, "wb") as f:
            pickle.dump(casos, f)
        r = subprocess.run([sys.executable, os.path.join(AQUI, "_render_au.py"), pasta_codigo, entrada, saida],
                           capture_output=True, text=True, timeout=tempo_limite)
        if r.returncode != 0:
            raise RuntimeError("falha ao desenhar em processo separado:\n" + (r.stderr or "")[-1500:])
        imgs = {}
        for c in casos:
            im = QImage(os.path.join(saida, c["id"].replace(":", "_").replace("/", "_") + ".png"))
            if im.isNull():
                raise RuntimeError("imagem ausente: " + c["id"])
            imgs[c["id"]] = im
        return imgs
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def desenhar_com_atual(casos):
    """Casos desenhados com os arquivos ATUAIS, em processo novo e limpo (mesmas condicoes da referencia au)."""
    return _rodar(casos, OVERLAY)


def desenhar_com_au(casos):
    """Casos desenhados com os arquivos CONGELADOS da build au (zip de referencia), em processo novo e limpo. {id: QImage}."""
    pasta = tempfile.mkdtemp(prefix="ref_au_")
    try:
        with zipfile.ZipFile(ZIP) as z:
            z.extractall(pasta)
        for d in ("fontes", "emblemas", "marca", "bandeiras", "referencias"):               # recursos que o overlay_iracing.py procura ao lado dele
            origem = os.path.join(OVERLAY, d)
            if os.path.isdir(origem):
                shutil.copytree(origem, os.path.join(pasta, d))
        return _rodar(casos, pasta)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
