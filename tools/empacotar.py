#!/usr/bin/env python3
"""Gera dist/<repo>-vX.Y.Z.zip com o conteudo publico do repositorio (sem arquivos pessoais ou gerados em uso).
Build ba: o conteudo vem do COMMIT (git archive), a mesma fonte do pacote de atualizacao; sem .git, da arvore de trabalho.
  python tools/empacotar.py [--commit <sha|HEAD>] [--esperar-sha <sha completo>]"""
import os, re, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventario_release as inv

RAIZ = inv.RAIZ
NOME = os.path.basename(RAIZ)
EXC_DIRS = {".git", "__pycache__", "dist", ".venv", "out_sport", "thumbs", "exe", "referencias", "logs_testes"}
EXC_ARQ = {"config.json", "config_lmu.json", "historico_projecoes.csv", "recordes_pessoais.json", "calibracao_pneus.json", "mapas_pistas.json", "pit_entradas.json", "pit_entradas_v2.json", "jogo_iracing.png", "jogo_lmu.png",
           "diagnostico_lmu.txt", "emblemas_faltando.txt", "emblemas_faltando_lmu.txt", "cronograma.json", "cronograma_anterior.json"}


def excluido(rel):
    partes = rel.split("/")
    a = partes[-1]
    if any(p in EXC_DIRS for p in partes[:-1]):
        return True
    if a in EXC_ARQ or a.endswith((".pyc", ".lock")) or a.startswith("overlay_log") or a.endswith("_ajustado.streamDeckProfile"):
        return True
    return rel.startswith("overlay/emblemas/") and not rel.endswith("LEIA-ME.txt")


def main():
    args = sys.argv[1:]
    commit = args[args.index("--commit") + 1] if "--commit" in args else "HEAD"
    esperado = args[args.index("--esperar-sha") + 1].lower() if "--esperar-sha" in args else ""
    if inv.tem_git():
        sha = inv.resolver_commit(commit)
        if esperado and sha != esperado:
            print("ERRO: o commit %s resolve para %s, esperado %s" % (commit, sha, esperado))
            return 1
        arquivos = inv.arquivos_do_commit(sha)
        origem = "commit " + sha[:12]
    else:
        arquivos = inv.arquivos_da_arvore()
        origem = "arvore de trabalho"
    versao = re.search(r"## \[(\d+\.\d+\.\d+)\]", arquivos["CHANGELOG.md"].decode("utf-8"))
    versao = versao.group(1) if versao else "0.0.0"
    os.makedirs(os.path.join(RAIZ, "dist"), exist_ok=True)
    destino = os.path.join(RAIZ, "dist", f"{NOME}-v{versao}.zip")
    n = 0
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, dados in sorted(arquivos.items()):
            if excluido(rel):
                continue
            z.writestr(f"{NOME}/{rel}", dados)
            n += 1
    print(f"{n} arquivos ({origem}) -> {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
