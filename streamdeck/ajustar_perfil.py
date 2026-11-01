#!/usr/bin/env python3
"""Ajusta o perfil do Stream Deck para a pasta onde VOCE instalou o overlay.

Os botoes que abrem arquivos (iniciar overlay, log, guia...) guardam o caminho completo da pasta do overlay. O perfil que
acompanha este repositorio foi gerado para o caminho PADRAO definido logo abaixo.
Se voce instalou em outro lugar, rode:

    python ajustar_perfil.py "D:\\Jogos\\wolfxracing-overlay\\overlay"

Isso cria "<perfil>_ajustado.streamDeckProfile" na mesma pasta. Importe esse arquivo no aplicativo do Stream Deck.
(Opcional: segundo argumento = caminho do .streamDeckProfile; por padrao usa o unico .streamDeckProfile desta pasta.)
"""
import glob, os, sys, zipfile

PADRAO = r"C:\WolfxRacing\wolfxracing-overlay-lmu\overlay"


def ajustar(pasta_overlay, perfil):
    antigo, novo = PADRAO.replace("\\", "\\\\"), pasta_overlay.rstrip("\\/").replace("\\", "\\\\")
    saida = os.path.splitext(perfil)[0] + "_ajustado.streamDeckProfile"
    n = 0
    with zipfile.ZipFile(perfil) as zin, zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            dados = zin.read(it.filename)
            if it.filename.endswith(".json"):
                t = dados.decode("utf-8")
                n += t.count(antigo)
                dados = t.replace(antigo, novo).encode("utf-8")
            zout.writestr(it.filename, dados)
    return saida, n


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); print("Caminho padrao do perfil:", PADRAO); sys.exit(1)
    pasta = sys.argv[1]
    perfil = sys.argv[2] if len(sys.argv) > 2 else (glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "*.streamDeckProfile")) or [None])[0]
    if not perfil or not os.path.exists(perfil):
        print("Nao achei o arquivo .streamDeckProfile."); sys.exit(1)
    if not os.path.isdir(pasta):
        print("Aviso: a pasta informada ainda nao existe:", pasta)
    saida, n = ajustar(pasta, perfil)
    print(f"{n} caminhos ajustados. Arquivo gerado: {saida}")
