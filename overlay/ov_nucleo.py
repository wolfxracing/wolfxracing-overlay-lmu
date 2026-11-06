# -*- coding: utf-8 -*-
"""
Overlay iRacing - NUCLEO (Fase 20)

Modulo SEM Qt e SEM iRacing/SDK: so Python puro. Aqui ficam as regras novas e criticas, que podem ser
testadas sozinhas (sem abrir o jogo nem janelas):

  - Registro            : log com niveis, rotacao de tamanho e limite de frequencia
  - motivo_volta_suja   : criterio unico para uma volta NAO servir de referencia/recorde
  - Limitador           : "rode isto no maximo a cada X segundos"
  - Desempenho          : mede o custo do ciclo e das janelas (para proteger o frametime do jogo)
  - GerenciadorPerfis   : layouts Treino / Classificacao / Corrida (posicao, tamanho, visibilidade)
  - SeletorPerfil       : escolhe o perfil pela sessao, com atraso para nao oscilar
  - comparar_oficial    : compara a projecao de iRating/SR com o resultado oficial
  - PROVENIENCIA        : o que e REAL (SDK), CALCULADO ou ESTIMADO em cada dado mostrado
  - ATALHOS / EscutaTeclas / DespachanteTeclas (Fase 20.2.2): teclas globais para o Stream Deck

Este arquivo precisa estar na mesma pasta do overlay_iracing.py.
"""

import os
import queue
import threading
import time
from collections import deque
from pathlib import Path

VERSAO_NUCLEO = "20.2.2"

# --------------------------------------------------------------------------
# Proveniencia dos dados: o que e medido pelo iRacing e o que o overlay calcula/estima
# --------------------------------------------------------------------------
REAL, CALCULADO, ESTIMADO = "real", "calculado", "estimado"

PROVENIENCIA = {
    # dado mostrado               : (tipo,      origem / observacao)
    "marcha, rpm, pedais, volante": (REAL, "SDK: Gear, RPM, Throttle, Brake, SteeringWheelAngle"),
    "velocidade":                  (REAL, "SDK: Speed"),
    "forca G":                     (REAL, "SDK: LatAccel/LongAccel (60 Hz); o pico pode perder pancadas curtas"),
    "combustivel no tanque":       (REAL, "SDK: FuelLevel"),
    "consumo por volta":           (CALCULADO, "media das voltas limpas medidas pelo overlay"),
    "voltas/litros ate o fim":     (CALCULADO, "consumo medio x voltas restantes informadas pelo SDK"),
    "delta (SDK)":                 (REAL, "SDK: LapDeltaToBestLap, quando o jogo marca como valido"),
    "delta (calculado)":           (CALCULADO, "tempo da volta atual - tempo da melhor volta LIMPA da sessao no mesmo ponto"),
    "setores (tempo)":             (CALCULADO, "cruzamento dos limites do SDK, com interpolacao"),
    "setores (limites)":           (REAL, "SDK: SplitTimeInfo; se ausente, 3 setores iguais (ESTIMADO)"),
    "radar: carro ao lado":        (REAL, "SDK: CarLeftRight (confirmado)"),
    "radar: lado lembrado":        (ESTIMADO, "memoria de ate 3 s do ultimo lado confirmado"),
    "radar: lado desconhecido":    (ESTIMADO, "o SDK nao informa a posicao lateral dos outros carros"),
    "radar: distancia (m)":        (CALCULADO, "diferenca de posicao na pista x comprimento da pista (centro a centro)"),
    "radar: aproximacao (km/h)":   (CALCULADO, "variacao da distancia, filtrada"),
    "relativo: diferenca de tempo": (CALCULADO, "distancia na pista / volta de referencia"),
    "pneus: temperatura real":     (REAL, "SDK; o jogo so atualiza nos boxes (mostra o horario da ultima leitura)"),
    "pneus: vida real":            (REAL, "SDK; so atualiza nos boxes (mostra o horario da ultima leitura)"),
    "pneus: temperatura/vida ao vivo": (ESTIMADO, "modelo do overlay calibrado nos boxes; sempre com '~'"),
    "voltas do pneu":              (CALCULADO, "voltas desde a ultima parada no box (aproximado se a sessao comecou antes)"),
    "iRating projetado":           (ESTIMADO, "modelo aproximado; o oficial so sai depois da corrida"),
    "Safety Rating projetado":     (ESTIMADO, "modelo aproximado; o oficial so sai depois da sessao"),
    "clima: temperaturas, vento":  (REAL, "SDK: TrackTemp, AirTemp, WindDir, WindVel, FogLevel"),
    "clima: tendencia de chuva":   (CALCULADO, "variacao da chuva atual; o SDK nao entrega previsao"),
    "danos: reparo, avisos":       (REAL, "SDK: PitRepairLeft, EngineWarnings, incidentes"),
    "danos: lado e forca do impacto": (ESTIMADO, "inferido pela aceleracao no instante da batida"),
}


def tipo_do_dado(nome):
    return PROVENIENCIA[nome][0]


# --------------------------------------------------------------------------
# Registro (log)
# --------------------------------------------------------------------------
class Registro:
    """Escreve em overlay_log.txt sem nunca derrubar o overlay.

    - `caminho` e uma FUNCAO que devolve o Path (assim o arquivo pode ser trocado em testes);
    - erro/aviso: gravados uma unica vez por texto (como nas fases anteriores);
    - calculo/evento: com limite de frequencia por nome, para nao encher o disco;
    - rotacao: ao passar de `limite_bytes`, o log vira overlay_log.txt.1 (so um backup).
    """

    def __init__(self, caminho, limite_bytes=1_000_000, relogio=time.time):
        self._caminho = caminho
        self.limite_bytes = limite_bytes
        self._relogio = relogio
        self._vistos = set()
        self._ultimo = {}

    def _escrever(self, linha):
        try:
            caminho = Path(self._caminho())
            try:
                if caminho.exists() and caminho.stat().st_size > self.limite_bytes:
                    os.replace(caminho, str(caminho) + ".1")
            except OSError:
                pass
            with caminho.open("a", encoding="utf-8") as arq:
                arq.write(linha if linha.endswith("\n") else linha + "\n")
            return True
        except Exception:
            return False

    def _carimbo(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._relogio()))

    def erro(self, contexto, texto_traceback):
        try:
            linhas = texto_traceback.strip().splitlines()
            chave = (contexto, linhas[-1] if linhas else "")
            if chave in self._vistos:
                return False
            self._vistos.add(chave)
            return self._escrever(f"[{self._carimbo()}] erro em {contexto}\n{texto_traceback}\n")
        except Exception:
            return False

    def aviso(self, texto):
        chave = ("aviso", texto)
        if chave in self._vistos:
            return False
        self._vistos.add(chave)
        return self._escrever(f"[{self._carimbo()}] aviso: {texto}")

    def info(self, texto):
        return self._escrever(f"[{self._carimbo()}] info: {texto}")

    def calculo(self, nome, intervalo=0.0, /, **valores):
        """Resultado de um calculo. `intervalo` (s) = no maximo uma linha por `nome` nesse tempo."""
        agora = self._relogio()
        if intervalo and agora - self._ultimo.get(nome, -1e18) < intervalo:
            return False
        self._ultimo[nome] = agora
        corpo = " ".join(f"{k}={_fmt(v)}" for k, v in valores.items())
        return self._escrever(f"[{self._carimbo()}] calculo {nome}: {corpo}")

    def cabecalho(self, versoes):
        corpo = " | ".join(f"{k} {v}" for k, v in versoes.items())
        return self._escrever(f"[{self._carimbo()}] inicio: {corpo}")


