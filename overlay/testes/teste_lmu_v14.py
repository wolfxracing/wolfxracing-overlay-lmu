# -*- coding: utf-8 -*-
"""
Testes automaticos do LMU 1.4.0 - janela Curvas (velocidade minima por curva), pelo caminho completo:
memoria falsa do jogo -> TelemetriaLMU -> analisador -> janela. NAO prova que o LMU real entrega os dados assim.
Execucao: python testes\\teste_lmu_v14.py
"""
import math
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import teste_lmu as T                                   # noqa: E402
import teste_curvas as tc                               # noqa: E402
from teste_lmu import confere, grupo                    # noqa: E402


def preparar(j):
    j.carros[3].voltas = 1
    j.carros[3].dist = 0.0
    tel, rel = T.telemetria(j)
    return tel, rel


def volta(j, tel, rel, ajuste=None, hz=30, **mudancas):
    """Uma volta completa do jogador (carro 4) passando por TelemetriaLMU.ler()."""
    jogador = j.carros[3]
    comp = j.comprimento
    pct, d = 0.0, None
    for k, v in mudancas.items():
        setattr(j, k, v)
    while pct < 1.0:
        v = tc.velocidade(pct, ajuste)
        j.vel_ms = (0.0, 0.0, -v / 3.6)
        j.volante = -(120.0 if v < 150 else 4.0) / 270.0          # curso visual de 540 graus: positivo = direita no jogo
        jogador.dist = pct * comp
        rel.avancar(1.0 / hz)
        j.et += 1.0 / hz
        j.tempo_decorrido += 1.0 / hz
        d = tel.ler()
        pct += (v / 3.6) / hz / comp
    return d


def fechar(j, tel, rel):
    j.carros[3].dist = 0.01 * j.comprimento
    rel.avancar(0.03)
    return tel.ler()


def teste_curvas_lmu():
    grupo("v1.4.0 - Curvas no LMU (caminho completo)")
    m = T.preparar_modulo()
    j = T.cenario_corrida()
    tel, rel = preparar(j)
    d = tel.ler()
    confere(d.get("curvas") is not None and d["curvas"]["estado"] == "aprendendo", "antes da primeira volta: aprendendo")
    volta(j, tel, rel)
    volta(j, tel, rel)
    d = fechar(j, tel, rel)
    c = d["curvas"]
    confere(c["estado"] == "ok" and c["n"] == 5, f"5 curvas mapeadas ({c['estado']}, {c['n']})")
    confere(tel.v14_curvas.voltas_validas == 2, f"2 voltas validas ({tel.v14_curvas.voltas_validas})")
    volta(j, tel, rel, ajuste={0: 7.0, 1: -9.0})
    d = fechar(j, tel, rel)
    va = d["curvas"]["volta_anterior"]
    confere(va is not None and va["pior_n"] == 2 and va["perda"] > 8.0, f"volta anterior: pior curva C2 ({va})")

    # ao vivo: C2 mais lenta
    jogador, comp = j.carros[3], j.comprimento
    pct = 0.02
    while pct < 0.45:
        v = tc.velocidade(pct, {1: -12.0})
        j.vel_ms = (0.0, 0.0, -v / 3.6)
        j.volante = -(120.0 if v < 150 else 4.0) / 270.0
        jogador.dist = pct * comp
        rel.avancar(1 / 30.0)
        d = tel.ler()
        pct += (v / 3.6) / 30.0 / comp
    c2 = [r for r in d["curvas"]["lista"] if r["n"] == 2]
    confere(bool(c2) and -14.0 < c2[0]["delta"] < -8.0, f"C2 12 km/h mais lenta: DELTA ~ -12 ({c2[0]['delta'] if c2 else None})")
    confere(bool(c2) and abs(abs(c2[0]["volante"]) - 120.0) < 1.5, "volante no ponto da minima (graus do jogo)")

    # boxes, fora da pista e grid nao contam
    validas = tel.v14_curvas.voltas_validas
    jogador.box = True
    volta(j, tel, rel)
    jogador.box = False
    volta(j, tel, rel)
    fechar(j, tel, rel)
    confere(tel.v14_curvas.voltas_validas == validas + 1, f"volta nos boxes nao conta ({validas} -> {tel.v14_curvas.voltas_validas})")
    validas = tel.v14_curvas.voltas_validas
    j.superficie = 2                                            # 4 rodas na grama
    volta(j, tel, rel)
    j.superficie = 0
    volta(j, tel, rel)
    fechar(j, tel, rel)
    confere(tel.v14_curvas.voltas_validas == validas + 1, "volta fora da pista nao conta")

    # sessao nova zera
    j.sessao = 3
    j.et += 5.0
    rel.avancar(5.0)
    d = tel.ler()
    confere(not tel.v14_curvas.curvas and d["curvas"]["estado"] == "aprendendo", "sessao nova zera o aprendizado")

    # janela e menu
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    cfg = m.base.carregar_config()
    cfg["travado"] = True
    jan = m.base.JanelaCurvas(dict(cfg))
    jan.show()
    dd = m.base.Telemetria(demo=True).ler()
    jan.atualizar(dd)
    jan.repaint()
    img = jan.grab().toImage()
    alfa = sum(img.pixelColor(x, y).alpha() for y in range(0, img.height(), 4) for x in range(0, img.width(), 4))
    confere(alfa > 0, "janela Curvas desenha com os dados de demonstracao")
    for chave in ("x_curvas", "y_curvas", "mostrar_curvas", "escala_curvas"):
        confere(chave in cfg, f"config tem {chave}")


TESTES = [teste_curvas_lmu]

if __name__ == "__main__":
    for t in TESTES:
        try:
            t()
        except Exception:
            T._falhas.append(f"{t.__name__}: excecao")
            print("  EXCECAO em", t.__name__)
            traceback.print_exc()
    print(f"\nResultado LMU 1.4.0: {T._ok} verificacoes ok, {len(T._falhas)} falha(s).")
    for f in T._falhas:
        print(" -", f)
    sys.exit(1 if T._falhas else 0)
