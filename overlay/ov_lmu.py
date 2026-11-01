# -*- coding: utf-8 -*-
"""
Overlay LMU - camada de dados do Le Mans Ultimate (SEM Qt e SEM overlay_iracing).

O Le Mans Ultimate publica os dados numa memoria compartilhada nativa ("LMU_Data"). No Windows nao e preciso
nenhum plugin (basta a opcao "Enable Plugins" ligada em Settings > Gameplay no jogo). A estrutura de dados vem da
biblioteca pyLMUSharedMemory (licenca MIT, pasta pyLMUSharedMemory/), que espelha o cabecalho oficial do jogo.

Este arquivo so LE (acesso somente leitura ao mapa de memoria) e converte para as unidades/convencoes do overlay.
Nao injeta nada no jogo e nunca CRIA o mapa de memoria (so abre o que o jogo ja criou).

Convencoes do jogo (rFactor 2 / LMU) usadas aqui:
  - eixos locais do carro: +x = ESQUERDA, +y = cima, +z = para TRAS  (por isso G lateral = x e G longitudinal = -z)
  - tempos em segundos; combustivel em litros; temperaturas em Celsius; vento em m/s (modulo do vetor)
"""
import ctypes
import math
import re
import sys
import time

from pyLMUSharedMemory import lmu_data

NOME_MAPA = "LMU_Data"
MAX_CARROS = lmu_data.LMUConstants.MAX_MAPPED_VEHICLES          # 104
TAMANHO = ctypes.sizeof(lmu_data.LMUObjectOut)                  # 324 820 bytes nesta versao da estrutura
GRAVIDADE = 9.81
FILE_MAP_READ = 0x0004

# Estados da conexao
SEM_JOGO = "sem_jogo"              # o mapa "LMU_Data" nao existe: o jogo nao esta aberto
INCOMPATIVEL = "incompativel"      # existe, mas nao tem o formato esperado (jogo atualizado?)
SEM_SESSAO = "sem_sessao"          # jogo aberto, mas sem sessao carregada (menus)
OK = "ok"


class MapaIndisponivel(Exception):
    """O jogo nao esta aberto (nao ha mapa de memoria para abrir)."""


class MapaIncompativel(Exception):
    """O mapa existe, mas e menor do que a estrutura esperada."""


# --------------------------------------------------------------------------
# Texto
# --------------------------------------------------------------------------
def texto(valor):
    """bytes/str da estrutura -> texto limpo (corta no primeiro NUL, aceita lixo sem quebrar)."""
    if valor is None:
        return ""
    if isinstance(valor, (bytes, bytearray)):
        valor = bytes(valor).split(b"\0", 1)[0].decode("utf-8", "replace")
    return str(valor).strip()


def numero_do_carro(nome_veiculo):
    """'Toyota Gazoo Racing #7' -> '7'. Sem '#', procura um numero no fim do nome; senao ''.
    (O LMU nao tem um campo separado para o numero: ele vem no nome do veiculo - confirmar no jogo real.)"""
    t = texto(nome_veiculo)
    m = re.search(r"#\s*(\d{1,3})\b", t)
    if m:
        return m.group(1)
    m = re.search(r"(?:^|[\s:])(\d{1,3})\s*$", t)
    return m.group(1) if m else ""


# --------------------------------------------------------------------------
# Classes (o jogo informa so o nome; cor e ordem sao do overlay)
# --------------------------------------------------------------------------
# (rotulo, cor, ordem): ordem menor = classe mais rapida = aparece primeiro
_CLASSES = {
    "hyper": ("HYPERCAR", (230, 60, 40), 0), "hypercar": ("HYPERCAR", (230, 60, 40), 0),
    "lmp1": ("LMP1", (255, 0, 170), 1),
    "lmp2": ("LMP2", (0, 136, 255), 2), "lmp2_elms": ("LMP2 ELMS", (0, 68, 170), 2),
    "lmp3": ("LMP3", (136, 0, 136), 3),
    "gte": ("GTE", (0, 204, 68), 4), "gt2": ("GT2", (187, 0, 0), 4),
    "gt3": ("LMGT3", (34, 153, 0), 5), "lmgt3": ("LMGT3", (34, 153, 0), 5),
}


def classe_do_carro(nome):
    """Nome da classe (mVehicleClass) -> {"rotulo", "cor", "ordem"}. Classe desconhecida: cor estavel pelo nome,
    ordem 9 (depois das conhecidas) - nunca quebra."""
    bruto = texto(nome)
    chave = bruto.lower().replace(" ", "")
    if chave in _CLASSES:
        rotulo, cor, ordem = _CLASSES[chave]
        return {"rotulo": rotulo, "cor": cor, "ordem": float(ordem)}
    h = sum(ord(c) * (i + 3) for i, c in enumerate(chave)) or 1
    cor = (80 + (h * 37) % 150, 80 + (h * 91) % 150, 80 + (h * 53) % 150)
    return {"rotulo": bruto.upper() or "CLASSE", "cor": cor, "ordem": 9.0}


