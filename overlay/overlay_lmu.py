# -*- coding: utf-8 -*-
"""
Overlay LMU (Le Mans Ultimate) - versao 1.2, base: Overlay iRacing Fase 20.2.2

Seis janelas base, com o MESMO visual, tamanho e posicao do overlay do iRacing (reaproveita o desenho dele):
  1. Telemetria    : marcha, velocidade, RPM, pedais, volante + grafico de acelerador e freio
  2. Voltas        : delta, tempo de volta (atual / ultima / melhor) e calculo de combustivel
  3. Classificacao : por classe (Hypercar, LMP2, LMGT3...): posicao e variacao no grid, numero, carro, piloto, PIT/PEN,
                     paradas, combustivel %, gap, intervalo, melhor, ultima e media das ultimas 5 voltas
  4. Clima         : temperatura da pista e do ar, chuva, umidade da pista e vento
  5. Combustivel   : medidor + calculadora (janela de pit, litros a colocar, autonomia, consumo das ultimas voltas)
  6. Forca G       : circulo de G lateral e longitudinal com rastro, G atual e pico

Seis janelas NOVAS do LMU (v1.2, so existem aqui; dados da memoria compartilhada do jogo):
  7. Energia       : energia virtual + combustivel, recurso limitante, alcance, janela de pit e alvo por volta
  8. Pneus         : temperatura, pressao, vida, composto e freios das 4 rodas + oleo e agua
  9. Danos         : 8 zonas de impacto, pecas soltas, rodas furadas, superaquecimento, ultimo impacto
 10. Alertas       : FCY/amarela/azul, classe mais rapida atras, carro lento a frente, saida dos boxes, limite dos boxes
 11. Stints        : historico por stint (voltas, tempo, energia, combustivel, pneu, desgaste, ritmo)
 12. Tendencia     : grafico das voltas limpas com reta de tendencia, ritmo das ultimas 5 e temperatura da pista

Os arquivos do overlay do iRacing NAO sao alterados: este programa os importa (overlay_iracing.py e ov_nucleo.py precisam
estar na mesma pasta) e troca apenas a FONTE dos dados (memoria compartilhada do LMU, ov_lmu.py). Configuracao, log e
demais arquivos sao proprios do LMU (config_lmu.json, overlay_log_lmu.txt) e nao se misturam com os do iRacing.

Uso:
  iniciar_overlay_lmu.bat   -> le os dados do Le Mans Ultimate
  testar_demo_lmu.bat       -> demonstracao (dados simulados, sem o jogo)
  diagnostico_lmu.bat       -> grava diagnostico_lmu.txt com o que o overlay enxerga do jogo (use com o jogo aberto)
"""
import json
import math
import shutil
import sys
import tempfile
import time
import traceback
from collections import deque
from pathlib import Path

PASTA = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent   # v1.6.1: no EXE, ao lado do .exe
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(PASTA))

import ov_lmu as lmu                                  # camada de dados do LMU (sem Qt)
import ov_classif_lmu as classif_lmu                  # classificacao detalhada (logica pura)
import ov_estrategia_lmu as estr_lmu                  # energia, stints e tendencia (logica pura)
import ov_alertas_lmu as alertas_lmu                  # alertas na pista (logica pura)
import ov_atalhos_lmu as atalhos_lmu                  # teclas globais para o Stream Deck (mapa proprio do LMU)
import ov_demo_lmu                                    # dados simulados das janelas novas (--demo)
import overlay_iracing as base                        # janelas e calculos ja homologados do overlay do iRacing
import ov_curvas as curvas_mod                      # v1.4.0: velocidade minima por curva (logica pura)
import ov_v16 as v16                                  # v1.6.0: ultimo contato e entrada do pit (logica pura)
import ov_v15 as v15                                  # v1.5.0: bandeiras, trafego, minimapa e auxiliar (logica pura)
import ov_v12 as v12                                  # v1.2.0: logica das Luzes, Retorno a pista e Estrategia de pneus (sem Qt)
nucleo = base.nucleo

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from ov_janela_lmu import JanelaClassificacaoLMU, JanelaClimaLMU, classe_classificacao      # classificacao com mais colunas (so no LMU)
import ov_janelas_extra_lmu as extra_lmu              # janelas novas (energia, pneus, danos, alertas, stints, tendencia)

VERSAO = "LMU 1.6.1 Glass/Sport (base iRacing 1.6.1)"
NOME_JOGO = "Le Mans Ultimate"
DEMO = "--demo" in sys.argv
DIAGNOSTICO = "--diagnostico" in sys.argv

ARQ_CONFIG_LMU = PASTA / "config_lmu.json"
ARQ_LOG_LMU = PASTA / "overlay_log_lmu.txt"
ARQ_DIAGNOSTICO = PASTA / "diagnostico_lmu.txt"


def redirecionar_arquivos(pasta_dados=None, config=None, log=None):
    """Aponta TODOS os arquivos que o codigo do iRacing escreve para arquivos do LMU (ou uma pasta temporaria):
    assim nada do iRacing (config, recordes, mapas, calibracao) e lido ou alterado por este programa."""
    pasta = Path(pasta_dados) if pasta_dados else PASTA
    base.ARQ_CONFIG = Path(config) if config else ARQ_CONFIG_LMU
    base.ARQ_LOG = Path(log) if log else ARQ_LOG_LMU
    base.ARQ_MAPAS = pasta / "mapas_pistas_lmu.json"
    base.ARQ_PNEUS = pasta / "calibracao_pneus_lmu.json"
    base.ARQ_RECORDES = pasta / "recordes_pessoais_lmu.json"
    base.ARQ_HISTORICO = pasta / "historico_projecoes_lmu.csv"
    base.ARQ_PENDENTE = pasta / "projecao_pendente_lmu.json"
    base.ARQ_COMPARACAO = pasta / "comparacao_oficial_lmu.csv"
    base.ARQ_EMBLEMAS_FALTANDO = pasta / "emblemas_faltando_lmu.txt"


def garantir_arquivos_do_lmu():
    """Rede de seguranca: se ninguem redirecionou ainda, aponta os arquivos para os do LMU (nunca grava no log, nos
    recordes ou na configuracao do iRacing)."""
    if base.ARQ_LOG == PASTA / "overlay_log.txt" or base.ARQ_CONFIG == PASTA / "config.json":
        redirecionar_arquivos()


# Chaves que so existem no LMU (o carregar_config do iRacing ignora chaves desconhecidas, por isso sao lidas aqui).
# Posicao e tamanho das janelas novas; limiares dos alertas (definicoes do overlay, nao regras do jogo).
CONFIG_LMU_PADRAO = {
    "x_lmu_energia": 440, "y_lmu_energia": 560, "mostrar_lmu_energia": True, "escala_lmu_energia": 1.0,
    "x_lmu_alertas": 640, "y_lmu_alertas": 60, "mostrar_lmu_alertas": True, "escala_lmu_alertas": 1.0,
    "x_lmu_stints": 60, "y_lmu_stints": 780, "mostrar_lmu_stints": True, "escala_lmu_stints": 1.0,
    "x_lmu_tendencia": 680, "y_lmu_tendencia": 780, "mostrar_lmu_tendencia": True, "escala_lmu_tendencia": 1.0,
    "escala_x_lmu_energia": None, "escala_y_lmu_energia": None, "escala_x_lmu_alertas": None,
    "escala_y_lmu_alertas": None, "escala_x_lmu_stints": None, "escala_y_lmu_stints": None,
    "escala_x_lmu_tendencia": None, "escala_y_lmu_tendencia": None,
    **alertas_lmu.PADRAO,
}


def carregar_config_lmu():
    """Config do LMU = config do overlay do iRacing (mesmas chaves e perfis) + as chaves exclusivas do LMU.
    Valor salvo com tipo errado (arquivo editado a mao) volta ao padrao em vez de derrubar o overlay."""
    cfg = base.carregar_config()
    try:
        salvo = json.loads(base.ARQ_CONFIG.read_text(encoding="utf-8"))
        if not isinstance(salvo, dict):
            salvo = {}
    except Exception:
        salvo = {}
    for chave, padrao in CONFIG_LMU_PADRAO.items():
        valor = salvo.get(chave, padrao)
        if padrao is None:
            ok = valor is None or (isinstance(valor, (int, float)) and not isinstance(valor, bool))
        elif isinstance(padrao, bool):
            ok = isinstance(valor, bool)
        else:
            ok = isinstance(valor, (int, float)) and not isinstance(valor, bool)
        cfg[chave] = valor if ok else padrao
    try:
        base._PERFIS.inicializar(cfg)           # as chaves novas de layout entram tambem nos perfis
    except Exception:
        base.registrar_erro("perfis do LMU")
    return cfg


def semear_config():
    """Primeira execucao: copia a posicao/tamanho das janelas do overlay do iRacing (mesmo layout). So le o config.json."""
    if ARQ_CONFIG_LMU.exists():
        return False
    origem = PASTA / "config.json"
    if not origem.exists():
        return False
    try:
        shutil.copyfile(origem, ARQ_CONFIG_LMU)
        base.registrar_info("config_lmu.json criado a partir do layout do overlay do iRacing (config.json)")
        return True
    except Exception:
        base.registrar_erro("copiar o layout do iRacing")
        return False


# --------------------------------------------------------------------------
# Textos: o desenho do iRacing diz "iRacing"/"SDK"; aqui trocamos so o TEXTO na hora de desenhar
# --------------------------------------------------------------------------
_TROCAS = (("Aguardando o iRacing...", f"Aguardando o {NOME_JOGO}..."),
           ("SDK · vs melhor volta", "JOGO · vs melhor volta"),
           ("iRacing", NOME_JOGO))


def traduzir_texto(texto):
    if texto == "PAIS":            # o LMU nao informa o pais do piloto: a coluna fica vazia (sem cabecalho)
        return ""
    for antigo, novo in _TROCAS:
        if antigo in texto:
            texto = texto.replace(antigo, novo)
    return texto


class PintorLMU(QPainter):
    """QPainter que troca os textos fixos do desenho do iRacing (nao muda nenhuma coordenada nem cor)."""

    def drawText(self, *args):
        return super().drawText(*[traduzir_texto(a) if isinstance(a, str) else a for a in args])


def _pintor_lmu(self):
    p = PintorLMU(self)
    p.scale(self.escala_x, self.escala_y)
    return p


def _sem_pais(self, p, x, y, w, h, codigo):
    """O LMU nao informa o pais do piloto: nao desenha a caixa cinza "---" da coluna PAIS (o espaco e mantido, para o
    layout continuar identico ao do iRacing)."""
    return None


def aplicar_textos_lmu():
    base.JanelaBase._pintor = _pintor_lmu
    base.JanelaClassificacao._pais = _sem_pais


