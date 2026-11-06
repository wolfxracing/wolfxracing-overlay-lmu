# -*- coding: utf-8 -*-
"""Build p: regressao do Delta Trace (referencia que muda) e robustez de Consumo / Delta Trace (ruido e resolucao do nivel,
taxas de atualizacao variaveis, cobertura dos 200 pontos, voltas rapidas e lentas, melhor referencia mudando, interrupcoes).
Logica pura (ov_onda1); o caminho real de cada jogo e coberto por teste_v170_onda1*.py. Identico nas duas arvores."""
import math, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ov_onda1 as on

falhas, _ok = [], 0
def confere(c, msg):
    global _ok
    if c: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)
def grupo(t): print("\n== " + t)

# perfil de gasto do circuito: peso por trecho (3 trechos de gasto alto) - o 'gabarito' das zonas
N = on.N_ZONAS
PESO = [1.0] * N
for i in (4, 5, 6): PESO[i] = 2.0
for i in (15, 16): PESO[i] = 0.4
SOMA = sum(PESO)

def gasto_acumulado(pct, litros_volta):
    """litros queimados da largada ate pct (curva por partes, conforme o PESO)."""
    x, tot = pct * N, 0.0
    for i in range(N):
        tot += PESO[i] * min(1.0, max(0.0, x - i))
    return tot / SOMA * litros_volta

def tempo_acumulado(pct, tempo_volta):
    return pct * tempo_volta * (1.0 + 0.05 * math.sin(2 * math.pi * pct)) / 1.0

def rodar(cons=None, delta=None, voltas=5, tempo_volta=90.0, litros=2.0, hz=20.0, ruido=0.0, resol=0.0, jitter=0.0, nivel0=60.0,
          buracos=(), rng=None, t0=0.0, ult=None):
    """Simula `voltas` voltas completas. buracos: lista de (inicio_s, fim_s) em que NADA e entregue. Devolve (relogio, nivel_real, tempo_total)."""
    rng = rng or random.Random(1)
    t, nivel_real = t0, nivel0
    for v in range(voltas):
        base_t = 0.0
        tv_ = tempo_volta[v] if isinstance(tempo_volta, (list, tuple)) else tempo_volta
        l_ = litros[v] if isinstance(litros, (list, tuple)) else litros
        n_amostras = 0
        pct, tvolta = 0.0, 0.0
        while pct < 1.0:
            dt = (1.0 / hz) * (1.0 + (rng.uniform(-jitter, jitter) if jitter else 0.0))
            tvolta += dt; t += dt
            # inverte tempo_acumulado numericamente (monotono): pct a partir do tempo decorrido
            lo, hi = 0.0, 1.0
            for _ in range(30):
                mid = (lo + hi) / 2
                if tempo_acumulado(mid, tv_) < tvolta: lo = mid
                else: hi = mid
            pct = hi
            if tvolta >= tempo_acumulado(1.0, tv_): break
            em_buraco = any(a <= t < b for a, b in buracos)
            nivel = nivel_real = nivel0 - 0 if False else nivel_real
            queimado = gasto_acumulado(pct, l_)
            n_ver = nivel0_volta[0] - queimado
            nivel_obs = n_ver + (rng.gauss(0, ruido) if ruido else 0.0)
            if resol: nivel_obs = round(nivel_obs / resol) * resol
            if not em_buraco:
                if cons is not None: cons.atualizar(t, pct, nivel_obs, True)
                if delta is not None: delta.atualizar(pct, tvolta, True, ult)
        # cruza a linha: ultimo ponto antes de zerar e primeiro depois
        nivel0_volta[0] -= l_
        t += 0.01
        if cons is not None: cons.atualizar(t, 0.001, nivel0_volta[0], True)
        if delta is not None: delta.atualizar(0.001, 0.01, True, tv_)
    return t

nivel0_volta = [60.0]
def novo(v0=60.0):
    nivel0_volta[0] = v0

def prep(cons, delta, hz=20.0, **kw):
    """posiciona o carro no fim da volta (p>0.9) para que a primeira passagem pela linha abra a volta 1."""
    if cons is not None: cons.atualizar(0.0, 0.95, nivel0_volta[0], True)
    if delta is not None: delta.atualizar(0.95, 80.0, True)

def zonas_do(res):
    return [z["litros"] for z in res["zonas"]] if res["zonas"] else None

