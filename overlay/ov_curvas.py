# -*- coding: utf-8 -*-
"""
Velocidade minima por curva (v1.4.0) - logica pura, sem Qt e sem depender do jogo.

Como funciona
  1. A cada amostra (posicao na volta 0..1, velocidade em km/h, volante em graus) o analisador guarda a MENOR
     velocidade vista em cada um de 1000 trechos da volta, e o volante nesse ponto.
  2. Quando a primeira volta valida termina, as curvas sao achadas no perfil de velocidade: cada queda de velocidade
     seguida de recuperacao e uma curva (C1, C2... a partir da linha de chegada). As tres primeiras voltas validas
     refinam esse mapa (vale o da volta mais rapida); depois ele congela.
  3. Para cada curva: MIN = menor velocidade da volta; BEST = melhor MIN ja visto naquela curva (melhor passagem);
     DELTA = MIN - BEST das voltas anteriores (positivo = mais rapido que a sua melhor passagem).
  4. Volta valida = sem boxes, sem sair da pista, sem parar, cobertura quase completa e sem ser muito mais lenta que
     a melhor. Voltas invalidas nao entram no BEST.

Tudo vem do carro (velocidade, volante, posicao): nada e estimado; o mapa de curvas e inferido do perfil de velocidade.
"""
import math

BINS = 1000
VOLTAS_PARA_CONGELAR = 3


def _finito(v):
    return v is not None and isinstance(v, (int, float)) and math.isfinite(v)


def preencher(perfil, max_faltando=0.08):
    """Completa os trechos sem amostra por interpolacao linear. Devolve None se faltar mais que max_faltando."""
    faltam = sum(1 for v in perfil if v is None)
    if faltam > max_faltando * len(perfil) or faltam == len(perfil):
        return None
    out = list(perfil)
    n = len(out)
    i = 0
    while i < n:
        if out[i] is None:
            j = i
            while j < n and out[j] is None:
                j += 1
            esq = out[i - 1] if i > 0 else None
            dir_ = out[j] if j < n else None
            for k in range(i, j):
                if esq is None:
                    out[k] = dir_
                elif dir_ is None:
                    out[k] = esq
                else:
                    f = (k - i + 1) / (j - i + 1)
                    out[k] = esq + (dir_ - esq) * f
            i = j
        else:
            i += 1
    return out


