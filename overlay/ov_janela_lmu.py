# -*- coding: utf-8 -*-
"""
Janela de classificacao DETALHADA do LMU (mesmo visual do overlay do iRacing, com mais colunas).

Herda da janela de classificacao do iRacing (arquivo original intacto) e troca apenas o desenho/tamanho:
  P | variacao no grid | # | carro | piloto | PIT/PEN | paradas | combustivel % | GAP | INT | melhor | ultima | media 5
"""
import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPen, QPolygonF

import overlay_iracing as base
import ov_classif_lmu as cl

fonte, TEMA = base.fonte, base.TEMA
COR_CINZA, COR_TEXTO, COR_VERDE = base.COR_CINZA, base.COR_TEXTO, base.COR_VERDE
COR_VERMELHO, COR_LARANJA = base.COR_VERMELHO, base.COR_LARANJA

LARGURA_LMU = 846
ALTURA_LINHA = base.ALTURA_LINHA_CLASS
# (chave, x, largura, rotulo) - posicoes no tamanho base (100 %)
X = {"pos": (20, 26), "var": (50, 34), "num": (86, 38), "marca": (126, 34), "piloto": (164, 134),
     "tags": (302, 58), "par": (364, 28), "comb": (396, 40), "gap": (442, 72), "int": (518, 62),
     "melhor": (586, 78), "ultima": (670, 78), "media": (754, 78)}


