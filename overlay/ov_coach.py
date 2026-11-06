# -*- coding: utf-8 -*-
"""
Coach em tempo real (v1.7) - logica pura, sem Qt e sem depender do jogo (iRacing e LMU usam o mesmo nucleo).

Como funciona
  1. REFERENCIA: uma volta guardada em 1000 trechos da pista (alinhada pela DISTANCIA, nao pelo tempo): velocidade, freio,
     acelerador, marcha e o tempo decorrido em cada trecho. Pode ser a sua melhor volta limpa (gravada aqui) ou uma volta
     importada (CSV do Garage 61, ver ov_referencias.py).
  2. ZONAS DE FRENAGEM: achadas na referencia (freio acima de 10% por um trecho continuo, com pico minimo). Cada zona tem o
     ponto de freada, o apice (menor velocidade), a velocidade no apice e a marcha no apice.
  3. AO VIVO: a distancia ate o proximo ponto de freada, a marcha e a velocidade-alvo no apice, a contagem 3-2-1-FREIE
     (no relogio da referencia) e o delta contra a referencia.
  4. APOS A CURVA: compara a sua freada com a da referencia (metros mais cedo/tarde), a velocidade no apice e a marcha.
  5. APOS A VOLTA: resumo com a pior curva e, se a volta for limpa e mais rapida, ela vira a nova referencia propria.

Convencoes: "~" = estimativa. Nada aqui e dado do jogo alem de velocidade, pedais, marcha, posicao e tempo da volta;
as zonas e os apices sao INFERIDOS da referencia. A referencia e a de um piloto real (voce ou outro): ela depende do carro
e do acerto dele. O coach mostra consistencia, nao um limite fisico "ideal".
"""
import atexit
import json
import math
import os
import re
import threading
import time
from collections import deque
from pathlib import Path

import ov_curvas as curvas_mod

BINS = 1000
VERSAO_REFERENCIA = 1
LIM_FREIO = 0.10              # freio acima disto = "freando"
PICO_MIN = 0.25               # a zona precisa de um pico de freio ao menos deste tamanho (ignora toques)
FOLGA_M = 15.0                # lacunas menores que isto dentro da mesma frenagem nao separam a zona
VEL_MIN_CONTAGEM = 25.0         # abaixo disto (km/h) a contagem por distancia/velocidade nao e confiavel
ANTECEDENCIA_M = 400.0        # so orienta zonas a ate esta distancia
BUSCA_ANTES_M = 120.0         # ao avaliar, procura a sua freada ate esta distancia antes do ponto da referencia
BUSCA_APICE_M = 30.0          # e o seu apice ate esta distancia depois do apice da referencia
COBERTURA_MIN = 0.92
ACEL_PLENA = 0.90             # 1.7.0: acelerador acima disto = pe embaixo
ACEL_TIRADA = 0.60            # abaixo disto (sem freio) = tirou o pe
ACEL_TIRADA_FUNDO = 0.35      # a tirada precisa chegar ate aqui para contar como zona
TIRADA_MIN_M = 10.0           # tirada mais curta que isto e ruido
TIRADA_ANTES_M = 40.0         # tem que vir de pe embaixo ate esta distancia antes
TIRADA_AFASTA_FREIO_M = 25.0  # tiradas coladas numa freada fazem parte dela, nao viram zona
LIM_PERFEITA_M, LIM_BOA_M, LIM_MUITO_M = 8.0, 20.0, 60.0


def _finito(v):
    return v is not None and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# --------------------------------------------------------------------------
# Nomes e compatibilidade
# --------------------------------------------------------------------------
def normalizar_nome(texto):
    return re.sub(r"[^a-z0-9]+", " ", str(texto or "").lower()).strip()


def slug(texto):
    return re.sub(r"[^a-z0-9]+", "_", str(texto or "").lower()).strip("_") or "x"


