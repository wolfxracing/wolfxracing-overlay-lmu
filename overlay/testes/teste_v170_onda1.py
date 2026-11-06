# -*- coding: utf-8 -*-
"""Onda 1 (build o): logica pura de Consumo por trecho (Fuel Flow + Burn Zones) e Delta Trace, com voltas sinteticas."""
import os, sys, math
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, PASTA)
import ov_onda1 as o1

falhas = []
def confere(c, msg):
    print(("OK    " if c else "FALHA ") + msg)
    if not c: falhas.append(msg)

HZ = 60.0
# perfil: litros por 100% da volta em cada ponto; trecho 0.50-0.625 (bins 12..14) gasta 3x
def dens(p, alto=True):
    return 3.0 if (alto and 0.50 <= p < 0.625) else 1.0
BASE_L = 2.0   # litros por volta se dens=1 em tudo (ajustado abaixo)

def simula(c, n_voltas, t0=0.0, nivel0=60.0, tempo_volta=90.0, pct0=0.0, alto=True, escala=1.0, pit_em=None, reabastece_em=None,
           ate_pct=None, passo_pct=None):
    """Roda n voltas a 60 Hz. Retorna (t, nivel, pct)."""
    t, nivel, pct = t0, nivel0, pct0
    norma = sum(dens(i / 1000.0, alto) for i in range(1000)) / 1000.0
    dpct = 1.0 / (tempo_volta * HZ)
    voltas_feitas = 0
    while voltas_feitas < n_voltas:
        gasto = (BASE_L * escala / norma) * dens(pct, alto) * dpct
        nivel -= gasto
        pct += dpct
        t += 1.0 / HZ
        valido = not (pit_em is not None and pit_em[0] <= pct < pit_em[1])
        if reabastece_em is not None and abs(pct - reabastece_em) < dpct / 2:
            nivel += 5.0
        if pct >= 1.0:
            pct -= 1.0
            voltas_feitas += 1
        c.atualizar(t, pct, nivel, valido)
        if ate_pct is not None and voltas_feitas == n_voltas - 1 and pct >= ate_pct:
            break
    return t, nivel, pct

print("== 1) Consumo: zonas de maior gasto")
c = o1.Consumo()
t, nv, pct = simula(c, 2)
r = c.resumo()
confere(r["estado"] in ("sem_dados", "medindo") and r["voltas"] <= 2, f"antes de {o1.MIN_VOLTAS_ZONAS} voltas: sem zonas (estado={r['estado']}, voltas={r['voltas']})")
t, nv, pct = simula(c, 4, t, nv, pct0=pct)
r = c.resumo()
confere(r["estado"] == "ok" and r["voltas"] >= 3, f"com voltas suficientes: zonas calculadas (voltas={r['voltas']})")
confere(abs(r["medio_lv"] - BASE_L) < 0.05, f"consumo medio por volta = {r['medio_lv']:.3f} L (esperado {BASE_L})")
z = r["zonas"]
altos = [i for i, x in enumerate(z) if x["nivel"] == "alta"]
confere(altos == [12, 13, 14], f"trechos de consumo alto identificados corretamente {altos}")
confere(all(x["nivel"] == "normal" for i, x in enumerate(z) if i not in altos), "demais trechos normais")
op = r["oportunidades"]
confere(len(op) == 1 and abs(op[0]["ini"] - 0.5) < 1e-9 and abs(op[0]["fim"] - 0.625) < 1e-9, f"uma oportunidade agrupada 50%-62,5% ({op})")
confere(abs(op[0]["parcela"] - 0.30) < 0.01, f"parcela do consumo da volta = 9/(21+9) = {op[0]['parcela']:.3f}")
confere(abs(sum(x["ratio"] for x in z) - o1.N_ZONAS) < 1e-6, "soma das razoes = numero de zonas")
confere(r["tendencia"] in (None, "estavel"), f"tendencia estavel com consumo constante ({r['tendencia']})")

print("== 2) Consumo: fluxo instantaneo (L/h)")
esperado = BASE_L * 3600.0 / 90.0                       # L/h medios
c2 = o1.Consumo()
simula(c2, 1, tempo_volta=90.0, alto=False)
ih = c2.resumo()["inst_lh"]
confere(ih is not None and abs(ih - esperado) < 0.05 * esperado, f"vazao instantanea {ih:.1f} L/h (esperado ~{esperado:.1f})")
c2b = o1.Consumo(); c2b.atualizar(0.0, 0.1, 50.0, True); c2b.atualizar(0.5, 0.101, 49.99, True)
confere(c2b.resumo()["inst_lh"] is None, "janela curta demais: sem vazao (evita ruido)")

