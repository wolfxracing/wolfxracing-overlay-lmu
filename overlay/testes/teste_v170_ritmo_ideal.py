# -*- coding: utf-8 -*-
"""Build v (auditoria da build u): Delta Trace - ritmo ideal ESTIMADO (soma dos melhores trechos).
Verifica o algoritmo (propriedades com voltas aleatorias), o comportamento apos troca de referencia, o tratamento de voltas
incompletas/invalidas/com buracos, e que a interface rotula o resultado como estimativa (nunca como volta realmente feita)."""
import os, random, re, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import ov_onda1 as on
import overlay_iracing as o
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter

falhas, _ok = [], 0
def confere(c, msg):
    global _ok
    if c: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

N = on.N_PONTOS
def acum(trechos):
    t = [0.0]
    for d in trechos: t.append(t[-1] + d)
    return t

def alimentar(dt, tempos, total, pulos=(), parar_em=None, valido=True):
    """Uma volta a ~uma leitura por trecho; 'pulos' = indices sem leitura; fecha a volta cruzando a linha."""
    dt.atualizar(0.97, max(0.0, tempos[-1] - 1.0), True)
    for i in range(0, N + 1):
        if parar_em is not None and i > parar_em: break
        if i in pulos: continue
        dt.atualizar(min(0.999, (i + 0.01) / N), tempos[i], valido)       # (+0.01: evita int(pct*N) cair no trecho de baixo por arredondamento)
    dt.atualizar(0.001, 0.05, True, total)

def volta_aleatoria(rng, base=0.45, ruido=0.08):
    return [base + rng.random() * ruido for _ in range(N)]

# ---- 1) algoritmo: propriedades com voltas aleatorias ------------------------------------------------------------------
print("== algoritmo (propriedades, 30 sequencias aleatorias)")
rng = random.Random(2026); ok_soma = ok_teto = ok_delta = ok_mono = ok_ordem = True
for rodada in range(30):
    k = rng.randint(2, 7); voltas = [volta_aleatoria(rng) for _ in range(k)]
    dt = on.DeltaTrace(); anterior = None
    for v in voltas:
        t = acum(v); alimentar(dt, t, t[-1]); r = dt.resumo()
        if r["ideal_total"] is not None:
            if anterior is not None and r["ideal_total"] > anterior + 1e-9: ok_mono = False        # mais voltas nunca pioram o ideal
            anterior = r["ideal_total"]
    r = dt.resumo()
    minimos = [min(v[i] for v in voltas) for i in range(N)]
    if abs(r["ideal_total"] - sum(minimos)) > 1e-6: ok_soma = False
    if r["ideal_total"] > r["ref_total"] + 1e-9: ok_teto = False                                  # nunca acima da melhor volta real
    if any(d is not None and d > 1e-9 for d in r["ideal"]): ok_delta = False
    dt2 = on.DeltaTrace()
    for v in reversed(voltas):
        t = acum(v); alimentar(dt2, t, t[-1])
    # a ordem das voltas pode mudar a referencia vigente, nao o ideal
    if abs(dt2.resumo()["ideal_total"] - r["ideal_total"]) > 1e-6: ok_ordem = False
confere(ok_soma, "ideal = soma dos melhores trechos entre as voltas validas")
confere(ok_teto, "ideal nunca e maior que a melhor volta real (ref_total)")
confere(ok_delta, "a linha ideal nunca fica acima da referencia")
confere(ok_mono, "acrescentar voltas nunca piora o ideal")
confere(ok_ordem, "o ideal nao depende da ordem em que as voltas foram feitas")

# ---- 2) apos mudar a referencia ----------------------------------------------------------------------------------------
print("\n== troca de referencia")
a = [0.5] * N; b = [0.5] * N; c = [0.5] * N
for k in range(0, 60): a[k] = 0.44
for k in range(120, 180): b[k] = 0.43
c = [0.46] * N                                  # volta C: 92,0 s, mais rapida que A e B (vira a referencia)
dt = on.DeltaTrace()
for v in (a, b):
    t = acum(v); alimentar(dt, t, t[-1])
r1 = dt.resumo(); ref1 = r1["ref_total"]
t = acum(c); alimentar(dt, t, t[-1]); r2 = dt.resumo()
confere(r2["ref_total"] < ref1 and abs(r2["ref_total"] - sum(c)) < 1e-6, f"a volta mais rapida vira a referencia ({ref1:.3f} -> {r2['ref_total']:.3f})")
confere(abs(r2["ideal_total"] - sum(min(x, y, z) for x, y, z in zip(a, b, c))) < 1e-6, "o ideal combina os trechos das 3 voltas")
confere(r2["ideal_total"] <= r2["ref_total"] + 1e-9 and max(d for d in r2["ideal"] if d is not None) <= 1e-9, "o ideal continua <= nova referencia e a linha <= 0")
confere(abs(r2["ideal"][-1] - (r2["ideal_total"] - r2["ref_total"])) < 1e-6, "ultimo ponto da linha = ideal_total - ref_total (recalculado com a nova referencia)")
dt.resetar(); r0 = dt.resumo()
confere(r0["ideal"] is None and r0["ideal_total"] is None, "trocar de sessao/pista (resetar) apaga o ideal")

