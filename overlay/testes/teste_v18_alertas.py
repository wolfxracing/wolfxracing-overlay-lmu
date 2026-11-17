# -*- coding: utf-8 -*-
"""Telemetria (build aj): fundo do grafico e barras dos pedais piscam com limitador de pit, ABS e TC. Sem o jogo."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import overlay_iracing as o
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor
app = QApplication.instance() or QApplication([])
falhas, _ok = [], 0
def confere(c, m):
    global _ok
    if c: _ok += 1
    else: falhas.append(m); print("FALHA", m)
S = tempfile.mkdtemp(); o.ARQ_CONFIG = o.Path(S) / "c.json"; o.ARQ_LOG = o.Path(S) / "l.txt"
cfg = o.carregar_config()
confere(all(cfg.get(k) is True for k in ("telemetria_pisca_limitador", "telemetria_pisca_tc", "telemetria_pisca_abs")), "padrao: os tres alertas ligados")
J = o.JanelaTelemetria(dict(cfg))
base = o.Telemetria(demo=True).ler()
confere("limitador" in base, "dados trazem 'limitador'")
def dados(**k):
    d = dict(base); d.update({"conectado": True, "limitador": False, "abs": False, "luz_tc": {"ativa": False}, "freio": 0.0, "acelerador": 0.0}); d.update(k); return d
on = lambda *a: True
J._fase_pisca = on
confere(J._fundo_alerta(dados()) is None, "sem evento: fundo normal")
f = J._fundo_alerta(dados(limitador=True)); confere(f is not None and (f.red(), f.green(), f.blue()) == (255, 140, 30), "limitador: laranja")
f = J._fundo_alerta(dados(abs=True)); confere(f is not None and (f.red(), f.green(), f.blue()) == (250, 205, 40), "ABS: amarelo")
f = J._fundo_alerta(dados(luz_tc={"ativa": True})); confere(f is not None and (f.red(), f.green(), f.blue()) == (60, 150, 255), "TC: azul")
f = J._fundo_alerta(dados(limitador=True, abs=True)); confere((f.red(), f.green(), f.blue()) == (255, 140, 30), "limitador tem prioridade")
J._fase_pisca = lambda *a: False
confere(J._fundo_alerta(dados(limitador=True)) is None, "fase apagada: volta ao fundo normal (pisca)")
# pedais
J._fase_pisca = on
cf, ca = QColor(255, 0, 0), QColor(0, 255, 0)
c = J._cor_pedal("FRE", cf, 0.5, dados(abs=True)); confere((c.red(), c.green(), c.blue()) == (250, 205, 40), "freio pisca amarelo com ABS e pedal pressionado")
confere(J._cor_pedal("FRE", cf, 0.0, dados(abs=True)) == cf, "freio nao pisca com pedal solto")
confere(J._cor_pedal("FRE", cf, 0.5, dados(abs=False)) == cf, "freio nao pisca sem ABS")
c = J._cor_pedal("ACE", ca, 0.8, dados(luz_tc={"ativa": True})); confere((c.red(), c.green(), c.blue()) == (60, 150, 255), "acelerador pisca azul com TC")
confere(J._cor_pedal("ACE", ca, 0.8, dados(abs=True)) == ca and J._cor_pedal("EMB", ca, 0.8, dados(abs=True, luz_tc={"ativa": True})) == ca, "so o pedal certo pisca")
# desligar nas opcoes
J.config.update({"telemetria_pisca_limitador": False, "telemetria_pisca_abs": False, "telemetria_pisca_tc": False})
confere(J._fundo_alerta(dados(limitador=True, abs=True)) is None and J._cor_pedal("FRE", cf, 0.5, dados(abs=True)) == cf, "opcoes desligadas: nada pisca")
J.config.update({"telemetria_pisca_limitador": True, "telemetria_pisca_abs": True, "telemetria_pisca_tc": True})
# imagens: painel, sem grafico e barra
def foto(nome, **conf):
    j = o.JanelaTelemetria({**cfg, **conf}); j._fase_pisca = on
    j.dados = dados(limitador=True, abs=True, freio=0.7, acelerador=0.0)
    j.show(); img = j.grab().toImage(); img.save(os.path.join(S, nome)); j.close(); return img
a = foto("painel.png"); b = foto("sem_grafico.png", mostrar_grafico=False); c = foto("barra.png", telemetria_barra=True)
confere(not a.isNull() and not b.isNull() and not c.isNull(), "tres layouts desenham")
j = o.JanelaTelemetria(dict(cfg)); j._fase_pisca = lambda *a: False; j.dados = dados(limitador=True, abs=True, freio=0.7); j.show(); sem = j.grab().toImage(); j.close()
confere(a != sem, "imagem muda entre fase acesa e apagada")
for n in ("painel.png", "sem_grafico.png", "barra.png"): print("png", os.path.join(S, n))
print("ok" if not falhas else "FALHAS", _ok); sys.exit(1 if falhas else 0)
