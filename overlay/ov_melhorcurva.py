# -*- coding: utf-8 -*-
"""
Melhor por curva e resumo pos-sessao (1.7.0) - logica pura, sem Qt e sem depender do jogo (iRacing e LMU usam o mesmo nucleo).

Ideia
  O Coach compara a volta atual com UMA referencia. Aqui guardamos as suas voltas VALIDAS (por pista e carro) e, para cada
  curva, olhamos qual das suas passagens foi a mais rapida (tempo entre PAD_ANTES_M antes do evento e PAD_DEPOIS_M depois do apice):
    1. MELHOR POR CURVA (ao vivo): se uma passagem sua foi mais rapida que a da referencia ativa, o Coach mostra a DIFERENCA
       OBSERVADA (tempo do trecho e onde ocorreu o evento de freada/tirada). Nao afirma causa: so compara o que aconteceu.
       A referencia principal nunca muda.
    2. RESUMO DA SESSAO: onde, em media, voce perdeu mais tempo em relacao a sua melhor passagem de cada curva, quanto
       varia o seu ponto de freada e quanto daria a "volta ideal" (soma das melhores passagens, estimativa).

Convencoes: "~" = estimativa. Curvas = zonas de freada/tirada achadas em cada volta (ver ov_coach); zonas de voltas diferentes
formam a mesma curva se o apice estiver a ate RAIO_AGRUPAR_M (distancia CIRCULAR, a pista e um anel), forem do mesmo TIPO
(freada ou tirada de pe) e nunca duas da mesma volta. O tempo do trecho e a diferenca do relogio da volta entre dois pontos fixos
da pista (pode atravessar a linha de chegada). Nao e um limite fisico: e o melhor que VOCE ja fez naquele trecho, no mesmo carro.

Identidade da volta (1.7.0): cada volta guardada tem "id" (origem + sessao + numero + tempo + impressao digital do relogio);
duas voltas diferentes com o mesmo tempo sao mantidas; a mesma volta vinda de duas origens (ao vivo e .ibt) e reconhecida pelo
tempo e pelo perfil do relogio. Historicos antigos (sem id) continuam valendo.
"""
import hashlib
import json
import math
import os
import statistics
import threading
import zlib
from pathlib import Path

import ov_coach as co

PAD_ANTES_M = 50.0         # o trecho de cada curva comeca isto antes da freada/tirada
PAD_DEPOIS_M = 80.0        # e termina isto depois do apice (ou do fim da zona)
RAIO_AGRUPAR_M = 60.0      # apices ate esta distancia (circular), do mesmo tipo e de voltas diferentes, sao a mesma curva (calibrado com .ibt reais: o apice varia 13-33 m entre voltas; patamar a partir de 60 m)
MAX_VOLTAS = 40            # voltas guardadas por pista+carro
LIM_RITMO = 1.07           # voltas mais lentas que 107% da melhor nao contam
MIN_VOLTAS_DICA = 3        # a dica exige ao menos isto de passagens validas na curva
MIN_VOLTAS_SESSAO = 3      # o resumo exige ao menos isto de voltas da sessao
GANHO_MIN_S = 0.03         # dica so se a passagem for ao menos isto mais rapida que a referencia...
RUIDO_K = 1.0              # ...e ao menos RUIDO_K x o desvio-padrao dos tempos do trecho entre as voltas (3+ passagens)
DIF_FREADA_MIN_M = 6.0     # e se diferir ao menos isto no ponto do evento...
DIF_VEL_MIN = 3.0          # ...ou ao menos isto (km/h) no apice
TOL_COMPRIMENTO = 0.015    # historico so aceita voltas do mesmo comprimento (mesmo tracado), tolerancia de 1,5%
TOL_PERFIL_MS = 120        # mesma volta vinda de origens diferentes: diferenca MAXIMA do relogio entre os perfis (ms)...
TOL_PERFIL_MEDIA_MS = 45   # ...e diferenca MEDIA (ms): voltas distintas com o mesmo tempo oficial nao passam nos dois criterios
TOL_TEMPO_S = 0.002        # ...e tempos iguais a este valor