def _fmt(valor):
    if isinstance(valor, float):
        return f"{valor:.3f}"
    return str(valor).replace("\n", " ")


def variaveis_ausentes(existe, nomes):
    """Lista os nomes de variaveis do SDK que `existe(nome)` nao encontra (relatorio de disponibilidade)."""
    ausentes = []
    for nome in nomes:
        try:
            if not existe(nome):
                ausentes.append(nome)
        except Exception:
            ausentes.append(nome)
    return ausentes


# --------------------------------------------------------------------------
# Volta valida para referencia / recorde
# --------------------------------------------------------------------------
# Superficie da pista no iRacing (irsdk_TrkLoc): -1 fora do mundo, 0 fora da pista, 1 box (vaga),
# 2 entrando nos boxes, 3 na pista.
def motivo_volta_suja(na_box=False, superficie=None, reboque_s=0.0, replay=False):
    """Devolve o MOTIVO pelo qual a volta nao deve virar referencia/recorde, ou None se esta limpa.

    O iRacing NAO informa se uma volta foi invalidada; este criterio e do overlay e e CONSERVADOR:
    prefere descartar uma volta boa a aceitar uma volta suja.
    """
    if replay:
        return "replay"
    if na_box:
        return "boxes"
    if superficie is not None:
        try:
            s = int(superficie)
        except (TypeError, ValueError):
            s = None
        if s == 0:
            return "fora da pista"
        if s in (1, 2):
            return "boxes"
        if s == -1:
            return "fora do mundo"
    try:
        if reboque_s and float(reboque_s) > 0:
            return "reboque"
    except (TypeError, ValueError):
        pass
    return None


# --------------------------------------------------------------------------
# Limitador e desempenho
# --------------------------------------------------------------------------
class Limitador:
    """deve(chave, intervalo, agora): True no maximo uma vez por `intervalo` segundos para cada chave."""

    def __init__(self):
        self._ultimo = {}

    def deve(self, chave, intervalo, agora):
        anterior = self._ultimo.get(chave)
        if anterior is None or agora - anterior >= intervalo or agora < anterior:
            self._ultimo[chave] = agora
            return True
        return False

    def esquecer(self, chave=None):
        if chave is None:
            self._ultimo.clear()
        else:
            self._ultimo.pop(chave, None)


class Desempenho:
    """Mede o custo (em ms) da leitura/calculo e do desenho de cada janela.

    O overlay roda no mesmo PC do jogo: se ele gastar CPU demais, o iRacing perde frames.
    """

    def __init__(self, amostras=600, orcamento_ms=8.0):
        self.amostras = amostras
        self.orcamento_ms = orcamento_ms          # custo medio por ciclo (leitura + calculo) aceitavel
        self._series = {}
        self._limite_aviso = Limitador()

    def medir(self, nome, ms):
        fila = self._series.get(nome)
        if fila is None:
            fila = self._series[nome] = deque(maxlen=self.amostras)
        fila.append(float(ms))

    def estatistica(self, nome):
        fila = self._series.get(nome)
        if not fila:
            return None
        ordem = sorted(fila)
        return {"n": len(ordem), "media": sum(ordem) / len(ordem),
                "p95": ordem[min(len(ordem) - 1, int(len(ordem) * 0.95))], "max": ordem[-1]}

    def resumo(self):
        return {nome: self.estatistica(nome) for nome in sorted(self._series)}

    def custo_por_segundo(self, taxas):
        """ms de CPU por segundo gasto desenhando: soma(media da janela x repinturas por segundo)."""
        total = 0.0
        for nome, hz in taxas.items():
            est = self.estatistica("pintura:" + nome)
            if est:
                total += est["media"] * hz
        return total

    def alerta(self, agora, intervalo_aviso=300.0):
        """Texto de aviso se o ciclo medio passou do orcamento (no maximo 1 aviso a cada 5 min)."""
        fila = self._series.get("ciclo")
        if not fila or len(fila) < 60 or sum(fila) / len(fila) <= self.orcamento_ms:
            return None                     # caminho comum: sem ordenar as amostras
        est = self.estatistica("ciclo")
        if est and est["n"] >= 60 and est["media"] > self.orcamento_ms:
            if self._limite_aviso.deve("ciclo", intervalo_aviso, agora):
                return (f"ciclo de leitura/calculo lento: media {est['media']:.1f} ms, p95 {est['p95']:.1f} ms, "
                        f"max {est['max']:.1f} ms (orcamento {self.orcamento_ms:.0f} ms)")
        return None


# --------------------------------------------------------------------------
# Perfis de exibicao
# --------------------------------------------------------------------------
PERFIS = ("Treino", "Classificacao", "Corrida")
_PREFIXOS_LAYOUT = ("x_", "y_", "escala", "mostrar_")
_EXTRAS_LAYOUT = ("x", "y", "classificacao_todas")
_SESSAO_PARA_PERFIL = {"CORRIDA": "Corrida", "QUALIFICACAO": "Classificacao",
                       "TREINO": "Treino", "TESTE": "Treino", "AQUECIMENTO": "Treino"}


def chaves_de_layout(config):
    """Chaves do config que pertencem ao layout de uma janela (posicao, tamanho, visibilidade)."""
    return [k for k in config
            if k in _EXTRAS_LAYOUT or (isinstance(k, str) and k.startswith(_PREFIXOS_LAYOUT))]


