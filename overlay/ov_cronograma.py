# -*- coding: utf-8 -*-
"""Cronograma de corridas do iRacing (PDF "Season Schedule" -> cronograma.json) com filtros e aviso. Logica pura (sem Qt, sem rede).

Premissas (declaradas ao piloto):
  - As cadencias do PDF estao em UTC/GMT. "A cada 2 horas" assume horas PARES de UTC (ou impares quando o texto diz "odd").
  - A semana de competicao do iRacing comeca na terca-feira 00:00 UTC e dura 7 dias (data 'Week N (AAAA-MM-DD)' do PDF).
  - Series com horarios que o PDF nao informa (ex.: '5 Timeslots Per Week') ou fora dos padroes simples ficam SEM aviso automatico.
O fuso do piloto e, por padrao, o do Windows (inclusive horario de verao); opcionalmente um numero fixo de horas (padrao -3).
"""
import datetime as _dt
import functools
import json
import os
import re
import unicodedata

SEMANA = _dt.timedelta(days=7)
CLASSES = ("R", "D", "C", "B", "A")


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(s.lower().split())


def _cadencia_valida(c):
    """Cadencia saneada. Qualquer coisa fora do formato vira 'desconhecida' (a serie fica sem aviso, mas nada quebra)."""
    if not isinstance(c, dict):
        return {"tipo": "desconhecida"}
    tipo = c.get("tipo")
    try:
        if tipo == "passo":
            passo = int(c.get("passo_min"))
            if passo not in (30, 60, 120):
                raise ValueError("passo")
            mins = [int(m) for m in (c.get("minutos") or [0])]
            if not mins or any(not 0 <= m <= 59 for m in mins):
                raise ValueError("minutos")
            par = c.get("paridade")
            par = None if par is None else int(par)
            if par not in (None, 0, 1):
                raise ValueError("paridade")
            out = dict(c)
            out.update(passo_min=passo, minutos=mins, paridade=par)
            return out
        if tipo == "semanal":
            hs = []
            for it in c.get("horarios") or []:
                dia, h = int(it[0]), int(it[1])
                mn = int(it[2]) if len(it) > 2 else 0
                if 0 <= dia <= 6 and 0 <= h <= 23 and 0 <= mn <= 59:
                    hs.append([dia, h, mn])
            if not hs:
                raise ValueError("horarios")
            out = dict(c)
            out["horarios"] = hs
            return out
        if tipo == "desconhecida":
            return {"tipo": "desconhecida", "texto": str(c.get("texto", ""))}
    except (TypeError, ValueError, IndexError, KeyError):
        pass
    return {"tipo": "desconhecida", "texto": str(c.get("texto", "")) if isinstance(c.get("texto", ""), (str, int, float)) else ""}


def _duracao_valida(d):
    if not isinstance(d, dict):
        return None
    try:
        if d.get("min"):
            return {"min": float(d["min"])}
        if d.get("voltas"):
            return {"voltas": int(d["voltas"])}
    except (TypeError, ValueError):
        pass
    return None


def sanitizar(d):
    """Valida a estrutura do cronograma: serie com nome, semanas com data valida, cadencia no formato. Descarta o que estiver
    malformado. Retorna (dados_limpos, quantas_series_descartadas)."""
    series, descartadas = [], 0
    brutas = d.get("series") if isinstance(d, dict) else None
    for s in (brutas if isinstance(brutas, list) else []):
        if not isinstance(s, dict) or not str(s.get("serie") or "").strip():
            descartadas += 1
            continue
        semanas = []
        for w in (s.get("semanas") if isinstance(s.get("semanas"), list) else []):
            if not isinstance(w, dict):
                continue
            try:
                _inicio_semana(str(w.get("inicio")))
            except Exception:
                continue
            semanas.append(dict(w, inicio=str(w["inicio"]), pista=str(w.get("pista") or ""), duracao=_duracao_valida(w.get("duracao"))))
        if not semanas:
            descartadas += 1
            continue
        carros = s.get("carros")
        series.append(dict(s, serie=str(s["serie"]), carros=[str(c) for c in carros] if isinstance(carros, list) else [],
                           classe=str(s.get("classe") or ""), classe_serie=str(s.get("classe_serie") or ""),
                           cadencia=_cadencia_valida(s.get("cadencia")), semanas=semanas))
    limpo = dict(d) if isinstance(d, dict) else {}
    limpo["series"] = series
    return limpo, descartadas


