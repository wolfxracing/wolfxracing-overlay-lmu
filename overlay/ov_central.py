# -*- coding: utf-8 -*-
"""v1.6.0 - Central de configuracoes (janela interativa, no estilo de um painel de controle).

A central NAO tem logica propria: cada botao aciona o mesmo item do menu da bandeja (setChecked dispara o mesmo tratamento),
entao perfis, atalhos do Stream Deck e config.json continuam coerentes. Se este arquivo faltar, o overlay segue com o menu
completo de antes.
"""
import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSlider, QSpinBox,
                               QStackedWidget, QVBoxLayout, QWidget)

try:
    import ov_fov as _fov
except Exception:                                           # sem o modulo, a Central segue sem a calculadora de FOV
    _fov = None

MARCA_DIR = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent) / "marca"      # logo e fundo da WolfxRacing (opcionais)
ACENTO = "#ec1c24"                                         # vermelho da logo
MARCA = "#ec1c24"

# CHAVE da janela -> (titulo, descricao, categoria, extras [(chave da acao no menu, rotulo)], dica)
PAINEIS = {
    "principal": ("Telemetria", "Marcha, velocidade, volante e pedais; painel ou barra horizontal.", "Pilotagem",
                  [("mostrar_grafico", "Gráfico de acelerador e freio"), ("telemetria_barra", "Layout em barra horizontal"),
                   ("telemetria_pisca_limitador", "Limitador de pit pisca o fundo"), ("telemetria_pisca_abs", "ABS pisca fundo e freio"),
                   ("telemetria_pisca_tc", "TC pisca fundo e acelerador")], ""),
    "voltas": ("Voltas e combustível", "Delta, tempos de volta e cálculo de combustível.", "Pilotagem",
               [("mostrar_calc_combustivel", "Cálculo de combustível")], ""),
    "relativo": ("Relativo", "Os carros logo à frente e atrás de você na pista, com diferença de tempo.", "Corrida",
                 [("mostrar_projecao", "Projeção de iRating e SR")], ""),
    "classificacao": ("Classificação", "Todos os carros por posição e classe, com SR, iRating e posições ganhas.", "Corrida",
                      [("classificacao_todas", "Mostrar todas as classes"),
                       ("classif_bandeira_fundo", "Bandeira quadriculada no fundo ao encerrar a sessão"),
                       ("classif_bandeira_coluna", "Bandeira quadriculada ao lado de quem terminou")], ""),
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
    "vazao": ("Mapa de vazão", "Consumo instantâneo (L/h) por faixa de RPM e abertura do acelerador, em mapa de calor.", "Carro",
              [("vazao_valores", "Mostrar o número em cada célula")],
              "O mapa se preenche conforme você dirige; células sem amostra ficam apagadas. Precisa do nível do tanque (igual ao Consumo por trecho)."),
    "marcha_efic": ("Eficiência por marcha", "L/100 km a acelerador pleno em cada marcha e faixa de RPM, com a parcela do tempo em cada uma.", "Carro",
                    [("marcha_destacar", "Destacar a marcha engatada")],
                    "Só conta com acelerador a fundo e acima de 20 km/h; verde = menos combustível por distância."),
    "destino": ("Destino do combustível", "Quanto do combustível foi gasto a fundo, alto, médio, baixo e solto, e em que faixa de RPM.", "Carro",
                [("destino_litros", "Mostrar em litros (em vez de %)")], "É o gasto medido pelo nível do tanque, não uma estimativa de economia."),
    "digiflag": ("Digiflag", "Painel colorido com a bandeira em vigor: verde, amarela, azul, branca, quadriculada...", "Pista",
                 [("digiflag_piscar", "Piscar nas bandeiras de atenção")], "Usa a mesma detecção da janela Bandeiras."),
    "ultrapassagem": ("Alerta de ultrapassagem", "Carros que se aproximam por trás, com diferença em segundos e velocidade de aproximação.", "Automáticos",
                      [("ultrap_auto", "Só aparecer quando houver alerta"), ("ultrap_distante", "Avisar mais cedo (5 s em vez de 3 s)"),
                       ("ultrap_so_outras", "Só carros de outras classes"), ("ultrap_so_mesma_volta", "Ignorar carros de outra volta")],
                      "Precisa da janela de relativo do jogo ativa (iRacing) ou da classificação (LMU)."),
    "calendario": ("Calendário de corridas", "Próximas corridas do cronograma do iRacing (com os seus filtros e aviso) ou do seu calendario_corridas.csv, com contagem regressiva.", "Corrida",
                   [("calendario_24h", "Horário em 24 horas")],
                   "Use o botão acima para escolher série, pista, carro, classe e horário e ser avisado. Sem filtros, vale o CSV (modelo: calendario_exemplo.csv)."),
    "hibrido": ("Energia híbrida (Boost)", "Carga da bateria, uso do deploy e valores da volta anterior.", "Carro",
                [("hibrido_alerta", "Piscar com a bateria abaixo de 15%")], "Só mostra dados quando o carro e o jogo informam o sistema híbrido."),
    "coach_pedais": ("Pedais do Coach", "O que fazer agora com os pedais: freie (com % alvo), trail braking, solte o acelerador, acelere. Barras com a sua % ao vivo e a marca da referência.", "Pilotagem",
                     [], "Arraste com a janela destravada ou use 'Centralizar' no menu da bandeja. Usa a mesma referência do Coach ao vivo."),
    "sessao": ("Tempo da sessão", "Tempo ou voltas restantes com barra de progresso.", "Corrida",
               [("sessao_hms", "Sempre em h:mm:ss")], ""),
    "lmu_energia": ("Energia e combustível (LMU)", "Energia virtual, consumo por volta e voltas até o fim.", "Carro", [], ""),
    "lmu_alertas": ("Alertas na pista (LMU)", "Amarelas, limite dos boxes e classe rápida chegando.", "Automáticos", [], ""),
    "lmu_stints": ("Stints (LMU)", "Histórico de stints: voltas, energia e combustível.", "Corrida", [], ""),
    "lmu_tendencia": ("Tendência de ritmo (LMU)", "Ritmo das últimas voltas limpas.", "Corrida", [], ""),
}
CATEGORIAS = ("Todos", "Pilotagem", "Corrida", "Carro", "Pista", "Automáticos")

TEMAS_CENTRAL = {
    "classico": {"nome": "Clássico escuro", "acento": "#ec1c24", "rgb": (236, 28, 36), "base": "#09090b", "fundo": None, "veu": 222,
                 "cartao": "rgba(16,16,19,225)", "borda": "#2c2c33", "lateral": "rgba(0,0,0,215)", "ligado_borda": "#b3141b",
                 "chip": "rgba(14,14,17,200)", "campo": "rgba(12,12,15,225)", "brilho": 0},
    "grafite": {"nome": "Vidro grafite", "acento": "#ec1c24", "rgb": (236, 28, 36), "base": "#0c0d11", "fundo": ((30, 33, 42), (11, 12, 16), (36, 17, 21)), "veu": 120,
                "cartao": "rgba(255,255,255,17)", "borda": "rgba(255,255,255,46)", "lateral": "rgba(255,255,255,12)", "ligado_borda": "rgba(236,28,36,200)",
                "chip": "rgba(255,255,255,14)", "campo": "rgba(0,0,0,90)", "brilho": 40},
    "gelo": {"nome": "Vidro gelo", "acento": "#3fb6ff", "rgb": (63, 182, 255), "base": "#08121c", "fundo": ((24, 58, 86), (8, 18, 30), (22, 52, 78)), "veu": 90,
             "cartao": "rgba(190,225,255,24)", "borda": "rgba(190,225,255,72)", "lateral": "rgba(190,225,255,16)", "ligado_borda": "rgba(63,182,255,210)",
             "chip": "rgba(190,225,255,18)", "campo": "rgba(0,12,24,110)", "brilho": 56},
    "ambar": {"nome": "Vidro âmbar", "acento": "#ffb020", "rgb": (255, 176, 32), "base": "#100b07", "fundo": ((52, 32, 14), (16, 11, 8), (58, 24, 12)), "veu": 100,
              "cartao": "rgba(255,205,140,21)", "borda": "rgba(255,205,130,64)", "lateral": "rgba(255,205,140,14)", "ligado_borda": "rgba(255,176,32,210)",
              "chip": "rgba(255,205,140,16)", "campo": "rgba(20,10,0,110)", "brilho": 44},
}