# --------------------------------------------------------------------------
# Sessao
# --------------------------------------------------------------------------
def tipo_sessao(codigo):
    """mSession: 0=teste 1-4=treino 5-8=classificacao 9=aquecimento 10-13=corrida (nomes iguais aos do iRacing)."""
    try:
        c = int(codigo)
    except (TypeError, ValueError):
        return None
    if c == 0:
        return "TESTE"
    if 1 <= c <= 4:
        return "TREINO"
    if 5 <= c <= 8:
        return "QUALIFICACAO"
    if c == 9:
        return "AQUECIMENTO"
    if 10 <= c <= 13:
        return "CORRIDA"
    return None


def voltas_da_sessao(max_voltas):
    """mMaxLaps: numero de voltas da sessao; sessao por tempo vem com um valor enorme -> None."""
    try:
        v = int(max_voltas)
    except (TypeError, ValueError):
        return None
    return v if 0 < v < 30000 else None


def tempo_restante(info):
    """Segundos ate o fim da sessao (mEndET - mCurrentET); None se a sessao nao tem limite de tempo."""
    try:
        fim, agora = float(info.mEndET), float(info.mCurrentET)
        if 0 < fim < 1.0e6 and agora >= 0:
            restante = fim - agora
            if 0 <= restante < 86400:
                return restante
        resto = float(info.mSessionTimeRemaining)
        if 0 <= resto < 86400:
            return resto
    except (TypeError, ValueError):
        pass
    return None


# --------------------------------------------------------------------------
# Clima
# --------------------------------------------------------------------------
def nivel_pista_molhada(umidade):
    """Umidade media da pista (0..1) -> escala 1..7 do painel (1 seca ... 7 encharcada).
    Limiares do OVERLAY (o jogo informa so a fracao 0..1): servem de apoio visual, nao sao uma medida do jogo."""
    try:
        w = float(umidade)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(w):
        return None
    for limite, nivel in ((0.02, 1), (0.08, 2), (0.20, 3), (0.40, 4), (0.60, 5), (0.80, 6)):
        if w < limite:
            return nivel
    return 7


def ceu_do_painel(cobertura):
    """mCloudCoverage (0..10) -> 0 limpo, 1 parcialmente nublado, 2 nublado, 3 encoberto (escala do painel)."""
    try:
        c = int(cobertura)
    except (TypeError, ValueError):
        return None
    if c <= 0:
        return 0
    if c <= 2:
        return 1
    if c == 3:
        return 2
    return 3


def vento_do_carro(info, tele):
    """Vento do jogo: velocidade (km/h) e direcao RELATIVA ao carro (de onde vem, rad, horario a partir da frente).
    O LMU nao tem referencia de norte; so o vetor do mundo (mWind, m/s) e a orientacao do carro (mOri, linhas =
    eixos locais x=esquerda, y=cima, z=traseira). Vetor exatamente zero = o jogo nao informou (devolve None)."""
    saida = {"vel": None, "dir_rel": None, "mundo": None, "local": None}
    try:
        w = info.mWind
        wx, wy, wz = float(w.x), float(w.y), float(w.z)
    except (TypeError, ValueError, AttributeError):
        return saida
    if not all(math.isfinite(v) for v in (wx, wy, wz)):
        return saida
    saida["mundo"] = (wx, wy, wz)
    if wx == 0.0 and wy == 0.0 and wz == 0.0:
        return saida
    saida["vel"] = math.sqrt(wx * wx + wy * wy + wz * wz) * 3.6                    # m/s -> km/h
    if tele is None:
        return saida
    try:
        local = tuple(float(tele.mOri[k].x) * wx + float(tele.mOri[k].y) * wy + float(tele.mOri[k].z) * wz
                      for k in range(3))
    except (TypeError, ValueError, AttributeError):
        return saida
    if not all(math.isfinite(v) for v in local):
        return saida
    saida["local"] = local                                                          # (esquerda, cima, traseira)
    if math.hypot(local[0], local[2]) >= 0.05:                                      # abaixo disso: sem direcao util
        # o ar vai para +z (traseira) quando VEM da frente; vai para +x (esquerda) quando VEM da direita
        saida["dir_rel"] = math.atan2(local[0], local[2]) % (2.0 * math.pi)
    return saida


