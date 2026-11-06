# -*- coding: utf-8 -*-
"""Build v (auditoria da build u): regressao equivalente no adaptador LMU. TelemetriaLMU.ler() -> _ler_real() -> _montar_coach, com o
JOGO FALSO de teste_lmu.py (memoria compartilhada simulada, estruturas reais), tem de alimentar o Coach, fechar voltas e gravar a
referencia. Prova o desenho do codigo; NAO prova que o LMU real entrega os dados assim."""
import math, os, sys, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import teste_lmu as T
from teste_lmu import confere, grupo

COMP, VOLTA_S, HZ = 3000.0, 60.0, 20.0
m = T.preparar_modulo()
base = m.base
grupo("LMU - ciclo real alimenta o Coach")
j = T.cenario_corrida()
j.comprimento = COMP
eu = j.carros[3]; eu.voltas, eu.dist, eu.ultima, eu.melhor = 0, 0.0, -1.0, -1.0
j.et = j.inicio_volta = j.tempo_decorrido = 0.0
tel, rel = T.telemetria(j)
with tempfile.TemporaryDirectory() as tmp:
    tel.v17_coach = base.coach_mod.Coach(base.coach_mod.BibliotecaReferencias(Path(tmp) / "referencias"))
    estado = {"t": 0.0, "n": 0}

    def volta(numero, ultima, box_apos=None, ticks=None):
        n = int(VOLTA_S * HZ); d = None
        for k in range(ticks or n):
            pct = k / n
            estado["t"] += 1.0 / HZ; j.et = estado["t"]; rel.avancar(1.0 / HZ)
            eu.dist = COMP * pct
            j.tempo_decorrido = estado["t"]
            j.vel_ms = (0.0, 0.0, -(40.0 + 25.0 * math.sin(pct * 2 * math.pi * 3)))
            j.freio = 1.0 if 0.2 < pct < 0.23 else 0.0
            eu.box = bool(box_apos is not None and k >= box_apos)
            if k == 0:
                j.inicio_volta = estado["t"]; eu.voltas = numero - 1; eu.ultima = ultima
            d = tel.ler()
        return d
    d = volta(1, -1.0)
    confere(d["conectado"] and d["no_carro"], "LMU ciclo real: conectado e no carro")
    confere(d["coach"] is not None and d["coach"].get("estado") != "ok", f"1a volta: Coach recebe dados, sem referencia ainda (estado={d['coach'] and d['coach'].get('estado')})")
    d = volta(2, VOLTA_S)
    c = tel.v17_coach
    confere(c.voltas_gravadas >= 1, f"LMU: o Coach fechou volta pelo ciclo real (gravadas={c.voltas_gravadas})")
    confere(c.ref_propria is not None, "LMU: referencia propria registrada pelo ciclo real")
    d = volta(3, VOLTA_S)
    confere(d["coach"] is not None and d["coach"].get("estado") == "ok", f"LMU: 3a volta com estado 'ok' (estado={d['coach'] and d['coach'].get('estado')})")
    confere(d["coach"].get("proxima") is not None, "LMU: o Coach informa a proxima freada")
    confere(c.descarregar(5.0) and c.estatisticas_gravacao()["gravacoes"] >= 1, "LMU: referencia gravada em disco")
    volta(4, VOLTA_S, box_apos=600)
    antes = c.voltas_gravadas
    volta(5, VOLTA_S, ticks=3)
    confere(c.voltas_gravadas == antes, f"LMU: volta com box nao e gravada ({antes} -> {c.voltas_gravadas})")
    tel.encerrar()
print(f"\nRESULTADO: {'OK' if not T._falhas else str(len(T._falhas)) + ' FALHA(S)'} ({T._ok} verificacoes)")
sys.exit(1 if T._falhas else 0)
