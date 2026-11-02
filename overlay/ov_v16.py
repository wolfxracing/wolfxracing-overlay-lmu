# -*- coding: utf-8 -*-
"""v1.6.0 - logica pura (sem Qt): Ultimo contato e Entrada do pit.

ULTIMO CONTATO: quando o jogo registra uma batida (contador de incidentes / pico de aceleracao no iRacing; impacto no LMU)
e ha um carro encostado (a ate 7 m), esse carro vira o "ultimo contato". Mostra quem era, os pontos de incidente (0x/1x/2x/4x
quando o jogo informa), a volta, ha quanto tempo foi e onde ele esta AGORA em segundos (+ a frente, - atras).

ENTRADA DO PIT: a pista nao informa onde fica a entrada dos boxes; o overlay aprende a posicao na primeira vez que voce entra
(guarda por pista) e depois conta a distancia, calcula se ainda da para frear ate o limite (estimativa) e mostra o limite.
"""
import math

DIST_CONTATO_M = 7.0           # carro "encostado": ate 7 m entre os centros (comprimento de um carro ~4,5-5 m)
VEL_MIN_REF = 15.0             # m/s: referencia minima para converter metros em segundos


def _delta_pct(a, b):
    """b - a em fracao de volta, no intervalo [-0.5, 0.5)."""
    return (b - a + 0.5) % 1.0 - 0.5


# =====================================================================================================================
# ULTIMO CONTATO
# =====================================================================================================================
def escolher_alvo(candidatos, limite=DIST_CONTATO_M):
    """candidatos: [(id, distancia_m_com_sinal_ou_modulo, info_dict)] -> o mais proximo dentro do limite, ou None."""
    melhor = None
    for id_, dist, info in candidatos:
        d = abs(dist)
        if d <= limite and (melhor is None or d < melhor[0]):
            melhor = (d, id_, info)
    return (melhor[1], melhor[2]) if melhor else None


class UltimoContato:
    SEGUNDOS_PONTOS = 3.0          # tempo para o contador de incidentes completar o registro da batida

    def __init__(self):
        self.resetar()

    def resetar(self):
        self.atual = None

    def registrar(self, agora, alvo_id, info, volta, pontos=None):
        """Novo contato com o carro `alvo_id` (info: numero, nome, classe, cor)."""
        self.atual = {"t": agora, "id": alvo_id, "numero": info.get("numero", ""), "nome": info.get("nome", "?"),
                      "classe": info.get("classe", ""), "cor": tuple(info.get("cor", (150, 150, 160)))[:3],
                      "volta": volta, "pontos": pontos}

    def completar_pontos(self, agora, pontos):
        """O contador de incidentes sobe um instante depois do impacto: completa o registro."""
        if self.atual and pontos is not None and agora - self.atual["t"] <= self.SEGUNDOS_PONTOS:
            self.atual["pontos"] = int(pontos)

    def exibicao(self, agora, dist_atual_m=None, box=False, v_ref=0.0):
        """Dict para a janela, ou None sem contato. dist_atual_m: onde o outro carro esta agora (+ a frente, - atras)."""
        c = self.atual
        if not c:
            return None
        gap = sinal = None
        if dist_atual_m is not None and math.isfinite(dist_atual_m):
            gap = abs(dist_atual_m) / max(VEL_MIN_REF, float(v_ref or 0.0))
            sinal = 1 if dist_atual_m >= 0 else -1
        return {"numero": c["numero"], "nome": c["nome"], "classe": c["classe"], "cor": c["cor"],
                "pontos": c["pontos"], "volta": c["volta"], "ha_s": max(0.0, agora - c["t"]),
                "gap_s": gap, "sinal": sinal, "box": bool(box)}


def fmt_ha(seg):
    """'1:05 ATRAS' / '12 s ATRAS' / '2 min ATRAS' - compacto."""
    seg = int(max(0, seg))
    if seg < 60:
        return f"{seg} s"
    return f"{seg // 60}:{seg % 60:02d}"


