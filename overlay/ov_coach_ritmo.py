# -*- coding: utf-8 -*-
"""
Resumo de stint e coach de ritmo (v1.7) - logica pura, sem Qt.

  AcumuladorStint : junta as avaliacoes curva a curva das voltas do stint e aponta ONDE se perde mais (freada, apice).
  coach_ritmo     : ritmo-alvo (media das 3 melhores voltas limpas do stint), situacao da ultima volta, tendencia e o aviso de
                    combustivel (quanto poupar por volta para chegar ao fim sem parar, quando for o caso).

Convencoes: "~" = estimativa. Nada aqui inventa dado do jogo: so combina tendencia de ritmo, avaliacao do coach e combustivel.
"""
import math


def _finito(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


class AcumuladorStint:
    """Guarda, por curva, o que o coach avaliou em cada volta do stint (maximo de voltas lembradas: 12)."""

    def __init__(self, max_voltas=12):
        self.max_voltas = max_voltas
        self.voltas = []                   # cada item: {"tempo", "diferenca_ref", "feedbacks": [...]}

    def resetar(self):
        self.voltas = []

    def registrar(self, resumo_volta):
        if not resumo_volta or not resumo_volta.get("feedbacks"):
            return False
        self.voltas.append({"tempo": resumo_volta.get("tempo"), "diferenca_ref": resumo_volta.get("diferenca_ref"),
                            "feedbacks": [dict(f) for f in resumo_volta["feedbacks"]]})
        del self.voltas[:-self.max_voltas]
        return True

    def resumo(self):
        """None sem dados; senao {'voltas', 'curvas': [{'n','media_freada_m','vezes_cedo','vezes_tarde','media_dif_vel','pior_vezes'}],
        'piores': [top 3 curvas a melhorar], 'texto': frase}."""
        if not self.voltas:
            return None
        por_curva = {}
        for v in self.voltas:
            for f in v["feedbacks"]:
                por_curva.setdefault(f["n"], []).append(f)
        curvas = []
        for n, fs in sorted(por_curva.items()):
            freadas = [f["freada_m"] for f in fs if _finito(f.get("freada_m"))]
            difs = [f["dif_vel"] for f in fs if _finito(f.get("dif_vel"))]
            cedo = sum(1 for f in fs if f.get("nota") in ("cedo", "muito_cedo"))
            tarde = sum(1 for f in fs if f.get("nota") in ("tarde", "muito_tarde"))
            curvas.append({"n": n, "voltas": len(fs),
                           "media_freada_m": sum(freadas) / len(freadas) if freadas else None,
                           "vezes_cedo": cedo, "vezes_tarde": tarde,
                           "media_dif_vel": sum(difs) / len(difs) if difs else None,
                           "gravidade_media": sum(f.get("gravidade", 0) for f in fs) / len(fs)})
        piores = sorted((c for c in curvas if c["gravidade_media"] > 0.3), key=lambda c: -c["gravidade_media"])[:3]
        if piores:
            c = piores[0]
            if c["vezes_cedo"] >= c["vezes_tarde"] and c["vezes_cedo"]:
                o = f"freia cedo ({c['vezes_cedo']} de {c['voltas']} voltas)"
            elif c["vezes_tarde"]:
                o = f"freia tarde ({c['vezes_tarde']} de {c['voltas']} voltas)"
            else:
                o = "sai lento do apice"
            texto = f"Onde mais perde: C{c['n']}, {o}"
        else:
            texto = "Sem ponto fraco claro neste stint"
        return {"voltas": len(self.voltas), "curvas": curvas, "piores": piores, "texto": texto}


def coach_ritmo(tendencia, voltas_fim=None, nivel=None, consumo=None, margem_voltas=0.5):
    """tendencia: dict de TendenciaRitmo.resumo() (ou None). voltas_fim: voltas ate a bandeirada (pode ser fracionario).
    nivel: litros no tanque. consumo: litros por volta. Devolve dict ou None."""
    if not tendencia or not tendencia.get("voltas"):
        return None
    stint = tendencia.get("stint_atual")
    atuais = [t for (_, t, s) in tendencia["voltas"] if s == stint and _finito(t)]
    if len(atuais) < 3:
        return {"alvo": None, "motivo": "poucas voltas limpas no stint", "combustivel": _combustivel(voltas_fim, nivel, consumo, margem_voltas)}
    melhores = sorted(atuais)[:3]
    alvo = sum(melhores) / 3.0
    ultima = atuais[-1]
    dif = ultima - alvo
    if dif <= 0.15:
        situacao = "no_ritmo"
    elif dif <= 0.6:
        situacao = "acima"
    else:
        situacao = "bem_acima"
    inc = tendencia.get("inclinacao")
    queda = inc is not None and inc > 0.08           # s/volta: ritmo piorando (pneu/combustivel)
    return {"alvo": alvo, "ultima": ultima, "dif": dif, "situacao": situacao, "queda": bool(queda), "inclinacao": inc,
            "consistencia": tendencia.get("consistencia"),
            "combustivel": _combustivel(voltas_fim, nivel, consumo, margem_voltas)}


def _combustivel(voltas_fim, nivel, consumo, margem_voltas):
    """Quanto poupar por volta para chegar ao fim SEM parar. None se faltam dados ou se nao ha como (precisa parar)."""
    if not (_finito(voltas_fim) and _finito(nivel) and _finito(consumo)) or consumo <= 0 or voltas_fim <= 0:
        return None
    necessario = (voltas_fim + margem_voltas) * consumo
    folga = nivel - necessario
    if folga >= 0:
        return {"estado": "ok", "folga_l": folga, "poupar_l_volta": 0.0, "poupar_pct": 0.0}
    poupar = -folga / voltas_fim
    pct = 100.0 * poupar / consumo
    estado = "poupar" if pct <= 6.0 else "parada"       # mais de ~6% por volta ja pede estrategia de parada, nao de economia
    return {"estado": estado, "folga_l": folga, "poupar_l_volta": poupar, "poupar_pct": pct}


def texto_ritmo(r):
    """Linha curta para a janela."""
    if not r:
        return ""
    if r.get("alvo") is None:
        return "Ritmo: aguardando voltas limpas"
    m = int(r["alvo"] // 60)
    s = r["alvo"] - 60 * m
    alvo = f"{m}:{s:06.3f}"
    base = {"no_ritmo": "no ritmo", "acima": f"+{r['dif']:.1f} s", "bem_acima": f"+{r['dif']:.1f} s"}[r["situacao"]]
    c = r.get("combustivel")
    extra = ""
    if c and c["estado"] == "poupar":
        extra = f" | poupe {math.ceil(c['poupar_pct'] - 1e-9)}%/volta"
    elif c and c["estado"] == "parada":
        extra = " | combustivel pede parada"
    elif r.get("queda"):
        extra = " | ritmo caindo"
    return f"Alvo {alvo} | {base}{extra}"