def clima_bruto(info):
    """Dados do clima do jogo em unidades do painel. Neblina nao e informada pelo LMU nesta estrutura (None: o painel
    mostra '--' em vez de inventar). A velocidade do vento sai daqui; a direcao, de vento_do_carro (precisa do carro)."""
    def num(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None

    vento = vento_do_carro(info, None)["vel"]
    chuva = num(info.mRaining)
    return {
        "pista": num(info.mTrackTemp), "ar": num(info.mAmbientTemp),
        "chuva_pct": None if chuva is None else max(0.0, min(100.0, chuva * 100.0)),
        "umidade_pista": num(info.mAvgPathWetness),
        "pista_molhada": nivel_pista_molhada(info.mAvgPathWetness),
        "ceu": ceu_do_painel(info.mCloudCoverage),
        "vento_vel": vento,
    }


# --------------------------------------------------------------------------
# Carro (telemetria)
# --------------------------------------------------------------------------
def forca_g_do_carro(tele):
    """(lateral, longitudinal) em g, no sentido do painel: lateral > 0 = esquerda; longitudinal > 0 = acelerando.
    LMU: +x = esquerda e +z = para tras, entao lateral = x e longitudinal = -z."""
    a = tele.mLocalAccel
    return float(a.x) / GRAVIDADE, -float(a.z) / GRAVIDADE


def velocidade_kmh(tele):
    v = tele.mLocalVel
    return math.sqrt(float(v.x) ** 2 + float(v.y) ** 2 + float(v.z) ** 2) * 3.6


def volante_graus(tele):
    """Graus do volante, positivo = esquerda (padrao do painel). O jogo informa -1..1 (esquerda -> direita) e o
    curso visual do volante em graus."""
    curso = float(tele.mVisualSteeringWheelRange) or float(tele.mPhysicalSteeringWheelRange) or 540.0
    if not math.isfinite(curso) or curso <= 0:
        curso = 540.0
    return -float(tele.mUnfilteredSteering) * (curso / 2.0)


def bias_dianteiro_pct(tele):
    """Balanco de freio em % NA FRENTE (mRearBrakeBias = fracao atras). None se o valor nao parece valido."""
    traseira = float(tele.mRearBrakeBias)
    if not math.isfinite(traseira) or not 0.05 <= traseira <= 0.95:
        return None
    return (1.0 - traseira) * 100.0


def controle_tracao(tele):
    """{'nivel','nivel2','ligado'} no formato do painel, ou None se o carro nao tem controle de tracao."""
    if int(tele.mTCMax) <= 0:
        return None
    return {"nivel": float(tele.mTC), "nivel2": None, "ligado": int(tele.mTC) > 0}


def abs_nivel(tele):
    return float(tele.mABS) if int(tele.mABSMax) > 0 else None


def motivo_volta_suja(scor, tele):
    """Por que a volta atual NAO deve servir de referencia (ou None se esta limpa). Conservador, como no iRacing:
    prefere descartar uma volta boa a aceitar uma volta suja."""
    if scor is not None and (scor.mInPits or scor.mInGarageStall):
        return "boxes"
    if scor is not None and int(scor.mPitState) in (1, 2, 3, 4):
        return "boxes"
    if tele is not None:
        if tele.mLapInvalidated:
            return "volta invalidada pelo jogo"
        sup = [int(tele.mWheels[i].mSurfaceType) for i in range(4)]
        if all(s in (2, 3, 4) for s in sup):            # grama, terra ou cascalho nas quatro rodas
            return "fora da pista"
    return None


# --------------------------------------------------------------------------
# Pneus, freios, danos, energia virtual e bandeiras (so o carro do jogador tem telemetria completa)
# --------------------------------------------------------------------------
KELVIN = 273.15
# --- v1.5: temperaturas (validadas contra o log do jogo real) --------------------------------------------------
# FREIO: o jogo informa mBrakeTemp em KELVIN (parado nos boxes o valor e ~290-295, igual a temperatura ambiente; em Celsius
# seria impossivel). Antes o overlay mostrava ~273 C a mais. Se um dia o jogo passar a informar Celsius, trocar para False.
FREIO_EM_KELVIN = True
# PNEU: o jogo mostra no MFD um valor "entre a superficie e a camada interna" (nao e a carcaca) - FAQ do TinyPedal.
# v1.5.1: a media "meio" ficou abaixo do jogo no teste real (log 01/11: superficie ~50-85, interna ~67-82) -> padrao "interna".
# Antes o overlay usava so a superficie (mTemperature, oscila muito e fica mais fria). Opcoes:
#   "meio" (media de superficie e camada interna)  |  "superficie"  |  "interna"  |  "carcaca"
TEMP_PNEU_FONTE = "interna"
# mWear: "0.0-1.0, fraction of maximum" - NAO esta claro se 1.0 e pneu novo ou pneu no limite. Suposicao inicial: 1.0 = novo
# (vida restante). A conferencia e o teste 4 do roteiro (o diagnostico imprime o valor cru). Se estiver invertido, trocar aqui.
PNEU_NOVO_E_1 = True
RODAS = ("FL", "FR", "RL", "RR")                      # 0=dianteira esquerda, 1=dianteira direita, 2=traseira esq., 3=traseira dir.
COMPOSTOS = {0: "S", 1: "M", 2: "H", 3: "W"}          # mCompoundType: 0 macio, 1 medio, 2 duro, 3 chuva (documentado pelo jogo)
NOMES_COMPOSTO = {"S": "Macio", "M": "Medio", "H": "Duro", "W": "Chuva"}
# mDentSeverity[8]: "8 locais ao redor do carro". ORDEM conferida no jogo real: impacto frente-esquerda (x=+1,04 m, z=-1,72 m)
# acendeu o indice 1; impactos na direita acenderam 7 (frente-direita), 5 (x=-0,99, z=+1,48), 6 (x=-0,98, z=-0,30); impacto
# frontal (x=+0,37, z=-2,41) acendeu 0; impacto no canto traseiro (x=-0,95, z=+2,26) acendeu 4. Logo: a partir da frente, no
# sentido ANTI-horario visto de cima. Indices 2 (esquerda) e 3 (traseira-esquerda) ainda sem batida de teste.
ZONAS_DANO = ("frente", "frente-esquerda", "esquerda", "traseira-esquerda", "traseira", "traseira-direita", "direita",
              "frente-direita")


def lado_do_impacto(x, z):
    """Lado do ultimo impacto a partir da posicao local (mLastImpactPos): +x = esquerda, -z = frente (padrao rFactor 2,
    conferido em impactos reais). Devolve o nome de ZONAS_DANO (8 setores) ou None se nao der para saber.
    Calibrado com o jogo real: nas FACES da frente e da traseira (|z| >= 2,1 m) vale frente/traseira, mesmo no canto (um
    impacto em x=-0,95 m, z=+2,26 m acendeu a zona 'traseira', nao a 'traseira-direita'); nas laterais, o comprimento do
    carro e normalizado (+-2,1 m) para os 8 setores ficarem proporcionais ao carro."""
    if not (_finito(x) and _finito(z)) or (abs(float(x)) < 0.05 and abs(float(z)) < 0.05):
        return None
    if abs(float(z)) >= 2.1:
        return "frente" if float(z) < 0 else "traseira"
    ang = math.degrees(math.atan2(float(x), -float(z) / 2.1))  # 0 = frente, +90 = esquerda, 180 = traseira
    ordem = ("frente", "frente-esquerda", "esquerda", "traseira-esquerda", "traseira", "traseira-direita", "direita",
             "frente-direita")
    return ordem[int(round((ang % 360.0) / 45.0)) % 8]


def _finito(v):
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def pneus_do_carro(tele):
    """Quatro rodas: temperatura do pneu (ver TEMP_PNEU_FONTE, C), pressao (kPa), vida restante (%), freio (C),
    composto, furado/solta. Valores ausentes viram None (nunca 0 inventado)."""
    rodas = []
    for i in range(4):
        w = tele.mWheels[i]
        temps = [float(t) - KELVIN for t in w.mTemperature if _finito(t) and float(t) > 150.0]
        internas = [float(t) - KELVIN for t in w.mTireInnerLayerTemperature if _finito(t) and float(t) > 150.0]
        t_sup = (sum(temps) / len(temps)) if temps else None
        t_int = (sum(internas) / len(internas)) if internas else None
        t_car = (float(w.mTireCarcassTemperature) - KELVIN) if _finito(w.mTireCarcassTemperature) and float(w.mTireCarcassTemperature) > 150.0 else None
        if TEMP_PNEU_FONTE == "superficie":
            t_pneu = t_sup
        elif TEMP_PNEU_FONTE == "interna":
            t_pneu = t_int if t_int is not None else t_sup
        elif TEMP_PNEU_FONTE == "carcaca":
            t_pneu = t_car if t_car is not None else t_sup
        else:                                               # "meio": entre superficie e camada interna (como o MFD do jogo)
            partes = [v for v in (t_sup, t_int) if v is not None]
            t_pneu = (sum(partes) / len(partes)) if partes else None
        desgaste = float(w.mWear) if _finito(w.mWear) else None
        vida = None
        # v1.5.2: o jogo as vezes entrega mWear exatamente 0.0 em algumas rodas enquanto outra tem valor real (log 01/11:
        # [0.0, 0.0, 0.932, 0.0]); pneu util com 0% nao existe, entao 0.0 exato = sem leitura (None), nunca "0% de vida".
        if desgaste is not None and desgaste == 0.0:
            desgaste = None
        if desgaste is not None and -0.01 <= desgaste <= 1.01:
            vida = max(0.0, min(1.0, desgaste if PNEU_NOVO_E_1 else 1.0 - desgaste)) * 100.0
        pressao = float(w.mPressure) if _finito(w.mPressure) and float(w.mPressure) > 1.0 else None
        freio_bruto = float(w.mBrakeTemp) if _finito(w.mBrakeTemp) and float(w.mBrakeTemp) > 0.0 else None
        freio = None
        if freio_bruto is not None:
            freio = freio_bruto - KELVIN if FREIO_EM_KELVIN else freio_bruto
            if not (-50.0 < freio < 1500.0):                # fora de qualquer faixa fisica: descarta (nada inventado)
                freio = None
        otima = float(w.mOptimalTemp) if _finito(w.mOptimalTemp) and float(w.mOptimalTemp) > 20.0 else None
        letra = COMPOSTOS.get(int(w.mCompoundType))
        nome = texto(tele.mFrontTireCompoundName if i < 2 else tele.mRearTireCompoundName)
        rodas.append({"roda": RODAS[i], "temp": t_pneu, "temp_sup": t_sup, "temp_int": t_int, "temp_carc": t_car,
                      "freio_bruto": freio_bruto, "pressao": pressao,
                      "vida": vida, "freio": freio, "otima": otima, "composto": letra, "composto_nome": nome,
                      "furado": bool(w.mFlat), "solta": bool(w.mDetached)})
    oleo = float(tele.mEngineOilTemp) if _finito(tele.mEngineOilTemp) and float(tele.mEngineOilTemp) > 0 else None
    agua = float(tele.mEngineWaterTemp) if _finito(tele.mEngineWaterTemp) and float(tele.mEngineWaterTemp) > 0 else None
    return {"rodas": rodas, "oleo": oleo, "agua": agua}


def danos_do_carro(tele):
    """Danos do carro: 8 zonas (0 nenhum, 1 algum, 2 maior), pecas soltas, superaquecimento, rodas furadas/soltas e o
    ultimo impacto. O LMU NAO informa percentual de dano nem tempo de reparo nesta estrutura."""
    zonas = [max(0, min(2, int(tele.mDentSeverity[i]))) for i in range(8)]
    impacto_et = float(tele.mLastImpactET) if _finito(tele.mLastImpactET) else None
    desde = None
    if impacto_et is not None and impacto_et > 0 and _finito(tele.mElapsedTime):
        desde = max(0.0, float(tele.mElapsedTime) - impacto_et)
    # v1.5.2: motor parado = ignicao ligada (1) e rotacao praticamente zero (a luz de ignicao do painel do jogo); 2 = motor de
    # partida acionado (partida normal), nao conta.
    ign = int(tele.mIgnitionStarter)
    rpm = float(tele.mEngineRPM) if _finito(tele.mEngineRPM) else None
    return {"zonas": zonas, "solta": bool(tele.mDetached), "superaquecendo": bool(tele.mOverheating),
            "ignicao": ign, "motor_parado": bool(ign == 1 and rpm is not None and rpm < 100.0),
            "farois": bool(tele.mHeadlights),
            "furados": [bool(tele.mWheels[i].mFlat) for i in range(4)],
            "rodas_soltas": [bool(tele.mWheels[i].mDetached) for i in range(4)],
            "impacto_desde": desde,
            "impacto_forca": float(tele.mLastImpactMagnitude) if _finito(tele.mLastImpactMagnitude) else None,
            "impacto_lado": lado_do_impacto(tele.mLastImpactPos.x, tele.mLastImpactPos.z) if desde is not None else None}


def energia_virtual_pct(tele):
    """Energia virtual (0 a 100 %) ou None. O jogo informa uma fracao 0..1; fora disso o valor e descartado."""
    v = tele.mVirtualEnergy
    if not _finito(v) or not -0.001 <= float(v) <= 1.001:
        return None
    return max(0.0, min(1.0, float(v))) * 100.0


def _byte_com_sinal(valor):
    """Campos 'char' da estrutura chegam como bytes de tamanho 1; converte para inteiro com sinal."""
    if isinstance(valor, (bytes, bytearray)):
        return int.from_bytes(bytes(valor)[:1] or b"\0", "little", signed=True)
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


NOMES_FCY = {0: "", 1: "pendente", 2: "boxes fechados", 3: "boxes: volta do lider", 4: "boxes abertos", 5: "ultima volta",
             6: "retomada", 7: "corrida parada"}


def bandeiras(info):
    """Estado de bandeiras da sessao: {'fase', 'fcy' (bandeira amarela geral/safety car), 'fcy_estado', 'parada',
    'amarelas_setor' (indices 0..2 com amarela local), 'amarelas_brutas' (valores do jogo, para validacao)}.
    VALORES CONFIRMADOS NO JOGO REAL: 11 = sem amarela naquele setor; 1 = amarela local (ex.: [11, 1, 11]). Na 1.2 o
    codigo tratava qualquer valor diferente de 0 como amarela (alerta falso permanente). Agora so o valor 1 vale e, se os
    3 setores acenderem juntos fora da bandeira amarela geral, o dado e tratado como nao confiavel."""
    fase = int(info.mGamePhase)
    brutas = [int(info.mSectorFlag[i]) for i in range(3)]
    setores = [i for i in range(3) if brutas[i] == 1]
    suspeito = len(setores) == 3 and fase != 6
    return {"fase": fase, "fcy": fase == 6, "fcy_estado": NOMES_FCY.get(_byte_com_sinal(info.mYellowFlagState), ""),
            "parada": fase == 7, "amarelas_setor": [] if suspeito else setores, "amarelas_brutas": brutas,
            "amarelas_suspeitas": suspeito or any(b not in (0, 1, 11) for b in brutas)}


# --------------------------------------------------------------------------
# Janela do jogo (Windows) - so para diagnostico: o overlay aparece por cima do jogo?
# --------------------------------------------------------------------------
NOMES_EXE_JOGO = ("lemansultimate", "lmu")


def descrever_janela_jogo(j):
    """Texto curto (pt-BR) sobre a janela do jogo, para o log e o diagnostico."""
    if not j:
        return "janela do jogo nao encontrada (jogo fechado, ou nao e Windows)"
    modo = ("JANELA COM BORDA (modo Janela)" if j["com_borda"] else
            "SEM BORDA cobrindo a tela inteira (Borderless OU tela cheia exclusiva: o Windows nao diferencia aqui)"
            if j["tela_cheia"] else "sem borda, nao cobre a tela inteira")
    z = ""
    if j.get("z_overlay") is not None:
        z = " | overlay " + ("ACIMA do jogo na ordem das janelas" if j["z_overlay"] < j["z_jogo"] else
                             "ABAIXO do jogo na ordem das janelas (o jogo esta cobrindo o overlay)")
    return (f"{j['exe']} | {modo} | {j['largura']}x{j['altura']} em ({j['x']},{j['y']}) | "
            f"jogo 'sempre no topo': {'sim' if j['topmost'] else 'nao'} | primeiro plano: "
            f"{'o proprio jogo' if j['primeiro_plano'] else (j.get('exe_primeiro_plano') or 'outro programa')}{z}")


def janela_do_jogo(hwnds_overlay=()):
    """Procura a janela do Le Mans Ultimate (Windows) e devolve {exe, x, y, largura, altura, com_borda, tela_cheia,
    topmost, primeiro_plano, z_jogo, z_overlay} ou None. Somente LEITURA de informacoes de janela do Windows
    (EnumWindows, GetWindowRect...); nao toca no processo do jogo."""
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes
        user32, kernel32 = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")          # instancias proprias: nao alteram o uso global
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                        ctypes.POINTER(wintypes.DWORD)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        meus = {int(h) for h in hwnds_overlay}
        ordem, achados = [], {}

        def exe_da_janela(hwnd):
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            h = kernel32.OpenProcess(0x1000, False, pid.value)           # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return ""
            try:
                buf, tam = ctypes.create_unicode_buffer(520), wintypes.DWORD(520)
                if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(tam)):
                    return buf.value.replace("\\", "/").rsplit("/", 1)[-1]
                return ""
            finally:
                kernel32.CloseHandle(h)

        def olhar(hwnd, _):
            ordem.append(int(hwnd or 0))
            if int(hwnd or 0) in meus or not user32.IsWindowVisible(hwnd):
                return True
            r = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(r)) or (r.right - r.left) < 400 or (r.bottom - r.top) < 300:
                return True
            if int(hwnd or 0) in achados:
                return True
            nome = exe_da_janela(hwnd)
            chave = nome.lower().replace(" ", "").replace(".exe", "")
            if any(chave.startswith(n) for n in NOMES_EXE_JOGO):
                achados[int(hwnd)] = (nome, r)
            return True

        Enum = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(Enum(olhar), 0)
        if not achados:
            return None
        hwnd, (nome, r) = next(iter(achados.items()))
        estilo = user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
        ex = user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF

        class _InfoMonitor(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD)]
        mi = _InfoMonitor()
        mi.cbSize = ctypes.sizeof(_InfoMonitor)
        tela_cheia = False
        mon = user32.MonitorFromWindow(hwnd, 2)                             # MONITOR_DEFAULTTONEAREST
        if mon and user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
            m = mi.rcMonitor
            tela_cheia = (r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom)
        z_jogo = ordem.index(int(hwnd)) if int(hwnd) in ordem else 0
        z_meu = min((ordem.index(h) for h in meus if h in ordem), default=None)
        return {"hwnd": int(hwnd), "exe": nome, "x": r.left, "y": r.top, "largura": r.right - r.left, "altura": r.bottom - r.top,
                "com_borda": bool(estilo & 0x00C00000), "tela_cheia": tela_cheia, "topmost": bool(ex & 0x8),
                "primeiro_plano": int(user32.GetForegroundWindow() or 0) == int(hwnd), "z_jogo": z_jogo,
                "z_overlay": z_meu,
                "exe_primeiro_plano": (exe_da_janela(user32.GetForegroundWindow()) if user32.GetForegroundWindow() else "")}
    except Exception:
        return None


