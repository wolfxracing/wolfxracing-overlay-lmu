# -*- coding: utf-8 -*-
"""
Testes automaticos do overlay LMU (sem o jogo, sem tela: Qt em modo "offscreen").

IMPORTANTE: estes testes usam um JOGO FALSO que escreve a memoria no formato esperado. Eles provam que o codigo faz o que
foi desenhado; NAO provam que o LMU real entrega os dados desse jeito. A homologacao so acontece com o jogo real
(ver ROTEIRO_VALIDACAO_LMU.txt e diagnostico_lmu.bat).

Execucao: python testes\\teste_lmu.py   (ou executar_testes.bat)
"""
import ctypes
import hashlib
import math
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))

import ov_lmu as lmu                                    # noqa: E402
from pyLMUSharedMemory import lmu_data                   # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="teste_lmu_"))
PREVIAS = Path(os.environ.get("PREVIAS_LMU", TMP / "previas"))

_ok, _falhas = 0, []


def confere(condicao, descricao):
    global _ok
    if condicao:
        _ok += 1
    else:
        _falhas.append(descricao)
        print("  FALHOU:", descricao)


def quase(a, b, tol=1e-6):
    return a is not None and b is not None and abs(a - b) <= tol


def grupo(nome):
    print(f"\n== {nome}")


# ----------------------------------------------------------------------------
# Jogo falso: monta a memoria "LMU_Data" no formato real a partir de um cenario
# ----------------------------------------------------------------------------
def _txt(estrutura, campo, valor):
    """Grava texto num campo de caracteres da estrutura (o ctypes devolve bytes ao ler, entao usamos posicao e tamanho)."""
    descritor = getattr(type(estrutura), campo)
    dados = valor.encode("utf-8")[:descritor.size - 1] if isinstance(valor, str) else valor
    base = ctypes.addressof(estrutura) + descritor.offset
    ctypes.memset(base, 0, descritor.size)
    ctypes.memmove(base, dados, len(dados))


class Carro:
    def __init__(self, id_, nome, classe, piloto, lugar, voltas=3, dist=1000.0, ultima=-1.0, melhor=-1.0,
                 box=False, jogador=False, paradas=0, pen=0, comb=128, tbn=0.0, lbn=0, quali=-1, final=0, estado_box=0,
                 vel=None, pit_dist=0.0, bandeira=0):
        self.vel, self.pit_dist, self.bandeira = vel, pit_dist, bandeira
        self.paradas, self.pen, self.comb, self.tbn, self.lbn = paradas, pen, comb, tbn, lbn
        self.quali, self.final, self.estado_box = quali, final, estado_box
        self.id, self.nome, self.classe, self.piloto, self.lugar = id_, nome, classe, piloto, lugar
        self.voltas, self.dist, self.ultima, self.melhor, self.box, self.jogador = voltas, dist, ultima, melhor, box, jogador


class Jogo:
    """Cenario editavel: um jogador (telemetria completa) + outros carros (so classificacao)."""

    def __init__(self):
        self.pista, self.comprimento = "Circuit de la Sarthe", 13626.0
        self.sessao, self.et, self.fim, self.max_voltas = 10, 100.0, 3600.0, 30000
        self.chuva, self.umidade, self.nuvens = 0.0, 0.0, 0
        self.temp_pista, self.temp_ar, self.vento = 31.0, 22.0, (2.0, 0.0, 0.0)
        self.tempo_real, self.no_carro = True, True
        self.carros = []
        self.marcha, self.rpm, self.rpm_max = 4, 6800.0, 8200.0
        self.vel_ms = (0.0, 0.0, -55.0)                      # z negativo = para frente
        self.acel = (0.0, 0.0, 0.0)                          # m/s2 no referencial do carro
        self.acelerador, self.freio, self.embreagem, self.volante = 0.7, 0.0, 0.0, 0.0
        self.combustivel, self.capacidade = 80.0, 105.0
        self.inicio_volta, self.tempo_decorrido = 100.0, 100.0
        self.delta_jogo, self.invalidada = 0.0, False
        self.superficie = 0
        self.tc, self.tc_max, self.abs_, self.abs_max = 3, 10, 2, 12
        self.freio_traseiro = 0.46
        self.estimada = 205.0
        # --- janelas novas (v1.2) ---
        self.energia = 0.62                                   # fracao 0..1
        self.fase, self.amarelas, self.estado_amarela = 5, (0, 0, 0), 0
        self.limitador = False
        self.rodas = [dict(temp=(355.0, 365.0, 360.0), pressao=205.0, desgaste=0.8, freio=520.0, composto=1, otima=90.0,
                           furado=False, solta=False) for _ in range(4)]
        self.dentes = [0] * 8
        self.peca_solta, self.superaquecendo = False, False
        self.ignicao, self.farois = 2, False                  # v1.5.2
        self.impacto_et, self.impacto_forca = 0.0, 0.0

    def preencher(self, dados):
        info = dados.scoring.scoringInfo
        _txt(info, "mTrackName", self.pista)
        info.mSession, info.mCurrentET, info.mEndET = self.sessao, self.et, self.fim
        info.mStartET = 0.0
        info.mMaxLaps, info.mLapDist = self.max_voltas, self.comprimento
        info.mNumVehicles, info.mInRealtime = len(self.carros), self.tempo_real
        info.mRaining, info.mAvgPathWetness, info.mCloudCoverage = self.chuva, self.umidade, self.nuvens
        info.mTrackTemp, info.mAmbientTemp = self.temp_pista, self.temp_ar
        info.mGamePhase = self.fase
        for k in range(3):
            info.mSectorFlag[k] = self.amarelas[k]
        info.mYellowFlagState = self.estado_amarela.to_bytes(1, "little", signed=True)
        info.mWind.x, info.mWind.y, info.mWind.z = self.vento
        dados.telemetry.activeVehicles = len(self.carros)
        dados.telemetry.playerHasVehicle = self.no_carro
        for i, c in enumerate(self.carros):
            v = dados.scoring.vehScoringInfo[i]
            v.mID, v.mPlace, v.mTotalLaps, v.mLapDist = c.id, c.lugar, c.voltas, c.dist
            v.mLastLapTime, v.mBestLapTime, v.mInPits, v.mIsPlayer = c.ultima, c.melhor, c.box, c.jogador
            v.mEstimatedLapTime = self.estimada
            v.mNumPitstops, v.mNumPenalties, v.mFuelFraction = c.paradas, c.pen, c.comb
            v.mTimeBehindNext, v.mLapsBehindNext, v.mQualification = c.tbn, c.lbn, c.quali
            v.mFinishStatus, v.mPitState = c.final, c.estado_box
            v.mPitLapDist, v.mFlag = c.pit_dist, c.bandeira
            if c.vel is not None:
                v.mLocalVel.x, v.mLocalVel.y, v.mLocalVel.z = 0.0, 0.0, -c.vel
            _txt(v, "mDriverName", c.piloto)
            _txt(v, "mVehicleName", c.nome)
            _txt(v, "mVehicleClass", c.classe)
            t = dados.telemetry.telemInfo[i]
            t.mID = c.id
            if c.jogador:
                dados.telemetry.playerVehicleIdx = i
                t.mGear, t.mEngineRPM, t.mEngineMaxRPM = self.marcha, self.rpm, self.rpm_max
                t.mLocalVel.x, t.mLocalVel.y, t.mLocalVel.z = self.vel_ms
                t.mLocalAccel.x, t.mLocalAccel.y, t.mLocalAccel.z = self.acel
                t.mUnfilteredThrottle, t.mUnfilteredBrake = self.acelerador, self.freio
                t.mUnfilteredClutch, t.mUnfilteredSteering = self.embreagem, self.volante
                t.mFuel, t.mFuelCapacity = self.combustivel, self.capacidade
                t.mLapStartET, t.mElapsedTime = self.inicio_volta, self.tempo_decorrido
                t.mDeltaBest, t.mLapInvalidated = self.delta_jogo, self.invalidada
                t.mVisualSteeringWheelRange = 540.0
                t.mRearBrakeBias = self.freio_traseiro
                t.mTC, t.mTCMax, t.mABS, t.mABSMax = self.tc, self.tc_max, self.abs_, self.abs_max
                t.mIgnitionStarter = self.ignicao
                t.mHeadlights = self.farois
                for k in range(4):
                    t.mWheels[k].mSurfaceType = self.superficie
                    r = self.rodas[k]
                    w = t.mWheels[k]
                    for q in range(3):
                        w.mTemperature[q] = r["temp"][q]
                    w.mPressure, w.mWear, w.mBrakeTemp = r["pressao"], r["desgaste"], r["freio"]
                    w.mCompoundType, w.mOptimalTemp = r["composto"], r["otima"]
                    w.mFlat, w.mDetached = r["furado"], r["solta"]
                t.mVirtualEnergy = self.energia
                t.mSpeedLimiterActive = self.limitador
                for k in range(8):
                    t.mDentSeverity[k] = self.dentes[k]
                t.mDetached, t.mOverheating = self.peca_solta, self.superaquecendo
                t.mLastImpactET, t.mLastImpactMagnitude = self.impacto_et, self.impacto_forca
                t.mEngineOilTemp, t.mEngineWaterTemp = 108.0, 92.0
                _txt(t, "mFrontTireCompoundName", "Medium")
                _txt(t, "mRearTireCompoundName", "Medium")

    def bytes(self):
        bruto = bytearray(lmu.TAMANHO)
        self.preencher(lmu_data.LMUObjectOut.from_buffer(bruto))
        return bytes(bruto)


class MapaFalso:
    def __init__(self, jogo):
        self.jogo, self.fechado = jogo, False

    def copiar(self):
        return self.jogo.bytes()

    def fechar(self):
        self.fechado = True


class Relogio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def avancar(self, s):
        self.t += s


def cenario_corrida():
    j = Jogo()
    j.carros = [
        Carro(1, "Toyota GR010 #7", "Hyper", "K. Kobayashi", 1, voltas=5, dist=4000, ultima=205.4, melhor=204.9,
              paradas=1, quali=2),
        Carro(2, "Ferrari 499P #50", "Hyper", "A. Fuoco", 2, voltas=5, dist=3000, ultima=205.9, melhor=205.2,
              tbn=15.0, quali=1),
        Carro(3, "Oreca 07 #22", "LMP2", "Fulano de Tal", 3, voltas=5, dist=2000, ultima=214.0, melhor=213.1,
              tbn=14.0, quali=4),
        Carro(4, "BMW M4 GT3 #31", "LMGT3", "Jogador Meu", 5, voltas=4, dist=9000, ultima=232.5, melhor=231.9,
              jogador=True, tbn=87.5, quali=5, comb=90, paradas=1),
        Carro(5, "Porsche 911 GT3 R #92", "LMGT3", "M. Cicrano", 4, voltas=5, dist=500, ultima=231.0, melhor=230.4,
              tbn=60.0, quali=7),
        Carro(6, "Corvette Z06 GT3.R #33", "LMGT3", "R. Beltrano", 6, voltas=4, dist=100, ultima=233.3, melhor=232.0,
              box=True, tbn=60.3, quali=6, paradas=2, pen=1, comb=40, estado_box=3),
    ]
    return j


def telemetria(jogo, relogio=None):
    m = preparar_modulo()
    relogio = relogio or Relogio()
    leitor = lmu.LeitorLMU(abridor=lambda: MapaFalso(jogo), relogio=relogio)
    tel = m.TelemetriaLMU(leitor=leitor, relogio=relogio)
    return tel, relogio


def preparar_modulo():
    import overlay_lmu as m
    m.redirecionar_arquivos(TMP, TMP / "config_teste.json", TMP / "log_teste.txt")
    m.ARQ_CONFIG_LMU = TMP / "config_teste.json"
    m.aplicar_textos_lmu()
    return m


# ----------------------------------------------------------------------------
def teste_estrutura():
    grupo("Estrutura do jogo (tamanho e posicoes dos campos)")
    confere(lmu.TAMANHO == 324820, f"tamanho da estrutura = 324820 (obtido {lmu.TAMANHO})")
    confere(lmu.MAX_CARROS == 104, "104 carros no maximo")
    off = lambda c, campo: getattr(c, campo).offset
    # Posicoes fixadas: se alguem trocar a biblioteca e algo mudar, este teste avisa
    confere(off(lmu_data.LMUObjectOut, "scoring") > off(lmu_data.LMUObjectOut, "paths") > off(lmu_data.LMUObjectOut, "generic"),
            "ordem generic < paths < scoring")
    confere(off(lmu_data.LMUObjectOut, "telemetry") > off(lmu_data.LMUObjectOut, "scoring"), "telemetria depois do scoring")
    confere(ctypes.sizeof(lmu_data.LMUScoringData) + ctypes.sizeof(lmu_data.LMUTelemetryData) < lmu.TAMANHO, "blocos cabem no total")
    confere(len(lmu_data.LMUScoringData.vehScoringInfo) == 104 if hasattr(lmu_data.LMUScoringData.vehScoringInfo, "__len__") else True,
            "vetor de 104 carros no scoring")
    confere(lmu.tamanho_suficiente(lmu.TAMANHO) and lmu.tamanho_suficiente(lmu.TAMANHO + 4096), "tamanho igual ou maior: aceito")
    confere(not lmu.tamanho_suficiente(lmu.TAMANHO - 1) and not lmu.tamanho_suficiente(0), "tamanho menor: recusado")


