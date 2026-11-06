# -*- coding: utf-8 -*-
"""Onda 1 da 1.7.0 (build o): logica pura (sem Qt, sem jogo) de Consumo por trecho (Burn Zones + Fuel Flow) e Delta Trace.
Identico nas arvores iRacing e LMU. Tudo recebe o tempo/posicao de fora (testavel); nada e gravado em disco.

CONSUMO (Fuel Flow + Burn Zones)
  - A volta e dividida em N_ZONAS trechos iguais (por LapDistPct). A cada passo, o combustivel gasto desde o passo anterior
    e distribuido pelos trechos percorridos. So conta volta COMPLETA e LIMPA (comecou ao cruzar a linha, sem box, sem saida de
    pista, sem reabastecimento, sem salto de posicao).
  - Zona = mediana por trecho das ultimas voltas validas (minimo MIN_VOLTAS_ZONAS). 'ratio' 1.0 = consumo medio do trecho.
    As "oportunidades" sao os trechos que gastam bem mais que a media; NAO e uma estimativa de economia em litros.
  - Fuel Flow: consumo instantaneo (L/h) derivado do NIVEL de combustivel em litros numa janela curta (o mesmo calculo nos
    dois jogos; nao usa a variavel de vazao do jogo, que tem unidade diferente entre carros/jogos).

DELTA TRACE
  - Guarda, por volta, o tempo de volta em N_PONTOS posicoes. A referencia e a melhor volta limpa completa da sessao.
    delta(x) = tempo_agora(x) - tempo_ref(x); negativo = mais rapido que a referencia (mesmo sinal do delta do jogo).
"""
from collections import deque
import math

N_ZONAS = 24
MIN_VOLTAS_ZONAS = 3
MAX_VOLTAS = 8
JANELA_FLUXO_S = 6.0
MIN_JANELA_FLUXO_S = 2.0
SALTO_REABASTECER_L = 0.05        # aumento de nivel (entre duas leituras) acima disso = reabastecimento; abaixo = ruido do sensor (build p)
K_SUAVIZA = 4                     # leituras medias nas pontas da janela do fluxo (reduz o efeito do ruido)
LIMIAR_ALTA = 1.25                # trecho com consumo >= 125% da media
LIMIAR_BAIXA = 0.75
N_PONTOS = 200


