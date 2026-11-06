# -*- coding: utf-8 -*-
"""Build v (auditoria da build u): o CICLO REAL do iRacing, Telemetria.ler() -> _ler_real(), com um pyirsdk falso (variaveis e YAML da
sessao), tem de alimentar o Coach, fechar voltas e gravar a referencia. Diferente do teste_v170_coach_real.py (que chama so
_alimentar_coach), aqui passa por toda a cadeia de montagem de dados, na ordem real."""
import math, os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import overlay_iracing as ov

S = Path(tempfile.mkdtemp()); ov.ARQ_LOG = S / "l.txt"
falhas, _ok = [], 0
def confere(c, msg):
    global _ok
    if c: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

COMP, VOLTA_S, HZ = 2300.0, 60.0, 20.0

class FakeIR:
    """Imita o minimo do pyirsdk: is_initialized/is_connected/startup/freeze e ir[nome] (variavel ou YAML da sessao)."""
    is_initialized = True; is_connected = True
    def __init__(self): self.v = {}
    def startup(self): return True
    def shutdown(self): pass
    def freeze_var_buffer_latest(self): pass
    def unfreeze_var_buffer_latest(self): pass
    def __getitem__(self, k): return self.v.get(k)

def sessao(ir):
    ir.v.update({
        "WeekendInfo": {"TrackLength": "2.30 km", "TrackDisplayName": "Pista de Teste", "TrackNumTurns": 6, "Official": 0,
                        "WeekendOptions": {"IncidentLimit": "unlimited"}},
        "DriverInfo": {"DriverCarIdx": 0, "Drivers": [{"CarIdx": 0, "UserName": "Piloto", "CarNumber": "7", "CarClassID": 1,
                       "CarClassShortName": "GT3", "CarScreenName": "Carro de Teste", "CarID": 99, "IRating": 2000}]},
        "SessionInfo": {"Sessions": [{"SessionNum": 0, "SessionType": "Practice"}]},
        "PlayerCarIdx": 0, "SessionNum": 0, "SessionUniqueID": 1, "IsOnTrack": True, "IsInGarage": False, "IsReplayPlaying": False,
        "OnPitRoad": False, "PlayerTrackSurface": 3, "FuelLevel": 50.0, "Gear": 3, "RPM": 6000.0, "Throttle": 0.8, "Brake": 0.0, "Clutch": 1.0,
        "SteeringWheelAngle": 0.0, "LapBestLapTime": -1.0, "LapLastLapTime": -1.0, "LapCurrentLapTime": 0.01, "LapDistPct": 0.0, "Lap": 1,
        "LapCompleted": 0, "Speed": 40.0})

def rodar_volta(ir, tele, numero, ultima, box_apos=None, ticks=None):
    n = int(VOLTA_S * HZ); d = None
    for k in range(ticks or n):
        if box_apos is not None: ir.v["OnPitRoad"] = k >= box_apos
        pct = k / n; t = k / HZ
        vel = 40.0 + 25.0 * math.sin(pct * 2 * math.pi * 3)
        ir.v.update({"LapDistPct": pct, "LapCurrentLapTime": max(t, 0.01), "LapLastLapTime": ultima, "Lap": numero, "LapCompleted": numero - 1,
                     "Speed": vel, "Brake": 1.0 if 0.2 < pct < 0.23 else 0.0, "Throttle": 0.8})
        d = tele.ler()
    return d

with __import__("tempfile").TemporaryDirectory() as tmp:
    ov.Telemetria.__init__.__globals__["ARQ_MAPAS"] = Path(tmp) / "mapas.json"
    tele = ov.Telemetria(demo=False)
    tele.ir = FakeIR(); sessao(tele.ir)
    tele.config_coach_modo = "auto"
    tele.v17_coach = ov.coach_mod.Coach(ov.coach_mod.BibliotecaReferencias(Path(tmp) / "referencias"))
    d = rodar_volta(tele.ir, tele, 1, -1.0)
    confere(d["conectado"] and d["no_carro"], "ciclo real: conectado e no carro")
    confere(tele._comprimento == COMP and tele._nome_pista == "Pista de Teste", f"pista lida da sessao (comprimento {tele._comprimento}, {tele._nome_pista!r})")
    confere(d["coach"] is not None and d["coach"].get("estado") != "ok", f"1a volta: o Coach recebe dados mas ainda sem referencia (estado={d['coach'] and d['coach'].get('estado')})")
    d = rodar_volta(tele.ir, tele, 2, VOLTA_S)
    c = tele.v17_coach
    confere(c.voltas_gravadas >= 1, f"o Coach fechou volta pelo ciclo real (gravadas={c.voltas_gravadas})")
    confere(c.ref_propria is not None, "referencia propria registrada pelo ciclo real")
    d = rodar_volta(tele.ir, tele, 3, VOLTA_S)
    confere(d["coach"] is not None and d["coach"].get("estado") == "ok", f"3a volta: estado 'ok' (estado={d['coach'] and d['coach'].get('estado')})")
    confere(d["coach"].get("proxima") is not None, "o Coach ja informa a proxima freada")
    confere(c.descarregar(5.0) and c.estatisticas_gravacao()["gravacoes"] >= 1, "referencia gravada em disco")
    # volta suja (box): nao vira referencia e o ciclo segue
    rodar_volta(tele.ir, tele, 4, VOLTA_S, box_apos=600)           # entra no box no meio da volta 4
    antes = c.voltas_gravadas
    rodar_volta(tele.ir, tele, 5, VOLTA_S, ticks=3)                # cruza a linha: fecha a volta 4 (suja)
    confere(c.voltas_gravadas == antes, f"volta com box nao e gravada ({antes} -> {c.voltas_gravadas})")
    tele.encerrar()
print(f"\nRESULTADO: {len(falhas)} FALHA(S)" if falhas else f"\n{_ok} ok, 0 falha(s)")
sys.exit(1 if falhas else 0)
