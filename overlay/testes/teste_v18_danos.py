# -*- coding: utf-8 -*-
"""Detector de danos (iRacing): contato leve, confirmacao pelo tempo de reparo, limpeza apos reparo. Logica pura; sem o jogo."""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import overlay_iracing as o
falhas, _ok = [], 0
def confere(c, m):
    global _ok
    if c: _ok += 1
    else: falhas.append(m); print("FALHA", m)
G = 9.81
def rodar(d, t0, dur, ax=0.0, ay=0.0, inc=0, rep=0.0, hz=60):
    t = t0
    for _ in range(int(dur * hz)):
        d.atualizar(t, ax, ay, inc, True, rep); t += 1.0 / hz
    return t
# 1) batida forte de frente com incidente: zona F, sev>=2
d = o.DetectorImpactos(); t = rodar(d, 0, 2)
t = rodar(d, t, 0.1, ax=-9 * G, inc=0); t = rodar(d, t, 0.5, inc=2)
confere(d.zonas["F"] >= 2, f"batida de frente marca F ({d.zonas})")
# 2) contato leve (1,3 g) com incidente 4x: antes ficava sem zona
d = o.DetectorImpactos(); t = rodar(d, 0, 2)
t = rodar(d, t, 0.1, ay=1.3 * G, inc=0); t = rodar(d, t, 0.5, inc=4)
confere(any(d.zonas.values()), f"contato leve de 1,3 g passa a marcar zona ({d.zonas})")
# 3) saida de pista (+1) com pico baixo continua sem zona
d = o.DetectorImpactos(); t = rodar(d, 0, 2); t = rodar(d, t, 0.5, ay=1.3 * G, inc=0); t = rodar(d, t, 0.5, inc=1)
confere(not any(d.zonas.values()) and d.eventos[-1]["tipo"] == "saida", "saida de pista leve nao marca zona")
# 4) reparo sobe sem impacto proprio: evento 'dano' confirmado pelo reparo
d = o.DetectorImpactos(); t = rodar(d, 0, 2); n = d.total
t = rodar(d, t, 0.5, rep=0.0); t = rodar(d, t, 0.5, rep=30.0)
confere(d.total == n + 1 and d.eventos[-1]["tipo"] == "dano" and d.eventos[-1]["sev"] == 2, f"reparo de 30 s vira evento dano sev 2 ({d.eventos[-1:]})")
# 5) reparo sobe logo apos batida com zona: eleva a severidade da mesma zona, sem duplicar
d = o.DetectorImpactos(); t = rodar(d, 0, 2)
t = rodar(d, t, 0.1, ax=-4 * G); t = rodar(d, t, 0.3, inc=2); n = d.total
t = rodar(d, t, 0.5, rep=60.0, inc=2)
confere(d.total == n and d.zonas["F"] == 3, f"reparo de 60 s eleva F a 3 sem duplicar ({d.zonas}, {d.total}/{n})")
# 6) fim do reparo limpa as marcas
t = rodar(d, t, 0.5, rep=0.0, inc=2)
confere(not any(d.zonas.values()), "reparo concluido limpa as marcas")
# 7) reparo opcional entra na soma (chamada do montador)
d = o.DetectorImpactos(); t = rodar(d, 0, 1); t = rodar(d, t, 0.5, rep=0.0 + 12.0)
confere(d.eventos and d.eventos[-1]["sev"] == 1, "reparo curto = sev 1")
# 8) resetar zera o estado do reparo
d.resetar(); confere(d._reparo_ant is None and d.total == 0, "resetar zera reparo e total")
# 10) frenagem forte (rampa de 0 a -4 g em 100 ms) nao e batida
d = o.DetectorImpactos(); t = rodar(d, 0, 2)
for i in range(7): d.atualizar(t, -4 * G * i / 6, 0.0, 0, True, 0.0); t += 1 / 60
t = rodar(d, t, 3.0, ax=-4 * G)
confere(d.total == 0, f"frenagem de 4 g nao gera impacto ({d.total})")
# 11) batida de 3 g em uma amostra (salto) e detectada, com zona do lado
d = o.DetectorImpactos(); t = rodar(d, 0, 2)
d.atualizar(t, 0.0, 3.2 * G, 0, True, 0.0); t += 1 / 60; t = rodar(d, t, 0.5)
confere(d.total == 1 and d.eventos[-1]["zona"] == "D", f"salto de 3,2 g lateral marca lado direito ({d.eventos[-1:]})")
# 12) refino: o pico real (8 g de frente) logo apos o gatilho corrige zona e g
d = o.DetectorImpactos(); t = rodar(d, 0, 2)
d.atualizar(t, 0.0, 2.6 * G, 0, True, 0.0); t += 1 / 60
d.atualizar(t, -8 * G, 0.0, 0, True, 0.0); t += 1 / 60; t = rodar(d, t, 0.5)
confere(d.total == 1 and d.eventos[-1]["zona"] == "F" and d.eventos[-1]["g"] >= 7 and d.zonas["E"] == 0 and d.zonas["D"] == 0,
        f"refino corrige para F com g alto ({d.eventos[-1:]}, {d.zonas})")
