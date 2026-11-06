# -*- coding: utf-8 -*-
"""
Leitor de arquivos .ibt do iRacing (telemetria gravada em Documents/iRacing/telemetry) - logica pura, so biblioteca padrao.

Formato (documentado no SDK do iRacing): cabecalho de 112 bytes, sub-cabecalho de disco (data, tempos, voltas, registros),
tabela de variaveis (144 bytes cada) e registros de tamanho fixo (bufLen) a partir de varBuf[0].bufOffset. A sessao (YAML)
traz pista, layout, comprimento e carro.

  info_ibt(caminho)        -> {"pista", "layout", "comprimento", "carro", "taxa", "registros", "voltas", ...}
  voltas_ibt(caminho)      -> lista de voltas: {"n", "tempo", "valida", "motivo", "cobertura", "pct", "vel", "freio", "acel", "marcha", "t"}
  volta_para_csv(volta)    -> texto CSV (LapDistPct, Speed, Brake, Throttle, Gear, LapCurrentLapTime) que o importador entende
  melhor_volta(voltas)     -> a mais rapida entre as validas (ou None)

Uma volta e VALIDA quando: completa (cobre >= 98% da pista), sem passar pelos boxes, sempre na pista e com tempo plausivel.
"""
import re
import struct
from pathlib import Path

import ov_coach as co
import ov_referencias as rf

_TIPOS = {0: ("c", 1), 1: ("?", 1), 2: ("i", 4), 3: ("I", 4), 4: ("f", 4), 5: ("d", 8)}
_PEDIDAS = ("Speed", "Brake", "Throttle", "Gear", "LapDistPct", "LapCurrentLapTime", "Lap", "OnPitRoad", "PlayerTrackSurface",
            "IsOnTrack", "LapLastLapTime", "SessionNum")
_DE_VALIDACAO = ("OnPitRoad", "PlayerTrackSurface", "IsOnTrack")      # sem eles nao da para provar que a volta e limpa (validacao parcial)
SALTO_MAX = 0.20                  # variacao de LapDistPct entre dois registros acima disto = reset/teletransporte
VEL_PARTIDA_MIN_KMH = 10.0        # volta que comeca (quase) parada = largada ou saida dos boxes


class ErroIbt(Exception):
    """Mensagem curta em portugues."""


def _cabecalho(f):
    f.seek(0)
    h = f.read(144)
    if len(h) < 144:
        raise ErroIbt("arquivo curto demais para ser um .ibt")
    ver, status, taxa, siu, sil, sio, nv, vho, nb, buf_len = struct.unpack_from("<10i", h, 0)
    buf_off = struct.unpack_from("<i", h, 52)[0]
    voltas, registros = struct.unpack_from("<ii", h, 136)
    if not (0 < taxa <= 360 and 0 < nv < 5000 and 0 < buf_len < 1_000_000 and 0 < registros):
        raise ErroIbt("cabecalho de telemetria invalido (nao parece um .ibt do iRacing)")
    return {"taxa": taxa, "sil": sil, "sio": sio, "nv": nv, "vho": vho, "buf_len": buf_len, "buf_off": buf_off,
            "registros": registros, "voltas_arquivo": voltas}


def _variaveis(f, c):
    f.seek(c["vho"])
    bruto = f.read(144 * c["nv"])
    out = {}
    for i in range(c["nv"]):
        t, off, cnt = struct.unpack_from("<iii", bruto, i * 144)
        nome = bruto[i * 144 + 16:i * 144 + 48].split(b"\0")[0].decode("latin-1")
        out[nome] = (t, off, cnt)
    return out


def _sessao(f, c):
    f.seek(c["sio"])
    return f.read(c["sil"]).decode("latin-1", errors="replace")


def _campo(yaml, chave):
    m = re.search(r"^\s*" + re.escape(chave) + r":\s*(.*)$", yaml, re.M)
    return m.group(1).strip() if m else ""