def jogo_acima_do_overlay(hwnd_jogo, hwnds_overlay):
    """Amostra rapida (Windows): a janela do jogo esta ACIMA de alguma janela do overlay na ordem do Windows?
    Devolve {"acima": bool, "ocultas": n} ou None. 'ocultas' = janelas do overlay "cloaked" pelo DWM (escondidas pelo
    sistema mesmo estando visiveis para o programa). So leitura."""
    if sys.platform != "win32" or not hwnd_jogo:
        return None
    try:
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32")
        user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetWindow.restype = wintypes.HWND
        dwm = ctypes.WinDLL("dwmapi")
        acima, ocultas, n = False, 0, 0
        for h in hwnds_overlay:
            n += 1
            cur, passos = user32.GetWindow(h, 3), 0                      # GW_HWNDPREV: janela imediatamente acima
            while cur and passos < 4000:
                if int(cur) == int(hwnd_jogo):
                    acima = True
                    break
                cur, passos = user32.GetWindow(cur, 3), passos + 1
            valor = wintypes.DWORD(0)
            if dwm.DwmGetWindowAttribute(wintypes.HWND(h), 13, ctypes.byref(valor), ctypes.sizeof(valor)) == 0 and valor.value:
                ocultas += 1                                             # DWMWA_CLOAKED
        return {"acima": acima, "ocultas": ocultas, "n": n}
    except Exception:
        return None