# =====================================================================================================================
# ENTRADA DO PIT
# =====================================================================================================================
class PitEntrada:
    """Aprende a entrada dos boxes por pista e orienta a aproximacao e a velocidade na pit lane."""
    DECEL = 12.0                    # m/s2 (~1,2 g) usado para a distancia de frenagem: ESTIMATIVA
    ALCANCE_M = 700.0               # comeca a mostrar a ate esta distancia da entrada

    def __init__(self, entradas=None):
        self.entradas = dict(entradas or {})      # chave da pista -> fracao da volta da entrada
        self._ant_pit = None
        self._ant_pct = None
        self.mudou = False                         # o chamador salva o arquivo quando for True

    def entrada(self, chave):
        v = self.entradas.get(chave)
        return float(v) if v is not None else None

    def _aprender(self, chave, pct_antes):
        # entrada = ponto onde "na pit lane" ligou; usa o pct do quadro anterior se existir (mais perto da linha)
        if chave is None or pct_antes is None:
            return
        antigo = self.entradas.get(chave)
        if antigo is None or abs(_delta_pct(antigo, pct_antes)) > 0.002:
            self.entradas[chave] = round(pct_antes % 1.0, 5)
            self.mudou = True

    def atualizar(self, chave, na_pit_lane, pct, comprimento, v_ms, limite_kmh, pct_box=None, quer_parar=False,
                  sempre=False):
        """Retorna dict {"fase","dist","luz","vel","limite","freio_m","dist_box"} ou None (nada a mostrar)."""
        ant_pit, ant_pct = self._ant_pit, self._ant_pct
        self._ant_pit, self._ant_pct = bool(na_pit_lane), pct
        if pct is None or not comprimento or comprimento < 300.0:
            return None
        kmh = (v_ms or 0.0) * 3.6
        lim = float(limite_kmh) if limite_kmh and 10.0 < limite_kmh < 200.0 else None
        if na_pit_lane:
            if ant_pit is False:
                self._aprender(chave, ant_pct)
            luz, excesso = "verde", None
            if lim is not None:
                excesso = kmh - lim
                luz = "vermelho" if excesso > 1.0 else ("amarelo" if excesso > -3.0 else "verde")
            dist_box = None
            if pct_box is not None and pct_box >= 0:
                d = _delta_pct(pct, pct_box) * comprimento
                if -5.0 <= d <= 900.0:
                    dist_box = max(0.0, d)
            return {"fase": "pista", "dist": None, "luz": luz, "vel": kmh, "limite": lim, "excesso": excesso,
                    "freio_m": None, "dist_box": dist_box}
        e = self.entrada(chave)
        if e is None or not (quer_parar or sempre):
            return None
        d = _delta_pct(pct, e) * comprimento
        if not (0.0 < d <= self.ALCANCE_M):
            return None
        freio = None
        luz = "verde"
        if lim is not None:
            v, vl = v_ms or 0.0, lim / 3.6
            freio = max(0.0, (v * v - vl * vl) / (2.0 * self.DECEL))
            if freio > 0:
                luz = "vermelho" if d <= freio * 1.15 else ("amarelo" if d <= freio * 2.0 + 40.0 else "verde")
        return {"fase": "entrada", "dist": d, "luz": luz, "vel": kmh, "limite": lim, "excesso": None,
                "freio_m": freio, "dist_box": None}


# =====================================================================================================================
# TENDENCIA DE RITMO (iRacing)
# =====================================================================================================================
VOLTA_LENTA = 1.30             # volta limpa: sem boxes, sem bandeira de perigo e ate 130% da melhor volta
MIN_VOLTAS_TENDENCIA = 4       # voltas limpas do stint atual para calcular a inclinacao
MAX_VOLTAS_TENDENCIA = 40
ESTAVEL_S_VOLTA = 0.03         # |inclinacao| abaixo disto = ritmo estavel (definicao do overlay, s/volta)
BANDEIRAS_SUJAS = ("amarela", "amarela_setor", "amarela_total", "vermelha")


