# -*- coding: utf-8 -*-
"""1.7.0 - o Coach considera tambem a TIRADA DE PE (acelerador cai sem freio): zonas, contagem TIRE e avaliacao."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ov_coach as co

falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

L, N = 4000.0, 1000          # 4 m por trecho
# pista: tirada de pe em 1000-1060 m (curva rapida), freada forte em 2400-2490 m, e uma tirada COLADA na freada (2300-2390)
def acel_em(x):
    if 1000 <= x < 1060: return 0.0
    if 2300 <= x < 2500: return 0.0
    if 3200 <= x < 3500: return 0.7        # acelerador parcial na saida: nao e tirada
    return 1.0
def freio_em(x): return 0.9 if 2400 <= x < 2490 else 0.0
def vel_em(x):
    if 1000 <= x < 1060: return 190 - 30 * (x - 1000) / 60 if x < 1030 else 160 + 30 * (x - 1030) / 30
    if 2300 <= x < 2500: return 200 - 120 * min(1, (x - 2300) / 160)
    return 200.0
xs = [(i + 0.5) * L / N for i in range(N)]
ref = co.nova_referencia("Pista Teste", "Carro Teste", "propria", L, 90.0, [vel_em(x) for x in xs], [freio_em(x) for x in xs],
                         [acel_em(x) for x in xs], [4] * N, [i * 0.09 for i in range(N)])

zt = co.zonas_de_tirada(ref)
confere(len(zt) == 1 and zt[0]["tipo"] == "tirada", f"acha 1 zona de tirada (a colada na freada e a de acelerador parcial nao contam): {len(zt)}")
confere(abs(zt[0]["ini"] * 4 - 1000) <= 8, f"a tirada comeca perto de 1000 m ({zt[0]['ini'] * 4} m)")
confere(len(co.zonas_de_frenagem(ref)) == 1, "a freada continua sendo uma zona de freada")
todas = co.todas_as_zonas(ref)
confere([z["n"] for z in todas] == [1, 2] and [z["tipo"] for z in todas] == ["tirada", "freio"], "numeracao conjunta C1 (tirada), C2 (freada)")

# --- ao vivo: guia e contagem
def volta(c, atraso_m=0.0, tira=True):
    """Dirige uma volta contra a referencia. atraso_m: tirada tardia (positivo = mais tarde que a referencia)."""
    guias, fbs, v = [], [], 0.0
    for k in range(0, 2000):
        x = k * 2.0 + 0.5
        if x >= L: break
        a = 1.0
        if tira and 1000 + atraso_m <= x < 1060 + atraso_m: a = 0.0
        if 2300 <= x < 2500: a = 0.0
        r = c.atualizar(x / L, vel_em(x), freio_em(x), a, 4, x * 0.045, True, L, None)
        if r["proxima"]: guias.append(r["proxima"])
        if r["feedback"] and (not fbs or r["feedback"] is not fbs[-1]): fbs.append(r["feedback"])
    return guias, fbs
with tempfile.TemporaryDirectory() as d:
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref); c.modo = "importada"
    guias, fbs = volta(c)
    conts = [(g["tipo"], g["contagem"]) for g in guias if g["contagem"]]
    confere(("tirada", "TIRE") in conts and ("tirada", "3") in conts, "contagem 3-2-1-TIRE antes da tirada")
    confere(("freio", "FREIE") in conts, "e 3-2-1-FREIE antes da freada")
    confere(not any(t == "tirada" and cn == "FREIE" for t, cn in conts), "tirada nunca mostra FREIE")
    tir = [f for f in fbs if f["tipo"] == "tirada"]
    confere(len(tir) == 1 and tir[0]["nota"] in ("perfeita", "boa") and "tirada" in tir[0]["texto"], f"tirada no ponto: {tir and tir[0]['texto']}")
    c2 = co.Coach(co.BibliotecaReferencias(d)); c2.definir_contexto("Pista Teste", "Carro Teste", L)
    c2.definir_importada(ref); c2.modo = "importada"
    _, fbs = volta(c2, atraso_m=40.0)
    tir = [f for f in fbs if f["tipo"] == "tirada"]
    confere(tir and tir[0]["nota"] in ("tarde", "muito_tarde") and "tirou o pe" in tir[0]["texto"], f"tirada 40 m tarde: {tir and tir[0]['texto']}")
    c3 = co.Coach(co.BibliotecaReferencias(d)); c3.definir_contexto("Pista Teste", "Carro Teste", L)
    c3.definir_importada(ref); c3.modo = "importada"
    _, fbs = volta(c3, tira=False)
    tir = [f for f in fbs if f["tipo"] == "tirada"]
    confere(tir and tir[0]["nota"] == "sem_tirada" and tir[0]["gravidade"] < 100, f"sem tirar o pe: {tir and tir[0]['texto']}")

print("\n" + ("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")); sys.exit(1 if falhas else 0)