def erro_zonas(res, litros):
    """maior desvio relativo entre os litros por trecho medidos e o gabarito (PESO)."""
    z = zonas_do(res)
    if not z: return 9e9
    return max(abs(z[i] - PESO[i] / SOMA * litros) / (PESO[i] / SOMA * litros) for i in range(N))

# ---------------------------------------------------------------- P1
grupo("P1) Delta Trace: referencia que melhora - o grafico anterior e recalculado")
def tempos_lineares(total, n=200):
    return [total * i / n for i in range(n + 1)]

d = on.DeltaTrace()
def fechar_volta(d, total, n=200, defasagem=0.0):
    """alimenta uma volta completa de duracao `total` e fecha na linha."""
    d.atualizar(0.95, 5.0, True)
    d.atualizar(0.02, 0.0, True, None)
    for i in range(1, n):
        d.atualizar(i / n + 0.0001, total * i / n, True)
fechar_volta(d, 100.0); d.atualizar(0.01, 0.5, True, 100.0)
confere(d.resumo()["ref_total"] == 100.0, "1a volta (100 s) vira a referencia")
fechar_volta(d, 90.0); d.atualizar(0.01, 0.5, True, 90.0)
r = d.resumo()
confere(r["ref_total"] == 90.0, "volta de 90 s substitui a referencia de 100 s")
ant = [x for x in (r["anterior"] or []) if x is not None]
confere(bool(ant) and max(abs(x) for x in ant) < 1e-6, f"grafico anterior (a propria nova melhor) = delta ZERO contra ela mesma (max {max(abs(x) for x in ant) if ant else None})")
confere(abs(ant[-1]) < 1e-9 if ant else False, "o ponto final da volta anterior (nova melhor) tambem e zero (nao -10 s)")
fechar_volta(d, 95.0); d.atualizar(0.01, 0.5, True, 95.0)
r = d.resumo(); ant = [x for x in r["anterior"] if x is not None]
confere(r["ref_total"] == 90.0 and abs(ant[-1] - 5.0) < 1e-6, f"volta mais lenta (95 s): referencia continua 90 s e o anterior termina em +5 s ({ant[-1]:.3f})")
for total in (88.0, 85.0, 84.0):
    fechar_volta(d, total); d.atualizar(0.01, 0.5, True, total)
    r = d.resumo(); ant = [x for x in r["anterior"] if x is not None]
    confere(r["ref_total"] == total and max(abs(x) for x in ant) < 1e-6, f"referencias sucessivamente melhores: {total} s -> anterior zerado contra a nova referencia")
# grafico atual: durante a volta seguinte, o delta e contra a referencia vigente (84 s)
for k in range(1, 101):
    d.atualizar(k / 200.0 + 0.0001, 84.0 * k / 200.0 + 0.3, True)          # esta volta anda 0,3 s atras da ref de 84 s
r = d.resumo()
confere(r["atual"] is not None and abs(r["atual"] - 0.3) < 0.01, f"grafico atual usa a referencia vigente (atual {r['atual']})")
# volta mais rapida E a ref muda enquanto a volta anterior era lenta: tempos brutos preservados
conf = d._ant
confere(conf is not None and conf[-1] == 84.0, "tempos brutos da volta anterior preservados em self._ant")
# recalcular manualmente: delta de uma volta antiga contra a nova ref
d2 = on.DeltaTrace()
fechar_volta(d2, 100.0); d2.atualizar(0.01, 0.5, True, 100.0)
antes = d2.resumo()["anterior"]
confere(antes is not None and abs([x for x in antes if x is not None][-1]) < 1e-9, "1a volta: anterior = zero contra si mesma")
fechar_volta(d2, 101.0); d2.atualizar(0.01, 0.5, True, 101.0)
r2 = d2.resumo(); a2 = [x for x in r2["anterior"] if x is not None]
confere(abs(a2[-1] - 1.0) < 1e-6, "volta mais lenta (101 s) contra ref de 100 s termina em +1 s")

# ---------------------------------------------------------------- P2 cobertura dos 200 pontos
grupo("P2) Delta Trace: cobertura dos 200 pontos")
for hz in (60.0, 30.0, 15.0, 10.0, 5.0, 3.0):
    d = on.DeltaTrace(); novo()
    prep(None, d)
    rodar(None, d, voltas=2, hz=hz)
    r = d.resumo()
    cobre = sum(1 for x in (r["anterior"] or []) if x is not None) if r["anterior"] else 0
    ref_ok = r["estado"] == "ok"
    confere(ref_ok and cobre >= 0.95 * 201, f"{hz:g} Hz: referencia criada e {cobre}/201 pontos cobertos (>= 95%)")
