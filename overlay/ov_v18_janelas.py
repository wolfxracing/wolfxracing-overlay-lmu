# -*- coding: utf-8 -*-
"""v1.8: as oito janelas novas. Identico nas arvores iRacing e LMU. Uso: classes = ov_v18_janelas.construir(overlay_iracing).

Todas leem so o dicionario 'v18' dentro dos dados (montado por ov_v18.Coletor); cada uma tem ELEMENTOS liga/desliga e opcoes na Central.
As cores sao pedidas a B.QColor / B.COR_* NA HORA de desenhar, entao o modo daltonico (troca de B.QColor) vale para todas."""
import math
import time

import ov_v18 as v18


def construir(B):
    from PySide6.QtCore import Qt, QRectF, QPointF
    from PySide6.QtGui import QFont, QFontMetrics, QPen, QPolygonF

    JB = B.JanelaBase
    JA = B.JanelaAutomatica

    def Q(*a):
        return B.QColor(*a)

    def ft(tam, peso=QFont.Normal, p=None):
        return B.fonte(tam, peso, p=p)

    def mistura(c1, c2, t):
        t = max(0.0, min(1.0, t))
        return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))

    PARADAS = ((28, 38, 78), (36, 110, 190), (245, 200, 50), (235, 70, 60))

    def escala_calor(t):
        """0..1 -> azul-escuro / azul / amarelo / vermelho (legivel tambem sem distinguir verde de vermelho: muda o brilho)."""
        t = max(0.0, min(1.0, t))
        x = t * (len(PARADAS) - 1)
        i = min(len(PARADAS) - 2, int(x))
        return Q(*mistura(PARADAS[i], PARADAS[i + 1], x - i))

    def escala_boa_ruim(t):
        """0 = bom (verde) ... 1 = ruim (vermelho), passando pelo amarelo; passa pelo remapeamento daltonico."""
        t = max(0.0, min(1.0, t))
        return Q(*(mistura((60, 200, 90), (250, 200, 40), t * 2) if t < 0.5 else mistura((250, 200, 40), (235, 60, 60), (t - 0.5) * 2)))

    def v18d(d):
        return (d or {}).get("v18") or {}

    def titulo(p, texto, largura, direita=""):
        p.setPen(B.COR_TEXTO)
        p.setFont(ft(10, QFont.Bold, p=p))
        p.drawText(QRectF(14, 6, largura - 28, 20), Qt.AlignLeft | Qt.AlignVCenter, texto)
        if direita:
            p.setPen(B.COR_CINZA)
            p.setFont(ft(8, QFont.DemiBold, p=p))
            p.drawText(QRectF(14, 6, largura - 28, 20), Qt.AlignRight | Qt.AlignVCenter, direita)

    def titulo_direita(p, direita, largura):
        """So o texto pequeno do canto direito do titulo (build au: item proprio, com posicao e estilo)."""
        if direita:
            p.setPen(B.COR_CINZA)
            p.setFont(ft(8, QFont.DemiBold, p=p))
            p.drawText(QRectF(14, 6, largura - 28, 20), Qt.AlignRight | Qt.AlignVCenter, direita)

    def cfg_bool(j, chave, padrao):
        return bool(j.config.get(chave, padrao))

    # ================================================================== 1. Mapa de vazao
    STOPS_VAZAO = ((42, 100, 225), (35, 200, 230), (100, 225, 130), (245, 235, 70), (250, 150, 60), (235, 70, 65))

    def escala_vazao(t):
        """0..1 -> azul / ciano / verde / amarelo / laranja / vermelho (estilo mapa de calor de vazao)."""
        t = max(0.0, min(1.0, t))
        x = t * (len(STOPS_VAZAO) - 1)
        i = min(len(STOPS_VAZAO) - 2, int(x))
        return Q(*mistura(STOPS_VAZAO[i], STOPS_VAZAO[i + 1], x - i))

    def texto_sobre(cor):
        """Preto sobre cor clara, branco sobre cor escura (le o brilho da cor ja remapeada pelo modo daltonico)."""
        lum = 0.299 * cor.red() + 0.587 * cor.green() + 0.114 * cor.blue()
        return Q(15, 18, 24) if lum > 140 else Q(255, 255, 255)

    def kfmt(rpm):
        s = f"{rpm / 1000:.1f}".rstrip("0").rstrip(".")
        return s + "k"

    AMARELO = (255, 221, 40)

    class JanelaVazao(JB):
        """Mapa de vazao: consumo instantaneo medio (L/h) por faixa de RPM (colunas) e abertura do acelerador (linhas)."""
        CHAVE = "vazao"
        CHAVE_ATIVO = "mostrar_vazao"
        TAXA_HZ = 6.0
        LARG = 440
        ELEMENTOS = (("titulo", "Título"), ("resumo", "Consumo agora, última volta, média e mapa do motor"), ("mapa", "Mapa de calor"),
                     ("cursor", "Marcador da posição atual"), ("trilha", "Trilha da posição recente"),
                     ("legenda", "Legenda de cores (mín. e máx.)"))
        SECOES = (("titulo", 0, 26), ("resumo", 26, 42), ("mapa", 68, 228), ("legenda", 296, 28))
        DEPENDE = {"cursor": "mapa", "trilha": "mapa"}          # build av: marcador e trilha sao desenhados sobre o mapa de calor

        def tamanho(self):
            return (self.LARG, self._alt_util(324))

        def paintEvent(self, _e):
            p = self._pintor()
            d = self.dados
            if not self._fundo(p, d["conectado"], "Aguardando o jogo..."):
                return
            r = v18d(d).get("vazao") or {}
            cel = r.get("celulas") or []
            atual = r.get("atual")
            nl = v18.N_LINHAS_ACEL
            x0, y0, cw, ch = 50, 98, 37, 17
            mn, mx = r.get("minimo"), r.get("maximo")
            if self._abre(p, "titulo"):
                titulo(p, "MAPA DE VAZÃO", self.LARG, "L/h por faixa de RPM e acelerador")
                self._fecha(p)
            if self._abre(p, "resumo"):
                itens = [("AGORA", r.get("agora_lh"), "L/h", 0), ("ÚLTIMA VOLTA", r.get("ultima_lv"), "L", 2), ("MÉDIA", r.get("medio_lv"), "L", 2)]
                if r.get("mapa_motor") is not None:
                    itens.append(("MAPA", r.get("mapa_motor"), "", 0))
                xs = (14, 108, 232, 350)
                for i, (rot, val, un, dec) in enumerate(itens):
                    x = xs[i]
                    p.setPen(B.COR_CINZA)
                    p.setFont(ft(7, QFont.DemiBold, p=p))
                    p.drawText(QRectF(x, 29, 110, 12), Qt.AlignLeft | Qt.AlignVCenter, rot)
                    p.setPen(B.COR_TEXTO)
                    p.setFont(ft(15, QFont.Bold, p=p))
                    txt = "--" if val is None else (f"{val:.{dec}f}" if isinstance(val, float) else str(val))
                    p.drawText(QRectF(x, 41, 110, 24), Qt.AlignLeft | Qt.AlignVCenter, txt)
                    if un:
                        w = p.fontMetrics().horizontalAdvance(txt)
                        p.setPen(B.COR_CINZA)
                        p.setFont(ft(8, QFont.DemiBold, p=p))
                        p.drawText(QRectF(x + w + 4, 46, 40, 18), Qt.AlignLeft | Qt.AlignVCenter, un)
                self._fecha(p)
            if self._abre(p, "mapa"):
                rpm_max = r.get("rpm_max") or v18d(d).get("rpm_max")
                p.setFont(ft(7, QFont.DemiBold, p=p))
                p.setPen(B.COR_CINZA)
                p.drawText(QRectF(4, 70, x0 - 8, 18), Qt.AlignRight | Qt.AlignVCenter, "ACEL. %")
                lims = v18.limites_rpm(rpm_max) if rpm_max else None
                for ci in range(v18.N_COLS):                                   # cabecalho de RPM (a coluna atual em caixa branca)
                    ret = QRectF(x0 + ci * cw + 2, 70, cw - 4, 17)
                    ativo = atual is not None and atual[1] == ci
                    if ativo:
                        p.setPen(Qt.NoPen)
                        p.setBrush(Q(255, 255, 255))
                        p.drawRoundedRect(ret, 3, 3)
                    if lims:
                        p.setPen(Q(15, 18, 24) if ativo else Q(235, 238, 245))
                        p.setFont(ft(8, QFont.Bold, p=p))
                        p.drawText(ret, Qt.AlignCenter, kfmt(lims[ci][0]))
                for ci in range(5, v18.N_COLS):                                # barra de zona de RPM alto (verde -> amarelo -> vermelho)
                    t = (ci - 5) / 4.0
                    p.setPen(Qt.NoPen)
                    p.setBrush(escala_boa_ruim(t))
                    p.drawRect(QRectF(x0 + ci * cw + 2, 90, cw - 4, 3))
                for ri in range(nl):
                    linha = cel[ri] if ri < len(cel) else [None] * v18.N_COLS
                    y = y0 + (nl - 1 - ri) * ch
                    ativo_l = atual is not None and atual[0] == ri
                    ret_l = QRectF(8, y + 1, x0 - 14, ch - 2)
                    if ativo_l:
                        p.setPen(Qt.NoPen)
                        p.setBrush(Q(255, 255, 255))
                        p.drawRoundedRect(ret_l, 3, 3)
                    p.setPen(Q(15, 18, 24) if ativo_l else Q(235, 238, 245))
                    p.setFont(ft(8, QFont.Bold, p=p))
                    p.drawText(ret_l, Qt.AlignCenter, str(ri * 10))
                    for ci in range(v18.N_COLS):
                        v = linha[ci] if ci < len(linha) else None
                        ret = QRectF(x0 + ci * cw + 1, y + 1, cw - 2, ch - 2)
                        p.setPen(Qt.NoPen)
                        if v is None or mx is None:
                            p.setBrush(Q(255, 255, 255, 12))
                            p.drawRoundedRect(ret, 2, 2)
                            if cfg_bool(self, "vazao_valores", True):
                                p.setPen(Q(255, 255, 255, 70))
                                p.setFont(ft(7, p=p))
                                p.drawText(ret, Qt.AlignCenter, "-")
                            continue
                        t = 0.5 if mx <= mn else (v - mn) / (mx - mn)
                        cor = escala_vazao(t)
                        p.setBrush(cor)
                        p.drawRoundedRect(ret, 2, 2)
                        if cfg_bool(self, "vazao_valores", True):
                            p.setPen(texto_sobre(cor))
                            p.setFont(ft(7, QFont.Bold, p=p))
                            p.drawText(ret, Qt.AlignCenter, f"{v:.0f}")
                def centro(li, co):
                    return QPointF(x0 + co * cw + cw / 2.0, y0 + (nl - 1 - li) * ch + ch / 2.0)
                if self._abre(p, "trilha"):
                    pts = [(li, co) for li, co in (r.get("trilha") or []) if co is not None]
                    if atual is not None and atual[1] is not None and (not pts or pts[-1] != tuple(atual)):
                        pts.append(tuple(atual))
                    if len(pts) >= 2:
                        n = len(pts) - 1
                        for k in range(n):
                            a_, b_ = centro(*pts[k]), centro(*pts[k + 1])
                            p.setPen(QPen(Q(255, 255, 255, int(70 + 170 * (k + 1) / n)), 2.0, Qt.SolidLine, Qt.RoundCap))
                            p.drawLine(a_, b_)
                        p.setPen(Qt.NoPen)
                        p.setBrush(Q(255, 255, 255, 230))
                        p.drawEllipse(centro(*pts[0]), 3.2, 3.2)
                    self._fecha(p)
                if atual is not None and atual[1] is not None and self._abre(p, "cursor"):
                    li, co = atual
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QPen(Q(0, 0, 0, 120), 4))
                    p.drawRoundedRect(QRectF(x0 + co * cw, y0 + (nl - 1 - li) * ch, cw, ch), 3, 3)
                    p.setPen(QPen(Q(255, 255, 255), 2))
                    p.drawRoundedRect(QRectF(x0 + co * cw, y0 + (nl - 1 - li) * ch, cw, ch), 3, 3)
                    self._fecha(p)
                self._fecha(p)
            if self._abre(p, "legenda"):
                bx, bw = x0, 170
                for k in range(60):
                    p.setPen(Qt.NoPen)
                    p.setBrush(escala_vazao(k / 59.0))
                    p.drawRect(QRectF(bx + k * bw / 60.0, 304, bw / 60.0 + 0.6, 8))
                p.setPen(B.COR_CINZA)
                p.setFont(ft(8, QFont.DemiBold, p=p))
                p.drawText(QRectF(8, 300, x0 - 12, 16), Qt.AlignRight | Qt.AlignVCenter, "0" if mn is None else f"{mn:.0f}")
                p.drawText(QRectF(bx + bw + 6, 300, 70, 16), Qt.AlignLeft | Qt.AlignVCenter, "L/h" if mx is None else f"{mx:.0f} L/h")
                p.setFont(ft(7, QFont.DemiBold, p=p))
                p.drawText(QRectF(self.LARG - 190, 300, 176, 16), Qt.AlignRight | Qt.AlignVCenter, "VAZÃO MÉDIA POR CÉLULA")
                self._fecha(p)

    # ================================================================== 2. Eficiencia por marcha
    class JanelaMarcha(JB):
        """Eficiencia por marcha: L/100 km a acelerador pleno por faixa de RPM, com a marcha e o RPM atuais, o RPM maximo observado e a parcela do tempo."""
        CHAVE = "marcha_efic"
        CHAVE_ATIVO = "mostrar_marcha_efic"
        TAXA_HZ = 4.0
        LARG = 440
        N = 8
        ELEMENTOS = (("titulo", "Título e consumo agora"), ("grade", "Grade por faixa de RPM"), ("parcela", "Parcela do tempo em cada marcha"),
                     ("troca", "RPM máximo observado"), ("rpm_atual", "Marcador do RPM atual"), ("resumo", "Melhor, média e pior"),
                     ("legenda", "Legenda inferior"))
        DEPENDE = {"parcela": "grade", "troca": "grade", "rpm_atual": "grade"}      # build av: desenhados sobre a grade
        SECOES = (("titulo", 0, 36), ("grade", 36, 190), ("resumo", 228, 34), ("legenda", 264, 22))

        def tamanho(self):
            return (self.LARG, self._alt_util(288))

        def paintEvent(self, _e):
            p = self._pintor()
            d = self.dados
            if not self._fundo(p, d["conectado"], "Aguardando o jogo..."):
                return
            r = v18d(d).get("marcha") or {}
            ms = {m["marcha"]: m for m in (r.get("marchas") or [])}
            atual_g = r.get("atual") if isinstance(r.get("atual"), int) else None
            if self._abre(p, "titulo"):
                p.setPen(B.COR_TEXTO)
                p.setFont(ft(10, QFont.Bold, p=p))
                p.drawText(QRectF(14, 6, 230, 26), Qt.AlignLeft | Qt.AlignVCenter, "EFICIÊNCIA POR MARCHA")
                xr = self.LARG - 14
                if atual_g:                                                    # selo da marcha engatada
                    p.setPen(Qt.NoPen)
                    p.setBrush(Q(*AMARELO))
                    p.drawRoundedRect(QRectF(xr - 28, 9, 28, 18), 3, 3)
                    p.setPen(Q(15, 18, 24))
                    p.setFont(ft(9, QFont.Bold, p=p))
                    p.drawText(QRectF(xr - 28, 9, 28, 18), Qt.AlignCenter, f"G{atual_g}")
                    xr -= 34
                p.setPen(B.COR_CINZA)
                p.setFont(ft(8, QFont.DemiBold, p=p))
                p.drawText(QRectF(xr - 50, 6, 50, 26), Qt.AlignRight | Qt.AlignVCenter, "L/100 km")
                ag = r.get("agora_l100")
                p.setPen(B.COR_TEXTO)
                p.setFont(ft(15, QFont.Bold, p=p))
                p.drawText(QRectF(xr - 112, 4, 58, 28), Qt.AlignRight | Qt.AlignVCenter, "-" if ag is None else f"{ag:.0f}")
                self._fecha(p)
            rpm_max_car = r.get("rpm_max")
            lo_rpm = v18.LIMITE_RPM_INF * rpm_max_car if rpm_max_car else None
            x0, cw = 40, 30
            largura_grade = v18.N_COLS * cw
            def xr_rpm(rpm):
                if not (lo_rpm and rpm_max_car and rpm_max_car > lo_rpm):
                    return None
                return x0 + max(0.0, min(1.0, (rpm - lo_rpm) / (rpm_max_car - lo_rpm))) * largura_grade
            if self._abre(p, "grade"):
                mn, mx = r.get("minimo"), r.get("maximo")
                maior = max([m["marcha"] for m in ms.values()] + ([atual_g] if atual_g else []) + [6])
                n = max(6, min(self.N, maior))
                y0 = 52.0
                ch = 156.0 / n
                p.setFont(ft(8, QFont.Bold, p=p))
                if self._abre(p, "parcela"):
                    p.setPen(B.COR_CINZA)
                    p.setFont(ft(7, QFont.DemiBold, p=p))
                    p.drawText(QRectF(350, 38, 80, 12), Qt.AlignRight | Qt.AlignVCenter, "PARCELA")
                    self._fecha(p)
                for k in range(n):
                    g = n - k
                    m = ms.get(g)
                    y = y0 + k * ch
                    atual = atual_g == g and cfg_bool(self, "marcha_destacar", True)        # opcao do painel: destacar a marcha engatada
                    if atual:
                        p.setPen(Qt.NoPen)
                        p.setBrush(Q(255, 255, 255, 22))
                        p.drawRoundedRect(QRectF(4, y, self.LARG - 8, ch), 4, 4)
                    p.setPen(Q(*AMARELO) if atual else (B.COR_TEXTO if m else Q(255, 255, 255, 60)))
                    p.setFont(ft(11 if atual else 10, QFont.Bold, p=p))
                    p.drawText(QRectF(8, y, 28, ch), Qt.AlignCenter, str(g))
                    ultimo = None
                    for ci in range(v18.N_COLS):
                        v = m["celulas"][ci] if m else None
                        p.setPen(Qt.NoPen)
                        ret = QRectF(x0 + ci * cw + 1, y + 1, cw - 2, ch - 3)
                        if v is None or mx is None:
                            p.setBrush(Q(255, 255, 255, 12))
                        else:
                            t = 0.5 if mx <= mn else (v - mn) / (mx - mn)
                            p.setBrush(escala_boa_ruim(t))
                            ultimo = (ci, v, t)
                        p.drawRoundedRect(ret, 2, 2)
                    if ultimo is not None:                                     # valor da faixa de RPM mais alta com dado
                        ci, v, t = ultimo
                        p.setPen(texto_sobre(escala_boa_ruim(t)))
                        p.setFont(ft(7, QFont.Bold, p=p))
                        p.drawText(QRectF(x0 + ci * cw + 1, y + 1, cw - 2, ch - 3), Qt.AlignCenter, f"{v:.0f}")
                    if m and m.get("rpm_max") and self._abre(p, "troca"): # marca do RPM maximo observado nesta marcha
                        xm = xr_rpm(m["rpm_max"])
                        if xm is not None:
                            p.setPen(QPen(Q(255, 255, 255, 190), 2))
                            p.drawLine(QPointF(xm, y + 3), QPointF(xm, y + ch - 3))
                        self._fecha(p)
                    if m and m.get("parcela") is not None and self._abre(p, "parcela"):
                        p.setPen(Qt.NoPen)
                        p.setBrush(Q(255, 255, 255, 36))
                        p.drawRoundedRect(QRectF(352, y + ch - 7, 50, 3), 1.5, 1.5)
                        p.setBrush(Q(255, 255, 255, 200 if atual else 150))
                        p.drawRoundedRect(QRectF(352, y + ch - 7, 50 * max(0.02, m["parcela"]), 3), 1.5, 1.5)
                        p.setPen(B.COR_TEXTO if atual else B.COR_CINZA)
                        p.setFont(ft(8, QFont.Bold if atual else QFont.Normal, p=p))
                        p.drawText(QRectF(350, y, 80, ch - 6), Qt.AlignRight | Qt.AlignVCenter, f"{m['parcela'] * 100:.0f}%")
                        self._fecha(p)
                # eixo de RPM
                if lo_rpm:
                    p.setPen(B.COR_CINZA)
                    p.setFont(ft(7, p=p))
                    k_ = int(lo_rpm // 1000) + 1
                    while k_ * 1000 <= rpm_max_car:
                        xx = xr_rpm(k_ * 1000)
                        p.drawText(QRectF(xx - 16, y0 + 156 + 3, 32, 12), Qt.AlignCenter, f"{k_}k")
                        k_ += 1
                # linha do RPM maximo observado na marcha engatada (tracejada) + etiqueta
                if atual_g and ms.get(atual_g) and ms[atual_g].get("rpm_max") and self._abre(p, "troca"):
                    xm = xr_rpm(ms[atual_g]["rpm_max"])
                    if xm is not None:
                        p.setPen(QPen(Q(*AMARELO), 1.4, Qt.DashLine))
                        p.drawLine(QPointF(xm, y0 - 3), QPointF(xm, y0 + 156))
                        txt = f"MÁX {kfmt(ms[atual_g]['rpm_max'])}"
                        w = 54
                        bx = max(x0, min(x0 + largura_grade - w, xm - w / 2))
                        p.setPen(Qt.NoPen)
                        p.setBrush(Q(*AMARELO))
                        p.drawRoundedRect(QRectF(bx, 36, w, 13), 2, 2)
                        p.setPen(Q(15, 18, 24))
                        p.setFont(ft(7, QFont.Bold, p=p))
                        p.drawText(QRectF(bx, 36, w, 13), Qt.AlignCenter, txt)
                    self._fecha(p)
                # marcador do RPM atual na marcha engatada
                if atual_g and 1 <= atual_g <= n and r.get("rpm") and self._abre(p, "rpm_atual"):
                    xa = xr_rpm(r["rpm"])
                    if xa is not None:
                        ya = y0 + (n - atual_g) * ch
                        p.setPen(QPen(Q(255, 255, 255), 2))
                        p.drawLine(QPointF(xa, ya + 1), QPointF(xa, ya + ch - 1))
                        w = 30
                        bx = max(x0, min(x0 + largura_grade - w, xa - w / 2))
                        p.setPen(Qt.NoPen)
                        p.setBrush(Q(255, 255, 255))
                        p.drawRoundedRect(QRectF(bx, ya - 6, w, 12), 2, 2)
                        p.setPen(Q(15, 18, 24))
                        p.setFont(ft(7, QFont.Bold, p=p))
                        p.drawText(QRectF(bx, ya - 6, w, 12), Qt.AlignCenter, kfmt(r["rpm"]))
                    self._fecha(p)
                self._fecha(p)
            if self._abre(p, "resumo"):
                itens = (("MELHOR", r.get("minimo")), ("MÉDIA", r.get("media")), ("PIOR", r.get("maximo")))
                for i, (rot, val) in enumerate(itens):
                    x = 14 + i * 110
                    p.setPen(B.COR_CINZA)
                    p.setFont(ft(7, QFont.DemiBold, p=p))
                    p.drawText(QRectF(x, 230, 100, 12), Qt.AlignLeft | Qt.AlignVCenter, rot)
                    p.setPen(B.COR_TEXTO)
                    p.setFont(ft(14, QFont.Bold, p=p))
                    p.drawText(QRectF(x, 241, 100, 22), Qt.AlignLeft | Qt.AlignVCenter, "--" if val is None else f"{val:.0f}")
                self._fecha(p)
            if self._abre(p, "legenda"):
                p.setPen(B.COR_CINZA)
                p.setFont(ft(7, QFont.DemiBold, p=p))
                p.drawText(QRectF(14, 266, 160, 16), Qt.AlignLeft | Qt.AlignVCenter, "SÓ ACELERADOR PLENO")
                p.drawText(QRectF(160, 266, 120, 16), Qt.AlignCenter, "RPM")
                p.drawText(QRectF(self.LARG - 174, 266, 160, 16), Qt.AlignRight | Qt.AlignVCenter, "MENOR É MELHOR")
                self._fecha(p)

    # ================================================================== 3. Destino do combustivel
    class JanelaDestino(JB):
        """Destino do combustivel: parcela do combustivel medido por faixa de acelerador (linhas) e de RPM (colunas), com a celula atual."""
        CHAVE = "destino"
        CHAVE_ATIVO = "mostrar_destino"
        TAXA_HZ = 4.0
        LARG = 440
        ELEMENTOS = (("titulo", "Título e stint"), ("barras", "Tabela por faixa de acelerador e RPM"), ("rpm", "Faixas de RPM (cabeçalho e cores por célula)"),
                     ("totais", "Barra a fundo, parcial e solto"), ("destaque", "Onde mais gasta"))
        SECOES = (("titulo", 0, 28), ("barras", 28, 184), ("totais", 214, 36), ("destaque", 252, 40))
        DEPENDE = {"rpm": "barras"}                                # build av: cabecalho de RPM faz parte da tabela
        NOMES = {"FLAT": "A FUNDO", "HIGH": "ALTO", "MID": "MÉDIO", "LOW": "BAIXO", "COAST": "SOLTO"}
        FAIXAS = {"FLAT": "90–100%", "HIGH": "60–90%", "MID": "30–60%", "LOW": "5–30%", "COAST": "0–5%"}

        def tamanho(self):
            return (self.LARG, self._alt_util(296))

        @staticmethod
        def _pct(v):
            return "<1%" if 0 < v < 0.01 else f"{v * 100:.0f}%"

        def paintEvent(self, _e):
            p = self._pintor()
            d = self.dados
            if not self._fundo(p, d["conectado"], "Aguardando o jogo..."):
                return
            r = v18d(d).get("destino") or {}
            em_litros = cfg_bool(self, "destino_litros", False)
            total = r.get("total_l") or 0.0
            faixas = r.get("faixas") or []
            atual = r.get("atual")
            rpm_max = r.get("rpm_max") or v18d(d).get("rpm_max")
            if self._abre(p, "titulo"):
                titulo(p, "DESTINO DO COMBUSTÍVEL", self.LARG)
                sl, sv = r.get("stint_l"), r.get("stint_voltas")
                p.setPen(B.COR_TEXTO)
                p.setFont(ft(8, QFont.Bold, p=p))
                p.drawText(QRectF(14, 6, self.LARG - 28, 20), Qt.AlignRight | Qt.AlignVCenter,
                           f"STINT {sl or 0:.1f} L · {sv or 0} {'VOLTA' if sv == 1 else 'VOLTAS'}")
                self._fecha(p)
            if self._abre(p, "barras"):
                x0, cw, y0, ch = 66, 36, 54, 27
                if rpm_max and self._abre(p, "rpm"):
                    lims = v18.limites_rpm(rpm_max)
                    p.setFont(ft(8, QFont.Bold, p=p))
                    for ci in range(v18.N_COLS):
                        p.setPen(B.COR_TEXTO if not (atual and atual[1] == ci) else Q(255, 255, 255))
                        p.drawText(QRectF(x0 + ci * cw, 30, cw, 16), Qt.AlignCenter, kfmt(lims[ci][0]))
                    p.setPen(Qt.NoPen)
                    p.setBrush(Q(255, 221, 40))
                    p.drawRect(QRectF(x0 + (v18.N_COLS - 3) * cw + 2, 47, 3 * cw - 4, 2))
                    self._fecha(p)
                p.setFont(ft(7, QFont.DemiBold, p=p))
                p.setPen(B.COR_CINZA)
                p.drawText(QRectF(8, 30, 56, 16), Qt.AlignLeft | Qt.AlignVCenter, "RPM")
                maior_c = max([c_ for f in faixas for c_ in (f.get("celulas") or []) if c_] or [1e-9])
                for i, f in enumerate(faixas):
                    y = y0 + i * (ch + 3)
                    p.setPen(B.COR_TEXTO)
                    p.setFont(ft(9, QFont.Bold, p=p))
                    p.drawText(QRectF(8, y, 58, ch * 0.6), Qt.AlignLeft | Qt.AlignVCenter, self.NOMES.get(f["nome"], f["nome"]))
                    p.setPen(B.COR_CINZA)
                    p.setFont(ft(7, p=p))
                    p.drawText(QRectF(8, y + ch * 0.55, 58, ch * 0.4), Qt.AlignLeft | Qt.AlignVCenter, self.FAIXAS.get(f["nome"], ""))
                    cells = f.get("celulas") or []
                    for ci in range(v18.N_COLS):
                        c_ = cells[ci] if ci < len(cells) else None
                        ret = QRectF(x0 + ci * cw + 1, y, cw - 2, ch)
                        p.setPen(Qt.NoPen)
                        if not c_:
                            p.setBrush(Q(255, 255, 255, 14))
                            p.drawRoundedRect(ret, 3, 3)
                        else:
                            t = (c_ / maior_c) ** 0.6 if self.visivel("rpm") else 0.7
                            p.setBrush(Q(*mistura((86, 24, 32), (232, 52, 58), t)))
                            p.drawRoundedRect(ret, 3, 3)
                            p.setPen(Q(255, 255, 255))
                            p.setFont(ft(8, QFont.Bold, p=p))
                            p.drawText(ret, Qt.AlignCenter, (("<0.1" if c_ * total < 0.1 else f"{c_ * total:.1f}") if em_litros else self._pct(c_)))
                        if atual and atual[0] == f["nome"] and atual[1] == ci:
                            p.setBrush(Qt.NoBrush)
                            p.setPen(QPen(Q(255, 255, 255), 2))
                            p.drawRoundedRect(ret, 3, 3)
                self._fecha(p)
            if self._abre(p, "totais"):
                faixa_p = {f["nome"]: f.get("parcela") for f in faixas}
                flat = faixa_p.get("FLAT") or 0.0
                coast = faixa_p.get("COAST") or 0.0
                parcial = r.get("parcial") if r.get("parcial") is not None else 0.0
                x, larg_b, y = 14, self.LARG - 28, 218
                p.setPen(Qt.NoPen)
                p.setBrush(Q(255, 255, 255, 20))
                p.drawRoundedRect(QRectF(x, y, larg_b, 16), 3, 3)
                if total > 0:
                    segs = (("A FUNDO", flat, Q(232, 52, 58), Q(255, 255, 255)), ("PARCIAL", parcial, Q(255, 240, 150), Q(30, 26, 8)),
                            ("", coast, Q(235, 238, 245), Q(30, 26, 8)))
                    xx = x
                    for nome, par, cor, tx in segs:
                        wseg = larg_b * par
                        if wseg <= 0.4:
                            continue
                        p.setPen(Qt.NoPen)
                        p.setBrush(cor)
                        p.drawRect(QRectF(xx, y, max(2.0, wseg), 16))
                        if nome and wseg > 70:
                            p.setPen(tx)
                            p.setFont(ft(8, QFont.Bold, p=p))
                            p.drawText(QRectF(xx, y, wseg, 16), Qt.AlignCenter, f"{nome} {par * 100:.0f}%")
                        xx += wseg
                    p.setPen(B.COR_CINZA)
                    p.setFont(ft(7, QFont.DemiBold, p=p))
                    p.drawText(QRectF(x, y + 18, larg_b, 12), Qt.AlignRight | Qt.AlignVCenter, f"SOLTO {self._pct(coast)}")
                self._fecha(p)
            if self._abre(p, "destaque"):
                m = r.get("maior")
                p.setFont(ft(9, QFont.DemiBold, p=p))
                if m and rpm_max:
                    lo, hi = v18.limites_rpm(rpm_max)[m["col"]]
                    p.setPen(Qt.NoPen)
                    p.setBrush(Q(232, 52, 58))
                    p.drawRect(QRectF(14, 262, 9, 9))
                    p.setPen(B.COR_TEXTO)
                    p.drawText(QRectF(30, 256, self.LARG - 44, 20), Qt.AlignLeft | Qt.AlignVCenter,
                               f"Maior zona: {self.NOMES.get(m['faixa'], m['faixa']).lower()} entre {kfmt(lo)} e {kfmt(hi)} rpm, {m['parcela'] * 100:.0f}% do combustível")
                else:
                    p.setPen(B.COR_CINZA)
                    p.drawText(QRectF(14, 256, self.LARG - 28, 20), Qt.AlignLeft | Qt.AlignVCenter, "Medindo... dirija algumas voltas.")
                p.setPen(B.COR_CINZA)
                p.setFont(ft(8, p=p))
                p.drawText(QRectF(14, 276, self.LARG - 28, 16), Qt.AlignLeft | Qt.AlignVCenter,
                           f"Medido pelo nível do tanque: {total:.1f} L no total · células em {'litros' if em_litros else '% do total'}")
                self._fecha(p)

    # ================================================================== 4. Digiflag
    class JanelaDigiflag(JB):
        """Digiflag: painel colorido com a bandeira em vigor (le a mesma deteccao da janela Bandeiras)."""
        CHAVE = "digiflag"
        CHAVE_ATIVO = "mostrar_digiflag"
        TAXA_HZ = 15.0
        LARG, ALT = 260, 120
        ELEMENTOS = (("painel", "Painel colorido"), ("texto", "Nome da bandeira"), ("sub", "Explicação"), ("borda", "Borda (pulsa nas bandeiras de atenção)"))
        SECOES = ()

        def tamanho(self):
            return (self.LARG, self.ALT)

        def paintEvent(self, _e):
            p = self._pintor()
            d = self.dados
            if not self._fundo(p, d["conectado"], "Aguardando o jogo...", com_fundo=False):
                return
            b = d.get("bandeira") or {}
            ident = b.get("id") or "verde"
            cor = b.get("cor") or (60, 210, 100)
            ret = QRectF(2, 2, self.LARG - 4, self.ALT - 4)
            fase = (time.monotonic() * 2.5) % 1.0
            pisca = cfg_bool(self, "digiflag_piscar", True) and ident not in ("verde", "nenhuma")
            if self._abre(p, "painel"):
                alfa = 235 if not pisca else int(150 + 90 * (0.5 + 0.5 * math.sin(fase * 2 * math.pi)))
                p.setPen(Qt.NoPen)
                p.setBrush(Q(cor[0], cor[1], cor[2], alfa))
                p.drawRoundedRect(ret, 12, 12)
                if ident == "quadriculada":
                    p.setBrush(Q(0, 0, 0, 230))
                    n = 12
                    cw = ret.width() / n
                    ch = ret.height() / 6
                    for i in range(n):
                        for k in range(6):
                            if (i + k) % 2 == 0:
                                p.drawRect(QRectF(ret.left() + i * cw, ret.top() + k * ch, cw, ch))
                elif ident == "azul":
                    p.setPen(QPen(Q(255, 255, 255, 220), 6))
                    p.drawLine(QPointF(ret.left() + 14, ret.bottom() - 14), QPointF(ret.right() - 14, ret.top() + 14))
                self._fecha(p)
            if self._abre(p, "borda"): # borda fixa e discreta; pulsa nas bandeiras de atencao
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(Q(255, 255, 255, int(255 * (0.5 + 0.5 * math.sin(fase * 2 * math.pi))) if pisca else 120), 3))
                p.drawRoundedRect(ret.adjusted(2, 2, -2, -2), 11, 11)
                self._fecha(p)
            escuro = (cor[0] * 0.299 + cor[1] * 0.587 + cor[2] * 0.114) > 150 and ident != "quadriculada"
            tc = Q(10, 10, 12) if escuro else Q(255, 255, 255)
            if ident == "quadriculada":
                tc = Q(255, 255, 255)
            if self._abre(p, "texto"):
                p.setPen(Q(0, 0, 0, 200) if ident == "quadriculada" else tc)
                p.setFont(ft(19, QFont.Bold, p=p))
                p.drawText(QRectF(8, 18, self.LARG - 16, 50), Qt.AlignCenter, str(b.get("titulo") or "BANDEIRA VERDE"))
                self._fecha(p)
            if self._abre(p, "sub"):
                p.setPen(tc)
                p.setFont(ft(10, QFont.DemiBold, p=p))
                p.drawText(QRectF(8, 68, self.LARG - 16, 32), Qt.AlignCenter | Qt.TextWordWrap, str(b.get("sub") or ""))
                self._fecha(p)

    # ================================================================== 5. Alerta de ultrapassagem
    class JanelaUltrapassagem(JA):
        """Alerta de ultrapassagem: carros de tras que estao perto e fechando. So aparece quando ha alerta (ou destravada)."""
        CHAVE = "ultrapassagem"
        CHAVE_ATIVO = "mostrar_ultrapassagem"
        TAXA_HZ = 12.0
        LARG = 330
        LIN = 34
        ELEMENTOS = (("titulo", "Título"), ("numero", "Número e classe"), ("nome", "Nome do piloto"), ("gap", "Diferença em segundos"),
                     ("taxa", "Velocidade de aproximação"))
        SECOES = ()

        def tamanho(self):
            return (self.LARG, 28 + 4 * self.LIN + 8)

        def atualizar(self, dados):
            carros = (v18d(dados).get("ultrapassagem") or {}).get("carros") or []
            auto = cfg_bool(self, "ultrap_auto", True) and bool(self.config.get("travado", True))
            self._definir_conteudo((not auto) or bool(carros))
            super().atualizar(dados)

        def paintEvent(self, _e):
            p = self._pintor()
            d = self.dados
            if not self._fundo(p, d["conectado"], "Aguardando o jogo..."):
                return
            carros = (v18d(d).get("ultrapassagem") or {}).get("carros") or []
            if self._abre(p, "titulo"):
                titulo(p, "VEM ALGUÉM ATRÁS", self.LARG)
                self._fecha(p)
            if not carros:
                p.setPen(B.COR_CINZA)
                p.setFont(ft(10, p=p))
                p.drawText(QRectF(14, 30, self.LARG - 28, 60), Qt.AlignCenter, "Nenhum carro se aproximando por trás.")
                return
            for i, c in enumerate(carros[:4]):
                y = 30 + i * self.LIN
                gap = c.get("gap") or 9.9
                urg = 1.0 - min(1.0, max(0.0, (gap - 0.3) / 3.0))
                p.setPen(Qt.NoPen)
                p.setBrush(Q(255, 255, 255, int(14 + 40 * urg)))
                p.drawRoundedRect(QRectF(8, y, self.LARG - 16, self.LIN - 4), 6, 6)
                p.setBrush(escala_boa_ruim(1.0 - min(1.0, gap / 3.0)))
                p.drawRoundedRect(QRectF(8, y, 5, self.LIN - 4), 2, 2)
                x = 20
                if self._abre(p, "numero"):
                    cor = c.get("cor") or (170, 170, 185)
                    p.setBrush(Q(*cor))
                    p.drawRoundedRect(QRectF(x, y + 4, 46, self.LIN - 12), 5, 5)
                    p.setPen(Q(10, 10, 12))
                    p.setFont(ft(11, QFont.Bold, p=p))
                    p.drawText(QRectF(x, y + 4, 46, self.LIN - 12), Qt.AlignCenter, f"#{c.get('numero', '')}")
                    x += 54
                    self._fecha(p)
                if self._abre(p, "nome"):
                    p.setPen(B.COR_TEXTO)
                    p.setFont(ft(10, QFont.DemiBold, p=p))
                    p.drawText(QRectF(x, y, 132, self.LIN - 4), Qt.AlignLeft | Qt.AlignVCenter, v18.nome_curto(c.get("nome", "")))
                    self._fecha(p)
                if self._abre(p, "gap"):
                    p.setPen(B.COR_TEXTO)
                    p.setFont(ft(13, QFont.Bold, p=p))
                    p.drawText(QRectF(self.LARG - 126, y, 52, self.LIN - 4), Qt.AlignRight | Qt.AlignVCenter, f"{gap:.1f}s")
                    self._fecha(p)
                if c.get("fecha") and self._abre(p, "taxa"):
                    p.setPen(B.COR_AMARELO)
                    p.setFont(ft(9, QFont.Bold, p=p))
                    p.drawText(QRectF(self.LARG - 68, y, 58, self.LIN - 4), Qt.AlignLeft | Qt.AlignVCenter, "▲" + f"{c['fecha']:.2f}")
                    self._fecha(p)

    # ================================================================== 6. Calendario de corridas
    class JanelaCalendario(JB):
        """Calendario: proximas corridas lidas de um CSV do proprio piloto (o iRacing nao libera a agenda sem login)."""
        CHAVE = "calendario"
        CHAVE_ATIVO = "mostrar_calendario"
        TAXA_HZ = 1.0
        LARG = 340
        LIN = 44
        ELEMENTOS = (("titulo", "Título"), ("classe", "Classe da corrida"), ("hora", "Horário de início"), ("contagem", "Contagem regressiva"),
                     ("registro", "Fechamento do registro"))
        SECOES = ()

        def tamanho(self):
            return (self.LARG, 32 + 4 * self.LIN + 6)

        @staticmethod
        def _fmt_contagem(seg):
            seg = int(seg)
            if seg < 0:
                return "em andamento"
            h, r = divmod(seg, 3600)
            m, s = divmod(r, 60)
            if h >= 24:
                return f"em {h // 24} d {h % 24} h"
            return f"em {h} h {m:02d} min" if h else f"em {m} min {s:02d} s"

        def paintEvent(self, _e):
            p = self._pintor()
            d = self.dados
            if not self._fundo(p, d["conectado"], "Aguardando o jogo..."):
                return
            itens = v18d(d).get("calendario") or []
            if self._abre(p, "titulo"):
                titulo(p, "ALERTA DE CORRIDA" if v18d(d).get("calendario_alerta") else "PRÓXIMAS CORRIDAS", self.LARG, str(v18d(d).get("calendario_fonte") or ""))
                self._fecha(p)
            if not itens:
                p.setPen(B.COR_CINZA)
                p.setFont(ft(9, p=p))
                p.drawText(QRectF(14, 30, self.LARG - 28, 4 * self.LIN), Qt.AlignCenter | Qt.TextWordWrap,
                           str(v18d(d).get("calendario_aviso") or "Sem corridas no arquivo calendario_corridas.csv."))
                return
            h24 = cfg_bool(self, "calendario_24h", True)
            for i, it in enumerate(itens[:4]):
                y = 32 + i * self.LIN
                p.setPen(Qt.NoPen)
                p.setBrush(Q(255, 255, 255, 18))
                p.drawRoundedRect(QRectF(8, y, self.LARG - 16, self.LIN - 4), 6, 6)
                andamento = it.get("em_andamento")
                p.setBrush(B.COR_VERDE if andamento else Q(255, 255, 255, 70))
                p.drawRoundedRect(QRectF(8, y, 5, self.LIN - 4), 2, 2)
                alerta = bool(it.get("alerta"))
                if alerta:                                  # cronograma: corrida dos seus filtros prestes a comecar
                    p.setBrush(Q(255, 150, 40, 70))
                    p.drawRoundedRect(QRectF(8, y, self.LARG - 16, self.LIN - 4), 6, 6)
                    p.setBrush(B.COR_AMARELO)
                    p.drawRoundedRect(QRectF(8, y, 5, self.LIN - 4), 2, 2)
                p.setPen(B.COR_TEXTO)
                p.setFont(ft(10, QFont.Bold, p=p))
                nome = str(it.get("nome", ""))
                p.drawText(QRectF(20, y + 2, 190, 18), Qt.AlignLeft | Qt.AlignVCenter,
                           QFontMetrics(ft(10, QFont.Bold, p=p)).elidedText(nome, Qt.ElideRight, 190))
                if it.get("classe") and self._abre(p, "classe"):
                    p.setPen(B.COR_AMARELO)
                    p.setFont(ft(8, QFont.Bold, p=p))
                    p.drawText(QRectF(210, y + 2, 56, 18), Qt.AlignLeft | Qt.AlignVCenter, str(it["classe"]))
                    self._fecha(p)
                if self._abre(p, "hora"):
                    ini = it["inicio"]
                    txt = ini.strftime("%H:%M") if h24 else ini.strftime("%I:%M %p").lstrip("0")
                    p.setPen(B.COR_TEXTO)
                    p.setFont(ft(11, QFont.Bold, p=p))
                    p.drawText(QRectF(self.LARG - 86, y + 2, 72, 18), Qt.AlignRight | Qt.AlignVCenter, txt)
                    self._fecha(p)
                if self._abre(p, "contagem"):
                    p.setPen(B.COR_AMARELO if alerta else (B.COR_VERDE if andamento else B.COR_CINZA))
                    p.setFont(ft(9, QFont.Bold if alerta else QFont.DemiBold, p=p))
                    p.drawText(QRectF(20, y + 21, 110, 16), Qt.AlignLeft | Qt.AlignVCenter, self._fmt_contagem(it["ate_inicio_s"]))
                    self._fecha(p)
                if it.get("pista"):
                    p.setPen(B.COR_CINZA)
                    p.setFont(ft(8, p=p))
                    p.drawText(QRectF(112, y + 21, self.LARG - 128, 16), Qt.AlignRight | Qt.AlignVCenter,
                               QFontMetrics(ft(8, p=p)).elidedText(str(it["pista"]), Qt.ElideLeft, self.LARG - 128))
                rg = it.get("reg_s")
                if rg is not None and self._abre(p, "registro"):
                    p.setPen(B.COR_AMARELO if 0 < rg < 600 else B.COR_CINZA)
                    p.setFont(ft(8, p=p))
                    p.drawText(QRectF(160, y + 21, self.LARG - 176, 16), Qt.AlignRight | Qt.AlignVCenter,
                               "registro aberto: " + self._fmt_contagem(rg).replace("em ", "") if rg > 0 else "registro fechado")
                    self._fecha(p)

    # ================================================================== 7. Energia hibrida / Boost box
    class JanelaHibrido(JB):
        """Boost box: carga da bateria, uso do deploy e os valores da volta anterior (so quando o jogo informa)."""
        CHAVE = "hibrido"
        CHAVE_ATIVO = "mostrar_hibrido"
        TAXA_HZ = 10.0
        LARG = 280
        ELEMENTOS = (("titulo", "Título"), ("bateria", "Carga da bateria"), ("deploy", "Uso do deploy"), ("ultima", "Volta anterior"),
                     ("estado", "Estado (propulsão / regeneração)"))
        SECOES = (("titulo", 0, 28), ("bateria", 28, 58), ("deploy", 86, 58), ("ultima", 144, 40))

        def tamanho(self):
            return (self.LARG, self._alt_util(184))

        def _barra(self, p, y, rot, valor, cor, bloco=False, ref=None):
            p.setPen(B.COR_CINZA)
            p.setFont(ft(8, QFont.DemiBold, p=p))
            p.drawText(QRectF(14, y, 150, 14), Qt.AlignLeft | Qt.AlignVCenter, rot)
            p.setPen(B.COR_TEXTO)
            p.setFont(ft(15, QFont.Bold, p=p))
            p.drawText(QRectF(self.LARG - 94, y - 2, 80, 24), Qt.AlignRight | Qt.AlignVCenter, "--" if valor is None else f"{valor * 100:.0f}%")
            p.setPen(Qt.NoPen)
            p.setBrush(Q(255, 255, 255, 26))
            p.drawRoundedRect(QRectF(14, y + 24, self.LARG - 28, 14), 4, 4)
            if valor is not None:
                p.setBrush(cor)
                p.drawRoundedRect(QRectF(14, y + 24, (self.LARG - 28) * max(0.01, valor), 14), 4, 4)
            if ref is not None:
                p.setPen(QPen(Q(255, 255, 255, 230), 2))
                x = 14 + (self.LARG - 28) * ref
                p.drawLine(QPointF(x, y + 21), QPointF(x, y + 41))

        def paintEvent(self, _e):
            p = self._pintor()
            d = self.dados
            if not self._fundo(p, d["conectado"], "Aguardando o jogo..."):
                return
            h = v18d(d).get("hibrido")
            if self._abre(p, "titulo"):
                titulo(p, "ENERGIA HÍBRIDA", self.LARG)
                self._fecha(p)
            if h and self._abre(p, "estado"):
                titulo_direita(p, "ENTREGANDO" if h.get("ativo") else "RECARREGANDO/PARADO", self.LARG)
                self._fecha(p)
            if h is None:
                p.setPen(B.COR_CINZA)
                p.setFont(ft(9, p=p))
                p.drawText(QRectF(14, 32, self.LARG - 28, self.height() / max(0.01, self.escala_y) - 40), Qt.AlignCenter | Qt.TextWordWrap,
                           "Este carro não informa dados do sistema híbrido.")
                return
            if self._abre(p, "bateria"):
                baixa = h["carga"] < 0.15 and cfg_bool(self, "hibrido_alerta", True)
                cor = B.COR_VERMELHO if baixa and int(time.monotonic() * 3) % 2 == 0 else escala_boa_ruim(1.0 - h["carga"])
                self._barra(p, 34, "BATERIA", h["carga"], cor, ref=h.get("ult_carga"))
                self._fecha(p)
            if self._abre(p, "deploy"):
                self._barra(p, 92, "DEPLOY NA VOLTA", h.get("deploy"), Q(70, 170, 235), ref=h.get("ult_deploy"))
                self._fecha(p)
            if self._abre(p, "ultima"):
                p.setPen(B.COR_CINZA)
                p.setFont(ft(8, QFont.DemiBold, p=p))
                uc, ud = h.get("ult_carga"), h.get("ult_deploy")
                p.drawText(QRectF(14, 148, self.LARG - 28, 30), Qt.AlignLeft | Qt.AlignVCenter,
                           "VOLTA ANTERIOR  bateria " + ("--" if uc is None else f"{uc * 100:.0f}%") + "  ·  deploy " + ("--" if ud is None else f"{ud * 100:.0f}%"))
                self._fecha(p)

    # ================================================================== 8. Relogio da sessao
    class JanelaSessao(JB):
        """Tempo da sessao: tempo (ou voltas) restante com barra de progresso."""
        CHAVE = "sessao"
        CHAVE_ATIVO = "mostrar_sessao"
        TAXA_HZ = 4.0
        LARG = 260
        ELEMENTOS = (("rotulo", "Rótulo (tempo ou voltas)"), ("relogio", "Relógio grande"), ("barra", "Barra de progresso"), ("percentual", "Percentual corrido"))
        SECOES = (("rotulo", 0, 26), ("relogio", 26, 52), ("barra", 78, 22))

        def tamanho(self):
            return (self.LARG, self._alt_util(104))

        def paintEvent(self, _e):
            p = self._pintor()
            d = self.dados
            if not self._fundo(p, d["conectado"], "Aguardando o jogo..."):
                return
            s = v18d(d).get("sessao")
            if s is None:
                p.setPen(B.COR_CINZA)
                p.setFont(ft(10, p=p))
                p.drawText(QRectF(14, 8, self.LARG - 28, 88), Qt.AlignCenter | Qt.TextWordWrap, "Sem tempo ou voltas definidos para esta sessão.")
                return
            if self._abre(p, "rotulo"):
                titulo(p, "TEMPO RESTANTE" if s["modo"] == "tempo" else "VOLTAS RESTANTES", self.LARG)
                self._fecha(p)
            if s.get("fracao") is not None and self._abre(p, "percentual"):
                titulo_direita(p, f"{s['fracao'] * 100:.0f}% corrido", self.LARG)
                self._fecha(p)
            if self._abre(p, "relogio"):
                texto = s["texto"]
                if s["modo"] == "tempo" and cfg_bool(self, "sessao_hms", False):
                    seg = int(s["restante"])
                    texto = f"{seg // 3600}:{(seg % 3600) // 60:02d}:{seg % 60:02d}"
                crit = s["modo"] == "tempo" and s["restante"] < 300
                p.setPen(B.COR_AMARELO if crit else B.COR_TEXTO)
                p.setFont(ft(28, QFont.Bold, p=p))
                p.drawText(QRectF(10, 28, self.LARG - 20, 48), Qt.AlignCenter, texto)
                self._fecha(p)
            if self._abre(p, "barra"):
                if s.get("fracao") is not None:
                    p.setPen(Qt.NoPen)
                    p.setBrush(Q(255, 255, 255, 26))
                    p.drawRoundedRect(QRectF(14, 82, self.LARG - 28, 10), 5, 5)
                    p.setBrush(B.COR_AMARELO if s["fracao"] > 0.9 else Q(255, 255, 255, 200))
                    p.drawRoundedRect(QRectF(14, 82, (self.LARG - 28) * max(0.01, s["fracao"]), 10), 5, 5)
                self._fecha(p)

    # ================================================================== 9. Pedais do Coach (build ap)
    class JanelaCoachPedais(JB):
        """Pedais do Coach: o que fazer AGORA com freio e acelerador (FREIE, TRAIL BRAKING, SOLTE, ACELERE, PE FUNDO), a % alvo de
        freio da referencia e a sua % ao vivo, com a marca da referencia nas barras. Pode ser colocada em qualquer lugar da tela."""
        CHAVE = "coach_pedais"
        CHAVE_ATIVO = "mostrar_coach_pedais"
        TAXA_HZ = 30.0
        LARG = 320
        ELEMENTOS = (("fase", "Instrução (freie, trail braking, solte, acelere)"), ("barras", "Barras de freio e acelerador (você x referência)"),
                     ("plano", "Próxima freada (% alvo e trail)"))
        SECOES = (("fase", 0, 62), ("barras", 62, 74), ("plano", 136, 30))
        TEXTOS = {"frear": ("FREIE", "vermelho"), "trail": ("TRAIL BRAKING", "laranja"), "soltar_freio": ("SOLTE O FREIO", "laranja"),
                  "soltar": ("SOLTE O ACELERADOR", "amarelo"), "acelerar": ("ACELERE", "verde"), "fundo": ("PÉ FUNDO", "verde")}

        def tamanho(self):
            return (self.LARG, self._alt_util(168))

        def centralizar(self, horizontal=True, vertical=False):
            """Centraliza a janela na tela do jogo (a principal) e grava a posicao."""
            from PySide6.QtGui import QGuiApplication
            tela = QGuiApplication.primaryScreen()
            if tela is None:
                return False
            g = tela.geometry()
            x = g.x() + (g.width() - self.width()) // 2 if horizontal else self.x()
            y = g.y() + (g.height() - self.height()) // 2 if vertical else self.y()
            self.move(int(x), int(y))
            self.config[self._chave("x")], self.config[self._chave("y")] = int(x), int(y)
            return True

        @staticmethod
        def _exemplo():
            return {"fase": "trail", "alvo_freio_pct": 62, "alvo_acel_pct": None, "freio_ref_pct": 62, "acel_ref_pct": 0, "pico_pct": 92,
                    "trail": True, "freio_pct": 55, "acel_pct": 0,
                    "_plano": {"n": 3, "dist_m": 84, "pico_pct": 92, "trail": True, "trail_m": 28.0, "freio_apice_pct": 18, "acel_saida_pct": 65}}

        def _cor(self, nome):
            return {"vermelho": B.COR_VERMELHO, "laranja": B.COR_LARANJA, "amarelo": B.COR_AMARELO, "verde": B.COR_VERDE}.get(nome, B.COR_TEXTO)

        def _barra_pedal(self, p, y, nome, cor, vivo, ref):
            p.setPen(B.COR_CINZA)
            p.setFont(ft(9, QFont.DemiBold, p=p))
            p.drawText(QRectF(14, y, 62, 22), Qt.AlignLeft | Qt.AlignVCenter, nome)
            x0, larg = 80.0, self.LARG - 80 - 62.0
            p.setPen(Qt.NoPen)
            p.setBrush(Q(255, 255, 255, 26))
            p.drawRoundedRect(QRectF(x0, y + 4, larg, 14), 4, 4)
            if vivo is not None:
                p.setBrush(cor)
                p.drawRoundedRect(QRectF(x0, y + 4, max(2.0, larg * vivo / 100.0), 14), 4, 4)
            if ref is not None:                                   # marca da referencia: onde o pedal DEVERIA estar aqui
                xr = x0 + larg * ref / 100.0
                p.setPen(QPen(Q(255, 255, 255, 235), 2.5))
                p.drawLine(QPointF(xr, y), QPointF(xr, y + 22))
            p.setPen(B.COR_TEXTO)
            p.setFont(ft(14, QFont.Bold, p=p))
            p.drawText(QRectF(self.LARG - 58, y - 2, 46, 26), Qt.AlignRight | Qt.AlignVCenter, "--" if vivo is None else f"{vivo:.0f}%")

        def paintEvent(self, _e):
            p = self._pintor()
            d = self.dados
            if not self._fundo(p, d["conectado"], "Aguardando o jogo..."):
                return
            c = d.get("coach") or {}
            ped = c.get("pedais")
            exemplo = False
            if not ped and (not self.config["travado"] or d.get("previa") or getattr(self, "modo_previa", False)):
                ped, exemplo = self._exemplo(), True
            if not ped:
                p.setPen(B.COR_CINZA)
                p.setFont(ft(11, QFont.DemiBold, p=p))
                p.drawText(QRectF(14, 8, self.LARG - 28, 90), Qt.AlignCenter | Qt.TextWordWrap,
                           "Sem referência do Coach para esta pista e carro.\nDirija uma volta limpa para gravar.")
                return
            if self._abre(p, "fase"):
                texto, cor = self.TEXTOS.get(ped.get("fase"), ("--", "cinza"))
                p.setPen(self._cor(cor))
                p.setFont(ft(26 if len(texto) <= 14 else 20, QFont.Bold, p=p))
                p.drawText(QRectF(10, 4, self.LARG - 20, 38), Qt.AlignCenter, texto)
                alvo = ped.get("alvo_freio_pct") if ped.get("fase") in ("frear", "trail", "soltar_freio") else ped.get("alvo_acel_pct")
                sub = "" if alvo is None else (f"freio alvo {alvo}%" if ped.get("fase") in ("frear", "trail", "soltar_freio") else f"acelerador alvo {alvo}%")
                if ped.get("fase") == "fundo" and ped.get("acel_ref_pct") is not None:
                    sub = f"acelerador {ped['acel_ref_pct']}%"
                if ped.get("fase") == "trail":
                    sub = "solte o freio aos poucos até o ápice · " + sub
                p.setPen(B.COR_CINZA)
                p.setFont(ft(9, QFont.DemiBold, p=p))
                p.drawText(QRectF(10, 40, self.LARG - 20, 18), Qt.AlignCenter,
                           QFontMetrics(p.font()).elidedText(sub, Qt.ElideRight, int(self.LARG - 24)))
                self._fecha(p)
            if self._abre(p, "barras"):
                self._barra_pedal(p, 66, "FREIO", B.COR_VERMELHO, ped.get("freio_pct"), ped.get("freio_ref_pct"))
                self._barra_pedal(p, 100, "ACELER.", B.COR_VERDE, ped.get("acel_pct"), ped.get("acel_ref_pct"))
                self._fecha(p)
            if self._abre(p, "plano"):
                pl = ((c.get("proxima") or {}).get("plano")) or ped.get("_plano")
                pr = c.get("proxima") or ped.get("_plano") or {}
                p.setPen(B.COR_CINZA)
                p.setFont(ft(9, QFont.DemiBold, p=p))
                fm = QFontMetrics(p.font())
                if pl:
                    trail = f"trail {pl['trail_m']:.0f} m" if pl.get("trail") else "sem trail (solta de vez)"
                    sai = pl.get("acel_saida_pct")
                    l1 = f"C{pr.get('n', '?')} em {pr.get('dist_m', 0):.0f} m · freio {pl['pico_pct']}%"
                    l2 = trail + ("" if sai is None else f" · acel saída {sai}%")
                else:
                    l1, l2 = "Sem zona de frenagem à frente", ""
                for yy, tx in ((137, l1), (151, l2)):
                    if tx:
                        p.drawText(QRectF(14, yy, self.LARG - 28, 14), Qt.AlignLeft | Qt.AlignVCenter,
                                   fm.elidedText(tx, Qt.ElideRight, int(self.LARG - 28)))
                self._fecha(p)

    for K, rot in ((JanelaVazao, "Mostrar Mapa de vazão (consumo por RPM x acelerador)"), (JanelaMarcha, "Mostrar Eficiência por marcha"),
                   (JanelaDestino, "Mostrar Destino do combustível"), (JanelaDigiflag, "Mostrar Digiflag (bandeira em painel colorido)"),
                   (JanelaUltrapassagem, "Mostrar Alerta de ultrapassagem"), (JanelaCalendario, "Mostrar Calendário de corridas"),
                   (JanelaHibrido, "Mostrar Energia híbrida (Boost)"), (JanelaSessao, "Mostrar Tempo da sessão"),
                   (JanelaCoachPedais, "Mostrar Pedais do Coach (freio %, trail braking, soltar e acelerar)")):
        K.ROTULO_MENU = rot
    return {"vazao": JanelaVazao, "marcha_efic": JanelaMarcha, "destino": JanelaDestino, "digiflag": JanelaDigiflag,
            "ultrapassagem": JanelaUltrapassagem, "calendario": JanelaCalendario, "hibrido": JanelaHibrido, "sessao": JanelaSessao,
            "coach_pedais": JanelaCoachPedais}