def instalar_gancho_primeiro_plano(ao_mudar):
    """Windows: chama `ao_mudar()` assim que o primeiro plano muda ou uma janela e restaurada (ex.: clique no jogo), para o
    overlay reafirmar o topo na hora, sem esperar o temporizador. Devolve o objeto a manter vivo (ou None)."""
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32")
        proto = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG, wintypes.LONG,
                                   wintypes.DWORD, wintypes.DWORD)

        def proc(*_):
            try:
                ao_mudar()
            except Exception:
                pass
        retorno = proto(proc)
        user32.SetWinEventHook.restype = wintypes.HANDLE
        hooks = [user32.SetWinEventHook(ev, ev, None, retorno, 0, 0, 0) for ev in (0x0003, 0x0017)]   # FOREGROUND, MINIMIZEEND
        return {"proc": retorno, "hooks": hooks}
    except Exception:
        return None


# --------------------------------------------------------------------------
# Localizar o jogador e validar o conteudo
# --------------------------------------------------------------------------
def localizar_jogador(dados):
    """(indice no scoring, indice na telemetria) do carro do jogador, ou (None, None).
    A telemetria e achada pelo mID (os indices de scoring e telemetria podem ser diferentes)."""
    info = dados.scoring.scoringInfo
    n = max(0, min(int(info.mNumVehicles), MAX_CARROS))
    veiculos = dados.scoring.vehScoringInfo
    i_scor = None
    for i in range(n):
        if veiculos[i].mIsPlayer:
            i_scor = i
            break
    if i_scor is None:
        return None, None
    id_jogador = int(veiculos[i_scor].mID)
    tele = dados.telemetry
    ativos = max(0, min(int(tele.activeVehicles), MAX_CARROS))
    for j in range(ativos):
        if int(tele.telemInfo[j].mID) == id_jogador:
            return i_scor, j
    if tele.playerHasVehicle and 0 <= int(tele.playerVehicleIdx) < MAX_CARROS:
        return i_scor, int(tele.playerVehicleIdx)
    return i_scor, None


