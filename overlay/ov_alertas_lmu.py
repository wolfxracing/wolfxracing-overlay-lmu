# -*- coding: utf-8 -*-
"""
Alertas na pista do LMU - logica pura (sem Qt, sem leitura de memoria).

Origem de cada alerta:
  MEDIDO PELO JOGO : bandeira amarela geral (fase 6), corrida parada (fase 7), amarela local por setor, bandeira azul
                     (mFlag), penalidades, estado de boxes, limitador de velocidade, superaquecimento, pneu furado,
                     peca solta.
  CALCULADO AQUI   : distancia ate carros na pista (diferenca de distancia na volta), carro de classe mais rapida
                     atras, carro lento/parado a frente (velocidade relativa), tempo ate o contato (distancia / velocidade
                     de aproximacao), carros chegando na saida dos boxes, limite de velocidade dos boxes (MEDIDO: o jogo
                     nao informa o limite; o overlay anota a velocidade com o limitador ligado nos boxes).
  LIMIARES         : distancias e velocidades que disparam avisos sao DEFINICOES DO OVERLAY (config_lmu.json), nao regras
                     do jogo. Ajuste conforme o seu gosto.

Nivel: 0 informacao, 1 atencao, 2 perigo.
"""
import math
from collections import Counter

PADRAO = {
    "alerta_traseiro_m": 600.0,      # carro de classe mais rapida atras: avisa a partir desta distancia (m)
    "alerta_frente_m": 350.0,        # carro lento/parado a frente: avisa a partir desta distancia (m)
    "alerta_lento_kmh": 70.0,        # abaixo disto (e mais lento que voce) o carro a frente e considerado lento
    "alerta_saida_box_m": 900.0,     # saindo dos boxes: avisa carros que chegam por tras ate esta distancia (m)
}
NIVEL_INFO, NIVEL_ATENCAO, NIVEL_PERIGO = 0, 1, 2
MAX_ALERTAS = 6
MIN_AMOSTRAS_LIMITE = 20            # amostras com limitador ligado antes de aceitar o limite de boxes medido


def finito(v):
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _alerta(id_, nivel, titulo, detalhe=""):
    return {"id": id_, "nivel": nivel, "titulo": titulo, "detalhe": detalhe}


def distancia_atras(eu, outro, comprimento):
    """Metros que `outro` esta ATRAS de `eu` na pista (0 a comprimento). None se nao der para calcular."""
    if not comprimento or comprimento < 100.0 or not (finito(eu["dist"]) and finito(outro["dist"])):
        return None
    return (float(eu["dist"]) - float(outro["dist"])) % comprimento


def _mais_rapida(eu, outro):
    """Classe do outro e MAIS RAPIDA que a minha (so entre classes conhecidas)."""
    a, b = outro["classe"], eu["classe"]
    return a["rotulo"] != b["rotulo"] and a["ordem"] < b["ordem"] and a["ordem"] < 9 and b["ordem"] < 9


def _na_pista(c):
    return not c["box"] and int(c.get("final", 0)) == 0


def fmt_metros(m):
    return f"{m:.0f} m" if m < 1000 else f"{m / 1000.0:.1f} km"


