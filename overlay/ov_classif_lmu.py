# -*- coding: utf-8 -*-
"""
Classificacao detalhada do LMU - logica pura (sem Qt, sem leitura de memoria): recebe uma lista de carros ja extraida
do jogo e devolve a estrutura que a janela desenha.

Origem de cada informacao (nada estimado e apresentado como medido):
  MEDIDO PELO JOGO : posicao, classe, voltas, ultima/melhor volta, paradas, penalidades, % de combustivel,
                     estado nos boxes, resultado (fim/DNF/DSQ), intervalo para o carro logo a frente (quando ele e o
                     vizinho direto na classificacao geral).
  CALCULADO AQUI   : posicao na classe, variacao em relacao ao grid (pela posicao de qualificacao do jogo),
                     media das ultimas 5 voltas, gap para o lider da classe e intervalos que nao sao vizinhos diretos.
  ESTIMADO ("~")   : tempo de gap/intervalo entre carros que NAO sao vizinhos diretos na classificacao geral
                     (distancia na pista x melhor volta da classe). O proprio texto da janela leva "~".
"""
import math
from collections import deque

MEDIA_VOLTAS = 5            # voltas da media
MINIMO_PARA_MEDIA = 2       # menos que isso: "--" (uma volta so nao e media)
VOLTA_LENTA = 1.30          # volta acima de 130 % da melhor do proprio carro nao entra na media (bandeira, incidente)


def finito(v):
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def tempo_ok(v):
    """Tempo de volta valido (> 0 e finito); -1 do jogo = sem tempo."""
    return float(v) if finito(v) and float(v) > 0 else None


class HistoricoVoltas:
    """Guarda, por carro, as ultimas voltas VALIDAS para a media. Fica de fora da media: volta com passagem pelos
    boxes (entrada ou saida), volta muito lenta (> 130 % da melhor do carro) e a volta de largada."""

    def __init__(self):
        self._chave = None
        self._carros = {}

    def atualizar(self, chave_sessao, carros):
        if chave_sessao != self._chave:                     # nova sessao: recomeca
            self._chave, self._carros = chave_sessao, {}
        for c in carros:
            k = (c["id"], c["piloto"], c["veiculo"])        # o id pode ser reaproveitado quando alguem sai do servidor
            voltas = int(c["voltas"])
            est = self._carros.get(k)
            if est is None:
                self._carros[k] = {"voltas": voltas, "box": bool(c["box"]), "tempos": deque(maxlen=MEDIA_VOLTAS)}
                continue
            if voltas == est["voltas"] + 1:
                ultima, melhor = tempo_ok(c["ultima"]), tempo_ok(c["melhor"])
                if (ultima is not None and not est["box"] and est["voltas"] >= 1
                        and (melhor is None or ultima <= melhor * VOLTA_LENTA)):
                    est["tempos"].append(ultima)
                est["voltas"], est["box"] = voltas, bool(c["box"])
            elif voltas != est["voltas"]:                   # salto ou retrocesso: nao da para confiar
                est["tempos"].clear()
                est["voltas"], est["box"] = voltas, bool(c["box"])
            elif c["box"]:
                est["box"] = True

    def media(self, c):
        est = self._carros.get((c["id"], c["piloto"], c["veiculo"]))
        if not est or len(est["tempos"]) < MINIMO_PARA_MEDIA:
            return None
        return sum(est["tempos"]) / len(est["tempos"])


def _progresso(c, comprimento):
    """Voltas completas + fracao da volta atual (so voltas inteiras se o comprimento da pista for desconhecido)."""
    frac = 0.0
    if comprimento and comprimento > 100.0 and finito(c["dist"]):
        frac = (float(c["dist"]) / comprimento) % 1.0 if float(c["dist"]) >= 0 else 0.0
    return int(c["voltas"]) + frac


def _intervalo(frente, atras, ref, comprimento):
    """Diferenca de `atras` para o carro `frente` (da mesma classe): {"tipo": "voltas"|"tempo", ...} ou None."""
    d = _progresso(frente, comprimento) - _progresso(atras, comprimento)
    if not finito(d):
        return None, None
    if d >= 1.0:
        return {"tipo": "voltas", "valor": int(d)}, None
    d = max(0.0, d)
    vizinhos = int(atras["lugar"]) == int(frente["lugar"]) + 1
    tbn = atras["tbn"]
    if vizinhos and finito(tbn) and 0.0 <= float(tbn) < 3600.0 and int(atras["lbn"]) == 0:
        # MEDIDO pelo jogo. Guardamos tambem a estimativa para comparar no log (validacao no jogo real).
        est = d * ref if ref else None
        return {"tipo": "tempo", "valor": float(tbn), "estimado": False}, (float(tbn), est)
    if ref:
        return {"tipo": "tempo", "valor": d * ref, "estimado": True}, None
    return None, None