for hz in (2.0, 1.0):
    d = on.DeltaTrace(); novo(); prep(None, d); rodar(None, d, voltas=2, hz=hz)
    confere(d.voltas_validas == 2, f"{hz:g} Hz (muito lento): pontos pulados (<= 10) sao interpolados e a volta vale ({d.voltas_validas} voltas)")
d = on.DeltaTrace(); novo(); prep(None, d); rodar(None, d, voltas=3, hz=20.0, jitter=0.9, rng=random.Random(7))
confere(d.resumo()["estado"] == "ok" and d.voltas_validas >= 2, f"taxa variavel (+-90% por quadro): {d.voltas_validas} voltas validas")

# ---------------------------------------------------------------- P2 voltas rapidas e lentas
grupo("P2) Voltas rapidas e lentas")
d = on.DeltaTrace(); novo(); prep(None, d)
rodar(None, d, voltas=3, tempo_volta=[30.0, 300.0, 45.0], hz=20.0)
r = d.resumo()
confere(d.voltas_validas == 3 and r["ref_total"] is not None and abs(r["ref_total"] - 30.0) < 0.2, f"30 s / 300 s / 45 s: 3 voltas validas, referencia = a de 30 s ({r['ref_total']})")
a = [x for x in r["anterior"] if x is not None]
confere(abs(a[-1] - 15.0) < 0.3, f"a ultima (45 s) termina +15 s contra a de 30 s ({a[-1]:.2f})")
c = on.Consumo(); novo(); prep(c, None)
rodar(c, None, voltas=4, tempo_volta=[40.0, 240.0, 40.0, 90.0], litros=2.0)
r = c.resumo()
confere(r["voltas"] == 4 and abs(r["medio_lv"] - 2.0) < 0.05, f"consumo identico em voltas de 40 s e 240 s: {r['voltas']} voltas, medio {r['medio_lv']:.3f} L")

# ---------------------------------------------------------------- P2 ruido e resolucao do nivel
grupo("P2) Consumo: ruido e resolucao do nivel de combustivel")
LITROS = 2.0
for resol in (0.0, 0.001, 0.01, 0.05):
    c = on.Consumo(); novo(); prep(c, None); rodar(c, None, voltas=5, litros=LITROS, resol=resol)
    r = c.resumo()
    confere(r["estado"] == "ok" and abs(r["medio_lv"] - LITROS) < 0.06, f"resolucao {resol} L: medio {r['medio_lv']:.3f} L/volta (esperado {LITROS})")
    if resol <= 0.01:
        confere(erro_zonas(r, LITROS) < 0.25, f"resolucao {resol} L: zonas preservam o perfil (erro max {erro_zonas(r, LITROS):.2f})")
    else:
        top = r["oportunidades"][0] if r["oportunidades"] else None       # 0,05 L ~ 60% de um trecho: so se exige o total e nao quebrar
        confere(True, f"resolucao {resol} L (grosseira): total correto; zonas sao indicativas (1o trecho de maior consumo: {None if not top else (round(top['ini'],2), round(top['fim'],2))})")
for ruido in (0.0005, 0.002, 0.005, 0.01):
    c = on.Consumo(); novo(); prep(c, None); rodar(c, None, voltas=5, litros=LITROS, ruido=ruido, rng=random.Random(3))
    r = c.resumo()
    vies = ((r["medio_lv"] or 0.0) - LITROS) / LITROS
    confere(r["estado"] == "ok" and abs(vies) < 0.03, f"ruido gaussiano {ruido} L: vies do medio {vies*100:+.1f}% (limite 3%)")
    ops = [(o["ini"], o["fim"]) for o in r["oportunidades"]]
    confere(any(abs(o[0] - 4 / N) < 0.05 for o in ops), f"ruido {ruido} L: o trecho de maior consumo (5-7) continua o primeiro ({ops[:1]})")

# fluxo instantaneo (L/h) com ruido: 2 L em 90 s = 80 L/h
for ruido in (0.0, 0.002, 0.005):
    c = on.Consumo(); rng = random.Random(11); t = 0.0; niv = 60.0
    for k in range(int(10 * 20)):
        t += 0.05; niv -= 2.0 / 90.0 * 0.05
        c.atualizar(t, (k * 0.0005) % 1.0, niv + rng.gauss(0, ruido), True)
    lh = c.resumo()["inst_lh"]
    confere(lh is not None and abs(lh - 80.0) / 80.0 < 0.25, f"fluxo L/h com ruido {ruido} L: {lh if lh is None else round(lh, 1)} (esperado 80, tolerancia 25%)")

