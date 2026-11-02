# -*- coding: utf-8 -*-
"""v1.6.0 - Central de configuracoes (janela interativa, no estilo de um painel de controle).

A central NAO tem logica propria: cada botao aciona o mesmo item do menu da bandeja (setChecked dispara o mesmo tratamento),
entao perfis, atalhos do Stream Deck e config.json continuam coerentes. Se este arquivo faltar, o overlay segue com o menu
completo de antes.
"""
import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QRadioButton, QScrollArea, QSlider, QStackedWidget, QVBoxLayout, QWidget)

MARCA_DIR = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent) / "marca"      # logo e fundo da WolfxRacing (opcionais)
ACENTO = "#ec1c24"                                         # vermelho da logo
MARCA = "#ec1c24"

# CHAVE da janela -> (titulo, descricao, categoria, extras [(chave da acao no menu, rotulo)], dica)
PAINEIS = {
    "principal": ("Telemetria", "Marcha, velocidade, volante e pedais; painel ou barra horizontal.", "Pilotagem",
                  [("mostrar_grafico", "Gráfico de acelerador e freio"), ("telemetria_barra", "Layout em barra horizontal")], ""),
    "voltas": ("Voltas e combustível", "Delta, tempos de volta e cálculo de combustível.", "Pilotagem",
               [("mostrar_calc_combustivel", "Cálculo de combustível")], ""),
    "relativo": ("Relativo", "Os carros logo à frente e atrás de você na pista, com diferença de tempo.", "Corrida",
                 [("mostrar_projecao", "Projeção de iRating e SR")], ""),
    "classificacao": ("Classificação", "Todos os carros por posição e classe, com SR, iRating e posições ganhas.", "Corrida",
                      [("classificacao_todas", "Mostrar todas as classes")], ""),
    "mapa": ("Mapa da pista", "Traçado da pista com todos os carros na cor da classe.", "Pista", [], ""),
    "radar": ("Radar", "Carros ao seu redor, com aviso de carro ao lado.", "Automáticos",
              [("radar_auto", "Só aparecer com carro por perto")], "Aparece sozinho quando há carro por perto."),
    "setores": ("Setores", "Tempo de cada setor contra a sua melhor volta.", "Pilotagem", [], ""),
    "pneus": ("Pneus", "Temperatura, vida útil e composto.", "Carro", [], ""),
    "clima": ("Clima", "Temperatura, chuva, vento e umidade da pista.", "Pista", [], ""),
    "danos": ("Danos e impactos", "Zonas do carro atingidas e incidentes.", "Carro", [], ""),
    "combustivel": ("Combustível e pit", "Combustível, voltas restantes e dados de parada.", "Carro", [], ""),
    "forca_g": ("Força G", "Aceleração lateral e longitudinal.", "Pilotagem", [], ""),
    "luz_abs": ("Luz do ABS", "Acende quando o ABS atua.", "Carro", [], ""),
    "luz_tc": ("Luz do TC", "Acende quando o controle de tração atua.", "Carro", [], ""),
    "retorno": ("Retorno à pista", "PARE / CEDA / LIVRE ao voltar para a pista.", "Automáticos", [], "Aparece sozinho quando você está fora da pista."),
    "estrategia": ("Estratégia de pneus", "Chuva x seco: quando vale trocar.", "Corrida",
                   [("estrategia_pulsar", "Pulsar na hora de trocar")], ""),
    "curvas": ("Velocidade nas curvas", "Velocidade mínima em cada curva contra a sua melhor passagem.", "Pilotagem", [], ""),
    "bandeiras": ("Bandeiras", "Bandeira da pista: amarela, azul, branca, quadriculada e outras.", "Automáticos", [],
                  "Aparece sozinha só quando há bandeira."),
    "trafego": ("Tráfego de outras classes", "Carros de outra classe chegando, com a diferença em segundos.", "Automáticos", [],
                "Aparece sozinho só com carro de outra classe a menos de ~6 s."),
    "minimapa": ("Minimapa rotativo", "Trecho da pista ao seu redor girando com o carro sempre para cima.", "Pista", [], ""),
    "auxiliar": ("Auxiliar de sessão", "Etapa da sessão, contagem de largada e tempo restante.", "Automáticos",
                 [("auxiliar_sempre", "Mostrar também durante a sessão")], "Aparece antes da largada e no fim da sessão."),
    "contato": ("Último contato", "Quem você tocou por último, pontos, volta e onde o piloto está agora.", "Automáticos", [],
                "Aparece depois que você toca em um carro."),
    "pit": ("Entrada do pit", "Distância até a entrada dos boxes, aviso de freio e limite da pit lane.", "Automáticos",
            [("pit_sempre", "Mostrar sempre perto da entrada")], "Aparece com parada pedida (ou sempre, se ligar a opção). A entrada é aprendida na 1ª vez que você entra."),
    "tendencia": ("Tendência de ritmo", "Últimas voltas limpas, ritmo médio, inclinação do stint e previsão da próxima volta.", "Corrida", [],
                  "Precisa de voltas limpas (sem boxes nem bandeira de perigo); a inclinação (~) aparece com 4 voltas no stint."),
    "lmu_energia": ("Energia e combustível (LMU)", "Energia virtual, consumo por volta e voltas até o fim.", "Carro", [], ""),
    "lmu_alertas": ("Alertas na pista (LMU)", "Amarelas, limite dos boxes e classe rápida chegando.", "Automáticos", [], ""),
    "lmu_stints": ("Stints (LMU)", "Histórico de stints: voltas, energia e combustível.", "Corrida", [], ""),
    "lmu_tendencia": ("Tendência de ritmo (LMU)", "Ritmo das últimas voltas limpas.", "Corrida", [], ""),
}
CATEGORIAS = ("Todos", "Pilotagem", "Corrida", "Carro", "Pista", "Automáticos")

