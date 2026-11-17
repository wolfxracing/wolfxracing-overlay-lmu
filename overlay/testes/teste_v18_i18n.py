# -*- coding: utf-8 -*-
"""Build aq: multi-idioma. Catalogo integro (6 colunas, mesmos '{}'), traducao exata e por modelo, recuo preservado, fallback
para portugues, deteccao pelo Windows, ganchos do Qt (rotulos, acoes, menu, pintura), config e seletores."""
import os, sys
from pathlib import Path
RAIZ = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
falhas, _ok = [], 0
def confere(c, msg):
    global _ok
    if c: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

import ov_i18n as i18n, ov_i18n_catalogo as cat
confere(i18n.CODIGOS == ("pt", "en", "es", "de", "fr", "it"), "6 idiomas: pt, en, es, de, fr, it")
confere(cat.ORDEM == ("en", "es", "de", "fr", "it"), "ordem das colunas do catalogo")
confere(len(cat.CAT) >= 400, f"catalogo com {len(cat.CAT)} entradas")
ruins = [k for k, v in cat.CAT.items() if len(v) != 5 or any((not t.strip()) or (t.count("{}") + t.count("{#}")) != (k.count("{}") + k.count("{#}")) for t in v)]
confere(not ruins, f"toda entrada tem 5 traducoes nao vazias e os mesmos '{{}}' ({ruins[:2]})")
confere(all("\n" not in k for k in cat.CAT), "chaves sem quebra de linha")

confere(i18n.definir_idioma("pt") == "pt" and i18n.tr("Sair") == "Sair", "pt devolve o texto original")
for cod, esperado in (("en", "Quit"), ("es", "Salir"), ("de", "Beenden"), ("fr", "Quitter"), ("it", "Esci")):
    confere(i18n.definir_idioma(cod) == cod and i18n.tr("Sair") == esperado, f"{cod}: Sair -> {esperado}")
i18n.definir_idioma("en")
confere(i18n.tr("Texto que nao existe no catalogo") == "Texto que nao existe no catalogo", "sem traducao: fica em portugues (nunca quebra)")
confere(i18n.tr("   Testar a Luz do ABS (1,5 s)") == "   Test the ABS light (1,5 s)", "modelo com {} e recuo preservado")
confere(i18n.tr("Opacidade do fundo: 80%") == "Background opacity: 80%", "modelo numerico")
confere(i18n.tr("") == "" and i18n.tr(None) is None and i18n.tr(5) == 5, "vazio/None/numero passam direto")
i18n.definir_idioma("de")
confere(i18n.tr("PENALIDADE") == "STRAFE" and i18n.tr("Volta 3") == "Volta 3", "alemao: texto igual so com maiuscula diferente nao casa por engano")

# deteccao do idioma
confere(i18n.resolver("pt") == "pt" and i18n.resolver("FR") == "fr" and i18n.resolver("xx") == "pt", "resolver: codigo valido, caixa e invalido")
auto = i18n.resolver("auto")
confere(auto in i18n.CODIGOS, f"auto -> {auto}")
os.environ["LANG"] = ""
import PySide6.QtCore as QC
orig = QC.QLocale.system
class _L:
    def __init__(self, n): self._n = n
    def name(self): return self._n
for nome, esp in (("pt_BR", "pt"), ("es_MX", "es"), ("fr_CA", "fr"), ("it_IT", "it"), ("ja_JP", "en"), ("de_AT", "de")):
    QC.QLocale.system = staticmethod(lambda n=nome: _L(n))
    confere(i18n.idioma_do_sistema() == esp, f"Windows {nome} -> {esp}")
QC.QLocale.system = orig

# ganchos do Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QMenu, QCheckBox
from PySide6.QtGui import QAction, QImage, QPainter, QActionGroup
from PySide6.QtCore import QRectF, Qt
app = QApplication.instance() or QApplication([])
i18n.instalar(); i18n.instalar()
i18n.definir_idioma("en")
l = QLabel("Sair"); confere(l.text() == "Quit", "QLabel(texto) traduz")
l.setText("Corrida"); confere(l.text() == "Race", "QLabel.setText traduz")
b = QPushButton("Treino"); confere(b.text() == "Practice", "QPushButton traduz")
c = QCheckBox("Mostrar este painel"); confere(c.text() == "Show this panel", "QCheckBox traduz")
m = QMenu("Todas as opções (avançado)"); confere(m.title() == "All options (advanced)", "QMenu(titulo) traduz")
a = m.addAction("Abrir configurações…"); confere(a.text() == "Open settings…", "QMenu.addAction(texto) traduz")
a2 = QAction("Sair", m); confere(a2.text() == "Quit", "QAction(texto) traduz")
sub = m.addMenu("Idioma / Language"); confere(sub.title() == "Language", "QMenu.addMenu traduz")
b.setToolTip("Sair"); confere(b.toolTip() == "Quit", "tooltip traduz")
i18n.definir_idioma("pt")
l.setText("Sair"); confere(l.text() == "Sair", "voltando a pt, o texto volta")
# pintura: o texto desenhado e o traduzido (compara imagens)
def pinta(lang, texto):
    i18n.definir_idioma(lang)
    img = QImage(220, 40, QImage.Format_ARGB32); img.fill(0xFF000000)
    p = QPainter(img); p.setPen(Qt.white); p.drawText(QRectF(0, 0, 220, 40), Qt.AlignCenter, texto); p.end()
    return img