def _fin(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


class Consumo:
    def __init__(self, n=N_ZONAS):
        self.n = n
        self.resetar()

    def resetar(self):
        self._voltas = deque(maxlen=MAX_VOLTAS)     # litros por trecho de cada volta valida
        self._atual = [0.0] * self.n
        self._cob = [False] * self.n
        self._ult = None                            # (pct, nivel)
        self._lap_ok = False
        self._hist = deque()                        # (t, nivel) para o consumo instantaneo
        self.descartadas = 0

    # ------------------------------------------------------------------ entrada
    def _invalidar(self):
        if self._lap_ok:
            self.descartadas += 1
        self._lap_ok = False

    def _distribuir(self, p0, p1, litros):
        """Reparte `litros` gastos entre p0 e p1 (0..1, p1 >= p0) proporcionalmente ao trecho percorrido."""
        if p1 <= p0:
            return
        total = p1 - p0
        i0 = min(self.n - 1, int(p0 * self.n))
        i1 = min(self.n - 1, int(min(p1, 0.999999) * self.n))
        for i in range(i0, i1 + 1):
            a, b = max(p0, i / self.n), min(p1, (i + 1) / self.n)
            if b > a:
                self._atual[i] += litros * (b - a) / total
                self._cob[i] = True

    def _fechar_volta(self):
        cob = sum(1 for c in self._cob if c) / float(self.n)
        total = sum(self._atual)
        if self._lap_ok and cob >= 0.95 and total > 0.01:
            self._voltas.append(list(self._atual))
        elif self._lap_ok:
            self.descartadas += 1
        self._atual = [0.0] * self.n
        self._cob = [False] * self.n

    def atualizar(self, agora, pct, nivel, valido):
        """agora: segundos (monotonico); pct: 0..1; nivel: litros; valido: no carro, na pista, fora do box."""
        if not (_fin(pct) and _fin(nivel)) or pct < 0.0 or pct > 1.0:
            return
        # ---- fluxo instantaneo
        if self._hist and nivel > self._hist[-1][1] + SALTO_REABASTECER_L:
            self._hist.clear()                                  # reabasteceu: a janela recomeca
        if valido:
            self._hist.append((agora, nivel))
            while self._hist and agora - self._hist[0][0] > JANELA_FLUXO_S:
                self._hist.popleft()
        else:
            self._hist.clear()
        # ---- trechos
        if not valido:
            self._invalidar()
            self._ult = None
            return
        if self._ult is None:
            self._ult = (pct, nivel)
            return
        p0, n0 = self._ult
        self._ult = (pct, nivel)
        if nivel > n0 + SALTO_REABASTECER_L:
            self._invalidar()
            return
        gasto = n0 - nivel                                      # COM sinal: ruido pequeno se cancela (max(0,.) criava vies para cima)
        if p0 > 0.9 and pct < 0.1:                              # cruzou a linha
            frente = (1.0 - p0) + pct
            if frente > 0.2:
                self._invalidar()
                self._atual = [0.0] * self.n
                self._cob = [False] * self.n
                return
            self._distribuir(p0, 1.0, gasto * (1.0 - p0) / frente)
            self._fechar_volta()
            self._lap_ok = True                                 # a proxima volta comeca aqui, inteira
            self._distribuir(0.0, pct, gasto * pct / frente)
        elif pct < p0 - 0.02 or pct - p0 > 0.2:                 # voltou atras / saltou (reset, reboque, replay)
            self._invalidar()
            self._atual = [0.0] * self.n
            self._cob = [False] * self.n
        else:
            if pct > p0:
                self._distribuir(p0, pct, gasto)

    # ------------------------------------------------------------------ saida
    def _inst_lh(self):
        if len(self._hist) < 2:
            return None
        k = max(1, min(K_SUAVIZA, len(self._hist) // 4))
        ini, fim = list(self._hist)[:k], list(self._hist)[-k:]
        t0, n0 = sum(x[0] for x in ini) / k, sum(x[1] for x in ini) / k
        t1, n1 = sum(x[0] for x in fim) / k, sum(x[1] for x in fim) / k
        if self._hist[-1][0] - self._hist[0][0] < MIN_JANELA_FLUXO_S or t1 - t0 <= 0 or n1 > n0 + 1e-9:
            return None
        return (n0 - n1) / (t1 - t0) * 3600.0

    def resumo(self):
        voltas = list(self._voltas)
        n = len(voltas)
        res = {"estado": "sem_dados", "voltas": n, "minimo": MIN_VOLTAS_ZONAS, "inst_lh": self._inst_lh(), "medio_lv": None,
               "ultima_lv": None, "tendencia": None, "zonas": None, "atual": None, "oportunidades": [], "n_zonas": self.n}
        atual = [self._atual[i] if self._cob[i] else None for i in range(self.n)]
        res["atual"] = atual if any(a is not None for a in atual) else None
        if n == 0:
            return res
        totais = [sum(v) for v in voltas]
        res["ultima_lv"] = totais[-1]
        res["medio_lv"] = sum(totais) / n
        if n >= 4:
            rec, ant = totais[-2:], totais[-5:-2] if n >= 5 else totais[:-2]
            m_rec, m_ant = sum(rec) / len(rec), sum(ant) / len(ant)
            if m_ant > 0:
                var = (m_rec - m_ant) / m_ant
                res["tendencia"] = "subindo" if var > 0.03 else ("caindo" if var < -0.03 else "estavel")
        res["estado"] = "medindo"
        if n < MIN_VOLTAS_ZONAS:
            return res
        med = []
        for i in range(self.n):
            col = sorted(max(0.0, v[i]) for v in voltas)
            m = len(col) // 2
            med.append(col[m] if len(col) % 2 else (col[m - 1] + col[m]) / 2.0)
        soma = sum(med)
        if soma <= 0:
            return res
        ratio = [m * self.n / soma for m in med]
        res["estado"] = "ok"
        res["zonas"] = [{"ratio": r, "nivel": "alta" if r >= LIMIAR_ALTA else ("baixa" if r <= LIMIAR_BAIXA else "normal"),
                         "litros": m} for r, m in zip(ratio, med)]
        # oportunidades: grupos contiguos de trechos 'alta', ordenados pela parcela do consumo da volta
        grupos, i = [], 0
        while i < self.n:
            if ratio[i] >= LIMIAR_ALTA:
                j = i
                while j + 1 < self.n and ratio[j + 1] >= LIMIAR_ALTA:
                    j += 1
                grupos.append({"ini": i / self.n, "fim": (j + 1) / self.n, "parcela": sum(med[i:j + 1]) / soma,
                               "ratio": sum(ratio[i:j + 1]) / (j - i + 1)})
                i = j + 1
            else:
                i += 1
        grupos.sort(key=lambda g: g["parcela"], reverse=True)
        res["oportunidades"] = grupos[:3]
        return res


class DeltaTrace:
    """Guarda os TEMPOS BRUTOS de cada volta (build p). Todo delta e calculado na hora contra a referencia vigente, entao
    quando uma volta melhor vira a referencia o grafico da volta anterior e recalculado contra ela (e nao contra a antiga)."""
    MAX_LACUNA = 10                       # pontos pulados entre duas leituras que ainda sao preenchidos por interpolacao (5% da volta)

    def __init__(self, n=N_PONTOS):
        self.n = n
        self.resetar()

    def resetar(self):
        self._ref = None                  # tempos brutos (len n+1; indice 0 = 0 s) da melhor volta valida
        self._ref_total = None
        self._atual = [None] * (self.n + 1)
        self._ant = None                  # tempos brutos da volta que acabou de fechar (o 'fantasma'); o delta e calculado no resumo
        self._seg_melhor = None           # build s: melhor tempo de cada um dos n trechos entre as voltas validas da sessao (volta ideal)
        self._ok = False
        self._ult_pct = None
        self._ult_i = None
        self._ult_tv = None
        self.voltas_validas = 0

    def _novo(self):
        self._atual = [None] * (self.n + 1)
        self._ult_i = None
        self._ult_tv = None

    def _delta_de(self, tempos):
        if self._ref is None or tempos is None:
            return None
        return [None if (t is None or r is None) else t - r for t, r in zip(tempos, self._ref)]

    def _acumular_trechos(self, tempos):
        """Guarda, por trecho, o menor tempo ja feito (so trechos com as duas pontas medidas e duracao positiva)."""
        if self._seg_melhor is None:
            self._seg_melhor = [None] * self.n
        for k in range(self.n):
            a, b = tempos[k], tempos[k + 1]
            if a is None or b is None or b <= a:
                continue
            d = b - a
            if self._seg_melhor[k] is None or d < self._seg_melhor[k]:
                self._seg_melhor[k] = d

    def _ideal(self):
        """Tempos acumulados da volta ideal (soma dos melhores trechos; trecho sem medida usa o da referencia) e o delta dela contra a
        referencia vigente. So existe com pelo menos 2 voltas validas; o delta nunca passa de 0 (a referencia e uma das voltas)."""
        if self._ref is None or self._seg_melhor is None or self.voltas_validas < 2:
            return None, None
        acum, tot = [0.0], 0.0
        for k in range(self.n):
            ref_k = self._ref[k + 1] - self._ref[k] if (self._ref[k] is not None and self._ref[k + 1] is not None) else None
            d = self._seg_melhor[k] if self._seg_melhor[k] is not None else ref_k
            if d is None:
                return None, None
            if ref_k is not None and d > ref_k:
                d = ref_k
            tot += d
            acum.append(tot)
        delta = [0.0 if r is None else min(0.0, a - r) for a, r in zip(acum, self._ref)]
        return delta, acum[-1]

    def atualizar(self, pct, tempo_volta, valido, ultima_volta=None):
        """pct 0..1; tempo_volta: segundos da volta em andamento; ultima_volta: tempo da volta que acabou de fechar (se o jogo o der)."""
        if not (_fin(pct) and _fin(tempo_volta)) or pct < 0.0 or pct > 1.0 or tempo_volta < 0:
            return
        if not valido:
            self._ok = False
            self._ult_pct = None
            return
        p0 = self._ult_pct
        self._ult_pct = pct
        if p0 is None:
            return
        if p0 > 0.9 and pct < 0.1:                              # cruzou a linha: fecha a volta
            if self._ok and sum(1 for t in self._atual if t is not None) >= 0.95 * (self.n + 1):
                total = ultima_volta if _fin(ultima_volta) and ultima_volta > 0 else None
                if total is None:
                    total = max((t for t in self._atual if t is not None), default=None)
                if total:
                    atual = list(self._atual)
                    atual[self.n] = total
                    self._ant = atual                           # primeiro guarda os tempos brutos...
                    self.voltas_validas += 1
                    self._acumular_trechos(atual)
                    if self._ref_total is None or total < self._ref_total:
                        self._ref, self._ref_total = atual, total   # ...depois troca a referencia: o delta e sempre recalculado
            self._novo()
            self._ok = True
            self._atual[0] = 0.0
            self._ult_i, self._ult_tv = 0, 0.0
        elif pct < p0 - 0.02 or pct - p0 > 0.2:                # voltou atras / saltou
            self._ok = False
            self._novo()
            return
        if not self._ok:
            return
        if self._ult_tv is not None and tempo_volta < self._ult_tv - 0.5:     # relogio da volta voltou atras
            if pct > 0.95:                                      # o jogo zerou o relogio um pouco ANTES da posicao dar a volta: ignora a leitura
                return
            if pct < 0.05:                                      # ...ou a posicao deu a volta antes do relogio: descarta os pontos com tempo velho
                for k in range(1, self.n + 1):
                    if self._atual[k] is not None and self._atual[k] > tempo_volta + 0.5:
                        self._atual[k] = None
                self._atual[0] = 0.0
                self._ult_i, self._ult_tv = 0, tempo_volta
            else:                                               # no meio da volta: reinicio/reset -> volta descartada
                self._ok = False
                self._novo()
                return
        i = int(pct * self.n)
        i0 = self._ult_i
        if i0 is None or i <= i0:
            if i == 0:
                self._atual[0] = 0.0
            return
        if 1 < i - i0 <= self.MAX_LACUNA and self._ult_tv is not None:     # leitura pulou pontos: interpola o tempo entre as duas leituras
            for k in range(i0 + 1, i):
                self._atual[k] = self._ult_tv + (tempo_volta - self._ult_tv) * (k - i0) / float(i - i0)
        if self._atual[i] is None:
            self._atual[i] = tempo_volta
        self._ult_i, self._ult_tv = i, tempo_volta

    def resumo(self):
        pontos = self._delta_de(self._atual)
        ideal, ideal_total = self._ideal()
        res = {"estado": "sem_ref" if self._ref is None else "ok", "n": self.n, "pontos": pontos, "anterior": self._delta_de(self._ant),
               "ref_total": self._ref_total, "ref_tempos": None if self._ref is None else list(self._ref), "atual": None, "voltas": self.voltas_validas,
               "melhor": None, "pior": None, "ideal": ideal, "ideal_total": ideal_total}
        if pontos:
            validos = [d for d in pontos if d is not None]
            if validos:
                res["atual"] = validos[-1]
                res["melhor"], res["pior"] = min(validos), max(validos)
        return res


# ---------------------------------------------------------------------------- blocos por curva do Delta Trace (build q)
def zonas_de_curvas(curvas, bins):
    """Converte as curvas do analisador (indices de trecho 0..bins-1) em zonas de posicao da volta 0..1: [{n, ini, fim}].
    Build r: uma zona CIRCULAR (comeca antes da linha de chegada e termina depois dela: ini > fim) e mantida como UMA zona so
    (ini > fim); as demais funcoes sabem lidar com ela. Zona vazia, fora de 0..1 ou de volta inteira e descartada."""
    out = []
    try:
        for k, c in enumerate(curvas or []):
            ini, fim = float(c["ini"]) / bins, float(c["fim"] + 1) / bins
            if not (0.0 <= ini < 1.0 and 0.0 < fim <= 1.0):
                continue
            if ini < fim or (ini > fim and ini - fim >= 1.0 / bins):          # normal, ou circular (sobre a linha de chegada)
                out.append({"n": k + 1, "ini": ini, "fim": fim})
    except (KeyError, TypeError, ValueError):
        return []
    return out


def zona_circular(z):
    """True se a zona atravessa a linha de chegada (comeca antes e termina depois dela)."""
    return z["ini"] > z["fim"]


def pct_na_zona(z, pct):
    """A posicao `pct` (0..1) esta dentro da zona? (considera a zona circular)."""
    if zona_circular(z):
        return pct >= z["ini"] or pct <= z["fim"]
    return z["ini"] <= pct <= z["fim"]


def delta_por_curva(pontos, zonas):
    """Tempo ganho (negativo) ou perdido (positivo) DENTRO de cada curva = delta(fim da curva) - delta(inicio da curva), nos pontos
    da volta atual. None = a curva ainda nao foi percorrida (ou faltam pontos). Mesmo sinal do jogo: negativo = mais rapido.
    Zona circular (build r): soma do trecho ate a linha de chegada com o trecho depois dela (o delta recomeca do zero na virada)."""
    if not pontos or not zonas:
        return []
    n = len(pontos) - 1
    out = []
    for z in zonas:
        i0, i1 = int(z["ini"] * n), min(n, int(round(z["fim"] * n)))
        if zona_circular(z):
            p0 = pontos[0] if _fin(pontos[0]) else 0.0
            d0, dn, d1 = (pontos[i0] if 0 <= i0 <= n else None), pontos[n], (pontos[i1] if 0 <= i1 <= n else None)
            ok = _fin(d0) and _fin(dn) and _fin(d1)
            delta = ((dn - d0) + (d1 - p0)) if ok else None
        else:
            d0, d1 = pontos[i0] if 0 <= i0 <= n else None, pontos[i1] if 0 <= i1 <= n else None
            delta = (d1 - d0) if (_fin(d0) and _fin(d1)) else None
        out.append({"n": z["n"], "ini": z["ini"], "fim": z["fim"], "delta": delta})
    return out


def eixo_tempo(ref_tempos, n):
    """Posicao horizontal (fracao 0..1 do tempo da volta de referencia) de cada um dos n+1 pontos do Delta Trace. O grafico e os blocos
    por curva usam este eixo: quanto mais tempo se passa num trecho, mais largo ele fica (curvas lentas ocupam mais espaco).
    Pontos sem tempo sao interpolados; sem referencia valida devolve o eixo linear (por distancia)."""
    linear = [i / float(n) for i in range(n + 1)]
    if not ref_tempos or len(ref_tempos) != n + 1:
        return linear
    t = list(ref_tempos)
    total = t[-1] if _fin(t[-1]) and t[-1] > 0 else None
    if total is None or not _fin(t[0]):
        return linear
    i = 0
    while i <= n:                                  # interpola buracos
        if not _fin(t[i]):
            j = i
            while j <= n and not _fin(t[j]):
                j += 1
            if j > n:
                return linear
            a, b = t[i - 1], t[j]
            for k in range(i, j):
                t[k] = a + (b - a) * (k - i + 1) / float(j - i + 1)
            i = j
        i += 1
    xs, ult = [], 0.0
    for v in t:
        ult = max(ult, min(1.0, max(0.0, v / total)))        # monotono e dentro de 0..1
        xs.append(ult)
    return xs


def curva_em_foco(zonas, pct):
    """Curva a destacar no painel: a que o carro esta fazendo ("agora") ou a proxima ("proxima", volta ao C1 depois da ultima)."""
    if not zonas or not _fin(pct):
        return None, None
    for z in zonas:
        if pct_na_zona(z, pct):
            return z, "agora"
    for z in sorted(zonas, key=lambda q: q["ini"]):
        if z["ini"] > pct:
            return z, "proxima"
    return min(zonas, key=lambda q: q["ini"]), "proxima"


def delta_na_curva(pontos, zona, pct):
    """Tempo ganho/perdido na curva `zona` ate agora (parcial se a curva esta em andamento); None se ainda nao chegou nela.
    Zona circular: depois da linha de chegada o comeco da curva ficou na volta anterior, entao o parcial e None (nada inventado)."""
    if not pontos or not zona or not _fin(pct):
        return None
    n = len(pontos) - 1
    i0 = int(zona["ini"] * n)
    if zona_circular(zona):
        if pct < zona["ini"]:
            return None
        i1 = int(pct * n)
        if i1 <= i0 or not (0 <= i0 <= n):
            return None
        d0, d1 = pontos[i0], pontos[i1]
        return (d1 - d0) if (_fin(d0) and _fin(d1)) else None
    i1 = min(int(round(zona["fim"] * n)), int(pct * n))
    if i1 <= i0 or not (0 <= i0 <= n):
        return None
    d0, d1 = pontos[i0], pontos[i1]
    return (d1 - d0) if (_fin(d0) and _fin(d1)) else None


def ritmo_por_trecho(pontos, pct, nseg=120, janela=2, limiar=0.004):
    """Ritmo local da volta atual para colorir o desenho da pista.

    Devolve `nseg` valores, um por trecho da pista: -1 = ganhando tempo (verde), +1 = perdendo (vermelho),
    0 = equivalente a referencia, None = trecho ainda nao percorrido nesta volta.
    O ritmo e a variacao do delta ao longo do trecho (em segundos); abaixo de `limiar` e neutro.
    """
    saida = [None] * nseg
    if not pontos or len(pontos) < 3 or not _fin(pct):
        return saida
    n = len(pontos) - 1
    for s in range(nseg):
        i0 = int(s * n / float(nseg))
        i1 = min(n, int((s + 1) * n / float(nseg)))
        if i1 > int(max(0.0, min(1.0, pct)) * n):
            break
        a = max(0, i0 - janela)
        b = min(n, i1 + janela)
        da, db = pontos[a], pontos[b]
        if not (_fin(da) and _fin(db)):
            continue
        v = db - da
        saida[s] = -1 if v < -limiar else (1 if v > limiar else 0)
    return saida


def layout_blocos(desejados, x0, x1, largura_min=30.0, folga=2.0):
    """Posiciona os blocos por curva dentro de [x0, x1], sem sobreposicao (build r).
    `desejados`: lista (na ordem de desenho, da esquerda para a direita) de (inicio_x, fim_x) ideais, em pixels (largura = tempo na curva).
    Devolve [(x, largura)] na mesma ordem. Regras: nenhum bloco sai da regiao; separados por `folga`; a largura minima se adapta quando
    ha muitas curvas; as larguras ficam proporcionais ao tempo sempre que couber e, se nao couber, o EXCESSO acima do minimo e
    reduzido na mesma proporcao para todos (preserva a ordem de grandeza)."""
    n = len(desejados)
    if n == 0:
        return []
    disp = max(0.0, (x1 - x0) - folga * (n - 1))
    minimo = min(largura_min, disp / n)
    larg = [max(minimo, max(0.0, b - a)) for a, b in desejados]
    soma = sum(larg)
    if soma > disp and soma - n * minimo > 1e-9:
        k = (disp - n * minimo) / (soma - n * minimo)
        larg = [minimo + (w - minimo) * k for w in larg]
    pos = []
    for (a, b), w in zip(desejados, larg):                        # posicao ideal: centrada no trecho, dentro dos limites
        pos.append(max(x0, min(x1 - w, (a + b) / 2.0 - w / 2.0)))
    ant = x0 - folga
    for i in range(n):                                            # passada para a frente: sem sobreposicao
        pos[i] = max(pos[i], ant + folga)
        ant = pos[i] + larg[i]
    lim = x1 + folga
    for i in range(n - 1, -1, -1):                                # passada para tras: nada passa do limite direito
        pos[i] = min(pos[i], lim - folga - larg[i])
        lim = pos[i]
    return [(pos[i], larg[i]) for i in range(n)]