def _variacao_grid(membros, tipo_sessao):
    """{id: ganhos} = posicao no grid (na classe, pela qualificacao do jogo) menos a posicao atual na classe.
    Positivo = ganhou posicoes. So na corrida e so se a qualificacao de TODOS da classe for valida e sem repeticao."""
    if tipo_sessao != "CORRIDA":
        return {}
    quals = [int(c["quali"]) for c in membros]
    if any(q < 1 for q in quals) or len(set(quals)) != len(quals):
        return {}
    ordem_grid = {id(c): i for i, c in enumerate(sorted(membros, key=lambda c: int(c["quali"])), start=1)}
    return {id(c): ordem_grid[id(c)] - pos for pos, c in enumerate(membros, start=1)}


def montar(carros, comprimento, tipo_sessao, historico, sessao=None, volta=None):
    """Estrutura da janela. `carros`: lista de dicts (ver extrair_carros em overlay_lmu). None se nao ha dados."""
    carros = [c for c in carros if int(c["lugar"]) > 0]
    if not carros or not any(c["eu"] for c in carros):
        return None
    if historico is not None:
        historico.atualizar(sessao.get("chave") if sessao else None, carros)
    combustivel_informado = any(int(c["combustivel"]) > 0 for c in carros)

    grupos = {}
    for c in carros:
        grupos.setdefault(c["classe"]["rotulo"], []).append(c)
    classes, comparacoes = [], []
    for rotulo, membros in grupos.items():
        membros.sort(key=lambda c: int(c["lugar"]))
        validos = [t for t in (tempo_ok(c["melhor"]) for c in membros) if t]
        melhor_classe = min(validos) if validos else None
        variacao = _variacao_grid(membros, tipo_sessao)
        linhas, anterior, soma, gap_estimado, gap_ok = [], None, 0.0, False, True
        lider = membros[0]
        for pos, c in enumerate(membros, start=1):
            ultima, melhor = tempo_ok(c["ultima"]), tempo_ok(c["melhor"])
            intervalo = gap = None
            if anterior is None:
                gap = {"tipo": "lider", "valor": int(c["voltas"])}
            else:
                intervalo, cmp_ = _intervalo(anterior, c, melhor_classe, comprimento)
                if cmp_ is not None:
                    comparacoes.append(cmp_)
                d_lider = _progresso(lider, comprimento) - _progresso(c, comprimento)
                if finito(d_lider) and d_lider >= 1.0:
                    gap = {"tipo": "voltas", "valor": int(d_lider)}
                    gap_ok = False                              # depois de uma volta de diferenca nao somamos tempos
                elif intervalo is not None and intervalo["tipo"] == "tempo" and gap_ok:
                    soma += intervalo["valor"]
                    gap_estimado = gap_estimado or bool(intervalo.get("estimado"))
                    gap = {"tipo": "tempo", "valor": soma, "estimado": gap_estimado}
                else:
                    gap_ok = False
            if c["final"] == 1:
                status = "FIM"
            elif c["final"] == 2:
                status = "DNF"
            elif c["final"] == 3:
                status = "DSQ"
            else:
                status = None
            frac = int(c["combustivel"])
            linhas.append({
                "pos": pos, "numero": c["numero"], "marca": c["marca"], "nome": c["nome"], "pais": "---",
                "ultima": ultima, "melhor": melhor, "eu": bool(c["eu"]), "na_box": bool(c["box"]),
                "melhor_da_classe": (melhor is not None and melhor_classe is not None
                                     and abs(melhor - melhor_classe) < 0.0005),
                "pb": (ultima is not None and melhor is not None and abs(ultima - melhor) < 0.0005),
                "variacao": variacao.get(id(c)),
                "paradas": max(0, int(c["paradas"])),
                "combustivel_pct": (frac / 255.0 * 100.0) if combustivel_informado else None,
                "gap": gap, "intervalo": intervalo,
                "media5": historico.media(c) if historico is not None else None,
                "penalidades": max(0, int(c["penalidades"])),
                "status": status,
            })
            anterior = c
        classes.append({
            "nome": rotulo, "cor": membros[0]["classe"]["cor"], "ordem": membros[0]["classe"]["ordem"], "sof": None,
            "n_carros": len(membros), "minha": any(c["eu"] for c in membros), "linhas": linhas,
        })
    classes.sort(key=lambda c: (c["ordem"], c["nome"]))
    return {"classes": classes, "tipo_sessao": tipo_sessao, "volta": volta, "sessao": sessao or {},
            "comparacao_gap": comparacoes}


# ---- formatacao (usada pela janela e pelos testes) --------------------------------------------------------------
def fmt_gap(g):
    """Texto da celula GAP/INT: 'V 29' (lider), '+16.4', '~+16.4' (estimado), '+1 V' (uma volta ou mais atras), '--'."""
    if not g:
        return "--"
    if g["tipo"] == "lider":
        return f"V {g['valor']}"
    if g["tipo"] == "voltas":
        return f"+{g['valor']} V"
    sinal = "~" if g.get("estimado") else ""
    return f"{sinal}+{g['valor']:.1f}"


def fmt_hms(seg):
    """3723 -> '1:02:03'; None -> '--:--:--'."""
    if seg is None or not finito(seg) or seg < 0:
        return "--:--:--"
    seg = int(seg)
    return f"{seg // 3600}:{(seg // 60) % 60:02d}:{seg % 60:02d}"
