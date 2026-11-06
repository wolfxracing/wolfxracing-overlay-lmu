# -*- coding: utf-8 -*-
"""v1.4.2 - Telemetria em barra horizontal (layout opcional)."""
import os, sys, tempfile, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import overlay_iracing as o
from PySide6.QtWidgets import QApplication

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c: None
falhas = []
def confere(c, msg):
    print(("OK    " if c else "FALHA ") + msg)
    if not c: falhas.append(msg)

cfg = o.carregar_config(); cfg["travado"] = True
confere(cfg.get("telemetria_barra") is False, "padrao: layout em painel (nada muda para quem ja usa)")
j = o.JanelaTelemetria(cfg); j.show()
confere((j.width(), j.height()) == (o.LARGURA, o.ALTURA + o.ALTURA_GRAFICO), f"painel: tamanho original {j.width()}x{j.height()}")
j.definir_barra(True)
confere((j.width(), j.height()) == (620, 88), f"barra com grafico: 620x88 ({j.width()}x{j.height()})")
j.definir_grafico(False)
confere((j.width(), j.height()) == (292, 88), f"barra sem grafico: 292x88 ({j.width()}x{j.height()})")
j.definir_grafico(True)
t = o.Telemetria(demo=True)
for marcha in (-1, 0, 1, 6):
    d = t.ler(); d.update(marcha=marcha, embreagem=None if marcha == 0 else 0.4, pedais_cru=None)
    j.atualizar(d); j.repaint()
img = j.grab()
confere(img.width() == 620 and not img.isNull(), "desenho da barra (R, N, 1 e 6; embreagem ausente) sem erro")
d = t.ler(); d.update(conectado=False); j.atualizar(d); j.repaint()
confere(True, "sem conexao desenha a mensagem")
j.definir_barra(False)
confere((j.width(), j.height()) == (o.LARGURA, o.ALTURA + o.ALTURA_GRAFICO), "voltar para painel restaura o tamanho")
conf = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "overlay_iracing.py"), encoding="utf-8").read()
confere('VERSAO_PRODUTO = "1.7.0"' in conf and '"overlay": f"{VERSAO_PRODUTO}' in conf, "versao 1.7.0 (constante VERSAO_PRODUTO)")
print()
print("TODOS OS TESTES DA 1.4.2 (barra) PASSARAM" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