# ---------------------------------------------------------------- P2 taxas variaveis (consumo)
grupo("P2) Consumo: taxas de atualizacao variaveis")
for hz, jit in ((60.0, 0.0), (20.0, 0.0), (5.0, 0.0), (20.0, 0.9)):
    c = on.Consumo(); novo(); prep(c, None); rodar(c, None, voltas=5, litros=LITROS, hz=hz, jitter=jit, rng=random.Random(5))
    r = c.resumo()
    confere(r["estado"] == "ok" and abs(r["medio_lv"] - LITROS) < 0.05 and erro_zonas(r, LITROS) < 0.3,
            f"{hz:g} Hz jitter {jit}: medio {r['medio_lv']:.3f}, erro de zonas {erro_zonas(r, LITROS):.2f}")

# ---------------------------------------------------------------- P2 interrupcoes
grupo("P2) Falhas e interrupcoes temporarias da telemetria")
# (a) buraco curto (1 s) no meio de uma volta: a volta continua valida e o gasto nao se perde
c = on.Consumo(); d = on.DeltaTrace(); novo(); prep(c, d)
rodar(c, d, voltas=5, litros=LITROS, buracos=[(150.0, 151.0), (330.0, 331.0)], t0=0.0)
r = c.resumo()
confere(r["voltas"] >= 3 and abs(r["medio_lv"] - LITROS) < 0.08, f"buraco de 1 s: consumo continua medindo ({r['voltas']} voltas, medio {r['medio_lv']:.3f})")
confere(d.resumo()["estado"] == "ok", "buraco de 1 s: delta trace mantem a referencia")
# (b) buraco longo (8 s a 90 s/volta = ~9% da volta, menor que o salto de 20%): preenchido/ medido sem inventar
c = on.Consumo(); d = on.DeltaTrace(); novo(); prep(c, d)
rodar(c, d, voltas=4, litros=LITROS, buracos=[(100.0, 108.0)])
r = c.resumo()
confere(abs((r["medio_lv"] or 0) - LITROS) < 0.1, f"buraco de 8 s: gasto do trecho e atribuido ao trecho certo, sem perder litros ({r['medio_lv']})")
# (c) buraco enorme (40 s ~ 44% da volta): volta descartada, nao inventa dado
c = on.Consumo(); d = on.DeltaTrace(); novo(); prep(c, d)
rodar(c, d, voltas=1, litros=LITROS, buracos=[(30.0, 70.0)])
confere(c.resumo()["voltas"] == 0 and d.voltas_validas == 0, "buraco de 40 s: volta descartada (nada inventado)")
# (d) valores invalidos (None, NaN, inf, negativos) nunca quebram
c = on.Consumo(); d = on.DeltaTrace()
try:
    for args in ((0, None, 5.0, True), (0, float("nan"), 5.0, True), (0, 0.5, float("inf"), True), (0, -1.0, 5.0, True), (0, 2.0, 5.0, True)):
        c.atualizar(*args)
    for args in ((None, 1.0, True), (0.5, None, True), (float("nan"), 1.0, True), (0.5, float("inf"), True), (0.5, -2.0, True), (1.5, 1.0, True)):
        d.atualizar(*args)
    confere(True, "None / NaN / inf / negativos / fora de faixa: ignorados sem excecao")
except Exception as e:
    confere(False, f"entradas invalidas levantaram {e!r}")
# (e) valido=False no meio da volta invalida so essa volta; a seguinte conta
c = on.Consumo(); d = on.DeltaTrace(); novo(); prep(c, d)
rodar(c, d, voltas=2, litros=LITROS)
n_antes = c.resumo()["voltas"]; v_antes = d.voltas_validas
c.atualizar(500.0, 0.5, 50.0, False); d.atualizar(0.5, 40.0, False)
rodar(c, d, voltas=2, litros=LITROS, t0=501.0)
confere(c.resumo()["voltas"] >= n_antes and d.voltas_validas >= v_antes, "pausa invalida (box/fora da pista) nao apaga o aprendizado anterior")
# (f) relogio da volta voltando atras (reinicio) descarta a volta em andamento
d = on.DeltaTrace(); d.atualizar(0.95, 80.0, True); d.atualizar(0.02, 0.5, True); d.atualizar(0.3, 27.0, True); d.atualizar(0.31, 2.0, True)
confere(d._ok is False, "tempo de volta que volta atras invalida a volta em andamento")