def _suavizar(v, janela):
    n = len(v)
    r = max(0, janela // 2)
    acum = [0.0]
    for x in v:
        acum.append(acum[-1] + x)
    out = []
    for i in range(n):
        a, b = max(0, i - r), min(n, i + r + 1)
        out.append((acum[b] - acum[a]) / (b - a))
    return out


def detectar_curvas(perfil, comprimento=4000.0, queda_min=None):
    """Acha as curvas no perfil de velocidade (lista de BINS valores km/h, ja preenchida).
    Devolve [{"centro": bin, "ini": bin, "fim": bin}], em ordem de volta."""
    n = len(perfil)
    comp = comprimento if _finito(comprimento) and comprimento > 300.0 else 4000.0
    m2b = n / comp                                        # metros -> trechos
    suave = _suavizar(perfil, max(3, int(round(40.0 * m2b)) | 1))
    vmax = max(suave)
    queda = queda_min if queda_min is not None else max(12.0, 0.06 * vmax)
    meia = max(4, int(round(120.0 * m2b)))                # um minimo local vale dentro de +-120 m
    busca = max(meia * 2, int(round(500.0 * m2b)))        # a queda e medida ate 500 m de cada lado
    candidatos = []
    for i in range(n):
        a, b = max(0, i - meia), min(n, i + meia + 1)
        menor = min(suave[a:b])
        if suave[i] != menor or suave.index(menor, a, b) != i:
            continue
        esq = max(suave[max(0, i - busca):i + 1])
        dir_ = max(suave[i:min(n, i + busca + 1)])
        # nas pontas da volta so exige a queda do lado que existe (a curva pode cruzar a linha de chegada)
        if i - busca < 0:
            esq = dir_
        if i + busca >= n:
            dir_ = esq
        if min(esq, dir_) - suave[i] >= queda:
            candidatos.append(i)
    juntar = max(3, int(round(70.0 * m2b)))
    curvas = []
    for i in candidatos:
        if curvas and i - curvas[-1] < juntar:
            if suave[i] < suave[curvas[-1]]:
                curvas[-1] = i
        else:
            curvas.append(i)
    saida = []
    largura = max(4, int(round(200.0 * m2b)))
    for k, c in enumerate(curvas):
        ant = curvas[k - 1] if k > 0 else None
        prox = curvas[k + 1] if k + 1 < len(curvas) else None
        ini = c - largura if ant is None else max(c - largura, (ant + c) // 2)
        fim = c + largura if prox is None else min(c + largura, (c + prox) // 2)
        saida.append({"centro": c, "ini": max(0, ini), "fim": min(n - 1, fim)})
    return saida


class AnalisadorCurvas:
    def __init__(self, bins=BINS):
        self.bins = bins
        self.resetar()

    # ---- estado -------------------------------------------------------------------------------------------------
    def resetar(self):
        self.curvas = []                  # [{"centro","ini","fim"}]
        self.melhor = []                  # melhor MIN por curva (None = ainda sem passagem)
        self.voltas_validas = 0
        self.congelado = False
        self._ref_media = None            # media de velocidade da volta usada para achar as curvas
        self._melhor_media = None
        self.comprimento = 4000.0
        self.ultima = None                # ultima curva concluida (dict)
        self.volta_anterior = None        # resumo da ultima volta valida
        self._zerar_volta()
        self._ultimo_bin = None

    def _zerar_volta(self):
        self._vmin = [None] * self.bins
        self._ang = [0.0] * self.bins
        self._invalida = False
        self._prox = 0
        self._vivas = []

    # ---- entrada ------------------------------------------------------------------------------------------------
    def atualizar(self, pct, vel_kmh, volante=0.0, valido=True, comprimento=None):
        """Uma amostra. Devolve o dicionario para a janela (ou None sem posicao)."""
        if _finito(comprimento) and comprimento > 300.0:
            self.comprimento = float(comprimento)
        if not _finito(pct) or not _finito(vel_kmh):
            return self.resumo()
        pct = pct - math.floor(pct)
        b = min(self.bins - 1, max(0, int(pct * self.bins)))
        ant = self._ultimo_bin
        if ant is not None:
            if ant > 0.8 * self.bins and b < 0.2 * self.bins:
                self._fechar_volta()                                  # cruzou a linha de chegada
            elif b < ant - 0.1 * self.bins:
                self._zerar_volta()                                   # voltou no tempo (reset, replay): descarta a volta
            elif b > ant + 0.1 * self.bins:
                self._invalida = True                                 # salto para frente (teleporte, saida dos boxes)
        self._ultimo_bin = b
        if not valido:
            self._invalida = True
        if vel_kmh < 10.0 and b > 5:
            self._invalida = True                                     # parou na pista
        atual = self._vmin[b]
        if atual is None or vel_kmh < atual:
            self._vmin[b] = float(vel_kmh)
            self._ang[b] = float(volante) if _finito(volante) else 0.0
        self._avancar(b)
        return self.resumo()

    # ---- voltas e curvas ----------------------------------------------------------------------------------------
    def _minimo_na_curva(self, vmin, ang, c):
        melhor_i, melhor_v = None, None
        for i in range(c["ini"], c["fim"] + 1):
            v = vmin[i]
            if v is not None and (melhor_v is None or v < melhor_v):
                melhor_i, melhor_v = i, v
        if melhor_i is None:
            return None, 0.0
        return melhor_v, ang[melhor_i]

    def _avancar(self, b):
        """Fecha, durante a volta, as curvas que o carro acabou de passar."""
        while self._prox < len(self.curvas) and b > self.curvas[self._prox]["fim"]:
            k = self._prox
            self._prox += 1
            v, a = self._minimo_na_curva(self._vmin, self._ang, self.curvas[k])
            if v is None:
                continue
            res = self._montar(k, v, a)
            self._vivas.append(res)
            self.ultima = res

    def _montar(self, k, v, a):
        melhor = self.melhor[k] if k < len(self.melhor) else None
        return {"n": k + 1, "min": v, "best": melhor, "delta": None if melhor is None else v - melhor, "volante": a}

    def _fechar_volta(self):
        vmin, ang = self._vmin, self._ang
        perfil = preencher(vmin)
        valida = (not self._invalida) and perfil is not None
        media = (sum(perfil) / len(perfil)) if perfil else None
        if valida and self._melhor_media is not None and media < 0.85 * self._melhor_media:
            valida = False                                            # volta muito lenta (rodada, bandeira): nao conta
        if valida:
            self.voltas_validas += 1
            self._melhor_media = media if self._melhor_media is None else max(self._melhor_media, media)
            self._registrar(perfil, vmin, ang, media)
        self._zerar_volta()

    def _registrar(self, perfil, vmin, ang, media):
        if not self.congelado and (not self.curvas or (self._ref_media is not None and media > self._ref_media)):
            novas = detectar_curvas(perfil, self.comprimento)
            if novas:
                self._adotar(novas)
                self._ref_media = media
        if self.voltas_validas >= VOLTAS_PARA_CONGELAR and self.curvas:
            self.congelado = True
        if not self.curvas:
            return
        res = []
        for k, c in enumerate(self.curvas):
            v, a = self._minimo_na_curva(perfil, ang, c)
            if v is None:
                continue
            res.append(self._montar(k, v, a))
        for r in res:                                                 # so agora entram no BEST (compara-se com o anterior)
            k = r["n"] - 1
            if self.melhor[k] is None or r["min"] > self.melhor[k]:
                self.melhor[k] = r["min"]
        comparaveis = [r["delta"] for r in res if r["delta"] is not None]
        if comparaveis:
            pior = min((r for r in res if r["delta"] is not None), key=lambda r: r["delta"])
            self.volta_anterior = {"perda": -sum(d for d in comparaveis if d < 0), "ganho": sum(d for d in comparaveis if d > 0),
                                   "pior_n": pior["n"] if pior["delta"] < 0 else None,
                                   "pior_delta": pior["delta"] if pior["delta"] < 0 else None}
        else:
            self.volta_anterior = None

    def _adotar(self, novas):
        """Troca o mapa de curvas aproveitando o BEST das curvas que continuam no mesmo lugar."""
        antigas, melhor_antigo = self.curvas, self.melhor
        tol = max(4, int(round(60.0 * self.bins / self.comprimento)))
        novo_melhor = []
        for c in novas:
            herdado = None
            for j, a in enumerate(antigas):
                if abs(a["centro"] - c["centro"]) <= tol and j < len(melhor_antigo):
                    herdado = melhor_antigo[j]
                    break
            novo_melhor.append(herdado)
        self.curvas, self.melhor = novas, novo_melhor
        self.ultima = None

    # ---- saida --------------------------------------------------------------------------------------------------
    def resumo(self, linhas=8):
        if not self.curvas:
            return {"estado": "aprendendo", "voltas_validas": self.voltas_validas, "n": 0, "ultima": None,
                    "lista": [], "volta_anterior": None}
        return {"estado": "ok", "voltas_validas": self.voltas_validas, "n": len(self.curvas), "ultima": self.ultima,
                "lista": list(self._vivas[-linhas:]), "volta_anterior": self.volta_anterior}
