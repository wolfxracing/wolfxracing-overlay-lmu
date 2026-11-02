# -*- coding: utf-8 -*-
"""
v1.5.0 - logica pura (sem Qt e sem depender do jogo) das quatro janelas novas:
  * Bandeiras         : bandeira da pista (verde, amarela, amarela de pista inteira, azul, branca, quadriculada...)
  * Trafego de classes: carros de OUTRA classe por perto, com a diferenca em segundos
  * Minimapa rotativo : trecho da pista ao seu redor girando com o seu carro (sempre "para cima")
  * Auxiliar de sessao: etapa da sessao, tempo/voltas restantes e a proxima sessao

Convencao de dados do overlay: sem marca = dado do jogo; "~" = estimativa. Aqui:
  - bandeiras: dado do jogo (iRacing: SessionFlags; LMU: fase do jogo, amarelas de setor e bandeira do carro);
  - trafego: posicao na pista e classe vem do jogo; os SEGUNDOS sao calculados (distancia / sua velocidade);
  - minimapa: o desenho e APRENDIDO na sua primeira volta (como o Mapa); posicao dos carros vem do jogo;
  - auxiliar: o que o jogo informa; contagens que o jogo nao garante ficam marcadas com "~".
"""
import math

# =====================================================================================================================
# 1) BANDEIRAS
# =====================================================================================================================
# bits de SessionFlags do iRacing (irsdk_Flags)
F_CHECKERED, F_WHITE, F_GREEN, F_YELLOW, F_RED, F_BLUE, F_DEBRIS = 0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40
F_YELLOW_WAVING, F_GREEN_HELD, F_CAUTION, F_CAUTION_WAVING = 0x100, 0x400, 0x4000, 0x8000
F_BLACK, F_DISQ, F_REPAIR = 0x10000, 0x20000, 0x100000

# id -> (prioridade, titulo, subtitulo, cor RGB)
BANDEIRAS = {
    "desclassificado": (100, "DESCLASSIFICADO", "Você foi desclassificado", (235, 235, 240)),
    "preta":           (95, "BANDEIRA PRETA", "Penalidade: veja os boxes", (235, 235, 240)),
    "reparo":          (90, "REPARO OBRIGATÓRIO", "Volte aos boxes para o reparo", (235, 235, 240)),
    "vermelha":        (85, "BANDEIRA VERMELHA", "Sessão interrompida", (235, 50, 50)),
    "quadriculada":    (80, "BANDEIRA QUADRICULADA", "Fim da sessão", (245, 245, 250)),
    "amarela_total":   (70, "AMARELA · PISTA INTEIRA", "Safety car · sem ultrapassagem", (255, 205, 30)),
    "amarela_setor":   (62, "AMARELA", "Perigo à frente", (255, 205, 30)),
    "amarela":         (60, "AMARELA", "Perigo à frente · sem ultrapassar", (255, 205, 30)),
    "detritos":        (55, "DETRITOS NA PISTA", "Cuidado com a pista", (255, 205, 30)),
    "azul":            (50, "BANDEIRA AZUL", "Deixe o carro mais rápido passar", (60, 140, 255)),
    "branca":          (40, "BANDEIRA BRANCA", "Última volta", (245, 245, 250)),
    "verde":           (30, "BANDEIRA VERDE", "Pista livre", (60, 210, 100)),
}
SEGUNDOS_VERDE = 6.0         # a verde so aparece nos primeiros segundos (largada/retomada)
SEGUNDOS_MINIMO = 2.0        # uma bandeira nunca pisca: fica pelo menos esse tempo na tela


def _item(id_, extra=None):
    prio, titulo, sub, cor = BANDEIRAS[id_]
    return {"id": id_, "prio": prio, "titulo": titulo, "sub": extra or sub, "cor": cor}


def candidata_iracing(flags):
    """SessionFlags (inteiro) -> (bandeira de maior prioridade ou None, verde_ligada)."""
    try:
        f = int(flags)
    except (TypeError, ValueError):
        return None, False
    ordem = ((F_DISQ, "desclassificado"), (F_BLACK, "preta"), (F_REPAIR, "reparo"), (F_RED, "vermelha"),
             (F_CHECKERED, "quadriculada"), (F_CAUTION | F_CAUTION_WAVING, "amarela_total"),
             (F_YELLOW | F_YELLOW_WAVING, "amarela"), (F_DEBRIS, "detritos"), (F_BLUE, "azul"), (F_WHITE, "branca"))
    for mascara, id_ in ordem:
        if f & mascara:
            return _item(id_), bool(f & (F_GREEN | F_GREEN_HELD))
    return None, bool(f & (F_GREEN | F_GREEN_HELD))