# --------------------------------------------------------------------------
# Telemetria do LMU: produz o MESMO dicionario que o overlay do iRacing entrega as janelas
# --------------------------------------------------------------------------
class TelemetriaLMU:
    """Le o LMU (ov_lmu.LeitorLMU) e monta os dados no formato das janelas. Reaproveita os calculos ja testados:
    consumo de combustivel, calculadora/painel de combustivel, delta proprio, classificacao por classe."""

    PAUSADO_S = 2.0            # dados do jogo sem mudar por este tempo = jogo pausado/menu: janelas se escondem

    def __init__(self, demo=False, leitor=None, relogio=time.monotonic):
        garantir_arquivos_do_lmu()
        self.demo = demo
        self._relogio = relogio
        self._demo = base.Telemetria(demo=True) if demo else None
        self.leitor = leitor or lmu.LeitorLMU(relogio=relogio, ao_mudar_estado=self._estado_mudou)
        self.consumo = base.ConsumoCombustivel()
        self.delta_proprio = base.DeltaProprio()
        self.ritmo = base.RitmoVolta()
        self.margem_combustivel = 1.0
        self._limitador = nucleo.Limitador()
        self._cache = {}
        self._hist_chuva = deque()
        self._pico_g = 0.0
        self._sessao_g = None
        self._et = None
        self._t_et = self._relogio()
        self._pilotos = {}
        self._t_pilotos = 0.0
        self.historico_voltas = classif_lmu.HistoricoVoltas()
        self.consumo_energia = base.ConsumoCombustivel()      # mesma regra de voltas limpas, aplicada a energia virtual (%)
        self.stints = estr_lmu.HistoricoStints()
        self.alertas = alertas_lmu.AlertasLMU()
        self.config = {}                  # preenchido pelo principal (limiares dos alertas)
        self._demo_extra = ov_demo_lmu.DemoExtraLMU(relogio) if demo else None
        self._ult_bandeiras = None
        self._ult_impacto = None
        self._volta_ant = None            # (voltas completas, inicio da volta) para conferir a ultima volta do jogo
        self._avisos = set()
        self.ultimo_estado = lmu.SEM_JOGO
        self.v12_retorno = v12.CalculadorRetorno()        # v1.2.0
        self.v14_curvas = curvas_mod.AnalisadorCurvas()   # v1.4.0
        self.v12_pneus = v12.EstrategiaPneus()
        self.v15_bandeiras = v15.GestorBandeiras()        # v1.5.0
        self.v15_mapa = v15.MapaPlano()
        self.v16_contato = v16.UltimoContato()            # v1.6.0
        self.v16_pit = v16.PitEntrada(base.Telemetria._carregar_pit())
        self._v16_impacto_et = None
        self._memoria_trafego = {}
        self._v12_sessao = None

    # -- eventos / diagnostico ----------------------------------------------------
    def _estado_mudou(self, anterior, estado, motivo):
        base.registrar_info(f"LMU: {anterior} -> {estado}" + (f" ({motivo})" if motivo else ""))

    def _aviso_unico(self, chave, texto):
        if chave not in self._avisos:
            self._avisos.add(chave)
            base.registrar_aviso(texto)

    def _cacheado(self, chave, intervalo, funcao):
        if self._limitador.deve(chave, intervalo, self._relogio()) or chave not in self._cache:
            self._cache[chave] = funcao()
        return self._cache[chave]

    def zerar_pico_g(self):
        self._pico_g = 0.0

    def encerrar(self):
        try:
            self.leitor.fechar()
        except Exception:
            pass

    # -- leitura --------------------------------------------------------------------
    def ler(self):
        if self.demo:
            dados = self._demo.ler()
            dados["tipo_sessao"] = dados.get("tipo_sessao") or "CORRIDA"
            dados.update(self._demo_extra.ler())
            return dados
        t0 = time.perf_counter()
        try:
            return self._ler_real()
        finally:
            base.DESEMPENHO.medir("ciclo", (time.perf_counter() - t0) * 1000.0)
            aviso = base.DESEMPENHO.alerta(self._relogio())
            if aviso:
                base.registrar_aviso(aviso)

    def _ler_real(self):
        dados = base.Telemetria._vazio()
        estado, snap = self.leitor.ler()
        self.ultimo_estado = estado
        if snap is None or estado != lmu.OK:
            return dados
        info = snap.scoring.scoringInfo
        dados["conectado"] = True
        dados["tipo_sessao"] = lmu.tipo_sessao(info.mSession)

        # dados parados (jogo pausado, menu, replay): as janelas se escondem
        agora = self._relogio()
        et = float(info.mCurrentET)
        if et != self._et:
            self._et, self._t_et = et, agora
        pausado = (agora - self._t_et) > self.PAUSADO_S

        i_scor, i_tele = lmu.localizar_jogador(snap)
        scor = snap.scoring.vehScoringInfo[i_scor] if i_scor is not None else None
        tele = snap.telemetry.telemInfo[i_tele] if i_tele is not None else None
        ativo = bool(scor is not None and tele is not None and snap.telemetry.playerHasVehicle
                     and (info.mInRealtime or int(tele.mIgnitionStarter) > 0))
        dados["no_carro"] = bool(ativo and not pausado)

        try:
            dados["clima"] = self._cacheado("clima", 1.0, lambda: self._montar_clima(info, tele))
        except Exception:
            base.registrar_erro("clima")
        try:
            dados["classificacao"] = self._cacheado("classificacao", 0.5, lambda: self._montar_classificacao(snap, i_scor))
        except Exception:
            base.registrar_erro("classificacao")
        if scor is None or tele is None:
            return dados

        try:
            dados["forca_g"] = self._montar_forca_g(info, tele, dados["no_carro"])
        except Exception:
            base.registrar_erro("forca G")

        # --- telemetria do carro ---
        dados["marcha"] = int(tele.mGear)
        dados["velocidade"] = lmu.velocidade_kmh(tele)
        dados["rpm"] = float(tele.mEngineRPM)
        max_rpm = float(tele.mEngineMaxRPM)
        dados["rpm_max"] = max_rpm if max_rpm > 1000 else 8000.0
        dados["acelerador"] = min(1.0, max(0.0, float(tele.mUnfilteredThrottle)))
        dados["freio"] = min(1.0, max(0.0, float(tele.mUnfilteredBrake)))
        dados["embreagem"] = min(1.0, max(0.0, float(tele.mUnfilteredClutch)))
        dados["abs"] = bool(tele.mABSActive)
        dados["tc"] = lmu.controle_tracao(tele)
        dados["abs_nivel"] = lmu.abs_nivel(tele)
        dados["bias"] = lmu.bias_dianteiro_pct(tele)
        dados["volante"] = lmu.volante_graus(tele)
        try:
            self._montar_v12(dados, snap, info, scor, tele, i_scor)
        except Exception:
            base.registrar_erro("v1.2.0 (luzes, retorno, estrategia)")

        # --- voltas e delta ---
        try:
            self._montar_voltas_e_delta(dados, info, scor, tele)
        except Exception:
            base.registrar_erro("voltas e delta")

        # --- combustivel ---
        try:
            self._montar_combustivel(dados, info, scor, tele)
        except Exception:
            base.registrar_erro("combustivel")

        # --- janelas novas do LMU (cada bloco falha sozinho, sem derrubar o resto) ---
        self._montar_extras(dados, snap, info, scor, tele, i_scor)
        return dados

    # -- v1.2.0: Luz do TC, Retorno a pista e Estrategia de pneus ----------------------------------------------------
    def _montar_v12(self, dados, snap, info, scor, tele, i_scor):
        agora = self._relogio()
        chave = (int(info.mSession), round(float(info.mStartET)))
        if self._v12_sessao != chave:
            if self._v12_sessao is not None:
                base.registrar_info("v1.2.0: nova sessao, historicos do Retorno e da Estrategia reiniciados")
            self._v12_sessao = chave
            self.v12_retorno.resetar()
            self.v14_curvas.resetar()
            self.v15_bandeiras.resetar()
            self.v16_contato.resetar()
            self._memoria_trafego.clear()
            self.v12_pneus.resetar()
        # Luz do TC: o LMU informa mTCActive (dado do jogo, nao estimativa, ao contrario do iRacing)
        dados["luz_tc"] = {"ativa": bool(tele.mTCActive), "patinagem": 0.0, "estado": "jogo"}
        fase = int(info.mGamePhase)
        antes_da_largada = fase <= 4                       # grid, volta de apresentacao e luzes: ninguem esta "parado na pista"
        dados["retorno"] = self._cacheado("retorno", 0.1, lambda: self._montar_retorno(dados, snap, info, scor, tele, i_scor,
                                                                                         agora, antes_da_largada))
        dados["estrategia"] = self._cacheado("estrategia", 0.5, lambda: self._montar_estrategia(dados, info, scor, tele,
                                                                                                 agora, antes_da_largada))
        # v1.4.0: velocidade minima por curva
        try:
            pct = self._pct_volta(info, scor)
            sup_rodas = [int(tele.mWheels[i].mSurfaceType) for i in range(4)]
            valido = (bool(dados.get("no_carro")) and not bool(scor.mInPits) and not bool(scor.mInGarageStall)
                      and not all(s in (2, 3, 4) for s in sup_rodas) and not antes_da_largada)
            dados["curvas"] = self.v14_curvas.atualizar(pct, dados["velocidade"], dados["volante"], valido, float(info.mLapDist))
        except Exception:
            base.registrar_erro("curvas")
        try:
            self._montar_v15(dados, snap, info, scor, tele, i_scor, agora, fase)
        except Exception:
            base.registrar_erro("v1.5.0 (bandeiras/trafego/minimapa/auxiliar)")

    def _montar_v15(self, dados, snap, info, scor, tele, i_scor, agora, fase):
        """v1.5.0: bandeiras, trafego de outras classes, minimapa rotativo e auxiliar de sessao."""
        # bandeiras (mGamePhase, bandeiras de setor e a bandeira azul do proprio carro: tudo dado do jogo)
        b = lmu.bandeiras(info)
        cand, verde = v15.candidata_lmu(b["fase"], b["fcy_estado"], b["amarelas_setor"], int(scor.mFlag),
                                        int(scor.mFinishStatus), False)
        dados["bandeira"] = self.v15_bandeiras.atualizar(cand, verde, agora)
        comprimento = float(info.mLapDist)
        no_carro = bool(dados.get("no_carro"))
        carros = self._cacheado("carros_v15", 0.1, lambda: extrair_carros(snap, i_scor))
        meu = next((c for c in carros if c["eu"]), None)
        # trafego (so com voce na pista e fora do box)
        if meu is not None and comprimento > 300.0 and no_carro and not bool(scor.mInPits) and fase >= 5:
            lista = []
            for c in carros:
                if not math.isfinite(c["dist"]):
                    continue
                lista.append({"id": c["id"], "classe_id": c["classe"]["rotulo"], "classe_nome": c["classe"]["rotulo"],
                              "cor": c["classe"]["cor"], "ordem": c["classe"]["ordem"], "numero": c["numero"],
                              "nome": c["nome"], "pct": (c["dist"] / comprimento) % 1.0, "vel": c["vel"],
                              "box": c["box"], "ativo": True})
            dados["trafego"] = v15.montar_trafego(lista, meu["id"], comprimento, dados["velocidade"] / 3.6,
                                                  self._memoria_trafego, agora)
        # minimapa: o LMU informa a posicao no mundo; o tracado e aprendido numa volta limpa
        chave = lmu.texto(info.mTrackName)
        if self.v15_mapa.chave != chave:
            self.v15_mapa.resetar(chave)
        pct = self._pct_volta(info, scor)
        valido = (no_carro and not bool(scor.mInPits) and not bool(scor.mInGarageStall) and fase >= 5)
        self.v15_mapa.atualizar(pct, float(scor.mPos.x), float(scor.mPos.z), valido)
        mapa = self.v15_mapa.exibicao()
        mapa["carros"] = [{"pct": (c["dist"] / comprimento) % 1.0, "numero": c["numero"], "cor": c["classe"]["cor"],
                           "eu": bool(c["eu"])} for c in carros if comprimento > 300.0 and math.isfinite(c["dist"])]
        dados["mapa"] = mapa
        self._montar_v16(dados, scor, tele, info, carros, meu, comprimento, fase, agora, no_carro)
        # auxiliar de sessao
        luzes = (int(info.mStartLight), int(info.mNumRedLights)) if fase == 4 else None
        dados["auxiliar"] = v15.montar_auxiliar_lmu(dados.get("tipo_sessao"), fase, lmu.tempo_restante(info),
                                                    lmu.voltas_da_sessao(info.mMaxLaps), None, luzes)

    def _montar_v16(self, dados, scor, tele, info, carros, meu, comprimento, fase, agora, no_carro):
        """v1.6.0: ultimo contato (impacto do jogo + carro encostado) e entrada do pit."""
        et = float(tele.mLastImpactET)
        if self._v16_impacto_et is None:
            self._v16_impacto_et = et                       # impacto anterior a abertura do overlay: ignora
        elif et != self._v16_impacto_et and et > 0:
            self._v16_impacto_et = et
            if meu is not None and no_carro:
                px, pz = float(scor.mPos.x), float(scor.mPos.z)
                cands = [(c["id"], math.hypot(c["pos_x"] - px, c["pos_z"] - pz), c) for c in carros
                         if not c["eu"] and not c["box"] and math.isfinite(c["pos_x"]) and math.isfinite(c["pos_z"])]
                alvo = v16.escolher_alvo(cands)
                if alvo:
                    idx, c = alvo
                    self.v16_contato.registrar(agora, idx, {"numero": c["numero"], "nome": c["nome"],
                                                            "classe": c["classe"]["rotulo"], "cor": c["classe"]["cor"]},
                                               int(scor.mTotalLaps) + 1, None)      # o LMU nao informa pontos por carro
        c = self.v16_contato.atual
        if c and comprimento > 300.0 and meu is not None:
            outro = next((x for x in carros if x["id"] == c["id"]), None)
            dist = None
            if outro is not None and math.isfinite(outro["dist"]):
                dist = v16._delta_pct(meu["dist"] / comprimento, outro["dist"] / comprimento) * comprimento
            dados["contato"] = self.v16_contato.exibicao(agora, dist, bool(outro and outro["box"]), dados["velocidade"] / 3.6)
        # entrada do pit: o limite vem do limitador medido pelos alertas; o box, de mPitLapDist
        if meu is not None and comprimento > 300.0 and no_carro:
            pct = self._pct_volta(info, scor)
            pit_box = float(scor.mPitLapDist) / comprimento if float(scor.mPitLapDist) > 0 else None
            quer = int(scor.mPitState) in (1, 2)
            pit = self.v16_pit.atualizar(lmu.texto(info.mTrackName), bool(scor.mInPits), pct, comprimento,
                                         dados["velocidade"] / 3.6, self.alertas.limite_pit, pit_box, quer,
                                         bool(self.config.get("pit_sempre", False)))
            if self.v16_pit.mudou:
                self.v16_pit.mudou = False
                try:
                    base.ARQ_PIT.write_text(json.dumps(self.v16_pit.entradas, indent=1), encoding="utf-8")
                except Exception:
                    base.registrar_erro("salvar entradas do pit")
            if pit:
                dados["pit"] = pit

    def _montar_retorno(self, dados, snap, info, scor, tele, i_scor, agora, antes_da_largada):
        carros = extrair_carros(snap, i_scor)
        comprimento = float(info.mLapDist)
        meu = next((i for i, c in enumerate(carros) if c["eu"]), None)
        if meu is None or comprimento <= 100.0:
            return None
        pcts = []
        for c in carros:
            d = c["dist"]
            pcts.append((d / comprimento) % 1.0 if math.isfinite(d) else -1.0)
        sup = [3] * len(carros)                            # 3 = na pista (o LMU nao informa a superficie dos outros carros)
        sup_rodas = [int(tele.mWheels[i].mSurfaceType) for i in range(4)]
        if all(s in (2, 3, 4) for s in sup_rodas):         # grama, terra ou cascalho nas quatro rodas = fora da pista
            sup[meu] = 0
        box = [bool(c["box"]) for c in carros]
        if antes_da_largada or not dados.get("no_carro"):
            box[meu] = True                                # no grid ou fora do carro nao faz sentido avisar
        return self.v12_retorno.atualizar(agora, meu, pcts, sup, box, comprimento, dados["velocidade"] / 3.6,
                                          dados.get("melhor_volta"))

    def _montar_estrategia(self, dados, info, scor, tele, agora, antes_da_largada):
        clima = dados.get("clima") or {}
        nome = lmu.texto(tele.mFrontTireCompoundName) or lmu.texto(tele.mRearTireCompoundName)
        est = base.estilo_pneu(nome)
        meu_tipo = v12.classe_pneu(est[1] if est else None)
        tipo_sessao = dados.get("tipo_sessao")
        pre = ((tipo_sessao == "CORRIDA" and antes_da_largada)
               or (tipo_sessao == "QUALIFICACAO" and bool(scor.mInGarageStall or scor.mInPits)))
        # O LMU nao informa o pneu dos outros carros nem o pedido feito nos boxes: sem vantagem estimada e sem contagem de rivais.
        # tem_chuva = True: no LMU todas as classes tem pneu de chuva disponivel (no iRacing nem todo carro tem)
        res = self.v12_pneus.atualizar(agora, clima.get("pista_molhada"), clima.get("chuva"), meu_tipo,
                                       True, None, pre, None, 0, 0)
        res["meu_pneu_nome"] = nome or None
        return res

    # -- blocos ---------------------------------------------------------------------
    @staticmethod
    def _pct_volta(info, scor):
        comprimento = float(info.mLapDist)
        if comprimento <= 100.0 or not math.isfinite(float(scor.mLapDist)):
            return None
        pct = float(scor.mLapDist) / comprimento
        return pct - math.floor(pct)

    def _montar_voltas_e_delta(self, dados, info, scor, tele):
        concluidas = max(0, int(scor.mTotalLaps))
        dados["volta"] = concluidas + 1                              # volta em andamento
        corrente = float(tele.mElapsedTime) - float(tele.mLapStartET)
        dados["tempo_volta"] = corrente if 0.0 <= corrente < 3600.0 else None
        dados["ultima_volta"] = base.tempo_valido(scor.mLastLapTime)
        dados["melhor_volta"] = base.tempo_valido(scor.mBestLapTime)
        self._conferir_ultima_volta(concluidas, tele, dados["ultima_volta"])

        pct = self._pct_volta(info, scor)
        chave = ((int(info.mSession), round(float(info.mStartET))), lmu.texto(info.mTrackName),
                 lmu.texto(scor.mVehicleName))
        delta, ok = self.delta_proprio.atualizar(
            pct, dados["tempo_volta"], concluidas, bool(scor.mInPits), dados["ultima_volta"],
            chave=chave, motivo=lmu.motivo_volta_suja(scor, tele))
        if ok:
            dados["delta"], dados["delta_ok"], dados["delta_fonte"] = delta, True, "overlay"
        # O delta do proprio jogo (mDeltaBest) NAO e exibido nesta versao: o sinal e a validade dele ainda nao foram
        # conferidos no jogo real. Fica so no log, para comparar com o calculado (ver ROTEIRO_VALIDACAO_LMU.txt).
        jogo = float(tele.mDeltaBest)
        if ok and math.isfinite(jogo):
            base.registrar_calculo("delta LMU: overlay x jogo (mDeltaBest)", 20.0,
                                   overlay=round(delta, 3), jogo=round(jogo, 3), pct=None if pct is None else round(pct, 3))

    def _conferir_ultima_volta(self, concluidas, tele, ultima_jogo):
        """Compara a ultima volta informada pelo jogo com a calculada pelo inicio das voltas (so registra)."""
        inicio = float(tele.mLapStartET)
        if self._volta_ant is not None and concluidas == self._volta_ant[0] + 1 and ultima_jogo:
            calc = inicio - self._volta_ant[1]
            if 20.0 < calc < 3600.0 and abs(calc - ultima_jogo) > 0.25:
                base.registrar_aviso(f"ultima volta: o jogo informou {ultima_jogo:.3f} s e o calculo pelo inicio das "
                                     f"voltas deu {calc:.3f} s (volta {concluidas})")
        if self._volta_ant is None or concluidas != self._volta_ant[0]:
            self._volta_ant = (concluidas, inicio)

    def _montar_combustivel(self, dados, info, scor, tele):
        nivel = float(tele.mFuel)
        capacidade = float(tele.mFuelCapacity)
        capacidade = capacidade if capacidade > 1.0 else None
        concluidas = max(0, int(scor.mTotalLaps))
        na_box = bool(scor.mInPits)
        self.consumo.atualizar(concluidas, nivel, na_box)
        media = self.consumo.media
        dados["combustivel"] = nivel
        dados["consumo_volta"] = media
        dados["voltas_restantes"] = (nivel / media) if media else None

        pct = self._pct_volta(info, scor)
        self.ritmo.atualizar(concluidas, dados["ultima_volta"], na_box)
        estimado = base.tempo_valido(scor.mEstimatedLapTime)
        ritmo = self.ritmo.estimativa or dados["melhor_volta"] or estimado or 210.0
        voltas = lmu.voltas_da_sessao(info.mMaxLaps)
        voltas_restantes_sessao = None if voltas is None else max(0, voltas - concluidas)
        restante = lmu.tempo_restante(info)
        dados["calc_combustivel"] = base.calcular_combustivel(
            nivel, media, voltas_restantes_sessao, restante, ritmo, pct, self.margem_combustivel, capacidade)
        calc = dados["calc_combustivel"] or {}
        registros = list(self.consumo.registros)
        usos = [u for _, u in registros]
        dados["painel_combustivel"] = base.calcular_painel_combustivel(
            nivel, capacidade, media, max(usos) if usos else media, min(usos) if usos else media,
            calc.get("voltas_fim"), max(1, int(dados.get("volta") or 1)), pct, self.margem_combustivel,
            calc.get("ritmo"), restante, registros)

    # -- janelas novas (v1.2) --------------------------------------------------------------------------------------
    def _montar_extras(self, dados, snap, info, scor, tele, i_scor):
        concluidas = max(0, int(scor.mTotalLaps))
        na_box = bool(scor.mInPits)
        ve = lmu.energia_virtual_pct(tele)
        try:
            dados["lmu_energia"] = self._montar_energia(dados, tele, ve, concluidas, na_box)
        except Exception:
            base.registrar_erro("energia virtual")
        try:
            dados["lmu_pneus"] = lmu.pneus_do_carro(tele)
            self._registrar_pneus(dados["lmu_pneus"], tele)
        except Exception:
            base.registrar_erro("pneus")
        try:
            dados["lmu_danos"] = lmu.danos_do_carro(tele)
            self._registrar_impacto(tele)
        except Exception:
            base.registrar_erro("danos")
        try:
            dados["lmu_alertas"] = self._cacheado("alertas", 0.1, lambda: self._montar_alertas(dados, snap, info, scor, tele, i_scor))
        except Exception:
            base.registrar_erro("alertas")
        try:
            self._montar_stints(dados, info, scor, tele, ve, concluidas, na_box)
        except Exception:
            base.registrar_erro("stints e tendencia")

    def _montar_energia(self, dados, tele, ve, concluidas, na_box):
        if ve is not None:
            self.consumo_energia.atualizar(concluidas, ve, na_box)
        capacidade = float(tele.mFuelCapacity)
        capacidade = capacidade if capacidade > 1.0 else None
        calc = dados.get("calc_combustivel") or {}
        painel = estr_lmu.painel_energia(ve, self.consumo_energia.media if ve is not None else None, float(tele.mFuel),
                                         capacidade, self.consumo.media, calc.get("voltas_fim"),
                                         max(1, int(dados.get("volta") or 1)), self.margem_combustivel)
        if painel["alcance"] is not None:
            base.registrar_calculo("energia virtual LMU", 30.0, nivel_pct=None if ve is None else round(ve, 2),
                                   consumo_pct_volta=painel["energia"]["por_volta"] and round(painel["energia"]["por_volta"], 3),
                                   alcance_voltas=round(painel["alcance"], 2), limitante=painel["limitante"],
                                   voltas_fim=painel["voltas_fim"], mensagem=painel["mensagem"])
        return painel

    def _registrar_pneus(self, pn, tele):
        """Valores crus do jogo no log (validacao do sentido do desgaste e das temperaturas no jogo real)."""
        if not self._limitador.deve("log_pneus", 60.0, self._relogio()):
            return
        w = tele.mWheels
        base.registrar_calculo("pneus LMU: valores crus do jogo", 1.0,
                               mWear=[round(float(w[i].mWear), 3) for i in range(4)],
                               composto=[int(w[i].mCompoundType) for i in range(4)],
                               temp_c=[None if r["temp"] is None else round(r["temp"], 1) for r in pn["rodas"]],
                               temp_superficie_c=[None if r["temp_sup"] is None else round(r["temp_sup"], 1) for r in pn["rodas"]],
                               temp_interna_c=[None if r["temp_int"] is None else round(r["temp_int"], 1) for r in pn["rodas"]],
                               temp_carcaca_c=[None if r["temp_carc"] is None else round(r["temp_carc"], 1) for r in pn["rodas"]],
                               freio_bruto_jogo=[None if r["freio_bruto"] is None else round(r["freio_bruto"]) for r in pn["rodas"]],
                               pressao_kpa=[None if r["pressao"] is None else round(r["pressao"], 1) for r in pn["rodas"]],
                               freio_c=[None if r["freio"] is None else round(r["freio"]) for r in pn["rodas"]],
                               vida_pct=[None if r["vida"] is None else round(r["vida"]) for r in pn["rodas"]])

    def _registrar_impacto(self, tele):
        """Cada impacto novo vai para o log com as zonas do jogo (validacao da ordem das 8 zonas)."""
        et = float(tele.mLastImpactET)
        if self._ult_impacto is None:
            self._ult_impacto = et                      # impacto anterior a abertura do overlay: nao registra
            return
        if et != self._ult_impacto and et > 0:
            self._ult_impacto = et
            agora = time.monotonic()
            if agora - getattr(self, "_t_log_impacto", -1e9) < 5.0:      # v1.5.2: no maximo 1 linha a cada 5 s (spam no log)
                return
            self._t_log_impacto = agora
            base.registrar_info("impacto LMU: forca %.0f | zonas (0-2) %s | pos (%.2f, %.2f, %.2f)" % (
                float(tele.mLastImpactMagnitude), [int(tele.mDentSeverity[i]) for i in range(8)],
                float(tele.mLastImpactPos.x), float(tele.mLastImpactPos.y), float(tele.mLastImpactPos.z)))

    def _montar_alertas(self, dados, snap, info, scor, tele, i_scor):
        carros = extrair_carros(snap, i_scor)
        bandeiras = lmu.bandeiras(info)
        chave = (bandeiras["fase"], tuple(bandeiras["amarelas_brutas"]), bandeiras["fcy_estado"])
        if chave != self._ult_bandeiras:                # mudanca de bandeira: log (validacao da numeracao dos setores)
            base.registrar_info(f"bandeiras LMU: fase {bandeiras['fase']} | valores crus dos 3 setores "
                                f"{bandeiras['amarelas_brutas']} | amarelas aceitas {bandeiras['amarelas_setor']}"
                                f"{' (dado suspeito, ignorado)' if bandeiras['amarelas_suspeitas'] else ''} | "
                                f"estado FCY '{bandeiras['fcy_estado']}'")
            self._ult_bandeiras = chave
        ctx = {"bandeiras": bandeiras, "carros": carros, "comprimento": float(info.mLapDist),
               "limitador": {"ativo": bool(tele.mSpeedLimiterActive), "vel": dados.get("velocidade"),
                             "nos_boxes": bool(scor.mInPits)},
               "danos": dados.get("lmu_danos"), "energia": dados.get("lmu_energia")}
        lista = self.alertas.calcular(ctx, self.config)
        return {"lista": lista, "limite_pit": self.alertas.limite_pit}

    def _montar_stints(self, dados, info, scor, tele, ve, concluidas, na_box):
        pn = dados.get("lmu_pneus") or {"rodas": []}
        vidas = [r["vida"] for r in pn["rodas"] if r["vida"] is not None]
        desgaste = (sum(vidas) / len(vidas) / 100.0) if vidas else None
        compostos = [r["composto"] for r in pn["rodas"] if r["composto"]]
        composto = max(set(compostos), key=compostos.count) if compostos else None
        chave = (int(info.mSession), round(float(info.mStartET)), lmu.texto(scor.mVehicleName))
        temp = float(info.mTrackTemp)
        melhor = dados.get("melhor_volta")
        self.stints.atualizar(chave, concluidas, na_box, ve, float(tele.mFuel), desgaste, composto,
                              dados.get("ultima_volta"), melhor, temp if math.isfinite(temp) else None)
        dados["lmu_stints"] = {"stints": self.stints.resumo(melhor)}
        dados["lmu_tendencia"] = self.stints.tendencia(melhor)

    def _montar_forca_g(self, info, tele, no_carro):
        chave = (int(info.mSession), round(float(info.mStartET)))
        if self._sessao_g != chave:
            self._sessao_g, self._pico_g = chave, 0.0
        lat, lon = lmu.forca_g_do_carro(tele)
        if not (math.isfinite(lat) and math.isfinite(lon)):
            return None
        total = math.hypot(lat, lon)
        if no_carro:
            self._pico_g = max(self._pico_g, total)
        temp = float(info.mTrackTemp)
        return {"lat": lat, "lon": lon, "total": total, "pico": self._pico_g,
                "pista": lmu.texto(info.mTrackName), "temp": temp if math.isfinite(temp) else None}

    def _montar_clima(self, info, tele):
        c = lmu.clima_bruto(info)
        chuva = c["chuva_pct"]
        if chuva is not None:
            agora = self._relogio()
            if not self._hist_chuva or agora - self._hist_chuva[-1][0] >= 5.0:
                self._hist_chuva.append((agora, chuva))
                while self._hist_chuva and agora - self._hist_chuva[0][0] > 660.0:
                    self._hist_chuva.popleft()
        vento = lmu.vento_do_carro(info, tele)
        self._registrar_vento(vento, info)
        # O LMU nao tem norte: a direcao e relativa ao carro; "rumo" 0 = carro apontado para cima na bussola do painel
        return {"rumo": 0.0 if vento["dir_rel"] is not None else None,
                "vel_carro": lmu.velocidade_kmh(tele) if tele is not None else 0.0,
                "chuva": chuva, "tendencia_chuva": base.tendencia_chuva(list(self._hist_chuva), chuva),
                "pista_molhada": c["pista_molhada"], "declarado_molhado": False,
                "ceu": c["ceu"], "dinamico": None, "pista": c["pista"], "ar": c["ar"],
                "neblina": None, "vento_dir": vento["dir_rel"], "vento_vel": vento["vel"]}

    def _registrar_vento(self, vento, info):
        """Log (a cada 60 s) do vetor cru do vento: validar no jogo real se o LMU informa velocidade e direcao."""
        if not self._limitador.deve("log_vento", 60.0, self._relogio()):
            return
        mundo, local = vento["mundo"], vento["local"]
        base.registrar_calculo("clima LMU: vento cru do jogo", 1.0,
                               mundo_ms=None if mundo is None else tuple(round(v, 2) for v in mundo),
                               local_esq_cima_tras=None if local is None else tuple(round(v, 2) for v in local),
                               vel_kmh=None if vento["vel"] is None else round(vento["vel"], 1),
                               dir_de_onde_vem_graus=None if vento["dir_rel"] is None else round(math.degrees(vento["dir_rel"])),
                               chuva=round(float(info.mRaining), 2), nuvens=round(float(info.mCloudCoverage), 2),
                               umidade_pista=round(float(info.mAvgPathWetness), 2))

    def _montar_classificacao(self, snap, i_scor):
        info = snap.scoring.scoringInfo
        if i_scor is None:
            return None
        veiculos = snap.scoring.vehScoringInfo
        carros = extrair_carros(snap, i_scor)
        if not carros:
            return None
        tipo = lmu.tipo_sessao(info.mSession)
        total = float(info.mEndET)
        sessao = {"chave": (int(info.mSession), round(float(info.mStartET))),
                  "decorrido": float(info.mCurrentET) if math.isfinite(float(info.mCurrentET)) else None,
                  "total": total if 0 < total < 1.0e6 else None, "restante": lmu.tempo_restante(info),
                  "voltas_total": lmu.voltas_da_sessao(info.mMaxLaps),
                  "pista": lmu.clima_bruto(info)["pista"], "ar": lmu.clima_bruto(info)["ar"]}
        classif = classif_lmu.montar(carros, float(info.mLapDist), tipo, self.historico_voltas, sessao,
                                     volta=max(0, int(veiculos[i_scor].mTotalLaps) + 1))
        if classif is not None:
            self._registrar_comparacao_gap(classif.get("comparacao_gap") or [])
        return classif

    def _registrar_comparacao_gap(self, pares):
        """Validacao no jogo real: o intervalo medido pelo jogo (mTimeBehindNext) concorda com o calculado pela
        posicao na pista? So vai para o log (a cada 60 s)."""
        pares = [(j, e) for j, e in pares if e is not None]
        if not pares or not self._limitador.deve("log_gap", 60.0, self._relogio()):
            return
        difs = sorted(abs(j - e) for j, e in pares)
        base.registrar_calculo("gap da classe LMU: jogo x calculado pela posicao", 1.0, pares=len(difs),
                               dif_mediana=round(difs[len(difs) // 2], 2), dif_max=round(difs[-1], 2))


def extrair_carros(snap, i_scor):
    """Lista de dicts (um por carro) com o que a classificacao precisa, lido da memoria do jogo."""
    info = snap.scoring.scoringInfo
    n = max(0, min(int(info.mNumVehicles), lmu.MAX_CARROS))
    veiculos = snap.scoring.vehScoringInfo
    carros = []
    for i in range(n):
        v = veiculos[i]
        if int(v.mPlace) <= 0:
            continue
        veiculo = lmu.texto(v.mVehicleName)
        piloto = lmu.texto(v.mDriverName)
        carros.append({
            "id": int(v.mID), "piloto": piloto, "veiculo": veiculo, "eu": i == i_scor, "lugar": int(v.mPlace),
            "classe": lmu.classe_do_carro(v.mVehicleClass), "numero": lmu.numero_do_carro(veiculo),
            "marca": base.marca_do_carro(veiculo, fallback=False), "nome": base.nome_curto(piloto),
            "voltas": int(v.mTotalLaps), "dist": float(v.mLapDist), "ultima": float(v.mLastLapTime),
            "melhor": float(v.mBestLapTime), "box": bool(v.mInPits) or int(v.mPitState) in (2, 3, 4),
            "paradas": int(v.mNumPitstops), "penalidades": int(v.mNumPenalties),
            "combustivel": int(v.mFuelFraction), "tbn": float(v.mTimeBehindNext), "lbn": int(v.mLapsBehindNext),
            "tbl": float(v.mTimeBehindLeader), "lbl": int(v.mLapsBehindLeader), "quali": int(v.mQualification),
            "final": int(v.mFinishStatus),
            "vel": math.sqrt(float(v.mLocalVel.x) ** 2 + float(v.mLocalVel.y) ** 2 + float(v.mLocalVel.z) ** 2),
            "pit_estado": int(v.mPitState), "pit_dist": float(v.mPitLapDist), "bandeira": int(v.mFlag),
            "pos_x": float(v.mPos.x), "pos_z": float(v.mPos.z)})
    return carros


# --------------------------------------------------------------------------
# Diagnostico (sem janelas): o que o overlay enxerga do jogo
# --------------------------------------------------------------------------
def sondar_api_local(porta=6397, caminhos=("/swagger/v1/swagger.json", "/rest/sessions/weather", "/rest/sessions", "/")):
    """Diagnostico: consulta (GET, so leitura) a API local oficial do jogo e registra o que ela responde, para saber se
    traz previsao do tempo/vento. Nao altera nada no jogo. Qualquer falha so vira texto."""
    import urllib.error
    import urllib.request
    saida = []
    for caminho in caminhos:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{porta}{caminho}", timeout=2.0) as r:
                corpo = r.read(1500).decode("utf-8", "replace").replace("\r", " ").replace("\n", " ")
                saida.append(f"GET {caminho}: HTTP {r.status} | {corpo[:600]}")
        except urllib.error.HTTPError as e:
            saida.append(f"GET {caminho}: HTTP {e.code}")
        except Exception as e:
            saida.append(f"GET {caminho}: sem resposta ({type(e).__name__})")
            if "WinError" in str(e) or isinstance(e, (ConnectionError, TimeoutError, OSError)):
                break                                    # porta fechada: nao adianta tentar os outros caminhos
    return saida


def gerar_diagnostico(leitor=None):
    leitor = leitor or lmu.LeitorLMU()
    estado, snap = leitor.ler()
    linhas = [f"Diagnostico do overlay LMU - {time.strftime('%Y-%m-%d %H:%M:%S')}",
              f"versao: {VERSAO} | python {sys.version.split()[0]} | tamanho da estrutura esperada: {lmu.TAMANHO} bytes",
              f"estado da conexao: {estado}" + (f" ({leitor.motivo})" if leitor.motivo else "")]
    if snap is None:
        linhas.append("Sem dados. Conferir: jogo aberto? 'Enable Plugins' ligado em Settings > Gameplay? "
                      "jogo em janela sem borda (nao tela cheia exclusiva)?")
        return "\n".join(linhas), estado
    info = snap.scoring.scoringInfo
    i_scor, i_tele = lmu.localizar_jogador(snap)
    linhas += [f"versao do jogo (generic.gameVersion): {snap.generic.gameVersion}",
               f"pista: {lmu.texto(info.mTrackName)} | comprimento: {info.mLapDist:.0f} m | sessao: {info.mSession} "
               f"({lmu.tipo_sessao(info.mSession)}) | fase: {info.mGamePhase} | carros: {info.mNumVehicles}",
               f"tempo da sessao: {info.mCurrentET:.1f} s | fim: {info.mEndET:.1f} s | voltas max: {info.mMaxLaps} | "
               f"mInRealtime: {info.mInRealtime}",
               f"clima: pista {info.mTrackTemp:.1f} C | ar {info.mAmbientTemp:.1f} C | chuva {info.mRaining:.2f} | "
               f"umidade media {info.mAvgPathWetness:.2f} | nuvens {info.mCloudCoverage} | "
               f"vento ({info.mWind.x:.1f}, {info.mWind.y:.1f}, {info.mWind.z:.1f}) m/s",
               f"indice do jogador no scoring: {i_scor} | na telemetria: {i_tele} | playerHasVehicle: "
               f"{snap.telemetry.playerHasVehicle}"]
    if i_scor is not None:
        s = snap.scoring.vehScoringInfo[i_scor]
        linhas += [f"jogador: {lmu.texto(s.mDriverName)} | carro: '{lmu.texto(s.mVehicleName)}' "
                   f"(numero lido: '{lmu.numero_do_carro(s.mVehicleName)}') | classe: '{lmu.texto(s.mVehicleClass)}'",
                   f"posicao: {s.mPlace} | voltas completas: {s.mTotalLaps} | distancia na volta: {s.mLapDist:.1f} m | "
                   f"ultima: {s.mLastLapTime:.3f} | melhor: {s.mBestLapTime:.3f} | nos boxes: {s.mInPits}"]
    if i_tele is not None:
        t = snap.telemetry.telemInfo[i_tele]
        lat, lon = lmu.forca_g_do_carro(t)
        linhas += [f"telemetria: marcha {t.mGear} | {lmu.velocidade_kmh(t):.0f} km/h | {t.mEngineRPM:.0f} rpm "
                   f"(max {t.mEngineMaxRPM:.0f}) | acel {t.mUnfilteredThrottle:.2f} freio {t.mUnfilteredBrake:.2f} "
                   f"embr {t.mUnfilteredClutch:.2f} | volante {t.mUnfilteredSteering:.2f}",
                   f"combustivel: {t.mFuel:.2f} L de {t.mFuelCapacity:.1f} L | energia virtual: {t.mVirtualEnergy:.3f} | "
                   f"G lateral {lat:+.2f} (>0 = esquerda) | G longitudinal {lon:+.2f} (>0 = acelerando)",
                   f"delta do jogo (mDeltaBest): {t.mDeltaBest:+.3f} | volta invalidada: {t.mLapInvalidated} | "
                   f"balanco de freio dianteiro: {lmu.bias_dianteiro_pct(t)} | TC: {t.mTC}/{t.mTCMax} | ABS: {t.mABS}/{t.mABSMax}"]
    if i_tele is not None:
        t = snap.telemetry.telemInfo[i_tele]
        pn, dn = lmu.pneus_do_carro(t), lmu.danos_do_carro(t)
        w = t.mWheels
        linhas.append("--- janelas novas: valores CRUS do jogo (para conferir sentido e ordem no jogo real) ---")
        for i, r in enumerate(pn["rodas"]):
            linhas.append(f"roda {r['roda']}: mWear {float(w[i].mWear):.3f} (vida mostrada {r['vida']}) | composto {int(w[i].mCompoundType)} "
                          f"'{r['composto_nome']}' | temp banda {[round(float(x) - lmu.KELVIN, 1) for x in w[i].mTemperature]} C | "
                          f"pressao {float(w[i].mPressure):.1f} kPa | freio bruto {float(w[i].mBrakeTemp):.0f} (= {float(w[i].mBrakeTemp) - lmu.KELVIN:.0f} C se Kelvin) | camada interna {[round(float(x) - lmu.KELVIN, 1) for x in w[i].mTireInnerLayerTemperature]} C | carcaca {float(w[i].mTireCarcassTemperature) - lmu.KELVIN:.1f} C | otima {float(w[i].mOptimalTemp):.1f} | "
                          f"furado {bool(w[i].mFlat)} | solta {bool(w[i].mDetached)}")
        linhas.append(f"oleo {pn['oleo']} C | agua {pn['agua']} C | superaquecendo {dn['superaquecendo']} | peca solta {dn['solta']}")
        linhas.append(f"zonas de dano (mDentSeverity, 0-2, ordem a confirmar: {', '.join(lmu.ZONAS_DANO)}): {dn['zonas']} | "
                      f"ultimo impacto: ha {dn['impacto_desde']} s, forca {dn['impacto_forca']}, lado (pela posicao) {dn['impacto_lado']} | "
                      f"posicao local do impacto (x esq+, z tras+): ({float(t.mLastImpactPos.x):.2f}, {float(t.mLastImpactPos.z):.2f})")
        bd = lmu.bandeiras(info)
        linhas.append(f"bandeiras: fase {bd['fase']} | FCY {bd['fcy']} ('{bd['fcy_estado']}') | amarelas por setor (indice do jogo, "
                      f"0..2) aceitas {bd['amarelas_setor']} | valores CRUS {bd['amarelas_brutas']} | suspeito {bd['amarelas_suspeitas']} | setor do jogador (mSector, 0=S3 1=S1 2=S2): "
                      f"{snap.scoring.vehScoringInfo[i_scor].mSector if i_scor is not None else None}")
        if i_scor is not None:
            s = snap.scoring.vehScoringInfo[i_scor]
            v = s.mLocalVel
            linhas.append(f"boxes: estado {int(s.mPitState)} (0 nada, 1 pedido, 2 entrando, 3 parado, 4 saindo) | distancia dos boxes na volta "
                          f"{float(s.mPitLapDist):.0f} m | limitador ativo {bool(t.mSpeedLimiterActive)} (disponivel {int(t.mSpeedLimiterAvailable)}) | "
                          f"velocidade {math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2) * 3.6:.1f} km/h | bandeira do carro (mFlag) {int(s.mFlag)}")
        vt = lmu.vento_do_carro(info, t)
        linhas.append(f"vento: vetor do jogo (m/s) {None if vt['mundo'] is None else tuple(round(x, 2) for x in vt['mundo'])} | "
                      f"no eixo do carro (esq, cima, tras) {None if vt['local'] is None else tuple(round(x, 2) for x in vt['local'])} | "
                      f"velocidade {None if vt['vel'] is None else round(vt['vel'], 1)} km/h | direcao relativa (de onde vem, graus a partir da frente) "
                      f"{None if vt['dir_rel'] is None else round(math.degrees(vt['dir_rel']))}  [vetor zero = o jogo nao informa o vento]")
    linhas.append("--- API local do jogo (so leitura, http://localhost:6397): existe e tem previsao do tempo/vento? ---")
    linhas += sondar_api_local()
    linhas.append("--- janela do jogo (o overlay aparece por cima?) ---")
    linhas.append(lmu.descrever_janela_jogo(lmu.janela_do_jogo()))
    linhas.append("--- carros: posicao | classe | numero | marca | piloto | veiculo ---")
    linhas.append("    (cada carro tem uma 2a linha: voltas, distancia, paradas, penalidades, combustivel 0-255, "
                  "tempo/voltas atras do proximo e do lider, qualificacao, resultado, estado de boxes)")
    for i in range(min(int(info.mNumVehicles), lmu.MAX_CARROS)):
        v = snap.scoring.vehScoringInfo[i]
        nome = lmu.texto(v.mVehicleName)
        linhas.append(f"{int(v.mPlace):3d} | {lmu.texto(v.mVehicleClass):10s} | #{lmu.numero_do_carro(nome):3s} | "
                      f"{base.marca_do_carro(nome, fallback=False):14s} | {lmu.texto(v.mDriverName):22s} | {nome}")
        linhas.append(f"      voltas {v.mTotalLaps} | dist {v.mLapDist:.0f} m | paradas {v.mNumPitstops} | pen {v.mNumPenalties} | "
                      f"comb {v.mFuelFraction}/255 | prox {v.mTimeBehindNext:.2f} s +{v.mLapsBehindNext}v | "
                      f"lider {v.mTimeBehindLeader:.2f} s +{v.mLapsBehindLeader}v | quali {v.mQualification} | "
                      f"resultado {v.mFinishStatus} | boxes {int(v.mInPits)}/{v.mPitState}")
    return "\n".join(linhas), estado


# --------------------------------------------------------------------------
# Janelas e bandeja
# --------------------------------------------------------------------------
def criar_icone():
    try:                                           # v1.6.0: logo WXR original (arquivo marca/logo_wxr.png), se existir
        logo = base.PASTA / "marca" / "logo_wxr.png"
        if logo.is_file():
            pm = QPixmap(str(logo))
            if not pm.isNull():
                return QIcon(pm)
    except Exception:
        pass
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(0, 110, 220))
    p.setPen(Qt.NoPen)
    p.drawEllipse(4, 4, 56, 56)
    p.setPen(QColor(255, 255, 255))
    p.setFont(base.fonte(26, QFont.Bold))
    p.drawText(pix.rect(), Qt.AlignCenter, "LM")
    p.end()
    return QIcon(pix)


def trava_instancia_unica():
    from PySide6.QtCore import QLockFile
    nome = "overlay_lmu_demo.lock" if DEMO else "overlay_lmu.lock"
    trava = QLockFile(str(Path(tempfile.gettempdir()) / nome))
    trava.setStaleLockTime(0)
    return trava if trava.tryLock(200) else None


def criar_api_teclas():
    """Acesso do Windows aos atalhos globais (Stream Deck). Retorna None fora do Windows ou se falhar."""
    if sys.platform != "win32":
        return None
    try:
        return nucleo.ApiTeclasWindows()
    except Exception:
        base.registrar_erro("atalhos globais (api do Windows)")
        return None


def principal(leitor=None, config_extra=None, ao_iniciar=None, api_teclas=None):
    """`leitor`, `config_extra`, `ao_iniciar` e `api_teclas` existem so para os testes automaticos."""
    garantir_arquivos_do_lmu()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    trava = trava_instancia_unica()
    if trava is None:
        QMessageBox.information(None, "Overlay LMU", "O overlay do LMU ja esta em execucao.\n\nProcure o icone azul "
                                "com \"LM\" perto do relogio do Windows (pode estar na setinha ^).")
        return 0

    semear_config()
    config = carregar_config_lmu()
    if config_extra:
        config.update(config_extra)
    versoes = {"overlay": VERSAO, "nucleo": nucleo.VERSAO_NUCLEO, "python": sys.version.split()[0], "SO": sys.platform,
               "estrutura_lmu": f"{lmu.TAMANHO} bytes", "modo": "demo" if DEMO else NOME_JOGO}
    try:
        import PySide6
        versoes["PySide6"] = PySide6.__version__
    except Exception:
        pass
    base._REGISTRO.cabecalho(versoes)
    if config.get("tema_vidro", True) and config.get("tema_sport", False):
        config["tema_sport"] = False                  # Glass Fume e Sport sao excludentes (config antigo: vence o Glass Fume)
    base.definir_tema(config.get("tema_moderno", True), config.get("opacidade_fundo", 0.80), config.get("tema_sport", False), config.get("tema_vidro", True))
    base.JanelaBase.MULT_TAXA = 0.5 if config.get("economia_cpu") else 1.0
    if config.get("prioridade_baixa", True) and not DEMO and base.definir_prioridade_baixa(True):
        base.registrar_info("prioridade do processo do overlay: abaixo do normal")

    telemetria = TelemetriaLMU(demo=DEMO, leitor=leitor)
    telemetria.margem_combustivel = float(config.get("margem_combustivel", 1.0))
    telemetria.config = config
    janela_telemetria = base.JanelaTelemetria(config)
    janela_voltas = base.JanelaVoltas(config)
    janela_classificacao = classe_classificacao(config)(config)
    janela_clima = JanelaClimaLMU(config)
    janela_combustivel = base.JanelaCombustivel(config)
    janela_forca_g = base.JanelaForcaG(config)
    janela_energia = extra_lmu.JanelaEnergiaLMU(config)
    janela_pneus = extra_lmu.JanelaPneusLMU(config)
    janela_danos = extra_lmu.JanelaDanosLMU(config)
    janela_alertas = extra_lmu.JanelaAlertasLMU(config)
    janela_stints = extra_lmu.JanelaStintsLMU(config)
    janela_tendencia = extra_lmu.JanelaTendenciaLMU(config)
    janela_luz_abs = base.JanelaLuzAbs(config)
    janela_luz_tc = base.JanelaLuzTc(config)
    janela_retorno = base.JanelaRetorno(config)
    janela_estrategia = base.JanelaEstrategia(config)
    janela_curvas = base.JanelaCurvas(config)
    janela_bandeiras = base.JanelaBandeiras(config)
    janela_trafego = base.JanelaTrafego(config)
    janela_minimapa = base.JanelaMinimapa(config)
    janela_auxiliar = base.JanelaAuxiliar(config)
    janela_contato = base.JanelaUltimoContato(config)
    janela_pit = base.JanelaPitEntrada(config)
    telemetria.v12_retorno.definir_limites(config.get("retorno_pare", 1.5), config.get("retorno_ceda", 3.5))
    janelas = [janela_telemetria, janela_voltas, janela_classificacao, janela_clima, janela_combustivel, janela_forca_g,
               janela_energia, janela_pneus, janela_danos, janela_alertas, janela_stints, janela_tendencia,
               janela_luz_abs, janela_luz_tc, janela_retorno, janela_estrategia, janela_curvas,
               janela_bandeiras, janela_trafego, janela_minimapa, janela_auxiliar, janela_contato, janela_pit]
    for j in janelas:
        j.setWindowTitle("Overlay " + NOME_JOGO)
    visib = base.VisibilidadeAuto(bool(config.get("auto_modo", True)) and not DEMO)
    if not config["travado"]:
        visib.visivel = True
    for j in janelas:
        j.definir_auto_visivel(visib.visivel)

    icone = criar_icone()
    bandeja = QSystemTrayIcon(icone, app)
    bandeja.setToolTip("Overlay " + NOME_JOGO + (" (demo)" if DEMO else ""))
    menu = QMenu()
    acoes = []
    acao_por_chave = {}            # chave do config -> item marcavel do menu (os atalhos globais usam estes mesmos itens)

    def adicionar(texto_menu, marcado, ao_alterar, chave=None):
        acao = QAction(texto_menu, menu)
        acao.setCheckable(True)
        acao.setChecked(bool(marcado))
        acao.toggled.connect(ao_alterar)
        menu.addAction(acao)
        acoes.append(acao)
        if chave:
            acao_por_chave[chave] = acao
        return acao

    def alternar_janela(janela):
        def f(marcado):
            janela.definir_ativo(marcado)
            base.salvar_config(config)
        return f

    def ao_travar(marcado):
        for j in janelas:
            j.aplicar_travamento(marcado)
        base.salvar_config(config)

    def guardar(chave, efeito=None):
        def f(marcado):
            config[chave] = bool(marcado)
            if efeito:
                efeito(marcado)
            base.salvar_config(config)
        return f

    def ao_economia(marcado):
        base.JanelaBase.MULT_TAXA = 0.5 if marcado else 1.0

    def ao_tema(marcado):
        base.definir_tema(moderno=marcado)
        for j in janelas:
            j.update()

    def _sincronizar_estilo():
        for chave in ("tema_sport", "tema_vidro"):
            acao = acao_por_chave.get(chave)
            if acao is not None and acao.isChecked() != bool(config.get(chave)):
                acao.blockSignals(True)
                acao.setChecked(bool(config.get(chave)))
                acao.blockSignals(False)

    def ao_sport(marcado):
        if marcado:
            config["tema_vidro"] = False
        base.definir_tema(sport=marcado)
        _sincronizar_estilo()
        for j in janelas:
            j.update()

    def ao_vidro(marcado):
        if marcado:
            config["tema_sport"] = False
        base.definir_tema(vidro=marcado)
        _sincronizar_estilo()
        for j in janelas:
            j.update()

    def ao_opacidade(valor):
        config["opacidade_fundo"] = float(valor)
        base.definir_tema(opacidade=valor)
        for j in janelas:
            j.update()
        base.salvar_config(config)

    def ao_margem(valor):
        config["margem_combustivel"] = float(valor)
        telemetria.margem_combustivel = float(valor)
        base.salvar_config(config)

    def ao_alcance_g(valor):
        config["g_max"] = float(valor)
        janela_forca_g.update()
        base.salvar_config(config)

    def ao_restaurar_tamanhos():
        for j in janelas:
            j.definir_escala(1.0, salvar=False)
        base.salvar_config(config)

    def ao_reforcar(marcado):
        if marcado:
            base.reforcar_sobreposicao(janelas)

    adicionar("Travar posicao (cliques atravessam o overlay)", config["travado"], ao_travar, chave="travado")
    adicionar("Aparecer sozinho ao entrar no carro (so com as janelas travadas)", config["auto_modo"],
              guardar("auto_modo", lambda m: setattr(visib, "automatico", bool(m))), chave="auto_modo")
    adicionar("Modo economia de CPU (metade das atualizacoes por segundo)", config["economia_cpu"],
              guardar("economia_cpu", ao_economia), chave="economia_cpu")
    if sys.platform == "win32":
        adicionar("Prioridade baixa do overlay (o jogo tem preferencia na CPU)", config["prioridade_baixa"],
                  guardar("prioridade_baixa", lambda m: base.definir_prioridade_baixa(m)))
    menu.addSeparator()
    adicionar("Mostrar telemetria (marcha, velocidade e pedais)", config["mostrar_telemetria"], alternar_janela(janela_telemetria), chave="mostrar_telemetria")
    adicionar("   Grafico de acelerador e freio (na telemetria)", config["mostrar_grafico"],
              lambda m: (janela_telemetria.definir_grafico(m), base.salvar_config(config)), chave="mostrar_grafico")
    adicionar("   Layout em barra horizontal (na telemetria)", config["telemetria_barra"],
              lambda m: (janela_telemetria.definir_barra(m), base.salvar_config(config)), chave="telemetria_barra")
    adicionar("Mostrar delta e voltas", config["mostrar_voltas"], alternar_janela(janela_voltas), chave="mostrar_voltas")
    adicionar("   Calculo de combustivel (na janela Voltas)", config["mostrar_calc_combustivel"],
              lambda m: (janela_voltas.definir_calc(m), base.salvar_config(config)), chave="mostrar_calc_combustivel")
    adicionar("Mostrar classificacao", config["mostrar_classificacao"], alternar_janela(janela_classificacao), chave="mostrar_classificacao")
    adicionar("   Classificacao: mostrar todas as classes", config["classificacao_todas"],
              lambda m: (config.__setitem__("classificacao_todas", bool(m)), janela_classificacao.recalcular(),
                         base.salvar_config(config)), chave="classificacao_todas")
    adicionar("Mostrar clima e chuva", config["mostrar_clima"], alternar_janela(janela_clima), chave="mostrar_clima")
    adicionar("   Vento: inverter a direcao da seta (se estiver ao contrario)", bool(config.get("vento_invertido")),
              guardar("vento_invertido", lambda m: janela_clima.update()))
    adicionar("Mostrar painel de combustivel e pit", config["mostrar_combustivel"], alternar_janela(janela_combustivel), chave="mostrar_combustivel")
    submenu_margem = menu.addMenu("   Margem de seguranca do combustivel")
    grupo_margem = QActionGroup(submenu_margem)
    grupo_margem.setExclusive(True)
    for valor in (0.5, 1.0, 1.5, 2.0):
        a = QAction(f"{valor:g} volta(s) de folga", submenu_margem)
        a.setCheckable(True)
        a.setChecked(abs(float(config.get("margem_combustivel", 1.0)) - valor) < 1e-6)
        a.triggered.connect(lambda _m=False, v=valor: ao_margem(v))
        grupo_margem.addAction(a)
        submenu_margem.addAction(a)
        acoes.append(a)
    adicionar("Mostrar forca G", config["mostrar_forca_g"], alternar_janela(janela_forca_g), chave="mostrar_forca_g")
    submenu_g = menu.addMenu("   Alcance da forca G (aneis)")
    grupo_g = QActionGroup(submenu_g)
    grupo_g.setExclusive(True)
    for valor in (2.0, 3.0, 4.0, 5.0):
        a = QAction(f"ate {valor:g} g", submenu_g)
        a.setCheckable(True)
        a.setChecked(abs(float(config.get("g_max", 4.0)) - valor) < 1e-6)
        a.triggered.connect(lambda _m=False, v=valor: ao_alcance_g(v))
        grupo_g.addAction(a)
        submenu_g.addAction(a)
        acoes.append(a)
    acao_zerar_g = QAction("   Zerar o pico de G", menu)
    acao_zerar_g.triggered.connect(telemetria.zerar_pico_g)
    menu.addAction(acao_zerar_g)
    menu.addSeparator()
    adicionar("Mostrar energia virtual e combustivel (LMU)", config["mostrar_lmu_energia"], alternar_janela(janela_energia), chave="mostrar_lmu_energia")
    adicionar("Mostrar pneus e freios (LMU)", config["mostrar_pneus"], alternar_janela(janela_pneus), chave="mostrar_pneus")
    adicionar("Mostrar danos do carro (LMU)", config["mostrar_danos"], alternar_janela(janela_danos), chave="mostrar_danos")
    adicionar("Mostrar alertas na pista (LMU)", config["mostrar_lmu_alertas"], alternar_janela(janela_alertas), chave="mostrar_lmu_alertas")
    adicionar("Mostrar historico de stints (LMU)", config["mostrar_lmu_stints"], alternar_janela(janela_stints), chave="mostrar_lmu_stints")
    adicionar("Mostrar tendencia de ritmo (LMU)", config["mostrar_lmu_tendencia"], alternar_janela(janela_tendencia), chave="mostrar_lmu_tendencia")
    menu.addSeparator()

    # ---- v1.2.0: grafico de pedais da Telemetria, Luzes do ABS e do TC, Retorno a pista e Estrategia de pneus ----
    def _submenu_escolha(titulo, chave, opcoes, ao_mudar):
        sub = menu.addMenu(titulo)
        grupo = QActionGroup(sub)
        grupo.setExclusive(True)
        for valor, rotulo in opcoes:
            a = QAction(rotulo, sub)
            a.setCheckable(True)
            a.setChecked(config.get(chave) == valor)
            a.triggered.connect(lambda _m=False, v=valor: ao_mudar(chave, v))
            grupo.addAction(a)
            sub.addAction(a)
            acoes.append(a)
        return sub

    def _definir(chave, valor, depois=None):
        config[chave] = valor
        if depois:
            depois()
        base.salvar_config(config)

    def ao_flag(chave):
        def fn(marcado):
            _definir(chave, bool(marcado))
        return fn

    def ao_inputs_opcao(chave, valor):
        _definir(chave, valor, janela_telemetria.reconfigurar)

    def ao_peca(chave):
        def fn(marcado):
            _definir(chave, bool(marcado), janela_telemetria.reconfigurar)
        return fn

    def ao_luz_opcao(chave, valor):
        _definir(chave, valor, lambda: (janela_luz_abs.update(), janela_luz_tc.update()))

    def ao_retorno_limite(chave, valor):
        def aplicar():
            lp, lc = v12.normalizar_limites(config.get("retorno_pare", 1.5), config.get("retorno_ceda", 3.5))
            config["retorno_pare"], config["retorno_ceda"] = lp, lc
            telemetria.v12_retorno.definir_limites(lp, lc)
        _definir(chave, valor, aplicar)

    _submenu_escolha("   Telemetria: tempo do grafico de pedais", "inputs_segundos",
                     [(5, "5 segundos"), (8, "8 segundos"), (12, "12 segundos (padrao)"), (20, "20 segundos"), (30, "30 segundos")],
                     ao_inputs_opcao)
    for rotulo_p, chave_p in (("Degraus das marchas no grafico", "inputs_marchas_fundo"),
                              ("Marca do ABS (amarelo) no freio", "inputs_marca_abs"),
                              ("Marca do TC (azul) no acelerador", "inputs_marca_tc")):
        adicionar("   Telemetria: " + rotulo_p, config[chave_p], ao_peca(chave_p), chave=chave_p)
    adicionar("Mostrar Luz do ABS", config["mostrar_luz_abs"], alternar_janela(janela_luz_abs), chave="mostrar_luz_abs")
    _submenu_escolha("   Luz do ABS: cor", "luz_abs_cor",
                     [("dourado", "Dourado (padrao)"), ("vermelho", "Vermelho"), ("branco", "Branco")], ao_luz_opcao)
    _submenu_escolha("   Luz do ABS: como pisca", "luz_abs_modo",
                     [("ritmo", "No ritmo do ABS (padrao)"), ("suave", "Piscada suave"), ("fixa", "Luz fixa")], ao_luz_opcao)
    adicionar("   Luz do ABS: deixar visivel e apagada quando nao atua", config["luz_abs_apagada"], ao_flag("luz_abs_apagada"),
              chave="luz_abs_apagada")
    acao_teste_abs = QAction("   Testar a Luz do ABS (5 s)", menu)
    acao_teste_abs.triggered.connect(lambda: janela_luz_abs.testar(5.0))
    menu.addAction(acao_teste_abs)
    adicionar("Mostrar Luz do TC (controle de tracao atuando)", config["mostrar_luz_tc"], alternar_janela(janela_luz_tc), chave="mostrar_luz_tc")
    _submenu_escolha("   Luz do TC: cor", "luz_tc_cor",
                     [("azul", "Azul (padrao)"), ("dourado", "Dourado"), ("vermelho", "Vermelho"), ("branco", "Branco")],
                     ao_luz_opcao)
    _submenu_escolha("   Luz do TC: como pisca", "luz_tc_modo",
                     [("ritmo", "No ritmo do TC (padrao)"), ("suave", "Piscada suave"), ("fixa", "Luz fixa")], ao_luz_opcao)
    adicionar("   Luz do TC: deixar visivel e apagada quando nao atua", config["luz_tc_apagada"], ao_flag("luz_tc_apagada"),
              chave="luz_tc_apagada")
    acao_teste_tc = QAction("   Testar a Luz do TC (5 s)", menu)
    acao_teste_tc.triggered.connect(lambda: janela_luz_tc.testar(5.0))
    menu.addAction(acao_teste_tc)
    adicionar("Mostrar Retorno a pista (PARE / CEDA / LIVRE)", config["mostrar_retorno"], alternar_janela(janela_retorno), chave="mostrar_retorno")
    _submenu_escolha("   Retorno: nao entre abaixo de (vermelho)", "retorno_pare",
                     [(v, f"{v:g} s" + ("  (padrao)" if v == 1.5 else "")) for v in (1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0)],
                     ao_retorno_limite)
    _submenu_escolha("   Retorno: entre cedendo abaixo de (laranja)", "retorno_ceda",
                     [(v, f"{v:g} s" + ("  (padrao)" if v == 3.5 else "")) for v in (2.0, 3.5, 5.0, 7.0, 10.0, 15.0, 25.0)],
                     ao_retorno_limite)
    adicionar("   Retorno: deixar sempre visivel enquanto piloto", config["retorno_sempre"], ao_flag("retorno_sempre"),
              chave="retorno_sempre")
    acao_teste_ret = QAction("   Testar o aviso de Retorno (9 s)", menu)
    acao_teste_ret.triggered.connect(lambda: janela_retorno.testar(9.0))
    menu.addAction(acao_teste_ret)
    adicionar("Mostrar Estrategia de pneus (chuva x seco)", config["mostrar_estrategia"], alternar_janela(janela_estrategia), chave="mostrar_estrategia")
    adicionar("   Estrategia: pulsar quando for hora de trocar", config["estrategia_pulsar"], ao_flag("estrategia_pulsar"),
              chave="estrategia_pulsar")
    adicionar("Mostrar Curvas (velocidade minima x melhor passagem)", config["mostrar_curvas"], alternar_janela(janela_curvas), chave="mostrar_curvas")
    adicionar("Mostrar Bandeiras (so aparece com bandeira)", config["mostrar_bandeiras"], alternar_janela(janela_bandeiras), chave="mostrar_bandeiras")
    adicionar("Mostrar Trafego de outras classes (so com carro por perto)", config["mostrar_trafego"], alternar_janela(janela_trafego), chave="mostrar_trafego")
    adicionar("Mostrar Minimapa rotativo", config["mostrar_minimapa"], alternar_janela(janela_minimapa), chave="mostrar_minimapa")
    acao_raio = QAction(f"   Minimapa: alcance {int(config.get('minimapa_raio', 260))} m (clique para trocar)", menu)

    def trocar_raio():
        raios = base.JanelaMinimapa.RAIOS
        atual = float(config.get("minimapa_raio", 260.0))
        config["minimapa_raio"] = raios[(raios.index(atual) + 1) % len(raios)] if atual in raios else raios[1]
        acao_raio.setText(f"   Minimapa: alcance {int(config['minimapa_raio'])} m (clique para trocar)")
        base.salvar_config(config)
    acao_raio.triggered.connect(trocar_raio)
    menu.addAction(acao_raio)
    adicionar("Mostrar Auxiliar de sessao (grid, contagem e proxima sessao)", config["mostrar_auxiliar"], alternar_janela(janela_auxiliar), chave="mostrar_auxiliar")
    adicionar("   Auxiliar: tambem durante a sessao (tempo restante)", config["auxiliar_sempre"], ao_flag("auxiliar_sempre"), chave="auxiliar_sempre")
    adicionar("Mostrar Ultimo contato (so depois de tocar em um carro)", config["mostrar_contato"], alternar_janela(janela_contato), chave="mostrar_contato")
    adicionar("Mostrar Entrada do pit (distancia, freio e limite)", config["mostrar_pit"], alternar_janela(janela_pit), chave="mostrar_pit")
    adicionar("   Pit: mostrar sempre perto da entrada (nao so com parada pedida)", config["pit_sempre"], ao_flag("pit_sempre"), chave="pit_sempre")
    acao_zerar_curvas = QAction("   Curvas: reiniciar o aprendizado desta pista", menu)
    acao_zerar_curvas.triggered.connect(lambda: telemetria.v14_curvas.resetar())
    menu.addAction(acao_zerar_curvas)
    menu.addSeparator()
    adicionar("Visual moderno (desmarque para voltar ao visual classico)", config["tema_moderno"],
              guardar("tema_moderno", ao_tema))
    adicionar("   Estilo Glass Fume (vidro escuro translucido)", config["tema_vidro"], guardar("tema_vidro", ao_vidro), chave="tema_vidro")
    adicionar("   Estilo Sport (italico e detalhes vermelhos)", config["tema_sport"], guardar("tema_sport", ao_sport), chave="tema_sport")
    submenu_op = menu.addMenu("   Transparencia do fundo das janelas")
    grupo_op = QActionGroup(submenu_op)
    grupo_op.setExclusive(True)
    for valor in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4):
        a = QAction(f"Fundo {valor * 100:.0f}% opaco" + ("  (padrao)" if valor == 0.8 else ""), submenu_op)
        a.setCheckable(True)
        a.setChecked(abs(float(config.get("opacidade_fundo", 0.8)) - valor) < 1e-6)
        a.triggered.connect(lambda _m=False, v=valor: ao_opacidade(v))
        grupo_op.addAction(a)
        submenu_op.addAction(a)
        acoes.append(a)
    adicionar("Manter o overlay por cima do jogo (reforcar)", config["reforcar_topo"], guardar("reforcar_topo", ao_reforcar), chave="reforcar_topo")
    adicionar("Teclas de atalho para o Stream Deck (Ctrl+Shift+F13...F24 e Alt+Shift+F13...F24)", config.get("teclas_globais", True),
              lambda marcado: ao_teclas(marcado), chave="teclas_globais")
    acao_tamanhos = QAction("Restaurar o tamanho das janelas (100%)", menu)
    acao_tamanhos.triggered.connect(ao_restaurar_tamanhos)
    menu.addAction(acao_tamanhos)
    menu.addSeparator()
    acao_sair = QAction("Sair", menu)
    acao_sair.triggered.connect(app.quit)
    menu.addAction(acao_sair)

    # ---- teclas de atalho globais (Stream Deck): mapa proprio do LMU, em ov_atalhos_lmu.py ----
    # Cada atalho chama o MESMO item do menu da bandeja (liga/desliga) ou a mesma funcao (zerar G, restaurar, sair).
    acoes_chamar = {"zerar_pico_g": telemetria.zerar_pico_g, "restaurar_tamanhos": ao_restaurar_tamanhos, "sair": app.quit}

    def executar_atalho(tipo, alvo):
        if tipo == "alternar":
            acao_por_chave[alvo].toggle()           # liga/desliga e dispara o mesmo tratamento do clique no menu
        elif tipo == "chamar":
            acoes_chamar[alvo]()
        else:
            raise ValueError(f"tipo de atalho desconhecido: {tipo}")

    despachante = nucleo.DespachanteTeclas(
        executar_atalho, atalhos=atalhos_lmu.ATALHOS_LMU,
        ao_erro=lambda contexto, erro: base.registrar_aviso(f"{contexto} falhou: {erro!r}"),
        ao_evento=base.registrar_info)
    estado_teclas = {"escuta": None, "avisou": False}

    def iniciar_teclas():
        if estado_teclas["escuta"] is not None:
            return
        api = api_teclas if api_teclas is not None else criar_api_teclas()
        if api is None:
            return
        escuta = nucleo.EscutaTeclas(api, atalhos=atalhos_lmu.ATALHOS_LMU)
        try:
            n_ok, falhas = escuta.iniciar()
        except Exception:
            base.registrar_erro("atalhos globais (iniciar)")
            return
        estado_teclas["escuta"] = escuta
        base.registrar_info(f"atalhos globais: {n_ok} de {len(atalhos_lmu.ATALHOS_LMU)} registrados")
        if escuta.erro:
            base.registrar_aviso(f"atalhos globais: a escuta falhou ({escuta.erro})")
        if falhas:
            base.registrar_aviso("atalhos globais NAO registrados (outro programa usa a mesma combinacao?): "
                                 + ", ".join(f"{a.nome} [{a.rotulo}] - {erro}" for a, erro in falhas))
            if not estado_teclas["avisou"]:
                estado_teclas["avisou"] = True
                bandeja.showMessage("Overlay " + NOME_JOGO,
                                    f"{len(falhas)} atalho(s) para o Stream Deck nao puderam ser registrados "
                                    "(outro programa usa a mesma combinacao). Veja o overlay_log_lmu.txt.",
                                    QSystemTrayIcon.Warning, 8000)

    def parar_teclas():
        escuta = estado_teclas["escuta"]
        estado_teclas["escuta"] = None
        if escuta is not None:
            escuta.parar()
            base.registrar_info("atalhos globais desligados")

    def ao_teclas(marcado):
        config["teclas_globais"] = bool(marcado)
        base.salvar_config(config)
        (iniciar_teclas if marcado else parar_teclas)()

    def ciclo_teclas():
        escuta = estado_teclas["escuta"]
        if escuta is None:
            return
        try:
            for codigo in escuta.retirar():
                despachante.tratar(codigo)
        except Exception:
            base.registrar_erro("atalhos globais (ciclo)")

    timer_teclas = QTimer()
    timer_teclas.timeout.connect(ciclo_teclas)
    timer_teclas.start(40)
    app.aboutToQuit.connect(parar_teclas)

    bandeja.setContextMenu(menu)
    central = base.montar_central(app, bandeja, menu, janelas, acao_por_chave, config, acao_sair, NOME_JOGO,
                                  lambda: TelemetriaLMU(demo=True), {
                                      "opacidade": ao_opacidade, "restaurar": ao_restaurar_tamanhos,
                                      "salvar": lambda: base.salvar_config(config), "alcance_minimapa": trocar_raio})
    bandeja.show()
    if config.get("teclas_globais", True):
        iniciar_teclas()
    if visib.automatico and config["travado"] and not visib.visivel:
        bandeja.showMessage("Overlay " + NOME_JOGO, "Ativo. As janelas aparecem sozinhas quando voce entrar no carro.",
                            QSystemTrayIcon.Information, 6000)

    def ciclo():
        try:
            dados = telemetria.ler()
            mostrar = visib.atualizar(dados, time.monotonic(), edicao=not config["travado"])
            for j in janelas:
                j.definir_auto_visivel(mostrar)
                j.atualizar(dados)
        except Exception:
            base.registrar_erro("atualizacao")

    timer = QTimer()
    timer.timeout.connect(ciclo)
    timer.start(base.INTERVALO_MS)

    def ciclo_topo():
        if config.get("reforcar_topo", True):
            base.reforcar_sobreposicao(janelas)

    timer_topo = QTimer()
    timer_topo.timeout.connect(ciclo_topo)
    timer_topo.start(100)                        # o LMU tambem se coloca "no topo": reafirmamos 10 vezes por segundo
    ciclo_topo()
    gancho_topo = lmu.instalar_gancho_primeiro_plano(ciclo_topo)     # e na hora em que o foco muda (clique no jogo)

    estado_janela = {"ultimo": None, "hwnd": None}
    amostras = {"n": 0, "jogo_acima": 0, "ocultas": 0, "inicio": time.monotonic()}

    def amostrar_sobreposicao():
        """Mede com que frequencia o jogo fica ACIMA do overlay (briga por 'sempre no topo') e se o DWM esconde as janelas.
        Registrado a cada 60 s: prova ou descarta a hipotese de 'o jogo cobre o overlay' no modo Borderless."""
        if DEMO or telemetria.ultimo_estado != lmu.OK or not estado_janela["hwnd"]:
            return
        try:
            r = lmu.jogo_acima_do_overlay(estado_janela["hwnd"], [int(w.winId()) for w in janelas if w.isVisible()])
            if r is None:
                return
            amostras["n"] += 1
            amostras["jogo_acima"] += 1 if r["acima"] else 0
            amostras["ocultas"] += 1 if r["ocultas"] else 0
            agora = time.monotonic()
            if agora - amostras["inicio"] >= 60.0 and amostras["n"]:
                base.registrar_info(f"sobreposicao LMU: {amostras['n']} amostras em {agora - amostras['inicio']:.0f} s | jogo ACIMA do overlay em "
                                    f"{100.0 * amostras['jogo_acima'] / amostras['n']:.0f}% | janelas escondidas pelo DWM (cloaked) em "
                                    f"{100.0 * amostras['ocultas'] / amostras['n']:.0f}%")
                amostras.update(n=0, jogo_acima=0, ocultas=0, inicio=agora)
        except Exception:
            base.registrar_erro("amostra de sobreposicao")

    timer_amostra = QTimer()
    timer_amostra.timeout.connect(amostrar_sobreposicao)
    timer_amostra.start(250)

    def ciclo_janela_jogo():
        """Log (so quando muda) de como o jogo esta na tela: ajuda a explicar overlay escondido (tela cheia exclusiva)."""
        if DEMO or telemetria.ultimo_estado != lmu.OK:
            return
        try:
            j = lmu.janela_do_jogo([int(w.winId()) for w in janelas if w.isVisible()])
            estado_janela["hwnd"] = None if j is None else j.get("hwnd")
            chave = None if j is None else (j["com_borda"], j["tela_cheia"], j["topmost"], j["z_overlay"] is None or
                                            j["z_overlay"] < j["z_jogo"], j["largura"], j["altura"])
            if chave != estado_janela["ultimo"]:
                estado_janela["ultimo"] = chave
                base.registrar_info("janela do jogo LMU: " + lmu.descrever_janela_jogo(j))
        except Exception:
            base.registrar_erro("janela do jogo")

    timer_janela = QTimer()
    timer_janela.timeout.connect(ciclo_janela_jogo)
    timer_janela.start(10000)

    def registrar_desempenho():
        try:
            taxas = {j.CHAVE: j.TAXA_HZ * base.JanelaBase.MULT_TAXA for j in janelas if j.isVisible()}
            est = base.DESEMPENHO.estatistica("ciclo") or {}
            base.registrar_calculo("desempenho", ciclo_ms_medio=est.get("media", 0.0), ciclo_ms_p95=est.get("p95", 0.0),
                                   ciclo_ms_max=est.get("max", 0.0), desenho_ms_por_segundo=base.DESEMPENHO.custo_por_segundo(taxas),
                                   janelas_visiveis=len(taxas), economia=bool(config.get("economia_cpu")))
        except Exception:
            base.registrar_erro("resumo de desempenho")

    timer_desempenho = QTimer()
    timer_desempenho.timeout.connect(registrar_desempenho)
    timer_desempenho.start(10 * 60 * 1000)
    app.aboutToQuit.connect(registrar_desempenho)
    app.aboutToQuit.connect(telemetria.encerrar)
    app.aboutToQuit.connect(trava.unlock)           # libera a trava de instancia unica ao sair
    app.aboutToQuit.connect(lambda: base.salvar_config(config))
    app._refs = (janelas, bandeja, menu, acoes, acao_sair, acao_tamanhos, acao_zerar_g, timer, timer_topo,
                 timer_desempenho, visib, trava, telemetria, timer_teclas, estado_teclas, acao_por_chave)
    if ao_iniciar:
        ao_iniciar(app, janelas, telemetria, config)
    return app.exec()


def principal_diagnostico():
    texto, _estado = gerar_diagnostico()
    try:
        ARQ_DIAGNOSTICO.write_text(texto + "\n", encoding="utf-8")
    except Exception:
        pass
    print(texto)
    print(f"\n(gravado em {ARQ_DIAGNOSTICO})")
    return 0


if __name__ == "__main__":
    redirecionar_arquivos()
    aplicar_textos_lmu()
    try:
        sys.exit(principal_diagnostico() if DIAGNOSTICO else principal())
    except Exception:
        ARQ_LOG_LMU.write_text(traceback.format_exc(), encoding="utf-8")
        raise
