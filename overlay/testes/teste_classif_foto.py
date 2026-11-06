"""Testes automatizados da versao 1.6.1 no iRacing (janela de classificacao no layout da foto).
Executar: py -3.12 testes\\teste_classif_foto.py   (ou executar_testes.bat). Nao precisa do iRacing aberto.
Dados SIMULADOS: nao substitui a validacao em pista real (ROTEIRO_VALIDACAO.txt)."""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.argv = ["x", "--demo"]
PACOTE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PACOTE)
from pathlib import Path
import overlay_iracing as o
import ov_classif_foto as cf
from PySide6.QtWidgets import QApplication

S = Path(tempfile.mkdtemp(prefix="overlay_testes_v17_"))
o.ARQ_LOG = S / "log_v17.txt"; o.ARQ_CONFIG = S / "cfg_inexistente_v17.json"
for nome in ("ARQ_PENDENTE", "ARQ_COMPARACAO", "ARQ_HISTORICO", "ARQ_RECORDES", "ARQ_PNEUS", "ARQ_MAPAS"):
    setattr(o, nome, S / (nome.lower() + ".tmp"))
app = QApplication([]); o.salvar_config = lambda c: None
cfg = o.carregar_config(); cfg["travado"] = True

# ---- 1) configuracao
assert cfg["classificacao_layout"] == "foto" and cfg["classificacao_idioma"] == "en"
print("1) configuracao: layout 'foto' e idioma 'en' por padrao OK")

# ---- 2) formatacao
assert cf.fmt_gap(None) == "--" and cf.fmt_gap({"voltas": 2}) == "+2L" and cf.fmt_gap(1.2345) == "+1.234" or cf.fmt_gap(1.2345) == "+1.235"
assert cf.fmt_gap(75.04) == "+1:15.0" and cf.fmt_gap(0.0) == "0.000"
assert cf.fmt_ir_k(4800) == "4.8k" and cf.fmt_ir_k(10250) == "10.2k" or cf.fmt_ir_k(10250) == "10.3k"
assert cf.fmt_ir_k(0) == "--" and cf.fmt_ir_k(None) == "--"
assert cf.fmt_licenca("A3.4") == "A 3.4" and cf.fmt_licenca("") == ""
assert cf.fmt_duracao(154) == "2:34" and cf.fmt_duracao(4000) == "1:06:40" and cf.fmt_duracao(None) == "--:--"
assert cf.fmt_duracao_total(2700) == "45m" and cf.fmt_duracao_total(5400) == "1h30m" and cf.fmt_duracao_total(3600) == "1h"
assert cf.sigla_pneu("Duro") == "H" and cf.sigla_pneu("Macio") == "S" and cf.sigla_pneu("Medio") == "M"
assert cf.sigla_pneu("Chuva") == "W" and cf.sigla_pneu("Intermediario") == "I" and cf.sigla_pneu("Dry") == "D"
assert cf.sigla_pneu(None) == ""
print("2) formatacao (gap, iR, licenca, tempos, pneu) OK")

# ---- 3) paradas e stint
c = cf.ContadorParadas()
box, sup, lap = [False, False], [3, 3], [5, 5]
c.atualizar("s", lap, box, sup)
assert c.paradas(0) == 0 and c.stint(0, lap) == (5, False)            # abriu no meio da corrida: stint aproximado
box[0], sup[0] = True, 2                                              # entrou na pit lane
c.atualizar("s", lap, box, sup)
sup[0] = 1                                                            # parado na vaga
c.atualizar("s", lap, box, sup)
box[0], sup[0], lap[0] = False, 3, 6                                  # saiu
c.atualizar("s", lap, box, sup)
assert c.paradas(0) == 1 and c.stint(0, [6, 5]) == (0, True)
lap[0] = 9
assert c.stint(0, lap) == (3, True)
box[1], sup[1] = True, 2                                              # drive-through do carro 1: nao conta
c.atualizar("s", lap, box, sup)
box[1], sup[1] = False, 3
c.atualizar("s", lap, box, sup)
assert c.paradas(1) == 0
c.atualizar("outra", lap, box, sup)                                   # nova sessao zera
assert c.paradas(0) == 0 and c.stint(0, lap) == (9, False)
print("3) paradas e stint (parada, drive-through, sessao nova) OK")

