# -*- coding: utf-8 -*-
"""
Estrategia do LMU - logica pura (sem Qt): energia virtual + combustivel, historico de stints e tendencia de ritmo.

Origem dos numeros:
  MEDIDO PELO JOGO  : nivel de energia virtual (fracao 0..1), litros, composto, desgaste, temperaturas, tempos de volta.
  CALCULADO AQUI    : consumo por volta (media das ultimas voltas limpas), alcance, janela de pit, alvo por volta,
                      resumo por stint e tendencia (regressao linear das voltas limpas).
  NAO EXISTE NO JOGO: tempo de parada planejado, tempo de reparo e previsao do tempo: este modulo NAO os inventa.
"""
import math

CONSUMO_MINIMO_ENERGIA = 0.05      # % de energia por volta abaixo disso = o carro nao usa energia virtual (ou nao mudou)
VOLTA_LENTA = 1.30                 # volta acima de 130 % da melhor nao conta como "limpa" (bandeira, incidente)
MAX_VOLTAS_TENDENCIA = 60
MINIMO_VOLTAS_TENDENCIA = 4


def finito(v):
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------------------------------------------
# Energia virtual + combustivel
# ---------------------------------------------------------------------------------------------------------------
def painel_energia(ve_pct, ve_por_volta, comb_l, capacidade_l, comb_por_volta, voltas_fim, volta_atual, margem=1.0):
    """Painel de energia e combustivel.

    ve_pct / ve_por_volta : energia virtual restante e consumo medio (em % do total por volta) ou None
    comb_l / comb_por_volta: litros no tanque e consumo medio (L por volta) ou None; capacidade_l pode ser None
    voltas_fim            : voltas ate o fim da sessao (None se nao da para saber)
    margem                : voltas de folga de seguranca
    """
    usa_energia = bool(finito(ve_pct) and finito(ve_por_volta) and ve_por_volta > CONSUMO_MINIMO_ENERGIA)
    usa_comb = bool(finito(comb_l) and finito(comb_por_volta) and comb_por_volta > 0)
    r = {"energia": None, "combustivel": None, "limitante": None, "alcance": None, "voltas_fim": voltas_fim,
         "margem": margem, "precisa_parar": None, "paradas": None, "janela": None, "alvo_energia": None,
         "alvo_comb": None, "mensagem": "sem_dados", "ve_informada": finito(ve_pct)}
    alcances, cheios = {}, {}
    if usa_energia:
        alcance = ve_pct / ve_por_volta
        alcances["energia"], cheios["energia"] = alcance, 100.0 / ve_por_volta
    if usa_comb:
        alcance = comb_l / comb_por_volta
        alcances["combustivel"] = alcance
        if finito(capacidade_l) and capacidade_l > 0:
            cheios["combustivel"] = capacidade_l / comb_por_volta
    r["energia"] = {"nivel_pct": ve_pct if finito(ve_pct) else None, "por_volta": ve_por_volta if usa_energia else None,
                    "alcance": alcances.get("energia")}
    r["combustivel"] = {"litros": comb_l if finito(comb_l) else None, "capacidade": capacidade_l if finito(capacidade_l) else None,
                        "por_volta": comb_por_volta if usa_comb else None, "alcance": alcances.get("combustivel")}
    if not alcances:
        return r
    r["limitante"] = min(alcances, key=alcances.get)
    r["alcance"] = alcances[r["limitante"]]
    cheio = min(cheios.values()) if cheios else None          # voltas com tanque/energia cheios (recurso mais curto)
    if finito(voltas_fim) and voltas_fim > 0:
        if usa_energia:
            r["alvo_energia"] = ve_pct / voltas_fim
        if usa_comb:
            r["alvo_comb"] = comb_l / voltas_fim
        r["precisa_parar"] = (voltas_fim + margem) > r["alcance"]
        if not r["precisa_parar"]:
            r["paradas"], r["mensagem"] = 0, "chega"
        elif cheio is None or cheio - margem <= 0:
            r["mensagem"] = "parada"
        else:
            rende = cheio - margem                                         # voltas que uma parada acrescenta
            falta = voltas_fim + margem - r["alcance"]
            paradas = max(1, int(math.ceil(falta / rende - 1e-9)))
            r["paradas"] = paradas
            r["mensagem"] = "parada" if paradas == 1 else "paradas"
            ultima = int(math.floor(r["alcance"] - margem))                # voltas a partir de agora (ultima chance)
            primeira = int(math.ceil(voltas_fim + margem - cheio))         # cedo demais: nao cabe tudo no tanque
            if paradas == 1 and finito(volta_atual) and ultima >= 0:
                r["janela"] = (int(volta_atual) + max(0, primeira), int(volta_atual) + ultima)
    else:
        r["mensagem"] = "sem_fim"                                          # sessao sem fim conhecido
    return r


# ---------------------------------------------------------------------------------------------------------------
# Historico de stints
# ---------------------------------------------------------------------------------------------------------------
def _novo_stint(n, parcial, ve, comb, desgaste, composto, temp_pista):
    return {"n": n, "parcial": parcial, "voltas": 0, "tempo": 0.0, "ve_ini": ve, "ve_fim": ve, "comb_ini": comb,
            "comb_fim": comb, "des_ini": desgaste, "des_fim": desgaste, "composto": composto, "limpas": [],
            "temp_ini": temp_pista, "temp_fim": temp_pista}