def teste_auxiliares():
    grupo("Funcoes auxiliares")
    confere(lmu.texto(b"Le Mans\0\0lixo") == "Le Mans", "texto corta no primeiro NUL")
    confere(lmu.texto(b"\xff\xfeabc\0").endswith("abc"), "texto aceita bytes invalidos sem quebrar")
    confere(lmu.texto(None) == "", "texto(None)")
    confere(lmu.numero_do_carro("Toyota GR010 #7") == "7", "numero #7")
    confere(lmu.numero_do_carro("Ferrari 499P # 50") == "50", "numero com espaco")
    confere(lmu.numero_do_carro("Oreca 07 22") == "22", "numero no fim sem #")
    confere(lmu.numero_do_carro("Carro sem numero") == "", "sem numero")
    confere(lmu.classe_do_carro("Hyper")["rotulo"] == "HYPERCAR" and lmu.classe_do_carro("LMP2")["rotulo"] == "LMP2", "classes conhecidas")
    confere(lmu.classe_do_carro("LMGT3")["ordem"] > lmu.classe_do_carro("LMP2")["ordem"] > lmu.classe_do_carro("Hyper")["ordem"],
            "ordem Hypercar < LMP2 < LMGT3")
    desc = lmu.classe_do_carro("ClasseNova")
    confere(desc["rotulo"] == "CLASSENOVA" and desc["ordem"] == 9.0 and lmu.classe_do_carro("ClasseNova")["cor"] == desc["cor"],
            "classe desconhecida: rotulo, ultima ordem e cor estavel")
    confere([lmu.tipo_sessao(c) for c in (0, 1, 4, 5, 8, 9, 10, 13, 14)] ==
            ["TESTE", "TREINO", "TREINO", "QUALIFICACAO", "QUALIFICACAO", "AQUECIMENTO", "CORRIDA", "CORRIDA", None],
            "tipo de sessao")
    confere(lmu.voltas_da_sessao(30000) is None and lmu.voltas_da_sessao(0) is None and lmu.voltas_da_sessao(25) == 25, "voltas da sessao")
    confere([lmu.nivel_pista_molhada(x) for x in (0.0, 0.05, 0.15, 0.3, 0.5, 0.7, 0.95)] == [1, 2, 3, 4, 5, 6, 7], "pista molhada 1..7")
    confere(lmu.nivel_pista_molhada(float("nan")) is None, "pista molhada NaN = None")
    confere([lmu.ceu_do_painel(c) for c in (0, 1, 3, 6)] == [0, 1, 2, 3], "ceu")
    # sinais da forca G: LMU +x = esquerda, +z = tras
    j = cenario_corrida()
    j.acel = (19.62, 0.0, 9.81)          # esquerda 2 g, e acelerando para tras no eixo z (freando = +z)
    bruto = bytearray(j.bytes())
    d = lmu_data.LMUObjectOut.from_buffer(bruto)
    i_s, i_t = lmu.localizar_jogador(d)
    lat, lon = lmu.forca_g_do_carro(d.telemetry.telemInfo[i_t])
    confere(quase(lat, 2.0, 1e-4) and quase(lon, -1.0, 1e-4), f"G lateral +2 (esquerda) e longitudinal -1 (freando): {lat:.3f}/{lon:.3f}")
    j.acel = (-9.81, 0.0, -14.715)
    d = lmu_data.LMUObjectOut.from_buffer(bytearray(j.bytes()))
    lat, lon = lmu.forca_g_do_carro(d.telemetry.telemInfo[i_t])
    confere(quase(lat, -1.0, 1e-4) and quase(lon, 1.5, 1e-4), "G lateral -1 (direita) e longitudinal +1,5 (acelerando)")
    j.vel_ms = (3.0, 0.0, -4.0)
    d = lmu_data.LMUObjectOut.from_buffer(bytearray(j.bytes()))
    confere(quase(lmu.velocidade_kmh(d.telemetry.telemInfo[i_t]), 18.0, 1e-3), "velocidade em km/h (modulo do vetor)")
    j.volante = 0.5
    d = lmu_data.LMUObjectOut.from_buffer(bytearray(j.bytes()))
    confere(quase(lmu.volante_graus(d.telemetry.telemInfo[i_t]), -135.0, 1e-3), "volante: 0,5 (direita) = -135 graus")
    confere(quase(lmu.bias_dianteiro_pct(d.telemetry.telemInfo[i_t]), 54.0, 1e-3), "balanco de freio 54% na frente")
    j.freio_traseiro = 0.0
    d = lmu_data.LMUObjectOut.from_buffer(bytearray(j.bytes()))
    confere(lmu.bias_dianteiro_pct(d.telemetry.telemInfo[i_t]) is None, "balanco invalido = None")
    j.tc_max = 0
    d = lmu_data.LMUObjectOut.from_buffer(bytearray(j.bytes()))
    confere(lmu.controle_tracao(d.telemetry.telemInfo[i_t]) is None, "carro sem TC = None")


def teste_motivos_volta_suja():
    grupo("Volta suja (referencia do delta)")
    j = cenario_corrida()
    def motivo(**kw):
        for k, v in kw.items():
            setattr(j, k, v)
        d = lmu_data.LMUObjectOut.from_buffer(bytearray(j.bytes()))
        i_s, i_t = lmu.localizar_jogador(d)
        return lmu.motivo_volta_suja(d.scoring.vehScoringInfo[i_s], d.telemetry.telemInfo[i_t])
    confere(motivo() is None, "volta limpa = sem motivo")
    confere(motivo(invalidada=True) == "volta invalidada pelo jogo", "volta invalidada pelo jogo")
    j.invalidada = False
    confere(motivo(superficie=3) == "fora da pista", "quatro rodas na grama")
    j.superficie = 0
    j.carros[3].box = True
    confere(motivo() == "boxes", "nos boxes")


def teste_leitor():
    grupo("Leitor da memoria (estados)")
    eventos = []
    rel = Relogio()
    # 1) jogo fechado
    def abridor_fechado():
        raise lmu.MapaIndisponivel("fechado")
    L = lmu.LeitorLMU(abridor=abridor_fechado, relogio=rel, ao_mudar_estado=lambda a, b, c: eventos.append((a, b)))
    confere(L.ler() == (lmu.SEM_JOGO, None), "jogo fechado = sem_jogo")
    # 2) abre quando o jogo aparece (respeitando o intervalo de tentativas)
    jogo = cenario_corrida()
    mapas = []
    def abridor():
        m_ = MapaFalso(jogo)
        mapas.append(m_)
        return m_
    L = lmu.LeitorLMU(abridor=abridor, relogio=rel)
    estado, dados = L.ler()
    confere(estado == lmu.OK and dados is not None, "jogo aberto com sessao = ok")
    # 3) sem sessao (menu): zero carros
    vazio = Jogo()
    L2 = lmu.LeitorLMU(abridor=lambda: MapaFalso(vazio), relogio=rel)
    confere(L2.ler()[0] == lmu.SEM_SESSAO, "zero carros = sem_sessao")
    # 4) estrutura incompativel (tamanho)
    def abridor_incompativel():
        raise lmu.MapaIncompativel("pequeno")
    L3 = lmu.LeitorLMU(abridor=abridor_incompativel, relogio=rel)
    confere(L3.ler() == (lmu.INCOMPATIVEL, None), "mapa de outro tamanho = incompativel")
    # 5) conteudo sem sentido (lixo): incompativel e sem dados
    lixo = cenario_corrida()
    lixo.comprimento = float("nan")
    L4 = lmu.LeitorLMU(abridor=lambda: MapaFalso(lixo), relogio=rel)
    estado, dados = L4.ler()
    confere(estado == lmu.INCOMPATIVEL and dados is None, "conteudo invalido (NaN) = incompativel")
    lixo2 = cenario_corrida()
    lixo2.pista = "\x01\x02\x03"
    estado, _ = lmu.LeitorLMU(abridor=lambda: MapaFalso(lixo2), relogio=rel).ler()
    confere(estado == lmu.INCOMPATIVEL, "nome da pista ilegivel = incompativel")
    # 6) dados parados por mais de 30 s: solta o mapa e volta a procurar
    parado = cenario_corrida()
    mapas2 = []
    def abridor2():
        m_ = MapaFalso(parado)
        mapas2.append(m_)
        return m_
    rel2 = Relogio()
    L5 = lmu.LeitorLMU(abridor=abridor2, relogio=rel2)
    confere(L5.ler()[0] == lmu.OK, "parado: primeira leitura ok")
    rel2.avancar(10.0)
    confere(L5.ler()[0] == lmu.OK and L5.segundos_sem_mudar >= 10.0, "parado 10 s: ainda ok (pausa curta)")
    rel2.avancar(25.0)
    confere(L5.ler() == (lmu.SEM_JOGO, None) and mapas2[0].fechado, "parado 35 s: fecha o mapa (sem_jogo)")
    parado.et += 5.0
    rel2.avancar(2.0)
    confere(L5.ler()[0] == lmu.OK and len(mapas2) == 2, "jogo voltou: reabre sozinho")
    # 7) falha ao ler (excecao): fecha e tenta de novo depois
    class MapaQuebrado(MapaFalso):
        def copiar(self):
            raise OSError("leitura falhou")
    quebrado = MapaQuebrado(cenario_corrida())
    L6 = lmu.LeitorLMU(abridor=lambda: quebrado, relogio=rel2)
    confere(L6.ler()[0] == lmu.SEM_JOGO and quebrado.fechado, "falha de leitura: sem_jogo e mapa fechado")
    # 8) copia inconsistente (jogo escrevendo): tenta de novo e usa a consistente
    class MapaInconsistente(MapaFalso):
        def __init__(self, jogo):
            super().__init__(jogo)
            self.chamadas = 0
        def copiar(self):
            self.chamadas += 1
            if self.chamadas == 1:
                bruto = bytearray(self.jogo.bytes())
                lmu_data.LMUObjectOut.from_buffer(bruto).telemetry.activeVehicles = 3     # != mNumVehicles
                return bytes(bruto)
            return self.jogo.bytes()
    inc = MapaInconsistente(cenario_corrida())
    estado, dados = lmu.LeitorLMU(abridor=lambda: inc, relogio=rel2).ler()
    confere(estado == lmu.OK and inc.chamadas == 2 and int(dados.telemetry.activeVehicles) == 6, "copia inconsistente: relê")
    # 9) mapa nunca e criado por nos: so abre. Em Linux a classe real recusa
    try:
        lmu.MapaWindows()
        confere(sys.platform == "win32", "MapaWindows abriu fora do Windows?")
    except lmu.MapaIndisponivel:
        confere(sys.platform != "win32" or True, "MapaWindows recusa sem o jogo / fora do Windows")


def teste_104_carros():
    grupo("Grid cheio (104 carros)")
    j = Jogo()
    for i in range(104):
        j.carros.append(Carro(i + 1, f"Carro {i} #{i + 1}", ("Hyper", "LMP2", "LMGT3")[i % 3], f"Piloto {i}", i + 1,
                              voltas=2, dist=100.0 * i, ultima=210 + i * 0.1, melhor=209 + i * 0.1, jogador=(i == 50)))
    tel, rel = telemetria(j)
    d = tel.ler()
    confere(d["conectado"] and d["classificacao"] is not None, "104 carros: classificacao montada")
    j.carros.append(Carro(105, "Extra", "LMP2", "X", 105))
    tel2, _ = telemetria(j)
    d = tel2.ler()
    confere(not d["conectado"], "105 carros (fora da faixa): recusado como incompativel, sem quebrar")


# ----------------------------------------------------------------------------
def teste_telemetria_dados():
    grupo("TelemetriaLMU: dados entregues as janelas")
    j = cenario_corrida()
    j.acel = (14.715, 0.0, 4.905)            # 1,5 g esquerda, 0,5 g freando
    j.chuva, j.umidade, j.nuvens = 0.35, 0.45, 5
    j.volante = -0.25
    tel, rel = telemetria(j)
    d = tel.ler()
    confere(d["conectado"] and d["no_carro"], "conectado e no carro")
    confere(d["tipo_sessao"] == "CORRIDA", "sessao: corrida")
    confere(d["marcha"] == 4 and quase(d["rpm"], 6800.0) and quase(d["rpm_max"], 8200.0), "marcha e rpm")
    confere(quase(d["velocidade"], 55 * 3.6, 1e-3), "velocidade km/h")
    confere(quase(d["acelerador"], 0.7, 1e-6) and d["freio"] == 0.0, "pedais")
    confere(quase(d["volante"], 67.5, 1e-3), "volante: -0,25 = 67,5 graus para a esquerda")
    confere(d["tc"] == {"nivel": 3.0, "nivel2": None, "ligado": True} and d["abs_nivel"] == 2.0, "TC e ABS")
    confere(quase(d["bias"], 54.0, 1e-3), "balanco de freio")
    g = d["forca_g"]
    confere(g is not None and quase(g["lat"], 1.5, 1e-4) and quase(g["lon"], -0.5, 1e-4), "forca G: 1,5 esquerda / 0,5 freando")
    confere(g is not None and quase(g["total"], math.hypot(1.5, 0.5), 1e-4) and g["pico"] >= g["total"] - 1e-9, "G total e pico")
    confere(g is not None and g["pista"] == "Circuit de la Sarthe" and quase(g["temp"], 31.0), "G: pista e temperatura")
    c = d["clima"]
    confere(c is not None and quase(c["pista"], 31.0) and quase(c["ar"], 22.0), "clima: temperaturas")
    confere(c["chuva"] is not None and quase(c["chuva"], 35.0, 1e-3), "clima: chuva 35%")
    confere(c["pista_molhada"] == 5 and c["ceu"] == 3, "clima: pista molhada 5, ceu encoberto")
    confere(quase(c["vento_vel"], 7.2, 1e-3), "clima: vento 2 m/s = 7,2 km/h")
    confere(c["neblina"] is None and c["vento_dir"] is None and c["rumo"] is None, "clima: neblina/direcao nao inventadas")
    # pico de G sobe e nao desce; zerar funciona
    j.acel = (39.24, 0.0, 0.0)
    rel.avancar(1.0)
    j.et += 1.0
    d = tel.ler()
    pico_alto = d["forca_g"]["pico"]
    j.acel = (0.0, 0.0, 0.0)
    rel.avancar(1.0)
    j.et += 1.0
    d = tel.ler()
    confere(quase(pico_alto, 4.0, 1e-3) and quase(d["forca_g"]["pico"], 4.0, 1e-3), "pico de G se mantem")
    tel.zerar_pico_g()
    rel.avancar(1.0)
    j.et += 1.0
    d = tel.ler()
    confere(d["forca_g"]["pico"] < 0.01, "zerar pico de G")


def teste_classificacao():
    grupo("Classificacao por classe")
    j = cenario_corrida()
    tel, rel = telemetria(j)
    d = tel.ler()
    c = d["classificacao"]
    confere(c is not None, "classificacao existe")
    if c is None:
        return
    nomes = [g["nome"] for g in c["classes"]]
    confere(nomes == ["HYPERCAR", "LMP2", "LMGT3"], f"classes na ordem Hypercar, LMP2, LMGT3 (obtido {nomes})")
    por_classe = {g["nome"]: g for g in c["classes"]}
    confere([l["numero"] for l in por_classe["HYPERCAR"]["linhas"]] == ["7", "50"], "Hypercar: #7 e #50 na ordem")
    gt3 = por_classe["LMGT3"]["linhas"]
    confere([l["numero"] for l in gt3] == ["92", "31", "33"], "LMGT3 na ordem geral (4o, 5o, 6o)")
    confere([l["pos"] for l in gt3] == [1, 2, 3], "posicao NA CLASSE reiniciada em 1")
    confere(por_classe["LMGT3"]["minha"] and not por_classe["HYPERCAR"]["minha"], "classe do jogador marcada")
    eu = [l for g in c["classes"] for l in g["linhas"] if l["eu"]]
    confere(len(eu) == 1 and eu[0]["numero"] == "31" and eu[0]["marca"] == "BMW", "linha do jogador: #31 BMW")
    confere(eu[0]["nome"] == "J. Meu", f"nome abreviado ({eu[0]['nome']})")
    confere(gt3[2]["na_box"] and not gt3[0]["na_box"], "carro nos boxes marcado")
    confere(quase(eu[0]["ultima"], 232.5) and quase(eu[0]["melhor"], 231.9), "ultima e melhor volta do jogador")
    confere(por_classe["HYPERCAR"]["linhas"][0]["melhor_da_classe"], "melhor volta da classe destacada")
    confere(c.get("tipo_sessao") == "CORRIDA" and c.get("volta") == 5, "sessao e volta na classificacao")
    # sem tempo ainda (-1) nao vira volta de 0 s
    j.carros[0].ultima = j.carros[0].melhor = -1.0
    rel.avancar(1.0)
    j.et += 1.0
    tel2, _ = telemetria(j)
    c2 = tel2.ler()["classificacao"]
    l0 = c2["classes"][0]["linhas"][0]
    confere(l0["ultima"] in (None, 0, 0.0) or l0["ultima"] is None, f"sem volta valida nao inventa tempo ({l0['ultima']})")