# 13) incidente sem pico conta como impacto (e vai para o log)
d = o.DetectorImpactos(); t = rodar(d, 0, 2); t = rodar(d, t, 0.5, inc=4)
confere(d.total == 1, f"incidente 4x sem pico conta no total ({d.total})")
# 14) o registro final so fecha depois do refino/janela do incidente (2 s); impacto sem pico fecha na hora
d = o.DetectorImpactos(); t = rodar(d, 0, 2)
d.atualizar(t, 0.0, 3.2 * G, 0, True, 0.0); t += 1 / 60
confere(d.eventos[-1]["final"] is False and d.eventos[-1]["n"] == 1, "pancada nasce provisoria (n=1)")
t = rodar(d, t, 1.0); confere(d.eventos[-1]["final"] is False, "ainda provisoria com 1 s")
t = rodar(d, t, 1.5); confere(d.eventos[-1]["final"] is True, "final apos 2 s")
d = o.DetectorImpactos(); t = rodar(d, 0, 2); t = rodar(d, t, 0.5, inc=4)
confere(d.eventos[-1]["final"] is True and d.eventos[-1]["n"] == 1, "incidente sem pico ja nasce final")
# 15) log pelo montador: um registro por impacto, com valores finais; troca de sessao nao gera '#0'
avisos = []
o.registrar_aviso = lambda txt: avisos.append(txt)
T = o.Telemetria(demo=True)
vals = {"SessionNum": 0, "SessionUniqueID": 1, "PitRepairLeft": 0.0, "PitOptRepairLeft": 0.0, "PlayerCarMyIncidentCount": 0,
        "IsOnTrack": True, "IsReplayPlaying": False, "LongAccel": 0.0, "LatAccel": 0.0, "EngineWarnings": 0}
T._var = lambda nome, padrao=None: vals.get(nome, padrao)
relogio = [100.0]
o.time.monotonic = lambda: relogio[0]
def passo(n, dt=1 / 60):
    for _ in range(n):
        relogio[0] += dt; T._montar_danos()
passo(120)
vals["LatAccel"] = 3.0 * G; passo(1); vals["LatAccel"] = 0.0; vals["LongAccel"] = -9 * G; passo(1); vals["LongAccel"] = 0.0
passo(30)
confere(avisos == [], f"nada e registrado antes de o evento ficar final ({avisos})")
vals["PlayerCarMyIncidentCount"] = 4; passo(150)
imp = [a for a in avisos if a.startswith("Danos: impacto")]
confere(len(imp) == 1 and "#1 " in imp[0] and "zona=F" in imp[0] and "tipo=contato" in imp[0] and "g=9." in imp[0], f"log final com zona F, contato e pico 9 g ({imp})")
passo(120); confere(len([a for a in avisos if a.startswith("Danos: impacto")]) == 1, "nao registra de novo")
vals["LatAccel"] = 3.0 * G; passo(1); vals["LatAccel"] = 0.0; passo(10)          # nova pancada ainda provisoria
vals["SessionUniqueID"] = 2; passo(5)                                             # troca de sessao
imp = [a for a in avisos if a.startswith("Danos: impacto")]
confere(len(imp) == 2 and "#2 " in imp[1] and "sessao encerrada" in imp[1], f"troca de sessao fecha o pendente ({imp[1:]})")
confere(not any("#0" in a for a in avisos) and T.impactos.total == 0, "nenhum impacto #0 apos a troca de sessao")
passo(240); confere(len([a for a in avisos if a.startswith("Danos: impacto")]) == 2, "sem registros novos na sessao nova")
# 9) a janela desenha os novos tipos (dano, local indefinido) sem erro
import tempfile
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
S = tempfile.mkdtemp(); o.ARQ_CONFIG = o.Path(S) / "c.json"; o.ARQ_LOG = o.Path(S) / "l.txt"
j = o.JanelaDanos(o.carregar_config())
base = {"conectado": True}
ev = [{"t": 1.0, "zona": None, "sev": 2, "g": 0.0, "delta": 0, "tipo": "dano", "idade": 3.0},
      {"t": 0.5, "zona": None, "sev": 1, "g": 0.0, "delta": 1, "tipo": "saida", "idade": 8.0},
      {"t": 0.2, "zona": "F", "sev": 3, "g": 9.0, "delta": 2, "tipo": "batida", "idade": 20.0}]
dn = {"zonas": {"F": 3, "T": 0, "E": 0, "D": 0}, "total": 3, "eventos": ev, "reparo": 30.0, "reparo_opc": 0.0,
      "avisos": [], "incidentes": 6, "limite": 17, "reboque": 0.0, "rapidos": 1}
j.dados = dict(j.dados) if isinstance(getattr(j, "dados", None), dict) else {}
j.dados.update({"conectado": True, "danos": dn})
img = j.grab().toImage()
confere(not img.isNull() and img.width() > 100, "janela de danos renderiza com evento dano e zona indefinida")
confere(j.NOMES_ZONA[None] == "Local indefinido" and "dano" in j.NOMES_TIPO, "rotulos novos")
print("ok" if not falhas else "FALHAS", _ok)
sys.exit(1 if falhas else 0)