# fase do jogo (LMU/rFactor 2): 5 = verde, 6 = amarela de pista inteira (FCY), 7 = corrida parada, 8 = sessao acabou
def candidata_lmu(fase, fcy_estado="", amarelas_setor=(), meu_flag=0, final=0, penalidade_preta=False):
    """Estado do LMU -> (bandeira de maior prioridade ou None, verde_ligada)."""
    if final == 3:
        return _item("desclassificado"), False
    if penalidade_preta:
        return _item("preta"), False
    if fase == 7:
        return _item("vermelha", "Corrida parada"), False
    if fase == 8:
        return _item("quadriculada"), False
    if fase == 6:
        return _item("amarela_total", ("Safety car · " + fcy_estado) if fcy_estado else None), False
    if amarelas_setor:
        setores = " e ".join(str(int(s) + 1) for s in amarelas_setor)
        return _item("amarela_setor", f"Perigo no setor {setores}"), fase == 5
    if meu_flag == 6:
        return _item("azul"), fase == 5
    return None, fase == 5


class GestorBandeiras:
    """Decide o que mostrar: a de maior prioridade, a verde so por alguns segundos, sem piscar."""

    def __init__(self):
        self.resetar()

    def resetar(self):
        self.atual = None
        self._desde = 0.0
        self._verde_ant = False
        self._verde_ate = 0.0

    def atualizar(self, candidata, verde, agora, estado_corrida=None):
        if verde and not self._verde_ant:
            self._verde_ate = agora + SEGUNDOS_VERDE
        self._verde_ant = bool(verde)
        cand = candidata
        if cand is None and agora < self._verde_ate:
            cand = _item("verde")
        atual = self.atual
        if atual is not None and (agora - self._desde) < SEGUNDOS_MINIMO:
            if cand is None or (cand["id"] != atual["id"] and cand["prio"] <= atual["prio"]):
                return atual                                          # ainda dentro do tempo minimo
        if cand is None:
            self.atual = None
        elif atual is None or cand["id"] != atual["id"]:
            self.atual, self._desde = cand, agora
        else:
            self.atual = cand                                         # mesmo tipo: atualiza o texto, mantem o relogio
        return self.atual


# =====================================================================================================================
# 2) TRAFEGO DE OUTRAS CLASSES
# =====================================================================================================================
LIMITE_TRAFEGO_S = 6.0       # mostra carros de outra classe a ate esta diferenca de tempo
LIMITE_TRAFEGO_M = 450.0     # ... e a ate esta distancia na pista
VEL_MIN_REF = 15.0           # m/s: abaixo disso a referencia de tempo usa este valor (parado/lento nao gera "infinito")