def validar(dados):
    """(ok, motivo): confere se o que foi lido parece mesmo a estrutura do jogo (protege contra versao diferente)."""
    info = dados.scoring.scoringInfo
    tele = dados.telemetry
    if not 0 <= int(info.mNumVehicles) <= MAX_CARROS:
        return False, f"numero de carros fora da faixa ({info.mNumVehicles})"
    if not 0 <= int(tele.activeVehicles) <= MAX_CARROS:
        return False, f"carros ativos fora da faixa ({tele.activeVehicles})"
    for nome, valor in (("mCurrentET", info.mCurrentET), ("mLapDist", info.mLapDist),
                        ("mTrackTemp", info.mTrackTemp), ("mAmbientTemp", info.mAmbientTemp)):
        if not math.isfinite(float(valor)):
            return False, f"{nome} nao e um numero valido"
    if int(info.mNumVehicles) > 0:
        pista = texto(info.mTrackName)
        if not pista or not pista.isprintable():
            return False, "nome da pista ilegivel"
    return True, None


def estado_dos_dados(dados):
    ok, motivo = validar(dados)
    if not ok:
        return INCOMPATIVEL, motivo
    if int(dados.scoring.scoringInfo.mNumVehicles) <= 0:
        return SEM_SESSAO, None
    return OK, None