def _carro_do_piloto(yaml):
    """(CarScreenName, CarPath) do SEU carro: o YAML lista todos os pilotos (DriverInfo > Drivers); vale o de CarIdx == DriverCarIdx."""
    m = re.search(r"^\s*DriverCarIdx:\s*(\d+)", yaml, re.M)
    ini = yaml.find("\n Drivers:")
    if m and ini >= 0:
        lista = yaml[ini:]
        alvo = re.search(r"^\s*-\s*CarIdx:\s*" + m.group(1) + r"\s*$", lista, re.M)
        if alvo:
            resto = lista[alvo.end():]
            prox = re.search(r"^\s*-\s*CarIdx:", resto, re.M)
            bloco = resto[:prox.start()] if prox else resto
            nome, caminho = _campo(bloco, "CarScreenName"), _campo(bloco, "CarPath")
            if nome:
                return nome, caminho
    return _campo(yaml, "CarScreenName"), _campo(yaml, "CarPath")


def info_ibt(caminho):
    with open(caminho, "rb") as f:
        c = _cabecalho(f)
        y = _sessao(f, c)
    comp = re.search(r"([\d.]+)\s*km", _campo(y, "TrackLength"))
    carro, carro_id = _carro_do_piloto(y)
    return {"pista": _campo(y, "TrackDisplayName"), "layout": _campo(y, "TrackConfigName"),
            "comprimento": float(comp.group(1)) * 1000.0 if comp else None, "carro": carro,
            "carro_id": carro_id, "taxa": c["taxa"], "registros": c["registros"]}


def _ler_registros(caminho):
    with open(caminho, "rb") as f:
        c = _cabecalho(f)
        v = _variaveis(f, c)
        faltam = [n for n in ("Speed", "Brake", "Gear", "LapDistPct", "LapCurrentLapTime", "Lap") if n not in v]
        if faltam:
            raise ErroIbt("faltam canais no arquivo: " + ", ".join(faltam))
        campos = [(n, v[n]) for n in _PEDIDAS if n in v and v[n][0] in _TIPOS and v[n][2] == 1]
        campos.sort(key=lambda x: x[1][1])
        fmt = "<"
        pos = 0
        ordem = []
        for nome, (t, off, _) in campos:
            if off > pos:
                fmt += f"{off - pos}x"
            cod, tam = _TIPOS[t]
            fmt += cod
            pos = off + tam
            ordem.append(nome)
        ler = struct.Struct(fmt)
        if ler.size > c["buf_len"]:
            raise ErroIbt("registro maior que o esperado")
        f.seek(c["buf_off"])
        regs = []
        for _ in range(c["registros"]):
            bloco = f.read(c["buf_len"])
            if len(bloco) < c["buf_len"]:
                break
            regs.append(dict(zip(ordem, ler.unpack_from(bloco, 0))))
        c = dict(c, canais=[n for n in ordem])
        return c, regs


def _separar(regs):
    """Divide os registros em voltas: muda a variavel Lap OU a sessao (SessionNum), quando existir."""
    voltas, atual = [], []
    for r in regs:
        if atual and (r["Lap"] != atual[-1]["Lap"] or r.get("SessionNum") != atual[-1].get("SessionNum")):
            voltas.append(atual)
            atual = []
        atual.append(r)
    if atual:
        voltas.append(atual)
    return voltas


def _problema_de_posicao(pct):
    """None se a posicao for coerente; senao o motivo. Ignora a virada de 1.0 -> 0.0 nos primeiros/ultimos registros (o 'Lap'
    muda um pouco antes/depois do LapDistPct virar). Uma virada no MEIO da volta = linha de largada deslocada em relacao ao
    zero de LapDistPct (a referencia por distancia nao e valida para esse tipo de volta)."""
    n = len(pct)
    borda = 5
    for i in range(1, n):
        d = pct[i] - pct[i - 1]
        if d < -0.5 and (i <= borda or i >= n - borda):
            continue
        if d < -0.5:
            return "linha de largada deslocada (LapDistPct vira no meio da volta)"
        if abs(d) > SALTO_MAX:
            return "salto de posicao (reset ou teletransporte)"
    return None