# ---- 4) gap e intervalo
def linhas(n, melhor=80.0):
    return [{"idx": i, "pos": i + 1, "melhor": melhor + i * 0.3, "irating": 3000 + i * 400} for i in range(n)]

ls = linhas(4)
prog = {0: 10.50, 1: 10.40, 2: 10.30, 3: 9.20}                        # carro 3 uma volta atras
cf.calcular_gap_int(ls, "CORRIDA", prog, 80.0)
assert ls[0]["gap"] is None and ls[0]["int"] is None
assert abs(ls[1]["gap"] - 0.10 * 80.15) < 0.1 and abs(ls[1]["int"] - ls[1]["gap"]) < 1e-9
assert abs(ls[2]["gap"] - 0.20 * 80.15) < 0.1 and abs(ls[2]["int"] - 0.10 * 80.15) < 0.1
assert ls[3]["gap"] == {"voltas": 1} and ls[3]["int"] == {"voltas": 1}
assert all(l["gap_estimado"] for l in ls)
ls = linhas(3)
cf.calcular_gap_int(ls, "QUALIFICACAO", {}, 80.0)                      # fora da corrida: diferenca das melhores voltas
assert abs(ls[1]["gap"] - 0.3) < 1e-9 and abs(ls[2]["gap"] - 0.6) < 1e-9 and abs(ls[2]["int"] - 0.3) < 1e-9
assert not ls[1]["gap_estimado"]
ls = linhas(2); ls[1]["melhor"] = None
cf.calcular_gap_int(ls, "TREINO", {}, 80.0)
assert ls[1]["gap"] is None
ls = linhas(2)
cf.calcular_gap_int(ls, "CORRIDA", {0: 3.0}, 80.0)                     # sem progresso do carro: sem valor, sem erro
assert ls[1]["gap"] is None
print("4) gap/intervalo: corrida (progresso x referencia, voltas atras) e qualificacao (melhores voltas) OK")

# ---- 5) iRating projetado por carro
ls = linhas(6)
cf.projetar_ir_por_carro(ls, o.variacao_irating)
deltas = [l["ir_delta"] for l in ls]
assert all(isinstance(d, int) for d in deltas) and abs(sum(deltas)) <= 6        # soma ~ zero (arredondamento)
assert deltas[0] > 0 > deltas[-1]
ls = linhas(1)
cf.projetar_ir_por_carro(ls, o.variacao_irating)
assert ls[0]["ir_delta"] is None
print("5) iRating projetado por carro (soma zero, vencedor ganha, ultimo perde) OK")

# ---- 6) cabecalho
cab = cf.montar_cabecalho("CORRIDA", 5, 0, 2000.0, 2700.0, 24.0, 31.0, 0.45, 2, 25, 1, 0.0, ref_volta=80.0, fracao_volta=0.5)
assert cab["sessao"] == "RACE" and cab["voltas_total"] is None and abs(cab["decorrido"] - 700.0) < 1e-9
assert abs(cab["umidade"] - 45.0) < 1e-9 and cab["clima"] == "Dry" and cab["inc"] == 2 and cab["inc_limite"] == 25
assert abs(cab["voltas_estimadas"] - (4 + 0.5 + 2000.0 / 80.0)) < 1e-9
cab = cf.montar_cabecalho("CORRIDA", 5, 20, 100.0, 2700.0, None, None, None, 0, None, 5, 0.0)
assert cab["voltas_total"] == 20 and cab["voltas_estimadas"] is None and cab["clima"] == "Wet"
cab = cf.montar_cabecalho("QUALIFICACAO", 2, 32767, None, None, 20.0, 25.0, 50.0, 0, None, 3, 10.0, idioma="pt")
assert cab["sessao"] == "CLASSIF" and cab["voltas_total"] is None and cab["decorrido"] is None and cab["clima"] == "Chuva"
print("6) barra superior (RACE, voltas, decorrido, umidade, clima) OK")