print("== 3) Consumo: voltas invalidas nao entram")
c3 = o1.Consumo()
t, nv, pct = simula(c3, 4)
n0 = c3.resumo()["voltas"]
# volta com box
t, nv, pct = simula(c3, 1, t, nv, pct0=pct, pit_em=(0.3, 0.4))
confere(c3.resumo()["voltas"] == n0, "volta com passagem pelo box e descartada")
# volta com reabastecimento
t, nv, pct = simula(c3, 1, t, nv, pct0=pct, reabastece_em=0.7)
confere(c3.resumo()["voltas"] == n0, "volta com reabastecimento e descartada")
# a seguinte, limpa, entra
t, nv, pct = simula(c3, 2, t, nv, pct0=pct)
confere(c3.resumo()["voltas"] > n0, "a volta limpa seguinte volta a contar")
# volta que comecou no meio (sem cruzar a linha) nao conta
c3b = o1.Consumo()
simula(c3b, 1, pct0=0.5, ate_pct=None)
confere(c3b.resumo()["voltas"] == 0, "so conta volta que comecou ao cruzar a linha")
# salto de posicao (reboque/reset)
c3c = o1.Consumo(); t, nv, pct = simula(c3c, 3); a = c3c.resumo()["voltas"]
c3c.atualizar(t + 1, 0.2, nv, True); c3c.atualizar(t + 1.02, 0.6, nv, True)    # teleporte
confere(c3c.resumo()["voltas"] == a, "teleporte nao cria volta")
# entradas invalidas
for ent in ((None, 1.0), (0.5, None), (float("nan"), 3.0), (-1.0, 4.0), (1.5, 4.0)):
    try:
        c3c.atualizar(t + 2, ent[0], ent[1], True); ok = True
    except Exception:
        ok = False
    confere(ok, f"entrada invalida {ent} e ignorada sem erro")
c3c.resetar(); confere(c3c.resumo()["estado"] == "sem_dados", "resetar limpa tudo")

print("== 4) Consumo: tendencia e volta atual")
c4 = o1.Consumo()
t, nv, pct = simula(c4, 4, escala=1.0)
t, nv, pct = simula(c4, 3, t, nv, pct0=pct, escala=1.2)
confere(c4.resumo()["tendencia"] == "subindo", f"consumo 20% maior nas ultimas voltas: tendencia {c4.resumo()['tendencia']}")
c4b = o1.Consumo(); t, nv, pct = simula(c4b, 4, escala=1.0); t, nv, pct = simula(c4b, 3, t, nv, pct0=pct, escala=0.8)
confere(c4b.resumo()["tendencia"] == "caindo", f"20% menor: tendencia {c4b.resumo()['tendencia']}")
t, nv, pct = simula(c4, 1, t, nv, pct0=pct, ate_pct=0.5)
at = c4.resumo()["atual"]
confere(at is not None and sum(1 for a in at if a is not None) >= 10 and sum(1 for a in at if a is not None) < o1.N_ZONAS,
        "a volta em andamento aparece parcialmente preenchida")

print("== 5) Delta Trace")
def volta_dt(d, n, tempo, perfil=lambda p: 1.0, p0=0.0, valido=True):
    """Uma volta com tempo total `tempo`; perfil(p) escala a velocidade local (muda a distribuicao do tempo)."""
    # tempo acumulado por pct: integra 1/perfil
    passos = int(tempo * HZ)
    soma = sum(1.0 / perfil(i / passos) for i in range(passos))
    t_acum, pct = 0.0, 0.0
    for i in range(passos):
        t_acum += (tempo / soma) / perfil(i / passos) * 1.0
        pct = (i + 1) / passos
        d.atualizar(pct if pct < 1.0 else 0.999999, t_acum, valido)
    return t_acum
d = o1.DeltaTrace()
def roda(d, tempo, perfil=lambda p: 1.0, valido=True, entrada=True):
    # cruza a linha para iniciar a volta
    d.atualizar(0.995, tempo - 0.1, valido)
    d.atualizar(0.002, 0.1, valido, ultima_volta=None)
    passos = int(tempo * HZ)
    soma = sum(1.0 / perfil(i / passos) for i in range(passos))
    acum = 0.0
    for i in range(passos):
        acum += (tempo / soma) / perfil(i / passos)
        pct = (i + 1) / passos
        if pct > 0.997: break
        d.atualizar(pct, acum, valido)
    return acum
