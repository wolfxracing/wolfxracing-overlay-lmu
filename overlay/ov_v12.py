# -*- coding: utf-8 -*-
"""WolfxRacing Overlay - versao 1.2.0: logica pura dos 5 novos overlays.

Sem Qt e sem SDK (testavel por simulacao):
  - PiscaLuz / DetectorPatinagem  -> Luz ABS e Luz TC
  - CalculadorRetorno             -> Retorno a pista (PARE / CEDA / LIVRE)
  - RitmoPorPneu / EstrategiaPneus-> Estrategia de pneus (chuva x seco)
  - HistoricoInputs               -> grafico de pedais (Inputs)

Convencao de dados do projeto: sem marca = leitura do SDK; "~" = estimativa calculada pelo overlay.
A Luz TC e a vantagem em segundos por volta dos pneus SAO ESTIMATIVAS (o iRacing nao informa).
"""
import math
from collections import deque

VERSAO_V12 = "1.2.0"

# ---------------------------------------------------------------------------------------------
# Luzes (ABS e TC)
# ---------------------------------------------------------------------------------------------
HOLD_PISCA = {"ritmo": 0.066, "suave": 0.10, "fixa": 0.25}     # s acesa depois de cada pulso


class PiscaLuz:
    """Transforma o sinal (verdadeiro/falso, ~30 amostras/s) em luz: cada pulso mantem a luz acesa por
    um tempo que depende do modo (ritmo do sinal, piscada suave ou luz fixa)."""

    def __init__(self, modo="ritmo"):
        self.modo = modo if modo in HOLD_PISCA else "ritmo"
        self._ate = -1e9

    def definir_modo(self, modo):
        self.modo = modo if modo in HOLD_PISCA else "ritmo"

    def atualizar(self, ativo, agora):
        if ativo:
            self._ate = agora + HOLD_PISCA[self.modo]
        return agora < self._ate

    def forcar(self, agora, duracao):
        """Teste: mantem a luz acesa por `duracao` s."""
        self._ate = max(self._ate, agora + duracao)


SENSIBILIDADE_TC = {"fina": 0.035, "normal": 0.05, "grossa": 0.075}   # fracao de patinagem para acender


class DetectorPatinagem:
    """Estima patinagem das rodas motrizes SEM dado do jogo (o iRacing nao avisa quando o TC corta).

    Com a embreagem solta, rpm / velocidade do carro e constante em cada marcha (relacao do cambio).
    Se as rodas patinam, o motor sobe sem o carro andar mais: a relacao aumenta. O overlay aprende a
    relacao de cada marcha enquanto o piloto esta sem acelerar e sem frear; depois compara.
    E uma DEDUCAO: pode deixar passar patinada pequena ou avisar a mais no limite (use a sensibilidade).
    """
    MIN_AMOSTRAS = 15            # amostras (~0,5 s) antes de confiar na relacao de uma marcha
    VEL_MIN = 5.0                # m/s (~18 km/h)
    ATRASO_TROCA = 0.4           # s ignorados depois de cada troca de marcha
    ACEL_MIN = 0.15              # abaixo disso ele nao julga patinagem
    DESVIO_MAX = 0.12            # amostra de aprendizado 12% fora da relacao conhecida = descartada
    REJEICOES_RESET = 30         # descartes seguidos = relacao final mudou: reaprende a marcha

    def __init__(self, sensibilidade="normal"):
        self.sensibilidade = sensibilidade if sensibilidade in SENSIBILIDADE_TC else "normal"
        self.resetar()

    def resetar(self):
        self.ref = {}            # marcha -> [relacao, amostras]
        self._rejeitadas = {}
        self._marcha_ant = None
        self._t_troca = -1e9

    def definir_sensibilidade(self, s):
        self.sensibilidade = s if s in SENSIBILIDADE_TC else "normal"

    @property
    def limiar(self):
        return SENSIBILIDADE_TC[self.sensibilidade]

    def _aprender(self, marcha, relacao):
        atual = self.ref.get(marcha)
        if atual is None:
            self.ref[marcha] = [relacao, 1]
            return
        valor, n = atual
        if n >= self.MIN_AMOSTRAS and abs(relacao / valor - 1.0) > self.DESVIO_MAX:
            self._rejeitadas[marcha] = self._rejeitadas.get(marcha, 0) + 1
            if self._rejeitadas[marcha] >= self.REJEICOES_RESET:
                self.ref[marcha] = [relacao, 1]
                self._rejeitadas[marcha] = 0
            return
        self._rejeitadas[marcha] = 0
        passo = 0.2 if n < self.MIN_AMOSTRAS else 0.08
        atual[0] = valor + (relacao - valor) * passo
        atual[1] = n + 1

    def atualizar(self, agora, marcha, rpm, vel_ms, acelerador, freio, embreagem, rpm_max=None, limitador=False):
        """Devolve {"ativa", "patinagem" (fracao ~ ou None), "estado"}.
        estado: 'ok' (julgando), 'aprendendo' (marcha ainda sem relacao), 'ignorado' (momento em que nao olha)."""
        if marcha != self._marcha_ant:
            self._marcha_ant = marcha
            self._t_troca = agora
        if (marcha is None or marcha <= 0 or rpm <= 0 or vel_ms < self.VEL_MIN or embreagem > 0.1
                or freio > 0.15 or agora - self._t_troca < self.ATRASO_TROCA or limitador
                or (rpm_max and rpm >= 0.985 * rpm_max)):
            return {"ativa": False, "patinagem": None, "estado": "ignorado"}
        relacao = rpm / vel_ms
        if acelerador < 0.05 and freio < 0.05 and embreagem < 0.05:
            self._aprender(marcha, relacao)             # sem forca nas rodas: relacao pura do cambio
            return {"ativa": False, "patinagem": 0.0, "estado": "ok" if self._conhecida(marcha) else "aprendendo"}
        if acelerador < self.ACEL_MIN:
            return {"ativa": False, "patinagem": None, "estado": "ignorado"}
        if not self._conhecida(marcha):
            return {"ativa": False, "patinagem": None, "estado": "aprendendo"}
        patinagem = max(0.0, relacao / self.ref[marcha][0] - 1.0)
        return {"ativa": patinagem > self.limiar, "patinagem": patinagem, "estado": "ok"}

    def _conhecida(self, marcha):
        r = self.ref.get(marcha)
        return bool(r) and r[1] >= self.MIN_AMOSTRAS