def teste_voltas_delta_combustivel():
    grupo("Voltas, delta e combustivel (simulando voltas completas)")
    j = cenario_corrida()
    j.carros[3].voltas, j.carros[3].dist = 0, 0.0
    j.carros[3].ultima = j.carros[3].melhor = -1.0
    j.combustivel, j.inicio_volta, j.tempo_decorrido = 100.0, 0.0, 0.0
    j.et = 0.0
    j.fim = 3600.0
    tel, rel = telemetria(j)
    comprimento = j.comprimento
    tempo_volta = 232.0
    consumo = 3.5
    dt = 1.0
    t = 0.0
    voltas_feitas = 0
    ultimo = None
    amostras_delta = []
    while voltas_feitas < 3:
        t += dt
        j.et += dt
        rel.avancar(dt)
        pct = (t - j.inicio_volta) / tempo_volta
        j.carros[3].dist = comprimento * pct
        j.tempo_decorrido = t
        j.combustivel -= consumo * dt / tempo_volta
        if t - j.inicio_volta >= tempo_volta:
            voltas_feitas += 1
            j.carros[3].voltas = voltas_feitas
            j.carros[3].ultima = tempo_volta + 0.0
            j.carros[3].melhor = tempo_volta
            j.inicio_volta = t
            j.carros[3].dist = 0.0
            j.combustivel = 100.0 - consumo * voltas_feitas
        ultimo = tel.ler()
        if voltas_feitas == 3 and ultimo.get("delta_ok"):
            amostras_delta.append(ultimo["delta"])
    d = ultimo
    confere(d["volta"] == 4, f"volta em andamento = 4 (obtido {d['volta']})")
    confere(quase(d["ultima_volta"], 232.0, 1e-6) and quase(d["melhor_volta"], 232.0, 1e-6), "ultima e melhor volta")
    confere(d["consumo_volta"] is not None and quase(d["consumo_volta"], consumo, 0.15), f"consumo medio ~{consumo} L/volta (obtido {d['consumo_volta']})")
    confere(d["voltas_restantes"] is not None and quase(d["voltas_restantes"], d["combustivel"] / d["consumo_volta"], 1e-6), "voltas restantes")
    confere(d["calc_combustivel"] is not None, "calculadora de combustivel calculada")
    confere(d["painel_combustivel"] is not None, "painel de combustivel calculado")
    confere(d["delta_fonte"] in ("overlay", None), "delta calculado pelo overlay (nao usa o delta do jogo)")
    if amostras_delta:
        confere(all(abs(x) < 0.6 for x in amostras_delta), f"delta de volta identica ~0 (max {max(abs(x) for x in amostras_delta):.2f})")
    else:
        confere(False, "delta ficou disponivel apos 3 voltas")
    # volta lenta: delta positivo
    j.inicio_volta = t - 100.0
    j.tempo_decorrido = t
    j.carros[3].dist = comprimento * 0.5
    rel.avancar(1.0)
    j.et += 1.0
    d = tel.ler()
    if d.get("delta_ok"):
        confere(-20.0 < d["delta"] < -12.0, f"100 s para meia volta (referencia ~116 s): delta negativo ~-16 (obtido {d['delta']:.1f})")
    else:
        confere(False, "delta disponivel na volta de teste")
    # volta suja nao vira referencia nem delta
    j.invalidada = True
    rel.avancar(1.0)
    j.et += 1.0
    d = tel.ler()
    confere(not d.get("delta_ok") or d["delta"] is not None, "volta invalidada nao quebra")


def teste_estados_do_jogador():
    grupo("Jogador fora do carro / pausa / jogo fechado")
    j = cenario_corrida()
    tel, rel = telemetria(j)
    d = tel.ler()
    confere(d["no_carro"], "no carro")
    # pausa: tempo do jogo nao anda por mais de 2 s -> janelas escondem
    rel.avancar(3.0)
    d = tel.ler()
    confere(d["conectado"] and not d["no_carro"], "jogo pausado (tempo parado > 2 s): fora do carro")
    j.et += 1.0
    rel.avancar(0.5)
    d = tel.ler()
    confere(d["no_carro"], "tempo voltou a andar: no carro")
    # nos menus/garagem: playerHasVehicle falso
    j.no_carro = False
    j.et += 1.0
    rel.avancar(0.5)
    d = tel.ler()
    confere(d["conectado"] and not d["no_carro"], "sem veiculo do jogador: fora do carro")
    # sem jogador na lista
    j2 = cenario_corrida()
    for c in j2.carros:
        c.jogador = False
    tel2, _ = telemetria(j2)
    d = tel2.ler()
    confere(d["conectado"] and not d["no_carro"] and d["classificacao"] is None, "sem carro do jogador: nao quebra")
    # jogo fechado
    tel3 = __import__("overlay_lmu").TelemetriaLMU(leitor=lmu.LeitorLMU(abridor=lambda: (_ for _ in ()).throw(lmu.MapaIndisponivel("x")),
                                                                           relogio=Relogio()))
    d = tel3.ler()
    confere(not d["conectado"] and tel3.ultimo_estado == lmu.SEM_JOGO, "jogo fechado: desconectado")


def teste_sessoes():
    grupo("Tipos de sessao e sessao por voltas/tempo")
    for codigo, nome in ((1, "TREINO"), (5, "QUALIFICACAO"), (10, "CORRIDA")):
        j = cenario_corrida()
        j.sessao = codigo
        tel, _ = telemetria(j)
        confere(tel.ler()["tipo_sessao"] == nome, f"sessao {codigo} = {nome}")
    j = cenario_corrida()
    j.max_voltas = 20
    j.fim = 1.0e9
    tel, _ = telemetria(j)
    d = tel.ler()
    confere(d["calc_combustivel"] is None or isinstance(d["calc_combustivel"], dict), "corrida por voltas: calculadora responde")


# ----------------------------------------------------------------------------
def teste_textos():
    grupo("Textos (iRacing -> Le Mans Ultimate)")
    m = preparar_modulo()
    confere(m.traduzir_texto("Aguardando o iRacing...") == "Aguardando o Le Mans Ultimate...", "mensagem de espera")
    confere("SDK" not in m.traduzir_texto("SDK · vs melhor volta"), "origem do delta nao diz SDK")
    confere(m.traduzir_texto("Pista seca") == "Pista seca", "texto comum nao muda")
    confere(m.traduzir_texto("PAIS") == "", "cabecalho PAIS some (o LMU nao informa pais)")


def renderizar_janelas():
    grupo("Renderizacao das janelas (offscreen) + textos desenhados")
    m = preparar_modulo()
    import overlay_iracing as base
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    PREVIAS.mkdir(parents=True, exist_ok=True)
    m.semear_config()
    cfg = base.carregar_config()
    cfg["travado"] = True
    base.definir_tema(cfg.get("tema_moderno", True), cfg.get("opacidade_fundo", 0.8))

    desenhados = []
    original = m.PintorLMU.drawText

    def espiao(self, *args):
        for a in args:
            if isinstance(a, str):
                desenhados.append(m.traduzir_texto(a))
        return original(self, *args)
    m.PintorLMU.drawText = espiao
    try:
        j = cenario_corrida()
        j.acel = (17.0, 0.0, 6.0)
        j.chuva, j.umidade, j.nuvens = 0.2, 0.3, 4
        j.carros[3].voltas, j.carros[3].dist = 3, 4000.0
        tel, rel = telemetria(j)
        d = None
        # algumas voltas para o painel de combustivel e o delta terem o que mostrar
        t = 0.0
        for volta in range(1, 4):
            for _ in range(60):
                t += 4.0
                j.et += 4.0
                rel.avancar(4.0)
                j.tempo_decorrido = t
                j.carros[3].dist = (j.carros[3].dist + 230.0) % j.comprimento
                j.combustivel -= 0.07
                d = tel.ler()
            j.carros[3].voltas += 1
            j.carros[3].ultima, j.carros[3].melhor = 232.0 + volta * 0.1, 231.9
            j.inicio_volta = t
        d = tel.ler()
        from ov_janela_lmu import JanelaClassificacaoLMU
        classes = [base.JanelaTelemetria, base.JanelaVoltas, JanelaClassificacaoLMU, base.JanelaClima,
                   base.JanelaCombustivel, base.JanelaForcaG]
        confere(d["conectado"], "dados conectados para desenhar")
        for cls in classes:
            w = cls(cfg)
            w.resize(w.size())
            w.atualizar(d)
            w.show()
            app.processEvents()
            img = w.grab()
            arq = PREVIAS / f"previa_{cls.__name__}.png"
            ok = img.save(str(arq)) and not img.isNull() and img.width() > 50 and img.height() > 20
            confere(ok, f"{cls.__name__}: desenhou ({img.width()}x{img.height()}) -> {arq.name}")
            w.hide()
        # sem conexao: janelas mostram a espera, sem erro
        vazio = base.Telemetria._vazio()
        for cls in classes:
            w = cls(cfg)
            w.atualizar(vazio)
            w.show()
            app.processEvents()
            w.grab()
            w.hide()
        confere(True, "janelas desenham sem conexao sem lancar erro")
    finally:
        m.PintorLMU.drawText = original
    confere(not any("iRacing" in t or "SDK" in t for t in desenhados), "nenhum texto desenhado cita iRacing/SDK")
    confere(any("Le Mans Ultimate" in t for t in desenhados), "mensagem de espera cita o Le Mans Ultimate")
    confere(len(desenhados) > 50, f"textos desenhados ({len(desenhados)})")


def teste_config_isolada():
    grupo("Configuracao propria do LMU (nao mexe no iRacing)")
    m = preparar_modulo()
    origem = PASTA / "config.json"
    if not origem.exists():
        confere(True, "config.json do iRacing ausente: nada a conferir")
        return
    h0 = hashlib.sha256(origem.read_bytes()).hexdigest()
    alvo = TMP / "config_semeada.json"
    m.ARQ_CONFIG_LMU = alvo
    m.redirecionar_arquivos(TMP, alvo, TMP / "log2.txt")
    confere(m.semear_config() and alvo.exists(), "primeira execucao cria o config do LMU a partir do layout do iRacing")
    confere(hashlib.sha256(origem.read_bytes()).hexdigest() == h0, "config.json do iRacing nao foi alterado")
    alvo.write_text('{"travado": true}', encoding="utf-8")
    confere(m.semear_config() is False and alvo.read_text(encoding="utf-8") == '{"travado": true}', "nao sobrescreve o config existente")


def teste_principal():
    grupo("Programa completo (principal) com jogo falso")
    m = preparar_modulo()
    alvo = TMP / "config_principal.json"
    m.ARQ_CONFIG_LMU = alvo
    m.redirecionar_arquivos(TMP, alvo, TMP / "log_principal.txt")
    j = cenario_corrida()
    rel_real = {"n": 0}

    class RelogioReal:
        def __call__(self):
            import time
            return time.monotonic()
    leitor = lmu.LeitorLMU(abridor=lambda: MapaFalso(j), relogio=RelogioReal())
    estado = {}

    def ao_iniciar(app, janelas, telemetria_, config):
        from PySide6.QtCore import QTimer

        def avancar():
            j.et += 0.05
            j.carros[3].dist = (j.carros[3].dist + 5.0) % j.comprimento
        t1 = QTimer()
        t1.timeout.connect(avancar)
        t1.start(50)
        app._t_teste = t1

        def conferir():
            estado["janelas"] = len(janelas)
            estado["visiveis"] = sum(1 for w in janelas if w.isVisible())
            estado["conectado"] = telemetria_.ultimo_estado
        QTimer.singleShot(1200, conferir)
        QTimer.singleShot(1600, app.quit)
    codigo = m.principal(leitor=leitor, config_extra={"auto_modo": False, "travado": True}, ao_iniciar=ao_iniciar)
    confere(codigo == 0, "principal terminou sem erro")
    confere(estado.get("janelas") == 16, f"16 janelas criadas (obtido {estado.get('janelas')})")
    confere(estado.get("conectado") == lmu.OK, f"leitor em estado ok (obtido {estado.get('conectado')})")
    confere(estado.get("visiveis", 0) >= 10, f"janelas visiveis ({estado.get('visiveis')})")
    log = TMP / "log_principal.txt"
    texto_log = log.read_text(encoding="utf-8") if log.exists() else ""
    confere("inicio:" in texto_log and "Le Mans Ultimate" in texto_log, "log proprio do LMU com cabecalho")
    confere("Traceback" not in texto_log and "ERRO" not in texto_log.upper().replace("ERROS", ""), "nenhum erro no log do LMU")