confere(d.resumo()["estado"] == "sem_ref", "sem volta anterior: sem referencia")
roda(d, 90.0)
roda(d, 91.0)                      # fecha a volta de 90 s -> referencia
d.atualizar(0.995, 90.9, True); d.atualizar(0.002, 0.1, True, ultima_volta=90.9)
r = d.resumo()
confere(r["estado"] == "ok" and abs(r["ref_total"] - 90.0) < 0.6, f"melhor volta limpa vira referencia ({r['estado']}, ref={r['ref_total']})")
confere(r["voltas"] >= 1, f"voltas validas contadas ({r['voltas']})")
roda(d, 92.0)
r = d.resumo()
confere(r["atual"] is not None and r["atual"] > 0, f"volta mais lenta: delta positivo no fim ({r['atual']:.2f} s)")
confere(r["pior"] >= r["atual"] - 1e-9 and r["melhor"] <= r["pior"], "pior >= atual e melhor <= pior")
# volta mais rapida: delta negativo e vira nova referencia
d2 = o1.DeltaTrace()
roda(d2, 92.0); roda(d2, 90.0); roda(d2, 95.0)
r2 = d2.resumo()
confere(r2["ref_total"] is not None and r2["ref_total"] < 91.0, f"a volta mais rapida passa a ser a referencia ({r2['ref_total']})")
# perfil: perde tempo no inicio, recupera no fim
d3 = o1.DeltaTrace()
roda(d3, 90.0); roda(d3, 90.0, perfil=lambda p: 0.7 if p < 0.3 else 1.3)
r3 = d3.resumo(); pts = [x for x in r3["pontos"] if x is not None]
confere(r3["melhor"] is not None and (r3["pior"] > 1.0 or r3["melhor"] < -1.0), f"o traco acompanha onde se ganha/perde (pior={r3['pior']:.2f}, melhor={r3['melhor']:.2f})")
# volta invalida (box) nao vira referencia
d4 = o1.DeltaTrace(); roda(d4, 85.0, valido=False); roda(d4, 90.0, valido=False)
confere(d4.resumo()["estado"] == "sem_ref", "voltas invalidas (box) nao viram referencia")
# entradas invalidas e reset
for ent in ((None, 1.0), (0.5, None), (float("nan"), 3.0), (-1.0, 4.0), (1.5, 4.0), (0.5, -2.0)):
    try:
        d3.atualizar(ent[0], ent[1], True); ok = True
    except Exception:
        ok = False
    confere(ok, f"delta trace: entrada invalida {ent} ignorada")
d3.resetar(); confere(d3.resumo()["estado"] == "sem_ref" and d3.resumo()["voltas"] == 0, "resetar limpa a referencia")
# salto de posicao invalida a volta
d5 = o1.DeltaTrace(); roda(d5, 90.0); d5.atualizar(0.2, 20.0, True); d5.atualizar(0.7, 21.0, True)
confere(d5._ok is False, "teleporte invalida a volta em andamento")


# ===================================================================================================================
# Partes com Qt: caminho real (Telemetria.ler com SDK falso), janelas e Central
os.environ["QT_QPA_PLATFORM"] = "offscreen"
_argv0 = sys.argv
sys.argv = ["x", "--demo"]
import tempfile
from pathlib import Path
import overlay_iracing as o
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu
S = Path(tempfile.mkdtemp(prefix="overlay_testes_onda1_")); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
for nome in ("ARQ_PENDENTE", "ARQ_COMPARACAO", "ARQ_HISTORICO", "ARQ_RECORDES", "ARQ_PNEUS", "ARQ_MAPAS"):
    setattr(o, nome, S / (nome.lower() + ".tmp"))
app = QApplication([]); o.salvar_config = lambda c_: None

print("== 6) Configuracao e registro das janelas novas")
cfg = o.carregar_config(); cfg["travado"] = True
for chave in ("x_consumo", "y_consumo", "mostrar_consumo", "escala_consumo", "escala_x_consumo", "escala_y_consumo",
              "x_delta_trace", "mostrar_delta_trace", "escala_delta_trace"):
    confere(chave in cfg, f"config tem '{chave}'")
confere(not any("ponto_cego" in k for k in cfg) and not hasattr(o, "JanelaPontoCego"), "build q: o Ponto cego foi removido (o Radar ja cobre o carro ao lado)")
confere({"x_consumo", "y_consumo", "mostrar_consumo", "escala_consumo"} <= set(o.nucleo.chaves_de_layout(cfg)), "as chaves de layout das janelas novas entram nos perfis")

print("== 7) Caminho real: Telemetria.ler() alimenta consumo e delta trace")
class IRFalso:
    is_initialized = True; is_connected = True
    def __init__(self, vv): self.v = vv
    def __getitem__(self, k): return self.v.get(k)
    def startup(self): return True
    def freeze_var_buffer_latest(self): pass
    def unfreeze_var_buffer_latest(self): pass
    def shutdown(self): pass
