# -*- coding: utf-8 -*-
"""Build aw: desenha um painel a partir de um 'caso' (classe + config + dados). Usado dos DOIS lados da comparacao com a referencia
congelada da build au: no processo do teste (arquivos atuais) e em outro processo (arquivos da build au). O mesmo codigo desenha nos dois,
entao qualquer diferenca de imagem vem dos arquivos de desenho e nao do teste."""
import os
import sys
import pickle
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
OVERLAY = os.path.dirname(AQUI)
_MEMO = {}


def classe_de(caso, o):
    origem, nome = caso["origem"], caso["nome"]
    if origem == "o":
        return getattr(o, nome)
    if origem == "v18":
        if "v18" not in _MEMO:
            import ov_v18_janelas as v18
            _MEMO["v18"] = {k.CHAVE: k for k in v18.construir(o).values()}
        return _MEMO["v18"][nome]
    if origem == "cf":
        if "cf" not in _MEMO:
            import ov_classif_foto as cf
            _MEMO["cf"] = cf.construir(o)
        return _MEMO["cf"]
    if origem == "lmu_extra":
        import ov_janelas_extra_lmu as ex
        return getattr(ex, nome)
    if origem == "lmu_classif":
        import ov_janela_lmu as jl
        return jl.classe_classificacao(caso["cfg"])
    raise KeyError(origem)


def render_caso(o, caso):
    K = classe_de(caso, o)
    c2 = dict(caso["cfg"])
    c2[K.CHAVE_ATIVO] = False
    c2["travado"] = True
    j = K(c2)
    j.atualizar(caso["dados"])
    return j.grab().toImage()


def congelar_relogio():
    import time as _t
    _t.monotonic = lambda: 5000.0
    _t.time = lambda: 1.7e9


if __name__ == "__main__":                      # processo filho: arquivos da build au
    pasta_au, entrada, saida = sys.argv[1:4]
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["WOLFX_IDIOMA"] = "pt"
    sys.argv = ["x", "--demo"]
    sys.path.insert(0, OVERLAY)
    sys.path.insert(0, pasta_au)                # os arquivos da build au vem primeiro
    congelar_relogio()
    import overlay_iracing as o
    assert os.path.dirname(os.path.abspath(o.__file__)) == os.path.abspath(pasta_au), "a referencia au nao foi a carregada"
    from pathlib import Path
    from PySide6.QtWidgets import QApplication
    S = Path(tempfile.mkdtemp())
    o.ARQ_LOG = S / "l.txt"
    o.ARQ_CONFIG = S / "c.json"
    app = QApplication([])
    o.salvar_config = lambda c_: None
    o.carregar_fontes_corrida()                  # mesma condicao do processo do teste
    with open(entrada, "rb") as f:
        casos = pickle.load(f)
    for caso in casos:
        render_caso(o, caso).save(os.path.join(saida, caso["id"].replace(":", "_").replace("/", "_") + ".png"))