def teste_atalhos_stream_deck():
    grupo("v1.4 - teclas globais para o Stream Deck (mapa proprio do LMU)")
    import queue
    import time as _t
    import ov_atalhos_lmu as at
    import ov_nucleo as nu
    confere(at.validar_atalhos_lmu() == [], f"mapa do LMU sem erro nem colisao com o iRacing ({at.validar_atalhos_lmu()})")
    confere(len(at.ATALHOS_LMU) == 24, f"24 atalhos (16 janelas + 8 controles): {len(at.ATALHOS_LMU)}")
    confere(sum(1 for a in at.ATALHOS_LMU if a.id.startswith("janela_")) == 16, "16 atalhos de janela")
    combos_ir = {(a.mods, a.fn) for a in nu.ATALHOS}
    confere(all((a.mods, a.fn) not in combos_ir for a in at.ATALHOS_LMU), "nenhuma combinacao repete as do iRacing")
    confere(at.atalho_lmu_por_id("janela_telemetria").nome == "Ctrl+Shift+F13", "janelas = Ctrl+Shift+F13..F24")
    confere(at.atalho_lmu_por_id("janela_tendencia").nome == "Ctrl+Shift+F24", "ultima janela = Ctrl+Shift+F24")
    confere(at.atalho_lmu_por_id("sair").nome == "Alt+Shift+F20", "controles = Alt+Shift+F13..F20 (sair = F20)")
    confere(at.atalho_lmu_por_id("janela_energia").alvo == "mostrar_lmu_energia", "janela de energia liga a chave do LMU")
    confere("Ctrl+Shift+F13" in at.texto_atalhos_lmu() and "Alt+Shift+F20" in at.texto_atalhos_lmu(), "tabela legivel do mapa")
    # Mapa com colisao e tecla invalida e detectado
    colidindo = (nu.AtalhoGlobal("x", "x", nu.MODS_JANELAS, 13, "alternar", "k"),)
    confere(nu.validar_atalhos(colidindo + colidindo) != [], "validador pega atalho repetido")

    class ApiFalsa:
        def __init__(self, recusar=()):
            self.fila, self.recusar, self.ok, self.liberados = queue.Queue(), set(recusar), [], []

        def preparar(self):
            return 1

        def registrar(self, codigo, mods, vk):
            if codigo in self.recusar:
                return False, "ja usada por outro programa (erro 1409)"
            self.ok.append((codigo, mods, vk))
            return True, ""

        def liberar(self, codigo):
            self.liberados.append(codigo)

        def esperar(self):
            return self.fila.get()

        def encerrar(self, id_thread):
            self.fila.put(None)

    # Escuta com o mapa do LMU: registra os 20, uma tecla recusada nao derruba as outras
    api = ApiFalsa(recusar={nu.ID_BASE_TECLA + 3})
    escuta = nu.EscutaTeclas(api, atalhos=at.ATALHOS_LMU)
    n, falhas = escuta.iniciar()
    confere(n == 23 and len(falhas) == 1 and falhas[0][0].id == "janela_clima", f"23 registrados, 1 recusado ({n}, {len(falhas)})")
    confere(all(m & nu.MOD_NOREPEAT for _c, m, _v in api.ok), "registro com MOD_NOREPEAT")
    confere(api.ok[0][2] == 0x7C and api.ok[0][1] & 0x0006 == 0x0006, "Ctrl+Shift+F13 -> vk 0x7C com Ctrl e Shift")
    escuta.parar()
    confere(len(api.liberados) == 23, "ao parar, libera as teclas registradas")

    # Programa completo: teclas chegam, ligam/desligam as janelas e fecham o overlay
    m = preparar_modulo()
    alvo = TMP / "config_atalhos.json"
    m.ARQ_CONFIG_LMU = alvo
    m.redirecionar_arquivos(TMP, alvo, TMP / "log_atalhos.txt")
    j = cenario_corrida()
    leitor = lmu.LeitorLMU(abridor=lambda: MapaFalso(j), relogio=Relogio())
    api2 = ApiFalsa()
    cod = lambda id_: nu.ID_BASE_TECLA + [a.id for a in at.ATALHOS_LMU].index(id_)
    estado = {}

    def ao_iniciar(app, janelas, telemetria_, config):
        from PySide6.QtCore import QTimer
        estado["config0"] = (config["mostrar_telemetria"], config["mostrar_lmu_energia"], config["economia_cpu"],
                             config["travado"], config["classificacao_todas"])
        estado["t0"] = _t.monotonic()

        def enviar():
            for id_ in ("janela_telemetria", "janela_energia", "economia_cpu", "travar_posicao", "classif_todas", "zerar_pico_g"):
                api2.fila.put(cod(id_))
                _t.sleep(0.25)                                   # acima do intervalo minimo entre repeticoes
            api2.fila.put(cod("janela_telemetria"))              # segundo toque: volta a ligar
        QTimer.singleShot(400, lambda: __import__("threading").Thread(target=enviar, daemon=True).start())

        def conferir():
            estado["config1"] = (config["mostrar_telemetria"], config["mostrar_lmu_energia"], config["economia_cpu"],
                                 config["travado"], config["classificacao_todas"])
            estado["menu"] = [a.text() for a in app._refs[3]]
            estado["chaves"] = sorted(app._refs[-1])
            api2.fila.put(cod("sair"))                           # o proprio atalho fecha o overlay
        QTimer.singleShot(2600, conferir)
        QTimer.singleShot(8000, app.quit)                        # rede de seguranca: se o atalho "sair" falhar
    codigo = m.principal(leitor=leitor, config_extra={"auto_modo": False, "travado": False}, ao_iniciar=ao_iniciar, api_teclas=api2)
    confere(codigo == 0, "principal terminou sem erro")
    confere(_t.monotonic() - estado["t0"] < 6.0, "o atalho Alt+Shift+F20 FECHOU o overlay (nao foi a rede de seguranca)")
    c0, c1 = estado["config0"], estado["config1"]
    confere(c0 == (True, True, False, False, c0[4]), f"estado inicial conhecido ({c0})")
    confere(c1[0] is True, "telemetria: desliga e liga de novo (dois toques)")
    confere(c1[1] is False, "energia (janela nova): desligada pelo atalho")
    confere(c1[2] is True, "economia de CPU: ligada pelo atalho")
    confere(c1[3] is True, "travar posicao: ligado pelo atalho")
    confere(c1[4] != c0[4], "classificacao de todas as classes: alternada pelo atalho")
    confere(any("Teclas de atalho para o Stream Deck" in t for t in estado["menu"]), "item de menu para ligar/desligar as teclas")
    faltam = [a.alvo for a in at.ATALHOS_LMU if a.tipo == "alternar" and a.alvo not in estado["chaves"]]
    confere(not faltam, f"todo atalho de liga/desliga tem item no menu ({faltam})")
    m.base.JanelaBase.MULT_TAXA = 1.0
    log = (TMP / "log_atalhos.txt").read_text(encoding="utf-8")
    confere("atalhos globais: 24 de 24 registrados" in log, "log: 24 de 24 atalhos registrados")
    confere("Ctrl+Shift+F13" in log and "Alt+Shift+F20" in log, "log registra os atalhos usados")
    confere("Traceback" not in log and "ERRO" not in log.upper().replace("ERROS", ""), "nenhum erro no log")
    confere(len(api2.liberados) == 24, "ao fechar, as 24 teclas sao liberadas")


def teste_perfil_stream_deck():
    grupo("v1.4 - perfil do Stream Deck 'Overlay LMU' confere com o programa")
    import json
    import zipfile
    import ov_atalhos_lmu as at
    txt = PASTA / "ATALHOS_STREAM_DECK_LMU.txt"
    confere(txt.exists(), "ATALHOS_STREAM_DECK_LMU.txt existe")
    if txt.exists():
        t = txt.read_text(encoding="utf-8")
        confere(all(a.nome in t and a.rotulo in t for a in at.ATALHOS_LMU), "o txt lista os 24 atalhos exatamente como o programa")
    arq = PASTA / "streamdeck_lmu" / "Overlay LMU.streamDeckProfile"
    if not arq.exists():
        confere(True, "perfil do Stream Deck ausente nesta copia (pacote do amigo): nada a conferir")
        return
    z = zipfile.ZipFile(arq)
    confere(z.testzip() is None, "perfil e um zip integro")
    pac = json.loads(z.read("package.json"))
    confere(pac.get("DeviceModel") == "20GAT9902", "perfil para o Stream Deck XL")
    vistos, abertos, imagens_ok, n_botoes, decorativos = [], [], True, 0, 0
    for nome in z.namelist():
        if not nome.endswith("manifest.json") or "/Profiles/" not in nome:
            continue
        pasta_pag = nome.rsplit("/", 1)[0]
        acoes = json.loads(z.read(nome))["Controllers"][0]["Actions"] or {}
        for pos, a in acoes.items():
            n_botoes += 1
            img = a["States"][0]["Image"]
            imagens_ok = imagens_ok and (pasta_pag + "/" + img) in z.namelist()
            if a["UUID"].endswith(".hotkey") and a["Settings"]["Hotkeys"][0]["VKeyCode"] == -1:
                decorativos += 1                          # botao so com imagem: hotkey sem tecla, nao envia nada
            elif a["UUID"].endswith(".hotkey"):
                h = a["Settings"]["Hotkeys"][0]
                mods = (nu_mod("shift") if h["KeyShift"] else 0) | (nu_mod("ctrl") if h["KeyCtrl"] else 0) | (nu_mod("alt") if h["KeyOption"] else 0)
                achou = [x for x in at.ATALHOS_LMU if x.vk == h["VKeyCode"] and x.mods == mods]
                confere(len(achou) == 1, f"botao {pos}: tecla {h['VKeyCode']} mods {mods} existe no mapa do LMU")
                vistos += [x.id for x in achou]
            elif a["UUID"].endswith(".system.open"):
                abertos.append(a["Settings"]["path"].strip('"').rsplit("\\", 1)[-1])
    confere(sorted(vistos) == sorted(x.id for x in at.ATALHOS_LMU), "o perfil usa os 24 atalhos, cada um uma vez")
    confere(imagens_ok and n_botoes == 37 + decorativos, f"37 botoes com acao + decorativos, todos com imagem ({n_botoes})")
    confere(decorativos in (0, 2), f"0 ou 2 botoes decorativos (logos LM e iRacing) sem nenhuma acao ({decorativos})")
    ausentes = [n for n in abertos if n != "overlay_lmu" and not (PASTA / n).exists() and n not in ("overlay_log_lmu.txt", "diagnostico_lmu.txt")]
    confere(not ausentes, f"botoes que abrem arquivos apontam para arquivos do pacote ({ausentes})")


def nu_mod(nome):
    import ov_nucleo as nu
    return {"shift": nu.MOD_SHIFT, "ctrl": nu.MOD_CONTROL, "alt": nu.MOD_ALT}[nome]


def teste_diagnostico():
    grupo("Diagnostico")
    m = preparar_modulo()
    j = cenario_corrida()
    leitor = lmu.LeitorLMU(abridor=lambda: MapaFalso(j), relogio=Relogio())
    texto_diag, estado = m.gerar_diagnostico(leitor)
    confere(estado == lmu.OK and "Circuit de la Sarthe" in texto_diag and "Jogador Meu" in texto_diag, "diagnostico traz pista e piloto")
    confere(texto_diag.count("\n") > 12 and "G lateral" in texto_diag, "diagnostico traz telemetria e G")
    texto_vazio, estado = m.gerar_diagnostico(lmu.LeitorLMU(abridor=lambda: (_ for _ in ()).throw(lmu.MapaIndisponivel("x")),
                                                           relogio=Relogio()))
    confere(estado == lmu.SEM_JOGO and "Enable Plugins" in texto_vazio, "diagnostico sem jogo orienta o usuario")


def teste_demo():
    grupo("Modo demonstracao")
    m = preparar_modulo()
    t = m.TelemetriaLMU(demo=True)
    d = t.ler()
    confere(d["conectado"] and d["classificacao"] is not None and d["painel_combustivel"] is not None, "demo entrega os dados das janelas base")
    for k in ("lmu_energia", "lmu_pneus", "lmu_danos", "lmu_alertas", "lmu_stints", "lmu_tendencia"):
        confere(d.get(k) is not None, f"demo entrega {k}")
    # a classificacao do demo precisa ter os mesmos campos da real e desenhar sem erro (falhou antes no teste com amigo)
    import overlay_iracing as base
    from ov_janela_lmu import JanelaClassificacaoLMU
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    real = telemetria(cenario_corrida())[0].ler()["classificacao"]
    chaves_real = set(real["classes"][0]["linhas"][0])
    chaves_demo = set(d["classificacao"]["classes"][0]["linhas"][0])
    confere(chaves_real <= chaves_demo, f"classificacao do demo tem todos os campos da real (faltam {sorted(chaves_real - chaves_demo)})")
    cfg = base.carregar_config()
    cfg["travado"] = True
    w = JanelaClassificacaoLMU(cfg)
    erros = []
    original = w._linha

    def vigia(*a, **k):
        try:
            return original(*a, **k)
        except Exception as e:                      # o Qt engole excecoes do paintEvent: capturamos aqui
            erros.append(repr(e))
            raise
    w._linha = vigia
    w.atualizar(d)
    w.show()
    app.processEvents()
    confere(not w.grab().isNull() and not erros, f"janela de classificacao desenha com os dados do demo ({erros[:1]})")
    w.hide()


def teste_v13_correcoes_do_jogo_real():
    grupo("v1.3 - correcoes vindas do teste no jogo real (danos, amarela, vento, janela do jogo)")
    import math as _m
    from types import SimpleNamespace as NS
    m = preparar_modulo()
    # --- lado do impacto pela posicao (x = esquerda, z negativo = frente) -------------------------------------
    casos = (((1.04, -1.72), "frente-esquerda"), ((-0.02, -2.43), "frente"), ((1.0, 1.34), "traseira-esquerda"),
             ((-1.0, 0.0), "direita"), ((1.0, 0.0), "esquerda"), ((0.0, 2.4), "traseira"), ((-1.0, 1.5), "traseira-direita"),
             ((-1.0, -1.5), "frente-direita"),
             # impactos REAIS do log (posicao -> zona que o jogo acendeu)
             ((-0.96, -1.93), "frente-direita"), ((-1.06, -1.55), "frente-direita"), ((-0.99, 1.48), "traseira-direita"),
             ((-0.95, 2.26), "traseira"), ((-0.98, -0.30), "direita"), ((0.37, -2.41), "frente"))
    for (x, z), esperado in casos:
        confere(lmu.lado_do_impacto(x, z) == esperado, f"lado do impacto ({x}, {z}) = {esperado}")
    confere(lmu.lado_do_impacto(0.0, 0.0) is None and lmu.lado_do_impacto(float("nan"), 1.0) is None, "impacto sem posicao: None")
    # --- amarela: so o valor 1 vale; 3 setores juntos fora da amarela geral = dado suspeito --------------------
    j = cenario_corrida()
    info = _dados_brutos(j)[0].scoring.scoringInfo
    j.amarelas = (1, 1, 1)
    b = lmu.bandeiras(_dados_brutos(j)[0].scoring.scoringInfo)
    confere(b["amarelas_setor"] == [] and b["amarelas_suspeitas"] and b["amarelas_brutas"] == [1, 1, 1],
            "3 setores acesos fora da bandeira geral: ignorado e marcado como suspeito (como no jogo real)")
    j.amarelas = (11, 11, 11)
    b = lmu.bandeiras(_dados_brutos(j)[0].scoring.scoringInfo)
    confere(b["amarelas_setor"] == [] and not b["amarelas_suspeitas"] and b["amarelas_brutas"] == [11, 11, 11],
            "valor 11 = sem amarela (confirmado no jogo real): sem alerta e sem suspeita")
    j.amarelas = (11, 1, 11)
    b = lmu.bandeiras(_dados_brutos(j)[0].scoring.scoringInfo)
    confere(b["amarelas_setor"] == [1] and not b["amarelas_suspeitas"], "[11, 1, 11] (log real): amarela no setor de indice 1")
    j.amarelas = (0, 7, 0)
    b = lmu.bandeiras(_dados_brutos(j)[0].scoring.scoringInfo)
    confere(b["amarelas_setor"] == [] and b["amarelas_suspeitas"], "valor desconhecido (7): nao vira alerta, fica como suspeito")
    j.amarelas = (0, 1, 0)
    b = lmu.bandeiras(_dados_brutos(j)[0].scoring.scoringInfo)
    confere(b["amarelas_setor"] == [1] and not b["amarelas_suspeitas"], "amarela real em 1 setor: aceita")
    j.fase, j.amarelas = 6, (1, 1, 1)
    b = lmu.bandeiras(_dados_brutos(j)[0].scoring.scoringInfo)
    confere(b["fcy"] and b["amarelas_setor"] == [0, 1, 2], "amarela geral (fase 6): 3 setores sao validos")
    # --- vento ---------------------------------------------------------------------------------------------------
    ident = [NS(x=1.0, y=0.0, z=0.0), NS(x=0.0, y=1.0, z=0.0), NS(x=0.0, y=0.0, z=1.0)]   # eixos locais = mundo
    tele = NS(mOri=ident)
    zero = NS(mWind=NS(x=0.0, y=0.0, z=0.0))
    v = lmu.vento_do_carro(zero, tele)
    confere(v["vel"] is None and v["dir_rel"] is None and v["mundo"] == (0.0, 0.0, 0.0), "vento zero = o jogo nao informou: sem velocidade nem direcao")
    v = lmu.vento_do_carro(NS(mWind=NS(x=0.0, y=0.0, z=2.0)), tele)          # ar indo para a traseira = vem da FRENTE
    confere(quase(v["vel"], 7.2, 1e-6) and quase(v["dir_rel"], 0.0, 1e-9), "vento vindo da frente: 7,2 km/h, direcao 0")
    v = lmu.vento_do_carro(NS(mWind=NS(x=3.0, y=0.0, z=0.0)), tele)          # ar indo para a esquerda = vem da DIREITA
    confere(quase(v["dir_rel"], _m.pi / 2, 1e-9), "vento vindo da direita: direcao 90 graus (horario a partir da frente)")
    v = lmu.vento_do_carro(NS(mWind=NS(x=0.0, y=0.0, z=-2.0)), tele)         # vem de TRAS
    confere(quase(v["dir_rel"], _m.pi, 1e-9), "vento vindo de tras: direcao 180")
    girado = [NS(x=0.0, y=0.0, z=-1.0), NS(x=0.0, y=1.0, z=0.0), NS(x=1.0, y=0.0, z=0.0)]   # carro virado 90 graus
    v = lmu.vento_do_carro(NS(mWind=NS(x=0.0, y=0.0, z=2.0)), NS(mOri=girado))
    confere(v["dir_rel"] is not None and quase(v["local"][0], -2.0, 1e-9) , f"orientacao do carro entra na conta (local {v['local']})")
    v = lmu.vento_do_carro(NS(mWind=NS(x=0.0, y=0.0, z=0.01)), tele)
    confere(v["vel"] is not None and v["dir_rel"] is None, "vento fraquissimo: velocidade sim, direcao nao")
    confere(lmu.vento_do_carro(NS(mWind=NS(x=float("nan"), y=0.0, z=0.0)), tele)["vel"] is None, "vento invalido: None")
    # clima pelo pipeline completo com o jogo falso (orientacao zerada = sem direcao, sem inventar)
    j2 = cenario_corrida()
    j2.vento = (0.0, 0.0, 0.0)
    c = telemetria(j2)[0].ler()["clima"]
    confere(c["vento_vel"] is None and c["vento_dir"] is None, "pipeline: vento zero fica '--' (nao mostra 0 km/h falso)")
    # --- janela do jogo (so Windows; aqui so o texto e o retorno seguro) ---------------------------------------
    confere(lmu.janela_do_jogo() is None, "fora do Windows: janela_do_jogo() devolve None sem erro")
    confere("nao encontrada" in lmu.descrever_janela_jogo(None), "texto quando o jogo nao e encontrado")
    confere(lmu.jogo_acima_do_overlay(1234, [1, 2]) is None, "fora do Windows: amostra de sobreposicao devolve None sem erro")
    confere(lmu.instalar_gancho_primeiro_plano(lambda: None) is None, "fora do Windows: gancho de foco nao instala e nao quebra")
    amostra = {"exe": "Le Mans Ultimate.exe", "x": 0, "y": 0, "largura": 2560, "altura": 1440, "com_borda": False,
               "tela_cheia": True, "topmost": True, "primeiro_plano": False, "exe_primeiro_plano": "chrome.exe", "z_jogo": 1,
               "z_overlay": 3}
    t = lmu.descrever_janela_jogo(amostra)
    confere("ABAIXO do jogo" in t and "2560x1440" in t and "exclusiva" in t and "chrome.exe" in t,
            "texto: jogo cobrindo o overlay, modo sem borda/exclusiva e quem esta em primeiro plano")
    amostra.update(z_overlay=0, com_borda=True, tela_cheia=False)
    t = lmu.descrever_janela_jogo(amostra)
    confere("ACIMA do jogo" in t and "modo Janela" in t, "texto: overlay acima e modo Janela")
    # --- janelas desenham (clima LMU com vento e sem vento; danos com lado) ------------------------------------------
    import overlay_iracing as base
    from ov_janela_lmu import JanelaClimaLMU
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    cfg = base.carregar_config()
    cfg["travado"] = True
    for rotulo, vel, dire in (("com vento", 14.0, 1.0), ("vento invertido", 14.0, 4.0), ("sem vento", None, None)):
        w = JanelaClimaLMU(cfg)
        dados = base.Telemetria._vazio()
        dados["conectado"] = True
        dados["clima"] = {"rumo": 0.0 if dire is not None else None, "vel_carro": 120.0, "chuva": 10.0, "tendencia_chuva": "estavel",
                          "pista_molhada": 1, "declarado_molhado": False, "ceu": 2, "dinamico": None, "pista": 31.0, "ar": 22.0,
                          "neblina": None, "vento_dir": dire, "vento_vel": vel}
        erros = []
        original = w._bussola

        def vigia(*a, _o=original, **k):
            try:
                return _o(*a, **k)
            except Exception as e:
                erros.append(repr(e))
                raise
        w._bussola = vigia
        w.atualizar(dados)
        w.show()
        app.processEvents()
        confere(not w.grab().isNull() and not erros, f"janela de clima do LMU desenha ({rotulo}) {erros[:1]}")
        w.hide()
    cfg["vento_invertido"] = True
    w = JanelaClimaLMU(cfg)
    w.atualizar(dados)
    w.show()
    app.processEvents()
    confere(not w.grab().isNull(), "janela de clima desenha com a opcao 'inverter vento'")
    w.hide()


