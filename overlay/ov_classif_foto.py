# -*- coding: utf-8 -*-
"""
v1.6.1 - Janela de classificacao no layout "foto" (tabela estilo transmissao).

Duas partes:
  1) LOGICA PURA (sem Qt e sem SDK, testavel em qualquer sistema): gap e intervalo por carro, contagem de paradas e stint,
     sigla do pneu, variacao projetada de iRating por carro e montagem da barra superior (sessao, voltas, tempo,
     temperaturas, umidade, incidentes, pista).
  2) JANELA (construir): JanelaClassificacaoFoto, subclasse da JanelaClassificacao original. So e criada quando o
     overlay a pede (construir(base)); se este arquivo faltar, o overlay segue com a classificacao antiga.

Colunas: POS, +/-, #, pneu, LIC . iR (com a variacao projetada), marca, pais, PILOTO, GAP, INT, MELHOR, ULTIMA, PIT, STINT.
O gap e o intervalo, na corrida, sao ESTIMADOS: diferenca de progresso na pista (voltas + fracao) x tempo de volta de
referencia da classe. Fora da corrida, sao a diferenca entre as melhores voltas.
"""
import math
import statistics

IDIOMAS = {
    "en": {"pos": "POS", "carro": "#", "pneu": "", "lic": "LIC · iR", "piloto": "DRIVER", "gap": "GAP", "int": "INT",
           "melhor": "BEST", "ultima": "LAST", "pit": "PIT", "stint": "STINT", "sof": "SOF",
           "sessao": {"CORRIDA": "RACE", "QUALIFICACAO": "QUALIFY", "TREINO": "PRACTICE", "TESTE": "TEST",
                      "AQUECIMENTO": "WARMUP"},
           "clima": {"seco": "Dry", "umido": "Damp", "molhado": "Wet", "chuva": "Rain"},
           "volta": "LAP", "sem_dados": "No standings data"},
    "pt": {"pos": "POS", "carro": "#", "pneu": "", "lic": "LIC · iR", "piloto": "PILOTO", "gap": "GAP", "int": "INT",
           "melhor": "MELHOR", "ultima": "ULTIMA", "pit": "PIT", "stint": "STINT", "sof": "SOF",
           "sessao": {"CORRIDA": "CORRIDA", "QUALIFICACAO": "CLASSIF", "TREINO": "TREINO", "TESTE": "TESTE",
                      "AQUECIMENTO": "AQUEC."},
           "clima": {"seco": "Seca", "umido": "Umida", "molhado": "Molhada", "chuva": "Chuva"},
           "volta": "VOLTA", "sem_dados": "Sem dados de classificacao"},
}


def textos(idioma):
    return IDIOMAS.get(str(idioma or "en").lower(), IDIOMAS["en"])