def mesmo_carro(a, b):
    """Tolera sufixos ("Dallara P217" x "Dallara P217 LMP2")."""
    na, nb = normalizar_nome(a), normalizar_nome(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def compativel(ref, pista, carro, comprimento, tolerancia=0.015):
    """'ok', 'outro_carro' (mesma pista/layout, carro diferente) ou 'incompativel' (outra pista ou layout)."""
    if not ref:
        return "incompativel"
    comp_ref = ref.get("comprimento")
    if _finito(comp_ref) and _finito(comprimento) and comprimento > 0:
        if abs(comp_ref - comprimento) / comprimento > tolerancia:
            return "incompativel"                       # outro layout (o comprimento muda mais que a tolerancia)
    if normalizar_nome(ref.get("pista")) and normalizar_nome(pista) and not (
            mesmo_carro(ref.get("pista"), pista)):
        return "incompativel"
    return "ok" if mesmo_carro(ref.get("carro"), carro) else "outro_carro"


# --------------------------------------------------------------------------
# Referencia
# --------------------------------------------------------------------------
def nova_referencia(pista, carro, origem, comprimento, tempo, vel, freio, acel, marcha, t, fonte=""):
    return {"versao": VERSAO_REFERENCIA, "pista": str(pista or ""), "carro": str(carro or ""), "origem": origem,
            "fonte": fonte, "comprimento": float(comprimento), "tempo": float(tempo),
            "vel": [round(float(x), 2) for x in vel], "freio": [round(float(x), 3) for x in freio],
            "acel": [round(float(x), 3) for x in acel], "marcha": [int(x) for x in marcha],
            "t": [round(float(x), 3) for x in t]}


def validar_referencia(ref):
    """Lista de problemas (vazia = ok): estrutura, quantidade de trechos, valores finitos e em faixa plausivel, relogio nao
    decrescente e coerente com o tempo de volta. Nunca levanta."""
    if not isinstance(ref, dict):
        return ["referencia nao e um dicionario"]
    problemas = []
    n = None
    ok_campos = {}
    for campo in ("vel", "freio", "acel", "marcha", "t"):
        v = ref.get(campo)
        if not isinstance(v, list) or not v:
            problemas.append(f"campo '{campo}' ausente ou vazio")
            continue
        if n is None:
            n = len(v)
        elif len(v) != n:
            problemas.append(f"campo '{campo}' tem {len(v)} trechos (esperado {n})")
            continue
        if not all(_finito(x) for x in v):
            problemas.append(f"campo '{campo}' tem valores invalidos")
            continue
        ok_campos[campo] = v
    if n is not None and n < 100:
        problemas.append(f"poucos trechos ({n})")
    if not _finito(ref.get("comprimento")) or ref["comprimento"] < 300.0:
        problemas.append("comprimento da pista invalido")
    if not _finito(ref.get("tempo")) or ref["tempo"] <= 0:
        problemas.append("tempo de volta invalido")
    if "vel" in ok_campos and not all(0.0 <= x <= 500.0 for x in ok_campos["vel"]):
        problemas.append("velocidade fora da faixa (0-500 km/h)")
    for campo in ("freio", "acel"):
        if campo in ok_campos and not all(-0.01 <= x <= 1.01 for x in ok_campos[campo]):
            problemas.append(f"campo '{campo}' fora de 0-1")
    if "t" in ok_campos:
        t = ok_campos["t"]
        if any(t[i] > t[i + 1] + 1e-9 for i in range(len(t) - 1)):
            problemas.append("relogio nao e crescente")
        elif _finito(ref.get("tempo")) and ref["tempo"] > 0 and (t[-1] > ref["tempo"] * 1.05 or t[0] < -1e-6):
            problemas.append("relogio incoerente com o tempo de volta")
    return problemas


def corrigir_blips(acel, marcha, freio=None, antes=1, depois=7):
    """Remove o 'blip' automatico de acelerador nas reducoes de marcha (comum em exportacoes): interpola entre o valor
    logo antes e o valor logo depois. Usado so em voltas IMPORTADAS; o traco ao vivo continua cru."""
    n = len(acel)
    out = list(acel)
    for i in range(1, n):
        if marcha[i] < marcha[i - 1] and marcha[i] > 0:           # reducao de marcha
            a, b = max(0, i - 1 - antes), min(n - 1, i + depois)
            va, vb = acel[a], acel[b]
            if max(acel[a:b + 1]) - max(va, vb) < 0.08:            # nao houve pico: nada a corrigir
                continue
            for k in range(a, b + 1):
                f = (k - a) / max(1, b - a)
                out[k] = va + (vb - va) * f
    return out


def zonas_de_frenagem(ref):
    """Zonas de frenagem da referencia: [{n, ini, fim, pico, apice, vel_entrada, vel_apice, marcha_apice}]."""
    cache = ref.get("_zonas")
    if cache is not None:
        return cache
    freio, vel, marcha = ref["freio"], ref["vel"], ref["marcha"]
    n = len(freio)
    comp = float(ref["comprimento"])
    folga = max(2, int(round(FOLGA_M / comp * n)))
    brutas = []
    i = 0
    while i < n:
        if freio[i] >= LIM_FREIO:
            ult, k = i, i
            while k < n and (k - ult) <= folga:
                if freio[k] >= LIM_FREIO:
                    ult = k
                k += 1
            pico = max(freio[i:ult + 1])
            if pico >= PICO_MIN and (ult - i + 1) >= 3:
                brutas.append((i, ult, pico))
            i = ult + 1
        else:
            i += 1
    zonas = []
    max_apice = int(round(0.06 * n))
    for idx, (ini, fim, pico) in enumerate(brutas):
        limite = brutas[idx + 1][0] - 1 if idx + 1 < len(brutas) else n - 1
        fim_busca = min(limite, fim + max_apice)
        apice = min(range(ini, fim_busca + 1), key=lambda j: vel[j])
        zonas.append({"n": idx + 1, "ini": ini, "fim": fim, "pico": pico, "apice": apice, "vel_entrada": vel[ini],
                      "vel_apice": vel[apice], "marcha_apice": marcha[apice]})
    ref["_zonas"] = zonas
    return zonas


def zonas_de_tirada(ref):
    """1.7.0: zonas em que a referencia TIRA O PE do acelerador sem frear (curvas rapidas, 'trail-off'): vinha de pe embaixo,
    o acelerador cai abaixo de ACEL_TIRADA_FUNDO sem freio e volta. Tiradas coladas numa freada pertencem a ela."""
    cache = ref.get("_zonas_tirada")
    if cache is not None:
        return cache
    acel, freio, vel, marcha = ref.get("acel"), ref["freio"], ref["vel"], ref["marcha"]
    zonas = []
    if not acel or len(acel) != len(freio):
        ref["_zonas_tirada"] = zonas
        return zonas
    n = len(freio)
    comp = float(ref["comprimento"])
    bm = n / comp                                                       # bins por metro
    minimo = max(2, int(round(TIRADA_MIN_M * bm)))
    antes = max(2, int(round(TIRADA_ANTES_M * bm)))
    freadas = [(z["ini"] - int(TIRADA_AFASTA_FREIO_M * bm), z["fim"] + int(10 * bm)) for z in zonas_de_frenagem(ref)]
    i = 0
    while i < n:
        if acel[i] is not None and acel[i] < ACEL_TIRADA and freio[i] < LIM_FREIO:
            k = i
            while k + 1 < n and acel[k + 1] is not None and acel[k + 1] < ACEL_TIRADA and freio[k + 1] < LIM_FREIO:
                k += 1
            fundo = min(acel[i:k + 1])
            # onde comecou a cair: volta enquanto o acelerador estiver abaixo de ACEL_PLENA
            j = i
            while j > 0 and acel[j - 1] is not None and acel[j - 1] < ACEL_PLENA and (i - j) < antes:
                j -= 1
            veio_de_pe_embaixo = j > 0 and acel[j - 1] is not None and acel[j - 1] >= ACEL_PLENA
            if (k - i + 1) >= minimo and fundo <= ACEL_TIRADA_FUNDO and veio_de_pe_embaixo \
                    and not any(not (k < a or j > b) for a, b in freadas):
                fim_busca = min(n - 1, k + int(30 * bm))
                apice = min(range(j, fim_busca + 1), key=lambda x: vel[x] if vel[x] is not None else 1e9)
                zonas.append({"ini": j, "fim": k, "pico": round(1.0 - fundo, 3), "apice": apice, "vel_entrada": vel[j],
                              "vel_apice": vel[apice], "marcha_apice": marcha[apice], "tipo": "tirada"})
            i = k + 1
        else:
            i += 1
    ref["_zonas_tirada"] = zonas
    return zonas


def todas_as_zonas(ref):
    """Zonas de freada + de tirada, em ordem de pista, numeradas juntas (C1, C2...). Sem tiradas, igual a zonas_de_frenagem."""
    cache = ref.get("_zonas_todas")
    if cache is not None:
        return cache
    todas = [dict(z, tipo="freio") for z in zonas_de_frenagem(ref)] + [dict(z) for z in zonas_de_tirada(ref)]
    todas.sort(key=lambda z: z["ini"])
    for idx, z in enumerate(todas):
        z["n"] = idx + 1
    ref["_zonas_todas"] = todas
    return todas


# --------------------------------------------------------------------------
# Gravacao em segundo plano (1.7.0): nenhuma escrita em disco na thread que atualiza o Coach / a interface
# --------------------------------------------------------------------------
registrar_log = None            # o overlay liga isto ao log: registrar_log("aviso" | "info", texto)


def _log(nivel, texto):
    try:
        if registrar_log is not None:
            registrar_log(nivel, texto)
    except Exception:
        pass


class _Exclusao:
    """Pedido de exclusao entregue ao gravador (ver GravadorSegundoPlano.registrar_exclusao)."""
    def __init__(self, chave, versao, funcao):
        self.chave, self.versao, self.funcao = chave, versao, funcao
        self.evento = threading.Event()
        self.resultado = False
        self.nao_antes = 0.0


class _EmVoo:
    """Trabalho que a thread gravadora ja retirou da fila e ainda nao executou (para o encerramento nao o perder)."""
    __slots__ = ("lote", "item", "tomado")

    def __init__(self, lote, item):
        self.lote, self.item, self.tomado = lote, item, False


class GravadorSegundoPlano:
    """Fila de gravacao por chave, atendida por UMA thread daemon (nunca ha duas gravacoes em paralelo).
    Cada tarefa leva uma VERSAO monotonica: um snapshot mais antigo nunca substitui nem sobrescreve um mais novo, mesmo que
    quem o agendou chegue atrasado (ordem de agendamento != ordem de criacao). Falha de gravacao nao some: tenta de novo
    (TENTATIVAS), registra no log, guarda a tarefa em 'falhou' e gravar_agora() tenta uma ultima vez ao encerrar.
    EXCLUSAO serializada: registrar_exclusao() grava no gravador um "piso" de versao (nada abaixo dele e publicado, nem o que
    ja estava na fila nem o que estiver em gravacao quando a thread de fundo chegar a ele) e entrega a exclusao a MESMA thread
    que grava, que a executa sob o lock de I/O depois da gravacao em curso e antes de qualquer snapshot posterior. Assim um
    snapshot antigo nunca recria um arquivo apagado. agendar() e registrar_exclusao() nunca bloqueiam no disco."""
    TENTATIVAS = 3
    ESPERA_S = 0.2

    def __init__(self, nome="coach-gravador"):
        self._cv = threading.Condition()
        self._io = threading.Lock()         # quem grava segura isto (thread de fundo ou gravar_agora)
        self._pend = {}                     # chave -> (versao, funcao)
        self._falhou = {}                   # chave -> (versao, funcao): gravacao que nao deu certo e ainda nao foi superada
        self._ultima = {}                   # chave -> maior versao ja gravada ou invalidada
        self._piso = {}                     # chave -> versao minima publicavel (abaixo disso o snapshot foi invalidado)
        self._exclusoes = []                # exclusoes pedidas e ainda nao executadas (ordem de pedido)
        self._seq = 0
        self._ocupado = False
        self._voo = None
        self._thread = None
        self._nome = nome
        self.gravacoes = 0
        self.falhas = 0
        self.obsoletos = 0                  # snapshots antigos descartados (chegaram depois de um mais novo)
        self.exclusoes = 0                  # exclusoes executadas
        self.ultimo_erro = None

    # ---- entrada -------------------------------------------------------------------------------------------
    def agendar(self, chave, funcao, versao=None):
        """Agenda a gravacao. Devolve False se descartada por ser mais antiga que uma versao ja gravada/agendada."""
        with self._cv:
            if versao is None:
                self._seq += 1
                versao = self._seq
            atual = max(self._ultima.get(chave, -1), self._pend[chave][0] if chave in self._pend else -1)
            if versao < atual:
                self.obsoletos += 1
                return False
            self._pend[chave] = (versao, funcao)
            if chave in self._falhou and self._falhou[chave][0] <= versao:
                del self._falhou[chave]               # o snapshot novo substitui o que tinha falhado
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._rodar, name=self._nome, daemon=True)
                self._thread.start()
            self._cv.notify_all()
            return True

    def invalidar(self, chave, versao):
        """Descarta tudo o que for mais antigo que 'versao' para a chave (ex.: o arquivo foi apagado de proposito)."""
        with self._cv:
            self._ultima[chave] = max(self._ultima.get(chave, -1), versao)
            self._piso[chave] = max(self._piso.get(chave, -1), versao)
            if chave in self._pend and self._pend[chave][0] < versao:
                del self._pend[chave]
            if chave in self._falhou and self._falhou[chave][0] < versao:
                del self._falhou[chave]
            self._cv.notify_all()

    def registrar_exclusao(self, chave, versao, funcao):
        """Invalida tudo que for mais antigo que 'versao' e pede que 'funcao' (a exclusao) rode na thread do gravador, sob o lock
        de I/O: depois da gravacao em curso e antes de qualquer snapshot de versao >= 'versao'. Nao bloqueia. Devolve um objeto
        com .evento (set quando a exclusao foi executada). Quem chama deve usar uma 'versao' maior que a de qualquer snapshot
        ja criado (o Coach faz isso dentro do seu lock) para que o piso cubra todos os snapshots antigos."""
        exc = _Exclusao(chave, versao, funcao)
        with self._cv:
            self._ultima[chave] = max(self._ultima.get(chave, -1), versao)
            self._piso[chave] = max(self._piso.get(chave, -1), versao)
            if chave in self._pend and self._pend[chave][0] < versao:
                del self._pend[chave]
            if chave in self._falhou and self._falhou[chave][0] < versao:
                del self._falhou[chave]
            self._exclusoes.append(exc)
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._rodar, name=self._nome, daemon=True)
                self._thread.start()
            self._cv.notify_all()
        return exc

    def _publicavel(self, chave, versao):
        """True se o snapshot nao foi invalidado. Chamado sob o lock de I/O, imediatamente antes de gravar."""
        with self._cv:
            return versao >= self._piso.get(chave, -1)

    # ---- thread de fundo -----------------------------------------------------------------------------------
    def _executar(self, chave, versao, funcao, verbo="gravar"):
        """Executa com ate TENTATIVAS tentativas. True se deu certo."""
        erro = None
        for k in range(self.TENTATIVAS):
            try:
                if funcao() is not False:
                    return True
                erro = "a gravacao devolveu falha"
            except Exception as e:
                erro = f"{e.__class__.__name__}: {e}"
            if k + 1 < self.TENTATIVAS:
                time.sleep(self.ESPERA_S)
        self.ultimo_erro = erro
        if verbo == "gravar":
            _log("aviso", f"Coach: nao consegui gravar {chave[0]} apos {self.TENTATIVAS} tentativas ({erro}); "
                          "os dados continuam na memoria e serao regravados")
        else:
            _log("aviso", f"Coach: nao consegui apagar {chave[0]} apos {self.TENTATIVAS} tentativas ({erro}); "
                          "a exclusao continua pendente e nenhum dado antigo sera regravado")
        return False

    def _executar_exclusoes(self, lote):
        """Roda as exclusoes (sob o lock de I/O). As que falham voltam para a fila, com espera, e BLOQUEIAM novas gravacoes da
        mesma chave ate darem certo (para a exclusao tardia nao apagar um snapshot novo)."""
        for exc in lote:
            ok = self._executar(exc.chave, exc.versao, exc.funcao, "apagar")
            with self._cv:
                if ok:
                    exc.resultado = True
                    exc.evento.set()
                    self.exclusoes += 1
                else:
                    exc.nao_antes = time.monotonic() + 1.0
                    self._exclusoes.insert(0, exc)

    def _rodar(self):
        while True:
            lote, item = [], None
            with self._cv:
                while True:
                    agora = time.monotonic()
                    lote = [e for e in self._exclusoes if e.nao_antes <= agora]
                    if lote:
                        self._exclusoes = [e for e in self._exclusoes if e not in lote]
                        break
                    travadas = {e.chave for e in self._exclusoes}              # chave com exclusao falha em espera: nao grava
                    livres = [k for k in self._pend if k not in travadas]
                    if livres:
                        chave = livres[0]
                        versao, funcao = self._pend.pop(chave)
                        # a versao em gravacao ja conta como "vista": um snapshot mais antigo que chegue enquanto esta grava e descartado
                        self._ultima[chave] = max(self._ultima.get(chave, -1), versao)
                        item = (chave, versao, funcao)
                        break
                    if not self._pend and not self._exclusoes:
                        self._cv.wait(timeout=2.0)
                        if not self._pend and not self._exclusoes:
                            self._thread = None
                            self._cv.notify_all()
                            return
                    else:
                        self._cv.wait(timeout=0.2)
                self._ocupado = True
                voo = _EmVoo(lote, item)
                self._voo = voo                                        # o que ja saiu da fila e ainda nao rodou (gravar_agora pode assumir)
            try:
                with self._io:
                    with self._cv:
                        if voo.tomado:                                 # gravar_agora (encerramento) ja executou isto
                            continue
                    if lote:
                        self._executar_exclusoes(lote)
                        continue
                    chave, versao, funcao = item
                    if not self._publicavel(chave, versao):
                        with self._cv:
                            self.obsoletos += 1                     # invalidado (ex.: historico apagado) enquanto esperava a vez
                        continue
                    ok = self._executar(chave, versao, funcao)
                with self._cv:
                    if ok:
                        self.gravacoes += 1
                        self._ultima[chave] = max(self._ultima.get(chave, -1), versao)
                        self._falhou.pop(chave, None)
                    else:
                        self.falhas += 1
                        if chave not in self._pend or self._pend[chave][0] < versao:      # se ja ha um snapshot mais novo, ele cobre este
                            self._falhou[chave] = (versao, funcao)
            finally:
                with self._cv:
                    self._ocupado = False
                    self._voo = None
                    self._cv.notify_all()

    # ---- descarga -------------------------------------------------------------------------------------------
    def pendentes(self):
        with self._cv:
            return len(self._pend) + len(self._falhou) + len(self._exclusoes) + (1 if self._ocupado else 0)

    def descarregar(self, timeout=5.0):
        """Espera a fila esvaziar. True so se TUDO foi gravado (sem pendente nem gravacao falha)."""
        fim = time.monotonic() + timeout
        with self._cv:
            while self._pend or self._ocupado or self._exclusoes:
                resto = fim - time.monotonic()
                if resto <= 0:
                    return False
                self._cv.wait(timeout=min(resto, 0.2))
            return not self._falhou

    def gravar_agora(self, timeout=5.0):
        """Ultima chance (ao encerrar): grava NA THREAD DE QUEM CHAMA o que sobrou (pendente ou falho). True se nada ficou."""
        if not self._io.acquire(timeout=timeout):
            _log("aviso", "Coach: gravador ocupado ao encerrar; ha gravacao pendente")
            return False
        try:
            with self._cv:
                restantes = dict(self._falhou)
                restantes.update(self._pend)
                excl = list(self._exclusoes)
                voo = getattr(self, "_voo", None)
                if voo is not None and not voo.tomado:             # item que a thread ja tirou da fila mas ainda nao executou
                    voo.tomado = True
                    if voo.lote:
                        excl += list(voo.lote)
                    elif voo.item:
                        c, v, fn = voo.item
                        if v >= restantes.get(c, (-1, None))[0]:
                            restantes[c] = (v, fn)
                self._pend.clear()
                self._falhou.clear()
                self._exclusoes = []
            tudo = True
            for exc in excl:                                   # exclusoes primeiro: nada invalidado pode ser regravado
                exc.nao_antes = 0.0
            self._executar_exclusoes(excl)
            with self._cv:
                ainda = {e.chave for e in self._exclusoes}
            tudo = not ainda
            for chave, (versao, funcao) in restantes.items():
                if chave in ainda or not self._publicavel(chave, versao):
                    continue
                if versao < self._ultima.get(chave, -1):
                    continue
                if self._executar(chave, versao, funcao):
                    self._ultima[chave] = max(self._ultima.get(chave, -1), versao)
                    self.gravacoes += 1
                else:
                    self.falhas += 1
                    tudo = False
                    with self._cv:
                        self._falhou[chave] = (versao, funcao)
            return tudo
        finally:
            self._io.release()


