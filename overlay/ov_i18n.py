# -*- coding: utf-8 -*-
"""Multi-idioma (build aq). O texto-fonte do programa e o portugues do Brasil; os catalogos ov_i18n_<lang>.py mapeiam
'texto em portugues' -> traducao. A traducao acontece NA SAIDA (nas chamadas do Qt que mostram texto), entao vale para
menus, Central, dialogos e painéis sem reescrever cada tela. Texto sem traducao aparece em portugues (nunca quebra).
Entradas com '{}' sao modelos: 'Alcance {} m' casa com 'Alcance 260 m' e leva o valor junto.
Idiomas: pt (original), en, es, de, fr, it. Config: 'idioma' = 'auto' (segue o Windows) ou o codigo."""
import importlib
import locale
import os
import re

IDIOMAS = (("pt", "Português (Brasil)"), ("en", "English"), ("es", "Español"), ("de", "Deutsch"), ("fr", "Français"), ("it", "Italiano"))
CODIGOS = tuple(c for c, _ in IDIOMAS)
_lang = "pt"
_catalogos = {}          # lang -> {texto: traducao}
_modelos = {}            # lang -> [(regex, traducao_com_{})]
_cache = {}
_SEPARADORES = re.compile(r"(  \|  | \| | · )")
_coleta = None           # conjunto de textos vistos (modo coleta de testes)
_instalado = False
AVISO_REINICIAR = {
    "pt": "Idioma alterado. Os paineis mudam na hora; reinicie o overlay para traduzir tambem a Central e os menus.",
    "en": "Language changed. Panels update immediately; restart the overlay to translate the settings window and menus too.",
    "es": "Idioma cambiado. Los paneles cambian al instante; reinicie el overlay para traducir tambien la Central y los menus.",
    "de": "Sprache geaendert. Die Panels wechseln sofort; starten Sie das Overlay neu, um auch Einstellungen und Menues zu uebersetzen.",
    "fr": "Langue modifiee. Les panneaux changent immediatement; redemarrez l'overlay pour traduire aussi la Central et les menus.",
    "it": "Lingua cambiata. I pannelli cambiano subito; riavvia l'overlay per tradurre anche la Central e i menu.",
}


def idioma_do_sistema():
    """Idioma do Windows (ou do ambiente) reduzido ao que temos; desconhecido -> 'en' (lingua franca), portugues -> 'pt'."""
    cand = [os.environ.get("WOLFX_IDIOMA", "")]  # variavel de ambiente: forca o idioma automatico (testes/suporte)
    try:
        from PySide6.QtCore import QLocale
        cand.append(QLocale.system().name())
    except Exception:
        pass
    try:
        cand.append((locale.getlocale()[0] or ""))
    except Exception:
        pass
    cand.append(os.environ.get("LANG", ""))
    for c in cand:
        base = str(c).lower().replace("-", "_").split("_")[0]
        if base in CODIGOS:
            return base
    return "en"


def resolver(valor):
    """'auto' ou vazio -> idioma do sistema; codigo valido -> ele; qualquer outra coisa -> 'pt'."""
    v = str(valor or "auto").strip().lower()
    if v == "auto":
        return idioma_do_sistema()
    return v if v in CODIGOS else "pt"


def idioma():
    return _lang


def _carregar(lang):
    if lang in _catalogos or lang == "pt":
        return
    dic = {}
    try:
        cat = importlib.import_module("ov_i18n_catalogo")
        idx = cat.ORDEM.index(lang)
        dic = {pt: tr_[idx] for pt, tr_ in cat.CAT.items()}
    except Exception:
        dic = {}
    _catalogos[lang] = {k: v for k, v in dic.items() if "{}" not in k and "{#}" not in k}
    mods = []
    for k, v in dic.items():
        if "{}" in k or "{#}" in k:
            rx = re.escape(k).replace(re.escape("{#}"), r"(\d+(?:[.,]\d+)?)").replace(re.escape("{}"), "(.+?)")
            mods.append((re.compile("^" + rx + "$", re.S), v.replace("{#}", "{}")))
    mods.sort(key=lambda m: -len(m[0].pattern))
    _modelos[lang] = mods


def definir_idioma(valor):
    """Escolhe o idioma ('auto' ou codigo). Devolve o codigo efetivo."""
    global _lang
    _lang = resolver(valor)
    _carregar(_lang)
    _cache.clear()
    return _lang


def tr(texto):
    """Traduz um texto em portugues para o idioma atual (devolve o proprio texto se nao houver traducao)."""
    if not isinstance(texto, str) or not texto:
        return texto
    if _coleta is not None and len(_coleta) < 20000:
        _coleta.add(texto)
    if _lang == "pt":
        return texto
    cat = _catalogos.get(_lang)
    if not cat and not _modelos.get(_lang):
        return texto
    r = cat.get(texto)
    if r is not None:
        return r
    r = _cache.get(texto)
    if r is not None:
        return r
    saida = texto
    if texto.strip() != texto:                       # espacos nas pontas (recuos do menu) sao preservados
        ini = texto[:len(texto) - len(texto.lstrip())]
        fim = texto[len(texto.rstrip()):]
        miolo = texto.strip()
        t = tr(miolo) if miolo else miolo
        saida = ini + t + fim
    else:
        achou = False
        for rx, modelo in _modelos.get(_lang, ()):
            m = rx.match(texto)
            if m:
                partes = list(m.groups())
                # o valor capturado pode ser traduzivel (ex.: nome de modo): tenta
                saida = modelo
                for g in partes:
                    saida = saida.replace("{}", tr(g) if len(g) > 2 else g, 1)
                achou = True
                break
        if not achou:
            pedacos = _SEPARADORES.split(texto)         # textos compostos ("A | B", "A · B"): traduz cada pedaco
            if len(pedacos) > 1:
                saida = "".join(p if i % 2 else tr(p) for i, p in enumerate(pedacos))
    if len(_cache) > 6000:
        _cache.clear()
    _cache[texto] = saida
    return saida


