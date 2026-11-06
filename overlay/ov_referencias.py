# -*- coding: utf-8 -*-
"""
Importador de voltas de referencia (v1.7) - logica pura, sem Qt e sem rede.

Le o CSV de UMA volta (por exemplo, a telemetria exportada de outro piloto no Garage 61 ou de uma sessao sua) e devolve
uma referencia para o Coach. O formato do Garage 61 AINDA NAO foi confirmado com um arquivo real: por isso o leitor e
TOLERANTE (reconhece varios nomes de coluna, unidades e separadores) e diz exatamente o que faltou quando recusa.

Colunas (qualquer um dos nomes, sem diferenciar maiusculas/acentos):
  posicao na volta : LapDistPct / lap_dist_pct / pct (0-1 ou 0-100)   OU   LapDist / distance / dist (metros)
  velocidade       : Speed / velocidade / speed_kmh (m/s, km/h ou mph: a unidade vem do nome; sem unidade, deduz)
  freio            : Brake / freio (0-1 ou 0-100)
  acelerador       : Throttle / acelerador (0-1 ou 0-100)
  marcha           : Gear / marcha
  tempo (opcional) : LapCurrentLapTime / time / tempo / elapsed (s) - sem ele, o tempo e integrado da velocidade
Obrigatorias: posicao, velocidade, freio e marcha. O acelerador e opcional (a correcao do "blip" da reducao fica desligada sem ele).
"""
import csv
import io
import math
import re
import re
import unicodedata
from pathlib import Path

import ov_coach as co

BINS = co.BINS
COB_MIN = 0.90                 # cobertura minima da volta
MAX_EXTRAPOLACAO = 0.03        # fracao maxima da pista sem dados nas pontas (acima disto, recusa)
MAX_BURACO = 0.05              # maior intervalo sem amostras tolerado (fracao da pista)
MAX_LINHAS_RUINS = 0.30        # fracao maxima de linhas incompletas (acima disto, arquivo truncado/inconsistente)
VEL_MAX_KMH, VEL_MIN_KMH = 450.0, 30.0


class ErroImportacao(Exception):
    """Mensagem curta, em portugues, pronta para mostrar ao piloto."""


def _norm(txt):
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", txt.lower())


_ALIASES = {
    "pct": ("lapdistpct", "lapdistancepct", "distpct", "pct", "trackpct", "trackposition", "normalizedposition", "posicaonavolta",
            "percentual", "lapprogress", "progress"),
    "dist": ("lapdist", "lapdistance", "distance", "dist", "distancia", "distanciametros", "distm", "distancem"),
    "vel": ("speed", "speedkmh", "speedms", "speedmph", "velocidade", "velocidadekmh", "vel", "velkmh", "velocity", "groundspeed"),
    "freio": ("brake", "freio", "brakepct", "brakepedal", "brk", "brakeraw"),
    "acel": ("throttle", "acelerador", "throttlepct", "throttlepedal", "gas", "thr", "throttleraw"),
    "marcha": ("gear", "marcha", "currentgear", "gearno"),
    "tempo": ("lapcurrentlaptime", "laptime", "time", "tempo", "elapsed", "elapsedtime", "currentlaptime", "t", "sessiontime"),
}
_PRIORIDADE_TEMPO = ("lapcurrentlaptime", "currentlaptime", "laptime", "elapsed", "elapsedtime", "tempo", "time", "t", "sessiontime")


def detectar_colunas(cabecalho):
    """cabecalho: lista de nomes. Devolve {campo: indice}. Campos nao achados ficam de fora."""
    nomes = [_norm(c) for c in cabecalho]
    achados = {}
    for campo, aliases in _ALIASES.items():
        ordem = _PRIORIDADE_TEMPO if campo == "tempo" else aliases
        for alias in ordem:
            if alias in nomes:
                achados[campo] = nomes.index(alias)
                break
    return achados


def _unidade_vel(nome, valores):
    n = _norm(nome)
    if "mph" in n:
        return "mph"
    if "kmh" in n or "kph" in n:
        return "kmh"
    if n.endswith("ms"):
        return "ms"
    maximo = max(valores) if valores else 0.0                 # sem unidade no nome: deduz pelo tamanho
    return "ms" if maximo < 110.0 else "kmh"                  # abaixo de 110 m/s (396 km/h) so pode ser m/s num carro de pista