QSS = f"""
QWidget#central {{ background: #09090b; color: #f2f2f4; font-family: 'Segoe UI', 'Inter', sans-serif; }}
QFrame#lateral {{ background: rgba(0,0,0,215); border-right: 2px solid {ACENTO}; }}
QLabel {{ color: #f2f2f4; background: transparent; }}
QLabel#h1 {{ font-size: 25px; font-weight: 800; font-style: italic; }}
QLabel#h2 {{ font-size: 11px; font-weight: 800; color: {ACENTO}; letter-spacing: 2px; }}
QLabel#mudo {{ color: #9a9aa6; font-size: 12px; }}
QLabel#marca {{ font-size: 17px; font-weight: 800; font-style: italic; color: #ffffff; }}
QPushButton#nav {{ text-align: left; padding: 11px 14px; border: none; border-radius: 4px; color: #c9c9d1; font-size: 14px; font-weight: 600; font-style: italic; background: transparent; }}
QPushButton#nav:hover {{ background: rgba(236,28,36,40); color: #fff; }}
QPushButton#nav:checked {{ background: rgba(236,28,36,70); color: #fff; border-left: 4px solid {ACENTO}; }}
QPushButton#chip {{ padding: 6px 16px; border: 1px solid #34343c; border-radius: 3px; color: #c9c9d1; background: rgba(14,14,17,200); font-weight: 600; font-style: italic; }}
QPushButton#chip:hover {{ border-color: {ACENTO}; }}
QPushButton#chip:checked {{ background: {ACENTO}; color: #ffffff; border-color: {ACENTO}; font-weight: 800; }}
QPushButton#link {{ border: none; color: {ACENTO}; text-align: right; background: transparent; font-size: 12px; font-weight: 700; }}
QPushButton#link:hover {{ color: #fff; }}
QPushButton#acao {{ padding: 9px 16px; border: 1px solid {ACENTO}; border-radius: 3px; background: rgba(236,28,36,35); color: #fff; font-weight: 700; }}
QPushButton#acao:hover {{ background: {ACENTO}; }}
QFrame#cartao {{ background: rgba(16,16,19,225); border: 1px solid #2c2c33; border-radius: 6px; }}
QFrame#cartao[ligado="true"] {{ border: 1px solid #b3141b; }}
QFrame#bloco {{ background: rgba(16,16,19,225); border: 1px solid #2c2c33; border-radius: 6px; }}
QLineEdit {{ background: rgba(12,12,15,225); border: 1px solid #34343c; border-radius: 4px; padding: 9px 12px; color: #f2f2f4; }}
QLineEdit:focus {{ border: 1px solid {ACENTO}; }}
QSlider::groove:horizontal {{ height: 4px; background: #34343c; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACENTO}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #fff; border: 3px solid {ACENTO}; width: 12px; height: 12px; margin: -8px 0; border-radius: 9px; }}
QRadioButton {{ color: #f2f2f4; spacing: 10px; padding: 6px 0; font-size: 14px; font-weight: 600; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: #3a3a42; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACENTO}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


class Interruptor(QAbstractButton):
    """Chave liga/desliga (44x24)."""

    def __init__(self, ligado=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(bool(ligado))
        self.setFixedSize(46, 26)
        self.setCursor(Qt.PointingHandCursor)

    def definir(self, valor):
        if self.isChecked() != bool(valor):
            self.blockSignals(True)
            self.setChecked(bool(valor))
            self.blockSignals(False)
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ACENTO) if on else QColor("#3a3a42"))
        p.drawRoundedRect(QRectF(1, 1, 44, 24), 12, 12)
        p.setBrush(QColor("#ffffff") if on else QColor("#c9c9d1"))
        p.drawEllipse(QPointF(33 if on else 13, 13), 8.5, 8.5)


class Miniatura(QLabel):
    """Imagem da janela (prévia) sobre fundo xadrez escuro."""

    def __init__(self, largura, altura, parent=None):
        super().__init__(parent)
        self._lw, self._lh = largura, altura
        self.setFixedSize(largura, altura)
        self.setAlignment(Qt.AlignCenter)
        self._pix = None

    def definir(self, pix):
        self._pix = pix
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#08080a"))
        p.drawRoundedRect(self.rect(), 5, 5)
        passo = 12
        p.setBrush(QColor("#111116"))
        for i in range(0, self._lw, passo):
            for j in range(0, self._lh, passo):
                if (i // passo + j // passo) % 2 == 0:
                    p.drawRect(i, j, passo, passo)
        if self._pix is None or self._pix.isNull():
            p.setPen(QColor("#5b6178"))
            p.drawText(self.rect(), Qt.AlignCenter, "sem prévia")
            return
        alvo = self._pix.size().scaled(self._lw - 16, self._lh - 16, Qt.KeepAspectRatio)
        if alvo.width() > self._pix.width():
            alvo = self._pix.size()
        x, y = (self._lw - alvo.width()) // 2, (self._lh - alvo.height()) // 2
        p.drawPixmap(x, y, alvo.width(), alvo.height(), self._pix)


class Banner(QWidget):
    """Faixa da marca no topo do Inicio (imagem da WolfxRacing com degrade escuro)."""

    def __init__(self, titulo, versao):
        super().__init__()
        self.setFixedHeight(128)
        self._img = QPixmap(str(MARCA_DIR / "banner.jpg"))            # so cenario (sem logo)
        self._logo = QPixmap(str(MARCA_DIR / "logo_wolfxracing.png"))    # logo ORIGINAL, sem alteracao
        self._titulo, self._versao = titulo, versao

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        caminho = QPainterPath()
        caminho.addRoundedRect(QRectF(self.rect()), 6, 6)
        p.setClipPath(caminho)
        if not self._img.isNull():
            esc = self._img.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap((self.width() - esc.width()) // 2, (self.height() - esc.height()) // 2, esc)
        g = QLinearGradient(0, 0, self.width(), 0)
        g.setColorAt(0.0, QColor(0, 0, 0, 215))
        g.setColorAt(0.55, QColor(0, 0, 0, 40))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), g)
        p.setClipping(False)
        p.setPen(QPen(QColor(ACENTO), 2))
        p.drawPath(caminho)
        if not self._logo.isNull():                       # a logo nunca recebe degrade nem recorte
            alt = self.height() - 14
            lg = self._logo.scaledToHeight(alt, Qt.SmoothTransformation)
            p.drawPixmap(self.width() - lg.width() - 18, 7, lg)
        f = QFont("Segoe UI", 18, QFont.Black)
        f.setItalic(True)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(20, 22, self.width() - 40, 40), Qt.AlignLeft | Qt.AlignVCenter, self._titulo.upper())
        f2 = QFont("Segoe UI", 9, QFont.Bold)
        p.setFont(f2)
        p.setPen(QColor(ACENTO))
        p.drawText(QRectF(20, 62, self.width() - 40, 20), Qt.AlignLeft | Qt.AlignVCenter, f"CENTRAL DE CONFIGURAÇÕES  ·  v{self._versao}")


class Central(QWidget):
    """Janela de configuracoes. `janelas`: as janelas do overlay; `acoes`: chave -> QAction marcavel do menu da bandeja."""

    def __init__(self, janelas, acoes, config, ganchos, fonte_demo=None, criar_previa=None, nome_jogo="iRacing", versao=""):
        super().__init__()
        self._nome_jogo, self._versao = nome_jogo, versao
        self.setObjectName("central")
        self.setWindowTitle(f"WolfxRacing · Configurações do overlay ({nome_jogo})")
        self.resize(1120, 720)
        self.setMinimumSize(900, 560)
        self.setStyleSheet(QSS)
        self._fundo = QPixmap(str(MARCA_DIR / "fundo.jpg"))
        if (MARCA_DIR / "logo_wxr.png").exists():
            self.setWindowIcon(QIcon(str(MARCA_DIR / "logo_wxr.png")))
        self.janelas = [j for j in janelas if j.CHAVE in PAINEIS]
        self.acoes, self.config, self.g = acoes, config, ganchos
        self.fonte_demo, self.criar_previa = fonte_demo, criar_previa
        self._previas, self._dados_demo, self._t_demo = {}, None, 0.0
        self._cartoes, self._categoria, self._filtro = {}, "Todos", ""
        self._atual = None
        self._sync = []                                   # (interruptor, getter) a atualizar com o estado real

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._montar_lateral(nome_jogo, versao))
        direita = QVBoxLayout()
        direita.setContentsMargins(26, 18, 26, 14)
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar painéis e opções")
        self.busca.textChanged.connect(self._ao_buscar)
        direita.addWidget(self.busca)
        direita.addSpacing(8)
        direita.addWidget(Banner(f"Overlay {nome_jogo}", versao))      # fixo: nao rola com as paginas
        direita.addSpacing(6)
        self.paginas = QStackedWidget()
        direita.addWidget(self.paginas, 1)
        raiz.addLayout(direita, 1)
        self.p_inicio, self.p_paineis = self._pagina_inicio(), self._pagina_paineis()
        self.p_detalhe, self.p_aparencia = self._pagina_detalhe(), self._pagina_aparencia()
        self.p_perfis = self._pagina_perfis()
        for pg in (self.p_inicio, self.p_paineis, self.p_detalhe, self.p_aparencia, self.p_perfis):
            self.paginas.addWidget(pg)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._ciclo)
        self.ir_para("inicio")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#09090b"))
        if not self._fundo.isNull():
            alvo = self._fundo.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap((self.width() - alvo.width()) // 2, (self.height() - alvo.height()) // 2, alvo)
        p.fillRect(self.rect(), QColor(5, 5, 7, 222))

    # ---------------------------------------------------------------- estrutura
    def _montar_lateral(self, nome_jogo, versao):
        lat = QFrame()
        lat.setObjectName("lateral")
        lat.setFixedWidth(210)
        v = QVBoxLayout(lat)
        v.setContentsMargins(14, 18, 14, 14)
        # identificacao do jogo: logo LOCAL do usuario (marca/jogo_iracing.png ou jogo_lmu.png; nao entra no pacote publico)
        chave = "lmu" if ("lmu" in nome_jogo.lower() or "mans" in nome_jogo.lower()) else "iracing"
        logo_jogo = QPixmap(str(MARCA_DIR / f"jogo_{chave}.png"))
        marca = QLabel()
        marca.setAlignment(Qt.AlignCenter)
        if not logo_jogo.isNull():
            marca.setPixmap(logo_jogo.scaledToWidth(168, Qt.SmoothTransformation))
        else:
            marca.setText("WolfxRacing")
            marca.setObjectName("marca")
        v.addWidget(marca)
        sub = QLabel("OVERLAY" if not logo_jogo.isNull() else f"OVERLAY {nome_jogo.upper()}")
        sub.setObjectName("h2")
        sub.setAlignment(Qt.AlignCenter)
        v.addWidget(sub)
        v.addSpacing(14)
        self._nav = {}
        grupo = QButtonGroup(self)
        for chave, texto in (("inicio", "Início"), ("paineis", "Painéis"), ("aparencia", "Aparência e sistema"),
                             ("perfis", "Perfis")):
            if chave == "perfis" and not self.g.get("modo_perfil"):
                continue
            b = QPushButton(texto)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c=False, c=chave: self.ir_para(c))
            grupo.addButton(b)
            v.addWidget(b)
            self._nav[chave] = b
        v.addStretch(1)
        ver = QLabel(f"v{versao}" if versao else "")
        ver.setObjectName("mudo")
        v.addWidget(ver)
        return lat

    def _pagina(self, titulo, subtitulo=""):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        h = QLabel(titulo)
        h.setObjectName("h1")
        lay.addWidget(h)
        if subtitulo:
            s = QLabel(subtitulo)
            s.setObjectName("mudo")
            s.setWordWrap(True)
            lay.addWidget(s)
        lay.addSpacing(8)
        return w, lay

    def _rolagem(self, conteudo):
        r = QScrollArea()
        r.setWidgetResizable(True)
        r.setWidget(conteudo)
        r.setFrameShape(QFrame.NoFrame)
        r.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return r

    def ir_para(self, chave):
        mapa = {"inicio": 0, "paineis": 1, "detalhe": 2, "aparencia": 3, "perfis": 4}
        self.paginas.setCurrentIndex(mapa[chave])
        if chave in self._nav:
            self._nav[chave].setChecked(True)
        elif chave == "detalhe":
            self._nav["paineis"].setChecked(True)
        self._atualizar_tudo()
        self._ciclo(forcar=True)

    # ---------------------------------------------------------------- estado
    def _janela(self, chave):
        return next((j for j in self.janelas if j.CHAVE == chave), None)

    def _acao(self, chave_acao):
        return self.acoes.get(chave_acao)

    def _ligado(self, j):
        a = self._acao(j.CHAVE_ATIVO)
        return a.isChecked() if a is not None else bool(j.ativo)

    def _definir_ligado(self, j, valor):
        a = self._acao(j.CHAVE_ATIVO)
        if a is not None:
            a.setChecked(bool(valor))
        else:
            j.definir_ativo(bool(valor))
            if self.g.get("salvar"):
                self.g["salvar"]()
        self._atualizar_tudo()

    def _atualizar_tudo(self):
        for chave, c in self._cartoes.items():
            j = self._janela(chave)
            lig = self._ligado(j)
            c["interruptor"].definir(lig)
            c["status"].setText(("<span style='color:#ec1c24'>●</span> Ligado" if lig else "○ Desligado"))
            c["status"].setStyleSheet(f"color: {'#ffffff' if lig else '#8b8b96'}; font-size: 12px; font-weight: 700;")
            c["quadro"].setProperty("ligado", "true" if lig else "false")
            c["quadro"].style().unpolish(c["quadro"])
            c["quadro"].style().polish(c["quadro"])
        for interruptor, getter in self._sync:
            try:
                interruptor.definir(getter())
            except Exception:
                pass
        n = sum(1 for j in self.janelas if self._ligado(j))
        self.lb_ligadas.setText(f"{n} de {len(self.janelas)} ligados")
        travado = self._get_acao("travado", True)
        self.lb_travado.setText("Travadas" if travado else "Destravadas (modo mover)")
        self._filtrar()

    def _get_acao(self, chave, padrao=False):
        a = self._acao(chave)
        return a.isChecked() if a is not None else bool(self.config.get(chave, padrao))

    def _set_acao(self, chave, valor):
        a = self._acao(chave)
        if a is not None:
            a.setChecked(bool(valor))
        else:
            self.config[chave] = bool(valor)
            if self.g.get("salvar"):
                self.g["salvar"]()
        self._atualizar_tudo()

    def _interruptor_acao(self, chave, fixo=False):
        i = Interruptor(self._get_acao(chave))
        i._fixo = fixo
        i.toggled.connect(lambda v, c=chave: self._set_acao(c, v))
        self._sync.append((i, lambda c=chave: self._get_acao(c)))
        return i

    def _linha_opcao(self, rotulo, interruptor, dica=""):
        f = QFrame()
        f.setObjectName("bloco")
        h = QHBoxLayout(f)
        h.setContentsMargins(14, 10, 14, 10)
        col = QVBoxLayout()
        t = QLabel(rotulo)
        col.addWidget(t)
        if dica:
            d = QLabel(dica)
            d.setObjectName("mudo")
            d.setWordWrap(True)
            col.addWidget(d)
        h.addLayout(col, 1)
        h.addWidget(interruptor)
        return f

    # ---------------------------------------------------------------- paginas
    def _pagina_inicio(self):
        w, lay = self._pagina("Início", "Ligue e desligue os painéis, ajuste tamanho e aparência. Tudo se aplica na hora.")
        linha = QHBoxLayout()
        for titulo, attr, acao in (("PAINÉIS", "lb_ligadas", lambda: self.ir_para("paineis")),
                                   ("POSIÇÕES", "lb_travado", lambda: self._set_acao("travado", not self._get_acao("travado", True)))):
            blocoq = QFrame()
            blocoq.setObjectName("bloco")
            v = QVBoxLayout(blocoq)
            v.setContentsMargins(18, 14, 18, 14)
            t = QLabel(titulo)
            t.setObjectName("h2")
            val = QLabel("")
            val.setStyleSheet("font-size: 22px; font-weight: 700;")
            setattr(self, attr, val)
            b = QPushButton("Abrir" if attr == "lb_ligadas" else "Travar / destravar")
            b.setObjectName("link")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c=False, f=acao: f())
            v.addWidget(t)
            v.addWidget(val)
            v.addWidget(b, 0, Qt.AlignLeft)
            linha.addWidget(blocoq, 1)
        lay.addLayout(linha)
        lay.addSpacing(10)
        cab = QHBoxLayout()
        h2 = QLabel("PAINÉIS LIGADOS")
        h2.setObjectName("h2")
        cab.addWidget(h2)
        cab.addStretch(1)
        todos = QPushButton("Ver todos →")
        todos.setObjectName("link")
        todos.setCursor(Qt.PointingHandCursor)
        todos.clicked.connect(lambda: self.ir_para("paineis"))
        cab.addWidget(todos)
        lay.addLayout(cab)
        self._grade_inicio = QGridLayout()
        self._grade_inicio.setSpacing(14)
        cont = QWidget()
        self._cont_inicio = cont
        cont.setLayout(self._grade_inicio)
        lay.addWidget(cont)
        lay.addStretch(1)
        return self._rolagem(w)

    def _pagina_paineis(self):
        w, lay = self._pagina("Painéis", "Ligue um painel aqui; abra \"Personalizar\" para tamanho e opções com a prévia ao lado.")
        chips = QHBoxLayout()
        grupo = QButtonGroup(self)
        for cat in CATEGORIAS:
            b = QPushButton(cat)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(cat == "Todos")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c=False, c=cat: self._ao_categoria(c))
            grupo.addButton(b)
            chips.addWidget(b)
        chips.addStretch(1)
        lay.addLayout(chips)
        self._grade = QGridLayout()
        self._grade.setSpacing(14)
        self._grade.setAlignment(Qt.AlignTop)
        cont = QWidget()
        cont.setLayout(self._grade)
        lay.addWidget(self._rolagem(cont), 1)
        for j in self.janelas:
            self._cartoes[j.CHAVE] = self._criar_cartao(j)
        self._filtrar()
        return w

    def _criar_cartao(self, j, miniatura_largura=236):
        titulo, desc, cat, extras, dica = PAINEIS[j.CHAVE]
        q = QFrame()
        q.setObjectName("cartao")
        q.setProperty("ligado", "false")
        q.setMinimumWidth(258)
        q.setMinimumHeight(236)
        v = QVBoxLayout(q)
        v.setContentsMargins(12, 12, 12, 10)
        mini = Miniatura(miniatura_largura, 96)
        v.addWidget(mini)
        topo = QHBoxLayout()
        t = QLabel(titulo)
        t.setStyleSheet("font-size: 15px; font-weight: 700;")
        topo.addWidget(t, 1)
        sw = Interruptor(self._ligado(j))
        sw.toggled.connect(lambda val, jj=j: self._definir_ligado(jj, val))
        topo.addWidget(sw)
        v.addLayout(topo)
        d = QLabel(desc)
        d.setObjectName("mudo")
        d.setWordWrap(True)
        d.setMinimumHeight(34)
        v.addWidget(d)
        base = QHBoxLayout()
        st = QLabel("")
        base.addWidget(st)
        base.addStretch(1)
        b = QPushButton("Personalizar →")
        b.setObjectName("link")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _c=False, c=j.CHAVE: self.abrir_detalhe(c))
        base.addWidget(b)
        v.addLayout(base)
        return {"quadro": q, "mini": mini, "interruptor": sw, "status": st, "chave": j.CHAVE, "cat": cat, "titulo": titulo,
                "desc": desc}

    def _pagina_detalhe(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        voltar = QPushButton("← Todos os painéis")
        voltar.setObjectName("link")
        voltar.setCursor(Qt.PointingHandCursor)
        voltar.clicked.connect(lambda: self.ir_para("paineis"))
        lay.addWidget(voltar, 0, Qt.AlignLeft)
        self.det_titulo = QLabel("")
        self.det_titulo.setObjectName("h1")
        lay.addWidget(self.det_titulo)
        self.det_dica = QLabel("")
        self.det_dica.setObjectName("mudo")
        self.det_dica.setWordWrap(True)
        lay.addWidget(self.det_dica)
        corpo = QHBoxLayout()
        esq = QVBoxLayout()
        self.det_ligar = Interruptor(False)
        self.det_ligar.toggled.connect(lambda v: self._atual and self._definir_ligado(self._janela(self._atual), v))
        esq.addWidget(self._linha_opcao("Mostrar este painel", self.det_ligar))
        bloco_escala = QFrame()
        bloco_escala.setObjectName("bloco")
        be = QVBoxLayout(bloco_escala)
        be.setContentsMargins(14, 10, 14, 12)
        self.det_lb_escala = QLabel("Tamanho: 100%")
        be.addWidget(self.det_lb_escala)
        self.det_escala = QSlider(Qt.Horizontal)
        self.det_escala.setRange(50, 250)
        self.det_escala.valueChanged.connect(self._ao_escala)
        be.addWidget(self.det_escala)
        esq.addWidget(bloco_escala)
        self.det_extras = QVBoxLayout()
        esq.addLayout(self.det_extras)
        rest = QPushButton("Restaurar tamanho (100%)")
        rest.setObjectName("acao")
        rest.clicked.connect(lambda: self.det_escala.setValue(100))
        esq.addWidget(rest, 0, Qt.AlignLeft)
        esq.addStretch(1)
        ce = QWidget()
        ce.setLayout(esq)
        ce.setFixedWidth(380)
        corpo.addWidget(ce)
        dir_ = QVBoxLayout()
        h = QLabel("PRÉVIA AO VIVO")
        h.setObjectName("h2")
        dir_.addWidget(h)
        self.det_previa = Miniatura(560, 360)
        dir_.addWidget(self.det_previa)
        n = QLabel("Prévia com dados de exemplo. Com o jogo aberto, o painel mostra os dados reais.")
        n.setObjectName("mudo")
        n.setWordWrap(True)
        dir_.addWidget(n)
        dir_.addStretch(1)
        corpo.addLayout(dir_, 1)
        lay.addLayout(corpo, 1)
        return w

    def abrir_detalhe(self, chave):
        j = self._janela(chave)
        if j is None:
            return
        self._atual = None
        titulo, desc, cat, extras, dica = PAINEIS[chave]
        self.det_titulo.setText(titulo)
        self.det_dica.setText(desc + ("  " + dica if dica else ""))
        self.det_ligar.definir(self._ligado(j))
        self.det_escala.blockSignals(True)
        self.det_escala.setValue(int(round(j.escala * 100)))
        self.det_escala.blockSignals(False)
        self.det_lb_escala.setText(f"Tamanho: {int(round(j.escala * 100))}%")
        while self.det_extras.count():
            it = self.det_extras.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._sync = [(i, g) for (i, g) in self._sync if getattr(i, "_fixo", False)]
        for chave_acao, rotulo in extras:
            if self._acao(chave_acao) is None and chave_acao not in self.config:
                continue
            i = self._interruptor_acao(chave_acao)
            self.det_extras.addWidget(self._linha_opcao(rotulo, i))
        if chave == "minimapa" and self.g.get("alcance_minimapa"):
            b = QPushButton(f"Alcance do minimapa: {int(self.config.get('minimapa_raio', 260))} m (clique para trocar)")
            b.setObjectName("acao")
            b.clicked.connect(lambda: (self.g["alcance_minimapa"](), b.setText(
                f"Alcance do minimapa: {int(self.config.get('minimapa_raio', 260))} m (clique para trocar)")))
            self.det_extras.addWidget(b)
        self._atual = chave
        self.ir_para("detalhe")

    def _ao_escala(self, valor):
        if not self._atual:
            return
        j = self._janela(self._atual)
        self.det_lb_escala.setText(f"Tamanho: {valor}%")
        j.definir_escala(valor / 100.0, salvar=False)
        if self.g.get("salvar") and not self.det_escala.isSliderDown():
            self.g["salvar"]()
        p = self._previas.get(self._atual)
        if p is not None:
            p.definir_escala(valor / 100.0, salvar=False)

    def _pagina_aparencia(self):
        w, lay = self._pagina("Aparência e sistema", "Estilo das janelas e comportamento do overlay.")
        blocos = QVBoxLayout()
        h = QLabel("ESTILO")
        h.setObjectName("h2")
        blocos.addWidget(h)
        bo = QFrame()
        bo.setObjectName("bloco")
        v = QVBoxLayout(bo)
        v.setContentsMargins(14, 10, 14, 12)
        self.lb_opac = QLabel("")
        v.addWidget(self.lb_opac)
        self.sl_opac = QSlider(Qt.Horizontal)
        self.sl_opac.setRange(30, 100)
        self.sl_opac.setValue(int(round(float(self.config.get("opacidade_fundo", 0.8)) * 100)))
        self.lb_opac.setText(f"Opacidade do fundo: {self.sl_opac.value()}%")
        self.sl_opac.valueChanged.connect(self._ao_opacidade)
        v.addWidget(self.sl_opac)
        blocos.addWidget(bo)
        for chave, rotulo, dica in (("tema_moderno", "Tema moderno", "Fontes e cantos do estilo atual."),
                                    ("tema_vidro", "Efeito vidro", "Reflexo e brilho nas janelas."),
                                    ("tema_sport", "Estilo Sport", "Itálico e detalhes vermelhos.")):
            if self._acao(chave) is not None:
                blocos.addWidget(self._linha_opcao(rotulo, self._interruptor_acao(chave, True), dica))
        h2 = QLabel("POSIÇÃO E SISTEMA")
        h2.setObjectName("h2")
        blocos.addSpacing(8)
        blocos.addWidget(h2)
        for chave, rotulo, dica in (
                ("travado", "Travar posição", "Travado: os cliques atravessam o overlay. Destrave para mover e redimensionar."),
                ("auto_modo", "Aparecer sozinho ao entrar no carro", "Só com as janelas travadas."),
                ("reforcar_topo", "Manter o overlay por cima do jogo", "Reforça a posição acima do jogo."),
                ("economia_cpu", "Modo economia de CPU", "Metade das atualizações por segundo."),
                ("prioridade_baixa", "Prioridade baixa do overlay", "O jogo tem preferência na CPU."),
                ("teclas_globais", "Teclas de atalho do Stream Deck", "Ctrl+Alt+F13...F24 e Alt+F13...F16.")):
            if self._acao(chave) is not None:
                blocos.addWidget(self._linha_opcao(rotulo, self._interruptor_acao(chave, True), dica))
        if self.g.get("restaurar"):
            b = QPushButton("Restaurar o tamanho de todas as janelas (100%)")
            b.setObjectName("acao")
            b.clicked.connect(lambda: self.g["restaurar"]())
            blocos.addSpacing(6)
            blocos.addWidget(b, 0, Qt.AlignLeft)
        blocos.addStretch(1)
        cont = QWidget()
        cont.setLayout(blocos)
        lay.addWidget(self._rolagem(cont), 1)
        return w

    def _ao_opacidade(self, valor):
        self.lb_opac.setText(f"Opacidade do fundo: {valor}%")
        if self.g.get("opacidade"):
            self.g["opacidade"](valor / 100.0)

    def _pagina_perfis(self):
        w, lay = self._pagina("Perfis", "Cada perfil guarda posição, tamanho e painéis. No automático, o overlay troca pelo tipo de sessão (treino, classificação, corrida).")
        grupo = QButtonGroup(self)
        self._radios = {}
        for modo, texto in (("auto", "Automático (pelo tipo de sessão)"), ("Treino", "Treino"),
                            ("Classificacao", "Classificação"), ("Corrida", "Corrida")):
            r = QRadioButton(texto)
            r.setChecked(self.config.get("perfil_modo", "auto") == modo)
            r.clicked.connect(lambda _c=False, m=modo: self.g["modo_perfil"](m) if self.g.get("modo_perfil") else None)
            grupo.addButton(r)
            lay.addWidget(r)
            self._radios[modo] = r
        self.lb_perfil = QLabel("")
        self.lb_perfil.setObjectName("mudo")
        lay.addWidget(self.lb_perfil)
        if self.g.get("copiar_layout"):
            b = QPushButton("Copiar o layout atual para os outros perfis")
            b.setObjectName("acao")
            b.clicked.connect(lambda: self.g["copiar_layout"]())
            lay.addSpacing(8)
            lay.addWidget(b, 0, Qt.AlignLeft)
        lay.addStretch(1)
        return w

    # ---------------------------------------------------------------- busca / filtro
    def _ao_categoria(self, cat):
        self._categoria = cat
        self._filtrar()

    def _ao_buscar(self, texto):
        self._filtro = texto.strip().lower()
        if self._filtro and self.paginas.currentIndex() != 1:
            self.ir_para("paineis")
        self._filtrar()

    def _filtrar(self):
        visiveis = []
        for chave, c in self._cartoes.items():
            ok = (self._categoria == "Todos" or c["cat"] == self._categoria)
            if self._filtro:
                ok = ok and (self._filtro in c["titulo"].lower() or self._filtro in c["desc"].lower())
            c["quadro"].setVisible(ok)
            if ok:
                visiveis.append(c)
        while self._grade.count():
            self._grade.takeAt(0)
        for k, c in enumerate(visiveis):
            self._grade.addWidget(c["quadro"], k // 3, k % 3)
        # inicio: so os ligados (cartoes proprios, sem interruptor duplicado -> reusa a miniatura)
        if hasattr(self, "_grade_inicio"):
            while self._grade_inicio.count():
                it = self._grade_inicio.takeAt(0)
                w_ = it.widget()
                if w_ is not None:
                    w_.hide()
                    w_.setParent(None)
                    w_.deleteLater()
            ligados = [j for j in self.janelas if self._ligado(j)][:6]
            self._mini_inicio = {}
            for k, j in enumerate(ligados):
                c = self._criar_cartao(j, 236)
                c["interruptor"].definir(True)
                c["quadro"].setProperty("ligado", "true")
                c["quadro"].setMinimumWidth(258)
                self._mini_inicio[j.CHAVE] = c["mini"]
                self._grade_inicio.addWidget(c["quadro"], k // 3, k % 3)
            linhas = (len(ligados) + 2) // 3
            self._cont_inicio.setMinimumHeight(max(1, linhas) * 250)

    # ---------------------------------------------------------------- previas
    def _previa(self, chave):
        p = self._previas.get(chave)
        if p is None and self.criar_previa:
            try:
                p = self.criar_previa(self._janela(chave))
            except Exception:
                p = False
            self._previas[chave] = p
        return p or None

    def _ciclo(self, forcar=False):
        if not self.isVisible() and not forcar:
            return
        # estado real (atalhos/perfis podem ter mudado)
        self._atualizar_estado_leve()
        # dados de exemplo: um quadro novo a cada ciclo
        try:
            self._dados_demo = self.fonte_demo() if self.fonte_demo else None
        except Exception:
            self._dados_demo = None
        pg = self.paginas.currentIndex()
        if pg == 2 and self._atual:
            self.det_previa.definir(self._grab(self._atual))
        elif pg in (0, 1):
            alvo = self._cartoes if pg == 1 else getattr(self, "_mini_inicio", {})
            for chave, c in (self._cartoes.items() if pg == 1 else []):
                if c["quadro"].isVisible():
                    c["mini"].definir(self._grab(chave))
            if pg == 0:
                for chave, mini in getattr(self, "_mini_inicio", {}).items():
                    mini.definir(self._grab(chave))
        elif pg == 4 and hasattr(self, "lb_perfil"):
            self.lb_perfil.setText(f"Perfil ativo: {self.config.get('perfil_ativo', '')}")
            for modo, r in self._radios.items():
                r.setChecked(self.config.get("perfil_modo", "auto") == modo)

    def _atualizar_estado_leve(self):
        for chave, c in self._cartoes.items():
            j = self._janela(chave)
            c["interruptor"].definir(self._ligado(j))
        for interruptor, getter in self._sync:
            try:
                interruptor.definir(getter())
            except Exception:
                pass
        if hasattr(self, "lb_ligadas"):
            n = sum(1 for j in self.janelas if self._ligado(j))
            self.lb_ligadas.setText(f"{n} de {len(self.janelas)} ligados")
            self.lb_travado.setText("Travadas" if self._get_acao("travado", True) else "Destravadas (modo mover)")

    def _grab(self, chave):
        p = self._previa(chave)
        if p is None or self._dados_demo is None:
            return None
        try:
            p.atualizar(self._dados_demo)
            return p.grab()
        except Exception:
            return None

    # ---------------------------------------------------------------- ciclo de vida
    def mostrar(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self._timer.start(500)
        self._atualizar_tudo()
        self._ciclo(forcar=True)

    def closeEvent(self, e):
        self._timer.stop()
        e.accept()