def perfil_da_sessao(tipo):
    """TIPO de sessao (traduzido: CORRIDA, QUALIFICACAO, TREINO...) -> nome do perfil, ou None."""
    return _SESSAO_PARA_PERFIL.get(str(tipo or "").upper())


class GerenciadorPerfis:
    """Guarda, por perfil, a posicao, o tamanho e a visibilidade de CADA janela.

    O config continua "plano" como nas versoes anteriores (o layout em uso fica nas mesmas chaves de
    sempre). Os perfis ficam em config["perfis"]; trocar de perfil salva o layout atual no perfil que
    sai e carrega o do perfil que entra.
    """

    def __init__(self, nomes=PERFIS):
        self.nomes = tuple(nomes)

    def inicializar(self, config):
        """Garante os 3 perfis. Na primeira vez, TODOS copiam o layout atual (nada muda de lugar)."""
        atual = {k: config[k] for k in chaves_de_layout(config)}
        perfis = config.get("perfis")
        if not isinstance(perfis, dict):
            perfis = {}
        for nome in self.nomes:
            p = perfis.get(nome)
            p = dict(p) if isinstance(p, dict) else {}
            for k, v in atual.items():
                p.setdefault(k, v)             # chave nova (janela nova): comeca igual ao layout atual
            perfis[nome] = p
        config["perfis"] = perfis
        modo = config.get("perfil_modo")
        config["perfil_modo"] = modo if modo == "auto" or modo in self.nomes else "auto"
        ativo = config.get("perfil_ativo")
        config["perfil_ativo"] = ativo if ativo in self.nomes else self.nomes[-1]
        return config

    def capturar(self, config):
        """Copia o layout em uso para o perfil ativo (chamar antes de salvar o config)."""
        ativo = config.get("perfil_ativo")
        if ativo in self.nomes and isinstance(config.get("perfis"), dict):
            config["perfis"].setdefault(ativo, {}).update({k: config[k] for k in chaves_de_layout(config)})

    def trocar(self, config, novo):
        """Salva o layout atual no perfil ativo e carrega o de `novo`. Devolve True se trocou."""
        if novo not in self.nomes or novo == config.get("perfil_ativo"):
            return False
        self.capturar(config)
        config.update(config["perfis"][novo])
        config["perfil_ativo"] = novo
        return True

    def escolher(self, config, tipo_sessao):
        """Perfil que deveria estar ativo agora (manual ou automatico); None = sem decisao."""
        modo = config.get("perfil_modo", "auto")
        if modo in self.nomes:
            return modo
        return perfil_da_sessao(tipo_sessao)


class SeletorPerfil:
    """Atraso (debounce) da troca automatica: so troca se o tipo de sessao ficou estavel."""

    def __init__(self, gerenciador, estabilidade_s=3.0):
        self.g = gerenciador
        self.estabilidade_s = estabilidade_s
        self._candidato = None
        self._desde = None

    def decidir(self, config, tipo_sessao, agora, editando=False):
        """Devolve o nome do perfil a ativar agora, ou None (nada a fazer)."""
        if editando:                                  # janelas destravadas = voce esta posicionando
            self._candidato = self._desde = None
            return None
        alvo = self.g.escolher(config, tipo_sessao)
        if alvo is None or alvo == config.get("perfil_ativo"):
            self._candidato = self._desde = None
            return None
        if alvo != self._candidato:
            self._candidato, self._desde = alvo, agora
            return None
        if agora - self._desde >= self.estabilidade_s:
            self._candidato = self._desde = None
            return alvo
        return None


# --------------------------------------------------------------------------
# Projecao x resultado oficial
# --------------------------------------------------------------------------
# Fase 20.1: a comparacao so e feita quando a projecao pode ser ASSOCIADA com seguranca ao resultado:
#   - a projecao guarda a IDENTIDADE da corrida (SubSessionID do iRacing, categoria, usuario);
#   - o iRating/SR "de agora" so valem para a mesma categoria e o mesmo usuario;
#   - a corrida nao pode ser a mesma sessao ainda em andamento;
#   - se a base de uma corrida nasceu antes de o resultado da anterior ser publicado, ela e descartada.
MOTIVOS_DESCARTE = ("pendente_sem_id", "base_incerta")      # nunca poderao ser associadas: a projecao expira
MOTIVOS_TEXTO = {
    "ok": "comparada (PROVISORIA: sem confirmacao do resultado oficial pelo SubSessionID)",
    "ok_confirmada": "comparada e CONFIRMADA pelo resultado oficial da corrida (SubSessionID)",
    "resultado_divergente": "resultado oficial recebido e de outra corrida/usuario: ignorado",
    "resultado_incompleto": "resultado oficial da corrida sem os valores de iRating/SR necessarios: nao confirma",
    "sem_pendente": "nao ha projecao pendente",
    "pendente_sem_id": "projecao sem identificacao da corrida (formato da Fase 20): descartada sem comparar",
    "base_incerta": "base de iRating/SR anterior ao resultado da corrida anterior: descartada sem comparar",
    "mesma_sessao": "ainda na mesma corrida: aguardando",
    "categoria_diferente": "sessao atual e de outra categoria: iRating/SR nao comparaveis, aguardando",
    "categoria_desconhecida": "categoria nao informada pelo SDK: nao e possivel associar com seguranca",
    "usuario_diferente": "outro usuario do iRacing nesta sessao: aguardando",
    "sem_atualizacao_numerica": "valores no jogo iguais aos do inicio da corrida: SEM atualizacao numerica (nao e "
                                "resultado oficial; so o resultado da corrida confirma variacao zero)",
    "ja_provisoria": "ja comparada de forma provisoria: aguardando confirmacao pelo resultado oficial",
    "ja_confirmada": "ja confirmada pelo resultado oficial: nada a fazer",
    "ja_expirada": "projecao expirada: nada a fazer",
    "expirada": "projecao expirada (prazo ou base invalida)",
}