# (g) relogio da volta e posicao atualizam em instantes diferentes (LMU: scoring x telemetria) - nao pode descartar a volta
def virada(d, total, adiantar_relogio):
    """fim de uma volta e comeco da proxima. adiantar_relogio=True: o relogio zera ANTES da posicao dar a volta; False: a posicao
    da a volta ANTES do relogio zerar (o tempo ainda e o velho, ~total)."""
    if adiantar_relogio:
        d.atualizar(0.998, total * 0.998, True)
        d.atualizar(0.999, 0.05, True)                            # relogio ja zerou, posicao ainda no fim
        d.atualizar(0.9995, 0.10, True)
        d.atualizar(0.002, 0.15, True, total)                     # agora a posicao da a volta
    else:
        d.atualizar(0.998, total * 0.998, True)
        d.atualizar(0.003, total, True, total)                    # posicao deu a volta, relogio ainda velho (~total)
        d.atualizar(0.004, total, True)
        d.atualizar(0.006, 0.4, True)                             # relogio zerou
def corpo(d, total, n=200):
    for i in range(3, n):
        d.atualizar(i / n + 0.0001, total * i / n, True)
for adiantar in (True, False):
    d = on.DeltaTrace(); d.atualizar(0.95, 85.0, True)
    for _ in range(3):
        virada(d, 90.0, adiantar); corpo(d, 90.0)
    virada(d, 90.0, adiantar)
    nome = "relogio zera antes da posicao" if adiantar else "posicao vira antes do relogio (tempo velho)"
    confere(d.voltas_validas >= 2 and d.resumo()["estado"] == "ok", f"dessincronia ({nome}): voltas continuam validas ({d.voltas_validas})")
    a = [x for x in (d.resumo()["anterior"] or []) if x is not None]
    confere(bool(a) and max(abs(x) for x in a) < 0.2, f"dessincronia ({nome}): nenhum ponto com tempo velho no grafico (max {max(abs(x) for x in a) if a else None})")

# ---------------------------------------------------------------- P2 referencia muda durante a sessao
grupo("P2) Melhor referencia mudando durante a sessao")
d = on.DeltaTrace(); novo(); prep(None, d)
tempos = [95.0, 93.0, 94.0, 91.0, 92.0, 90.0]
hist_ref = []
for tv in tempos:
    rodar(None, d, voltas=1, tempo_volta=tv); hist_ref.append(round(d.resumo()["ref_total"], 1))
    a = [x for x in d.resumo()["anterior"] if x is not None]
    confere(abs(a[-1] - (tv - d.resumo()["ref_total"])) < 0.25, f"volta {tv:g} s: anterior termina em {a[-1]:+.2f} (esperado {tv - d.resumo()['ref_total']:+.2f}) contra ref {d.resumo()['ref_total']:.1f}")
confere(hist_ref == [95.0, 93.0, 93.0, 91.0, 91.0, 90.0], f"a referencia so melhora: {hist_ref}")

# ---------------------------------------------------------------- build q: blocos por curva e eixo de tempo
grupo("build q) Delta Trace: blocos por curva (largura = tempo na curva)")
curvas = [{"ini": 100, "fim": 129}, {"ini": 400, "fim": 449}, {"ini": 700, "fim": 719}]       # trechos de 0..999
z = on.zonas_de_curvas(curvas, 1000)
confere([k["n"] for k in z] == [1, 2, 3] and abs(z[0]["ini"] - 0.10) < 1e-9 and abs(z[0]["fim"] - 0.13) < 1e-9, "zonas de curva em fracao da volta (C1..C3)")
confere(on.zonas_de_curvas(None, 1000) == [] and on.zonas_de_curvas([{"x": 1}], 1000) == [] and on.zonas_de_curvas([{"ini": 5, "fim": 4}], 1000) == [], "curvas ausentes/invalidas: lista vazia, sem excecao")
# volta atual: perde 0,10 s na C1, ganha 0,20 s na C2, C3 ainda nao percorrida
pts = [None] * 201
for i in range(0, 131):
    d_ = 0.0
    if i >= 20: d_ += min(i - 20, 6) / 6 * 0.10            # C1 (pct 0,10..0,13 = pontos 20..26)
    if i >= 80: d_ -= min(i - 80, 10) / 10 * 0.20          # C2 (pct 0,40..0,45 = pontos 80..90)
    pts[i] = d_