def montar_trafego(carros, meu, comprimento, v_eu, memoria, agora, limite_s=LIMITE_TRAFEGO_S, max_linhas=2):
    """Carros de OUTRA classe por perto.

    carros: lista de dicts {"id","classe_id","classe_nome","cor","ordem","numero","nome","pct","vel" (m/s ou None),
            "box" (bool), "ativo" (bool, na pista)}; `meu` = id do seu carro. `memoria` (dict) guarda o historico para
    estimar a velocidade dos carros cuja velocidade o jogo nao informa (derivada da posicao).
    Retorna {"linhas": [...], "n": total_de_carros_de_outras_classes_por_perto} ou None sem dados.
    """
    if not comprimento or comprimento < 300.0:
        return None
    eu = next((c for c in carros if c["id"] == meu), None)
    if eu is None or eu.get("pct") is None or eu["pct"] < 0:
        return None
    v_ref = max(VEL_MIN_REF, float(v_eu or 0.0))
    linhas = []
    for c in carros:
        if c["id"] == meu or c.get("pct") is None or c["pct"] < 0:
            continue
        # velocidade do outro carro: a do jogo, ou derivada da posicao (filtrada)
        m = memoria.setdefault(c["id"], {})
        v = c.get("vel")
        if v is None and "pct" in m:
            dt = agora - m["t"]
            if 0.05 < dt < 1.5:
                dp = (c["pct"] - m["pct"] + 0.5) % 1.0 - 0.5
                est = dp * comprimento / dt
                if -20.0 < est < 140.0:
                    m["vel"] = est if "vel" not in m else m["vel"] + 0.3 * (est - m["vel"])
            v = m.get("vel")
        m["pct"], m["t"] = c["pct"], agora
        if c.get("classe_id") == eu.get("classe_id") or c.get("box") or c.get("ativo") is False:
            continue
        dist = ((c["pct"] - eu["pct"] + 0.5) % 1.0 - 0.5) * comprimento
        if abs(dist) > LIMITE_TRAFEGO_M:
            continue
        gap = abs(dist) / v_ref
        if gap > limite_s:
            continue
        # aproximacao (m/s): positiva = a distancia entre voces diminui
        fecha = None
        if v is not None:
            fecha = (v_ref - v) if dist > 0 else (v - v_ref)
        mais_rapida = c.get("ordem", 0.0) < eu.get("ordem", 0.0)       # ordem menor = classe mais rapida
        atras = dist < 0
        urg = 0
        if gap < 3.0 and (fecha is None or fecha > 0.5):
            urg = 1
        if atras and mais_rapida and gap < 2.0 and (fecha is None or fecha > 1.0):
            urg = 2                                                   # classe mais rapida chegando por tras
        linhas.append({"id": c["id"], "numero": c.get("numero", ""), "nome": c.get("nome", ""),
                       "classe": c.get("classe_nome", ""), "cor": tuple(c.get("cor", (150, 150, 160)))[:3],
                       "dist": dist, "gap_s": gap, "sinal": -1 if atras else 1, "fecha": fecha,
                       "mais_rapida": mais_rapida, "urg": urg})
    if len(memoria) > 120:
        vivos = {c["id"] for c in carros}
        for k in [k for k in memoria if k not in vivos]:
            memoria.pop(k, None)
    linhas.sort(key=lambda l: (-l["urg"], l["gap_s"]))
    return {"linhas": linhas[:max_linhas], "n": len(linhas)}


# =====================================================================================================================
# 3) MINIMAPA ROTATIVO
# =====================================================================================================================
def _suavizar(pontos, k=1):
    n = len(pontos)
    out = []
    for i in range(n):
        xs = [pontos[(i + d) % n] for d in range(-k, k + 1)]
        out.append((sum(p[0] for p in xs) / len(xs), sum(p[1] for p in xs) / len(xs)))
    return out