def iniciar_coleta():
    global _coleta
    _coleta = set()
    return _coleta


def coletados():
    return sorted(_coleta or ())


# argumentos nomeados que carregam texto visivel (so estes sao traduzidos; identificadores e valores internos nunca)
TEXTO_KW = frozenset(("text", "title", "toolTip", "tooltip", "string", "label"))


def _kw(k):
    if not k:
        return k
    return {n: (tr(v) if (n in TEXTO_KW and isinstance(v, str)) else v) for n, v in k.items()}


# ---- ganchos no Qt -----------------------------------------------------------------------------------------------
def _envolver_metodo(cls, nome, indices=None):
    """Troca cls.nome por uma versao que traduz os argumentos str (indices=None: todos)."""
    orig = getattr(cls, nome, None)
    if orig is None or getattr(orig, "_i18n", False):
        return

    def novo(self, *a, **k):
        a = tuple(tr(x) if (isinstance(x, str) and (indices is None or i in indices)) else x for i, x in enumerate(a))
        return orig(self, *a, **_kw(k))
    novo._i18n = True
    novo.__name__ = nome
    try:
        setattr(cls, nome, novo)
    except Exception:
        pass


def _envolver_init(cls, indices=(0,)):
    orig = cls.__init__
    if getattr(orig, "_i18n", False):
        return

    def novo(self, *a, **k):
        a = tuple(tr(x) if (isinstance(x, str) and i in indices) else x for i, x in enumerate(a))
        return orig(self, *a, **_kw(k))
    novo._i18n = True
    try:
        cls.__init__ = novo
    except Exception:
        pass


def instalar():
    """Liga a traducao nas chamadas do Qt que mostram texto. Idempotente; sem efeito de visual em 'pt'."""
    global _instalado
    if _instalado:
        return
    from PySide6 import QtWidgets as W, QtGui as G
    for cls in (W.QLabel, W.QPushButton, W.QCheckBox, W.QRadioButton, W.QToolButton, G.QAction):
        _envolver_metodo(cls, "setText")
        _envolver_metodo(cls, "setToolTip")
    for cls in (W.QLabel, W.QPushButton, W.QCheckBox, W.QRadioButton):
        _envolver_init(cls, (0,))
    _envolver_init(G.QAction, (0,))
    _envolver_init(W.QMenu, (0,))
    _envolver_init(W.QGroupBox, (0,))
    for nome in ("setWindowTitle", "setToolTip", "setStatusTip", "setWhatsThis"):
        _envolver_metodo(W.QWidget, nome)
    _envolver_metodo(W.QMenu, "setTitle")
    _envolver_metodo(W.QMenu, "addAction", (0,))
    _envolver_metodo(W.QMenu, "addMenu", (0,))
    _envolver_metodo(W.QMenu, "addSection", (0,))
    _envolver_metodo(W.QGroupBox, "setTitle")
    _envolver_metodo(W.QComboBox, "addItem", (0, 1))
    _envolver_metodo(W.QTabWidget, "addTab", (1, 2))
    _envolver_metodo(W.QTabWidget, "setTabText", (1,))
    _envolver_metodo(W.QLineEdit, "setPlaceholderText")
    _envolver_metodo(W.QMessageBox, "setText")
    _envolver_metodo(W.QMessageBox, "setInformativeText")
    _envolver_metodo(W.QSystemTrayIcon, "showMessage", (0, 1))
    _envolver_metodo(W.QSystemTrayIcon, "setToolTip")
    _envolver_metodo(W.QFormLayout, "addRow", (0,))
    _envolver_metodo(G.QPainter, "drawText")
    _envolver_metodo(G.QFontMetrics, "elidedText", (0,))
    _envolver_metodo(G.QFontMetrics, "horizontalAdvance", (0,))
    _instalado = True


# ---- modo coleta (so para montar os catalogos: WOLFX_I18N_COLETAR=<pasta>) ---------------------------------------
if os.environ.get("WOLFX_I18N_COLETAR"):
    import atexit

    iniciar_coleta()

    def _gravar():
        try:
            pasta = os.environ["WOLFX_I18N_COLETAR"]
            os.makedirs(pasta, exist_ok=True)
            with open(os.path.join(pasta, "col_%d.txt" % os.getpid()), "w", encoding="utf-8") as f:
                for t in coletados():
                    f.write(t.replace("\n", "\\n") + "\n")
        except Exception:
            pass
    atexit.register(_gravar)