class AlertasLMU:
    """Calcula os alertas a cada ciclo. Guarda so a medicao do limite de velocidade dos boxes."""

    def __init__(self):
        self._amostras_pit = Counter()
        self.limite_pit = None            # km/h medido, ou None

    # -- limite dos boxes (medido) --------------------------------------------------------------------------
    def _medir_limite(self, limitador):
        if not limitador or not limitador.get("ativo") or not limitador.get("nos_boxes"):
            return
        v = limitador.get("vel")
        if finito(v) and 20.0 <= v <= 120.0:
            self._amostras_pit[int(round(v))] += 1
            total = sum(self._amostras_pit.values())
            if total >= MIN_AMOSTRAS_LIMITE:
                valor, qtd = self._amostras_pit.most_common(1)[0]
                if qtd >= 0.4 * total:                # a velocidade mais comum com o limitador ligado = o limite
                    self.limite_pit = float(valor)

    # -- alertas -----------------------------------------------------------------------------------------------
    def calcular(self, ctx, cfg=None):
        """`ctx`: {'bandeiras', 'carros', 'comprimento', 'limitador', 'danos', 'energia'} (qualquer um pode faltar).
        Devolve a lista de alertas (maior nivel primeiro, no maximo MAX_ALERTAS)."""
        c = dict(PADRAO)
        if cfg:
            for k in PADRAO:
                if finito(cfg.get(k)):
                    c[k] = float(cfg[k])
        alertas = []
        self._medir_limite(ctx.get("limitador"))
        self._bandeiras(ctx.get("bandeiras"), alertas)
        eu = next((x for x in ctx.get("carros") or [] if x["eu"]), None)
        if eu is not None:
            self._penalidades(eu, alertas)
            self._boxes(eu, ctx, alertas, c)
            self._trafego(eu, ctx, alertas, c)
        self._carro(ctx.get("danos"), alertas, eu)
        self._energia(ctx.get("energia"), alertas)
        alertas.sort(key=lambda a: -a["nivel"])           # estavel: dentro do mesmo nivel mantem a ordem de insercao
        return alertas[:MAX_ALERTAS]

    @staticmethod
    def _bandeiras(b, alertas):
        if not b:
            return
        if b.get("parada"):
            alertas.append(_alerta("parada", NIVEL_PERIGO, "CORRIDA PARADA", "bandeira vermelha / sessao interrompida"))
        if b.get("fcy"):
            alertas.append(_alerta("fcy", NIVEL_PERIGO, "AMARELA GERAL (FCY)", b.get("fcy_estado") or ""))
        if b.get("amarelas_setor"):
            alertas.append(_alerta("amarela_local", NIVEL_ATENCAO, "AMARELA NA PISTA",
                                   "ha bandeira amarela local; reduza e nao ultrapasse"))

    @staticmethod
    def _penalidades(eu, alertas):
        n = int(eu.get("penalidades", 0))
        if n > 0:
            alertas.append(_alerta("penalidade", NIVEL_PERIGO, "PENALIDADE" if n == 1 else f"PENALIDADES ({n})",
                                   "cumpra nos boxes conforme as regras da sessao"))

    def _boxes(self, eu, ctx, alertas, c):
        lim = ctx.get("limitador") or {}
        if eu["box"] and lim.get("ativo") and finito(lim.get("vel")):
            vel = float(lim["vel"])
            if self.limite_pit:
                if vel > self.limite_pit + 1.5:
                    alertas.append(_alerta("limite_pit", NIVEL_PERIGO, "ACIMA DO LIMITE DOS BOXES",
                                           f"{vel:.0f} km/h (limite medido {self.limite_pit:.0f} km/h)"))
                else:
                    alertas.append(_alerta("limite_pit", NIVEL_INFO, "LIMITADOR DOS BOXES",
                                           f"{vel:.0f} km/h (limite medido {self.limite_pit:.0f} km/h)"))
            else:
                alertas.append(_alerta("limite_pit", NIVEL_INFO, "LIMITADOR DOS BOXES",
                                       f"{vel:.0f} km/h (medindo o limite desta pista)"))
        # pedido de parada: distancia ate os boxes (o jogo informa a posicao dos boxes na volta)
        if int(eu.get("pit_estado", 0)) == 1 and finito(eu.get("pit_dist")) and finito(eu.get("dist")):
            comp = ctx.get("comprimento") or 0.0
            if comp > 100.0:
                falta = (float(eu["pit_dist"]) - float(eu["dist"])) % comp
                alertas.append(_alerta("box_distancia", NIVEL_INFO, "PARADA SOLICITADA", f"boxes em {fmt_metros(falta)}"))
        # saindo dos boxes: carros chegando por tras
        if int(eu.get("pit_estado", 0)) == 4:
            comp = ctx.get("comprimento")
            vistos = []
            for o in ctx.get("carros") or []:
                if o["eu"] or not _na_pista(o):
                    continue
                d = distancia_atras(eu, o, comp)
                if d is not None and 0.0 < d <= c["alerta_saida_box_m"]:
                    vistos.append((d, o))
            if vistos:
                d, o = min(vistos, key=lambda t: t[0])
                alertas.append(_alerta("saida_box", NIVEL_ATENCAO, "SAINDO DOS BOXES",
                                       f"#{o['numero']} {o['classe']['rotulo']} chegando a {fmt_metros(d)}"))
            else:
                alertas.append(_alerta("saida_box", NIVEL_INFO, "SAINDO DOS BOXES", "pista livre atras"))

    def _trafego(self, eu, ctx, alertas, c):
        if not _na_pista(eu):
            return
        comp = ctx.get("comprimento")
        v_eu = float(eu["vel"]) if finito(eu.get("vel")) else None        # m/s
        # azul: o jogo mostra a bandeira azul para o seu carro
        atras = []
        for o in ctx.get("carros") or []:
            if o["eu"] or not _na_pista(o):
                continue
            d = distancia_atras(eu, o, comp)
            if d is not None and 0.0 < d <= c["alerta_traseiro_m"] and _mais_rapida(eu, o):
                atras.append((d, o))
        if int(eu.get("bandeira", 0)) == 6:
            detalhe = "deixe passar o carro mais rapido"
            if atras:
                d, o = min(atras, key=lambda t: t[0])
                detalhe = f"#{o['numero']} {o['classe']['rotulo']} a {fmt_metros(d)}"
            alertas.append(_alerta("azul", NIVEL_ATENCAO, "BANDEIRA AZUL", detalhe))
        elif atras:
            d, o = min(atras, key=lambda t: t[0])
            detalhe = f"#{o['numero']} {o['classe']['rotulo']} a {fmt_metros(d)}"
            nivel = NIVEL_ATENCAO
            if v_eu is not None and finito(o.get("vel")):
                aproxima = float(o["vel"]) - v_eu                           # m/s
                if aproxima > 1.0:
                    t = d / aproxima
                    detalhe += f" (alcanca em ~{t:.0f} s)"
                    if t < 8.0:
                        nivel = NIVEL_PERIGO
            alertas.append(_alerta("classe_rapida", nivel, "CLASSE MAIS RAPIDA ATRAS", detalhe))
        # carro lento ou parado a frente (qualquer classe)
        if v_eu is not None:
            frente = []
            for o in ctx.get("carros") or []:
                if o["eu"] or not _na_pista(o) or not finito(o.get("vel")):
                    continue
                d = distancia_atras(o, eu, comp)                            # metros que o outro esta A FRENTE
                if d is None or not 0.0 < d <= c["alerta_frente_m"]:
                    continue
                v_o = float(o["vel"])
                if v_o * 3.6 < c["alerta_lento_kmh"] and v_eu > v_o + 1.0:
                    frente.append((d, o, v_eu - v_o))
            if frente:
                d, o, aproxima = min(frente, key=lambda t: t[0])
                t = d / aproxima
                parado = float(o["vel"]) * 3.6 < 10.0
                alertas.append(_alerta("lento_frente", NIVEL_PERIGO if t < 5.0 else NIVEL_ATENCAO,
                                       "CARRO PARADO A FRENTE" if parado else "CARRO LENTO A FRENTE",
                                       f"#{o['numero']} a {fmt_metros(d)}, {float(o['vel']) * 3.6:.0f} km/h (contato em ~{t:.0f} s)"))

    @staticmethod
    def _carro(danos, alertas, eu=None):
        if not danos:
            return
        # v1.5.2: motor parado na pista (ignicao ligada, sem rotacao): mesma condicao da luz de ignicao do painel do jogo
        if danos.get("motor_parado") and eu is not None and _na_pista(eu):
            alertas.append(_alerta("motor_parado", NIVEL_PERIGO, "MOTOR PARADO", "ignicao ligada sem rotacao: religue ou volte aos boxes"))
        if danos.get("superaquecendo"):
            alertas.append(_alerta("superaquecendo", NIVEL_PERIGO, "MOTOR SUPERAQUECENDO", "alivie o ritmo"))
        if any(danos.get("furados") or []):
            alertas.append(_alerta("furado", NIVEL_PERIGO, "PNEU FURADO", "va para os boxes"))
        if any(danos.get("rodas_soltas") or []):
            alertas.append(_alerta("roda_solta", NIVEL_PERIGO, "RODA SOLTA", "va para os boxes"))
        elif danos.get("solta"):
            alertas.append(_alerta("peca_solta", NIVEL_ATENCAO, "PECA SOLTA NO CARRO", "verifique o dano"))

    @staticmethod
    def _energia(painel, alertas):
        if not painel or not finito(painel.get("alcance")):
            return
        alcance = float(painel["alcance"])
        nome = "ENERGIA" if painel.get("limitante") == "energia" else "COMBUSTIVEL"
        if alcance < 2.0:
            alertas.append(_alerta("reserva", NIVEL_PERIGO, f"{nome} NA RESERVA", f"alcance ~{alcance:.1f} volta(s)"))
        elif alcance < 3.0:
            alertas.append(_alerta("reserva", NIVEL_ATENCAO, f"{nome} BAIXO", f"alcance ~{alcance:.1f} volta(s)"))