# ---------------------------------------------------------------------------------------------
# Retorno a pista
# ---------------------------------------------------------------------------------------------
COR_VERMELHO, COR_LARANJA, COR_AMARELO, COR_VERDE = (235, 50, 50), (245, 140, 40), (240, 205, 50), (70, 205, 100)


def _mistura(a, b, f):
    f = max(0.0, min(1.0, f))
    return tuple(int(round(a[i] + (b[i] - a[i]) * f)) for i in range(3))


def cor_retorno(segundos, lim_pare=1.5, lim_ceda=3.5):
    """Cor continua: vermelho (em cima) -> laranja -> amarelo -> verde exatamente em `lim_ceda`."""
    if segundos is None or segundos >= lim_ceda:
        return COR_VERDE
    f = max(0.0, segundos) / max(0.1, lim_ceda)
    if f < 0.33:
        return _mistura(COR_VERMELHO, COR_LARANJA, f / 0.33)
    if f < 0.66:
        return _mistura(COR_LARANJA, COR_AMARELO, (f - 0.33) / 0.33)
    return _mistura(COR_AMARELO, COR_VERDE, (f - 0.66) / 0.34)


def estado_retorno(segundos, lim_pare=1.5, lim_ceda=3.5):
    if segundos is None:
        return "livre"
    if segundos < lim_pare:
        return "pare"
    if segundos < lim_ceda:
        return "ceda"
    return "livre"


def normalizar_limites(lim_pare, lim_ceda):
    """Vermelho 1..15 s, laranja 1.5..25 s, em passos de 0.5; o laranja fica sempre >= vermelho + 0.5."""
    lim_pare = max(1.0, min(15.0, round(float(lim_pare) * 2) / 2))
    lim_ceda = max(1.5, min(25.0, round(float(lim_ceda) * 2) / 2))
    if lim_ceda < lim_pare + 0.5:
        lim_ceda = min(25.0, lim_pare + 0.5)
    return lim_pare, lim_ceda