N = 3
drivers = [{"CarIdx": k, "UserName": f"Piloto {k}", "CarNumber": str(k), "CarClassID": 1, "CarClassShortName": "GT3",
            "CarClassColor": 0xffda59, "IRating": 2000, "LicString": "A 3.20", "LicColor": 0x0153db,
            "CarScreenName": "Porsche 911 GT3 R", "CarPath": "porsche992rgt3", "CarIsPaceCar": 0, "IsSpectator": 0,
            "UserID": 500 + k} for k in range(N)]
sdk = {"PlayerCarIdx": 0, "Speed": 55.0, "Gear": 4, "RPM": 6000.0, "Lap": 1, "LapCompleted": 0, "LapDistPct": 0.0,
       "LapCurrentLapTime": 0.0, "LapLastLapTime": -1.0, "FuelLevel": 60.0, "OnPitRoad": False, "IsOnTrack": True, "SessionNum": 0,
       "SessionUniqueID": 1, "SessionState": 4, "Throttle": 1.0, "Brake": 0.0, "Clutch": 1.0, "ThrottleRaw": 1.0, "BrakeRaw": 0.0,
       "ClutchRaw": 1.0, "BrakeABSactive": False, "SteeringWheelAngle": 0.0, "EngineWarnings": 0, "PlayerTrackSurface": 3,
       "CarIdxLapDistPct": [0.0, 0.5, 0.7], "CarIdxTrackSurface": [3] * N, "CarIdxOnPitRoad": [False] * N,
       "CarIdxClassPosition": [1, 2, 3], "CarIdxLapCompleted": [0] * N, "CarIdxLap": [1] * N, "CarIdxTireCompound": [0] * N,
       "CarIdxLastLapTime": [0.0] * N, "CarLeftRight": 1, "LatAccel": 0.0, "LongAccel": 0.0, "TrackTemp": 25.0, "TrackWetness": 1,
       "Precipitation": 0.0, "PitSvFlags": 0, "PitSvTireCompound": 0, "IsReplayPlaying": False,
       "DriverInfo": {"Drivers": drivers, "DriverTires": [{"TireIndex": 0, "TireCompoundType": "Dry"}]},
       "WeekendInfo": {"TrackDisplayName": "Pista Simulada", "TrackLength": "5.00 km", "Official": 1, "SubSessionID": 1, "Category": "Road"},
       "SessionInfo": {"Sessions": [{"SessionType": "Race"}]}}
tel = o.Telemetria(demo=False); tel.conectado = True; tel.ir = IRFalso(sdk)
relogio = [1000.0]; real_mono = o.time.monotonic; o.time.monotonic = lambda: relogio[0]
TEMPO = 90.0
def volta_real(tempo=TEMPO, consumo=2.4, **extra):
    """Uma volta completa pelo Telemetria.ler(); retorna os dados do ultimo ciclo."""
    pct, dd = 0.0, None
    dpct = 1.0 / (tempo * 30.0)
    norma = sum(dens(k / 1000.0) for k in range(1000)) / 1000.0
    sdk.update(extra)
    t_volta = 0.0
    while pct < 1.0:
        sdk["FuelLevel"] -= consumo / norma * dens(pct) * dpct
        sdk["LapDistPct"] = pct
        sdk["CarIdxLapDistPct"] = [pct, 0.5, 0.7]
        sdk["LapCurrentLapTime"] = t_volta
        relogio[0] += 1.0 / 30.0
        t_volta += 1.0 / 30.0
        dd = tel.ler()
        pct += dpct
    return dd, t_volta
def cruzar(ult):
    sdk["LapDistPct"] = 0.003; sdk["CarIdxLapDistPct"] = [0.003, 0.5, 0.7]; sdk["LapCurrentLapTime"] = 0.1
    sdk["LapLastLapTime"] = ult; sdk["LapCompleted"] = sdk["LapCompleted"] + 1; sdk["Lap"] = sdk["Lap"] + 1
    relogio[0] += 0.03
    return tel.ler()