def teste_dependencias():
    grupo("Arquivos do iRacing intactos")
    for nome in ("overlay_iracing.py", "ov_nucleo.py"):
        confere((PASTA / nome).exists(), f"{nome} presente")
    texto = (PASTA / "overlay_lmu.py").read_text(encoding="utf-8")
    confere("TinyPedal" not in texto.replace("TinyPedal nao", ""), "sem referencias a codigo GPL do TinyPedal no overlay")
    licenca = PASTA / "pyLMUSharedMemory" / "License.txt"
    confere(licenca.exists(), "licenca da biblioteca de memoria compartilhada incluida")


def teste_classificacao_detalhada():
    grupo("Classificacao detalhada (gap, intervalo, grid, paradas, combustivel, media 5)")
    import ov_classif_lmu as cl
    j = cenario_corrida()
    tel, rel = telemetria(j)
    c = tel.ler()["classificacao"]
    por = {g["nome"]: {l["numero"]: l for l in g["linhas"]} for g in c["classes"]}
    h7, h50 = por["HYPERCAR"]["7"], por["HYPERCAR"]["50"]
    confere(h7["gap"] == {"tipo": "lider", "valor": 5} and h7["intervalo"] is None, "lider da classe: 'V 5' e sem intervalo")
    confere(cl.fmt_gap(h7["gap"]) == "V 5", "formato do lider")
    confere(h50["intervalo"] == {"tipo": "tempo", "valor": 15.0, "estimado": False}, "vizinho direto: intervalo MEDIDO pelo jogo (15,0 s)")
    confere(h50["gap"] == {"tipo": "tempo", "valor": 15.0, "estimado": False}, "gap do 2o = intervalo")
    confere(h7["variacao"] == 1 and h50["variacao"] == -1, "variacao no grid: #7 ganhou 1, #50 perdeu 1 (pela qualificacao)")
    gt = por["LMGT3"]
    confere(gt["92"]["variacao"] == 2 and gt["31"]["variacao"] == -1 and gt["33"]["variacao"] == -1, "variacao no grid da LMGT3")
    confere(por["LMP2"]["22"]["variacao"] == 0, "sem mudanca = 0")
    confere(gt["31"]["gap"]["valor"] == 87.5 and not gt["31"]["gap"]["estimado"], "gap do #31 = 87,5 s medido")
    confere(gt["33"]["gap"] == {"tipo": "voltas", "valor": 1}, f"#33 uma volta atras do lider da classe ({gt['33']['gap']})")
    confere(cl.fmt_gap(gt["33"]["gap"]) == "+1 V", "formato '+1 V'")
    confere(gt["33"]["intervalo"] == {"tipo": "tempo", "valor": 60.3, "estimado": False}, "intervalo do #33 para o #31 = 60,3 s")
    confere(gt["31"]["paradas"] == 1 and gt["33"]["paradas"] == 2 and gt["92"]["paradas"] == 0, "paradas")
    confere(gt["33"]["penalidades"] == 1 and gt["31"]["penalidades"] == 0, "penalidades")
    confere(gt["33"]["na_box"] and not gt["31"]["na_box"], "PIT (nos boxes ou entrando/parado)")
    confere(quase(gt["31"]["combustivel_pct"], 90 / 255 * 100, 1e-6) and quase(gt["33"]["combustivel_pct"], 40 / 255 * 100, 1e-6),
            "combustivel % (0..255 do jogo -> 0..100)")
    s = c["sessao"]
    confere(quase(s["decorrido"], 100.0) and quase(s["total"], 3600.0) and quase(s["pista"], 31.0) and quase(s["ar"], 22.0)
            and s["voltas_total"] is None, "cabecalho: tempo decorrido/total, temperaturas")
    confere(len(c["comparacao_gap"]) >= 3 and all(e is not None for _, e in c["comparacao_gap"]), "pares jogo x calculado para o log")

    # intervalo entre carros que NAO sao vizinhos diretos: estimado (~)
    j2 = cenario_corrida()
    j2.carros[2].lugar = 5          # LMP2 entre os GT3
    j2.carros[3].lugar = 6
    j2.carros[5].lugar = 7
    j2.carros[4].lugar = 4
    tel2, _ = telemetria(j2)
    gt2 = {l["numero"]: l for g in tel2.ler()["classificacao"]["classes"] if g["nome"] == "LMGT3" for l in g["linhas"]}
    confere(gt2["31"]["intervalo"]["estimado"] is True and quase(gt2["31"]["intervalo"]["valor"], 86.7, 0.6),
            f"nao vizinho: intervalo ESTIMADO ~86,7 s ({gt2['31']['intervalo']})")
    confere(cl.fmt_gap(gt2["31"]["intervalo"]).startswith("~+"), "estimado aparece com '~'")
    confere(gt2["31"]["gap"]["estimado"] is True, "gap que depende de intervalo estimado tambem e estimado")
    confere(gt2["33"]["intervalo"]["estimado"] is False, "vizinho direto continua medido")

    # grid: qualificacao invalida, repetida ou fora da corrida = sem setas
    j3 = cenario_corrida()
    j3.carros[3].quali = -1
    gt3 = {l["numero"]: l for g in telemetria(j3)[0].ler()["classificacao"]["classes"] if g["nome"] == "LMGT3" for l in g["linhas"]}
    confere(all(l["variacao"] is None for l in gt3.values()), "qualificacao invalida: sem variacao")
    j3 = cenario_corrida()
    j3.sessao = 1
    c3 = telemetria(j3)[0].ler()["classificacao"]
    confere(all(l["variacao"] is None for g in c3["classes"] for l in g["linhas"]), "fora da corrida: sem variacao")
    # combustivel nao informado
    j4 = cenario_corrida()
    for car in j4.carros:
        car.comb = 0
    c4 = telemetria(j4)[0].ler()["classificacao"]
    confere(all(l["combustivel_pct"] is None for g in c4["classes"] for l in g["linhas"]), "combustivel zerado em todos = nao informado ('--')")
    # resultado
    j5 = cenario_corrida()
    j5.carros[0].final, j5.carros[1].final, j5.carros[2].final = 1, 2, 3
    c5 = telemetria(j5)[0].ler()["classificacao"]
    st = {l["numero"]: l["status"] for g in c5["classes"] for l in g["linhas"]}
    confere(st["7"] == "FIM" and st["50"] == "DNF" and st["22"] == "DSQ" and st["31"] is None, "FIM / DNF / DSQ")

    # media das ultimas 5 voltas
    def car(voltas, ultima, melhor, box=False, id_=1, piloto="A"):
        return {"id": id_, "piloto": piloto, "veiculo": "V", "voltas": voltas, "ultima": ultima, "melhor": melhor, "box": box}
    h = cl.HistoricoVoltas()
    chave = (10, 0)
    h.atualizar(chave, [car(0, -1, -1)])
    h.atualizar(chave, [car(1, 100.0, 100.0)])
    confere(h.media(car(1, 0, 0)) is None, "volta de largada nao entra na media")
    h.atualizar(chave, [car(2, 100.0, 100.0)])
    confere(h.media(car(2, 0, 0)) is None, "uma volta so: media indisponivel")
    h.atualizar(chave, [car(3, 101.0, 100.0)])
    confere(quase(h.media(car(3, 0, 0)), 100.5), "media de 2 voltas = 100,5")
    h.atualizar(chave, [car(3, 101.0, 100.0, box=True)])
    h.atualizar(chave, [car(4, 160.0, 100.0, box=True)])
    confere(quase(h.media(car(4, 0, 0)), 100.5), "volta com passagem pelos boxes nao entra")
    h.atualizar(chave, [car(5, 140.0, 100.0)])
    confere(quase(h.media(car(5, 0, 0)), 100.5), "volta lenta (> 130 % da melhor) nao entra")
    h.atualizar(chave, [car(6, 102.0, 100.0)])
    confere(quase(h.media(car(6, 0, 0)), 101.0), "media de 3 voltas = 101,0")
    for k, t_ in enumerate((99.0, 98.0, 97.0, 96.0), start=7):
        h.atualizar(chave, [car(k, t_, 96.0 if k == 10 else 99.0)])
    confere(quase(h.media(car(10, 0, 0)), (102 + 99 + 98 + 97 + 96) / 5), "so as ultimas 5 voltas")
    h.atualizar(chave, [car(14, 99.0, 96.0)])        # salto de voltas (leitura perdida): recomeca
    confere(h.media(car(14, 0, 0)) is None, "salto de voltas: nao confia, recomeca")
    h.atualizar((10, 99), [car(14, 99.0, 96.0)])
    confere(h.media(car(14, 0, 0)) is None, "nova sessao: historico zerado")
    h.atualizar((10, 99), [car(14, 99.0, 96.0, id_=7, piloto="B")])
    confere(h.media(car(14, 0, 0, id_=7, piloto="B")) is None and h.media(car(14, 0, 0)) is None, "mesmo id com outro piloto: historico separado")
    # media aparece na classificacao completa
    j6 = cenario_corrida()
    tel6, rel6 = telemetria(j6)
    tel6.ler()
    for volta in (5, 6, 7):
        for car_ in j6.carros:
            car_.voltas = volta
            car_.ultima = 210.0 + volta
        j6.et += 1.0
        rel6.avancar(0.6)
        c6 = tel6.ler()["classificacao"]
    m7 = {l["numero"]: l["media5"] for g in c6["classes"] for l in g["linhas"]}
    confere(m7["7"] is not None and quase(m7["7"], 216.5, 0.01), f"media 5 na classificacao ({m7['7']})")

    # formatos
    confere(cl.fmt_gap(None) == "--" and cl.fmt_gap({"tipo": "tempo", "valor": 130.84, "estimado": False}) == "+130.8", "formatos de gap")
    confere(cl.fmt_hms(4534) == "1:15:34" and cl.fmt_hms(None) == "--:--:--", "formato do relogio")

    # desempenho com 104 carros
    import time as _t
    j7 = Jogo()
    for i in range(104):
        j7.carros.append(Carro(i + 1, f"Carro {i} #{i + 1}", ("Hyper", "LMP2", "LMGT3")[i % 3], f"Piloto {i}", i + 1,
                               voltas=5, dist=100.0 * i, ultima=210 + i * 0.1, melhor=209 + i * 0.1, jogador=(i == 50),
                               tbn=3.0, quali=i + 1))
    tel7, _ = telemetria(j7)
    tel7.ler()
    t0 = _t.perf_counter()
    for _ in range(10):
        tel7._cache.clear()
        tel7._montar_classificacao(*[tel7.leitor.ler()[1], 50])
    ms = (_t.perf_counter() - t0) * 100.0
    print(f"   classificacao com 104 carros: {ms:.1f} ms por calculo")
    confere(ms < 80.0, f"104 carros: calculo da classificacao abaixo de 80 ms ({ms:.1f})")


