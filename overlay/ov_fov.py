# -*- coding: utf-8 -*-
"""Calculadora de FOV (campo de visao) para sim racing: matematica pura, sem Qt, igual nos dois jogos.

Geometria (vista de cima, olho na origem, tela central a distancia D, medida do olho ate o CENTRO da tela):
  - tela plana:  FOV vertical = 2*atan(h/2 / D);  FOV horizontal = 2*atan(w/2 / D)
  - tela curva (raio R, concava para o piloto): as bordas ficam mais perto; corda c = 2R sen(w/2R), flecha s = R(1 - cos(w/2R)),
    FOV horizontal = 2*atan((c/2) / (D - s)); o vertical no centro nao muda
  - triplo: as laterais ficam a mesma distancia D do olho, viradas para ele. O angulo entre uma lateral e a central e
    (FOV_central + FOV_lateral)/2 + angulo da moldura; o FOV total e FOV_central + 2*(FOV_lateral + angulo da moldura).
    A moldura (por emenda) vale beta = atan(moldura / distancia do olho a borda da tela); negativa = telas sobrepostas (kit sem moldura).
  Modelo do triplo (build ad, explicito): as tres telas ficam a mesma distancia D do olho (olho -> CENTRO de cada tela), com a central de
  frente e cada lateral girada de phi em torno do olho e virada para ele. Cada tela e um arco de circulo (plana = raio infinito) com a mesma
  curvatura da central, salvo se a lateral tiver curvatura propria; as bordas de uma tela curva ficam 'flecha' mais perto do olho. A moldura
  e o vao angular entre a borda da central e a borda interna da lateral, visto do olho: beta = atan(moldura / distancia do olho a borda da
  central) (aproximacao; no vao real as telas tambem ficam inclinadas). Laterais de tamanho diferente entram com o proprio FOV e a propria flecha.
  Todos os pontos (bordas, cantos traseiros) sao calculados na planta com a MESMA geometria, entao FOV total, angulo das laterais, largura X,
  profundidade Y e as medidas de fita vem do mesmo desenho e sao coerentes entre si (o teste confere pelo angulo da borda externa).
  Geometrias fisicamente impossiveis (FOV total >= 360 graus, largura/profundidade nao positivas, raio de curvatura invalido) levantam ValueError.
E o tamanho ocupado (largura X e profundidade Y, em cm) e as medidas para conferir o angulo com uma fita metrica.
Tudo em cm e graus. Valores de entrada invalidos levantam ValueError com mensagem em portugues."""
import math

ESPESSURA_PAINEL_CM = 8.0          # espessura tipica do painel + traseira, usada na profundidade
MARGEM_QUADRO_CM = 2.0             # borda externa/estrutura da tela somada a largura total
ASPECTOS = {"16:9": (16.0, 9.0), "21:9": (21.0, 9.0), "32:9": (32.0, 9.0)}
CURVATURAS_MM = (1000, 1500, 1800, 3000, 4000)
POL = 2.54

# Qual numero cada jogo pede (conforme a referencia da calculadora; confirme no menu do jogo, que muda entre versoes)
JOGOS = (("iRacing", "horizontal"), ("Le Mans Ultimate", "vertical"), ("Assetto Corsa / ACC", "vertical"), ("AMS2", "horizontal"),
         ("BeamNG", "vertical"), ("Live for Speed", "horizontal"))

EXEMPLOS = (
    ("Monitor 27\" 16:9 a 70 cm", {"dist": 70.0, "diag": 27.0 * POL, "aspecto": "16:9", "curva": None, "triplo": False, "bezel_mm": 0.0}),
    ("Monitor 32\" 16:9 a 80 cm", {"dist": 80.0, "diag": 32.0 * POL, "aspecto": "16:9", "curva": None, "triplo": False, "bezel_mm": 0.0}),
    ("Ultrawide 34\" 21:9 curvo 1500R a 80 cm", {"dist": 80.0, "diag": 34.0 * POL, "aspecto": "21:9", "curva": 1500, "triplo": False, "bezel_mm": 0.0}),
    ("Super ultrawide 49\" 32:9 curvo 1800R a 90 cm", {"dist": 90.0, "diag": 49.0 * POL, "aspecto": "32:9", "curva": 1800, "triplo": False, "bezel_mm": 0.0}),
    ("Triplo 3x27\" 16:9 a 80 cm (moldura 15 mm)", {"dist": 80.0, "diag": 27.0 * POL, "aspecto": "16:9", "curva": None, "triplo": True, "bezel_mm": 15.0}),
    ("Triplo 3x32\" 16:9 a 90 cm (moldura 10 mm)", {"dist": 90.0, "diag": 32.0 * POL, "aspecto": "16:9", "curva": None, "triplo": True, "bezel_mm": 10.0}),
)


