#!/usr/bin/env python3
"""Layout do perfil Stream Deck XL 'Overlay LMU' (chaves "coluna,linha") + previas. Uso: python layout_previa_lmu.py <pasta_base>"""
import json, sys
from PIL import Image, ImageDraw, ImageFont
BASE = sys.argv[1]
P = f"{BASE}/icones/png"
PRINCIPAL = {}
for i, n in enumerate(["telemetria", "voltas", "classificacao", "clima", "combustivel", "forca_g", "energia", "pneus",
                       "danos", "alertas", "stints", "tendencia"]):
    PRINCIPAL[(i % 8, i // 8)] = f"janela_{n}"
PRINCIPAL.update({
    (4, 1): "ctrl_classif_todas", (5, 1): "ctrl_manter_topo", (6, 1): "ctrl_restaurar_tamanhos", (7, 1): "ctrl_zerar_pico_g",
    (0, 2): "ctrl_economia_cpu", (1, 2): "ctrl_aparecer_sozinho", (2, 2): "ctrl_travar_posicao",
    (5, 2): "sup_demo", (6, 2): "sup_log", (7, 2): "sup_pasta_overlay",
    (0, 3): "ctrl_iniciar", (1, 3): "ctrl_fechar", (2, 3): "ctrl_forcar_fechamento", (7, 3): "sup_pasta_suporte",
    (3, 3): "janela_luz_abs", (4, 3): "janela_luz_tc", (5, 3): "janela_retorno", (6, 3): "janela_estrategia"})
SUP = {(0, 0): "sup_voltar", (1, 0): "sup_atalhos", (2, 0): "sup_guia", (3, 0): "sup_roteiro", (4, 0): "sup_testes",
       (5, 0): "sup_diagnostico", (6, 0): "sup_ver_diagnostico"}


def previa(lay, titulo, destino):
    K, G, M = 120, 14, 36
    W = 8 * K + 7 * G + 2 * M; H = 4 * K + 3 * G + 2 * M + 40
    im = Image.new("RGB", (W, H), (20, 20, 24)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Bold.otf", 18)
    fs = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Regular.otf", 12)
    d.text((M, 10), titulo, fill=(244, 244, 244), font=f)
    for r in range(4):
        for c in range(8):
            x, y = M + c * (K + G), 40 + M // 2 + r * (K + G)
            nome = lay.get((c, r), "livre")
            ic = Image.open(f"{P}/{nome}.png").convert("RGB").resize((K, K), Image.LANCZOS)
            im.paste(ic, (x, y)); d.rectangle([x - 1, y - 1, x + K, y + K], outline=(60, 60, 66))
            if nome == "livre":
                d.text((x + 3, y + K - 14), f"{c},{r}", fill=(120, 120, 128), font=fs)
    im.save(destino)


previa(PRINCIPAL, "Overlay LMU - Pagina principal - Stream Deck XL (8 colunas x 4 linhas = 32 botoes)", f"{BASE}/previa_pagina_principal_lmu.png")
previa(SUP, "Overlay LMU - Pasta Suporte (tecla 0,0 reservada para Voltar)", f"{BASE}/previa_pasta_suporte_lmu.png")
json.dump({"principal": {f"{c},{r}": n for (c, r), n in PRINCIPAL.items()}, "suporte": {f"{c},{r}": n for (c, r), n in SUP.items()}},
          open(f"{BASE}/layout_lmu.json", "w"), indent=1)
print(len(PRINCIPAL), len(SUP))
