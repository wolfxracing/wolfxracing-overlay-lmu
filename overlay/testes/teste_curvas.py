# -*- coding: utf-8 -*-
"""
Testes automaticos da v1.4.0 - velocidade minima por curva (ov_curvas.py).
Pista simulada de 5000 m com 5 curvas (uma delas e uma chicane de duas), volantes e voltas com qualidade diferente.
Execucao: python testes\\teste_curvas.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ov_curvas as oc          # noqa: E402

_ok = 0
_falhas = []


def confere(cond, msg):
    global _ok
    if cond:
        _ok += 1
    else:
        _falhas.append(msg)
        print("  FALHOU:", msg)


COMP = 5000.0
# (posicao 0..1, velocidade minima km/h, largura em metros)
CURVAS = [(0.10, 110.0, 90.0), (0.30, 70.0, 70.0), (0.335, 95.0, 50.0), (0.55, 150.0, 120.0), (0.82, 90.0, 80.0)]


def velocidade(pct, ajuste=None, reta=260.0):
    """Perfil de velocidade: reta de 260 km/h com um mergulho gaussiano por curva."""
    v = reta
    for k, (centro, vmin, larg) in enumerate(CURVAS):
        d = (pct - centro) * COMP
        v = min(v, reta - (reta - (vmin + (ajuste or {}).get(k, 0.0))) * math.exp(-(d / larg) ** 2))
    return v


def volta(a, ajuste=None, hz=60, fator=1.0, valido=lambda p: True, reta=260.0, pular=None):
    """Percorre uma volta inteira (pct 0 -> 1) alimentando o analisador. Devolve o ultimo resumo."""
    pct, res = 0.0, None
    while pct < 1.0:
        v = velocidade(pct, ajuste, reta) * fator
        if pular is None or not (pular[0] <= pct <= pular[1]):
            res = a.atualizar(pct, v, volante=(120.0 if v < 150 else 5.0), valido=valido(pct), comprimento=COMP)
        pct += (v / 3.6) / hz / COMP
    return res


def fechar(a):
    """A volta so fecha quando chega a primeira amostra depois da linha de chegada."""
    return a.atualizar(0.01, 255.0, 0.0, True, COMP)


def principal():
    print("\n=== v1.4.0 - detector de curvas ===")
    # ---- 1. deteccao no perfil ------------------------------------------------------------------------------
    perfil = [velocidade(i / oc.BINS) for i in range(oc.BINS)]
    achadas = oc.detectar_curvas(perfil, COMP)
    centros = [c["centro"] / oc.BINS for c in achadas]
    confere(len(achadas) == 5, f"acha as 5 curvas da pista simulada ({len(achadas)})")
    for esperado, (centro, _v, _l) in zip(centros, CURVAS):
        confere(abs(esperado - centro) < 0.008, f"curva em {centro:.3f} achada em {esperado:.3f}")
    confere(all(a["ini"] <= a["centro"] <= a["fim"] for a in achadas), "o centro de cada curva esta dentro da sua janela")
    confere(all(achadas[i]["fim"] < achadas[i + 1]["ini"] + 2 for i in range(len(achadas) - 1)), "janelas nao se sobrepoem")
    confere(oc.detectar_curvas([200.0] * oc.BINS, COMP) == [], "reta continua: nenhuma curva")
    confere(oc.detectar_curvas([200.0 - (i % 7) for i in range(oc.BINS)], COMP) == [], "ruido pequeno nao vira curva")
    confere(oc.preencher([None] * oc.BINS) is None, "sem nenhuma amostra: perfil indisponivel")
    confere(oc.preencher([100.0] * 500 + [None] * 200 + [100.0] * 300) is None, "mais de 8% sem amostra: invalido")
    p = oc.preencher([100.0, None, None, 130.0] + [130.0] * 996)
    confere(p is not None and abs(p[1] - 110.0) < 1e-9 and abs(p[2] - 120.0) < 1e-9, "interpola lacunas curtas")

    # ---- 2. primeira volta so aprende ----------------------------------------------------------------------
    a = oc.AnalisadorCurvas()
    r = volta(a)
    confere(r["estado"] == "aprendendo" and r["n"] == 0, "durante a 1a volta: aprendendo")
    r = volta(a)
    fechar(a)                                                       # cruza a linha: fecha a 1a volta valida
    confere(a.voltas_validas == 2 and len(a.curvas) == 5, f"voltas validas contadas e 5 curvas mapeadas ({a.voltas_validas}, {len(a.curvas)})")
    confere(all(abs(m - alvo[1]) < 3.0 for m, alvo in zip(a.melhor, CURVAS)),
            f"BEST = minima de cada curva ({[round(m) for m in a.melhor]})")

    # ---- 3. 2a volta: melhor em C1 (+6), pior em C2 (-8); DELTA contra a passagem anterior ------------------
    a = oc.AnalisadorCurvas()
    volta(a)
    fechar(a)
    volta(a, ajuste={0: 6.0, 1: -8.0})
    fechar(a)
    confere(a.voltas_validas == 2, f"duas voltas validas ({a.voltas_validas})")
    va = a.volta_anterior
    confere(va is not None and va["perda"] > 6.0 and va["pior_n"] == 2, f"volta anterior: pior curva C2 ({va})")
    confere(va["ganho"] > 3.0, "volta anterior: ganho em C1")
    confere(a.melhor[0] > 112.0 and abs(a.melhor[1] - 70.0) < 3.0, f"BEST sobe em C1 e fica em C2 ({[round(m) for m in a.melhor]})")

    # ---- 4. ao vivo: a cada curva concluida aparece o cartao -----------------------------------------------
    a = oc.AnalisadorCurvas()
    volta(a)
    fechar(a)
    volta(a, ajuste={})                                             # 2a volta (valida) ja com o mapa
    fechar(a)
    # 3a volta passo a passo, parando logo depois da C2
    pct, ultimo_n = 0.02, []
    while pct < 0.45:
        v = velocidade(pct, {1: -10.0})
        res = a.atualizar(pct, v, 140.0 if v < 120 else 3.0, True, COMP)
        if res["ultima"] and (not ultimo_n or ultimo_n[-1] != res["ultima"]["n"]):
            ultimo_n.append(res["ultima"]["n"])
        pct += (v / 3.6) / 60 / COMP
    confere(ultimo_n[-3:] == [1, 2, 3] or ultimo_n[-2:] == [1, 2], f"cartao mostra C1 e depois C2 ({ultimo_n})")
    confere(ultimo_n[0] == 5, "no inicio da volta ainda mostra a ultima curva da volta anterior (C5)")
    u = res["ultima"]
    confere(u["n"] == 3 or u["n"] == 2, "ultima curva concluida coerente")
    c2 = [x for x in res["lista"] if x["n"] == 2][0]
    confere(-12.0 < c2["delta"] < -7.0, f"C2 10 km/h mais lenta: DELTA ~ -10 ({c2['delta']:.1f})")
    confere(abs(c2["volante"] - 140.0) < 0.1, "volante no ponto da minima registrado")
    confere(c2["best"] is not None and abs(c2["best"] - 70.0) < 3.0, "BEST da C2 vem das voltas anteriores")

    # ---- 5. voltas invalidas nao contam ---------------------------------------------------------------------
    a = oc.AnalisadorCurvas()
    volta(a)
    volta(a)
    fechar(a)
    antes = a.voltas_validas
    volta(a, valido=lambda p: not (0.4 < p < 0.45))                 # tocou os boxes / saiu da pista
    fechar(a)
    confere(antes == 2 and a.voltas_validas == antes, f"volta com trecho invalido nao conta ({antes} -> {a.voltas_validas})")
    a2 = oc.AnalisadorCurvas()
    volta(a2)
    volta(a2)
    fechar(a2)
    antes = a2.voltas_validas
    volta(a2, fator=0.6)                                            # muito lenta (rodada)
    fechar(a2)
    confere(a2.voltas_validas == antes, "volta muito lenta nao conta")
    a3_ = oc.AnalisadorCurvas()
    volta(a3_)
    volta(a3_)
    fechar(a3_)
    antes = a3_.voltas_validas
    volta(a3_, pular=(0.2, 0.35))                                   # 15% sem dados
    fechar(a3_)
    confere(a3_.voltas_validas == antes, "volta sem cobertura nao conta")

    # ---- 6. reset, saltos e entradas ruins -------------------------------------------------------------------
    a = oc.AnalisadorCurvas()
    volta(a)
    volta(a)
    a.atualizar(0.5, 200.0, 0.0, True, COMP)
    a.atualizar(0.1, 200.0, 0.0, True, COMP)                        # voltou no tempo: descarta a volta em curso
    confere(a._vmin.count(None) > 990, "voltar no tempo descarta a volta em andamento")
    for ruim in ((None, 100.0), (0.5, None), (float("nan"), 100.0), (0.5, float("inf"))):
        try:
            a.atualizar(ruim[0], ruim[1], 0.0, True, COMP)
            confere(True, "entrada invalida ignorada")
        except Exception as e:
            confere(False, f"entrada invalida derrubou: {e}")
    a.resetar()
    confere(a.resumo()["estado"] == "aprendendo" and a.voltas_validas == 0 and not a.curvas, "resetar volta ao inicio")

    # ---- 7. congela depois de 3 voltas e herda o BEST ao re-mapear ---------------------------------------------
    a = oc.AnalisadorCurvas()
    for _ in range(5):
        volta(a)
    confere(a.congelado and len(a.curvas) == 5, "mapa de curvas congela depois de 3 voltas validas")
    a = oc.AnalisadorCurvas()
    volta(a)
    volta(a)
    a._adotar([dict(c) for c in a.curvas[:3]])
    confere(len(a.curvas) == 3 and all(m is not None for m in a.melhor), "novo mapa herda o BEST das curvas que ficaram no lugar")

    # ---- 8. custo por amostra --------------------------------------------------------------------------------
    import time
    a = oc.AnalisadorCurvas()
    volta(a)
    t0 = time.perf_counter()
    n = 0
    pct = 0.0
    while pct < 0.99:
        a.atualizar(pct, velocidade(pct), 10.0, True, COMP)
        pct += 0.0001
        n += 1
    custo = (time.perf_counter() - t0) / n * 1000.0
    confere(custo < 0.2, f"custo por amostra baixo ({custo:.4f} ms)")

    print(f"\nResultado curvas: {_ok} verificacoes ok, {len(_falhas)} falha(s).")
    for f in _falhas:
        print(" -", f)
    return 1 if _falhas else 0


if __name__ == "__main__":
    sys.exit(principal())