class TendenciaRitmo:
    """Ritmo das ultimas voltas limpas e para onde ele esta indo (regressao linear, s/volta, no stint atual).

    Stint = trecho entre duas passagens pelos boxes. A inclinacao e a previsao sao ESTIMATIVAS (~) calculadas sobre voltas
    reais; os tempos de volta vem do jogo.
    """

    def __init__(self):
        self.resetar(None)

    def resetar(self, chave):
        self._chave = chave
        self.voltas = []                  # (numero da volta, tempo, numero do stint)
        self.stint = 1
        self._ant = None
        self._sujo = False
        self._box_ant = False

    def atualizar(self, chave, voltas_completas, ultima_volta, melhor, na_box, bandeira=None):
        if chave != self._chave:
            self.resetar(chave)
        if voltas_completas is None or voltas_completas < 0:
            return
        if bandeira in BANDEIRAS_SUJAS:
            self._sujo = True
        if na_box:
            self._sujo = True
        if self._box_ant and not na_box:                       # saiu dos boxes: novo stint
            self.stint += 1
        self._box_ant = bool(na_box)
        if self._ant is None or voltas_completas < self._ant:   # primeira leitura / sessao reiniciada
            if self._ant is not None:
                self.resetar(chave)
                self._box_ant = bool(na_box)
            self._ant = voltas_completas
            self._sujo = bool(na_box)
            return
        if voltas_completas == self._ant + 1:
            ok = bool(ultima_volta) and ultima_volta > 0 and not self._sujo
            if ok and melhor and melhor > 0 and ultima_volta > melhor * VOLTA_LENTA:
                ok = False
            if ok:
                self.voltas.append((voltas_completas, float(ultima_volta), self.stint))
                del self.voltas[:-MAX_VOLTAS_TENDENCIA]
            self._sujo = bool(na_box)          # amarela que continua marca a volta nova nos ciclos seguintes
        elif voltas_completas != self._ant:                     # salto: nao da para confiar nessa volta
            self._sujo = True
        self._ant = voltas_completas

    def resumo(self, melhor=None):
        """None sem voltas limpas; senao dict com ritmo (media das 5 ultimas), inclinacao (~), previsao (~) e consistencia."""
        if not self.voltas:
            return None
        melhor = melhor if melhor and melhor > 0 else None
        ultimas = [t for _, t, _ in self.voltas[-5:]]
        ritmo5 = sum(ultimas) / len(ultimas)
        atuais = [(v, t) for v, t, s in self.voltas if s == self.stint]
        inc = prev = None
        if len(atuais) >= MIN_VOLTAS_TENDENCIA:
            xs, ys = [a[0] for a in atuais], [a[1] for a in atuais]
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            den = sum((x - mx) ** 2 for x in xs)
            if den > 0:
                inc = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
                prev = my + inc * (xs[-1] + 1 - mx)
                prev = min(max(prev, min(ys) - 1.5), max(ys) + 1.5)       # nao deixa a reta "voar"
        cons = None
        if len(self.voltas) >= 3:
            ult = [t for _, t, _ in self.voltas[-8:]]
            m = sum(ult) / len(ult)
            cons = math.sqrt(sum((t - m) ** 2 for t in ult) / len(ult))
        return {"voltas": list(self.voltas), "stint_atual": self.stint, "melhor": melhor, "ritmo5": ritmo5,
                "delta_ritmo": (ritmo5 - melhor) if melhor else None, "inclinacao": inc, "previsao": prev,
                "consistencia": cons, "ultima": self.voltas[-1][1]}


def estado_tendencia(inc):
    """(rotulo, cor) da inclinacao em s/volta: negativo = melhorando."""
    if inc is None:
        return ("calculando", "cinza")
    if abs(inc) < ESTAVEL_S_VOLTA:
        return ("estável", "verde")
    if inc < 0:
        return ("melhorando", "verde")
    return ("piorando", "amarelo" if inc < 0.15 else "vermelho")