# ---- 7) demonstracao + janela
tel = o.Telemetria(demo=True); tel.config_v16 = cfg
classif = tel._demo_classificacao(40.0)
assert classif["cabecalho"]["sessao"] == "RACE"
todas = [l for c in classif["classes"] for l in c["linhas"]]
assert all("gap" in l and "int" in l and "paradas" in l and "stint" in l and "pneu" in l and "ir_delta" in l for l in todas)
assert sum(1 for l in todas if l["pneu"]) == len(todas)
cls = cf.construir(o)
assert cls is cf.construir(o)                                        # uma unica classe
j = cls(cfg)
dados = tel._demo()
dados["classificacao"] = classif
j.atualizar(dados)
j.show(); app.processEvents()
img = j.grab().toImage()
assert img.width() == cf.LARGURA_FOTO and img.height() == j._altura_necessaria()
# a imagem nao pode estar em branco: precisa ter bastante variacao de cor
pixels = {img.pixel(x, y) for x in range(0, img.width(), 7) for y in range(0, img.height(), 5)}
assert len(pixels) > 60, len(pixels)
j.close()
print("7) demonstracao enriquecida e janela renderizada (%dx%d) OK" % (img.width(), img.height()))

# ---- 8) idioma portugues e layout classico
cfg_pt = dict(cfg); cfg_pt["classificacao_idioma"] = "pt"
jp = cls(cfg_pt)
assert jp._tx["piloto"] == "PILOTO"
jp.atualizar(dados); jp.show(); app.processEvents(); jp.grab(); jp.close()
assert issubclass(cls, o.JanelaClassificacao)                        # a janela antiga continua disponivel
print("8) idioma 'pt' e compatibilidade com a janela antiga OK")


# ---- 9) caminho real: Telemetria.ler() com SDK simulado
class IRFalso:
    is_initialized = True; is_connected = True
    def __init__(self, vv): self.v = vv
    def __getitem__(self, k): return self.v.get(k)
    def startup(self): return True
    def freeze_var_buffer_latest(self): pass
    def unfreeze_var_buffer_latest(self): pass
    def shutdown(self): pass


N = 4
drivers = [{"CarIdx": i, "UserName": f"Piloto {i}", "CarNumber": str(i + 1), "CarClassID": 1, "CarClassShortName": "GT3",
            "CarClassColor": 0xffda59, "IRating": 2000 + 500 * i, "LicString": "A 3.20", "LicColor": 0x0153db,
            "CarScreenName": "Porsche 911 GT3 R", "CarPath": "porsche992rgt3", "CarIsPaceCar": 0, "IsSpectator": 0,
            "UserID": 700 + i} for i in range(N)]
sdk = {"PlayerCarIdx": 1, "Speed": 40.0, "Gear": 3, "RPM": 6000.0, "Lap": 8, "LapCompleted": 7, "LapDistPct": 0.4,
       "FuelLevel": 50.0, "OnPitRoad": False, "IsOnTrack": True, "SessionNum": 0, "SessionUniqueID": 1, "SessionState": 4,
       "Throttle": 1.0, "Brake": 0.0, "Clutch": 1.0, "ThrottleRaw": 1.0, "BrakeRaw": 0.0, "ClutchRaw": 1.0,
       "BrakeABSactive": False, "SteeringWheelAngle": 0.0, "EngineWarnings": 0, "PlayerTrackSurface": 3,
       "CarIdxLapDistPct": [0.5, 0.4, 0.3, 0.45], "CarIdxTrackSurface": [3] * N, "CarIdxOnPitRoad": [False] * N,
       "CarIdxClassPosition": [1, 2, 3, 4], "CarIdxLapCompleted": [7, 7, 7, 6], "CarIdxLap": [8, 8, 8, 7],
       "CarIdxTireCompound": [0] * N, "CarIdxLastLapTime": [80.1, 80.4, 80.9, 81.0], "CarIdxBestLapTime": [79.8, 80.1, 80.5, 80.9],
       "CarLeftRight": 1, "LatAccel": 0.0, "LongAccel": 0.0, "TrackTemp": 25.0, "AirTemp": 21.0, "RelativeHumidity": 0.5,
       "TrackWetness": 1, "Precipitation": 0.0, "PlayerCarMyIncidentCount": 3, "SessionTimeRemain": 1500.0,
       "SessionTimeTotal": 2700.0, "SessionLapsTotal": 32767, "PitSvFlags": 0, "PitSvTireCompound": 0,
       "DriverInfo": {"Drivers": drivers, "DriverTires": [{"TireIndex": 0, "TireCompoundType": "Hard"}],
                      "DriverCarEstLapTime": 80.0},
       "WeekendInfo": {"TrackDisplayName": "Pista Simulada", "TrackLength": "5.00 km", "Official": 1, "SubSessionID": 1,
                       "Category": "Road", "WeekendOptions": {"IncidentLimit": "25"}},
       "SessionInfo": {"Sessions": [{"SessionType": "Race"}]}}