def carregar(caminho):
    """Le o cronograma.json e valida a estrutura. Retorna (dados, aviso). dados None se faltar/estiver invalido."""
    try:
        with open(caminho, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
        if not isinstance(d, dict) or not isinstance(d.get("series"), list) or not d["series"]:
            return None, "O arquivo cronograma.json esta vazio ou invalido. Gere de novo com atualizar_cronograma.bat."
        limpo, descartadas = sanitizar(d)
        if not limpo["series"]:
            return None, "O cronograma.json nao tem nenhuma serie valida (estrutura incorreta). Importe o PDF de novo."
        limpo["_descartadas"] = descartadas
        return limpo, ""
    except FileNotFoundError:
        return None, "Cronograma nao encontrado: coloque o cronograma.json na pasta do overlay (ou use atualizar_cronograma.bat com o PDF)."
    except Exception as ex:
        return None, f"Falha ao ler o cronograma.json: {ex}"


def letra_classe(serie):
    """Classe da serie no iRacing (secao 'B Class Series' do PDF). Sem ela, usa a licenca exigida do cabecalho ('Class C 4.0 -> ...')."""
    cs = str(serie.get("classe_serie") or "")
    if cs in CLASSES:
        return cs
    m = re.match(r"\s*([RDCBA])\b", str(serie.get("classe") or ""))
    return m.group(1) if m else ""


@functools.lru_cache(maxsize=4096)
def _inicio_semana(texto):
    return _dt.datetime.strptime(texto, "%Y-%m-%d").replace(tzinfo=_dt.timezone.utc)


def horarios_da_semana(cad, ini):
    """Todos os inicios de corrida (datetime UTC) da semana que comeca em 'ini' (UTC 00:00). [] se a cadencia nao e conhecida."""
    out = []
    if not isinstance(cad, dict):
        return out
    tipo = cad.get("tipo")
    if tipo == "passo":
        try:
            passo, mins = int(cad.get("passo_min") or 0), [int(m) for m in (cad.get("minutos") or [0])]
        except (TypeError, ValueError):
            return out
        par = cad.get("paridade")
        if passo == 120 and par is None:
            par = 0                                           # premissa documentada: horas pares de UTC (nunca 168/semana)
        for dia in range(7):
            base = ini + _dt.timedelta(days=dia)
            for h in range(24):
                if passo == 120 and par is not None and h % 2 != par:
                    continue
                if passo in (60, 120):
                    for m in mins:
                        out.append(base + _dt.timedelta(hours=h, minutes=int(m)))
                elif passo == 30:
                    out.append(base + _dt.timedelta(hours=h, minutes=int(mins[0])))
                    out.append(base + _dt.timedelta(hours=h, minutes=int(mins[0]) + 30))
    elif tipo == "semanal":
        horarios = set()
        for it in cad.get("horarios") or []:
            try:                                              # [dia, hora] (formato antigo) ou [dia, hora, minuto]
                horarios.add((int(it[0]), int(it[1]), int(it[2]) if len(it) > 2 else 0))
            except (TypeError, ValueError, IndexError):
                continue
        for dia in range(7):
            base = ini + _dt.timedelta(days=dia)
            for d, h, mn in horarios:
                if base.weekday() == d:
                    out.append(base + _dt.timedelta(hours=h, minutes=mn))
    return sorted(out)


def _duracao_min(semana):
    d = semana.get("duracao") or {}
    try:
        return float(d["min"]) if d.get("min") else (None)
    except (TypeError, ValueError):
        return None


def _duracao_txt(semana):
    d = semana.get("duracao") or {}
    if d.get("voltas"):
        return f"{int(d['voltas'])} voltas"
    if d.get("min"):
        return f"{int(d['min'])} min"
    return ""


def ocorrencias(dados, de_utc, ate_utc, pre=None):
    """Todas as corridas das series conhecidas com inicio em [de_utc, ate_utc]. Cada item traz a serie e a semana.
    'pre(serie, semana)' (opcional) descarta cedo o que os filtros ja recusam, para nao gerar horarios a toa."""
    out = []
    for s in dados.get("series", []):
        if not isinstance(s, dict) or not isinstance(s.get("semanas"), list):
            continue
        cad = s.get("cadencia")
        for w in s["semanas"]:
            try:
                ini = _inicio_semana(w["inicio"])
            except Exception:
                continue
            if ini > ate_utc or ini + SEMANA < de_utc - _dt.timedelta(hours=1):
                continue
            if pre is not None and not pre(s, w):
                continue
            for t in horarios_da_semana(cad, ini):
                if de_utc <= t <= ate_utc:
                    out.append({"serie": s, "semana": w, "t": t})
    out.sort(key=lambda x: x["t"])
    return out


def _hm(texto, padrao):
    try:
        h, m = str(texto).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return padrao


def filtros_validos(f):
    f = f if isinstance(f, dict) else {}
    lst = lambda k: [str(x) for x in f.get(k, []) if str(x).strip()] if isinstance(f.get(k), (list, tuple)) else []
    try:
        ant = max(1, min(240, int(f.get("antecedencia_min", 30))))
    except Exception:
        ant = 30
    try:
        fuso = max(-12.0, min(14.0, float(f.get("fuso_h", -3))))
    except Exception:
        fuso = -3.0
    return {"series": lst("series"), "pistas": lst("pistas"), "carros": lst("carros"),
            "classes": [c for c in lst("classes") if c in CLASSES],
            "janela": bool(f.get("janela", False)), "ini": str(f.get("ini", "18:00")), "fim": str(f.get("fim", "23:59")),
            "antecedencia_min": ant, "fuso_h": fuso, "fuso_auto": bool(f.get("fuso_auto", True))}


def tem_filtro(f):
    return bool(f["series"] or f["pistas"] or f["carros"] or f["classes"] or f["janela"])


def passa_estatico(s, w, f):
    """Filtros que dependem so da serie e da semana (serie, classe, pista, carro). Texto sem acento e sem maiusculas."""
    if f["series"] and s.get("serie") not in f["series"]:
        return False
    if f["classes"] and letra_classe(s) not in f["classes"]:
        return False
    if f["pistas"] and not any(_norm(p) in _norm(w.get("pista")) for p in f["pistas"]):
        return False
    if f["carros"] and not any(_norm(c) in _norm(" ".join(s.get("carros") or [])) for c in f["carros"]):
        return False
    return True


def deslocamento(t_utc, f):
    """Diferenca entre o horario local e o UTC NAQUELA data. Padrao (fuso_auto): o fuso do Windows, inclusive horario de verao;
    com fuso_auto desligado vale o numero fixo de horas escolhido pelo piloto."""
    if f.get("fuso_auto", True):
        try:
            d = t_utc.astimezone().utcoffset()
            if d is not None:
                return d
        except (OverflowError, OSError, ValueError):
            pass
    return _dt.timedelta(hours=f["fuso_h"])


def fuso_txt(f, agora_utc):
    """'UTC-03:00' do fuso em uso agora (para mostrar ao piloto)."""
    seg = int(deslocamento(agora_utc, f).total_seconds())
    sinal = "-" if seg < 0 else "+"
    seg = abs(seg)
    return "UTC%s%02d:%02d" % (sinal, seg // 3600, (seg % 3600) // 60)


def passa_janela(t_utc, f):
    """Filtro de horario (local do piloto). A janela pode virar a meia-noite (ex.: 22:00-02:00)."""
    if not f["janela"]:
        return True
    local = t_utc + deslocamento(t_utc, f)
    m, a, b = local.hour * 60 + local.minute, _hm(f["ini"], 0), _hm(f["fim"], 1439)
    return (a <= m <= b) if a <= b else (m >= a or m <= b)


def passa(oc, f):
    """Todos os filtros ativos precisam passar; dentro de cada lista basta um (OU)."""
    return passa_estatico(oc["serie"], oc["semana"], f) and passa_janela(oc["t"], f)


def proximas(dados, filtros, agora_utc, n=4, horizonte_h=72):
    """Proximas corridas que passam nos filtros, no formato do painel Calendario (inicio ja no fuso do piloto, sem tzinfo)."""
    f = filtros_validos(filtros)
    if not dados or not isinstance(dados, dict) or not isinstance(dados.get("series"), list) or not tem_filtro(f):
        return []
    de = agora_utc - _dt.timedelta(minutes=20)
    out = []
    for oc in ocorrencias(dados, de, agora_utc + _dt.timedelta(hours=horizonte_h), pre=lambda se, we: passa_estatico(se, we, f)):
        if not passa(oc, f):
            continue
        s, w, t = oc["serie"], oc["semana"], oc["t"]
        ate = (t - agora_utc).total_seconds()
        dur = _duracao_min(w) or 25.0
        if ate < -dur * 60:
            continue
        out.append({"nome": s.get("serie", ""), "classe": letra_classe(s), "inicio": (t + deslocamento(t, f)).replace(tzinfo=None),
                    "dur": dur, "ate_inicio_s": ate, "reg_s": None, "em_andamento": ate < 0,
                    "pista": w.get("pista", ""), "carro": ", ".join((s.get("carros") or [])[:2]), "duracao": _duracao_txt(w),
                    "alerta": (-300 < ate <= f["antecedencia_min"] * 60), "semana": w.get("semana")})
    return out[:max(1, n)]


def sem_horario(dados):
    """Series sem horario automatico (para avisar o piloto)."""
    return [str(s.get("serie", "?")) for s in dados.get("series", []) if isinstance(s, dict) and (s.get("cadencia") if isinstance(s.get("cadencia"), dict) else {}).get("tipo") not in ("passo", "semanal")]


def listar_series(dados):
    return sorted({str(s["serie"]) for s in dados.get("series", []) if isinstance(s, dict) and s.get("serie")}, key=_norm)


def aviso_vazio(dados, filtros):
    f = filtros_validos(filtros)
    if not dados:
        return ""
    if not tem_filtro(f):
        return "Defina os filtros no menu da bandeja: Cronograma de corridas."
    return "Nenhuma corrida dos seus filtros nas proximas 72 h."


# ---------------------------------------------------------------------------------------------------------------------
# Build al: resultado para o painel, texto da previa, dica de filtro vazio e importacao de um novo PDF
# ---------------------------------------------------------------------------------------------------------------------
DIAS_PT = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def calendario_do_cronograma(dados, aviso, filtros, agora_utc, n=4):
    """Resultado para o painel Calendario: (itens, aviso, alerta). Usado pelo painel real e pela previa da Central (mesma conta)."""
    if dados is None:
        return [], aviso, None
    itens = proximas(dados, filtros, agora_utc, n)
    if itens:
        return itens, "", next((i for i in itens if i.get("alerta")), None)
    return [], aviso_vazio(dados, filtros), None


def contagem_txt(seg):
    seg = int(seg)
    if seg < 0:
        return "em andamento"
    h, r = divmod(seg, 3600)
    m = r // 60
    if h >= 24:
        return f"em {h // 24} d {h % 24} h"
    return f"em {h} h {m:02d} min" if h else f"em {m} min"


def linha_previa(it):
    """Uma corrida da previa: 'ter 17/11 12:45  Serie | Pista | 20 min  (em 1 h 05 min)' (horario local do piloto)."""
    ini = it["inicio"]
    partes = [str(it.get("nome", "")), str(it.get("pista", "")), str(it.get("duracao", ""))]
    return f"{DIAS_PT[ini.weekday()]} {ini:%d/%m %H:%M}   " + " | ".join(p for p in partes if p) + f"   ({contagem_txt(it['ate_inicio_s'])})"


ROTULO_FILTRO = {"series": "Séries", "pistas": "Pista", "carros": "Carro", "classes": "Classe", "janela": "Janela de horário"}


def dica_vazio(dados, filtros, agora_utc, horizonte_h=72):
    """Quando os filtros nao acham nada: qual deles mais restringe (quantas corridas haveria sem ele). '' se nenhum ajuda."""
    f = filtros_validos(filtros)
    melhor = (0, "")
    for chave in ("series", "pistas", "carros", "classes", "janela"):
        if not f[chave]:
            continue
        g = dict(f)
        g[chave] = False if chave == "janela" else []
        if not tem_filtro(g):
            continue
        n = len(proximas(dados, g, agora_utc, 500, horizonte_h))
        if n > melhor[0]:
            melhor = (n, ROTULO_FILTRO[chave])
    return f"O filtro '{melhor[1]}' é o que mais restringe: sem ele haveria {melhor[0]} corridas nas próximas {horizonte_h} h." if melhor[0] else ""


def leitor_pdf_disponivel():
    """True se o computador consegue ler PDF (utilitario pdftotext ou o pacote pypdf)."""
    import importlib.util
    import shutil
    return bool(shutil.which("pdftotext") or importlib.util.find_spec("pypdf"))


def instalar_pypdf(timeout=240):
    """Instala o pypdf (so leitura de PDF) com o pip do Python do overlay. Retorna (ok, mensagem). Nao vale para o .exe empacotado."""
    import importlib
    import subprocess
    import sys
    if getattr(sys, "frozen", False):
        return False, "Esta versao empacotada (.exe) nao instala componentes. Converta o PDF em .txt (pdftotext -layout) ou use o atualizar_cronograma.bat."
    try:
        kw = {"creationflags": 0x08000000} if sys.platform.startswith("win") else {}
        p = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pypdf"], capture_output=True, text=True, timeout=timeout, **kw)
        importlib.invalidate_caches()
        return (p.returncode == 0), ("" if p.returncode == 0 else ((p.stderr or p.stdout or "").strip()[-300:] or "falha do pip"))
    except Exception as ex:
        return False, str(ex)


def importar_arquivo(origem, pasta, agora_utc=None):
    """Converte o PDF 'Season Schedule' do iRacing (ou o .txt extraido dele) em cronograma.json dentro de 'pasta'.
    Retorna {'ok', 'msg', 'dados', 'precisa_pypdf'}. Troca o arquivo atual SO se o novo for valido; o anterior fica em cronograma_anterior.json."""
    import shutil
    res = {"ok": False, "msg": "", "dados": None, "precisa_pypdf": False}
    origem = str(origem or "")
    if not os.path.isfile(origem):
        res["msg"] = "Arquivo não encontrado."
        return res
    if not origem.lower().endswith((".pdf", ".txt")):
        res["msg"] = "Escolha o PDF 'Season Schedule' do iRacing (ou o .txt extraído dele)."
        return res
    try:
        import importar_cronograma as imp
    except Exception as ex:
        res["msg"] = f"O módulo de importação não está na pasta do overlay: {ex}"
        return res
    try:
        texto = imp.texto_do_pdf(origem)
    except ImportError:
        res["precisa_pypdf"], res["msg"] = True, "Falta o componente para ler PDF (pypdf)."
        return res
    except Exception as ex:
        res["msg"] = f"Não consegui ler o arquivo: {ex}"
        return res
    if "Week 1 (" not in texto:
        res["msg"] = "Este arquivo não parece o Season Schedule do iRacing (não achei as linhas 'Week 1 (...)')."
        return res
    try:
        novo = imp.converter_texto(texto, os.path.basename(origem))
    except Exception as ex:
        res["msg"] = f"Falha ao interpretar o cronograma: {ex}"
        return res
    series = novo.get("series") or []
    semanas = sum(len(s.get("semanas", [])) for s in series)
    if not series or not semanas:
        res["msg"] = "Não encontrei nenhuma série com semanas neste arquivo. O cronograma atual foi mantido."
        return res
    agora_p1 = agora_utc or _dt.datetime.now(_dt.timezone.utc)
    ini_t = agora_p1.replace(hour=0, minute=0, second=0, microsecond=0)
    if not any(horarios_da_semana(_cadencia_valida(s.get("cadencia")), ini_t) for s in series):
        res["msg"] = (f"O arquivo tem {len(series)} séries, mas nenhuma com horário que o overlay consiga calcular (cadência desconhecida em todas). "
                      "O cronograma atual foi mantido. Confira se é o PDF Season Schedule completo da temporada.")
        return res
    destino = os.path.join(str(pasta), "cronograma.json")
    tmp = destino + ".novo"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(novo, f, ensure_ascii=False, indent=1)
        conferido, motivo = carregar(tmp)
        if conferido is None:
            raise ValueError(motivo)
        antes = None
        if os.path.isfile(destino):
            antes, _ = carregar(destino)
            shutil.copy2(destino, os.path.join(str(pasta), "cronograma_anterior.json"))
        os.replace(tmp, destino)
    except Exception as ex:
        try:
            os.remove(tmp)
        except OSError:
            pass
        res["msg"] = f"Não consegui gravar o cronograma.json ({ex}). O cronograma atual foi mantido."
        return res
    inicios = sorted(w["inicio"] for s in series for w in s.get("semanas", []) if w.get("inicio"))
    sem_h = len(sem_horario(novo))
    msg = f"Importado: {len(series)} séries, {semanas} semanas"
    if inicios:
        msg += f" ({inicios[0]} a {inicios[-1]})"
    msg += f". {sem_h} série(s) sem horário automático."
    if antes is not None:
        msg += f" O cronograma anterior ficou em cronograma_anterior.json."
    agora = agora_utc or _dt.datetime.now(_dt.timezone.utc)
    try:
        if inicios and _inicio_semana(inicios[-1]) + SEMANA < agora:
            msg += " Atenção: este cronograma já terminou; importe o da temporada atual."
    except Exception:
        pass
    res.update(ok=True, msg=msg, dados=conferido)
    return res