class CalculadorRetorno:
    """Quantos segundos faltam para o carro mais proximo que vem ATRAS chegar onde voce esta.

    Velocidade de cada carro = avanco medido ao vivo na pista (nao a media da volta); se ainda nao deu
    para medir, usa o tempo de volta estimado. Considera qualquer carro na pista atras de voce (tambem
    retardatario); ignora pit lane e carros fora da pista. Mais de `alcance` s = livre, sem numero.
    """
    VEL_PARADO = 2.0          # m/s: abaixo disso voce esta "quase parado"
    PERSISTE = 1.5            # s que o aviso fica depois que voce volta a andar
    VEL_MIN_OUTRO = 2.0       # carro quase parado atras de voce nao "chega"

    def __init__(self, lim_pare=1.5, lim_ceda=3.5, alcance=30.0):
        self.lim_pare, self.lim_ceda = normalizar_limites(lim_pare, lim_ceda)
        self.alcance = alcance
        self._ult = {}        # idx -> (t, pct)
        self._vel = {}        # idx -> m/s suavizado
        self._ate = -1e9

    def definir_limites(self, lim_pare, lim_ceda):
        self.lim_pare, self.lim_ceda = normalizar_limites(lim_pare, lim_ceda)

    def resetar(self):
        self._ult.clear()
        self._vel.clear()
        self._ate = -1e9

    def _medir(self, idx, pct, agora, comprimento):
        antes = self._ult.get(idx)
        self._ult[idx] = (agora, pct)
        if antes is None:
            return
        dt = agora - antes[0]
        if dt < 0.02 or dt > 1.0:
            if dt > 1.0:
                self._vel.pop(idx, None)
            return
        dp = (pct - antes[1]) % 1.0
        if dp > 0.5:                      # andou para tras (ou voltou ao box): nao conta
            dp = 0.0
        v = dp * comprimento / dt
        anterior = self._vel.get(idx)
        self._vel[idx] = v if anterior is None else anterior + (v - anterior) * 0.25

    def atualizar(self, agora, meu, pcts, superficies, no_pit, comprimento, vel_propria_ms, ref_volta=None, validos=None):
        """Devolve {"visivel", "estado", "segundos" (None = ninguem em `alcance` s), "idx", "cor"}."""
        vazio = {"visivel": False, "estado": "livre", "segundos": None, "idx": None, "cor": COR_VERDE}
        if not pcts or meu is None or meu < 0 or meu >= len(pcts) or not comprimento:
            return vazio
        sup_meu = superficies[meu] if superficies is not None and meu < len(superficies) else None
        pit_meu = bool(no_pit[meu]) if no_pit is not None and meu < len(no_pit) else False
        precisa = (sup_meu == 0) or (sup_meu == 3 and vel_propria_ms < self.VEL_PARADO and not pit_meu)
        if pit_meu or sup_meu in (1, 2):
            precisa = False
            self._ate = -1e9
        if precisa:
            self._ate = agora + self.PERSISTE
        visivel = agora < self._ate
        meu_pct = pcts[meu]
        melhor = None
        for idx, pct in enumerate(pcts):
            if pct is None or pct < 0:
                continue
            self._medir(idx, pct, agora, comprimento)
            if idx == meu or meu_pct is None or meu_pct < 0 or (validos is not None and idx not in validos):
                continue
            sup = superficies[idx] if superficies is not None and idx < len(superficies) else None
            if sup != 3 or (no_pit is not None and idx < len(no_pit) and no_pit[idx]):
                continue
            dist = ((meu_pct - pct) % 1.0) * comprimento          # metros ATRAS de voce
            v = self._vel.get(idx)
            if v is None and ref_volta:
                v = comprimento / ref_volta
            if v is None or v < self.VEL_MIN_OUTRO:
                continue
            t = dist / v
            if melhor is None or t < melhor[0]:
                melhor = (t, idx)
        segundos = melhor[0] if melhor and melhor[0] <= self.alcance else None
        return {"visivel": visivel, "estado": estado_retorno(segundos, self.lim_pare, self.lim_ceda),
                "segundos": segundos, "idx": melhor[1] if segundos is not None else None,
                "cor": cor_retorno(segundos, self.lim_pare, self.lim_ceda)}


# ---------------------------------------------------------------------------------------------
# Estrategia de pneus
# ---------------------------------------------------------------------------------------------
NIVEIS_PISTA = ("Seca", "Quase seca", "Umida", "Pouco molhada", "Molhada", "Muito molhada", "Encharcada")


def nome_nivel(nivel):
    if nivel is None or not 1 <= int(nivel) <= 7:
        return None
    return NIVEIS_PISTA[int(nivel) - 1]


def classe_pneu(nome_estilo):
    """Rotulo de estilo_pneu() ('Chuva', 'Intermediario', 'Macio'...) -> 'chuva' ou 'seco' (None = desconhecido)."""
    if not nome_estilo:
        return None
    return "chuva" if str(nome_estilo).lower() in ("chuva", "intermediario") else "seco"


