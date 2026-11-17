# -*- coding: utf-8 -*-
"""v1.8: logica pura (sem Qt, sem jogo) das janelas novas. Identico nas arvores iRacing e LMU.

Tudo recebe o tempo e os dados de fora (testavel); nada e gravado em disco, exceto o calendario, que so le um CSV do piloto.

JANELAS ALIMENTADAS POR ESTE MODULO (cada uma mostra so o que o jogo informa; nada e estimado alem do dito):
  vazao        Mapa de vazao: consumo instantaneo (L/h) medio por faixa de RPM x abertura do acelerador (11 x 10 celulas).
  marcha       Eficiencia por marcha: litros por 100 km a ACELERADOR PLENO, por marcha e faixa de RPM, e a parcela do tempo em cada marcha.
  destino      Destino do combustivel: parcela dos litros gastos em cada faixa de acelerador x RPM (FLAT/HIGH/MID/LOW/COAST) e total do stint.
  ultrapassagem Alerta de ultrapassagem: carros de TRAS que se aproximam (diferenca em segundos caindo) e estao perto.
  hibrido      Energia hibrida: carga da bateria, uso de deploy e os valores da volta anterior (so quando o jogo informa).
  sessao       Relogio da sessao: tempo (ou voltas) restante e a fracao ja corrida.
  calendario   Proximas corridas de um CSV local do piloto (o iRacing nao libera a agenda sem login na conta).

O consumo instantaneo vem do NIVEL do tanque em litros (mesmo calculo do Fuel Flow da 1.7.0, igual nos dois jogos).
"""
from collections import deque
import csv
import math
import datetime as _dt

N_COLS = 10                      # faixas de RPM (de LIMITE_RPM_INF * rpm_max ate rpm_max)
LIMITE_RPM_INF = 0.35
N_LINHAS_ACEL = 11               # 0%, 10%, ..., 100% de acelerador
MAX_MARCHAS = 8
ACEL_PLENO = 0.90                # "acelerador a fundo" para a eficiencia por marcha
VEL_MIN_KMH = 20.0               # abaixo disso, litros/100 km nao faz sentido
TRILHA_S = 4.0                   # a trilha do mapa de vazao mostra os ultimos segundos da posicao (rpm x acelerador)
TRILHA_MAX = 48
MIN_T_CELULA = 0.05              # segundos de amostra (ponderados pelo tempo) para a celula aparecer
DT_MAX_S = 0.5                   # intervalos maiores que isso (pausa, menu) nao entram nas somas
FAIXAS_ACEL = (("FLAT", 0.90), ("HIGH", 0.60), ("MID", 0.30), ("LOW", 0.05), ("COAST", 0.0))
JANELA_GAP_S = 4.0
FECHA_MIN = 0.02                 # s/s de aproximacao para considerar "fechando"
SEGURA_ALERTA_S = 2.0            # o alerta fica este tempo depois de sumir a causa (nao pisca)


