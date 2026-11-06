# -*- coding: utf-8 -*-
"""Build v: a Central precisa MONTAR com a telemetria de demonstracao REAL de cada jogo. Defeito da build t/u: no iRacing
Telemetria._demo e um METODO, e montar_central tentava gravar um atributo nele (AttributeError) -> a Central nao abria."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import overlay_iracing as o
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PySide6.QtGui import QAction

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda c_: None
falhas, _ok = [], 0
def confere(c, msg):
    global _ok
    if c: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

erros = []
o.registrar_erro = lambda ctx, *a, **k: erros.append(ctx)
try:
    import overlay_lmu as lmu
except Exception:
    lmu = None
casos = [("iRacing", lambda: o.Telemetria(demo=True))]
if lmu is not None:
    casos.append(("LMU", lambda: lmu.TelemetriaLMU(demo=True)))
for nome, fabrica in casos:
    cfg = o.carregar_config(); cfg["travado"] = True
    bandeja, menu = QSystemTrayIcon(), QMenu()
    sair = QAction("Sair")
    ganchos = {"salvar": lambda: None, "restaurar": lambda: None, "opacidade": lambda v: None}
    c = o.montar_central(app, bandeja, menu, [], {}, cfg, sair, nome, fabrica, ganchos)
    confere(c is not None, f"{nome}: a Central monta com a telemetria de demonstracao real")
    confere(not erros, f"{nome}: nenhum erro registrado ({erros})")
    if c is not None:
        c.mostrar(); app.processEvents()
        confere(c.isVisible(), f"{nome}: a Central abre")
        c.close()
    # a telemetria de demonstracao funciona em modo previa (iRacing: gerador interno; LMU: gerador reaproveitado)
    t = fabrica(); t.modo_previa = True
    ger = getattr(t, "_demo", None)
    if ger is not None and not callable(ger):
        ger.modo_previa = True
    d = t.ler()
    confere(isinstance(d, dict) and d, f"{nome}: ler() devolve dados de exemplo")
print(f"\nRESULTADO: {len(falhas)} FALHA(S)" if falhas else f"\n{_ok} ok, 0 falha(s)")
sys.exit(1 if falhas else 0)