confere(pinta("en", "PENALIDADE") == pinta("pt", "PENALTY"), "drawText: PENALIDADE aparece como PENALTY no ingles")
confere(pinta("pt", "PENALIDADE") != pinta("en", "PENALIDADE"), "drawText: em portugues continua PENALIDADE")

# config, menu e Central
import overlay_iracing as ov
cfg = ov.carregar_config()
confere(cfg.get("idioma") == "auto", "config padrao: idioma 'auto' (segue o Windows)")
confere(callable(getattr(ov, "montar_menu_idioma", None)), "menu da bandeja: montar_menu_idioma")
i18n.definir_idioma("pt")
menu = QMenu()
ov.montar_menu_idioma(menu, {"idioma": "auto"})
sub = [x for x in menu.actions() if x.menu() is not None]
confere(len(sub) == 1 and len(sub[0].menu().actions()) == 7, "submenu Idioma: Automatico + 6 idiomas")
nomes = [x.text() for x in sub[0].menu().actions()]
confere("English" in nomes and "Deutsch" in nomes and "Italiano" in nomes and "Español" in nomes and "Français" in nomes, f"nomes nativos dos idiomas ({nomes})")
confere(sum(1 for x in sub[0].menu().actions() if x.isChecked()) == 1 and sub[0].menu().actions()[0].isChecked(), "marca 'Automatico' quando idioma=auto")
fonte = (RAIZ / "ov_central.py").read_text(encoding="utf-8")
confere("_ao_idioma" in fonte and "IDIOMA / LANGUAGE" in fonte, "Central: seletor de idioma na Aparencia")
lmu = RAIZ / "overlay_lmu.py"
if lmu.exists():
    t = lmu.read_text(encoding="utf-8")
    confere("montar_menu_idioma" in t and "definir_idioma" in t, "LMU: menu de idioma e idioma aplicado ao iniciar")

# build ar (auditoria aq): argumentos nomeados e aviso de reinicio na Central
i18n.definir_idioma("en")
b = QPushButton(text="Sair"); confere(b.text() == "Quit", "QPushButton(text=...) traduz")
b.setText("Sair"); confere(b.text() == "Quit", "setText posicional continua traduzindo")
lb = QLabel(text="Sair", toolTip="Sair"); confere(lb.text() == "Quit" and lb.toolTip() == "Quit", "QLabel(text=..., toolTip=...) traduz")
confere(QCheckBox(text="Sair").text() == "Quit" and QAction(text="Sair").text() == "Quit" and QMenu(title="Sair").title() == "Quit",
        "QCheckBox/QAction(text=...) e QMenu(title=...) traduzem")
b.setObjectName("Sair"); confere(b.objectName() == "Sair", "identificador interno (objectName) nao e traduzido")
b.setProperty("Sair", "Sair"); confere(b.property("Sair") == "Sair", "valor de propriedade interna nao e traduzido")
import ov_central as oc
from types import SimpleNamespace
chamadas, salvou = [], []
orig_info = oc.QMessageBox.information
oc.QMessageBox.information = staticmethod(lambda *a, **k: chamadas.append(a))
try:
    fake = SimpleNamespace(config={}, g={"salvar": lambda: salvou.append(1)}, _registrar_erro=lambda c: salvou.append(c))
    oc.Central._ao_idioma(fake, "de")
finally:
    oc.QMessageBox.information = orig_info
confere(fake.config["idioma"] == "de" and salvou == [1], "Central: idioma gravado e config salva")
confere(len(chamadas) == 1 and chamadas[0][2] == i18n.AVISO_REINICIAR["de"], "Central: exibe o aviso de reinicio no idioma escolhido")
i18n.definir_idioma("pt")
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
