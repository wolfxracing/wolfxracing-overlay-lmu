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
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSlider,
                               QStackedWidget, QVBoxLayout, QWidget)

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
    "coach": ("Coach ao vivo", "Onde frear, marcha e velocidade no ápice, contra a sua melhor volta (ou uma importada).", "Pilotagem", [], "Grava sozinho a sua primeira volta limpa em cada pista e carro."),
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
    "consumo": ("Consumo por trecho", "Fuel Flow e Burn Zones: consumo agora, por volta e os trechos de maior consumo da pista (indicativo; nao estima economia).", "Carro", [],
                "Precisa de 3 voltas limpas (sem box nem reabastecer) para mapear os trechos. É indicativo: não calcula economia em litros."),
    "delta_trace": ("Delta Trace", "Tempo ganho ou perdido ao longo da volta contra a melhor volta limpa da sessão.", "Pilotagem", [],
                    "Precisa de uma volta limpa completa (sem box) para criar a referência. Ganhar tempo sobe (verde); perder desce (vermelho)."),
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

    def __init__(self, largura, altura, parent=None, flexivel=False):
        super().__init__(parent)
        self._lw, self._lh = largura, altura
        if flexivel:                                  # build l: a previa ocupa o espaco que a janela der (nao corta nem sobra)
            self.setMinimumSize(360, 260)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        else:
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
        self._lw, self._lh = self.width(), self.height()
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
        self._erros_previa = set()
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
        self._timer_previa = QTimer(self)                       # build t: a previa do painel aberto atualiza ~8x por segundo
        self._timer_previa.timeout.connect(self._ciclo_previa)
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
        bloco_op = QFrame()
        bloco_op.setObjectName("bloco")
        bo = QVBoxLayout(bloco_op)
        bo.setContentsMargins(14, 10, 14, 12)
        self.det_lb_op = QLabel("Opacidade do fundo: geral")
        bo.addWidget(self.det_lb_op)
        self.det_op = QSlider(Qt.Horizontal)
        self.det_op.setRange(0, 100)                      # 0 = usa a opacidade geral; 20..100 = propria deste painel
        self.det_op.valueChanged.connect(self._ao_opacidade_painel)
        bo.addWidget(self.det_op)
        esq.addWidget(bloco_op)
        self.det_extras = QVBoxLayout()
        esq.addLayout(self.det_extras)
        rest = QPushButton("Restaurar tamanho (100%)")
        rest.setObjectName("acao")
        rest.clicked.connect(lambda: self.det_escala.setValue(100))
        esq.addWidget(rest, 0, Qt.AlignLeft)
        esq.addStretch(1)
        ce = QWidget()
        ce.setLayout(esq)
        rol = self._rolagem(ce)                                 # build l: com as opcoes do painel a coluna pode passar da altura
        rol.setFixedWidth(404)
        corpo.addWidget(rol)
        dir_ = QVBoxLayout()
        h = QLabel("PRÉVIA AO VIVO")
        h.setObjectName("h2")
        dir_.addWidget(h)
        self.det_previa = Miniatura(560, 360, flexivel=True)
        dir_.addWidget(self.det_previa, 10)
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
        op = (self.config.get("opacidade_painel") or {}).get(chave)
        self.det_op.blockSignals(True)
        self.det_op.setValue(0 if op is None else int(round(float(op) * 100)))
        self.det_op.blockSignals(False)
        self.det_lb_op.setText("Opacidade do fundo: geral" if op is None else f"Opacidade do fundo: {int(round(float(op) * 100))}%")
        while self.det_extras.count():
            it = self.det_extras.takeAt(0)
            if it.widget():
                it.widget().hide()                             # some na hora; o deleteLater so roda no proximo ciclo de eventos
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
        self._opcoes_painel(chave, j)
        self._atual = chave
        self.ir_para("detalhe")

    # ---------------------------------------------------------------- opcoes proprias de cada painel (build l)
    # Toda mudanca vale NA HORA: grava no config, repinta a janela real e a previa, e a previa e redesenhada na mesma hora
    # (sem esperar o ciclo de 500 ms), para o piloto ver o resultado enquanto mexe.
    def _opcoes_painel(self, chave, j):
        self._previa(chave)                                    # cria a previa agora (ela compartilha o dicionario de colunas)
        if chave == "classificacao":
            self._bloco_colunas(chave, j)
        elif chave == "minimapa":
            self._bloco_numeracao(chave)
        elif chave == "delta_trace":
            self._bloco_layout_delta(chave)
            self._bloco_elementos(chave, j)
        elif chave == "principal" and self.g.get("importar_volante"):
            self._bloco_volante(chave)
        if chave not in ("classificacao", "minimapa", "delta_trace") and getattr(type(j), "ELEMENTOS", ()):
            self._bloco_elementos(chave, j)                       # build u: elementos liga/desliga em qualquer painel que os declare

    def _titulo_bloco(self, texto):
        h = QLabel(texto)
        h.setObjectName("h2")
        self.det_extras.addSpacing(6)
        self.det_extras.addWidget(h)

    def _cfg_painel(self, chave, nome, valor):
        """Grava a opcao no config real e na copia usada pela previa."""
        self.config[nome] = valor
        p = self._previas.get(chave)
        if p is not None:
            p.config[nome] = valor

    def _registrar_erro(self, contexto):
        """Erro dentro de um tratamento de excecao: vai para o overlay_log.txt (gancho 'registrar_erro'); sem gancho, para o stderr.
        Nunca levanta: a Central continua funcionando."""
        try:
            gancho = self.g.get("registrar_erro")
            if gancho:
                gancho(contexto)
                return
        except Exception:
            pass
        try:
            import traceback
            sys.stderr.write(contexto + "\n" + traceback.format_exc() + "\n")
        except Exception:
            pass

    def _aplicar_opcao(self, chave):
        for w in (self._janela(chave), self._previas.get(chave)):
            if w is not None:
                try:
                    w.opcoes_mudaram()
                except Exception:
                    self._registrar_erro("Central: opcoes_mudaram() falhou no painel '%s' (%s)" % (chave, type(w).__name__))
        if self.g.get("salvar"):
            self.g["salvar"]()
        if self._atual == chave or self._atual is None:
            self.det_previa.definir(self._grab(chave))        # a previa muda imediatamente

    def _definir_opcao(self, chave, nome, valor):
        self._cfg_painel(chave, nome, valor)
        self._aplicar_opcao(chave)

    # -- Classificacao: colunas
    def _bloco_colunas(self, chave, j):
        grupos = getattr(type(j), "GRUPOS", None)
        if not grupos:
            n = QLabel("As colunas personalizáveis valem para o layout padrão da Classificação.")
            n.setObjectName("mudo")
            n.setWordWrap(True)
            self.det_extras.addWidget(n)
            return
        self._titulo_bloco("COLUNAS DA CLASSIFICAÇÃO")
        dic = self.config.get("classif_colunas")
        if not isinstance(dic, dict):
            dic = self.config["classif_colunas"] = {}
            p = self._previas.get(chave)
            if p is not None:
                p.config["classif_colunas"] = dic
        dica = QLabel("Ligue ou desligue cada coluna e use as setas para mudar a ordem. A prévia ao lado muda na hora.")
        dica.setObjectName("mudo")
        dica.setWordWrap(True)
        self.det_extras.addWidget(dica)
        self._lista_cols = QVBoxLayout()
        self._lista_cols.setSpacing(6)
        cont = QWidget()
        cont.setLayout(self._lista_cols)
        self.det_extras.addWidget(cont)
        self._montar_lista_colunas(chave, j)
        linha = QHBoxLayout()
        b1 = QPushButton("Mostrar todas as colunas")
        b1.setObjectName("acao")
        b1.clicked.connect(lambda: self._todas_colunas(chave))
        b2 = QPushButton("Ordem original")
        b2.setObjectName("acao")
        b2.clicked.connect(lambda: self._ordem_original(chave, j))
        linha.addWidget(b1)
        linha.addWidget(b2)
        linha.addStretch(1)
        cx = QWidget()
        cx.setLayout(linha)
        self.det_extras.addWidget(cx)
        self._bloco_cabecalho(chave, j)

    def _montar_lista_colunas(self, chave, j):
        """(Re)constroi as linhas das colunas na ordem atual: nome, setas para cima/baixo e o liga/desliga."""
        lista = self._lista_cols
        while lista.count():
            it = lista.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().deleteLater()
        dic = self.config.get("classif_colunas") if isinstance(self.config.get("classif_colunas"), dict) else {}
        nomes = {g: r for g, r, _k in type(j).GRUPOS}
        fixas = getattr(type(j), "FIXAS", ())
        ordem = list(j._ordem(self.config))
        self._interruptores_colunas = {}
        for n, gid in enumerate(ordem):
            i = Interruptor(dic.get(gid, True) is not False or gid in fixas)
            i.setEnabled(gid not in fixas)
            i.toggled.connect(lambda v, g=gid: self._ao_coluna(chave, g, v))
            self._interruptores_colunas[gid] = i
            f = QFrame()
            f.setObjectName("bloco")
            h = QHBoxLayout(f)
            h.setContentsMargins(14, 6, 14, 6)
            nome = QLabel(nomes[gid] + ("  (sempre visível)" if gid in fixas else ""))
            nome.setWordWrap(True)
            h.addWidget(nome, 1)
            for texto, passo, ativo in (("▲", -1, n > 0), ("▼", 1, n < len(ordem) - 1)):
                bt = QPushButton(texto)
                bt.setObjectName("acao")
                bt.setFixedSize(34, 30)
                bt.setStyleSheet("padding: 0px; font-size: 11px;")
                bt.setEnabled(ativo)
                bt.setToolTip("Mover para a esquerda" if passo < 0 else "Mover para a direita")
                bt.clicked.connect(lambda _=False, g=gid, p_=passo: self._mover_coluna(chave, j, g, p_))
                h.addWidget(bt)
            h.addWidget(i)
            lista.addWidget(f)

    def _mover_coluna(self, chave, j, gid, passo):
        ordem = list(j._ordem(self.config))
        k = ordem.index(gid)
        novo = k + passo
        if not 0 <= novo < len(ordem):
            return
        ordem[k], ordem[novo] = ordem[novo], ordem[k]
        self._cfg_painel(chave, "classif_ordem", ordem)
        self._montar_lista_colunas(chave, j)
        self._aplicar_opcao(chave)

    def _ordem_original(self, chave, j):
        self._cfg_painel(chave, "classif_ordem", [])
        self._montar_lista_colunas(chave, j)
        self._aplicar_opcao(chave)

    def _bloco_cabecalho(self, chave, j):
        itens = getattr(type(j), "CABECALHO", ())
        if not itens:
            return
        self._titulo_bloco("CABEÇALHO DA CLASSIFICAÇÃO")
        cfg = self.config.get("classif_cabecalho")
        cfg = cfg if isinstance(cfg, dict) else {}
        self._interruptores_cab = {}
        for iid, rotulo in itens:
            i = Interruptor(cfg.get(iid, True) is not False)
            i.toggled.connect(lambda v, k=iid: self._ao_cabecalho(chave, k, v))
            self._interruptores_cab[iid] = i
            self.det_extras.addWidget(self._linha_opcao(rotulo, i))
        b = QPushButton("Mostrar todo o cabeçalho")
        b.setObjectName("acao")
        b.clicked.connect(lambda: self._todo_cabecalho(chave))
        self.det_extras.addWidget(b, 0, Qt.AlignLeft)

    def _ao_cabecalho(self, chave, iid, ligado):
        cfg = dict(self.config.get("classif_cabecalho") if isinstance(self.config.get("classif_cabecalho"), dict) else {})
        if ligado:
            cfg.pop(iid, None)
        else:
            cfg[iid] = False
        self._cfg_painel(chave, "classif_cabecalho", cfg)
        self._aplicar_opcao(chave)

    def _todo_cabecalho(self, chave):
        self._cfg_painel(chave, "classif_cabecalho", {})
        for i in getattr(self, "_interruptores_cab", {}).values():
            i.definir(True)
        self._aplicar_opcao(chave)

    def _ao_coluna(self, chave, gid, ligada):
        dic = self.config.get("classif_colunas")
        if not isinstance(dic, dict):
            dic = self.config["classif_colunas"] = {}
        if ligada:
            dic.pop(gid, None)
        else:
            dic[gid] = False
        p = self._previas.get(chave)
        if p is not None and p.config.get("classif_colunas") is not dic:
            p.config["classif_colunas"] = dic
        self._aplicar_opcao(chave)

    def _todas_colunas(self, chave):
        dic = self.config.get("classif_colunas")
        if isinstance(dic, dict):
            dic.clear()
        for i in getattr(self, "_interruptores_colunas", {}).values():
            i.definir(True)
        self._aplicar_opcao(chave)

    # -- Minimapa: numeracao dos pilotos
    def _bloco_numeracao(self, chave):
        self._titulo_bloco("NUMERAÇÃO DOS PILOTOS")
        quadro = QFrame()
        quadro.setObjectName("bloco")
        lay = QVBoxLayout(quadro)
        lay.setContentsMargins(14, 10, 14, 12)
        t = QLabel("Posição escrita dentro da bolinha de cada carro")
        lay.addWidget(t)
        linha = QHBoxLayout()
        atual = str(self.config.get("minimapa_numeros", "classe")).lower()
        atual = atual if atual in ("classe", "geral") else "off"
        grupo = QButtonGroup(quadro)
        grupo.setExclusive(True)
        self._chips_numeracao = {}
        for valor, rotulo in (("off", "Desligada"), ("classe", "Posição na classe"), ("geral", "Posição geral")):
            b = QPushButton(rotulo)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(valor == atual)
            b.setStyleSheet("padding: 6px 8px;")
            grupo.addButton(b)
            b.clicked.connect(lambda _=False, v=valor: self._definir_opcao(chave, "minimapa_numeros", v))
            self._chips_numeracao[valor] = b
            linha.addWidget(b)
        lay.addLayout(linha)
        dica = QLabel("Em corrida multiclasse, “na classe” mostra a sua colocação dentro de cada classe.")
        dica.setObjectName("mudo")
        dica.setWordWrap(True)
        lay.addWidget(dica)
        self.det_extras.addWidget(quadro)

    # -- Delta Trace: layout do painel (build r)
    def _bloco_layout_delta(self, chave):
        self._titulo_bloco("LAYOUT DO PAINEL")
        quadro = QFrame()
        quadro.setObjectName("bloco")
        lay = QVBoxLayout(quadro)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.addWidget(QLabel("Como o delta é desenhado"))
        linha = QHBoxLayout()
        atual = str(self.config.get("delta_trace_layout", "grafico")).lower()
        atual = atual if atual in ("grafico", "racelab") else "grafico"
        grupo = QButtonGroup(quadro)
        grupo.setExclusive(True)
        self._chips_layout_delta = {}
        for valor, rotulo in (("grafico", "Gráfico ao longo da volta"), ("racelab", "Estilo RaceLab (número grande + barra)")):
            b = QPushButton(rotulo)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(valor == atual)
            b.setStyleSheet("padding: 6px 8px;")
            grupo.addButton(b)
            b.clicked.connect(lambda _=False, v=valor: self._definir_opcao(chave, "delta_trace_layout", v))
            self._chips_layout_delta[valor] = b
            linha.addWidget(b)
        lay.addLayout(linha)
        dica = QLabel("Os blocos por curva e o desenho da pista aparecem nos dois layouts.")
        dica.setObjectName("mudo")
        dica.setWordWrap(True)
        lay.addWidget(dica)
        self.det_extras.addWidget(quadro)

    # -- Delta Trace: elementos do painel (build r), no mesmo esquema das colunas da Classificacao
    def _bloco_elementos(self, chave, j):
        """Elementos liga/desliga do painel (build u; nasceu no Delta Trace, build r). Vale para qualquer janela que declare ELEMENTOS:
        a janela real e a previa mudam na hora e, onde houver secoes, a janela encolhe junto."""
        elementos = getattr(type(j), "ELEMENTOS", ())
        if not elementos:
            return
        titulo = PAINEIS.get(chave, (chave,))[0]
        self._titulo_bloco("ELEMENTOS: " + titulo.upper())
        dica = QLabel("Ligue ou desligue cada elemento. A prévia ao lado e a janela mudam na hora (a janela encolhe junto).")
        dica.setObjectName("mudo")
        dica.setWordWrap(True)
        self.det_extras.addWidget(dica)
        chave_cfg = j._chave_elementos()
        cfg = self.config.get(chave_cfg)
        cfg = cfg if isinstance(cfg, dict) else {}
        self._interruptores_delta = {}
        for eid, rotulo in elementos:
            i = Interruptor(cfg.get(eid, True) is not False)
            i.toggled.connect(lambda v, k=eid: self._ao_elemento(chave, k, v))
            self._interruptores_delta[eid] = i
            self.det_extras.addWidget(self._linha_opcao(rotulo, i))
        b = QPushButton("Mostrar todos os elementos")
        b.setObjectName("acao")
        b.clicked.connect(lambda: self._todos_elementos(chave))
        self.det_extras.addWidget(b, 0, Qt.AlignLeft)

    def _chave_cfg_elementos(self, chave):
        j = self._janela(chave)
        return j._chave_elementos() if j is not None else "elementos_" + chave

    def _ao_elemento(self, chave, eid, ligado):
        nome = self._chave_cfg_elementos(chave)
        cfg = dict(self.config.get(nome) if isinstance(self.config.get(nome), dict) else {})
        if ligado:
            cfg.pop(eid, None)
        else:
            cfg[eid] = False
        self._cfg_painel(chave, nome, cfg)
        self._aplicar_opcao(chave)

    def _todos_elementos(self, chave):
        self._cfg_painel(chave, self._chave_cfg_elementos(chave), {})
        for i in getattr(self, "_interruptores_delta", {}).values():
            i.definir(True)
        self._aplicar_opcao(chave)

    # nomes da build r (os testes antigos e quem os chamava continuam funcionando)
    _bloco_elementos_delta = _bloco_elementos
    _ao_elemento_delta = _ao_elemento
    _todos_elementos_delta = _todos_elementos

    # -- Telemetria: imagem do volante
    def _arquivo_volante(self):
        """Janela de escolha do arquivo (separada para poder ser substituida nos testes)."""
        caminho, _ = QFileDialog.getOpenFileName(self, "Escolher a imagem do volante", "",
                                                 "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)")
        return caminho or None

    def _bloco_volante(self, chave):
        self._titulo_bloco("VOLANTE")
        quadro = QFrame()
        quadro.setObjectName("bloco")
        lay = QVBoxLayout(quadro)
        lay.setContentsMargins(14, 10, 14, 12)
        self._lb_volante = QLabel("")
        self._lb_volante.setWordWrap(True)
        lay.addWidget(self._lb_volante)
        linha = QHBoxLayout()
        b1 = QPushButton("Escolher imagem…")
        b1.setObjectName("acao")
        b1.clicked.connect(lambda: self._ao_escolher_volante(chave))
        self._bt_remover_volante = QPushButton("Voltar ao desenhado")
        self._bt_remover_volante.setObjectName("acao")
        self._bt_remover_volante.clicked.connect(lambda: self._ao_remover_volante(chave))
        linha.addWidget(b1)
        linha.addWidget(self._bt_remover_volante)
        lay.addLayout(linha)
        self._it_giro = Interruptor(bool(self.config.get("volante_imagem_giro", True)))
        self._it_giro.toggled.connect(lambda v: self._definir_opcao(chave, "volante_imagem_giro", bool(v)))
        lay.addWidget(self._linha_opcao("Girar a imagem com o volante", self._it_giro))
        self._lb_tam_volante = QLabel("")
        lay.addWidget(self._lb_tam_volante)
        self._sl_tam_volante = QSlider(Qt.Horizontal)
        self._sl_tam_volante.setRange(50, 200)
        self._sl_tam_volante.setValue(int(self.config.get("volante_imagem_tamanho", 100) or 100))
        self._sl_tam_volante.valueChanged.connect(lambda v: self._ao_tamanho_volante(chave, v))
        lay.addWidget(self._sl_tam_volante)
        nota = QLabel("Use um PNG com fundo transparente, de preferência com o volante visto de frente e o topo para cima. "
                      "A imagem é copiada para a pasta do overlay (no máximo 512 px).")
        nota.setObjectName("mudo")
        nota.setWordWrap(True)
        lay.addWidget(nota)
        self.det_extras.addWidget(quadro)
        self._estado_volante()

    def _estado_volante(self):
        tem = bool(self.config.get("volante_imagem"))
        self._lb_volante.setText("Imagem do volante: " + (str(self.config.get("volante_imagem")).split("/")[-1] if tem
                                                           else "volante desenhado (padrão)"))
        self._bt_remover_volante.setEnabled(tem)
        self._it_giro.setEnabled(tem)
        self._sl_tam_volante.setEnabled(tem)
        v = self._sl_tam_volante.value()
        self._lb_tam_volante.setText(f"Tamanho da imagem: {v}%")

    def _ao_escolher_volante(self, chave):
        caminho = self._arquivo_volante()
        if not caminho:
            return
        try:
            rel = self.g["importar_volante"](caminho)
        except ValueError as e:
            QMessageBox.warning(self, "Volante", str(e))
            return
        self._cfg_painel(chave, "volante_imagem", rel)
        self._estado_volante()
        self._aplicar_opcao(chave)

    def _ao_remover_volante(self, chave):
        if self.g.get("remover_volante"):
            self.g["remover_volante"]()
        self._cfg_painel(chave, "volante_imagem", "")
        self._estado_volante()
        self._aplicar_opcao(chave)

    def _ao_tamanho_volante(self, chave, valor):
        self._lb_tam_volante.setText(f"Tamanho da imagem: {valor}%")
        self._definir_opcao(chave, "volante_imagem_tamanho", int(valor))

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

    def _ao_opacidade_painel(self, valor):
        """v1.7.0: opacidade do fundo so deste painel (0 = volta a usar a geral)."""
        if not self._atual:
            return
        mapa = self.config.get("opacidade_painel")
        if not isinstance(mapa, dict):
            mapa = self.config["opacidade_painel"] = {}
        if valor < 20:
            mapa.pop(self._atual, None)
            self.det_lb_op.setText("Opacidade do fundo: geral")
        else:
            mapa[self._atual] = valor / 100.0
            self.det_lb_op.setText(f"Opacidade do fundo: {valor}%")
        for j in (self._janela(self._atual), self._previas.get(self._atual)):
            if j is not None:
                j._repintar()
        if self.g.get("salvar") and not self.det_op.isSliderDown():
            self.g["salvar"]()

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
                self._registrar_erro("Central: nao foi possivel criar a previa do painel '%s'" % chave)
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

    def _ciclo_previa(self):
        """Previa ao vivo: so na pagina de um painel e com a Central visivel (os cartoes e o inicio seguem no ciclo de 500 ms)."""
        if not self.isVisible() or self.paginas.currentIndex() != 2 or not self._atual:
            return
        try:
            self._dados_demo = self.fonte_demo() if self.fonte_demo else None
        except Exception:
            self._dados_demo = None
        self.det_previa.definir(self._grab(self._atual))

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
            if chave not in self._erros_previa:                  # build t: antes o erro era engolido e a previa ficava em branco
                self._erros_previa.add(chave)
                self._registrar_erro("Central: a previa do painel '%s' falhou ao desenhar" % chave)
            return None

    # ---------------------------------------------------------------- ciclo de vida
    def mostrar(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self._timer.start(500)
        self._timer_previa.start(125)
        self._atualizar_tudo()
        self._ciclo(forcar=True)

    def closeEvent(self, e):
        self._timer.stop()
        self._timer_previa.stop()
        e.accept()