def _pos(valor, nome):
    try:
        v = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{nome}: valor invalido")
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f"{nome}: precisa ser maior que zero")
    return v


def aspecto_de(chave, custom=None):
    """('16:9' | '21:9' | '32:9' | 'custom') -> (a, b). 'custom' recebe (a, b)."""
    if isinstance(chave, str) and chave in ASPECTOS:
        return ASPECTOS[chave]
    if isinstance(chave, (tuple, list)) and custom is None:       # proporcao ja entregue como par (a, b)
        custom = chave
    if not isinstance(custom, (tuple, list)) or len(custom) != 2:
        raise ValueError("proporcao personalizada sem valores")
    return _pos(custom[0], "proporcao (largura)"), _pos(custom[1], "proporcao (altura)")


def _raio(curva, nome="curvatura"):
    """None = tela plana; senao o raio em mm precisa ser finito e > 0 (zero, negativo, NaN e infinito sao rejeitados)."""
    if curva is None:
        return None
    return _pos(curva, nome)


def dimensoes_tela(diag_cm, aspecto):
    """(largura, altura) em cm a partir da diagonal e da proporcao."""
    a, b = aspecto
    d = _pos(diag_cm, "diagonal")
    n = math.hypot(a, b)
    return d * a / n, d * b / n


def _tela(dist, largura, altura, raio_mm):
    """Para UMA tela a distancia 'dist' (olho -> centro): FOV h/v em radianos, meia-corda, distancia axial das bordas, flecha."""
    if raio_mm is not None:
        r = raio_mm / 10.0
        meio = largura / (2.0 * r)
        if meio >= math.pi / 2:
            raise ValueError("curvatura forte demais para esta largura de tela")
        corda_2 = r * math.sin(meio)
        flecha = r * (1.0 - math.cos(meio))
    else:
        corda_2, flecha = largura / 2.0, 0.0
    axial = dist - flecha
    if axial <= 0:
        raise ValueError("a distancia ate a tela e menor que a curvatura da tela")
    hfov = 2.0 * math.atan(corda_2 / axial)
    vfov = 2.0 * math.atan((altura / 2.0) / dist)
    return {"hfov": hfov, "vfov": vfov, "meia_corda": corda_2, "axial": axial, "flecha": flecha, "borda": math.hypot(corda_2, axial)}


def calcular(e):
    """Calcula e garante que nenhum resultado numerico e nao finito."""
    r = _calcular(e)
    for k, v in r.items():
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError("resultado nao finito: confira os valores informados")
    return r