class JanelaClassificacaoLMU(base.JanelaClassificacao):
    LINHAS_MINHA_CLASSE = 10        # carros mostrados na sua classe (topo + vizinhanca)
    LINHAS_OUTRAS_CLASSES = 5       # carros mostrados nas demais classes

    def tamanho(self):
        return (LARGURA_LMU, self._altura_base)

    # -- quais linhas aparecem -----------------------------------------------------------------------------
    def _blocos(self, classif):
        todas = self.config.get("classificacao_todas", True)
        blocos = []
        for classe in classif["classes"]:
            if not todas and not classe["minha"]:
                continue
            linhas = classe["linhas"]
            i_eu = next((i for i, l in enumerate(linhas) if l["eu"]), None)
            if not todas:
                limite = self.LINHAS_MINHA_CLASSE + 4
            else:
                limite = self.LINHAS_MINHA_CLASSE if classe["minha"] else self.LINHAS_OUTRAS_CLASSES
            visiveis, anterior = [], None
            for k in base.selecionar_linhas(len(linhas), i_eu, limite):
                visiveis.append((linhas[k], anterior is not None and k != anterior + 1))
                anterior = k
            blocos.append((classe, visiveis))
        return blocos

    # -- desenho ---------------------------------------------------------------------------------------------
    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        classif = d.get("classificacao")
        if not classif or not self._blocos_atual:
            p.setPen(COR_CINZA)
            p.setFont(fonte(12))
            p.drawText(self._retangulo_base(), Qt.AlignCenter, "Sem dados de classificacao")
            return
        self._barra_superior(p, classif)
        y = self.ALTURA_TOPO
        for classe, linhas in self._blocos_atual:
            self._cabecalho_classe(p, y, classe)
            y += ALTURA_LINHA
            for linha, salto in linhas:
                self._linha(p, y, linha, salto, QColor(*classe["cor"]))
                y += ALTURA_LINHA

    def _barra_superior(self, p, classif):
        sessao = classif.get("sessao") or {}
        p.setFont(fonte(8, QFont.DemiBold))
        p.setPen(COR_CINZA)
        p.drawText(14, 5, 110, 18, Qt.AlignLeft | Qt.AlignVCenter, "CLASSIFICACAO")
        x = 122
        tipo = classif.get("tipo_sessao")
        if tipo:
            p.setFont(fonte(10, QFont.Bold))
            p.setPen(QColor(255, 255, 255))
            p.drawText(x, 5, 120, 18, Qt.AlignLeft | Qt.AlignVCenter, tipo)
            x += 112
        p.setFont(fonte(9, QFont.DemiBold))
        p.setPen(COR_TEXTO)
        partes = []
        if sessao.get("decorrido") is not None:
            texto = cl.fmt_hms(sessao["decorrido"])
            if sessao.get("total"):
                texto += " / " + cl.fmt_hms(sessao["total"])
            partes.append(texto)
        if classif.get("volta"):
            v = f"VOLTA {classif['volta']}"
            if sessao.get("voltas_total"):
                v += f"/{sessao['voltas_total']}"
            partes.append(v)
        p.drawText(x, 5, 330, 18, Qt.AlignLeft | Qt.AlignVCenter, "    ".join(partes))
        # direita: temperaturas e total de carros
        direita = []
        if sessao.get("pista") is not None:
            direita.append(f"PISTA {sessao['pista']:.0f}°C")
        if sessao.get("ar") is not None:
            direita.append(f"AR {sessao['ar']:.0f}°C")
        total = sum(c["n_carros"] for c in classif["classes"])
        direita.append(f"{total} CARROS")
        p.setFont(fonte(8, QFont.DemiBold))
        p.setPen(COR_CINZA)
        p.drawText(LARGURA_LMU - 14 - 300, 5, 300, 18, Qt.AlignRight | Qt.AlignVCenter, "    ".join(direita))

        # Rotulos das colunas
        p.setFont(fonte(7, QFont.DemiBold))
        y = 26
        rot = (("pos", "P", Qt.AlignRight), ("num", "#", Qt.AlignLeft), ("marca", "CARRO", Qt.AlignHCenter),
               ("piloto", "PILOTO", Qt.AlignLeft), ("par", "PAR", Qt.AlignHCenter), ("comb", "COMB", Qt.AlignRight),
               ("gap", "GAP", Qt.AlignRight), ("int", "INT", Qt.AlignRight), ("melhor", "MELHOR", Qt.AlignRight),
               ("ultima", "ULTIMA", Qt.AlignRight), ("media", "MED 5", Qt.AlignRight))
        for chave, texto, alinh in rot:
            x0, w = X[chave]
            p.drawText(x0, y, w, 16, alinh | Qt.AlignVCenter, texto)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawLine(14, 43, LARGURA_LMU - 14, 43)

    def _cabecalho_classe(self, p, y, classe):
        h = ALTURA_LINHA
        cor = QColor(*classe["cor"])
        fundo = QColor(cor)
        fundo.setAlpha(70)
        p.setPen(Qt.NoPen)
        p.setBrush(fundo)
        p.drawRoundedRect(8, y + 2, LARGURA_LMU - 16, h - 4, 5, 5)
        p.setBrush(cor)
        p.drawRect(8, y + 2, 4, h - 4)
        p.setFont(fonte(10, QFont.Bold))
        p.setPen(cor.lighter(125))
        p.drawText(20, y, 200, h, Qt.AlignLeft | Qt.AlignVCenter, classe["nome"])
        mostrados = next((len(v) for c, v in self._blocos_atual if c is classe), classe["n_carros"])
        texto = f"{mostrados}/{classe['n_carros']} CARROS" if mostrados != classe["n_carros"] else f"{classe['n_carros']} CARROS"
        p.setFont(fonte(8, QFont.DemiBold))
        p.setPen(base.COR_TEXTO)
        p.drawText(LARGURA_LMU - 20 - 240, y, 240, h, Qt.AlignRight | Qt.AlignVCenter, texto)

    # -- pecas da linha ----------------------------------------------------------------------------------------
    @staticmethod
    def _seta(p, x, y, h, ganhou):
        cy = y + h / 2.0
        cor = COR_VERDE if ganhou else COR_VERMELHO
        p.setPen(Qt.NoPen)
        p.setBrush(cor)
        if ganhou:
            tri = QPolygonF([QPointF(x, cy + 3), QPointF(x + 8, cy + 3), QPointF(x + 4, cy - 4)])
        else:
            tri = QPolygonF([QPointF(x, cy - 3), QPointF(x + 8, cy - 3), QPointF(x + 4, cy + 4)])
        p.drawPolygon(tri)

    def _selo(self, p, x, y, h, texto, cor_fundo, cor_texto=QColor(20, 20, 24)):
        fonte_selo = fonte(7, QFont.Bold)
        largura = QFontMetrics(fonte_selo).horizontalAdvance(texto) + 8
        p.setPen(Qt.NoPen)
        p.setBrush(cor_fundo)
        p.drawRoundedRect(x, y + 5, largura, h - 10, 3, 3)
        p.setFont(fonte_selo)
        p.setPen(cor_texto)
        p.drawText(x, y + 5, largura, h - 10, Qt.AlignCenter, texto)
        return largura + 3

    def _linha(self, p, y, d, salto, cor_classe):
        h = ALTURA_LINHA
        if salto:
            p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.DotLine))
            p.drawLine(20, y, LARGURA_LMU - 20, y)
        if d["eu"]:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(176, 140, 42, 235) if TEMA["moderno"] else QColor(45, 90, 190, 235))
            p.drawRoundedRect(6, y + 1, LARGURA_LMU - 12, h - 2, 5, 5)

        p.setPen(Qt.NoPen)
        p.setBrush(cor_classe)
        p.drawRect(12, y + 4, 4, h - 8)
        # posicao na classe
        p.setFont(fonte(10, QFont.Bold))
        p.setPen(COR_TEXTO)
        p.drawText(X["pos"][0], y, X["pos"][1], h, Qt.AlignRight | Qt.AlignVCenter, str(d["pos"]))
        # variacao em relacao ao grid
        v = d.get("variacao")
        xv = X["var"][0]
        if v:
            self._seta(p, xv, y, h, v > 0)
            p.setFont(fonte(8, QFont.Bold))
            p.setPen(COR_VERDE if v > 0 else COR_VERMELHO)
            p.drawText(xv + 11, y, 22, h, Qt.AlignLeft | Qt.AlignVCenter, str(abs(v)))
        # numero e marca
        p.setFont(fonte(10, QFont.Bold))
        p.setPen(cor_classe.lighter(120))
        p.drawText(X["num"][0], y, X["num"][1], h, Qt.AlignLeft | Qt.AlignVCenter, f"#{d['numero']}")
        self._emblema(p, X["marca"][0], y, X["marca"][1], h, d["marca"])
        # piloto
        fonte_nome = fonte(10, QFont.Bold)
        p.setFont(fonte_nome)
        p.setPen(QColor(255, 255, 255))
        nome = QFontMetrics(fonte_nome).elidedText(d["nome"], Qt.ElideRight, X["piloto"][1] - 4)
        p.drawText(X["piloto"][0], y, X["piloto"][1], h, Qt.AlignLeft | Qt.AlignVCenter, nome)
        # selos: PIT, PEN e resultado
        xs = X["tags"][0]
        if d["na_box"]:
            xs += self._selo(p, xs, y, h, "PIT", COR_LARANJA)
        if d["penalidades"] > 0:
            xs += self._selo(p, xs, y, h, "PEN" if d["penalidades"] == 1 else f"PEN {d['penalidades']}",
                             COR_VERMELHO, QColor(255, 255, 255))
        if d["status"]:
            cor_status = {"FIM": COR_VERDE, "DNF": QColor(120, 120, 135), "DSQ": COR_VERMELHO}[d["status"]]
            self._selo(p, xs, y, h, d["status"], cor_status, QColor(255, 255, 255) if d["status"] != "FIM" else QColor(20, 20, 24))
        # paradas e combustivel
        p.setFont(fonte(9, QFont.DemiBold))
        p.setPen(COR_TEXTO)
        p.drawText(X["par"][0], y, X["par"][1], h, Qt.AlignCenter, f"P{d['paradas']}")
        if d["combustivel_pct"] is None:
            p.setPen(COR_CINZA)
            texto = "--"
        else:
            texto = f"{d['combustivel_pct']:.0f}%"
        p.drawText(X["comb"][0], y, X["comb"][1], h, Qt.AlignRight | Qt.AlignVCenter, texto)
        # gap e intervalo (cinza com "~" = estimado, nao medido pelo jogo)
        p.setFont(fonte(9, QFont.Bold))
        for chave, valor in (("gap", d["gap"]), ("int", d["intervalo"])):
            estimado = bool(valor and valor.get("estimado"))
            p.setPen(COR_CINZA if (valor is None or estimado) else QColor(255, 255, 255))
            p.drawText(X[chave][0], y, X[chave][1], h, Qt.AlignRight | Qt.AlignVCenter, cl.fmt_gap(valor))
        # melhor (roxo = melhor da classe), ultima (verde = igual a propria melhor) e media das ultimas 5
        p.setFont(fonte(10, QFont.Bold))
        p.setPen(COR_CINZA if d["melhor"] is None else (QColor(190, 130, 255) if d["melhor_da_classe"] else QColor(255, 255, 255)))
        p.drawText(X["melhor"][0], y, X["melhor"][1], h, Qt.AlignRight | Qt.AlignVCenter, base.fmt_tempo(d["melhor"]))
        p.setPen(COR_CINZA if d["ultima"] is None else (COR_VERDE if d["pb"] else QColor(255, 255, 255)))
        p.drawText(X["ultima"][0], y, X["ultima"][1], h, Qt.AlignRight | Qt.AlignVCenter, base.fmt_tempo(d["ultima"]))
        p.setPen(COR_CINZA if d["media5"] is None else QColor(255, 255, 255))
        p.drawText(X["media"][0], y, X["media"][1], h, Qt.AlignRight | Qt.AlignVCenter, base.fmt_tempo(d["media5"]))


