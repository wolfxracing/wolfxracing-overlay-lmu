# -*- coding: utf-8 -*-
"""
Teclas de atalho globais do overlay LMU (para o Stream Deck) - sem Qt, testavel em qualquer sistema.

Reaproveita a maquinaria ja homologada do overlay do iRacing (ov_nucleo: AtalhoGlobal, EscutaTeclas, DespachanteTeclas),
mas com um mapa PROPRIO de combinacoes, diferente do iRacing, para os dois overlays poderem ficar abertos ao mesmo tempo
(ou os perfis do Stream Deck conviverem) sem nenhuma colisao:

  iRacing : Ctrl+Alt+Shift+F13..F24 (janelas)  e  Ctrl+Alt+F13..F22 (perfis e controles)
  LMU     : Ctrl+Shift+F13..F24     (janelas)  e  Alt+Shift+F13..F20 (controles)
  1.3.0   : as 4 janelas novas usam Alt+F13..F16 no iRacing e Alt+Shift+F21..F24 no LMU
  build q : Consumo/Delta Trace/Curvas usam Alt+F17..F19 no iRacing e Alt+F21..F23 no LMU

As teclas F13..F24 nao existem na maioria dos teclados: nada disso digita no jogo. Cada atalho chama o MESMO item do menu
da bandeja que o clique do mouse ja chamava (ver overlay_lmu.py).
"""
import ov_nucleo as nu

MODS_JANELAS_LMU = nu.MOD_CONTROL | nu.MOD_SHIFT          # Ctrl+Shift  (o iRacing usa Ctrl+Alt+Shift)
MODS_CONTROLES_LMU = nu.MOD_ALT | nu.MOD_SHIFT            # Alt+Shift   (o iRacing usa Ctrl+Alt)
MODS_NOVAS_Q = nu.MOD_ALT                                  # build q: Alt+F21..F23 (so Alt; o iRacing usa Alt+F13..F19)
MODS_NOVAS_LMU = MODS_CONTROLES_LMU                        # 1.3.0: Alt+Shift+F21..F24 (livres; os controles usam F13..F20)


def _janela(fn, id_, rotulo, chave):
    return nu.AtalhoGlobal("janela_" + id_, "Mostrar/ocultar " + rotulo, MODS_JANELAS_LMU, fn, "alternar", chave)


def _controle(fn, id_, rotulo, tipo, alvo):
    return nu.AtalhoGlobal(id_, rotulo, MODS_CONTROLES_LMU, fn, tipo, alvo)


# tipo: "alternar" = liga/desliga o item marcavel do menu (alvo = chave do config); "chamar" = executa uma acao do menu
ATALHOS_LMU = (
    _janela(13, "telemetria", "telemetria", "mostrar_telemetria"),
    _janela(14, "voltas", "voltas (delta e combustivel)", "mostrar_voltas"),
    _janela(15, "classificacao", "classificacao", "mostrar_classificacao"),
    _janela(16, "clima", "clima e chuva", "mostrar_clima"),
    _janela(17, "combustivel", "painel de combustivel e pit", "mostrar_combustivel"),
    _janela(18, "forca_g", "forca G", "mostrar_forca_g"),
    _janela(19, "energia", "energia virtual e combustivel", "mostrar_lmu_energia"),
    _janela(20, "pneus", "pneus e freios", "mostrar_pneus"),
    _janela(21, "danos", "danos do carro", "mostrar_danos"),
    _janela(22, "alertas", "alertas na pista", "mostrar_lmu_alertas"),
    _janela(23, "stints", "historico de stints", "mostrar_lmu_stints"),
    _janela(24, "tendencia", "tendencia de ritmo", "mostrar_lmu_tendencia"),
    _controle(13, "economia_cpu", "Modo economia de CPU (liga/desliga)", "alternar", "economia_cpu"),
    _controle(14, "aparecer_sozinho", "Aparecer sozinho ao entrar no carro (liga/desliga)", "alternar", "auto_modo"),
    _controle(15, "travar_posicao", "Travar posicao das janelas (liga/desliga)", "alternar", "travado"),
    _controle(16, "zerar_pico_g", "Zerar o pico de G", "chamar", "zerar_pico_g"),
    _controle(17, "classif_todas", "Classificacao: mostrar todas as classes (liga/desliga)", "alternar", "classificacao_todas"),
    _controle(18, "manter_no_topo", "Manter o overlay por cima do jogo (liga/desliga)", "alternar", "reforcar_topo"),
    _controle(19, "restaurar_tamanhos", "Restaurar o tamanho das janelas (100%)", "chamar", "restaurar_tamanhos"),
    _controle(20, "sair", "FECHAR o overlay (o mesmo que Sair no menu da bandeja)", "chamar", "sair"),
    # 1.3.0: janelas novas da 1.2.0 (acrescentadas no fim para nao mudar o codigo dos atalhos antigos)
    nu.AtalhoGlobal("janela_luz_abs", "Mostrar/ocultar luz do ABS", MODS_NOVAS_LMU, 21, "alternar", "mostrar_luz_abs"),
    nu.AtalhoGlobal("janela_luz_tc", "Mostrar/ocultar luz do TC", MODS_NOVAS_LMU, 22, "alternar", "mostrar_luz_tc"),
    nu.AtalhoGlobal("janela_retorno", "Mostrar/ocultar retorno a pista", MODS_NOVAS_LMU, 23, "alternar", "mostrar_retorno"),
    nu.AtalhoGlobal("janela_estrategia", "Mostrar/ocultar estrategia de pneus", MODS_NOVAS_LMU, 24, "alternar", "mostrar_estrategia"),
    # 1.7.0 build q: telas novas. Alt+F21..F23 (o iRacing usa Alt+F13..F19; sem colisao entre os dois mapas)
    nu.AtalhoGlobal("janela_consumo", "Mostrar/ocultar consumo por trecho (Burn Zones e Fuel Flow)", MODS_NOVAS_Q, 21, "alternar", "mostrar_consumo"),
    nu.AtalhoGlobal("janela_delta_trace", "Mostrar/ocultar Delta Trace", MODS_NOVAS_Q, 22, "alternar", "mostrar_delta_trace"),
    nu.AtalhoGlobal("janela_curvas", "Mostrar/ocultar Curvas (velocidade minima por curva)", MODS_NOVAS_Q, 23, "alternar", "mostrar_curvas"),
)

CHAVES_ALTERNAR = tuple(a.alvo for a in ATALHOS_LMU if a.tipo == "alternar")
ACOES_CHAMAR = tuple(a.alvo for a in ATALHOS_LMU if a.tipo == "chamar")


def validar_atalhos_lmu():
    """Problemas do mapa do LMU (lista vazia = tudo certo): erros do mapa em si + colisao com o mapa do iRacing."""
    erros = list(nu.validar_atalhos(ATALHOS_LMU))
    ocupados = {(a.mods, a.fn): a for a in nu.ATALHOS}
    for a in ATALHOS_LMU:
        outro = ocupados.get((a.mods, a.fn))
        if outro is not None:
            erros.append(f"{a.id}: mesma combinacao do atalho do iRacing {outro.id} ({outro.nome})")
    return erros


def atalho_lmu_por_id(id_):
    return nu.atalho_por_id(id_, ATALHOS_LMU)


def texto_atalhos_lmu():
    """Tabela legivel (para o ATALHOS_STREAM_DECK_LMU.txt)."""
    return nu.texto_atalhos(ATALHOS_LMU)
