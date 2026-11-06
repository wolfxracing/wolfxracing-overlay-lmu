# -*- coding: utf-8 -*-
"""
Contrato de dados e adaptadores por jogo (v1.7) - logica pura, sem Qt e sem depender do jogo.

Ideia: todas as janelas leem UM dicionario ("snapshot") montado a cada ciclo. Cada jogo tem um ADAPTADOR que entrega esse
dicionario. O contrato abaixo diz quais chaves existem, o tipo de cada uma e quem as entrega. E a base do app unico (v2.0):
um novo jogo so precisa de um adaptador que cumpra o contrato.

Regras
  - chave "obrigatoria": sempre presente no snapshot, com o tipo indicado.
  - chave "opcional": pode ser None (o jogo nao fornece, ou ainda nao ha dado). Quando presente, tem o tipo indicado.
  - "jogos": quem entrega (iracing, lmu). Chave que so um jogo entrega fica None no outro.
  - Nada aqui le a memoria do jogo: os adaptadores apenas ENVOLVEM as classes de leitura ja testadas.
"""
import importlib

JOGOS = ("iracing", "lmu")

NUM, INT, BOOL, TXT, DICT = "num", "int", "bool", "txt", "dict"

# (chave, tipo, obrigatoria, jogos, descricao)
CONTRATO = (
    ("conectado", BOOL, True, JOGOS, "ha dados do jogo"),
    ("no_carro", BOOL, True, JOGOS, "o piloto esta dentro do carro, no mundo do jogo"),
    ("replay", BOOL, True, JOGOS, "o jogo esta em replay"),
    ("tipo_sessao", TXT, False, JOGOS, "CORRIDA / QUALIFICACAO / TREINO..."),
    ("marcha", INT, True, JOGOS, "marcha atual (0 = neutro, -1 = re)"),
    ("velocidade", NUM, True, JOGOS, "km/h"),
    ("rpm", NUM, True, JOGOS, "rotacao"),
    ("rpm_max", NUM, True, JOGOS, "rotacao maxima do carro"),
    ("acelerador", NUM, True, JOGOS, "0..1"),
    ("freio", NUM, True, JOGOS, "0..1"),
    ("embreagem", NUM, True, JOGOS, "0..1 (1 = pisada)"),
    ("volante", NUM, True, JOGOS, "graus (positivo = para a esquerda)"),
    ("volta", INT, True, JOGOS, "volta atual"),
    ("tempo_volta", NUM, False, JOGOS, "s, volta em andamento"),
    ("ultima_volta", NUM, False, JOGOS, "s"),
    ("melhor_volta", NUM, False, JOGOS, "s"),
    ("delta", NUM, True, JOGOS, "s, negativo = mais rapido que a melhor volta"),
    ("combustivel", NUM, True, JOGOS, "litros"),
    ("forca_g", DICT, False, JOGOS, "G lateral/longitudinal"),
    ("clima", DICT, False, JOGOS, "pista, ar, vento"),
    ("pneus", DICT, False, JOGOS, "temperatura/desgaste por roda"),
    ("danos", DICT, False, JOGOS, "reparos e impactos"),
    ("relativo", DICT, False, JOGOS, "carros proximos"),
    ("classificacao", DICT, False, JOGOS, "classes e linhas"),
    ("mapa", DICT, False, JOGOS, "minimapa"),
    ("radar", DICT, False, JOGOS, "radar"),
    ("curvas", DICT, False, JOGOS, "v1.4.0: velocidade minima por curva"),
    ("consumo", DICT, False, JOGOS, "v1.7.0 build o: consumo por trecho (Burn Zones) e fluxo (L/h)"),
    ("delta_trace", DICT, False, JOGOS, "v1.7.0 build o: delta ao longo da volta"),
    ("bandeira", DICT, False, JOGOS, "v1.5.0"),
    ("trafego", DICT, False, JOGOS, "v1.5.0"),
    ("tendencia", DICT, False, JOGOS, "v1.6.0: ritmo"),
    ("pit", DICT, False, JOGOS, "v1.6.0"),
    ("coach", DICT, False, JOGOS, "v1.7.0: orientacao ao vivo (referencia por distancia)"),
    # --- demais chaves que as janelas ja usam (todas opcionais) ---
    ("abs", BOOL, False, JOGOS, "ABS atuando"),
    ("abs_nivel", NUM, False, JOGOS, "ajuste do ABS, se o carro tiver"),
    ("tc", DICT, False, JOGOS, "ajuste do controle de tracao"),
    ("bias", NUM, False, JOGOS, "balanco de freio dianteiro, se ajustavel"),
    ("luz_tc", DICT, False, JOGOS, "v1.2.0: TC atuando"),
    ("pedais_cru", DICT, False, JOGOS, "v1.2.0: pedais sem a calibracao do carro"),
    ("retorno", DICT, False, JOGOS, "v1.2.0: retorno a pista"),
    ("estrategia", DICT, False, JOGOS, "v1.2.0: chuva x seco"),
    ("auxiliar", DICT, False, JOGOS, "v1.5.0: etapa e tempo restante da sessao"),
    ("contato", DICT, False, JOGOS, "v1.6.0: ultimo carro tocado"),
    ("delta_ok", BOOL, False, JOGOS, "o delta e confiavel"),
    ("delta_fonte", TXT, False, JOGOS, "'overlay' (calculado aqui) ou 'sim' (do jogo)"),
    ("consumo_volta", NUM, False, JOGOS, "litros por volta"),
    ("voltas_restantes", NUM, False, JOGOS, "voltas de combustivel restantes"),
    ("calc_combustivel", DICT, False, JOGOS, "calculadora de combustivel"),
    ("painel_combustivel", DICT, False, JOGOS, "janela de pit e autonomia"),
    ("projecao", DICT, False, JOGOS, "projecao de iRating/SR (so iRacing)"),
    ("setores", DICT, False, JOGOS, "setores da volta"),
    # --- so o LMU entrega ---
    ("lmu_alertas", DICT, False, ("lmu",), "alertas na pista"),
    ("lmu_danos", DICT, False, ("lmu",), "danos por peca"),
    ("lmu_energia", DICT, False, ("lmu",), "energia virtual"),
    ("lmu_pneus", DICT, False, ("lmu",), "pneus e freios"),
    ("lmu_stints", DICT, False, ("lmu",), "historico de stints"),
    ("lmu_tendencia", DICT, False, ("lmu",), "tendencia do LMU"),
)

