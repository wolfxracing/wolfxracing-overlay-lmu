#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Biblioteca de icones do Overlay LMU para o Stream Deck XL (144x144, SVG + PNG).

Mesmo sistema visual do overlay do iRacing (fibra de carbono, acento ambar, vermelho = perigo, verde = iniciar/ligado,
roxo, cinza, rotulo italico em caixa alta com sombra, olho no canto das janelas). Reaproveita as funcoes de desenho da
biblioteca do iRacing (base/gerar_icones_iracing.py, copia somente-leitura) e acrescenta os pictogramas das janelas
exclusivas do LMU. Uso: python gerar_icones_lmu.py <pasta_de_saida>
"""
import importlib.util, math, os, sys

SAIDA = sys.argv[1]
AQUI = os.path.dirname(os.path.abspath(__file__))
_argv = sys.argv[:]
sys.argv = [_argv[0], os.path.join(SAIDA, "_base_tmp")]           # o modulo base le a pasta de saida ao ser importado
_spec = importlib.util.spec_from_file_location("gi", os.path.join(AQUI, "base", "gerar_icones_iracing.py"))
gi = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(gi)
sys.argv = _argv
# Paleta do acento. Padrao: VERMELHO (cor medida na foto de referencia do usuario, RGB ~233,32,69 / #F82040 no brilho).
# Use "ambar" como 2o argumento para voltar ao amarelo do perfil do iRacing.
COR = sys.argv[2] if len(sys.argv) > 2 else "vermelho"
if COR == "vermelho":
    gi.DEFS = (gi.DEFS
               .replace('<stop offset="0" stop-color="#FFD84D"/><stop offset="1" stop-color="#F29A00"/>',
                        '<stop offset="0" stop-color="#FF4560"/><stop offset="1" stop-color="#D91236"/>')      # acento principal
               .replace('<stop offset="0" stop-color="#E0A300"/><stop offset="1" stop-color="#9A5C00"/>',
                        '<stop offset="0" stop-color="#C41635"/><stop offset="1" stop-color="#7C0B20"/>'))     # sombra do acento
A, W, DK, GY, RD, GR, PU, AM2 = gi.A, gi.W, gi.DK, gi.GY, gi.RD, gi.GR, gi.PU, gi.AM2
letra = gi.letra


# ------------------------------------------------------------------ pictogramas novos (area x 18..126, y 6..94)
def p_energia():
    """Bateria com raio: energia virtual."""
    return (f'<rect x="20" y="22" width="92" height="58" rx="11" fill="none" stroke="{W}" stroke-width="6"/>'
            f'<rect x="114" y="40" width="11" height="22" rx="4" fill="{W}"/>'
            f'<rect x="29" y="31" width="58" height="40" rx="6" fill="{A}"/>'
            f'<rect x="92" y="31" width="11" height="40" rx="4" fill="{AM2}"/>'
            f'<path d="M69 26 L47 54 H61 L55 78 L82 46 H67 Z" fill="{DK}" stroke="{DK}" stroke-width="3"/>')


def p_pneus_freios():
    """Roda com pneu, disco de freio e pinca vermelha."""
    furos = "".join(f'<circle cx="{72 + 10*math.cos(math.radians(i*45)):.1f}" cy="{46 + 10*math.sin(math.radians(i*45)):.1f}" r="2.6" fill="{DK}"/>' for i in range(8))
    return (f'<circle cx="72" cy="46" r="40" fill="#3A3C43"/>'
            + "".join(f'<path d="M{72 + 32*math.cos(math.radians(i*30)):.1f} {46 + 32*math.sin(math.radians(i*30)):.1f} L{72 + 39*math.cos(math.radians(i*30)):.1f} {46 + 39*math.sin(math.radians(i*30)):.1f}" stroke="#8C919A" stroke-width="4"/>' for i in range(12))
            + f'<circle cx="72" cy="46" r="27" fill="none" stroke="{A}" stroke-width="6"/>'
            f'<circle cx="72" cy="46" r="20" fill="{GY}"/><circle cx="72" cy="46" r="6" fill="{DK}"/>' + furos
            + f'<path d="M90 28 A24 24 0 0 1 90 64" fill="none" stroke="{RD}" stroke-width="10"/>')


def p_alertas():
    """Bandeira amarela com exclamacao."""
    return (f'<path d="M34 8 V92" stroke="{W}" stroke-width="7"/>'
            f'<path d="M38 14 Q60 4 80 14 T122 14 V54 Q100 64 80 54 T38 54 Z" fill="{A}"/>'
            f'<rect x="76" y="22" width="9" height="19" rx="4" fill="{DK}"/><circle cx="80.5" cy="48" r="5" fill="{DK}"/>')


def p_stints():
    """Linha do tempo de stints: barras de tamanhos diferentes, o ultimo (em andamento) em verde."""
    t = ""
    for y, x2, cor in ((14, 100, GY), (40, 118, A), (66, 74, GR)):
        t += (f'<rect x="44" y="{y}" width="{x2 - 44}" height="22" rx="7" fill="{cor}"/>'
              f'<circle cx="30" cy="{y + 11}" r="9" fill="#3A3C43"/><circle cx="30" cy="{y + 11}" r="4.5" fill="{W}"/>')
    return t


def p_tendencia():
    """Voltas limpas (pontos) com reta de tendencia caindo = ritmo melhorando."""
    pts = ((32, 28), (46, 44), (58, 32), (72, 50), (86, 44), (100, 60), (112, 54))
    return (f'<path d="M22 10 V90 H128" fill="none" stroke="{W}" stroke-width="5"/>'
            + "".join(f'<circle cx="{x}" cy="{y}" r="6" fill="{A}"/>' for x, y in pts)
            + f'<path d="M30 30 L110 66" stroke="{GR}" stroke-width="7"/><path d="M98 70 L116 70 L110 54 Z" fill="{GR}" stroke="{GR}" stroke-width="3"/>')


def p_todas_classes():
    """Tres linhas de classificacao com a etiqueta de cada classe (Hypercar, LMP2, GT3)."""
    t = ""
    for y, cor in ((10, RD), (36, PU), (62, GR)):
        t += (f'<rect x="20" y="{y}" width="104" height="24" rx="7" fill="{GY}"/><rect x="20" y="{y}" width="26" height="24" rx="7" fill="{cor}"/>'
              f'<rect x="54" y="{y + 9}" width="54" height="6" rx="3" fill="{DK}"/>')
    return t


def p_manter_topo():
    """Janela da frente sobre a de tras, com seta para cima."""
    return (f'<rect x="18" y="34" width="72" height="56" rx="9" fill="{GY}"/>'
            f'<rect x="46" y="12" width="80" height="58" rx="9" fill="{A}"/><rect x="46" y="12" width="80" height="14" rx="7" fill="{AM2}"/>'
            f'<path d="M86 62 V36 M74 46 L86 34 L98 46" fill="none" stroke="{DK}" stroke-width="7"/>')


def p_restaurar():
    """Cantos de enquadramento + 100%."""
    cantos = (f'<path d="M24 28 V10 H42 M102 10 H120 V28 M24 62 V80 H42 M102 80 H120 V62" fill="none" stroke="{A}" stroke-width="8"/>')
    return cantos + letra("100%", 30, 72, 45, W, 0.86)


def p_diagnostico():
    """Lupa sobre um sinal de batimento."""
    return (f'<circle cx="60" cy="44" r="31" fill="none" stroke="{A}" stroke-width="8"/><path d="M83 67 L116 90" stroke="{A}" stroke-width="12"/>'
            f'<path d="M36 46 H48 L54 30 L65 60 L71 46 H84" fill="none" stroke="{W}" stroke-width="5"/>')


# ------------------------------------------------------------------ catalogo
JANELAS = [
    ("janela_telemetria", ["TELEMETRIA"], gi.p_telemetria), ("janela_voltas", ["VOLTAS"], gi.p_voltas),
    ("janela_classificacao", ["CLASSIF."], gi.p_classificacao), ("janela_clima", ["CLIMA"], gi.p_clima),
    ("janela_combustivel", ["COMBUSTÍVEL"], gi.p_combustivel), ("janela_forca_g", ["FORÇA G"], gi.p_forca_g),
    ("janela_energia", ["ENERGIA"], p_energia), ("janela_pneus", ["PNEUS E", "FREIOS"], p_pneus_freios),
    ("janela_danos", ["DANOS"], gi.p_danos), ("janela_alertas", ["ALERTAS"], p_alertas),
    ("janela_stints", ["STINTS"], p_stints), ("janela_tendencia", ["TENDÊNCIA"], p_tendencia),
]
CONTROLES = [  # (arquivo, rotulo, pictograma, tem_variante_desligada)
    ("ctrl_iniciar", ["INICIAR", "OVERLAY"], gi.p_play, False), ("ctrl_fechar", ["FECHAR", "OVERLAY"], gi.p_fechar, False),
    ("ctrl_forcar_fechamento", ["FORÇAR", "FECHAMENTO"], gi.p_forcar, False),
    ("ctrl_economia_cpu", ["ECONOMIA", "DE CPU"], gi.p_chip, True), ("ctrl_travar_posicao", ["TRAVAR", "POSIÇÃO"], gi.p_cadeado, True),
    ("ctrl_aparecer_sozinho", ["APARECER", "SOZINHO"], gi.p_olho, True), ("ctrl_zerar_pico_g", ["ZERAR", "PICO DE G"], gi.p_zerar_g, False),
    ("ctrl_classif_todas", ["TODAS AS", "CLASSES"], p_todas_classes, True), ("ctrl_manter_topo", ["MANTER NO", "TOPO"], p_manter_topo, True),
    ("ctrl_restaurar_tamanhos", ["TAMANHO", "PADRÃO"], p_restaurar, False),
]
SUPORTE = [
    ("sup_demo", ["MODO", "DEMO"], gi.p_frasco), ("sup_log", ["ABRIR", "LOG"], gi.p_doc), ("sup_pasta_overlay", ["PASTA DO", "OVERLAY"], gi.p_pasta),
    ("sup_pasta_suporte", ["SUPORTE"], gi.p_engrenagem), ("sup_voltar", ["VOLTAR"], gi.p_voltar),
    ("sup_atalhos", ["LISTA DE", "ATALHOS"], gi.p_teclado), ("sup_testes", ["RODAR", "TESTES"], gi.p_escudo_ok),
    ("sup_guia", ["GUIA", "RÁPIDO"], gi.p_livro), ("sup_roteiro", ["ROTEIRO", "VALIDAÇÃO"], gi.p_prancheta),
    ("sup_diagnostico", ["RODAR", "DIAGNÓSTICO"], p_diagnostico), ("sup_ver_diagnostico", ["VER", "DIAGNÓSTICO"], gi.p_doc),
]


def main():
    import cairosvg
    for sub in ("svg", "png", "variantes_desligado/svg", "variantes_desligado/png"):
        os.makedirs(f"{SAIDA}/{sub}", exist_ok=True)
    itens = {}

    def salvar(nome, svg, sub=""):
        base = f"{SAIDA}/{sub}" if sub else SAIDA
        open(f"{base}/svg/{nome}.svg", "w", encoding="utf-8").write(svg)
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=f"{base}/png/{nome}.png", output_width=144, output_height=144)

    for nome, rot, fn in JANELAS:
        salvar(nome, gi.moldura(fn(), rot, selo="on"))
        salvar(nome + "_desligada", gi.moldura(fn(), rot, selo="off", apagado=True), "variantes_desligado")
        itens[nome] = nome
    for nome, rot, fn, off in CONTROLES:
        salvar(nome, gi.moldura(fn(), rot))
        if off:
            salvar(nome + "_desligado", gi.moldura(fn(), rot, selo="off", apagado=True), "variantes_desligado")
        itens[nome] = nome
    for nome, rot, fn in SUPORTE:
        salvar(nome, gi.moldura(fn(), rot)); itens[nome] = nome
    salvar("livre", gi.moldura(None))
    import shutil
    shutil.rmtree(f"{SAIDA}/_base_tmp", ignore_errors=True)
    return itens


if __name__ == "__main__":
    print(len(main()), "icones")
