# -*- coding: utf-8 -*-
"""
Overlay iRacing - Fase 20.2.2 (teclas de atalho globais para o Stream Deck; base: 20.2.1)
Doze janelas independentes (cada uma pode ser movida e ligada/desligada pelo icone da bandeja):
  1. Telemetria    : marcha, velocidade, RPM, pedais, volante + grafico de acelerador e freio
  2. Voltas        : delta, tempo de volta (atual / ultima / melhor) e combustivel
  3. Relativo      : carros a frente e atras de voce, com tipo de pneu e voltas do pneu + projecao de iRating e SR
  4. Classificacao : posicao, carro, piloto, pais, ultima e melhor volta, agrupados por classe
  5. Mapa          : tracado da pista (aprendido na sua primeira volta) com a posicao dos carros
  6. Radar         : carros ao redor de voce, visto de cima, para evitar contato
  7. Pneus         : vida util e temperatura de cada pneu (estimadas ao vivo; reais nos boxes)
  8. Setores       : tempo por setor, ultima/melhor/otima vs o seu recorde (carro + pista)
  9. Clima         : temperatura da pista e do ar, neblina, chuva e vento (bussola relativa ao carro)
 10. Danos         : reparo necessario, avisos do motor e impactos detectados (frente/tras/lados)
 11. Combustivel   : janela de pit, litros a colocar, autonomia e consumo das ultimas voltas
 12. Forca G       : circulo de G lateral e longitudinal com rastro, G atual e pico

Fase 20: confiabilidade (radar real x estimado, delta/setores validados, pneus com ultima leitura, iRating/SR
projetados x oficial), perfis Treino/Classificacao/Corrida, desempenho (repintura por taxa) e log completo.
Fase 20.1: radar separa ocupacao lateral (SDK) de identidade (inferida) e nao projeta colisao so pela
aproximacao longitudinal; projecao x oficial so compara com a corrida/categoria/usuario certos; paradas de
combustivel respeitam a margem a cada parada; mapa fecha a volta com amostragem lenta; real x estimado dos
pneus numa regra unica testada.
Fase 20.2: comparacao de iRating/SR marcada PROVISORIA (so "confirmada" com o resultado oficial da mesma corrida)
e litros da 1a parada de combustivel = capacidade disponivel na chegada aos boxes (nao mais divisao igual).
Fase 20.2.2: teclas de atalho GLOBAIS (Ctrl+Alt+F13..F24 e Ctrl+Alt+Shift+F13..F24) para o Stream Deck trocarem o
perfil e ligarem/desligarem as janelas; cada atalho chama o mesmo item do menu da bandeja (ver ATALHOS_STREAM_DECK.txt).
Arquivos: overlay_iracing.py (leitura do SDK + janelas) e ov_nucleo.py (regras novas, sem Qt e sem SDK).

Uso:
  iniciar_overlay.bat   -> modo normal (le os dados do iRacing)
  testar_demo.bat       -> modo demonstracao (dados simulados, sem o iRacing)
  ativar_inicio_automatico.bat -> abre o overlay junto com o Windows; as janelas aparecem sozinhas
                                  quando voce entra no carro (modo automatico, ver LEIA-ME)
"""
import bisect
import json
import math
import os
import re
import sys
import time
import traceback
import unicodedata
from collections import deque
from pathlib import Path

try:
    import ov_nucleo as nucleo            # regras novas e testaveis (sem Qt e sem SDK): precisa estar na mesma pasta
except ImportError:                       # pacote incompleto: avisa em vez de falhar em silencio
    _msg = ("Falta o arquivo 'ov_nucleo.py' na pasta do overlay.\n"
            "Copie TODOS os arquivos do pacote (overlay_iracing.py e ov_nucleo.py) para a mesma pasta.")
    try:
        with (Path(__file__).resolve().parent / "overlay_log.txt").open("a", encoding="utf-8") as _arq:
            _arq.write(_msg + "\n")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, _msg, "Overlay iRacing", 0x10)
    except Exception:
        print(_msg)
    sys.exit(1)

try:
    import ov_v12 as v12                  # v1.2.0: logica dos novos overlays (sem Qt e sem SDK)
except ImportError:
    _msg12 = "Falta o arquivo 'ov_v12.py' na pasta do overlay. Copie TODOS os arquivos do pacote para a mesma pasta."
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, _msg12, "Overlay iRacing", 0x10)
    except Exception:
        print(_msg12)
    sys.exit(1)

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QFontMetrics, QIcon, QLinearGradient,
                           QActionGroup, QImage, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon, QWidget

PASTA = Path(__file__).resolve().parent
ARQ_CONFIG = PASTA / "config.json"
ARQ_LOG = PASTA / "overlay_log.txt"
ARQ_MAPAS = PASTA / "mapas_pistas.json"
PASTA_BANDEIRAS = PASTA / "bandeiras"        # bandeiras dos paises (incluidas no pacote)
PASTA_EMBLEMAS = PASTA / "emblemas"          # emblemas das marcas (imagens que VOCE coloca aqui)
ARQ_EMBLEMAS_FALTANDO = PASTA / "emblemas_faltando.txt"
ARQ_HISTORICO = PASTA / "historico_projecoes.csv"   # projecao x resultado de cada corrida (calibracao)
ARQ_PNEUS = PASTA / "calibracao_pneus.json"          # calibracao do desgaste por carro
ARQ_RECORDES = PASTA / "recordes_pessoais.json"     # melhor volta e setores por pista + carro
ARQ_PENDENTE = PASTA / "projecao_pendente.json"      # projecoes de corrida e seu ciclo de vida (pendente/provisoria/confirmada/expirada)
ARQ_COMPARACAO = PASTA / "comparacao_oficial.csv"    # projecao x resultado oficial (calibracao)
DEMO ="--demo" in sys.argv
INTERVALO_MS = 33  # ~30 atualizacoes por segundo

# Janela de telemetria (parte de cima: marcha, velocidade, RPM, pedais, volante)
LARGURA, ALTURA = 560, 132
# Grafico de pedais (parte de baixo da janela de telemetria)
ALTURA_GRAFICO = 104
AMOSTRAS_GRAFICO = 300  # ~10 s a 30 Hz
# Janela de delta / voltas / combustivel
LARGURA_VOLTAS, ALTURA_VOLTAS = 460, 104
ALTURA_CALC_COMBUSTIVEL = 62   # faixa do calculo de combustivel (parte de baixo da janela Voltas)

# Mapa da pista e radar
LARGURA_MAPA, ALTURA_MAPA = 340, 250
LARGURA_RADAR, ALTURA_RADAR = 200, 304   # 14 px a mais: linha de legenda (SDK x estimado)
LARGURA_PNEUS, ALTURA_PNEUS = 378, 282
LARGURA_CLIMA, ALTURA_CLIMA = 220, 526
LARGURA_COMB, ALTURA_COMB = 710, 318   # painel de combustivel e pit
LARGURA_G, ALTURA_G = 250, 306         # forca G (circulo + etiqueta da pista)
LARGURA_DANOS, ALTURA_DANOS = 260, 426   # danos do carro   # clima: pista, ar, neblina, vento e velocidade do carro
CANTOS_PNEUS = ("LF", "RF", "LR", "RR")
ALCANCE_RADAR = 20.0       # metros mostrados a frente e atras de voce
ZONA_LATERAL = 8.0         # metros: carro "ao lado" quando o iRacing acusa carro esquerda/direita
COMPR_CARRO = 4.6          # metros: comprimento medio de um carro (para a distancia para-choque a para-choque)
TEMPO_MEMORIA_LADO = 3.0   # s: por quanto tempo lembrar de que lado um carro estava depois de passar
FAIXA_LATERAL = 3.2        # metros de afastamento lateral usado para desenhar um carro ao lado
N_PONTOS_MAPA = 360        # resolucao do tracado

# Redimensionamento das janelas (arrastando bordas/cantos ou Ctrl + roda do mouse)
MARGEM_REDIM = 10          # pixels da borda que "pegam" o redimensionamento
ESCALA_MIN, ESCALA_MAX = 0.5, 3.0
_BORDA_ESQ, _BORDA_DIR, _BORDA_TOPO, _BORDA_BASE = 1, 2, 4, 8

# Janela do relativo
LARGURA_REL = 460
SLOTS_FRENTE, SLOTS_TRAS = 3, 3
ALTURA_CAB, ALTURA_LINHA, ALTURA_RODAPE = 28, 26, 26
ALTURA_REL = ALTURA_CAB + ALTURA_LINHA * (SLOTS_FRENTE + 1 + SLOTS_TRAS) + ALTURA_RODAPE
ALTURA_PROJECAO = 40            # faixa de projecao de iRating / SR (entre as linhas e o rodape)

# Janela de setores (vs melhor volta)
LARGURA_SETORES = 300
ALTURA_LINHA_SETOR = 25
ALTURA_TOPO_SETORES = 54

# Janela da classificacao
LARGURA_CLASS = 530
ALTURA_LINHA_CLASS = 24
MAX_LINHAS_MINHA_CLASSE = 8     # carros mostrados na sua classe (topo + vizinhanca)
MAX_LINHAS_OUTRAS_CLASSES = 3   # carros mostrados nas demais classes


# --------------------------------------------------------------------------
# Configuracao (posicoes, travamento e janelas ligadas)
# --------------------------------------------------------------------------
_PERFIS = nucleo.GerenciadorPerfis()           # perfis Treino / Classificacao / Corrida (layout por perfil)


def carregar_config():
    padrao = {
        "perfis": {}, "perfil_modo": "auto", "perfil_ativo": "Corrida",   # Fase 20: layout por perfil
        "economia_cpu": False, "prioridade_baixa": True,                   # Fase 20: desempenho
        "teclas_globais": True,                                            # Fase 20.2.2: atalhos para o Stream Deck

        "x": 60, "y": 60, "travado": False, "mostrar_telemetria": True,
        "mostrar_grafico": True,
        "x_voltas": 60, "y_voltas": 306, "mostrar_voltas": True,
        "x_relativo": 640, "y_relativo": 60, "mostrar_relativo": True,
        "x_classificacao": 1060, "y_classificacao": 60, "mostrar_classificacao": True,
        "classificacao_todas": True,
        "x_mapa": 270, "y_mapa": 420, "mostrar_mapa": True,
        "x_radar": 60, "y_radar": 420, "mostrar_radar": True,
        "escala": 1.0, "escala_voltas": 1.0, "escala_relativo": 1.0, "escala_classificacao": 1.0,
        "escala_mapa": 1.0, "escala_radar": 1.0,
        "reforcar_topo": True,
        "mostrar_calc_combustivel": True, "margem_combustivel": 1.0,
        "x_pneus": 660, "y_pneus": 420, "mostrar_pneus": True, "escala_pneus": 1.0,
        "pneu_temp_min": 80.0, "pneu_temp_max": 105.0,
        "auto_modo": True,
        "pneu_desgaste_volta": 0.7, "pneu_vida_minima": 30, "pneu_lado_invertido": False,
        "mostrar_projecao": True,
        "x_setores": 1060, "y_setores": 440, "mostrar_setores": True, "escala_setores": 1.0,
        "x_clima": 1330, "y_clima": 60, "mostrar_clima": True, "escala_clima": 1.0,
        "vento_invertido": False,
        "x_forca_g": 1580, "y_forca_g": 60, "mostrar_forca_g": True, "escala_forca_g": 1.0, "g_max": 4.0,
        "tema_moderno": True, "tema_sport": False, "tema_vidro": True, "opacidade_fundo": 0.80,
        "x_combustivel": 60, "y_combustivel": 560, "mostrar_combustivel": True, "escala_combustivel": 1.0,
        "x_danos": 1330, "y_danos": 600, "mostrar_danos": True, "escala_danos": 1.0,
        # ---- v1.2.0 ----
        "inputs_segundos": 12, "inputs_marchas_fundo": True, "inputs_marca_abs": True, "inputs_marca_tc": False,
        "inputs_origem": "carro",
        "x_luz_abs": 800, "y_luz_abs": 900, "mostrar_luz_abs": True, "escala_luz_abs": 1.0,
        "luz_abs_cor": "dourado", "luz_abs_modo": "ritmo", "luz_abs_apagada": False,
        "x_luz_tc": 910, "y_luz_tc": 900, "mostrar_luz_tc": True, "escala_luz_tc": 1.0,
        "luz_tc_cor": "azul", "luz_tc_modo": "ritmo", "luz_tc_apagada": False, "luz_tc_sens": "normal",
        "luz_opacidade": 1.0,
        "x_retorno": 800, "y_retorno": 760, "mostrar_retorno": True, "escala_retorno": 1.0,
        "retorno_pare": 1.5, "retorno_ceda": 3.5, "retorno_sempre": False, "retorno_opacidade": 0.95,
        "x_estrategia": 1060, "y_estrategia": 700, "mostrar_estrategia": True, "escala_estrategia": 1.0,
        "estrategia_vantagem": True, "estrategia_rivais": True, "estrategia_pulsar": True,
    }
    # escala por eixo (largura / altura) de cada janela; None = acompanha a escala unica
    for sufixo in ("", "_voltas", "_relativo", "_classificacao", "_mapa", "_radar", "_pneus", "_setores", "_clima", "_danos", "_combustivel", "_forca_g",
                   "_luz_abs", "_luz_tc", "_retorno", "_estrategia"):
        padrao["escala_x" + sufixo] = None
        padrao["escala_y" + sufixo] = None
    try:
        dados = json.loads(ARQ_CONFIG.read_text(encoding="utf-8"))
        padrao.update({k: dados[k] for k in padrao if k in dados})
        # Migracao de versoes anteriores: o painel extra virou a janela "Voltas"
        if "mostrar_voltas" not in dados and "painel_extra" in dados:
            padrao["mostrar_voltas"] = bool(dados["painel_extra"])
        if "x_voltas" not in dados or "y_voltas" not in dados:
            grafico = ALTURA_GRAFICO if padrao["mostrar_grafico"] else 0
            padrao["x_voltas"] = int(padrao["x"])
            padrao["y_voltas"] = int(padrao["y"]) + ALTURA + grafico + 10
    except Exception:
        pass
    try:
        _PERFIS.inicializar(padrao)     # 1a vez: os 3 perfis copiam o layout atual (nada muda de lugar)
    except Exception:
        registrar_erro("perfis")
    return padrao


def salvar_config(cfg):
    try:
        _PERFIS.capturar(cfg)           # o layout em uso vai para o perfil ativo
        ARQ_CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass


_REGISTRO = nucleo.Registro(lambda: ARQ_LOG)      # o caminho e lido a cada escrita (ARQ_LOG pode ser trocado)
_erros_registrados = _REGISTRO._vistos            # mantido por compatibilidade com os testes antigos
DESEMPENHO = nucleo.Desempenho()


def registrar_erro(contexto):
    """Grava o erro atual em overlay_log.txt (uma vez por tipo) sem derrubar o overlay."""
    _REGISTRO.erro(contexto, traceback.format_exc())


def registrar_aviso(texto):
    """Grava um aviso em overlay_log.txt (uma vez por texto)."""
    _REGISTRO.aviso(texto)


def registrar_info(texto):
    """Evento informativo (troca de perfil, sessao, referencia aceita...)."""
    _REGISTRO.info(texto)


def registrar_calculo(nome, intervalo=0.0, /, **valores):
    """Resultado de um calculo no log; `intervalo` = no maximo uma linha por `nome` nesse tempo (s)."""
    _REGISTRO.calculo(nome, intervalo, **valores)


# --------------------------------------------------------------------------
# Formatacao e utilitarios
# --------------------------------------------------------------------------
def fmt_tempo(seg):
    """83.456 -> '1:23.456'. Sem valor -> '--:--.---'."""
    if seg is None or seg <= 0:
        return "--:--.---"
    minutos = int(seg // 60)
    resto = seg - minutos * 60
    return f"{minutos}:{resto:06.3f}"


def fmt_relogio(seg):
    """939 -> '15:39'; 4000 -> '1:06:40'."""
    seg = int(max(0, seg))
    horas, resto = divmod(seg, 3600)
    minutos, segundos = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02d}:{segundos:02d}"
    return f"{minutos:02d}:{segundos:02d}"


def fmt_irating(valor):
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        return "--"
    if valor <= 0:
        return "--"
    return f"{valor / 1000:.1f}k" if valor >= 1000 else str(valor)


def cor_de_int(valor, padrao=(150, 150, 160)):
    """Cor do iRacing (inteiro 0xRRGGBB) -> (r, g, b)."""
    try:
        v = int(valor, 0) if isinstance(valor, str) else int(valor)  # aceita 0xRRGGBB como texto
    except (TypeError, ValueError):
        return padrao
    if v <= 0:
        return padrao
    return ((v >> 16) & 255, (v >> 8) & 255, v & 255)


def nome_curto(nome):
    """'Joao da Silva' -> 'J. da Silva'."""
    partes = str(nome or "").split()
    if len(partes) >= 2:
        return f"{partes[0][0]}. {' '.join(partes[1:])}"
    return partes[0] if partes else "?"


def lic_curta(lic):
    """'A 3.50' -> 'A3.5'."""
    try:
        letra, numero = str(lic).split()
        return f"{letra}{float(numero):.1f}"
    except Exception:
        return str(lic or "")


def licenca_sr(d):
    """(SR, letra da licenca) de um item de DriverInfo.Drivers. 'A 3.47' -> (3.47, 'A')."""
    sr, letra = None, ""
    partes = str(d.get("LicString") or "").split()
    if len(partes) == 2:
        letra = partes[0][:1].upper()
        try:
            sr = float(partes[1])
        except ValueError:
            sr = None
    if sr is None:
        try:
            sub = float(d.get("LicSubLevel"))
            sr = sub / 100.0 if sub > 0 else None
        except (TypeError, ValueError):
            sr = None
    return sr, letra


def calcular_sof(ratings):
    """Strength of Field no mesmo formato usado pelo iRacing."""
    r = [x for x in ratings if x and x > 0]
    if not r:
        return None
    soma = sum(math.exp(-x * math.log(2) / 1600.0) for x in r)
    return (1600.0 / math.log(2)) * math.log(len(r) / soma)


def tempo_valido(valor):
    """Tempo de volta em segundos; ausente, zero ou negativo (-1) viram None."""
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return None
    return valor if valor > 0 else None


_PAISES = {
    "brazil": "BRA", "brasil": "BRA", "united states": "USA", "united states of america": "USA",
    "usa": "USA", "us": "USA", "united kingdom": "GBR", "great britain": "GBR", "uk": "GBR",
    "uk & i": "GBR", "uk and i": "GBR", "uk & ireland": "GBR", "uk and ireland": "GBR",
    "england": "GBR", "scotland": "GBR", "wales": "GBR", "northern ireland": "GBR",
    "ireland": "IRL", "germany": "DEU", "france": "FRA", "italy": "ITA", "spain": "ESP",
    "portugal": "PRT", "netherlands": "NLD", "the netherlands": "NLD", "belgium": "BEL",
    "luxembourg": "LUX", "switzerland": "CHE", "austria": "AUT", "sweden": "SWE", "norway": "NOR",
    "denmark": "DNK", "finland": "FIN", "iceland": "ISL", "poland": "POL", "czech republic": "CZE",
    "czechia": "CZE", "slovakia": "SVK", "hungary": "HUN", "romania": "ROU", "bulgaria": "BGR",
    "greece": "GRC", "turkey": "TUR", "turkiye": "TUR", "russia": "RUS", "ukraine": "UKR",
    "croatia": "HRV", "serbia": "SRB", "slovenia": "SVN", "estonia": "EST", "latvia": "LVA",
    "lithuania": "LTU", "belarus": "BLR", "cyprus": "CYP", "malta": "MLT", "monaco": "MCO",
    "andorra": "AND", "canada": "CAN", "mexico": "MEX", "argentina": "ARG", "chile": "CHL",
    "colombia": "COL", "peru": "PER", "uruguay": "URY", "venezuela": "VEN", "ecuador": "ECU",
    "bolivia": "BOL", "paraguay": "PRY", "costa rica": "CRI", "panama": "PAN", "guatemala": "GTM",
    "dominican republic": "DOM", "puerto rico": "PRI", "australia": "AUS", "new zealand": "NZL",
    "japan": "JPN", "china": "CHN", "hong kong": "HKG", "taiwan": "TWN", "south korea": "KOR",
    "korea": "KOR", "singapore": "SGP", "malaysia": "MYS", "indonesia": "IDN", "thailand": "THA",
    "philippines": "PHL", "vietnam": "VNM", "india": "IND", "united arab emirates": "ARE",
    "saudi arabia": "SAU", "qatar": "QAT", "bahrain": "BHR", "kuwait": "KWT", "israel": "ISR",
    "south africa": "ZAF", "egypt": "EGY", "morocco": "MAR", "kazakhstan": "KAZ",
    "georgia": "GEO", "armenia": "ARM", "azerbaijan": "AZE",
    "honduras": "HND", "el salvador": "SLV", "nicaragua": "NIC", "jamaica": "JAM",
    "trinidad and tobago": "TTO", "cuba": "CUB", "lebanon": "LBN", "jordan": "JOR", "oman": "OMN",
    "pakistan": "PAK", "sri lanka": "LKA", "bangladesh": "BGD", "nigeria": "NGA", "kenya": "KEN",
    "tunisia": "TUN", "algeria": "DZA", "albania": "ALB", "north macedonia": "MKD",
    "bosnia and herzegovina": "BIH", "montenegro": "MNE", "moldova": "MDA", "liechtenstein": "LIE",
    "san marino": "SMR",
}

# Codigo de 3 letras -> codigo de 2 letras (nome do arquivo da bandeira em "bandeiras/")
_ISO2 = {
    "BRA": "br", "USA": "us", "GBR": "gb", "IRL": "ie", "DEU": "de", "FRA": "fr", "ITA": "it",
    "ESP": "es", "PRT": "pt", "NLD": "nl", "BEL": "be", "LUX": "lu", "CHE": "ch", "AUT": "at",
    "SWE": "se", "NOR": "no", "DNK": "dk", "FIN": "fi", "ISL": "is", "POL": "pl", "CZE": "cz",
    "SVK": "sk", "HUN": "hu", "ROU": "ro", "BGR": "bg", "GRC": "gr", "TUR": "tr", "RUS": "ru",
    "UKR": "ua", "HRV": "hr", "SRB": "rs", "SVN": "si", "EST": "ee", "LVA": "lv", "LTU": "lt",
    "BLR": "by", "CYP": "cy", "MLT": "mt", "MCO": "mc", "AND": "ad", "CAN": "ca", "MEX": "mx",
    "ARG": "ar", "CHL": "cl", "COL": "co", "PER": "pe", "URY": "uy", "VEN": "ve", "ECU": "ec",
    "BOL": "bo", "PRY": "py", "CRI": "cr", "PAN": "pa", "GTM": "gt", "DOM": "do", "PRI": "pr",
    "AUS": "au", "NZL": "nz", "JPN": "jp", "CHN": "cn", "HKG": "hk", "TWN": "tw", "KOR": "kr",
    "SGP": "sg", "MYS": "my", "IDN": "id", "THA": "th", "PHL": "ph", "VNM": "vn", "IND": "in",
    "ARE": "ae", "SAU": "sa", "QAT": "qa", "BHR": "bh", "KWT": "kw", "ISR": "il", "ZAF": "za",
    "EGY": "eg", "MAR": "ma", "KAZ": "kz", "GEO": "ge", "ARM": "am", "AZE": "az",
    "HND": "hn", "SLV": "sv", "NIC": "ni", "JAM": "jm", "TTO": "tt", "CUB": "cu", "LBN": "lb",
    "JOR": "jo", "OMN": "om", "PAK": "pk", "LKA": "lk", "BGD": "bd", "NGA": "ng", "KEN": "ke",
    "TUN": "tn", "DZA": "dz", "ALB": "al", "MKD": "mk", "BIH": "ba", "MNE": "me", "MDA": "md",
    "LIE": "li", "SMR": "sm",
}


def codigo_pais(nome):
    """'Brazil' -> 'BRA'. Nome desconhecido -> '---' (e fica registrado no overlay_log.txt)."""
    texto = str(nome or "").strip()
    if not texto:
        return "---"
    codigo = _PAISES.get(texto.lower())
    if codigo:
        return codigo
    if len(texto) <= 3 and texto.isalpha():
        return texto.upper()
    registrar_aviso(f"nacionalidade nao mapeada: {texto}")
    return "---"


_MARCAS = [
    "Aston Martin", "Alfa Romeo", "Mercedes-AMG", "Mercedes-Benz", "Mercedes", "Porsche", "BMW",
    "Audi", "Ferrari", "Lamborghini", "McLaren", "Ford", "Chevrolet", "Cadillac", "Acura", "Toyota",
    "Mazda", "Honda", "Hyundai", "Nissan", "Dallara", "Ligier", "Oreca", "Radical", "Lotus",
    "Subaru", "Volkswagen", "Renault", "Dodge", "Pontiac", "Buick", "Lexus", "Kia", "Genesis",
    "Peugeot", "Skip Barber", "Super Formula", "Williams", "Ray",
]


def marca_do_carro(*nomes):
    """'Porsche 911 GT3 R (992)' -> 'Porsche'. Se nenhuma marca conhecida aparecer, usa a primeira palavra."""
    for texto in nomes:
        texto = str(texto or "").strip()
        if not texto:
            continue
        melhor = None
        for marca in _MARCAS:
            achado = re.search(r"(?<![A-Za-z])" + re.escape(marca) + r"(?![A-Za-z])", texto, re.I)
            if achado:
                chave = (achado.start(), -len(marca))  # a que aparece primeiro; empate: a mais longa
                if melhor is None or chave < melhor[0]:
                    melhor = (chave, marca)
        return melhor[1] if melhor else texto.split()[0]
    return "--"


_EXTENSOES_IMAGEM = (".png", ".jpg", ".jpeg", ".webp", ".svg")
_cache_pixmaps = {}      # caminho -> QPixmap original (ou None se nao carregou)
_cache_ajustados = {}    # (caminho, largura_px, altura_px) -> QPixmap redimensionado
_cache_emblemas = {}     # marca -> (caminho ou None, instante da busca)
_emblemas_faltando = {}  # marca -> nome de arquivo esperado


def slug_marca(marca):
    """'Aston Martin' -> 'aston-martin'; 'Mercedes-AMG' -> 'mercedes-amg'."""
    texto = unicodedata.normalize("NFKD", str(marca or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")


def abreviacao_marca(marca):
    """Iniciais usadas enquanto nao ha emblema: 'Aston Martin' -> 'AM'; 'Porsche' -> 'POR'."""
    palavras = [w for w in re.split(r"[\s\-]+", str(marca or "")) if w]
    if not palavras:
        return "--"
    if len(palavras) > 1:
        return "".join(w[0] for w in palavras[:3]).upper()
    return palavras[0][:3].upper()


def _carregar_pixmap(caminho):
    chave = str(caminho)
    if chave not in _cache_pixmaps:
        try:
            pm = QPixmap(chave)
            _cache_pixmaps[chave] = None if pm.isNull() else pm
        except Exception:
            _cache_pixmaps[chave] = None
    return _cache_pixmaps[chave]


def _pixmap_ajustado(caminho, largura_px, altura_px):
    """Imagem reduzida (mantendo a proporcao) para caber em largura x altura pixels; com cache."""
    pm = _carregar_pixmap(caminho)
    if pm is None:
        return None
    chave = (str(caminho), int(largura_px), int(altura_px))
    if chave not in _cache_ajustados:
        if len(_cache_ajustados) > 600:
            _cache_ajustados.clear()
        _cache_ajustados[chave] = pm.scaled(max(1, int(largura_px)), max(1, int(altura_px)),
                                            Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return _cache_ajustados[chave]


def achar_emblema(marca):
    """Arquivo de emblema da marca na pasta 'emblemas' (ou None). Procura de novo a cada 5 s se faltar."""
    agora = time.time()
    achado = _cache_emblemas.get(marca)
    if achado is not None and (achado[0] is not None or agora - achado[1] < 5.0):
        return achado[0]
    caminho = None
    slug = slug_marca(marca)
    nomes = []
    for nome in (slug, slug.replace("-", ""), slug.replace("-", "_"), slug.split("-")[0] if slug else ""):
        if nome and nome not in nomes:
            nomes.append(nome)
    for nome in nomes:
        for ext in _EXTENSOES_IMAGEM:
            candidato = PASTA_EMBLEMAS / f"{nome}{ext}"
            if candidato.is_file() and _carregar_pixmap(candidato) is not None:
                caminho = candidato
                break
        if caminho:
            break
    _cache_emblemas[marca] = (caminho, agora)
    if caminho is None and slug and marca not in _emblemas_faltando:
        _emblemas_faltando[marca] = f"{slug}.png"
        try:
            linhas = ["Marcas que apareceram no jogo e ainda nao tem emblema.",
                      "Coloque na pasta 'emblemas' uma imagem com o nome indicado (PNG, fundo transparente):", ""]
            linhas += [f"{arq:28s} (marca: {nome})" for nome, arq in sorted(_emblemas_faltando.items())]
            ARQ_EMBLEMAS_FALTANDO.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        except Exception:
            pass
    return caminho



_SESSOES = {
    "race": "CORRIDA", "practice": "TREINO", "offline testing": "TESTE",
    "open qualify": "QUALIFICACAO", "lone qualify": "QUALIFICACAO", "qualify": "QUALIFICACAO",
    "warmup": "AQUECIMENTO",
}


def traduzir_sessao(tipo):
    texto = str(tipo or "").strip()
    if not texto:
        return None
    return _SESSOES.get(texto.lower(), texto.upper())


def ordem_da_classe(d):
    """Chave de ordenacao das classes: a mais rapida primeiro."""
    try:
        rel = d.get("CarClassRelSpeed")
        if rel not in (None, ""):
            return -float(rel)
    except (TypeError, ValueError):
        pass
    return tempo_valido(d.get("CarClassEstLapTime")) or 0.0


def selecionar_linhas(n, i_eu, limite):
    """Indices visiveis de uma lista com n carros.

    Mostra o topo da classificacao e, se voce estiver mais abaixo, a sua vizinhanca.
    """
    if n <= limite:
        return list(range(n))
    if i_eu is None or i_eu < limite:
        return list(range(limite))
    topo = max(1, limite // 3)
    restante = limite - topo
    inicio = max(topo, i_eu - restante // 2)
    fim = min(n, inicio + restante)
    inicio = max(topo, fim - restante)
    return list(range(topo)) + list(range(inicio, fim))


# --------------------------------------------------------------------------
# Consumo de combustivel por volta
# --------------------------------------------------------------------------
class ConsumoCombustivel:
    """Estima o consumo medio por volta usando as ultimas 5 voltas 'limpas'.

    Nao entram na conta: a primeira volta (parcial), voltas com passagem
    pelos boxes, voltas com reabastecimento e voltas puladas.
    """

    def __init__(self):
        self.historico = deque(maxlen=5)
        self.registros = deque(maxlen=12)   # (volta, litros) das ultimas voltas limpas
        self.resetar()

    def resetar(self):
        self.volta = None
        self.nivel_inicio = None
        self.nivel_anterior = None
        self.contaminada = True
        self.historico.clear()
        self.registros.clear()

    def atualizar(self, volta_completa, nivel, na_box):
        if volta_completa < 0:
            return
        # Primeira leitura ou nova sessao (contador de voltas voltou)
        if self.volta is None or volta_completa < self.volta:
            self.resetar()
            self.volta = volta_completa
            self.nivel_inicio = nivel
            self.nivel_anterior = nivel
            return
        if na_box:
            self.contaminada = True
        if self.nivel_anterior is not None and nivel > self.nivel_anterior + 0.05:
            self.contaminada = True  # reabastecimento
        self.nivel_anterior = nivel
        if volta_completa > self.volta:
            if volta_completa - self.volta > 1:
                self.contaminada = True
            uso = (self.nivel_inicio - nivel) if self.nivel_inicio is not None else 0.0
            if not self.contaminada and 0.01 < uso < 60.0:
                self.historico.append(uso)
                self.registros.append((volta_completa, uso))
            self.volta = volta_completa
            self.nivel_inicio = nivel
            self.contaminada = bool(na_box)

    @property
    def media(self):
        if not self.historico:
            return None
        return sum(self.historico) / len(self.historico)


# --------------------------------------------------------------------------
# Relativo: carros ao redor de voce
# --------------------------------------------------------------------------
def montar_relativo(pilotos, meu, pcts, voltas, est, superficie, box, posc, ref,
                    n_frente=SLOTS_FRENTE, n_tras=SLOTS_TRAS):
    """Monta as linhas do relativo a partir dos dados por carro (indexados por CarIdx).

    pilotos : {CarIdx: dados do piloto}      pcts : % da volta (0..1, -1 = fora da pista)
    voltas  : voltas completadas por carro   est  : tempo estimado ate o ponto atual (s)
    ref     : tempo de volta de referencia (s), usado para converter distancia em segundos.
    Retorna None se nao houver dados suficientes.
    """
    if not pilotos or meu not in pilotos or not pcts:
        return None
    if meu >= len(pcts) or pcts[meu] is None or pcts[meu] < 0:
        return None
    ref = ref if ref and ref > 5 else 90.0

    def item(lista, i, padrao=None):
        try:
            valor = lista[i]
        except (TypeError, IndexError, KeyError):
            return padrao
        return padrao if valor is None else valor

    pct_eu = pcts[meu]
    volta_eu = item(voltas, meu, 0)
    classe_eu = pilotos[meu].get("classe_id")

    candidatos = []  # (dpct, gap_s, idx, dif_voltas)
    for idx in pilotos:
        if idx == meu or idx >= len(pcts):
            continue
        pct = pcts[idx]
        if pct is None or pct < 0:
            continue
        if item(superficie, idx, 3) < 0:  # fora do mundo
            continue
        dpct = pct - pct_eu
        if dpct > 0.5:
            dpct -= 1.0
        elif dpct < -0.5:
            dpct += 1.0
        gap = dpct * ref
        e_outro, e_eu = item(est, idx, 0), item(est, meu, 0)
        if e_outro > 0 and e_eu > 0:
            g = e_outro - e_eu
            if g > ref / 2:
                g -= ref
            elif g < -ref / 2:
                g += ref
            if g * dpct > 0:  # mesmo sentido da distancia: confiavel
                gap = g
        dif = (item(voltas, idx, 0) + pct) - (volta_eu + pct_eu)
        candidatos.append((dpct, gap, idx, dif))

    frente = sorted([c for c in candidatos if c[0] > 0], key=lambda c: c[0])[:n_frente]
    atras = sorted([c for c in candidatos if c[0] <= 0], key=lambda c: -c[0])[:n_tras]

    def linha(idx, gap, dif, eu=False):
        p = pilotos[idx]
        if dif >= 1.0:
            volta_rel = 1    # carro uma volta (ou mais) a frente de voce
        elif dif <= -1.0:
            volta_rel = -1   # carro uma volta (ou mais) atras de voce
        else:
            volta_rel = 0
        return {
            "idx": idx,
            "pos_classe": int(item(posc, idx, 0) or 0) or None,
            "numero": p.get("numero", ""),
            "nome": p.get("nome", "?"),
            "lic": p.get("lic", ""),
            "lic_cor": p.get("lic_cor", (90, 90, 100)),
            "irating": p.get("irating", 0),
            "classe_cor": p.get("classe_cor", (150, 150, 160)),
            "gap": gap,
            "eu": eu,
            "na_box": bool(item(box, idx, False)),
            "volta_rel": volta_rel,
            "mesma_classe": p.get("classe_id") == classe_eu,
        }

    return {
        "frente": [linha(c[2], c[1], c[3]) for c in reversed(frente)],  # mais distante no topo
        "eu": linha(meu, 0.0, 0.0, eu=True),
        "atras": [linha(c[2], c[1], c[3]) for c in atras],
        "n_frente": n_frente,
        "n_tras": n_tras,
    }


def montar_classificacao(pilotos, meu, posc, ultimas, melhores, box):
    """Classificacao completa agrupada por classe (classe mais rapida primeiro).

    posc : posicao na classe por carro (0 = nao classificado)
    ultimas / melhores : ultima e melhor volta de cada carro (s)
    Retorna None se nao houver dados suficientes.
    """
    if not pilotos or meu not in pilotos or not posc:
        return None

    def item(lista, i, padrao=None):
        try:
            valor = lista[i]
        except (TypeError, IndexError, KeyError):
            return padrao
        return padrao if valor is None else valor

    grupos = {}
    for idx, p in pilotos.items():
        try:
            pos = int(item(posc, idx, 0))
        except (TypeError, ValueError):
            pos = 0
        if pos > 0:
            grupos.setdefault(p.get("classe_id"), []).append((pos, idx))
    if not grupos:
        return None

    classe_eu = pilotos[meu].get("classe_id")
    classes = []
    for classe_id, membros in grupos.items():
        membros.sort()
        ref = pilotos[membros[0][1]]
        validos = [t for t in (tempo_valido(item(melhores, i)) for _, i in membros) if t]
        melhor_classe = min(validos) if validos else None
        linhas = []
        for pos, idx in membros:
            p = pilotos[idx]
            ultima = tempo_valido(item(ultimas, idx))
            melhor = tempo_valido(item(melhores, idx))
            linhas.append({
                "pos": pos,
                "numero": p.get("numero", ""),
                "marca": p.get("marca", "--"),
                "nome": p.get("nome", "?"),
                "pais": p.get("pais", "---"),
                "ultima": ultima,
                "melhor": melhor,
                "eu": idx == meu,
                "na_box": bool(item(box, idx, False)),
                "melhor_da_classe": (melhor is not None and melhor_classe is not None
                                     and abs(melhor - melhor_classe) < 0.0005),
                "pb": (ultima is not None and melhor is not None and abs(ultima - melhor) < 0.0005),
            })
        ratings = [x.get("irating", 0) for x in pilotos.values() if x.get("classe_id") == classe_id]
        classes.append({
            "nome": ref.get("classe_nome", "Classe"),
            "cor": ref.get("classe_cor", (150, 150, 160)),
            "ordem": ref.get("classe_ordem", 0.0),
            "sof": calcular_sof(ratings),
            "n_carros": len(membros),
            "minha": classe_id == classe_eu,
            "linhas": linhas,
        })
    classes.sort(key=lambda c: (c["ordem"], c["nome"]))
    return {"classes": classes}


# Dados ficticios do modo demonstracao
_DEMO_CLASSE_A = (255, 201, 60)
_DEMO_CLASSE_B = (80, 200, 230)
_LIC = {"A": (1, 83, 219), "B": (0, 199, 2), "C": (254, 236, 4), "D": (252, 138, 39)}
_DEMO_LISTA = [
    # numero, nome, classe, irating, licenca
    ("7", "R. Almeida", "A", 4800, "A3.4"),     # voce
    ("21", "C. Mendes", "A", 5200, "A4.1"),
    ("77", "V. Lima", "A", 7200, "A4.9"),       # uma volta a frente
    ("3", "L. Fontes", "B", 3100, "B3.2"),
    ("88", "M. Duarte", "A", 4400, "A3.0"),
    ("9", "P. Nogueira", "A", 6100, "A4.8"),
    ("45", "D. Pires", "B", 1900, "D2.2"),      # uma volta atras
    ("52", "F. Barros", "B", 2700, "B2.1"),     # nos boxes
    ("12", "A. Cardoso", "A", 3500, "C3.9"),
    ("5", "S. Moura", "A", 4600, "A3.5"),
]
_DEMO_OFFSETS = [0.0, 0.0125, 1.0235, 0.0460, 0.0790, -0.0100, -1.0225, -0.0390, -0.0610, 0.3000]


def _pilotos_demo():
    pilotos = {}
    for i, (numero, nome, classe, ir, lic) in enumerate(_DEMO_LISTA):
        pilotos[i] = {
            "numero": numero, "nome": nome,
            "classe_id": 1 if classe == "A" else 2,
            "classe_cor": _DEMO_CLASSE_A if classe == "A" else _DEMO_CLASSE_B,
            "irating": ir, "lic": lic, "lic_cor": _LIC.get(lic[0], (90, 90, 100)),
            "lic_letra": lic[0], "sr": float(lic[1:]),
        }
    return pilotos


# Classificacao ficticia (3 classes) para o modo demonstracao
_DEMO_CLASSES_CLASSIF = {
    1: ("GTP", (255, 201, 60), -3.0),
    2: ("P217", (80, 200, 230), -2.0),
    3: ("GT3", (235, 80, 140), -1.0),
}
_DEMO_CARROS_CLASSIF = [
    # classe, numero, nome, marca, pais, melhor volta (s), iRating
    (1, "2", "A. Costa", "Cadillac", "BRA", 69.175, 6900),
    (1, "4", "L. Moreau", "Porsche", "FRA", 69.512, 6200),
    (1, "27", "D. Molina", "Acura", "ESP", 69.624, 4900),
    (1, "15", "R. Santos", "BMW", "BRA", 69.720, 5600),
    (1, "6", "E. Bernd", "Aston Martin", "DEU", 70.094, 5300),
    (2, "25", "N. Kalnis", "Dallara", "LVA", 73.297, 4100),
    (2, "26", "D. Weber", "Ligier", "USA", 73.332, 2700),
    (2, "23", "T. Reinhard", "Oreca", "DEU", 73.992, 3100),
    (2, "31", "K. Tanaka", "Dallara", "JPN", 74.410, 3600),
    (3, "24", "I. Cotelo", "Ferrari", "ARG", 83.958, 5900),
    (3, "5", "M. Benecke", "McLaren", "GBR", 84.122, 3400),
    (3, "3", "S. Haase", "Ferrari", "DEU", 84.178, 2500),
    (3, "11", "J. Ferreira", "Porsche", "PRT", 84.301, 4200),
    (3, "18", "P. Rossi", "Lamborghini", "ITA", 84.355, 3900),
    (3, "33", "G. Vermeer", "Mercedes-AMG", "NLD", 84.470, 3300),
    (3, "9", "T. Walker", "Audi", "AUS", 84.512, 2900),
    (3, "61", "H. Larsen", "BMW", "DNK", 84.690, 3700),
    (3, "44", "F. Aguirre", "Aston Martin", "MEX", 84.801, 2400),
    (3, "7", "R. Almeida", "Porsche", "BRA", 84.935, 4800),   # voce (10o da GT3)
    (3, "88", "B. Santana", "Ford", "BRA", 85.120, 2100),
    (3, "52", "C. Dupont", "Chevrolet", "FRA", 85.480, 1900),
]


def _base_classificacao_demo():
    pilotos, posc, meu = {}, [], 0
    contagem = {}
    for i, (classe, numero, nome, marca, pais, _melhor, ir) in enumerate(_DEMO_CARROS_CLASSIF):
        nome_classe, cor, ordem = _DEMO_CLASSES_CLASSIF[classe]
        pilotos[i] = {
            "numero": numero, "nome": nome, "marca": marca, "pais": pais, "irating": ir,
            "classe_id": classe, "classe_nome": nome_classe, "classe_cor": cor, "classe_ordem": ordem,
        }
        contagem[classe] = contagem.get(classe, 0) + 1
        posc.append(contagem[classe])
        if numero == "7":
            meu = i
    return pilotos, posc, meu



class DeltaProprio:
    """Delta calculado pelo proprio overlay (reserva para quando o iRacing nao informa o dele).

    Guarda, para a melhor volta limpa, o tempo decorrido em cada ponto da pista. Na volta atual,
    delta = tempo atual - tempo da melhor volta no mesmo ponto. A primeira volta limpa (sem boxes,
    comecando na linha de largada) vira a referencia; voltas mais rapidas a substituem.
    """

    def __init__(self):
        self.resetar()

    def resetar(self):
        self.ref_pcts = None
        self.ref_tempos = None
        self.ref_tempo = None
        self._voltas = None
        self._chave = None   # (sessao, pista, carro): a referencia so vale para a mesma combinacao
        self._zerar_volta()

    def _zerar_volta(self):
        self.perfil = []     # [(pct, tempo)] da volta em andamento
        self.sujo = False    # volta que nao serve de referencia (boxes, fora da pista, reboque, salto...)
        self.motivo_sujo = None

    def _marcar(self, motivo):
        if not self.sujo:
            self.sujo, self.motivo_sujo = True, motivo

    @property
    def pronto(self):
        return self.ref_pcts is not None

    def _interpolar(self, pct):
        pcts, tempos = self.ref_pcts, self.ref_tempos
        i = bisect.bisect_right(pcts, pct)
        if i <= 0:
            return tempos[0]
        if i >= len(pcts):
            return tempos[-1]
        a, b = pcts[i - 1], pcts[i]
        f = (pct - a) / (b - a) if b > a else 0.0
        return tempos[i - 1] + (tempos[i] - tempos[i - 1]) * f

    def _finalizar_volta(self, ultima_volta):
        perfil = self.perfil

        def rejeitar(motivo):
            registrar_calculo("delta: volta nao usada como referencia", motivo=motivo,
                              tempo=ultima_volta if ultima_volta else "--")

        if not ultima_volta or ultima_volta <= 0:
            return
        if self.sujo:
            return rejeitar(self.motivo_sujo or "volta suja")
        if len(perfil) < 20:
            return rejeitar("poucas amostras")
        if perfil[0][0] > 0.05 or perfil[-1][0] < 0.95:
            return rejeitar("nao cobre a volta inteira")  # ex.: entrou no meio da volta
        if max(b[0] - a[0] for a, b in zip(perfil, perfil[1:])) > 0.05:
            return rejeitar("buraco nos dados")
        if abs(perfil[-1][1] - ultima_volta) > max(1.0, ultima_volta * 0.02):
            return rejeitar("tempo medido nao bate com o oficial")
        if self.ref_tempo is not None and ultima_volta >= self.ref_tempo:
            return  # nao e mais rapida que a referencia atual (comportamento normal, nao registra)
        pcts = [0.0] + [q for q, _ in perfil] + [1.0]
        tempos = [0.0] + [t for _, t in perfil] + [float(ultima_volta)]
        self.ref_pcts, self.ref_tempos, self.ref_tempo = pcts, tempos, float(ultima_volta)
        registrar_calculo("delta: nova referencia (melhor volta limpa)", tempo=float(ultima_volta),
                          amostras=len(perfil))

    def atualizar(self, pct, tempo_volta, voltas_completas, na_box, ultima_volta, chave=None, motivo=None):
        """Retorna (delta em segundos, valido).

        `chave` = (sessao, pista, carro): ao mudar, a referencia e descartada (outro carro/pista/sessao nao
        serve de comparacao). `motivo` = texto de motivo_volta_suja (fora da pista, reboque...) ou None.
        """
        try:
            if chave is not None and chave != self._chave:
                if self.pronto or self._chave is not None:
                    registrar_calculo("delta: referencia descartada", motivo="troca de sessao, pista ou carro",
                                      de=self._chave, para=chave)
                self.resetar()
                self._chave = chave
            if voltas_completas is None:
                return 0.0, False
            if self._voltas is None:
                self._voltas = voltas_completas
            elif voltas_completas != self._voltas:
                if voltas_completas == self._voltas + 1:
                    self._finalizar_volta(ultima_volta)
                else:
                    self.resetar()          # sessao reiniciada / contador voltou
                self._voltas = voltas_completas
                self._zerar_volta()
            if na_box:
                self._marcar("boxes")
            if motivo:
                self._marcar(motivo)
            if pct is None or tempo_volta is None or tempo_volta < 0 or not (0.0 <= pct < 1.0):
                return 0.0, False
            if not self.perfil:
                if pct <= 0.2:
                    self.perfil.append((pct, tempo_volta))
            elif pct > self.perfil[-1][0]:
                if pct - self.perfil[-1][0] > 0.05:
                    self._marcar("salto na posicao (reset/teleporte)")
                self.perfil.append((pct, tempo_volta))
            if not self.pronto or not self.perfil:
                return 0.0, False
            return tempo_volta - self._interpolar(pct), True
        except Exception:
            registrar_erro("delta proprio")
            return 0.0, False



# --------------------------------------------------------------------------
# Setores x melhor volta (recorde pessoal por pista + carro)
# --------------------------------------------------------------------------
def fmt_setor(seg):
    """4.965 -> '4.965'; 83.2 -> '1:23.200'. Sem valor -> '--'."""
    if seg is None:
        return "--"
    return f"{seg:.3f}" if seg < 60 else fmt_tempo(seg)


class RecordesPessoais:
    """Melhor volta, setores da melhor volta e melhor tempo de cada setor, por pista + carro.

    Fica no arquivo recordes_pessoais.json (vale entre sessoes). Por "melhor" entenda: a melhor volta
    LIMPA (sem boxes, volta inteira) que o overlay viu; recordes de antes do overlay nao existem.
    """

    def __init__(self, arquivo):
        self.arquivo = Path(arquivo)
        self.dados = {}
        try:
            lido = json.loads(self.arquivo.read_text(encoding="utf-8"))
            if isinstance(lido, dict):
                self.dados = lido
        except Exception:
            pass

    def obter(self, chave):
        return self.dados.get(chave)

    def zerar(self, chave):
        if self.dados.pop(chave, None) is not None:
            self._salvar()

    def _salvar(self):
        try:
            tmp = self.arquivo.with_name(self.arquivo.name + ".tmp")
            tmp.write_text(json.dumps(self.dados, indent=1), encoding="utf-8")
            tmp.replace(self.arquivo)
        except Exception:
            registrar_erro("recordes pessoais")

    def registrar_volta(self, chave, tempo, setores):
        """Registra uma volta valida. Devolve a referencia ANTERIOR (para comparar) e os "roxos"
        (novos melhores setores / nova melhor volta)."""
        n = len(setores)
        antes = self.dados.get(chave)
        if antes and antes.get("n") != n:
            antes = None                      # a divisao em setores mudou: recomeca
        ref_antes = None
        melhores = [None] * n
        if antes:
            ref_antes = {"n": n, "melhor": antes["melhor"], "setores_melhor": list(antes["setores_melhor"]),
                         "melhores_setores": list(antes["melhores_setores"])}
            melhores = list(antes["melhores_setores"])
        roxos = [bool(antes) and m is not None and sv < m - 1e-9 for sv, m in zip(setores, melhores)]
        nova_melhor = antes is None or tempo < antes["melhor"] - 1e-9
        self.dados[chave] = {
            "n": n,
            "melhor": float(tempo) if nova_melhor else antes["melhor"],
            "setores_melhor": list(setores) if nova_melhor else list(antes["setores_melhor"]),
            "melhores_setores": [sv if m is None else min(sv, m) for sv, m in zip(setores, melhores)],
            "atualizado": time.strftime("%Y-%m-%d"),
        }
        self._salvar()
        return {"ref_antes": ref_antes, "roxos": roxos, "melhor_volta": bool(antes) and nova_melhor}


class AnaliseSetores:
    """Mede o tempo de cada setor da volta (com interpolacao no instante de cruzamento) e compara com
    o recorde pessoal guardado para a pista + carro."""

    def __init__(self):
        self.inicios = [0.0, 1.0 / 3.0, 2.0 / 3.0]
        self.estimado = True               # True = setores divididos igualmente (iRacing nao informou)
        self.resetar()

    @property
    def n(self):
        return len(self.inicios)

    def resetar(self):
        self._chave = None
        self._sessao = None
        self._voltas = None
        self.observadas = 0                # voltas completas vistas nesta sessao
        self.ultima = None
        self._zerar_volta()

    def _marcar(self, motivo):
        if not self.sujo:
            self.sujo, self.motivo_sujo = True, motivo

    def _zerar_volta(self):
        self.cruz = [None] * (len(self.inicios) - 1)   # cruz[j] = instante do fim do setor j
        self.sujo = False
        self.motivo_sujo = None
        self.anterior = None               # (pct, tempo) do ciclo anterior
        self.tempo_max = 0.0

    def definir_setores(self, inicios):
        """inicios: SectorStartPct de cada setor (como o iRacing informa para a pista)."""
        try:
            lista = sorted({round(float(x), 5) for x in inicios if 0.0 <= float(x) < 1.0})
        except (TypeError, ValueError):
            return
        if not lista or lista[0] > 0.001:
            lista.insert(0, 0.0)
        if len(lista) < 2:
            return
        if lista != self.inicios or self.estimado:
            self.inicios, self.estimado = lista, False
            self.ultima = None
            self._zerar_volta()

    def _finalizar_volta(self, ultima_volta, chave, recordes):
        n = self.n
        valida = (not self.sujo and self.observadas >= 1 and bool(ultima_volta) and ultima_volta > 0
                  and all(c is not None for c in self.cruz)
                  and abs(self.tempo_max - ultima_volta) <= max(1.0, ultima_volta * 0.02))
        setores = None
        if valida:
            pontos = [0.0] + list(self.cruz) + [float(ultima_volta)]
            setores = [pontos[k + 1] - pontos[k] for k in range(n)]
            if any(sv <= 0 for sv in setores):
                valida, setores = False, None
        if valida:
            r = recordes.registrar_volta(chave, float(ultima_volta), setores)
            self.ultima = {"tempo": float(ultima_volta), "setores": setores, "valida": True,
                           "ref_antes": r["ref_antes"], "roxos": r["roxos"], "melhor_volta": r["melhor_volta"]}
        elif ultima_volta and ultima_volta > 0:
            self.ultima = {"tempo": float(ultima_volta), "setores": None, "valida": False,
                           "ref_antes": None, "roxos": None, "melhor_volta": False}
            if self.observadas >= 1:
                registrar_calculo("setores: volta nao registrada como recorde",
                                  motivo=self.motivo_sujo or "setores incompletos ou tempo incoerente",
                                  tempo=float(ultima_volta))
        if valida:
            registrar_calculo("setores: volta valida", tempo=float(ultima_volta),
                              setores=" / ".join(f"{x:.3f}" for x in setores), estimado=self.estimado)
        self.observadas += 1

    def atualizar(self, pct, tempo_volta, voltas_completas, na_box, ultima_volta, chave, recordes,
                  motivo=None, sessao=None):
        """`sessao` = (SessionNum, SessionUniqueID): ao mudar, as voltas em andamento sao descartadas
        (os recordes pessoais em arquivo continuam valendo). `motivo` = por que esta volta e suja."""
        try:
            if chave != self._chave or (sessao is not None and sessao != self._sessao):
                if self._chave is not None:
                    registrar_calculo("setores: estado reiniciado", motivo="troca de sessao, pista ou carro")
                self.resetar()
                self._chave = chave
                self._sessao = sessao
            if voltas_completas is None:
                return
            if self._voltas is None:
                self._voltas = voltas_completas
            elif voltas_completas != self._voltas:
                if voltas_completas == self._voltas + 1:
                    self._finalizar_volta(ultima_volta, chave, recordes)
                else:
                    self.resetar()              # sessao reiniciada / contador voltou
                    self._chave = chave
                self._voltas = voltas_completas
                self._zerar_volta()
            if na_box:
                self._marcar("boxes")
            if motivo:
                self._marcar(motivo)
            if pct is None or tempo_volta is None or tempo_volta < 0 or not (0.0 <= pct < 1.0):
                self.anterior = None
                return
            if self.anterior is not None:
                p0, t0 = self.anterior
                dp = pct - p0
                if 0.0 < dp < 0.05 and tempo_volta >= t0:
                    for j in range(self.n - 1):
                        b = self.inicios[j + 1]
                        if self.cruz[j] is None and p0 < b <= pct:
                            self.cruz[j] = t0 + (b - p0) / dp * (tempo_volta - t0)
                elif dp >= 0.05:
                    self._marcar("salto na posicao (reset/teleporte)")   # reset do carro / teleporte
            self.anterior = (pct, tempo_volta)
            self.tempo_max = max(self.tempo_max, tempo_volta)
        except Exception:
            registrar_erro("analise de setores")

    def exibicao(self, registro):
        """Dados prontos para a janela. `registro` = recorde atual da pista + carro (ou None)."""
        n = self.n
        ref = registro if (registro and registro.get("n") == n) else None
        linhas = []
        for k in range(n):
            tempo = delta = None
            roxo = ao_vivo = False
            fim = self.cruz[k] if k < n - 1 else None
            inicio = (self.cruz[k - 1] if k else 0.0)
            if fim is not None and inicio is not None:        # setor concluido na volta em andamento
                tempo, ao_vivo = fim - inicio, True
                if ref:
                    delta = tempo - ref["setores_melhor"][k]
                    roxo = tempo < ref["melhores_setores"][k] - 1e-9
            elif self.ultima and self.ultima.get("setores"):  # senao, o da ultima volta
                tempo = self.ultima["setores"][k]
                ref_a = self.ultima.get("ref_antes")
                if ref_a:
                    delta = tempo - ref_a["setores_melhor"][k]
                    roxo = bool(self.ultima["roxos"][k])
            linhas.append({"tempo": tempo, "delta": delta, "roxo": roxo, "ao_vivo": ao_vivo})
        ultima = None
        if self.ultima:
            u = self.ultima
            base = u.get("ref_antes") or ref
            ultima = {"tempo": u["tempo"], "valida": u["valida"], "roxo": bool(u["melhor_volta"]),
                      "delta": (u["tempo"] - base["melhor"]) if base else None}
        otima = None
        if ref and all(m is not None for m in ref["melhores_setores"]):
            otima = sum(ref["melhores_setores"])
        return {"n": n, "linhas": linhas, "ultima": ultima, "melhor": ref["melhor"] if ref else None,
                "otima": otima, "estimado": self.estimado}


class RitmoVolta:
    """Tempo de volta tipico (mediana das ultimas voltas limpas), usado para estimar voltas em corridas por tempo."""

    def __init__(self):
        self.tempos = deque(maxlen=5)
        self._voltas = None
        self._sujo = False

    def atualizar(self, voltas_completas, ultima_volta, na_box):
        if na_box:
            self._sujo = True
        if voltas_completas is None:
            return
        if self._voltas is None:
            self._voltas = voltas_completas
            return
        if voltas_completas != self._voltas:
            if voltas_completas == self._voltas + 1:
                if ultima_volta and ultima_volta > 0 and not self._sujo:
                    self.tempos.append(float(ultima_volta))
            elif voltas_completas < self._voltas:
                self.tempos.clear()
            self._voltas = voltas_completas
            self._sujo = False

    @property
    def estimativa(self):
        if not self.tempos:
            return None
        ordenados = sorted(self.tempos)
        return ordenados[len(ordenados) // 2]


def _paradas_restantes(restante, cap_voltas, margem):
    """Paradas ainda necessarias DEPOIS de sair cheio de uma parada, faltando `restante` voltas.

    Estrategia gulosa (a que minimiza o numero de paradas): anda o maximo de voltas inteiras que o tanque
    cheio permite chegando na parada seguinte com `margem` voltas de reserva, e reabastece ate o topo.
    Devolve None se o tanque nao permite avancar nem uma volta com essa reserva.
    """
    k, restante = 0, float(restante)
    while cap_voltas < restante + margem - 1e-9:
        avanca = math.floor(cap_voltas - margem + 1e-9)
        if avanca < 1:
            return None
        restante -= avanca
        k += 1
        if k > 300:
            return None
    return k


def planejar_paradas(nivel, consumo, capacidade, margem, voltas_fim, resto):
    """Plano de paradas de combustivel (Fase 20.1): numero MINIMO de paradas e janela da 1a parada.

    nivel/consumo/capacidade em litros (litros por volta); margem em voltas de reserva, exigida na chegada
    de CADA parada e na bandeirada; voltas_fim = voltas ate o fim contando o que falta da volta atual;
    resto = fracao da volta atual que ainda falta (0..1]. Paradas so acontecem nas passagens pela linha
    (volta inteira); cada parada reabastece ate o topo do tanque.
    Devolve {"n", "primeira", "ultima", "viavel", "urgente", "motivo"}; primeira/ultima = voltas A PARTIR
    DE AGORA (0 = ao fim da volta atual). `n` e None se nao existe plano viavel.
    motivos: None (ok) | sem_dados | nao_chega_ao_box | tanque_insuficiente | sem_janela
    """
    r = {"n": None, "primeira": None, "ultima": None, "viavel": False, "urgente": False, "motivo": None}
    if not consumo or consumo <= 0 or voltas_fim is None or nivel is None:
        r["motivo"] = "sem_dados"
        return r
    margem = max(0.0, float(margem or 0.0))
    resto = min(max(float(resto), 1e-6), 1.0)
    f0 = nivel / consumo
    if f0 >= voltas_fim + margem - 1e-9:                      # chega ao fim com a margem, sem parar
        r.update(n=0, viavel=True)
        return r
    cap = (capacidade / consumo) if (capacidade and capacidade > 0) else None
    # ultima passagem pela linha em que ainda se chega com a reserva; sem ela, so a primeira (urgente)
    j_max = math.floor(f0 - margem - resto + 1e-9)
    if j_max < 0:
        if f0 - resto < -1e-9:
            r["motivo"] = "nao_chega_ao_box"                   # nem a proxima linha de chegada e alcancavel
            return r
        r["urgente"], j_max = True, 0
    melhor, janela = None, []
    for j in range(0, min(j_max, 400) + 1):
        queimado = resto + j
        if queimado >= voltas_fim - 1e-9:                      # a bandeirada vem antes desta passagem
            break
        extra = 0 if cap is None else _paradas_restantes(voltas_fim - queimado, cap, margem)
        if extra is None:
            continue
        total = 1 + extra
        if melhor is None or total < melhor:
            melhor, janela = total, [j]
        elif total == melhor:
            janela.append(j)
    if melhor is None:
        r["motivo"] = "tanque_insuficiente" if cap is not None and cap - margem < 1 else "sem_janela"
        return r
    r.update(n=melhor, primeira=min(janela), ultima=max(janela), viavel=True)
    return r


def detalhar_paradas(nivel, consumo, capacidade, margem, voltas_fim, resto, plano):
    """Litros de CADA parada do plano (Fase 20.2), a partir da 1a parada de `plano` (planejar_paradas).

    Regra: a parada reabastece ATE O TOPO do tanque (capacidade - combustivel projetado na chegada ao box),
    exceto a ultima, que so poe o que falta para terminar com a margem. O combustivel na chegada a 1a parada e
    `nivel - consumo x (resto + j)` (j = voltas inteiras a partir de agora). Cada parada seguinte e feita o mais
    tarde possivel mantendo a margem. Devolve [{"j", "chegada_l", "adicionar_l", "ate_o_topo"}]; a soma dos
    litros e sempre o total (voltas_fim + margem) x consumo - nivel. Lista vazia se nao ha parada ou plano.
    """
    if not plano.get("viavel") or not plano.get("n") or not consumo or consumo <= 0:
        return []
    restante = max(0.0, (voltas_fim + margem) * consumo - nivel)
    j = plano["primeira"]
    chegada = nivel - consumo * (resto + j)
    paradas = []
    while restante > 1e-9 and len(paradas) < 400:
        livre = max(0.0, capacidade - chegada) if capacidade else restante
        adicionar = min(livre, restante)
        paradas.append({"j": j, "chegada_l": chegada, "adicionar_l": adicionar,
                        "ate_o_topo": bool(capacidade) and adicionar >= livre - 1e-9})
        restante -= adicionar
        if restante <= 1e-9:
            break
        saida = chegada + adicionar
        avanca = math.floor(saida / consumo - margem + 1e-9)
        if avanca < 1:
            break
        j += avanca
        chegada = saida - consumo * avanca
    return paradas


def _voltas_ate_fim(voltas_sessao, tempo_restante, ritmo, pct):
    """(voltas ate a bandeirada contando o que falta da volta atual, fonte). Se ha limite de voltas E de tempo,
    vale o que acabar primeiro. No tempo: a corrida acaba na primeira passagem pela linha apos o relogio zerar."""
    candidatos = []
    if voltas_sessao is not None and 0 <= voltas_sessao < 30000:
        candidatos.append((max(0.0, float(voltas_sessao) - pct), "voltas"))
    if tempo_restante is not None and 0 <= tempo_restante < 86400 and ritmo and ritmo > 20:
        candidatos.append((max(0.0, math.ceil(pct + tempo_restante / ritmo - 1e-9) - pct), "tempo"))
    return min(candidatos) if candidatos else (None, None)


def calcular_combustivel(nivel, consumo, voltas_sessao, tempo_restante, ritmo, pct_volta,
                         margem_voltas, capacidade):
    """Quanto combustivel falta para terminar a sessao, com margem de seguranca.

    voltas_sessao : SessionLapsRemainEx (voltas restantes, contando a que esta em andamento) ou None
    tempo_restante: SessionTimeRemain em segundos (corridas por tempo) ou None
    ritmo         : tempo de volta tipico em segundos (para corridas por tempo)
    pct_volta     : fracao da volta atual ja percorrida (0..1)
    margem_voltas : voltas extras de combustivel como folga de seguranca
    capacidade    : litros que o tanque comporta (ou None)
    `paradas` e o numero MINIMO de paradas (planejar_paradas: a margem vale em cada parada, entao o tanque
    rende `capacidade - margem x consumo` por parada); None = nao ha plano viavel (`motivo` diz por que).
    """
    r = {"voltas_fim": None, "fonte": None, "ritmo": ritmo, "necessario": None, "adicionar": None,
         "folga": None, "livre_tanque": None, "paradas": None, "margem_voltas": margem_voltas,
         "nivel": nivel, "motivo": None, "primeira_parada": None}
    pct = pct_volta if (pct_volta is not None and 0.0 <= pct_volta < 1.0) else 0.0
    r["voltas_fim"], r["fonte"] = _voltas_ate_fim(voltas_sessao, tempo_restante, ritmo, pct)
    if capacidade and capacidade > 0:
        r["livre_tanque"] = max(0.0, capacidade - nivel)
    if r["voltas_fim"] is None or not consumo or consumo <= 0:
        return r
    necessario = (r["voltas_fim"] + margem_voltas) * consumo
    r["necessario"] = necessario
    r["adicionar"] = max(0.0, necessario - nivel)
    r["folga"] = max(0.0, nivel - necessario)
    if r["adicionar"] == 0:
        r["paradas"] = 0
    else:
        plano = planejar_paradas(nivel, consumo, capacidade, margem_voltas, r["voltas_fim"], 1.0 - pct)
        r["paradas"], r["motivo"] = plano["n"], plano["motivo"]
        det = detalhar_paradas(nivel, consumo, capacidade, margem_voltas, r["voltas_fim"], 1.0 - pct, plano)
        r["primeira_parada"] = det[0]["adicionar_l"] if det else None   # litros da 1a parada (ate o topo, se houver mais)
    return r


def calcular_painel_combustivel(nivel, capacidade, c_med, c_max, c_min, voltas_fim, volta_atual, pct,
                                margem, ritmo, tempo_restante, ultimas):
    """Painel de estrategia de combustivel: janela de pit, reabastecimento e autonomia.

    c_med / c_max / c_min : consumo por volta (L) medio, maior e menor das ultimas voltas limpas
    voltas_fim            : voltas ate a bandeirada, contando o que falta da volta atual (ou None)
    volta_atual / pct     : numero da volta em andamento e fracao ja percorrida
    margem                : voltas extras de folga      ultimas : [(volta, litros)] mais recente por ultimo
    O valor medio e o usado na decisao (a linha marcada com *).
    Fase 20.2: `reabastecer` e `linhas[*]["reabast"]` = litros da PRIMEIRA parada (primeira volta da janela): ate o
    topo (capacidade - combustivel projetado na chegada ao box) quando ainda ha outra parada depois; so o que falta
    quando e a unica/ultima. `parada1` detalha (volta, chegada, litros, faixa na janela) e `plano` lista todas.
    Fase 20.1: a margem vale a cada parada (cada parada rende `capacidade - margem x consumo`); a janela vem de
    planejar_paradas (numero minimo de paradas, em voltas inteiras); "sem_janela" tambem quando o carro nao
    chega ao box ou o tanque nao comporta a estrategia (`janela["motivo"]`).
    """
    pct = pct if (pct is not None and 0.0 <= pct < 1.0) else 0.0
    r = {"nivel": nivel, "capacidade": capacidade, "linhas": {}, "janela": None, "reabastecer": None,
         "tempo": None, "voltas": None, "ultimas": [], "volta_atual": volta_atual, "voltas_fim": voltas_fim,
         "parada1": None, "plano": []}

    def linha(c):
        if not c or c <= 0:
            return None
        voltas = nivel / c
        total = paradas = por_parada = 0.0
        if voltas_fim is not None:
            total = max(0.0, (voltas_fim + margem) * c - nivel)
            if total <= 0:
                paradas, n = 0.0, 0
            elif capacidade and capacidade > 0:
                util = capacidade - margem * c                  # litros que cada parada realmente acrescenta
                paradas = total / util if util > 0 else None
                n = max(1, math.ceil(paradas - 1e-9)) if paradas is not None else 0
            else:
                paradas, n = 1.0, 1
            por_parada = 0.0
            if n:
                det = detalhar_paradas(nivel, c, capacidade, margem, voltas_fim, 1.0 - pct,
                                       planejar_paradas(nivel, c, capacidade, margem, voltas_fim, 1.0 - pct))
                por_parada = det[0]["adicionar_l"] if det else None      # None: sem plano viavel
        return {"uso": c, "voltas": voltas, "paradas": paradas if voltas_fim is not None else None,
                "reabast": por_parada if voltas_fim is not None else None,      # 1a parada (Fase 20.2)
                "total": total if voltas_fim is not None else None,
                "acaba": int((volta_atual - 1) + pct + voltas) + 1}

    for chave, c in (("med", c_med), ("max", c_max), ("min", c_min)):
        r["linhas"][chave] = linha(c)
    med = r["linhas"]["med"]

    # ultimas voltas: consumo e diferenca para a media
    for volta, uso in list(ultimas)[-5:][::-1]:
        r["ultimas"].append({"volta": volta, "uso": uso, "dif": (uso - c_med) if c_med else None})

    if not med or voltas_fim is None:
        return r
    c = c_med
    plano = planejar_paradas(nivel, c, capacidade, margem, voltas_fim, 1.0 - pct)
    if plano["n"] == 0:
        r["janela"] = {"estado": "sem_parada", "primeira": None, "ultima": None, "paradas": 0}
        r["reabastecer"] = 0.0
    elif not plano["viavel"]:
        r["janela"] = {"estado": "sem_janela", "primeira": None, "ultima": None, "paradas": None,
                       "urgente": False, "motivo": plano["motivo"]}
        r["reabastecer"] = None                    # sem plano viavel: nao mostra um valor que nao pode ser seguido
    else:
        primeira, ultima = volta_atual + plano["primeira"], volta_atual + plano["ultima"]
        r["janela"] = {"estado": "fechada" if volta_atual < primeira else "aberta",
                       "primeira": primeira, "ultima": ultima, "paradas": plano["n"],
                       "urgente": plano["urgente"], "motivo": None}
        det = detalhar_paradas(nivel, c, capacidade, margem, voltas_fim, 1.0 - pct, plano)
        r["plano"] = [dict(d, volta=volta_atual + d["j"]) for d in det]
        d1 = det[0]
        ult = detalhar_paradas(nivel, c, capacidade, margem, voltas_fim, 1.0 - pct, dict(plano, primeira=plano["ultima"]))
        r["parada1"] = {"volta": volta_atual + d1["j"], "chegada_l": d1["chegada_l"], "adicionar_l": d1["adicionar_l"],
                        "ate_o_topo": d1["ate_o_topo"], "adicionar_ultima_volta_l": ult[0]["adicionar_l"],
                        "volta_ultima": ultima}
        r["reabastecer"] = d1["adicionar_l"]
        med["reabast"] = r["reabastecer"]
    # autonomia (sem margem): quanto dura o combustivel e quanto falta para a bandeirada
    r["voltas"] = {"autonomia": med["voltas"], "dif": med["voltas"] - voltas_fim}
    if ritmo and ritmo > 20:
        tempo_corrida = tempo_restante if (tempo_restante is not None and 0 <= tempo_restante < 86400) else voltas_fim * ritmo
        r["tempo"] = {"autonomia": med["voltas"] * ritmo, "dif": med["voltas"] * ritmo - tempo_corrida}
    return r


def fmt_dec(valor, casas=1, sinal=False):
    """Numero com virgula decimal (padrao brasileiro). None -> '-'."""
    if valor is None:
        return "-"
    texto = f"{valor:+.{casas}f}" if sinal else f"{valor:.{casas}f}"
    return texto.replace(".", ",")


def fmt_dist_aprox(metros):
    """Distancia CALCULADA (Δ posicao na pista x comprimento): sempre com '~' e arredondada,
    para nao parecer medida exata (0,5 m abaixo de 10 m; 1 m acima)."""
    try:
        m = max(0.0, float(metros))
    except (TypeError, ValueError):
        return "--"
    if m < 0.5:
        return "<0,5 m"
    m = round(m * 2.0) / 2.0 if m < 10.0 else float(round(m))
    return "~" + fmt_dec(m, 1 if m < 10.0 else 0) + " m"


def fmt_hms(segundos, sinal=False):
    """Segundos -> HH:MM:SS (com sinal opcional)."""
    if segundos is None:
        return "-"
    neg = segundos < 0
    t = int(round(abs(segundos)))
    texto = f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"
    if neg:
        return "-" + texto
    return ("+" + texto) if sinal else texto


def _mistura(c1, c2, f):
    f = max(0.0, min(1.0, f))
    return tuple(int(round(a + (b - a) * f)) for a, b in zip(c1, c2))


def cor_temperatura(temp, ideal_min=80.0, ideal_max=105.0):
    """Azul (frio) -> verde (faixa ideal) -> amarelo -> vermelho (quente demais)."""
    if temp is None:
        return (90, 90, 100)
    azul, ciano, verde = (60, 100, 255), (60, 200, 230), (60, 200, 90)
    amarelo, vermelho = (250, 200, 40), (235, 60, 60)
    if temp < ideal_min - 15:
        return _mistura(azul, ciano, (temp - (ideal_min - 45)) / 30.0)
    if temp < ideal_min:
        return _mistura(ciano, verde, (temp - (ideal_min - 15)) / 15.0)
    if temp <= ideal_max:
        return verde
    if temp <= ideal_max + 12:
        return _mistura(verde, amarelo, (temp - ideal_max) / 12.0)
    return _mistura(amarelo, vermelho, (temp - ideal_max - 12) / 13.0)


def cor_vida(restante):
    """Cor da vida util restante do pneu (0..1)."""
    if restante is None:
        return (90, 90, 100)
    if restante >= 0.70:
        return (60, 200, 90)
    if restante >= 0.45:
        return (250, 200, 40)
    if restante >= 0.25:
        return (255, 140, 40)
    return (235, 60, 60)


def _trio_valido(valores, minimo):
    """Tupla de 3 numeros (esq, meio, dir) ou None se ausente / sem leitura (tudo abaixo do minimo)."""
    try:
        trio = tuple(float(v) for v in valores)
    except (TypeError, ValueError):
        return None
    return trio if max(trio) > minimo else None



def comprimento_pista(texto):
    """'5.41 km' / '3.35 mi' -> metros (None se nao reconhecido)."""
    try:
        m = re.match(r"\s*([0-9]+(?:[.,][0-9]+)?)\s*(km|mi|m)?", str(texto).lower())
        valor = float(m.group(1).replace(",", "."))
        unidade = m.group(2) or "km"
        metros = valor * {"km": 1000.0, "mi": 1609.344, "m": 1.0}[unidade]
        return metros if metros > 100 else None
    except Exception:
        return None


def _item(lista, i, padrao=None):
    try:
        valor = lista[i]
        return padrao if valor is None else valor
    except Exception:
        return padrao


class MapaPista:
    """Aprende o tracado da pista durante a sua primeira volta e o guarda em disco.

    O iRacing nao entrega o desenho da pista. Usamos a posicao GPS do SEU carro (Lat/Lon) e a
    porcentagem da volta (LapDistPct) para montar uma lista de N_PONTOS_MAPA pontos em ordem ao
    longo da pista. Depois disso, qualquer carro pode ser posicionado so com o seu LapDistPct.
    """

    MINIMO = 0.995  # (Fase 20.1: so para exibicao; a volta completa agora e decidida por LACUNA_MAX)
    LACUNA_MAX = 3   # maior sequencia de pontos sem amostra aceita na volta completa (interpolada no fim)
    SALTO_MAX = 12   # entre duas amostras seguidas, ate N pontos saltados sao interpolados (amostragem lenta)
    TEMPO_MAX_ENTRE_AMOSTRAS = 1.0   # s: acima disso a amostra anterior nao vale para interpolar

    def __init__(self, arquivo):
        self.arquivo = Path(arquivo)
        self.chave = None
        self._cache = {}
        try:
            self._cache = json.loads(self.arquivo.read_text(encoding="utf-8"))
        except Exception:
            self._cache = {}
        self._zerar()

    def _zerar(self):
        self.bins = [None] * N_PONTOS_MAPA
        self.preenchidos = 0
        self.completo = False
        self.pontos = None
        self.versao = 0
        self.origem = None
        self._pos = (0.0, 0.0)      # posicao estimada (so no modo alternativo por direcao)
        self._t_ant = None
        self._b0 = None
        self._primeira = None
        self._usou_direcao = False
        self._ult_i = self._ult_pos = self._ult_t = None   # ultima amostra valida (continuidade)
        self.interpolados = 0                              # pontos preenchidos entre amostras seguidas

    # -- pista atual -----------------------------------------------------------
    def definir_pista(self, chave):
        if chave == self.chave:
            return
        self.chave = chave
        self._zerar()
        guardado = self._cache.get(chave)
        if isinstance(guardado, list) and len(guardado) == N_PONTOS_MAPA:
            try:
                self.pontos = [(float(a), float(b)) for a, b in guardado]
                self.completo = True
                self.preenchidos = N_PONTOS_MAPA
            except Exception:
                self.pontos = None
                self.completo = False
        self.versao += 1

    def refazer(self):
        """Esquece o mapa guardado desta pista e comeca a aprender de novo."""
        chave = self.chave
        if chave is None:
            return
        self._cache.pop(chave, None)
        self._salvar()
        self.chave = None
        self.definir_pista(chave)

    # -- aprendizado -------------------------------------------------------------
    def atualizar(self, pct, lat, lon, na_pista, velocidade=0.0, direcao=None, agora=None):
        """pct 0..1; lat/lon em graus; velocidade em m/s; direcao (yaw) em rad como alternativa."""
        if self.completo or self.chave is None:
            return
        try:
            if pct is None or not (0.0 <= float(pct) < 1.0) or not na_pista or velocidade < 3.0:
                self._t_ant = None
                self._ult_i = self._ult_pos = self._ult_t = None   # box/parado/fora da pista: quebra a continuidade
                return
            agora = time.time() if agora is None else agora
            if lat is not None and lon is not None and (abs(lat) > 1e-9 or abs(lon) > 1e-9):
                if self.origem is None:
                    self.origem = (float(lat), float(lon))
                lat0, lon0 = self.origem
                x = (float(lon) - lon0) * math.cos(math.radians(lat0)) * 111320.0
                y = (float(lat) - lat0) * 110540.0
            elif direcao is not None:
                # Alternativa: integra velocidade e direcao (acumula erro; corrigido ao fechar a volta)
                self._usou_direcao = True
                if self._t_ant is not None:
                    dt = min(max(agora - self._t_ant, 0.0), 0.2)
                    self._pos = (self._pos[0] - math.sin(direcao) * velocidade * dt,
                                 self._pos[1] + math.cos(direcao) * velocidade * dt)
                self._t_ant = agora
                x, y = self._pos
            else:
                return
            i = int(float(pct) * N_PONTOS_MAPA) % N_PONTOS_MAPA
            if self._b0 is None:
                self._b0 = i
                self._primeira = (x, y)
            # amostragem lenta x velocidade alta: o carro pode saltar varios pontos entre duas amostras.
            # Entre DUAS amostras reais seguidas (mesmo trecho, pouco tempo) a interpolacao linear e valida.
            if self._ult_i is not None and agora - self._ult_t <= self.TEMPO_MAX_ENTRE_AMOSTRAS:
                salto = (i - self._ult_i) % N_PONTOS_MAPA
                if 1 < salto <= self.SALTO_MAX:
                    x0, y0 = self._ult_pos
                    for k in range(1, salto):
                        b = (self._ult_i + k) % N_PONTOS_MAPA
                        if self.bins[b] is None:
                            f = k / float(salto)
                            self.bins[b] = (x0 + (x - x0) * f, y0 + (y - y0) * f)
                            self.preenchidos += 1
                            self.interpolados += 1
            self._ult_i, self._ult_pos, self._ult_t = i, (x, y), agora
            if self.bins[i] is None:
                self.preenchidos += 1
            self.bins[i] = (x, y)
            self._ultima = (x, y)
            self.versao += 1
            if self.preenchidos >= N_PONTOS_MAPA // 2 and self.lacuna_maxima() <= self.LACUNA_MAX:
                self._finalizar()
        except Exception:
            registrar_erro("mapa (aprendizado)")

    def lacuna_maxima(self):
        """Maior sequencia (circular) de pontos ainda sem amostra. A volta esta completa quando <= LACUNA_MAX."""
        n = N_PONTOS_MAPA
        ancora = next((i for i in range(n) if self.bins[i] is not None), None)
        if ancora is None:
            return n
        maior = atual = 0
        for k in range(1, n + 1):
            if self.bins[(ancora + k) % n] is None:
                atual += 1
                if atual > maior:
                    maior = atual
            else:
                atual = 0
        return maior

    def _finalizar(self):
        bins = list(self.bins)
        n = N_PONTOS_MAPA
        if self._usou_direcao and self._primeira is not None:
            # distribui o erro acumulado ao longo da volta
            dx, dy = self._ultima[0] - self._primeira[0], self._ultima[1] - self._primeira[1]
            for i in range(n):
                if bins[i] is not None:
                    r = ((i - self._b0) % n) / float(n)
                    bins[i] = (bins[i][0] - dx * r, bins[i][1] - dy * r)
        # preenche pequenos buracos por interpolacao linear (circular)
        for i in range(n):
            if bins[i] is None:
                a = next(k for k in range(1, n) if bins[(i - k) % n] is not None)
                b = next(k for k in range(1, n) if bins[(i + k) % n] is not None)
                pa, pb = bins[(i - a) % n], bins[(i + b) % n]
                f = a / float(a + b)
                bins[i] = (pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f)
        self.pontos = bins
        self.completo = True
        self.versao += 1
        if self.chave:
            self._cache[self.chave] = [[round(x, 1), round(y, 1)] for x, y in bins]
            self._salvar()

    def _salvar(self):
        try:
            self.arquivo.write_text(json.dumps(self._cache), encoding="utf-8")
        except Exception:
            pass

    # -- exibicao ----------------------------------------------------------------
    def exibicao(self):
        """Lista de pontos (com None onde ainda nao ha dado) e metadados para a janela."""
        return {
            "pontos": self.pontos if self.completo else self.bins,
            "completo": self.completo,
            "progresso": 1.0 if self.completo else min(0.99, self.preenchidos / float(N_PONTOS_MAPA)),
            "versao": self.versao,
        }


def montar_mapa_carros(pilotos, meu, pcts, superficie):
    """Lista de carros (porcentagem da volta, numero, cor da classe) para o desenho do mapa."""
    carros = []
    for idx, piloto in pilotos.items():
        pct = _item(pcts, idx, -1.0)
        surf = _item(superficie, idx, -1)
        if pct is None or pct < 0 or surf == -1:
            continue
        carros.append({
            "pct": float(pct) % 1.0,
            "numero": piloto.get("numero", ""),
            "cor": piloto.get("classe_cor", (150, 150, 160)),
            "eu": idx == meu,
        })
    carros.sort(key=lambda c: c["eu"])  # voce por ultimo (desenhado por cima)
    return carros


_LADOS = {2: (1, 0), 3: (0, 1), 4: (1, 1), 5: (2, 0), 6: (0, 2)}  # CarLeftRight -> (esquerda, direita)


def montar_radar(pilotos, meu, pcts, superficie, box, lado, comprimento, alcance=ALCANCE_RADAR,
                 memoria=None, agora=None):
    """Carros ao redor de voce, com distancia, aproximacao longitudinal e urgencia.

    O que e CONFIRMADO, o que e CALCULADO e o que e INFERIDO (Fase 20.1):
      - OCUPACAO LATERAL (confirmada pelo SDK): CarLeftRight diz quantos carros ha a esquerda e a direita.
        Vai em `esq`/`dir` e `ocupacao_sdk`. O SDK NAO diz QUAL carro (CarIdx) esta ali.
      - IDENTIDADE (inferida): o(s) carro(s) mais proximo(s) dentro de ZONA_LATERAL sao ASSUMIDOS como os
        ocupantes (`lado_fonte="inferido"`); `ident`="unica" se ha exatamente os candidatos necessarios,
        "ambigua" se ha mais candidatos que vagas ocupadas.
      - POSICAO LONGITUDINAL (calculada): diferenca de LapDistPct x comprimento da pista (centro a centro).
      - POSICAO LATERAL (desconhecida) dos demais: ficam na sua linha (`lado_fonte="indef"`). O lado e
        LEMBRADO por ~3 s depois que o carro sai da zona lateral (`lado_fonte="lembrado"`).
    A aproximacao longitudinal (`aprox`, `alcance_s`) NAO e previsao de colisao: sem a posicao lateral nao ha
    como saber se os carros se sobrepoem. Por isso a urgencia 3 (perigo) so existe com ocupacao SDK; sem
    lateral conhecida o maximo e 1 (atencao). A urgencia 2 deixou de ser usada.

    `memoria` (dict, persistente entre chamadas) guarda o historico por carro para calcular a
    velocidade de aproximacao. Retorna None se nao houver dados suficientes.
    """
    if not comprimento:
        return None
    pct_eu = _item(pcts, meu, None)
    if pct_eu is None or pct_eu < 0:
        return None
    agora = time.time() if agora is None else agora
    memoria = {} if memoria is None else memoria
    eu_na_box = bool(_item(box, meu, False))
    candidatos = []
    for idx, piloto in pilotos.items():
        if idx == meu:
            continue
        pct = _item(pcts, idx, -1.0)
        surf = _item(superficie, idx, -1)
        if pct is None or pct < 0 or surf in (-1, 1):
            memoria.pop(idx, None)
            continue
        if bool(_item(box, idx, False)) and not eu_na_box:
            memoria.pop(idx, None)
            continue
        dist = ((pct - pct_eu + 0.5) % 1.0 - 0.5) * comprimento
        if abs(dist) > alcance * 1.3:
            memoria.pop(idx, None)
            continue
        candidatos.append({"idx": idx, "dist": dist, "faixa": 0.0, "aprox": 0.0, "alcance_s": None, "ident": None,
                           "gap": max(0.0, abs(dist) - COMPR_CARRO), "urgencia": 0,
                           "lado_fonte": "indef",       # "inferido" (ocupacao SDK) | "lembrado" (<= 3 s) | "indef"
                           "numero": piloto.get("numero", ""),
                           "cor": piloto.get("classe_cor", (150, 150, 160))})

    # ---- lado: carros apontados pelo aviso de "carro ao lado" -------------------------------
    n_esq, n_dir = _LADOS.get(int(lado), (0, 0)) if lado is not None else (0, 0)
    ao_lado = sorted((c for c in candidatos if abs(c["dist"]) <= ZONA_LATERAL),
                     key=lambda c: abs(c["dist"]))
    designados = ao_lado[: n_esq + n_dir]
    esquerda_restante, direita_restante = n_esq, n_dir
    alternar = esquerda_restante >= 1 and direita_restante >= 1
    for k, c in enumerate(designados):
        usar_esquerda = (k % 2 == 0) if alternar else esquerda_restante > 0
        if usar_esquerda and esquerda_restante > 0:
            c["faixa"] = -float(n_esq - esquerda_restante + 1)
            esquerda_restante -= 1
        elif direita_restante > 0:
            c["faixa"] = float(n_dir - direita_restante + 1)
            direita_restante -= 1
        elif esquerda_restante > 0:
            c["faixa"] = -float(n_esq - esquerda_restante + 1)
            esquerda_restante -= 1
    ids_designados = {c["idx"] for c in designados}
    ambigua = len(ao_lado) > len(designados)       # mais candidatos que vagas ocupadas: identidade incerta
    for c in ao_lado:
        if designados and (c in designados or ambigua):
            c["ident"] = "ambigua" if ambigua else "unica"
    for c in designados:
        c["lado_fonte"] = "inferido"               # a ocupacao e do SDK; QUEM esta ali e inferencia nossa
    sem_par = (max(0, esquerda_restante), max(0, direita_restante))   # SDK acusa carro, mas nenhum bate com ele

    # ---- memoria: lado lembrado e velocidade de aproximacao ---------------------------------
    for c in candidatos:
        m = memoria.setdefault(c["idx"], {})
        # velocidade de aproximacao (m/s; positiva = a distancia entre os carros esta diminuindo)
        if "dist" in m:
            dt = agora - m["t"]
            if 0.005 < dt < 0.5:
                v = (abs(m["dist"]) - abs(c["dist"])) / dt
                if abs(v) < 120.0:
                    m["vel"] = v if "vel" not in m else m["vel"] + 0.35 * (v - m["vel"])
        m["dist"], m["t"] = c["dist"], agora
        c["aprox"] = m.get("vel", 0.0)

        if c["idx"] in ids_designados:
            m["faixa"], m["t_faixa"] = c["faixa"], agora
        elif "faixa" in m:
            idade = agora - m["t_faixa"]
            if abs(c["dist"]) <= ZONA_LATERAL or idade >= TEMPO_MEMORIA_LADO:
                # o aviso de lateral do iRacing esta limpo para este carro, ou a memoria expirou
                m.pop("faixa", None)
            else:
                c["faixa"] = m["faixa"] * (1.0 - idade / TEMPO_MEMORIA_LADO)
                c["lado_fonte"] = "lembrado"

        # tempo de ALCANCE longitudinal (so quando esta se aproximando) e urgencia. Nao e previsao de colisao.
        if c["aprox"] > 1.0 and c["gap"] > 0:
            c["alcance_s"] = c["gap"] / c["aprox"]
        perto = ((c["alcance_s"] is not None and c["alcance_s"] < 3.5) or c["gap"] < 2.5
                 or abs(c["dist"]) < 10.0)
        if c["lado_fonte"] == "inferido" and abs(c["dist"]) <= ZONA_LATERAL:
            c["urgencia"] = 3                       # ocupacao lateral CONFIRMADA pelo SDK (carro inferido)
        elif perto:
            c["urgencia"] = 1                       # atencao: perto/chegando na pista; lateral desconhecida

    # esquece carros que sairam do alcance
    if len(memoria) > 120:
        presentes = {c["idx"] for c in candidatos}
        for k in [k for k in memoria if k not in presentes]:
            memoria.pop(k, None)

    # ---- resumo: carro mais proximo a frente e atras ----------------------------------------
    def resumo(lista):
        if not lista:
            return None
        c = min(lista, key=lambda q: abs(q["dist"]))
        return {"gap": c["gap"], "dist": c["dist"], "aprox": c["aprox"], "alcance_s": c["alcance_s"],
                "urgencia": c["urgencia"], "numero": c["numero"]}

    return {
        "carros": candidatos, "esq": n_esq, "dir": n_dir, "sem_par": sem_par,
        "ocupacao_sdk": {"esq": n_esq, "dir": n_dir},      # o UNICO dado lateral confirmado pelo SDK
        "frente": resumo([c for c in candidatos if c["dist"] >= 0]),
        "tras": resumo([c for c in candidatos if c["dist"] < 0]),
    }


# --------------------------------------------------------------------------
# Projecao de iRating e Safety Rating  (ESTIMATIVAS)
# --------------------------------------------------------------------------
# As formulas OFICIAIS do iRacing para iRating e SR nao sao publicas. O que segue sao modelos
# aproximados, baseados no que a comunidade documenta; servem como ORDEM DE GRANDEZA em tempo real.
# Para calibrar, o overlay grava em historico_projecoes.csv a projecao de cada corrida: compare
# com o resultado real que o iRacing mostrar depois e ajuste as constantes abaixo.
IR_B = 1600.0 / math.log(2)          # escala logistica do iRating (400 pontos ~ 10x de chance)

# SR: media movel de "curvas por incidente" (CPI). CPI de equilibrio para manter SR 3.00 e janela
# (curvas) por licenca. Valores de D e A vem de estimativas da comunidade; R/C/B/P sao interpolados.
SR_CPI_EQ = {"R": 8.0, "D": 16.0, "C": 28.0, "B": 46.0, "A": 75.0, "P": 90.0}
SR_JANELA = {"R": 300.0, "D": 600.0, "C": 1000.0, "B": 1500.0, "A": 2000.0, "P": 2600.0}
SR_PESO_SESSAO = {"CORRIDA": 1.0, "QUALIFICACAO": 0.5, "AQUECIMENTO": 0.5}   # treino/teste nao contam
SR_SENSIBILIDADE = 1.0               # SR por unidade de variacao logaritmica da taxa de incidentes
SR_CRESCIMENTO_CPI = 0.5             # o CPI de equilibrio cresce e^(0,5) por ponto de SR acima de 3,00
SR_PRIOR_INCIDENTES = 0.5            # "incidente fantasma": evita taxa zero com poucas curvas
SR_TETO_CPI = 3.0                    # corrida limpa vale no maximo 3x o CPI de equilibrio (retornos decrescentes)


def _prob_superar(ri, rj):
    """Chance de um piloto de rating ri terminar a frente de um de rating rj (modelo do iRating)."""
    wi, wj = math.exp(-ri / IR_B), math.exp(-rj / IR_B)
    den = (1.0 - wj) * wi + (1.0 - wi) * wj
    return 0.5 if den <= 0 else ((1.0 - wi) * wj) / den


def variacao_irating(ratings, posicao, i):
    """Variacao estimada de iRating do piloto i (indice em `ratings`), dado que terminaria em
    `posicao` (1 = vencedor) entre len(ratings) pilotos da mesma classe.

    (carros batidos - carros que se esperava bater) x 200 / N. Soma zero entre todos os pilotos.
    """
    n = len(ratings)
    if n < 2 or not 1 <= posicao <= n:
        return None
    esperado = sum(_prob_superar(ratings[i], ratings[j]) for j in range(n) if j != i)
    return ((n - posicao) - esperado) * 200.0 / n


def projetar_irating(pilotos, meu, posc):
    """Projecao do seu iRating se a corrida terminasse agora (apenas a sua classe conta).

    posc = CarIdxClassPosition. Retorna dict (delta, novo, atual, pos, n, por_pos) ou None.
    """
    eu = pilotos.get(meu)
    if not eu:
        return None
    classe = eu.get("classe_id")
    part = []
    for idx, p in pilotos.items():
        if p.get("classe_id") != classe:
            continue
        ir = p.get("irating") or 0
        pos = _item(posc, idx, 0) or 0
        if ir <= 0 or int(pos) <= 0:
            continue
        part.append((int(pos), idx, float(ir)))
    if len(part) < 2 or not any(idx == meu for _, idx, _ in part):
        return None
    part.sort()   # reclassifica 1..N (ignora lacunas e empates)
    ratings = [r for _, _, r in part]
    i = next(k for k, (_, idx, _) in enumerate(part) if idx == meu)
    delta = variacao_irating(ratings, i + 1, i)
    if delta is None:
        return None
    atual = int(ratings[i])
    return {"delta": delta, "novo": atual + int(round(delta)), "atual": atual,
            "pos": i + 1, "n": len(part), "por_pos": 200.0 / len(part)}


def estimar_sr(sr, letra, curvas, incidentes, peso):
    """Variacao estimada de SR se a sessao terminasse agora. Retorna dict ou None se nao se aplica.

    Modelo: a taxa de incidentes por curva da sessao e misturada a media historica (janela de
    curvas da licenca); o SR varia com o logaritmo da razao entre a taxa de equilibrio e a nova taxa.
    Inclui o bonus/perda de 0,40 ao cruzar um numero inteiro de SR.
    """
    if sr is None or peso <= 0:
        return None
    letra = (letra or "C")[:1].upper()
    if letra not in SR_CPI_EQ:
        letra = "C"
    cpi_eq = SR_CPI_EQ[letra] * math.exp(SR_CRESCIMENTO_CPI * (sr - 3.0))
    r_eq = 1.0 / cpi_eq
    c = max(0.0, float(curvas))
    r_sessao = (incidentes + SR_PRIOR_INCIDENTES) / (c + SR_PRIOR_INCIDENTES * cpi_eq)
    r_sessao = max(r_sessao, r_eq / SR_TETO_CPI)
    c_ef = c * peso
    janela = SR_JANELA[letra]
    r_novo = (janela * r_eq + c_ef * r_sessao) / (janela + c_ef)
    novo = sr + SR_SENSIBILIDADE * math.log(r_eq / r_novo)
    novo += 0.4 * (math.floor(novo) - math.floor(sr))      # cruzou um numero inteiro
    novo = min(4.99, max(0.0, novo))
    return {"delta": novo - sr, "novo": novo, "atual": sr}


def montar_projecao(tipo, oficial, ir, sr_info, curvas, incidentes):
    """Dicionario unico consumido pela janela Relativo."""
    return {"tipo": tipo, "oficial": oficial, "ir": ir if tipo == "CORRIDA" else None,
            "sr": sr_info, "curvas": curvas, "inc": incidentes}


class ContadorCurvas:
    """Conta as curvas que voce percorreu (fracao de volta x curvas da pista); zera a cada sessao."""

    def __init__(self):
        self.chave, self.curvas, self._ultimo = None, 0.0, None

    def atualizar(self, chave, pct, contando, curvas_por_volta):
        if chave != self.chave:
            self.chave, self.curvas, self._ultimo = chave, 0.0, None
        if pct is None or pct < 0:
            self._ultimo = None
            return self.curvas
        if contando and curvas_por_volta and self._ultimo is not None:
            d = pct - self._ultimo
            if d < -0.5:
                d += 1.0                       # cruzou a linha de chegada
            if 0.0 <= d < 0.05:                # descarta saltos (reset do carro, teleporte)
                self.curvas += d * curvas_por_volta
        self._ultimo = pct
        return self.curvas


def _tracado_demo():
    """Tracado fictício (curva fechada) para o modo demonstracao."""
    pontos = []
    for i in range(N_PONTOS_MAPA):
        a = 2 * math.pi * i / N_PONTOS_MAPA
        x = 300 * math.cos(a) + 90 * math.cos(3 * a + 0.8)
        y = 170 * math.sin(a) + 70 * math.sin(2 * a + 0.3)
        pontos.append((x, y))
    return pontos


# --------------------------------------------------------------------------
# Estimativa de pneus ao vivo
# --------------------------------------------------------------------------
class EstimadorPneus:
    """Estima desgaste e temperatura de cada pneu DURANTE a corrida.

    O iRacing so informa desgaste/temperatura reais quando o carro para nos boxes. Entre uma parada
    e outra, este modelo acumula um "esforco" por pneu (velocidade x aceleracao lateral/longitudinal,
    distribuido pela transferencia de carga: curva carrega o lado externo, freada o eixo dianteiro,
    aceleracao o traseiro) e converte em perda de vida util. A cada leitura real nos boxes, a
    conversao e RECALIBRADA (e guardada por carro em calibracao_pneus.json).
    Sao estimativas: servem para comparar pneus e acompanhar o ritmo de desgaste, nao como medida.
    """

    G = 9.81
    K_PROV = 3.5e-6          # fracao de vida perdida por unidade de esforco (valor inicial grosseiro)
    E_MIN = 1500.0           # esforco minimo desde a ancora para aceitar uma calibracao
    CANTOS = ("LF", "RF", "LR", "RR")

    def __init__(self, arquivo=None, desgaste_volta=0.007, inverter_lado=False, limite=0.30):
        self.arquivo = arquivo
        self.desgaste_volta = max(0.001, float(desgaste_volta))
        self.inverter = bool(inverter_lado)
        self.limite = float(limite)
        self._cal = self._carregar()
        self.carro = None
        self.k_real = None       # calibrado em parada nos boxes
        self.n_cal = 0
        self.k_base = None       # derivado da 1a volta limpa + desgaste_volta
        self.resetar_sessao()

    # ---- persistencia ---------------------------------------------------
    def _carregar(self):
        try:
            dados = json.loads(Path(self.arquivo).read_text(encoding="utf-8")) if self.arquivo else {}
            return dados if isinstance(dados, dict) else {}
        except Exception:
            return {}

    def _salvar(self):
        if not self.arquivo or not self.carro:
            return
        try:
            self._cal[str(self.carro)] = {"k": self.k_real, "n": self.n_cal}
            tmp = Path(str(self.arquivo) + ".tmp")
            tmp.write_text(json.dumps(self._cal, indent=1), encoding="utf-8")
            tmp.replace(self.arquivo)
        except Exception:
            registrar_erro("salvar calibracao de pneus")

    def definir_carro(self, carro_id):
        if carro_id is None or carro_id == self.carro:
            return
        self.carro = carro_id
        reg = self._cal.get(str(carro_id)) or {}
        k = reg.get("k")
        self.k_real = float(k) if isinstance(k, (int, float)) and k > 0 else None
        self.n_cal = int(reg.get("n", 0)) if self.k_real else 0
        self.k_base = None
        self.resetar_sessao()

    def resetar_sessao(self):
        self.ancora = {c: 1.0 for c in self.CANTOS}          # vida na ultima leitura real (ou 100%)
        self.ancora_real = {c: False for c in self.CANTOS}
        self.energia = {c: 0.0 for c in self.CANTOS}          # esforco desde a ancora
        self.energia_volta = {c: 0.0 for c in self.CANTOS}
        self.voltas = {c: 0 for c in self.CANTOS}
        self.perda_volta = {c: None for c in self.CANTOS}
        self.ultima_leitura = {c: None for c in self.CANTOS}
        self.q = {c: 0.0 for c in self.CANTOS}                # esforco instantaneo suavizado (calor)
        self.temp = {c: None for c in self.CANTOS}
        self._volta = None
        self._volta_limpa = True

    @property
    def k(self):
        return self.k_real or self.k_base or self.K_PROV

    @property
    def origem(self):
        return "boxes" if self.k_real else ("1a volta" if self.k_base else "padrao")

    # ---- fisica simplificada ---------------------------------------------
    def _pesos(self, ay, ax):
        """Fatia de carga de cada pneu (media 1.0) a partir das aceleracoes (m/s2)."""
        ayg = ay / self.G
        if self.inverter:
            ayg = -ayg
        fs = min(1.0, abs(ayg) / 2.5)
        externo = 0.5 + 0.35 * fs
        lado_ext = "R" if ayg > 0 else "L"          # LatAccel > 0 = curva para a esquerda (eixo y a esquerda)
        axg = ax / self.G
        fb = max(0.0, min(1.0, -axg / 2.0))
        fa = max(0.0, min(1.0, axg / 1.0))
        frente = 0.5 + 0.2 * fb - 0.2 * fa
        pesos = {}
        for c in self.CANTOS:
            lado = externo if c[0] == lado_ext else 1.0 - externo
            eixo = frente if c[1] == "F" else 1.0 - frente
            pesos[c] = 4.0 * lado * eixo
        return pesos

    def atualizar(self, dt, ativo, vel, ay, ax, temp_pista=None):
        """Chamado a cada ciclo. ativo = carro na pista, fora da pit lane e nao em replay."""
        if dt <= 0 or dt > 0.5:
            return
        tp = 30.0 if temp_pista is None else float(temp_pista)
        for c in self.CANTOS:
            if self.temp[c] is None:
                self.temp[c] = tp
        if not ativo or vel < 3.0:
            for c in self.CANTOS:                    # esfria devagar
                self.q[c] += (0.0 - self.q[c]) * min(1.0, dt / 4.0)
                self.temp[c] += ((tp + 5.0) - self.temp[c]) * min(1.0, dt / 60.0)
            return
        ayg, axg = ay / self.G, ax / self.G
        esforco = vel * (ayg * ayg + 0.6 * axg * axg)
        pesos = self._pesos(ay, ax)
        for c in self.CANTOS:
            inst = esforco * pesos[c]
            ganho = inst * dt
            self.energia[c] += ganho
            self.energia_volta[c] += ganho
            self.q[c] += (inst - self.q[c]) * min(1.0, dt / 4.0)
            alvo = tp + 25.0 + 45.0 * min(1.3, self.q[c] / 40.0)
            self.temp[c] += (alvo - self.temp[c]) * min(1.0, dt / 20.0)

    def fim_de_volta(self, volta_concluida, na_box):
        """Informe a volta concluida (LapCompleted); detecta a virada e fecha o ciclo da volta."""
        if na_box:
            self._volta_limpa = False
        if volta_concluida is None or volta_concluida < 0:
            return
        if self._volta is None:
            self._volta = volta_concluida
            self.energia_volta = {c: 0.0 for c in self.CANTOS}
            self._volta_limpa = not na_box
            return
        if volta_concluida == self._volta:
            return
        self._volta = volta_concluida
        if self._volta_limpa:
            media = sum(self.energia_volta.values()) / 4.0
            if self.k_base is None and media > self.E_MIN * 0.5:
                self.k_base = self.desgaste_volta / media     # 1a volta limpa define o ritmo base
            for c in self.CANTOS:
                self.voltas[c] += 1
                p = self.k * self.energia_volta[c]
                ant = self.perda_volta[c]
                self.perda_volta[c] = p if ant is None else 0.6 * ant + 0.4 * p
        self.energia_volta = {c: 0.0 for c in self.CANTOS}
        self._volta_limpa = not na_box

    # ---- leituras reais (so atualizam nos boxes) ---------------------------
    def registrar_leituras(self, leituras):
        """leituras: {canto: (esq, meio, dir) ou None}. Retorna True se houve leitura nova."""
        mudou, ks = {}, []
        for c in self.CANTOS:
            trio = leituras.get(c)
            if not trio:
                continue
            real = sum(trio) / 3.0
            ult = self.ultima_leitura[c]
            if ult is not None and abs(real - ult) < 0.003:
                continue
            mudou[c] = (real, ult)
        for c, (real, ult) in mudou.items():
            self.ultima_leitura[c] = real
            if real > self.ancora[c] + 0.10:             # pneu novo
                self.voltas[c] = 0
                self.perda_volta[c] = None
            else:
                queda = self.ancora[c] - real
                if queda > 0.01 and self.energia[c] > self.E_MIN:
                    ks.append(queda / self.energia[c])
            self.ancora[c], self.ancora_real[c], self.energia[c] = real, True, 0.0
        if ks:
            ks.sort()
            novo = ks[len(ks) // 2]
            novo = max(self.K_PROV * 0.05, min(self.K_PROV * 30.0, novo))
            self.k_real = novo if not self.k_real or not self.n_cal else 0.5 * self.k_real + 0.5 * novo
            self.n_cal += 1
            self._salvar()
        return bool(mudou)

    def definir_temp_real(self, canto, valor):
        if valor:
            self.temp[canto] = float(valor)

    # ---- saida ---------------------------------------------------------------
    def vida(self, c):
        return max(0.0, self.ancora[c] - self.k * self.energia[c])

    def resumo(self):
        cantos = {}
        for c in self.CANTOS:
            real = self.ancora_real[c] and self.energia[c] < self.E_MIN * 0.2
            cantos[c] = {"vida": self.vida(c), "tipo": "real" if real else "est",
                         "temp": self.temp[c], "perda_volta": self.perda_volta[c],
                         "voltas": self.voltas[c]}
        pior = min(self.CANTOS, key=lambda c: cantos[c]["vida"])
        perda = cantos[pior]["perda_volta"]
        voltas_limite = None
        if perda and perda > 0.0003:
            voltas_limite = max(0.0, (cantos[pior]["vida"] - self.limite) / perda)
        return {"cantos": cantos, "pior": pior, "voltas_limite": voltas_limite,
                "limite": self.limite, "origem": self.origem, "n_cal": self.n_cal}


def tendencia_chuva(historico, atual, janela=600.0, minimo=60.0, limiar=3.0):
    """historico: lista de (instante_s, chuva_%). Compara a chuva atual com a mais antiga dentro de
    'janela' s (precisa de pelo menos 'minimo' s de historico). Retorna 'subindo' / 'diminuindo' /
    'estavel' ou None enquanto ainda esta medindo."""
    if atual is None or not historico:
        return None
    agora = historico[-1][0]
    antigos = [(t, v) for t, v in historico if agora - t <= janela]
    if not antigos or agora - antigos[0][0] < minimo:
        return None
    delta = atual - antigos[0][1]
    return "subindo" if delta >= limiar else ("diminuindo" if delta <= -limiar else "estavel")


class DetectorImpactos:
    """Detecta batidas pela aceleracao e pelo contador de incidentes (o iRacing nao informa dano por peca).

    - O contador de incidentes sobe: 1 = saiu da pista, 2 = perda de controle / batida em objeto,
      4 = contato com outro carro. E o sinal mais confiavel de que houve impacto.
    - Direcao e forca: pico de aceleracao horizontal (acima da aceleracao "normal" de pilotagem) nos
      ultimos instantes. Aceleracao longitudinal negativa = batida de frente, positiva = de tras; lateral
      indica o lado batido. Impacto forte sem incidente (pancada) tambem e registrado.
    Zonas: F frente, T traseira, E lado esquerdo, D lado direito. Severidade 1 leve, 2 media, 3 forte.
    """

    G = 9.81
    LIMIAR_PANCADA = 6.0 * 9.81     # pico acima da base, m/s2 (acelerar/frear/curvar forte fica abaixo)
    JANELA = 1.5                    # s de amostras guardadas para achar o pico de um incidente
    MAX_EVENTOS = 6

    def __init__(self, inverter_lado=False):
        self.inverter = bool(inverter_lado)
        self.resetar()

    def resetar(self):
        self.amostras = deque()          # (t, ax, ay) ja descontada a base
        self.base = [0.0, 0.0]
        self._t = None
        self.incidentes = None
        self.zonas = {"F": 0, "T": 0, "E": 0, "D": 0}
        self.eventos = []                # mais recente por ultimo
        self._ult_pancada = -99.0
        self._tinha_reparo = False
        self.total = 0                   # impactos registrados na sessao

    def limpar_marcas(self):
        self.zonas = {"F": 0, "T": 0, "E": 0, "D": 0}

    # ---- classificacao ----
    def _zona(self, ax, ay):
        if abs(ax) >= abs(ay):
            return "F" if ax < 0 else "T"
        empurrado_esq = ay > 0                      # LatAccel > 0 = aceleracao para a esquerda
        if self.inverter:
            empurrado_esq = not empurrado_esq
        return "D" if empurrado_esq else "E"        # empurrado para a esquerda = bateram do lado direito

    @staticmethod
    def _severidade(g, delta):
        sev = 3 if g >= 10.0 else (2 if g >= 5.0 else 1)
        if delta == 4:
            sev = max(sev, 2)
        elif delta == 2:
            sev = max(sev, 2)
        return sev

    def _pico(self, agora):
        melhor = None
        for t, ax, ay in self.amostras:
            if agora - t <= self.JANELA:
                m = math.hypot(ax, ay)
                if melhor is None or m > melhor[0]:
                    melhor = (m, ax, ay)
        return melhor

    def _registrar(self, agora, ax, ay, g, delta, tipo):
        zona = self._zona(ax, ay)
        sev = self._severidade(g, delta)
        self.zonas[zona] = max(self.zonas[zona], sev)
        self.eventos.append({"t": agora, "zona": zona, "sev": sev, "g": g, "delta": delta, "tipo": tipo})
        del self.eventos[:-self.MAX_EVENTOS]
        self.total += 1

    # ---- ciclo ----
    def atualizar(self, agora, ax, ay, incidentes, ativo=True, reparo=0.0):
        """ax/ay em m/s2 (longitudinal / lateral). Retorna True se registrou um impacto novo."""
        novo = False
        if ativo:
            dt = 0.033 if self._t is None else max(0.001, min(0.5, agora - self._t))
            k = min(1.0, dt / 0.4)                  # base = aceleracao "normal" que muda devagar
            dx, dy = ax - self.base[0], ay - self.base[1]
            self.base[0] += (ax - self.base[0]) * k
            self.base[1] += (ay - self.base[1]) * k
            self.amostras.append((agora, dx, dy))
            while self.amostras and agora - self.amostras[0][0] > self.JANELA + 0.5:
                self.amostras.popleft()
            mag = math.hypot(dx, dy)
            if mag >= self.LIMIAR_PANCADA and agora - self._ult_pancada > 1.0:
                self._ult_pancada = agora
                self._registrar(agora, dx, dy, mag / self.G, 0, "pancada")
                novo = True
        self._t = agora
        if incidentes is not None:
            if self.incidentes is not None and incidentes > self.incidentes:
                delta = incidentes - self.incidentes
                recente = self.eventos[-1] if self.eventos else None
                if recente and recente["delta"] == 0 and agora - recente["t"] < 2.0:
                    recente["delta"] = delta                       # mesma batida: completa o registro
                    recente["tipo"] = "contato" if delta >= 4 else "batida"
                    recente["sev"] = max(recente["sev"], self._severidade(recente["g"], delta))
                    self.zonas[recente["zona"]] = max(self.zonas[recente["zona"]], recente["sev"])
                else:
                    pico = self._pico(agora)
                    if pico and pico[0] / self.G >= 2.0:
                        m, ax_p, ay_p = pico
                        self._registrar(agora, ax_p, ay_p, m / self.G, delta,
                                        "contato" if delta >= 4 else ("batida" if delta == 2 else "saida"))
                    else:
                        self.eventos.append({"t": agora, "zona": None, "sev": 1, "g": 0.0, "delta": delta,
                                             "tipo": "saida" if delta == 1 else "batida"})
                        del self.eventos[:-self.MAX_EVENTOS]
                novo = True
            self.incidentes = incidentes
        # reparo concluido (tempo de reparo caiu a zero depois de ter existido): limpa as marcas
        if reparo and reparo > 0:
            self._tinha_reparo = True
        elif self._tinha_reparo:
            self._tinha_reparo = False
            self.limpar_marcas()
        return novo

    def exibicao(self, agora):
        return {"zonas": dict(self.zonas), "total": self.total,
                "eventos": [dict(e, idade=agora - e["t"]) for e in self.eventos[-3:]][::-1]}


def estilo_pneu(nome):
    """Nome do composto (DriverTires.TireCompoundType) -> (cor, rotulo). None se desconhecido."""
    if not nome:
        return None
    n = str(nome).lower()
    if "inter" in n:
        return (60, 200, 120), "Intermediario"
    if "wet" in n or "rain" in n or "chuva" in n:
        return (60, 160, 255), "Chuva"
    if "soft" in n or "alternate" in n or "option" in n or "red" in n:
        return (235, 70, 110), "Macio"
    if "medium" in n:
        return (250, 200, 40), "Medio"
    if "hard" in n or "primary" in n:
        return (235, 235, 240), "Duro"
    return (225, 225, 232), str(nome)         # "Dry" e outros: pneu de seco unico


class IdadePneus:
    """Voltas de cada carro desde a ultima parada nos boxes (o iRacing nao informa a idade do pneu dos outros).

    Premissa: toda parada com o carro no box (parado na vaga) troca os pneus, ou o composto mudou.
    Se o overlay entrou depois da largada, a contagem dos carros que ja tinham rodado e aproximada
    (confiavel = False) ate o carro passar por uma parada.
    """

    def __init__(self):
        self.resetar()

    def resetar(self):
        self.carros = {}
        self.chave = None

    @staticmethod
    def _item(lista, i, padrao=None):
        try:
            v = lista[i]
        except (TypeError, IndexError, KeyError):
            return padrao
        return padrao if v is None else v

    def atualizar(self, chave, completadas, box, superficie, compostos):
        if chave != self.chave:
            self.resetar()
            self.chave = chave
        if not completadas:
            return
        for idx, lap in enumerate(completadas):
            if lap is None or lap < 0:
                continue
            na_box = bool(self._item(box, idx, False))
            sup = self._item(superficie, idx, 3)
            comp = self._item(compostos, idx, None)
            comp = comp if (comp is not None and comp >= 0) else None
            c = self.carros.get(idx)
            if c is None:
                c = self.carros[idx] = {"inicio": 0, "parou": False, "box": na_box, "comp": comp,
                                        "confiavel": lap <= 1}
            if sup == 1:                                   # parado na vaga do box
                c["parou"] = True
            if c["box"] and not na_box:                    # saiu da pit lane
                if c["parou"]:
                    c["inicio"], c["confiavel"] = lap, True
                c["parou"] = False
            elif comp is not None and c["comp"] is not None and comp != c["comp"]:
                c["inicio"], c["confiavel"] = lap, True    # composto mudou: pneu novo
            c["box"] = na_box
            if comp is not None:
                c["comp"] = comp

    def voltas(self, idx, completadas):
        c = self.carros.get(idx)
        lap = self._item(completadas, idx, None)
        if c is None or lap is None:
            return None, False
        return max(0, int(lap) - c["inicio"]), c["confiavel"]


# --------------------------------------------------------------------------
# Leitura de telemetria
# --------------------------------------------------------------------------
class Telemetria:
    """Le os dados do iRacing via SDK oficial (ou simula no modo demo)."""

    def __init__(self, demo=False):
        self.demo = demo
        self.conectado = False
        self._t0 = time.time()
        self._ultima_tentativa = 0.0
        self._rpm_max = 8000.0
        self._ultima_leitura_rpm_max = 0.0
        self.consumo = ConsumoCombustivel()
        # Pilotos / sessao (atualizados a cada 2 s)
        self._pilotos = {}
        self._ultima_leitura_pilotos = 0.0
        self._ref_volta = 90.0
        self._limite_inc = None
        self._tipo_sessao = None
        self._pilotos_demo = _pilotos_demo()
        self._classif_demo = _base_classificacao_demo()
        self._pontos_demo = _tracado_demo()
        self.mapa = MapaPista(ARQ_MAPAS)
        self.delta_proprio = DeltaProprio()
        self.ritmo = RitmoVolta()
        self._vida_ultima = {}          # ultima leitura de desgaste por pneu (so atualiza nos boxes)
        self._diag_pneus = False
        self.estimador_pneus = EstimadorPneus(ARQ_PNEUS)
        self._t_pneus = None            # instante do ciclo anterior (dt do estimador)
        self._sessao_pneus = None
        self._temp_ult = {}             # ultima temperatura real vista por pneu
        self._temp_mudou = {}           # quando ela mudou pela ultima vez
        self._ult_temp = {}             # ultima MEDICAO real de temperatura (valores, horario, volta, local)
        self._vida_info = {}            # ultima MEDICAO real de desgaste (horario, volta, local)
        self._hist_chuva = deque()      # (instante, chuva %) para a tendencia
        self.impactos = DetectorImpactos()
        self.v12_tc = v12.DetectorPatinagem("normal")          # v1.2.0
        self.v12_retorno = v12.CalculadorRetorno()
        self.v12_pneus = v12.EstrategiaPneus()
        self.v12_ritmo = v12.RitmoPorPneu()
        self._v12_sessao = None
        self._pico_g = 0.0
        self._sessao_g = None
        self._limitador = nucleo.Limitador()    # blocos lentos (classificacao, clima) nao precisam rodar a 30 Hz
        self._cache_blocos = {}
        self._ultima_ausencia = None
        self._relatorio_na_pista = False
        self.idade_pneus = IdadePneus()
        self._tipos_pneu = {}           # indice do composto -> nome (DriverInfo.DriverTires)
        self._sessao_danos = None
        self.margem_combustivel = 1.0
        self._capacidade = None
        self._aviso_delta = False
        self._memoria_radar = {}
        self._comprimento = None
        self._ultima_leitura_pista = 0.0
        self._curvas_pista = None       # curvas por volta (WeekendInfo.TrackNumTurns)
        self._nome_pista = ""
        self._oficial = None            # WeekendInfo.Official (None = desconhecido)
        self._categoria = None          # WeekendInfo.Category (Road/Oval/...): iRating e SR sao POR categoria
        self._subsessao = None          # WeekendInfo.SubSessionID: identifica a corrida no iRacing (0 = offline)
        self.contador_curvas = ContadorCurvas()
        self.recordes = RecordesPessoais(ARQ_RECORDES)
        self.setores = AnaliseSetores()
        self._chave_pista = None
        self._chave_recorde = None
        self._aviso_setores = False
        self._base_sessao = {}          # SR / iRating no inicio da sessao (para a projecao)
        self._sessao_registrada = None
        self._aguardando_oficial = False   # ha projecao anterior sem atualizacao numerica (base de iRating/SR incerta)
        self.ir = None
        if not demo:
            import irsdk  # biblioteca pyirsdk

            self.ir = irsdk.IRSDK()

    @staticmethod
    def _vazio():
        return {
            "conectado": False,
            "clima": None,         # pista, ar, neblina, vento (direcao e velocidade)
            "tipo_sessao": None,   # CORRIDA / QUALIFICACAO / TREINO... (escolhe o perfil de exibicao)
            "forca_g": None,       # G lateral/longitudinal, total e pico
            "luz_tc": None,        # v1.2.0: {"ativa", "patinagem" (~ estimativa), "estado"}
            "retorno": None,       # v1.2.0: {"visivel", "estado" pare/ceda/livre, "segundos", "cor"}
            "estrategia": None,    # v1.2.0: chuva x seco (SEGUIR / PREPARE-SE / TROCAR)
            "pedais_cru": None,    # v1.2.0: pedais sem a calibracao do carro
            "danos": None,         # reparo necessario, avisos do motor, impactos detectados
            "no_carro": False,     # voce esta dentro do carro, no mundo do jogo (nao na garagem/menu)
            "replay": False,
            "marcha": 0,
            "velocidade": 0.0,  # km/h
            "rpm": 0.0,
            "rpm_max": 8000.0,
            "acelerador": 0.0,
            "freio": 0.0,
            "embreagem": 0.0,
            "abs": False,
            "tc": None,            # ajuste do controle de tracao: {"nivel", "nivel2", "ligado"}
            "abs_nivel": None,     # ajuste do ABS (dcABS), se o carro tiver
            "bias": None,          # balanco de freio (dcBrakeBias), se ajustavel
            # Fase 2
            "volta": 0,
            "tempo_volta": None,   # s
            "ultima_volta": None,  # s
            "melhor_volta": None,  # s
            "delta": 0.0,          # s (negativo = mais rapido que a melhor volta)
            "delta_ok": False,
            "delta_fonte": None,   # "overlay" (calculado aqui) ou "sim" (informado pelo iRacing)
            "combustivel": 0.0,    # litros
            "consumo_volta": None,  # litros por volta
            "voltas_restantes": None,
            "calc_combustivel": None,
            "painel_combustivel": None,   # estrategia: janela de pit, reabastecimento e autonomia
            "pneus": None,
            # Fase 3
            "relativo": None,
            # Fase 4
            "classificacao": None,
            # Fase 5
            "volante": 0.0,        # graus (positivo = para a esquerda)
            "mapa": None,
            "radar": None,
            "projecao": None,
            "setores": None,
        }

    # -- modo demonstracao ----------------------------------------------------
    @staticmethod
    def _demo_pedais(t):
        p = (t / 4.0) % 1.0  # uma "curva" a cada 4 s
        if p < 0.55:
            ace, fre = 1.0, 0.0
        elif p < 0.62:
            k = (p - 0.55) / 0.07
            ace, fre = 1.0 - k, 0.95 * k
        elif p < 0.78:
            k = (p - 0.62) / 0.16
            ace, fre = 0.0, 0.95 - 0.75 * k
        elif p < 0.90:
            k = (p - 0.78) / 0.12
            ace, fre = 0.6 * k, 0.2 * (1.0 - k)
        else:
            k = (p - 0.90) / 0.10
            ace, fre = 0.6 + 0.4 * k, 0.0
        return ace, fre, fre > 0.85

    def _demo_painel_combustivel(self, t, nivel):
        ciclo = (t / 12.0) % 15.0
        usos = [(8 + k, 3.4 + (0.1 if k % 2 else -0.1) * (k % 3)) for k in range(int(ciclo) % 6 + 3)]
        c_med = sum(u for _, u in usos[-5:]) / len(usos[-5:])
        return calcular_painel_combustivel(
            nivel, 88.0, c_med, max(u for _, u in usos), min(u for _, u in usos),
            max(0.0, 21.5 - ciclo), 8 + int(ciclo), (t % 12.0) / 12.0, self.margem_combustivel, 92.0, None, usos)

    def _demo_relativo(self, t):
        tot_eu = 3.0 + t / 12.0
        n = len(_DEMO_OFFSETS)
        tots = [tot_eu + _DEMO_OFFSETS[i] + (0.002 * math.sin(0.7 * t + i) if i else 0.0)
                for i in range(n)]
        pcts = [x % 1.0 for x in tots]
        voltas = [int(x // 1.0) for x in tots]
        box = [False] * n
        box[7] = True
        posc = [0] * n
        por_classe = {}
        for i in range(n):
            por_classe.setdefault(self._pilotos_demo[i]["classe_id"], []).append(i)
        for ids in por_classe.values():
            for pos, i in enumerate(sorted(ids, key=lambda k: -tots[k]), start=1):
                posc[i] = pos
        rel = montar_relativo(self._pilotos_demo, 0, pcts, voltas, None, [3] * n, box, posc, 92.0)
        compostos = [(250, 200, 40), (235, 70, 110), (235, 235, 240), (60, 160, 255)]
        nomes = ["Medio", "Macio", "Duro", "Chuva"]
        for linha in list(rel["frente"]) + [rel["eu"]] + list(rel["atras"]):
            k = linha["idx"] % 4
            linha["pneu"] = {"cor": compostos[k], "nome": nomes[k]}
            linha["voltas_pneu"] = (voltas[linha["idx"]] + 2 * linha["idx"]) % 24
            linha["voltas_pneu_confiavel"] = linha["idx"] % 5 != 3
        classe_eu = self._pilotos_demo[0]["classe_id"]
        rel.update({
            "pista_temp": 38.0,
            "sof": calcular_sof([p["irating"] for p in self._pilotos_demo.values()
                                 if p["classe_id"] == classe_eu]),
            "inc": 1, "inc_limite": 25,
            "volta": int(tot_eu),
            "tempo_restante": max(0.0, 939.0 - (t % 939.0)),
            "voltas_restantes": None,
        })
        return rel

    def _demo_projecao(self, t):
        """Projecao ficticia: o piloto sobe e desce de posicao ao longo do tempo."""
        tot_eu = 3.0 + t / 12.0
        n = len(_DEMO_OFFSETS)
        tots = [tot_eu + _DEMO_OFFSETS[i] for i in range(n)]
        posc = [0] * n
        por_classe = {}
        for i in range(n):
            por_classe.setdefault(self._pilotos_demo[i]["classe_id"], []).append(i)
        for ids in por_classe.values():
            for pos, i in enumerate(sorted(ids, key=lambda k: -tots[k]), start=1):
                posc[i] = pos
        eu = self._pilotos_demo[0]
        curvas = 12.0 * (t / 12.0 + 3.0)
        incidentes = 1 if t > 8 else 0
        sr = estimar_sr(eu["sr"], eu["lic_letra"], curvas, incidentes, 1.0)
        return montar_projecao("CORRIDA", True, projetar_irating(self._pilotos_demo, 0, posc),
                               sr, curvas, incidentes)

    def _demo_setores(self, t):
        """Setores ficticios: 4 setores; a 'volta' demo dura 12 s."""
        volta, ciclo = int(t // 12.0), (t % 12.0) / 12.0
        ref = [18.20, 24.35, 12.80, 17.35]
        melhores = [17.95, 24.10, 12.62, 17.20]

        def tempos(v):
            return [ref[k] + 0.7 * math.sin(v * 1.9 + k * 1.3) - 0.15 for k in range(4)]
        linhas = []
        feitos = int(ciclo * 4)
        for k in range(4):
            ao_vivo = k < feitos
            tempo = tempos(volta)[k] if ao_vivo else (tempos(volta - 1)[k] if volta > 0 else None)
            delta = None if tempo is None else tempo - ref[k]
            linhas.append({"tempo": tempo, "delta": delta,
                           "roxo": tempo is not None and tempo < melhores[k], "ao_vivo": ao_vivo})
        ultima = None
        if volta > 0:
            ult = sum(tempos(volta - 1))
            ultima = {"tempo": ult, "valida": True, "roxo": ult < sum(ref) - 0.4, "delta": ult - sum(ref)}
        return {"n": 4, "linhas": linhas, "ultima": ultima, "melhor": sum(ref), "otima": sum(melhores),
                "estimado": False, "pista": "Interlagos", "carro": "Porsche 911 GT3 R"}

    def _demo_classificacao(self, t):
        pilotos, posc, meu = self._classif_demo
        volta = int(t // 12.0)
        n = len(_DEMO_CARROS_CLASSIF)
        melhores, ultimas = [None] * n, [None] * n
        if volta > 0:  # na primeira volta ainda nao ha tempos
            for i, carro in enumerate(_DEMO_CARROS_CLASSIF):
                base = carro[5]
                melhores[i] = base
                extra = 0.0 if (volta + i) % 5 == 0 else 0.35 + abs(math.sin(volta * 1.7 + i)) * 1.1
                ultimas[i] = base + extra
        box = [False] * n
        box[3] = True
        classif = montar_classificacao(pilotos, meu, posc, ultimas, melhores, box)
        classif["tipo_sessao"] = "CORRIDA"
        classif["volta"] = 1 + volta
        return classif

    def _demo_pneus(self, t):
        voltas = t / 4.0
        cantos = {}
        for i, c in enumerate(CANTOS_PNEUS):
            lado = 1.35 if c[0] == "R" else 1.0            # curva a esquerda carrega o lado direito
            perda = (0.0065 + 0.0006 * i) * lado
            vida = max(0.05, 1.0 - (perda * voltas) % 0.9)
            temp = 74 + 22 * (0.5 + 0.5 * math.sin(t * 0.35 + i)) + (6 if c[0] == "R" else 0)
            cantos[c] = {"vida": vida, "tipo": "real" if voltas % 9 < 0.6 else "est", "temp": temp,
                         "perda_volta": perda, "voltas": int(voltas % 9)}
        pior = min(CANTOS_PNEUS, key=lambda c: cantos[c]["vida"])
        perda = cantos[pior]["perda_volta"]
        ultima = {c: {"temp": (88.0 + 3 * i, 92.0 + 3 * i, 90.0 + 3 * i), "idade": 260.0 + 4.0 * t % 300,
                      "hora": "15:43", "volta": 7, "local": "boxes", "ao_vivo": False,
                      "vida_idade": 260.0 + 4.0 * t % 300, "vida_hora": "15:43", "vida_local": "boxes"}
                  for i, c in enumerate(CANTOS_PNEUS)}
        return {"temp": {c: None for c in CANTOS_PNEUS}, "vida": {c: None for c in CANTOS_PNEUS},
                "fonte": None, "ultima": ultima,
                "est": {"cantos": cantos, "pior": pior, "origem": "boxes", "n_cal": 2, "limite": 0.30,
                        "voltas_limite": max(0.0, (cantos[pior]["vida"] - 0.30) / perda)}}

    def _demo_mapa(self, t):
        tot_eu = 3.0 + t / 12.0
        n = len(_DEMO_OFFSETS)
        pcts = [(tot_eu + _DEMO_OFFSETS[i]) % 1.0 for i in range(n)]
        carros = montar_mapa_carros(self._pilotos_demo, 0, pcts, [3] * n)
        return {"pontos": self._pontos_demo, "completo": True, "progresso": 1.0, "versao": 1,
                "carros": carros}

    def _demo_radar(self, t):
        comprimento = 4000.0
        n = len(_DEMO_OFFSETS)
        pcts = [-1.0] * n
        pcts[0] = 0.5
        d1 = -35.0 + ((t % 16.0) / 16.0) * 70.0       # vem de tras e ultrapassa pela esquerda
        d2 = 14.0 + 3.0 * math.sin(t)                   # carro a frente
        d3 = 7.0 * math.sin(t / 3.0)                    # carro que fica ao lado, pela direita
        d4 = -16.0 + 4.0 * math.sin(t / 2.0)            # carro atras
        for i, dist in ((1, d1), (2, d2), (3, d3), (4, d4)):
            pcts[i] = 0.5 + dist / comprimento
        esq = 1 if abs(d1) <= 5.5 else 0
        dire = 1 if abs(d3) <= 5.5 else 0
        codigo = {(0, 0): 1, (1, 0): 2, (0, 1): 3, (1, 1): 4}[(esq, dire)]
        return montar_radar(self._pilotos_demo, 0, pcts, [3] * n, [False] * n, codigo, comprimento,
                            memoria=self._memoria_radar, agora=t)

    def _demo_retorno(self, t):
        fase = (t % 24.0) / 24.0
        seg = max(0.4, 8.0 - fase * 11.0)
        return {"visivel": fase < 0.7, "segundos": seg, "estado": v12.estado_retorno(seg),
                "cor": v12.cor_retorno(seg), "idx": 7}

    @staticmethod
    def _demo_estrategia(t):
        passo = int((t % 32.0) // 8)
        acao = ("seguir", "prepare", "trocar", "pedido")[passo]
        return {"nivel": (4, 3, 2, 2)[passo], "nivel_nome": v12.nome_nivel((4, 3, 2, 2)[passo]), "tendencia": "secando",
                "acao": acao, "alvo": "seco", "minutos": 14 if acao == "prepare" else None, "vantagem": 1.4,
                "vantagem_estimada": True, "meu_pneu": "chuva", "rivais_outro": 3, "rivais_mesmo": 5,
                "pre_largada": False, "meu_pneu_nome": "Chuva"}

    def _demo(self):
        t = time.time() - self._t0
        ciclo = (t % 12.0) / 12.0  # 12 s por "volta" simulada
        marcha = 1 + int(ciclo * 6)
        pos = (ciclo * 6) % 1.0
        rpm = 3500 + pos * 4300
        vel = 40 + ciclo * 230
        ace, fre, abs_ativo = self._demo_pedais(t)
        volta_idx = int(t // 12.0)
        consumo = 2.4
        nivel = 40.0 - ((t / 12.0) % 15.0) * consumo
        return {
            "conectado": True,
            "no_carro": True,
            "replay": False,
            "danos": {"zonas": {"F": 2, "T": 0, "E": 0, "D": 1},
                      "total": 2, "eventos": [{"zona": "F", "sev": 2, "g": 7.4, "delta": 4, "tipo": "contato", "idade": 12.0 + t % 30},
                                  {"zona": "D", "sev": 1, "g": 3.1, "delta": 2, "tipo": "batida", "idade": 95.0 + t % 30}],
                      "reparo": 38.0, "reparo_opc": 12.0, "avisos": ["Oleo (temp.)"], "incidentes": 6,
                      "limite": 17, "reboque": 0.0, "rapidos": 1},
            "clima": {"pista": 54.0, "ar": 23.0, "neblina": 10.0,
                      "rumo": (t * 0.35) % (2 * math.pi), "vel_carro": vel,
                      "chuva": 35.0 + 25.0 * math.sin(t * 0.1), "tendencia_chuva": "subindo",
                      "pista_molhada": 3, "declarado_molhado": False, "ceu": 2, "dinamico": True,
                      "vento_dir": (math.radians(120) + t * 0.15) % (2 * math.pi),
                      "vento_vel": 3.22 + 2.0 * math.sin(t * 0.4)},
            "marcha": marcha,
            "velocidade": vel,
            "rpm": rpm,
            "rpm_max": 8000.0,
            "acelerador": ace,
            "freio": fre,
            "embreagem": 1.0 if pos > 0.96 else 0.0,
            "abs": abs_ativo,
            "tc": {"nivel": 3.0, "nivel2": None, "ligado": True},
            "abs_nivel": 4.0,
            "bias": 54.5 + 0.5 * math.sin(t / 5.0),
            "volta": 1 + volta_idx,
            "tempo_volta": ciclo * 92.0,
            "ultima_volta": 92.410 if volta_idx > 0 else None,
            "melhor_volta": 91.873 if volta_idx > 0 else None,
            "delta": 0.55 * math.sin(t * 0.9),
            "delta_ok": volta_idx > 0,
            "delta_fonte": "overlay" if volta_idx > 0 else None,
            "combustivel": nivel,
            "consumo_volta": consumo if volta_idx > 1 else None,
            "voltas_restantes": (nivel / consumo) if volta_idx > 1 else None,
            "calc_combustivel": calcular_combustivel(
                nivel, consumo if volta_idx > 1 else None, 18 - (volta_idx % 14), None, 92.0,
                ciclo, self.margem_combustivel, 60.0),
            "painel_combustivel": self._demo_painel_combustivel(t, nivel),
            "tipo_sessao": "CORRIDA",
            "luz_tc": {"ativa": ace > 0.9 and pos < 0.12, "patinagem": 0.07 if (ace > 0.9 and pos < 0.12) else 0.0,
                       "estado": "ok"},
            "pedais_cru": {"acelerador": ace * 0.96, "freio": fre * 0.92, "embreagem": 1.0 if pos > 0.96 else 0.0},
            "retorno": self._demo_retorno(t),
            "estrategia": self._demo_estrategia(t),
            "forca_g": {"lat": 2.4 * math.sin(t * 0.9), "lon": -1.6 * math.cos(t * 1.8) + 0.4,
                        "total": math.hypot(2.4 * math.sin(t * 0.9), -1.6 * math.cos(t * 1.8) + 0.4),
                        "pico": 3.1, "pista": "Road America", "temp": 24.0},
            "relativo": self._demo_relativo(t),
            "classificacao": self._demo_classificacao(t),
            "volante": 150.0 * math.sin(t * 0.8) * (1.0 - fre),
            "pneus": self._demo_pneus(t),
            "mapa": self._demo_mapa(t),
            "radar": self._demo_radar(t),
            "projecao": self._demo_projecao(t),
            "setores": self._demo_setores(t),
        }

    # -- leitura real -----------------------------------------------------------
    def _var(self, nome, padrao=0.0):
        try:
            valor = self.ir[nome]
            return padrao if valor is None else valor
        except Exception:
            return padrao

    def _var_primeiro(self, nomes, padrao=None):
        for nome in nomes:
            valor = self._var(nome, None)
            if valor is not None:
                return valor
        return padrao

    @staticmethod
    def _tempo(valor):
        """Converte para segundos; valores invalidos (<= 0 ou ausentes) viram None."""
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            return None
        return valor if valor > 0 else None

    def _ler_tc(self):
        """Ajuste do controle de tracao (so existe em carros que o tem). O iRacing NAO informa quando
        o TC esta atuando; so o ajuste do dial (dcTractionControl / 2) e se esta ligado."""
        nivel = self._var("dcTractionControl", None)
        nivel2 = self._var("dcTractionControl2", None)
        ligado = self._var("dcTractionControlToggle", None)
        if nivel is None and nivel2 is None and ligado is None:
            return None
        return {"nivel": float(nivel) if nivel is not None else None,
                "nivel2": float(nivel2) if nivel2 is not None else None,
                "ligado": None if ligado is None else bool(ligado)}

    def _atualizar_rpm_max(self):
        agora = time.time()
        if agora - self._ultima_leitura_rpm_max < 5.0:
            return
        self._ultima_leitura_rpm_max = agora
        try:
            limite = self.ir["DriverInfo"]["DriverCarRedLine"]
            if limite and limite > 1000:
                self._rpm_max = float(limite)
        except Exception:
            pass

    def _atualizar_pilotos(self):
        agora = time.time()
        if self._pilotos and agora - self._ultima_leitura_pilotos < 2.0:
            return
        self._ultima_leitura_pilotos = agora
        info = self.ir["DriverInfo"]
        if not info:
            return
        pilotos = {}
        for d in info.get("Drivers") or []:
            try:
                if d.get("CarIsPaceCar") or d.get("IsSpectator"):
                    continue
                pilotos[int(d["CarIdx"])] = {
                    "numero": str(d.get("CarNumber", "")).strip(),
                    "nome": nome_curto(d.get("UserName")),
                    "classe_id": d.get("CarClassID"),
                    "classe_nome": str(d.get("CarClassShortName") or f"Classe {d.get('CarClassID')}"),
                    "classe_cor": cor_de_int(d.get("CarClassColor")),
                    "classe_ordem": ordem_da_classe(d),
                    "irating": int(d.get("IRating") or 0),
                    "sr": licenca_sr(d)[0], "lic_letra": licenca_sr(d)[1],
                    "usuario_id": d.get("UserID"),
                    "carro": str(d.get("CarScreenName") or d.get("CarPath") or ""),
                    "carro_id": str(d.get("CarPath") or d.get("CarScreenName") or ""),
                    "lic": lic_curta(d.get("LicString")),
                    "lic_cor": cor_de_int(d.get("LicColor"), (90, 90, 100)),
                    "marca": marca_do_carro(d.get("CarScreenName"), d.get("CarScreenNameShort"),
                                            d.get("CarPath")),
                    "pais": codigo_pais(d.get("FlairName") or d.get("ClubName")),
                }
            except Exception:
                continue
        if pilotos:
            self._pilotos = pilotos
        try:
            self._tipos_pneu = {int(t["TireIndex"]): str(t.get("TireCompoundType") or "")
                                for t in (info.get("DriverTires") or []) if "TireIndex" in t}
        except Exception:
            self._tipos_pneu = {}
        estimativa = self._tempo(info.get("DriverCarEstLapTime"))
        if estimativa:
            self._ref_volta = estimativa
        try:
            maximo = float(info.get("DriverCarFuelMaxLtr") or 0.0)
            fracao = float(info.get("DriverCarMaxFuelPct") or 1.0)
            self._capacidade = maximo * fracao if maximo > 0 else None
        except (TypeError, ValueError):
            self._capacidade = None
        try:
            limite = (self.ir["WeekendInfo"] or {}).get("WeekendOptions", {}).get("IncidentLimit")
            self._limite_inc = int(limite) if str(limite).isdigit() else None
        except Exception:
            self._limite_inc = None
        try:
            oficial = (self.ir["WeekendInfo"] or {}).get("Official")
            self._oficial = None if oficial is None else bool(int(oficial))
        except Exception:
            self._oficial = None
        try:
            winfo = self.ir["WeekendInfo"] or {}
            self._categoria = winfo.get("Category")
            self._subsessao = winfo.get("SubSessionID")
        except Exception:
            self._categoria = self._subsessao = None
        try:
            sessoes = (self.ir["SessionInfo"] or {}).get("Sessions") or []
            numero = int(self._var("SessionNum", 0))
            self._tipo_sessao = (traduzir_sessao(sessoes[numero].get("SessionType"))
                                 if 0 <= numero < len(sessoes) else None)
        except Exception:
            self._tipo_sessao = None

    def _atualizar_pista(self):
        agora = time.time()
        if agora - self._ultima_leitura_pista < 2.0:
            return
        self._ultima_leitura_pista = agora
        info = self.ir["WeekendInfo"]
        if not info:
            return
        self._comprimento = comprimento_pista(info.get("TrackLength"))
        self._nome_pista = str(info.get("TrackDisplayName") or info.get("TrackName") or "")
        try:
            curvas = int(info.get("TrackNumTurns"))
        except (TypeError, ValueError):
            curvas = 0
        if curvas <= 0 and self._comprimento:
            curvas = max(4, round(self._comprimento / 1000.0 * 2.5))   # estimativa: ~2,5 curvas/km
        self._curvas_pista = curvas or None
        chave = f"{info.get('TrackID')}|{info.get('TrackConfigName') or ''}|{info.get('TrackName') or ''}"
        self._chave_pista = chave
        try:
            lista = (self.ir["SplitTimeInfo"] or {}).get("Sectors") or []
            inicios = [float(x["SectorStartPct"]) for x in lista]
        except Exception:
            inicios = []
        if len(inicios) >= 2:
            self.setores.definir_setores(inicios)
        elif not self._aviso_setores:
            self._aviso_setores = True
            registrar_aviso("SplitTimeInfo.Sectors indisponivel: usando 3 setores de tamanho igual.")
        self.mapa.definir_pista(chave)

    def _motivo_volta_suja(self):
        """Por que a volta em andamento NAO deve servir de referencia/recorde (ou None se esta limpa)."""
        try:
            meu = int(self._var("PlayerCarIdx", -1))
            superficie = self._var("PlayerTrackSurface", None)
            if superficie is None:
                superficie = _item(self._var("CarIdxTrackSurface", None), meu, None)
            return nucleo.motivo_volta_suja(
                na_box=bool(self._var("OnPitRoad", False)), superficie=superficie,
                reboque_s=self._var("PlayerCarTowTime", 0.0) or 0.0,
                replay=bool(self._var("IsReplayPlaying", False)))
        except Exception:
            registrar_erro("criterio de volta limpa")
            return None

    def _chave_carro_pista(self):
        """(sessao, pista, carro): a combinacao em que delta e setores sao comparaveis."""
        try:
            self._atualizar_pilotos()
            self._atualizar_pista()
            eu = self._pilotos.get(int(self._var("PlayerCarIdx", -1))) or {}
            return ((self._var("SessionNum", 0), self._var("SessionUniqueID", 0)),
                    self._chave_pista, eu.get("carro_id"))
        except Exception:
            registrar_erro("chave de sessao/pista/carro")
            return None             # sem chave: o delta continua funcionando, so sem a protecao de troca

    def _calcular_delta(self, dados):
        """Delta: usa o calculado pelo overlay (se ja ha volta de referencia); senao o do iRacing."""
        delta_sim = float(self._var("LapDeltaToBestLap", 0.0))
        ok_sim = bool(self._var("LapDeltaToBestLap_OK", False))
        meu = int(self._var("PlayerCarIdx", -1))
        pct = self._var("LapDistPct", None)
        if pct is None:
            pct = _item(self._var("CarIdxLapDistPct", None), meu, None)
        delta_own, ok_own = self.delta_proprio.atualizar(
            pct, dados["tempo_volta"], int(self._var("LapCompleted", -1)),
            bool(self._var("OnPitRoad", False)), dados["ultima_volta"],
            chave=self._chave_carro_pista(), motivo=self._motivo_volta_suja(),
        )
        if ok_own:
            dados["delta"], dados["delta_ok"], dados["delta_fonte"] = delta_own, True, "overlay"
        elif ok_sim:
            dados["delta"], dados["delta_ok"], dados["delta_fonte"] = delta_sim, True, "sim"
        else:
            dados["delta"], dados["delta_ok"], dados["delta_fonte"] = 0.0, False, None
        if not ok_sim and ok_own and not self._aviso_delta:
            self._aviso_delta = True
            registrar_aviso(f"Delta do iRacing indisponivel (LapDeltaToBestLap_OK={ok_sim}, "
                            f"valor={delta_sim}); usando o delta calculado pelo overlay.")

    def _montar_clima(self):
        """Temperaturas, neblina e vento. Vento: direcao de ONDE ele vem (rad, 0 = norte) e km/h."""
        pista = self._var_primeiro(("TrackTempCrew", "TrackTemp"))
        ar = self._var("AirTemp", None)
        neblina = self._var("FogLevel", None)
        direcao = self._var("WindDir", None)
        vento = self._var("WindVel", None)
        chuva = self._var("Precipitation", None)
        if pista is None and ar is None and neblina is None and vento is None and chuva is None:
            return None
        chuva_pct = None
        if chuva is not None:
            chuva_pct = max(0.0, min(100.0, float(chuva) * 100.0 if float(chuva) <= 1.0 else float(chuva)))
            agora = time.monotonic()
            if not self._hist_chuva or agora - self._hist_chuva[-1][0] >= 5.0:
                self._hist_chuva.append((agora, chuva_pct))
                while self._hist_chuva and agora - self._hist_chuva[0][0] > 660.0:
                    self._hist_chuva.popleft()
        molhada = self._var("TrackWetness", None)
        dinamico = None
        try:
            tipo = (self.ir["WeekendInfo"] or {}).get("TrackWeatherType")
            if tipo:
                dinamico = "static" not in str(tipo).lower()
        except Exception:
            pass
        if neblina is not None:
            neblina = float(neblina)
            neblina = neblina * 100.0 if neblina <= 1.0 else neblina    # o SDK informa 0..1
        yaw = self._var("YawNorth", None)       # iRacing: anti-horario a partir do norte -> rumo = -yaw
        return {"rumo": (-float(yaw)) % (2 * math.pi) if yaw is not None else None,
                "vel_carro": float(self._var("Speed", 0.0) or 0.0) * 3.6,
                "chuva": chuva_pct,
                "tendencia_chuva": tendencia_chuva(list(self._hist_chuva), chuva_pct),
                "pista_molhada": int(molhada) if molhada is not None else None,   # 1 seca ... 7 encharcada
                "declarado_molhado": bool(self._var("WeatherDeclaredWet", False)),
                "ceu": int(self._var("Skies", -1)) if self._var("Skies", None) is not None else None,
                "dinamico": dinamico,
                "pista": float(pista) if pista is not None else None,
                "ar": float(ar) if ar is not None else None,
                "neblina": max(0.0, min(100.0, neblina)) if neblina is not None else None,
                "vento_dir": float(direcao) if direcao is not None else None,
                "vento_vel": float(vento) * 3.6 if vento is not None else None}   # km/h

    AVISOS_MOTOR = ((0x01, "Agua"), (0x02, "Comb."), (0x04, "Oleo press."),
                    (0x40, "Oleo temp."), (0x08, "Parado"))

    def _montar_forca_g(self):
        """G lateral e longitudinal (em g), total e pico da sessao; nome e temperatura da pista."""
        lat, lon = self._var("LatAccel", None), self._var("LongAccel", None)
        if lat is None and lon is None:
            return None
        chave = (self._var("SessionNum", 0), self._var("SessionUniqueID", 0))
        if self._sessao_g != chave:
            self._sessao_g, self._pico_g = chave, 0.0
        lat_g, lon_g = float(lat or 0.0) / 9.81, float(lon or 0.0) / 9.81
        if self.estimador_pneus.inverter:
            lat_g = -lat_g
        total = math.hypot(lat_g, lon_g)
        if self._ler_presenca()[0] and not self._var("IsReplayPlaying", False):
            self._pico_g = max(self._pico_g, total)
        self._atualizar_pista()
        temp = self._var_primeiro(("TrackTempCrew", "TrackTemp"))
        return {"lat": lat_g, "lon": lon_g, "total": total, "pico": self._pico_g,
                "pista": self._nome_pista or "", "temp": float(temp) if temp is not None else None}

    # ---- v1.2.0: Luz TC, Retorno a pista, Estrategia de pneus, pedais crus ----
    def _tipo_pneu_de(self, idx, compostos):
        comp = _item(compostos, idx, None)
        if comp is None:
            return None
        try:
            nome = self._tipos_pneu.get(int(comp)) if int(comp) >= 0 else None
        except (TypeError, ValueError):
            return None
        est = estilo_pneu(nome)
        return v12.classe_pneu(est[1] if est else None)

    def _montar_v12(self, dados):
        agora = time.monotonic()
        chave = (self._var("SessionNum", 0), self._var("SessionUniqueID", 0))
        if self._v12_sessao != chave:
            if self._v12_sessao is not None:
                registrar_info("v1.2: nova sessao, aprendizado da Luz TC e historicos reiniciados")
            self._v12_sessao = chave
            self.v12_tc.resetar()
            self.v12_retorno.resetar()
            self.v12_pneus.resetar()
            self.v12_ritmo.resetar()
        vivo = dados["no_carro"] and not dados["replay"]
        # pedais crus (sem a calibracao do carro)
        try:
            ac, fr, em = (self._var("ThrottleRaw", None), self._var("BrakeRaw", None), self._var("ClutchRaw", None))
            if ac is not None or fr is not None:
                dados["pedais_cru"] = {"acelerador": float(ac) if ac is not None else None,
                                       "freio": float(fr) if fr is not None else None,
                                       "embreagem": (1.0 - float(em)) if em is not None else None}
        except Exception:
            registrar_erro("pedais crus")
        # Luz TC (estimativa)
        try:
            if vivo:
                limitador = bool(int(self._var("EngineWarnings", 0) or 0) & 0x10)
                dados["luz_tc"] = self.v12_tc.atualizar(
                    agora, dados["marcha"], dados["rpm"], dados["velocidade"] / 3.6, dados["acelerador"],
                    dados["freio"], dados["embreagem"], self._rpm_max, limitador)
        except Exception:
            registrar_erro("luz TC")
        # Retorno a pista
        try:
            if dados["no_carro"] or dados["velocidade"] > 0:
                self._atualizar_pilotos()
                self._atualizar_pista()
                dados["retorno"] = self.v12_retorno.atualizar(
                    agora, int(self._var("PlayerCarIdx", -1)), self._var("CarIdxLapDistPct", None),
                    self._var("CarIdxTrackSurface", None), self._var("CarIdxOnPitRoad", None), self._comprimento,
                    dados["velocidade"] / 3.6, self._ref_volta, validos=set(self._pilotos))
        except Exception:
            registrar_erro("retorno a pista")
        # Estrategia de pneus (2 vezes por segundo)
        try:
            dados["estrategia"] = self._cacheado("estrategia", 0.5, lambda: self._montar_estrategia(dados))
        except Exception:
            registrar_erro("estrategia de pneus")

    def _montar_estrategia(self, dados):
        agora = time.monotonic()
        self._atualizar_pilotos()
        meu = int(self._var("PlayerCarIdx", -1))
        clima = dados.get("clima") or {}
        compostos = self._var("CarIdxTireCompound", None)
        meu_tipo = self._tipo_pneu_de(meu, compostos)
        if meu_tipo is None:
            pc = self._var("PlayerTireCompound", None)
            if pc is not None:
                comp_lista = {meu: pc}
                meu_tipo = self._tipo_pneu_de(meu, comp_lista)
        tem_chuva = any(v12.classe_pneu((estilo_pneu(n) or (None, None))[1]) == "chuva"
                        for n in self._tipos_pneu.values())
        # pneu pedido nos boxes (so se houver troca de pneus marcada)
        pedido = None
        flags = self._var("PitSvFlags", None)
        if flags is not None and int(flags) & 0x0F:
            pc = self._var("PitSvTireCompound", None)
            if pc is not None:
                pedido = self._tipo_pneu_de(0, {0: pc})
        # rivais da sua classe
        eu = self._pilotos.get(meu) or {}
        classe = eu.get("classe_id")
        idxs = [i for i, pl in self._pilotos.items() if pl.get("classe_id") == classe] if classe is not None else [meu]
        completadas = self._var("CarIdxLapCompleted", None)
        ultimas = self._var("CarIdxLastLapTime", None)
        no_pit = self._var("CarIdxOnPitRoad", None)
        outros = {"seco": 0, "chuva": 0}
        for i in idxs:
            tipo = self._tipo_pneu_de(i, compostos)
            if i != meu and tipo in outros:
                outros[tipo] += 1
            self.v12_ritmo.atualizar(agora, i, _item(completadas, i, None), _item(ultimas, i, None), tipo,
                                     bool(_item(no_pit, i, False)))
        outro = "chuva" if meu_tipo == "seco" else "seco"
        vant, _n = self.v12_ritmo.vantagem(agora, meu_tipo, idxs)
        estado = self._var("SessionState", None)
        tipo_sessao = self._tipo_sessao
        pre = ((tipo_sessao == "CORRIDA" and estado is not None and int(estado) <= 3)
               or (tipo_sessao == "QUALIFICACAO" and (bool(self._var("IsInGarage", False))
                                                      or bool(self._var("OnPitRoad", False)))))
        res = self.v12_pneus.atualizar(
            agora, clima.get("pista_molhada"), clima.get("chuva"), meu_tipo, tem_chuva, pedido, pre, vant,
            outros.get(outro, 0), outros.get(meu_tipo, 0) + 1 if meu_tipo in outros else 0)
        nome = None
        res["meu_pneu_nome"] = nome
        return res

    def zerar_pico_g(self):
        self._pico_g = 0.0

    def _montar_danos(self):
        """Danos: tempo de reparo (do iRacing), avisos do motor, incidentes e impactos detectados."""
        agora = time.monotonic()
        chave = (self._var("SessionNum", 0), self._var("SessionUniqueID", 0))
        if self._sessao_danos != chave:
            if self._sessao_danos is not None:
                self.impactos.resetar()
            self._sessao_danos = chave
        reparo = float(self._var("PitRepairLeft", 0.0) or 0.0)
        opcional = float(self._var("PitOptRepairLeft", 0.0) or 0.0)
        incidentes = self._var("PlayerCarMyIncidentCount", None)
        incidentes = int(incidentes) if incidentes is not None else None
        ativo = bool(self._var("IsOnTrack", True)) and not bool(self._var("IsReplayPlaying", False))
        self.impactos.inverter = self.estimador_pneus.inverter
        self.impactos.atualizar(
            agora, float(self._var("LongAccel", 0.0) or 0.0), float(self._var("LatAccel", 0.0) or 0.0),
            incidentes, ativo, reparo)
        bits = int(self._var("EngineWarnings", 0) or 0)
        avisos = [nome for bit, nome in self.AVISOS_MOTOR if bits & bit]
        reboque = float(self._var("PlayerCarTowTime", 0.0) or 0.0)
        res = self.impactos.exibicao(agora)
        res.update({"reparo": reparo, "reparo_opc": opcional, "avisos": avisos, "incidentes": incidentes,
                    "limite": self._limite_inc, "reboque": reboque,
                    "rapidos": int(self._var("FastRepairAvailable", 0) or 0)})
        return res

    def limpar_impactos(self):
        self.impactos.limpar_marcas()

    def _ler_presenca(self):
        """(no_carro, replay): voce esta dirigindo no mundo do jogo? Garagem, menus e replay = nao."""
        replay = bool(self._var("IsReplayPlaying", False))
        na_pista = self._var("IsOnTrack", None)
        if na_pista is None:                           # SDK sem IsOnTrack: usa a superficie da pista
            meu = self._var("PlayerCarIdx", None)
            sup = _item(self._var("CarIdxTrackSurface", None), int(meu), None) if meu is not None else None
            na_pista = True if sup is None else int(sup) != -1
        no_carro = bool(na_pista) and not bool(self._var("IsInGarage", False))
        return no_carro, replay

    def _montar_pneus(self):
        """Pneus: leitura real (boxes) + estimativa ao vivo de desgaste e temperatura."""
        est = self.estimador_pneus
        agora = time.monotonic()
        dt = 0.0 if self._t_pneus is None else agora - self._t_pneus
        self._t_pneus = agora
        self._atualizar_pilotos()
        meu = int(self._var("PlayerCarIdx", -1))
        eu = self._pilotos.get(meu) or {}
        est.definir_carro(eu.get("carro_id"))
        chave = (self._var("SessionNum", 0), self._var("SessionUniqueID", 0))
        if self._sessao_pneus != chave:
            if self._sessao_pneus is not None:
                est.resetar_sessao()
                # medicoes da sessao anterior nao valem para a nova (pneus novos, outro carro...)
                self._vida_ultima.clear(); self._temp_ult.clear(); self._temp_mudou.clear()
                self._ult_temp.clear(); self._vida_info.clear()
                registrar_calculo("pneus: medicoes reais descartadas", motivo="troca de sessao")
            self._sessao_pneus = chave

        temp, vida, n_carc, n_sup, leituras = {}, {}, 0, 0, {}
        vel = float(self._var("Speed", 0.0))
        na_box_agora = bool(self._var("OnPitRoad", False))
        local = "boxes" if (na_box_agora or vel < 1.0) else "pista"
        volta_agora = int(self._var("LapCompleted", -1))
        for c in CANTOS_PNEUS:
            carcaca = _trio_valido([self._var(f"{c}temp{z}", None) for z in ("CL", "CM", "CR")], 1.0)
            superficie = _trio_valido([self._var(f"{c}temp{z}", None) for z in ("L", "M", "R")], 1.0)
            real = carcaca or superficie
            if carcaca:
                n_carc += 1
            elif superficie:
                n_sup += 1
            if real != self._temp_ult.get(c):
                self._temp_ult[c], self._temp_mudou[c] = real, agora
                if real:                              # nova leitura real: guarda quando, onde e em que volta
                    self._ult_temp[c] = {"temp": tuple(real), "mono": agora, "hora": time.strftime("%H:%M"),
                                         "volta": volta_agora, "local": local, "tipo": "carcaca" if carcaca else "superficie"}
            viva = bool(real) and vel > 5.0 and agora - self._temp_mudou.get(c, 0.0) < 3.0
            temp[c] = real if (viva or (real and vel < 1.0)) else None
            if real and (viva or vel < 1.0):
                est.definir_temp_real(c, sum(real) / 3.0)
            atual = _trio_valido([self._var(f"{c}wear{z}", None) for z in ("L", "M", "R")], 0.0)
            if atual:
                if atual != self._vida_ultima.get(c):
                    self._vida_info[c] = {"mono": agora, "hora": time.strftime("%H:%M"),
                                          "volta": volta_agora, "local": local}
                self._vida_ultima[c] = atual
            leituras[c] = atual
            vida[c] = self._vida_ultima.get(c)
        est.registrar_leituras(leituras)

        na_box = bool(self._var("OnPitRoad", False))
        na_pista = self._var("IsOnTrack", None)
        na_pista = (vel > 3.0) if na_pista is None else bool(na_pista)
        replay = bool(self._var("IsReplayPlaying", False))
        est.atualizar(dt, na_pista and not na_box and not replay, vel,
                      float(self._var("LatAccel", 0.0) or 0.0), float(self._var("LongAccel", 0.0) or 0.0),
                      self._var("TrackTemp", None))
        if not replay:
            est.fim_de_volta(int(self._var("LapCompleted", -1)), na_box)

        if not self._diag_pneus and vel > 15.0:
            self._diag_pneus = True
            lf = {k: self._var(f"LF{k}", None) for k in
                  ("tempCL", "tempCM", "tempCR", "tempL", "tempM", "tempR", "wearL", "wearM", "wearR")}
            registrar_aviso(f"Pneus (diagnostico, LF): {lf} | LatAccel={self._var('LatAccel', None)} "
                            f"LongAccel={self._var('LongAccel', None)}")
        ultima = {}
        for c in CANTOS_PNEUS:
            t_u, v_u = self._ult_temp.get(c), self._vida_info.get(c)
            ultima[c] = {
                "temp": t_u["temp"] if t_u else None,
                "idade": (agora - t_u["mono"]) if t_u else None,
                "hora": t_u["hora"] if t_u else None, "volta": t_u["volta"] if t_u else None,
                "local": t_u["local"] if t_u else None,
                "ao_vivo": bool(temp.get(c)),
                "vida_idade": (agora - v_u["mono"]) if v_u else None,
                "vida_hora": v_u["hora"] if v_u else None, "vida_local": v_u["local"] if v_u else None,
            }
        return {"temp": temp, "vida": vida, "ultima": ultima,
                "fonte": "carcaca" if n_carc >= n_sup and n_carc else ("superficie" if n_sup else None),
                "est": est.resumo()}

    def _montar_painel_combustivel(self, dados, nivel):
        calc = dados.get("calc_combustivel") or {}
        capacidade = self._capacidade
        if not capacidade:
            fracao = self._var("FuelLevelPct", None)
            if fracao and fracao > 0.05 and nivel > 0:
                capacidade = nivel / float(fracao)
        registros = list(self.consumo.registros)
        usos = [u for _, u in registros]
        c_med = dados.get("consumo_volta")
        pct = self._var("LapDistPct", None)
        restante = self._var("SessionTimeRemain", None)
        return calcular_painel_combustivel(
            nivel, capacidade, c_med, max(usos) if usos else c_med, min(usos) if usos else c_med,
            calc.get("voltas_fim"), max(1, int(dados.get("volta") or 1)),
            float(pct) if pct is not None else None, self.margem_combustivel, calc.get("ritmo"),
            float(restante) if restante is not None else None, registros)

    def _montar_calc_combustivel(self, dados, nivel, na_box):
        self._atualizar_pilotos()
        meu = int(self._var("PlayerCarIdx", -1))
        self.ritmo.atualizar(int(self._var("LapCompleted", -1)), dados["ultima_volta"], na_box)
        pct = self._var("LapDistPct", None)
        if pct is None:
            pct = _item(self._var("CarIdxLapDistPct", None), meu, None)
        voltas = self._var("SessionLapsRemainEx", None)
        restante = self._var("SessionTimeRemain", None)
        ritmo = self.ritmo.estimativa or dados["melhor_volta"] or self._ref_volta
        capacidade = self._capacidade
        if not capacidade:
            fracao = self._var("FuelLevelPct", None)
            if fracao and fracao > 0.05 and nivel > 0:
                capacidade = nivel / float(fracao)
        return calcular_combustivel(
            nivel, dados["consumo_volta"],
            int(voltas) if voltas is not None else None,
            float(restante) if restante is not None else None,
            ritmo, float(pct) if pct is not None else None,
            self.margem_combustivel, capacidade,
        )

    def refazer_mapa(self):
        self.mapa.refazer()

    def _montar_mapa(self):
        self._atualizar_pilotos()
        self._atualizar_pista()
        meu = int(self._var("PlayerCarIdx", -1))
        pcts = self._var("CarIdxLapDistPct", None)
        superficie = self._var("CarIdxTrackSurface", None)
        pct_eu = _item(pcts, meu, None)
        na_pista = (_item(superficie, meu, -1) == 3) and not bool(self._var("OnPitRoad", False))
        self.mapa.atualizar(
            pct_eu, self._var("Lat", None), self._var("Lon", None), na_pista,
            float(self._var("Speed", 0.0)), self._var("YawNorth", None),
        )
        dados = self.mapa.exibicao()
        dados["carros"] = montar_mapa_carros(self._pilotos, meu, pcts, superficie)
        return dados

    def _montar_radar(self):
        self._atualizar_pilotos()
        self._atualizar_pista()
        meu = int(self._var("PlayerCarIdx", -1))
        return montar_radar(
            self._pilotos, meu,
            self._var("CarIdxLapDistPct", None),
            self._var("CarIdxTrackSurface", None),
            self._var("CarIdxOnPitRoad", None),
            self._var("CarLeftRight", None),
            self._comprimento,
            memoria=self._memoria_radar,
        )

    def _montar_projecao(self):
        """Projecao de iRating e SR (estimativas) para a sessao atual."""
        self._atualizar_pilotos()
        self._atualizar_pista()
        meu = int(self._var("PlayerCarIdx", -1))
        eu = self._pilotos.get(meu)
        if not eu:
            return None
        tipo = self._tipo_sessao
        chave = (self._var("SessionNum", 0), self._var("SessionUniqueID", 0))
        if self._base_sessao.get("chave") != chave:
            # fotografa SR e iRating no inicio da sessao (o iRacing so os atualiza depois do fim)
            self._base_sessao = {"chave": chave, "sr": eu.get("sr"), "letra": eu.get("lic_letra"),
                                 "ir": eu.get("irating")}
            registrar_calculo("projecao: base da sessao", sessao=chave, irating=eu.get("irating"),
                              sr=eu.get("sr"), licenca=eu.get("lic_letra"), tipo=tipo)
            # base_incerta: ha uma corrida anterior (mesma categoria/usuario) cujo resultado oficial ainda
            # nao apareceu; o iRating/SR de agora podem nao incluir essa corrida
            self._verificar_oficial(eu)
            self._base_sessao["incerta"] = bool(self._aguardando_oficial)
        base = self._base_sessao
        superficie = self._var("CarIdxTrackSurface", None)
        pct = self._var("LapDistPct", None)
        if pct is None:
            pct = _item(self._var("CarIdxLapDistPct", None), meu, None)
        na_pista = (_item(superficie, meu, -1) == 3) and not bool(self._var("OnPitRoad", False))
        estado = self._var("SessionState", None)
        contando = estado is None or int(estado) >= 4        # so depois da largada
        curvas = self.contador_curvas.atualizar(chave, pct, na_pista and contando, self._curvas_pista)
        incidentes = int(self._var("PlayerCarMyIncidentCount", 0))
        posc = self._var("CarIdxClassPosition", None)

        ir = projetar_irating(self._pilotos, meu, posc) if tipo == "CORRIDA" else None
        sr = estimar_sr(base.get("sr"), base.get("letra"), curvas, incidentes,
                        SR_PESO_SESSAO.get(tipo or "", 0.0))
        res = montar_projecao(tipo, self._oficial, ir, sr, curvas, incidentes)
        if estado is not None and int(estado) >= 5:
            self._registrar_historico(chave, res, eu, base)
        return res

    def _montar_setores(self, dados):
        self._atualizar_pilotos()
        self._atualizar_pista()
        meu = int(self._var("PlayerCarIdx", -1))
        eu = self._pilotos.get(meu)
        if not eu or not self._chave_pista or not eu.get("carro_id"):
            return None
        chave = f"{self._chave_pista}|{eu['carro_id']}"
        self._chave_recorde = chave
        pct = self._var("LapDistPct", None)
        if pct is None:
            pct = _item(self._var("CarIdxLapDistPct", None), meu, None)
        self.setores.atualizar(
            pct, dados["tempo_volta"], int(self._var("LapCompleted", -1)),
            bool(self._var("OnPitRoad", False)), dados["ultima_volta"], chave, self.recordes,
            motivo=self._motivo_volta_suja(),
            sessao=(self._var("SessionNum", 0), self._var("SessionUniqueID", 0)))
        exib = self.setores.exibicao(self.recordes.obter(chave))
        exib["pista"], exib["carro"] = self._nome_pista, eu.get("carro") or ""
        return exib

    def zerar_referencia(self):
        """Apaga o recorde da pista + carro atuais (e recomeca a medir)."""
        if self._chave_recorde:
            self.recordes.zerar(self._chave_recorde)
        self.setores.resetar()

    def _identidade_sessao(self, eu):
        """Identidade da corrida de agora (SubSessionID + categoria + usuario) para associar a projecao."""
        return nucleo.identidade_sessao(self._subsessao, self._categoria, (eu or {}).get("usuario_id"),
                                        self._oficial)

    # ---- ciclo de vida das projecoes (Fase 20.2.1): pendente -> provisoria -> confirmada | expirada ----
    def _ler_projecoes(self):
        """Le projecao_pendente.json (qualquer versao) e devolve a lista de registros; avisa o que foi migrado."""
        if not ARQ_PENDENTE.exists():
            return []
        try:
            conteudo = json.loads(ARQ_PENDENTE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            registrar_aviso("projecao_pendente.json ilegivel: ignorado (preservado como esta).")
            return []
        lista, avisos = nucleo.migrar_arquivo(conteudo, time.time())
        for a in avisos:
            registrar_aviso(a)
        if avisos:                       # migrou ou descartou: grava no formato atual (avisa uma unica vez)
            try:
                self._gravar_projecoes(lista)
            except OSError:
                registrar_erro("migracao de projecao_pendente.json")
        return lista

    def _gravar_projecoes(self, lista):
        """Grava a lista (podada) de forma atomica: um desligamento no meio nao corrompe o arquivo."""
        lista = nucleo.podar(lista, time.time())
        if nucleo.excede_capacidade(lista):          # so projecoes ativas: nada e apagado, mas o excesso e avisado
            registrar_aviso(f"projecao_pendente.json: {len(lista)} projecoes ativas (limite de referencia "
                            f"{nucleo.MAX_REGISTROS}); nenhuma foi removida. Verifique se ha corridas sem resultado.")
        tmp = ARQ_PENDENTE.with_name(ARQ_PENDENTE.name + ".tmp")
        tmp.write_text(json.dumps({"versao": 3, "projecoes": lista}), encoding="utf-8")
        os.replace(tmp, ARQ_PENDENTE)

    _CAB_COMPARACAO = ("data;corrida_id;categoria;pista;status;ir_projetado;ir_oficial;ir_erro;"
                       "sr_projetado;sr_oficial;sr_erro")

    def _registrar_comparacao(self, reg, res):
        """Grava a comparacao em comparacao_oficial.csv: UMA linha por corrida_id (a confirmada SUBSTITUI a
        provisoria; nunca duplica)."""
        self._preparar_csv(ARQ_COMPARACAO, self._CAB_COMPARACAO)
        linha = ";".join(str(x) for x in (
            time.strftime("%Y-%m-%d %H:%M"), reg.get("id", ""), reg.get("categoria", ""),
            str(reg.get("pista", "")).replace(";", ","), res.get("status", nucleo.STATUS_PROVISORIA),
            res.get("ir_proj", ""), res.get("ir_real", ""), res.get("ir_erro", ""),
            res.get("sr_proj", ""), res.get("sr_real", ""), res.get("sr_erro", "")))
        with ARQ_COMPARACAO.open("r", encoding="utf-8-sig", newline="") as f:
            linhas = f.read().splitlines()
        id_ = str(reg.get("id", ""))
        cab, corpo = linhas[0], [l for l in linhas[1:] if l.strip()]
        corpo = [l for l in corpo if l.split(";")[1:2] != [id_]]
        corpo.append(linha)
        tmp = ARQ_COMPARACAO.with_name(ARQ_COMPARACAO.name + ".tmp")
        with tmp.open("w", encoding="utf-8-sig", newline="") as f:
            f.write("\n".join([cab] + corpo) + "\n")
        os.replace(tmp, ARQ_COMPARACAO)

    def _aplicar_evento(self, reg, evento, res):
        """Efeitos de uma transicao: log e CSV."""
        if evento in ("provisoria", "confirmada") and res:
            confirmada = evento == "confirmada"
            extra = {}
            if res.get("variacao_nula"):
                extra["variacao"] = "ZERO confirmada pelo resultado oficial"
            if res.get("divergencia_provisoria"):
                extra["divergencia_provisoria"] = res["divergencia_provisoria"]
            registrar_calculo("projecao x OFICIAL", pista=reg.get("pista", ""), corrida=reg.get("id"),
                              categoria=reg.get("categoria"),
                              aviso="confirmada pelo resultado oficial (SubSessionID)" if confirmada
                              else "PROVISORIA: sem confirmacao pelo SubSessionID",
                              **{k: v for k, v in res.items() if k not in ("provisoria_anterior",
                                                                            "divergencia_provisoria")}, **extra)
            self._registrar_comparacao(reg, res)
        elif evento == "expirada":
            registrar_aviso(f"projecao {reg.get('id')} expirada ({reg.get('motivo_expirada')}).")

    def _verificar_oficial(self, eu):
        """No inicio de uma sessao: percorre as projecoes guardadas e compara com o iRating/SR visto agora.

        Uma projecao so e comparada se puder ser ASSOCIADA com seguranca (categoria e usuario iguais, outra
        sessao, base valida). A comparacao dessa leitura e sempre PROVISORIA e a projecao e MANTIDA (nao e apagada)
        para a confirmacao posterior por `confirmar_resultado_oficial`. Valores iguais aos do inicio nao sao
        resultado oficial: "sem_atualizacao_numerica". Define `self._aguardando_oficial` (base incerta).
        Devolve o motivo da projecao mais recente (nucleo.MOTIVOS_TEXTO).
        """
        self._aguardando_oficial = False
        try:
            lista = self._ler_projecoes()
            if not lista:
                return "sem_pendente"
            atual = self._identidade_sessao(eu)
            agora = time.time()
            motivo_final, mudou, novas = "sem_pendente", False, []
            for reg in lista:
                novo, evento, res, motivo = nucleo.avaliar_registro(reg, atual, eu.get("irating"), eu.get("sr"), agora)
                if motivo not in ("ja_confirmada", "ja_expirada", "ja_provisoria", "ok"):
                    registrar_calculo("projecao x OFICIAL: NAO comparada", motivo=motivo,
                                      detalhe=nucleo.MOTIVOS_TEXTO.get(motivo, ""), pendente=reg.get("id"),
                                      atual=atual.get("id"), cat_pendente=reg.get("categoria"),
                                      cat_atual=atual.get("categoria"))
                if motivo == "sem_atualizacao_numerica":
                    self._aguardando_oficial = True
                if novo != reg:
                    mudou = True
                if evento:
                    self._aplicar_evento(novo, evento, res)
                novas.append(novo)
                motivo_final = motivo
            if mudou:
                self._gravar_projecoes(novas)
            return motivo_final
        except Exception:
            registrar_erro("comparacao com o resultado oficial")
            return "erro"

    def confirmar_resultado_oficial(self, resultado_oficial):
        """Ponto de extensao (NAO ligado a nenhuma fonte nesta fase; reservado para a Data API do iRacing).

        `resultado_oficial` = {"subsession_id","cust_id","ir_antigo","ir_novo","sr_antigo","sr_novo"}.
        Confirma a projecao da MESMA corrida e usuario (pendente ou provisoria); variacao zero e resultado valido.
        Idempotente. Devolve o motivo ("ok_confirmada", "resultado_divergente", "ja_confirmada", ...).
        """
        try:
            lista = self._ler_projecoes()
            ro = resultado_oficial or {}
            alvo = [i for i, r in enumerate(lista) if str(r.get("id")) == str(ro.get("subsession_id"))]
            if not alvo:
                registrar_calculo("resultado oficial: sem projecao desta corrida", corrida=ro.get("subsession_id"))
                return "resultado_divergente"
            i = alvo[0]
            novo, evento, res, motivo = nucleo.aplicar_resultado_oficial(lista[i], ro, time.time())
            if evento:
                lista[i] = novo
                self._aplicar_evento(novo, evento, res)
                self._gravar_projecoes(lista)
            else:
                registrar_calculo("resultado oficial: NAO aplicado", motivo=motivo,
                                  detalhe=nucleo.MOTIVOS_TEXTO.get(motivo, ""), corrida=ro.get("subsession_id"))
            return motivo
        except Exception:
            registrar_erro("confirmacao pelo resultado oficial")
            return "erro"

    @staticmethod
    def _preparar_csv(caminho, cabecalho):
        """Cria o CSV com o cabecalho atual; se existir um de formato antigo, preserva-o renomeado."""
        if caminho.exists():
            try:
                with caminho.open("r", encoding="utf-8-sig") as f:
                    primeira = f.readline().strip()
            except OSError:
                primeira = cabecalho
            if primeira == cabecalho:
                return
            destino = caminho.with_name(f"{caminho.stem}_formato_antigo{caminho.suffix}")
            k = 1
            while destino.exists():
                k += 1
                destino = caminho.with_name(f"{caminho.stem}_formato_antigo{k}{caminho.suffix}")
            caminho.rename(destino)
            registrar_aviso(f"{caminho.name}: formato antigo preservado em {destino.name}.")
        with caminho.open("w", encoding="utf-8-sig", newline="") as f:
            f.write(cabecalho + "\n")

    def _registrar_historico(self, chave, res, eu, base):
        """No fim de cada corrida, grava a projecao em historico_projecoes.csv (uma linha por corrida)."""
        if res["tipo"] != "CORRIDA" or self._sessao_registrada == chave:
            return
        self._sessao_registrada = chave
        ir, sr = res.get("ir") or {}, res.get("sr") or {}
        campos = [
            time.strftime("%Y-%m-%d %H:%M"), self._nome_pista, eu.get("marca") or "",
            eu.get("classe_nome") or "", base.get("letra") or "",
            f"{base['sr']:.2f}" if base.get("sr") is not None else "",
            f"{sr['novo']:.2f}" if sr else "",
            base.get("ir") or "", ir.get("novo", ""), ir.get("pos", ""), ir.get("n", ""),
            f"{res['curvas']:.0f}", res["inc"],
            {True: "sim", False: "nao", None: "?"}[res.get("oficial")],
        ]
        try:                              # guarda a projecao para comparar com o resultado OFICIAL depois
            ident = self._identidade_sessao(eu)
            registrar_calculo("projecao: final da corrida (PROJETADA, nao oficial)", pista=self._nome_pista,
                              ir_delta=ir.get("delta", "--"), sr_delta=sr.get("delta", "--"),
                              posicao=ir.get("pos", "--"), curvas=res.get("curvas"), incidentes=res.get("inc"),
                              corrida=ident.get("id"), categoria=ident.get("categoria"))
            if not ident["forte"]:
                # sem SubSessionID/categoria/usuario/oficial nao ha como associar ao resultado: nao guarda projecao.
                # As projecoes ja guardadas (outras corridas) continuam intactas.
                registrar_aviso("projecao sem identificacao segura da corrida (offline/nao oficial/"
                                f"categoria ou usuario desconhecido): nao sera comparada. {ident}")
            else:
                agora = time.time()
                novo = nucleo.novo_registro(ident, self._nome_pista, base.get("ir"), ir.get("delta"),
                                            base.get("sr"), sr.get("delta"), bool(base.get("incerta")), agora)
                lista = [r for r in self._ler_projecoes() if str(r.get("id")) != str(ident["id"])]
                lista = nucleo.sobrepor_pendentes(lista, novo, agora)
                lista.append(novo)
                self._gravar_projecoes(lista)
        except Exception:
            registrar_erro("projecao pendente")
        try:
            novo = not ARQ_HISTORICO.exists()
            with ARQ_HISTORICO.open("a", encoding="utf-8-sig", newline="") as arq:
                if novo:
                    arq.write("data;pista;carro;classe;licenca;sr_inicial;sr_projetado;irating_inicial;"
                              "irating_projetado;posicao_classe;pilotos_classe;curvas;incidentes;oficial\n")
                arq.write(";".join(str(c).replace(";", ",") for c in campos) + "\n")
        except Exception:
            registrar_erro("historico de projecoes")

    def _montar_classificacao(self):
        self._atualizar_pilotos()
        meu = int(self._var("PlayerCarIdx", -1))
        classif = montar_classificacao(
            self._pilotos, meu,
            self._var("CarIdxClassPosition", None),
            self._var("CarIdxLastLapTime", None),
            self._var("CarIdxBestLapTime", None),
            self._var("CarIdxOnPitRoad", None),
        )
        if classif is not None:
            classif["tipo_sessao"] = self._tipo_sessao
            classif["volta"] = max(0, int(self._var("Lap", 0)))
        return classif

    def _anexar_pneus(self, rel):
        """Acrescenta a cada linha do relativo o tipo de pneu e as voltas desde a ultima parada."""
        completadas = self._var("CarIdxLapCompleted", None)
        if completadas is None:
            lap = self._var("CarIdxLap", None)
            completadas = [max(0, (v or 0) - 1) for v in lap] if lap is not None else None
        compostos = self._var("CarIdxTireCompound", None)
        chave = (self._var("SessionNum", 0), self._var("SessionUniqueID", 0))
        self.idade_pneus.atualizar(chave, completadas, self._var("CarIdxOnPitRoad", None),
                                   self._var("CarIdxTrackSurface", None), compostos)
        for linha in list(rel["frente"]) + [rel["eu"]] + list(rel["atras"]):
            idx = linha.get("idx")
            comp = _item(compostos, idx, None)
            nome = self._tipos_pneu.get(int(comp)) if comp is not None and int(comp) >= 0 else None
            est = estilo_pneu(nome)
            voltas, confiavel = self.idade_pneus.voltas(idx, completadas)
            linha["pneu"] = {"cor": est[0], "nome": est[1]} if est else None
            linha["voltas_pneu"] = voltas
            linha["voltas_pneu_confiavel"] = confiavel

    def _montar_relativo(self):
        self._atualizar_pilotos()
        meu = int(self._var("PlayerCarIdx", -1))
        rel = montar_relativo(
            self._pilotos, meu,
            self._var("CarIdxLapDistPct", None),
            self._var("CarIdxLap", None),
            self._var("CarIdxEstTime", None),
            self._var("CarIdxTrackSurface", None),
            self._var("CarIdxOnPitRoad", None),
            self._var("CarIdxClassPosition", None),
            self._ref_volta,
        )
        if rel is None:
            return None
        try:
            self._anexar_pneus(rel)
        except Exception:
            registrar_erro("pneus no relativo")
        classe = self._pilotos[meu].get("classe_id")
        temp = self._var("TrackTemp", None)
        restante = self._var("SessionTimeRemain", None)
        voltas_rest = self._var("SessionLapsRemainEx", None)
        rel.update({
            "pista_temp": float(temp) if temp is not None else None,
            "sof": calcular_sof([p["irating"] for p in self._pilotos.values()
                                 if p["classe_id"] == classe]),
            "inc": int(self._var("PlayerCarMyIncidentCount", 0)),
            "inc_limite": self._limite_inc,
            "volta": max(0, int(self._var("Lap", 0))),
            "tempo_restante": (float(restante)
                               if restante is not None and 0 <= float(restante) < 86400 else None),
            "voltas_restantes": (int(voltas_rest)
                                 if voltas_rest is not None and 0 <= int(voltas_rest) < 30000 else None),
        })
        return rel

    def _cacheado(self, chave, intervalo, funcao):
        """Roda `funcao` no maximo a cada `intervalo` s e devolve o ultimo resultado nas demais chamadas."""
        if self._limitador.deve(chave, intervalo, time.monotonic()) or chave not in self._cache_blocos:
            self._cache_blocos[chave] = funcao()
        return self._cache_blocos[chave]

    # variaveis do SDK que o overlay usa; as ausentes vao para o log (nem todo carro/serie as informa)
    VARIAVEIS_ESPERADAS = (
        "Speed", "Gear", "RPM", "Throttle", "Brake", "SteeringWheelAngle", "LapDistPct", "Lap", "LapCompleted",
        "LapCurrentLapTime", "LapLastLapTime", "LapBestLapTime", "LapDeltaToBestLap", "LapDeltaToBestLap_OK",
        "FuelLevel", "OnPitRoad", "IsOnTrack", "PlayerTrackSurface", "PlayerCarTowTime", "PlayerCarIdx",
        "CarIdxLapDistPct", "CarIdxTrackSurface", "CarIdxOnPitRoad", "CarIdxClassPosition", "CarIdxLap",
        "CarIdxLapCompleted", "CarIdxTireCompound", "CarLeftRight", "LatAccel", "LongAccel",
        "TrackTemp", "AirTemp", "WindDir", "WindVel", "Precipitation", "PitRepairLeft", "EngineWarnings",
        "LFtempCL", "LFwearL", "dcBrakeBias", "dcABS", "dcTractionControl",
        "BrakeABSactive", "ThrottleRaw", "BrakeRaw", "ClutchRaw", "TrackWetness", "CarIdxLastLapTime",
        "PitSvFlags", "PitSvTireCompound",
    )

    def _relatorio_variaveis(self):
        """Uma vez por conexao: registra no log quais variaveis esperadas o SDK NAO esta entregando."""
        def existe(nome):
            return self.ir[nome] is not None
        ausentes = nucleo.variaveis_ausentes(existe, self.VARIAVEIS_ESPERADAS)
        if ausentes != self._ultima_ausencia:
            self._ultima_ausencia = ausentes
            registrar_calculo("sdk: variaveis indisponiveis agora",
                              total=len(ausentes), nomes=", ".join(ausentes) if ausentes else "nenhuma",
                              observacao="normal fora da pista/garagem; confirmar dentro do carro")

    def ler(self):
        if self.demo:
            return self._demo()
        t0 = time.perf_counter()
        try:
            return self._ler_real()
        finally:
            DESEMPENHO.medir("ciclo", (time.perf_counter() - t0) * 1000.0)
            aviso = DESEMPENHO.alerta(time.monotonic())
            if aviso:
                registrar_aviso(aviso)

    def _ler_real(self):

        ir = self.ir
        dados = self._vazio()

        # Gerencia a conexao com o iRacing
        if self.conectado and not (ir.is_initialized and ir.is_connected):
            self.conectado = False
            ir.shutdown()
        elif not self.conectado:
            agora = time.time()
            if agora - self._ultima_tentativa >= 1.0:
                self._ultima_tentativa = agora
                if ir.startup() and ir.is_initialized and ir.is_connected:
                    self.conectado = True
                    self._ultima_ausencia = None
                    self._relatorio_na_pista = False
                    registrar_info("conectado ao iRacing")

        if not self.conectado:
            return dados

        ir.freeze_var_buffer_latest()
        try:
            self._atualizar_rpm_max()
            dados["conectado"] = True
            if self._ultima_ausencia is None and self._var("Speed", None) is not None:
                self._relatorio_variaveis()
            dados["no_carro"], dados["replay"] = self._ler_presenca()
            dados["tipo_sessao"] = self._tipo_sessao
            if dados["no_carro"] and not self._relatorio_na_pista:
                self._relatorio_na_pista = True        # repete o relatorio ja com voce DENTRO do carro (mais fiel)
                self._relatorio_variaveis()
            try:
                dados["forca_g"] = self._montar_forca_g()
            except Exception:
                registrar_erro("forca G")
                dados["forca_g"] = None
            try:
                dados["danos"] = self._montar_danos()
            except Exception:
                registrar_erro("danos")
                dados["danos"] = None
            try:
                dados["clima"] = self._cacheado("clima", 1.0, self._montar_clima)
            except Exception:
                registrar_erro("clima")
                dados["clima"] = None
            dados["marcha"] = int(self._var("Gear", 0))
            dados["velocidade"] = float(self._var("Speed", 0.0)) * 3.6  # m/s -> km/h
            dados["rpm"] = float(self._var("RPM", 0.0))
            dados["rpm_max"] = self._rpm_max
            dados["acelerador"] = float(self._var("Throttle", 0.0))
            dados["freio"] = float(self._var("Brake", 0.0))
            # No iRacing, Clutch = 1.0 significa pedal solto; invertemos para exibir
            dados["embreagem"] = 1.0 - float(self._var("Clutch", 1.0))
            dados["abs"] = bool(self._var("BrakeABSactive", False))
            dados["tc"] = self._ler_tc()
            nivel_abs = self._var("dcABS", None)
            dados["abs_nivel"] = float(nivel_abs) if nivel_abs is not None else None
            bias = self._var("dcBrakeBias", None)
            dados["bias"] = float(bias) if bias is not None else None
            dados["volante"] = math.degrees(float(self._var("SteeringWheelAngle", 0.0)))
            self._montar_v12(dados)

            # --- Fase 2: voltas, delta e combustivel ---
            dados["volta"] = max(0, int(self._var("Lap", 0)))
            dados["tempo_volta"] = self._tempo(
                self._var_primeiro(("LapCurrentLapTime", "LapCurLapTime"))
            )
            dados["ultima_volta"] = self._tempo(self._var("LapLastLapTime", None))
            dados["melhor_volta"] = self._tempo(self._var("LapBestLapTime", None))
            self._calcular_delta(dados)

            nivel = float(self._var("FuelLevel", 0.0))
            na_box = bool(self._var("OnPitRoad", False))
            self.consumo.atualizar(int(self._var("LapCompleted", -1)), nivel, na_box)
            media = self.consumo.media
            dados["combustivel"] = nivel
            dados["consumo_volta"] = media
            dados["voltas_restantes"] = (nivel / media) if media else None
            try:
                dados["calc_combustivel"] = self._montar_calc_combustivel(dados, nivel, na_box)
            except Exception:
                registrar_erro("calculo de combustivel")
                dados["calc_combustivel"] = None
            try:
                dados["painel_combustivel"] = self._montar_painel_combustivel(dados, nivel)
            except Exception:
                registrar_erro("painel de combustivel")
                dados["painel_combustivel"] = None

            # --- Fase 3: relativo (um erro aqui nunca derruba o resto do overlay) ---
            try:
                dados["relativo"] = self._montar_relativo()
            except Exception:
                registrar_erro("relativo")
                dados["relativo"] = None

            # --- Fase 4: classificacao (idem: isolada para nao afetar as outras janelas) ---
            try:
                dados["classificacao"] = self._cacheado("classificacao", 0.5, self._montar_classificacao)
            except Exception:
                registrar_erro("classificacao")
                dados["classificacao"] = None

            try:
                dados["pneus"] = self._montar_pneus()
            except Exception:
                registrar_erro("pneus")
                dados["pneus"] = None

            # --- Fase 5: mapa e radar (isolados) ---
            try:
                dados["mapa"] = self._montar_mapa()
            except Exception:
                registrar_erro("mapa")
                dados["mapa"] = None
            try:
                dados["radar"] = self._montar_radar()
            except Exception:
                registrar_erro("radar")
                dados["radar"] = None
            try:
                dados["projecao"] = self._montar_projecao()
            except Exception:
                registrar_erro("projecao de iR/SR")
                dados["projecao"] = None
            try:
                dados["setores"] = self._montar_setores(dados)
            except Exception:
                registrar_erro("setores")
                dados["setores"] = None
            dados["tipo_sessao"] = self._tipo_sessao      # (de novo: ja atualizado pelas leituras acima)
        finally:
            ir.unfreeze_var_buffer_latest()
        return dados

    def encerrar(self):
        try:
            if self.ir is not None:
                self.ir.shutdown()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Janelas
# --------------------------------------------------------------------------
COR_FUNDO_BARRA = QColor(255, 255, 255, 35)
COR_CINZA = QColor(170, 170, 185)
COR_TEXTO = QColor(235, 235, 240)
COR_VERDE = QColor(60, 200, 90)
COR_AMARELO = QColor(250, 200, 40)
COR_VERMELHO = QColor(235, 60, 60)
COR_LARANJA = QColor(255, 150, 40)


# --------------------------------------------------------------------------
# Visual (tema moderno x classico)
# --------------------------------------------------------------------------
TEMA = {"moderno": True, "sport": False, "vidro": True, "opacidade": 0.80}      # opacidade 0.80 = o fundo de sempre (alfa 205)
COR_DESTAQUE = QColor(224, 49, 63)               # vermelho do visual Sport (mesmo do dash do MagicDash 4)
_FAMILIAS = {True: ["Bahnschrift", "Segoe UI"], False: ["Segoe UI"]}
_TEXTURA = []


def fonte(tamanho, peso=QFont.Normal):
    """Fonte do overlay. Tema moderno: Bahnschrift (fonte de painel automotivo, ja vem no Windows 10/11);
    se nao existir, cai sozinha na Segoe UI. Tema classico: Segoe UI."""
    familias = _FAMILIAS[bool(TEMA["moderno"])]
    f = QFont(familias[0], tamanho, peso)
    f.setFamilies(familias)
    if TEMA["moderno"] and (TEMA["sport"] or TEMA["vidro"]):
        f.setItalic(True)                         # visual Sport: texto inclinado (v20.3)
    return f


_FONTE_TITULO = {"familia": None}
_ARQ_FONTE_TITULO = ("C:/Program Files (x86)/SimHub/DashFonts/SUIGBI_.TTF", "C:/Program Files/SimHub/DashFonts/SUIGBI_.TTF",
                     "fontes/SUIGBI_.TTF")


def fonte_titulo(tamanho):
    """Fonte dos titulos das janelas. Visual Sport e Glass Fume: Sui Generis Bold Italic (a mesma do dash do MagicDash 4), se estiver
    instalada com o SimHub; sem ela, cai na fonte normal em negrito. So para texto simples (a Sui Generis nao tem alguns
    simbolos, como o grau). Nunca levanta erro."""
    if TEMA["moderno"] and (TEMA["sport"] or TEMA["vidro"]):
        try:
            if _FONTE_TITULO["familia"] is None:
                _FONTE_TITULO["familia"] = ""
                from PySide6.QtGui import QFontDatabase
                for caminho in _ARQ_FONTE_TITULO:
                    if os.path.exists(caminho):
                        ident = QFontDatabase.addApplicationFont(caminho)
                        familias = QFontDatabase.applicationFontFamilies(ident) if ident >= 0 else []
                        if familias:
                            _FONTE_TITULO["familia"] = familias[0]
                            break
            if _FONTE_TITULO["familia"]:
                f = QFont(_FONTE_TITULO["familia"], max(6, int(round(tamanho * 0.92))), QFont.Bold)
                f.setItalic(True)
                return f
        except Exception:
            pass
    return fonte(tamanho, QFont.Bold)


def definir_tema(moderno=None, opacidade=None, sport=None, vidro=None):
    """Estilos: Glass Fume (vidro escuro translucido), Sport (italico, carbono, detalhes vermelhos) ou so o moderno.
    Glass Fume e Sport sao excludentes; se os dois vierem ligados (config antigo), vale o Glass Fume."""
    if sport is not None:
        TEMA["sport"] = bool(sport)
        if sport:
            TEMA["vidro"] = False
    if vidro is not None:
        TEMA["vidro"] = bool(vidro)
        if vidro:
            TEMA["sport"] = False
    if moderno is not None:
        TEMA["moderno"] = bool(moderno)
    if opacidade is not None:
        TEMA["opacidade"] = max(0.2, min(1.0, float(opacidade)))


def _textura_carbono():
    """Trama fina (fibra de carbono) em azulejo 4x4, bem discreta."""
    if not _TEXTURA:
        pix = QPixmap(4, 4)
        pix.fill(Qt.transparent)
        q = QPainter(pix)
        q.setPen(Qt.NoPen)
        q.setBrush(QColor(255, 255, 255, 12))
        q.drawRect(0, 0, 2, 2)
        q.drawRect(2, 2, 2, 2)
        q.setBrush(QColor(0, 0, 0, 40))
        q.drawRect(2, 0, 2, 2)
        q.drawRect(0, 2, 2, 2)
        q.end()
        _TEXTURA.append(pix)
    return _TEXTURA[0]


_TEXTURA_SPORT = []


def _textura_sport():
    """Trama diagonal (sarja) de fibra de carbono, discreta; azulejo 8x8."""
    if not _TEXTURA_SPORT:
        img = QImage(8, 8, QImage.Format_ARGB32)
        img.fill(0)
        for y in range(8):
            for x in range(8):
                d = (x - y) % 8
                if d < 4:
                    img.setPixelColor(x, y, QColor(255, 255, 255, 13 if d in (1, 2) else 7))
                else:
                    img.setPixelColor(x, y, QColor(0, 0, 0, 52 if d in (5, 6) else 34))
        _TEXTURA_SPORT.append(QPixmap.fromImage(img))
    return _TEXTURA_SPORT[0]


def _superficie_sport(p, rect, raio, cartao):
    """Visual Sport: janela com cantos cortados (superior esquerdo e inferior direito), fibra de carbono em sarja e
    detalhes vermelhos como no dash do MagicDash 4; cartao: cantos suaves e marca vermelha no topo."""
    a = int(255 * TEMA["opacidade"])
    if cartao:
        r = min(float(raio), 6.0)
        g = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        g.setColorAt(0.0, QColor(255, 255, 255, 24))
        g.setColorAt(1.0, QColor(255, 255, 255, 7))
        p.setBrush(g)
        p.drawRoundedRect(rect, r, r)
        p.setBrush(QBrush(_textura_sport()))
        p.drawRoundedRect(rect, r, r)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), r, r)
        p.setPen(Qt.NoPen)
        p.setBrush(COR_DESTAQUE)
        p.drawRect(QRectF(rect.left() + 8, rect.top(), 16, 2))
        return
    c = min(14.0, rect.height() / 4.0)
    cam = QPainterPath()
    cam.moveTo(rect.left() + c, rect.top())
    cam.lineTo(rect.right() - 6, rect.top())
    cam.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + 6)
    cam.lineTo(rect.right(), rect.bottom() - c)
    cam.lineTo(rect.right() - c, rect.bottom())
    cam.lineTo(rect.left() + 6, rect.bottom())
    cam.quadTo(rect.left(), rect.bottom(), rect.left(), rect.bottom() - 6)
    cam.lineTo(rect.left(), rect.top() + c)
    cam.closeSubpath()
    g = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
    g.setColorAt(0.0, QColor(30, 32, 40, a))
    g.setColorAt(0.5, QColor(15, 16, 22, a))
    g.setColorAt(1.0, QColor(8, 9, 13, a))
    p.setBrush(g)
    p.drawPath(cam)
    p.setBrush(QBrush(_textura_sport()))
    p.drawPath(cam)
    brilho = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())      # reflexo diagonal
    brilho.setColorAt(0.0, QColor(255, 255, 255, 20))
    brilho.setColorAt(0.35, QColor(255, 255, 255, 0))
    brilho.setColorAt(1.0, QColor(224, 49, 63, 14))
    p.setBrush(brilho)
    p.drawPath(cam)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 44), 1))
    p.drawPath(cam)
    # detalhes vermelhos: faixa no topo (a partir do canto cortado) e ponta no canto inferior direito
    p.setPen(Qt.NoPen)
    p.setBrush(COR_DESTAQUE)
    if rect.height() >= 48:                       # etiquetas pequenas (pilulas) ficam so com o corte e a borda
        p.drawRect(QRectF(rect.left() + c + 4, rect.top(), min(52.0, rect.width() * 0.2), 3))
        p.drawRect(QRectF(rect.right() - c - 22, rect.bottom() - 3, 22, 3))
    else:
        p.drawRect(QRectF(rect.left() + c + 2, rect.top(), min(18.0, rect.width() * 0.2), 2))


def _superficie_vidro(p, rect, raio, cartao):
    """Visual Glass Fume: vidro escuro translucido (fume). Degrade grafite com transparencia, reflexo suave no topo,
    faixa de luz diagonal, borda fina clara (mais forte no canto superior esquerdo) e linha interna de profundidade.
    Sem textura e sem detalhes vermelhos. Cartao: vidro mais leve, cantos suaves."""
    a = int(255 * TEMA["opacidade"] * 0.92)
    r = min(float(raio), 8.0) if cartao else max(float(raio), 12.0)
    r = min(r, rect.height() / 2.0)
    if cartao:
        g = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        g.setColorAt(0.0, QColor(255, 255, 255, 30))
        g.setColorAt(1.0, QColor(255, 255, 255, 9))
        p.setBrush(g)
        p.drawRoundedRect(rect, r, r)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 34), 1))
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), r, r)
        return
    g = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
    g.setColorAt(0.0, QColor(58, 63, 74, a))
    g.setColorAt(0.45, QColor(26, 29, 36, a))
    g.setColorAt(1.0, QColor(12, 14, 18, a))
    p.setBrush(g)
    p.drawRoundedRect(rect, r, r)
    # reflexo de vidro: faixa clara no topo que some ate a metade
    topo = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.top() + rect.height() * 0.5)
    topo.setColorAt(0.0, QColor(255, 255, 255, 38))
    topo.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setBrush(topo)
    p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), r, r)
    # faixa de luz diagonal bem suave
    luz = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
    luz.setColorAt(0.0, QColor(255, 255, 255, 0))
    luz.setColorAt(0.30, QColor(255, 255, 255, 14))
    luz.setColorAt(0.42, QColor(255, 255, 255, 0))
    luz.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setBrush(luz)
    p.drawRoundedRect(rect, r, r)
    # borda: clara no canto superior esquerdo, discreta no inferior direito
    borda = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
    borda.setColorAt(0.0, QColor(255, 255, 255, 120))
    borda.setColorAt(0.5, QColor(255, 255, 255, 40))
    borda.setColorAt(1.0, QColor(255, 255, 255, 22))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QBrush(borda), 1))
    p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), r, r)
    p.setPen(QPen(QColor(0, 0, 0, 90), 1))
    p.drawRoundedRect(rect.adjusted(1.5, 1.5, -1.5, -1.5), max(1.0, r - 1), max(1.0, r - 1))


def pintar_superficie(p, rect, raio=12, cartao=False, borda_classica=False):
    """Fundo de janela ou de cartao. Moderno: degrade grafite, trama de carbono, borda fina e brilho no topo.
    Classico: cor lisa (como era antes)."""
    rect = QRectF(rect)
    p.setPen(Qt.NoPen)
    if TEMA["moderno"] and TEMA["vidro"]:
        _superficie_vidro(p, rect, raio, cartao)
        return
    if TEMA["moderno"] and TEMA["sport"]:
        _superficie_sport(p, rect, raio, cartao)
        return
    if not TEMA["moderno"]:
        if cartao:
            if borda_classica:
                p.setPen(QPen(QColor(255, 255, 255, 22), 1))
            p.setBrush(QColor(255, 255, 255, 14))
        else:
            p.setBrush(QColor(14, 14, 20, int(255 * TEMA["opacidade"])))
        p.drawRoundedRect(rect, raio, raio)
        return
    a = int(255 * TEMA["opacidade"])
    g = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
    if cartao:
        g.setColorAt(0.0, QColor(255, 255, 255, 26))
        g.setColorAt(1.0, QColor(255, 255, 255, 8))
    else:
        g.setColorAt(0.0, QColor(34, 37, 46, a))
        g.setColorAt(0.55, QColor(20, 22, 29, a))
        g.setColorAt(1.0, QColor(11, 12, 17, a))
    p.setBrush(g)
    p.drawRoundedRect(rect, raio, raio)
    p.setBrush(QBrush(_textura_carbono()))
    p.drawRoundedRect(rect, raio, raio)
    # brilho no topo + borda fina
    brilho = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.top() + min(rect.height(), 26))
    brilho.setColorAt(0.0, QColor(255, 255, 255, 22 if not cartao else 12))
    brilho.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setBrush(brilho)
    p.drawRoundedRect(rect, raio, raio)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 46 if not cartao else 30), 1))
    p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), raio, raio)


class JanelaBase(QWidget):
    """Janela transparente, sempre no topo, que pode ser arrastada e travada."""

    CHAVE = "principal"   # prefixo das posicoes salvas no config.json
    CHAVE_ATIVO = None    # chave do config que liga/desliga a janela (None = sempre ligada)
    TAXA_HZ = 30.0        # repintura maxima por segundo (cada janela escolhe a sua; dados lentos = taxa baixa)
    MULT_TAXA = 1.0       # 0.5 no "modo economia de CPU"

    def __init_subclass__(cls, **kwargs):
        """Mede o tempo de desenho de cada janela (DESEMPENHO) sem mexer nos paintEvent existentes."""
        super().__init_subclass__(**kwargs)
        original = cls.__dict__.get("paintEvent")
        if original is not None:
            def medido(self, evento, _original=original):
                t0 = time.perf_counter()
                try:
                    _original(self, evento)
                finally:
                    DESEMPENHO.medir("pintura:" + self.CHAVE, (time.perf_counter() - t0) * 1000.0)
            medido.__name__ = "paintEvent"
            cls.paintEvent = medido

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._t_pintura = -1e9
        self.dados = Telemetria._vazio()
        self._arrasto = None
        self._redim = None
        self.escala_x, self.escala_y = self._ler_escalas(config)
        self.ativo = True if self.CHAVE_ATIVO is None else bool(config.get(self.CHAVE_ATIVO, True))
        self.auto_visivel = True      # modo automatico: False = escondida ate voce entrar no carro

        self.setWindowTitle("Overlay iRacing")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.aplicar_tamanho()
        self.move(int(config[self._chave("x")]), int(config[self._chave("y")]))
        self.aplicar_travamento(config["travado"])

    def tamanho(self):
        """Tamanho BASE (100 %) da janela; o tamanho real e este valor x escala_x / escala_y."""
        return (LARGURA, ALTURA)

    @staticmethod
    def _limitar_escala(valor):
        return max(ESCALA_MIN, min(ESCALA_MAX, float(valor)))

    def _ler_escalas(self, config):
        """Escalas de largura e altura salvas (ou a escala unica, de versoes anteriores)."""
        try:
            unica = self._limitar_escala(config.get(self._chave("escala"), 1.0))
            sx, sy = config.get(self._chave("escala_x")), config.get(self._chave("escala_y"))
            return (unica if sx is None else self._limitar_escala(sx),
                    unica if sy is None else self._limitar_escala(sy))
        except (TypeError, ValueError):
            return 1.0, 1.0

    @property
    def escala(self):
        """Escala media (para quem so precisa de uma referencia unica)."""
        return (self.escala_x + self.escala_y) / 2.0

    def aplicar_tamanho(self):
        largura, altura = self.tamanho()
        self.setFixedSize(max(40, round(largura * self.escala_x)), max(30, round(altura * self.escala_y)))

    def _gravar_escalas(self):
        self.config[self._chave("escala")] = round(self.escala, 3)
        self.config[self._chave("escala_x")] = round(self.escala_x, 3)
        self.config[self._chave("escala_y")] = round(self.escala_y, 3)

    def definir_escalas(self, escala_x, escala_y, salvar=True):
        self.escala_x = self._limitar_escala(escala_x)
        self.escala_y = self._limitar_escala(escala_y)
        self._gravar_escalas()
        self.aplicar_tamanho()
        self.update()
        if salvar:
            salvar_config(self.config)

    def definir_escala(self, escala, salvar=True):
        """Mesma escala na largura e na altura (mantem a proporcao)."""
        self.definir_escalas(escala, escala, salvar)

    def _retangulo_base(self):
        return QRect(0, 0, *self.tamanho())

    def _pintor(self):
        """QPainter ja na escala da janela: todo o desenho usa as coordenadas do tamanho base."""
        p = QPainter(self)
        p.scale(self.escala_x, self.escala_y)
        return p

    def _chave(self, base):
        return base if self.CHAVE == "principal" else f"{base}_{self.CHAVE}"

    # -- travar / ligar / desligar ----------------------------------------------
    def aplicar_travamento(self, travado):
        self.config["travado"] = bool(travado)
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        if travado:
            flags |= Qt.WindowTransparentForInput  # cliques atravessam o overlay
        self.setWindowFlags(flags)
        self._aplicar_visibilidade(forcar=True)
        self.update()

    def _aplicar_visibilidade(self, forcar=False):
        """Aparece so se estiver ligada no menu E o modo automatico permitir."""
        deve = self.ativo and self.auto_visivel
        if deve and (forcar or not self.isVisible()):
            self.show()
        elif not deve and (forcar or self.isVisible()):
            self.hide()

    def definir_auto_visivel(self, visivel):
        visivel = bool(visivel)
        if visivel != self.auto_visivel:
            self.auto_visivel = visivel
            self._aplicar_visibilidade()

    def definir_ativo(self, ativo):
        self.ativo = bool(ativo)
        if self.CHAVE_ATIVO:
            self.config[self.CHAVE_ATIVO] = self.ativo
        self._aplicar_visibilidade(forcar=True)

    # -- mover / redimensionar com o mouse (somente destravado) -----------------
    def _borda(self, pos):
        m = 0
        if pos.x() <= MARGEM_REDIM:
            m |= _BORDA_ESQ
        elif pos.x() >= self.width() - MARGEM_REDIM:
            m |= _BORDA_DIR
        if pos.y() <= MARGEM_REDIM:
            m |= _BORDA_TOPO
        elif pos.y() >= self.height() - MARGEM_REDIM:
            m |= _BORDA_BASE
        return m

    @staticmethod
    def _cursor_da_borda(m):
        if m in (_BORDA_ESQ | _BORDA_TOPO, _BORDA_DIR | _BORDA_BASE):
            return Qt.SizeFDiagCursor
        if m in (_BORDA_DIR | _BORDA_TOPO, _BORDA_ESQ | _BORDA_BASE):
            return Qt.SizeBDiagCursor
        if m & (_BORDA_ESQ | _BORDA_DIR):
            return Qt.SizeHorCursor
        if m & (_BORDA_TOPO | _BORDA_BASE):
            return Qt.SizeVerCursor
        return Qt.SizeAllCursor

    def mousePressEvent(self, evento):
        if evento.button() != Qt.LeftButton or self.config["travado"]:
            return
        ponto_global = evento.globalPosition().toPoint()
        borda = self._borda(evento.position().toPoint())
        if borda:
            self._redim = {"borda": borda, "origem": ponto_global, "x": self.x(), "y": self.y(),
                           "w": self.width(), "h": self.height(),
                           "sx": self.escala_x, "sy": self.escala_y}
        else:
            self._arrasto = ponto_global - self.frameGeometry().topLeft()

    def _redimensionar(self, ponto_global):
        """Bordas laterais mudam so a LARGURA; borda de cima/baixo so a ALTURA; cantos mudam as
        duas mantendo a proporcao que a janela tinha."""
        r = self._redim
        borda = r["borda"]
        dx, dy = ponto_global.x() - r["origem"].x(), ponto_global.y() - r["origem"].y()
        largura = r["w"] + (dx if borda & _BORDA_DIR else -dx if borda & _BORDA_ESQ else 0)
        altura = r["h"] + (dy if borda & _BORDA_BASE else -dy if borda & _BORDA_TOPO else 0)
        fx, fy = largura / float(r["w"]), altura / float(r["h"])
        sx0, sy0 = r["sx"], r["sy"]
        horizontal = bool(borda & (_BORDA_ESQ | _BORDA_DIR))
        vertical = bool(borda & (_BORDA_TOPO | _BORDA_BASE))
        if horizontal and vertical:
            f = (fx + fy) / 2.0
            f = max(max(ESCALA_MIN / sx0, ESCALA_MIN / sy0), min(f, min(ESCALA_MAX / sx0, ESCALA_MAX / sy0)))
            sx, sy = sx0 * f, sy0 * f
        elif horizontal:
            sx, sy = sx0 * fx, sy0
        else:
            sx, sy = sx0, sy0 * fy
        self.definir_escalas(sx, sy, salvar=False)
        x = r["x"] + r["w"] - self.width() if borda & _BORDA_ESQ else r["x"]
        y = r["y"] + r["h"] - self.height() if borda & _BORDA_TOPO else r["y"]
        self.move(x, y)

    def mouseMoveEvent(self, evento):
        if self.config["travado"]:
            return
        if self._redim is not None:
            self._redimensionar(evento.globalPosition().toPoint())
        elif self._arrasto is not None:
            self.move(evento.globalPosition().toPoint() - self._arrasto)
        else:
            self.setCursor(self._cursor_da_borda(self._borda(evento.position().toPoint())))

    def mouseReleaseEvent(self, evento):
        if self._arrasto is not None or self._redim is not None:
            self._arrasto = None
            self._redim = None
            self.config[self._chave("x")], self.config[self._chave("y")] = self.x(), self.y()
            self._gravar_escalas()
            salvar_config(self.config)

    def wheelEvent(self, evento):
        """Ctrl + roda do mouse (com as janelas destravadas) amplia/reduz a janela."""
        if self.config["travado"] or not (evento.modifiers() & Qt.ControlModifier):
            evento.ignore()
            return
        passo = 1.06 ** (evento.angleDelta().y() / 120.0)
        self.definir_escalas(self.escala_x * passo, self.escala_y * passo)
        evento.accept()

    # -- atualizacao --------------------------------------------------------------
    def atualizar(self, dados):
        self.dados = dados
        self._repintar()

    def _repintar(self):
        """Pede o desenho respeitando a taxa da janela (poupa CPU: o jogo vem primeiro)."""
        agora = time.monotonic()
        minimo = 1.0 / max(0.5, self.TAXA_HZ * JanelaBase.MULT_TAXA)
        if agora - self._t_pintura >= minimo - 0.004:      # 4 ms de tolerancia para o relogio do timer
            self._t_pintura = agora
            self.update()

    def recarregar_layout(self):
        """Le de novo posicao, tamanho e visibilidade do config (usado ao trocar de perfil)."""
        self.escala_x, self.escala_y = self._ler_escalas(self.config)
        if self.CHAVE_ATIVO:
            self.ativo = bool(self.config.get(self.CHAVE_ATIVO, True))
        self.aplicar_tamanho()
        self.move(int(self.config[self._chave("x")]), int(self.config[self._chave("y")]))
        self._aplicar_visibilidade(forcar=True)
        self.update()

    # -- desenho comum ------------------------------------------------------------
    def _fundo(self, p, conectado=True, mensagem="Aguardando o iRacing...", com_fundo=True):
        """Desenha o fundo. Retorna False (e escreve a mensagem) quando nao ha dados.
        com_fundo=False: janela sem painel (a propria janela desenha o seu formato)."""
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        base = self._retangulo_base()
        if com_fundo:
            pintar_superficie(p, base.adjusted(1, 1, -1, -1), 12)

        # Contorno amarelo indica "modo mover / redimensionar"
        if not self.config["travado"]:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 200, 0, 230), 2))
            p.drawRoundedRect(base.adjusted(2, 2, -2, -2), 12, 12)
            # puxador no canto inferior direito
            p.setPen(QPen(QColor(255, 200, 0, 230), 2, Qt.SolidLine, Qt.RoundCap))
            x, y = base.width() - 6, base.height() - 6
            for k in (6, 11, 16):
                p.drawLine(x - k, y, x, y - k)

        if not conectado:
            p.setPen(QColor(200, 200, 210))
            p.setFont(fonte(15, QFont.DemiBold))
            p.drawText(base, Qt.AlignCenter, mensagem)
            return False
        return True


def desenhar_grafico_inputs(p, ret, hist, c, marchas_max):
    """Grafico rolante de pedais (acelerador verde, freio vermelho), degraus da marcha e marcas de ABS/TC."""
    p.setPen(QPen(QColor(255, 255, 255, 40), 1))
    p.setBrush(QColor(0, 0, 0, 90))
    p.drawRoundedRect(ret, 6, 6)
    seg = hist.segundos
    p.setPen(QPen(QColor(255, 255, 255, 28), 1))
    p.drawLine(QPointF(ret.left(), ret.center().y()), QPointF(ret.right(), ret.center().y()))
    passo = max(1.0, seg / 6.0)
    k = passo
    while k < seg:
        xx = ret.right() - ret.width() * k / seg
        p.drawLine(QPointF(xx, ret.top()), QPointF(xx, ret.bottom()))
        k += passo
    am = hist.amostras()
    if len(am) < 2:
        return
    agora = am[-1][0]
    topo, base = ret.top() + 5, ret.bottom() - 5
    altura = base - topo

    def pt(t, v):
        return QPointF(ret.right() - ret.width() * (agora - t) / seg, base - altura * max(0.0, min(1.0, v)))

    def linha(indice, cor, esp, filtro=None):
        caminho = QPainterPath()
        primeiro = True
        for a in am:
            v = a[indice]
            if v is None:
                continue
            q = pt(a[0], v)
            if primeiro:
                caminho.moveTo(q)
                primeiro = False
            else:
                caminho.lineTo(q)
        p.setPen(QPen(cor, esp, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(caminho)

    if c.get("inputs_marchas_fundo", True):
        maxg = max(2, marchas_max)
        caminho = QPainterPath()
        primeiro = True
        for a in am:
            q = pt(a[0], max(0, a[5]) / float(maxg))
            if primeiro:
                caminho.moveTo(q)
                primeiro = False
            else:
                caminho.lineTo(QPointF(q.x(), caminho.currentPosition().y()))     # degrau
                caminho.lineTo(q)
        p.setPen(QPen(QColor(150, 150, 165, 120), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawPath(caminho)
    origem = c.get("inputs_origem", "carro")
    if origem in ("cru", "ambos"):
        linha(6, QColor(60, 200, 90, 255 if origem == "cru" else 110), 2.0 if origem == "ambos" else 2.4)
    if origem in ("carro", "ambos"):
        linha(1, COR_VERDE, 2.6)
    if origem in ("cru", "ambos"):
        linha(7, QColor(235, 60, 60, 255 if origem == "cru" else 110), 2.0 if origem == "ambos" else 2.4)
    if origem in ("carro", "ambos"):
        linha(2, COR_VERMELHO, 2.6)
    # marcas de ABS (amarelo, sobre o freio) e TC (azul, sobre o acelerador)
    for ativo_idx, cor, valor_idx, ligado in ((3, QColor(250, 200, 40), 2, c.get("inputs_marca_abs", True)),
                                              (4, QColor(80, 150, 255), 1, c.get("inputs_marca_tc", False))):
        if not ligado:
            continue
        trecho = []
        for a in am + [None]:
            if a is not None and a[ativo_idx]:
                trecho.append(pt(a[0], a[valor_idx]))
            elif trecho:
                if len(trecho) >= 2:
                    cam = QPainterPath(trecho[0])
                    for q in trecho[1:]:
                        cam.lineTo(q)
                    p.setPen(QPen(cor, 4.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    p.setBrush(Qt.NoBrush)
                    p.drawPath(cam)
                else:
                    p.setPen(Qt.NoPen)
                    p.setBrush(cor)
                    p.drawEllipse(trecho[0], 2.5, 2.5)
                trecho = []


# ---- Janela 1: telemetria (marcha, velocidade, RPM, pedais e grafico) ----------------
class JanelaTelemetria(JanelaBase):
    CHAVE = "principal"            # mantem a posicao (x, y) ja salva pelo usuario
    CHAVE_ATIVO = "mostrar_telemetria"
    TAXA_HZ = 30.0

    def __init__(self, config):
        self.hist = v12.HistoricoInputs(config.get("inputs_segundos", 12))
        self._marchas_max = 6
        super().__init__(config)

    def tamanho(self):
        grafico = ALTURA_GRAFICO if self.config.get("mostrar_grafico", True) else 0
        return (LARGURA, ALTURA + grafico)

    def definir_grafico(self, ativo):
        self.config["mostrar_grafico"] = bool(ativo)
        self.aplicar_tamanho()
        self.update()

    def atualizar(self, dados):
        self.dados = dados
        if dados["conectado"]:
            tc = (dados.get("luz_tc") or {}).get("ativa")
            cru = dados.get("pedais_cru") or {}
            self.hist.adicionar(time.monotonic(), dados["acelerador"], dados["freio"], dados.get("abs"), bool(tc),
                                dados["marcha"], cru.get("acelerador"), cru.get("freio"))
            self._marchas_max = max(self._marchas_max, int(dados["marcha"] or 0))
        self._repintar()

    def reconfigurar(self):
        self.hist.definir_segundos(self.config.get("inputs_segundos", 12))
        self.update()

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        self._desenhar_principal(p, d)
        if self.config.get("mostrar_grafico", True):
            p.save()
            p.translate(0, ALTURA)
            p.setPen(QPen(QColor(255, 255, 255, 40), 1))
            p.drawLine(14, 0, LARGURA - 14, 0)
            self._desenhar_grafico(p, d)
            p.restore()

    def _desenhar_principal(self, p, d):
        # Barra de RPM
        proporcao = max(0.0, min(1.0, d["rpm"] / d["rpm_max"])) if d["rpm_max"] else 0.0
        p.setPen(Qt.NoPen)
        p.setBrush(COR_FUNDO_BARRA)
        p.drawRoundedRect(14, 14, LARGURA - 28, 14, 6, 6)
        if proporcao < 0.80:
            cor = COR_VERDE
        elif proporcao < 0.92:
            cor = COR_AMARELO
        else:
            cor = COR_VERMELHO
        p.setBrush(cor)
        p.drawRoundedRect(14, 14, int((LARGURA - 28) * proporcao), 14, 6, 6)

        # Marcha
        marcha = d["marcha"]
        texto_marcha = "R" if marcha < 0 else ("N" if marcha == 0 else str(marcha))
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(54, QFont.Bold))
        p.drawText(14, 38, 110, 84, Qt.AlignCenter, texto_marcha)

        # Velocidade
        p.setFont(fonte(38, QFont.Bold))
        p.drawText(130, 40, 180, 54, Qt.AlignRight | Qt.AlignVCenter, str(int(round(d["velocidade"]))))
        p.setPen(COR_CINZA)
        p.setFont(fonte(11))
        p.drawText(130, 92, 180, 20, Qt.AlignRight | Qt.AlignVCenter, "km/h")
        p.drawText(130, 108, 180, 20, Qt.AlignRight | Qt.AlignVCenter, f"{int(d['rpm']):,} rpm".replace(",", "."))

        # Pedais: embreagem, freio, acelerador
        cru = d.get("pedais_cru") or {}
        usar_cru = self.config.get("inputs_origem", "carro") == "cru"
        v_fre = cru.get("freio") if usar_cru and cru.get("freio") is not None else d["freio"]
        v_ace = cru.get("acelerador") if usar_cru and cru.get("acelerador") is not None else d["acelerador"]
        pedais = [
            ("EMB", d["embreagem"], QColor(70, 140, 255)),
            ("FRE", v_fre, COR_VERMELHO),
            ("ACE", v_ace, COR_VERDE),
        ]
        x = 340
        for nome, valor, cor in pedais:
            valor = max(0.0, min(1.0, valor))
            p.setPen(Qt.NoPen)
            p.setBrush(COR_FUNDO_BARRA)
            p.drawRoundedRect(x, 40, 24, 70, 5, 5)
            altura = int(70 * valor)
            p.setBrush(cor)
            p.drawRoundedRect(x, 40 + 70 - altura, 24, altura, 5, 5)
            p.setPen(COR_CINZA)
            p.setFont(fonte(8))
            p.drawText(x - 4, 112, 32, 14, Qt.AlignCenter, nome)
            x += 38

        self._desenhar_volante(p, LARGURA - 54, 74, 36, d["volante"])

    @staticmethod
    def _desenhar_volante(p, cx, cy, r, graus):
        """Volante girando conforme o seu volante real; o marcador vermelho fica no topo do aro."""
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(cx, cy)
        p.rotate(-graus)  # positivo = esquerda (anti-horario)
        branco = QColor(245, 245, 248)
        # aro
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(branco, 8))
        p.drawEllipse(-r, -r, 2 * r, 2 * r)
        # raios (horizontal e para baixo) e cubo
        p.setPen(Qt.NoPen)
        p.setBrush(branco)
        p.drawRoundedRect(-r + 2, -4, 2 * r - 4, 9, 3, 3)
        p.drawRoundedRect(-4, 0, 9, r - 2, 3, 3)
        p.drawEllipse(-9, -9, 18, 18)
        # marcador do topo
        p.setBrush(COR_VERMELHO)
        p.drawRoundedRect(-3, -r - 4, 7, 11, 2, 2)
        p.restore()
        p.setPen(COR_CINZA)
        p.setFont(fonte(8))
        p.drawText(cx - 40, cy + r + 6, 80, 14, Qt.AlignCenter, f"{graus:+.0f}\u00b0")

    @staticmethod
    def _fmt_nivel(v):
        return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"

    @staticmethod
    def _selo_ajuste(p, x, texto, cor_texto, cor_fundo):
        """Selo arredondado de 16 px de altura; devolve o x logo depois dele."""
        largura = max(34, QFontMetrics(p.font()).horizontalAdvance(texto) + 14)
        p.setPen(Qt.NoPen)
        p.setBrush(cor_fundo)
        p.drawRoundedRect(x, 9, largura, 16, 5, 5)
        p.setPen(cor_texto)
        p.drawText(x, 9, largura, 16, Qt.AlignCenter, texto)
        return x + largura

    def _desenhar_tc(self, p, tc, x):
        """Selo do controle de tracao (TC): mostra o AJUSTE, nao a atuacao. Devolve o proximo x."""
        cor_texto = COR_CINZA
        if not tc:
            texto = "TC --"
        elif tc.get("ligado") is False:
            texto, cor_texto = "TC OFF", COR_LARANJA
        else:
            partes = [self._fmt_nivel(v) for v in (tc.get("nivel"), tc.get("nivel2")) if v is not None]
            texto = "TC " + "/".join(partes) if partes else "TC"
            cor_texto = QColor(120, 190, 255)
        return self._selo_ajuste(p, x, texto, cor_texto, COR_FUNDO_BARRA)

    def _desenhar_bias(self, p, bias, x):
        """Selo do balanco de freio (BB). Valores de 20 a 80 sao tratados como % (dianteira)."""
        if bias is None:
            return self._selo_ajuste(p, x, "BB --", COR_CINZA, COR_FUNDO_BARRA)
        texto = f"BB {bias:.1f}%" if 20.0 <= bias <= 80.0 else f"BB {bias:.1f}"
        return self._selo_ajuste(p, x, texto, QColor(255, 190, 120), COR_FUNDO_BARRA)

    def _desenhar_grafico(self, p, d):
        x0, x1 = 14, LARGURA - 14
        y_topo, y_base = 32, ALTURA_GRAFICO - 14

        # Legenda (esquerda) e valores atuais (direita)
        p.setFont(fonte(8, QFont.DemiBold))
        p.setPen(Qt.NoPen)
        p.setBrush(COR_VERDE)
        p.drawRoundedRect(x0, 13, 8, 8, 2, 2)
        p.setPen(COR_CINZA)
        p.drawText(x0 + 13, 8, 90, 18, Qt.AlignLeft | Qt.AlignVCenter, "ACELERADOR")
        p.setPen(Qt.NoPen)
        p.setBrush(COR_VERMELHO)
        p.drawRoundedRect(x0 + 108, 13, 8, 8, 2, 2)
        p.setPen(COR_CINZA)
        p.drawText(x0 + 121, 8, 60, 18, Qt.AlignLeft | Qt.AlignVCenter, "FREIO")

        # Selos de ajuste (em sequencia): ABS (acende quando atua), TC e balanco de freio
        abs_ativo = bool(d.get("abs"))
        x = x0 + 172
        texto_abs = "ABS" if d.get("abs_nivel") is None else f"ABS {self._fmt_nivel(d['abs_nivel'])}"
        x = self._selo_ajuste(p, x, texto_abs, QColor(20, 20, 25) if abs_ativo else COR_CINZA,
                              COR_AMARELO if abs_ativo else COR_FUNDO_BARRA)
        x = self._desenhar_tc(p, d.get("tc"), x + 6)
        self._desenhar_bias(p, d.get("bias"), x + 6)

        p.setFont(fonte(10, QFont.Bold))
        p.setPen(COR_VERDE)
        p.drawText(x1 - 150, 8, 70, 18, Qt.AlignRight | Qt.AlignVCenter, f"{d['acelerador'] * 100:.0f}%")
        p.setPen(COR_VERMELHO)
        p.drawText(x1 - 75, 8, 75, 18, Qt.AlignRight | Qt.AlignVCenter, f"{d['freio'] * 100:.0f}%")

        desenhar_grafico_inputs(p, QRectF(x0, y_topo, x1 - x0, y_base - y_topo), self.hist, self.config, self._marchas_max)


# ---- Janela 2: delta, voltas e combustivel ----------------------------------------------
class JanelaVoltas(JanelaBase):
    CHAVE = "voltas"
    CHAVE_ATIVO = "mostrar_voltas"
    TAXA_HZ = 15.0

    def tamanho(self):
        extra = ALTURA_CALC_COMBUSTIVEL if self.config.get("mostrar_calc_combustivel", True) else 0
        return (LARGURA_VOLTAS, ALTURA_VOLTAS + extra)

    def definir_calc(self, ativo):
        self.config["mostrar_calc_combustivel"] = bool(ativo)
        self.aplicar_tamanho()
        self.update()

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        self._desenhar_voltas(p, d)
        if self.config.get("mostrar_calc_combustivel", True):
            self._desenhar_calc(p, d)

    def _desenhar_calc(self, p, d):
        """Faixa inferior: voltas ate o fim, combustivel necessario (com margem) e quanto adicionar."""
        y0 = ALTURA_VOLTAS
        larg = 138
        colunas = [14, 161, 308]
        c = d.get("calc_combustivel") or {}

        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawLine(14, y0, LARGURA_VOLTAS - 14, y0)

        def rotulo(x, texto):
            p.setPen(COR_CINZA)
            p.setFont(fonte(8, QFont.DemiBold))
            p.drawText(x, y0 + 5, larg + 4, 14, Qt.AlignLeft | Qt.AlignVCenter, texto)

        def valor(x, texto, cor=QColor(255, 255, 255)):
            p.setPen(cor)
            p.setFont(fonte(17, QFont.Bold))
            p.drawText(x, y0 + 18, larg, 28, Qt.AlignLeft | Qt.AlignVCenter, texto)

        def sub(x, texto, cor=COR_CINZA):
            p.setPen(cor)
            p.setFont(fonte(8))
            p.drawText(x, y0 + 45, larg + 6, 14, Qt.AlignLeft | Qt.AlignVCenter, texto)

        # ---- 1) voltas ate o fim
        x = colunas[0]
        rotulo(x, "VOLTAS ATE O FIM")
        if c.get("voltas_fim") is None:
            valor(x, "--", COR_CINZA)
            sub(x, "sessao sem fim definido")
        else:
            valor(x, f"{c['voltas_fim']:.1f}")
            if c["fonte"] == "tempo" and c.get("ritmo"):
                sub(x, f"por tempo (ritmo {fmt_tempo(c['ritmo'])})")
            else:
                sub(x, "pelas voltas da sessao")

        # ---- 2) combustivel necessario com margem
        x = colunas[1]
        margem = c.get("margem_voltas", 1.0)
        rotulo(x, f"NECESSARIO (+{margem:g} v)")
        if c.get("necessario") is None:
            valor(x, "--", COR_CINZA)
            sub(x, "complete 2 voltas limpas" if c.get("voltas_fim") is not None else "")
        else:
            valor(x, f"{c['necessario']:.1f} L")
            sub(x, f"tem {c['nivel']:.1f} L no tanque")

        # ---- 3) adicionar
        x = colunas[2]
        rotulo(x, "ADICIONAR")
        if c.get("adicionar") is None:
            valor(x, "--", COR_CINZA)
            livre = c.get("livre_tanque")
            sub(x, f"cabe +{livre:.0f} L" if livre else "")
        elif c["adicionar"] <= 0.05:
            valor(x, "OK", COR_VERDE)
            sub(x, f"folga de {c['folga']:.1f} L", COR_VERDE)
        else:
            livre = c.get("livre_tanque")
            cabe = livre is None or c["adicionar"] <= livre + 0.05
            valor(x, f"+{c['adicionar']:.1f} L", COR_AMARELO if cabe else COR_VERMELHO)
            if cabe:
                sub(x, f"cabe +{livre:.0f} L" if livre is not None else "parar nos boxes")
            else:
                sub(x, (f"nao cabe: {c['paradas']} paradas" if c.get("paradas")
                        else "sem plano de pit viavel"), COR_VERMELHO)

    def _desenhar_voltas(self, p, d):
        y0 = 0
        larg = 138
        colunas = [14, 161, 308]

        def rotulo(x, texto):
            p.setPen(COR_CINZA)
            p.setFont(fonte(8, QFont.DemiBold))
            p.drawText(x, y0 + 6, larg, 14, Qt.AlignLeft | Qt.AlignVCenter, texto)

        def linha(x, y, nome, valor, cor=COR_TEXTO):
            p.setFont(fonte(9))
            p.setPen(COR_CINZA)
            p.drawText(x, y, larg, 16, Qt.AlignLeft | Qt.AlignVCenter, nome)
            p.setPen(cor)
            p.drawText(x, y, larg, 16, Qt.AlignRight | Qt.AlignVCenter, valor)

        # ---- Coluna 1: delta vs melhor volta ---------------------------------
        x = colunas[0]
        rotulo(x, "DELTA")
        delta = d["delta"]
        if d["delta_ok"]:
            if delta < -0.0005:
                cor_delta = COR_VERDE
            elif delta > 0.0005:
                cor_delta = COR_VERMELHO
            else:
                cor_delta = QColor(255, 255, 255)
            texto_delta = f"{delta:+.3f}"
        else:
            cor_delta = COR_CINZA
            texto_delta = "--.---"
        p.setPen(cor_delta)
        p.setFont(fonte(24, QFont.Bold))
        p.drawText(x, y0 + 20, larg, 38, Qt.AlignLeft | Qt.AlignVCenter, texto_delta)

        # Barra de delta: verde para a direita (mais rapido), vermelha para a esquerda
        p.setPen(Qt.NoPen)
        p.setBrush(COR_FUNDO_BARRA)
        p.drawRoundedRect(x, y0 + 62, larg, 10, 4, 4)
        if d["delta_ok"]:
            metade = larg / 2.0
            tamanho = int(min(1.0, abs(delta) / 1.0) * metade)  # 1,0 s = barra cheia
            p.setBrush(cor_delta)
            if delta < 0:
                p.drawRect(int(x + metade), y0 + 62, tamanho, 10)
            else:
                p.drawRect(int(x + metade) - tamanho, y0 + 62, tamanho, 10)
        p.setPen(QPen(QColor(255, 255, 255, 140), 1))
        p.drawLine(int(x + larg / 2), y0 + 60, int(x + larg / 2), y0 + 74)
        p.setPen(COR_CINZA)
        p.setFont(fonte(8))
        p.drawText(x, y0 + 78, larg, 14, Qt.AlignLeft | Qt.AlignVCenter,
                   ("SDK \u00b7 vs melhor volta" if d.get("delta_fonte") == "sim"
                    else "~ calc. \u00b7 melhor volta limpa") if d["delta_ok"] else "complete 1 volta limpa")

        # ---- Coluna 2: voltas -------------------------------------------------
        x = colunas[1]
        rotulo(x, f"VOLTA {d['volta']}")
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(20, QFont.Bold))
        p.drawText(x, y0 + 20, larg, 38, Qt.AlignLeft | Qt.AlignVCenter, fmt_tempo(d["tempo_volta"]))
        linha(x, y0 + 58, "ULTIMA", fmt_tempo(d["ultima_volta"]))
        linha(x, y0 + 76, "MELHOR", fmt_tempo(d["melhor_volta"]), QColor(190, 130, 255))

        # ---- Coluna 3: combustivel -------------------------------------------
        x = colunas[2]
        rotulo(x, "COMBUSTIVEL")
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(22, QFont.Bold))
        p.drawText(x, y0 + 20, larg, 38, Qt.AlignLeft | Qt.AlignVCenter, f"{d['combustivel']:.1f} L")
        consumo = d["consumo_volta"]
        restantes = d["voltas_restantes"]
        linha(x, y0 + 58, "CONSUMO", f"{consumo:.2f} L/v" if consumo else "--")
        if restantes is None:
            linha(x, y0 + 76, "RESTAM", "--")
        else:
            if restantes < 3:
                cor_rest = COR_VERMELHO
            elif restantes < 6:
                cor_rest = COR_AMARELO
            else:
                cor_rest = COR_TEXTO
            linha(x, y0 + 76, "RESTAM", f"{restantes:.1f} voltas", cor_rest)


# ---- Janela 3: relativo -------------------------------------------------------------
class JanelaRelativo(JanelaBase):
    CHAVE = "relativo"
    CHAVE_ATIVO = "mostrar_relativo"
    TAXA_HZ = 10.0

    def _com_projecao(self):
        return bool(self.config.get("mostrar_projecao", True))

    def tamanho(self):
        return (LARGURA_REL, ALTURA_REL + (ALTURA_PROJECAO if self._com_projecao() else 0))

    def definir_projecao(self, ativo):
        self.config["mostrar_projecao"] = bool(ativo)
        self.aplicar_tamanho()
        self.update()

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        rel = d.get("relativo")
        if not rel:
            p.setPen(COR_CINZA)
            p.setFont(fonte(12))
            p.drawText(self._retangulo_base(), Qt.AlignCenter, "Sem dados dos outros carros")
            return

        self._cabecalho(p, rel)

        n_frente = rel["n_frente"]
        frente = rel["frente"]
        # Carros a frente ficam encostados na sua linha; os espacos vazios ficam no topo
        for k, linha in enumerate(frente):
            self._linha(p, ALTURA_CAB + (n_frente - len(frente) + k) * ALTURA_LINHA, linha)
        self._linha(p, ALTURA_CAB + n_frente * ALTURA_LINHA, rel["eu"])
        for k, linha in enumerate(rel["atras"]):
            self._linha(p, ALTURA_CAB + (n_frente + 1 + k) * ALTURA_LINHA, linha)

        if self._com_projecao():
            self._projecao(p, d.get("projecao"))
        self._rodape(p, rel)

    # ---- faixa de projecao de iRating e SR (estimativas) ----------------------------------
    @staticmethod
    def _cor_variacao(valor, limite):
        if valor > limite:
            return COR_VERDE
        if valor < -limite:
            return COR_VERMELHO
        return QColor(255, 255, 255)

    @staticmethod
    def _seta(valor, limite):
        return "\u25B2 " if valor > limite else ("\u25BC " if valor < -limite else "= ")

    def _celula_projecao(self, p, x, y, largura, rotulo, dica, valor, cor, resultado):
        p.setFont(fonte(8, QFont.DemiBold))
        p.setPen(COR_CINZA)
        p.drawText(x, y + 3, largura, 13, Qt.AlignLeft | Qt.AlignVCenter, rotulo)
        if dica:
            p.setFont(fonte(7))
            p.drawText(x, y + 3, largura, 13, Qt.AlignRight | Qt.AlignVCenter, dica)
        p.setFont(fonte(14, QFont.Bold))
        p.setPen(cor)
        p.drawText(x, y + 16, 104, 22, Qt.AlignLeft | Qt.AlignVCenter, valor)
        if resultado:
            p.setFont(fonte(9, QFont.DemiBold))
            p.setPen(COR_TEXTO)
            p.drawText(x + 104, y + 18, largura - 104, 20, Qt.AlignRight | Qt.AlignVCenter, resultado)

    def _projecao(self, p, proj):
        y0 = ALTURA_CAB + (SLOTS_FRENTE + 1 + SLOTS_TRAS) * ALTURA_LINHA
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawLine(14, y0, LARGURA_REL - 14, y0)
        p.drawLine(LARGURA_REL // 2, y0 + 6, LARGURA_REL // 2, y0 + ALTURA_PROJECAO - 4)
        proj = proj or {}
        tipo, oficial = proj.get("tipo"), proj.get("oficial")
        larg = LARGURA_REL // 2 - 24
        cinza = COR_CINZA

        # --- iRating (so vale em corrida oficial) ---
        ir = proj.get("ir")
        rot_ir = "iRATING PROJETADO"
        if oficial is False:
            args = (rot_ir, "nao oficial", "--", cinza, "")
        elif tipo and tipo != "CORRIDA":
            args = (rot_ir, "so em corrida", "--", cinza, "")
        elif not ir:
            args = (rot_ir, "", "--", cinza, "")
        else:
            delta = ir["delta"]
            args = (rot_ir, f"base {ir['atual']:,}".replace(",", "."),
                    f"{self._seta(delta, 0.5)}{int(round(delta)):+d}", self._cor_variacao(delta, 0.5),
                    "~" + f"{ir['novo']:,}".replace(",", "."))
        self._celula_projecao(p, 14, y0, larg, *args)

        # --- Safety Rating (estimativa) ---
        sr = proj.get("sr")
        x2 = LARGURA_REL // 2 + 12
        rot_sr = "SR PROJETADO"
        if oficial is False:
            args = (rot_sr, "nao oficial", "--", cinza, "")
        elif not sr:
            args = (rot_sr, "nao conta" if tipo else "", "--", cinza, "")
        else:
            delta = sr["delta"]
            curvas, inc = proj.get("curvas", 0.0), proj.get("inc", 0)
            dica = f"base {fmt_dec(sr['atual'], 2)} | {curvas:.0f} curvas"
            if inc > 0 and curvas >= 1:
                dica += f" | CPI {curvas / inc:.0f}"
            args = (rot_sr, dica,
                    f"{self._seta(delta, 0.004)}{delta:+.2f}", self._cor_variacao(delta, 0.004),
                    "~" + f"{sr['novo']:.2f}")
        self._celula_projecao(p, x2, y0, larg, *args)

    def _rotulo_valor(self, p, x, y, rotulo, valor, cor_valor=None):
        p.setFont(fonte(8, QFont.DemiBold))
        p.setPen(COR_CINZA)
        largura_rotulo = QFontMetrics(p.font()).horizontalAdvance(rotulo) + 6
        p.drawText(x, y, largura_rotulo, 18, Qt.AlignLeft | Qt.AlignVCenter, rotulo)
        p.setFont(fonte(10, QFont.Bold))
        p.setPen(cor_valor or QColor(255, 255, 255))
        p.drawText(x + largura_rotulo, y, 110, 18, Qt.AlignLeft | Qt.AlignVCenter, valor)

    def _cabecalho(self, p, rel):
        temp = rel.get("pista_temp")
        self._rotulo_valor(p, 14, 5, "PISTA", f"{temp:.0f}°C" if temp is not None else "--")
        sof = rel.get("sof")
        self._rotulo_valor(p, 130, 5, "SOF", fmt_irating(sof) if sof else "--")
        inc = f"{rel.get('inc', 0)}x"
        if rel.get("inc_limite"):
            inc += f"/{rel['inc_limite']}"
        self._rotulo_valor(p, 235, 5, "INC", inc)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawLine(14, ALTURA_CAB - 1, LARGURA_REL - 14, ALTURA_CAB - 1)

    def _rodape(self, p, rel):
        y = ALTURA_CAB + (SLOTS_FRENTE + 1 + SLOTS_TRAS) * ALTURA_LINHA
        if self._com_projecao():
            y += ALTURA_PROJECAO
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawLine(14, y, LARGURA_REL - 14, y)
        self._rotulo_valor(p, 14, y + 4, "VOLTA", str(rel.get("volta", 0)))
        if rel.get("tempo_restante") is not None:
            rotulo, valor = "RESTA", fmt_relogio(rel["tempo_restante"])
        elif rel.get("voltas_restantes") is not None:
            rotulo, valor = "RESTAM", f"{rel['voltas_restantes']} voltas"
        else:
            return
        p.setFont(fonte(8, QFont.DemiBold))
        largura_rotulo = QFontMetrics(p.font()).horizontalAdvance(rotulo) + 6
        p.setFont(fonte(10, QFont.Bold))
        largura_valor = QFontMetrics(p.font()).horizontalAdvance(valor)
        self._rotulo_valor(p, LARGURA_REL - 14 - largura_rotulo - largura_valor, y + 4, rotulo, valor)

    def _linha(self, p, y, d):
        h = ALTURA_LINHA
        if d["eu"]:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(176, 140, 42, 235) if TEMA["moderno"] else QColor(45, 90, 190, 235))
            p.drawRoundedRect(6, y + 1, LARGURA_REL - 12, h - 2, 5, 5)
        # Carros de outras classes ficam mais discretos
        p.setOpacity(1.0 if (d["eu"] or d["mesma_classe"]) else 0.6)

        # Faixa com a cor da classe
        cor_classe = QColor(*d["classe_cor"])
        p.setPen(Qt.NoPen)
        p.setBrush(cor_classe)
        p.drawRect(12, y + 4, 4, h - 8)

        # Posicao na classe
        p.setFont(fonte(10, QFont.Bold))
        p.setPen(COR_TEXTO)
        p.drawText(20, y, 24, h, Qt.AlignRight | Qt.AlignVCenter,
                   str(d["pos_classe"]) if d["pos_classe"] else "-")

        # Numero do carro (na cor da classe)
        p.setPen(cor_classe.lighter(120))
        p.drawText(48, y, 40, h, Qt.AlignLeft | Qt.AlignVCenter, f"#{d['numero']}")

        # Pneu: tipo (barra inclinada na cor do composto) e voltas desde a ultima parada
        self._pneu(p, 90, y, d)

        # Nome (vermelho: uma volta a frente de voce; azul: uma volta atras de voce)
        fonte_nome = fonte(10, QFont.Bold)
        p.setFont(fonte_nome)
        if d["volta_rel"] > 0:
            p.setPen(QColor(255, 120, 120))
        elif d["volta_rel"] < 0:
            p.setPen(QColor(120, 175, 255))
        else:
            p.setPen(QColor(255, 255, 255))
        nome = QFontMetrics(fonte_nome).elidedText(d["nome"], Qt.ElideRight, 116)
        p.drawText(134, y, 118, h, Qt.AlignLeft | Qt.AlignVCenter, nome)

        # Licenca e iRating
        self._selo(p, 256, y, 46, d["lic"], QColor(*d["lic_cor"]))
        self._selo(p, 306, y, 44, fmt_irating(d["irating"]), QColor(255, 255, 255))

        # Distancia em segundos (ou BOX)
        p.setFont(fonte(10, QFont.Bold))
        if d["na_box"]:
            p.setPen(COR_LARANJA)
            texto = "BOX"
        else:
            p.setPen(COR_TEXTO)
            texto = f"{abs(d['gap']):.1f}"
        p.drawText(LARGURA_REL - 88, y, 76, h, Qt.AlignRight | Qt.AlignVCenter, texto)
        p.setOpacity(1.0)

    @staticmethod
    def _pneu(p, x, y, d):
        """Barra inclinada (cor = composto) + circulo com as voltas do pneu. Nada se nao houver dado."""
        pneu, voltas = d.get("pneu"), d.get("voltas_pneu")
        if not pneu and voltas is None:
            return
        cor = QColor(*pneu["cor"]) if pneu else QColor(150, 150, 160)
        h = ALTURA_LINHA
        p.setPen(Qt.NoPen)
        p.setBrush(cor)
        p.drawPolygon([QPoint(x + 4, y + 5), QPoint(x + 10, y + 5), QPoint(x + 6, y + h - 5), QPoint(x, y + h - 5)])
        if voltas is None:
            return
        confiavel = d.get("voltas_pneu_confiavel", True)
        cx, cy, r = x + 24, y + h // 2, 10
        p.setBrush(QColor(8, 8, 12, 200))
        p.setPen(QPen(QColor(cor.red(), cor.green(), cor.blue(), 255 if confiavel else 110), 1.5))
        p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)
        p.setPen(QColor(255, 255, 255) if confiavel else QColor(150, 150, 160))
        p.setFont(fonte(8, QFont.Bold))
        p.drawText(cx - r, cy - r, 2 * r, 2 * r, Qt.AlignCenter, str(voltas))

    @staticmethod
    def _selo(p, x, y, largura, texto, cor_fundo):
        altura = 18
        p.setPen(Qt.NoPen)
        p.setBrush(cor_fundo)
        p.drawRoundedRect(x, y + (ALTURA_LINHA - altura) // 2, largura, altura, 4, 4)
        luminosidade = 0.299 * cor_fundo.red() + 0.587 * cor_fundo.green() + 0.114 * cor_fundo.blue()
        p.setPen(QColor(20, 20, 25) if luminosidade > 150 else QColor(255, 255, 255))
        p.setFont(fonte(8, QFont.Bold))
        p.drawText(x, y + (ALTURA_LINHA - altura) // 2, largura, altura, Qt.AlignCenter, texto)


# ---- Janela 4: classificacao ---------------------------------------------------------
class JanelaClassificacao(JanelaBase):
    CHAVE = "classificacao"
    CHAVE_ATIVO = "mostrar_classificacao"
    TAXA_HZ = 2.0
    ALTURA_PADRAO = 170
    ALTURA_TOPO = 46  # barra superior + rotulos das colunas

    def __init__(self, config):
        self._blocos_atual = []
        self._altura_base = self.ALTURA_PADRAO
        super().__init__(config)

    def tamanho(self):
        return (LARGURA_CLASS, self._altura_base)

    def _blocos(self, classif):
        """Lista de (classe, [(linha, salto), ...]) com as linhas que cabem na tela."""
        todas = self.config.get("classificacao_todas", True)
        blocos = []
        for classe in classif["classes"]:
            if not todas and not classe["minha"]:
                continue
            linhas = classe["linhas"]
            i_eu = next((i for i, l in enumerate(linhas) if l["eu"]), None)
            if not todas:
                limite = MAX_LINHAS_MINHA_CLASSE + 4  # so a sua classe: mostra mais carros
            else:
                limite = MAX_LINHAS_MINHA_CLASSE if classe["minha"] else MAX_LINHAS_OUTRAS_CLASSES
            visiveis, anterior = [], None
            for k in selecionar_linhas(len(linhas), i_eu, limite):
                visiveis.append((linhas[k], anterior is not None and k != anterior + 1))
                anterior = k
            blocos.append((classe, visiveis))
        return blocos

    def _altura_necessaria(self):
        if not self._blocos_atual:
            return self.ALTURA_PADRAO
        linhas = sum(1 + len(v) for _, v in self._blocos_atual)
        return self.ALTURA_TOPO + linhas * ALTURA_LINHA_CLASS + 10

    def atualizar(self, dados):
        self.dados = dados
        classif = dados.get("classificacao") if dados["conectado"] else None
        self._blocos_atual = self._blocos(classif) if classif else []
        altura = self._altura_necessaria()
        if altura != self._altura_base:
            self._altura_base = altura
            self.aplicar_tamanho()
        self._repintar()

    def recalcular(self):
        self.atualizar(self.dados)

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        classif = d.get("classificacao")
        if not classif or not self._blocos_atual:
            p.setPen(COR_CINZA)
            p.setFont(fonte(12))
            p.drawText(self._retangulo_base(), Qt.AlignCenter, "Sem dados de classificacao")
            return
        self._barra_superior(p, classif)
        y = self.ALTURA_TOPO
        for classe, linhas in self._blocos_atual:
            self._cabecalho_classe(p, y, classe)
            y += ALTURA_LINHA_CLASS
            for linha, salto in linhas:
                self._linha(p, y, linha, salto, QColor(*classe["cor"]))
                y += ALTURA_LINHA_CLASS

    def _emblema(self, p, x, y, w, h, marca):
        caminho = achar_emblema(marca)
        pm = None
        if caminho is not None:
            caixa_l, caixa_a = w - 4, h - 6
            original = _carregar_pixmap(caminho)
            razao = min(caixa_l / float(original.width()), caixa_a / float(original.height()))
            tw, th = original.width() * razao, original.height() * razao
            pm = _pixmap_ajustado(caminho, round(tw * self.escala_x), round(th * self.escala_y))
        if pm is not None:
            ex, ey = x + (w - tw) / 2.0, y + (h - th) / 2.0
            p.drawPixmap(QRectF(ex, ey, tw, th), pm, QRectF(pm.rect()))
            return
        # sem emblema: iniciais em um selo discreto
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(62, 62, 78))
        p.drawRoundedRect(x, y + 4, w - 4, h - 8, 4, 4)
        p.setFont(fonte(7, QFont.Bold))
        p.setPen(QColor(210, 210, 222))
        p.drawText(x, y + 4, w - 4, h - 8, Qt.AlignCenter, abreviacao_marca(marca))

    def _pais(self, p, x, y, w, h, codigo):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(62, 62, 78))
        p.drawRoundedRect(x, y + 4, w, h - 8, 4, 4)
        iso2 = _ISO2.get(codigo)
        pm = None
        if iso2:
            caminho = PASTA_BANDEIRAS / f"{iso2}.png"
            if caminho.is_file():
                pm = _pixmap_ajustado(caminho, round(20 * self.escala_x), round(15 * self.escala_y))
        p.setFont(fonte(8, QFont.Bold))
        p.setPen(QColor(210, 210, 222))
        if pm is None:
            p.drawText(x, y + 4, w, h - 8, Qt.AlignCenter, codigo)
            return
        fx, fy = x + 6, y + (h - 15) / 2.0
        caminho_recorte = QPainterPath()
        caminho_recorte.addRoundedRect(QRectF(fx, fy, 20, 15), 2.5, 2.5)
        p.save()
        p.setClipPath(caminho_recorte)
        p.drawPixmap(QRectF(fx, fy, 20, 15), pm, QRectF(pm.rect()))
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 70), 1))
        p.drawRoundedRect(QRectF(fx, fy, 20, 15), 2.5, 2.5)
        p.setPen(QColor(210, 210, 222))
        p.drawText(x + 30, y + 4, w - 32, h - 8, Qt.AlignCenter, codigo)

    def _barra_superior(self, p, classif):
        p.setFont(fonte(8, QFont.DemiBold))
        p.setPen(COR_CINZA)
        p.drawText(14, 5, 110, 18, Qt.AlignLeft | Qt.AlignVCenter, "CLASSIFICACAO")
        tipo = classif.get("tipo_sessao")
        if tipo:
            p.setFont(fonte(10, QFont.Bold))
            p.setPen(QColor(255, 255, 255))
            p.drawText(122, 5, 160, 18, Qt.AlignLeft | Qt.AlignVCenter, tipo)
        total = sum(c["n_carros"] for c in classif["classes"])
        p.setFont(fonte(8, QFont.DemiBold))
        p.setPen(COR_CINZA)
        p.drawText(LARGURA_CLASS - 14 - 200, 5, 200, 18, Qt.AlignRight | Qt.AlignVCenter, f"{total} CARROS")

        # Rotulos das colunas
        p.setFont(fonte(7, QFont.DemiBold))
        y = 26
        p.drawText(20, y, 26, 16, Qt.AlignRight | Qt.AlignVCenter, "P")
        p.drawText(50, y, 38, 16, Qt.AlignLeft | Qt.AlignVCenter, "#")
        p.drawText(88, y, 38, 16, Qt.AlignCenter, "CARRO")
        p.drawText(132, y, 140, 16, Qt.AlignLeft | Qt.AlignVCenter, "PILOTO")
        p.drawText(278, y, 70, 16, Qt.AlignCenter, "PAIS")
        p.drawText(354, y, 76, 16, Qt.AlignRight | Qt.AlignVCenter, "ULTIMA")
        p.drawText(436, y, 82, 16, Qt.AlignRight | Qt.AlignVCenter, "MELHOR")
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawLine(14, 43, LARGURA_CLASS - 14, 43)

    def _cabecalho_classe(self, p, y, classe):
        h = ALTURA_LINHA_CLASS
        cor = QColor(*classe["cor"])
        fundo = QColor(cor)
        fundo.setAlpha(70)
        p.setPen(Qt.NoPen)
        p.setBrush(fundo)
        p.drawRoundedRect(8, y + 2, LARGURA_CLASS - 16, h - 4, 5, 5)
        p.setBrush(cor)
        p.drawRect(8, y + 2, 4, h - 4)
        p.setFont(fonte(10, QFont.Bold))
        p.setPen(cor.lighter(125))
        p.drawText(20, y, 200, h, Qt.AlignLeft | Qt.AlignVCenter, classe["nome"])
        partes = []
        if classe["sof"]:
            partes.append(f"SOF {fmt_irating(classe['sof'])}")
        partes.append(f"{classe['n_carros']} CARROS")
        p.setFont(fonte(8, QFont.DemiBold))
        p.setPen(COR_TEXTO)
        p.drawText(LARGURA_CLASS - 20 - 240, y, 240, h, Qt.AlignRight | Qt.AlignVCenter, "   ".join(partes))

    def _linha(self, p, y, d, salto, cor_classe):
        h = ALTURA_LINHA_CLASS
        if salto:  # indica que existem carros omitidos acima desta linha
            p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.DotLine))
            p.drawLine(20, y, LARGURA_CLASS - 20, y)
        if d["eu"]:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(176, 140, 42, 235) if TEMA["moderno"] else QColor(45, 90, 190, 235))
            p.drawRoundedRect(6, y + 1, LARGURA_CLASS - 12, h - 2, 5, 5)

        # Faixa da classe, posicao e numero
        p.setPen(Qt.NoPen)
        p.setBrush(cor_classe)
        p.drawRect(12, y + 4, 4, h - 8)
        p.setFont(fonte(10, QFont.Bold))
        p.setPen(COR_TEXTO)
        p.drawText(20, y, 26, h, Qt.AlignRight | Qt.AlignVCenter, str(d["pos"]))
        p.setPen(cor_classe.lighter(120))
        p.drawText(50, y, 38, h, Qt.AlignLeft | Qt.AlignVCenter, f"#{d['numero']}")

        # Emblema da marca (ou iniciais, enquanto nao houver imagem na pasta "emblemas")
        self._emblema(p, 92, y, 34, h, d["marca"])

        # Piloto
        fonte_nome = fonte(10, QFont.Bold)
        p.setFont(fonte_nome)
        p.setPen(QColor(255, 255, 255))
        nome = QFontMetrics(fonte_nome).elidedText(d["nome"], Qt.ElideRight, 136)
        p.drawText(132, y, 140, h, Qt.AlignLeft | Qt.AlignVCenter, nome)

        # Nacionalidade: bandeira + codigo do pais
        self._pais(p, 278, y, 70, h, d["pais"])

        # Ultima volta (verde = igual a sua melhor) e melhor volta (roxo = melhor da classe)
        p.setFont(fonte(10, QFont.Bold))
        if d["ultima"] is None:
            p.setPen(COR_CINZA)
        else:
            p.setPen(COR_VERDE if d["pb"] else QColor(255, 255, 255))
        p.drawText(354, y, 76, h, Qt.AlignRight | Qt.AlignVCenter, fmt_tempo(d["ultima"]))
        if d["melhor"] is None:
            p.setPen(COR_CINZA)
        else:
            p.setPen(QColor(190, 130, 255) if d["melhor_da_classe"] else QColor(255, 255, 255))
        p.drawText(436, y, 82, h, Qt.AlignRight | Qt.AlignVCenter, fmt_tempo(d["melhor"]))



# ---- Janela 5: mapa da pista ---------------------------------------------------------
class JanelaMapa(JanelaBase):
    CHAVE = "mapa"
    CHAVE_ATIVO = "mostrar_mapa"
    TAXA_HZ = 10.0

    def __init__(self, config):
        self._geo = None  # (versao, pontos na tela, caminho)
        super().__init__(config)

    def tamanho(self):
        return (LARGURA_MAPA, ALTURA_MAPA)

    def _geometria(self, mapa):
        versao = mapa.get("versao")
        if self._geo is not None and self._geo[0] == versao:
            return self._geo
        pontos = mapa["pontos"]
        validos = [q for q in pontos if q is not None]
        xs, ys = [q[0] for q in validos], [q[1] for q in validos]
        largura = max(xs) - min(xs) or 1.0
        altura = max(ys) - min(ys) or 1.0
        margem = 22
        area_l, area_a = LARGURA_MAPA - 2 * margem, ALTURA_MAPA - 2 * margem - 10
        escala = min(area_l / largura, area_a / altura)
        ox = margem + (area_l - largura * escala) / 2.0 - min(xs) * escala
        oy = margem + (area_a - altura * escala) / 2.0 + max(ys) * escala  # norte para cima
        tela = [None if q is None else (ox + q[0] * escala, oy - q[1] * escala) for q in pontos]
        caminho = QPainterPath()
        novo_trecho = True
        for q in tela:
            if q is None:
                novo_trecho = True
                continue
            if novo_trecho:
                caminho.moveTo(*q)
                novo_trecho = False
            else:
                caminho.lineTo(*q)
        if mapa.get("completo"):
            caminho.closeSubpath()
        self._geo = (versao, tela, caminho)
        return self._geo

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        mapa = d.get("mapa")
        if not mapa or not mapa.get("pontos") or not any(q is not None for q in mapa["pontos"]):
            p.setPen(COR_CINZA)
            p.setFont(fonte(10))
            texto = "Mapa da pista\nDirija uma volta completa\npara o overlay aprender o tracado"
            p.drawText(self._retangulo_base(), Qt.AlignCenter, texto)
            return
        _, tela, caminho = self._geometria(mapa)
        completo = mapa.get("completo")

        # pista: contorno claro + miolo escuro
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(240, 240, 245, 230 if completo else 120), 11, Qt.SolidLine,
                      Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(caminho)
        p.setPen(QPen(QColor(24, 24, 30), 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(caminho)

        # linha de largada/chegada
        if completo and tela[0] is not None and tela[1] is not None:
            (x0, y0), (x1, y1) = tela[0], tela[1]
            dx, dy = x1 - x0, y1 - y0
            norma = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / norma * 9, dx / norma * 9
            p.setPen(QPen(QColor(255, 255, 255), 3))
            p.drawLine(int(x0 - nx), int(y0 - ny), int(x0 + nx), int(y0 + ny))

        if not completo:
            progresso = int(mapa.get("progresso", 0.0) * 100)
            p.setPen(QColor(250, 200, 40))
            p.setFont(fonte(9, QFont.DemiBold))
            p.drawText(0, ALTURA_MAPA - 24, LARGURA_MAPA, 18, Qt.AlignCenter,
                       f"Aprendendo o tracado... {progresso}% (complete uma volta)")
            return

        # carros
        carros = mapa.get("carros") or []
        raio = 6 if len(carros) > 24 else 8
        n = len(tela)
        p.setFont(fonte(6 if raio == 6 else 7, QFont.Bold))
        for c in carros:
            pos = c["pct"] * n
            i0 = int(pos) % n
            i1 = (i0 + 1) % n
            a, b = tela[i0], tela[i1]
            if a is None or b is None:
                continue
            f = pos - int(pos)
            x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            if c["eu"]:
                r = raio + 3
                p.setPen(QPen(QColor(255, 255, 255), 2))
                p.setBrush(QColor(255, 220, 0))
                texto_cor = QColor(20, 20, 25)
            else:
                r = raio
                p.setPen(QPen(QColor(15, 15, 20), 1))
                cor = tuple(c["cor"])[:3]
                p.setBrush(QColor(*cor))
                luminosidade = 0.299 * cor[0] + 0.587 * cor[1] + 0.114 * cor[2]
                texto_cor = QColor(20, 20, 25) if luminosidade > 140 else QColor(255, 255, 255)
            p.drawEllipse(int(x - r), int(y - r), 2 * r, 2 * r)
            p.setPen(texto_cor)
            p.drawText(int(x - r - 4), int(y - r), 2 * r + 8, 2 * r, Qt.AlignCenter, str(c["numero"])[:3])


# ---- Janela 6: radar de proximidade ----------------------------------------------------
class JanelaRadar(JanelaBase):
    CHAVE = "radar"
    CHAVE_ATIVO = "mostrar_radar"
    TAXA_HZ = 30.0
    ALTURA_RODAPE = 54

    # cores por urgencia: 0 normal, 1 atencao (so aproximacao longitudinal), 2 sem uso (Fase 20.1), 3 ocupacao lateral SDK
    CORES = (QColor(232, 232, 238), QColor(255, 205, 60), QColor(255, 120, 40), QColor(255, 55, 55))

    def tamanho(self):
        return (LARGURA_RADAR, ALTURA_RADAR)

    @staticmethod
    def _rotulo_metros(p, c, x, y, larg, cor, largura_janela, ocupados):
        """Distancia (para-choque a para-choque) escrita ao lado do carro: a esquerda dos carros da
        esquerda e a direita dos carros da direita e do centro. Se o texto bater em outro carro ou
        rotulo, sobe/desce um pouco para continuar legivel."""
        faixa = c.get("faixa", 0.0)
        if abs(faixa) < 0.5 and abs(c["dist"]) > 12.0:
            return                                    # carro distante na sua linha: ja esta no rodape
        gap = c.get("gap", 0.0)
        if gap >= 0.05:
            seta = "\u25B2 " if c["dist"] > 0 else "\u25BC "   # carro a frente / atras de voce
        else:
            seta = ""                                  # lado a lado (sobreposto)
        texto = f"{seta}{fmt_dist_aprox(gap)}"
        fnt = fonte(8, QFont.Bold)
        p.setFont(fnt)
        larg_txt = QFontMetrics(fnt).horizontalAdvance(texto) + 2
        alt_txt = 14.0
        esquerda = faixa <= -0.5
        x_txt = x - larg / 2 - 4 - larg_txt if esquerda else x + larg / 2 + 4
        x_txt = max(2.0, min(largura_janela - larg_txt - 2.0, x_txt))
        ret = QRectF(x_txt, y - alt_txt / 2, larg_txt, alt_txt)
        for desvio in (0.0, alt_txt, -alt_txt, 2 * alt_txt, -2 * alt_txt):
            candidato = ret.translated(0.0, desvio)
            if not any(candidato.intersects(o) for o in ocupados):
                ret = candidato
                break
        ocupados.append(ret)
        alinhamento = (Qt.AlignRight if esquerda else Qt.AlignLeft) | Qt.AlignVCenter
        p.setPen(QColor(0, 0, 0, 190))                # sombra para ler sobre o brilho vermelho
        p.drawText(ret.translated(1, 1), alinhamento, texto)
        urgencia = c.get("urgencia", 0)
        # ao lado (vermelho sobre o brilho vermelho) -> branco; atencao/perigo -> cor da urgencia
        p.setPen(QColor(255, 255, 255) if urgencia >= 3 else (cor if urgencia >= 1 else QColor(235, 235, 240)))
        p.drawText(ret, alinhamento, texto)

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"], "Radar"):
            return
        radar = d.get("radar")
        w, h = LARGURA_RADAR, ALTURA_RADAR - self.ALTURA_RODAPE
        cx, cy = w / 2.0, h / 2.0
        escala = (h - 20) / (2.0 * ALCANCE_RADAR)  # pixels por metro

        # faixa da pista e marcas de distancia (a cada 10 m)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 14))
        p.drawRect(int(cx - 5.5 * escala), 10, int(11 * escala), int(h - 20))
        p.setPen(QPen(QColor(255, 255, 255, 45), 1, Qt.DashLine))
        for metros in (-ALCANCE_RADAR / 2, ALCANCE_RADAR / 2):
            y = int(cy - metros * escala)
            p.drawLine(int(cx - 5.5 * escala), y, int(cx + 5.5 * escala), y)

        if radar is None:
            p.setPen(COR_CINZA)
            p.setFont(fonte(8))
            p.drawText(0, h - 22, w, 16, Qt.AlignCenter, "sem dados de carros")
        else:
            # brilho lateral onde ha carro ao lado
            for lado, n in ((-1, radar["esq"]), (1, radar["dir"])):
                if n <= 0:
                    continue
                x_borda = 2 if lado < 0 else w - 2
                grad = QRadialGradient(x_borda, cy, 95)
                grad.setColorAt(0.0, QColor(255, 30, 30, 215 if n == 1 else 245))
                grad.setColorAt(0.55, QColor(255, 30, 30, 110))
                grad.setColorAt(1.0, QColor(255, 30, 30, 0))
                p.setPen(Qt.NoPen)
                p.setBrush(grad)
                p.drawRect(0, int(cy - 95), w, 190)
            # o SDK acusou carro ao lado, mas nenhum carro bate com a posicao: avisa sem inventar posicao
            sem_par = radar.get("sem_par") or (0, 0)
            p.setFont(fonte(7, QFont.Bold))
            p.setPen(QColor(255, 255, 255, 230))
            if sem_par[0] > 0:
                p.drawText(4, int(cy) - 8, 40, 14, Qt.AlignLeft | Qt.AlignVCenter, "SDK")
            if sem_par[1] > 0:
                p.drawText(w - 44, int(cy) - 8, 40, 14, Qt.AlignRight | Qt.AlignVCenter, "SDK")
            # brilho frontal/traseiro quando um carro se aproxima rapido
            for chave, sinal in (("tras", 1), ("frente", -1)):
                r = radar.get(chave)
                # ambar = "chegando" (so longitudinal, NAO e previsao de colisao); vermelho so com ocupacao SDK
                if r and r["urgencia"] >= 1 and r["aprox"] > 1.0 and abs(r["dist"]) <= ALCANCE_RADAR:
                    y_borda = h - 4 if sinal > 0 else 4
                    grad = QRadialGradient(cx, y_borda, 80)
                    cor = self.CORES[r["urgencia"]]
                    grad.setColorAt(0.0, QColor(cor.red(), cor.green(), cor.blue(), 200))
                    grad.setColorAt(1.0, QColor(cor.red(), cor.green(), cor.blue(), 0))
                    p.setPen(Qt.NoPen)
                    p.setBrush(grad)
                    p.drawRect(0, int(y_borda - 80), w, 160)

            # outros carros
            comp, larg = COMPR_CARRO * escala, 2.0 * escala
            ocupados, pendentes = [], []     # retangulos dos carros e rotulos de metros a desenhar
            for c in sorted(radar["carros"], key=lambda q: q.get("urgencia", 0)):
                if abs(c["dist"]) > ALCANCE_RADAR:
                    continue
                x = cx + c["faixa"] * FAIXA_LATERAL * escala
                y = cy - c["dist"] * escala
                cor = self.CORES[c.get("urgencia", 0)]
                origem = c.get("lado_fonte", "indef")
                if origem == "lembrado":                 # lado lembrado (<= 3 s): translucido e tracejado
                    p.setPen(QPen(cor, 1, Qt.DashLine))
                    p.setBrush(QColor(cor.red(), cor.green(), cor.blue(), 90))
                elif origem == "indef" and abs(c["dist"]) <= ZONA_LATERAL:   # lado desconhecido e muito perto
                    p.setPen(QPen(cor, 1, Qt.DotLine))
                    p.setBrush(QColor(cor.red(), cor.green(), cor.blue(), 120))
                elif origem == "inferido" and c.get("ident") == "ambigua":   # ocupacao SDK, mas ha mais de um candidato
                    p.setPen(QPen(cor, 1, Qt.DashDotLine))
                    p.setBrush(cor)
                else:                                    # ocupacao SDK (carro inferido) ou longe, na sua linha
                    p.setPen(Qt.NoPen)
                    p.setBrush(cor)
                p.drawRoundedRect(int(x - larg / 2), int(y - comp / 2), int(larg), int(comp), 3, 3)
                p.setPen(Qt.NoPen)
                p.setBrush(cor)
                ocupados.append(QRectF(x - larg / 2, y - comp / 2, larg, comp))
                # seta indicando que o carro esta se aproximando
                if c.get("aprox", 0.0) > 2.0 and abs(c["dist"]) > 2.5:
                    sentido = 1 if c["dist"] > 0 else -1   # aponta para voce: a frente = para baixo
                    ponta = y + sentido * (comp / 2 + 7)
                    base = y + sentido * (comp / 2 + 1)
                    seta = QPainterPath()
                    seta.moveTo(x, base)
                    seta.lineTo(x - 4, ponta)
                    seta.lineTo(x + 4, ponta)
                    seta.closeSubpath()
                    p.setBrush(QColor(cor.red(), cor.green(), cor.blue(), 190))
                    p.drawPath(seta)
                pendentes.append((c, x, y, cor))

            # metros ao lado de cada carro (por ultimo, para ficarem por cima dos brilhos)
            ocupados.append(QRectF(cx - 1.0 * escala, cy - COMPR_CARRO / 2 * escala,
                                   2.0 * escala, COMPR_CARRO * escala))
            for c, x, y, cor in pendentes:
                self._rotulo_metros(p, c, x, y, larg, cor, w, ocupados)

        # o seu carro (verde), no centro
        p.setBrush(QColor(60, 200, 90))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(int(cx - 1.0 * escala), int(cy - COMPR_CARRO / 2 * escala), int(2.0 * escala),
                          int(COMPR_CARRO * escala), 3, 3)

        # rodape: distancia (para-choque a para-choque) ao carro mais proximo a frente e atras
        base_y = ALTURA_RADAR - self.ALTURA_RODAPE
        p.setPen(QColor(150, 150, 165))
        p.setFont(fonte(6, QFont.DemiBold))
        p.drawText(8, base_y + 40, w - 16, 12, Qt.AlignCenter,
                   "ocup. lateral SDK  \u00b7  carro/dist. ~ estimado")
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawLine(12, base_y, w - 12, base_y)
        for k, (rotulo, chave) in enumerate((("FRENTE", "frente"), ("ATRAS", "tras"))):
            x0 = 10 + k * (w // 2)
            larg_col = w // 2 - 14
            r = radar.get(chave) if radar else None
            p.setPen(COR_CINZA)
            p.setFont(fonte(7, QFont.DemiBold))
            p.drawText(x0, base_y + 3, larg_col, 12, Qt.AlignLeft | Qt.AlignVCenter, rotulo)
            if r is None or r["gap"] > 60:
                p.setPen(COR_CINZA)
                p.setFont(fonte(13, QFont.Bold))
                p.drawText(x0, base_y + 14, larg_col, 22, Qt.AlignLeft | Qt.AlignVCenter, "--")
                continue
            p.setPen(self.CORES[r["urgencia"]])
            p.setFont(fonte(13, QFont.Bold))
            p.drawText(x0, base_y + 14, larg_col, 22, Qt.AlignLeft | Qt.AlignVCenter, fmt_dist_aprox(r["gap"]))
            if r["aprox"] > 1.0:
                p.setPen(COR_CINZA)
                p.setFont(fonte(7))
                p.drawText(x0, base_y + 3, larg_col, 12, Qt.AlignRight | Qt.AlignVCenter,
                           f"+{r['aprox'] * 3.6:.0f} km/h")
                if r["alcance_s"] is not None and r["alcance_s"] < 9.9:
                    p.setFont(fonte(8, QFont.DemiBold))
                    p.drawText(x0, base_y + 17, larg_col, 18, Qt.AlignRight | Qt.AlignVCenter,
                               f"~{r['alcance_s']:.1f} s")


# ---- Janela 8: setores vs melhor volta ---------------------------------------------------
class JanelaSetores(JanelaBase):
    CHAVE = "setores"
    CHAVE_ATIVO = "mostrar_setores"
    TAXA_HZ = 4.0
    COR_ROXO = QColor(200, 120, 255)

    def __init__(self, config):
        self._n = 3
        super().__init__(config)

    @staticmethod
    def altura_para(n):
        return ALTURA_TOPO_SETORES + n * ALTURA_LINHA_SETOR + 14 + 3 * ALTURA_LINHA_SETOR + 22

    def tamanho(self):
        return (LARGURA_SETORES, self.altura_para(self._n))

    def atualizar(self, dados):
        self.dados = dados
        st = dados.get("setores") if dados["conectado"] else None
        n = st["n"] if st else self._n
        if n != self._n:
            self._n = n
            self.aplicar_tamanho()
        self._repintar()

    @staticmethod
    def _cor_delta(delta):
        if delta is None:
            return COR_CINZA
        return COR_VERDE if delta < -0.004 else (COR_VERMELHO if delta > 0.004 else QColor(255, 255, 255))

    def _linha(self, p, y, rotulo, tempo, delta, roxo=False, ao_vivo=False, mostrar_delta=True):
        h = ALTURA_LINHA_SETOR
        p.setFont(fonte(11, QFont.Bold))
        p.setPen(COR_AMARELO)
        p.drawText(16, y, 110, h, Qt.AlignLeft | Qt.AlignVCenter, rotulo)
        p.setPen(COR_CINZA if tempo is None else (self.COR_ROXO if roxo else QColor(255, 255, 255)))
        p.drawText(112, y, 98, h, Qt.AlignRight | Qt.AlignVCenter, fmt_setor(tempo) if tempo is not None else "--")
        if mostrar_delta:
            p.setPen(self._cor_delta(delta))
            p.drawText(214, y, 70, h, Qt.AlignRight | Qt.AlignVCenter,
                       f"{delta:+.2f}" if delta is not None else "")

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        st = d.get("setores")
        if not st:
            p.setPen(COR_CINZA)
            p.setFont(fonte(11))
            p.drawText(self._retangulo_base(), Qt.AlignCenter, "Sem dados de setores")
            return
        # titulo
        p.setFont(fonte(12, QFont.Bold))
        p.setPen(COR_AMARELO)
        p.drawText(16, 8, LARGURA_SETORES - 32, 22, Qt.AlignLeft | Qt.AlignVCenter, "VS MELHOR VOLTA")
        sub = " | ".join(x for x in (st.get("pista"), st.get("carro")) if x)
        fnt = fonte(8)
        p.setFont(fnt)
        p.setPen(COR_CINZA)
        p.drawText(16, 30, LARGURA_SETORES - 32, 14, Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(fnt).elidedText(sub, Qt.ElideRight, LARGURA_SETORES - 32))
        y = ALTURA_TOPO_SETORES
        for k, ln in enumerate(st["linhas"]):
            self._linha(p, y, f"Setor {k + 1}:", ln["tempo"], ln["delta"], ln["roxo"], ln["ao_vivo"])
            y += ALTURA_LINHA_SETOR
        p.setPen(QPen(QColor(255, 255, 255, 70), 1))
        p.drawLine(16, y + 5, LARGURA_SETORES - 16, y + 5)
        y += 10
        u = st.get("ultima")
        self._linha(p, y, "Ultima:", u["tempo"] if u else None, u["delta"] if u else None,
                    bool(u and u["roxo"]))
        y += ALTURA_LINHA_SETOR
        self._linha(p, y, "Melhor:", st.get("melhor"), None, mostrar_delta=False)
        y += ALTURA_LINHA_SETOR
        self._linha(p, y, "Otima:", st.get("otima"), None, mostrar_delta=False)
        if st.get("estimado") or st.get("melhor") is None:
            p.setFont(fonte(7))
            p.setPen(COR_CINZA)
            nota = ("setores iguais (o iRacing nao informou os setores)" if st.get("estimado")
                    else "complete 1 volta limpa para criar a referencia")
            p.drawText(16, int(self.altura_para(self._n)) - 16, LARGURA_SETORES - 32, 12,
                       Qt.AlignLeft | Qt.AlignVCenter, nota)


# ---- Janela 7: pneus (vida util e temperatura: leitura real + estimativa ao vivo) ----------
class JanelaPneus(JanelaBase):
    CHAVE = "pneus"
    CHAVE_ATIVO = "mostrar_pneus"
    TAXA_HZ = 2.0
    LARG_CARTAO, ALT_CARTAO = 170, 112
    NOMES = {"LF": "DIANTEIRO ESQ.", "RF": "DIANTEIRO DIR.", "LR": "TRASEIRO ESQ.", "RR": "TRASEIRO DIR."}

    def tamanho(self):
        return (LARGURA_PNEUS, ALTURA_PNEUS)

    @staticmethod
    def _cantos(pneus):
        """Dados por pneu: usa a estimativa ao vivo; sem ela, cai nas leituras reais (formato antigo)."""
        if not pneus:
            return {}, None
        est = pneus.get("est")
        if est:
            return est["cantos"], est
        cantos = {}
        for c in CANTOS_PNEUS:
            vida = pneus["vida"].get(c) if pneus.get("vida") else None
            cantos[c] = {"vida": (sum(vida) / 3.0) if vida else None, "tipo": "real", "temp": None,
                         "perda_volta": None, "voltas": 0}
        return cantos, None

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        pneus = d.get("pneus")
        cantos, est = self._cantos(pneus)
        ideal_min = float(self.config.get("pneu_temp_min", 80.0))
        ideal_max = float(self.config.get("pneu_temp_max", 105.0))
        posicoes = {"LF": (14, 10), "RF": (14 + self.LARG_CARTAO + 10, 10),
                    "LR": (14, 10 + self.ALT_CARTAO + 8), "RR": (14 + self.LARG_CARTAO + 10, 10 + self.ALT_CARTAO + 8)}
        for canto, (x, y) in posicoes.items():
            real = pneus["temp"].get(canto) if pneus and pneus.get("temp") else None
            ultima = (pneus.get("ultima") or {}).get(canto) if pneus else None
            self._cartao(p, x, y, canto, cantos.get(canto), real, ideal_min, ideal_max,
                         est is not None and est.get("pior") == canto, ultima)

        # rodape: resumo do pior pneu e origem dos dados
        p.setPen(COR_TEXTO)
        p.setFont(fonte(8, QFont.DemiBold))
        y_rod = ALTURA_PNEUS - 40
        if est:
            pior = est["pior"]
            v = cantos[pior]["vida"]
            linha = f"Pior: {self.NOMES[pior].title()} {v * 100:.0f}%"
            if v <= est["limite"]:
                linha += f"  |  abaixo do limite de {est['limite'] * 100:.0f}%"
            elif est.get("voltas_limite") is not None:
                linha += f"  |  limite de {est['limite'] * 100:.0f}% em ~{est['voltas_limite']:.0f} voltas"
            else:
                linha += "  |  medindo o ritmo (1a volta)"
        else:
            linha = "sem dados de pneus"
        p.drawText(14, y_rod, LARGURA_PNEUS - 28, 14, Qt.AlignLeft | Qt.AlignVCenter, linha)
        p.setPen(COR_CINZA)
        p.setFont(fonte(7))
        if est:
            origem = {"boxes": f"calibrado nos boxes ({est['n_cal']}x)", "1a volta": "ritmo da 1a volta",
                      "padrao": "sem calibracao ainda"}.get(est["origem"], "")
            nota = f"~ estimado pelo overlay ({origem}); valor real so nos boxes"
        else:
            nota = "o carro/serie pode nao informar dados de pneus"
        p.drawText(14, y_rod + 15, LARGURA_PNEUS - 28, 12, Qt.AlignLeft | Qt.AlignVCenter, nota)

    def _cartao(self, p, x, y, canto, info, temp_real, ideal_min, ideal_max, destaque=False, ultima=None):
        w, h = self.LARG_CARTAO, self.ALT_CARTAO
        pintar_superficie(p, QRectF(x, y, w, h), 8, cartao=True)
        if destaque:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 150, 40, 170), 1.5))
            p.drawRoundedRect(x, y, w, h, 8, 8)

        p.setPen(COR_CINZA)
        p.setFont(fonte(7, QFont.DemiBold))
        p.drawText(x + 10, y + 5, 100, 14, Qt.AlignLeft | Qt.AlignVCenter, self.NOMES[canto])
        t_est = info.get("temp") if info else None
        media = (sum(temp_real) / 3.0) if temp_real else None
        antiga = None                    # ultima leitura REAL (quando o jogo ja nao esta atualizando)
        if not temp_real and ultima and ultima.get("temp"):
            antiga = ultima["temp"]
        orig = nucleo.origem_pneu(temp_real, ultima, t_est, info)     # regra unica real x estimado (testada)
        if orig["temp_cabecalho"] == "real":
            p.setPen(QColor(*cor_temperatura(media, ideal_min, ideal_max)))
            p.setFont(fonte(10, QFont.Bold))
            p.drawText(x + w - 78, y + 3, 68, 18, Qt.AlignRight | Qt.AlignVCenter, f"{media:.0f}\u00b0C")
        elif orig["temp_cabecalho"] == "estimada":            # cabecalho: estimativa ao vivo, com "~"
            p.setPen(QColor(*cor_temperatura(t_est, ideal_min, ideal_max)))
            p.setFont(fonte(10, QFont.Bold))
            p.drawText(x + w - 78, y + 3, 68, 18, Qt.AlignRight | Qt.AlignVCenter, f"~{t_est:.0f}\u00b0C")

        # zonas da banda de rodagem (so quando o iRacing informa as 3 zonas); senao, bloco estimado
        faixa_l = (w - 20 - 8) / 3.0
        if orig["temp_corpo"] in ("real_ao_vivo", "real_antiga"):
            valores = temp_real or antiga
            rotulos = ("E", "M", "I") if canto in ("LF", "LR") else ("I", "M", "E")  # externa / meio / interna
            for i in range(3):
                bx = x + 10 + i * (faixa_l + 4)
                by = y + 24
                cor = QColor(*cor_temperatura(valores[i], ideal_min, ideal_max))
                if antiga is not None:
                    cor.setAlpha(110)                    # esmaecido: leitura antiga, nao e o valor de agora
                p.setPen(Qt.NoPen)
                p.setBrush(cor)
                p.drawRoundedRect(int(bx), by, int(faixa_l), 38, 6, 6)
                p.setPen(QColor(15, 15, 20) if antiga is None else QColor(235, 235, 240))
                p.setFont(fonte(12, QFont.Bold))
                p.drawText(int(bx), by, int(faixa_l), 38, Qt.AlignCenter, f"{valores[i]:.0f}")
                if antiga is None:
                    p.setPen(COR_CINZA)
                    p.setFont(fonte(7))
                    p.drawText(int(bx), by + 39, int(faixa_l), 11, Qt.AlignCenter, rotulos[i])
            if antiga is not None:                       # quando/onde foi a ultima leitura real
                local = ultima.get("local") or ""
                p.setPen(COR_AMARELO if (ultima.get("idade") or 0) > 600 else COR_CINZA)
                p.setFont(fonte(7))
                p.drawText(x + 10, y + 63, w - 20, 11, Qt.AlignCenter,
                           f"real, h\u00e1 {nucleo.fmt_idade_medicao(ultima.get('idade'))} ({ultima.get('hora') or '--'}"
                           + (f", {local}" if local else "") + ")")
        else:
            bw = w - 20
            if t_est is not None:
                cor, texto, cor_texto = QColor(*cor_temperatura(t_est, ideal_min, ideal_max)), f"~{t_est:.0f}\u00b0C", QColor(15, 15, 20)
            else:
                cor, texto, cor_texto = QColor(255, 255, 255, 25), "--", COR_CINZA
            p.setPen(Qt.NoPen)
            p.setBrush(cor)
            p.drawRoundedRect(x + 10, y + 24, bw, 38, 6, 6)
            p.setPen(cor_texto)
            p.setFont(fonte(14, QFont.Bold))
            p.drawText(x + 10, y + 24, bw, 38, Qt.AlignCenter, texto)
            p.setPen(COR_CINZA)
            p.setFont(fonte(7))
            p.drawText(x + 10, y + 63, bw, 11, Qt.AlignCenter, "temperatura estimada")

        # vida util
        yb = y + 82
        vida = info.get("vida") if info else None
        est_tag = orig["vida"] == "estimada"
        p.setPen(COR_CINZA)
        p.setFont(fonte(7, QFont.DemiBold))
        p.drawText(x + 10, yb - 3, 34, 14, Qt.AlignLeft | Qt.AlignVCenter, orig["rotulo_vida"])
        largura_barra = w - 10 - 44 - 52
        p.setPen(Qt.NoPen)
        p.setBrush(COR_FUNDO_BARRA)
        p.drawRoundedRect(x + 44, yb, largura_barra, 8, 4, 4)
        if vida is not None:
            v = max(0.0, min(1.0, vida))
            p.setBrush(QColor(*cor_vida(v)))
            p.drawRoundedRect(x + 44, yb, max(4, int(largura_barra * v)), 8, 4, 4)
            p.setPen(QColor(*cor_vida(v)))
            p.setFont(fonte(10, QFont.Bold))
            p.drawText(x + w - 56, yb - 5, 48, 18, Qt.AlignRight | Qt.AlignVCenter, f"{v * 100:.0f}%")
            # linha de baixo: ritmo de desgaste e idade do pneu
            perda, voltas = info.get("perda_volta"), info.get("voltas", 0)
            partes = []
            if perda:
                partes.append(f"-{perda * 100:.1f}%/volta")
            if voltas:
                partes.append(f"{voltas} volta" + ("s" if voltas != 1 else ""))
            if not est_tag:
                idade_v = (ultima or {}).get("vida_idade")
                partes.append("real, h\u00e1 " + nucleo.fmt_idade_medicao(idade_v) if idade_v is not None
                              else "leitura real")
            p.setPen(COR_CINZA)
            p.setFont(fonte(7))
            p.drawText(x + 10, y + 94, w - 20, 12, Qt.AlignLeft | Qt.AlignVCenter, "  |  ".join(partes))
        else:
            p.setPen(COR_CINZA)
            p.setFont(fonte(10, QFont.Bold))
            p.drawText(x + w - 56, yb - 5, 48, 18, Qt.AlignRight | Qt.AlignVCenter, "--")


# ---- Janela 9: clima e vento ------------------------------------------------------------------
def vento_relativo(vento_dir, rumo, vel):
    """Vento visto do carro. vento_dir = de ONDE ele vem (rad, horario a partir do norte); rumo = para
    onde o carro aponta (rad, horario). Retorna (angulo na tela, rad horario a partir do topo, para onde
    o vento SOPRA; componente em km/h, positivo = a favor/cauda, negativo = de frente)."""
    sopra = vento_dir + math.pi
    rel = sopra - rumo
    return rel, vel * math.cos(rel)


class JanelaClima(JanelaBase):
    CHAVE = "clima"
    CHAVE_ATIVO = "mostrar_clima"
    TAXA_HZ = 2.0
    COR_CIANO = QColor(70, 200, 235)

    def tamanho(self):
        return (LARGURA_CLIMA, ALTURA_CLIMA)

    # --- icones simples desenhados em vetor ---
    @staticmethod
    def _icone_pista(p, x, y):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(190, 190, 200))
        p.drawPolygon([QPoint(x + 8, y), QPoint(x + 24, y), QPoint(x + 32, y + 30), QPoint(x, y + 30)])
        p.setBrush(QColor(30, 30, 38))
        for k in range(3):
            p.drawRect(x + 15, y + 3 + k * 9, 2, 5)

    @staticmethod
    def _mini_pista(p, x, y):
        """Versao pequena (18 px) do icone da pista."""
        p.save()
        p.translate(x, y)
        p.scale(0.55, 0.55)
        JanelaClima._icone_pista(p, 0, 0)
        p.restore()

    @staticmethod
    def _icone_sol(p, x, y):
        cx, cy = x + 16, y + 16
        p.setPen(QPen(QColor(250, 190, 40), 2, Qt.SolidLine, Qt.RoundCap))
        for k in range(8):
            a = k * math.pi / 4
            p.drawLine(int(cx + 11 * math.cos(a)), int(cy + 11 * math.sin(a)),
                       int(cx + 15 * math.cos(a)), int(cy + 15 * math.sin(a)))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(250, 190, 40))
        p.drawEllipse(cx - 7, cy - 7, 14, 14)

    @staticmethod
    def _icone_neblina(p, x, y):
        p.setPen(QPen(QColor(190, 190, 200), 2, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(x + 4, y + 6, 14, 14, 90 * 16, 180 * 16)
        p.drawArc(x + 10, y + 2, 16, 18, 20 * 16, 160 * 16)
        p.drawArc(x + 20, y + 8, 10, 12, -90 * 16, 180 * 16)
        for k, (a, b) in enumerate(((2, 30), (6, 26), (10, 22))):
            p.drawLine(x + a, y + 24 + k * 4, x + b, y + 24 + k * 4)

    @staticmethod
    def _icone_vento(p, x, y):
        p.setPen(QPen(QColor(190, 190, 200), 2, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        for k, (comp, y0) in enumerate(((26, 6), (30, 14), (20, 22))):
            p.drawLine(x, y + y0, x + comp - 6, y + y0)
            p.drawArc(x + comp - 10, y + y0 - 8 if k != 2 else y + y0 - 4, 8, 8 if k != 2 else 8, 90 * 16, -200 * 16)

    def _cartao(self, p, y, h, titulo):
        pintar_superficie(p, QRectF(10, y, LARGURA_CLIMA - 20, h), 8, cartao=True, borda_classica=True)
        p.setPen(COR_CINZA)
        p.setFont(fonte(8, QFont.DemiBold))
        p.drawText(22, y + 6, 175, 16, Qt.AlignLeft | Qt.AlignVCenter, titulo)

    def _valor(self, p, y, icone, texto):
        icone(p, 24, y + 26)
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(20, QFont.DemiBold))
        p.drawText(68, y + 22, 120, 34, Qt.AlignLeft | Qt.AlignVCenter, texto)

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        c = d.get("clima") or {}
        fmt = lambda v, suf: f"{v:.0f}{suf}" if v is not None else "--"
        self._cartao(p, 10, 58, "TEMP. DA PISTA")
        self._valor(p, 10, self._icone_pista, fmt(c.get("pista"), "\u00baC"))
        self._cartao(p, 76, 58, "TEMP. DO AR")
        self._valor(p, 76, self._icone_sol, fmt(c.get("ar"), "\u00baC"))
        self._cartao(p, 142, 58, "NEBLINA")
        self._valor(p, 142, self._icone_neblina, fmt(c.get("neblina"), "%"))
        self._cartao_chuva(p, 208, c)
        self._cartao(p, 282, 234, "VENTO (VISTO DO CARRO)")
        self._bussola(p, 110, 282 + 22 + 66, 62, c)
        self._rodape_vento(p, 282 + 158, c)

    NIVEIS_PISTA = {1: "seca", 2: "quase seca", 3: "umida leve", 4: "umida", 5: "molhada",
                    6: "muito molhada", 7: "encharcada"}
    CEUS = {0: "ceu limpo", 1: "parc. nublado", 2: "nublado", 3: "encoberto"}

    @staticmethod
    def _icone_chuva(p, x, y):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(190, 190, 200))
        p.drawEllipse(x + 3, y + 8, 14, 12)
        p.drawEllipse(x + 11, y + 3, 15, 15)
        p.drawEllipse(x + 19, y + 9, 12, 11)
        p.drawRect(x + 9, y + 14, 16, 6)
        p.setPen(QPen(QColor(70, 200, 235), 2, Qt.SolidLine, Qt.RoundCap))
        for dx in (8, 16, 24):
            p.drawLine(x + dx, y + 24, x + dx - 3, y + 31)

    def _cartao_chuva(self, p, y, c):
        self._cartao(p, y, 66, "CHUVA")
        self._icone_chuva(p, 24, y + 26)
        chuva = c.get("chuva")
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(20, QFont.DemiBold))
        p.drawText(64, y + 22, 64, 40, Qt.AlignLeft | Qt.AlignVCenter, f"{chuva:.0f}%" if chuva is not None else "--")
        molhada = c.get("pista_molhada")
        pista = self.NIVEIS_PISTA.get(molhada) if molhada else None
        if pista:
            pista = "pista " + pista
        elif c.get("declarado_molhado"):
            pista = "pista molhada"
        tend = {"subindo": "subindo \u2191", "diminuindo": "diminuindo \u2193", "estavel": "estavel \u2192"}.get(
            c.get("tendencia_chuva"), "medindo...")
        if c.get("dinamico") is False:
            tend = "clima fixo"
        p.setFont(fonte(7, QFont.DemiBold))
        cor_pista = QColor(255, 255, 255) if (molhada or 0) >= 4 else COR_CINZA
        p.setPen(cor_pista)
        p.drawText(130, y + 24, 80, 16, Qt.AlignLeft | Qt.AlignVCenter, pista or "pista --")
        p.setPen(COR_AMARELO if c.get("tendencia_chuva") == "subindo" else COR_CINZA)
        p.drawText(130, y + 40, 80, 16, Qt.AlignLeft | Qt.AlignVCenter, tend)

    def _bussola(self, p, cx, cy, r, c):
        rumo = c.get("rumo")
        h = rumo if rumo is not None else 0.0
        p.setPen(QPen(QColor(255, 255, 255, 40), 1.5))
        p.setBrush(QColor(8, 8, 12, 235))
        p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)
        # marcas a cada 15 graus (giram com o rumo do carro: o carro fica sempre apontado para cima)
        for k in range(24):
            a = math.radians(k * 15) - h
            ri = r - (7 if k % 6 == 0 else 4)
            p.setPen(QPen(QColor(255, 255, 255, 110 if k % 6 == 0 else 55), 1))
            p.drawLine(int(cx + ri * math.sin(a)), int(cy - ri * math.cos(a)),
                       int(cx + (r - 1) * math.sin(a)), int(cy - (r - 1) * math.cos(a)))
        if rumo is not None:
            p.setFont(fonte(9, QFont.Bold))
            for letra, graus in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
                a = math.radians(graus) - h
                x, y = cx + (r - 17) * math.sin(a), cy - (r - 17) * math.cos(a)
                p.setPen(QColor(235, 90, 90) if letra == "N" else COR_CINZA)
                p.drawText(int(x - 9), int(y - 9), 18, 18, Qt.AlignCenter, letra)
        # carro (visto de cima, sempre apontado para cima)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(200, 200, 210))
        p.drawRoundedRect(cx - 7, cy - 15, 14, 30, 5, 5)
        p.setBrush(QColor(8, 8, 12))
        p.drawRoundedRect(cx - 5, cy - 8, 10, 7, 2, 2)
        p.drawRoundedRect(cx - 5, cy + 4, 10, 5, 2, 2)
        # seta do vento: aponta para onde o vento SOPRA, vindo da borda
        direcao = c.get("vento_dir")
        if direcao is None or c.get("vento_vel") is None or rumo is None:
            return
        if self.config.get("vento_invertido"):
            direcao += math.pi
        rel, _comp = vento_relativo(direcao, rumo, c["vento_vel"])
        ux, uy = math.sin(rel), -math.cos(rel)          # vetor unitario na tela (para onde sopra)
        px, py = -uy, ux
        mx, my = cx - ux * 0.52 * r, cy - uy * 0.52 * r  # meio da seta (do lado de onde o vento vem)
        comp = 22.0
        ponta = (mx + ux * comp, my + uy * comp)
        p.setBrush(self.COR_CIANO)
        p.drawPolygon([QPointF(*ponta),
                       QPointF(mx + px * 9 - ux * 4, my + py * 9 - uy * 4),
                       QPointF(mx - ux * 1, my - uy * 1),
                       QPointF(mx - px * 9 - ux * 4, my - py * 9 - uy * 4)])
        for k in range(1, 4):                              # rastro
            t = k * 8.0
            p.setBrush(QColor(70, 200, 235, 210 - k * 55))
            p.drawEllipse(QPointF(mx - ux * (t + 2), my - uy * (t + 2)), 3.2 - k * 0.6, 3.2 - k * 0.6)

    def _rodape_vento(self, p, y, c):
        self._icone_vento(p, 24, y + 14)
        v = c.get("vento_vel")
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(20, QFont.DemiBold))
        texto = f"{v:.1f}" if v is not None else "--"
        p.drawText(64, y + 4, 80, 40, Qt.AlignLeft | Qt.AlignVCenter, texto)
        larg = QFontMetrics(p.font()).horizontalAdvance(texto)
        p.setPen(COR_CINZA)
        p.setFont(fonte(8, QFont.DemiBold))
        p.drawText(64 + larg + 6, y + 4, 60, 40, Qt.AlignLeft | Qt.AlignVCenter, "KM/H")
        # componente: de frente (contra) ou a favor (cauda), e a velocidade do carro
        direcao, rumo = c.get("vento_dir"), c.get("rumo")
        linha = ""
        if v is not None and direcao is not None and rumo is not None:
            if self.config.get("vento_invertido"):
                direcao += math.pi
            _rel, comp = vento_relativo(direcao, rumo, v)
            if abs(comp) < 0.5:
                linha = "vento lateral"
            else:
                linha = f"{'a favor' if comp > 0 else 'de frente'} {abs(comp):.1f} km/h"
        p.setFont(fonte(7))
        p.setPen(COR_CINZA)
        p.drawText(22, y + 46, 100, 16, Qt.AlignLeft | Qt.AlignVCenter, linha)
        p.setPen(COR_TEXTO)
        p.drawText(112, y + 46, 76, 16, Qt.AlignRight | Qt.AlignVCenter, f"carro {c.get('vel_carro', 0.0):.0f} km/h")


# ---- Janela 10: danos do carro ----------------------------------------------------------------
def fmt_idade(seg):
    seg = max(0.0, float(seg))
    return f"ha {seg:.0f} s" if seg < 60 else f"ha {seg / 60:.0f} min"


class JanelaDanos(JanelaBase):
    CHAVE = "danos"
    CHAVE_ATIVO = "mostrar_danos"
    TAXA_HZ = 4.0
    NOMES_ZONA = {"F": "Frente", "T": "Traseira", "E": "Lado esquerdo", "D": "Lado direito", None: "Fora da pista"}
    NOMES_TIPO = {"contato": "contato com carro", "batida": "batida", "saida": "saida de pista",
                  "pancada": "pancada"}

    def tamanho(self):
        return (LARGURA_DANOS, ALTURA_DANOS)

    @staticmethod
    def cor_sev(sev):
        return {0: QColor(255, 255, 255, 30), 1: QColor(250, 200, 40), 2: QColor(255, 140, 40),
                3: QColor(235, 60, 60)}.get(sev, QColor(255, 255, 255, 30))

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        dn = d.get("danos")
        p.setPen(COR_CINZA)
        p.setFont(fonte(9, QFont.DemiBold))
        p.drawText(16, 8, 150, 20, Qt.AlignLeft | Qt.AlignVCenter, "DANOS DO CARRO")
        if not dn:
            p.setFont(fonte(9))
            p.drawText(16, 40, LARGURA_DANOS - 32, 20, Qt.AlignLeft | Qt.AlignVCenter, "Sem dados de danos")
            return
        inc, lim = dn.get("incidentes"), dn.get("limite")
        if inc is not None:
            txt = f"Incidentes {inc}" + (f" / {lim}" if lim else "")
            p.setPen(COR_AMARELO if (lim and inc >= 0.7 * lim) else COR_TEXTO)
            p.setFont(fonte(9, QFont.Bold))
            p.drawText(110, 8, LARGURA_DANOS - 126, 20, Qt.AlignRight | Qt.AlignVCenter, txt)

        # faixa de situacao
        reparo, opc, reboque = dn.get("reparo", 0.0), dn.get("reparo_opc", 0.0), dn.get("reboque", 0.0)
        zonas, eventos = dn.get("zonas", {}), dn.get("eventos", [])
        if reboque and reboque > 0:
            cor, texto = COR_VERMELHO, f"REBOQUE  {reboque:.0f} s"
        elif reparo and reparo > 0:
            cor, texto = COR_VERMELHO, f"REPARO OBRIGATORIO  {reparo:.0f} s"
        elif opc and opc > 0:
            cor, texto = COR_LARANJA, f"REPARO OPCIONAL  {opc:.0f} s"
        elif any(zonas.values()):
            cor, texto = COR_AMARELO, "IMPACTO REGISTRADO"
        else:
            cor, texto = COR_VERDE, "SEM DANO REGISTRADO"
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(cor.red(), cor.green(), cor.blue(), 60))
        p.drawRoundedRect(12, 34, LARGURA_DANOS - 24, 30, 8, 8)
        p.setPen(cor)
        p.setFont(fonte(10, QFont.Bold))
        p.drawText(12, 34, LARGURA_DANOS - 24, 30, Qt.AlignCenter, texto)

        # carro visto de cima, com as 4 zonas de impacto
        cx, cy = 78, 160
        sev = lambda z: zonas.get(z, 0)
        p.setPen(Qt.NoPen)
        p.setBrush(self.cor_sev(sev("F")))
        p.drawRoundedRect(cx - 28, cy - 80, 56, 18, 8, 8)
        p.setBrush(self.cor_sev(sev("T")))
        p.drawRoundedRect(cx - 28, cy + 62, 56, 18, 8, 8)
        p.setBrush(self.cor_sev(sev("E")))
        p.drawRoundedRect(cx - 50, cy - 52, 16, 104, 8, 8)
        p.setBrush(self.cor_sev(sev("D")))
        p.drawRoundedRect(cx + 34, cy - 52, 16, 104, 8, 8)
        p.setBrush(QColor(95, 95, 108))
        p.drawRoundedRect(cx - 28, cy - 62, 56, 124, 18, 18)
        p.setBrush(QColor(14, 14, 20))
        p.drawRoundedRect(cx - 19, cy - 32, 38, 18, 5, 5)       # parabrisa
        p.drawRoundedRect(cx - 19, cy + 24, 38, 12, 4, 4)       # vidro traseiro
        p.setBrush(QColor(60, 60, 70))
        for dx in (-34, 24):
            for dy in (-50, 32):
                p.drawRoundedRect(cx + dx, cy + dy, 10, 20, 3, 3)  # rodas
        p.setPen(COR_CINZA)
        p.setFont(fonte(7))
        p.drawText(cx - 40, cy - 98, 80, 12, Qt.AlignCenter, "FRENTE")

        # coluna da direita: reparos
        def item(y, rotulo, valor, cor_v=COR_TEXTO):
            p.setPen(COR_CINZA)
            p.setFont(fonte(7, QFont.DemiBold))
            p.drawText(150, y, 100, 12, Qt.AlignLeft | Qt.AlignVCenter, rotulo)
            p.setPen(cor_v)
            p.setFont(fonte(13, QFont.Bold))
            p.drawText(150, y + 12, 100, 22, Qt.AlignLeft | Qt.AlignVCenter, valor)
        item(78, "REPARO OBRIGATORIO", f"{reparo:.0f} s" if reparo else "0 s", COR_VERMELHO if reparo else COR_TEXTO)
        item(122, "REPARO OPCIONAL", f"{opc:.0f} s" if opc else "0 s", COR_LARANJA if opc else COR_TEXTO)
        item(166, "REPAROS RAPIDOS", str(dn.get("rapidos", 0)))
        item(210, "IMPACTOS", str(dn.get("total", len(eventos))))

        # avisos do motor
        p.setPen(COR_CINZA)
        p.setFont(fonte(7, QFont.DemiBold))
        p.drawText(16, 262, 120, 12, Qt.AlignLeft | Qt.AlignVCenter, "MOTOR")
        avisos = dn.get("avisos") or []
        x = 62
        if not avisos:
            p.setPen(COR_VERDE)
            p.setFont(fonte(9, QFont.DemiBold))
            p.drawText(x, 260, 150, 16, Qt.AlignLeft | Qt.AlignVCenter, "sem avisos")
        yc = 259
        for nome in avisos:
            larg = QFontMetrics(fonte(8, QFont.Bold)).horizontalAdvance(nome) + 14
            if x + larg > LARGURA_DANOS - 12:           # quebra para a linha de baixo
                x, yc = 62, yc + 20
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(235, 60, 60, 190))
            p.drawRoundedRect(x, yc, larg, 17, 8, 8)
            p.setPen(QColor(255, 255, 255))
            p.setFont(fonte(8, QFont.Bold))
            p.drawText(x, yc, larg, 17, Qt.AlignCenter, nome)
            x += larg + 4

        # ultimos impactos
        p.setPen(COR_CINZA)
        p.setFont(fonte(7, QFont.DemiBold))
        p.drawText(16, 302, 150, 12, Qt.AlignLeft | Qt.AlignVCenter, "ULTIMOS IMPACTOS")
        if not eventos:
            p.setFont(fonte(9))
            p.drawText(16, 318, LARGURA_DANOS - 32, 18, Qt.AlignLeft | Qt.AlignVCenter, "nenhum nesta sessao")
        for i, e in enumerate(eventos[:3]):
            y = 318 + i * 26
            p.setPen(COR_CINZA)
            p.setFont(fonte(8))
            p.drawText(16, y, 56, 24, Qt.AlignLeft | Qt.AlignVCenter, fmt_idade(e.get("idade", 0.0)))
            p.setPen(COR_TEXTO)
            p.setFont(fonte(9, QFont.DemiBold))
            p.drawText(74, y, 110, 14, Qt.AlignLeft | Qt.AlignBottom, self.NOMES_ZONA.get(e.get("zona"), "--"))
            p.setPen(COR_CINZA)
            p.setFont(fonte(7))
            p.drawText(74, y + 13, 120, 11, Qt.AlignLeft | Qt.AlignTop, self.NOMES_TIPO.get(e.get("tipo"), ""))
            p.setPen(self.cor_sev(e.get("sev", 1)))
            p.setFont(fonte(11, QFont.Bold))
            g = e.get("g") or 0.0
            p.drawText(180, y, 66, 24, Qt.AlignRight | Qt.AlignVCenter, f"{g:.1f} g" if g else "--")

        p.setPen(COR_CINZA)
        p.setFont(fonte(7))
        p.drawText(16, ALTURA_DANOS - 24, LARGURA_DANOS - 32, 16, Qt.AlignLeft | Qt.AlignVCenter,
                   "Estimado; o iRacing nao informa dano por peca")


# ---- Janela 11: painel de combustivel e pit -----------------------------------------------------
class JanelaCombustivel(JanelaBase):
    CHAVE = "combustivel"
    CHAVE_ATIVO = "mostrar_combustivel"
    TAXA_HZ = 2.0
    COLUNAS = (("USO", 70), ("VOLTAS", 132), ("PARADAS", 198), ("REABAST.", 270), ("T.REABAST.", 346), ("ACABA", 434))
    N_BARRAS = 37

    def tamanho(self):
        return (LARGURA_COMB, ALTURA_COMB)

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        pn = d.get("painel_combustivel")
        if not pn:
            p.setPen(COR_CINZA)
            p.setFont(fonte(11))
            p.drawText(self._retangulo_base(), Qt.AlignCenter, "Sem dados de combust\u00edvel")
            return
        self._topo(p, pn)
        self._tabela(p, pn)
        self._barras_pit(p, pn)
        self._caixas(p, pn)
        self._ultimas(p, pn)
        p.setPen(COR_CINZA)
        p.setFont(fonte(7))
        p.drawText(14, ALTURA_COMB - 20, 500, 14, Qt.AlignLeft | Qt.AlignVCenter,
                   "* linha usada nos c\u00e1lculos (m\u00e9dia das \u00faltimas voltas limpas, sem box)")

    # ---- topo: janela de pit, litros a colocar e nivel do tanque ----
    def _topo(self, p, pn):
        jn = pn.get("janela")
        estado = jn["estado"] if jn else None
        if estado == "aberta":
            cor, titulo, sub = COR_VERDE, "ABERTA", f"V{jn['primeira']}-{jn['ultima']}"
        elif estado == "fechada":
            cor, titulo, sub = COR_LARANJA, "FECHADA", f"abre na V{jn['primeira']}"
        elif estado == "sem_janela":
            motivo = (jn or {}).get("motivo")
            cor, titulo, sub = COR_VERMELHO, "SEM JANELA", {
                "nao_chega_ao_box": "não chega ao box", "tanque_insuficiente": "tanque insuficiente",
            }.get(motivo, "sem plano viável")
        elif estado == "sem_parada":
            cor, titulo, sub = COR_VERDE, "SEM PARADA", "chega ao fim"
        else:
            cor, titulo, sub = QColor(120, 120, 130), "PIT", "medindo..."
        if jn and jn.get("urgente"):
            sub = "box AGORA"
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(cor.red(), cor.green(), cor.blue(), 235))
        p.drawRoundedRect(14, 12, 104, 46, 6, 6)
        p.setPen(QColor(15, 15, 20))
        p.setFont(fonte(11, QFont.Bold))
        p.drawText(14, 15, 104, 22, Qt.AlignCenter, titulo)
        p.setFont(fonte(8, QFont.DemiBold))
        p.drawText(14, 35, 104, 18, Qt.AlignCenter, sub)

        p.setPen(QPen(QColor(cor.red(), cor.green(), cor.blue(), 220), 1.5))
        p.setBrush(QColor(255, 255, 255, 12))
        p.drawRoundedRect(118, 12, 132, 46, 6, 6)
        r = pn.get("reabastecer")
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(18, QFont.Bold))
        p.drawText(118, 12, 132, 46, Qt.AlignCenter, f"+{fmt_dec(r)} L" if r else ("--" if r is None else "+0 L"))
        p.setPen(COR_CINZA)
        p.setFont(fonte(7, QFont.DemiBold))
        p1 = pn.get("parada1")
        rotulo = "COLOCAR NA PARADA" if not p1 else (f"COLOCAR NA V{p1['volta']}" + ("  \u00b7  AT\u00c9 O TOPO" if p1["ate_o_topo"] else ""))
        p.drawText(118, 12, 132, 12, Qt.AlignCenter, rotulo)

        # tanque
        nivel, cap = pn["nivel"], pn.get("capacidade")
        x, y, w = 268, 16, 250
        p.setPen(QPen(QColor(255, 255, 255, 120), 1.2))
        p.setBrush(QColor(255, 255, 255, 14))
        p.drawRoundedRect(x, y, w, 18, 4, 4)
        if cap:
            frac = max(0.0, min(1.0, nivel / cap))
            voltas = pn["linhas"]["med"]["voltas"] if pn["linhas"].get("med") else None
            cor_n = COR_VERMELHO if (voltas is not None and voltas < 3) else (COR_AMARELO if (voltas is not None and voltas < 6) else QColor(255, 255, 255))
            p.setPen(Qt.NoPen)
            p.setBrush(cor_n)
            p.drawRoundedRect(x + 2, y + 2, max(3, int((w - 4) * frac)), 14, 3, 3)
        p.setPen(COR_CINZA)
        p.setFont(fonte(8))
        p.drawText(x, y + 22, 40, 16, Qt.AlignLeft | Qt.AlignVCenter, "0")
        if cap:
            p.drawText(x + w - 60, y + 22, 60, 16, Qt.AlignRight | Qt.AlignVCenter, f"{cap:.0f} L")
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(12, QFont.Bold))
        p.drawText(x + 40, y + 20, w - 100, 20, Qt.AlignCenter, f"{fmt_dec(nivel)} L")

    # ---- tabela MED / MAX / MIN ----
    def _tabela(self, p, pn):
        p.setFont(fonte(8, QFont.DemiBold))
        p.setPen(COR_CINZA)
        for nome, x in self.COLUNAS:
            p.drawText(x, 72, 70, 16, Qt.AlignLeft | Qt.AlignVCenter, nome)
        linhas = (("M\u00c9D*", "med"), ("M\u00c1X", "max"), ("M\u00cdN", "min"))
        for i, (rotulo, chave) in enumerate(linhas):
            y = 92 + i * 26
            if chave == "med":
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255, 255, 255, 20))
                p.drawRoundedRect(8, y, 506, 24, 4, 4)
            p.setPen(QColor(255, 255, 255))
            p.setFont(fonte(9, QFont.Bold))
            p.drawText(14, y, 52, 24, Qt.AlignLeft | Qt.AlignVCenter, rotulo)
            ln = pn["linhas"].get(chave)
            vals = [None] * 6
            if ln:
                vals = [fmt_dec(ln["uso"]), fmt_dec(ln["voltas"]),
                        fmt_dec(ln["paradas"]) if ln["paradas"] is not None else "-",
                        fmt_dec(ln["reabast"]) if ln["reabast"] else "-",
                        fmt_dec(ln["total"]) if ln["total"] else "-",
                        f"V{ln['acaba']}"]
            p.setFont(fonte(12, QFont.DemiBold))
            for (nome, x), v in zip(self.COLUNAS, vals):
                p.setPen(QColor(255, 255, 255) if v not in (None, "-") else COR_CINZA)
                p.drawText(x, y, 70, 24, Qt.AlignLeft | Qt.AlignVCenter, v if v is not None else "-")

    # ---- janela de pit em barras ----
    def _barras_pit(self, p, pn):
        y = 176
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(9, QFont.Bold))
        p.drawText(14, y, 40, 22, Qt.AlignLeft | Qt.AlignVCenter, "PIT")
        atual = pn["volta_atual"]
        jn = pn.get("janela") or {}
        fim = None
        if pn.get("voltas_fim") is not None:
            fim = math.ceil(atual - 1 + pn["voltas_fim"])
        x0 = 64
        for k in range(self.N_BARRAS):
            volta = atual - 4 + k
            if volta < 1 or (fim is not None and volta > fim):
                continue
            x = x0 + k * 12
            dentro = jn.get("primeira") is not None and jn["primeira"] <= volta <= jn["ultima"]
            if volta == atual:
                p.setBrush(COR_AMARELO)
                p.setPen(Qt.NoPen)
                p.drawRect(x, y + 1, 9, 20)
            else:
                p.setPen(Qt.NoPen)
                if dentro:
                    p.setBrush(QColor(60, 200, 90, 230))
                else:
                    p.setBrush(QColor(255, 255, 255, 28 if volta < atual else 48))
                p.drawRect(x, y + 4, 9, 14)

    # ---- tempo e voltas ate acabar ----
    def _caixas(self, p, pn):
        tempo, voltas = pn.get("tempo"), pn.get("voltas")
        self._caixa(p, 206, "TEMPO AT\u00c9 ACABAR",
                    fmt_hms(tempo["autonomia"]) if tempo else "--:--:--",
                    fmt_hms(tempo["dif"], sinal=True) if tempo else "", tempo["dif"] if tempo else None)
        self._caixa(p, 254, "VOLTAS AT\u00c9 ACABAR",
                    fmt_dec(voltas["autonomia"]) if voltas else "-",
                    fmt_dec(voltas["dif"], sinal=True) if voltas else "", voltas["dif"] if voltas else None)

    def _caixa(self, p, y, rotulo, valor, diferenca, dif_num):
        ok = dif_num is None or dif_num >= 0
        cor = COR_VERDE if ok else COR_VERMELHO
        p.setPen(QPen(QColor(cor.red(), cor.green(), cor.blue(), 190), 1.5))
        p.setBrush(QColor(255, 255, 255, 10))
        p.drawRoundedRect(14, y, 500, 42, 7, 7)
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(10, QFont.Bold))
        p.drawText(28, y, 200, 42, Qt.AlignLeft | Qt.AlignVCenter, rotulo)
        p.setFont(QFont("Consolas", 21, QFont.Bold))
        p.drawText(220, y, 150, 42, Qt.AlignCenter, valor)
        p.setPen(cor)
        p.setFont(fonte(11, QFont.Bold))
        p.drawText(370, y, 130, 42, Qt.AlignRight | Qt.AlignVCenter, diferenca)

    # ---- ultimas voltas ----
    def _ultimas(self, p, pn):
        x0 = 548
        p.setFont(fonte(8, QFont.DemiBold))
        p.setPen(COR_CINZA)
        for nome, dx in (("VOLTA", 0), ("USO", 62), ("DIF", 110)):
            p.drawText(x0 + dx, 72, 60, 16, Qt.AlignLeft | Qt.AlignVCenter, nome)
        ult = pn.get("ultimas") or []
        if not ult:
            p.setFont(fonte(9))
            p.drawText(x0, 100, 150, 40, Qt.AlignLeft | Qt.TextWordWrap, "Conclua uma volta limpa (sem box) para medir o consumo.")
            return
        for i, u in enumerate(ult):
            y = 96 + i * 32
            p.setPen(QColor(255, 255, 255))
            p.setFont(fonte(12, QFont.DemiBold))
            p.drawText(x0, y, 60, 28, Qt.AlignLeft | Qt.AlignVCenter, str(u["volta"]))
            p.drawText(x0 + 62, y, 60, 28, Qt.AlignLeft | Qt.AlignVCenter, fmt_dec(u["uso"]))
            dif = u.get("dif")
            p.setPen(QColor(255, 255, 255) if dif is None or abs(dif) < 0.05 else (COR_VERDE if dif < 0 else COR_VERMELHO))
            p.drawText(x0 + 110, y, 60, 28, Qt.AlignLeft | Qt.AlignVCenter, fmt_dec(dif, sinal=False) if dif is not None and abs(dif) < 0.05 else fmt_dec(dif, sinal=True))


# ---- Janela 12: forca G ---------------------------------------------------------------------------
class JanelaForcaG(JanelaBase):
    CHAVE = "forca_g"
    CHAVE_ATIVO = "mostrar_forca_g"
    TAXA_HZ = 30.0
    RAIO = 112
    CENTRO = (125, 122)

    def __init__(self, config):
        self.trilha = deque(maxlen=45)              # ~1,5 s de pontos (x, y em g)
        super().__init__(config)

    def tamanho(self):
        return (LARGURA_G, ALTURA_G)

    def atualizar(self, dados):
        self.dados = dados
        g = dados.get("forca_g") if dados["conectado"] else None
        if g:
            self.trilha.append((g["lat"], g["lon"]))
        else:
            self.trilha.clear()
        self._repintar()

    def _ponto(self, lat, lon, gmax):
        """G -> pixel. Aceleracao para cima, freada para baixo; curva a esquerda leva o ponto para a esquerda."""
        cx, cy = self.CENTRO
        x, y = -lat / gmax, -lon / gmax                # LatAccel > 0 = esquerda (eixo y a esquerda)
        n = math.hypot(x, y)
        if n > 1.0:
            x, y = x / n, y / n
        return cx + x * self.RAIO, cy + y * self.RAIO

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        self._fundo(p, True, com_fundo=False)
        cx, cy, r = self.CENTRO[0], self.CENTRO[1], self.RAIO
        gmax = max(1.0, float(self.config.get("g_max", 4.0)))
        alfa = int(255 * TEMA["opacidade"])
        # disco
        g = QRadialGradient(cx, cy, r)
        g.setColorAt(0.0, QColor(24, 26, 33, alfa))
        g.setColorAt(1.0, QColor(10, 11, 15, alfa))
        p.setPen(QPen(QColor(255, 255, 255, 60), 1.5))
        p.setBrush(g)
        p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)
        # aneis de 1 g, 2 g ... e cruz
        p.setBrush(Qt.NoBrush)
        passo = 1.0 if gmax <= 5 else 2.0
        k = passo
        while k < gmax + 1e-9:
            raio = int(r * k / gmax)
            p.setPen(QPen(QColor(255, 255, 255, 52), 1))
            p.drawEllipse(cx - raio, cy - raio, 2 * raio, 2 * raio)
            p.setPen(QColor(255, 255, 255, 90))
            p.setFont(fonte(7))
            p.drawText(cx + 3, cy - raio + 1, 28, 11, Qt.AlignLeft | Qt.AlignVCenter, f"{k:g}g")
            k += passo
        p.setPen(QPen(QColor(255, 255, 255, 34), 1))
        p.drawLine(cx - r + 6, cy, cx + r - 6, cy)
        p.drawLine(cx, cy - r + 6, cx, cy + r - 6)

        gd = d.get("forca_g") if d["conectado"] else None
        if gd is None:
            p.setPen(COR_CINZA)
            p.setFont(fonte(10, QFont.DemiBold))
            p.drawText(cx - r, cy - 12, 2 * r, 24, Qt.AlignCenter,
                       "Aguardando o iRacing..." if not d["conectado"] else "Sem dados de G")
        else:
            self._trilha_e_ponto(p, gmax)
        self._etiqueta(p, gd)

    def _trilha_e_ponto(self, p, gmax):
        pts = list(self.trilha)
        n = len(pts)
        p.setPen(Qt.NoPen)
        for i, (lat, lon) in enumerate(pts[:-1]):
            f = (i + 1) / n
            x, y = self._ponto(lat, lon, gmax)
            p.setBrush(QColor(70, 120, 255, int(170 * f * f)))
            raio = 1.5 + 3.5 * f
            p.drawEllipse(QRectF(x - raio, y - raio, 2 * raio, 2 * raio))
        if pts:
            x, y = self._ponto(pts[-1][0], pts[-1][1], gmax)
            brilho = QRadialGradient(x, y, 15)
            brilho.setColorAt(0.0, QColor(160, 190, 255, 200))
            brilho.setColorAt(1.0, QColor(70, 120, 255, 0))
            p.setBrush(brilho)
            p.drawEllipse(QRectF(x - 15, y - 15, 30, 30))
            p.setBrush(QColor(255, 255, 255))
            p.drawEllipse(QRectF(x - 4.5, y - 4.5, 9, 9))

    @staticmethod
    def _termometro(p, x, y):
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(190, 190, 200))
        p.drawRoundedRect(QRectF(x + 3, y, 4, 12), 2, 2)
        p.drawEllipse(QRectF(x, y + 9, 10, 10))
        p.setBrush(QColor(30, 30, 38))
        p.drawRect(QRectF(x + 4.2, y + 4, 1.6, 9))
        p.restore()

    def _etiqueta(self, p, gd):
        """Aba com 'G atual . pico' e, embaixo, pista e temperatura."""
        cx = self.CENTRO[0]
        y0 = self.CENTRO[1] + self.RAIO + 8
        pintar_superficie(p, QRectF(cx - 52, y0, 104, 22), 9)
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(11, QFont.Bold))
        texto = f"{fmt_dec(gd['total'])} \u2022 {fmt_dec(gd['pico'])}" if gd else "-- \u2022 --"
        p.drawText(cx - 52, y0, 104, 22, Qt.AlignCenter, texto)
        y1 = y0 + 22
        pintar_superficie(p, QRectF(8, y1, LARGURA_G - 16, 30), 12)
        nome = (gd or {}).get("pista") or "--"
        temp = (gd or {}).get("temp")
        JanelaClima._mini_pista(p, 18, y1 + 6)
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(11, QFont.Bold))
        nome = QFontMetrics(p.font()).elidedText(nome, Qt.ElideRight, 118)
        p.drawText(40, y1, 124, 30, Qt.AlignLeft | Qt.AlignVCenter, nome)
        self._termometro(p, 170, y1 + 6)
        p.drawText(188, y1, 54, 30, Qt.AlignLeft | Qt.AlignVCenter, f"{temp:.0f}\u00b0C" if temp is not None else "--")


# --------------------------------------------------------------------------
# Versao 1.2.0: Inputs, Luz ABS, Luz TC, Retorno a pista e Estrategia de pneus
# --------------------------------------------------------------------------
CORES_LUZ = {"dourado": (250, 190, 40), "vermelho": (235, 60, 60), "branco": (245, 245, 248), "azul": (70, 140, 255)}
ROTULO_ACAO = {"seguir": "SEGUIR", "prepare": "PREPARE-SE", "trocar": "TROCAR", "pedido": "PEDIDO NOS BOXES"}


def _texto_contorno(p, rect, flags, texto, fonte_, cor, contorno=QColor(0, 0, 0, 235), largura=5.0):
    """Texto com borda preta (le-se de qualquer fundo: grama, brita, asfalto)."""
    caminho = QPainterPath()
    fm = QFontMetrics(fonte_)
    r = QRectF(rect)
    x = r.x() + (r.width() - fm.horizontalAdvance(texto)) / 2.0 if flags & Qt.AlignHCenter else r.x()
    y = r.y() + (r.height() + fm.ascent() - fm.descent()) / 2.0
    caminho.addText(x, y, fonte_, texto)
    p.save()
    p.setPen(QPen(contorno, largura, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(caminho)
    p.setPen(Qt.NoPen)
    p.setBrush(cor)
    p.drawPath(caminho)
    p.restore()


class _JanelaLuz(JanelaBase):
    """Icone solto (sem painel) que acende e apaga como a luz de um painel de carro."""
    TAXA_HZ = 30.0
    LADO = 96
    CHAVE_COR = CHAVE_MODO = CHAVE_APAGADA = ""

    def __init__(self, config):
        self.pisca = v12.PiscaLuz(config.get(self.CHAVE_MODO, "ritmo"))
        self.acesa = False
        super().__init__(config)

    def tamanho(self):
        return (self.LADO, self.LADO)

    def cor(self):
        return CORES_LUZ.get(self.config.get(self.CHAVE_COR), CORES_LUZ["dourado"])

    def sinal(self, dados):
        return False

    def testar(self, segundos=5.0):
        """Pisca sozinha por alguns segundos (para posicionar sem ir para a pista)."""
        self._teste_ate = time.monotonic() + segundos

    def atualizar(self, dados):
        self.dados = dados
        agora = time.monotonic()
        self.pisca.definir_modo(self.config.get(self.CHAVE_MODO, "ritmo"))
        ativo = self.sinal(dados) if dados.get("conectado") else False
        teste = getattr(self, "_teste_ate", 0.0)
        if agora < teste:
            ativo = ativo or (int(agora * 6) % 2 == 0)
        acesa = self.pisca.atualizar(ativo, agora)
        if acesa != self.acesa:
            self.acesa = acesa
            self._t_pintura = agora
            self.update()
        elif not self.config["travado"] or agora < teste:
            self._repintar()

    def _mostrar_apagada(self):
        return (bool(self.config.get(self.CHAVE_APAGADA, False)) or not self.config["travado"]
                or time.monotonic() < getattr(self, "_teste_ate", 0.0))

    def paintEvent(self, _evento):
        p = self._pintor()
        p.setRenderHint(QPainter.Antialiasing)
        if not self.config["travado"]:
            self._fundo(p, True, com_fundo=False)
        if not self.acesa and not self._mostrar_apagada():
            return                                       # janela transparente: nao ocupa nada na tela
        cor = QColor(*self.cor()) if self.acesa else QColor(95, 98, 108, 190)
        opacidade = float(self.config.get("luz_opacidade", 1.0))
        p.setOpacity(max(0.2, min(1.0, opacidade)))
        if self.acesa:
            brilho = QRadialGradient(self.LADO / 2.0, self.LADO / 2.0, self.LADO / 2.0)
            c1 = QColor(cor)
            c1.setAlpha(110)
            c2 = QColor(cor)
            c2.setAlpha(0)
            brilho.setColorAt(0.0, c1)
            brilho.setColorAt(1.0, c2)
            p.setPen(Qt.NoPen)
            p.setBrush(brilho)
            p.drawEllipse(QRectF(0, 0, self.LADO, self.LADO))
        self.icone(p, cor)

    def icone(self, p, cor):
        pass


class JanelaLuzAbs(_JanelaLuz):
    CHAVE = "luz_abs"
    CHAVE_ATIVO = "mostrar_luz_abs"
    CHAVE_COR = "luz_abs_cor"
    CHAVE_MODO = "luz_abs_modo"
    CHAVE_APAGADA = "luz_abs_apagada"

    def sinal(self, dados):
        return bool(dados.get("abs"))

    def icone(self, p, cor):
        c = self.LADO / 2.0
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(cor, 5.0, Qt.SolidLine, Qt.RoundCap))
        p.drawEllipse(QRectF(c - 26, c - 26, 52, 52))
        p.setPen(QPen(cor, 4.0, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(c - 36, c - 30, 22, 60), 120 * 16, 120 * 16)        # parenteses dos dois lados
        p.drawArc(QRectF(c + 14, c - 30, 22, 60), -60 * 16, 120 * 16)
        p.setPen(cor)
        p.setFont(fonte(17, QFont.Bold))
        p.drawText(QRectF(c - 26, c - 14, 52, 28), Qt.AlignCenter, "ABS")


class JanelaLuzTc(_JanelaLuz):
    CHAVE = "luz_tc"
    CHAVE_ATIVO = "mostrar_luz_tc"
    CHAVE_COR = "luz_tc_cor"
    CHAVE_MODO = "luz_tc_modo"
    CHAVE_APAGADA = "luz_tc_apagada"

    def sinal(self, dados):
        return bool((dados.get("luz_tc") or {}).get("ativa"))

    def icone(self, p, cor):
        c = self.LADO / 2.0
        p.setPen(Qt.NoPen)
        p.setBrush(cor)
        corpo = QPainterPath()
        corpo.moveTo(c - 22, c + 4)
        corpo.lineTo(c - 18, c - 10)
        corpo.quadTo(c - 14, c - 20, c - 4, c - 20)
        corpo.lineTo(c + 8, c - 20)
        corpo.quadTo(c + 18, c - 20, c + 22, c - 8)
        corpo.lineTo(c + 24, c + 4)
        corpo.closeSubpath()
        p.drawPath(corpo)
        p.setBrush(QColor(20, 22, 28, 220))
        p.drawEllipse(QRectF(c - 15, c, 9, 9))
        p.drawEllipse(QRectF(c + 8, c, 9, 9))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(cor, 3.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for dx in (-14, 8):                                          # marcas em zigue-zague das rodas
            caminho = QPainterPath(QPointF(c + dx, c + 14))
            for k in range(3):
                caminho.lineTo(c + dx + (5 if k % 2 == 0 else 0), c + 20 + k * 7)
            p.drawPath(caminho)


class JanelaRetorno(JanelaBase):
    """Fora da pista ou parado: PARE / CEDA / LIVRE e os segundos para o carro de tras chegar. So aparece quando precisa."""
    CHAVE = "retorno"
    CHAVE_ATIVO = "mostrar_retorno"
    TAXA_HZ = 30.0

    def __init__(self, config):
        self._teste_ate = 0.0
        super().__init__(config)

    def tamanho(self):
        return (300, 120)

    def testar(self, segundos=9.0):
        self._teste_ate = time.monotonic() + segundos
        self._teste_ini = time.monotonic()
        self._teste_dur = segundos

    def _estado_atual(self):
        agora = time.monotonic()
        lp, lc = self.config.get("retorno_pare", 1.5), self.config.get("retorno_ceda", 3.5)
        lp, lc = v12.normalizar_limites(lp, lc)
        if agora < self._teste_ate:                           # teste: percorre os tres estados, do livre ao pare
            f = (agora - self._teste_ini) / self._teste_dur
            seg = max(0.3, (lc + 2.0) * (1.0 - f))
            return {"visivel": True, "segundos": seg, "estado": v12.estado_retorno(seg, lp, lc),
                    "cor": v12.cor_retorno(seg, lp, lc)}
        r = self.dados.get("retorno") if self.dados.get("conectado") else None
        if r and (r.get("visivel") or self.config.get("retorno_sempre", False)):
            return r
        if not self.config["travado"]:
            return {"visivel": True, "segundos": 2.4, "estado": "ceda", "cor": v12.cor_retorno(2.4, lp, lc)}
        return None

    def atualizar(self, dados):
        self.dados = dados
        if self._estado_atual() is not None or self.isVisible():
            self._repintar()

    def paintEvent(self, _evento):
        p = self._pintor()
        p.setRenderHint(QPainter.Antialiasing)
        if not self.config["travado"]:
            self._fundo(p, True, com_fundo=False)
        r = self._estado_atual()
        if r is None:
            return
        p.setOpacity(max(0.2, min(1.0, float(self.config.get("retorno_opacidade", 0.95)))))
        cor = QColor(*r["cor"])
        palavra = {"pare": "PARE", "ceda": "CEDA", "livre": "LIVRE"}[r["estado"]]
        _texto_contorno(p, QRectF(0, 4, 300, 70), Qt.AlignHCenter, palavra, fonte_titulo(52), cor)
        if r.get("segundos") is not None:
            _texto_contorno(p, QRectF(0, 70, 300, 44), Qt.AlignHCenter, f"{fmt_dec(r['segundos'])} s",
                            fonte(26, QFont.Bold), QColor(255, 255, 255), largura=4.0)


class JanelaEstrategia(JanelaBase):
    """Chuva x seco: qual pneu vale a pena agora (SEGUIR / PREPARE-SE / TROCAR) e com qual largar. So le dados."""
    CHAVE = "estrategia"
    CHAVE_ATIVO = "mostrar_estrategia"
    TAXA_HZ = 15.0
    LARG, ALT = 340, 158

    def __init__(self, config):
        self._pre = False
        super().__init__(config)

    def tamanho(self):
        return (self.LARG, self.ALT)

    def definir_auto_visivel(self, visivel):
        super().definir_auto_visivel(bool(visivel) or self._pre)      # antes da largada aparece tambem na garagem

    def atualizar(self, dados):
        self.dados = dados
        e = dados.get("estrategia") if dados.get("conectado") else None
        self._pre = bool(e and e.get("pre_largada") and e.get("acao") not in (None, "sem_dado"))
        self._repintar()

    @staticmethod
    def _pneu(p, x, y, tipo, raio=9):
        p.setBrush(Qt.NoBrush)
        cor = QColor(70, 150, 255) if tipo == "chuva" else QColor(240, 240, 245)
        p.setPen(QPen(cor, 4))
        p.drawEllipse(QRectF(x - raio, y - raio, 2 * raio, 2 * raio))
        p.setPen(QPen(cor, 2))
        p.drawEllipse(QRectF(x - 2.5, y - 2.5, 5, 5))

    def paintEvent(self, _evento):
        p = self._pintor()
        d = self.dados
        if not self._fundo(p, d["conectado"]):
            return
        pintar_superficie(p, QRectF(1, 1, self.LARG - 2, self.ALT - 2), 12)
        e = d.get("estrategia")
        if not e or e.get("acao") == "sem_dado":
            p.setPen(COR_CINZA)
            p.setFont(fonte(12, QFont.DemiBold))
            motivo = (e or {}).get("motivo")
            texto = ("Este carro nao tem pneu de chuva" if motivo == "carro_sem_chuva"
                     else "Sem dados de pista molhada")
            p.drawText(QRectF(0, 0, self.LARG, self.ALT), Qt.AlignCenter, "ESTRATEGIA DE PNEUS\n" + texto)
            return
        agora = time.monotonic()
        pulso = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(agora * 7.0))
        # linha 1: para onde a pista vai + pneu montado
        tend = {"secando": ("SECANDO", COR_VERDE), "molhando": ("MOLHANDO", QColor(90, 160, 255)),
                "sem_chuva": ("SEM CHUVA", COR_CINZA), "estavel": ("ESTAVEL", COR_CINZA)}.get(e.get("tendencia"))
        p.setFont(fonte_titulo(11))
        p.setPen(COR_CINZA)
        p.drawText(QRectF(14, 8, 150, 18), Qt.AlignLeft | Qt.AlignVCenter, "PARA A CORRIDA" if e.get("pre_largada") else "PISTA")
        if tend:
            p.setPen(tend[1])
            p.setFont(fonte(11, QFont.Bold))
            p.drawText(QRectF(90, 8, 150, 18), Qt.AlignLeft | Qt.AlignVCenter, tend[0])
        self._pneu(p, self.LARG - 26, 18, e.get("meu_pneu"))
        # linha 2: nivel (7 segmentos) + nome
        nivel = e.get("nivel") or 0
        for i in range(7):
            ret = QRectF(14 + i * 25, 34, 22, 10)
            if i < nivel:
                f = i / 6.0
                p.setBrush(QColor(int(200 - 130 * f), int(190 - 40 * f), int(120 + 135 * f)))
            else:
                p.setBrush(QColor(255, 255, 255, 30))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(ret, 3, 3)
        p.setPen(QColor(255, 255, 255))
        p.setFont(fonte(11, QFont.Bold))
        p.drawText(QRectF(196, 28, 134, 22), Qt.AlignRight | Qt.AlignVCenter, f"{e.get('nivel_nome') or '-'}  {nivel}/7")
        # linha 3: o que fazer
        acao, alvo = e["acao"], e.get("alvo")
        nome_alvo = {"seco": "SECO", "chuva": "CHUVA"}.get(alvo, "")
        nome_meu = {"seco": "SECO", "chuva": "CHUVA"}.get(e.get("meu_pneu"), "")
        pulsa = bool(self.config.get("estrategia_pulsar", True))
        cor, texto, sub = COR_CINZA, "", ""
        if acao == "seguir":
            texto = f"SEGUIR COM {nome_meu}"
        elif acao == "prepare":
            cor = COR_LARANJA
            texto = f"PREPARE-SE: {nome_alvo}"
            sub = f"~{e['minutos']} min" if e.get("minutos") else ""
        elif acao == "trocar":
            cor = COR_LARANJA
            texto = f"TROCAR PARA {nome_alvo}"
        elif acao == "pedido":
            cor = COR_VERDE
            texto = f"{nome_alvo} PEDIDO NOS BOXES"
        elif acao == "largar_ok":
            cor = COR_VERDE
            texto = f"LARGUE COM {nome_alvo}  ✓"
        elif acao == "largar_trocar":
            cor = COR_VERMELHO
            texto = f"PARA A LARGADA: TROQUE PARA {nome_alvo}"
        if cor in (COR_LARANJA, COR_VERMELHO) and acao in ("trocar", "largar_trocar") and pulsa:
            cor = QColor(cor)
            cor.setAlpha(int(255 * pulso))
        p.setPen(cor)
        p.setFont(fonte_titulo(19 if len(texto) < 22 else 14))
        largura_sub = 70 if sub else 0
        p.drawText(QRectF(14, 56, self.LARG - 28 - largura_sub, 40), Qt.AlignLeft | Qt.AlignVCenter, texto)
        if sub:
            p.setFont(fonte(14, QFont.Bold))
            p.drawText(QRectF(self.LARG - 14 - largura_sub, 56, largura_sub, 40), Qt.AlignRight | Qt.AlignVCenter, sub)
        # linha 4: vantagem e rivais (so informacao)
        p.setFont(fonte(11))
        p.setPen(COR_CINZA)
        linhas = []
        if e.get("pre_largada"):
            if e.get("rivais_mesmo") is not None and acao == "largar_ok":
                linhas.append(f"{e['rivais_mesmo']} da sua classe com esse pneu")
        else:
            if self.config.get("estrategia_vantagem", True):
                v = e.get("vantagem")
                linhas.append("Vantagem: ~" + (fmt_dec(abs(v), 1) + " s/volta" if v is not None and v > 0 else "-- s/volta"))
            if self.config.get("estrategia_rivais", True) and e.get("rivais_outro"):
                linhas.append(f"{e['rivais_outro']} da sua classe ja trocaram")
        for i, t in enumerate(linhas[:2]):
            p.drawText(QRectF(14, 100 + i * 20, self.LARG - 28, 20), Qt.AlignLeft | Qt.AlignVCenter, t)


# Compatibilidade com a versao anterior
Overlay = OverlayPrincipal = JanelaTelemetria


# --------------------------------------------------------------------------
# Aparecer sozinho + iniciar com o Windows + instancia unica
# --------------------------------------------------------------------------
class VisibilidadeAuto:
    """Decide se as janelas devem aparecer: so com o iRacing aberto e voce dentro do carro.

    Aparece na hora em que voce entra no carro. Para esconder espera ATRASO segundos seguidos fora
    do carro (assim uma ida rapida ao menu/ESC nao faz as janelas piscarem).
    """

    ATRASO = 6.0

    def __init__(self, automatico=True, atraso=None):
        self.automatico = bool(automatico)
        self.atraso = self.ATRASO if atraso is None else float(atraso)
        self.visivel = not self.automatico
        self._fora_desde = None

    def atualizar(self, dados, agora, edicao=False):
        """edicao=True (janelas destravadas para posicionar): mantem tudo visivel."""
        if not self.automatico or edicao:
            self.visivel, self._fora_desde = True, None
            return True
        dentro = bool(dados.get("conectado")) and bool(dados.get("no_carro")) and not dados.get("replay")
        if dentro:
            self.visivel, self._fora_desde = True, None
        elif self.visivel:
            if self._fora_desde is None:
                self._fora_desde = agora
            elif agora - self._fora_desde >= self.atraso:
                self.visivel, self._fora_desde = False, None
        return self.visivel


NOME_INICIO = "OverlayIRacing"
CHAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def comando_inicio():
    """Comando gravado no Windows para abrir o overlay no login (pythonw = sem janela preta)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe" and exe.with_name("pythonw.exe").exists():
        exe = exe.with_name("pythonw.exe")
    return f'"{exe}" "{Path(__file__).resolve()}"'


def _winreg(winreg=None):
    if winreg is not None:
        return winreg
    if sys.platform != "win32":
        return None
    import winreg as _w
    return _w


def inicio_automatico_ativo(winreg=None):
    w = _winreg(winreg)
    if w is None:
        return False
    try:
        with w.OpenKey(w.HKEY_CURRENT_USER, CHAVE_RUN, 0, w.KEY_READ) as chave:
            valor, _tipo = w.QueryValueEx(chave, NOME_INICIO)
        return bool(valor)
    except OSError:
        return False
    except Exception:
        registrar_erro("ler inicio automatico")
        return False


def definir_inicio_automatico(ativo, winreg=None):
    """Liga/desliga a abertura do overlay junto com o Windows (so este usuario, sem administrador)."""
    w = _winreg(winreg)
    if w is None:
        return False
    try:
        if ativo:
            with w.CreateKey(w.HKEY_CURRENT_USER, CHAVE_RUN) as chave:
                w.SetValueEx(chave, NOME_INICIO, 0, w.REG_SZ, comando_inicio())
        else:
            try:
                with w.OpenKey(w.HKEY_CURRENT_USER, CHAVE_RUN, 0, w.KEY_SET_VALUE) as chave:
                    w.DeleteValue(chave, NOME_INICIO)
            except FileNotFoundError:
                pass
        return True
    except Exception:
        registrar_erro("configurar inicio automatico")
        return False


def criar_api_teclas():
    """Acesso do Windows aos atalhos globais (Fase 20.2.2). Retorna None fora do Windows ou se falhar."""
    if sys.platform != "win32":
        return None
    try:
        return nucleo.ApiTeclasWindows()
    except Exception:
        registrar_erro("atalhos globais (api do Windows)")
        return None


def trava_instancia_unica():
    """Impede duas copias do overlay ao mesmo tempo. Retorna (trava ou None se ja ha outra)."""
    import tempfile
    from PySide6.QtCore import QLockFile
    nome = "overlay_iracing_demo.lock" if DEMO else "overlay_iracing.lock"
    trava = QLockFile(str(Path(tempfile.gettempdir()) / nome))
    trava.setStaleLockTime(0)          # considera a trava velha se o processo dono morreu
    return trava if trava.tryLock(200) else None


# --------------------------------------------------------------------------
# Sobreposicao ao jogo (Windows)
# --------------------------------------------------------------------------
def reforcar_sobreposicao(janelas):
    """Reafirma "sempre no topo" e "sem foco" nas janelas do overlay (so no Windows).

    Quando o jogo ocupa a tela inteira, o Windows pode colocar a janela do jogo na frente das
    outras. Reaplicar HWND_TOPMOST periodicamente mantem o overlay por cima, sem roubar o foco
    do jogo. Isto NAO injeta nada no iRacing: funciona quando o jogo roda em janela sem borda ou
    em tela cheia "otimizada" pelo Windows; na tela cheia EXCLUSIVA o Windows nao deixa nenhuma
    janela de outro programa aparecer (e a forma segura de contornar e usar janela sem borda).
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        HWND_TOPMOST = ctypes.c_void_p(-1)
        GWL_EXSTYLE = -20
        WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x00000008, 0x00000080, 0x08000000
        SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
        for j in janelas:
            if not j.isVisible():
                continue
            hwnd = ctypes.c_void_p(int(j.winId()))
            estilo = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            novo = estilo | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            if novo != estilo:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, novo)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        return True
    except Exception:
        registrar_erro("sobreposicao")
        return False


# --------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------
def criar_icone():
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(COR_VERMELHO)
    p.setPen(Qt.NoPen)
    p.drawEllipse(4, 4, 56, 56)
    p.setPen(QColor(255, 255, 255))
    p.setFont(fonte(28, QFont.Bold))
    p.drawText(pix.rect(), Qt.AlignCenter, "i")
    p.end()
    return QIcon(pix)


def definir_prioridade_baixa(ativa):
    """Windows: prioridade ABAIXO DO NORMAL para o overlay (o iRacing tem preferencia na CPU).
    Opera so sobre o proprio processo do overlay; nao toca no jogo. Retorna True se aplicou."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        return bool(kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x00004000 if ativa else 0x00000020))
    except Exception:
        registrar_erro("prioridade do processo")
        return False


def registrar_cabecalho():
    """Primeira linha da sessao no log: versoes (ajuda a diagnosticar problemas)."""
    versoes = {"overlay": "1.2.0 (base Fase 20.2.2)", "nucleo": nucleo.VERSAO_NUCLEO, "python": sys.version.split()[0],
               "SO": sys.platform}
    try:
        import PySide6
        versoes["PySide6"] = PySide6.__version__
    except Exception:
        pass
    try:
        import irsdk
        versoes["pyirsdk"] = getattr(irsdk, "VERSION", "?")
    except Exception:
        versoes["pyirsdk"] = "nao instalado (modo demo?)"
    versoes["modo"] = "demo" if DEMO else "iRacing"
    _REGISTRO.cabecalho(versoes)


def principal():
    if "--ativar-inicio" in sys.argv or "--desativar-inicio" in sys.argv:
        ligar = "--ativar-inicio" in sys.argv
        ok = definir_inicio_automatico(ligar)
        print(("Inicio automatico ATIVADO: o overlay abrira junto com o Windows." if ligar
               else "Inicio automatico DESATIVADO.") if ok
              else "Nao foi possivel alterar o inicio automatico (veja overlay_log.txt).")
        return 0 if ok else 1

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    trava = trava_instancia_unica()
    if trava is None:
        QMessageBox.information(None, "Overlay iRacing",
                                "O overlay ja esta em execucao.\n\nProcure o icone vermelho com um \"i\" "
                                "perto do relogio do Windows (pode estar na setinha ^).")
        return 0

    config = carregar_config()
    registrar_cabecalho()
    if config.get("tema_vidro", True) and config.get("tema_sport", False):
        config["tema_sport"] = False                  # Glass Fume e Sport sao excludentes (config antigo: vence o Glass Fume)
    definir_tema(config.get("tema_moderno", True), config.get("opacidade_fundo", 0.80), config.get("tema_sport", False), config.get("tema_vidro", True))
    JanelaBase.MULT_TAXA = 0.5 if config.get("economia_cpu") else 1.0
    if config.get("prioridade_baixa", True) and not DEMO and definir_prioridade_baixa(True):
        registrar_info("prioridade do processo do overlay: abaixo do normal")
    telemetria = Telemetria(demo=DEMO)
    janela_telemetria = JanelaTelemetria(config)
    janela_voltas = JanelaVoltas(config)
    janela_relativo = JanelaRelativo(config)
    janela_classificacao = JanelaClassificacao(config)
    janela_mapa = JanelaMapa(config)
    janela_radar = JanelaRadar(config)
    janela_pneus = JanelaPneus(config)
    janela_setores = JanelaSetores(config)
    janela_clima = JanelaClima(config)
    janela_danos = JanelaDanos(config)
    janela_combustivel = JanelaCombustivel(config)
    janela_forca_g = JanelaForcaG(config)
    janela_luz_abs = JanelaLuzAbs(config)
    janela_luz_tc = JanelaLuzTc(config)
    janela_retorno = JanelaRetorno(config)
    janela_estrategia = JanelaEstrategia(config)
    visib = VisibilidadeAuto(bool(config.get("auto_modo", True)) and not DEMO)
    janelas = [janela_telemetria, janela_voltas, janela_relativo, janela_classificacao,
               janela_mapa, janela_radar, janela_pneus, janela_setores, janela_clima, janela_danos, janela_combustivel, janela_forca_g,
               janela_luz_abs, janela_luz_tc, janela_retorno, janela_estrategia]
    if not config["travado"]:
        visib.visivel = True               # destravado = posicionando: tudo visivel
    for j in janelas:
        j.definir_auto_visivel(visib.visivel)
    telemetria.margem_combustivel = float(config.get("margem_combustivel", 1.0))
    telemetria.v12_tc.definir_sensibilidade(config.get("luz_tc_sens", "normal"))
    telemetria.v12_retorno.definir_limites(config.get("retorno_pare", 1.5), config.get("retorno_ceda", 3.5))
    telemetria.estimador_pneus.desgaste_volta = max(0.001, float(config.get("pneu_desgaste_volta", 0.7)) / 100.0)
    telemetria.estimador_pneus.limite = float(config.get("pneu_vida_minima", 30)) / 100.0
    telemetria.estimador_pneus.inverter = bool(config.get("pneu_lado_invertido", False))

    # ---- perfis de exibicao: Treino / Classificacao / Corrida ----
    seletor_perfil = nucleo.SeletorPerfil(_PERFIS, 3.0)
    ressincronizar = []                           # chamadas para atualizar o menu depois de trocar o perfil

    def aplicar_perfil(novo):
        if not _PERFIS.trocar(config, novo):
            return
        for j in janelas:
            j.recarregar_layout()
        for fn in ressincronizar:
            fn()
        salvar_config(config)
        registrar_info(f"perfil de exibicao: {novo} (modo {'automatico' if config.get('perfil_modo') == 'auto' else 'manual'})")

    # Icone na bandeja do Windows (perto do relogio) com o menu de controle
    icone = criar_icone()
    bandeja = QSystemTrayIcon(icone, app)
    bandeja.setToolTip("Overlay iRacing" + (" (demo)" if DEMO else ""))
    menu = QMenu()
    acoes = []

    acoes_config = []              # (acao, chave do config): reajustadas ao trocar de perfil
    acao_por_chave = {}            # chave -> item marcavel do menu (Fase 20.2.2: os atalhos globais usam estes itens)

    def adicionar(texto, marcado, ao_alterar, chave=None, id_tecla=None):
        acao = QAction(texto, menu)
        acao.setCheckable(True)
        acao.setChecked(bool(marcado))
        acao.toggled.connect(ao_alterar)
        menu.addAction(acao)
        acoes.append(acao)
        if chave:
            acoes_config.append((acao, chave))
        if chave or id_tecla:
            acao_por_chave[id_tecla or chave] = acao

    def ao_travar(marcado):
        for j in janelas:
            j.aplicar_travamento(marcado)
        salvar_config(config)

    def ao_telemetria(marcado):
        janela_telemetria.definir_ativo(marcado)
        salvar_config(config)

    def ao_grafico(marcado):
        janela_telemetria.definir_grafico(marcado)
        salvar_config(config)

    def ao_voltas(marcado):
        janela_voltas.definir_ativo(marcado)
        salvar_config(config)

    def ao_relativo(marcado):
        janela_relativo.definir_ativo(marcado)
        salvar_config(config)

    def ao_classificacao(marcado):
        janela_classificacao.definir_ativo(marcado)
        salvar_config(config)

    def ao_mapa(marcado):
        janela_mapa.definir_ativo(marcado)
        salvar_config(config)

    def ao_radar(marcado):
        janela_radar.definir_ativo(marcado)
        salvar_config(config)

    def ao_pneus(marcado):
        janela_pneus.definir_ativo(marcado)
        salvar_config(config)

    def ao_setores(marcado):
        janela_setores.definir_ativo(marcado)
        salvar_config(config)

    def ao_clima(marcado):
        janela_clima.definir_ativo(marcado)
        salvar_config(config)

    def ao_tema(marcado):
        config["tema_moderno"] = bool(marcado)
        definir_tema(moderno=marcado)
        for j in janelas:
            j.update()
        salvar_config(config)

    def _sincronizar_estilo():
        for chave in ("tema_sport", "tema_vidro"):
            acao = acao_por_chave.get(chave)
            if acao is not None and acao.isChecked() != bool(config[chave]):
                acao.blockSignals(True)
                acao.setChecked(bool(config[chave]))
                acao.blockSignals(False)

    def ao_sport(marcado):
        config["tema_sport"] = bool(marcado)
        if marcado:
            config["tema_vidro"] = False
        definir_tema(sport=marcado)
        _sincronizar_estilo()
        for j in janelas:
            j.update()
        salvar_config(config)

    def ao_vidro(marcado):
        config["tema_vidro"] = bool(marcado)
        if marcado:
            config["tema_sport"] = False
        definir_tema(vidro=marcado)
        _sincronizar_estilo()
        for j in janelas:
            j.update()
        salvar_config(config)

    def ao_opacidade(valor):
        config["opacidade_fundo"] = float(valor)
        definir_tema(opacidade=valor)
        for j in janelas:
            j.update()
        salvar_config(config)

    def ao_forca_g(marcado):
        janela_forca_g.definir_ativo(marcado)
        salvar_config(config)

    def ao_alcance_g(valor):
        config["g_max"] = float(valor)
        janela_forca_g.update()
        salvar_config(config)

    def ao_zerar_pico_g():
        telemetria.zerar_pico_g()

    def ao_combustivel(marcado):
        janela_combustivel.definir_ativo(marcado)
        salvar_config(config)

    def ao_danos(marcado):
        janela_danos.definir_ativo(marcado)
        salvar_config(config)

    def ao_limpar_impactos():
        telemetria.limpar_impactos()

    def ao_zerar_referencia():
        telemetria.zerar_referencia()

    def ao_calc_combustivel(marcado):
        janela_voltas.definir_calc(marcado)
        salvar_config(config)

    def ao_projecao(marcado):
        janela_relativo.definir_projecao(marcado)
        salvar_config(config)

    def ao_margem(valor):
        config["margem_combustivel"] = float(valor)
        telemetria.margem_combustivel = float(valor)
        salvar_config(config)

    def ao_refazer_mapa():
        telemetria.refazer_mapa()

    def ao_restaurar_tamanhos():
        for j in janelas:
            j.definir_escala(1.0, salvar=False)
        salvar_config(config)

    def ao_reforcar(marcado):
        config["reforcar_topo"] = bool(marcado)
        salvar_config(config)
        if marcado:
            reforcar_sobreposicao(janelas)

    def ao_classificacao_todas(marcado):
        config["classificacao_todas"] = bool(marcado)
        janela_classificacao.recalcular()
        salvar_config(config)

    def ao_auto(marcado):
        config["auto_modo"] = bool(marcado)
        visib.automatico = bool(marcado)
        salvar_config(config)

    def ao_inicio(marcado):
        if not definir_inicio_automatico(marcado):
            bandeja.showMessage("Overlay iRacing", "Nao foi possivel alterar o inicio com o Windows.",
                                QSystemTrayIcon.Warning, 5000)

    adicionar("Travar posicao (cliques atravessam o overlay)", config["travado"], ao_travar, chave="travado")
    adicionar("Aparecer sozinho ao entrar no carro (so com as janelas travadas)",
              config["auto_modo"], ao_auto, id_tecla="auto_modo")
    if sys.platform == "win32":
        adicionar("Iniciar junto com o Windows", inicio_automatico_ativo(), ao_inicio)
    adicionar("Teclas de atalho para o Stream Deck (Ctrl+Alt+F13...F24)", config.get("teclas_globais", True),
              lambda marcado: ao_teclas(marcado), chave="teclas_globais")
    menu.addSeparator()
    rotulo_perfil = QAction("", menu)
    rotulo_perfil.setEnabled(False)
    menu.addAction(rotulo_perfil)
    submenu_perfil = menu.addMenu("Perfil de exibicao (posicao, tamanho e janelas por perfil)")
    grupo_perfil = QActionGroup(submenu_perfil)
    grupo_perfil.setExclusive(True)
    acoes_perfil = {}

    def ao_modo_perfil(modo):
        config["perfil_modo"] = modo
        if modo != "auto":
            aplicar_perfil(modo)
        salvar_config(config)
        atualizar_rotulo_perfil()

    for modo, texto in (("auto", "Automatico (pelo tipo de sessao)"), ("Treino", "Treino"),
                        ("Classificacao", "Classificacao"), ("Corrida", "Corrida")):
        acao_p = QAction(texto, submenu_perfil)
        acao_p.setCheckable(True)
        acao_p.setChecked(config.get("perfil_modo", "auto") == modo)
        acao_p.triggered.connect(lambda _m=False, m=modo: ao_modo_perfil(m))
        grupo_perfil.addAction(acao_p)
        submenu_perfil.addAction(acao_p)
        acoes_perfil[modo] = acao_p
        acoes.append(acao_p)

    def ao_copiar_layout():
        for nome in _PERFIS.nomes:
            config["perfis"][nome] = {k: config[k] for k in nucleo.chaves_de_layout(config)}
        salvar_config(config)
        registrar_info("layout do perfil ativo copiado para todos os perfis")

    acao_copiar = QAction("Copiar o layout atual para os outros perfis", submenu_perfil)
    acao_copiar.triggered.connect(ao_copiar_layout)
    submenu_perfil.addSeparator()
    submenu_perfil.addAction(acao_copiar)

    def atualizar_rotulo_perfil():
        modo = config.get("perfil_modo", "auto")
        rotulo_perfil.setText(f"Perfil ativo: {config.get('perfil_ativo')}" + ("  (automatico)" if modo == "auto" else "  (manual)"))
        bandeja.setToolTip(f"Overlay iRacing{' (demo)' if DEMO else ''} - perfil {config.get('perfil_ativo')}")

    def sincronizar_menu_config():
        for acao_c, chave_c in acoes_config:
            if chave_c in config:
                acao_c.blockSignals(True)
                acao_c.setChecked(bool(config[chave_c]))
                acao_c.blockSignals(False)
        atualizar_rotulo_perfil()

    ressincronizar.append(sincronizar_menu_config)

    def ao_economia(marcado):
        config["economia_cpu"] = bool(marcado)
        JanelaBase.MULT_TAXA = 0.5 if marcado else 1.0
        salvar_config(config)

    def ao_prioridade(marcado):
        config["prioridade_baixa"] = bool(marcado)
        definir_prioridade_baixa(marcado)
        salvar_config(config)

    adicionar("Modo economia de CPU (metade das atualizacoes por segundo)", config["economia_cpu"], ao_economia,
              chave="economia_cpu")
    if sys.platform == "win32":
        adicionar("Prioridade baixa do overlay (o jogo tem preferencia na CPU)", config["prioridade_baixa"],
                  ao_prioridade, chave="prioridade_baixa")
    menu.addSeparator()
    adicionar("Mostrar telemetria (marcha, velocidade e pedais)", config["mostrar_telemetria"],
              ao_telemetria, chave="mostrar_telemetria")
    adicionar("   Grafico de acelerador e freio (na telemetria)", config["mostrar_grafico"], ao_grafico, chave="mostrar_grafico")
    adicionar("Mostrar delta, voltas e combustivel", config["mostrar_voltas"], ao_voltas, chave="mostrar_voltas")
    adicionar("Mostrar relativo", config["mostrar_relativo"], ao_relativo, chave="mostrar_relativo")
    adicionar("   Projecao de iRating e SR (na janela Relativo)", config["mostrar_projecao"],
              ao_projecao, chave="mostrar_projecao")
    adicionar("Mostrar classificacao", config["mostrar_classificacao"], ao_classificacao, chave="mostrar_classificacao")
    adicionar("Classificacao: mostrar todas as classes", config["classificacao_todas"],
              ao_classificacao_todas, chave="classificacao_todas")
    adicionar("   Calculo de combustivel (na janela Voltas)", config["mostrar_calc_combustivel"],
              ao_calc_combustivel, chave="mostrar_calc_combustivel")
    submenu_margem = menu.addMenu("   Margem de seguranca do combustivel")
    grupo_margem = QActionGroup(submenu_margem)
    grupo_margem.setExclusive(True)
    for valor in (0.5, 1.0, 1.5, 2.0):
        acao_m = QAction(f"{valor:g} volta(s) de folga", submenu_margem)
        acao_m.setCheckable(True)
        acao_m.setChecked(abs(float(config.get("margem_combustivel", 1.0)) - valor) < 1e-6)
        acao_m.triggered.connect(lambda _marcado=False, v=valor: ao_margem(v))
        grupo_margem.addAction(acao_m)
        submenu_margem.addAction(acao_m)
        acoes.append(acao_m)
    adicionar("Mostrar pneus (temperatura e vida util)", config["mostrar_pneus"], ao_pneus, chave="mostrar_pneus")
    adicionar("Mostrar setores (vs melhor volta)", config["mostrar_setores"], ao_setores, chave="mostrar_setores")
    adicionar("Mostrar clima, chuva e vento", config["mostrar_clima"], ao_clima, chave="mostrar_clima")
    adicionar("Mostrar painel de combustivel e pit", config["mostrar_combustivel"], ao_combustivel, chave="mostrar_combustivel")
    adicionar("Mostrar forca G", config["mostrar_forca_g"], ao_forca_g, chave="mostrar_forca_g")
    submenu_g = menu.addMenu("   Alcance da forca G (aneis)")
    grupo_g = QActionGroup(submenu_g)
    grupo_g.setExclusive(True)
    for valor in (2.0, 3.0, 4.0, 5.0):
        acao_g = QAction(f"ate {valor:g} g", submenu_g)
        acao_g.setCheckable(True)
        acao_g.setChecked(abs(float(config.get("g_max", 4.0)) - valor) < 1e-6)
        acao_g.triggered.connect(lambda _marcado=False, v=valor: ao_alcance_g(v))
        grupo_g.addAction(acao_g)
        submenu_g.addAction(acao_g)
        acoes.append(acao_g)
    acao_zerar_g = QAction("   Zerar o pico de G", menu)
    acao_zerar_g.triggered.connect(ao_zerar_pico_g)
    menu.addAction(acao_zerar_g)
    adicionar("Mostrar danos do carro", config["mostrar_danos"], ao_danos, chave="mostrar_danos")
    acao_limpar = QAction("   Limpar as marcas de impacto do desenho do carro", menu)
    acao_limpar.triggered.connect(ao_limpar_impactos)
    menu.addAction(acao_limpar)
    acao_zerar = QAction("   Zerar a referencia de setores (carro e pista atuais)", menu)
    acao_zerar.triggered.connect(ao_zerar_referencia)
    menu.addAction(acao_zerar)
    adicionar("Mostrar mapa da pista", config["mostrar_mapa"], ao_mapa, chave="mostrar_mapa")
    adicionar("Mostrar radar de proximidade", config["mostrar_radar"], ao_radar, chave="mostrar_radar")
    acao_refazer = QAction("Refazer o mapa desta pista", menu)
    acao_refazer.triggered.connect(ao_refazer_mapa)
    menu.addAction(acao_refazer)

    # ---- v1.2.0: Inputs, Luz ABS, Luz TC, Retorno a pista, Estrategia de pneus ----
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
        salvar_config(config)

    def ao_inputs_opcao(chave, valor):
        _definir(chave, valor, janela_telemetria.reconfigurar)

    def ao_peca(chave):
        def fn(marcado):
            _definir(chave, bool(marcado), janela_telemetria.reconfigurar)
        return fn

    def ao_luz_abs(marcado):
        janela_luz_abs.definir_ativo(marcado)
        salvar_config(config)

    def ao_luz_tc(marcado):
        janela_luz_tc.definir_ativo(marcado)
        salvar_config(config)

    def ao_luz_opcao(chave, valor):
        _definir(chave, valor, lambda: (janela_luz_abs.update(), janela_luz_tc.update()))

    def ao_tc_sens(chave, valor):
        _definir(chave, valor, lambda: telemetria.v12_tc.definir_sensibilidade(valor))

    def ao_retorno(marcado):
        janela_retorno.definir_ativo(marcado)
        salvar_config(config)

    def ao_retorno_limite(chave, valor):
        def aplicar():
            lp, lc = v12.normalizar_limites(config.get("retorno_pare", 1.5), config.get("retorno_ceda", 3.5))
            config["retorno_pare"], config["retorno_ceda"] = lp, lc
            telemetria.v12_retorno.definir_limites(lp, lc)
        _definir(chave, valor, aplicar)

    def ao_estrategia(marcado):
        janela_estrategia.definir_ativo(marcado)
        salvar_config(config)

    def ao_flag(chave):
        def fn(marcado):
            _definir(chave, bool(marcado))
        return fn

    _submenu_escolha("   Telemetria: tempo do grafico de pedais", "inputs_segundos",
                     [(5, "5 segundos"), (8, "8 segundos"), (12, "12 segundos (padrao)"), (20, "20 segundos"), (30, "30 segundos")],
                     ao_inputs_opcao)
    _submenu_escolha("   Telemetria: de onde vem os pedais", "inputs_origem",
                     [("carro", "Como chegam ao carro (calibrados)"), ("cru", "Como o pe pisa (cru)"),
                      ("ambos", "Os dois (mostra a calibracao)")], ao_inputs_opcao)
    for rotulo_p, chave_p in (("Degraus das marchas no grafico", "inputs_marchas_fundo"),
                              ("Marca do ABS (amarelo) no freio", "inputs_marca_abs"),
                              ("Marca do TC (azul, estimada) no acelerador", "inputs_marca_tc")):
        adicionar("   Telemetria: " + rotulo_p, config[chave_p], ao_peca(chave_p), chave=chave_p)
    adicionar("Mostrar Luz do ABS", config["mostrar_luz_abs"], ao_luz_abs, chave="mostrar_luz_abs")
    _submenu_escolha("   Luz do ABS: cor", "luz_abs_cor",
                     [("dourado", "Dourado (padrao)"), ("vermelho", "Vermelho"), ("branco", "Branco")], ao_luz_opcao)
    _submenu_escolha("   Luz do ABS: como pisca", "luz_abs_modo",
                     [("ritmo", "No ritmo do ABS (padrao)"), ("suave", "Piscada suave"), ("fixa", "Luz fixa")], ao_luz_opcao)
    adicionar("   Luz do ABS: deixar visivel e apagada quando nao atua", config["luz_abs_apagada"], ao_flag("luz_abs_apagada"),
              chave="luz_abs_apagada")
    acao_teste_abs = QAction("   Testar a Luz do ABS (5 s)", menu)
    acao_teste_abs.triggered.connect(lambda: janela_luz_abs.testar(5.0))
    menu.addAction(acao_teste_abs)
    adicionar("Mostrar Luz do TC (perda de tracao, estimada)", config["mostrar_luz_tc"], ao_luz_tc, chave="mostrar_luz_tc")
    _submenu_escolha("   Luz do TC: cor", "luz_tc_cor",
                     [("azul", "Azul (padrao)"), ("dourado", "Dourado"), ("vermelho", "Vermelho"), ("branco", "Branco")],
                     ao_luz_opcao)
    _submenu_escolha("   Luz do TC: como pisca", "luz_tc_modo",
                     [("ritmo", "No ritmo da patinagem (padrao)"), ("suave", "Piscada suave"), ("fixa", "Luz fixa")], ao_luz_opcao)
    _submenu_escolha("   Luz do TC: sensibilidade", "luz_tc_sens",
                     [("fina", "Fina (a partir de 3,5%)"), ("normal", "Normal (5%, padrao)"), ("grossa", "Grossa (7,5%)")],
                     ao_tc_sens)
    adicionar("   Luz do TC: deixar visivel e apagada quando nao atua", config["luz_tc_apagada"], ao_flag("luz_tc_apagada"),
              chave="luz_tc_apagada")
    acao_teste_tc = QAction("   Testar a Luz do TC (5 s)", menu)
    acao_teste_tc.triggered.connect(lambda: janela_luz_tc.testar(5.0))
    menu.addAction(acao_teste_tc)
    adicionar("Mostrar Retorno a pista (PARE / CEDA / LIVRE)", config["mostrar_retorno"], ao_retorno, chave="mostrar_retorno")
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
    adicionar("Mostrar Estrategia de pneus (chuva x seco)", config["mostrar_estrategia"], ao_estrategia, chave="mostrar_estrategia")
    adicionar("   Estrategia: mostrar a vantagem em segundos por volta (estimada)", config["estrategia_vantagem"],
              ao_flag("estrategia_vantagem"), chave="estrategia_vantagem")
    adicionar("   Estrategia: mostrar quantos da sua classe ja trocaram", config["estrategia_rivais"],
              ao_flag("estrategia_rivais"), chave="estrategia_rivais")
    adicionar("   Estrategia: pulsar quando for hora de trocar", config["estrategia_pulsar"], ao_flag("estrategia_pulsar"),
              chave="estrategia_pulsar")
    menu.addSeparator()
    adicionar("Visual moderno (desmarque para voltar ao visual classico)", config["tema_moderno"], ao_tema, chave="tema_moderno")
    adicionar("   Estilo Glass Fume (vidro escuro translucido)", config["tema_vidro"], ao_vidro, chave="tema_vidro")
    adicionar("   Estilo Sport (italico e detalhes vermelhos)", config["tema_sport"], ao_sport, chave="tema_sport")
    submenu_op = menu.addMenu("   Transparencia do fundo das janelas")
    grupo_op = QActionGroup(submenu_op)
    grupo_op.setExclusive(True)
    for valor in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4):
        acao_o = QAction(f"Fundo {valor * 100:.0f}% opaco" + ("  (padrao)" if valor == 0.8 else ""), submenu_op)
        acao_o.setCheckable(True)
        acao_o.setChecked(abs(float(config.get("opacidade_fundo", 0.8)) - valor) < 1e-6)
        acao_o.triggered.connect(lambda _marcado=False, v=valor: ao_opacidade(v))
        grupo_op.addAction(acao_o)
        submenu_op.addAction(acao_o)
        acoes.append(acao_o)
    adicionar("Manter o overlay por cima do jogo (reforcar)", config["reforcar_topo"], ao_reforcar, chave="reforcar_topo")
    acao_tamanhos = QAction("Restaurar o tamanho das janelas (100%)", menu)
    acao_tamanhos.triggered.connect(ao_restaurar_tamanhos)
    menu.addAction(acao_tamanhos)
    menu.addSeparator()

    acao_sair = QAction("Sair", menu)
    acao_sair.triggered.connect(app.quit)
    menu.addAction(acao_sair)

    # ---- Fase 20.2.2: teclas de atalho globais (Stream Deck) ----
    # Cada atalho chama o MESMO item do menu da bandeja (toggle) ou a mesma funcao (perfil, zerar G...).
    def executar_atalho(tipo, alvo):
        if tipo == "perfil":
            if alvo not in acoes_perfil:
                raise KeyError(alvo)
            acoes_perfil[alvo].setChecked(True)
            ao_modo_perfil(alvo)
        elif tipo == "alternar":
            acao_por_chave[alvo].toggle()           # liga/desliga e dispara o mesmo tratamento do clique no menu
        elif tipo == "chamar":
            {"zerar_pico_g": ao_zerar_pico_g, "limpar_impactos": ao_limpar_impactos, "sair": app.quit}[alvo]()
        else:
            raise ValueError(f"tipo de atalho desconhecido: {tipo}")

    despachante = nucleo.DespachanteTeclas(
        executar_atalho,
        ao_erro=lambda contexto, erro: registrar_aviso(f"{contexto} falhou: {erro!r}"),
        ao_evento=registrar_info)
    estado_teclas = {"escuta": None, "avisou": False}

    def iniciar_teclas():
        if estado_teclas["escuta"] is not None:
            return
        api = criar_api_teclas()
        if api is None:
            return
        escuta = nucleo.EscutaTeclas(api)
        try:
            n_ok, falhas = escuta.iniciar()
        except Exception:
            registrar_erro("atalhos globais (iniciar)")
            return
        estado_teclas["escuta"] = escuta
        registrar_info(f"atalhos globais: {n_ok} de {len(nucleo.ATALHOS)} registrados")
        if escuta.erro:
            registrar_aviso(f"atalhos globais: a escuta falhou ({escuta.erro})")
        if falhas:
            registrar_aviso("atalhos globais NAO registrados (outro programa usa a mesma combinacao?): "
                            + ", ".join(f"{a.nome} [{a.rotulo}] - {erro}" for a, erro in falhas))
            if not estado_teclas["avisou"]:
                estado_teclas["avisou"] = True
                bandeja.showMessage("Overlay iRacing",
                                    f"{len(falhas)} atalho(s) para o Stream Deck nao puderam ser registrados "
                                    "(outro programa usa a mesma combinacao). Veja o overlay_log.txt.",
                                    QSystemTrayIcon.Warning, 8000)

    def parar_teclas():
        escuta = estado_teclas["escuta"]
        estado_teclas["escuta"] = None
        if escuta is not None:
            escuta.parar()
            registrar_info("atalhos globais desligados")

    def ao_teclas(marcado):
        config["teclas_globais"] = bool(marcado)
        salvar_config(config)
        (iniciar_teclas if marcado else parar_teclas)()

    def ciclo_teclas():
        escuta = estado_teclas["escuta"]
        if escuta is None:
            return
        try:
            for codigo in escuta.retirar():
                despachante.tratar(codigo)
        except Exception:
            registrar_erro("atalhos globais (ciclo)")

    timer_teclas = QTimer()
    timer_teclas.timeout.connect(ciclo_teclas)
    timer_teclas.start(40)
    app.aboutToQuit.connect(parar_teclas)

    bandeja.setContextMenu(menu)
    bandeja.show()
    if config.get("teclas_globais", True):
        iniciar_teclas()
    if visib.automatico and config["travado"] and not visib.visivel:
        bandeja.showMessage("Overlay iRacing", "Ativo. As janelas aparecem sozinhas quando voce entrar no carro.",
                            QSystemTrayIcon.Information, 6000)

    def ciclo():
        try:
            dados = telemetria.ler()
            novo_perfil = seletor_perfil.decidir(config, dados.get("tipo_sessao"), time.monotonic(),
                                                 editando=not config["travado"])
            if novo_perfil:
                aplicar_perfil(novo_perfil)
            mostrar = visib.atualizar(dados, time.monotonic(), edicao=not config["travado"])
            for j in janelas:
                j.definir_auto_visivel(mostrar)
                j.atualizar(dados)
        except Exception:
            registrar_erro("atualizacao")

    timer = QTimer()
    timer.timeout.connect(ciclo)
    timer.start(INTERVALO_MS)

    def ciclo_topo():
        if config.get("reforcar_topo", True):
            reforcar_sobreposicao(janelas)

    timer_topo = QTimer()
    timer_topo.timeout.connect(ciclo_topo)
    timer_topo.start(1000)
    ciclo_topo()

    def registrar_desempenho():
        try:
            taxas = {j.CHAVE: j.TAXA_HZ * JanelaBase.MULT_TAXA for j in janelas if j.isVisible()}
            ciclo_est = DESEMPENHO.estatistica("ciclo") or {}
            pintura_ms_s = DESEMPENHO.custo_por_segundo(taxas)
            registrar_calculo("desempenho", ciclo_ms_medio=ciclo_est.get("media", 0.0),
                              ciclo_ms_p95=ciclo_est.get("p95", 0.0), ciclo_ms_max=ciclo_est.get("max", 0.0),
                              desenho_ms_por_segundo=pintura_ms_s,
                              janelas_visiveis=len(taxas), economia=bool(config.get("economia_cpu")))
            lentas = sorted(((n, e["media"]) for n, e in DESEMPENHO.resumo().items()
                             if n.startswith("pintura:") and e and e["media"] > 8.0), key=lambda t: -t[1])
            if lentas:
                registrar_aviso("janelas lentas para desenhar (>8 ms): " + ", ".join(f"{n[8:]} {m:.1f} ms" for n, m in lentas))
        except Exception:
            registrar_erro("resumo de desempenho")

    timer_desempenho = QTimer()
    timer_desempenho.timeout.connect(registrar_desempenho)
    timer_desempenho.start(10 * 60 * 1000)
    app.aboutToQuit.connect(registrar_desempenho)
    sincronizar_menu_config()
    app.aboutToQuit.connect(telemetria.encerrar)
    app.aboutToQuit.connect(lambda: salvar_config(config))

    # Mantem referencias vivas
    app._refs = (janelas, bandeja, menu, acoes, acao_sair, acao_refazer, acao_tamanhos, acao_zerar, acao_limpar, acao_zerar_g, timer, timer_topo, timer_desempenho, seletor_perfil, acoes_perfil, acoes_config,
                 trava, visib, timer_teclas, despachante, estado_teclas, acao_por_chave)
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(principal())
    except Exception:
        ARQ_LOG.write_text(traceback.format_exc(), encoding="utf-8")
        raise