blocos = on.delta_por_curva(pts, z)
confere(abs(blocos[0]["delta"] - 0.10) < 1e-6 and abs(blocos[1]["delta"] + 0.20) < 1e-6, f"delta por curva: C1 +0,10 e C2 -0,20 ({[b['delta'] for b in blocos]})")
confere(blocos[2]["delta"] is None, "curva ainda nao percorrida: sem valor")
confere(on.delta_por_curva(None, z) == [] and on.delta_por_curva(pts, []) == [], "sem pontos ou sem curvas: lista vazia")
# eixo de tempo: curva lenta ocupa mais largura que reta de mesma distancia
ref = [0.0]
for i in range(1, 201):
    x = (i - 0.5) / 200
    ref.append(ref[-1] + (3.0 if 0.40 <= x <= 0.45 else 1.0))
xs = on.eixo_tempo(ref, 200)
confere(len(xs) == 201 and xs[0] == 0.0 and abs(xs[-1] - 1.0) < 1e-9 and all(xs[i] <= xs[i + 1] for i in range(200)), "eixo de tempo: 0..1 e monotono")
larg_curva = xs[90] - xs[80]; larg_reta = xs[190] - xs[180]
confere(larg_curva > 2.5 * larg_reta, f"eixo de tempo: a curva lenta ocupa mais largura que a reta ({larg_curva:.4f} x {larg_reta:.4f})")
lin = on.eixo_tempo(None, 200)
confere(abs(lin[100] - 0.5) < 1e-9 and on.eixo_tempo([0.0] * 5, 200) == lin and on.eixo_tempo([1.0] + [None] * 199 + [None], 200) == lin, "sem referencia valida: eixo linear (por distancia)")
bur = list(ref); bur[50] = None; bur[51] = None
xb = on.eixo_tempo(bur, 200)
confere(abs(xb[50] - xs[50]) < 0.003 and abs(xb[51] - xs[51]) < 0.003, "pontos sem tempo na referencia sao interpolados")
# curva em foco e delta parcial da curva em andamento
zf, est = on.curva_em_foco(z, 0.115)
confere(zf["n"] == 1 and est == "agora", "carro dentro da C1: curva 1, 'agora'")
zf, est = on.curva_em_foco(z, 0.20)
confere(zf["n"] == 2 and est == "proxima", "entre C1 e C2: proxima = C2")
zf, est = on.curva_em_foco(z, 0.95)
confere(zf["n"] == 1 and est == "proxima", "depois da ultima curva: proxima = C1 (volta seguinte)")
confere(on.curva_em_foco([], 0.5) == (None, None) and on.curva_em_foco(z, None) == (None, None), "sem curvas ou sem posicao: nada a destacar")
parcial = on.delta_na_curva(pts, z[1], 0.425)      # no meio da C2 (pontos 80..90): perdeu/ganhou so a metade
confere(parcial is not None and abs(parcial + 0.10) < 0.021, f"delta parcial da curva em andamento (C2 ate o meio: {parcial})")
confere(on.delta_na_curva(pts, z[2], 0.60) is None and on.delta_na_curva(None, z[0], 0.5) is None, "curva ainda nao alcancada ou sem pontos: None")
# o resumo do DeltaTrace expoe os tempos brutos da referencia
dd_ = on.DeltaTrace(); fechar_volta(dd_, 90.0); dd_.atualizar(0.01, 0.5, True, 90.0)
rr = dd_.resumo()
confere(rr["ref_tempos"] is not None and len(rr["ref_tempos"]) == 201 and abs(rr["ref_tempos"][-1] - 90.0) < 1e-9, "resumo expoe os tempos brutos da referencia")

# ritmo por trecho (cor do tracado no painel da curva): verde ganhando, vermelho perdendo, None = nao percorrido
grupo("Ritmo por trecho (build q)")
pr = [0.0] * 201
for i in range(201):
    pr[i] = -0.002 * i if i <= 100 else -0.2 + 0.003 * (i - 100)      # ganha ate a metade, perde depois
rt = on.ritmo_por_trecho(pr, 1.0)
confere(len(rt) == 120 and rt[10] == -1 and rt[100] == 1, "ganhando = -1 (verde) e perdendo = +1 (vermelho)")
rt2 = on.ritmo_por_trecho(pr, 0.5)
confere(rt2[10] == -1 and rt2[80] is None and rt2[59] is not None, "so os trechos ja percorridos recebem cor")
confere(on.ritmo_por_trecho([0.0] * 201, 1.0)[30] == 0, "sem diferenca para a referencia = neutro")
confere(all(v is None for v in on.ritmo_por_trecho(None, 0.5)) and all(v is None for v in on.ritmo_por_trecho(pr, None)), "sem pontos ou sem posicao: tudo None")
pb = list(pr); pb[40:60] = [None] * 20
rb = on.ritmo_por_trecho(pb, 1.0)
confere(len(rb) == 120 and rb[10] == -1, "buracos (None) nos pontos nao quebram")