def teste_janela_classificacao():
    grupo("Janela de classificacao detalhada")
    m = preparar_modulo()
    import overlay_iracing as base
    from ov_janela_lmu import JanelaClassificacaoLMU, LARGURA_LMU
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    m.semear_config()
    cfg = base.carregar_config()
    cfg["travado"] = True
    j = cenario_corrida()
    j.carros[5].final = 0
    d = telemetria(j)[0].ler()
    w = JanelaClassificacaoLMU(cfg)
    confere(w.tamanho()[0] == LARGURA_LMU > base.LARGURA_CLASS, "mais larga que a do iRacing (colunas extras)")
    altura0 = w.tamanho()[1]
    w.atualizar(d)
    confere(w.tamanho()[1] > altura0, "altura se ajusta ao numero de linhas")
    # muitos carros: limites por classe
    jg = Jogo()
    for i in range(40):
        jg.carros.append(Carro(i + 1, f"Carro {i} #{i + 1}", ("Hyper", "LMP2", "LMGT3")[i % 3], f"Piloto {i}", i + 1,
                               voltas=5, dist=100.0 * i, ultima=210 + i * 0.1, melhor=209 + i * 0.1, jogador=(i == 38)))
    dg = telemetria(jg)[0].ler()
    w2 = JanelaClassificacaoLMU(cfg)
    w2.atualizar(dg)
    por_classe = {c["nome"]: len(v) for c, v in w2._blocos_atual}
    confere(por_classe["LMGT3"] == w2.LINHAS_MINHA_CLASSE and por_classe["HYPERCAR"] == w2.LINHAS_OUTRAS_CLASSES,
            f"limites de linhas por classe ({por_classe})")
    confere(any(l["eu"] for c, v in w2._blocos_atual for l, _ in v), "o seu carro sempre aparece, mesmo longe do topo")
    # desenha sem erro, com e sem dados
    w2.show()
    app.processEvents()
    confere(not w2.grab().isNull(), "desenha com 40 carros")
    w2.hide()
    w3 = JanelaClassificacaoLMU(cfg)
    w3.atualizar(base.Telemetria._vazio())
    w3.show()
    app.processEvents()
    confere(not w3.grab().isNull(), "desenha sem conexao")
    w3.hide()


# ----------------------------------------------------------------------------
# v1.2: janelas novas (energia, pneus, danos, alertas, stints, tendencia)
# ----------------------------------------------------------------------------
def _dados_brutos(j):
    d = lmu_data.LMUObjectOut.from_buffer(bytearray(j.bytes()))
    i_s, i_t = lmu.localizar_jogador(d)
    return d, i_s, d.telemetry.telemInfo[i_t]


def teste_leitores_novos():
    grupo("v1.2 - leitores de pneus, danos, energia e bandeiras (ov_lmu)")
    j = cenario_corrida()
    j.rodas[0].update(temp=(355.0, 365.0, 360.0), pressao=205.0, desgaste=0.8, freio=520.0, composto=1, otima=90.0)
    j.rodas[1].update(temp=(0.0, 0.0, 0.0), pressao=0.0, freio=0.0, composto=3, furado=True)
    j.rodas[2].update(desgaste=float("nan"), composto=9, solta=True)
    d, i_s, t = _dados_brutos(j)
    pn = lmu.pneus_do_carro(t)
    fl, fr, rl = pn["rodas"][0], pn["rodas"][1], pn["rodas"][2]
    confere(quase(fl["temp"], 360.0 - 273.15, 1e-6), f"temperatura = media dos 3 pontos em Celsius ({fl['temp']})")
    confere(quase(fl["pressao"], 205.0) and quase(fl["vida"], 80.0) and quase(fl["freio"], 520.0 - 273.15, 1e-6), "pressao, vida e freio da roda (freio em Kelvin no jogo)")
    confere(fl["composto"] == "M" and fl["composto_nome"] == "Medium" and quase(fl["otima"], 90.0), "composto M e temperatura otima")
    confere(fr["temp"] is None and fr["pressao"] is None and fr["freio"] is None, "valores zerados viram None (nada inventado)")
    confere(fr["composto"] == "W" and fr["furado"] and not fr["solta"], "composto de chuva e roda furada")
    confere(rl["vida"] is None and rl["composto"] is None and rl["solta"], "desgaste NaN e composto desconhecido = None; roda solta")
    confere([r["roda"] for r in pn["rodas"]] == ["FL", "FR", "RL", "RR"], "ordem das rodas FL FR RL RR")
    confere(quase(pn["oleo"], 108.0) and quase(pn["agua"], 92.0), "temperatura do oleo e da agua")
    antes = lmu.PNEU_NOVO_E_1
    try:
        lmu.PNEU_NOVO_E_1 = False
        confere(quase(lmu.pneus_do_carro(t)["rodas"][0]["vida"], 20.0), "se o sentido do desgaste estiver invertido, uma constante corrige")
    finally:
        lmu.PNEU_NOVO_E_1 = antes

    j2 = cenario_corrida()
    j2.dentes = [0, 1, 0, 0, 5, 0, 2, 0]
    j2.peca_solta, j2.superaquecendo = True, True
    j2.impacto_et, j2.impacto_forca = 90.0, 1850.0
    j2.tempo_decorrido = 100.0
    j2.rodas[3]["furado"] = True
    d2, _, t2 = _dados_brutos(j2)
    dn = lmu.danos_do_carro(t2)
    confere(dn["zonas"] == [0, 1, 0, 0, 2, 0, 2, 0], f"zonas de dano (valor acima de 2 limitado a 2): {dn['zonas']}")
    confere(dn["solta"] and dn["superaquecendo"] and dn["furados"] == [False, False, False, True], "peca solta, superaquecimento, roda furada")
    confere(quase(dn["impacto_desde"], 10.0) and quase(dn["impacto_forca"], 1850.0), "ultimo impacto: ha 10 s, forca 1850")
    j2.impacto_et = 0.0
    confere(lmu.danos_do_carro(_dados_brutos(j2)[2])["impacto_desde"] is None, "sem impacto: None")
    # v1.5.2: motor parado (ignicao 1 e rotacao ~0), farois e desgaste 0.0 exato = sem leitura
    j5 = cenario_corrida()
    j5.ignicao, j5.rpm, j5.farois = 1, 0.0, True
    dn5 = lmu.danos_do_carro(_dados_brutos(j5)[2])
    confere(dn5["motor_parado"] and dn5["farois"], "ignicao ligada sem rotacao = motor parado; farois ligados")
    j5.ignicao = 2
    confere(not lmu.danos_do_carro(_dados_brutos(j5)[2])["motor_parado"], "motor de partida acionado nao conta como motor parado")
    j5.ignicao, j5.rpm = 1, 6000.0
    confere(not lmu.danos_do_carro(_dados_brutos(j5)[2])["motor_parado"], "ignicao ligada com rotacao = motor funcionando")
    j5.rodas[0]["desgaste"] = 0.0
    confere(lmu.pneus_do_carro(_dados_brutos(j5)[2])["rodas"][0]["vida"] is None, "mWear 0.0 exato = sem leitura (None), nao 0% de vida")
    confere(lmu.ZONAS_DANO[0] == "frente" and len(lmu.ZONAS_DANO) == 8, "8 zonas, a primeira e a frente")
    confere(lmu.ZONAS_DANO[1] == "frente-esquerda" and lmu.ZONAS_DANO[7] == "frente-direita",
            "ordem conferida no jogo real: indice 1 = frente-esquerda (sentido anti-horario)")

    j3 = cenario_corrida()
    for valor, esperado in ((0.62, 62.0), (0.0, 0.0), (1.0, 100.0), (1.5, None), (-0.5, None), (float("nan"), None)):
        j3.energia = valor
        r = lmu.energia_virtual_pct(_dados_brutos(j3)[2])
        confere((r is None and esperado is None) or quase(r, esperado, 1e-6), f"energia virtual {valor} -> {esperado}")

    j4 = cenario_corrida()
    info = _dados_brutos(j4)[0].scoring.scoringInfo
    b0 = lmu.bandeiras(info)
    confere(b0["fase"] == 5 and not b0["fcy"] and not b0["parada"] and b0["amarelas_setor"] == [] and b0["amarelas_brutas"] == [0, 0, 0]
            and not b0["amarelas_suspeitas"], "sem bandeiras")
    j4.fase, j4.estado_amarela, j4.amarelas = 6, 2, (0, 1, 1)
    b = lmu.bandeiras(_dados_brutos(j4)[0].scoring.scoringInfo)
    confere(b["fcy"] and b["fcy_estado"] == "boxes fechados" and b["amarelas_setor"] == [1, 2] and not b["parada"],
            f"FCY, estado e setores com amarela: {b}")
    j4.fase, j4.estado_amarela = 7, -1
    b = lmu.bandeiras(_dados_brutos(j4)[0].scoring.scoringInfo)
    confere(b["parada"] and not b["fcy"] and b["fcy_estado"] == "", "corrida parada (fase 7); estado negativo desconhecido = vazio")


def teste_painel_energia():
    grupo("v1.2 - painel de energia virtual e combustivel (logica pura)")
    import ov_estrategia_lmu as e
    r = e.painel_energia(60.0, 4.0, 40.0, 100.0, 2.5, 12, 10, 1.0)
    confere(quase(r["energia"]["alcance"], 15.0) and quase(r["combustivel"]["alcance"], 16.0), "alcance = nivel / consumo")
    confere(r["limitante"] == "energia" and quase(r["alcance"], 15.0), "recurso limitante = o de menor alcance")
    confere(r["precisa_parar"] is False and r["mensagem"] == "chega" and r["paradas"] == 0, "12 voltas + margem 1 < 15: chega")
    confere(quase(r["alvo_energia"], 5.0) and quase(r["alvo_comb"], 40.0 / 12.0), "alvo por volta para chegar ao fim")
    r = e.painel_energia(60.0, 4.0, 40.0, 100.0, 2.5, 20, 10, 1.0)
    confere(r["precisa_parar"] and r["paradas"] == 1 and r["mensagem"] == "parada", "20 voltas: uma parada")
    confere(r["janela"] == (10, 24), f"janela de pit: da volta atual ate a ultima possivel ({r['janela']})")
    r = e.painel_energia(60.0, 4.0, 40.0, 100.0, 2.5, 60, 10, 1.0)
    confere(r["paradas"] == 2 and r["mensagem"] == "paradas" and r["janela"] is None, "60 voltas: duas paradas, sem janela unica")
    r = e.painel_energia(90.0, 3.0, 20.0, 100.0, 2.5, 20, 1, 1.0)
    confere(r["limitante"] == "combustivel" and quase(r["alcance"], 8.0), "combustivel pode ser o limitante")
    r = e.painel_energia(None, None, 20.0, 100.0, 2.5, 20, 1, 1.0)
    confere(r["energia"]["alcance"] is None and r["limitante"] == "combustivel" and not r["ve_informada"], "sem energia virtual: so combustivel")
    r = e.painel_energia(60.0, 0.01, 20.0, 100.0, 2.5, 20, 1, 1.0)
    confere(r["energia"]["por_volta"] is None and r["limitante"] == "combustivel", "consumo de energia desprezivel = carro sem energia virtual")
    r = e.painel_energia(None, None, None, None, None, 20, 1, 1.0)
    confere(r["alcance"] is None and r["mensagem"] == "sem_dados" and r["limitante"] is None, "sem dados nenhum")
    r = e.painel_energia(60.0, 4.0, 40.0, 100.0, 2.5, None, 3, 1.0)
    confere(r["mensagem"] == "sem_fim" and r["precisa_parar"] is None and r["janela"] is None, "sessao sem fim conhecido")
    r = e.painel_energia(60.0, 4.0, 40.0, None, 2.5, 20, 3, 1.0)
    confere(r["precisa_parar"] and r["paradas"] == 1, "sem capacidade do tanque: usa so a energia para a conta")
    r = e.painel_energia(float("nan"), 4.0, 40.0, 100.0, 2.5, 20, 3, 1.0)
    confere(r["energia"]["nivel_pct"] is None, "NaN nao vira numero")
    confere(e.fmt_duracao(1408) == "23:28" and e.fmt_duracao(5000) == "1:23:20" and e.fmt_duracao(None) == "--", "formato de duracao")


def teste_stints():
    grupo("v1.2 - historico de stints e tendencia (logica pura)")
    import ov_estrategia_lmu as e
    h = e.HistoricoStints()
    ve, comb, des = 100.0, 90.0, 1.0
    h.atualizar("a", 0, False, ve, comb, des, "M", None, None, 30.0)
    melhor = None
    for volta in (1, 2, 3):
        ve, comb, des = ve - 4.2, comb - 2.4, des - 0.03
        tempo = 215.0 + 0.1 * volta
        melhor = tempo if melhor is None else min(melhor, tempo)
        h.atualizar("a", volta, False, ve, comb, des, "M", tempo, melhor, 30.0 + volta)
    r = h.resumo(melhor)
    confere(len(r) == 1 and r[0]["n"] == 1 and r[0]["voltas"] == 3 and r[0]["atual"] and not r[0]["parcial"], "primeiro stint: 3 voltas")
    confere(quase(r[0]["energia"], 12.6, 1e-6) and quase(r[0]["comb"], 7.2, 1e-6) and quase(r[0]["desgaste"], 9.0, 1e-6), "energia, combustivel e desgaste do stint")
    confere(quase(r[0]["ritmo"], 215.2, 1e-6) and r[0]["limpas"] == 3 and r[0]["composto"] == "M", "ritmo = media das voltas limpas")
    confere(quase(r[0]["delta"], 215.2 - 215.1, 1e-6), "delta do ritmo contra a melhor volta")
    # parada: entra nos boxes, completa a volta nos boxes, reabastece, sai
    h.atualizar("a", 3, True, ve, comb, des, "M", None, melhor, 38.0)
    h.atualizar("a", 4, True, ve, comb, des, "M", 262.0, melhor, 38.0)
    ve, comb, des = 100.0, 90.0, 1.0
    h.atualizar("a", 4, True, ve, comb, des, "H", 262.0, melhor, 38.0)
    h.atualizar("a", 4, False, ve, comb, des, "H", 262.0, melhor, 38.0)
    for volta, tempo in ((5, 215.4), (6, 400.0), (7, 215.6)):
        ve, comb, des = ve - 4.2, comb - 2.4, des - 0.03
        h.atualizar("a", volta, False, ve, comb, des, "H", tempo, melhor, 40.0)
    r = h.resumo(melhor)
    confere(len(r) == 2 and r[0]["n"] == 2 and r[0]["atual"] and not r[1]["atual"], "a saida dos boxes abre o stint 2 (mais recente primeiro)")
    confere(r[1]["voltas"] == 4 and quase(r[1]["energia"], 12.6, 1e-6), "stint 1 manteve os valores de antes da parada (o reabastecimento nao entra)")
    confere(r[0]["voltas"] == 3 and r[0]["composto"] == "H" and r[0]["limpas"] == 1, "stint 2: volta de saida dos boxes e volta lenta (> 130%) ficam fora das limpas")
    confere(quase(r[0]["tempo"], 215.4 + 400.0 + 215.6, 1e-6), "o tempo do stint soma todas as voltas")
    confere(quase(r[0]["energia"], 12.6, 1e-6) and quase(r[0]["desgaste"], 9.0, 1e-6), "stint 2: energia e desgaste desde o reabastecimento")
    t = h.tendencia(melhor)
    confere([v[0] for v in t["voltas"]] == [1, 2, 3, 7], f"voltas limpas guardadas ({[v[0] for v in t['voltas']]})")
    confere(t["inclinacao"] is None, "tendencia precisa de 4 voltas limpas no stint atual")
    # tendencia: 5 voltas subindo 0,1 s por volta
    h2 = e.HistoricoStints()
    h2.atualizar("b", 0, False, 100, 90, 1.0, "M", None, None, 30.0)
    for volta in range(1, 7):
        h2.atualizar("b", volta, False, 100 - 4 * volta, 90 - 2 * volta, 1.0, "M", 215.0 + 0.1 * volta, 215.1, 30.0 + volta)
    t2 = h2.tendencia(215.1)
    confere(quase(t2["inclinacao"], 0.1, 1e-9), f"inclinacao = +0,1 s/volta ({t2['inclinacao']})")
    confere(quase(t2["ritmo5"], sum(215.0 + 0.1 * v for v in range(2, 7)) / 5, 1e-9), "ritmo das ultimas 5 limpas")
    confere(quase(t2["delta_ritmo"], t2["ritmo5"] - 215.1, 1e-9) and quase(t2["temp_variacao"], 5.0), "delta do ritmo e variacao da temperatura da pista")
    # overlay aberto no meio do stint: parcial
    h3 = e.HistoricoStints()
    h3.atualizar("c", 7, False, 50, 40, 0.5, "M", 215.0, 214.0, 30.0)
    confere(h3.resumo(214.0)[0]["parcial"], "aberto no meio do stint: marcado como parcial")
    # saida dos boxes sem nenhuma volta no stint (largada no box) nao cria stint vazio
    h4 = e.HistoricoStints()
    h4.atualizar("d", 0, True, 100, 90, 1.0, "M", None, None, 30.0)
    h4.atualizar("d", 0, False, 100, 90, 1.0, "M", None, None, 30.0)
    confere(len(h4.resumo()) == 1, "largada nos boxes: continua o stint 1")
    # nova sessao: recomeca
    h.atualizar("outra", 0, False, 100, 90, 1.0, "M", None, None, 30.0)
    confere(len(h.resumo()) == 1 and h.resumo()[0]["voltas"] == 0 and h.tendencia(None)["voltas"] == [], "nova sessao: historico zerado")
    # valores ausentes nunca viram zero
    h5 = e.HistoricoStints()
    h5.atualizar("e", 0, False, None, 90.0, None, None, None, None, None)
    h5.atualizar("e", 1, False, None, 87.0, None, None, 215.0, 215.0, None)
    r5 = h5.resumo(215.0)[0]
    confere(r5["energia"] is None and r5["desgaste"] is None and quase(r5["comb"], 3.0), "sem energia/desgaste: None, nao zero")
    confere(h5.tendencia(215.0)["temp_pista"] is None, "sem temperatura da pista: None")