def identidade_sessao(sub_session_id=None, categoria=None, usuario_id=None, oficial=None):
    """Identidade da corrida atual para associar a projecao ao resultado oficial.

    Devolve {"id": "<SubSessionID>" ou None, "categoria", "usuario", "oficial", "forte": bool}.
    So e `forte` (apta a ser associada) com SubSessionID > 0 (corrida online registrada pelo iRacing),
    categoria e usuario conhecidos e corrida OFICIAL. Testes offline tem SubSessionID 0 e nao geram resultado.
    """
    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    sub = _int(sub_session_id)
    cat = str(categoria).strip().lower() if categoria not in (None, "") else None
    usr = _int(usuario_id)
    ident = {"id": str(sub) if sub and sub > 0 else None, "categoria": cat,
             "usuario": usr if usr and usr > 0 else None,
             "oficial": None if oficial is None else bool(oficial)}
    ident["forte"] = bool(ident["id"] and ident["categoria"] and ident["usuario"] and ident["oficial"])
    return ident


STATUS_PROVISORIA, STATUS_CONFIRMADA = "provisoria", "confirmada"


def resultado_confere(pendente, resultado_oficial):
    """True se `resultado_oficial` e o resultado DA corrida projetada e DO mesmo usuario.

    Contrato (ainda NAO ligado a nenhuma fonte; reservado para a Data API do iRacing):
      resultado_oficial = {"subsession_id", "cust_id", "ir_antigo", "ir_novo", "sr_antigo", "sr_novo"}
    """
    if not pendente or not resultado_oficial:
        return False
    try:
        return (str(resultado_oficial.get("subsession_id")) == str(pendente.get("id"))
                and int(resultado_oficial.get("cust_id")) == int(pendente.get("usuario")))
    except (TypeError, ValueError):
        return False


def comparar_resultado_oficial(pendente, resultado_oficial):
    """Compara a projecao com o resultado OFICIAL JA associado a ela (use resultado_confere antes).

    Os valores reais vem do resultado (`ir_novo - ir_antigo`), nunca do jogo. Variacao ZERO e um resultado valido:
    diferencia "o resultado oficial diz que nao mudou" de "ainda nao ha atualizacao". Devolve None so se o
    resultado nao traz valores comparaveis (faltam antigo/novo, ou a projecao nao tinha previsao para a metrica).
    `variacao_nula` = True quando todas as variacoes reais comparadas sao zero.
    """
    ro = resultado_oficial or {}
    base = {"ir_base": ro.get("ir_antigo"), "ir_delta_proj": pendente.get("ir_delta_proj"),
            "sr_base": ro.get("sr_antigo"), "sr_delta_proj": pendente.get("sr_delta_proj")}
    res = comparar_oficial(base, ro.get("ir_novo"), ro.get("sr_novo"), aceitar_zero=True)
    if not res:
        return None
    res["status"] = STATUS_CONFIRMADA
    res["variacao_nula"] = all(res.get(k) == 0 for k in ("ir_real", "sr_real") if k in res)
    return res


def avaliar_comparacao(pendente, atual, ir_atual, sr_atual, resultado_oficial=None):
    """Decide se a projecao `pendente` pode ser comparada com o iRating/SR visto agora.

    pendente: dict gravado no fim da corrida ({"id","categoria","usuario","ir_base","ir_delta_proj",
              "sr_base","sr_delta_proj", ...}); atual: identidade_sessao() da sessao de agora.
    Devolve (resultado, motivo). `resultado` so existe com motivo "ok"/"ok_confirmada"; `motivo` esta em
    MOTIVOS_TEXTO. `resultado["status"]` e SEMPRE "provisoria" quando vem da diferenca entre os valores vistos no
    jogo (nada garante que so a corrida projetada alterou o rating); valores iguais aos do inicio dao
    "sem_atualizacao_numerica" (ausencia de atualizacao, NAO resultado oficial). So e "confirmada" quando
    `resultado_oficial` traz o resultado da MESMA corrida (SubSessionID) e usuario (Fase 20.2.1: inclusive com
    variacao zero).
    """
    if resultado_oficial is not None:
        if not resultado_confere(pendente, resultado_oficial):
            if pendente:
                return None, "resultado_divergente"
        else:
            res = comparar_resultado_oficial(pendente, resultado_oficial)
            return (res, "ok_confirmada") if res else (None, "resultado_incompleto")
    if not pendente:
        return None, "sem_pendente"
    if not pendente.get("id") or not pendente.get("categoria") or not pendente.get("usuario"):
        return None, "pendente_sem_id"
    if pendente.get("base_incerta"):
        return None, "base_incerta"
    atual = atual or {}
    if atual.get("id") and str(atual["id"]) == str(pendente["id"]):
        return None, "mesma_sessao"
    if not atual.get("categoria"):
        return None, "categoria_desconhecida"
    if atual["categoria"] != pendente["categoria"]:
        return None, "categoria_diferente"
    if not atual.get("usuario") or atual["usuario"] != pendente["usuario"]:
        return None, "usuario_diferente"
    res = comparar_oficial(pendente, ir_atual, sr_atual)
    if not res:
        return None, "sem_atualizacao_numerica"
    res["status"] = STATUS_PROVISORIA
    return res, "ok"


def comparar_oficial(pendente, ir_atual, sr_atual, aceitar_zero=False):
    """Parte numerica: compara a projecao guardada com os valores vistos depois.

    pendente: {"ir_base", "ir_delta_proj", "sr_base", "sr_delta_proj"}  (base = valor no inicio da corrida)
    Sem `aceitar_zero`, devolve None se os valores sao iguais aos do inicio (sem atualizacao numerica). Com
    `aceitar_zero` (so para resultado oficial ja associado), variacao zero entra como 0.
    NAO verifica a associacao com a corrida: use avaliar_comparacao().
    """
    if not pendente:
        return None
    res = {}
    ir_base, ir_proj = pendente.get("ir_base"), pendente.get("ir_delta_proj")
    if ir_base and ir_atual and (aceitar_zero or int(ir_atual) != int(ir_base)) and ir_proj is not None:
        real = int(ir_atual) - int(ir_base)
        res["ir_real"], res["ir_proj"], res["ir_erro"] = real, int(ir_proj), int(ir_proj) - real
    sr_base, sr_proj = pendente.get("sr_base"), pendente.get("sr_delta_proj")
    if sr_base is not None and sr_atual is not None and sr_proj is not None \
            and (aceitar_zero or abs(float(sr_atual) - float(sr_base)) >= 0.005):
        real = round(float(sr_atual) - float(sr_base), 2)
        res["sr_real"], res["sr_proj"], res["sr_erro"] = real, round(float(sr_proj), 2), round(float(sr_proj) - real, 2)
    return res or None


