# -*- coding: utf-8 -*-
"""Inventario dos arquivos de um commit, para que TODOS os ativos de uma release saiam da mesma fonte.
Com a pasta .git, le os arquivos do commit pedido (git archive: nao depende do que existe no disco nem da conversao de fim de linha
do Windows). Sem .git (zip do codigo), le a arvore de trabalho. Nunca mistura as duas."""
import hashlib
import io
import os
import subprocess
import tarfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(*args, raiz=RAIZ):
    r = subprocess.run(["git", "-C", raiz, *args], capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("git %s falhou: %s" % (" ".join(args), r.stderr.decode("utf-8", "replace").strip()))
    return r.stdout


def tem_git(raiz=RAIZ):
    try:
        _git("rev-parse", "--git-dir", raiz=raiz)
        return True
    except (RuntimeError, OSError, subprocess.SubprocessError):
        return False


def resolver_commit(commit="HEAD", raiz=RAIZ):
    """SHA completo (40 hex) do commit."""
    return _git("rev-parse", "--verify", commit + "^{commit}", raiz=raiz).decode().strip()


def arquivos_do_commit(commit="HEAD", prefixo="", raiz=RAIZ):
    """{caminho relativo ao prefixo: bytes} dos arquivos do commit sob `prefixo` (ex.: 'overlay')."""
    args = ["archive", "--format=tar", commit] + ([prefixo] if prefixo else [])
    dados = _git(*args, raiz=raiz)
    res = {}
    with tarfile.open(fileobj=io.BytesIO(dados)) as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            rel = m.name[len(prefixo) + 1:] if prefixo else m.name
            res[rel] = tar.extractfile(m).read()
    return res


def arquivos_da_arvore(prefixo="", raiz=RAIZ, ignorar_dirs=(".git", "__pycache__", "dist", "exe", "logs_testes")):
    """{caminho relativo ao prefixo: bytes} da arvore de trabalho (para o zip do codigo, que nao tem .git)."""
    base = os.path.join(raiz, prefixo) if prefixo else raiz
    res = {}
    for pasta, dirs, arqs in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ignorar_dirs and not d.startswith("backup_pre_")]
        for a in arqs:
            p = os.path.join(pasta, a)
            res[os.path.relpath(p, base).replace(os.sep, "/")] = open(p, "rb").read()
    return res


def sha256(dados):
    return hashlib.sha256(dados).hexdigest()