try:
    for _ in range(5):
        dd, tv = volta_real(); dd = cruzar(tv)
    c, dt = dd["consumo"], dd["delta_trace"]
    confere(c is not None and c["estado"] == "ok" and c["voltas"] >= 3, f"consumo: zonas calculadas pelo caminho real (estado={c and c['estado']}, voltas={c and c['voltas']})")
    confere(abs(c["medio_lv"] - 2.4) < 0.1, f"consumo medio por volta ~2,4 L ({c['medio_lv']:.2f})")
    altos = [k for k, z in enumerate(c["zonas"]) if z["nivel"] == "alta"]
    confere(altos == [12, 13, 14], f"trechos de maior consumo identificados {altos}")
    confere(dt is not None and dt["estado"] == "ok" and dt["voltas"] >= 3, f"delta trace: referencia criada (voltas={dt and dt['voltas']})")
    confere("curvas" in dt and isinstance(dt["curvas"], list) and dt.get("ref_tempos") and len(dt["ref_tempos"]) == 201, "delta trace: entrega curvas e tempos da referencia (blocos por curva, build q)")
    confere(abs(dt["ref_total"] - TEMPO) < 1.0, f"referencia ~90 s ({dt['ref_total']})")
    # volta com box nao entra
    n_antes = tel.vo_consumo.resumo()["voltas"]; d_antes = tel.vo_delta.voltas_validas
    dd, tv = volta_real(OnPitRoad=True); dd = cruzar(tv); sdk["OnPitRoad"] = False
    dd, tv = volta_real(); dd = cruzar(tv)                                  # a volta imediatamente apos o box tambem comeca no box
    n_dep = tel.vo_consumo.resumo()["voltas"]
    confere(n_dep <= n_antes + 1, f"volta com box nao entra no consumo ({n_antes} -> {n_dep})")
    confere(tel.vo_delta.voltas_validas <= d_antes + 1, "volta com box nao entra no delta trace")
    # replay nao alimenta
    sdk["IsReplayPlaying"] = True
    ant = tel.vo_consumo.resumo()["voltas"]
    dd, tv = volta_real(); dd = cruzar(tv)
    confere(tel.vo_consumo.resumo()["voltas"] == ant, "replay nao alimenta o consumo")
    sdk["IsReplayPlaying"] = False
    # nova sessao zera
    sdk["SessionUniqueID"] = 2; relogio[0] += 1.0
    dd = tel.ler()
    confere(dd["consumo"]["estado"] == "sem_dados" and dd["delta_trace"]["estado"] == "sem_ref", "sessao nova zera consumo e delta trace")
    # SDK sem combustivel nao derruba o ciclo
    sdk["FuelLevel"] = None
    try:
        dd = tel.ler(); ok = dd is not None
    except Exception:
        ok = False
    confere(ok, "FuelLevel ausente: o ciclo continua")
finally:
    o.time.monotonic = real_mono

print("== 8) Janelas: desenho, exemplo destravado, estados")
from PySide6.QtGui import QImage
demo = o.Telemetria(demo=True)
def img(w): return w.grab().toImage()
for Cls in (o.JanelaConsumo, o.JanelaDeltaTrace):
    cfgw = dict(cfg); cfgw["travado"] = True
    w = Cls(cfgw)
    d0 = demo.ler(); d0["consumo"] = None; d0["delta_trace"] = None; d0["radar"] = None; d0["conectado"] = True
    w.atualizar(d0); app.processEvents()
    vazio = img(w)
    confere(not vazio.isNull(), f"{Cls.__name__}: desenha sem dados")
    cfgw["travado"] = False
    w2 = Cls(cfgw); w2.atualizar(d0); app.processEvents()
    confere(img(w2) != vazio, f"{Cls.__name__}: destravada mostra o exemplo para posicionar")
    confere(w.size().width() == Cls.LARG and w.size().height() == Cls.ALT, f"{Cls.__name__}: tamanho {Cls.LARG}x{Cls.ALT}")
# Consumo: mapeando x pronto
cfgw = dict(cfg); cfgw["travado"] = True
w = o.JanelaConsumo(cfgw)
d1 = demo.ler(); d1["conectado"] = True
d1["consumo"] = {"estado": "medindo", "voltas": 2, "minimo": 3, "inst_lh": 50.0, "medio_lv": 2.0, "ultima_lv": 2.0, "tendencia": None, "zonas": None, "atual": None, "oportunidades": [], "n_zonas": 24}
w.atualizar(d1); app.processEvents(); img_med = img(w)
d1["consumo"] = o.JanelaConsumo._exemplo(); w.atualizar(d1); app.processEvents(); img_ok = img(w)
confere(img_med != img_ok, "Consumo: 'mapeando' e 'pronto' desenham diferente")
d1["consumo"]["oportunidades"] = []; w.atualizar(d1); app.processEvents()
confere(img(w) != img_ok, "Consumo: sem oportunidades mostra a mensagem de consumo uniforme")
for tend in ("subindo", "caindo", "estavel", None):
    d1["consumo"] = o.JanelaConsumo._exemplo(); d1["consumo"]["tendencia"] = tend; w.atualizar(d1); app.processEvents(); img(w)
confere(not img(w).isNull(), "Consumo: todas as tendencias desenham")
# valores None nao quebram
d1["consumo"] = {"estado": "ok", "voltas": 3, "minimo": 3, "inst_lh": None, "medio_lv": None, "ultima_lv": None, "tendencia": None,
                 "zonas": [{"ratio": 1.0, "nivel": "normal", "litros": 0.0}] * 24, "atual": [None] * 24, "oportunidades": [], "n_zonas": 24}