# --------------------------------------------------------------------------
# Ciclo de vida da projecao (Fase 20.2.1): pendente -> provisoria -> confirmada | expirada
# --------------------------------------------------------------------------
# pendente   : corrida terminou; ainda nao houve leitura numerica nova no jogo
# provisoria : o jogo mostrou rating diferente do inicio; comparacao registrada UMA vez (CSV status "provisoria"),
#              mas os dados originais da projecao sao MANTIDOS para uma confirmacao posterior
# confirmada : resultado oficial da MESMA corrida (SubSessionID + usuario) recebido; substitui a linha provisoria
# expirada   : prazo vencido, base invalida ou sobreposta por outra corrida; nunca mais e comparada
PENDENTE, PROVISORIA, CONFIRMADA, EXPIRADA = "pendente", "provisoria", "confirmada", "expirada"
ESTADOS = (PENDENTE, PROVISORIA, CONFIRMADA, EXPIRADA)
DIA_S = 86400.0
PRAZO_PENDENTE_S = 14 * DIA_S       # sem nenhuma leitura numerica: expira
PRAZO_PROVISORIA_S = 60 * DIA_S     # janela para a confirmacao pelo resultado oficial
RETENCAO_TERMINAL_S = 60 * DIA_S    # confirmadas/expiradas ficam registradas (evita duplicar) e depois saem
MAX_REGISTROS = 50


def novo_registro(ident, pista, ir_base, ir_delta_proj, sr_base, sr_delta_proj, base_incerta, agora):
    """Registro de uma projecao no fim de uma corrida (identidade FORTE obrigatoria: ver identidade_sessao)."""
    return {"versao": 3, "id": ident["id"], "categoria": ident["categoria"], "usuario": ident["usuario"],
            "pista": pista, "quando": agora, "ir_base": ir_base, "ir_delta_proj": ir_delta_proj,
            "sr_base": sr_base, "sr_delta_proj": sr_delta_proj, "base_incerta": bool(base_incerta),
            "estado": PENDENTE, "estado_desde": agora, "observacoes_sem_variacao": 0,
            "provisoria": None, "confirmada": None, "motivo_expirada": None}


def _expirar(reg, motivo, agora):
    reg["estado"], reg["estado_desde"], reg["motivo_expirada"] = EXPIRADA, agora, motivo
    return reg


def avaliar_registro(reg, atual, ir_atual, sr_atual, agora):
    """Passo de ciclo de vida no inicio de uma sessao. Devolve (registro_novo, evento, resultado, motivo).

    evento: "provisoria" (comparacao a registrar), "expirada" ou None. Nao ha efeitos fora do retorno.
    Uma projecao ja provisoria NAO e comparada de novo (sem duplicar linhas): so expira ou espera o resultado.
    """
    r = dict(reg)
    est = r.get("estado", PENDENTE)
    if est == CONFIRMADA:
        return r, None, None, "ja_confirmada"
    if est == EXPIRADA:
        return r, None, None, "ja_expirada"
    idade = agora - float(r.get("quando", 0))
    if est == PROVISORIA:
        if idade > PRAZO_PROVISORIA_S:
            return _expirar(r, "prazo", agora), "expirada", None, "expirada"
        return r, None, None, "ja_provisoria"
    if idade > PRAZO_PENDENTE_S:
        return _expirar(r, "prazo", agora), "expirada", None, "expirada"
    res, motivo = avaliar_comparacao(r, atual, ir_atual, sr_atual)
    if motivo == "ok":
        r["estado"], r["estado_desde"] = PROVISORIA, agora
        r["provisoria"] = dict(res, quando=agora)
        return r, "provisoria", res, motivo
    if motivo in MOTIVOS_DESCARTE:
        return _expirar(r, motivo, agora), "expirada", None, motivo
    if motivo == "sem_atualizacao_numerica":
        r["observacoes_sem_variacao"] = int(r.get("observacoes_sem_variacao", 0)) + 1
    return r, None, None, motivo


def aplicar_resultado_oficial(reg, resultado_oficial, agora):
    """Confirma a projecao com o resultado oficial. Devolve (registro_novo, evento, resultado, motivo).

    evento "confirmada" so quando SubSessionID e usuario conferem. Vale a partir de pendente OU provisoria (a
    provisoria, se houver, fica guardada em `confirmada["provisoria_anterior"]` para medir a divergencia).
    Idempotente: confirmar de novo nao muda nada. Projecao expirada nao e reaberta.
    """
    r = dict(reg)
    est = r.get("estado", PENDENTE)
    if est == CONFIRMADA:
        return r, None, None, "ja_confirmada"
    if est == EXPIRADA:
        return r, None, None, "ja_expirada"
    if not resultado_confere(r, resultado_oficial):
        return r, None, None, "resultado_divergente"
    res = comparar_resultado_oficial(r, resultado_oficial)
    if not res:
        return r, None, None, "resultado_incompleto"
    anterior = r.get("provisoria")
    if anterior:
        res["provisoria_anterior"] = {k: anterior[k] for k in ("ir_real", "sr_real") if k in anterior}
        res["divergencia_provisoria"] = {
            k: round(res[k] - anterior[k], 2) for k in ("ir_real", "sr_real") if k in res and k in anterior}
    r["estado"], r["estado_desde"], r["confirmada"] = CONFIRMADA, agora, dict(res, quando=agora)
    return r, "confirmada", res, "ok_confirmada"


def sobrepor_pendentes(registros, novo, agora):
    """Antes de registrar `novo`: projecoes ainda PENDENTES da mesma categoria/usuario ficam invalidas (o proximo
    resultado numerico misturaria as duas corridas). Provisorias/confirmadas nao sao afetadas."""
    saida = []
    for r in registros:
        if (r.get("estado") == PENDENTE and r.get("id") != novo["id"]
                and r.get("categoria") == novo["categoria"] and r.get("usuario") == novo["usuario"]):
            r = _expirar(dict(r), "sobreposta_por_outra_corrida", agora)
        saida.append(r)
    return saida


def ativos(registros):
    """Projecoes ainda em andamento (pendentes e provisorias): nunca sao removidas automaticamente."""
    return [r for r in registros if r.get("estado") in (PENDENTE, PROVISORIA)]