def _num(txt):
    t = str(txt).strip()
    if "," in t and "." not in t:
        t = t.replace(",", ".")                              # virgula decimal
    try:
        v = float(t)
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def _separador(amostra):
    try:
        return csv.Sniffer().sniff(amostra, delimiters=",;\t|").delimiter
    except csv.Error:
        return ";" if amostra.count(";") > amostra.count(",") else ","


def ler_tabela(texto):
    """Acha a linha de cabecalho (ignora linhas de metadados no inicio) e devolve (cabecalho, linhas)."""
    texto = texto.lstrip("﻿")
    linhas = [l for l in texto.splitlines() if l.strip()]
    if len(linhas) < 20:
        raise ErroImportacao("arquivo muito curto para ser uma volta (menos de 20 linhas)")
    sep = _separador("\n".join(linhas[:30]))
    leitor = list(csv.reader(io.StringIO("\n".join(linhas)), delimiter=sep))
    for i, linha in enumerate(leitor[:40]):
        cols = detectar_colunas(linha)
        if "vel" in cols and ("pct" in cols or "dist" in cols):
            return linha, leitor[i + 1:]
    raise ErroImportacao("nao achei as colunas de velocidade e de posicao na volta (LapDistPct ou LapDist)")


def _interpolar(xs, ys, x):
    """xs crescente. Interpolacao linear com recorte nas pontas."""
    import bisect
    i = bisect.bisect_left(xs, x)
    if i <= 0:
        return ys[0]
    if i >= len(xs):
        return ys[-1]
    x0, x1 = xs[i - 1], xs[i]
    return ys[i - 1] if x1 == x0 else ys[i - 1] + (ys[i] - ys[i - 1]) * (x - x0) / (x1 - x0)