# --------------------------------------------------------------------------
# Leitura da memoria compartilhada (somente leitura)
# --------------------------------------------------------------------------
class _MBI(ctypes.Structure):
    """MEMORY_BASIC_INFORMATION (Windows 64 bits)."""
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_uint32), ("PartitionId", ctypes.c_uint16),
                ("RegionSize", ctypes.c_size_t), ("State", ctypes.c_uint32),
                ("Protect", ctypes.c_uint32), ("Type", ctypes.c_uint32)]


def tamanho_suficiente(tamanho_regiao, esperado=TAMANHO):
    """O mapa precisa ter pelo menos o tamanho da estrutura; ler alem dele travaria o programa."""
    return tamanho_regiao is not None and int(tamanho_regiao) >= int(esperado)


class MapaWindows:
    """Abre o mapa "LMU_Data" que o jogo JA criou (OpenFileMapping, so leitura). Nunca cria o mapa: criar antes do
    jogo poderia atrapalhar o proprio jogo."""

    def __init__(self, nome=NOME_MAPA):
        if sys.platform != "win32":
            raise MapaIndisponivel("so funciona no Windows")
        k32 = ctypes.windll.kernel32
        k32.OpenFileMappingW.restype = ctypes.c_void_p
        k32.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
        k32.MapViewOfFile.restype = ctypes.c_void_p
        k32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]
        k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.VirtualQuery.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MBI), ctypes.c_size_t]
        self._k32 = k32
        self._h = k32.OpenFileMappingW(FILE_MAP_READ, 0, nome)
        if not self._h:
            raise MapaIndisponivel("mapa de memoria do LMU nao encontrado (jogo fechado?)")
        self._ptr = k32.MapViewOfFile(self._h, FILE_MAP_READ, 0, 0, 0)
        if not self._ptr:
            k32.CloseHandle(self._h)
            self._h = None
            raise MapaIndisponivel("nao foi possivel mapear a memoria do LMU")
        info = _MBI()
        if not k32.VirtualQuery(self._ptr, ctypes.byref(info), ctypes.sizeof(info)):
            self.fechar()
            raise MapaIndisponivel("nao foi possivel medir a memoria do LMU")
        self.tamanho = int(info.RegionSize)
        if not tamanho_suficiente(self.tamanho):
            self.fechar()
            raise MapaIncompativel(f"mapa com {self.tamanho} bytes; esperado pelo menos {TAMANHO}")

    def copiar(self):
        return ctypes.string_at(self._ptr, TAMANHO)

    def fechar(self):
        try:
            if getattr(self, "_ptr", None):
                self._k32.UnmapViewOfFile(self._ptr)
            if getattr(self, "_h", None):
                self._k32.CloseHandle(self._h)
        finally:
            self._ptr = self._h = None