def podar(registros, agora):
    """Retencao automatica. SO confirmadas/expiradas podem ser removidas; pendentes e provisorias nunca.

    1) terminais com mais de RETENCAO_TERMINAL_S saem; 2) acima de MAX_REGISTROS saem os terminais mais antigos.
    Se o limite for excedido apenas por projecoes ativas, TODAS sao mantidas (sem perda de dados): quem grava deve
    avisar com `excede_capacidade()`. Registros de estado desconhecido sao tratados como ativos (nao se apaga o
    que nao se entende).
    """
    def terminal(r):
        return r.get("estado") in (CONFIRMADA, EXPIRADA)
    manter = [r for r in registros
              if not (terminal(r) and agora - float(r.get("estado_desde", agora)) > RETENCAO_TERMINAL_S)]
    while len(manter) > MAX_REGISTROS:
        terminais = [r for r in manter if terminal(r)]
        if not terminais:
            break
        manter.remove(min(terminais, key=lambda r: float(r.get("estado_desde", r.get("quando", 0)))))
    return manter


def excede_capacidade(registros):
    """True se a lista (ja podada) passa de MAX_REGISTROS: so acontece com projecoes ativas em excesso."""
    return len(registros) > MAX_REGISTROS


def migrar_arquivo(conteudo, agora):
    """Converte o conteudo lido de projecao_pendente.json para a lista de registros. Devolve (lista, avisos).

    Formatos: v3 {"versao":3,"projecoes":[...]}; v2 (Fase 20.1/20.2) = um unico dict com "id" (vira PENDENTE);
    Fase 20 (sem "id") nao tem como ser associada e e descartada com aviso.
    """
    if isinstance(conteudo, dict) and isinstance(conteudo.get("projecoes"), list):
        return [r for r in conteudo["projecoes"] if isinstance(r, dict) and r.get("id")], []
    if isinstance(conteudo, dict) and conteudo.get("id") and conteudo.get("categoria") and conteudo.get("usuario"):
        reg = dict(conteudo)
        quando = float(reg.get("quando", agora))
        reg.update({"versao": 3, "quando": quando, "estado": PENDENTE, "estado_desde": quando,
                    "observacoes_sem_variacao": 0, "provisoria": None, "confirmada": None, "motivo_expirada": None,
                    "base_incerta": bool(reg.get("base_incerta"))})
        return [reg], ["projecao pendente de formato anterior migrada para o ciclo de vida (estado pendente)."]
    if conteudo:
        return [], ["projecao pendente sem identificacao da corrida (Fase 20): descartada sem comparar."]
    return [], []


# --------------------------------------------------------------------------
# Pneus: o que e REAL e o que e ESTIMADO na tela (Fase 20.1: regra unica e testavel)
# --------------------------------------------------------------------------
def origem_pneu(temp_real, ultima, temp_estimada, info_vida=None):
    """Decide a origem de cada dado do cartao de um pneu. Nunca mistura real com estimado:

    temp_real     : (3 zonas) lidas AGORA do SDK, ou None
    ultima        : {"temp": (3 zonas), ...} ultima leitura real conhecida (quando o jogo parou de atualizar)
    temp_estimada : temperatura estimada pelo overlay (ou None)
    info_vida     : {"vida": 0..1 ou None, "tipo": "real" | "est"}
    Devolve:
      temp_cabecalho : "real" (sem "~") | "estimada" (com "~") | None
      temp_corpo     : "real_ao_vivo" | "real_antiga" (esmaecida, com idade) | "estimada" (com "~") | "nenhuma"
      vida           : "real" | "estimada" (rotulo "VIDA~") | "nenhuma"
    """
    antiga = ultima.get("temp") if (not temp_real and ultima) else None
    if temp_real:
        corpo, cab = "real_ao_vivo", "real"
    elif antiga:
        corpo, cab = "real_antiga", ("estimada" if temp_estimada is not None else None)
    elif temp_estimada is not None:
        corpo, cab = "estimada", None
    else:
        corpo, cab = "nenhuma", None
    iv = info_vida or {}
    if iv.get("vida") is None:
        vida = "nenhuma"
    else:
        vida = "estimada" if iv.get("tipo") == "est" else "real"
    return {"temp_cabecalho": cab, "temp_corpo": corpo, "vida": vida,
            "rotulo_vida": "VIDA~" if vida == "estimada" else "VIDA"}


# --------------------------------------------------------------------------
# Formatacao de idade ("ha 4 min") usada pelos pneus
# --------------------------------------------------------------------------
def fmt_idade_medicao(segundos):
    if segundos is None:
        return "--"
    s = max(0, int(segundos))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min"
    return f"{s // 3600} h {(s % 3600) // 60:02d} min"


# --------------------------------------------------------------------------
# Fase 20.2.2: teclas de atalho globais (para o Stream Deck)
# --------------------------------------------------------------------------
# O overlay registra combinacoes de teclas no Windows (RegisterHotKey). Elas NAO entram no iRacing: so o
# overlay as recebe. Usam F13..F24, que nao existem na maioria dos teclados, com Ctrl+Alt+Shift (janelas) ou
# Ctrl+Alt (controles). O Stream Deck as envia com a acao "Hotkey". Cada botao reaproveita a MESMA funcao
# que o item correspondente do menu da bandeja ja usava: nada de janelas, calculos ou perfis foi alterado.
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x0001, 0x0002, 0x0004, 0x0008, 0x4000
VK_F13 = 0x7C                      # F13 = 0x7C ... F24 = 0x87
MODS_JANELAS = MOD_CONTROL | MOD_ALT | MOD_SHIFT
MODS_CONTROLES = MOD_CONTROL | MOD_ALT
MODS_NOVAS = MOD_ALT                # 1.3.0: as 4 janelas novas (Luz ABS/TC, Retorno, Estrategia); o LMU usa Alt+Shift+F21..F24
ID_BASE_TECLA = 0x4F00             # ids de atalho do overlay (faixa permitida: 0x0000 a 0xBFFF)
INTERVALO_MIN_ATALHO = 0.20        # s: um mesmo atalho repetido antes disso e ignorado (toque duplo/rebote)


class AtalhoGlobal:
    """Um atalho: id, rotulo, modificadores (valores do Windows), tecla F13..F24 e o que ele faz."""
    __slots__ = ("id", "rotulo", "mods", "fn", "tipo", "alvo")

    def __init__(self, id_, rotulo, mods, fn, tipo, alvo):
        self.id, self.rotulo, self.mods, self.fn, self.tipo, self.alvo = id_, rotulo, int(mods), int(fn), tipo, alvo

    @property
    def vk(self):
        return VK_F13 + (self.fn - 13)

    @property
    def nome(self):
        partes = [n for bit, n in ((MOD_CONTROL, "Ctrl"), (MOD_ALT, "Alt"), (MOD_SHIFT, "Shift"), (MOD_WIN, "Win"))
                  if self.mods & bit]
        return "+".join(partes + [f"F{self.fn}"])

    def __repr__(self):
        return f"AtalhoGlobal({self.id!r}, {self.nome})"