def voltas_ibt(caminho, cobertura_min=0.98):
    """Separa as voltas do arquivo (pela variavel Lap e pela sessao) e marca quais sao validas. Cada volta traz:
    'validacao' ('completa' = todos os canais de prova presentes; 'parcial' = faltam canais, e a volta NAO e aceita como valida
    porque nao da para provar que e limpa) e 'canais_faltando'. Pode demorar alguns segundos em arquivos grandes."""
    info = info_ibt(caminho)
    c, regs = _ler_registros(caminho)
    canais = set(c.get("canais", []))
    faltando = [n for n in _DE_VALIDACAO if n not in canais]
    voltas = _separar(regs)
    out = []
    for i, rs in enumerate(voltas):
        pct = [r["LapDistPct"] for r in rs]
        cobertura = (max(pct) - min(pct)) if pct else 0.0
        # tempo: o ultimo LapCurrentLapTime da volta (antes de zerar) ou o LapLastLapTime registrado na volta seguinte
        mesma_sessao = i + 1 < len(voltas) and voltas[i + 1][0].get("SessionNum") == rs[0].get("SessionNum")
        seguinte = voltas[i + 1][0].get("LapLastLapTime") if mesma_sessao else None
        clt = max(r["LapCurrentLapTime"] for r in rs)
        dur0 = (len(rs) - 1) / float(info["taxa"])
        # o LapLastLapTime pode divergir do tempo medido (ex.: penalidade); vale o que bate com a duracao real da volta
        if seguinte and seguinte > 0 and abs(seguinte - dur0) < 0.02 * dur0:
            tempo = seguinte
        else:
            tempo = clt if abs(clt - dur0) < 0.02 * max(dur0, 1.0) else dur0
        motivo = None
        problema_pos = _problema_de_posicao(pct)
        if len(rs) < 10:
            motivo = "volta incompleta"
        elif problema_pos and cobertura >= cobertura_min and "deslocada" in problema_pos:
            motivo = problema_pos
        elif cobertura < cobertura_min:
            motivo = "volta incompleta"
        elif problema_pos:
            motivo = problema_pos
        elif faltando:
            motivo = "validacao parcial: faltam canais " + ", ".join(faltando)
        elif any(r.get("OnPitRoad") for r in rs):
            motivo = "passou pelos boxes"
        elif any(r.get("PlayerTrackSurface", 3) != 3 for r in rs) or not all(r.get("IsOnTrack", True) for r in rs):
            motivo = "saiu da pista"
        elif rs[0]["Speed"] * 3.6 < VEL_PARTIDA_MIN_KMH:
            motivo = "volta de largada ou de saida dos boxes"
        elif not (20.0 <= tempo <= 1200.0):
            motivo = "tempo implausivel"
        # O LapCurrentLapTime so zera um pouco depois da virada da volta: o tempo decorrido vem da contagem de registros
        # (taxa fixa), ajustado ao tempo oficial da volta quando proximo.
        taxa = info["taxa"]
        dur = (len(rs) - 1) / float(taxa)
        k = (tempo / dur) if (dur > 0 and abs(tempo - dur) < 0.02 * tempo) else 1.0
        tdec = [j / float(taxa) * k for j in range(len(rs))]
        out.append({"n": rs[0]["Lap"], "sessao": rs[0].get("SessionNum"), "tempo": tempo, "valida": motivo is None,
                    "motivo": motivo, "cobertura": cobertura,
                    "validacao": "parcial" if faltando else "completa", "canais_faltando": list(faltando),
                    "pct": pct, "vel": [r["Speed"] * 3.6 for r in rs], "freio": [r["Brake"] for r in rs],
                    "acel": [r.get("Throttle", 0.0) for r in rs], "marcha": [int(r["Gear"]) for r in rs],
                    "t": tdec})
    return info, out