def projetar_minimapa(pontos, pct_eu, carros, raio_m=260.0, metade_px=100.0):
    """Gira o tracado para que o seu carro aponte sempre para cima.

    pontos: lista (uma posicao por trecho da volta; None onde ainda nao ha dado) em metros (x leste, y norte);
    carros: [{"pct","numero","cor","eu"}]. Devolve coordenadas de tela relativas ao CENTRO (x para a direita,
    y para baixo), em pixels: {"pista": [(x,y) ou None], "carros": [...], "norte": angulo_do_norte_em_graus,
    "rumo_ok": bool}. None se o mapa ainda nao esta completo ou nao ha sua posicao.
    """
    if not pontos or pct_eu is None or pct_eu < 0 or any(q is None for q in pontos):
        return None
    n = len(pontos)
    suave = _suavizar(pontos, 1)
    pos = (pct_eu % 1.0) * n
    i0 = int(pos) % n
    f = pos - int(pos)
    a, b = suave[i0], suave[(i0 + 1) % n]
    ex, ey = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
    # rumo: tangente do tracado ao seu redor (alguns trechos antes e depois)
    k = max(2, n // 120)
    p_ant, p_dep = suave[(i0 - k) % n], suave[(i0 + k + 1) % n]
    tx, ty = p_dep[0] - p_ant[0], p_dep[1] - p_ant[1]
    norma = math.hypot(tx, ty)
    if norma < 1e-6:
        return None
    tx, ty = tx / norma, ty / norma                      # sentido de marcha
    rx, ry = ty, -tx                                     # direita do carro (sentido horario a partir do rumo)
    esc = metade_px / float(raio_m)

    def tela(x, y):
        dx, dy = x - ex, y - ey
        return ((dx * rx + dy * ry) * esc, -(dx * tx + dy * ty) * esc)

    lim = (metade_px * 1.6) ** 2
    pista = []
    for q in suave:
        sx, sy = tela(q[0], q[1])
        pista.append((sx, sy) if sx * sx + sy * sy <= lim else None)
    cs = []
    for c in carros or []:
        pc = (c["pct"] % 1.0) * n
        j0 = int(pc) % n
        g = pc - int(pc)
        p0, p1 = suave[j0], suave[(j0 + 1) % n]
        sx, sy = tela(p0[0] + (p1[0] - p0[0]) * g, p0[1] + (p1[1] - p0[1]) * g)
        if sx * sx + sy * sy <= (metade_px * 1.05) ** 2:
            cs.append({"x": sx, "y": sy, "numero": c.get("numero", ""), "cor": tuple(c.get("cor", (150, 150, 160)))[:3],
                       "eu": bool(c.get("eu"))})
    # direcao do norte na tela (0 = para cima; positivo = horario): o norte geografico e (0, +1) no mapa
    nx, ny = tela(ex + 0.0, ey + 1.0)
    ox, oy = tela(ex, ey)
    norte = math.degrees(math.atan2(nx - ox, -(ny - oy)))
    return {"pista": pista, "carros": cs, "norte": norte, "rumo_ok": True}


class MapaPlano:
    """Aprende o tracado a partir de (posicao na volta, x, y) - usado no LMU, que informa a posicao no mundo.

    Mesma saida do Mapa do iRacing: {"pontos","completo","progresso","versao"}. O tracado fica completo quando 94%
    dos trechos tem amostra e o carro cruzou a linha de chegada; buracos pequenos sao interpolados."""

    def __init__(self, n=360):
        self.n = n
        self.resetar()

    def resetar(self, chave=None):
        self.chave = chave
        self.bins = [None] * self.n
        self.pontos = None
        self.completo = False
        self.versao = 0
        self._ant = None
        self._invalida = False

    def atualizar(self, pct, x, y, valido=True):
        if self.completo or pct is None or x is None or y is None or not (math.isfinite(x) and math.isfinite(y)):
            return
        pct = pct % 1.0
        b = min(self.n - 1, int(pct * self.n))
        ant = self._ant
        self._ant = b
        if not valido:
            self._invalida = True
        if ant is not None and ant > 0.9 * self.n and b < 0.1 * self.n:
            self._fechar()
            return
        if ant is not None and abs(b - ant) > 0.15 * self.n and not (ant > 0.85 * self.n and b < 0.15 * self.n):
            self.bins = [None] * self.n                           # saltou (reset, teletransporte): recomeca
            self._invalida = False
            return
        if valido:
            self.bins[b] = (float(x), float(y))

    def _fechar(self):
        preenchidos = sum(1 for q in self.bins if q is not None)
        if preenchidos >= 0.94 * self.n and not self._invalida:
            bins = list(self.bins)
            for i in range(self.n):
                if bins[i] is None:
                    a = next(k for k in range(1, self.n) if bins[(i - k) % self.n] is not None)
                    c = next(k for k in range(1, self.n) if bins[(i + k) % self.n] is not None)
                    pa, pc = bins[(i - a) % self.n], bins[(i + c) % self.n]
                    f = a / float(a + c)
                    bins[i] = (pa[0] + (pc[0] - pa[0]) * f, pa[1] + (pc[1] - pa[1]) * f)
            self.pontos, self.completo = bins, True
            self.versao += 1
        else:
            self.bins = [None] * self.n                           # volta incompleta/invalida: tenta de novo
            self._invalida = False

    def carregar(self, pontos):
        if pontos and len(pontos) == self.n:
            self.pontos, self.completo = [tuple(p) for p in pontos], True
            self.versao += 1

    def exibicao(self):
        preenchidos = sum(1 for q in self.bins if q is not None)
        return {"pontos": self.pontos if self.completo else self.bins, "completo": self.completo,
                "progresso": 1.0 if self.completo else min(0.99, preenchidos / float(self.n)), "versao": self.versao}


# =====================================================================================================================
# 4) AUXILIAR DE SESSAO
# =====================================================================================================================
def fmt_relogio(seg):
    """Segundos -> 'm:ss' (ou 'h:mm:ss' a partir de 1 h). None se nao for um numero valido."""
    try:
        s = int(round(float(seg)))
    except (TypeError, ValueError):
        return None
    if s < 0 or s > 24 * 3600:
        return None
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def montar_auxiliar_iracing(tipo, estado, restante_s, voltas_restantes, total_s, voltas_total, proxima):
    """Etapa da sessao do iRacing. estado = SessionState (1 no carro, 2 aquecimento, 3 volta de apresentacao,
    4 em andamento, 5 quadriculada, 6 encerrada). Devolve {"titulo","valor","sub","estimado"} ou None."""
    tipo = tipo or "SESSAO"
    try:
        estado = int(estado)
    except (TypeError, ValueError):
        return None
    prox = f"Próxima: {proxima}" if proxima else ""
    if estado in (1, 2, 3):
        etapa = {1: "Entre no carro", 2: "Aquecimento no grid", 3: "Volta de apresentação"}[estado]
        if tipo == "CORRIDA":
            duracao = (f"{voltas_total} voltas" if voltas_total and 0 < voltas_total < 1000
                       else (fmt_relogio(total_s) + " de prova") if total_s and 0 < total_s < 86400 else "")
            return {"titulo": "LARGADA", "valor": etapa.upper(), "sub": " · ".join(x for x in (duracao, prox) if x),
                    "estimado": False, "modo": "pre"}
        relogio = fmt_relogio(restante_s) if restante_s is not None and 0 < restante_s < 7200 else None
        return {"titulo": f"{tipo} EM", "valor": relogio or etapa.upper(), "sub": " · ".join(x for x in (etapa, prox) if x),
                "estimado": relogio is not None, "modo": "pre"}
    if estado == 4:
        if voltas_restantes is not None and 0 < voltas_restantes < 1000 and (restante_s is None or restante_s > 7200):
            valor, rotulo = f"{int(voltas_restantes)}", "VOLTAS RESTANTES" if voltas_restantes != 1 else "VOLTA RESTANTE"
        else:
            valor = fmt_relogio(restante_s) if restante_s is not None else None
            rotulo = "TEMPO RESTANTE"
        if valor is None:
            return None
        return {"titulo": rotulo, "valor": valor, "sub": " · ".join(x for x in (tipo, prox) if x), "estimado": False,
                "modo": "corrida"}
    if estado == 5:
        return {"titulo": tipo, "valor": "QUADRICULADA", "sub": prox, "estimado": False, "modo": "fim"}
    if estado == 6:
        return {"titulo": tipo, "valor": "ENCERRADA", "sub": prox, "estimado": False, "modo": "fim"}
    return None


NOMES_FASE_LMU = {0: "Fora da sessão", 1: "Reconhecimento da pista", 2: "Caminhada no grid", 3: "Volta de formação",
                  4: "Luzes de largada", 5: "Em andamento", 6: "Amarela de pista inteira", 7: "Corrida parada",
                  8: "Sessão encerrada", 9: "Pausado"}


def montar_auxiliar_lmu(tipo, fase, restante_s, voltas_total, total_s, luzes=None):
    """Etapa da sessao do LMU a partir de mGamePhase. luzes = (acesas, total) durante a contagem de largada."""
    tipo = tipo or "SESSÃO"
    try:
        fase = int(fase)
    except (TypeError, ValueError):
        return None
    if fase in (1, 2, 3, 4):
        duracao = (f"{voltas_total} voltas" if voltas_total and 0 < voltas_total < 1000
                   else (fmt_relogio(total_s) + " de prova") if total_s and 0 < total_s < 86400 else "")
        valor = NOMES_FASE_LMU[fase].upper()
        if fase == 4 and luzes and luzes[1]:
            valor = f"LUZES {int(luzes[0])}/{int(luzes[1])}"
        return {"titulo": "LARGADA" if tipo == "CORRIDA" else tipo, "valor": valor, "sub": duracao, "estimado": False,
                "modo": "pre"}
    if fase in (5, 6):
        if voltas_total and 0 < voltas_total < 1000 and (restante_s is None or restante_s > 7200):
            return {"titulo": "CORRIDA POR VOLTAS", "valor": f"{voltas_total} voltas", "sub": tipo, "estimado": False,
                    "modo": "corrida"}
        valor = fmt_relogio(restante_s) if restante_s is not None else None
        if valor is None:
            return None
        return {"titulo": "TEMPO RESTANTE", "valor": valor, "sub": tipo, "estimado": False, "modo": "corrida"}
    if fase == 8:
        return {"titulo": tipo, "valor": "ENCERRADA", "sub": "", "estimado": False, "modo": "fim"}
    return None