def gerar_qss(t):
    ACENTO = t["acento"]
    R, G, Bz = t["rgb"]
    base, lateral, cartao, borda = t["base"], t["lateral"], t["cartao"], t["borda"]
    ligado_borda, chip, campo = t["ligado_borda"], t["chip"], t["campo"]
    return f"""
QWidget#central {{ background: {base}; color: #f2f2f4; font-family: 'Segoe UI', 'Inter', sans-serif; }}
QFrame#lateral {{ background: {lateral}; border-right: 2px solid {ACENTO}; }}
QLabel {{ color: #f2f2f4; background: transparent; }}
QLabel#h1 {{ font-size: 26px; font-weight: 800; letter-spacing: 0.5px; }}
QLabel#h2 {{ font-size: 11px; font-weight: 800; color: {ACENTO}; letter-spacing: 2px; }}
QLabel#mudo {{ color: #9a9aa6; font-size: 12px; }}
QLabel#marca {{ font-size: 17px; font-weight: 800; letter-spacing: 1px; color: #ffffff; }}
QPushButton#nav {{ text-align: left; padding: 11px 16px; border: 1px solid transparent; border-radius: 12px; color: #b9bccb; font-size: 14px; font-weight: 600; background: transparent; }}
QPushButton#nav:hover {{ background: rgba(255,255,255,16); color: #fff; }}
QPushButton#nav:checked {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba({R},{G},{Bz},110), stop:1 rgba({R},{G},{Bz},18)); color: #fff; border: 1px solid rgba({R},{G},{Bz},150); }}
QPushButton#chip {{ padding: 6px 16px; border: 1px solid rgba(255,255,255,40); border-radius: 15px; color: #c9c9d1; background: {chip}; font-weight: 600; }}
QPushButton#chip:hover {{ border-color: {ACENTO}; }}
QPushButton#chip:checked {{ background: {ACENTO}; color: #ffffff; border-color: {ACENTO}; font-weight: 800; }}
QPushButton#link {{ border: none; color: {ACENTO}; text-align: right; background: transparent; font-size: 12px; font-weight: 700; }}
QPushButton#link:hover {{ color: #fff; }}
QPushButton#acao {{ padding: 9px 18px; border: 1px solid {ACENTO}; border-radius: 12px; background: rgba({R},{G},{Bz},35); color: #fff; font-weight: 700; }}
QPushButton#acao:hover {{ background: {ACENTO}; }}
QFrame#cartao {{ background: {cartao}; border: 1px solid {borda}; border-radius: 14px; }}
QFrame#cartao[ligado="true"] {{ border: 1px solid {ligado_borda}; }}
QFrame#bloco {{ background: {cartao}; border: 1px solid {borda}; border-radius: 14px; }}
QLineEdit {{ background: {campo}; border: 1px solid rgba(255,255,255,36); border-radius: 14px; padding: 10px 16px; color: #f2f2f4; }}
QLineEdit:focus {{ border: 1px solid {ACENTO}; }}
QComboBox, QDoubleSpinBox, QSpinBox {{ background: {campo}; border: 1px solid #34343c; border-radius: 4px; padding: 6px 10px; color: #f2f2f4; min-height: 20px; }}
QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{ border: 1px solid {ACENTO}; }}
QComboBox QAbstractItemView {{ background: #14141a; color: #f2f2f4; selection-background-color: {ACENTO}; border: 1px solid #34343c; }}
QLabel#numero {{ font-size: 20px; font-weight: 800; }}
QLabel#numero_g {{ font-size: 30px; font-weight: 800; color: {ACENTO}; }}
QPushButton#pilula {{ padding: 6px 16px; border: 1px solid rgba(255,255,255,38); border-radius: 12px; background: rgba(255,255,255,10); color: #c4c7d4; font-size: 12px; font-weight: 700; letter-spacing: 0.5px; }}
QPushButton#pilula:hover {{ border: 1px solid rgba({R},{G},{Bz},170); color: #fff; }}
QPushButton#pilula[ativo="true"] {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba({R},{G},{Bz},235), stop:1 rgba({R},{G},{Bz},120)); border: 1px solid {ACENTO}; color: #ffffff; }}
QFrame#cartao_g {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(255,255,255,26), stop:1 rgba(255,255,255,8)); border: 1px solid rgba(255,255,255,34); border-radius: 18px; }}
QFrame#cartao_g:hover {{ border: 1px solid rgba({R},{G},{Bz},150); }}
QFrame#cartao_g[ligado="true"] {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba({R},{G},{Bz},64), stop:0.55 rgba(255,255,255,12), stop:1 rgba(255,255,255,8)); border: 1px solid {ACENTO}; }}
QLabel#etiqueta {{ color: #7f8499; font-size: 10px; font-weight: 800; letter-spacing: 2px; }}
QPushButton#fantasma {{ padding: 6px 14px; border: 1px solid rgba({R},{G},{Bz},130); border-radius: 13px; background: rgba({R},{G},{Bz},26); color: #ffffff; font-size: 12px; font-weight: 700; }}
QPushButton#fantasma:hover {{ background: {ACENTO}; border: 1px solid {ACENTO}; }}
QSlider::groove:horizontal {{ height: 4px; background: #34343c; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACENTO}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #fff; border: 3px solid {ACENTO}; width: 12px; height: 12px; margin: -8px 0; border-radius: 9px; }}
QRadioButton {{ color: #f2f2f4; spacing: 10px; padding: 6px 0; font-size: 14px; font-weight: 600; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,48); border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACENTO}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


_TEMA = TEMAS_CENTRAL["classico"]
QSS = gerar_qss(_TEMA)


def definir_tema_central(nome):
    """Troca o tema visual da Central (globais lidas na hora de pintar). Nome desconhecido = classico."""
    global ACENTO, QSS, _TEMA
    _TEMA = TEMAS_CENTRAL.get(nome) or TEMAS_CENTRAL["classico"]
    ACENTO = _TEMA["acento"]
    QSS = gerar_qss(_TEMA)
    return QSS



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

    pressionado = Signal(float, float)        # build at: posicao no pixmap (px da imagem) onde o mouse foi pressionado
    arrastado = Signal(float, float)          # deslocamento acumulado desde o clique (px da imagem)
    solto = Signal()

    def __init__(self, largura, altura, parent=None, flexivel=False, galeria=False):
        super().__init__(parent)
        self._arrastavel = False
        self._ini = None
        self._lw, self._lh = largura, altura
        self._galeria = galeria
        if galeria:                                   # build ac: cartao de galeria (foto de fundo, previa centrada, texto por cima)
            self.setMinimumSize(10, 172)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        elif flexivel:                                  # build l: a previa ocupa o espaco que a janela der (nao corta nem sobra)
            self.setMinimumSize(360, 260)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        else:
            self.setFixedSize(largura, altura)
        self.setAlignment(Qt.AlignCenter)
        self._pix = None

    def definir(self, pix):
        self._pix = pix
        self.update()

    def definir_arrastavel(self, v):
        self._arrastavel = bool(v)
        self.setCursor(Qt.OpenHandCursor if v else Qt.ArrowCursor)
        self.setToolTip("Arraste um item da prévia para mover (qualquer direção)." if v else "")

    def _escala_img(self):
        """(x0, y0, fator): onde a imagem aparece no widget e quantos px do widget valem 1 px da imagem."""
        if self._pix is None or self._pix.isNull():
            return None
        alvo = self._pix.size().scaled(self.width() - 16, self.height() - 16, Qt.KeepAspectRatio)
        if alvo.width() > self._pix.width():
            alvo = self._pix.size()
        return ((self.width() - alvo.width()) / 2.0, (self.height() - alvo.height()) / 2.0, alvo.width() / float(self._pix.width()))

    def mousePressEvent(self, e):
        r = self._escala_img() if self._arrastavel and e.button() == Qt.LeftButton else None
        if r is None:
            return super().mousePressEvent(e)
        x0, y0, f = r
        pos = e.position()
        self._ini = (pos.x(), pos.y(), f)
        self.setCursor(Qt.ClosedHandCursor)
        self.pressionado.emit((pos.x() - x0) / f, (pos.y() - y0) / f)

    def mouseMoveEvent(self, e):
        if self._ini is None:
            return super().mouseMoveEvent(e)
        x, y, f = self._ini
        pos = e.position()
        self.arrastado.emit((pos.x() - x) / f, (pos.y() - y) / f)

    def mouseReleaseEvent(self, e):
        if self._ini is None:
            return super().mouseReleaseEvent(e)
        self._ini = None
        self.setCursor(Qt.OpenHandCursor if self._arrastavel else Qt.ArrowCursor)
        self.solto.emit()

    def _pintar_galeria(self):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        R, G, Bz = _TEMA["rgb"]
        caminho = QPainterPath()
        caminho.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 14, 14)
        p.setClipPath(caminho)
        fundo = QLinearGradient(0, 0, 0, h)
        fundo.setColorAt(0.0, QColor(8, 10, 16))
        fundo.setColorAt(1.0, QColor(18 + R // 18, 14 + G // 24, 24 + Bz // 24))
        p.fillRect(0, 0, w, h, fundo)
        brilho = QRadialGradient(w / 2, h * 0.55, max(w, h) * 0.55)
        brilho.setColorAt(0.0, QColor(R, G, Bz, 46))
        brilho.setColorAt(1.0, QColor(R, G, Bz, 0))
        p.fillRect(0, 0, w, h, brilho)
        p.setPen(QColor(255, 255, 255, 14))
        for x in range(10, w, 16):
            for y in range(10, h, 16):
                p.drawPoint(x, y)
        if self._pix is None or self._pix.isNull():
            p.setPen(QColor("#6f7690"))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "sem prévia")
            return
        alvo = self._pix.size().scaled(max(10, w - 28), max(10, h - 44), Qt.KeepAspectRatio)
        if alvo.width() > self._pix.width():
            alvo = self._pix.size()
        p.drawPixmap((w - alvo.width()) // 2, (h - alvo.height()) // 2 + 8, alvo.width(), alvo.height(), self._pix)

    def paintEvent(self, _e):
        if self._galeria:
            self._pintar_galeria()
            return
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
        self.resize(1280, 780)
        self.setMinimumSize(900, 560)
        definir_tema_central(config.get("central_tema", "classico"))
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
        self.p_fov = self._pagina_fov()
        for pg in (self.p_inicio, self.p_paineis, self.p_detalhe, self.p_aparencia, self.p_perfis, self.p_fov):
            self.paginas.addWidget(pg)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._ciclo)
        self._timer_previa = QTimer(self)                       # build t: a previa do painel aberto atualiza ~8x por segundo
        self._timer_previa.timeout.connect(self._ciclo_previa)
        self.ir_para("inicio")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_rolagem_paineis") and self.paginas.currentIndex() == 1:
            QTimer.singleShot(0, self._filtrar)               # numero de colunas da galeria acompanha a largura

    def paintEvent(self, _e):
        p = QPainter(self)
        t = _TEMA
        p.fillRect(self.rect(), QColor(t["base"]))
        if t["fundo"]:                                          # tema de vidro: gradiente diagonal + brilho no topo (sem depender de imagem)
            g = QLinearGradient(0, 0, self.width(), self.height())
            g.setColorAt(0.0, QColor(*t["fundo"][0]))
            g.setColorAt(0.55, QColor(*t["fundo"][1]))
            g.setColorAt(1.0, QColor(*t["fundo"][2]))
            p.fillRect(self.rect(), g)
        if not self._fundo.isNull():
            alvo = self._fundo.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.setOpacity(1.0 if not t["fundo"] else 0.35)
            p.drawPixmap((self.width() - alvo.width()) // 2, (self.height() - alvo.height()) // 2, alvo)
            p.setOpacity(1.0)
        p.fillRect(self.rect(), QColor(5, 5, 7, t["veu"]))
        if t["brilho"]:
            r = QLinearGradient(0, 0, 0, self.height() * 0.45)
            r.setColorAt(0.0, QColor(255, 255, 255, t["brilho"]))
            r.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(0, 0, self.width(), int(self.height() * 0.45), r)

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
                             ("fov", "Calculadora de FOV"), ("perfis", "Perfis")):
            if chave == "perfis" and not self.g.get("modo_perfil"):
                continue
            if chave == "fov" and _fov is None:
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
        mapa = {"inicio": 0, "paineis": 1, "detalhe": 2, "aparencia": 3, "perfis": 4, "fov": 5}
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
            _R, _G, _B = _TEMA["rgb"]
            c["status"].setText("●  LIGADO" if lig else "○  DESLIGADO")
            if c["quadro"].objectName() == "cartao_g":
                c["status"].setStyleSheet(
                    f"color: {ACENTO if lig else '#9096aa'}; font-size: 10px; font-weight: 800; letter-spacing: 1px; padding: 4px 10px; border-radius: 11px;"
                    f"background: rgba({_R},{_G},{_B},{50 if lig else 0}); border: 1px solid {ACENTO if lig else 'rgba(255,255,255,40)'};")
            else:
                c["status"].setStyleSheet(f"color: {'#ffffff' if lig else '#8b8b96'}; font-size: 12px; font-weight: 700;")
            c["quadro"].setProperty("ligado", "true" if lig else "false")
            c["quadro"].style().unpolish(c["quadro"])
            c["quadro"].style().polish(c["quadro"])
            it = getattr(self, "_itens_lista", {}).get(chave)
            if it is not None:
                it["ponto"].setText("<span style='color:%s'>●</span>" % ACENTO if lig else "")
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
        # filtros por categoria em pilulas (clique filtra; "Todos" limpa)
        self._cab_categoria, self._itens_lista = {}, {}
        faixa = QHBoxLayout()
        faixa.setSpacing(8)
        for cat in CATEGORIAS:
            n = len(self.janelas) if cat == "Todos" else sum(1 for j in self.janelas if PAINEIS[j.CHAVE][2] == cat)
            if cat != "Todos" and n == 0:
                continue
            cab = QPushButton(("TODOS" if cat == "Todos" else cat.upper()) + f"  {n}")
            cab.setObjectName("pilula")
            cab.setCursor(Qt.PointingHandCursor)
            cab.setProperty("ativo", "true" if cat == "Todos" else "false")
            cab.clicked.connect(lambda _c=False, k=cat: self._ao_categoria(k))
            self._cab_categoria[cat] = cab
            faixa.addWidget(cab)
        faixa.addStretch(1)
        lay.addLayout(faixa)
        corpo = QHBoxLayout()
        corpo.setSpacing(14)
        self._grade = QGridLayout()
        self._grade.setSpacing(14)
        self._grade.setAlignment(Qt.AlignTop)
        cont = QWidget()
        cont.setLayout(self._grade)
        self._rolagem_paineis = self._rolagem(cont)
        corpo.addWidget(self._rolagem_paineis, 1)
        lay.addLayout(corpo, 1)
        for j in self.janelas:
            self._cartoes[j.CHAVE] = self._criar_cartao(j, 236, galeria=True)
        self._filtrar()
        return w

    def _criar_cartao_galeria(self, j):
        """Cartao moderno: poco escuro com a previa, pilula de estado e chave no topo, titulo, descricao e acao."""
        titulo, desc, cat, extras, dica = PAINEIS[j.CHAVE]
        q = QFrame()
        q.setObjectName("cartao_g")
        q.setProperty("ligado", "false")
        q.setMinimumWidth(250)
        v = QVBoxLayout(q)
        v.setContentsMargins(10, 10, 10, 12)
        v.setSpacing(8)
        mini = Miniatura(0, 0, galeria=True)
        topo_g = QGridLayout()
        topo_g.setContentsMargins(0, 0, 0, 0)
        topo_g.addWidget(mini, 0, 0)
        sobre = QWidget()
        sobre.setAttribute(Qt.WA_TranslucentBackground)
        sv = QHBoxLayout(sobre)
        sv.setContentsMargins(10, 10, 10, 0)
        st = QLabel("")
        sv.addWidget(st, 0, Qt.AlignTop)
        sv.addStretch(1)
        sw = Interruptor(self._ligado(j))
        sw.toggled.connect(lambda val, jj=j: self._definir_ligado(jj, val))
        sv.addWidget(sw, 0, Qt.AlignTop)
        topo_g.addWidget(sobre, 0, 0)
        v.addLayout(topo_g)
        txt = QVBoxLayout()
        txt.setContentsMargins(6, 2, 6, 0)
        txt.setSpacing(3)
        et = QLabel(cat.upper())
        et.setObjectName("etiqueta")
        txt.addWidget(et)
        t = QLabel(titulo)
        t.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        txt.addWidget(t)
        d = QLabel(desc if len(desc) <= 84 else desc[:81].rstrip() + "…")
        d.setToolTip(desc)
        d.setWordWrap(True)
        d.setMinimumHeight(self.fontMetrics().lineSpacing() * 2 + 6)
        d.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        d.setStyleSheet("color: #aab0c2; font-size: 11px;")
        txt.addWidget(d)
        v.addLayout(txt, 1)
        rod = QHBoxLayout()
        rod.setContentsMargins(6, 0, 4, 0)
        rod.addStretch(1)
        b = QPushButton("Personalizar  ›")
        b.setObjectName("fantasma")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _c=False, c=j.CHAVE: self.abrir_detalhe(c))
        rod.addWidget(b)
        v.addLayout(rod)
        return {"quadro": q, "mini": mini, "interruptor": sw, "status": st, "chave": j.CHAVE, "cat": cat, "titulo": titulo, "desc": desc}

    def _criar_cartao(self, j, miniatura_largura=236, galeria=False):
        if galeria:
            return self._criar_cartao_galeria(j)
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
        self.det_previa.pressionado.connect(self._arrasto_ini)
        self.det_previa.arrastado.connect(self._arrasto_mov)
        self.det_previa.solto.connect(self._arrasto_fim)
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
        lmu = "lmu" in self._nome_jogo.lower() or "mans" in self._nome_jogo.lower()
        for chave_acao, rotulo in extras:
            if self._acao(chave_acao) is None and chave_acao not in self.config:
                continue
            if lmu and chave_acao in ("classif_bandeira_fundo", "classif_bandeira_coluna"):      # build am: so a classificacao do iRacing tem a bandeira
                continue
            i = self._interruptor_acao(chave_acao)
            self.det_extras.addWidget(self._linha_opcao(rotulo, i))
        if chave == "minimapa" and self.g.get("alcance_minimapa"):
            b = QPushButton(f"Alcance do minimapa: {int(self.config.get('minimapa_raio', 260))} m (clique para trocar)")
            b.setObjectName("acao")
            b.clicked.connect(lambda: (self.g["alcance_minimapa"](), b.setText(
                f"Alcance do minimapa: {int(self.config.get('minimapa_raio', 260))} m (clique para trocar)")))
            self.det_extras.addWidget(b)
        if chave == "calendario" and self.g.get("cronograma_filtros"):
            b = QPushButton("Cronograma do iRacing: filtros e avisos…")
            b.setObjectName("acao")
            b.clicked.connect(lambda: self.g["cronograma_filtros"]())
            self.det_extras.addWidget(b)
            if self.g.get("cronograma_importar"):
                b2 = QPushButton("Importar novo cronograma (PDF)…")
                b2.setObjectName("acao")
                b2.clicked.connect(lambda: self.g["cronograma_importar"]())
                self.det_extras.addWidget(b2)
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
            self._bloco_posicao_fonte(chave, j)                   # build au: posicao e estilo dos itens (sem o liga/desliga, que as colunas ja tem)
        elif chave == "minimapa":
            self._bloco_numeracao(chave)
            self._bloco_elementos(chave, j)                       # build av: itens do Minimapa
        elif chave == "delta_trace":
            self._bloco_layout_delta(chave)
            self._bloco_elementos(chave, j)
        elif chave == "principal":
            self._bloco_ordem_telemetria(chave, j)                # build as: ordem dos itens da Telemetria
            if self.g.get("importar_volante"):
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

    def _aplicar_opcao(self, chave, salvar=True):
        for w in (self._janela(chave), self._previas.get(chave)):
            if w is not None:
                try:
                    w.opcoes_mudaram()
                except Exception:
                    self._registrar_erro("Central: opcoes_mudaram() falhou no painel '%s' (%s)" % (chave, type(w).__name__))
        if salvar and self.g.get("salvar"):
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

    # -- Telemetria: ordem dos itens (build as)
    def _bloco_ordem_telemetria(self, chave, j):
        if not hasattr(type(j), "ordem_blocos"):
            return
        self._titulo_bloco("ORDEM DOS ITENS DA TELEMETRIA")
        dica = QLabel("Use as setas para mudar a posição de cada item (por exemplo, volante à direita e pedais entre a marcha e o volante). "
                      "A prévia ao lado muda na hora. Cada layout tem a sua própria ordem.")
        dica.setObjectName("mudo")
        dica.setWordWrap(True)
        self.det_extras.addWidget(dica)
        barra_em_uso = bool(self.config.get("telemetria_barra", False))
        self._listas_ordem = {}
        for barra in (barra_em_uso, not barra_em_uso):
            self.det_extras.addWidget(self._rotulo_mudo("Layout em barra" if barra else "Layout em painel"))
            lay = QVBoxLayout()
            lay.setSpacing(6)
            cont = QWidget()
            cont.setLayout(lay)
            self.det_extras.addWidget(cont)
            self._listas_ordem[barra] = lay
            self._montar_lista_ordem(chave, j, barra)
        b = QPushButton("Ordem original")
        b.setObjectName("acao")
        b.clicked.connect(lambda: self._ordem_original_telemetria(chave, j))
        self.det_extras.addWidget(b, 0, Qt.AlignLeft)

    def _rotulo_mudo(self, texto):
        r = QLabel(texto)
        r.setObjectName("mudo")
        return r

    def _montar_lista_ordem(self, chave, j, barra):
        lista = self._listas_ordem[barra]
        while lista.count():
            it = lista.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().deleteLater()
        cls = type(j)
        nomes = dict(cls.BLOCOS_BARRA if barra else cls.BLOCOS_PAINEL)
        ordem = list(cls.ordem_blocos(self.config, barra))
        for n, bid in enumerate(ordem):
            f = QFrame()
            f.setObjectName("bloco")
            h = QHBoxLayout(f)
            h.setContentsMargins(14, 6, 14, 6)
            h.addWidget(QLabel("%d.  %s" % (n + 1, nomes[bid])), 1)
            for texto, passo, ativo in (("◀", -1, n > 0), ("▶", 1, n < len(ordem) - 1)):
                bt = QPushButton(texto)
                bt.setObjectName("acao")
                bt.setFixedSize(34, 30)
                bt.setStyleSheet("padding: 0px; font-size: 11px;")
                bt.setEnabled(ativo)
                bt.setToolTip("Mover para a esquerda" if passo < 0 else "Mover para a direita")
                bt.clicked.connect(lambda _=False, g=bid, p_=passo, b_=barra: self._mover_item_telemetria(chave, j, b_, g, p_))
                h.addWidget(bt)
            lista.addWidget(f)

    def _mover_item_telemetria(self, chave, j, barra, bid, passo):
        cls = type(j)
        ordem = list(cls.ordem_blocos(self.config, barra))
        k = ordem.index(bid)
        novo = k + passo
        if not 0 <= novo < len(ordem):
            return
        ordem[k], ordem[novo] = ordem[novo], ordem[k]
        self._cfg_painel(chave, cls.CHAVE_ORDEM_BARRA if barra else cls.CHAVE_ORDEM_PAINEL, ordem)
        self._montar_lista_ordem(chave, j, barra)
        self._aplicar_opcao(chave)

    def _ordem_original_telemetria(self, chave, j):
        cls = type(j)
        self._cfg_painel(chave, cls.CHAVE_ORDEM_BARRA, [])
        self._cfg_painel(chave, cls.CHAVE_ORDEM_PAINEL, [])
        for barra in (True, False):
            if barra in getattr(self, "_listas_ordem", {}):
                self._montar_lista_ordem(chave, j, barra)
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
        linha = QVBoxLayout()                                 # build w: um chip embaixo do outro (lado a lado passavam da coluna de 404 px)
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
        depende = getattr(type(j), "DEPENDE", {})
        nomes = dict(elementos)
        for eid, rotulo in elementos:
            i = Interruptor(cfg.get(eid, True) is not False)
            i.toggled.connect(lambda v, k=eid: self._ao_elemento(chave, k, v))
            self._interruptores_delta[eid] = i
            dica_dep = None
            if eid in depende:                                     # build av: dependencia explicita (o item e desenhado dentro do outro)
                rotulo = "↳ " + rotulo
                dica_dep = f"Depende de: {nomes.get(depende[eid], depende[eid])} (fica desabilitado enquanto ele estiver desligado)"
            linha = self._linha_opcao(rotulo, i)
            if dica_dep:
                linha.setToolTip(dica_dep)
                i.setToolTip(dica_dep)
            self.det_extras.addWidget(linha)
        self._depende = dict(depende)
        self._atualiza_dependentes()
        b = QPushButton("Mostrar todos os elementos")
        b.setObjectName("acao")
        b.clicked.connect(lambda: self._todos_elementos(chave))
        self.det_extras.addWidget(b, 0, Qt.AlignLeft)
        self._bloco_posicao_fonte(chave, j)

    # -- posicao (arrastar) e fonte de cada elemento (build at)
    def _chave_pos(self, chave):
        return self._chave_cfg_elementos(chave) + "_pos"

    def _chave_estilo(self, chave):
        return self._chave_cfg_elementos(chave) + "_estilo"

    ESTILOS_FONTE = (("Padrão", (None, None)), ("Normal", (False, False)), ("Negrito", (True, False)),
                     ("Itálico", (False, True)), ("Negrito itálico", (True, True)))

    def _estilo_de(self, chave, eid):
        d = self.config.get(self._chave_estilo(chave))
        e = d.get(eid) if isinstance(d, dict) else None
        return dict(e) if isinstance(e, dict) else {}

    def _bloco_posicao_fonte(self, chave, j):
        elementos = getattr(type(j), "ELEMENTOS", ())
        self._titulo_bloco("POSIÇÃO E ESTILO DOS ITENS")
        dica = QLabel("Arraste qualquer item direto na prévia (horizontal e vertical) ou ajuste X e Y. Para cada item escolha a fonte "
                      "de corrida, negrito/itálico, o tamanho (%) e a cor do texto.")
        dica.setObjectName("mudo")
        dica.setWordWrap(True)
        self.det_extras.addWidget(dica)
        import overlay_iracing as _ov
        fontes = _ov.fontes_corrida_disponiveis() if hasattr(_ov, "fontes_corrida_disponiveis") else []
        pos = self.config.get(self._chave_pos(chave))
        pos = pos if isinstance(pos, dict) else {}
        self._campos_pos = {}
        for eid, rotulo in elementos:
            est = self._estilo_de(chave, eid)
            quadro = QFrame()
            quadro.setObjectName("bloco")
            col = QVBoxLayout(quadro)
            col.setContentsMargins(14, 8, 14, 8)
            col.setSpacing(6)
            l1 = QHBoxLayout()
            rot_l = QLabel(rotulo)
            rot_l.setWordWrap(True)
            rot_l.setMinimumWidth(40)
            l1.addWidget(rot_l, 1)
            v = pos.get(eid) if isinstance(pos.get(eid), (list, tuple)) and len(pos.get(eid)) == 2 else (0, 0)
            sx, sy = QSpinBox(), QSpinBox()
            for sp, val, pre in ((sx, v[0], "X "), (sy, v[1], "Y ")):
                sp.setRange(-600, 600)
                sp.setSingleStep(2)
                sp.setPrefix(pre)
                sp.setValue(int(round(float(val))))
                sp.setMinimumWidth(60)
                sp.setMaximumWidth(96)
                l1.addWidget(sp)
            col.addLayout(l1)
            l2 = QHBoxLayout()
            cb = QComboBox()
            cb.addItem("Fonte do tema", "")
            for fid, rot in fontes:
                cb.addItem(rot, fid)
            i = cb.findData(est.get("fonte", ""))
            cb.setCurrentIndex(i if i >= 0 else 0)
            ce = QComboBox()
            for rot, _v in self.ESTILOS_FONTE:
                ce.addItem(rot)
            ce.setCurrentIndex(next((n for n, (_r, (nb, ni)) in enumerate(self.ESTILOS_FONTE)
                                     if nb == est.get("negrito") and ni == est.get("italico")), 0))
            for w in (cb, ce):
                w.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
                w.setMinimumContentsLength(8)
                w.setMinimumWidth(60)
                l2.addWidget(w, 1)
            col.addLayout(l2)
            l3 = QHBoxLayout()
            st = QSpinBox()
            st.setRange(49, 200)                                  # build av: 49 = "Tam. padrão" (sem tamanho escolhido); 50 a 200 = tamanho real em %
            st.setSingleStep(5)
            st.setSuffix(" %")
            st.setSpecialValueText("Tam. padrão")
            st.setValue(int(est["tam"]) if est.get("tam") else 49)
            st.setMinimumWidth(60)
            bc = QPushButton(est.get("cor") or "Cor")
            bc.setObjectName("acao")
            bc.setMinimumWidth(60)
            l3.addWidget(st, 1)
            l3.addWidget(bc, 1)
            col.addLayout(l3)
            sx.valueChanged.connect(lambda _v, k=eid: self._ao_pos_campo(chave, k))
            sy.valueChanged.connect(lambda _v, k=eid: self._ao_pos_campo(chave, k))
            cb.currentIndexChanged.connect(lambda _i, k=eid: self._ao_estilo_campos(chave, k))
            ce.currentIndexChanged.connect(lambda _i, k=eid: self._ao_estilo_campos(chave, k))
            st.valueChanged.connect(lambda _v, k=eid: self._ao_estilo_campos(chave, k))
            bc.clicked.connect(lambda _=False, k=eid: self._ao_cor_elemento(chave, k))
            self._campos_pos[eid] = (sx, sy, cb, ce, st, bc)
            self.det_extras.addWidget(quadro)
        b = QPushButton("Restaurar posições e estilos")
        b.setObjectName("acao")
        b.clicked.connect(lambda: self._restaurar_pos_fonte(chave))
        self.det_extras.addWidget(b, 0, Qt.AlignLeft)
        self.det_previa.definir_arrastavel(True)

    def _ao_pos_campo(self, chave, eid):
        sx, sy = self._campos_pos[eid][:2]
        d = dict(self.config.get(self._chave_pos(chave)) if isinstance(self.config.get(self._chave_pos(chave)), dict) else {})
        if sx.value() == 0 and sy.value() == 0:
            d.pop(eid, None)
        else:
            d[eid] = [sx.value(), sy.value()]
        self._cfg_painel(chave, self._chave_pos(chave), d)
        self._aplicar_opcao(chave)

    def _gravar_estilo(self, chave, eid, est):
        d = dict(self.config.get(self._chave_estilo(chave)) if isinstance(self.config.get(self._chave_estilo(chave)), dict) else {})
        if est:
            d[eid] = est
        else:
            d.pop(eid, None)
        self._cfg_painel(chave, self._chave_estilo(chave), d)
        self._aplicar_opcao(chave)

    def _ao_estilo_campos(self, chave, eid):
        _sx, _sy, cb, ce, st, _bc = self._campos_pos[eid]
        est = self._estilo_de(chave, eid)
        for k in ("fonte", "negrito", "italico", "tam"):
            est.pop(k, None)
        if cb.currentData():
            est["fonte"] = cb.currentData()
        nb, ni = self.ESTILOS_FONTE[max(0, ce.currentIndex())][1]
        if nb is not None:
            est["negrito"], est["italico"] = nb, ni
        if st.value() != 49:
            est["tam"] = st.value()
        self._gravar_estilo(chave, eid, est)

    def _ao_cor_elemento(self, chave, eid):
        from PySide6.QtWidgets import QColorDialog
        est = self._estilo_de(chave, eid)
        atual = QColor(est.get("cor") or "#ffffff")
        cor = QColorDialog.getColor(atual, self, "Cor")
        bc = self._campos_pos[eid][5]
        if not cor.isValid():
            return
        est["cor"] = cor.name()
        bc.setText(est["cor"])
        self._gravar_estilo(chave, eid, est)

    def _restaurar_pos_fonte(self, chave):
        self._cfg_painel(chave, self._chave_pos(chave), {})
        self._cfg_painel(chave, self._chave_estilo(chave), {})
        for sx, sy, cb, ce, st, bc in getattr(self, "_campos_pos", {}).values():
            ws = (sx, sy, cb, ce, st)
            for w in ws:
                w.blockSignals(True)
            sx.setValue(0); sy.setValue(0); cb.setCurrentIndex(0); ce.setCurrentIndex(0); st.setValue(49)
            for w in ws:
                w.blockSignals(False)
            bc.setText("Cor")
        self._aplicar_opcao(chave)

    def _escala_previa(self, chave):
        """Quantos px da imagem da previa valem 1 px base da janela."""
        p = self._previa(chave)
        try:
            return max(0.1, p.width() / float(p.tamanho()[0]))
        except Exception:
            return 1.0

    def _elemento_em(self, chave, px, py):
        """Qual elemento esta sob o ponto (px, py) da imagem da previa: esconde o desenho de cada um por vez (sem mexer no layout)
        e ve quem some ali. Entre os candidatos vence o de menor area (o item e nao o fundo)."""
        p = self._previa(chave)
        j = self._janela(chave)
        if p is None or j is None or self._dados_demo is None:
            return None
        nome = self._chave_cfg_elementos(chave)
        ligados = self.config.get(nome) if isinstance(self.config.get(nome), dict) else {}
        def imagem():
            p.atualizar(self._dados_demo)
            im = p.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
            return im.width(), im.height(), memoryview(bytes(im.constBits())).cast("I")
        try:
            self._sincronizar_previa(chave, p)
            p._teste_oculto = None
            w0, h0, base = imagem()
            R = 6
            x0, y0 = max(0, int(px) - R), max(0, int(py) - R)
            x1, y1 = min(w0, int(px) + R + 1), min(h0, int(py) + R + 1)
            melhor, area = None, None
            for eid, _rot in type(j).ELEMENTOS:
                if ligados.get(eid) is False:
                    continue
                p._teste_oculto = eid
                w1, h1, im = imagem()
                if (w1, h1) != (w0, h0):
                    continue
                total = sum(1 for a_, b_ in zip(base, im) if a_ != b_)
                perto = 0
                for yy in range(y0, y1):
                    ini = yy * w0
                    perto += sum(1 for k in range(ini + x0, ini + x1) if base[k] != im[k])
                if perto and (area is None or total < area):
                    melhor, area = eid, total
            return melhor
        finally:
            p._teste_oculto = None

    def _arrasto_ini(self, px, py):
        chave = self._atual
        self._arr = None
        j = self._janela(chave) if chave else None
        if j is None or not getattr(type(j), "ELEMENTOS", ()):
            return
        try:
            eid = self._elemento_em(chave, px, py)
        except Exception:
            self._registrar_erro("Central: nao foi possivel achar o item sob o mouse no painel '%s'" % chave)
            return
        if eid is None:
            return
        pos = self.config.get(self._chave_pos(chave))
        v = pos.get(eid) if isinstance(pos, dict) and isinstance(pos.get(eid), (list, tuple)) and len(pos.get(eid)) == 2 else (0, 0)
        self._arr = (chave, eid, float(v[0]), float(v[1]), self._escala_previa(chave))

    def _arrasto_mov(self, dx, dy):
        a = getattr(self, "_arr", None)
        if not a:
            return
        chave, eid, x0, y0, esc = a
        nx = int(round((x0 + dx / esc) / 2.0)) * 2                      # encaixe de 2 px
        ny = int(round((y0 + dy / esc) / 2.0)) * 2
        nx, ny = max(-600, min(600, nx)), max(-600, min(600, ny))
        d = dict(self.config.get(self._chave_pos(chave)) if isinstance(self.config.get(self._chave_pos(chave)), dict) else {})
        if nx == 0 and ny == 0:
            d.pop(eid, None)
        else:
            d[eid] = [nx, ny]
        self._cfg_painel(chave, self._chave_pos(chave), d)
        campos = getattr(self, "_campos_pos", {}).get(eid)
        if campos:
            for sp, val in ((campos[0], nx), (campos[1], ny)):
                sp.blockSignals(True); sp.setValue(val); sp.blockSignals(False)
        self._aplicar_opcao(chave, salvar=False)

    def _arrasto_fim(self):
        a = getattr(self, "_arr", None)
        self._arr = None
        if a and self.g.get("salvar"):
            self.g["salvar"]()

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
        self._atualiza_dependentes()
        self._aplicar_opcao(chave)

    def _atualiza_dependentes(self):
        """Build av: o item que so existe dentro de outro fica desabilitado enquanto o de fora estiver desligado."""
        sw = getattr(self, "_interruptores_delta", {})
        for filho, pai in getattr(self, "_depende", {}).items():
            if filho in sw and pai in sw:
                sw[filho].setEnabled(sw[pai].isChecked())

    def _todos_elementos(self, chave):
        self._cfg_painel(chave, self._chave_cfg_elementos(chave), {})
        for i in getattr(self, "_interruptores_delta", {}).values():
            i.definir(True)
        self._atualiza_dependentes()
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

    def _bloco_chips(self, atual, opcoes, ao_escolher, dica=""):
        quadro = QFrame()
        quadro.setObjectName("bloco")
        lay = QVBoxLayout(quadro)
        lay.setContentsMargins(14, 10, 14, 12)
        linha = QHBoxLayout()
        grupo = QButtonGroup(quadro)
        grupo.setExclusive(True)
        for valor, rotulo in opcoes:
            b = QPushButton(rotulo)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(valor == atual)
            grupo.addButton(b)
            b.clicked.connect(lambda _=False, v=valor: ao_escolher(v))
            linha.addWidget(b)
        linha.addStretch(1)
        lay.addLayout(linha)
        if dica:
            d = QLabel(dica)
            d.setObjectName("mudo")
            d.setWordWrap(True)
            lay.addWidget(d)
        quadro._grupo = grupo
        return quadro

    def _ao_tema_central(self, nome):
        self.config["central_tema"] = nome
        definir_tema_central(nome)
        self.setStyleSheet(QSS)
        for w in self.findChildren(QWidget):
            w.update()
        self.update()
        if self.g.get("salvar"):
            self.g["salvar"]()

    def _ao_idioma(self, codigo):
        import ov_i18n as _i18n
        self.config["idioma"] = codigo
        _i18n.definir_idioma(codigo)
        if self.g.get("salvar"):
            self.g["salvar"]()
        try:
            QMessageBox.information(self, "Idioma / Language",
                                    _i18n.AVISO_REINICIAR.get(_i18n.idioma(), _i18n.AVISO_REINICIAR["en"]))
        except Exception:
            self._registrar_erro("Central: aviso de idioma")

    def _ao_daltonismo(self, modo):
        self.config["daltonismo"] = modo
        f = self.g.get("daltonismo")
        if f is not None:
            try:
                f(modo)
            except Exception:
                self._registrar_erro("Central: modo daltônico")
        if self.g.get("salvar"):
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
        h3 = QLabel("APARÊNCIA DA CENTRAL")
        h3.setObjectName("h2")
        blocos.addSpacing(8)
        blocos.addWidget(h3)
        blocos.addWidget(self._bloco_chips(self.config.get("central_tema", "classico"), [(k, v["nome"]) for k, v in TEMAS_CENTRAL.items()],
                                           self._ao_tema_central, "Só muda esta janela de configurações; o overlay no jogo não é afetado."))
        h4 = QLabel("MODO DALTÔNICO")
        h4.setObjectName("h2")
        blocos.addSpacing(8)
        blocos.addWidget(h4)
        blocos.addWidget(self._bloco_chips(self.config.get("daltonismo", "padrao"),
                                           [("padrao", "Padrão"), ("deuteranopia", "Deuteranopia"), ("protanopia", "Protanopia"), ("tritanopia", "Tritanopia")],
                                           self._ao_daltonismo, "Troca as cores de bom/ruim (verde e vermelho) das janelas do overlay por cores que o tipo escolhido distingue. É uma troca de paleta, não uma simulação médica."))
        try:
            import ov_i18n as _i18n
            h5 = QLabel("IDIOMA / LANGUAGE")
            h5.setObjectName("h2")
            blocos.addSpacing(8)
            blocos.addWidget(h5)
            blocos.addWidget(self._bloco_chips(str(self.config.get("idioma", "auto")),
                                               [("auto", "Automático (Windows)")] + [(c, n) for c, n in _i18n.IDIOMAS],
                                               self._ao_idioma, "Os painéis mudam na hora; reinicie o overlay para traduzir também esta janela e os menus."))
        except Exception:
            pass
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

    # ---------------------------------------------------------------- calculadora de FOV (build ab)
    FOV_PADRAO = {"dist": 70.0, "dist_un": "cm", "diag": 27.0, "diag_un": "pol", "aspecto": "16:9", "asp_w": 16.0, "asp_h": 9.0, "curva_on": False,
                  "curva_r": 1800, "triplo": False, "bezel": 15.0, "lat_on": False, "lat_diag": 27.0, "lat_aspecto": "16:9"}

    def _fov_estado(self):
        est = dict(self.FOV_PADRAO)
        salvo = self.config.get("fov_calc")
        if isinstance(salvo, dict):
            for k, v0 in self.FOV_PADRAO.items():
                ok_tipo = k in salvo and (type(salvo[k]) is type(v0) or (isinstance(v0, float) and type(salvo[k]) is int))
                if ok_tipo:
                    est[k] = salvo[k]
        return est

    def _fov_para_cm(self, valor, unidade):
        return valor * 2.54 if unidade == "pol" else valor

    def _fov_entrada(self):
        """Estado da pagina -> entrada de ov_fov.calcular()."""
        e = self._fov_est
        asp = _fov.aspecto_de(e["aspecto"], (e["asp_w"], e["asp_h"]) if e["aspecto"] == "custom" else None)
        curva = int(e["curva_r"]) if e["curva_on"] else None
        ent = {"dist": self._fov_para_cm(e["dist"], e["dist_un"]), "diag": self._fov_para_cm(e["diag"], e["diag_un"]), "aspecto": asp, "curva": curva,
               "triplo": bool(e["triplo"]), "bezel_mm": e["bezel"]}
        if e["triplo"] and e["lat_on"]:
            asp_l = _fov.aspecto_de(e["lat_aspecto"], (e["asp_w"], e["asp_h"]) if e["lat_aspecto"] == "custom" else None)
            ent["lateral"] = {"diag": self._fov_para_cm(e["lat_diag"], e["diag_un"]), "aspecto": asp_l, "curva": curva}
        return ent

    def _fov_bloco(self, titulo, dica=""):
        quadro = QFrame()
        quadro.setObjectName("bloco")
        lay = QVBoxLayout(quadro)
        lay.setContentsMargins(14, 10, 14, 12)
        t = QLabel(titulo)
        t.setObjectName("h2")
        lay.addWidget(t)
        if dica:
            d = QLabel(dica)
            d.setObjectName("mudo")
            d.setWordWrap(True)
            lay.addWidget(d)
        return quadro, lay

    def _fov_spin(self, chave, minimo, maximo, passo, sufixo=""):
        sp = QDoubleSpinBox()
        sp.setRange(minimo, maximo)
        sp.setDecimals(1)
        sp.setSingleStep(passo)
        sp.setSuffix(sufixo)
        sp.setValue(float(self._fov_est[chave]))
        sp.valueChanged.connect(lambda v, k=chave: self._fov_mudou(k, float(v)))
        self._fov_widgets[chave] = sp
        return sp

    def _fov_chips(self, chave, opcoes):
        linha = QHBoxLayout()
        grupo = QButtonGroup(self)
        grupo.setExclusive(True)
        botoes = {}
        for valor, rotulo in opcoes:
            b = QPushButton(rotulo)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(self._fov_est[chave] == valor)
            grupo.addButton(b)
            b.clicked.connect(lambda _=False, k=chave, v=valor: self._fov_mudou(k, v))
            linha.addWidget(b)
            botoes[valor] = b
        linha.addStretch(1)
        self._fov_widgets[chave] = (grupo, botoes)
        return linha

    def _fov_combo(self, chave, opcoes):
        cb = QComboBox()
        for valor, rotulo in opcoes:
            cb.addItem(rotulo, valor)
        i = max(0, cb.findData(self._fov_est[chave]))
        cb.setCurrentIndex(i)
        cb.currentIndexChanged.connect(lambda _i, k=chave, c=cb: self._fov_mudou(k, c.currentData()))
        self._fov_widgets[chave] = cb
        return cb

    def _fov_interruptor(self, chave):
        it = Interruptor(bool(self._fov_est[chave]))
        it.clicked.connect(lambda _=False, k=chave, i=it: self._fov_mudou(k, bool(i.isChecked())))
        self._fov_widgets[chave] = it
        return it

    def _pagina_fov(self):
        if _fov is None:
            return QWidget()
        self._fov_est = self._fov_estado()
        self._fov_widgets, self._fov_trava = {}, False
        w, lay = self._pagina("Calculadora de FOV", "Campo de visão (FOV) a partir da geometria da sua tela ou triplo. O resultado é um ponto de partida: ajuste cerca de ±10 % ao gosto.")
        corpo = QHBoxLayout()
        corpo.setSpacing(16)
        esq = QVBoxLayout()
        # exemplos
        q, v = self._fov_bloco("EXEMPLOS", "Preenche os campos com uma configuração comum; depois ajuste às suas medidas.")
        self._fov_ex = QComboBox()
        self._fov_ex.addItem("Escolha um exemplo...", None)
        for nome, ent in _fov.EXEMPLOS:
            self._fov_ex.addItem(nome, ent)
        self._fov_ex.currentIndexChanged.connect(self._fov_exemplo)
        v.addWidget(self._fov_ex)
        esq.addWidget(q)
        # distancia
        q, v = self._fov_bloco("DISTÂNCIA ATÉ A TELA", "Dos olhos até o centro da tela (a tela central, no triplo).")
        h = QHBoxLayout()
        h.addWidget(self._fov_spin("dist", 10.0, 400.0, 1.0), 1)
        h.addLayout(self._fov_chips("dist_un", (("cm", "cm"), ("pol", "pol"))))
        v.addLayout(h)
        esq.addWidget(q)
        # tela
        q, v = self._fov_bloco("TELA")
        h = QHBoxLayout()
        h.addWidget(QLabel("Diagonal"))
        h.addWidget(self._fov_spin("diag", 10.0, 120.0, 0.5), 1)
        h.addLayout(self._fov_chips("diag_un", (("pol", "pol"), ("cm", "cm"))))
        v.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(QLabel("Proporção"))
        h.addWidget(self._fov_combo("aspecto", (("16:9", "16:9"), ("21:9", "21:9"), ("32:9", "32:9"), ("custom", "Personalizada"))), 1)
        h.addWidget(self._fov_spin("asp_w", 1.0, 64.0, 1.0), 1)
        h.addWidget(QLabel(":"))
        h.addWidget(self._fov_spin("asp_h", 1.0, 64.0, 1.0), 1)
        v.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(QLabel("Tela curva"))
        h.addWidget(self._fov_interruptor("curva_on"))
        h.addWidget(QLabel("Raio"))
        h.addWidget(self._fov_combo("curva_r", tuple((r, f"{r}R") for r in _fov.CURVATURAS_MM)), 1)
        v.addLayout(h)
        esq.addWidget(q)
        # triplo
        q, v = self._fov_bloco("TELAS", "No triplo, as laterais ficam à mesma distância dos olhos, viradas para você.")
        v.addLayout(self._fov_chips("triplo", ((False, "Uma tela"), (True, "Três telas"))))
        h = QHBoxLayout()
        h.addWidget(QLabel("Moldura por emenda (mm)"))
        h.addWidget(self._fov_spin("bezel", -60.0, 120.0, 1.0), 1)
        v.addLayout(h)
        d = QLabel("Negativo = telas sobrepostas (kit sem moldura).")
        d.setObjectName("mudo")
        v.addWidget(d)
        h = QHBoxLayout()
        h.addWidget(QLabel("Laterais diferentes da central"))
        h.addWidget(self._fov_interruptor("lat_on"))
        v.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(QLabel("Diagonal lateral"))
        h.addWidget(self._fov_spin("lat_diag", 10.0, 120.0, 0.5), 1)
        h.addWidget(self._fov_combo("lat_aspecto", (("16:9", "16:9"), ("21:9", "21:9"), ("32:9", "32:9"), ("custom", "Personalizada"))), 1)
        v.addLayout(h)
        esq.addWidget(q)
        esq.addStretch(1)
        # resultado
        dir_ = QVBoxLayout()
        self.fov_res = QFrame()
        self.fov_res.setObjectName("bloco")
        self.fov_res_lay = QVBoxLayout(self.fov_res)
        self.fov_res_lay.setContentsMargins(16, 12, 16, 14)
        dir_.addWidget(self.fov_res)
        dir_.addStretch(1)
        ce, cd = QWidget(), QWidget()
        ce.setLayout(esq)
        cd.setLayout(dir_)
        corpo.addWidget(ce, 5)
        corpo.addWidget(cd, 6)
        cont = QWidget()
        cont.setLayout(corpo)
        lay.addWidget(self._rolagem(cont), 1)
        self._fov_visibilidade()
        self._fov_recalcular()
        return w

    def _fov_exemplo(self, _i):
        ent = self._fov_ex.currentData()
        if not ent:
            return
        e = self._fov_est
        e.update({"dist": ent["dist"], "dist_un": "cm", "diag": round(ent["diag"] / 2.54, 1), "diag_un": "pol", "aspecto": ent["aspecto"], "curva_on": bool(ent["curva"]),
                  "triplo": bool(ent["triplo"]), "bezel": float(ent["bezel_mm"]), "lat_on": False})
        if ent["curva"]:
            e["curva_r"] = int(ent["curva"])
        self._fov_sincronizar()
        self._fov_salvar()
        self._fov_visibilidade()
        self._fov_recalcular()

    def _fov_sincronizar(self):
        """Estado -> widgets (sem disparar recalculo em cadeia)."""
        self._fov_trava = True
        try:
            for k, wdg in self._fov_widgets.items():
                v = self._fov_est[k]
                if isinstance(wdg, QDoubleSpinBox):
                    wdg.setValue(float(v))
                elif isinstance(wdg, QComboBox):
                    wdg.setCurrentIndex(max(0, wdg.findData(v)))
                elif isinstance(wdg, Interruptor):
                    wdg.definir(bool(v))
                elif isinstance(wdg, tuple):
                    for val, b in wdg[1].items():
                        b.setChecked(val == v)
        finally:
            self._fov_trava = False

    def _fov_mudou(self, chave, valor):
        if self._fov_trava:
            return
        self._fov_est[chave] = valor
        self._fov_salvar()
        self._fov_visibilidade()
        self._fov_recalcular()

    def _fov_salvar(self):
        try:
            self.config["fov_calc"] = dict(self._fov_est)
            if self.g.get("salvar"):
                self.g["salvar"]()
        except Exception:
            self._registrar_erro("Central: nao salvou a calculadora de FOV")

    def _fov_visibilidade(self):
        e, wd = self._fov_est, self._fov_widgets
        custom = e["aspecto"] == "custom" or (e["triplo"] and e["lat_on"] and e["lat_aspecto"] == "custom")
        for k in ("asp_w", "asp_h"):
            wd[k].setEnabled(custom)
        wd["curva_r"].setEnabled(bool(e["curva_on"]))
        for k in ("bezel", "lat_on"):
            wd[k].setEnabled(bool(e["triplo"]))
        for k in ("lat_diag", "lat_aspecto"):
            wd[k].setEnabled(bool(e["triplo"] and e["lat_on"]))

    def _fov_linha(self, rotulo, texto, grande=False):
        h = QHBoxLayout()
        a = QLabel(rotulo)
        a.setObjectName("mudo")
        b = QLabel(texto)
        b.setObjectName("numero_g" if grande else "numero")
        h.addWidget(a, 1)
        h.addWidget(b)
        return h

    def _fov_recalcular(self):
        lay = self.fov_res_lay
        def limpar(layout):
            while layout.count():
                it = layout.takeAt(0)
                wd = it.widget()
                if wd is not None:
                    wd.hide()
                    wd.setParent(None)                       # sai da tela na hora (deleteLater sozinho deixa o desenho antigo por baixo)
                    wd.deleteLater()
                elif it.layout() is not None:
                    limpar(it.layout())
        limpar(lay)
        t = QLabel("RESULTADO")
        t.setObjectName("h2")
        lay.addWidget(t)
        try:
            res = _fov.calcular(self._fov_entrada())
        except ValueError as ex:
            m = QLabel("Confira os dados: " + str(ex))
            m.setWordWrap(True)
            lay.addWidget(m)
            self.fov_resultado = None
            return
        except Exception:
            self._registrar_erro("Central: calculadora de FOV falhou")
            self.fov_resultado = None
            return
        self.fov_resultado = res
        lay.addLayout(self._fov_linha("FOV vertical", f"{res['vfov']:.1f}°", True))
        lay.addLayout(self._fov_linha("FOV horizontal" + (" (tela central)" if res["triplo"] else ""), f"{res['hfov']:.1f}°", True))
        if res["triplo"]:
            lay.addLayout(self._fov_linha("FOV horizontal total (3 telas)", f"{res['hfov_total']:.1f}°"))
            lay.addLayout(self._fov_linha("Ângulo das laterais", f"{res['lateral_angulo']:.1f}°"))
        lay.addLayout(self._fov_linha("Largura (X)", f"{res['largura_x']:.0f} cm"))
        lay.addLayout(self._fov_linha("Profundidade (Y)", f"{res['profundidade_y']:.0f} cm"))
        nota = QLabel("Largura: de ponta a ponta das telas, com cerca de 2 cm de estrutura. Profundidade: da frente das laterais ao fundo do painel central (8 cm de espessura); "
                      "some cerca de 4,5 cm se usar suporte para triplo.")
        nota.setObjectName("mudo")
        nota.setWordWrap(True)
        lay.addWidget(nota)
        if res["triplo"]:
            t2 = QLabel("MEDIDAS COM FITA (para conferir o ângulo)")
            t2.setObjectName("h2")
            lay.addSpacing(6)
            lay.addWidget(t2)
            lay.addLayout(self._fov_linha("Entre os cantos externos das laterais", f"{res['fita_externa']:.1f} cm"))
            lay.addLayout(self._fov_linha("Entre os cantos internos das laterais", f"{res['fita_interna']:.1f} cm"))
        t3 = QLabel("O QUE DIGITAR NO JOGO")
        t3.setObjectName("h2")
        lay.addSpacing(6)
        lay.addWidget(t3)
        for nome, tipo in _fov.JOGOS:
            valor, conj = _fov.para_jogo(res, tipo)
            texto = f"{valor:.0f}° {tipo}" + (f"  (conjunto: {conj:.0f}°)" if conj else "")
            lo, hi = _fov.faixa(valor)
            l = QLabel(f"{nome}: {texto}  ·  ajuste fino {lo:.0f}° a {hi:.0f}°")
            l.setWordWrap(True)
            lay.addWidget(l)
        for av in res["avisos"]:
            a = QLabel("Atenção: " + av)
            a.setWordWrap(True)
            lay.addWidget(a)
        rod = QLabel("Cada jogo define se o número vale para uma tela ou para o conjunto no modo triplo: confirme no menu do jogo. "
                     "Os números por jogo seguem a referência da calculadora de Dan Suzuki; não alteram arquivos do jogo.")
        rod.setObjectName("mudo")
        rod.setWordWrap(True)
        lay.addSpacing(6)
        lay.addWidget(rod)

    # ---------------------------------------------------------------- busca / filtro
    def _ao_categoria(self, cat):
        self._categoria = cat
        for k, cab in getattr(self, "_cab_categoria", {}).items():
            cab.setProperty("ativo", "true" if k == cat else "false")
            cab.style().unpolish(cab)
            cab.style().polish(cab)
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
        largura = self._rolagem_paineis.viewport().width() if hasattr(self, "_rolagem_paineis") else 0
        cols = max(1, min(4, (largura if largura > 100 else 900) // 290))
        for k, c in enumerate(visiveis):
            self._grade.addWidget(c["quadro"], k // cols, k % cols)
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

    def _sincronizar_previa(self, chave, p):
        """Build w: a previa trabalha numa COPIA do config (feita ao criar). Opcoes ligadas por interruptores de acao
        (ex.: Telemetria > barra horizontal / grafico) mudavam so o config real e a janela real, e a previa ficava parada.
        Antes de cada desenho, os valores do config real passam para a copia; se algo mudou, a previa reaplica o layout."""
        j = self._janela(chave)
        ignorar = {getattr(j, "CHAVE_ATIVO", None), "travado"}
        mudou = False
        for k, v in list(self.config.items()):
            if k in ignorar:
                continue
            try:
                if k not in p.config or p.config[k] is not v and p.config[k] != v:
                    p.config[k] = v
                    mudou = True
            except Exception:
                continue
        if mudou:
            for nome in ("reconfigurar", "opcoes_mudaram", "aplicar_tamanho"):
                f = getattr(p, nome, None)
                if f is not None:
                    try:
                        f()
                    except Exception:
                        self._registrar_erro("Central: a previa do painel '%s' falhou em %s()" % (chave, nome))

    def _grab(self, chave):
        p = self._previa(chave)
        if p is None or self._dados_demo is None:
            return None
        try:
            self._sincronizar_previa(chave, p)
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