def _janela(fn, id_, rotulo, chave):
    return AtalhoGlobal("janela_" + id_, "Mostrar/ocultar " + rotulo, MODS_JANELAS, fn, "alternar", chave)


# tipo: "alternar" = liga/desliga o item (marcado) do menu; "perfil" = escolhe o perfil de exibicao;
#       "chamar" = executa uma acao do menu (sem estado)
ATALHOS = (
    _janela(13, "telemetria", "telemetria", "mostrar_telemetria"),
    _janela(14, "voltas", "voltas (delta e combustivel)", "mostrar_voltas"),
    _janela(15, "relativo", "relativo", "mostrar_relativo"),
    _janela(16, "classificacao", "classificacao", "mostrar_classificacao"),
    _janela(17, "mapa", "mapa da pista", "mostrar_mapa"),
    _janela(18, "radar", "radar", "mostrar_radar"),
    _janela(19, "pneus", "pneus", "mostrar_pneus"),
    _janela(20, "setores", "setores", "mostrar_setores"),
    _janela(21, "clima", "clima e vento", "mostrar_clima"),
    _janela(22, "danos", "danos", "mostrar_danos"),
    _janela(23, "combustivel", "painel de combustivel e pit", "mostrar_combustivel"),
    _janela(24, "forca_g", "forca G", "mostrar_forca_g"),
    AtalhoGlobal("perfil_auto", "Perfil: Automatico", MODS_CONTROLES, 13, "perfil", "auto"),
    AtalhoGlobal("perfil_treino", "Perfil: Treino", MODS_CONTROLES, 14, "perfil", "Treino"),
    AtalhoGlobal("perfil_classificacao", "Perfil: Classificacao", MODS_CONTROLES, 15, "perfil", "Classificacao"),
    AtalhoGlobal("perfil_corrida", "Perfil: Corrida", MODS_CONTROLES, 16, "perfil", "Corrida"),
    AtalhoGlobal("economia_cpu", "Modo economia de CPU (liga/desliga)", MODS_CONTROLES, 17, "alternar", "economia_cpu"),
    AtalhoGlobal("aparecer_sozinho", "Aparecer sozinho ao entrar no carro (liga/desliga)", MODS_CONTROLES, 18,
                 "alternar", "auto_modo"),
    AtalhoGlobal("travar_posicao", "Travar posicao das janelas (liga/desliga)", MODS_CONTROLES, 19, "alternar", "travado"),
    AtalhoGlobal("zerar_pico_g", "Zerar o pico de G", MODS_CONTROLES, 20, "chamar", "zerar_pico_g"),
    AtalhoGlobal("limpar_impactos", "Limpar as marcas de impacto", MODS_CONTROLES, 21, "chamar", "limpar_impactos"),
    AtalhoGlobal("sair", "FECHAR o overlay (o mesmo que Sair no menu da bandeja)", MODS_CONTROLES, 22, "chamar", "sair"),
    # 1.3.0: janelas novas da 1.2.0 (Alt+F13..F16). Acrescentadas NO FIM para nao mudar o codigo dos atalhos antigos.
    AtalhoGlobal("janela_luz_abs", "Mostrar/ocultar luz do ABS", MODS_NOVAS, 13, "alternar", "mostrar_luz_abs"),
    AtalhoGlobal("janela_luz_tc", "Mostrar/ocultar luz do TC (estimada)", MODS_NOVAS, 14, "alternar", "mostrar_luz_tc"),
    AtalhoGlobal("janela_retorno", "Mostrar/ocultar retorno a pista", MODS_NOVAS, 15, "alternar", "mostrar_retorno"),
    AtalhoGlobal("janela_estrategia", "Mostrar/ocultar estrategia de pneus", MODS_NOVAS, 16, "alternar", "mostrar_estrategia"),
    # 1.7.0: acrescentado NO FIM (os codigos dos atalhos antigos nao mudam)
    AtalhoGlobal("pedir_pit", "Pit: PEDIR a entrada (sempre liga; serve para o botao 'Pitting In' do Stream Deck)", MODS_CONTROLES, 23, "chamar", "pedir_pit"),
    AtalhoGlobal("cancelar_pit", "Pit: CANCELAR o pedido de entrada", MODS_CONTROLES, 24, "chamar", "cancelar_pit"),
    # 1.7.0 build q: telas novas (Alt+F17..F19; Alt+F13..F16 sao as janelas da 1.3.0)
    AtalhoGlobal("janela_consumo", "Mostrar/ocultar consumo por trecho (Burn Zones e Fuel Flow)", MODS_NOVAS, 17, "alternar", "mostrar_consumo"),
    AtalhoGlobal("janela_delta_trace", "Mostrar/ocultar Delta Trace", MODS_NOVAS, 18, "alternar", "mostrar_delta_trace"),
    AtalhoGlobal("janela_curvas", "Mostrar/ocultar Curvas (velocidade minima por curva)", MODS_NOVAS, 19, "alternar", "mostrar_curvas"),
)
TIPOS_ATALHO = ("alternar", "perfil", "chamar")


def validar_atalhos(atalhos=ATALHOS):
    """Lista de problemas do mapa de teclas (vazia = tudo certo): duplicados, tecla fora de F13..F24, sem modificador."""
    erros, ids, combos = [], set(), {}
    for a in atalhos:
        if a.id in ids:
            erros.append(f"id repetido: {a.id}")
        ids.add(a.id)
        if not 13 <= a.fn <= 24:
            erros.append(f"{a.id}: tecla F{a.fn} fora de F13..F24")
        if not a.mods & (MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_WIN):
            erros.append(f"{a.id}: sem modificador")
        if a.mods & MOD_NOREPEAT:
            erros.append(f"{a.id}: MOD_NOREPEAT e aplicado no registro, nao no mapa")
        if a.tipo not in TIPOS_ATALHO:
            erros.append(f"{a.id}: tipo desconhecido {a.tipo!r}")
        combo = (a.mods, a.fn)
        if combo in combos:
            erros.append(f"{a.id}: mesma combinacao de {combos[combo]} ({a.nome})")
        combos[combo] = a.id
    return erros


def atalho_por_id(id_, atalhos=ATALHOS):
    return next((a for a in atalhos if a.id == id_), None)