def _mediana(valores):
    v = sorted(valores)
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2.0


class RitmoPorPneu:
    """Guarda as ultimas voltas (limpas) dos carros da SUA classe por tipo de pneu e estima quantos
    segundos por volta o outro pneu rende. E uma estimativa (depende de quem ja trocou)."""
    MAX_VOLTAS = 3
    JANELA_S = 600.0

    def __init__(self):
        self._voltas = {}     # idx -> deque[(t, tipo, tempo)]
        self._ult_comp = {}   # idx -> ultima volta completada vista
        self._sujo = set()    # carros que passaram pelo pit na volta atual

    def resetar(self):
        self._voltas.clear()
        self._ult_comp.clear()
        self._sujo.clear()

    def atualizar(self, agora, idx, completadas, tempo_ultima, tipo, no_pit):
        if no_pit:
            self._sujo.add(idx)
        antes = self._ult_comp.get(idx)
        self._ult_comp[idx] = completadas
        if antes is None or completadas is None or completadas <= antes:
            return
        limpa = idx not in self._sujo
        self._sujo.discard(idx)
        if limpa and tipo and tempo_ultima and tempo_ultima > 0:
            self._voltas.setdefault(idx, deque(maxlen=self.MAX_VOLTAS)).append((agora, tipo, float(tempo_ultima)))

    def vantagem(self, agora, meu_tipo, idxs):
        """Segundos por volta que o OUTRO pneu rende (positivo = o outro e mais rapido). None = sem base."""
        if meu_tipo not in ("seco", "chuva"):
            return None, 0
        por_tipo = {"seco": [], "chuva": []}
        for idx in idxs:
            recentes = [(tp, t) for (tm, tp, t) in self._voltas.get(idx, ()) if agora - tm <= self.JANELA_S]
            for tipo in ("seco", "chuva"):
                tempos = [t for tp, t in recentes if tp == tipo]
                if tempos:
                    por_tipo[tipo].append(sum(tempos) / len(tempos))
        outro = "chuva" if meu_tipo == "seco" else "seco"
        if not por_tipo[meu_tipo] or not por_tipo[outro]:
            return None, len(por_tipo[outro])
        ganho = _mediana(por_tipo[meu_tipo]) - _mediana(por_tipo[outro])
        return ganho, len(por_tipo[outro])


