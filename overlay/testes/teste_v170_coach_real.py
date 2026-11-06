# -*- coding: utf-8 -*-
"""Build s: o Coach tem de GRAVAR voltas pelo caminho real do iRacing. O defeito (build r e anteriores): o Coach era alimentado
antes de 'tempo_volta'/'ultima_volta' serem montados, recebia None, e nunca gravava referencia ('Dirija uma volta limpa').
Aqui o SDK e simulado (ordem real dos campos) e o metodo de alimentacao e chamado como no ciclo do overlay."""
import math, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import overlay_iracing as ov

falhas, _ok = [], 0
def confere(c, msg):
    global _ok
    if c: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

COMP, TEMPO_VOLTA, HZ = 2300.0, 81.5, 20.0

class FakeIR(dict):
    pass

def volta(ir, tele, dados_base, numero, ultima):
    """Uma volta limpa a 20 Hz, na ordem do ciclo real: SDK -> coach (dados ainda SEM tempo_volta/ultima_volta)."""
    n = int(TEMPO_VOLTA * HZ)
    for k in range(n):
        t = k / HZ
        pct = (k / n) % 1.0
        vel = 40.0 + 25.0 * math.sin(pct * 2 * math.pi * 3)          # m/s
        ir.update({"LapDistPct": pct, "LapCurrentLapTime": t if t > 0 else 0.0001, "LapLastLapTime": ultima,
                   "PlayerTrackSurface": 3, "IsOnTrack": True, "OnPitRoad": False, "PlayerCarIdx": 0})
        d = dict(dados_base)
        d.update({"velocidade": vel * 3.6, "freio": 1.0 if 0.2 < pct < 0.23 else 0.0, "acelerador": 0.8, "marcha": 3})
        tele._alimentar_coach(d, True)
    return d

with tempfile.TemporaryDirectory() as tmp:
    tele = ov.Telemetria.__new__(ov.Telemetria)
    tele.ir = FakeIR()
    tele._comprimento = COMP
    tele._nome_pista = "Pista de Teste"
    tele._pilotos = {0: {"carro": "Carro de Teste"}}
    tele.config_coach_modo = "auto"
    tele.v17_coach = ov.coach_mod.Coach(ov.coach_mod.BibliotecaReferencias(Path(tmp) / "referencias"))
    base = {"velocidade": 0.0, "freio": 0.0, "acelerador": 0.0, "marcha": 0, "tempo_volta": None, "ultima_volta": None}
    d = volta(tele.ir, tele, base, 1, 0.0)
    confere(d["coach"].get("estado") != "ok", "primeira volta: ainda sem referencia (esperado)")
    d = volta(tele.ir, tele, base, 2, TEMPO_VOLTA)
    c = tele.v17_coach
    confere(c.voltas_gravadas >= 1, f"o Coach gravou voltas pelo caminho real (gravadas={c.voltas_gravadas})")
    confere(c.ref_propria is not None, "referencia propria criada")
    d = volta(tele.ir, tele, base, 3, TEMPO_VOLTA)
    confere(d["coach"].get("estado") == "ok", f"estado 'ok' depois de voltas limpas (estado={d['coach'].get('estado')})")
    confere(c.descarregar(5.0), "gravacao em disco concluida")
    confere(c.estatisticas_gravacao()["gravacoes"] >= 1, "arquivo de referencia gravado")

# o LMU monta o mesmo: protecao contra regressao no codigo-fonte do caminho real
fonte = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "overlay_iracing.py"
trecho = fonte.read_text(encoding="utf-8").split("def _alimentar_coach", 1)[1].split("def _montar_v12", 1)[0]
confere('dados.get("tempo_volta")' not in trecho and 'dados.get("ultima_volta")' not in trecho,
        "alimentacao do Coach nao depende de campos montados depois")
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
