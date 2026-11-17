# -*- coding: utf-8 -*-
"""Build an: icone WolfxRacing na barra de tarefas (identificador do programa + icone da aplicacao). Sem o jogo."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
falhas, _ok = [], 0
def confere(c, m):
    global _ok
    if c: _ok += 1
    else: falhas.append(m); print("FALHA", m)
import overlay_iracing as o
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
app = QApplication.instance() or QApplication([])
o.ARQ_LOG = o.Path(tempfile.mkdtemp()) / "l.txt"
confere((o.PASTA / "wolfxracing.ico").is_file() and not QIcon(str(o.PASTA / "wolfxracing.ico")).isNull(), "wolfxracing.ico existe e e valido")
app.setWindowIcon(QIcon()); o.definir_icone_app(app, "WolfxRacing.Teste")
confere(not app.windowIcon().isNull(), "icone da aplicacao definido (vale para todas as janelas)")
# sem o .ico: usa a logo/icone padrao, sem quebrar
ant = o.PASTA; o.PASTA = o.Path(tempfile.mkdtemp()); app.setWindowIcon(QIcon()); o.definir_icone_app(app, "WolfxRacing.Teste"); o.PASTA = ant
confere(not app.windowIcon().isNull(), "sem o arquivo .ico: cai no icone padrao")
print("ok" if not falhas else "FALHAS", _ok); sys.exit(1 if falhas else 0)