def _calcular(e):
    """e: dict com dist (cm), diag (cm), aspecto ('16:9'|'21:9'|'32:9' ou (a, b)), curva (None ou raio em mm), triplo (bool), bezel_mm (pode ser < 0),
    e, so no triplo com monitores laterais diferentes: lateral = {"diag": cm, "aspecto": ..., "curva": None|mm}. Devolve um dict com os resultados."""
    dist = _pos(e.get("dist"), "distancia")
    asp = aspecto_de(e.get("aspecto"))
    w, h = dimensoes_tela(e.get("diag"), asp)
    curva = _raio(e.get("curva"))
    c = _tela(dist, w, h, curva)
    saida = {"largura_tela": w, "altura_tela": h, "vfov": math.degrees(c["vfov"]), "hfov": math.degrees(c["hfov"]), "triplo": bool(e.get("triplo")),
             "curva": curva, "avisos": []}
    esp, marg = ESPESSURA_PAINEL_CM, MARGEM_QUADRO_CM
    if not e.get("triplo"):
        saida.update({"largura_x": w + marg, "profundidade_y": esp + c["flecha"], "lateral_angulo": None, "hfov_total": saida["hfov"]})
        if not (saida["largura_x"] > 0 and saida["profundidade_y"] > 0):
            raise ValueError("geometria impossivel: largura ou profundidade nao positiva")
        return saida
    lat = e.get("lateral")
    if lat:
        asp_l = aspecto_de(lat.get("aspecto"))
        wl, hl = dimensoes_tela(lat.get("diag"), asp_l)
        curva_l = _raio(lat.get("curva"), "curvatura da lateral")
    else:
        wl, hl, curva_l = w, h, curva
    s = _tela(dist, wl, hl, curva_l)
    try:
        bezel = float(e.get("bezel_mm", 0.0)) / 10.0
    except (TypeError, ValueError):
        raise ValueError("moldura: valor invalido")
    if not math.isfinite(bezel):
        raise ValueError("moldura: valor invalido")
    beta = math.atan2(bezel, c["borda"])                      # angulo da emenda visto do olho (negativo = sobreposicao)
    if beta < -0.5 * s["hfov"]:
        raise ValueError("sobreposicao maior que metade da tela lateral")
    phi = c["hfov"] / 2.0 + beta + s["hfov"] / 2.0            # direcao do centro da lateral (= angulo entre lateral e central)
    total = c["hfov"] + 2.0 * (beta + s["hfov"])
    if not math.isfinite(total) or total >= 2.0 * math.pi - 1e-9:
        raise ValueError(f"geometria impossivel: o FOV total do triplo seria {math.degrees(total):.0f} graus (precisa ser menor que 360); "
                         "afaste as telas, use telas menores ou reduza a moldura")
    # planta (x lateral, y para frente; olho na origem). Lateral: centro em C = D*(sen phi, cos phi), tangente t, normal n (para o olho).
    t = (math.cos(phi), -math.sin(phi))
    n = (-math.sin(phi), -math.cos(phi))
    cx, cy = dist * math.sin(phi), dist * math.cos(phi)
    sl = s["flecha"]
    ext = (cx + s["meia_corda"] * t[0] + sl * n[0], cy + s["meia_corda"] * t[1] + sl * n[1])      # borda externa (mais perto do olho se curva)
    inte = (cx - s["meia_corda"] * t[0] + sl * n[0], cy - s["meia_corda"] * t[1] + sl * n[1])     # borda interna
    # coerencia: o angulo da borda externa visto do olho TEM de ser metade do FOV total
    if abs(math.atan2(ext[0], ext[1]) - total / 2.0) > 1e-6:
        raise ValueError("geometria inconsistente do triplo")
    # pontos que definem o espaco ocupado: bordas e centros (frente) + fundos (esp. do painel para tras, ao longo da normal)
    frentes = [(c["meia_corda"], dist - c["flecha"]), (-c["meia_corda"], dist - c["flecha"]), ext, inte, (cx, cy),
               (-ext[0], ext[1]), (-inte[0], inte[1]), (-cx, cy)]
    fundos = [(0.0, dist + esp), (cx - esp * n[0], cy - esp * n[1]), (ext[0] - esp * n[0], ext[1] - esp * n[1]), (inte[0] - esp * n[0], inte[1] - esp * n[1])]
    fundos += [(-x, y) for x, y in fundos[1:]]
    xs = [abs(p_[0]) for p_ in frentes + fundos]
    ys = [p_[1] for p_ in frentes + fundos]
    largura_x = 2.0 * max(xs) + marg
    profundidade = max(ys) - min(ys)
    if not (largura_x > 0 and profundidade > 0):
        raise ValueError("geometria impossivel: largura ou profundidade nao positiva")
    saida.update({"lateral_angulo": math.degrees(phi), "hfov_total": math.degrees(total), "vfov_lateral": math.degrees(s["vfov"]),
                  "hfov_lateral": math.degrees(s["hfov"]), "largura_tela_lateral": wl, "altura_tela_lateral": hl,
                  "largura_x": largura_x, "profundidade_y": profundidade,
                  "fita_externa": 2.0 * ext[0], "fita_interna": 2.0 * inte[0], "bezel_angulo": math.degrees(beta)})
    if math.degrees(total) > 270.0:
        saida["avisos"].append("FOV total acima de 270°: confira as medidas, é uma montagem que envolve muito o piloto.")
    if phi > math.pi / 2.0:
        saida["avisos"].append("As laterais ficam atrás da linha dos olhos: confira a distância e o tamanho das telas.")
    if lat and abs(hl - h) > 0.5:
        saida["avisos"].append("As laterais têm altura diferente da central: o FOV vertical das laterais será diferente.")
    if bezel < 0:
        saida["avisos"].append("Moldura negativa: as telas se sobrepõem (kit sem moldura).")
    return saida


def para_jogo(res, jogo_tipo):
    """Numero a digitar no jogo: 'horizontal' ou 'vertical' (no triplo, devolve (central, conjunto))."""
    if jogo_tipo == "vertical":
        return res["vfov"], None
    return res["hfov"], (res["hfov_total"] if res["triplo"] else None)


def faixa(valor, pct=10.0):
    """Intervalo de ajuste fino sugerido em torno do valor calculado."""
    return valor * (1.0 - pct / 100.0), valor * (1.0 + pct / 100.0)