w.atualizar(d1); app.processEvents()
confere(not img(w).isNull(), "Consumo: valores ausentes (None) nao quebram o desenho")
# Delta trace: referencia certa
wd = o.JanelaDeltaTrace(cfgw); d2 = demo.ler(); d2["conectado"] = True
d2["delta_trace"] = o.JanelaDeltaTrace._exemplo(); wd.atualizar(d2); app.processEvents(); i1 = img(wd)
d2["delta_trace"]["pontos"] = [0.0 if k < 50 else None for k in range(201)]; d2["delta_trace"]["atual"] = 0.0; wd.atualizar(d2); app.processEvents()
confere(img(wd) != i1, "Delta Trace: o grafico muda com os pontos")
d2["delta_trace"] = {"estado": "ok", "n": 200, "pontos": [None] * 201, "anterior": None, "ref_total": None, "atual": None, "voltas": 1, "melhor": None, "pior": None}
wd.atualizar(d2); app.processEvents()
confere(not img(wd).isNull(), "Delta Trace: sem pontos nem referencia nao quebra")
confere(o.JanelaDeltaTrace._escala([0.1, -0.2]) == 0.25 and o.JanelaDeltaTrace._escala([3.0]) == 5.0 and o.JanelaDeltaTrace._escala([]) == 0.25 and o.JanelaDeltaTrace._escala([99.0]) == 10.0, "Delta Trace: escala do eixo automatica")
# build q: painel da curva (numero + desenho da pista) do Delta Trace
wq = o.JanelaDeltaTrace(cfgw)
dq = demo.ler(); dq["conectado"] = True; dq["delta_trace"] = o.JanelaDeltaTrace._exemplo()
dq["mapa"] = {"pontos": o._tracado_demo(), "completo": True, "versao": 1}
wq.atualizar(dq); app.processEvents(); com_pista = img(wq)
def _cores_painel(im):
    verde = vermelho = 0
    for yy in range(66, im.height() - 10, 2):
        for xx in range(Cls_x0 := o.JanelaDeltaTrace.LARG_GRAF + 10, im.width() - 6, 2):
            c_ = im.pixelColor(xx, yy)
            if c_.green() > 150 and c_.red() < 110 and c_.blue() < 130: verde += 1
            if c_.red() > 190 and c_.green() < 90 and c_.blue() < 90: vermelho += 1
    return verde, vermelho
vv, vm = _cores_painel(com_pista)
confere(vv > 5 and vm > 5, f"Delta Trace: tracado do mapa colorido em verde ({vv}) e vermelho ({vm}) conforme o ritmo")
dq2 = dict(dq); dq2["mapa"] = None; wq.atualizar(dq2); app.processEvents(); sem_pista = img(wq)
confere(com_pista != sem_pista, "Delta Trace: o desenho da pista aparece quando o Mapa ja aprendeu o tracado")
dq3 = dict(dq); dq3["delta_trace"] = dict(dq["delta_trace"]); dq3["delta_trace"]["curvas"] = []
wq.atualizar(dq3); app.processEvents()
confere(not img(wq).isNull(), "Delta Trace: sem curvas mapeadas nao quebra (so o grafico)")
dq4 = dict(dq); dq4["mapa"] = {"pontos": [None] * 360, "completo": False, "versao": 2}
wq.atualizar(dq4); app.processEvents()
confere(not img(wq).isNull(), "Delta Trace: mapa vazio nao quebra")
dq5 = dict(dq); dq5["mapa"] = {"pontos": [(1.0, 1.0), None, (2.0, 3.0)] * 10, "completo": False, "versao": 3}
wq.atualizar(dq5); app.processEvents()
confere(not img(wq).isNull(), "Delta Trace: mapa com buracos (None) nao quebra")
# build r: blocos de curva dentro da faixa (P1), curva circular (P2) e layout estilo RaceLab
wr_ = o.JanelaDeltaTrace(cfgw)
def _dados_com_zonas(zonas):
    dd_ = dict(dq); dd_["delta_trace"] = o.JanelaDeltaTrace._exemplo(); dd_["delta_trace"]["curvas"] = zonas
    return dd_