# ---- 3) voltas incompletas / invalidas / com buracos -------------------------------------------------------------------
print("\n== voltas incompletas, invalidas e com buracos")
def estado(dt): return (dt.voltas_validas, None if dt._seg_melhor is None else list(dt._seg_melhor))
base = [0.5] * N; tb = acum(base)
dt = on.DeltaTrace(); alimentar(dt, tb, tb[-1]); alimentar(dt, acum([0.51] * N), sum([0.51] * N)); ref_estado = estado(dt)
rapida = [0.40] * N; tr = acum(rapida)
dt_i = on.DeltaTrace(); alimentar(dt_i, tb, tb[-1]); alimentar(dt_i, acum([0.51] * N), sum([0.51] * N))
alimentar(dt_i, tr, tr[-1], parar_em=int(N * 0.6))                          # volta interrompida em 60 %
confere(estado(dt_i) == ref_estado and dt_i.resumo()["ideal_total"] == dt.resumo()["ideal_total"], "volta que parou em 60 % nao entra no ideal")
alimentar(dt_i, tr, tr[-1], valido=False)                                   # volta invalida (box, fora da pista, etc.)
confere(estado(dt_i) == ref_estado, "volta invalida nao entra no ideal")
dt_i.atualizar(0.5, 40.0, True); dt_i.atualizar(0.2, 10.0, True)           # voltou atras no meio da volta (reset/rewind)
alimentar(dt_i, tr, tr[-1], pulos=set(range(20, 60)))                       # 40 trechos sem leitura (> lacuna maxima): so ~80 % da volta
confere(estado(dt_i) == ref_estado, "volta com buraco grande (<95 % dos pontos) nao entra no ideal")
alimentar(dt_i, tr, tr[-1], pulos={7, 8, 9})                                # lacuna pequena: interpolada, a volta vale
confere(dt_i.voltas_validas == ref_estado[0] + 1 and dt_i.resumo()["ideal_total"] < dt.resumo()["ideal_total"], "lacuna pequena e interpolada e a volta vale")
# trecho sem medida nenhuma usa o da referencia: nunca inventa tempo
dt3 = on.DeltaTrace(); alimentar(dt3, tb, tb[-1]); v2 = [0.5] * N; t2 = acum(v2)
alimentar(dt3, t2, t2[-1], pulos={100, 101})
r3 = dt3.resumo()
confere(r3["ideal_total"] is not None and r3["ideal_total"] <= r3["ref_total"] + 1e-9, "trecho sem medida cai na referencia (nada inventado)")
dt1 = on.DeltaTrace(); alimentar(dt1, tb, tb[-1])
confere(dt1.resumo()["ideal"] is None, "com 1 volta valida nao existe ideal")

# ---- 4) a interface rotula como ESTIMATIVA -----------------------------------------------------------------------------
print("\n== rotulo na interface")
S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c_: None
cfg = o.carregar_config(); cfg["travado"] = True
textos = []
orig = QPainter.drawText
def espia(self, *a, **k):
    for x in a:
        if isinstance(x, str): textos.append(x)
    return orig(self, *a, **k)
QPainter.drawText = espia
j = o.JanelaDeltaTrace(dict(cfg)); d = o.Telemetria(demo=True).ler(); d["conectado"] = True
d["delta_trace"] = o.JanelaDeltaTrace._exemplo()
j.atualizar(d); j.grab()
QPainter.drawText = orig
rot = [t for t in textos if "azul" in t.lower() or "ideal" in t.lower()]
confere(bool(rot) and all("estimad" in t.lower() for t in rot), f"o texto da linha azul diz 'estimado': {rot}")
confere(not any(re.search(r"\\d+:\\d\\d", t) and "azul" in t.lower() for t in textos), "a interface nao mostra o tempo combinado como uma volta (so o ganho estimado)")
rotulos = [r for e, r in o.JanelaDeltaTrace.ELEMENTOS if e == "ideal"]
confere(rotulos and "estimad" in rotulos[0].lower(), f"o interruptor da Central diz 'estimado': {rotulos}")
print(f"\nRESULTADO: {len(falhas)} FALHA(S)" if falhas else f"\n{_ok} ok, 0 falha(s)")
sys.exit(1 if falhas else 0)