# --------------------------------------------------------------------------
# Formatacao
# --------------------------------------------------------------------------
def fmt_gap(valor):
    """None -> '--'; voltas ({'voltas': 2}) -> '+2L'; segundos -> '+1.234' (ou '+1:05.2' acima de 1 minuto)."""
    if valor is None:
        return "--"
    if isinstance(valor, dict):
        return "+%dL" % valor["voltas"]
    if valor < 0.0005:
        return "0.000"
    if valor >= 60.0:
        m = int(valor // 60)
        return "+%d:%04.1f" % (m, valor - m * 60)
    return "+%.3f" % valor


def fmt_ir_k(valor):
    """4800 -> '4.8k'; 10250 -> '10.3k'; sem valor -> '--'."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "--"
    if v <= 0:
        return "--"
    return "%.1fk" % (v / 1000.0)


def fmt_licenca(texto):
    """'A3.4' -> 'A 3.4'."""
    t = str(texto or "").strip()
    if len(t) >= 2 and t[0].isalpha():
        return t[0].upper() + " " + t[1:]
    return t


def fmt_duracao(seg):
    """Tempo decorrido: 154 -> '2:34'; 4000 -> '1:06:40'."""
    if seg is None:
        return "--:--"
    seg = int(max(0, seg))
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def fmt_duracao_total(seg):
    """Duracao da sessao: 2700 -> '45m'; 5400 -> '1h30m'; 3600 -> '1h'."""
    if seg is None:
        return "--"
    minutos = int(round(seg / 60.0))
    h, m = divmod(minutos, 60)
    if h and m:
        return "%dh%02dm" % (h, m)
    return "%dh" % h if h else "%dm" % m


# --------------------------------------------------------------------------
# Paradas e stint
# --------------------------------------------------------------------------
class ContadorParadas:
    """Paradas nos boxes e voltas desde a ultima parada, por carro.

    Uma parada conta quando o carro ficou PARADO na vaga (TrackSurface = 1) e depois saiu da pit lane; passagem sem parar
    (drive-through) nao conta. Se o overlay abriu depois da largada, o stint dos carros que ja tinham rodado e aproximado
    (confiavel = False) ate o carro passar por uma parada.
    """

    def __init__(self):
        self.resetar()

    def resetar(self):
        self.carros = {}
        self.chave = None

    @staticmethod
    def _item(lista, i, padrao=None):
        try:
            v = lista[i]
        except (TypeError, IndexError, KeyError):
            return padrao
        return padrao if v is None else v

    def atualizar(self, chave, completadas, box, superficie):
        if chave != self.chave:
            self.resetar()
            self.chave = chave
        if not completadas:
            return
        for idx, lap in enumerate(completadas):
            if lap is None or lap < 0:
                continue
            na_box = bool(self._item(box, idx, False))
            sup = self._item(superficie, idx, 3)
            c = self.carros.get(idx)
            if c is None:
                c = self.carros[idx] = {"n": 0, "inicio": 0, "parou": False, "box": na_box, "confiavel": lap <= 1}
            if sup == 1:                                   # parado na vaga do box
                c["parou"] = True
            if c["box"] and not na_box:                    # saiu da pit lane
                if c["parou"]:
                    c["n"] += 1
                    c["inicio"], c["confiavel"] = int(lap), True
                c["parou"] = False
            c["box"] = na_box

    def paradas(self, idx):
        c = self.carros.get(idx)
        return None if c is None else c["n"]

    def stint(self, idx, completadas):
        """(voltas desde a ultima parada, confiavel) ou (None, False)."""
        c = self.carros.get(idx)
        lap = self._item(completadas, idx, None)
        if c is None or lap is None:
            return None, False
        return max(0, int(lap) - c["inicio"]), c["confiavel"]


# --------------------------------------------------------------------------
# Pneu
# --------------------------------------------------------------------------
_SIGLAS = {"Duro": "H", "Medio": "M", "Macio": "S", "Chuva": "W", "Intermediario": "I"}


def sigla_pneu(rotulo):
    """Rotulo do composto (estilo_pneu) -> letra do circulo: H, M, S, W, I; 'Dry' e outros -> D (ou a inicial)."""
    if not rotulo:
        return ""
    if rotulo in _SIGLAS:
        return _SIGLAS[rotulo]
    return str(rotulo)[:1].upper()


# --------------------------------------------------------------------------
# Gap e intervalo
# --------------------------------------------------------------------------
def tempo_ref_classe(linhas, padrao):
    """Tempo de volta de referencia da classe: mediana das melhores voltas validas; sem elas, `padrao`."""
    melhores = [l["melhor"] for l in linhas if l.get("melhor")]
    if melhores:
        return float(statistics.median(melhores))
    return float(padrao) if padrao else None


def _diferenca(menor, maior, ref):
    """Diferenca de progresso (voltas.fracao) -> segundos ou {'voltas': n}. menor/maior: progresso de quem esta atras/a frente."""
    dif = maior - menor
    if dif < 0:
        dif = 0.0
    if dif >= 1.0:
        return {"voltas": int(dif)}
    if not ref:
        return None
    return dif * ref


def calcular_gap_int(linhas, tipo_sessao, progresso, ref_padrao):
    """Preenche linha['gap'] e linha['int'] de uma classe (linhas em ordem de posicao).

    Corrida: por progresso na pista x tempo de referencia da classe (estimado). Demais sessoes: diferenca das melhores voltas.
    Lider: gap e int None. Carro sem dado: None (a janela mostra '--').
    """
    corrida = tipo_sessao == "CORRIDA"
    ref = tempo_ref_classe(linhas, ref_padrao)
    lider = linhas[0] if linhas else None
    anterior = None
    for l in linhas:
        l["gap"] = l["int"] = None
        l["gap_estimado"] = corrida
        if anterior is not None and lider is not None:
            if corrida:
                pl, pa, pc = (progresso.get(lider.get("idx")), progresso.get(anterior.get("idx")),
                              progresso.get(l.get("idx")))
                if pc is not None and pl is not None:
                    l["gap"] = _diferenca(pc, pl, ref)
                if pc is not None and pa is not None:
                    l["int"] = _diferenca(pc, pa, ref)
            else:
                if l.get("melhor") and lider.get("melhor"):
                    l["gap"] = max(0.0, l["melhor"] - lider["melhor"])
                if l.get("melhor") and anterior.get("melhor"):
                    l["int"] = max(0.0, l["melhor"] - anterior["melhor"])
        anterior = l


# --------------------------------------------------------------------------
# iRating projetado por carro
# --------------------------------------------------------------------------
def projetar_ir_por_carro(linhas, variacao):
    """Preenche linha['ir_delta'] (inteiro; positivo = ganharia iRating) para os carros da classe.

    `variacao(ratings, posicao, i)` e o modelo do overlay (variacao_irating). Reclassifica 1..N pelos que tem iRating.
    """
    part = [(l["pos"], k, float(l["irating"])) for k, l in enumerate(linhas) if (l.get("irating") or 0) > 0]
    for l in linhas:
        l["ir_delta"] = None
    if len(part) < 2:
        return
    part.sort()
    ratings = [r for _, _, r in part]
    for i, (_, k, _) in enumerate(part):
        v = variacao(ratings, i + 1, i)
        linhas[k]["ir_delta"] = None if v is None else int(round(v))


# --------------------------------------------------------------------------
# Barra superior
# --------------------------------------------------------------------------
def _rotulo_clima(molhada, chuva, textos_clima):
    if chuva is not None and chuva >= 5.0:
        return textos_clima["chuva"]
    if molhada is None:
        return None
    if molhada <= 2:
        return textos_clima["seco"]
    if molhada <= 4:
        return textos_clima["umido"]
    return textos_clima["molhado"]


def montar_cabecalho(tipo_sessao, volta, voltas_total, restante, total, ar, pista, umidade, inc, inc_limite,
                     molhada, chuva_pct, ref_volta=None, fracao_volta=0.0, idioma="en"):
    """Dados da barra superior (tudo opcional; a janela omite o que estiver None)."""
    t = textos(idioma)
    unlimited = voltas_total is None or voltas_total <= 0 or voltas_total >= 30000
    decorrido = None
    if total is not None and restante is not None and 0 <= restante <= total + 1:
        decorrido = max(0.0, total - restante)
    estimativa = None
    if unlimited and restante is not None and ref_volta and ref_volta > 0 and volta and volta > 0:
        estimativa = (volta - 1) + (fracao_volta or 0.0) + restante / ref_volta
    if umidade is not None:
        umidade = umidade * 100.0 if umidade <= 1.0 else umidade
    return {
        "sessao": t["sessao"].get(tipo_sessao or "", (tipo_sessao or "").upper()),
        "volta": int(volta) if volta is not None else None,
        "voltas_total": None if unlimited else int(voltas_total),
        "voltas_estimadas": estimativa,
        "decorrido": decorrido,
        "total": total if (total is not None and 0 < total < 1e7) else None,
        "ar": ar, "pista": pista, "umidade": umidade,
        "inc": inc, "inc_limite": inc_limite,
        "clima": _rotulo_clima(molhada, chuva_pct, t["clima"]),
    }


# --------------------------------------------------------------------------
# Enriquecimento da classificacao (um unico ponto de entrada para a telemetria real e a demonstracao)
# --------------------------------------------------------------------------
def enriquecer(classif, tipo_sessao, progresso, ref_padrao, variacao, paradas=None, completadas=None,
               pneus=None, cabecalho=None):
    """Acrescenta a cada linha de classif['classes'][*]['linhas']: gap, int, paradas, stint, pneu, ir_delta.

    progresso : {idx: voltas completadas + fracao} ; paradas : ContadorParadas (ou None)
    pneus     : {idx: (cor, rotulo)} ; cabecalho : dict de montar_cabecalho
    """
    pneus = pneus or {}
    for classe in classif["classes"]:
        linhas = classe["linhas"]
        calcular_gap_int(linhas, tipo_sessao, progresso, ref_padrao)
        if tipo_sessao == "CORRIDA" and variacao is not None:
            projetar_ir_por_carro(linhas, variacao)
        for l in linhas:
            idx = l.get("idx")
            if paradas is not None:
                l["paradas"] = paradas.paradas(idx)
                l["stint"], l["stint_confiavel"] = paradas.stint(idx, completadas)
            est = pneus.get(idx)
            l["pneu"] = {"cor": est[0], "letra": sigla_pneu(est[1]), "nome": est[1]} if est else None
    classif["cabecalho"] = cabecalho
    return classif


# --------------------------------------------------------------------------
# Dados de demonstracao (modo --demo e testes)
# --------------------------------------------------------------------------
def entradas_demo(classif, volta, tempo):
    """(progresso, paradas, completadas, pneus, cabecalho) ficticios, coerentes com a ordem de classif."""
    progresso, completadas, pneus, estado = {}, {}, {}, {}
    comp = [((235, 235, 240), "Duro"), ((250, 200, 40), "Medio"), ((235, 70, 110), "Macio")]
    n = 0
    for classe in classif["classes"]:
        for k, l in enumerate(classe["linhas"]):
            idx = l["idx"]
            base = volta + (tempo % 12.0) / 12.0
            atraso = k * 0.011 + (0.045 * (k // 4)) + (1.02 if (n % 11 == 7 and not l["eu"]) else 0.0)
            progresso[idx] = max(0.0, base - atraso - (0.0 if k else 0.0))
            completadas[idx] = int(progresso[idx])
            pneus[idx] = comp[(idx + k) % 3] if (idx % 4) else comp[0]
            estado[idx] = idx
            n += 1

    class _Par(ContadorParadas):
        pass

    par = _Par()
    for idx in estado:
        par.carros[idx] = {"n": 1 if idx % 3 == 0 else (2 if idx % 7 == 0 else 0),
                           "inicio": max(0, completadas[idx] - (3 + idx % 9)), "parou": False, "box": False,
                           "confiavel": True}
    cab = montar_cabecalho("CORRIDA", 1 + volta, 0, 2700.0 - (154.0 + tempo), 2700.0, 24.0, 31.0, 0.45, 0, 25, 1, 0.0,
                           ref_volta=80.0, fracao_volta=(tempo % 12.0) / 12.0)
    return progresso, par, completadas, pneus, cab


# --------------------------------------------------------------------------
# Janela
# --------------------------------------------------------------------------
LARGURA_FOTO = 846
ALTURA_LINHA_FOTO = 26
ALTURA_BARRA = 36
ALTURA_ROTULOS = 18

_cache_classe = {}


def construir(base):
    """Cria (uma vez) e devolve a classe JanelaClassificacaoFoto, subclasse de base.JanelaClassificacao.
    `base` e o modulo do overlay (fonte, cores, emblemas e bandeiras vem dele)."""
    if "foto" in _cache_classe:
        return _cache_classe["foto"]
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainterPath, QPen

    class JanelaClassificacaoFoto(base.JanelaClassificacao):
        ALTURA_TOPO = ALTURA_BARRA + ALTURA_ROTULOS + 6

        X = {"pos": 12, "delta": 42, "num": 80, "pneu": 131, "lic": 158, "ir": 208, "ird": 250, "marca": 284,
             "pais": 318, "piloto": 348, "gap": 490, "int": 552, "melhor": 612, "ultima": 690, "pit": 768, "stint": 800}

        def __init__(self, config):
            self._tx = textos(config.get("classificacao_idioma", "en"))
            super().__init__(config)

        # -- tamanho -------------------------------------------------------------------
        def tamanho(self):
            return (LARGURA_FOTO, self._altura_base)

        def _altura_necessaria(self):
            if not self._blocos_atual:
                return self.ALTURA_PADRAO
            linhas = sum(1 + len(v) for _, v in self._blocos_atual)
            return self.ALTURA_TOPO + linhas * ALTURA_LINHA_FOTO + 10

        # -- pintura -------------------------------------------------------------------
        def paintEvent(self, _evento):
            p = self._pintor()
            d = self.dados
            if not self._fundo(p, d["conectado"]):
                return
            classif = d.get("classificacao")
            if not classif or not self._blocos_atual:
                p.setPen(base.COR_CINZA)
                p.setFont(base.fonte(12))
                p.drawText(self._retangulo_base(), Qt.AlignCenter, self._tx["sem_dados"])
                return
            self._barra(p, classif.get("cabecalho") or {})
            self._rotulos(p)
            y = self.ALTURA_TOPO
            for classe, linhas in self._blocos_atual:
                self._faixa_classe(p, y, classe)
                y += ALTURA_LINHA_FOTO
                for linha, salto in linhas:
                    self._linha_foto(p, y, linha, salto, QColor(*classe["cor"]))
                    y += ALTURA_LINHA_FOTO

        # barra superior ------------------------------------------------------------------
        def _barra(self, p, cab):
            h = ALTURA_BARRA
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 16))
            p.drawRoundedRect(QRectF(8, 6, LARGURA_FOTO - 16, h - 6), 8, 8)
            x = 16
            sessao = cab.get("sessao") or (self.dados.get("classificacao") or {}).get("tipo_sessao") or ""
            if sessao:
                f = base.fonte(9, QFont.Bold)
                larg = QFontMetrics(f).horizontalAdvance(sessao) + 18
                p.setBrush(QColor(176, 40, 56))
                p.drawRoundedRect(QRectF(x, 11, larg, 20), 5, 5)
                p.setFont(f)
                p.setPen(QColor(255, 255, 255))
                p.drawText(QRectF(x, 11, larg, 20), Qt.AlignCenter, sessao)
                x += larg + 16
            # voltas
            if cab.get("volta") is not None:
                total = cab.get("voltas_total")
                texto = "%d/%s" % (cab["volta"], "%d" % total if total else "∞")
                est = cab.get("voltas_estimadas")
                if est and not total:
                    texto += " = %.2f" % est
                x = self._item(p, x, texto, cor=QColor(255, 255, 255), tam=10, larg_min=60)
            if cab.get("decorrido") is not None and cab.get("total"):
                x = self._item(p, x, "%s / %s" % (fmt_duracao(cab["decorrido"]), fmt_duracao_total(cab["total"])),
                               cor=QColor(235, 235, 240), tam=10, larg_min=70)
            if cab.get("ar") is not None:
                x = self._item(p, x, "AIR %d°" % round(cab["ar"]), cor=base.COR_CINZA, tam=9)
            if cab.get("pista") is not None:
                x = self._item(p, x, "TRACK %d°" % round(cab["pista"]), cor=base.COR_CINZA, tam=9)
            if cab.get("umidade") is not None:
                x = self._item(p, x, "HUM %d%%" % round(cab["umidade"]), cor=base.COR_CINZA, tam=9)
            # lado direito: incidentes e pista
            xd = LARGURA_FOTO - 16
            if cab.get("clima"):
                f = base.fonte(10, QFont.Bold)
                larg = QFontMetrics(f).horizontalAdvance(cab["clima"]) + 8
                p.setFont(f)
                p.setPen(QColor(235, 235, 240))
                p.drawText(QRectF(xd - larg, 11, larg, 20), Qt.AlignRight | Qt.AlignVCenter, cab["clima"])
                xd -= larg + 14
            if cab.get("inc") is not None:
                lim = cab.get("inc_limite")
                txt = "%d/%d" % (cab["inc"], lim) if lim else "%d" % cab["inc"]
                cor = QColor(235, 235, 240)
                if lim and cab["inc"] >= 0.8 * lim:
                    cor = base.COR_VERMELHO
                elif lim and cab["inc"] >= 0.5 * lim:
                    cor = base.COR_AMARELO
                f = base.fonte(10, QFont.Bold)
                larg = QFontMetrics(f).horizontalAdvance(txt) + 8
                p.setFont(f)
                p.setPen(cor)
                p.drawText(QRectF(xd - larg, 11, larg, 20), Qt.AlignRight | Qt.AlignVCenter, txt)
                xd -= larg
                p.setFont(base.fonte(8, QFont.DemiBold))
                p.setPen(base.COR_CINZA)
                p.drawText(QRectF(xd - 34, 11, 32, 20), Qt.AlignRight | Qt.AlignVCenter, "INC")

        @staticmethod
        def _item(p, x, texto, cor, tam, larg_min=0):
            f = base.fonte(tam, QFont.Bold)
            larg = max(larg_min, QFontMetrics(f).horizontalAdvance(texto) + 8)
            p.setFont(f)
            p.setPen(cor)
            p.drawText(QRectF(x, 11, larg, 20), Qt.AlignLeft | Qt.AlignVCenter, texto)
            return x + larg + 12

        # rotulos das colunas ----------------------------------------------------------------
        def _rotulos(self, p):
            t, X = self._tx, self.X
            y = ALTURA_BARRA + 4
            p.setFont(base.fonte(7, QFont.DemiBold))
            p.setPen(base.COR_CINZA)
            h = ALTURA_ROTULOS

            def rot(chave_x, larg, texto, alinh):
                p.drawText(QRectF(X[chave_x], y, larg, h), alinh | Qt.AlignVCenter, texto)

            rot("pos", 26, t["pos"], Qt.AlignCenter)
            rot("delta", 34, "+/−", Qt.AlignCenter)
            rot("num", 44, t["carro"], Qt.AlignCenter)
            rot("lic", 118, t["lic"], Qt.AlignLeft)
            rot("piloto", 140, t["piloto"], Qt.AlignLeft)
            rot("gap", 58, t["gap"], Qt.AlignRight)
            rot("int", 56, t["int"], Qt.AlignRight)
            rot("melhor", 74, t["melhor"], Qt.AlignRight)
            rot("ultima", 74, t["ultima"], Qt.AlignRight)
            rot("pit", 30, t["pit"], Qt.AlignCenter)
            rot("stint", 40, t["stint"], Qt.AlignCenter)
            # circulo do pneu
            cx, cy = X["pneu"] + 9, y + h / 2.0
            p.setPen(QPen(base.COR_CINZA, 1.2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))
            p.setPen(QPen(QColor(255, 255, 255, 40), 1))
            p.drawLine(14, ALTURA_BARRA + ALTURA_ROTULOS + 4, LARGURA_FOTO - 14, ALTURA_BARRA + ALTURA_ROTULOS + 4)

        # faixa da classe -------------------------------------------------------------------
        def _faixa_classe(self, p, y, classe):
            h = ALTURA_LINHA_FOTO
            cor = QColor(*classe["cor"])
            f = base.fonte(9, QFont.Bold)
            larg = QFontMetrics(f).horizontalAdvance(classe["nome"]) + 20
            p.setPen(Qt.NoPen)
            p.setBrush(cor)
            p.drawRoundedRect(QRectF(12, y + 4, larg, h - 8), 5, 5)
            lum = 0.299 * cor.red() + 0.587 * cor.green() + 0.114 * cor.blue()
            p.setFont(f)
            p.setPen(QColor(20, 20, 25) if lum > 150 else QColor(255, 255, 255))
            p.drawText(QRectF(12, y + 4, larg, h - 8), Qt.AlignCenter, classe["nome"])
            x = 12 + larg + 12
            if classe.get("sof"):
                p.setFont(base.fonte(9, QFont.DemiBold))
                p.setPen(base.COR_TEXTO)
                p.drawText(QRectF(x, y, 120, h), Qt.AlignLeft | Qt.AlignVCenter,
                           "%s %s" % (self._tx["sof"], int(round(classe["sof"]))))
            p.setFont(base.fonte(8, QFont.DemiBold))
            p.setPen(base.COR_CINZA)
            p.drawText(QRectF(LARGURA_FOTO - 16 - 120, y, 120, h), Qt.AlignRight | Qt.AlignVCenter,
                       "%d" % classe["n_carros"])
            p.setPen(QPen(QColor(cor.red(), cor.green(), cor.blue(), 90), 1))
            p.drawLine(14, y + h - 1, LARGURA_FOTO - 14, y + h - 1)

        # linha -------------------------------------------------------------------------------
        def _linha_foto(self, p, y, d, salto, cor_classe):
            h, X = ALTURA_LINHA_FOTO, self.X
            if salto:
                p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.DotLine))
                p.drawLine(20, y, LARGURA_FOTO - 20, y)
            if d["eu"]:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(110, 62, 190, 220))
                p.drawRoundedRect(QRectF(6, y + 1, LARGURA_FOTO - 12, h - 2), 6, 6)
            na_box = bool(d.get("na_box"))
            texto = QColor(255, 255, 255) if not na_box else QColor(200, 200, 210)

            # posicao (quadrado)
            p.setPen(QPen(QColor(255, 255, 255, 60), 1))
            p.setBrush(QColor(0, 0, 0, 110) if not d["eu"] else QColor(255, 255, 255, 40))
            p.drawRoundedRect(QRectF(X["pos"], y + 3, 26, h - 6), 5, 5)
            p.setFont(base.fonte(10, QFont.Bold))
            p.setPen(texto)
            p.drawText(QRectF(X["pos"], y + 3, 26, h - 6), Qt.AlignCenter, str(d["pos"]))

            self._ganho(p, X["delta"], y, 34, h, d.get("delta"))

            # numero na cor da classe
            larg_num = 44
            p.setPen(Qt.NoPen)
            p.setBrush(cor_classe)
            p.drawRoundedRect(QRectF(X["num"], y + 3, larg_num, h - 6), 5, 5)
            lum = 0.299 * cor_classe.red() + 0.587 * cor_classe.green() + 0.114 * cor_classe.blue()
            p.setFont(base.fonte(10, QFont.Bold))
            p.setPen(QColor(20, 20, 25) if lum > 150 else QColor(255, 255, 255))
            p.drawText(QRectF(X["num"], y + 3, larg_num, h - 6), Qt.AlignCenter, "#" + str(d["numero"]))

            self._pneu(p, X["pneu"], y, h, d.get("pneu"))

            # licenca + iRating + variacao projetada
            lic = d.get("lic") or ""
            if lic:
                cor_lic = QColor(*d.get("lic_cor", (90, 90, 100)))
                p.setPen(Qt.NoPen)
                p.setBrush(cor_lic)
                p.drawRoundedRect(QRectF(X["lic"], y + 4, 46, h - 8), 4, 4)
                lum = 0.299 * cor_lic.red() + 0.587 * cor_lic.green() + 0.114 * cor_lic.blue()
                p.setPen(QColor(20, 20, 25) if lum > 150 else QColor(255, 255, 255))
                p.setFont(base.fonte(8, QFont.Bold))
                p.drawText(QRectF(X["lic"], y + 4, 46, h - 8), Qt.AlignCenter, fmt_licenca(lic))
            p.setFont(base.fonte(9, QFont.Bold))
            p.setPen(texto if d.get("irating") else base.COR_CINZA)
            p.drawText(QRectF(X["ir"], y, 42, h), Qt.AlignLeft | Qt.AlignVCenter, fmt_ir_k(d.get("irating")))
            ird = d.get("ir_delta")
            if ird:
                sobe = ird > 0
                p.setFont(base.fonte(8, QFont.Bold))
                p.setPen(QColor(60, 220, 110) if sobe else QColor(255, 85, 85))
                p.drawText(QRectF(X["ird"], y, 32, h), Qt.AlignLeft | Qt.AlignVCenter,
                           ("▲" if sobe else "▼") + str(abs(ird)))

            self._emblema(p, X["marca"], y, 32, h, d["marca"])
            self._bandeira(p, X["pais"], y, h, d["pais"])

            f = base.fonte(10, QFont.Bold)
            p.setFont(f)
            p.setPen(texto)
            p.drawText(QRectF(X["piloto"], y, 138, h), Qt.AlignLeft | Qt.AlignVCenter,
                       QFontMetrics(f).elidedText(d["nome"], Qt.ElideRight, 136))

            # gap / intervalo / melhor / ultima
            p.setFont(base.fonte(10, QFont.DemiBold))
            for chave, larg in (("gap", 58), ("int", 56)):
                v = d.get(chave)
                p.setPen(base.COR_CINZA if v is None else texto)
                p.drawText(QRectF(X[chave], y, larg, h), Qt.AlignRight | Qt.AlignVCenter, fmt_gap(v))
            p.setFont(base.fonte(10, QFont.Bold))
            p.setPen(base.COR_CINZA if d["melhor"] is None else
                     (QColor(190, 130, 255) if d["melhor_da_classe"] and not d["eu"] else texto))
            if d["melhor"] is not None and d["melhor_da_classe"] and d["eu"]:
                p.setPen(QColor(225, 195, 255))
            p.drawText(QRectF(X["melhor"], y, 74, h), Qt.AlignRight | Qt.AlignVCenter, base.fmt_tempo(d["melhor"]))
            if d["ultima"] is None:
                p.setPen(base.COR_CINZA)
            else:
                p.setPen(base.COR_VERDE if d["pb"] else texto)
            p.drawText(QRectF(X["ultima"], y, 74, h), Qt.AlignRight | Qt.AlignVCenter, base.fmt_tempo(d["ultima"]))

            # paradas e stint
            n = d.get("paradas")
            p.setFont(base.fonte(10, QFont.Bold))
            if na_box:
                p.setPen(QColor(255, 165, 60))
                p.drawText(QRectF(X["pit"] - 4, y, 38, h), Qt.AlignCenter, "BOX")
            else:
                p.setPen(base.COR_CINZA if n is None else texto)
                p.drawText(QRectF(X["pit"], y, 30, h), Qt.AlignCenter, "--" if n is None else str(n))
            s = d.get("stint")
            p.setPen(base.COR_CINZA if s is None or not d.get("stint_confiavel", True) else texto)
            p.drawText(QRectF(X["stint"], y, 40, h), Qt.AlignCenter, "--" if s is None else
                       (str(s) if d.get("stint_confiavel", True) else "~" + str(s)))

        @staticmethod
        def _pneu(p, x, y, h, pneu):
            cx, cy = x + 9, y + h / 2.0
            if not pneu:
                p.setPen(QPen(QColor(255, 255, 255, 50), 1))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QRectF(cx - 8, cy - 8, 16, 16))
                return
            cor = QColor(*pneu["cor"])
            p.setPen(QPen(cor, 2.2))
            p.setBrush(QColor(0, 0, 0, 120))
            p.drawEllipse(QRectF(cx - 8, cy - 8, 16, 16))
            p.setFont(base.fonte(8, QFont.Bold))
            p.setPen(cor)
            p.drawText(QRectF(cx - 8, cy - 8, 16, 16), Qt.AlignCenter, pneu["letra"])

        def _bandeira(self, p, x, y, h, codigo):
            iso2 = base._ISO2.get(codigo)
            pm = None
            if iso2:
                caminho = base.PASTA_BANDEIRAS / ("%s.png" % iso2)
                if caminho.is_file():
                    pm = base._pixmap_ajustado(caminho, round(22 * self.escala_x), round(16 * self.escala_y))
            fy = y + (h - 16) / 2.0
            if pm is None:
                p.setFont(base.fonte(7, QFont.Bold))
                p.setPen(base.COR_CINZA)
                p.drawText(QRectF(x - 2, y, 30, h), Qt.AlignCenter, str(codigo or ""))
                return
            recorte = QPainterPath()
            recorte.addRoundedRect(QRectF(x, fy, 22, 16), 3, 3)
            p.save()
            p.setClipPath(recorte)
            p.drawPixmap(QRectF(x, fy, 22, 16), pm, QRectF(pm.rect()))
            p.restore()
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 70), 1))
            p.drawRoundedRect(QRectF(x, fy, 22, 16), 3, 3)

    _cache_classe["foto"] = JanelaClassificacaoFoto
    return JanelaClassificacaoFoto
