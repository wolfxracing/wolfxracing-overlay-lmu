#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Biblioteca de icones do Overlay iRacing para o Stream Deck XL (144x144, SVG + PNG).

Sistema visual (padrao unico):
  fundo     : fibra de carbono (malha hexagonal) grafite, vinheta suave
  acento    : ambar (padrao), vermelho (perigo), verde (iniciar/ligado), cinza (neutro), roxo (melhor setor)
  traco     : 6 px (contorno), 3,5 px (detalhe), pontas e juntas arredondadas
  tipografia: Inter ExtraBold Italic condensada (x0,80), CAIXA ALTA, sombra projetada; convertida em CURVAS (SVG autonomo)
  desenho   : original; o estilo e inspirado no pacote "iRacing Icons" que voce usa (fundo escuro, ambar, texto italico).
"""
import csv, math, os, sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
import cairosvg
from PIL import Image, ImageDraw

SAIDA = sys.argv[1]
FONTE = "/usr/share/fonts/opentype/inter/Inter-ExtraBoldItalic.otf"
_f = TTFont(FONTE); GS = _f.getGlyphSet(); CMAP = _f.getBestCmap(); UPM = _f["head"].unitsPerEm; HMTX = _f["hmtx"]

A, W, DK = "url(#amb)", "#F4F4F4", "#101013"
GY, RD, GR, PU, AM2 = "url(#gry)", "url(#red)", "url(#grn)", "url(#pur)", "url(#amb2)"
SW, SD = 6, 3.5


def tpath(txt, size, xs=0.80):
    s, x, ds = size / UPM, 0.0, []
    for ch in txt:
        gn = CMAP.get(ord(ch))
        if gn is None:
            continue
        pen = SVGPathPen(GS)
        GS[gn].draw(TransformPen(pen, (s * xs, 0, 0, -s, x, 0)))
        ds.append(pen.getCommands())
        x += HMTX[gn][0] * s * xs
    return " ".join(ds), x


def rotulo(linhas):
    n, saida = len(linhas), []
    base = 24 if n == 1 else 22
    ys = [129] if n == 1 else [108, 132]
    for txt, y in zip(linhas, ys):
        d, w = tpath(txt, base)
        k = min(1.0, 122.0 / w)
        if k < 1.0:
            d, w = tpath(txt, base * k)
        x = 72 - w / 2
        saida.append(f'<path transform="translate({x+1.8:.2f} {y+1.8})" d="{d}" fill="#000" opacity=".9"/>'
                     f'<path transform="translate({x:.2f} {y})" d="{d}" fill="#F7F7F7"/>')
    return "".join(saida)


def letra(txt, size, cx, cy, fill=DK, xs=0.9):
    d, w = tpath(txt, size, xs)
    return f'<path transform="translate({cx - w/2:.2f} {cy + size*0.36:.2f})" d="{d}" fill="{fill}"/>'


def p_luz_abs():
    """Aro com ABS e dois arcos de freio (simbolo do painel de instrumentos)."""
    return (f'<circle cx="72" cy="48" r="31" fill="none" stroke="{A}" stroke-width="7"/>'
            + letra("ABS", 25, 72, 48, W, 0.84)
            + f'<path d="M28 24 A34 34 0 0 0 28 72" fill="none" stroke="{W}" stroke-width="6"/>'
              f'<path d="M116 24 A34 34 0 0 1 116 72" fill="none" stroke="{W}" stroke-width="6"/>')


def p_luz_tc():
    """Carro derrapando: rastros ondulados embaixo (perda de tracao)."""
    return (f'<path d="M24 58 Q24 48 34 46 L48 26 H94 L108 46 Q120 48 120 58 V64 H24 Z" fill="{A}"/>'
            f'<path d="M55 32 H70 V46 H47 Z" fill="{DK}"/><path d="M76 32 H90 L100 46 H76 Z" fill="{DK}"/>'
            f'<circle cx="48" cy="66" r="11" fill="#3A3C43" stroke="{W}" stroke-width="4"/>'
            f'<circle cx="98" cy="66" r="11" fill="#3A3C43" stroke="{W}" stroke-width="4"/>'
            f'<path d="M22 86 q10 -9 20 0 t20 0 t20 0 t20 0 t20 0" fill="none" stroke="{W}" stroke-width="5"/>')


def p_retorno():
    """Semaforo PARE / CEDA / LIVRE (vermelho, ambar, verde)."""
    return (f'<rect x="46" y="4" width="52" height="90" rx="16" fill="#3A3C43"/>'
            f'<circle cx="72" cy="22" r="11" fill="{RD}"/><circle cx="72" cy="49" r="11" fill="{A}"/>'
            f'<circle cx="72" cy="76" r="11" fill="{GR}"/>'
            f'<path d="M110 60 Q124 60 124 44 V34 M116 42 L124 32 L132 42" fill="none" stroke="{W}" stroke-width="5"/>')


def p_estrategia():
    """Pneu e gota de chuva: troca de composto conforme o tempo."""
    t = '<circle cx="50" cy="56" r="30" fill="#3A3C43"/>'
    t += "".join(f'<path d="M{50 + 23*math.cos(math.radians(i*30)):.1f} {56 + 23*math.sin(math.radians(i*30)):.1f} L{50 + 29*math.cos(math.radians(i*30)):.1f} {56 + 29*math.sin(math.radians(i*30)):.1f}" stroke="#8C919A" stroke-width="3"/>' for i in range(12))
    return (t + f'<circle cx="50" cy="56" r="19" fill="none" stroke="{A}" stroke-width="6"/><circle cx="50" cy="56" r="7" fill="{DK}"/>'
            f'<g transform="translate(-8 14)"><path d="M106 12 C106 12 88 36 88 50 A18 18 0 0 0 124 50 C124 36 106 12 106 12 Z" fill="{W}"/>'
            f'<path d="M98 52 A9 9 0 0 0 106 60" fill="none" stroke="{GY}" stroke-width="4"/></g>')


DEFS = f"""<defs>
<linearGradient id="amb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFD84D"/><stop offset="1" stop-color="#F29A00"/></linearGradient>
<linearGradient id="amb2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E0A300"/><stop offset="1" stop-color="#9A5C00"/></linearGradient>
<linearGradient id="red" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FF6A5C"/><stop offset="1" stop-color="#D1262B"/></linearGradient>
<linearGradient id="grn" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7CE38B"/><stop offset="1" stop-color="#2E9E4C"/></linearGradient>
<linearGradient id="gry" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E6E8EC"/><stop offset="1" stop-color="#8C919A"/></linearGradient>
<linearGradient id="pur" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C77DFF"/><stop offset="1" stop-color="#8A35D6"/></linearGradient>
<pattern id="hex" width="12.124" height="21" patternUnits="userSpaceOnUse">
<path d="M6.062 0 L12.124 3.5 L12.124 10.5 L6.062 14 L0 10.5 L0 3.5 Z M0 14 L6.062 17.5 L6.062 24.5 M12.124 14 L6.062 17.5" fill="none" stroke="#222226" stroke-width="1"/>
</pattern>
<radialGradient id="vig" cx="50%" cy="42%" r="75%"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".62"/></radialGradient>
</defs>"""


def moldura(corpo, linhas=None, selo=None, apagado=False):
    """selo: None | 'on' | 'off' (olho no canto: janela visivel/oculta). apagado: pictograma esmaecido."""
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="144" height="144" viewBox="0 0 144 144">', DEFS,
         '<rect width="144" height="144" fill="#0C0C0F"/><rect width="144" height="144" fill="url(#hex)"/>'
         '<rect width="144" height="144" fill="url(#vig)"/>']
    if corpo:
        s.append(f'<g opacity="{0.30 if apagado else 1}" stroke-linecap="round" stroke-linejoin="round">{corpo}</g>')
    if selo:
        s.append(f'<g transform="translate(122 15)"><rect x="-15" y="-11" width="30" height="22" rx="7" fill="#0C0C0F" opacity=".85"/>'
                 f'<path d="M-10 0 Q0 -9 10 0 Q0 9 -10 0 Z" fill="{W}"/><circle r="3.6" fill="{DK}"/>'
                 + ('<path d="M-11 8 L11 -8" stroke="#0C0C0F" stroke-width="6" stroke-linecap="round"/>'
                    '<path d="M-11 8 L11 -8" stroke="#FF4B40" stroke-width="3.2" stroke-linecap="round"/>' if selo == "off" else "")
                 + "</g>")
    if linhas:
        s.append(rotulo(linhas))
    s.append("</svg>")
    return "".join(s)


# ------------------------------------------------------------------ pictogramas (area x 18..126, y 6..94)
def p_play():
    return f'<path d="M50 18 L50 80 L104 49 Z" fill="{GR}" stroke="{GR}" stroke-width="9"/>'


def p_fechar():
    return (f'<circle cx="72" cy="49" r="35" fill="none" stroke="{RD}" stroke-width="8"/>'
            f'<path d="M57 34 L87 64 M87 34 L57 64" stroke="{RD}" stroke-width="9" fill="none"/>')


def p_forcar():
    pts = " ".join(f"{72 + 40*math.cos(math.radians(22.5 + i*45)):.1f},{49 + 40*math.sin(math.radians(22.5 + i*45)):.1f}" for i in range(8))
    return (f'<polygon points="{pts}" fill="{RD}" stroke="{RD}" stroke-width="4"/>'
            f'<path d="M79 18 L56 54 L69 54 L63 82 L90 43 L76 43 Z" fill="{W}"/>')


def p_selo_letra(txt, tam=58):
    return (f'<rect x="38" y="12" width="68" height="76" rx="12" fill="{A}"/>' + letra(txt, tam, 74, 50))


def p_selo_auto():
    return (f'<rect x="28" y="22" width="88" height="56" rx="12" fill="{A}"/>' + letra("AUTO", 30, 73, 50))


def p_chip():
    pinos = "".join(f'<path d="M{x} 14 V26 M{x} 74 V86" stroke="{W}" stroke-width="4"/>' for x in (54, 72, 90))
    pinos += "".join(f'<path d="M30 {y} H42 M102 {y} H114" stroke="{W}" stroke-width="4"/>' for y in (32, 50, 68))
    return (pinos + f'<rect x="42" y="24" width="60" height="52" rx="8" fill="{A}"/>'
            f'<rect x="54" y="35" width="36" height="30" rx="4" fill="{DK}"/>'
            f'<path d="M74 38 L63 52 H72 L69 62 L82 47 H73 Z" fill="{A}" stroke="none"/>')


def p_cadeado():
    return (f'<path d="M52 44 V34 A20 20 0 0 1 92 34 V44" fill="none" stroke="{W}" stroke-width="8"/>'
            f'<rect x="38" y="44" width="68" height="44" rx="9" fill="{A}"/>'
            f'<circle cx="72" cy="62" r="6" fill="{DK}"/><rect x="69.5" y="64" width="5" height="14" rx="2" fill="{DK}"/>')


def p_olho():
    return (f'<path d="M20 49 Q72 -4 124 49 Q72 102 20 49 Z" fill="{A}"/>'
            f'<circle cx="72" cy="49" r="22" fill="{W}"/><circle cx="72" cy="49" r="11" fill="{DK}"/>')


def p_zerar_g():
    return (f'<path d="M104 30 A36 36 0 1 0 108 56" fill="none" stroke="{A}" stroke-width="8"/>'
            f'<path d="M92 24 L112 26 L106 44 Z" fill="{A}" stroke="{A}" stroke-width="3"/>' + letra("G", 38, 72, 52, W))


def p_borracha():
    return (f'<path d="M28 58 L70 14 L112 46 L72 84 Z" fill="{A}"/>'
            f'<path d="M28 58 L50 76 L72 84 L36 84 Z" fill="{GY}"/>'
                        f'<path d="M104 14 L110 6 M116 22 L124 18" stroke="{W}" stroke-width="4"/>')


def p_frasco():
    return (f'<path d="M58 14 V40 L32 84 Q28 92 38 92 H106 Q116 92 112 84 L86 40 V14" fill="{A}"/>'
            f'<rect x="52" y="9" width="40" height="9" rx="4" fill="{W}"/>'
            f'<circle cx="66" cy="76" r="5" fill="{DK}"/><circle cx="82" cy="68" r="4" fill="{DK}"/><circle cx="76" cy="82" r="3" fill="{DK}"/>')


def p_doc():
    return (f'<path d="M40 10 H86 L108 32 V90 H40 Z" fill="{A}"/><path d="M86 10 V32 H108 Z" fill="{W}"/>'
            + "".join(f'<rect x="50" y="{y}" width="48" height="5" rx="2.5" fill="{DK}"/>' for y in (46, 58, 70)))


def p_pasta():
    return (f'<path d="M22 22 H56 L66 32 H122 V86 H22 Z" fill="{A}"/><rect x="22" y="40" width="100" height="46" rx="4" fill="{AM2}"/>'
            f'<rect x="22" y="40" width="100" height="6" fill="{W}"/>')


def p_teclado():
    t = f'<rect x="16" y="22" width="112" height="64" rx="10" fill="none" stroke="{A}" stroke-width="6"/>'
    t += "".join(f'<rect x="{26 + k*15}" y="{32 + r*15}" width="10" height="9" rx="2" fill="{W}"/>' for r in range(2) for k in range(7))
    return t + f'<rect x="44" y="62" width="56" height="10" rx="3" fill="{A}"/>'


def p_engrenagem():
    dentes = "".join(f'<path d="M{72 + 28*math.cos(math.radians(i*30)):.1f} {49 + 28*math.sin(math.radians(i*30)):.1f} L{72 + 42*math.cos(math.radians(i*30)):.1f} {49 + 42*math.sin(math.radians(i*30)):.1f}" stroke="{A}" stroke-width="11" stroke-linecap="butt"/>' for i in range(12))
    return dentes + f'<circle cx="72" cy="49" r="32" fill="{A}"/><circle cx="72" cy="49" r="13" fill="{DK}"/>'


def p_escudo_ok():
    return (f'<path d="M72 8 L112 22 V52 Q112 76 72 92 Q32 76 32 52 V22 Z" fill="{A}"/>'
            f'<path d="M52 50 L67 65 L94 34" fill="none" stroke="{DK}" stroke-width="9"/>')


def p_emblema():
    return (f'<path d="M72 8 L112 22 V52 Q112 76 72 92 Q32 76 32 52 V22 Z" fill="{A}"/><circle cx="72" cy="48" r="20" fill="{DK}"/>'
            f'<path d="M72 33 L77 44 L89 45 L80 53 L83 65 L72 59 L61 65 L64 53 L55 45 L67 44 Z" fill="{W}"/>')


def p_grafico():
    return (f'<path d="M24 12 V88 H126" fill="none" stroke="{W}" stroke-width="5"/>'
            f'<path d="M34 72 L58 50 L76 62 L100 30 L120 22" fill="none" stroke="{A}" stroke-width="7"/>'
            + "".join(f'<circle cx="{x}" cy="{y}" r="6" fill="{A}"/>' for x, y in ((34, 72), (58, 50), (76, 62), (100, 30), (120, 22))))


def p_livro():
    t = f'<path d="M20 20 L68 28 V90 L20 82 Z" fill="{A}"/><path d="M124 20 L76 28 V90 L124 82 Z" fill="{A}"/>'
    for y in (40, 54, 68):
        t += f'<path d="M28 {y} L58 {y+4} M116 {y} L86 {y+4}" stroke="{DK}" stroke-width="4"/>'
    return t


def p_prancheta():
    t = f'<rect x="32" y="16" width="80" height="76" rx="8" fill="{A}"/><rect x="54" y="8" width="36" height="16" rx="5" fill="{W}"/>'
    for i, y in enumerate((38, 54, 70)):
        t += f'<path d="M44 {y} l5 5 l9 -10" fill="none" stroke="{DK}" stroke-width="4"/><rect x="66" y="{y-3}" width="36" height="5" rx="2.5" fill="{DK}"/>'
    return t


def p_power(cor=A, ponto=False, corta=False):
    t = (f'<path d="M50 24 A36 36 0 1 0 94 24" fill="none" stroke="{cor}" stroke-width="9"/>'
         f'<path d="M72 8 V46" stroke="{cor}" stroke-width="9"/>')
    if ponto:
        t += f'<circle cx="72" cy="66" r="7" fill="{cor}"/>'
    if corta:
        t += f'<path d="M30 90 L114 12" stroke="#0C0C0F" stroke-width="13"/><path d="M30 90 L114 12" stroke="{RD}" stroke-width="7"/>'
    return t


def p_trofeu():
    return (f'<path d="M46 12 H98 V40 A26 26 0 0 1 46 40 Z" fill="{A}"/>'
            f'<path d="M46 20 H30 Q28 44 50 50 M98 20 H114 Q116 44 94 50" fill="none" stroke="{A}" stroke-width="6"/>'
            f'<rect x="66" y="64" width="12" height="14" fill="{A}"/><rect x="48" y="78" width="48" height="12" rx="4" fill="{GY}"/>')


def p_voltar():
    return f'<path d="M24 49 L62 14 V36 H120 V62 H62 V84 Z" fill="{A}" stroke="{A}" stroke-width="5"/>'


# ---- janelas
def p_telemetria():
    t = "".join(f'<rect x="{x}" y="{92-h}" width="22" height="{h}" rx="5" fill="{c}"/>' for x, h, c in ((26, 34, GY), (61, 50, RD), (96, 66, A)))
    return t + f'<path d="M26 40 A50 36 0 0 1 118 40" fill="none" stroke="{W}" stroke-width="4"/>'


def p_voltas():
    return (f'<circle cx="72" cy="54" r="34" fill="none" stroke="{A}" stroke-width="8"/><rect x="63" y="8" width="18" height="9" rx="3" fill="{W}"/>'
            f'<path d="M72 54 L89 34" stroke="{W}" stroke-width="7"/><circle cx="72" cy="54" r="6" fill="{W}"/>'
            f'<path d="M104 22 L110 15" stroke="{A}" stroke-width="6"/>')


def p_relativo():
    t = ""
    for y, c, w in ((14, GY, 84), (40, A, 96), (66, GY, 84)):
        t += (f'<rect x="22" y="{y}" width="{w}" height="22" rx="6" fill="{c}"/><rect x="28" y="{y+6}" width="14" height="10" rx="2" fill="{DK}"/>'
              f'<rect x="48" y="{y+9}" width="{w-36}" height="5" rx="2.5" fill="{DK}"/>')
    return t + f'<path d="M116 22 L122 14 L128 22 M116 78 L122 86 L128 78" fill="none" stroke="{W}" stroke-width="4"/>'


def p_classificacao():
    return (f'<rect x="22" y="56" width="32" height="34" fill="{GY}"/><rect x="56" y="38" width="32" height="52" fill="{A}"/><rect x="90" y="68" width="32" height="22" fill="#C98A4B"/>'
            f'<path d="M72 8 L77 20 L90 21 L80 30 L83 43 L72 36 L61 43 L64 30 L54 21 L67 20 Z" fill="{W}"/>')


def p_mapa():
    return (f'<path d="M30 74 Q22 46 44 30 Q62 18 80 28 Q96 36 110 24 Q128 24 122 48 Q112 62 112 76 Q108 92 84 90 L46 88 Q34 86 30 74 Z" fill="none" stroke="{W}" stroke-width="7"/>'
            f'<path d="M58 80 V94" stroke="{A}" stroke-width="5"/><circle cx="110" cy="24" r="9" fill="{A}"/><circle cx="46" cy="30" r="7" fill="{RD}"/>')


def p_radar():
    t = "".join(f'<circle cx="72" cy="52" r="{r}" fill="none" stroke="{A}" stroke-width="4"/>' for r in (14, 27, 40))
    return (t + f'<path d="M72 52 L104 28 A40 40 0 0 0 72 12 Z" fill="{A}" opacity=".40"/><path d="M72 52 L104 28" stroke="{W}" stroke-width="4"/>'
            f'<circle cx="72" cy="52" r="6" fill="{GR}"/><circle cx="46" cy="66" r="5" fill="{RD}"/><circle cx="92" cy="72" r="5" fill="{A}"/>')


def p_pneu():
    t = f'<circle cx="72" cy="50" r="42" fill="#3A3C43"/>'
    t += "".join(f'<path d="M{72 + 33*math.cos(math.radians(i*30)):.1f} {50 + 33*math.sin(math.radians(i*30)):.1f} L{72 + 41*math.cos(math.radians(i*30)):.1f} {50 + 41*math.sin(math.radians(i*30)):.1f}" stroke="#8C919A" stroke-width="4"/>' for i in range(12))
    return (t + f'<circle cx="72" cy="50" r="27" fill="none" stroke="{A}" stroke-width="7"/><circle cx="72" cy="50" r="17" fill="{DK}"/>'
            f'<circle cx="72" cy="50" r="6" fill="{A}"/>')


def p_setores():
    return (f'<rect x="20" y="42" width="34" height="26" rx="3" fill="{GR}"/><rect x="55" y="42" width="34" height="26" fill="{PU}"/><rect x="90" y="42" width="34" height="26" rx="3" fill="{A}"/>'
            f'<path d="M72 12 L84 28 H60 Z" fill="{W}"/><path d="M20 78 H124" stroke="{W}" stroke-width="4"/>'
            + "".join(f'<path d="M{x} 74 V88" stroke="{W}" stroke-width="4"/>' for x in (20, 55, 90, 124)))


def p_clima():
    nuvem = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{GY}"/>' for x, y, r in ((48, 40, 18), (72, 30, 24), (98, 42, 17)))
    return nuvem + f'<rect x="48" y="40" width="50" height="18" fill="{GY}"/>' + "".join(
        f'<path d="M{x} 68 L{x-7} 88" stroke="{A}" stroke-width="7"/>' for x in (52, 72, 92))


def p_danos():
    return (f'<rect x="34" y="8" width="48" height="84" rx="18" fill="{GY}"/><rect x="42" y="26" width="32" height="20" rx="6" fill="{DK}"/><rect x="42" y="64" width="32" height="16" rx="6" fill="{DK}"/>'
            f'<path d="M104 18 L124 56 H84 Z" fill="{RD}" stroke="{RD}" stroke-width="5"/><path d="M104 30 V44" stroke="{W}" stroke-width="5"/><circle cx="104" cy="50" r="2.6" fill="{W}"/>')


def p_combustivel():
    return (f'<rect x="28" y="10" width="54" height="80" rx="8" fill="{RD}"/><rect x="38" y="20" width="34" height="24" rx="3" fill="{DK}"/>'
            f'<path d="M82 40 H100 V70" fill="none" stroke="{W}" stroke-width="7"/><path d="M100 70 q-9 12 0 14 q9 -2 0 -14" fill="{W}"/>'
            f'<rect x="20" y="86" width="70" height="8" rx="3" fill="{W}"/>')


def p_forca_g():
    t = "".join(f'<circle cx="72" cy="50" r="{r}" fill="none" stroke="#8C919A" stroke-width="4"/>' for r in (14, 28, 42))
    return (t + '<path d="M26 50 H118 M72 6 V94" stroke="#8C919A" stroke-width="3"/>'
            f'<path d="M72 50 Q62 70 84 74 Q106 74 98 40" fill="none" stroke="{A}" stroke-width="7"/><circle cx="98" cy="38" r="9" fill="{W}"/>')


# ------------------------------------------------------------------ catalogo
# (arquivo, rotulo(linhas), pictograma, selo, variante_apagada)
JANELAS = [
    ("janela_telemetria", ["TELEMETRIA"], p_telemetria), ("janela_voltas", ["VOLTAS"], p_voltas),
    ("janela_relativo", ["RELATIVO"], p_relativo), ("janela_classificacao", ["CLASSIF."], p_classificacao),
    ("janela_mapa", ["MAPA"], p_mapa), ("janela_radar", ["RADAR"], p_radar),
    ("janela_pneus", ["PNEUS"], p_pneu), ("janela_setores", ["SETORES"], p_setores),
    ("janela_clima", ["CLIMA"], p_clima), ("janela_danos", ["DANOS"], p_danos),
    ("janela_combustivel", ["COMBUSTÍVEL"], p_combustivel), ("janela_forca_g", ["FORÇA G"], p_forca_g),
    ("janela_luz_abs", ["LUZ ABS"], p_luz_abs), ("janela_luz_tc", ["LUZ TC"], p_luz_tc),
    ("janela_retorno", ["RETORNO"], p_retorno), ("janela_estrategia", ["ESTRATÉGIA"], p_estrategia),
]
CONTROLES = [  # (arquivo, rotulo, pictograma, tem_variante_apagada)
    ("ctrl_iniciar", ["INICIAR", "OVERLAY"], p_play, False), ("ctrl_fechar", ["FECHAR", "OVERLAY"], p_fechar, False),
    ("ctrl_forcar_fechamento", ["FORÇAR", "FECHAMENTO"], p_forcar, False),
    ("perfil_auto", ["PERFIL", "AUTOMÁTICO"], p_selo_auto, False),
    ("perfil_treino", ["PERFIL", "TREINO"], lambda: p_selo_letra("T"), False),
    ("perfil_classificacao", ["PERFIL", "CLASSIF."], lambda: p_selo_letra("Q"), False),
    ("perfil_corrida", ["PERFIL", "CORRIDA"], lambda: p_selo_letra("R"), False),
    ("ctrl_economia_cpu", ["ECONOMIA", "DE CPU"], p_chip, True), ("ctrl_travar_posicao", ["TRAVAR", "POSIÇÃO"], p_cadeado, True),
    ("ctrl_aparecer_sozinho", ["APARECER", "SOZINHO"], p_olho, True),
    ("ctrl_zerar_pico_g", ["ZERAR", "PICO DE G"], p_zerar_g, False), ("ctrl_limpar_impactos", ["LIMPAR", "IMPACTOS"], p_borracha, False),
]
SUPORTE = [
    ("sup_demo", ["MODO", "DEMO"], p_frasco), ("sup_log", ["ABRIR", "LOG"], p_doc), ("sup_pasta_overlay", ["PASTA DO", "OVERLAY"], p_pasta),
    ("sup_atalhos", ["LISTA DE", "ATALHOS"], p_teclado), ("sup_pasta_suporte", ["SUPORTE"], p_engrenagem),
    ("sup_testes", ["RODAR", "TESTES"], p_escudo_ok), ("sup_emblemas", ["PASTA DE", "EMBLEMAS"], p_emblema),
    ("sup_historico", ["HISTÓRICO", "IR / SR"], p_grafico), ("sup_guia", ["GUIA", "RÁPIDO"], p_livro),
    ("sup_roteiro", ["ROTEIRO", "VALIDAÇÃO"], p_prancheta),
    ("sup_inicio_windows_on", ["INICIAR C/", "WINDOWS"], lambda: p_power(GR, True)),
    ("sup_inicio_windows_off", ["DESATIVAR", "INÍCIO"], lambda: p_power(RD, True, True)),
    ("sup_recordes", ["RECORDES", "PESSOAIS"], p_trofeu), ("sup_voltar", ["VOLTAR"], p_voltar),
]


def main():
    os.makedirs(f"{SAIDA}/svg", exist_ok=True); os.makedirs(f"{SAIDA}/png", exist_ok=True)
    os.makedirs(f"{SAIDA}/variantes_desligado/svg", exist_ok=True); os.makedirs(f"{SAIDA}/variantes_desligado/png", exist_ok=True)
    itens = {}

    def salvar(nome, svg, sub=""):
        base = f"{SAIDA}/{sub}" if sub else SAIDA
        open(f"{base}/svg/{nome}.svg", "w", encoding="utf-8").write(svg)
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=f"{base}/png/{nome}.png", output_width=144, output_height=144)

    for nome, rot, fn in JANELAS:
        salvar(nome, moldura(fn(), rot, selo="on"))
        salvar(nome + "_desligada", moldura(fn(), rot, selo="off", apagado=True), "variantes_desligado")
        itens[nome] = f"{SAIDA}/png/{nome}.png"
    for nome, rot, fn, off in CONTROLES:
        salvar(nome, moldura(fn(), rot))
        if off:
            salvar(nome + "_desligado", moldura(fn(), rot, selo="off", apagado=True), "variantes_desligado")
        itens[nome] = f"{SAIDA}/png/{nome}.png"
    for nome, rot, fn in SUPORTE:
        salvar(nome, moldura(fn(), rot)); itens[nome] = f"{SAIDA}/png/{nome}.png"
    salvar("livre", moldura(None)); itens["livre"] = f"{SAIDA}/png/livre.png"
    return itens


if __name__ == "__main__":
    print(len(main()), "icones")