def atalho_por_codigo(codigo, atalhos=ATALHOS):
    """Codigo recebido do Windows (WM_HOTKEY) -> atalho. O codigo e ID_BASE_TECLA + posicao no mapa."""
    i = int(codigo) - ID_BASE_TECLA
    return atalhos[i] if 0 <= i < len(atalhos) else None


class DespachanteTeclas:
    """Recebe o codigo de um atalho e chama executor(tipo, alvo). Ignora repeticao rapida e nunca levanta erro."""

    def __init__(self, executor, atalhos=ATALHOS, relogio=time.monotonic, ao_erro=None, ao_evento=None):
        self.executor, self.atalhos, self.relogio = executor, tuple(atalhos), relogio
        self.ao_erro, self.ao_evento = ao_erro, ao_evento
        self._ultimo = {}

    def tratar(self, codigo):
        """Retorna 'ok', 'repeticao', 'desconhecido' ou 'erro'."""
        a = atalho_por_codigo(codigo, self.atalhos)
        if a is None:
            return "desconhecido"
        agora = self.relogio()
        if agora - self._ultimo.get(a.id, -1e9) < INTERVALO_MIN_ATALHO:
            return "repeticao"
        self._ultimo[a.id] = agora
        try:
            self.executor(a.tipo, a.alvo)
        except Exception as erro:              # um atalho com defeito nunca pode derrubar o overlay
            if self.ao_erro:
                self.ao_erro(f"atalho global {a.id} ({a.nome})", erro)
            return "erro"
        if self.ao_evento:
            self.ao_evento(f"atalho global {a.nome}: {a.rotulo}")
        return "ok"


class EscutaTeclas:
    """Registra os atalhos e escuta WM_HOTKEY numa thread propria; entrega os codigos numa fila.

    `api` abstrai o Windows (para testar sem ele): preparar() -> id da thread; registrar(codigo, mods, vk) -> (ok, erro);
    liberar(codigo); esperar() -> codigo ou None (encerrar); encerrar(id_thread) para destravar esperar().
    O registro e a espera precisam acontecer na MESMA thread (regra do Windows): por isso tudo roda em _laco().
    """

    def __init__(self, api, atalhos=ATALHOS):
        self.api, self.atalhos = api, tuple(atalhos)
        self.registrados, self.falhas, self.erro = [], [], None      # falhas: (atalho, texto do erro)
        self._fila = queue.SimpleQueue()
        self._thread, self._id_thread, self._pronto = None, None, threading.Event()

    def iniciar(self, timeout=3.0):
        """Liga a escuta. Retorna (quantos registrados, lista de falhas)."""
        if self._thread is None:
            self._thread = threading.Thread(target=self._laco, name="teclas-globais", daemon=True)
            self._thread.start()
            self._pronto.wait(timeout)
        return len(self.registrados), list(self.falhas)

    def _laco(self):
        try:
            self._id_thread = self.api.preparar()
            for i, a in enumerate(self.atalhos):
                codigo = ID_BASE_TECLA + i
                ok, erro = self.api.registrar(codigo, a.mods | MOD_NOREPEAT, a.vk)
                if ok:
                    self.registrados.append(codigo)
                else:
                    self.falhas.append((a, erro))
        except Exception as e:
            self.erro = repr(e)
        finally:
            self._pronto.set()
        try:
            while self.erro is None:
                codigo = self.api.esperar()
                if codigo is None:
                    break
                self._fila.put(codigo)
        except Exception as e:
            self.erro = repr(e)
        finally:
            for codigo in self.registrados:
                try:
                    self.api.liberar(codigo)
                except Exception:
                    pass
            self.registrados = []

    def retirar(self):
        """Codigos recebidos desde a ultima chamada (nao bloqueia)."""
        saida = []
        while True:
            try:
                saida.append(self._fila.get_nowait())
            except queue.Empty:
                return saida

    def parar(self, timeout=2.0):
        if self._thread is not None and self._thread.is_alive():
            try:
                self.api.encerrar(self._id_thread)
            except Exception:
                pass
            self._thread.join(timeout)
        if self._thread is not None and self._thread.is_alive():
            return False                    # nao encerrou: mantem a referencia (nao esquece uma thread viva)
        self._thread = None
        return True


class ApiTeclasWindows:
    """Implementacao real (so Windows, so ctypes: nada a instalar). RegisterHotKey sem janela = fila da thread."""
    WM_HOTKEY, WM_QUIT, ERRO_JA_REGISTRADA = 0x0312, 0x0012, 1409

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self._ct, self._wt = ctypes, wintypes
        u, k = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)
        u.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        u.RegisterHotKey.restype = wintypes.BOOL
        u.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        u.UnregisterHotKey.restype = wintypes.BOOL
        u.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        u.GetMessageW.restype = ctypes.c_int                     # BOOL de 3 estados: 0 = WM_QUIT, -1 = erro
        u.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
        u.PeekMessageW.restype = wintypes.BOOL
        u.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        u.PostThreadMessageW.restype = wintypes.BOOL
        k.GetCurrentThreadId.restype = wintypes.DWORD
        self._u, self._k = u, k

    def preparar(self):
        self._u.PeekMessageW(self._ct.byref(self._wt.MSG()), None, 0, 0, 0)   # cria a fila de mensagens da thread
        return int(self._k.GetCurrentThreadId())

    def registrar(self, codigo, mods, vk):
        if self._u.RegisterHotKey(None, codigo, mods, vk):
            return True, ""
        erro = self._ct.get_last_error()
        return False, ("ja usada por outro programa (erro 1409)" if erro == self.ERRO_JA_REGISTRADA else f"erro {erro}")

    def liberar(self, codigo):
        self._u.UnregisterHotKey(None, codigo)

    def esperar(self):
        msg = self._wt.MSG()
        while True:
            r = self._u.GetMessageW(self._ct.byref(msg), None, 0, 0)
            if r <= 0:
                return None
            if msg.message == self.WM_HOTKEY:
                return int(msg.wParam)

    def encerrar(self, id_thread):
        if not self._u.PostThreadMessageW(int(id_thread), self.WM_QUIT, 0, 0):
            raise OSError(self._ct.get_last_error(), "PostThreadMessageW falhou")


def texto_atalhos(atalhos=ATALHOS):
    """Tabela legivel (para o ATALHOS_STREAM_DECK.txt e o LEIA-ME)."""
    larg = max(len(a.nome) for a in atalhos)
    linhas = []
    for a in atalhos:
        linhas.append(f"  {a.nome.ljust(larg)}  {a.rotulo}")
    return "\n".join(linhas)