def _mediana(valores):
    return statistics.median(valores) if valores else 0.0


def _volta_circ(d, n):
    """Diferenca circular em trechos, em (-n/2, n/2]."""
    d = d % n
    return d - n if d > n / 2.0 else d


def _dist_circ(a, b, n):
    return abs(_volta_circ(a - b, n))


# --------------------------------------------------------------------------
# Uma volta guardada
def _impressao(t_ms):
    return zlib.crc32(",".join(str(x) for x in t_ms).encode("ascii")) & 0xFFFFFFFF


def id_da_volta(origem, sessao, numero, tempo, t_ms):
    base = f"{origem}|{sessao}|{'' if numero is None else numero}|{tempo:.3f}|{_impressao(t_ms):08x}"
    return hashlib.sha1(base.encode("ascii")).hexdigest()[:16]


def volta_compacta(ref, sessao, origem="ao_vivo", numero=None):
    """Resumo de uma volta valida (dict de ov_coach.nova_referencia): relogio em ms por trecho + zonas medidas na propria volta."""
    zonas = []
    for z in co.todas_as_zonas(ref):
        zonas.append({"tipo": z["tipo"], "ini": z["ini"], "fim": z["fim"], "apice": z["apice"],
                      "vel_apice": round(z["vel_apice"], 1), "vel_entrada": round(z["vel_entrada"], 1),
                      "marcha": z["marcha_apice"]})
    t_ms = [int(round(x * 1000)) for x in ref["t"]]
    tempo = round(float(ref["tempo"]), 3)
    return {"id": id_da_volta(origem, int(sessao), numero, tempo, t_ms), "origem": origem, "numero": numero,
            "tempo": tempo, "t_ms": t_ms, "zonas": zonas, "sessao": int(sessao), "comprimento": float(ref["comprimento"])}


def validar_volta(v):
    """Lista de problemas de uma volta guardada (vazia = ok): estrutura, relogio crescente e indices das zonas."""
    if not isinstance(v, dict):
        return ["volta nao e um dicionario"]
    t = v.get("t_ms")
    if not isinstance(t, list) or len(t) < 100:
        return ["relogio ausente ou curto demais"]
    n = len(t)
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in t):
        return ["relogio com valores invalidos"]
    if any(t[i] > t[i + 1] for i in range(n - 1)):
        return ["relogio nao e crescente"]
    if not co._finito(v.get("tempo")) or v["tempo"] <= 0:
        return ["tempo de volta invalido"]
    if not co._finito(v.get("comprimento")) or v["comprimento"] < 300.0:
        return ["comprimento invalido"]
    zonas = v.get("zonas")
    if not isinstance(zonas, list):
        return ["zonas ausentes"]
    for z in zonas:
        if not isinstance(z, dict) or z.get("tipo") not in ("freio", "tirada"):
            return ["zona invalida"]
        try:
            ini, fim, apice = int(z["ini"]), int(z["fim"]), int(z["apice"])
        except (KeyError, TypeError, ValueError):
            return ["zona sem indices"]
        if not (0 <= ini <= fim < n and 0 <= apice < n):
            return ["indice de zona fora da volta"]
        if not co._finito(z.get("vel_apice")):
            return ["velocidade de apice invalida"]
    return []


def _id(v):
    """id da volta; historicos antigos (sem id) recebem um id derivado do conteudo."""
    return v.get("id") or id_da_volta(v.get("origem") or "legado", v.get("sessao", 0), v.get("numero"), v["tempo"], v["t_ms"])