def melhor_volta(voltas):
    validas = [v for v in voltas if v["valida"]]
    return min(validas, key=lambda v: v["tempo"]) if validas else None


def volta_para_csv(v):
    """Uma volta do .ibt em CSV (o mesmo formato que o importador de CSV entende)."""
    linhas = ["LapDistPct,Speed (km/h),Brake,Throttle,Gear,LapCurrentLapTime"]
    for p, s, b, a, g, t in zip(v["pct"], v["vel"], v["freio"], v["acel"], v["marcha"], v["t"]):
        linhas.append(f"{p:.5f},{s:.3f},{b:.4f},{a:.4f},{g},{t:.4f}")
    return "\n".join(linhas)


def referencia_de_volta(info, volta, origem="propria", fonte=""):
    """Converte uma volta do .ibt em referencia do Coach (levanta ov_referencias.ErroImportacao se nao servir)."""
    if not info.get("comprimento"):
        raise rf.ErroImportacao("o arquivo nao informa o comprimento da pista")
    ref, _ = rf.importar_csv(volta_para_csv(volta), info["pista"], info["carro"], info["comprimento"], fonte=fonte,
                             tempo_volta=volta["tempo"])
    ref["origem"] = origem
    return ref


def voltas_validas_da_pasta(pasta, pista, carro, comprimento, max_arquivos=6, max_voltas=30, tolerancia=0.015):
    """1.7.0: as MELHORES voltas validas desta pista e deste carro nas telemetrias mais novas (alimenta o 'melhor por curva').
    Devolve [(info, volta)] da mais rapida para a mais lenta. Nunca levanta."""
    pasta = Path(pasta)
    if not pasta.is_dir() or not comprimento:
        return []
    try:
        arquivos = sorted((p for p in pasta.glob("*.ibt") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return []
    achadas, usados = [], 0
    alvo_pista = co.normalizar_nome(pista)
    for a in arquivos:
        try:
            info = info_ibt(a)
        except (ErroIbt, OSError, struct.error):
            continue
        if co.normalizar_nome(info["pista"]) != alvo_pista or not co.mesmo_carro(info["carro"], carro):
            continue
        if not info["comprimento"] or abs(info["comprimento"] - comprimento) > tolerancia * comprimento:
            continue
        usados += 1
        if usados > max_arquivos:
            break
        try:
            info, voltas = voltas_ibt(a)
        except (ErroIbt, OSError, struct.error, KeyError, ValueError):
            continue
        achadas += [(info, v) for v in voltas if v["valida"]]
    achadas.sort(key=lambda x: x[1]["tempo"])
    return achadas[:max_voltas]


def melhor_volta_da_pasta(pasta, pista, carro, comprimento, max_arquivos=15, tolerancia=0.015):
    """Procura na pasta de telemetria a MELHOR volta valida desta pista e deste carro (mesmo comprimento, dentro da tolerancia).
    Devolve (caminho, volta, info) ou None. Le so os arquivos mais novos (max_arquivos que casam). Nunca levanta."""
    pasta = Path(pasta)
    if not pasta.is_dir() or not comprimento:
        return None
    try:
        arquivos = sorted((p for p in pasta.glob("*.ibt") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    melhor, usados = None, 0
    alvo_pista = co.normalizar_nome(pista)
    for a in arquivos:
        try:
            info = info_ibt(a)
        except (ErroIbt, OSError, struct.error):
            continue
        if co.normalizar_nome(info["pista"]) != alvo_pista or not co.mesmo_carro(info["carro"], carro):
            continue
        if not info["comprimento"] or abs(info["comprimento"] - comprimento) > tolerancia * comprimento:
            continue
        usados += 1
        if usados > max_arquivos:
            break
        try:
            info, voltas = voltas_ibt(a)
        except (ErroIbt, OSError, struct.error, KeyError, ValueError):
            continue
        v = melhor_volta(voltas)
        if v and (melhor is None or v["tempo"] < melhor[1]["tempo"]):
            melhor = (a, v, info)
    return melhor
