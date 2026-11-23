#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confere, ANTES de montar qualquer ativo, que a publicacao esta presa ao commit certo. Falha (exit 1) com a lista de problemas.

  python tools/validar_release.py --tag v1.8.2 --sha <GITHUB_SHA> [--repo dono/nome] [--sem-github]

Regras:
 1. a tag tem a forma vX.Y.Z e bate com o primeiro `## [X.Y.Z]` do CHANGELOG.md e com VERSAO_PRODUTO de overlay/overlay_iracing.py;
 2. se a tag JA existe, ela aponta exatamente para o commit em execucao (o fluxo nao empacota outro commit);
 3. se a tag NAO existe (disparo manual), o commit em execucao tem de ser a ponta da main (nao se publica de ramo avulso);
 4. o commit em execucao e o checkout (HEAD) sao o mesmo;
 5. nao existe release PUBLICADA com essa tag (release publicada nunca e reescrita; so rascunho de uma execucao anterior pode ser refeito)."""
import argparse
import json
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args):
    r = subprocess.run(["git", "-C", RAIZ, *args], capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def validar(tag, sha, repo="", com_github=True, raiz=RAIZ):
    erros = []
    m = re.fullmatch(r"v(\d+\.\d+\.\d+)", tag or "")
    if not m:
        return ["a tag '%s' nao tem a forma vX.Y.Z" % tag]
    versao = m.group(1)
    sha = (sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        erros.append("SHA do commit invalido: %r" % sha)
    texto = open(os.path.join(raiz, "CHANGELOG.md"), encoding="utf-8").read()
    topo = re.search(r"^## \[(\d+\.\d+\.\d+)\]", texto, re.M)
    if not topo or topo.group(1) != versao:
        erros.append("o primeiro '## [X.Y.Z]' do CHANGELOG.md e %s, nao %s" % (topo.group(1) if topo else "ausente", versao))
    fonte = open(os.path.join(raiz, "overlay", "overlay_iracing.py"), encoding="utf-8").read()
    v = re.search(r'^VERSAO_PRODUTO\s*=\s*"([^"]+)"', fonte, re.M)
    b = re.search(r'^BUILD\s*=\s*"([^"]+)"', fonte, re.M)
    if not v or v.group(1) != versao:
        erros.append("VERSAO_PRODUTO em overlay_iracing.py e %s, nao %s" % (v.group(1) if v else "ausente", versao))
    if not b:
        erros.append("BUILD ausente em overlay_iracing.py")
    rc, head, _ = git("rev-parse", "HEAD")
    if rc != 0 or head != sha:
        erros.append("o checkout (%s) nao e o commit em execucao (%s)" % (head or "?", sha))
    rc, alvo, _ = git("rev-parse", "--verify", "refs/tags/%s^{commit}" % tag)
    if rc == 0:
        if alvo != sha:
            erros.append("a tag %s ja existe e aponta para %s, nao para o commit em execucao %s" % (tag, alvo, sha))
    else:
        git("fetch", "--no-tags", "origin", "main")
        rc2, ponta, _ = git("rev-parse", "--verify", "refs/remotes/origin/main")
        if rc2 != 0 or ponta != sha:
            erros.append("a tag %s ainda nao existe e o commit em execucao (%s) nao e a ponta da main (%s)" % (tag, sha, ponta or "?"))
    if com_github and repo:
        r = subprocess.run(["gh", "release", "view", tag, "--repo", repo, "--json", "isDraft,url"], capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            info = json.loads(r.stdout)
            if not info.get("isDraft"):
                erros.append("ja existe uma release PUBLICADA para %s (%s); ela nao e reescrita. Use uma nova versao." % (tag, info.get("url")))
            else:
                print("aviso: existe um rascunho antigo de %s; sera substituido" % tag)
    return erros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--repo", default="")
    ap.add_argument("--sem-github", action="store_true")
    a = ap.parse_args()
    erros = validar(a.tag, a.sha, a.repo, not a.sem_github)
    if erros:
        print("RELEASE RECUSADA:")
        for e in erros:
            print(" -", e)
        return 1
    print("ok: %s -> commit %s; versao e CHANGELOG conferem" % (a.tag, a.sha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
