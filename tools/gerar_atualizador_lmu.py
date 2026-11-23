#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o pacote COMPLETO de atualizacao do LMU a partir de UM commit, e confere o conteudo contra o zip de codigo da mesma release.

  python tools/gerar_atualizador_lmu.py --commit <sha|HEAD> [--esperar-sha <sha completo>] [--saida dist] [--codigo-zip dist/<repo>-vX.Y.Z.zip]

- O conteudo de programa\\ vem do commit (git archive), nao da pasta de trabalho; PACOTE.json grava versao, build e SHA do commit.
- --esperar-sha: recusa gerar se o commit resolvido for outro (o fluxo de release passa o SHA da tag).
- --codigo-zip: todo arquivo de programa\\ que tambem esta no zip de codigo tem de ter os MESMOS bytes; so podem faltar no zip os que o
  empacotar.py exclui de proposito (dados pessoais do usuario). Qualquer diferenca = erro (exit 1).
- --arvore: sem .git (ex.: dentro do zip do codigo), usa a arvore de trabalho."""
import argparse
import io
import json
import os
import re
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventario_release as inv

RAIZ = inv.RAIZ
ATUALIZADOR = os.path.join(RAIZ, "tools", "atualizador_lmu")
FIXOS = ("atualizar_lmu.py", "ATUALIZAR_LMU.bat", "LEIA-ME_ATUALIZACAO_LMU.txt")
IGNORAR = re.compile(r"(^|/)(__pycache__|logs_testes|backup_pre_[^/]*)(/|$)|(^|/)(overlay_log\.txt|emblemas_faltando.*\.txt)$|\.pyc$", re.I)


def ler_versao_build(programa):
    txt = programa["overlay_iracing.py"].decode("utf-8")
    versao = re.search(r'^VERSAO_PRODUTO\s*=\s*"([^"]+)"', txt, re.M)
    build = re.search(r'^BUILD\s*=\s*"([^"]+)"', txt, re.M)
    if not versao or not build:
        raise SystemExit("ERRO: VERSAO_PRODUTO/BUILD nao encontrados em overlay_iracing.py")
    return versao.group(1), build.group(1)


def montar(commit, arvore, saida):
    if arvore:
        sha_commit = "arvore-de-trabalho"
        programa = inv.arquivos_da_arvore("overlay")
    else:
        sha_commit = inv.resolver_commit(commit)
        programa = inv.arquivos_do_commit(sha_commit, "overlay")
    programa = {rel: d for rel, d in programa.items() if not IGNORAR.search(rel)}
    versao, build = ler_versao_build(programa)
    manifesto = "".join("%s  %s\n" % (inv.sha256(d), rel) for rel, d in sorted(programa.items()))
    pacote = {"versao": versao, "build": build, "commit": sha_commit, "arquivos": len(programa),
              "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    nome = "WolfxRacing_LMU_%s_build%s_atualizacao_completa.zip" % (versao, build.upper())
    os.makedirs(saida, exist_ok=True)
    destino = os.path.join(saida, nome)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FIXOS:
            z.write(os.path.join(ATUALIZADOR, f), f)
        z.write(os.path.join(ATUALIZADOR, "verificar_migracao.py"), "verificacao/verificar_migracao.py")
        z.writestr("MANIFESTO_SHA256.txt", manifesto)
        z.writestr("PACOTE.json", json.dumps(pacote, indent=2, ensure_ascii=False) + "\n")
        for rel, d in sorted(programa.items()):
            z.writestr("programa/" + rel, d)
    return destino, programa, pacote


def comparar_com_codigo(programa, codigo_zip):
    """(iguais, so_no_atualizador, diferentes)."""
    with zipfile.ZipFile(codigo_zip) as z:
        raiz = z.namelist()[0].split("/")[0]
        no_zip = {n[len(raiz) + len("/overlay/"):]: n for n in z.namelist() if n.startswith(raiz + "/overlay/") and not n.endswith("/")}
        iguais, so_atual, dif = [], [], []
        for rel, d in sorted(programa.items()):
            if rel not in no_zip:
                so_atual.append(rel)
            elif z.read(no_zip[rel]) == d:
                iguais.append(rel)
            else:
                dif.append(rel)
    return iguais, so_atual, dif


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", default="HEAD")
    ap.add_argument("--esperar-sha", default="")
    ap.add_argument("--saida", default=os.path.join(RAIZ, "dist"))
    ap.add_argument("--codigo-zip", default="")
    ap.add_argument("--arvore", action="store_true", help="sem .git: usa a arvore de trabalho")
    a = ap.parse_args()
    if not a.arvore and a.esperar_sha and inv.resolver_commit(a.commit) != a.esperar_sha.lower():
        print("ERRO: o commit %s resolve para %s, esperado %s" % (a.commit, inv.resolver_commit(a.commit), a.esperar_sha))
        return 1
    destino, programa, pacote = montar(a.commit, a.arvore, a.saida)
    print("%s\n  versao %s build %s commit %s, %d arquivos em programa\\" % (destino, pacote["versao"], pacote["build"], pacote["commit"], pacote["arquivos"]))
    if a.codigo_zip:
        iguais, so_atual, dif = comparar_com_codigo(programa, a.codigo_zip)
        print("  comparacao com %s: %d iguais, %d so no atualizador, %d DIFERENTES" % (os.path.basename(a.codigo_zip), len(iguais), len(so_atual), len(dif)))
        for rel in so_atual:
            print("    so no atualizador (excluido do zip de codigo de proposito):", rel)
        for rel in dif:
            print("    DIFERENTE:", rel)
        if dif:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