lim_dir = o.JanelaDeltaTrace.LARG_GRAF - 14.0
for ncv in (5, 10, 15, 20, 25, 30):
    zs = [{"n": k + 1, "ini": 0.02 + k * 0.97 / ncv, "fim": 0.02 + k * 0.97 / ncv + 0.6 * 0.97 / ncv} for k in range(ncv)]
    wr_.atualizar(_dados_com_zonas(zs)); app.processEvents(); img(wr_)
    lay = wr_.ultimo_layout_blocos
    ok_ = len(lay) == ncv and all(x >= 14.0 - 1e-6 and x + w <= lim_dir + 1e-6 for _, x, w in lay) and all(lay[i][1] + lay[i][2] <= lay[i + 1][1] + 1e-6 for i in range(len(lay) - 1))
    confere(ok_, f"Delta Trace com {ncv} curvas: blocos dentro da faixa do grafico (nao invadem o painel do mapa) e sem sobreposicao")
zs = [{"n": k + 1, "ini": 0.80 + k * 0.01, "fim": 0.80 + k * 0.01 + 0.008} for k in range(20)]       # 20 curvas coladas no fim da volta
wr_.atualizar(_dados_com_zonas(zs)); app.processEvents(); img(wr_)
confere(max(x + w for _, x, w in wr_.ultimo_layout_blocos) <= lim_dir + 1e-6, "20 curvas coladas no fim: nenhum bloco passa do limite direito")
zs = [{"n": 1, "ini": 0.15, "fim": 0.20}, {"n": 2, "ini": 0.96, "fim": 0.03}]
wr_.atualizar(_dados_com_zonas(zs)); app.processEvents(); img_circ = img(wr_)
confere(len(wr_.ultimo_layout_blocos) == 2 and not img_circ.isNull(), "curva circular sobre a linha de chegada: um bloco so, sem erro (sem duplicar)")
dcirc = _dados_com_zonas(zs); dcirc["delta_trace"]["pontos"] = [0.0] * 5 + [None] * 190 + [0.01] * 6      # carro logo depois da linha: dentro da curva circular
wr_.atualizar(dcirc); app.processEvents()
confere(not img(wr_).isNull(), "carro dentro da curva circular (depois da linha): painel da curva desenha")
# layout estilo RaceLab
cfg_r = dict(cfgw); cfg_r["delta_trace_layout"] = "racelab"
wl = o.JanelaDeltaTrace(cfg_r); wl.atualizar(dq); app.processEvents(); img_rl = img(wl)
wg = o.JanelaDeltaTrace(cfgw); wg.atualizar(dq); app.processEvents(); img_gr = img(wg)
confere(wl.layout_atual() == "racelab" and wg.layout_atual() == "grafico" and img_rl != img_gr, "layout estilo RaceLab desenha diferente do grafico")
cfg_x = dict(cfgw); cfg_x["delta_trace_layout"] = "qualquer"
confere(o.JanelaDeltaTrace(cfg_x).layout_atual() == "grafico", "valor invalido de layout cai no grafico")
vv2, vm2 = _cores_painel(img_rl)
confere(vv2 > 5 and vm2 > 5, "RaceLab: mapa com cor de ritmo e blocos por curva continuam")
dsem = dict(dq); dsem["delta_trace"] = dict(dq["delta_trace"]); dsem["delta_trace"]["atual"] = None
wl.atualizar(dsem); app.processEvents()
confere(not img(wl).isNull(), "RaceLab sem delta atual nao quebra")
for val in (-3.0, 0.0, 0.4, 25.0):
    dv = dict(dq); dv["delta_trace"] = dict(dq["delta_trace"]); dv["delta_trace"]["atual"] = val; wl.atualizar(dv); app.processEvents(); img(wl)
confere(True, "RaceLab com delta extremo (-3, 0, 0,4, 25 s) desenha")
# build r: elementos do Delta Trace liga/desliga (mesmo esquema da Classificacao)
import itertools
def _wdt(**el):
    c_ = dict(cfgw); c_["delta_trace_elementos"] = {k: False for k, v in el.items() if not v}
    w_ = o.JanelaDeltaTrace(c_); w_.atualizar(dq); app.processEvents(); return w_
w0 = _wdt()
confere((w0.width(), w0.height()) == (710, 200), f"todos os elementos ligados: 710x200 como antes ({w0.width()}x{w0.height()})")
base_i = img(w0)
for eid, rot in o.JanelaDeltaTrace.ELEMENTOS:
    w_ = _wdt(**{eid: False}); im_ = img(w_)
    confere(not im_.isNull() and (im_ != base_i or w_.size() != w0.size()), f"Delta Trace: desligar '{eid}' muda o painel")
