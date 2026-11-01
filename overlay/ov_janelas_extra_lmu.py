# -*- coding: utf-8 -*-
"""
Janelas novas do LMU (mesmo visual do overlay do iRacing; herdam de JanelaBase, que continua intacta):
  Energia e combustivel | Pneus e freios | Danos | Alertas na pista | Historico de stints | Tendencia de ritmo

Regra do projeto: o que e MEDIDO pelo jogo aparece normal; o que o overlay CALCULA/ESTIMA aparece com "~" e o rodape
diz a origem. Nenhum numero estimado e apresentado como medido.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainterPath, QPen

import overlay_iracing as base
import ov_alertas_lmu as alt
import ov_estrategia_lmu as estr

fonte = base.fonte
COR_CINZA, COR_TEXTO, COR_VERDE = base.COR_CINZA, base.COR_TEXTO, base.COR_VERDE
COR_AMARELO, COR_VERMELHO, COR_LARANJA = base.COR_AMARELO, base.COR_VERMELHO, base.COR_LARANJA
COR_BARRA = base.COR_FUNDO_BARRA
COR_AZUL = QColor(70, 140, 255)
COR_ROXO = QColor(190, 130, 255)
BRANCO = QColor(255, 255, 255)

# tamanhos base (100 %)
TAM_ENERGIA = (372, 300)
TAM_PNEUS = (378, 350)
TAM_DANOS = (300, 334)
TAM_ALERTAS = (392, 262)
TAM_STINTS = (590, 270)
TAM_TENDENCIA = (540, 296)


# --------------------------------------------------------------------------------------------------------------
# Pecas de desenho comuns
# --------------------------------------------------------------------------------------------------------------
def _titulo(p, texto, largura, direita=None, cor_direita=None):
    p.setPen(COR_TEXTO if (base.TEMA["sport"] or base.TEMA["vidro"]) and base.TEMA["moderno"] else COR_CINZA)
    p.setFont(base.fonte_titulo(9))
    p.drawText(16, 8, int(largura * 0.62) if direita else largura - 32, 20, Qt.AlignLeft | Qt.AlignVCenter, texto)
    if direita:
        p.setPen(cor_direita or COR_CINZA)
        p.setFont(fonte(8, QFont.Bold))
        p.drawText(int(largura * 0.45), 8, int(largura * 0.55) - 16, 20, Qt.AlignRight | Qt.AlignVCenter, direita)


def _rotulo(p, x, y, w, texto, alinh=Qt.AlignLeft, h=12):
    p.setPen(COR_CINZA)
    p.setFont(fonte(7, QFont.DemiBold))
    p.drawText(x, y, w, h, alinh | Qt.AlignVCenter, texto)


def _barra(p, x, y, w, h, frac, cor):
    p.setPen(Qt.NoPen)
    p.setBrush(COR_BARRA)
    p.drawRoundedRect(x, y, w, h, h / 2.0, h / 2.0)
    if frac is not None:
        frac = max(0.0, min(1.0, frac))
        if frac > 0:
            p.setBrush(cor)
            p.drawRoundedRect(x, y, max(h, int(w * frac)), h, h / 2.0, h / 2.0)


def _rodape(p, largura, altura, linhas):
    p.setPen(COR_CINZA)
    p.setFont(fonte(7))
    n = len(linhas)
    for i, t in enumerate(linhas):
        p.drawText(16, altura - 8 - 12 * (n - i), largura - 32, 12, Qt.AlignLeft | Qt.AlignVCenter, t)


def _sem_dados(p, largura, texto="Sem dados"):
    p.setPen(COR_CINZA)
    p.setFont(fonte(10))
    p.drawText(16, 44, largura - 32, 24, Qt.AlignLeft | Qt.AlignVCenter, texto)


def _faixa(p, x, y, w, h, cor, texto, fonte_pt=11):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(cor.red(), cor.green(), cor.blue(), 60))
    p.drawRoundedRect(x, y, w, h, 8, 8)
    p.setPen(cor)
    p.setFont(fonte(fonte_pt, QFont.Bold))
    p.drawText(x, y, w, h, Qt.AlignCenter, texto)


def _num(valor, formato, vazio="--"):
    return vazio if valor is None else formato.format(valor)


# --------------------------------------------------------------------------------------------------------------
# 1. Energia virtual + combustivel
# --------------------------------------------------------------------------------------------------------------
class JanelaEnergiaLMU(base.JanelaBase):
    CHAVE = "lmu_energia"
    CHAVE_ATIVO = "mostrar_lmu_energia"
    TAXA_HZ = 4.0

    def tamanho(self):
        return TAM_ENERGIA

    @staticmethod
    def _cor_alcance(alcance, margem):
        if alcance is None:
            return COR_CINZA
        if alcance < margem + 1.0:
            return COR_VERMELHO
        if alcance < margem + 3.0:
            return COR_AMARELO
        return COR_VERDE

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        L, A = TAM_ENERGIA
        e = d.get("lmu_energia")
        limitante = (e or {}).get("limitante")
        _titulo(p, "ENERGIA VIRTUAL E COMBUSTIVEL", L,
                None if not limitante else "LIMITA: " + ("ENERGIA" if limitante == "energia" else "COMBUSTIVEL"),
                COR_AMARELO)
        if not e:
            _sem_dados(p, L)
            return
        margem = float(e.get("margem") or 1.0)
        en, cb = e.get("energia") or {}, e.get("combustivel") or {}

        def bloco(x, nome, valor_txt, frac, por_volta_txt, alcance, limita):
            if limita:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(250, 200, 40, 200), 1.5))
                p.drawRoundedRect(x - 6, 32, 170, 112, 8, 8)
            _rotulo(p, x, 36, 150, nome)
            p.setPen(BRANCO if valor_txt != "--" else COR_CINZA)
            p.setFont(fonte(28, QFont.Bold))
            p.drawText(x, 48, 156, 40, Qt.AlignLeft | Qt.AlignVCenter, valor_txt)
            cor = self._cor_alcance(alcance, margem)
            _barra(p, x, 92, 150, 10, frac, cor)
            p.setPen(COR_TEXTO)
            p.setFont(fonte(9, QFont.DemiBold))
            p.drawText(x, 106, 156, 16, Qt.AlignLeft | Qt.AlignVCenter, por_volta_txt)
            p.setPen(cor)
            p.setFont(fonte(10, QFont.Bold))
            p.drawText(x, 122, 156, 18, Qt.AlignLeft | Qt.AlignVCenter,
                       "alcance --" if alcance is None else f"alcance ~{alcance:.1f} V")

        nivel_en = en.get("nivel_pct")
        bloco(16, "ENERGIA VIRTUAL", "--" if nivel_en is None else f"{nivel_en:.1f}%",
              None if nivel_en is None else nivel_en / 100.0,
              "consumo --" if en.get("por_volta") is None else f"~{en['por_volta']:.2f} %/volta",
              en.get("alcance"), limitante == "energia")
        litros, cap = cb.get("litros"), cb.get("capacidade")
        bloco(194, "COMBUSTIVEL", "--" if litros is None else f"{litros:.1f} L",
              None if (litros is None or not cap) else litros / cap,
              "consumo --" if cb.get("por_volta") is None else f"~{cb['por_volta']:.2f} L/volta",
              cb.get("alcance"), limitante == "combustivel")

        # situacao (parada necessaria?)
        msg = e.get("mensagem")
        fim = e.get("voltas_fim")
        if msg == "chega":
            folga = e["alcance"] - fim
            _faixa(p, 12, 156, L - 24, 40, COR_VERDE, f"CHEGA AO FIM  (folga ~{folga:.1f} V)")
        elif msg in ("parada", "paradas") and e.get("paradas"):
            n = e["paradas"]
            titulo = "1 PARADA NECESSARIA" if n == 1 else f"~{n} PARADAS NECESSARIAS"
            if e.get("janela"):
                a, b = e["janela"]
                titulo += f"\nparar entre as voltas {a} e {b}"
            _faixa(p, 12, 156, L - 24, 40, COR_LARANJA if n == 1 else COR_VERMELHO, titulo, 10)
        elif msg == "parada":
            _faixa(p, 12, 156, L - 24, 40, COR_LARANJA, "PARADA NECESSARIA", 10)
        elif msg == "sem_fim":
            _faixa(p, 12, 156, L - 24, 40, COR_CINZA, "SESSAO SEM FIM CONHECIDO", 10)
        else:
            _faixa(p, 12, 156, L - 24, 40, COR_CINZA, "Aguardando voltas limpas...", 10)

        # alvo por volta para chegar ao fim e dados de apoio
        y = 206
        _rotulo(p, 16, y, 110, "VOLTAS ATE O FIM")
        _rotulo(p, 134, y, 110, "ALVO ENERGIA")
        _rotulo(p, 252, y, 110, "ALVO COMBUSTIVEL")
        p.setPen(COR_TEXTO)
        p.setFont(fonte(13, QFont.Bold))
        p.drawText(16, y + 12, 110, 24, Qt.AlignLeft | Qt.AlignVCenter, "--" if fim is None else (f"{fim}" if float(fim).is_integer() else f"~{fim:.1f}"))
        p.drawText(134, y + 12, 112, 24, Qt.AlignLeft | Qt.AlignVCenter,
                   _num(e.get("alvo_energia"), "~{:.2f} %/V"))
        p.drawText(252, y + 12, 112, 24, Qt.AlignLeft | Qt.AlignVCenter,
                   _num(e.get("alvo_comb"), "~{:.2f} L/V"))
        _rodape(p, L, A, ["Nivel: medido pelo jogo. Consumo, alcance, alvo e janela:",
                          f"~ calculados (media das voltas limpas; margem {margem:g} volta(s))."
                          + ("" if e.get("ve_informada") else "  Energia virtual indisponivel.")])


# --------------------------------------------------------------------------------------------------------------
# 2a. Pneus e freios
# --------------------------------------------------------------------------------------------------------------
class JanelaPneusLMU(base.JanelaBase):
    CHAVE = "pneus"                       # reaproveita a posicao da janela de pneus do layout do iRacing
    CHAVE_ATIVO = "mostrar_pneus"
    TAXA_HZ = 4.0
    LARG, ALT = 170, 118
    NOMES = {"FL": "DIANTEIRO ESQ.", "FR": "DIANTEIRO DIR.", "RL": "TRASEIRO ESQ.", "RR": "TRASEIRO DIR."}
    FAIXA_IDEAL_C = 10.0                  # definicao do overlay: ideal = temperatura otima do jogo +- 10 C

    def tamanho(self):
        return TAM_PNEUS

    def _cor_temp(self, r):
        t = r["temp"]
        if t is None:
            return COR_CINZA
        if r["otima"] is not None:
            baixo, alto = r["otima"] - self.FAIXA_IDEAL_C, r["otima"] + self.FAIXA_IDEAL_C
        else:
            baixo, alto = float(self.config.get("pneu_temp_min", 80.0)), float(self.config.get("pneu_temp_max", 105.0))
        if t < baixo:
            return COR_AZUL
        if t > alto:
            return COR_VERMELHO
        return COR_VERDE

    @staticmethod
    def _cor_vida(v):
        if v is None:
            return COR_CINZA
        return COR_VERDE if v >= 50 else (COR_AMARELO if v >= 25 else COR_VERMELHO)

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        L, A = TAM_PNEUS
        pn = d.get("lmu_pneus")
        _titulo(p, "PNEUS E FREIOS", L)
        if not pn:
            _sem_dados(p, L)
            return
        posicoes = {"FL": (12, 30), "FR": (12 + self.LARG + 12, 30),
                    "RL": (12, 30 + self.ALT + 8), "RR": (12 + self.LARG + 12, 30 + self.ALT + 8)}
        for r in pn["rodas"]:
            self._cartao(p, *posicoes[r["roda"]], r)
        # oleo e agua do motor
        y = 30 + 2 * self.ALT + 14
        _rotulo(p, 16, y, 60, "OLEO")
        _rotulo(p, 112, y, 60, "AGUA")
        p.setPen(COR_TEXTO)
        p.setFont(fonte(11, QFont.Bold))
        p.drawText(46, y - 3, 60, 18, Qt.AlignLeft | Qt.AlignVCenter, _num(pn.get("oleo"), "{:.0f}°C"))
        p.drawText(142, y - 3, 60, 18, Qt.AlignLeft | Qt.AlignVCenter, _num(pn.get("agua"), "{:.0f}°C"))
        _rodape(p, L, A, ["Pneu = camada interna (mais proxima do MFD do jogo; ajustavel",
                          "em TEMP_PNEU_FONTE). Freio convertido de Kelvin. Ideal = otima do jogo ±10 °C",
                          "(regra do overlay). Vida = leitura do jogo (mWear)."])

    def _cartao(self, p, x, y, r):
        base.pintar_superficie(p, QRectF(x, y, self.LARG, self.ALT), 8, cartao=True)
        _rotulo(p, x + 10, y + 6, 110, self.NOMES[r["roda"]])
        # composto
        if r["composto"]:
            cor = {"S": COR_VERMELHO, "M": COR_AMARELO, "H": BRANCO, "W": COR_AZUL}[r["composto"]]
            p.setPen(QPen(cor, 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(x + self.LARG - 26, y + 6, 18, 18)
            p.setPen(cor)
            p.setFont(fonte(9, QFont.Bold))
            p.drawText(x + self.LARG - 26, y + 6, 18, 18, Qt.AlignCenter, r["composto"])
        # temperatura grande
        p.setPen(self._cor_temp(r))
        p.setFont(fonte(24, QFont.Bold))
        p.drawText(x + 10, y + 20, 100, 34, Qt.AlignLeft | Qt.AlignVCenter, _num(r["temp"], "{:.0f}°"))
        p.setPen(COR_TEXTO)
        p.setFont(fonte(9, QFont.DemiBold))
        p.drawText(x + 92, y + 28, 70, 22, Qt.AlignRight | Qt.AlignVCenter, _num(r["pressao"], "{:.0f} kPa"))
        # vida
        _rotulo(p, x + 10, y + 56, 40, "VIDA")
        _barra(p, x + 10, y + 70, self.LARG - 20, 8, None if r["vida"] is None else r["vida"] / 100.0, self._cor_vida(r["vida"]))
        p.setPen(self._cor_vida(r["vida"]))
        p.setFont(fonte(9, QFont.Bold))
        p.drawText(x + self.LARG - 70, y + 54, 60, 14, Qt.AlignRight | Qt.AlignVCenter, _num(r["vida"], "{:.0f}%"))
        # freio
        _rotulo(p, x + 10, y + 86, 60, "FREIO")
        p.setPen(COR_TEXTO)
        p.setFont(fonte(10, QFont.Bold))
        p.drawText(x + 56, y + 84, 60, 16, Qt.AlignLeft | Qt.AlignVCenter, _num(r["freio"], "{:.0f}°C"))
        if r["furado"] or r["solta"]:
            _faixa(p, x + 8, y + 100, self.LARG - 16, 14, COR_VERMELHO, "FURADO" if r["furado"] else "RODA SOLTA", 8)


# --------------------------------------------------------------------------------------------------------------
# 2b. Danos
# --------------------------------------------------------------------------------------------------------------
class JanelaDanosLMU(base.JanelaBase):
    CHAVE = "danos"
    CHAVE_ATIVO = "mostrar_danos"
    TAXA_HZ = 4.0

    def tamanho(self):
        return TAM_DANOS

    @staticmethod
    def cor_sev(s):
        return {0: QColor(255, 255, 255, 30), 1: QColor(250, 200, 40), 2: QColor(235, 60, 60)}.get(s, QColor(255, 255, 255, 30))

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        L, A = TAM_DANOS
        dn = d.get("lmu_danos")
        _titulo(p, "DANOS DO CARRO", L)
        if not dn:
            _sem_dados(p, L)
            return
        z = dn["zonas"]
        forte = any(s >= 2 for s in z) or any(dn["furados"]) or any(dn["rodas_soltas"])
        if forte:
            cor, txt = COR_VERMELHO, "DANO FORTE"
        elif any(z) or dn["solta"]:
            cor, txt = COR_AMARELO, "IMPACTO REGISTRADO"
        else:
            cor, txt = COR_VERDE, "SEM DANO REGISTRADO"
        _faixa(p, 12, 32, L - 24, 28, cor, txt, 10)

        # carro visto de cima, frente para cima: ordem das zonas = ov_lmu.ZONAS_DANO (frente e sentido ANTI-horario)
        cx, cy = 92, 164
        formas = [(cx - 24, cy - 84, 48, 16), (cx - 48, cy - 68, 22, 30), (cx - 48, cy - 34, 14, 68),
                  (cx - 48, cy + 38, 22, 30), (cx - 24, cy + 68, 48, 16), (cx + 26, cy + 38, 22, 30),
                  (cx + 34, cy - 34, 14, 68), (cx + 26, cy - 68, 22, 30)]
        p.setPen(Qt.NoPen)
        for sev, (x, y, w, h) in zip(z, formas):
            p.setBrush(self.cor_sev(sev))
            p.drawRoundedRect(x, y, w, h, 6, 6)
        p.setBrush(QColor(95, 95, 108))
        p.drawRoundedRect(cx - 24, cy - 62, 48, 124, 16, 16)
        p.setBrush(QColor(14, 14, 20))
        p.drawRoundedRect(cx - 16, cy - 30, 32, 18, 5, 5)
        p.drawRoundedRect(cx - 16, cy + 22, 32, 12, 4, 4)
        # rodas (vermelhas se furadas ou soltas): FL, FR, RL, RR
        for i, (x, y) in enumerate(((cx - 66, cy - 58), (cx + 56, cy - 58), (cx - 66, cy + 36), (cx + 56, cy + 36))):
            ruim = dn["furados"][i] or dn["rodas_soltas"][i]
            p.setBrush(COR_VERMELHO if ruim else QColor(60, 60, 70))
            p.drawRoundedRect(x, y, 10, 22, 3, 3)
        _rotulo(p, cx - 40, cy - 102, 80, "FRENTE", Qt.AlignHCenter)
        lado = dn.get("impacto_lado")
        if lado:                                              # lado do ULTIMO impacto, pela posicao medida pelo jogo
            _rotulo(p, 12, cy + 90, 160, "LADO DO ULTIMO IMPACTO", Qt.AlignLeft)
            p.setPen(COR_TEXTO)
            p.setFont(fonte(11, QFont.Bold))
            p.drawText(12, cy + 102, 170, 20, Qt.AlignLeft | Qt.AlignVCenter, lado.upper().replace("-", " "))

        # coluna da direita: situacao medida pelo jogo
        def item(y, rotulo, valor, cor_v=COR_TEXTO):
            _rotulo(p, 176, y, 116, rotulo)
            p.setPen(cor_v)
            p.setFont(fonte(12, QFont.Bold))
            p.drawText(176, y + 12, 118, 22, Qt.AlignLeft | Qt.AlignVCenter, valor)
        desde, forca = dn.get("impacto_desde"), dn.get("impacto_forca")
        item(72, "ULTIMO IMPACTO", "nenhum" if desde is None else f"ha {estr.fmt_duracao(desde)}")
        item(108, "FORCA DO IMPACTO", "--" if (forca is None or desde is None) else f"{forca:.0f}")
        item(144, "PECA SOLTA", "SIM" if dn["solta"] else "nao", COR_LARANJA if dn["solta"] else COR_TEXTO)
        item(180, "RODAS FURADAS", str(sum(dn["furados"])) if any(dn["furados"]) else "nenhuma",
             COR_VERMELHO if any(dn["furados"]) else COR_TEXTO)
        if dn.get("motor_parado"):
            txt_motor, cor_motor = "PARADO", COR_VERMELHO
        elif dn["superaquecendo"]:
            txt_motor, cor_motor = "SUPERAQUECENDO", COR_VERMELHO
        else:
            txt_motor, cor_motor = "ok", COR_VERDE
        item(216, "MOTOR", txt_motor, cor_motor)
        item(252, "FAROL", "ligado" if dn.get("farois") else "apagado")
        _rodape(p, L, A, ["Dados do jogo. O LMU nao informa % de dano",
                          "nem tempo de reparo. Zonas: leve ou forte; ordem",
                          "conferida: frente-esq., frente-dir., tras.-dir."])


# --------------------------------------------------------------------------------------------------------------
# 3. Alertas na pista
# --------------------------------------------------------------------------------------------------------------
class JanelaAlertasLMU(base.JanelaBase):
    CHAVE = "lmu_alertas"
    CHAVE_ATIVO = "mostrar_lmu_alertas"
    TAXA_HZ = 10.0
    ALT_LINHA = 34
    CORES = {alt.NIVEL_INFO: COR_AZUL, alt.NIVEL_ATENCAO: COR_AMARELO, alt.NIVEL_PERIGO: COR_VERMELHO}

    def tamanho(self):
        return TAM_ALERTAS

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        L, A = TAM_ALERTAS
        a = d.get("lmu_alertas")
        direita = None
        if a and a.get("limite_pit"):
            direita = f"LIMITE BOXES {a['limite_pit']:.0f} km/h (medido)"
        _titulo(p, "ALERTAS NA PISTA", L, direita)
        if a is None:
            _sem_dados(p, L)
            return
        lista = a.get("lista") or []
        if not lista:
            _faixa(p, 12, 36, L - 24, 40, COR_VERDE, "SEM ALERTAS", 12)
        y = 32
        for al in lista:
            cor = self.CORES.get(al["nivel"], COR_CINZA)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(cor.red(), cor.green(), cor.blue(), 55 if al["nivel"] else 35))
            p.drawRoundedRect(12, y, L - 24, self.ALT_LINHA - 3, 6, 6)
            p.setBrush(cor)
            p.drawRect(12, y + 2, 4, self.ALT_LINHA - 7)
            p.setPen(cor if al["nivel"] else COR_TEXTO)
            p.setFont(fonte(10, QFont.Bold))
            p.drawText(24, y, L - 40, 18, Qt.AlignLeft | Qt.AlignVCenter, al["titulo"])
            p.setPen(COR_TEXTO)
            p.setFont(fonte(8))
            p.drawText(24, y + 15, L - 40, 14, Qt.AlignLeft | Qt.AlignVCenter, al["detalhe"])
            y += self.ALT_LINHA
        _rodape(p, L, A, ["Bandeiras/boxes: medidos pelo jogo. Distancias e tempos: ~ calculados.",
                          "Limiares de aviso: definicao do overlay (config_lmu.json)."])


# --------------------------------------------------------------------------------------------------------------
# 4a. Historico de stints
# --------------------------------------------------------------------------------------------------------------
class JanelaStintsLMU(base.JanelaBase):
    CHAVE = "lmu_stints"
    CHAVE_ATIVO = "mostrar_lmu_stints"
    TAXA_HZ = 2.0
    MAX_LINHAS = 6
    # (rotulo, x, largura, alinhamento)
    COLUNAS = (("STINT", 16, 40, Qt.AlignLeft), ("VOLTAS", 58, 48, Qt.AlignRight), ("TEMPO", 110, 62, Qt.AlignRight),
               ("ENERGIA", 176, 64, Qt.AlignRight), ("COMB.", 244, 60, Qt.AlignRight), ("PNEU", 308, 44, Qt.AlignHCenter),
               ("DESG.", 356, 52, Qt.AlignRight), ("RITMO", 412, 80, Qt.AlignRight), ("VS MELHOR", 496, 78, Qt.AlignRight))

    def tamanho(self):
        return TAM_STINTS

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        L, A = TAM_STINTS
        s = d.get("lmu_stints")
        _titulo(p, "HISTORICO DE STINTS", L)
        if not s or not s.get("stints"):
            _sem_dados(p, L, "Sem stints ainda (um stint comeca na saida dos boxes)")
            return
        for rot, x, w, al in self.COLUNAS:
            _rotulo(p, x, 32, w, rot, al)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawLine(14, 46, L - 14, 46)
        y = 50
        for st in s["stints"][:self.MAX_LINHAS]:
            self._linha(p, y, st)
            y += 28
        _rodape(p, L, A, ["Energia e combustivel por stint: nivel no inicio - nivel no fim (jogo). Ritmo: media das voltas limpas (~).",
                          "* = stint parcial (overlay aberto no meio do stint). Desgaste: pontos de vida do pneu (sentido a confirmar)."])

    def _linha(self, p, y, st):
        if st["atual"]:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(176, 140, 42, 150) if base.TEMA["moderno"] else QColor(45, 90, 190, 150))
            p.drawRoundedRect(8, y, TAM_STINTS[0] - 16, 26, 5, 5)
        c = {n: (x, w, al) for n, x, w, al in self.COLUNAS}

        def t(chave, texto, cor=COR_TEXTO, tam=10, peso=QFont.Bold):
            x, w, al = c[chave]
            p.setPen(cor)
            p.setFont(fonte(tam, peso))
            p.drawText(x, y, w, 26, al | Qt.AlignVCenter, texto)
        t("STINT", f"{st['n']}{'*' if st['parcial'] else ''}" + (" >" if st["atual"] else ""))
        t("VOLTAS", str(st["voltas"]))
        t("TEMPO", estr.fmt_duracao(st["tempo"]))
        t("ENERGIA", _num(st["energia"], "{:.1f}%"), COR_TEXTO if st["energia"] is not None else COR_CINZA)
        t("COMB.", _num(st["comb"], "{:.1f} L"), COR_TEXTO if st["comb"] is not None else COR_CINZA)
        comp = st["composto"]
        cor_c = {"S": COR_VERMELHO, "M": COR_AMARELO, "H": BRANCO, "W": COR_AZUL}.get(comp, COR_CINZA)
        t("PNEU", comp or "--", cor_c)
        t("DESG.", _num(st["desgaste"], "{:.0f}%"), COR_TEXTO if st["desgaste"] is not None else COR_CINZA)
        t("RITMO", "--" if st["ritmo"] is None else base.fmt_tempo(st["ritmo"]), COR_TEXTO if st["ritmo"] else COR_CINZA)
        delta = st["delta"]
        t("VS MELHOR", "--" if delta is None else f"{delta:+.2f}",
          COR_CINZA if delta is None else (COR_VERDE if delta < 0.3 else (COR_AMARELO if delta < 1.0 else COR_VERMELHO)))


# --------------------------------------------------------------------------------------------------------------
# 4b. Tendencia de ritmo
# --------------------------------------------------------------------------------------------------------------
class JanelaTendenciaLMU(base.JanelaBase):
    CHAVE = "lmu_tendencia"
    CHAVE_ATIVO = "mostrar_lmu_tendencia"
    TAXA_HZ = 2.0
    ESTAVEL = 0.03                       # |inclinacao| abaixo disto = ritmo estavel (definicao do overlay, s/volta)

    def tamanho(self):
        return TAM_TENDENCIA

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        L, A = TAM_TENDENCIA
        t = d.get("lmu_tendencia")
        _titulo(p, "TENDENCIA DE RITMO", L)
        if not t or not t["voltas"]:
            _sem_dados(p, L, "Aguardando voltas limpas (sem boxes, sem bandeira)")
            return
        # resumo
        ritmo, delta, inc = t["ritmo5"], t["delta_ritmo"], t["inclinacao"]
        _rotulo(p, 16, 30, 120, "RITMO (ULT. 5 LIMPAS)")
        p.setPen(BRANCO)
        p.setFont(fonte(15, QFont.Bold))
        p.drawText(16, 42, 150, 24, Qt.AlignLeft | Qt.AlignVCenter, base.fmt_tempo(ritmo))
        if delta is not None:
            p.setPen(COR_VERDE if delta < 0.3 else (COR_AMARELO if delta < 1.0 else COR_VERMELHO))
            p.setFont(fonte(9, QFont.Bold))
            p.drawText(16, 64, 150, 14, Qt.AlignLeft | Qt.AlignVCenter, f"{delta:+.2f} s vs melhor")
        _rotulo(p, 190, 30, 160, "TENDENCIA DO STINT")
        if inc is None:
            p.setPen(COR_CINZA)
            p.setFont(fonte(10, QFont.DemiBold))
            p.drawText(190, 42, 190, 24, Qt.AlignLeft | Qt.AlignVCenter, f"precisa de {estr.MINIMO_VOLTAS_TENDENCIA} voltas limpas")
        else:
            if abs(inc) < self.ESTAVEL:
                cor, rot = COR_VERDE, "estavel"
            elif inc > 0:
                cor, rot = (COR_AMARELO if inc < 0.15 else COR_VERMELHO), "piorando"
            else:
                cor, rot = COR_VERDE, "melhorando"
            p.setPen(cor)
            p.setFont(fonte(15, QFont.Bold))
            p.drawText(190, 42, 190, 24, Qt.AlignLeft | Qt.AlignVCenter, f"~{inc:+.2f} s/volta")
            p.setFont(fonte(9, QFont.Bold))
            p.drawText(190, 64, 190, 14, Qt.AlignLeft | Qt.AlignVCenter, rot)
        _rotulo(p, 390, 30, 130, "PISTA", Qt.AlignRight)
        p.setPen(COR_TEXTO)
        p.setFont(fonte(15, QFont.Bold))
        p.drawText(390, 42, 134, 24, Qt.AlignRight | Qt.AlignVCenter, _num(t["temp_pista"], "{:.0f}°C"))
        if t["temp_variacao"] is not None and abs(t["temp_variacao"]) >= 1.0:
            p.setPen(COR_CINZA)
            p.setFont(fonte(9, QFont.DemiBold))
            p.drawText(390, 64, 134, 14, Qt.AlignRight | Qt.AlignVCenter, f"{t['temp_variacao']:+.0f}°C no periodo")
        self._grafico(p, t, QRectF(54, 90, L - 72, A - 90 - 58))
        _rodape(p, L, A, ["Volta limpa = sem boxes e ate 130% da melhor. Tendencia (~) = regressao linear",
                          "das voltas limpas do stint atual. Linha roxa = melhor volta da sessao."])

    @staticmethod
    def _grafico(p, t, r):
        pontos = t["voltas"]
        tempos = [x[1] for x in pontos]
        melhor = t["melhor"]
        lo = min(tempos + ([melhor] if melhor else [])) - 0.4
        hi = max(tempos) + 0.4
        if hi - lo < 1.0:
            hi = lo + 1.0
        n = len(pontos)

        def px(i):
            return r.left() + (r.width() * (i + 0.5) / n if n > 1 else r.width() / 2.0)

        def py(v):
            return r.bottom() - (v - lo) / (hi - lo) * r.height()
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        for k in range(5):
            y = r.top() + r.height() * k / 4.0
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        p.setPen(COR_CINZA)
        p.setFont(fonte(7))
        p.drawText(2, int(r.top()) - 6, 50, 12, Qt.AlignRight | Qt.AlignVCenter, base.fmt_tempo(hi))
        p.drawText(2, int(r.bottom()) - 6, 50, 12, Qt.AlignRight | Qt.AlignVCenter, base.fmt_tempo(lo))
        if melhor:
            p.setPen(QPen(COR_ROXO, 1.2, Qt.DashLine))
            p.drawLine(QPointF(r.left(), py(melhor)), QPointF(r.right(), py(melhor)))
        # troca de stint: linha vertical pontilhada
        for i in range(1, n):
            if pontos[i][3] != pontos[i - 1][3]:
                x = (px(i) + px(i - 1)) / 2.0
                p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.DotLine))
                p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
        # linha e pontos (o stint atual em destaque)
        atual = t["stint_atual"]
        caminho = QPainterPath()
        for i, (_, tempo, _, _) in enumerate(pontos):
            caminho.moveTo(px(i), py(tempo)) if i == 0 else caminho.lineTo(px(i), py(tempo))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 90), 1.2))
        p.drawPath(caminho)
        p.setPen(Qt.NoPen)
        for i, (_, tempo, _, n_stint) in enumerate(pontos):
            p.setBrush(QColor(250, 200, 40) if n_stint == atual else QColor(150, 150, 165))
            p.drawEllipse(QPointF(px(i), py(tempo)), 3.2, 3.2)
        # reta de tendencia (so quando ha voltas suficientes no stint atual)
        if t["inclinacao"] is not None:
            idx = [i for i, x in enumerate(pontos) if x[3] == atual]
            xs = [pontos[i][0] for i in idx]
            ys = [pontos[i][1] for i in idx]
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            f = lambda volta: my + t["inclinacao"] * (volta - mx)
            p.setPen(QPen(COR_AMARELO, 1.6))
            p.drawLine(QPointF(px(idx[0]), py(f(pontos[idx[0]][0]))), QPointF(px(idx[-1]), py(f(pontos[idx[-1]][0]))))
        # numeros das voltas (a cada N)
        p.setPen(COR_CINZA)
        p.setFont(fonte(7))
        passo = max(1, n // 8)
        for i in range(0, n, passo):
            p.drawText(int(px(i)) - 14, int(r.bottom()) + 2, 28, 12, Qt.AlignCenter, f"V{pontos[i][0]}")


JANELAS_EXTRA = (JanelaEnergiaLMU, JanelaPneusLMU, JanelaDanosLMU, JanelaAlertasLMU, JanelaStintsLMU, JanelaTendenciaLMU)