def importar_csv(texto, pista, carro, comprimento=None, fonte="", tempo_volta=None, corrigir_blip=True):
    """Converte o CSV de uma volta em referencia. Devolve (referencia, avisos). Levanta ErroImportacao se nao der."""
    cab, linhas = ler_tabela(texto)
    cols = detectar_colunas(cab)
    falta = [nome for nome, k in (("freio", "freio"), ("marcha", "marcha")) if k not in cols]
    if falta:
        raise ErroImportacao("faltam colunas obrigatorias: " + ", ".join(falta))
    avisos = []
    bruto = {k: [] for k in cols}
    descartadas = 0
    for l in linhas:
        if len(l) <= max(cols.values()):
            descartadas += 1                       # linha truncada
            continue
        reg = {k: _num(l[i]) for k, i in cols.items()}
        if reg.get("vel") is None or (reg.get("pct") is None and reg.get("dist") is None):
            descartadas += 1
            continue
        for k, v in reg.items():
            bruto[k].append(v)
    n = len(bruto["vel"])
    if linhas and descartadas / float(len(linhas)) > MAX_LINHAS_RUINS:
        raise ErroImportacao(f"arquivo truncado ou inconsistente: {descartadas} de {len(linhas)} linhas sem os campos obrigatorios")
    if descartadas > 0.02 * max(1, len(linhas)):
        avisos.append(f"{descartadas} de {len(linhas)} linhas ignoradas (incompletas)")
    if n < 50:
        raise ErroImportacao(f"poucas amostras validas ({n})")
    # --- posicao ao longo da volta (0..1) ---
    if "pct" in cols and all(v is not None for v in bruto["pct"]):
        pct = list(bruto["pct"])
        if max(pct) > 1.5:
            pct = [v / 100.0 for v in pct]
    else:
        dist = [v for v in bruto.get("dist", []) if v is not None]
        if len(dist) != n:
            raise ErroImportacao("coluna de posicao com valores faltando")
        total = comprimento or max(dist)
        if not total or total < 300.0:
            raise ErroImportacao("sem LapDistPct e sem o comprimento da pista: nao da para alinhar a volta")
        pct = [d / total for d in dist]
        if comprimento is None:
            avisos.append("comprimento deduzido da maior distancia do arquivo")
    # recorta uma unica volta: do primeiro ponto crescente ate o maximo (descarta o inicio da volta seguinte)
    idx = [0]
    for i in range(1, n):
        if pct[i] > pct[idx[-1]]:
            idx.append(i)
    if len(idx) < 50 or pct[idx[-1]] - pct[idx[0]] < COB_MIN:
        raise ErroImportacao("o arquivo nao cobre uma volta inteira")
    if pct[idx[-1]] - pct[idx[0]] < 0.985:
        avisos.append(f"a volta cobre {100.0 * (pct[idx[-1]] - pct[idx[0]]):.0f}% da pista")
    pcts = [pct[i] for i in idx]
    # --- cobertura das pontas, buracos e extrapolacao (1.7.0): nada e inventado sem avisar ---
    ini, fim = pcts[0], pcts[-1]
    if ini < -0.01 or fim > 1.01:
        raise ErroImportacao("posicao fora de 0-100% da pista (arquivo com outra escala ou mais de uma volta)")
    extra = (max(0.0, ini) + max(0.0, 1.0 - fim))            # fracao da pista SEM dados (sera preenchida pelas pontas)
    if extra > MAX_EXTRAPOLACAO:
        raise ErroImportacao(f"a volta nao cobre o inicio/fim da pista: faltam {100.0 * extra:.1f}% (inicio em {100.0 * ini:.1f}%, "
                             f"fim em {100.0 * fim:.1f}%); exporte a volta inteira")
    if extra > 0.005:
        avisos.append(f"{100.0 * extra:.1f}% da pista sem dados nas pontas (inicio {100.0 * ini:.1f}%, fim {100.0 * fim:.1f}%): "
                      "os valores das pontas foram repetidos")
    buraco = max(pcts[i + 1] - pcts[i] for i in range(len(pcts) - 1))
    if buraco > MAX_BURACO:
        raise ErroImportacao(f"o arquivo tem um buraco de {100.0 * buraco:.1f}% da pista sem amostras (dados perdidos)")
    if buraco > 0.02:
        avisos.append(f"buraco de {100.0 * buraco:.1f}% da pista sem amostras (interpolado)")
    if "dist" in cols and comprimento and all(v is not None for v in bruto["dist"]) and len(bruto["dist"]) == n:
        alcance = max(bruto["dist"]) - min(bruto["dist"])
        if alcance > 0 and abs(alcance - comprimento) > 0.05 * comprimento:
            raise ErroImportacao(f"a distancia do arquivo ({alcance:.0f} m) nao bate com o comprimento da pista "
                                 f"({comprimento:.0f} m): pista, layout ou unidade errados")
        if alcance > 0 and abs(alcance - comprimento) > 0.015 * comprimento:
            avisos.append(f"a distancia do arquivo ({alcance:.0f} m) difere do comprimento da pista ({comprimento:.0f} m)")

    def serie(chave, escala=1.0):
        return [bruto[chave][i] * escala for i in idx]
    un = _unidade_vel(cab[cols["vel"]], bruto["vel"])
    k_vel = {"ms": 3.6, "kmh": 1.0, "mph": 1.609344}[un]
    vel = serie("vel", k_vel)
    if max(vel) > VEL_MAX_KMH or max(vel) < VEL_MIN_KMH or min(vel) < -1.0:
        raise ErroImportacao(f"velocidade implausivel (maxima {max(vel):.0f} km/h): unidade ou coluna errada?")
    freio = serie("freio")
    if max(freio) > 1.5:
        freio = [v / 100.0 for v in freio]
    if max(freio) > 1.05 or min(freio) < -0.05:
        raise ErroImportacao("freio fora de 0-1 (ou 0-100): coluna ou escala errada")
    acel = None
    if "acel" in cols:
        acel = serie("acel")
        if max(acel) > 1.5:
            acel = [v / 100.0 for v in acel]
        if max(acel) > 1.05 or min(acel) < -0.05:
            raise ErroImportacao("acelerador fora de 0-1 (ou 0-100): coluna ou escala errada")
    marcha = [int(round(v)) for v in serie("marcha")]
    # --- tempo ---
    tempo = None
    if "tempo" in cols and all(v is not None for v in bruto["tempo"]):
        t = serie("tempo")
        t = [v - t[0] for v in t]
        if all(t[i] <= t[i + 1] for i in range(len(t) - 1)) and t[-1] > 20.0:
            tempo = t
        else:
            avisos.append("coluna de tempo inutilizavel: tempo calculado pela velocidade")
    if tempo is None:
        comp_calc = comprimento or (max(bruto["dist"]) if "dist" in cols and bruto.get("dist") else None)
        if not comp_calc:
            raise ErroImportacao("sem coluna de tempo e sem o comprimento da pista")
        tempo = [0.0]
        for i in range(1, len(pcts)):
            d = (pcts[i] - pcts[i - 1]) * comp_calc
            v = max(1.0, (vel[i] + vel[i - 1]) / 2.0 / 3.6)
            tempo.append(tempo[-1] + d / v)
    tempo_total = tempo[-1] / max(1e-9, (pcts[-1] - pcts[0])) if pcts[-1] - pcts[0] < 0.999 else tempo[-1]
    if tempo_volta and tempo_volta > 20.0:
        if abs(tempo_total - float(tempo_volta)) > 0.02 * float(tempo_volta) and "tempo" in cols:
            avisos.append(f"o tempo do arquivo ({tempo_total:.1f} s) difere do tempo informado ({float(tempo_volta):.1f} s)")
        tempo_total = float(tempo_volta)
    if not (20.0 <= tempo_total <= 1200.0):
        raise ErroImportacao(f"tempo de volta fora do normal ({tempo_total:.1f} s)")
    # --- reamostra em 1000 trechos (centro de cada trecho) ---
    comp_ref = float(comprimento or (max(bruto["dist"]) if "dist" in cols and bruto.get("dist") else 0.0) or 0.0)
    if comp_ref < 300.0:
        raise ErroImportacao("informe o comprimento da pista (o arquivo nao traz)")
    centros = [(b + 0.5) / BINS for b in range(BINS)]
    v_b = [_interpolar(pcts, vel, c) for c in centros]
    f_b = [_interpolar(pcts, freio, c) for c in centros]
    a_b = [_interpolar(pcts, acel, c) for c in centros] if acel is not None else [0.0] * BINS
    t_b = [_interpolar(pcts, tempo, c) for c in centros]
    m_b = []
    for c in centros:
        j = min(len(pcts) - 1, max(0, _indice(pcts, c)))
        m_b.append(marcha[j])
    if acel is not None and corrigir_blip:
        a_b = co.corrigir_blips(a_b, m_b)
    elif acel is None:
        avisos.append("sem coluna de acelerador: a velocidade e o freio bastam para o coach")
    if max(f_b) < co.PICO_MIN:
        raise ErroImportacao("nenhuma frenagem encontrada: o freio veio zerado ou em outra escala")
    ref = co.nova_referencia(pista, carro, "importada", comp_ref, tempo_total, v_b, f_b, a_b, m_b, t_b, fonte)
    problemas = co.validar_referencia(ref)
    if problemas:
        raise ErroImportacao("referencia invalida: " + "; ".join(problemas))
    if not co.zonas_de_frenagem(ref):
        raise ErroImportacao("nenhuma zona de frenagem reconhecida nesta volta")
    return ref, avisos