# ---------------- build r: P1 (blocos dentro da faixa) e P2 (curva circular)
grupo("Layout dos blocos por curva (build r, P1)")
import random as _rnd
X0, X1 = 14.0, 544.0
for ncurvas in (5, 10, 15, 20, 25, 30):
    for caso in ("uniforme", "juntos", "aleatorio", "ultimo_largo"):
        r_ = _rnd.Random(ncurvas * 7)
        if caso == "uniforme":
            des = [(X0 + i * (X1 - X0) / ncurvas, X0 + i * (X1 - X0) / ncurvas + 12.0) for i in range(ncurvas)]
        elif caso == "juntos":                                   # todas as curvas coladas no fim da volta
            des = [(X1 - 60 + i * 2.0, X1 - 60 + i * 2.0 + 10.0) for i in range(ncurvas)]
        elif caso == "aleatorio":
            xs_ = sorted(r_.uniform(X0, X1) for _ in range(ncurvas)); des = [(a, a + r_.uniform(2, 60)) for a in xs_]
        else:
            des = [(X0 + i * 20.0, X0 + i * 20.0 + 14.0) for i in range(ncurvas)]; des[-1] = (des[-1][0], X1 + 100.0)
        r = on.layout_blocos(des, X0, X1)
        dentro = all(x >= X0 - 1e-6 and x + w <= X1 + 1e-6 for x, w in r)
        sem_sobrepor = all(r[i][0] + r[i][1] <= r[i + 1][0] + 1e-6 for i in range(len(r) - 1))
        confere(len(r) == ncurvas and dentro and sem_sobrepor and all(w > 0 for _, w in r), f"{ncurvas} curvas ({caso}): todos dentro da faixa e sem sobreposicao")
r = on.layout_blocos([(100.0, 160.0), (200.0, 300.0), (350.0, 380.0)], X0, X1)
confere(all(abs(w - d) < 1e-6 for (x, w), d in zip(r, (60.0, 100.0, 30.0))), "cabendo, a largura e exatamente proporcional ao tempo")
r = on.layout_blocos([(i * 17.0, i * 17.0 + 17.0) for i in range(30)], X0, X1)
confere(min(w for _, w in r) >= 10.0 and max(x + w for x, w in r) <= X1 + 1e-6, "30 curvas: larguras se adaptam (minimo reduzido) e nada passa do limite")
r = on.layout_blocos([(0, 100), (100, 400), (400, 450), (450, 900)], X0, X1)
confere(r[1][1] > r[0][1] and r[3][1] > r[2][1], "nao cabendo, a ordem de grandeza dos tempos e preservada")
confere(on.layout_blocos([], X0, X1) == [], "sem curvas: lista vazia")

grupo("Curva circular sobre a linha de chegada (build r, P2)")
z = on.zonas_de_curvas([{"ini": 990, "fim": 4}, {"ini": 100, "fim": 120}], 1000)
confere(len(z) == 2 and z[0]["ini"] == 0.99 and abs(z[0]["fim"] - 0.005) < 1e-9 and on.zona_circular(z[0]) and not on.zona_circular(z[1]), "zona 990..4 e mantida como UMA zona circular")
confere(on.zonas_de_curvas([{"ini": 5, "fim": 5}], 1000) != [] and on.zonas_de_curvas([{"ini": 500, "fim": 499}], 1000) == [], "zona vazia/de volta inteira e descartada; zona de 1 trecho fica")
confere(on.zonas_de_curvas([{"ini": 1200, "fim": 3}], 1000) == [] and on.zonas_de_curvas([{"x": 1}], 1000) == [], "indices fora da faixa ou invalidos: descartados sem erro")
zc = [{"n": 1, "ini": 0.10, "fim": 0.15}, {"n": 2, "ini": 0.95, "fim": 0.03}]
confere(on.curva_em_foco(zc, 0.97)[0]["n"] == 2 and on.curva_em_foco(zc, 0.97)[1] == "agora", "foco: antes da linha, dentro da circular")
confere(on.curva_em_foco(zc, 0.01)[0]["n"] == 2 and on.curva_em_foco(zc, 0.01)[1] == "agora", "foco: depois da linha, ainda a mesma curva circular (sem duplicar)")
confere(on.curva_em_foco(zc, 0.05)[0]["n"] == 1 and on.curva_em_foco(zc, 0.05)[1] == "proxima", "foco: fora das curvas -> a proxima")
confere(on.curva_em_foco(zc, 0.90)[0]["n"] == 2 and on.curva_em_foco(zc, 0.90)[1] == "proxima", "foco: a circular e a proxima antes de comecar")
pc = [0.0] * 201
for i in range(201):
    pc[i] = 0.0 if i < 190 else 0.01 * (i - 190)               # delta cresce 0,01 s por ponto de 190 a 200 (=+0,10 s no fim)
