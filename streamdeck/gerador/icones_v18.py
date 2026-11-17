# -*- coding: utf-8 -*-
"""Pictogramas dos 8 paineis novos da 1.8 (iRacing e LMU). Mesmo sistema visual da biblioteca (area x 18..126, y 6..94).
Uso: pictogramas(A, W, DK, GY, RD, GR, AM2, letra) -> lista de (arquivo, rotulo, funcao). Desenho original."""
import math


def pictogramas(A, W, DK, GY, RD, GR, AM2, letra):
    def p_vazao():
        """Mapa de calor 5x4 (azul -> vermelho) com a celula atual marcada."""
        cores = ["#2B6CFF", "#1FB6C9", "#3FCB5B", "#E8D335", "#F28A1E", "#E5342F"]
        s = ""
        for r in range(4):
            for c in range(5):
                k = min(5, max(0, (c + (3 - r)) * 6 // 8))
                s += f'<rect x="{22 + c*21}" y="{12 + r*19}" width="18" height="16" rx="3" fill="{cores[k]}"/>'
        return s + f'<rect x="64" y="31" width="22" height="20" rx="4" fill="none" stroke="{W}" stroke-width="4"/>'

    def p_marcha():
        """Degraus de marcha (1..6) com a faixa mais eficiente em destaque."""
        alt = (20, 32, 44, 56, 66, 74)
        s = "".join(f'<rect x="{22 + i*18}" y="{86 - h}" width="14" height="{h}" rx="3" fill="{(A if i == 3 else GY)}"/>' for i, h in enumerate(alt))
        return s + f'<path d="M22 86 H128" stroke="{W}" stroke-width="4"/>' + letra("G", 18, 22 + 3 * 18 + 7, 86 - 56 - 11, W, 0.9)

    def p_destino():
        """Rosca: a fundo (vermelho), parcial (ambar) e solto (cinza)."""
        cx, cy, r = 72, 50, 34
        def arco(a0, a1, cor):
            x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
            x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
            lg = 1 if (a1 - a0) > math.pi else 0
            return f'<path d="M{x0:.1f} {y0:.1f} A{r} {r} 0 {lg} 1 {x1:.1f} {y1:.1f}" fill="none" stroke="{cor}" stroke-width="15"/>'
        t = 2 * math.pi
        a = -math.pi / 2
        return arco(a, a + t * 0.52, RD) + arco(a + t * 0.52, a + t * 0.86, A) + arco(a + t * 0.86, a + t * 0.998, GY) + \
            f'<path d="M72 28 q-9 12 0 17 q9 -5 0 -17" fill="{W}"/>'

    def p_digiflag():
        """Bandeira verde ondulada no mastro."""
        return (f'<rect x="26" y="10" width="6" height="82" rx="3" fill="{W}"/>'
                f'<path d="M34 14 C52 6 62 24 80 16 C96 10 104 14 112 12 L112 54 C104 56 96 52 80 58 C62 66 52 48 34 56 Z" fill="{GR}"/>'
                f'<path d="M34 14 C52 6 62 24 80 16 C96 10 104 14 112 12" fill="none" stroke="{W}" stroke-width="3" opacity=".6"/>')

    def p_ultrapassagem():
        """Carro seguido por outro que se aproxima, com a seta de alerta."""
        return (f'<rect x="52" y="10" width="40" height="30" rx="9" fill="{W}"/><rect x="58" y="16" width="28" height="9" rx="3" fill="{DK}"/>'
                f'<rect x="52" y="56" width="40" height="30" rx="9" fill="{RD}"/><rect x="58" y="62" width="28" height="9" rx="3" fill="{DK}"/>'
                f'<path d="M104 78 L104 44 M94 54 L104 42 L114 54" fill="none" stroke="{A}" stroke-width="7"/>'
                f'<path d="M36 40 L36 74 M26 64 L36 76 L46 64" fill="none" stroke="{A}" stroke-width="7" opacity=".0"/>')

    def p_calendario():
        """Calendario com a corrida do dia destacada."""
        s = f'<rect x="22" y="16" width="100" height="72" rx="8" fill="{GY}"/><rect x="22" y="16" width="100" height="20" rx="8" fill="{A}"/>'
        s += f'<rect x="40" y="8" width="8" height="16" rx="4" fill="{W}"/><rect x="96" y="8" width="8" height="16" rx="4" fill="{W}"/>'
        for r in range(2):
            for c in range(5):
                hl = (r == 1 and c == 2)
                s += f'<rect x="{30 + c*18}" y="{44 + r*20}" width="13" height="13" rx="3" fill="{RD if hl else DK}" opacity="{1 if hl else .55}"/>'
        return s

    def p_hibrido():
        """Bateria com raio (energia hibrida / Boost)."""
        return (f'<rect x="26" y="26" width="86" height="48" rx="9" fill="none" stroke="{W}" stroke-width="7"/><rect x="114" y="40" width="9" height="20" rx="3" fill="{W}"/>'
                f'<rect x="34" y="34" width="46" height="32" rx="4" fill="{GR}"/>'
                f'<path d="M78 14 L58 54 L72 54 L64 88 L92 44 L76 44 L86 14 Z" fill="{A}" stroke="{DK}" stroke-width="3"/>')

    def p_sessao():
        """Cronometro (tempo da sessao)."""
        return (f'<circle cx="72" cy="54" r="34" fill="none" stroke="{W}" stroke-width="7"/><rect x="62" y="8" width="20" height="9" rx="3" fill="{W}"/>'
                f'<path d="M72 54 L72 32" stroke="{A}" stroke-width="7"/><path d="M72 54 L90 64" stroke="{W}" stroke-width="6"/><circle cx="72" cy="54" r="5" fill="{A}"/>')

    return [("janela_vazao", ["MAPA DE", "VAZÃO"], p_vazao), ("janela_marcha", ["EFIC. POR", "MARCHA"], p_marcha),
            ("janela_destino", ["DESTINO", "COMBUST."], p_destino), ("janela_digiflag", ["DIGIFLAG"], p_digiflag),
            ("janela_ultrapassagem", ["ALERTA", "ULTRAP."], p_ultrapassagem), ("janela_calendario", ["CALENDÁRIO"], p_calendario),
            ("janela_hibrido", ["ENERGIA", "HÍBRIDA"], p_hibrido), ("janela_sessao", ["TEMPO DA", "SESSÃO"], p_sessao)]