def _indice(xs, x):
    import bisect
    i = bisect.bisect_left(xs, x)
    if i <= 0:
        return 0
    if i >= len(xs):
        return len(xs) - 1
    return i if abs(xs[i] - x) < abs(xs[i - 1] - x) else i - 1


def tempo_do_nome(nome):
    """O CSV do Garage 61 nao tem coluna de tempo; o tempo da volta vem no nome do arquivo
    ("Garage 61 - Piloto - Carro - Pista - 01.22.572 - ID.csv"). Devolve segundos ou None."""
    m = re.search(r"(?<!\d)(\d{1,2})[.:](\d{2})[.:](\d{3})(?!\d)", nome or "")
    if not m:
        return None
    t = int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3)) / 1000.0
    return t if 20 <= t <= 1200 else None


def importar_arquivo(caminho, pista, carro, comprimento=None, fonte="", tempo_volta=None):
    caminho = Path(caminho)
    try:
        bruto = caminho.read_bytes()
    except OSError as e:
        raise ErroImportacao(f"nao consegui ler o arquivo ({e.__class__.__name__})")
    for cod in ("utf-8-sig", "latin-1"):
        try:
            texto = bruto.decode(cod)
            break
        except UnicodeDecodeError:
            continue
    if tempo_volta is None:
        tempo_volta = tempo_do_nome(caminho.name)
    return importar_csv(texto, pista, carro, comprimento, fonte or caminho.name, tempo_volta)


def listar_csv(pasta):
    """CSVs da pasta de entrada, do mais novo ao mais antigo."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []
    return sorted((p for p in pasta.glob("*.csv") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