class HistoricoStints:
    """Acompanha os stints do SEU carro. Um stint comeca na saida dos boxes. Se o overlay for aberto no meio de um stint,
    ele e marcado como parcial (o consumo inicial e o do momento em que o overlay abriu)."""

    MAX_STINTS = 12

    def __init__(self):
        self.resetar(None)

    def resetar(self, chave):
        self._chave = chave
        self.stints = []
        self.voltas_limpas = []                 # (numero da volta, tempo, temp. pista, numero do stint)
        self._voltas_ant = None
        self._box_ant = False
        self._box_na_volta = False

    def atualizar(self, chave, voltas_concluidas, na_box, ve_pct, comb_l, desgaste, composto, ultima_volta, melhor,
                  temp_pista):
        """`desgaste`: media das 4 rodas (0..1, como o jogo informa) ou None."""
        if chave != self._chave:
            self.resetar(chave)
        ve = ve_pct if finito(ve_pct) else None
        comb = comb_l if finito(comb_l) else None
        des = desgaste if finito(desgaste) else None
        temp = temp_pista if finito(temp_pista) else None
        if not self.stints:
            self.stints.append(_novo_stint(1, voltas_concluidas > 0, ve, comb, des, composto, temp))
            self._voltas_ant, self._box_ant, self._box_na_volta = voltas_concluidas, bool(na_box), bool(na_box)
            return
        atual = self.stints[-1]
        if self._box_ant and not na_box:                                   # saiu dos boxes: novo stint
            if atual["voltas"] == 0 and not atual["parcial"]:
                atual.update(ve_ini=ve, ve_fim=ve, comb_ini=comb, comb_fim=comb, des_ini=des, des_fim=des,
                             composto=composto, temp_ini=temp, temp_fim=temp)
            else:
                self.stints.append(_novo_stint(atual["n"] + 1, False, ve, comb, des, composto, temp))
                del self.stints[:-self.MAX_STINTS]
            atual = self.stints[-1]
        if voltas_concluidas == self._voltas_ant + 1:                      # volta completada
            atual["voltas"] += 1
            tempo = ultima_volta if finito(ultima_volta) and ultima_volta > 0 else None
            if tempo is not None:
                atual["tempo"] += tempo
                if not self._box_na_volta and (not finito(melhor) or melhor <= 0 or tempo <= melhor * VOLTA_LENTA):
                    atual["limpas"].append(tempo)
                    self.voltas_limpas.append((voltas_concluidas, tempo, temp, atual["n"]))
                    del self.voltas_limpas[:-MAX_VOLTAS_TENDENCIA]
            self._box_na_volta = bool(na_box)
        elif voltas_concluidas != self._voltas_ant:                        # salto/retrocesso: nao da para confiar
            self._box_na_volta = True
        self._voltas_ant = voltas_concluidas
        if na_box:
            self._box_na_volta = True
        else:                                                              # com o carro na pista os valores sao confiaveis
            atual["ve_fim"], atual["comb_fim"], atual["des_fim"], atual["temp_fim"] = ve, comb, des, temp
        self._box_ant = bool(na_box)

    def resumo(self, melhor_sessao=None):
        """Lista (mais recente primeiro) de stints com os totais calculados."""
        saida = []
        for s in reversed(self.stints):
            usado = lambda a, b: (a - b) if (a is not None and b is not None and a - b >= -0.01) else None
            energia = usado(s["ve_ini"], s["ve_fim"])
            comb = usado(s["comb_ini"], s["comb_fim"])
            desgaste = abs(s["des_ini"] - s["des_fim"]) * 100.0 if (s["des_ini"] is not None and s["des_fim"] is not None) else None
            ritmo = (sum(s["limpas"]) / len(s["limpas"])) if s["limpas"] else None
            delta = (ritmo - melhor_sessao) if (ritmo is not None and finito(melhor_sessao) and melhor_sessao > 0) else None
            saida.append({"n": s["n"], "atual": s is self.stints[-1], "parcial": s["parcial"], "voltas": s["voltas"],
                          "tempo": s["tempo"] if s["voltas"] else None, "energia": max(0.0, energia) if energia is not None else None,
                          "comb": max(0.0, comb) if comb is not None else None, "composto": s["composto"],
                          "desgaste": desgaste, "ritmo": ritmo, "delta": delta, "limpas": len(s["limpas"])})
        return saida

    def tendencia(self, melhor_sessao=None):
        """Ritmo das voltas limpas do stint atual + regressao linear (s/volta) quando ha voltas suficientes."""
        if not self.stints:
            return None
        n_atual = self.stints[-1]["n"]
        todas = list(self.voltas_limpas)
        atuais = [(v, t, tp) for v, t, tp, n in todas if n == n_atual]
        out = {"voltas": todas, "stint_atual": n_atual, "melhor": melhor_sessao if finito(melhor_sessao) and melhor_sessao > 0 else None,
               "ritmo5": None, "delta_ritmo": None, "inclinacao": None, "temp_pista": None, "temp_variacao": None}
        if not todas:
            return out
        ultimos = [t for _, t, _, _ in todas[-5:]]
        out["ritmo5"] = sum(ultimos) / len(ultimos)
        if out["melhor"]:
            out["delta_ritmo"] = out["ritmo5"] - out["melhor"]
        if len(atuais) >= MINIMO_VOLTAS_TENDENCIA:
            xs, ys = [a[0] for a in atuais], [a[1] for a in atuais]
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            den = sum((x - mx) ** 2 for x in xs)
            if den > 0:
                out["inclinacao"] = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
        temps = [tp for _, _, tp, _ in todas if tp is not None]
        if temps:
            out["temp_pista"] = temps[-1]
            out["temp_variacao"] = temps[-1] - temps[0] if len(temps) > 1 else 0.0
        return out


def fmt_duracao(seg):
    """1408 -> '23:28'; 5000 -> '1:23:20'; None -> '--'."""
    if not finito(seg) or seg < 0:
        return "--"
    seg = int(round(seg))
    h, m, s = seg // 3600, (seg // 60) % 60, seg % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