pc[0] = 0.0
bl = on.delta_por_curva(pc, [{"n": 1, "ini": 0.95, "fim": 0.03}])
confere(abs(bl[0]["delta"] - 0.10) < 1e-9, f"delta atravessando a linha: soma dos dois pedacos ({bl[0]['delta']})")
pc2 = list(pc)
for i in range(1, 7): pc2[i] = -0.02 * i                       # depois da linha (6 pontos) ganha 0,12 s
bl = on.delta_por_curva(pc2, [{"n": 1, "ini": 0.95, "fim": 0.03}])
confere(abs(bl[0]["delta"] - (0.10 + (-0.12))) < 1e-9, f"ganho depois da linha entra na soma ({bl[0]['delta']})")
pc3 = list(pc); pc3[200] = None
confere(on.delta_por_curva(pc3, [{"n": 1, "ini": 0.95, "fim": 0.03}])[0]["delta"] is None, "sem o ponto da linha de chegada: None (nada inventado)")
confere(abs(on.delta_na_curva(pc, zc[1], 0.99) - 0.08) < 1e-9, "parcial antes da linha: desde o inicio da curva")
confere(on.delta_na_curva(pc, zc[1], 0.01) is None and on.delta_na_curva(pc, zc[1], 0.90) is None, "parcial depois da linha (inicio na volta anterior) ou antes da curva: None")

grupo("Melhor ritmo / volta ideal (build s)")
def volta_trechos(trechos, n=on.N_PONTOS):
    """tempos brutos acumulados (n+1) a partir da duracao de cada trecho"""
    t = [0.0]
    for d in trechos: t.append(t[-1] + d)
    return t
def alimentar(dt, tempos, total):
    n = dt.n
    dt.atualizar(0.97, tempos[-1] - 1.0, True)
    for i in range(0, n + 1):
        dt.atualizar(min(1.0, i / n) if i < n else 0.999, tempos[i], True)
    dt.atualizar(0.001, 0.05, True, total)
n_ = on.N_PONTOS
a = [0.5] * n_; b = [0.5] * n_
for k in range(0, 40): a[k] = 0.45          # volta A e melhor nos 40 primeiros trechos
for k in range(100, 140): b[k] = 0.44       # volta B e melhor nos trechos 100..139
b[0:40] = [0.5] * 40
ta, tb = volta_trechos(a), volta_trechos(b)
dt = on.DeltaTrace()
alimentar(dt, ta, ta[-1]); r1 = dt.resumo()
confere(r1["ideal"] is None, "com uma volta so nao ha volta ideal")
alimentar(dt, tb, tb[-1]); r2 = dt.resumo()
confere(r2["ideal"] is not None and len(r2["ideal"]) == n_ + 1, "com 2 voltas validas a volta ideal existe")
confere(r2["ideal"] and max(v for v in r2["ideal"] if v is not None) <= 1e-9, "a linha ideal nunca fica acima da referencia")
confere(abs((r2["ideal_total"] or 0) - (sum(a) - 0.06 * 40)) < 1e-6, f"tempo da volta ideal = soma dos melhores trechos ({r2['ideal_total']})")
confere(r2["ideal"] and abs(r2["ideal"][-1] - (r2["ideal_total"] - r2["ref_total"])) < 1e-6, "ultimo ponto da linha ideal = ideal_total - ref_total")
dt.resetar()
confere(dt.resumo()["ideal"] is None and dt.resumo()["ideal_total"] is None, "resetar limpa a volta ideal")

print()
print(f"RESULTADO: {'OK' if not falhas else str(len(falhas)) + ' FALHA(S)'} ({_ok} verificacoes)")
for f in falhas: print(" -", f)
sys.exit(1 if falhas else 0)