class JanelaClimaLMU(base.JanelaClima):
    """Clima do LMU. O jogo nao tem referencia de norte: a bussola do iRacing (com N/E/S/W) fica sem as letras e a seta do
    vento e desenhada em relacao ao carro (carro sempre apontado para cima). Todo o resto e a janela original."""

    def _bussola(self, p, cx, cy, r, c):
        p.setPen(QPen(QColor(255, 255, 255, 40), 1.5))
        p.setBrush(QColor(8, 8, 12, 235))
        p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)
        for k in range(24):                                   # marcas fixas: 0 = frente do carro
            a = math.radians(k * 15)
            ri = r - (7 if k % 6 == 0 else 4)
            p.setPen(QPen(QColor(255, 255, 255, 110 if k % 6 == 0 else 55), 1))
            p.drawLine(int(cx + ri * math.sin(a)), int(cy - ri * math.cos(a)),
                       int(cx + (r - 1) * math.sin(a)), int(cy - (r - 1) * math.cos(a)))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(200, 200, 210))
        p.drawRoundedRect(cx - 7, cy - 15, 14, 30, 5, 5)
        p.setBrush(QColor(8, 8, 12))
        p.drawRoundedRect(cx - 5, cy - 8, 10, 7, 2, 2)
        p.drawRoundedRect(cx - 5, cy + 4, 10, 5, 2, 2)
        direcao = c.get("vento_dir")
        if direcao is None or c.get("vento_vel") is None:
            return
        if self.config.get("vento_invertido"):
            direcao += math.pi
        rel = direcao + math.pi                               # para onde o vento SOPRA, relativo a frente do carro
        ux, uy = math.sin(rel), -math.cos(rel)
        px, py = -uy, ux
        mx, my = cx - ux * 0.52 * r, cy - uy * 0.52 * r
        ponta = (mx + ux * 22.0, my + uy * 22.0)
        p.setBrush(self.COR_CIANO)
        p.drawPolygon([QPointF(*ponta), QPointF(mx + px * 9 - ux * 4, my + py * 9 - uy * 4),
                       QPointF(mx - ux * 1, my - uy * 1), QPointF(mx - px * 9 - ux * 4, my - py * 9 - uy * 4)])
        for k in range(1, 4):
            t = k * 8.0
            p.setBrush(QColor(70, 200, 235, 210 - k * 55))
            p.drawEllipse(QPointF(mx - ux * (t + 2), my - uy * (t + 2)), 3.2 - k * 0.6, 3.2 - k * 0.6)