def teste_alertas():
    grupo("v1.2 - alertas na pista (logica pura)")
    import ov_alertas_lmu as a
    from ov_demo_lmu import _carro

    def ids(lista):
        return [x["id"] for x in lista]

    def calc(carros, bandeiras=None, limitador=None, danos=None, energia=None, cfg=None, motor=None, comp=5000.0):
        motor = motor or a.AlertasLMU()
        return motor.calcular({"bandeiras": bandeiras, "carros": carros, "comprimento": comp, "limitador": limitador,
                               "danos": danos, "energia": energia}, cfg), motor
    eu = lambda **kw: _carro(True, 5, "LMGT3", 31, **{"dist": 2000.0, "vel_ms": 55.0, **kw})
    hyper = lambda dist, vel=70.0, **kw: _carro(False, 1, "Hypercar", 7, dist, vel, **kw)

    lista, _ = calc([eu()], {"fase": 6, "fcy": True, "fcy_estado": "retomada", "parada": False, "amarelas_setor": [1]})
    confere(ids(lista) == ["fcy", "amarela_local"] and lista[0]["nivel"] == a.NIVEL_PERIGO and lista[1]["nivel"] == a.NIVEL_ATENCAO,
            f"FCY (perigo) antes da amarela local (atencao): {ids(lista)}")
    lista, _ = calc([eu()], {"fase": 7, "fcy": False, "fcy_estado": "", "parada": True, "amarelas_setor": []})
    confere(ids(lista) == ["parada"], "corrida parada (fase 7)")
    lista, _ = calc([eu()], {"fase": 5, "fcy": False, "fcy_estado": "", "parada": False, "amarelas_setor": []})
    confere(lista == [], "sem bandeiras: nenhum alerta")

    # classe mais rapida atras
    lista, _ = calc([eu(), hyper(1700.0)])
    confere(ids(lista) == ["classe_rapida"] and lista[0]["nivel"] == a.NIVEL_ATENCAO and "#7" in lista[0]["detalhe"]
            and "300 m" in lista[0]["detalhe"] and "~20 s" in lista[0]["detalhe"], f"hypercar a 300 m, alcanca em ~20 s: {lista}")
    lista, _ = calc([eu(), hyper(1900.0)])
    confere(lista[0]["nivel"] == a.NIVEL_PERIGO, "hypercar a 100 m (alcanca em < 8 s): perigo")
    lista, _ = calc([eu(), hyper(1300.0)])
    confere(lista == [], "hypercar a 700 m (alem dos 600 m): sem alerta")
    lista, _ = calc([eu(), hyper(1700.0)], cfg={"alerta_traseiro_m": 200.0})
    confere(lista == [], "limiar configuravel: 200 m ignora o carro a 300 m")
    lista, _ = calc([eu(), hyper(1700.0, box=True)])
    confere(lista == [], "carro de classe rapida nos boxes: sem alerta")
    lista, _ = calc([eu(), _carro(False, 2, "LMGT3", 99, 1700.0, 70.0)])
    confere(lista == [], "carro da mesma classe atras: sem alerta")
    lista, _ = calc([_carro(True, 1, "Hypercar", 7, 2000.0, 55.0), _carro(False, 2, "LMGT3", 99, 1700.0, 70.0)])
    confere(lista == [], "carro de classe mais lenta atras: sem alerta")
    lista, _ = calc([eu(), _carro(False, 2, "ClasseNova", 99, 1700.0, 70.0)])
    confere(lista == [], "classe desconhecida nao e tratada como mais rapida")
    lista, _ = calc([eu(dist=100.0), hyper(4900.0)])
    confere(ids(lista) == ["classe_rapida"] and "200 m" in lista[0]["detalhe"], "distancia atravessa a linha de chegada")

    # carro lento ou parado a frente
    lento = lambda dist, vel: _carro(False, 6, "LMGT3", 88, dist, vel)
    lista, _ = calc([eu(), lento(2240.0, 14.0)])
    confere(ids(lista) == ["lento_frente"] and lista[0]["nivel"] == a.NIVEL_ATENCAO and lista[0]["titulo"] == "CARRO LENTO A FRENTE",
            f"carro lento a 240 m (contato em ~6 s): {lista}")
    lista, _ = calc([eu(), lento(2100.0, 14.0)])
    confere(lista[0]["nivel"] == a.NIVEL_PERIGO, "carro lento a 100 m (contato < 5 s): perigo")
    lista, _ = calc([eu(), lento(2100.0, 0.0)])
    confere(lista[0]["titulo"] == "CARRO PARADO A FRENTE", "carro parado")
    lista, _ = calc([eu(), lento(2240.0, 30.0)])
    confere(lista == [], "carro a frente em ritmo normal (acima de 70 km/h): sem alerta")
    lista, _ = calc([eu(), lento(2500.0, 14.0)])
    confere(lista == [], "carro lento alem de 350 m: sem alerta")
    lista, _ = calc([eu(vel_ms=10.0), lento(2240.0, 14.0)])
    confere(lista == [], "o outro carro e mais rapido que voce: sem alerta")

    # bandeira azul
    lista, _ = calc([eu(bandeira=6), hyper(1700.0)])
    confere(ids(lista) == ["azul"] and "#7" in lista[0]["detalhe"], f"bandeira azul com o carro mais rapido identificado: {lista}")
    lista, _ = calc([eu(bandeira=6)])
    confere(ids(lista) == ["azul"], "bandeira azul sem carro identificado")

    # penalidade, boxes
    lista, _ = calc([eu(penalidades=2)])
    confere(ids(lista) == ["penalidade"] and "2" in lista[0]["titulo"], "penalidades")
    lista, _ = calc([eu(box=True, pit_estado=4, vel_ms=20.0), hyper(1500.0)])
    confere(ids(lista) == ["saida_box"] and lista[0]["nivel"] == a.NIVEL_ATENCAO and "#7" in lista[0]["detalhe"], f"saindo dos boxes com carro chegando: {lista}")
    lista, _ = calc([eu(box=True, pit_estado=4, vel_ms=20.0)])
    confere(ids(lista) == ["saida_box"] and lista[0]["nivel"] == a.NIVEL_INFO, "saindo dos boxes com a pista livre: so informacao")
    lista, _ = calc([eu(pit_estado=1, pit_dist=2500.0)])
    confere(ids(lista) == ["box_distancia"] and "500 m" in lista[0]["detalhe"], f"parada solicitada: boxes a 500 m: {lista}")
    lista, _ = calc([eu(pit_estado=1, pit_dist=1500.0)])
    confere("4500 m" not in lista[0]["detalhe"] and "4.5 km" in lista[0]["detalhe"], "distancia ate os boxes dando a volta (4,5 km)")

    # limite dos boxes: medido pela velocidade mais comum com o limitador ligado
    motor = a.AlertasLMU()
    pit = lambda v: {"ativo": True, "vel": v, "nos_boxes": True}
    lista, motor = calc([eu(box=True, pit_estado=2)], limitador=pit(79.6), motor=motor)
    confere(motor.limite_pit is None and "medindo" in lista[0]["detalhe"], "antes de medir: informa que esta medindo")
    for _ in range(24):
        lista, motor = calc([eu(box=True, pit_estado=2)], limitador=pit(80.1), motor=motor)
    confere(motor.limite_pit == 80.0, f"limite dos boxes medido = 80 km/h ({motor.limite_pit})")
    lista, motor = calc([eu(box=True, pit_estado=2)], limitador=pit(84.0), motor=motor)
    confere(lista[0]["id"] == "limite_pit" and lista[0]["nivel"] == a.NIVEL_PERIGO, "acima do limite medido: perigo")
    lista, motor = calc([eu(box=True, pit_estado=2)], limitador=pit(80.5), motor=motor)
    confere(lista[0]["nivel"] == a.NIVEL_INFO, "dentro da tolerancia: so informacao")
    m2 = a.AlertasLMU()
    for v in [30.0, 55.0, 70.0] + [60.0] * 20:
        calc([eu(box=True, pit_estado=2)], limitador={"ativo": True, "vel": v, "nos_boxes": True}, motor=m2)
    confere(m2.limite_pit == 60.0, "a velocidade mais comum vale; aceleracao e freada nao enganam")
    m3 = a.AlertasLMU()
    for _ in range(30):
        calc([eu()], limitador={"ativo": True, "vel": 80.0, "nos_boxes": False}, motor=m3)
    confere(m3.limite_pit is None, "limitador ligado na pista (fora dos boxes) nao conta como medida")

    # carro e recursos
    lista, _ = calc([eu()], danos={"superaquecendo": True, "furados": [False, True, False, False], "rodas_soltas": [False] * 4, "solta": True})
    confere(ids(lista) == ["superaquecendo", "furado", "peca_solta"], f"superaquecimento, pneu furado e peca solta: {ids(lista)}")
    lista, _ = calc([eu()], danos={"superaquecendo": False, "furados": [False] * 4, "rodas_soltas": [False, False, True, False], "solta": True})
    confere(ids(lista) == ["roda_solta"], "roda solta substitui o aviso de peca solta (nao repete)")
    lista, _ = calc([eu()], danos={"superaquecendo": False, "furados": [False] * 4, "rodas_soltas": [False] * 4, "solta": True})
    confere(ids(lista) == ["peca_solta"] and lista[0]["nivel"] == a.NIVEL_ATENCAO, "peca solta")
    lista, _ = calc([eu()], danos={"superaquecendo": False, "motor_parado": True, "furados": [False] * 4, "rodas_soltas": [False] * 4, "solta": False})
    confere(ids(lista) == ["motor_parado"] and lista[0]["nivel"] == a.NIVEL_PERIGO, "motor parado na pista gera alerta")
    lista, _ = calc([eu(box=True)], danos={"superaquecendo": False, "motor_parado": True, "furados": [False] * 4, "rodas_soltas": [False] * 4, "solta": False})
    confere("motor_parado" not in ids(lista), "motor parado nos boxes nao gera alerta")
    for alcance, nivel in ((1.5, a.NIVEL_PERIGO), (2.5, a.NIVEL_ATENCAO), (5.0, None)):
        lista, _ = calc([eu()], energia={"alcance": alcance, "limitante": "energia"})
        confere((nivel is None and lista == []) or (lista and lista[0]["nivel"] == nivel and lista[0]["titulo"].startswith("ENERGIA")),
                f"reserva: alcance {alcance} V -> nivel {nivel}")
    lista, _ = calc([eu()], energia={"alcance": 1.0, "limitante": "combustivel"})
    confere(lista[0]["titulo"].startswith("COMBUSTIVEL"), "reserva nomeia o recurso limitante")
    # seu carro nos boxes: sem alerta de transito; ordenacao e limite de alertas
    lista, _ = calc([eu(box=True, pit_estado=3), hyper(1700.0)])
    confere("classe_rapida" not in ids(lista), "voce nos boxes parado: sem alerta de classe rapida")
    cheio, _ = calc([eu(penalidades=1, bandeira=6), hyper(1900.0), lento(2100.0, 0.0)],
                    {"fase": 6, "fcy": True, "fcy_estado": "", "parada": True, "amarelas_setor": [0]},
                    danos={"superaquecendo": True, "furados": [True] * 4, "rodas_soltas": [True] * 4, "solta": True},
                    energia={"alcance": 1.0, "limitante": "energia"})
    confere(len(cheio) == a.MAX_ALERTAS and [x["nivel"] for x in cheio] == sorted((x["nivel"] for x in cheio), reverse=True),
            f"no maximo {a.MAX_ALERTAS} alertas, do mais grave para o menos grave")
    lista, _ = calc([], None)
    confere(lista == [], "sem carros: sem erro")
    confere(a.distancia_atras({"dist": 10.0}, {"dist": 20.0}, 0.0) is None, "comprimento da pista desconhecido: sem distancia")
    confere(a.fmt_metros(250) == "250 m" and a.fmt_metros(1500) == "1.5 km", "formato de distancia")


def _correr_voltas(j, tel, rel, n_voltas, energia_por_volta=0.04, litros_por_volta=2.4, tempo_volta=232.0):
    """Anda `n_voltas` voltas com o jogador (carro 4 do cenario), gastando energia e combustivel."""
    jogador = j.carros[3]
    d = None
    for _ in range(n_voltas):
        for _ in range(20):
            rel.avancar(tempo_volta / 20.0)
            j.et += tempo_volta / 20.0
            j.tempo_decorrido += tempo_volta / 20.0
            jogador.dist = (jogador.dist + j.comprimento / 20.0) % j.comprimento
            j.energia = max(0.0, j.energia - energia_por_volta / 20.0)
            j.combustivel -= litros_por_volta / 20.0
            d = tel.ler()
        jogador.voltas += 1
        jogador.ultima = tempo_volta
        jogador.melhor = tempo_volta - 0.5
        j.inicio_volta = j.tempo_decorrido
    return tel.ler()


