# -*- coding: utf-8 -*-
"""v1.6.0 - classificacao com SR/iR, ultimo contato, entrada do pit."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import overlay_iracing as o
import ov_v16 as v
from PySide6.QtWidgets import QApplication

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"; o.ARQ_PIT = S / "pit.json"
for nome in ("ARQ_PENDENTE", "ARQ_COMPARACAO", "ARQ_HISTORICO", "ARQ_RECORDES", "ARQ_PNEUS", "ARQ_MAPAS"):
    setattr(o, nome, S / (nome.lower() + ".tmp"))
app = QApplication([]); o.salvar_config = lambda c: None
falhas = []
def confere(c, msg):
    print(("OK    " if c else "FALHA ") + msg)
    if not c: falhas.append(msg)

# ---- classificacao com SR e iR
cfg = o.carregar_config(); cfg["travado"] = True
d = o.Telemetria(demo=True).ler()
linha = d["classificacao"]["classes"][0]["linhas"][0]
confere(linha.get("lic") and linha.get("irating", 0) > 0, f"linha da classificacao traz licenca e iRating ({linha.get('lic')}, {linha.get('irating')})")
j = o.JanelaClassificacao(cfg); j.show(); j.atualizar(d); j.grab()
confere(j.width() == o.LARGURA_CLASS == 678, "classificacao 678 px")

# ---- ultimo contato (logica)
alvo = v.escolher_alvo([(1, 20.0, {}), (2, -4.0, {"n": 2}), (3, 6.5, {})])
confere(alvo and alvo[0] == 2, "escolhe o carro encostado mais perto")
confere(v.escolher_alvo([(1, 20.0, {})]) is None, "sem carro encostado: nao e contato")
u = v.UltimoContato()
confere(u.exibicao(10.0) is None, "sem contato: nada")
u.registrar(100.0, 5, {"numero": "43", "nome": "P. Dubois", "classe": "GT3", "cor": (1, 2, 3)}, 12)
u.completar_pontos(101.0, 4)
e = u.exibicao(165.0, -12.0, False, 30.0)
confere(e["pontos"] == 4 and e["sinal"] == -1 and abs(e["gap_s"] - 12 / 30.0) < 1e-6 and abs(e["ha_s"] - 65) < 1e-6, f"exibicao: {e}")
u.completar_pontos(200.0, 2)
confere(u.atual["pontos"] == 4, "pontos so completam logo depois do impacto")
confere(v.fmt_ha(65) == "1:05" and v.fmt_ha(12) == "12 s", "formato de 'ha quanto tempo'")

# ---- entrada do pit (logica)
P = v.PitEntrada()
P.atualizar("t", False, 0.94, 4000.0, 40.0, 60.0, 0.97, True)
P.atualizar("t", False, 0.949, 4000.0, 40.0, 60.0, 0.97, True)
r = P.atualizar("t", True, 0.951, 4000.0, 30.0, 60.0, 0.97, True)
confere(abs(P.entrada("t") - 0.949) < 1e-6 and P.mudou, "aprende a entrada do pit na primeira vez")
confere(r["fase"] == "pista" and r["luz"] == "vermelho" and abs(r["dist_box"] - 76.0) < 0.5, "pit lane: acima do limite = vermelho, distancia ao box")
r = P.atualizar("t", True, 0.96, 4000.0, 15.0, 60.0, 0.97, True)
confere(r["luz"] == "verde", "pit lane abaixo do limite = verde")
r = P.atualizar("t", False, 0.90, 4000.0, 70.0, 60.0, None, True)
confere(r["fase"] == "entrada" and r["luz"] == "vermelho" and r["freio_m"] > 100, "perto da entrada rapido demais: FREIE")
r = P.atualizar("t", False, 0.70, 4000.0, 70.0, 60.0, None, True)
confere(r is None, "longe da entrada (>700 m): nada")
confere(P.atualizar("t", False, 0.90, 4000.0, 70.0, 60.0, None, False, False) is None, "sem pedido de servico: nada (a menos que 'sempre')")
confere(P.atualizar("t", False, 0.90, 4000.0, 70.0, 60.0, None, False, True) is not None, "'sempre' mostra mesmo sem servico")
r = v.PitEntrada().atualizar("x", False, 0.9, 4000.0, 70.0, 60.0, None, True)
confere(r is None, "pista sem entrada aprendida: nada")

# ---- 1.7.0: pedido de entrada e aprendizado so ao entrar andando pela pista (dados reais: PitSvFlags fica != 0 sempre;
#      ao nascer no box a transicao "pit lane" ligou com v=0 e marcava a regiao da SAIDA)
Q = v.PitEntrada()
Q.atualizar("f", False, 0.0, 4000.0, 0.0, 60.0, 0.0935, False, False, 3)                 # nasce parado
r = Q.atualizar("f", True, 0.0935, 4000.0, 0.0, 60.0, 0.0935, False, False, 1)            # no box (superficie 1)
confere(Q.entrada("f") is None and not Q.mudou, "nascer no box NAO aprende a entrada")
Q = v.PitEntrada()
Q.atualizar("f", False, 0.0935, 4000.0, 3.0, 60.0, 0.0935, False, False, 3)               # quase parado na pista
Q.atualizar("f", True, 0.0936, 4000.0, 3.0, 60.0, 0.0935, False, False, 2)
confere(Q.entrada("f") is None, "entrar devagar demais (< 36 km/h) tambem nao aprende")
Q = v.PitEntrada()
Q.atualizar("f", False, 0.9300, 4000.0, 20.0, 60.0, 0.0935, False, False, 3)
Q.atualizar("f", True, 0.9310, 4000.0, 18.0, 60.0, 0.0935, False, False, 2)
confere(abs(Q.entrada("f") - 0.93) < 1e-6 and Q.mudou, "entrando pela pista a 72 km/h aprende a linha de ENTRADA")
Q = v.PitEntrada({"f": 0.93})
Q.atualizar("f", False, 0.2000, 4000.0, 40.0, 60.0, 0.0935, False, False, 3)
Q.atualizar("f", True, 0.2010, 4000.0, 40.0, 60.0, 0.0935, False, False, 2)
confere(abs(Q.entrada("f") - 0.93) < 1e-6, "entrada fora de ate 1500 m antes do box e ignorada")
Q = v.PitEntrada({"f": 0.93})
confere(Q.atualizar("f", False, 0.90, 4000.0, 50.0, 60.0, None, False, False, 3) is None, "sem pedido: janela do pit nao aparece")
confere(Q.alternar_pedido() is True and Q.atualizar("f", False, 0.90, 4000.0, 50.0, 60.0, None, Q.pedido, False, 3) is not None,
        "com pedido (atalho): aparece perto da entrada")
Q.atualizar("f", False, 0.9295, 4000.0, 20.0, 60.0, 0.0935, Q.pedido, False, 3)
Q.atualizar("f", True, 0.9302, 4000.0, 18.0, 60.0, 0.0935, Q.pedido, False, 2)
confere(Q.pedido is False, "o pedido some sozinho ao entrar na pit lane")
confere(Q.alternar_pedido() is True and Q.alternar_pedido() is False, "o atalho liga e desliga o pedido")

# ---- janelas
for cls in (o.JanelaUltimoContato, o.JanelaPitEntrada):
    w = cls(cfg); w.show(); w.atualizar(d); w.grab()
    confere(w.isVisible(), f"{cls.__name__} aparece com dados")
    d2 = dict(d); d2["contato"] = None; d2["pit"] = None; w.atualizar(d2)
    confere(not w.isVisible(), f"{cls.__name__} some sem dados")
    cfg["travado"] = False; w.atualizar(d2)
    confere(w.isVisible(), f"{cls.__name__} destravada mostra exemplo"); cfg["travado"] = True

# ---- caminho real: SDK falso -> Telemetria.ler()
class IRFalso:
    is_initialized = True; is_connected = True
    def __init__(self, vv): self.v = vv
    def __getitem__(self, k): return self.v.get(k)
    def startup(self): return True
    def freeze_var_buffer_latest(self): pass
    def unfreeze_var_buffer_latest(self): pass
    def shutdown(self): pass
N = 3
drivers = [{"CarIdx": i, "UserName": f"Piloto {i}", "CarNumber": str(40 + i), "CarClassID": 1, "CarClassShortName": "GT3",
            "CarClassColor": 0xffda59, "IRating": 2000, "LicString": "A 3.20", "LicColor": 0x0153db,
            "CarScreenName": "Porsche 911 GT3 R", "CarPath": "porsche992rgt3", "CarIsPaceCar": 0, "IsSpectator": 0,
            "UserID": 500 + i} for i in range(N)]
sdk = {"PlayerCarIdx": 0, "Speed": 40.0, "Gear": 3, "RPM": 6000.0, "Lap": 5, "LapCompleted": 4, "LapDistPct": 0.5,
       "FuelLevel": 50.0, "OnPitRoad": False, "IsOnTrack": True, "SessionNum": 0, "SessionUniqueID": 1, "SessionState": 4,
       "Throttle": 1.0, "Brake": 0.0, "Clutch": 1.0, "ThrottleRaw": 1.0, "BrakeRaw": 0.0, "ClutchRaw": 1.0,
       "BrakeABSactive": False, "SteeringWheelAngle": 0.0, "EngineWarnings": 0, "PlayerCarMyIncidentCount": 0,
       "PlayerTrackSurface": 3, "CarIdxLapDistPct": [0.5, 0.5008, 0.8], "CarIdxTrackSurface": [3] * N,
       "CarIdxOnPitRoad": [False] * N, "CarIdxClassPosition": [1, 2, 3], "CarIdxLapCompleted": [4] * N,
       "CarIdxLap": [5] * N, "CarIdxTireCompound": [0] * N, "CarIdxLastLapTime": [0.0] * N, "CarLeftRight": 1,
       "LatAccel": 0.0, "LongAccel": 0.0, "TrackTemp": 25.0, "TrackWetness": 1, "Precipitation": 0.0,
       "PitSvFlags": 0, "PitSvTireCompound": 0,
       "DriverInfo": {"Drivers": drivers, "DriverPitTrkPct": 0.97, "DriverTires": [{"TireIndex": 0, "TireCompoundType": "Dry"}]},
       "WeekendInfo": {"TrackDisplayName": "Pista Simulada", "TrackLength": "4.00 km", "TrackPitSpeedLimit": "60.00 kph",
                       "TrackID": 1, "Official": 1, "SubSessionID": 1, "Category": "Road"},
       "SessionInfo": {"Sessions": [{"SessionType": "Race"}]}}
tel = o.Telemetria(demo=False); tel.conectado = True; tel.ir = IRFalso(sdk)
tel.config_v16 = cfg
relogio = [1000.0]; o.time.monotonic = lambda: relogio[0]
def passo(**kw):
    sdk.update(kw); relogio[0] += 0.05; return tel.ler()
for _ in range(10): dd = passo()
confere(dd["contato"] is None, "sem batida: sem contato")
# batida de lado com o carro 1 (a 3,2 m) e incidente de 4x
dd = passo(LatAccel=80.0, LongAccel=0.0)
dd = passo(LatAccel=0.0)
dd = passo(PlayerCarMyIncidentCount=4)
confere(dd["contato"] is not None and dd["contato"]["numero"] == "41", f"contato com o #41 ({dd['contato']})")
confere(dd["contato"]["pontos"] == 4, "pontos 4x completados pelo contador de incidentes")
relogio[0] += 20.0
sdk["CarIdxLapDistPct"] = [0.5, 0.5008 + 0.004, 0.8]       # o outro carro avancou 16 m
dd = passo()
confere(dd["contato"]["gap_s"] > 0.3 and dd["contato"]["sinal"] == 1 and dd["contato"]["ha_s"] > 19, "gap atual e tempo desde o contato")
# batida em objeto sem carro por perto nao conta como contato novo
sdk["CarIdxLapDistPct"] = [0.5, 0.6, 0.8]
antes = dd["contato"]["nome"]
dd = passo(LatAccel=90.0); dd = passo(LatAccel=0.0); dd = passo(PlayerCarMyIncidentCount=6)
confere(dd["contato"]["nome"] == antes, "batida sem carro encostado nao troca o ultimo contato")
# pit: entra na pit lane perto de 0.95
sdk.update({"PitSvFlags": 1, "LapDistPct": 0.9, "CarIdxLapDistPct": [0.9, 0.6, 0.8], "Speed": 40.0})
dd = passo()
confere(dd["pit"] is None, "entrada ainda nao aprendida: sem luz de aproximacao")
sdk.update({"CarIdxLapDistPct": [0.948, 0.6, 0.8]}); dd = passo()
sdk.update({"OnPitRoad": True, "CarIdxLapDistPct": [0.951, 0.6, 0.8], "CarIdxOnPitRoad": [True, False, False]}); dd = passo()
confere(dd["pit"] is not None and dd["pit"]["fase"] == "pista" and abs(dd["pit"]["limite"] - 60.0) < 0.1, f"pit lane com limite lido do SDK ({dd['pit']})")
confere(o.ARQ_PIT.exists() and "0.948" in o.ARQ_PIT.read_text(), "entrada aprendida e gravada em arquivo")
sdk.update({"OnPitRoad": False, "CarIdxOnPitRoad": [False] * 3, "CarIdxLapDistPct": [0.90, 0.6, 0.8], "Speed": 70.0}); dd = passo()
confere(dd["pit"] is None, "volta seguinte SEM pedido: janela do pit nao aparece (PitSvFlags=1 nao conta como pedido)")
tel.pedir_pit(True); tel.pedir_pit(True); dd = passo()      # atalho do Stream Deck: apertar duas vezes nao desfaz
confere(tel.v16_pit.pedido is True and tel.pedir_pit(False) is False and tel.pedir_pit(True) is True, "atalhos pedir/cancelar sao idempotentes")
confere(dd["pit"] is not None and dd["pit"]["fase"] == "entrada" and dd["pit"]["luz"] == "vermelho", f"volta seguinte, COM pedido: luz de entrada ({dd['pit']})")

print("\n" + ("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)"))
sys.exit(1 if falhas else 0)