CHAVES = tuple(c[0] for c in CONTRATO)
_POR_CHAVE = {c[0]: c for c in CONTRATO}


def _tipo_ok(valor, tipo):
    if tipo == BOOL:
        return isinstance(valor, bool)
    if tipo == INT:
        return isinstance(valor, int) and not isinstance(valor, bool)
    if tipo == NUM:
        return isinstance(valor, (int, float)) and not isinstance(valor, bool)
    if tipo == TXT:
        return isinstance(valor, str)
    if tipo == DICT:
        return isinstance(valor, (dict, list))
    return True


def validar_snapshot(dados, jogo=None):
    """Lista de problemas do snapshot contra o contrato (vazia = ok). Nao levanta excecao."""
    if not isinstance(dados, dict):
        return ["snapshot nao e um dicionario"]
    problemas = []
    for chave, tipo, obrigatoria, jogos, _ in CONTRATO:
        if jogo is not None and jogo not in jogos:
            continue
        if chave not in dados:
            if obrigatoria:
                problemas.append(f"falta a chave obrigatoria '{chave}'")
            continue
        valor = dados[chave]
        if valor is None:
            if obrigatoria:
                problemas.append(f"'{chave}' obrigatoria esta None")
            continue
        if not _tipo_ok(valor, tipo):
            problemas.append(f"'{chave}' deveria ser {tipo}, veio {type(valor).__name__}")
    return problemas


def chaves_fora_do_contrato(dados):
    """Chaves do snapshot que o contrato ainda nao descreve (ajuda a manter a documentacao em dia)."""
    return sorted(k for k in dados if k not in _POR_CHAVE)


def texto_do_contrato():
    """Tabela legivel do contrato (vai para docs/CONTRATO_DE_DADOS.md)."""
    linhas = ["| Chave | Tipo | Obrigatoria | Descricao |", "|---|---|---|---|"]
    for chave, tipo, obrigatoria, _jogos, desc in CONTRATO:
        linhas.append(f"| `{chave}` | {tipo} | {'sim' if obrigatoria else 'nao'} | {desc} |")
    return "\n".join(linhas) + "\n"


# --------------------------------------------------------------------------
# Adaptadores
# --------------------------------------------------------------------------
class AdaptadorJogo:
    """Envolve a classe de leitura de um jogo e garante o contrato. Nao muda os dados: so os repassa."""

    def __init__(self, jogo, telemetria):
        if jogo not in JOGOS:
            raise ValueError(f"jogo desconhecido: {jogo!r}")
        self.jogo = jogo
        self.telemetria = telemetria
        self.problemas_ultimo = []

    @property
    def demo(self):
        return bool(getattr(self.telemetria, "demo", False))

    def ler(self, validar=False):
        dados = self.telemetria.ler()
        if validar:
            self.problemas_ultimo = validar_snapshot(dados, self.jogo)
        return dados

    def encerrar(self):
        fn = getattr(self.telemetria, "encerrar", None)
        if callable(fn):
            fn()

    def __getattr__(self, nome):                       # o resto (v14_curvas, consumo...) continua acessivel
        return getattr(self.telemetria, nome)


_CLASSES = {"iracing": ("overlay_iracing", "Telemetria"), "lmu": ("overlay_lmu", "TelemetriaLMU")}


def criar_adaptador(jogo, **kwargs):
    """Cria o adaptador do jogo (importa o modulo so quando precisa: o app unico da v2.0 carrega os dois)."""
    if jogo not in _CLASSES:
        raise ValueError(f"jogo desconhecido: {jogo!r}")
    modulo, classe = _CLASSES[jogo]
    cls = getattr(importlib.import_module(modulo), classe)
    return AdaptadorJogo(jogo, cls(**kwargs))