# --------------------------------------------------------------------------
# Biblioteca (arquivos locais)
# --------------------------------------------------------------------------
class BibliotecaReferencias:
    """Uma referencia propria e uma importada por pista+carro, em arquivos JSON na pasta indicada."""

    def __init__(self, pasta):
        self.pasta = Path(pasta)

    def _arquivo(self, pista, carro, origem):
        return self.pasta / f"{slug(pista)}__{slug(carro)}__{origem}.json"

    def salvar(self, ref):
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
            destino = self._arquivo(ref["pista"], ref["carro"], ref["origem"])
            limpo = {k: v for k, v in ref.items() if not k.startswith("_")}
            tmp = destino.with_name(destino.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                tmp.write_text(json.dumps(limpo, separators=(",", ":")), encoding="utf-8")
                os.replace(tmp, destino)
            except BaseException:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                raise
            return True
        except Exception:
            return False

    def carregar(self, pista, carro, origem):
        try:
            arq = self._arquivo(pista, carro, origem)
            if not arq.is_file():
                return None
            ref = json.loads(arq.read_text(encoding="utf-8"))
            return None if validar_referencia(ref) else ref
        except Exception:
            return None

    def apagar(self, pista, carro, origem):
        try:
            self._arquivo(pista, carro, origem).unlink()
            return True
        except Exception:
            return False

    def listar(self):
        saida = []
        try:
            for arq in sorted(self.pasta.glob("*.json")):
                try:
                    ref = json.loads(arq.read_text(encoding="utf-8"))
                    saida.append({"arquivo": arq.name, "pista": ref.get("pista"), "carro": ref.get("carro"),
                                  "origem": ref.get("origem"), "tempo": ref.get("tempo"), "fonte": ref.get("fonte", "")})
                except Exception:
                    continue
        except Exception:
            pass
        return saida


# --------------------------------------------------------------------------
# Gravacao da volta
# --------------------------------------------------------------------------
class RegistradorVolta:
    """Guarda a volta em andamento em BINS trechos. Mesmas regras de volta valida da velocidade minima por curva."""

    def __init__(self, bins=BINS):
        self.bins = bins
        self.zerar()

    def zerar(self):
        n = self.bins
        self.vel = [None] * n
        self.freio = [0.0] * n
        self.acel = [0.0] * n
        self.marcha = [None] * n
        self.t = [None] * n
        self.invalida = False
        self.ultimo_bin = None

    def registrar(self, b, vel, freio, acel, marcha, t, valido=True):
        """Uma amostra. Devolve a volta fechada (dict) se cruzou a linha de chegada, senao None."""
        evento = None
        ant = self.ultimo_bin
        n = self.bins
        if ant is not None:
            if ant > 0.8 * n and b < 0.2 * n:
                evento = self._fechar()
                ant = None
            elif b < ant - 0.1 * n:
                self.zerar()
                ant = None
            elif b > ant + 0.1 * n:
                self.invalida = True
                ant = None
        self.ultimo_bin = b
        if not valido:
            self.invalida = True
        if vel < 10.0 and b > 5:
            self.invalida = True
        inicio = b if ant is None or b <= ant else ant + 1
        for k in range(inicio, b + 1):                   # trechos pulados em alta velocidade recebem a mesma amostra
            self.vel[k] = float(vel)
            self.freio[k] = max(self.freio[k], float(freio))
            self.acel[k] = float(acel)
            self.marcha[k] = int(marcha)
            self.t[k] = float(t) if _finito(t) else None
        return evento

    def _fechar(self):
        n = self.bins
        cobertura = sum(1 for v in self.vel if v is not None) / float(n)
        volta = {"vel": list(self.vel), "freio": list(self.freio), "acel": list(self.acel), "marcha": list(self.marcha),
                 "t": list(self.t), "invalida": self.invalida, "cobertura": cobertura}
        self.zerar()
        return volta


def _completar_marcha(marcha):
    out, ult = [], 0
    for m in marcha:
        if m is not None:
            ult = m
        out.append(ult)
    return out


# --------------------------------------------------------------------------
# Coach ao vivo
# --------------------------------------------------------------------------
class Coach:
    def __init__(self, biblioteca=None, bins=BINS, historico=None):
        self.bins = bins
        self.bib = biblioteca
        # 1.7.0: historico das suas voltas validas (melhor por curva e resumo da sessao); fica ao lado da biblioteca
        if historico is None and biblioteca is not None:
            import ov_melhorcurva
            historico = ov_melhorcurva.HistoricoCurvas(Path(biblioteca.pasta) / "historico")
        self.hist = historico
        self.sessao = int(time.time())          # identifica esta execucao; o resumo da sessao so olha as voltas dela
        self._voltas_hist = None
        self._trava_hist = threading.Lock()      # protege SO a lista em memoria (as voltas dos .ibt entram de outra thread)
        self._dicas, self._dicas_chave = {}, None
        self._hist_ver = 0                       # sobe a cada mudanca do historico (invalida o cache das dicas)
        # 1.7.0: toda gravacao em disco (historico e referencia propria) acontece numa thread propria, nunca na de atualizacao
        self.gravador = GravadorSegundoPlano()
        self._perf = deque(maxlen=2048)          # duracao (ms) de cada atualizar(), para medir p95/p99 na sessao real
        self._perf_total = 0
        self._ref_ver = 0                        # versao das gravacoes da referencia propria
        atexit.register(self.encerrar, 3.0)
        self.modo = "auto"                 # auto (importada se houver) | propria | importada
        self.ref_propria = None
        self.ref_importada = None
        self.pista, self.carro, self.comprimento = "", "", None
        self.rec = RegistradorVolta(bins)
        self.voltas_gravadas = 0
        self.aviso_ref = None              # ex.: "referencia de outro carro"
        self.resumo_volta = None
        self.ultimo_feedback = None
        self._feitos = set()
        self._feedbacks = []

    # ---- contexto e referencia --------------------------------------------------------------------------------
    def definir_contexto(self, pista, carro, comprimento=None):
        if _finito(comprimento) and comprimento > 300.0:
            self.comprimento = float(comprimento)
        if (pista or "", carro or "") == (self.pista, self.carro):
            return
        self.pista, self.carro = pista or "", carro or ""
        self.rec.zerar()
        self._feitos, self._feedbacks = set(), []
        self.ultimo_feedback, self.resumo_volta, self.voltas_gravadas = None, None, 0
        self._voltas_hist, self._dicas, self._dicas_chave = None, {}, None
        self.ref_propria = self._carregar("propria")
        self.ref_importada = self._carregar("importada")

    def _carregar(self, origem):
        if self.bib is None or not self.pista:
            return None
        ref = self.bib.carregar(self.pista, self.carro, origem)
        if ref and compativel(ref, self.pista, self.carro, self.comprimento) == "incompativel":
            return None
        return ref

    def definir_propria(self, ref, salvar=True):
        """Instala uma referencia PROPRIA vinda de fora (ex.: telemetria .ibt gravada pelo iRacing). So vale se for mais rapida
        que a propria atual. Devolve True se instalou."""
        ref = dict(ref)
        ref["origem"] = "propria"
        if self.pista and compativel(ref, self.pista, self.carro, self.comprimento) != "ok":
            return False
        if self.ref_propria is not None and self.ref_propria["tempo"] <= ref["tempo"]:
            return False
        self.ref_propria = ref
        if salvar and self.bib is not None:
            self.bib.salvar(ref)
        return True

    def definir_importada(self, ref, salvar=True):
        """Instala uma referencia importada (ja validada). Devolve a compatibilidade com a pista/carro atuais."""
        ref = dict(ref)
        ref["origem"] = "importada"
        comp = compativel(ref, self.pista, self.carro, self.comprimento) if self.pista else "ok"
        if comp == "incompativel":
            return comp
        self.ref_importada = ref
        if salvar and self.bib is not None:
            self.bib.salvar(ref)
        return comp

    def referencia_ativa(self):
        if self.modo == "propria":
            return self.ref_propria
        if self.modo == "importada":
            return self.ref_importada
        # automatico: a MAIS RAPIDA entre a sua e a importada. Se a importada for de outro carro, a sua tem prioridade
        # (volta de outro carro/acerto nao e alvo confiavel), desde que exista.
        a, b = self.ref_propria, self.ref_importada
        if a is None or b is None:
            return a or b
        if compativel(b, self.pista, self.carro, self.comprimento) == "outro_carro":
            return a
        return a if a["tempo"] <= b["tempo"] else b

    def fonte_ativa(self):
        ref = self.referencia_ativa()
        return None if ref is None else ref.get("origem")

    # ---- entrada ----------------------------------------------------------------------------------------------
    def atualizar(self, pct, vel_kmh, freio, acel, marcha, tempo_volta, valido=True, comprimento=None, ultima_volta=None):
        t0 = time.perf_counter()
        try:
            return self._atualizar(pct, vel_kmh, freio, acel, marcha, tempo_volta, valido, comprimento, ultima_volta)
        finally:
            self._perf.append((time.perf_counter() - t0) * 1000.0)
            self._perf_total += 1

    def estatisticas_desempenho(self):
        """Duracao de atualizar() em ms sobre as ultimas chamadas: {n, total, p50, p95, p99, max}. Instrumentacao para a sessao real."""
        v = sorted(self._perf)
        if not v:
            return {"n": 0, "total": self._perf_total, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
        def pct(q):
            return v[min(len(v) - 1, int(math.ceil(q * len(v))) - 1)]
        return {"n": len(v), "total": self._perf_total, "p50": pct(0.50), "p95": pct(0.95), "p99": pct(0.99), "max": v[-1]}

    def descarregar(self, timeout=5.0):
        """Espera as gravacoes em segundo plano terminarem (chamado ao encerrar e antes de apagar arquivos). True se tudo gravado."""
        try:
            return self.gravador.descarregar(timeout)
        except Exception:
            return False

    def encerrar(self, timeout=5.0):
        """Ao fechar o overlay: espera a fila; se sobrar algo (pendente, falho ou tempo esgotado), grava agora, aqui, e registra
        no log. Nunca levanta. True se tudo ficou gravado."""
        try:
            ok = self.descarregar(timeout)
            if not ok:
                _log("aviso", f"Coach: {self.gravador.pendentes()} gravacao(oes) pendente(s) ao encerrar (prazo de {timeout:.0f} s); "
                              "gravando agora")
                ok = self.gravador.gravar_agora(timeout)
                _log("info" if ok else "aviso", "Coach: gravacao final " + ("concluida" if ok else "INCOMPLETA: ha dados nao gravados"))
            return ok
        except Exception:
            return False

    def estatisticas_gravacao(self):
        g = self.gravador
        return {"gravacoes": g.gravacoes, "falhas": g.falhas, "obsoletos": g.obsoletos, "pendentes": g.pendentes(),
                "ultimo_erro": g.ultimo_erro}

    def _atualizar(self, pct, vel_kmh, freio, acel, marcha, tempo_volta, valido, comprimento, ultima_volta):
        if _finito(comprimento) and comprimento > 300.0:
            self.comprimento = float(comprimento)
        if not (_finito(pct) and _finito(vel_kmh)):
            return self.resumo()
        n = self.bins
        pct = pct - math.floor(pct)
        b = min(n - 1, max(0, int(pct * n)))
        fechada = self.rec.registrar(b, vel_kmh, freio if _finito(freio) else 0.0, acel if _finito(acel) else 0.0,
                                     marcha if isinstance(marcha, int) else 0, tempo_volta, valido)
        if fechada is not None:
            self._volta_fechada(fechada, ultima_volta)
        ref = self.referencia_ativa()
        guia, delta = None, None
        if ref is not None and self.comprimento:
            self._avaliar_zonas_passadas(ref, b)
            guia = self._guia(ref, b, vel_kmh)
            if guia is not None:
                d = self._dicas_atuais(ref).get(guia["n"])
                if d:
                    guia["melhor_sua"] = dict(d)
            if _finito(tempo_volta) and tempo_volta > 0 and ref["t"][b] is not None:
                delta = float(tempo_volta) - ref["t"][b]
        return self.resumo(guia, delta)

    # ---- fim da volta -----------------------------------------------------------------------------------------
    def _volta_fechada(self, v, ultima_volta):
        ref = self.referencia_ativa()
        resumo = self._resumir_volta(ref, ultima_volta)
        self._feitos, self._feedbacks = set(), []
        if v["invalida"] or v["cobertura"] < COBERTURA_MIN or not self.comprimento or not self.pista:
            self.resumo_volta = resumo
            return
        vel = curvas_mod.preencher(v["vel"])
        t = curvas_mod.preencher(v["t"])
        if vel is None or t is None:
            self.resumo_volta = resumo
            return
        tempo = ultima_volta if _finito(ultima_volta) and ultima_volta > 0 else t[-1]
        if not _finito(tempo) or tempo <= 0:
            self.resumo_volta = resumo
            return
        candidata = nova_referencia(self.pista, self.carro, "propria", self.comprimento, tempo, vel, v["freio"],
                                    v["acel"], _completar_marcha(v["marcha"]), t, fonte="sua melhor volta")
        self.voltas_gravadas += 1
        self._registrar_historico(candidata, self.sessao)
        if self.ref_propria is None or tempo < self.ref_propria["tempo"]:
            self.ref_propria = candidata
            if self.bib is not None:
                bib = self.bib
                self._ref_ver += 1
                self.gravador.agendar(("ref", candidata["pista"], candidata["carro"], candidata["origem"]),
                                      lambda bib=bib, c=candidata: bib.salvar(c), self._ref_ver)
            if resumo is not None:
                resumo["nova_referencia"] = True
        self.resumo_volta = resumo

    # ---- historico: melhor por curva e resumo da sessao (1.7.0) -------------------------------------------------
    def _voltas(self):
        if self._voltas_hist is None:
            self._voltas_hist = self.hist.carregar(self.pista, self.carro) if (self.hist and self.pista) else []
        return self._voltas_hist

    def _registrar_historico(self, volta, sessao, origem="ao_vivo", numero=None):
        """Guarda uma volta valida no historico. O trabalho pesado (compactar, validar) fica FORA do lock; o lock cobre so a
        troca da lista em memoria; a gravacao em disco vai para a thread de segundo plano (snapshot imutavel). Nunca levanta."""
        try:
            if self.hist is None or not self.pista:
                return False
            import ov_melhorcurva as mc
            compacta = mc.volta_compacta(volta, sessao, origem, numero)
            pista, carro, hist = self.pista, self.carro, self.hist
            with self._trava_hist:
                antes = self._voltas()
                novas = mc.acrescentar(antes, compacta, self.sessao)
                if novas is antes:
                    return False
                self._voltas_hist = novas                 # a lista nunca e alterada no lugar: quem a leu continua com a sua copia
                self._hist_ver += 1
                versao = self._hist_ver                   # a versao nasce junto com o snapshot, dentro do lock
            # fora do lock: duas threads podem chegar aqui em ordem trocada; o gravador descarta o snapshot mais antigo
            self.gravador.agendar(("hist", pista, carro), lambda: hist.salvar(pista, carro, novas), versao)
            return True
        except Exception:
            return False

    def registrar_volta_externa(self, ref, origem="ibt", numero=None):
        """Volta valida de outra origem (ex.: telemetria .ibt): entra no historico como de uma sessao ANTERIOR (nao conta no
        resumo da sessao). So aceita a mesma pista e carro. A mesma volta nao entra duas vezes. Devolve True se entrou."""
        if self.pista and compativel(ref, self.pista, self.carro, self.comprimento) == "ok":
            return self._registrar_historico(ref, 0, origem, numero)
        return False

    TIMEOUT_APAGAR_S = 1.5            # quanto a thread chamadora espera a exclusao (nunca indefinidamente)

    def apagar_historico(self):
        """Apaga o historico por curva da pista e carro atuais. A exclusao roda na thread do gravador, depois da gravacao em curso
        e antes de qualquer snapshot novo; snapshots antigos ficam invalidados e nunca recriam o arquivo. Espera no maximo
        TIMEOUT_APAGAR_S: se a gravacao em curso demorar mais, a exclusao continua garantida em segundo plano (log de aviso).
        True se havia historico a apagar."""
        if self.hist is None or not self.pista:
            return False
        try:
            pista, carro, hist = self.pista, self.carro, self.hist
            existia = hist._arquivo(pista, carro).exists()
            def apagar_arquivo():
                hist.apagar(pista, carro)
                return not hist._arquivo(pista, carro).exists()      # arquivo ja inexistente tambem e sucesso
            with self._trava_hist:
                # memoria, versao e pedido de exclusao nascem juntos, sob o lock: todo snapshot anterior fica abaixo do piso
                # e todo snapshot posterior nasce depois do pedido (portanto depois da exclusao na fila do gravador)
                self._voltas_hist = []
                self._hist_ver += 1
                versao = self._hist_ver
                exc = self.gravador.registrar_exclusao(("hist", pista, carro), versao, apagar_arquivo)
            self._dicas, self._dicas_chave = {}, None
            if not exc.evento.wait(self.TIMEOUT_APAGAR_S):
                _log("aviso", "Coach: a gravacao em curso demorou; a exclusao do historico por curva foi agendada e sera "
                              "executada assim que ela terminar (nenhum dado antigo sera regravado)")
            return existia
        except Exception:
            return False

    def _dicas_atuais(self, ref):
        voltas = self._voltas()
        chave = (id(ref), self._hist_ver, ref.get("tempo"), self.pista, self.carro)
        if chave != self._dicas_chave:
            try:
                import ov_melhorcurva as mc
                self._dicas = mc.dicas_por_curva(voltas, ref)
                for d in self._dicas.values():
                    d["texto"] = mc.texto_dica(d)
            except Exception:
                self._dicas = {}
            self._dicas_chave = chave
        return self._dicas

    def resumo_da_sessao(self):
        """Onde mais perdeu tempo, por curva, nesta sessao (ver ov_melhorcurva.resumo_sessao). Nunca levanta."""
        try:
            import ov_melhorcurva as mc
            r = mc.resumo_sessao(self._voltas(), self.sessao)
            r["texto"] = mc.texto_resumo(r)
            r["pista"], r["carro"] = self.pista, self.carro
            return r
        except Exception:
            return {"aviso": "Resumo indisponivel.", "texto": "Resumo indisponivel.", "itens": [], "voltas": 0}

    def _resumir_volta(self, ref, tempo):
        if not self._feedbacks:
            return None
        pior = max(self._feedbacks, key=lambda f: f["gravidade"])
        dif = None
        if ref is not None and _finito(tempo) and tempo > 0:
            dif = float(tempo) - ref["tempo"]
        return {"tempo": tempo, "diferenca_ref": dif, "zonas": len(self._feedbacks),
                "pior": pior if pior["gravidade"] > 0 else None, "feedbacks": list(self._feedbacks),
                "nova_referencia": False}

    # ---- orientacao ao vivo -----------------------------------------------------------------------------------
    def _guia(self, ref, b, vel_kmh=None):
        """Orientacao ao vivo. A contagem 3-2-1 usa a DISTANCIA fisica ate o ponto de freada e a sua velocidade atual
        (tempo_ate = estimativa; contagem_base='distancia'). Sem velocidade valida, cai no relogio da referencia
        (contagem_base='referencia', so aproximado: e o tempo que a REFERENCIA levou, nao uma previsao para voce)."""
        zonas = todas_as_zonas(ref)
        if not zonas:
            return None
        n = self.bins
        comp = self.comprimento
        margem = int(round(10.0 / comp * n))
        alvo = next((z for z in zonas if b <= z["apice"] + margem), None)
        volta_seguinte = alvo is None
        if volta_seguinte:
            alvo = zonas[0]
        if volta_seguinte:
            dist_bins = alvo["ini"] + n - b                    # a pista e um anel: cruza a linha de chegada
        elif b <= alvo["ini"]:
            dist_bins = alvo["ini"] - b
        else:
            dist_bins = 0
        dist_m = max(0.0, dist_bins / float(n) * comp)
        dentro = (not volta_seguinte) and alvo["ini"] <= b <= alvo["apice"] + margem
        t = ref["t"]
        tempo_ref = t[alvo["ini"]] - t[b] if not volta_seguinte else t[alvo["ini"]] + ref["tempo"] - t[b]
        tempo_ref = max(0.0, tempo_ref)
        if _finito(vel_kmh) and vel_kmh >= VEL_MIN_CONTAGEM:
            tempo_ate, base = dist_m / (vel_kmh / 3.6), "distancia"
        else:
            tempo_ate, base = tempo_ref, "referencia"
        tempo_ate = max(0.0, tempo_ate)
        if dentro:
            fase, contagem = "freando", "FREANDO"
        elif dist_m > ANTECEDENCIA_M:
            fase, contagem = "livre", None
        else:
            fase = "adiante"
            if tempo_ate <= 0.25:
                contagem = "TIRE" if alvo.get("tipo") == "tirada" else "FREIE"
            elif tempo_ate <= 1.0:
                contagem = "1"
            elif tempo_ate <= 2.0:
                contagem = "2"
            elif tempo_ate <= 3.0:
                contagem = "3"
            else:
                contagem = None
        return {"n": alvo["n"], "dist_m": round(dist_m, 1), "tempo_ate": round(tempo_ate, 2), "tempo_ref": round(tempo_ref, 2),
                "contagem_base": base, "fase": fase,
                "contagem": contagem, "tipo": alvo.get("tipo", "freio"), "marcha": alvo["marcha_apice"], "vel_apice": round(alvo["vel_apice"], 1),
                "vel_entrada": round(alvo["vel_entrada"], 1), "pico": round(alvo["pico"], 2), "total": len(zonas)}

    # ---- feedback pos-curva -----------------------------------------------------------------------------------
    def _avaliar_zonas_passadas(self, ref, b):
        comp = self.comprimento
        n = self.bins
        margem = int(round(BUSCA_APICE_M / comp * n))
        for z in todas_as_zonas(ref):
            if z["n"] in self._feitos:
                continue
            if b > z["apice"] + margem and b - z["apice"] < 0.3 * n:
                self._feitos.add(z["n"])
                fb = self._avaliar(z, comp)
                if fb is not None:
                    self._feedbacks.append(fb)
                    self.ultimo_feedback = fb

    def _inicio_da_freada(self, z, ini_busca, comp):
        """Onde comecou a SUA freada desta curva: o inicio do evento de freio (corrida continua acima de LIM_FREIO, lacunas
        curtas fundidas) que alcanca a zona da referencia. Eventos que terminam antes da zona (cauda da curva anterior)
        sao ignorados; sem isso, curvas proximas davam 'freou muito cedo' falso (visto em dados reais do MX-5)."""
        n = self.bins
        rec = self.rec
        folga = max(1, int(round(FOLGA_M / comp * n)))
        eventos, ini, fim, pico, vazio = [], None, None, 0.0, 0
        for i in range(ini_busca, z["apice"] + 1):
            f = rec.freio[i]
            if f is not None and f >= LIM_FREIO:
                if ini is None:
                    ini, pico = i, 0.0
                fim, vazio = i, 0
                pico = max(pico, f)
            elif ini is not None:
                vazio += 1
                if vazio > folga:
                    eventos.append((ini, fim, pico))
                    ini, fim, pico, vazio = None, None, 0.0, 0
        if ini is not None:
            eventos.append((ini, fim, pico))
        candidatos = [e for e in eventos if e[1] >= z["ini"] and e[2] >= LIM_FREIO * 1.5]
        return candidatos[0][0] if candidatos else None

    def _inicio_da_tirada(self, z, ini_busca, comp):
        """Onde comecou a SUA tirada de pe desta curva (acelerador abaixo de ACEL_PLENA, indo ate ACEL_TIRADA, sem freio).
        Devolve (bin, freou): freou=True se voce freou onde a referencia so tirou o pe."""
        n = self.bins
        rec = self.rec
        fim = min(n - 1, z["apice"] + int(round(BUSCA_APICE_M / comp * n)))
        freou = any((rec.freio[i] or 0.0) >= LIM_FREIO * 3 for i in range(max(0, z["ini"]), fim + 1))
        i = ini_busca
        limite = int(round(TIRADA_ANTES_M / comp * n))
        while i <= fim:
            a = rec.acel[i]
            if a is not None and a < ACEL_TIRADA and (rec.freio[i] or 0.0) < LIM_FREIO:
                k = i                                          # fim desta corrida de acelerador baixo
                while k + 1 <= fim and rec.acel[k + 1] is not None and rec.acel[k + 1] < ACEL_TIRADA:
                    k += 1
                j = i
                while j > 0 and (i - j) < limite and rec.acel[j - 1] is not None and rec.acel[j - 1] < ACEL_PLENA:
                    j -= 1
                veio_de_pe_embaixo = j > 0 and rec.acel[j - 1] is not None and rec.acel[j - 1] >= ACEL_PLENA
                if veio_de_pe_embaixo and k > i:
                    return j, freou
                i = k + 1                                      # corrida que nao veio de pe embaixo (saida de curva): pula
                continue
            i += 1
        return None, freou

    def _avaliar(self, z, comp):
        n = self.bins
        rec = self.rec
        ini_busca = max(0, z["ini"] - int(round(BUSCA_ANTES_M / comp * n)))
        fim_busca = min(n - 1, z["apice"] + int(round(BUSCA_APICE_M / comp * n)))
        tirada = z.get("tipo") == "tirada"
        if tirada:
            primeiro, freou = self._inicio_da_tirada(z, ini_busca, comp)
        else:
            primeiro, freou = self._inicio_da_freada(z, ini_busca, comp), False
        vels = [(rec.vel[i], i) for i in range(z["ini"], fim_busca + 1) if rec.vel[i] is not None]
        if not vels:
            return None
        v_min, i_min = min(vels)
        dif_vel = v_min - z["vel_apice"]
        marcha_viva = rec.marcha[i_min]
        dif_marcha = None if marcha_viva is None else marcha_viva - z["marcha_apice"]
        if primeiro is None:
            nota, dif_m = ("freou_em_vez" if (tirada and freou) else "sem_tirada" if tirada else "sem_freada"), None
        else:
            dif_m = (z["ini"] - primeiro) / float(n) * comp          # positivo = freou ANTES (cedo)
            nota = nota_da_freada(dif_m)
        gravidade = 0.0
        if dif_m is not None:
            gravidade += abs(dif_m)
        else:
            gravidade += 30.0 if tirada else 100.0          # sem tirada pode ser ate mais rapido: pesa pouco
        gravidade += max(0.0, -dif_vel) * 2.0
        return {"n": z["n"], "freada_m": None if dif_m is None else round(dif_m, 1), "nota": nota,
                "vel_apice": round(v_min, 1), "dif_vel": round(dif_vel, 1), "marcha": marcha_viva,
                "marcha_ref": z["marcha_apice"], "dif_marcha": dif_marcha, "gravidade": round(gravidade, 1),
                "tipo": "tirada" if tirada else "freio",
                "texto": texto_feedback(z["n"], nota, dif_m, dif_vel, dif_marcha, "tirada" if tirada else "freio")}

    # ---- saida ------------------------------------------------------------------------------------------------
    def resumo(self, guia=None, delta=None):
        ref = self.referencia_ativa()
        if ref is None:
            estado = "gravando" if self.pista else "sem_contexto"
        else:
            estado = "ok"
        aviso = None
        if ref is not None and ref.get("origem") == "importada":
            if compativel(ref, self.pista, self.carro, self.comprimento) == "outro_carro":
                aviso = "referencia de outro carro"
        return {"estado": estado, "fonte": self.fonte_ativa(), "pista": self.pista, "carro": self.carro,
                "tempo_ref": None if ref is None else ref["tempo"], "proxima": guia, "delta": delta,
                "feedback": self.ultimo_feedback, "resumo_volta": self.resumo_volta,
                "voltas_gravadas": self.voltas_gravadas, "aviso": aviso, "modo": self.modo,
                "tem_propria": self.ref_propria is not None, "tem_importada": self.ref_importada is not None}


def nota_da_freada(dif_m):
    """dif_m: metros (positivo = freou antes do ponto da referencia)."""
    a = abs(dif_m)
    if a <= LIM_PERFEITA_M:
        return "perfeita"
    if a <= LIM_BOA_M:
        return "boa"
    sufixo = "cedo" if dif_m > 0 else "tarde"
    return ("muito_" + sufixo) if a > LIM_MUITO_M else sufixo


_ROTULOS_TIRADA = {"perfeita": "tirada perfeita", "boa": "boa tirada", "cedo": "tirou o pe cedo", "tarde": "tirou o pe tarde",
                   "muito_cedo": "tirou o pe muito cedo", "muito_tarde": "tirou o pe muito tarde",
                   "sem_tirada": "nao tirou o pe", "freou_em_vez": "freou onde bastava tirar o pe"}
_ROTULOS = {"perfeita": "freada perfeita", "boa": "boa freada", "cedo": "freou cedo", "tarde": "freou tarde",
            "muito_cedo": "freou muito cedo", "muito_tarde": "freou muito tarde", "sem_freada": "sem freada"}


def texto_feedback(n, nota, dif_m, dif_vel, dif_marcha, tipo="freio"):
    rotulos = _ROTULOS_TIRADA if tipo == "tirada" else _ROTULOS
    partes = [f"C{n}: {rotulos.get(nota, nota)}"]
    if dif_m is not None and nota not in ("perfeita", "boa"):
        partes[0] += f" (~{abs(dif_m):.0f} m)"
    if abs(dif_vel) >= 2.0:
        partes.append(f"apice {dif_vel:+.0f} km/h")
    if dif_marcha:
        partes.append(f"marcha {dif_marcha:+d}")
    return " | ".join(partes)