def mesma_volta(a, b):
    """True se for a MESMA volta: mesmo id, ou (origens diferentes/antigas) mesmo tempo e perfil do relogio praticamente igual.
    Duas voltas diferentes com o mesmo tempo, da mesma origem, sao mantidas."""
    if _id(a) == _id(b):
        return True
    if a.get("id") and b.get("id") and a.get("origem") == b.get("origem") and a.get("origem") not in (None, "legado"):
        return False
    if abs(a["tempo"] - b["tempo"]) >= TOL_TEMPO_S or len(a["t_ms"]) != len(b["t_ms"]):
        return False
    ta, tb = a["t_ms"], b["t_ms"]
    difs = [abs(ta[i] - tb[i]) for i in range(0, len(ta), 5)]
    # a mesma volta lida por dois caminhos difere so por quantizacao (poucos ms, no maximo ~1 trecho); duas voltas distintas
    # com o mesmo tempo oficial quase sempre se afastam em varios trechos. Exige maximo E media pequenos.
    return max(difs) <= TOL_PERFIL_MS and sum(difs) / len(difs) <= TOL_PERFIL_MEDIA_MS


# --------------------------------------------------------------------------
# Armazenamento
class HistoricoCurvas:
    """Voltas validas por pista+carro, em arquivos JSON numa pasta propria. Nunca levanta.
    A gravacao e atomica (arquivo temporario + os.replace); quem chama decide em qual thread gravar."""

    def __init__(self, pasta):
        self.pasta = Path(pasta)
        self.descartadas = 0              # voltas invalidas ignoradas na ultima leitura

    def _arquivo(self, pista, carro):
        return self.pasta / f"historico__{co.slug(pista)}__{co.slug(carro)}.json"

    def carregar(self, pista, carro):
        self.descartadas = 0
        try:
            arq = self._arquivo(pista, carro)
            if not arq.is_file():
                return []
            dados = json.loads(arq.read_text(encoding="utf-8"))
            voltas = dados.get("voltas", []) if isinstance(dados, dict) else []
            if not isinstance(voltas, list):
                return []
            boas = [v for v in voltas if not validar_volta(v)]
            # todas do mesmo tracado: vale o comprimento da primeira
            if boas:
                comp0, n0 = boas[0]["comprimento"], len(boas[0]["t_ms"])
                boas = [v for v in boas if len(v["t_ms"]) == n0 and abs(v["comprimento"] - comp0) <= TOL_COMPRIMENTO * comp0]
            self.descartadas = len(voltas) - len(boas)
            return boas
        except Exception:
            return []

    def salvar(self, pista, carro, voltas):
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
            destino = self._arquivo(pista, carro)
            tmp = destino.with_name(destino.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                tmp.write_text(json.dumps({"versao": 2, "pista": pista, "carro": carro, "voltas": voltas},
                                          separators=(",", ":")), encoding="utf-8")
                os.replace(tmp, destino)
            except BaseException:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                raise
            return True
        except Exception:
            return False

    def apagar(self, pista, carro):
        try:
            self._arquivo(pista, carro).unlink()
            return True
        except Exception:
            return False


def acrescentar(voltas, nova, sessao_atual=None):
    """Acrescenta a volta e mantem no maximo MAX_VOLTAS (descarta as mais lentas que nao sejam da sessao atual).
    Volta invalida, de outro tracado ou REPETIDA (mesma volta, ver mesma_volta) nao entra. Devolve a lista nova
    (ou a mesma, se nada mudou). Voltas diferentes com o mesmo tempo sao mantidas."""
    if validar_volta(nova):
        return voltas
    if "id" not in nova:
        nova = dict(nova, id=_id(nova))
    if voltas:
        ref = voltas[0]
        if len(ref["t_ms"]) != len(nova["t_ms"]) or abs(ref["comprimento"] - nova["comprimento"]) > TOL_COMPRIMENTO * ref["comprimento"]:
            return voltas
    if any(mesma_volta(v, nova) for v in voltas):
        return voltas
    voltas = list(voltas) + [nova]
    while len(voltas) > MAX_VOLTAS:
        candidatas = [v for v in voltas if v.get("sessao") != sessao_atual] or voltas
        voltas.remove(max(candidatas, key=lambda v: v["tempo"]))
    return voltas


# --------------------------------------------------------------------------
# Agrupamento por curva
def _validas(voltas):
    if not voltas:
        return []
    melhor = min(v["tempo"] for v in voltas)
    return [v for v in voltas if v["tempo"] <= melhor * LIM_RITMO]


def agrupar(voltas):
    """Curvas encontradas em ao menos uma volta, em ordem de pista:
    [{n, tipo, ini, fim, apice, a, b, membros{idx_volta: zona}}]. 'ini/fim/a/b' podem sair de [0, n) quando a curva
    atravessa a linha de chegada (o trecho e circular). Regras: distancia CIRCULAR, mesmo tipo, e uma zona por volta
    (duas zonas da mesma volta nunca viram a mesma curva, ex.: chicane). Resultado independente da ordem das voltas."""
    if not voltas:
        return []
    n = len(voltas[0]["t_ms"])
    comp = float(voltas[0].get("comprimento") or 0.0)
    if n < 10 or comp < 300.0:
        return []
    bm = n / comp
    raio = max(1.0, RAIO_AGRUPAR_M * bm)
    grupos = []                                            # {"tipo", "centro", "itens": [(idx, zona)], "idxs": set}
    # voltas mais rapidas primeiro (desempate pelo indice): os centros nascem das melhores voltas, de forma estavel
    ordem = sorted(range(len(voltas)), key=lambda i: (voltas[i]["tempo"], _id(voltas[i])))
    for i in ordem:
        candidatos = []
        for zi, z in enumerate(voltas[i]["zonas"]):
            for gi, g in enumerate(grupos):
                if g["tipo"] == z["tipo"] and i not in g["idxs"]:
                    d = _dist_circ(z["apice"], g["centro"], n)
                    if d <= raio:
                        candidatos.append((d, zi, gi))
        usados_z, usados_g = set(), set()
        for d, zi, gi in sorted(candidatos):                # uma zona por grupo e um grupo por zona (o mais proximo ganha)
            if zi in usados_z or gi in usados_g:
                continue
            usados_z.add(zi); usados_g.add(gi)
            g = grupos[gi]
            g["itens"].append((i, voltas[i]["zonas"][zi]))
            g["idxs"].add(i)
            g["centro"] = _centro([z["apice"] for _, z in g["itens"]], g["centro"], n)
        for zi, z in enumerate(voltas[i]["zonas"]):
            if zi not in usados_z:
                grupos.append({"tipo": z["tipo"], "centro": float(z["apice"]), "itens": [(i, z)], "idxs": {i}})
    curvas = []
    for g in grupos:
        c = g["centro"]
        zs = [z for _, z in g["itens"]]
        o_ini = _mediana([_volta_circ(z["ini"] - c, n) for z in zs])
        o_fim = _mediana([_volta_circ(z["fim"] - c, n) for z in zs])
        ini, fim = int(round(c + o_ini)), int(round(c + o_fim))
        curvas.append({"tipo": g["tipo"], "apice": int(round(c)) % n, "ini": ini, "fim": fim,
                       "membros": {i: z for i, z in g["itens"]}})
    curvas.sort(key=lambda c: (c["apice"], c["tipo"]))
    for k, c in enumerate(curvas):
        c["n"] = k + 1
        c["a"] = c["ini"] - int(round(PAD_ANTES_M * bm))
        c["b"] = max(c["fim"], c["ini"] + _volta_circ(c["apice"] - c["ini"], n)) + int(round(PAD_DEPOIS_M * bm))
    # sem sobreposicao entre curvas vizinhas (inclusive a ultima com a primeira, atraves da linha de chegada)
    if len(curvas) >= 2:
        for k in range(len(curvas)):
            atual, prox = curvas[k], curvas[(k + 1) % len(curvas)]
            a_prox = prox["a"] + (n if k == len(curvas) - 1 else 0)
            if atual["b"] >= a_prox:
                meio = (atual["fim"] + (prox["ini"] + (n if k == len(curvas) - 1 else 0))) // 2
                novo_b = max(atual["apice"] if atual["apice"] >= atual["a"] else atual["a"], min(atual["b"], meio))
                atual["b"] = novo_b
                prox["a"] = max(prox["a"], novo_b + 1 - (n if k == len(curvas) - 1 else 0))
    return curvas


def _centro(apices, atual, n):
    """Centro circular de um conjunto de apices (mediana dos desvios em relacao ao centro atual)."""
    return (atual + _mediana([_volta_circ(a - atual, n) for a in apices])) % n


def tempo_do_trecho(volta, a, b):
    """Segundos de a ate b (trechos, circular: a<0 ou b>=n atravessam a linha de chegada). None se faltar relogio."""
    t = volta["t_ms"]
    n = len(t)
    total = volta["tempo"] * 1000.0
    try:
        ta = t[a] if a >= 0 else t[a + n] - total
        tb = t[b] if b < n else t[b - n] + total
    except IndexError:
        return None
    s = (tb - ta) / 1000.0
    return s if s > 0 else None


def cobertura_trechos(curvas, n):
    """Fracao da pista dentro dos trechos analisados (sem contar sobreposicao)."""
    marcado = bytearray(n)
    for c in curvas:
        for k in range(c["a"], c["b"] + 1):
            marcado[k % n] = 1
    return sum(marcado) / float(n) if n else 0.0


# --------------------------------------------------------------------------
# 1) Melhor por curva (ao vivo)
def _ruido(tempos):
    """Variacao normal do tempo do trecho entre as suas voltas (desvio-padrao amostral; com menos de 3 passagens, 0)."""
    return statistics.stdev(tempos) if len(tempos) >= 3 else 0.0


def _evento_no_trecho(z, c, n):
    """O evento (apice) da zona cai dentro do trecho cronometrado da curva."""
    off = _volta_circ(z["apice"] - c["apice"], n)
    return (c["a"] - c["apice"]) <= off <= (c["b"] - c["apice"])


def dicas_por_curva(voltas, ref):
    """Para cada curva da referencia ativa, a sua passagem MAIS RAPIDA se ela superar a da referencia por margem acima do ruido:
    {n_da_referencia: {...}}. So compara eventos do MESMO tipo (freada com freada, tirada com tirada). Vazio se faltar
    historico. Descreve diferencas observadas, sem afirmar causa. Nunca troca a referencia."""
    boas = _validas(voltas)
    if len(boas) < MIN_VOLTAS_DICA or not ref:
        return {}
    curvas = agrupar(boas)
    if not curvas:
        return {}
    n = len(boas[0]["t_ms"])
    comp = float(boas[0]["comprimento"])
    if len(ref["t"]) != n or abs(float(ref["comprimento"]) - comp) > TOL_COMPRIMENTO * comp:
        return {}
    bm = n / comp
    raio = max(1.0, RAIO_AGRUPAR_M * bm)
    t_ref_ms = [int(round(x * 1000)) for x in ref["t"]]
    ref_volta = {"t_ms": t_ref_ms, "tempo": float(ref["tempo"])}
    saida = {}
    for zr in co.todas_as_zonas(ref):
        cand = [c for c in curvas if c["tipo"] == zr["tipo"] and _dist_circ(c["apice"], zr["apice"], n) <= raio]
        if not cand:
            continue
        c = min(cand, key=lambda c: _dist_circ(c["apice"], zr["apice"], n))
        if not _evento_no_trecho(zr, c, n):
            continue
        tempos = {i: tempo_do_trecho(boas[i], c["a"], c["b"]) for i in range(len(boas))}
        tempos = {i: s for i, s in tempos.items() if s is not None}
        if len(tempos) < MIN_VOLTAS_DICA:
            continue
        i_melhor = min((i for i in tempos if i in c["membros"]), key=lambda i: (tempos[i], i), default=None)
        if i_melhor is None:
            continue
        seg_ref = tempo_do_trecho(ref_volta, c["a"], c["b"])
        if seg_ref is None:
            continue
        ganho = seg_ref - tempos[i_melhor]
        ruido = _ruido(list(tempos.values()))
        if ganho < max(GANHO_MIN_S, RUIDO_K * ruido):
            continue
        zm = c["membros"][i_melhor]
        if not _evento_no_trecho(zm, c, n):
            continue
        dif_m = _volta_circ(zm["ini"] - zr["ini"], n) / float(n) * comp           # + = evento mais tarde que na referencia
        dif_v = zm["vel_apice"] - zr["vel_apice"]
        if abs(dif_m) < DIF_FREADA_MIN_M and abs(dif_v) < DIF_VEL_MIN:
            continue
        saida[zr["n"]] = {"n": zr["n"], "ganho": round(ganho, 3), "dif_tempo": round(-ganho, 3), "dif_m": round(dif_m, 1),
                          "dif_vel": round(dif_v, 1), "volta": i_melhor + 1, "tempo_volta": boas[i_melhor]["tempo"],
                          "tipo": zr["tipo"], "vel_apice": zm["vel_apice"], "marcha": zm.get("marcha"),
                          "passagens": len(tempos), "ruido": round(ruido, 3)}
    return saida


def _virgula(x, casas=2, sinal=False):
    s = f"{x:+.{casas}f}" if sinal else f"{x:.{casas}f}"
    return s.replace(".", ",")


def texto_dica(d):
    """Texto da dica: diferenca OBSERVADA, sem causalidade. Ex.: 'C4 | Melhor passagem: -0,15 s | Freada 12 m depois da referência'."""
    evento = "Tirada de pé" if d.get("tipo") == "tirada" else "Freada"
    partes = [f"C{d['n']}", f"Melhor passagem: {_virgula(d['dif_tempo'], 2, True)} s"]
    if abs(d["dif_m"]) >= DIF_FREADA_MIN_M:
        partes.append(f"{evento} {abs(d['dif_m']):.0f} m {'depois' if d['dif_m'] > 0 else 'antes'} da referência")
    if abs(d["dif_vel"]) >= DIF_VEL_MIN:
        partes.append(f"Ápice {d['dif_vel']:+.0f} km/h")
    return " | ".join(partes)


# --------------------------------------------------------------------------
# 2) Resumo da sessao
def resumo_sessao(voltas, sessao, topo=5):
    """Onde voce mais perdeu tempo nesta sessao, por curva, contra a sua MELHOR passagem (qualquer sessao):
    {voltas, voltas_base, melhor_volta, media_volta, itens[], potencial_s, ideal_s, cobertura_pista, aviso}."""
    boas = _validas(voltas)
    idx_sessao = [i for i, v in enumerate(boas) if v.get("sessao") == sessao]
    base = {"voltas": len(idx_sessao), "voltas_base": len(boas), "itens": [], "melhor_volta": None, "media_volta": None,
            "potencial_s": None, "ideal_s": None, "cobertura_pista": None, "aviso": None}
    if len(idx_sessao) < MIN_VOLTAS_SESSAO:
        base["aviso"] = f"Precisa de ao menos {MIN_VOLTAS_SESSAO} voltas validas nesta sessao (tem {len(idx_sessao)})."
        return base
    tempos_volta = [boas[i]["tempo"] for i in idx_sessao]
    base["melhor_volta"], base["media_volta"] = min(tempos_volta), sum(tempos_volta) / len(tempos_volta)
    curvas = agrupar(boas)
    n = len(boas[0]["t_ms"])
    comp = float(boas[0]["comprimento"])
    base["cobertura_pista"] = cobertura_trechos(curvas, n)
    itens = []
    for c in curvas:
        seg = {i: tempo_do_trecho(boas[i], c["a"], c["b"]) for i in range(len(boas))}
        seg = {i: s for i, s in seg.items() if s is not None}
        sessao_seg = [seg[i] for i in idx_sessao if i in seg]
        if len(sessao_seg) < MIN_VOLTAS_SESSAO or len(c["membros"]) < 2:
            continue
        melhor = min(seg.values())
        media = sum(sessao_seg) / len(sessao_seg)
        i_melhor = min((i for i in seg if i in c["membros"]), key=lambda i: (seg[i], i), default=None)
        info = {"n": c["n"], "perda_media": media - melhor, "melhor": melhor, "media": media,
                "variacao_s": statistics.pstdev(sessao_seg) if len(sessao_seg) > 1 else 0.0,
                "dif_freada_m": None, "variacao_freada_m": None, "dif_vel": None, "tipo": c["tipo"],
                "passagens": len(sessao_seg)}
        inis = [(i, c["membros"][i]) for i in idx_sessao if i in c["membros"]]
        if len(inis) >= 2 and i_melhor is not None:
            zm = c["membros"][i_melhor]
            desv = [_volta_circ(z["ini"] - zm["ini"], n) / float(n) * comp for _, z in inis]
            info["dif_freada_m"] = sum(desv) / len(desv)              # + = evento mais tarde que na melhor passagem
            info["variacao_freada_m"] = statistics.pstdev(desv)
            vs = [z["vel_apice"] for _, z in inis]
            info["dif_vel"] = sum(vs) / len(vs) - zm["vel_apice"]
        itens.append(info)
    itens.sort(key=lambda x: (-x["perda_media"], x["n"]))
    for x in itens:
        x["texto"] = _texto_item(x)
    base["itens"] = itens[:topo]
    # volta ideal: a sua melhor volta menos o que se ganharia levando cada curva ao melhor tempo (trechos nao se sobrepoem)
    i_vm = min(idx_sessao, key=lambda i: boas[i]["tempo"])
    potencial = 0.0
    for c in curvas:
        s_vm = tempo_do_trecho(boas[i_vm], c["a"], c["b"])
        todos = [tempo_do_trecho(v, c["a"], c["b"]) for v in boas]
        todos = [s for s in todos if s is not None]
        if s_vm is not None and len(todos) >= 2:
            potencial += max(0.0, s_vm - min(todos))
    base["potencial_s"] = potencial
    base["ideal_s"] = max(0.0, base["melhor_volta"] - potencial)
    return base


def _texto_item(x):
    evento = "tirada" if x["tipo"] == "tirada" else "freada"
    partes = [f"C{x['n']}: ~{_virgula(x['perda_media'])} s a mais que a sua melhor passagem (média de {x['passagens']} voltas)"]
    if x["dif_freada_m"] is not None and abs(x["dif_freada_m"]) >= 5.0:
        partes.append(f"{evento} em média {abs(x['dif_freada_m']):.0f} m {'depois' if x['dif_freada_m'] > 0 else 'antes'} da melhor passagem")
    if x["dif_vel"] is not None and abs(x["dif_vel"]) >= 2.0:
        partes.append(f"ápice {x['dif_vel']:+.0f} km/h")
    if x["variacao_freada_m"] is not None and x["variacao_freada_m"] >= 8.0:
        partes.append(f"ponto do evento varia ±{x['variacao_freada_m']:.0f} m")
    return " | ".join(partes)


def texto_resumo(r):
    """Resumo em texto puro (janela, area de transferencia e relatorio)."""
    if r["aviso"]:
        return r["aviso"]
    linhas = [f"Voltas válidas na sessão: {r['voltas']}  |  melhor {_virgula(r['melhor_volta'], 3)} s  |  média {_virgula(r['media_volta'], 3)} s",
              f"Base de comparação: {r['voltas_base']} voltas válidas do histórico deste carro e pista."]
    if r["itens"]:
        linhas.append("Onde mais perdeu tempo (tempo do trecho da curva, contra a sua melhor passagem):")
        linhas += [f"  {i + 1}. {x['texto']}" for i, x in enumerate(r["itens"])]
    else:
        linhas.append("Sem curvas comparáveis ainda (a mesma curva precisa ser detectada em várias voltas).")
    if r["potencial_s"] is not None:
        cob = "" if r["cobertura_pista"] is None else f" Os trechos analisados cobrem {100.0 * r['cobertura_pista']:.0f}% da pista."
        linhas.append(f"Volta ideal estimada: ~{_virgula(r['ideal_s'], 3)} s (~{_virgula(r['potencial_s'])} s abaixo da sua melhor). "
                      f"É uma estimativa: soma das suas melhores passagens nos trechos analisados, que não são a pista toda.{cob}")
    return "\n".join(linhas)