class EstrategiaPneus:
    """Decide SEGUIR / PREPARE-SE / TROCAR (chuva <-> seco) a partir de umidade da pista, chuva,
    tendencia e do que os rivais da sua classe fazem. So le dados: nunca pede pneu nem mexe no carro."""
    HOLD_S = 15.0                       # s minimos antes de baixar o aviso (evita pisca-pisca)
    NIVEL_TROCAR_CHUVA = 5              # Molhada
    NIVEL_PREPARE_CHUVA = 4
    NIVEL_TROCAR_SECO = 2               # Quase seca
    NIVEL_PREPARE_SECO = 3
    _RANK = {"seguir": 0, "prepare": 1, "pedido": 2, "trocar": 2}

    def __init__(self):
        self._hist = deque()            # (t, nivel)
        self._acao = None
        self._desde = -1e9

    def resetar(self):
        self._hist.clear()
        self._acao, self._desde = None, -1e9

    def _inclinacao(self, agora):
        """Niveis por minuto (positivo = molhando); None enquanto tem menos de 90 s de historico."""
        if len(self._hist) < 2:
            return None
        t0, n0 = self._hist[0]
        t1, n1 = self._hist[-1]
        if t1 - t0 < 90.0:
            return None
        return (n1 - n0) / ((t1 - t0) / 60.0)

    def atualizar(self, agora, nivel, chuva, meu_pneu, tem_chuva, pedido=None, pre_largada=False,
                  vantagem=None, rivais_outro=0, rivais_mesmo=0):
        nivel = int(nivel) if nivel is not None and 1 <= int(nivel) <= 7 else None
        if nivel is not None:
            if not self._hist or agora - self._hist[-1][0] >= 10.0:
                self._hist.append((agora, nivel))
            while self._hist and agora - self._hist[0][0] > 300.0:
                self._hist.popleft()
        chuva = float(chuva) if chuva is not None else None
        incl = self._inclinacao(agora)
        if (chuva or 0.0) >= 5.0 or (incl is not None and incl > 0.15):
            tendencia = "molhando"
        elif incl is not None and incl < -0.15:
            tendencia = "secando"
        elif nivel is not None:
            tendencia = "sem_chuva" if (chuva or 0.0) < 1.0 else "estavel"
        else:
            tendencia = None
        res = {"nivel": nivel, "nivel_nome": nome_nivel(nivel), "tendencia": tendencia, "acao": "sem_dado",
               "alvo": None, "minutos": None, "vantagem": vantagem, "vantagem_estimada": vantagem is not None,
               "meu_pneu": meu_pneu, "rivais_outro": rivais_outro, "rivais_mesmo": rivais_mesmo,
               "pre_largada": bool(pre_largada)}
        if nivel is None or meu_pneu not in ("seco", "chuva") or not tem_chuva:
            res["motivo"] = ("carro_sem_chuva" if not tem_chuva else "sem_dado")
            return res
        recomendado = "chuva" if (nivel >= self.NIVEL_PREPARE_CHUVA or (nivel >= 3 and (chuva or 0) >= 20)) else "seco"
        if pre_largada:
            res["alvo"] = recomendado
            res["acao"] = "largar_ok" if recomendado == meu_pneu else "largar_trocar"
            return res
        alvo = "seco" if meu_pneu == "chuva" else "chuva"
        res["alvo"] = alvo
        acao, minutos = "seguir", None
        if meu_pneu == "chuva":
            if nivel <= self.NIVEL_TROCAR_SECO and (chuva or 0.0) < 5.0:
                acao = "trocar"
            elif nivel <= self.NIVEL_PREPARE_SECO and (tendencia == "secando" or (incl is not None and incl < 0)):
                acao = "prepare"
                if incl and incl < -0.05:
                    minutos = int(max(1, min(60, round((nivel - self.NIVEL_TROCAR_SECO) / abs(incl)))))
        else:
            if nivel >= self.NIVEL_TROCAR_CHUVA or (nivel >= self.NIVEL_PREPARE_CHUVA and (chuva or 0.0) >= 20.0):
                acao = "trocar"
            elif (nivel >= self.NIVEL_PREPARE_CHUVA or (nivel >= 3 and tendencia == "molhando")
                  or (chuva or 0.0) >= 10.0 and tendencia == "molhando"):
                acao = "prepare"
        if (vantagem is not None and vantagem >= 1.0 and rivais_outro >= 2 and acao != "trocar"):
            acao = "trocar"                       # os rivais ja provam que o outro pneu e bem mais rapido
        # histerese: o aviso so desce depois de HOLD_S segundos
        if self._acao is not None and self._RANK.get(acao, 0) < self._RANK.get(self._acao, 0) \
                and agora - self._desde < self.HOLD_S:
            acao = self._acao
        if acao != self._acao:
            self._acao, self._desde = acao, agora
        if acao == "trocar" and pedido == alvo:
            acao = "pedido"
        res["acao"], res["minutos"] = acao, minutos
        return res


# ---------------------------------------------------------------------------------------------
# Inputs (grafico rolante)
# ---------------------------------------------------------------------------------------------
class HistoricoInputs:
    """Janela deslizante de `segundos` s com acelerador, freio, ABS, TC, marcha (e pedais crus)."""

    def __init__(self, segundos=12.0):
        self.segundos = max(5.0, min(30.0, float(segundos)))
        self._d = deque()

    def definir_segundos(self, segundos):
        self.segundos = max(5.0, min(30.0, float(segundos)))
        self._aparar(self._d[-1][0] if self._d else 0.0)

    def limpar(self):
        self._d.clear()

    def _aparar(self, agora):
        while self._d and agora - self._d[0][0] > self.segundos:
            self._d.popleft()

    def adicionar(self, agora, acel, freio, abs_ativo, tc_ativo, marcha, acel_cru=None, freio_cru=None):
        self._d.append((agora, float(acel), float(freio), bool(abs_ativo), bool(tc_ativo), int(marcha),
                        acel_cru, freio_cru))
        self._aparar(agora)

    def amostras(self):
        return list(self._d)

    def __len__(self):
        return len(self._d)


def marcha_texto(marcha):
    return "R" if marcha is not None and marcha < 0 else ("N" if not marcha else str(int(marcha)))


def pct_pedal(valor):
    """0..1 -> percentual inteiro em texto (0 a 100)."""
    v = max(0.0, min(1.0, float(valor or 0.0)))
    return str(int(round(v * 100)))