tel2 = o.Telemetria(demo=False); tel2.conectado = True; tel2.ir = IRFalso(sdk); tel2.config_v16 = cfg
relogio = [1000.0]; real_mono = o.time.monotonic; o.time.monotonic = lambda: relogio[0]
try:
    for _ in range(3):
        relogio[0] += 1.0
        dd = tel2.ler()
    cl = dd["classificacao"]
    assert cl is not None
    ls = cl["classes"][0]["linhas"]
    assert [l["pos"] for l in ls] == [1, 2, 3, 4]
    assert ls[0]["gap"] is None and ls[1]["gap"] is not None and ls[1]["gap"] > 0
    assert ls[3]["gap"] == {"voltas": 1} or ls[3]["gap"] > 5.0
    assert ls[1]["pneu"]["letra"] == "H" and ls[1]["paradas"] == 0
    cab = cl["cabecalho"]
    assert cab["sessao"] == "RACE" and cab["inc"] == 3 and cab["inc_limite"] == 25 and cab["voltas_total"] is None
    assert abs(cab["umidade"] - 50.0) < 1e-9 and abs(cab["decorrido"] - 1200.0) < 1e-9 and cab["clima"] == "Dry"
    assert all(l["ir_delta"] is not None for l in ls)
    print("9) Telemetria.ler() com SDK simulado: gap, pneu, paradas, cabecalho e iR por carro OK")
    # volta 8 do SDK sem os dados extras (variaveis ausentes) nao pode derrubar a classificacao
    for k in ("CarIdxLapDistPct", "RelativeHumidity", "SessionTimeTotal", "CarIdxTireCompound"):
        sdk.pop(k)
    relogio[0] += 1.0
    tel2._cache_blocos.clear()
    dd = tel2.ler()
    assert dd["classificacao"] is not None and dd["classificacao"]["classes"][0]["linhas"][1]["gap"] is None
    print("10) variaveis ausentes no SDK: a classificacao continua funcionando (gap '--') OK")
finally:
    o.time.monotonic = real_mono

print("\nTODOS OS TESTES DA CLASSIFICACAO (v1.6.1) PASSARAM.")

# ---- 9) 1.7.0: voltas de cada pneu na classificacao (como no Relativo)
assert all(("voltas_pneu" in l) for l in todas), "demo sem voltas_pneu"
assert any(l["voltas_pneu_confiavel"] is False for l in todas) and any(l["voltas_pneu_confiavel"] for l in todas)
j = cls(cfg); j.atualizar(dados); j.show(); app.processEvents(); com = j.grab().toImage(); j.close()
sem = {k: v for k, v in dados.items()}
cl2 = tel._demo_classificacao(40.0)
for l in (x for c in cl2["classes"] for x in c["linhas"]):
    l["voltas_pneu"] = None
sem["classificacao"] = cl2
j = cls(cfg); j.atualizar(sem); j.show(); app.processEvents(); sem_img = j.grab().toImage(); j.close()
assert com != sem_img, "o numero de voltas nao altera a imagem"
# nenhuma linha com dado quebra a janela quando voltas_pneu e None (sem telemetria)
print("9) voltas do pneu na classificacao (demo, confiavel/estimado, ausencia) OK")