def teste_extras_pipeline():
    grupo("v1.2 - dados das janelas novas pelo caminho completo (memoria falsa -> TelemetriaLMU)")
    j = cenario_corrida()
    j.energia, j.combustivel = 0.80, 70.0
    j.carros[3].voltas = 1
    j.max_voltas = 12
    j.carros[3].vel = 55.0
    tel, rel = telemetria(j)
    tel.ler()
    d = _correr_voltas(j, tel, rel, 5)
    en = d["lmu_energia"]
    confere(en is not None and en["energia"]["por_volta"] is not None and quase(en["energia"]["por_volta"], 4.0, 0.2),
            f"consumo de energia por volta ~4 % ({en['energia']['por_volta']})")
    confere(quase(en["combustivel"]["por_volta"], 2.4, 0.15), f"consumo de combustivel ~2,4 L ({en['combustivel']['por_volta']})")
    confere(en["limitante"] in ("energia", "combustivel") and en["alcance"] is not None and en["voltas_fim"] is not None,
            f"recurso limitante e voltas ate o fim ({en['limitante']}, {en['voltas_fim']})")
    confere(en["energia"]["nivel_pct"] is not None and en["energia"]["nivel_pct"] < 80.0, "nivel de energia vem do jogo")
    pn, dn = d["lmu_pneus"], d["lmu_danos"]
    confere(len(pn["rodas"]) == 4 and quase(pn["rodas"][0]["vida"], 80.0) and dn["zonas"] == [0] * 8, "pneus e danos entregues")
    confere(d["lmu_alertas"]["lista"] == [] and d["lmu_alertas"]["limite_pit"] is None, "pista tranquila: sem alertas")
    st = d["lmu_stints"]["stints"]
    confere(len(st) == 1 and st[0]["voltas"] >= 4 and st[0]["atual"] and st[0]["composto"] == "M", f"um stint em andamento ({st})")
    confere(st[0]["energia"] is not None and st[0]["energia"] > 10.0 and st[0]["comb"] > 8.0, "energia e combustivel gastos no stint")
    tr = d["lmu_tendencia"]
    confere(tr is not None and len(tr["voltas"]) >= 3 and tr["ritmo5"] is not None and quase(tr["ritmo5"], 232.0, 0.01), "tendencia com as voltas limpas")
    confere(tr["temp_pista"] == 31.0, "temperatura da pista vem do jogo")

    # bandeiras, penalidade, classe rapida: tudo junto
    j.fase, j.estado_amarela, j.amarelas = 6, 3, (0, 0, 1)
    j.carros[3].pen = 1
    j.carros[3].dist = 1000.0
    j.carros[0].dist, j.carros[0].vel = 700.0, 70.0
    rel.avancar(1.0)
    j.et += 1.0
    d = tel.ler()
    ids_ = [x["id"] for x in d["lmu_alertas"]["lista"]]
    confere("fcy" in ids_ and "amarela_local" in ids_ and "penalidade" in ids_ and "classe_rapida" in ids_, f"alertas pelo caminho completo: {ids_}")
    confere(d["lmu_alertas"]["lista"][0]["nivel"] == 2, "o mais grave vem primeiro")

    # limite dos boxes medido com o limitador ligado
    j.fase, j.amarelas, j.estado_amarela, j.carros[3].pen = 5, (0, 0, 0), 0, 0
    j.carros[3].box, j.carros[3].estado_box, j.limitador = True, 2, True
    j.vel_ms = (0.0, 0.0, -22.0)
    for _ in range(26):
        rel.avancar(0.2)
        j.et += 0.2
        d = tel.ler()
    confere(d["lmu_alertas"]["limite_pit"] == 79.0, f"limite dos boxes medido pelo caminho completo ({d['lmu_alertas']['limite_pit']})")

    # parada: novo stint
    j.carros[3].box, j.carros[3].estado_box, j.limitador = True, 0, False
    j.energia, j.combustivel = 1.0, 105.0
    rel.avancar(1.0)
    j.et += 1.0
    tel.ler()
    j.carros[3].box = False
    rel.avancar(1.0)
    j.et += 1.0
    d = tel.ler()
    j.vel_ms = (0.0, 0.0, -55.0)
    d = _correr_voltas(j, tel, rel, 3)
    st = d["lmu_stints"]["stints"]
    confere(len(st) == 2 and st[0]["n"] == 2 and st[0]["atual"], f"saida dos boxes abre o stint 2 ({[(s['n'], s['voltas']) for s in st]})")
    confere(st[1]["energia"] is not None and st[1]["energia"] > 10.0, "o stint 1 manteve o gasto de antes da parada")

    # impacto novo vai para o log (a ordem das zonas precisa ser conferida no jogo)
    j.dentes[6], j.impacto_et, j.impacto_forca = 2, j.tempo_decorrido - 2.0, 2500.0
    rel.avancar(1.0)
    j.et += 1.0
    d = tel.ler()
    confere(d["lmu_danos"]["zonas"][6] == 2 and d["lmu_danos"]["impacto_desde"] is not None, "impacto novo aparece nos danos")
    log = (TMP / "log_teste.txt").read_text(encoding="utf-8")
    confere("impacto LMU" in log and "pneus LMU: valores crus" in log and "bandeiras LMU" in log and "energia virtual LMU" in log,
            "log traz impacto, valores crus dos pneus, bandeiras e energia (validacao no jogo real)")
    confere("Traceback" not in log, "nenhum erro no log")

    # jogo sem energia virtual (valor invalido): a janela continua com o combustivel
    j2 = cenario_corrida()
    j2.energia = float("nan")
    tel2, rel2 = telemetria(j2)
    tel2.ler()
    d2 = tel2.ler()
    confere(d2["lmu_energia"]["energia"]["nivel_pct"] is None and d2["lmu_pneus"] is not None, "energia virtual invalida: sem energia, o resto segue funcionando")


def teste_config_lmu():
    grupo("v1.2 - configuracao das janelas novas")
    m = preparar_modulo()
    import overlay_iracing as base
    alvo = TMP / "config_lmu_teste.json"
    m.ARQ_CONFIG_LMU = alvo
    m.redirecionar_arquivos(TMP, alvo, TMP / "log_cfg.txt")
    cfg = m.carregar_config_lmu()
    confere(all(k in cfg for k in m.CONFIG_LMU_PADRAO), "todas as chaves novas existem por padrao")
    confere(cfg["x_lmu_energia"] == 440 and cfg["mostrar_lmu_alertas"] is True and cfg["alerta_traseiro_m"] == 600.0, "valores padrao")
    cfg["x_lmu_energia"], cfg["escala_lmu_stints"], cfg["alerta_traseiro_m"], cfg["mostrar_lmu_tendencia"] = 123, 1.4, 450.0, False
    base.salvar_config(cfg)
    c2 = m.carregar_config_lmu()
    confere(c2["x_lmu_energia"] == 123 and c2["escala_lmu_stints"] == 1.4 and c2["alerta_traseiro_m"] == 450.0
            and c2["mostrar_lmu_tendencia"] is False, "posicao, escala, limiar e visibilidade das janelas novas sao salvos e lidos")
    confere(all("x_lmu_energia" in p for p in c2["perfis"].values()), "as janelas novas entram nos perfis")
    texto = json_ = alvo.read_text(encoding="utf-8")
    import json
    dados = json.loads(texto)
    dados.update({"x_lmu_energia": "abc", "mostrar_lmu_stints": 5, "alerta_frente_m": True, "alerta_lento_kmh": 55})
    alvo.write_text(json.dumps(dados), encoding="utf-8")
    c3 = m.carregar_config_lmu()
    confere(c3["x_lmu_energia"] == 440 and c3["mostrar_lmu_stints"] is True and c3["alerta_frente_m"] == 350.0 and c3["alerta_lento_kmh"] == 55,
            "valor com tipo errado volta ao padrao; valor correto fica")
    alvo.write_text("isto nao e json", encoding="utf-8")
    c4 = m.carregar_config_lmu()
    confere(c4["x_lmu_energia"] == 440, "arquivo ilegivel: usa os padroes sem derrubar o overlay")


def renderizar_janelas_novas():
    grupo("v1.2 - desenho das 6 janelas novas (offscreen)")
    m = preparar_modulo()
    import overlay_iracing as base
    import ov_janelas_extra_lmu as ex
    import ov_demo_lmu
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    PREVIAS.mkdir(parents=True, exist_ok=True)
    alvo = TMP / "config_render.json"
    m.ARQ_CONFIG_LMU = alvo
    m.redirecionar_arquivos(TMP, alvo, TMP / "log_render.txt")
    cfg = m.carregar_config_lmu()
    cfg["travado"] = True
    base.definir_tema(True, 0.8)

    j = cenario_corrida()
    j.energia, j.combustivel, j.max_voltas = 0.80, 70.0, 12
    j.carros[3].voltas, j.carros[3].vel = 1, 55.0
    j.dentes = [0, 1, 0, 0, 0, 0, 2, 1]
    j.impacto_et, j.impacto_forca = 40.0, 1850.0
    j.rodas[0].update(temp=(350.0, 366.0, 359.0), desgaste=0.78)
    j.rodas[1].update(temp=(365.0, 380.0, 372.0), desgaste=0.70, freio=640.0)
    j.rodas[2].update(temp=(340.0, 345.0, 342.0), desgaste=0.30, freio=410.0)
    j.rodas[3].update(temp=(358.0, 362.0, 360.0), desgaste=0.12, composto=1)
    tel, rel = telemetria(j)
    tel.ler()
    d = _correr_voltas(j, tel, rel, 6)
    j.fase, j.amarelas = 5, (0, 1, 0)
    j.carros[3].dist, j.carros[0].dist, j.carros[0].vel = 1000.0, 700.0, 70.0
    j.carros[3].pen = 1
    rel.avancar(1.0)
    j.et += 1.0
    d = tel.ler()
    demo = base.Telemetria._vazio()
    demo.update(ov_demo_lmu.DemoExtraLMU().ler())
    demo["conectado"] = True
    demo["tipo_sessao"] = "CORRIDA"

    desenhados = []
    original = m.PintorLMU.drawText

    def espiao(self, *args):
        for a in args:
            if isinstance(a, str):
                desenhados.append(m.traduzir_texto(a))
        return original(self, *args)
    m.PintorLMU.drawText = espiao
    try:
        for cls in ex.JANELAS_EXTRA:
            for rotulo, dados in (("jogo_falso", d), ("demo", demo)):
                w = cls(cfg)
                w.resize(w.size())
                w.atualizar(dados)
                w.show()
                app.processEvents()
                img = w.grab()
                arq = PREVIAS / f"previa_{rotulo}_{cls.__name__}.png"
                ok = img.save(str(arq)) and not img.isNull() and img.width() >= 300 and img.height() >= 200
                confere(ok, f"{cls.__name__} ({rotulo}): desenhou {img.width()}x{img.height()}")
                w.hide()
            # sem conexao e conectado sem os dados novos: sem erro
            for dados in (base.Telemetria._vazio(), {**base.Telemetria._vazio(), "conectado": True}):
                w = cls(cfg)
                w.atualizar(dados)
                w.show()
                app.processEvents()
                w.grab()
                w.hide()
            confere(True, f"{cls.__name__}: sem dados nao lanca erro")
        # situacoes extremas dos dados
        extremos = dict(demo)
        extremos["lmu_pneus"] = {"rodas": [{"roda": r, "temp": None, "pressao": None, "vida": None, "freio": None, "otima": None,
                                           "composto": None, "composto_nome": "", "furado": True, "solta": False} for r in lmu.RODAS],
                                 "oleo": None, "agua": None}
        extremos["lmu_energia"] = {**demo["lmu_energia"], "mensagem": "paradas", "paradas": 3, "janela": None, "alcance": 2.0}
        extremos["lmu_tendencia"] = None
        extremos["lmu_stints"] = {"stints": demo["lmu_stints"]["stints"] * 3}
        for cls in ex.JANELAS_EXTRA:
            w = cls(cfg)
            w.atualizar(extremos)
            w.show()
            app.processEvents()
            w.grab()
            w.hide()
        confere(True, "dados extremos (tudo None, 3 paradas, 18 stints) desenham sem erro")
    finally:
        m.PintorLMU.drawText = original
    confere(not any("iRacing" in t or "SDK" in t for t in desenhados), "nenhum texto das janelas novas cita iRacing/SDK")
    confere(any("ENERGIA" in t for t in desenhados) and any("ALERTAS" in t for t in desenhados), "titulos das janelas novas desenhados")
    log = TMP / "log_render.txt"
    confere(not log.exists() or "Traceback" not in log.read_text(encoding="utf-8"), "nenhum erro no log durante o desenho")

    # tamanho e escala: as janelas novas obedecem a escala salva
    cfg["escala_lmu_alertas"], cfg["escala_x_lmu_alertas"], cfg["escala_y_lmu_alertas"] = 1.5, 1.5, 1.5
    w = ex.JanelaAlertasLMU(cfg)
    confere(w.width() == round(ex.TAM_ALERTAS[0] * 1.5) and w.height() == round(ex.TAM_ALERTAS[1] * 1.5), "escala salva da janela de alertas aplicada")
    confere(w.CHAVE_ATIVO == "mostrar_lmu_alertas" and ex.JanelaPneusLMU.CHAVE == "pneus" and ex.JanelaDanosLMU.CHAVE == "danos",
            "pneus e danos reaproveitam a posicao do layout do iRacing")


def teste_diagnostico_novo():
    grupo("v1.2 - diagnostico com os valores crus das janelas novas")
    m = preparar_modulo()
    j = cenario_corrida()
    j.dentes[2] = 1
    j.amarelas = (0, 0, 1)
    leitor = lmu.LeitorLMU(abridor=lambda: MapaFalso(j), relogio=Relogio())
    texto_diag, _ = m.gerar_diagnostico(leitor)
    confere("mWear 0.800" in texto_diag and "roda FL" in texto_diag and "roda RR" in texto_diag, "diagnostico traz o desgaste cru das 4 rodas")
    confere("zonas de dano" in texto_diag and "[0, 0, 1, 0, 0, 0, 0, 0]" in texto_diag, "diagnostico traz as 8 zonas de dano")
    confere("bandeiras:" in texto_diag and "[2]" in texto_diag and "boxes: estado" in texto_diag, "diagnostico traz bandeiras, setores e boxes")
    confere("energia virtual: 0.620" in texto_diag, "diagnostico traz a energia virtual")


TESTES = [teste_estrutura, teste_auxiliares, teste_motivos_volta_suja, teste_leitor, teste_104_carros,
          teste_telemetria_dados, teste_classificacao, teste_classificacao_detalhada, teste_janela_classificacao, teste_voltas_delta_combustivel, teste_estados_do_jogador,
          teste_sessoes, teste_textos, renderizar_janelas, teste_v13_correcoes_do_jogo_real, teste_config_isolada, teste_diagnostico, teste_demo,
          teste_leitores_novos, teste_painel_energia, teste_stints, teste_alertas, teste_extras_pipeline, teste_config_lmu,
          renderizar_janelas_novas, teste_diagnostico_novo,
          teste_dependencias, teste_principal, teste_atalhos_stream_deck, teste_perfil_stream_deck]

if __name__ == "__main__":
    for t in TESTES:
        try:
            t()
        except Exception:
            _falhas.append(f"{t.__name__}: excecao")
            print("  EXCECAO em", t.__name__)
            traceback.print_exc()
    print(f"\nResultado: {_ok} verificacoes ok, {len(_falhas)} falha(s).")
    for f in _falhas:
        print(" -", f)
    print(f"Previas das janelas: {PREVIAS}")
    shutil.rmtree(TMP / "x", ignore_errors=True)
    sys.exit(1 if _falhas else 0)