class LeitorLMU:
    """Entrega um retrato (copia consistente) da memoria do jogo a cada chamada de ler().

    `abridor` = funcao que devolve um objeto com copiar()/fechar() (padrao: MapaWindows); nos testes, uma versao falsa.
    Reabre sozinho: se o jogo for fechado e aberto de novo, volta a funcionar sem reiniciar o overlay.
    """

    TENTATIVA_S = 1.0          # intervalo entre tentativas de abrir o mapa
    PARADO_FECHA_S = 30.0      # dados sem mudar por tanto tempo: solta o mapa (o jogo pode ter sido fechado)

    def __init__(self, abridor=None, relogio=time.monotonic, ao_mudar_estado=None):
        self._abridor = abridor or MapaWindows
        self._relogio = relogio
        self._mapa = None
        self._ultima_tentativa = -1e9
        self._et = None
        self._t_et = 0.0
        self.estado = SEM_JOGO
        self.motivo = None
        self._ao_mudar = ao_mudar_estado

    def _definir(self, estado, motivo=None):
        if estado != self.estado or motivo != self.motivo:
            anterior = self.estado
            self.estado, self.motivo = estado, motivo
            if self._ao_mudar:
                try:
                    self._ao_mudar(anterior, estado, motivo)
                except Exception:
                    pass

    def fechar(self):
        if self._mapa is not None:
            try:
                self._mapa.fechar()
            except Exception:
                pass
            self._mapa = None

    def ler(self):
        """(estado, dados). dados so existe quando estado e OK ou SEM_SESSAO."""
        agora = self._relogio()
        if self._mapa is None:
            if agora - self._ultima_tentativa < self.TENTATIVA_S:
                return self.estado, None
            self._ultima_tentativa = agora
            try:
                self._mapa = self._abridor()
            except MapaIncompativel as e:
                self._definir(INCOMPATIVEL, str(e))
                return self.estado, None
            except MapaIndisponivel:
                self._definir(SEM_JOGO)
                return self.estado, None
            except Exception as e:                      # qualquer outra falha ao abrir: trata como jogo indisponivel
                self._definir(SEM_JOGO, f"falha ao abrir: {e!r}")
                return self.estado, None
            self._et, self._t_et = None, agora
        try:
            dados = None
            for _ in range(2):                          # 2 tentativas: evita pegar o jogo no meio de uma escrita
                bruto = bytearray(self._mapa.copiar())
                dados = lmu_data.LMUObjectOut.from_buffer(bruto)
                if int(dados.scoring.scoringInfo.mNumVehicles) == int(dados.telemetry.activeVehicles):
                    break
        except Exception as e:
            self.fechar()
            self._definir(SEM_JOGO, f"falha ao ler: {e!r}")
            return self.estado, None
        estado, motivo = estado_dos_dados(dados)
        self._definir(estado, motivo)
        et = float(dados.scoring.scoringInfo.mCurrentET)
        if et != self._et:
            self._et, self._t_et = et, agora
        elif agora - self._t_et > self.PARADO_FECHA_S:
            self.fechar()                               # jogo provavelmente fechado: solta o mapa e volta a procurar
            self._definir(SEM_JOGO)
            return self.estado, None
        if estado == INCOMPATIVEL:
            return estado, None
        return estado, dados

    @property
    def segundos_sem_mudar(self):
        return max(0.0, self._relogio() - self._t_et)