confere(_wdt(blocos=False).height() < 200 and _wdt(curva=False, mapa=False).width() == o.JanelaDeltaTrace.LARG_GRAF, "sem blocos a janela fica mais baixa; sem numero e mapa fica mais estreita")
wt = _wdt(titulo=False, delta=False, grafico=False, anterior=False, ideal=False, blocos=False, curva=False, mapa=False)
confere(wt.width() > 0 and wt.height() >= 70 and not img(wt).isNull(), "todos os elementos desligados: nao quebra e mantem tamanho minimo")
algum = True
for combo in itertools.product((True, False), repeat=len(o.JanelaDeltaTrace.ELEMENTOS)):
    w_ = _wdt(**dict(zip([e for e, _ in o.JanelaDeltaTrace.ELEMENTOS], combo)))
    if img(w_).isNull() or w_.height() < 70 or w_.width() < 400: algum = False
confere(algum, "256 combinacoes de elementos: todas desenham com tamanho valido")
cfg_rl = dict(cfgw); cfg_rl["delta_trace_layout"] = "racelab"; cfg_rl["delta_trace_elementos"] = {"grafico": False}
wrl = o.JanelaDeltaTrace(cfg_rl); wrl.atualizar(dq); app.processEvents()
confere(not img(wrl).isNull() and wrl.height() >= 150, "RaceLab sem a barra: numero grande continua")
cfg_bad = dict(cfgw); cfg_bad["delta_trace_elementos"] = "lixo"
confere(o.JanelaDeltaTrace(cfg_bad).visivel("blocos") is True, "config invalida de elementos: tudo visivel")
# build p: rotulo neutro do Burn Zones e grafico atual/anterior do Delta Trace depois de uma nova melhor volta
import inspect
fonte_c = inspect.getsource(o.JanelaConsumo)
confere("TRECHOS DE MAIOR CONSUMO" in fonte_c and "nao e economia" in fonte_c, "Consumo: rotulo 'trechos de maior consumo' sem sugerir economia")
confere("economize" not in fonte_c.lower() and "oportunidade" not in fonte_c.lower().replace("oportunidades' (interno)", "").replace("\"oportunidades\"", "").replace("oportunidades", ""), "Consumo: nenhum texto de 'oportunidade'/'economize' na janela")
dt = o.ons1.DeltaTrace()
def _volta(total):
    dt.atualizar(0.95, 5.0, True); dt.atualizar(0.02, 0.0, True)
    for i in range(1, 200):
        dt.atualizar(i / 200.0 + 0.0001, total * i / 200.0, True)
    dt.atualizar(0.01, 0.5, True, total)
_volta(100.0); _volta(90.0)
for k in range(1, 61):
    dt.atualizar(k / 200.0 + 0.0001, 90.0 * k / 200.0 + 0.2, True)
dd = demo.ler(); dd["conectado"] = True; dd["delta_trace"] = dt.resumo()
wdt = o.JanelaDeltaTrace(cfgw); wdt.atualizar(dd); app.processEvents()
anterior_ok = [x for x in dd["delta_trace"]["anterior"] if x is not None]
confere(max(abs(x) for x in anterior_ok) < 1e-6, "Delta Trace: grafico anterior (nova melhor volta) fica em zero contra a nova referencia")
confere(abs(dd["delta_trace"]["atual"] - 0.2) < 0.01, "Delta Trace: grafico atual mede contra a referencia vigente (+0,2 s)")
confere(not img(wdt).isNull(), "Delta Trace: janela desenha atual + anterior depois da troca de referencia")

print("== 9) Central: paineis novos com titulo, categoria e previa")
import ov_central as c_
for chave, cat in (("consumo", "Carro"), ("delta_trace", "Pilotagem")):
    confere(chave in c_.PAINEIS and c_.PAINEIS[chave][2] == cat, f"Central lista '{chave}' em '{cat}'")
confere("ponto_cego" not in c_.PAINEIS, "Central nao lista mais o Ponto cego")
cfgc = dict(cfg); cfgc["travado"] = True
Foto = None
janelas = [o.JanelaConsumo(cfgc), o.JanelaDeltaTrace(cfgc), o.JanelaTelemetria(cfgc)]
menu = QMenu(); acoes = {}
for jj in janelas:
    a = QAction(jj.CHAVE_ATIVO, menu); a.setCheckable(True); a.setChecked(True); acoes[jj.CHAVE_ATIVO] = a
def previa(jj):
    c2 = dict(cfgc); c2[jj.CHAVE_ATIVO] = False; c2["travado"] = True; return type(jj)(c2)
cen = c_.Central(janelas, acoes, cfgc, {"salvar": lambda: None}, demo.ler, previa, "iRacing", "1.7.0 (build r)")
cen.resize(1180, 820); cen.mostrar(); app.processEvents()
for chave in ("consumo", "delta_trace"):
    cen.abrir_detalhe(chave); cen._ciclo(forcar=True); app.processEvents()
    confere(cen.det_previa._pix is not None and not cen.det_previa._pix.isNull(), f"Central: a previa de '{chave}' desenha")

print()
print("RESULTADO:", "OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