def _fin(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def coluna_rpm(rpm, rpm_max):
    """Indice 0..N_COLS-1 da faixa de RPM (abaixo do limite inferior = 0)."""
    if not (_fin(rpm) and _fin(rpm_max)) or rpm_max <= 0:
        return None
    lo = LIMITE_RPM_INF * rpm_max
    return max(0, min(N_COLS - 1, int((rpm - lo) / (rpm_max - lo) * N_COLS)))


def limites_rpm(rpm_max):
    """Lista de (inicio, fim) de cada faixa de RPM."""
    lo = LIMITE_RPM_INF * rpm_max
    passo = (rpm_max - lo) / N_COLS
    return [(lo + i * passo, lo + (i + 1) * passo) for i in range(N_COLS)]


def linha_acel(acel):
    return max(0, min(N_LINHAS_ACEL - 1, int(round(acel * (N_LINHAS_ACEL - 1)))))


def faixa_acel(acel):
    for nome, minimo in FAIXAS_ACEL:
        if acel >= minimo:
            return nome
    return "COAST"


def nome_curto(nome):
    """'Istvan Fodor' -> 'Istvan FODOR' (ultimo nome em maiusculas)."""
    partes = str(nome or "").split()
    if len(partes) < 2:
        return str(nome or "")
    return " ".join(partes[:-1]) + " " + partes[-1].upper()


class Coletor:
    """Recebe um dicionario 'entrada' por ciclo e devolve o dicionario 'v18' que as janelas leem."""

    def __init__(self):
        self.resetar()

    def resetar(self):
        self._rpm_max = None
        self._fluxo = [[[0.0, 0.0, 0] for _ in range(N_COLS)] for _ in range(N_LINHAS_ACEL)]      # [linha][col] = [soma(L/h x dt), soma(dt), n]
        self._marcha = {}                  # marcha -> [[soma(L/100km x dt), soma(dt), n] x N_COLS]
        self._marcha_t = {}                # marcha -> segundos a acelerador pleno
        self._marcha_rpm_max = {}          # marcha -> MAIOR RPM OBSERVADO a acelerador pleno (nao e deteccao de troca de marcha)
        self._trilha = []                  # [(linha, coluna, t)] posicoes recentes no mapa de vazao (so apresentacao)
        self._marcha_glob = [0.0, 0.0, 0.0]  # [litros, km, segundos] das amostras elegiveis (media geral = litros / km x 100)
        self._zona = {n: [0.0] * N_COLS for n, _ in FAIXAS_ACEL}                            # litros
        self._litros_total = 0.0
        self._stint_l = 0.0
        self._stint_voltas = 0
        self._volta_ult = None
        self._t_ult = None
        self._box_antes = False
        self._gaps = {}
        self._alertas = {}
        self._hib = {"volta": None, "t_ativo": 0.0, "t_total": 0.0, "ult_carga": None, "ult_deploy": None, "ultima_carga": None, "ultimo_deploy": None}

    # ------------------------------------------------------------------ entrada
    def atualizar(self, e):
        agora = e.get("agora")
        if not _fin(agora):
            return self.resumo(e)
        dt = 0.0 if self._t_ult is None else agora - self._t_ult
        self._t_ult = agora
        if dt < 0 or dt > DT_MAX_S:
            dt = 0.0
        rpm_max = e.get("rpm_max")
        if _fin(rpm_max) and rpm_max > 1000 and self._rpm_max is not None and abs(rpm_max - self._rpm_max) > 1.0:
            # outro carro: as faixas de RPM mudam, entao o mapa recomeca (stint e alertas seguem)
            self._fluxo = [[[0.0, 0.0, 0] for _ in range(N_COLS)] for _ in range(N_LINHAS_ACEL)]
            self._marcha, self._marcha_t, self._marcha_rpm_max = {}, {}, {}
            self._marcha_glob = [0.0, 0.0, 0.0]
            self._trilha = []
            self._zona = {n: [0.0] * N_COLS for n, _ in FAIXAS_ACEL}
            self._litros_total = 0.0
        if _fin(rpm_max) and rpm_max > 1000:
            self._rpm_max = float(rpm_max)
        self._consumo(e, dt)
        self._stint(e)
        self._ultrapassagem(e, agora)
        self._hibrido(e, dt)
        return self.resumo(e)

    def _consumo(self, e, dt):
        if not e.get("valido") or self._rpm_max is None:
            return
        rpm, ace, lh = e.get("rpm"), e.get("acel"), e.get("inst_lh")
        if not (_fin(rpm) and _fin(ace) and _fin(lh)) or lh < 0 or rpm <= 0:
            return
        col = coluna_rpm(rpm, self._rpm_max)
        if col is None:
            return
        ace = max(0.0, min(1.0, ace))
        self._marcar_trilha(linha_acel(ace), col, e.get("agora"))
        c = self._fluxo[linha_acel(ace)][col]
        c[2] += 1
        if dt > 0:                                   # media PONDERADA PELO TEMPO: a taxa de aquisicao nao muda o resultado
            c[0] += lh * dt
            c[1] += dt
        if dt > 0:
            litros = lh / 3600.0 * dt
            self._zona[faixa_acel(ace)][col] += litros
            self._litros_total += litros
            self._stint_l += litros
        marcha = e.get("marcha")
        vel = e.get("vel_kmh")
        if isinstance(marcha, int) and 1 <= marcha <= MAX_MARCHAS and ace >= ACEL_PLENO:
            self._marcha_t[marcha] = self._marcha_t.get(marcha, 0.0) + dt
            self._marcha_rpm_max[marcha] = max(self._marcha_rpm_max.get(marcha, 0.0), float(rpm))
            if _fin(vel) and vel >= VEL_MIN_KMH:
                linha = self._marcha.setdefault(marcha, [[0.0, 0.0, 0] for _ in range(N_COLS)])
                linha[col][2] += 1
                if dt > 0:
                    linha[col][0] += lh / vel * 100.0 * dt
                    linha[col][1] += dt
                    g_ = self._marcha_glob                       # mesmas amostras das celulas: consumo total / distancia total
                    g_[0] += lh / 3600.0 * dt
                    g_[1] += vel / 3600.0 * dt
                    g_[2] += dt

    def _marcar_trilha(self, li, col, agora):
        if not _fin(agora):
            return
        if self._trilha and self._trilha[-1][0] == li and self._trilha[-1][1] == col:
            self._trilha[-1] = (li, col, agora)                      # mesma celula: so renova o instante
        else:
            self._trilha.append((li, col, agora))
            if len(self._trilha) > TRILHA_MAX:
                del self._trilha[0]

    def _stint(self, e):
        box = bool(e.get("box"))
        if self._box_antes and not box:                      # saiu dos boxes: stint novo
            self._stint_l, self._stint_voltas = 0.0, 0
        self._box_antes = box
        volta = e.get("volta")
        if isinstance(volta, int):
            if self._volta_ult is not None and volta == self._volta_ult + 1 and e.get("valido"):
                self._stint_voltas += 1
            self._volta_ult = volta

    @staticmethod
    def _chave_carro(d, vistos):
        """Identidade estavel do carro: 'id' do jogo (iRacing: indice do carro; LMU: mID). Sem ele, numero+classe+nome (nunca so o numero:
        carros de classes diferentes repetem o numero). Se ainda colidir no mesmo ciclo, o indice da ocorrencia desempata."""
        ident = d.get("id", d.get("idx"))
        base = ("id", ident) if ident is not None else ("n", str(d.get("numero")), str(d.get("classe_nome") or d.get("classe_cor") or ""), str(d.get("nome") or ""))
        chave, k = base, 1
        while chave in vistos:
            k += 1
            chave = base + (k,)
        return chave

    def _ultrapassagem(self, e, agora):
        rel = e.get("relativo") or {}
        vistos = set()
        for d in (rel.get("atras") or []):
            if not isinstance(d, dict) or d.get("eu"):
                continue
            gap = d.get("gap")
            if not _fin(gap) or (d.get("numero") is None and d.get("id", d.get("idx")) is None):
                continue
            gap = abs(gap)
            chave = self._chave_carro(d, vistos)
            vistos.add(chave)
            ident = (str(d.get("numero")), str(d.get("nome") or ""))
            reg = self._gaps.get(chave)
            if reg is None or reg["ident"] != ident:         # carro novo ou outro piloto/numero no mesmo id: historico recomeca
                reg = self._gaps[chave] = {"h": deque(), "ident": ident}
                self._alertas.pop(chave, None)
            h = reg["h"]
            h.append((agora, gap))
            while h and agora - h[0][0] > JANELA_GAP_S:
                h.popleft()
            fecha = None
            if len(h) >= 2 and h[-1][0] - h[0][0] >= 1.0:
                fecha = (h[0][1] - h[-1][1]) / (h[-1][0] - h[0][0])
            limite = float(e.get("ultrap_limite", 3.0))
            if d.get("na_box") or (d.get("volta_rel") or 0) != 0 and e.get("ultrap_so_mesma_volta", True):
                continue
            if e.get("ultrap_so_outras") and d.get("mesma_classe"):
                continue
            perto = gap <= limite
            fechando = fecha is not None and fecha >= FECHA_MIN
            if perto and (fechando or gap <= 1.0):
                self._alertas[chave] = {"ate": agora + SEGURA_ALERTA_S, "id": d.get("id", d.get("idx")), "numero": d.get("numero"), "nome": d.get("nome", ""),
                                        "gap": gap, "fecha": fecha, "cor": d.get("classe_cor"), "classe": d.get("classe_nome") or "",
                                        "mesma_classe": bool(d.get("mesma_classe"))}
            elif chave in self._alertas:
                self._alertas[chave]["gap"] = gap
                self._alertas[chave]["fecha"] = fecha
        for chave in list(self._gaps):
            if chave not in vistos:
                del self._gaps[chave]
        for chave in list(self._alertas):
            if self._alertas[chave]["ate"] < agora:
                del self._alertas[chave]

    def _hibrido(self, e, dt):
        """'ult_carga' / 'ult_deploy' = a ULTIMA leitura valida da volta que acabou (lida antes da leitura que traz a volta nova),
        nunca a leitura do instante da troca de volta."""
        h = e.get("hibrido")
        st = self._hib
        if not isinstance(h, dict) or not _fin(h.get("carga")):
            return                                           # leitura invalida: nada muda, o ultimo valor valido fica guardado
        volta = e.get("volta")
        if isinstance(volta, int) and isinstance(st["volta"], int) and volta != st["volta"]:
            if volta > st["volta"] and st["t_total"] > 1.0 and st["ultima_carga"] is not None:
                st["ult_carga"] = st["ultima_carga"]
                st["ult_deploy"] = st["ultimo_deploy"] if st["ultimo_deploy"] is not None else (st["t_ativo"] / st["t_total"])
            st["t_ativo"], st["t_total"] = 0.0, 0.0           # volta nova (ou contador reiniciado): recomeca a medida
            st["ultimo_deploy"] = None
        if isinstance(volta, int):
            st["volta"] = volta
        st["t_total"] += dt
        if h.get("ativo"):
            st["t_ativo"] += dt
        st["ultima_carga"] = h["carga"]
        if _fin(h.get("deploy")):
            st["ultimo_deploy"] = h["deploy"]

    # ------------------------------------------------------------------ saida
    def resumo(self, e):
        return {"vazao": self._r_vazao(e), "marcha": self._r_marcha(e), "destino": self._r_destino(e),
                "ultrapassagem": self._r_ultrap(), "hibrido": self._r_hibrido(e), "sessao": sessao(e), "rpm_max": self._rpm_max}

    def _r_vazao(self, e):
        celulas = [[(c[0] / c[1]) if c[1] >= MIN_T_CELULA else None for c in lin] for lin in self._fluxo]
        valores = [v for lin in celulas for v in lin if v is not None]
        atual = None
        if self._rpm_max and _fin(e.get("rpm")) and _fin(e.get("acel")):
            atual = (linha_acel(max(0.0, min(1.0, e["acel"]))), coluna_rpm(e["rpm"], self._rpm_max))
        cons = e.get("consumo") or {}
        return {"celulas": celulas, "maximo": max(valores) if valores else None, "minimo": min(valores) if valores else None,
                "atual": atual, "agora_lh": e.get("inst_lh"), "ultima_lv": cons.get("ultima_lv"), "medio_lv": cons.get("medio_lv"),
                "trilha": self._trilha_recente(e.get("agora")), "rpm": e.get("rpm") if _fin(e.get("rpm")) else None, "rpm_max": self._rpm_max,
                "mapa_motor": e.get("mapa_motor"), "amostras": sum(c[2] for lin in self._fluxo for c in lin)}

    def _trilha_recente(self, agora):
        if not _fin(agora):
            return []
        return [(li, co) for li, co, t in self._trilha if 0.0 <= agora - t <= TRILHA_S]

    def _r_marcha(self, e):
        total_t = sum(self._marcha_t.values())
        marchas = []
        for g in range(1, MAX_MARCHAS + 1):
            linha = self._marcha.get(g)
            if linha is None and g not in self._marcha_t:
                continue
            vals = [(c[0] / c[1]) if (linha and c[1] >= MIN_T_CELULA) else None for c in (linha or [[0.0, 0.0, 0]] * N_COLS)]
            marchas.append({"marcha": g, "celulas": vals, "parcela": (self._marcha_t.get(g, 0.0) / total_t) if total_t > 0 else None,
                            "rpm_max": self._marcha_rpm_max.get(g)})
        todos = [v for m in marchas for v in m["celulas"] if v is not None]
        gl, gkm, gt = self._marcha_glob
        media_geral = (gl / gkm * 100.0) if (todos and gt >= MIN_T_CELULA and gkm > 0) else None   # litros totais / km totais x 100
        agora_l100 = None                                   # consumo instantaneo (L/100 km) so quando a amostra seria elegivel
        lh, vel, ace, mar = e.get("inst_lh"), e.get("vel_kmh"), e.get("acel"), e.get("marcha")
        if _fin(lh) and _fin(vel) and _fin(ace) and vel >= VEL_MIN_KMH and lh >= 0 and ace >= ACEL_PLENO and isinstance(mar, int):
            agora_l100 = lh / vel * 100.0
        return {"marchas": marchas, "minimo": min(todos) if todos else None, "maximo": max(todos) if todos else None,
                "media": media_geral, "atual": e.get("marcha"), "agora_l100": agora_l100,
                "rpm": e.get("rpm") if _fin(e.get("rpm")) else None, "rpm_max": self._rpm_max}

    def _r_destino(self, e=None):
        tot = self._litros_total
        faixas = []
        for nome, _m in FAIXAS_ACEL:
            linha = self._zona[nome]
            soma = sum(linha)
            faixas.append({"nome": nome, "parcela": (soma / tot) if tot > 0 else None,
                           "celulas": [(v / tot) if tot > 0 else None for v in linha]})
        maior = None
        if tot > 0:
            melhor = max(((self._zona[n][c], n, c) for n, _ in FAIXAS_ACEL for c in range(N_COLS)), key=lambda x: x[0])
            if melhor[0] > 0:
                maior = {"faixa": melhor[1], "col": melhor[2], "parcela": melhor[0] / tot}
        atual = None                                          # (nome da faixa de acelerador, coluna de RPM) agora
        e = e or {}
        if self._rpm_max and _fin(e.get("rpm")) and _fin(e.get("acel")):
            atual = (faixa_acel(max(0.0, min(1.0, e["acel"]))), coluna_rpm(e["rpm"], self._rpm_max))
        parcelas = {f["nome"]: f["parcela"] for f in faixas}
        parcial = None if tot <= 0 else sum(parcelas.get(n) or 0.0 for n in ("HIGH", "MID", "LOW"))
        return {"faixas": faixas, "total_l": tot, "stint_l": self._stint_l, "stint_voltas": self._stint_voltas, "maior": maior,
                "atual": atual, "parcial": parcial, "rpm_max": self._rpm_max}

    def _r_ultrap(self):
        itens = sorted(self._alertas.values(), key=lambda a: a["gap"])
        return {"carros": [{k: v for k, v in a.items() if k != "ate"} for a in itens[:4]]}

    def _r_hibrido(self, e):
        h = e.get("hibrido")
        if not isinstance(h, dict) or not _fin(h.get("carga")):
            return None
        st = self._hib
        deploy = h.get("deploy")
        if deploy is None and st["t_total"] > 0:
            deploy = st["t_ativo"] / st["t_total"]
        return {"carga": max(0.0, min(1.0, h["carga"])), "deploy": None if deploy is None else max(0.0, min(1.0, deploy)),
                "ult_carga": st["ult_carga"], "ult_deploy": st["ult_deploy"], "ativo": bool(h.get("ativo"))}


def sessao(e):
    """Relogio da sessao: por tempo (restante em s) ou por voltas."""
    rest, voltas_rest, voltas_total, dec = e.get("restante"), e.get("voltas_rest"), e.get("voltas_total"), e.get("decorrido")
    if _fin(rest) and 0 <= rest < 86400 * 2:
        frac = None
        if _fin(dec) and dec >= 0 and dec + rest > 0:
            frac = max(0.0, min(1.0, dec / (dec + rest)))
        return {"modo": "tempo", "restante": float(rest), "fracao": frac, "texto": fmt_relogio(rest)}
    if isinstance(voltas_rest, int) and 0 <= voltas_rest < 10000:
        frac = None
        if isinstance(voltas_total, int) and voltas_total > 0 and voltas_total < 10000:
            frac = max(0.0, min(1.0, (voltas_total - voltas_rest) / voltas_total))
        return {"modo": "voltas", "restante": voltas_rest, "fracao": frac, "texto": f"{voltas_rest} voltas"}
    return None


def fmt_relogio(s):
    s = max(0, int(s))
    h, resto = divmod(s, 3600)
    m, seg = divmod(resto, 60)
    return f"{h:d}:{m:02d}:{seg:02d}" if h else f"{m:02d}:{seg:02d}"


def entrada_de_dados(dados, extra, agora):
    """Monta a 'entrada' do Coletor a partir do dicionario de telemetria ja pronto (igual nos dois jogos) mais o que cada jogo
    informa a parte em 'extra' (hibrido, restante, voltas_rest, voltas_total, decorrido). Nunca levanta erro."""
    dados = dados or {}
    extra = extra or {}
    rel = dados.get("relativo") or ({"atras": dados.get("v18_atras")} if dados.get("v18_atras") else {})
    eu = rel.get("eu") if isinstance(rel.get("eu"), dict) else {}
    cons = dados.get("consumo") or {}
    vel = dados.get("velocidade")
    e = {"agora": agora, "rpm": dados.get("rpm"), "rpm_max": dados.get("rpm_max"), "acel": dados.get("acelerador"),
         "marcha": dados.get("marcha"), "vel_kmh": vel, "inst_lh": cons.get("inst_lh") if isinstance(cons, dict) else None,
         "consumo": cons if isinstance(cons, dict) else {}, "volta": dados.get("volta"),
         "box": bool(eu.get("na_box")) if eu else bool(extra.get("box")),
         "valido": bool(dados.get("no_carro")) and not dados.get("replay") and _fin(vel) and vel > 5.0 and not (eu and eu.get("na_box")),
         "relativo": rel if isinstance(rel, dict) else {},
         "restante": extra.get("restante", rel.get("tempo_restante")), "voltas_rest": extra.get("voltas_rest", rel.get("voltas_restantes")),
         "voltas_total": extra.get("voltas_total"), "decorrido": extra.get("decorrido"), "hibrido": extra.get("hibrido")}
    for k in ("ultrap_limite", "ultrap_so_outras", "ultrap_so_mesma_volta"):
        if k in extra:
            e[k] = extra[k]
    return e


# ---------------------------------------------------------------------------------------------------------------------
# Calendario de corridas (CSV do piloto)
# ---------------------------------------------------------------------------------------------------------------------
def ler_calendario(texto):
    """CSV (virgula ou ponto e virgula): nome,classe,inicio,duracao_min[,registro_min[,repete_min]]
    inicio: 'HH:MM' (repete todo dia por padrao) ou 'AAAA-MM-DD HH:MM' (uma vez, ou repete a cada repete_min).
    Linhas vazias e comentarios (#) sao ignorados; linha com erro e descartada e listada em 'erros'."""
    itens, erros = [], []
    linhas = [l for l in str(texto or "").splitlines() if l.strip() and not l.strip().startswith("#")]
    if not linhas:
        return itens, erros
    delim = ";" if linhas[0].count(";") > linhas[0].count(",") else ","
    for n, row in enumerate(csv.reader(linhas, delimiter=delim), 1):
        row = [c.strip() for c in row]
        if not any(row):
            continue
        if n == 1 and row and row[0].lower() in ("nome", "name", "corrida"):
            continue
        try:
            if len(row) < 4:
                raise ValueError("faltam colunas")
            nome, classe, inicio, dur = row[0], row[1], row[2], int(float(row[3]))
            reg = int(float(row[4])) if len(row) > 4 and row[4] else None
            rep = int(float(row[5])) if len(row) > 5 and row[5] else None
            if dur <= 0 or dur > 24 * 60 or (reg is not None and not 0 <= reg <= dur) or (rep is not None and rep <= 0):
                raise ValueError("valor fora do limite")
            if len(inicio) <= 5:
                hh, mm = inicio.split(":")
                base, diario = _dt.time(int(hh), int(mm)), True
                data0 = None
            else:
                data0, diario = _dt.datetime.strptime(inicio, "%Y-%m-%d %H:%M"), False
                base = None
            itens.append({"nome": nome, "classe": classe, "hora": base, "data0": data0, "dur": dur, "reg": reg,
                          "rep": rep if rep else (1440 if diario else None)})
        except Exception as ex:
            erros.append(f"linha {n}: {ex}")
    return itens, erros


def proximas(itens, agora, n=4):
    """Proximas ocorrencias a partir de 'agora' (datetime). Cada item: nome, classe, inicio, dur, ate_inicio_s, reg_s (segundos
    ate fechar o registro, ou None) e 'em_andamento'."""
    out = []
    for it in itens:
        rep = it["rep"]
        if it["hora"] is not None:
            ini = _dt.datetime.combine(agora.date(), it["hora"])
            ini -= _dt.timedelta(days=1)           # comeca ontem para pegar a que ainda esta valendo
        else:
            ini = it["data0"]
        passo = _dt.timedelta(minutes=rep) if rep else None
        guarda = 0
        while ini + _dt.timedelta(minutes=it["dur"]) < agora and passo and guarda < 4000:
            ini += passo
            guarda += 1
        fim = ini + _dt.timedelta(minutes=it["dur"])
        if fim < agora:
            continue
        ate = (ini - agora).total_seconds()
        reg_fecha = None if it["reg"] is None else (ini + _dt.timedelta(minutes=it["reg"]) - agora).total_seconds()
        out.append({"nome": it["nome"], "classe": it["classe"], "inicio": ini, "dur": it["dur"], "ate_inicio_s": ate,
                    "reg_s": reg_fecha, "em_andamento": ate < 0})
    out.sort(key=lambda x: x["inicio"])
    return out[:n]


def exemplo_calendario(agora=None):
    agora = agora or _dt.datetime.now()
    base = agora.replace(second=0, microsecond=0)
    mk = lambda nome, classe, dm, dur, reg: {"nome": nome, "classe": classe, "inicio": base + _dt.timedelta(minutes=dm), "dur": dur,
                                              "ate_inicio_s": dm * 60.0, "reg_s": (dm + reg) * 60.0 if reg is not None else None,
                                              "em_andamento": dm < 0}
    return [mk("GT4 Challenge", "D", -12, 30, 15), mk("Formula 4 Series", "D", 18, 35, 15), mk("Super Formula Lights", "C", 33, 30, 15),
            mk("GT3 Sprint", "B", 63, 45, 15)]


class Servico:
    """Junta o Coletor, o calendario (CSV relido so quando o arquivo muda) e o 'extra' de cada jogo num unico passo por ciclo."""

    def __init__(self, pasta_dados=None):
        self.coletor = Coletor()
        self.pasta = pasta_dados
        self._cal_arq = None
        self._cal_mtime = None
        self._cal_itens, self._cal_erros = [], []
        self._cal_t = -1e9
        self._cal_aviso = ""
        self._cron, self._cron_aviso, self._cron_mtime, self._cron_t = None, "", None, -1e9

    def _cronograma(self, config, agora_mono):
        """cronograma.json (gerado do PDF do iRacing), relido so quando o arquivo muda."""
        import os
        import ov_cronograma as cr
        if agora_mono - self._cron_t < 2.0:                    # build al: confere o arquivo a cada 2 s (importar um PDF novo vale quase na hora)
            return
        self._cron_t = agora_mono
        arq = os.path.join(str(self.pasta), "cronograma.json") if self.pasta else "cronograma.json"
        try:
            mt = os.path.getmtime(arq)
        except OSError:
            mt = None
        if mt is not None and mt == self._cron_mtime and self._cron is not None:
            return
        self._cron_mtime = mt
        self._cron, self._cron_aviso = cr.carregar(arq)

    def _arquivo_calendario(self, config):
        import os
        nome = (config or {}).get("calendario_arquivo") or "calendario_corridas.csv"
        if os.path.isabs(nome) or not self.pasta:
            return nome
        return os.path.join(str(self.pasta), nome)

    def _calendario(self, config, agora_mono):
        import os
        if agora_mono - self._cal_t < 20.0:
            return
        self._cal_t = agora_mono
        arq = self._arquivo_calendario(config)
        try:
            mt = os.path.getmtime(arq)
        except OSError:
            self._cal_itens, self._cal_erros, self._cal_mtime, self._cal_arq = [], [], None, arq
            self._cal_aviso = "Crie o arquivo calendario_corridas.csv na pasta de dados do overlay (modelo: calendario_exemplo.csv)."
            return
        if arq == self._cal_arq and mt == self._cal_mtime:
            return
        self._cal_arq, self._cal_mtime = arq, mt
        try:
            with open(arq, "r", encoding="utf-8-sig") as f:
                self._cal_itens, self._cal_erros = ler_calendario(f.read())
        except Exception as ex:
            self._cal_itens, self._cal_erros = [], [str(ex)]
        self._cal_aviso = ("O arquivo do calendario esta vazio ou com erro: " + "; ".join(self._cal_erros[:2])) if not self._cal_itens else ""

    def montar(self, dados, extra, config, agora_mono, agora_relogio=None):
        """Devolve o dicionario 'v18' para os dados. Nunca levanta erro por causa de dado ausente."""
        e = entrada_de_dados(dados, extra, agora_mono)
        for k, ck in (("ultrap_so_outras", "ultrap_so_outras"), ("ultrap_so_mesma_volta", "ultrap_so_mesma_volta")):
            if config and ck in config:
                e[k] = bool(config[ck])
        if config:
            e["ultrap_limite"] = 5.0 if config.get("ultrap_distante") else 3.0
        r = self.coletor.atualizar(e)
        self._calendario(config, agora_mono)
        agora_rel = agora_relogio or _dt.datetime.now()
        r["calendario"] = proximas(self._cal_itens, agora_rel, 4) if self._cal_itens else []
        r["calendario_aviso"] = self._cal_aviso
        r["calendario_fonte"] = "arquivo local" if self._cal_itens else ""
        r["calendario_alerta"] = None
        if config and config.get("cronograma_ativo"):
            try:
                import ov_cronograma as cr
                self._cronograma(config, agora_mono)
                agora_utc = _dt.datetime.now(_dt.timezone.utc)
                itens, aviso, alerta = cr.calendario_do_cronograma(self._cron, self._cron_aviso, config.get("cronograma_filtros"), agora_utc, 4)
                r["calendario"], r["calendario_fonte"], r["calendario_aviso"], r["calendario_alerta"] = itens, "cronograma iRacing", aviso, alerta
            except Exception:
                r["calendario_aviso"] = "Falha ao calcular o cronograma (veja overlay_log.txt)."
        return r


def atras_por_distancia(carros, meu_id, v_eu, comprimento, limite_s=6.0, v_min=20.0):
    """Carros de TRAS (jogos sem lista de relativo, como o LMU): diferenca em segundos = distancia / velocidade de referencia.
    carros: dicts {id, numero, nome, pct (0..1), box, classe_id, classe_nome, cor}. Devolve a lista no formato do 'relativo'."""
    eu = next((c for c in carros if c.get("id") == meu_id), None)
    if eu is None or not _fin(comprimento) or comprimento < 300.0 or eu.get("pct") is None:
        return []
    v_ref = max(v_min, float(v_eu or 0.0))
    out = []
    for c in carros:
        if c.get("id") == meu_id or c.get("pct") is None or c.get("box") or not _fin(c["pct"]):
            continue
        dist = ((eu["pct"] - c["pct"] + 0.5) % 1.0 - 0.5) * comprimento          # positivo = o outro esta ATRAS de mim
        if dist <= 0:
            continue
        gap = dist / v_ref
        if gap > limite_s:
            continue
        out.append({"id": c.get("id"), "numero": str(c.get("numero", "")), "nome": c.get("nome", ""), "gap": gap, "eu": False, "na_box": False, "volta_rel": 0,
                    "mesma_classe": c.get("classe_id") == eu.get("classe_id"), "classe_cor": c.get("cor"), "classe_nome": c.get("classe_nome")})
    out.sort(key=lambda d: d["gap"])
    return out[:8]


def alimentar(servico, telemetria, dados, config, agora, erro=None):
    """Chamado uma vez por ciclo pelo laco principal de cada jogo: poe dados['v18'] (a demonstracao ja traz o seu)."""
    if not isinstance(dados, dict) or dados.get("v18") is not None:
        return
    extra = {}
    try:
        f = getattr(telemetria, "_extra_v18", None)
        extra = (f() if f else {}) or {}
    except Exception:
        if erro:
            erro("v1.8 (leitura extra do jogo)")
    try:
        dados["v18"] = servico.montar(dados, extra, config, agora)
    except Exception:
        dados["v18"] = None
        if erro:
            erro("v1.8 (coletor)")


def aplicar_daltonismo(B, modo):
    """Troca B.QColor por uma subclasse que remapeia as matizes e refaz as constantes COR_* ja criadas. 'padrao' restaura tudo."""
    orig = getattr(B, "_QColor_original", None)
    if orig is None:
        orig = B._QColor_original = B.QColor
        B._CORES_ORIGINAIS = {n: (v.red(), v.green(), v.blue(), v.alpha()) for n, v in vars(B).items()
                              if n.isupper() and type(v) is orig}
    if modo not in ("deuteranopia", "protanopia", "tritanopia"):
        B.QColor = orig
        B._daltonismo = "padrao"
    else:
        def _remap(*a, _modo=modo):
            if len(a) in (3, 4) and all(isinstance(x, int) and not isinstance(x, bool) for x in a):
                r, g, b = remapear_rgb(_modo, a[0], a[1], a[2])
                return (r, g, b) + tuple(a[3:])
            return a

        class QColorDaltonico(orig):
            def __init__(self, *a):
                if len(a) == 1 and isinstance(a[0], orig):        # copia de outro QColor (ja remapeado): o PySide nao copia subclasse direto
                    super().__init__()
                    self.setRgb(a[0].red(), a[0].green(), a[0].blue(), a[0].alpha())
                else:
                    super().__init__(*_remap(*a))

        B.QColor = QColorDaltonico
        B._daltonismo = modo
    for nome, (r, g, b, al) in B._CORES_ORIGINAIS.items():
        setattr(B, nome, B.QColor(r, g, b, al))
    return B._daltonismo


# ---------------------------------------------------------------------------------------------------------------------
# Modo daltonico: remapeia a MATIZ das cores semanticas (verde = bom, vermelho = ruim) para pares que o tipo escolhido separa.
# Cores sem saturacao (branco, cinza, preto) nao mudam. Nao e uma simulacao clinica: e uma troca de paleta.
# ---------------------------------------------------------------------------------------------------------------------
MODOS_DALTONISMO = ("padrao", "deuteranopia", "protanopia", "tritanopia")


def _rgb_hsv(r, g, b):
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        h = 0.0
    elif mx == r:
        h = (60.0 * ((g - b) / d)) % 360.0
    elif mx == g:
        h = 60.0 * ((b - r) / d) + 120.0
    else:
        h = 60.0 * ((r - g) / d) + 240.0
    return h, (0.0 if mx == 0 else d / mx), mx


def _hsv_rgb(h, s, v):
    h = h % 360.0
    c = v * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = v - c
    r, g, b = ((c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x))[int(h // 60) % 6]
    return int(round((r + m) * 255)), int(round((g + m) * 255)), int(round((b + m) * 255))


def remapear_rgb(modo, r, g, b):
    """Devolve (r, g, b) ja na paleta do modo. 'padrao' (ou modo desconhecido) devolve a cor original."""
    if modo not in ("deuteranopia", "protanopia", "tritanopia"):
        return r, g, b
    h, s, v = _rgb_hsv(r, g, b)
    if s < 0.28 or v < 0.18:
        return r, g, b
    if modo in ("deuteranopia", "protanopia"):
        if 75 <= h < 170:                                     # verde (bom) -> azul
            return _hsv_rgb(208.0, min(1.0, s * 0.95), min(1.0, v * 1.05 + 0.04))
        if h >= 338 or h < 22:                                # vermelho (ruim) -> laranja forte
            if modo == "protanopia":                          # o vermelho parece escuro: sobe o brilho
                v = min(1.0, v * 1.12 + 0.12)
            return _hsv_rgb(30.0, min(1.0, s * 0.95 + 0.05), v)
        if 22 <= h < 75:                                      # laranja/amarelo (aviso) -> amarelo claro, separado do laranja do "ruim"
            return _hsv_rgb(56.0, s * 0.80, min(1.0, v * 1.04 + 0.04))
        return r, g, b
    # tritanopia: azul <-> verde e amarelo <-> violeta se confundem; verde e vermelho ja se separam
    if 180 <= h < 262:                                        # azul/ciano -> violeta
        return _hsv_rgb(292.0, s, min(1.0, v * 1.05))
    if 42 <= h < 75:                                          # amarelo -> laranja claro
        return _hsv_rgb(32.0, s, v)
    return r, g, b


# ---------------------------------------------------------------------------------------------------------------------
# Dados de exemplo (modo demo e previa da Central): determinista por tempo
# ---------------------------------------------------------------------------------------------------------------------
_FONTE_CRON = {"config": None, "pasta": None, "dados": None, "aviso": "", "mtime": None, "t": -1e9, "chave": None, "res": None}


def definir_fonte_cronograma(config, pasta):
    """Build al: a previa da Central (e a demo) passam a mostrar o cronograma REAL com os filtros do piloto, em vez de corridas de exemplo."""
    _FONTE_CRON.update(config=config, pasta=pasta, dados=None, aviso="", mtime=None, t=-1e9, chave=None, res=None)


def _calendario_previa():
    """(itens, fonte, aviso, alerta) do cronograma real, ou None se o aviso do cronograma esta desligado / sem fonte registrada."""
    import json as _json
    import os
    import time as _time
    import ov_cronograma as cr
    cfg = _FONTE_CRON["config"]
    if not cfg or not cfg.get("cronograma_ativo") or not _FONTE_CRON["pasta"]:
        return None
    agora_m = _time.monotonic()
    if agora_m - _FONTE_CRON["t"] >= 2.0 or _FONTE_CRON["dados"] is None and not _FONTE_CRON["aviso"]:
        _FONTE_CRON["t"] = agora_m
        arq = os.path.join(str(_FONTE_CRON["pasta"]), "cronograma.json")
        try:
            mt = os.path.getmtime(arq)
        except OSError:
            mt = None
        if mt is None or mt != _FONTE_CRON["mtime"] or _FONTE_CRON["dados"] is None:
            _FONTE_CRON["mtime"] = mt
            _FONTE_CRON["dados"], _FONTE_CRON["aviso"] = cr.carregar(arq)
            _FONTE_CRON["chave"] = None
    agora_utc = _dt.datetime.now(_dt.timezone.utc)
    chave = (_json.dumps(cfg.get("cronograma_filtros"), sort_keys=True, default=str), int(agora_utc.timestamp()), _FONTE_CRON["mtime"])
    if chave != _FONTE_CRON["chave"]:                      # a previa redesenha ~8x por segundo; a conta so muda a cada segundo ou com os filtros
        _FONTE_CRON["res"] = cr.calendario_do_cronograma(_FONTE_CRON["dados"], _FONTE_CRON["aviso"], cfg.get("cronograma_filtros"), agora_utc, 4)
        _FONTE_CRON["chave"] = chave
    itens, aviso, alerta = _FONTE_CRON["res"]
    return itens, "cronograma iRacing", aviso, alerta


def exemplo(t=0.0):
    rpm_max = 8000.0
    c = Coletor()
    # preenche o mapa com um modelo simples de vazao (cresce com RPM e acelerador)
    for ri in range(N_LINHAS_ACEL):
        for ci in range(N_COLS):
            frac_rpm = (ci + 0.5) / N_COLS
            ace = ri / (N_LINHAS_ACEL - 1)
            if ri == 0 and ci < 6:
                continue
            lh = 8 + 150 * ace * (0.35 + 0.65 * frac_rpm) * (0.55 + 0.45 * frac_rpm)
            if ri >= 3 and ci < 2 + (10 - ri) // 3:
                continue
            c._fluxo[ri][ci] = [lh * 0.3, 0.3, 3]
    c._rpm_max = rpm_max
    for g in range(1, 7):
        lin = []
        for ci in range(N_COLS):
            if ci < 7 - g // 2 and g > 1 and ci < g - 1:
                lin.append([0.0, 0.0, 0])
                continue
            lin.append([(60 + 8 * abs(ci - (3 + g * 0.6)) + 6 * (7 - g) + 3 * g) * 0.2, 0.2, 2])
        c._marcha[g] = lin
        c._marcha_t[g] = [3, 5, 9, 12, 14, 8][g - 1]
        c._marcha_rpm_max[g] = rpm_max * (0.86 + 0.02 * (g % 3))
    _tt = sum(x[1] for lin in c._marcha.values() for x in lin)
    _tv = sum(x[0] for lin in c._marcha.values() for x in lin)
    c._marcha_glob = [_tv / 100.0, _tt, _tt]                 # demo: media geral coerente com as celulas (L/100 km)
    for nome, minimo in FAIXAS_ACEL:
        for ci in range(N_COLS):
            peso = {"FLAT": 0.9, "HIGH": 0.35, "MID": 0.18, "LOW": 0.1, "COAST": 0.02}[nome] * (0.2 + (ci / (N_COLS - 1)) ** 1.6)
            if nome == "FLAT" and ci < 3 or nome == "COAST" and ci > 5:
                peso = 0.0
            c._zona[nome][ci] = peso
    c._litros_total = sum(sum(v) for v in c._zona.values())
    scale = 13.2 / c._litros_total if c._litros_total else 1.0
    for nome in c._zona:
        c._zona[nome] = [v * scale for v in c._zona[nome]]
    c._litros_total = 13.2
    c._stint_l, c._stint_voltas = 13.2, 4
    ph = (t * 0.35) % 1.0
    e = {"agora": t, "rpm": 3500 + 3800 * ph, "rpm_max": rpm_max, "acel": 0.35 + 0.65 * ph, "marcha": 2 + int(ph * 4), "inst_lh": 60 + 90 * ph,
         "vel_kmh": 90 + 160 * ph, "consumo": {"ultima_lv": 2.86, "medio_lv": 2.86}, "valido": False,
         "hibrido": {"carga": 0.5 + 0.1 * math.sin(t * 0.3), "deploy": 0.8, "ativo": True}, "restante": 345.0 - (t % 300.0),
         "decorrido": 300.0 + (t % 300.0)}
    c._hib["ult_carga"], c._hib["ult_deploy"] = 0.68, 0.90
    r = c.resumo(e)
    trilha = []                                             # demo: trilha dos ultimos instantes (posicoes anteriores no mapa)
    for k in range(8, 0, -1):
        ph2 = ((t - 0.22 * k) * 0.35) % 1.0
        pt = (linha_acel(0.35 + 0.65 * ph2), coluna_rpm(3500 + 3800 * ph2, rpm_max))
        if trilha and pt[1] < trilha[-1][1] - 3:
            trilha = []                                     # o ciclo da demo recomecou: nao liga o fim ao comeco
        if not trilha or trilha[-1] != pt:
            trilha.append(pt)
    r["vazao"]["trilha"] = trilha
    r["vazao"]["mapa_motor"] = 3
    r["ultrapassagem"] = {"carros": [
        {"numero": "14", "nome": "Istvan Fodor", "gap": 0.4, "fecha": 0.12, "cor": (255, 220, 60), "classe": "LMP2", "mesma_classe": False},
        {"numero": "15", "nome": "Yuki Tsunoda", "gap": 1.4, "fecha": 0.08, "cor": (255, 220, 60), "classe": "LMP2", "mesma_classe": False},
        {"numero": "23", "nome": "Fernando Alonso", "gap": 1.7, "fecha": 0.05, "cor": (110, 220, 235), "classe": "LMP3", "mesma_classe": False},
        {"numero": "28", "nome": "Max Verstappen", "gap": 3.0, "fecha": 0.03, "cor": (235, 120, 200), "classe": "GT4", "mesma_classe": False}]}
    r["calendario"] = exemplo_calendario()
    try:
        real = _calendario_previa()
    except Exception:
        real = None
    if real is not None:
        r["calendario"], r["calendario_fonte"], r["calendario_aviso"], r["calendario_alerta"] = real
    return r
