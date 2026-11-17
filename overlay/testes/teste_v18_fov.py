# -*- coding: utf-8 -*-
"""Calculadora de FOV: matematica (ov_fov), pagina da Central e persistencia das entradas."""
import json, math, os, random, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
import ov_fov as f
falhas, _ok = [], 0
def confere(cond, msg):
    global _ok
    if cond: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)
def perto(a, b, tol=0.05):
    return abs(a - b) <= tol
POL = 2.54
def ent(**k):
    e = {"dist": 70.0, "diag": 27 * POL, "aspecto": "16:9", "curva": None, "triplo": False, "bezel_mm": 0.0}
    e.update(k); return e

# ---- uma tela plana: valores de referencia calculados a mao
r = f.calcular(ent())
w, h = 27 * POL * 16 / math.hypot(16, 9), 27 * POL * 9 / math.hypot(16, 9)
confere(perto(r["largura_tela"], w, 0.01) and perto(r["altura_tela"], h, 0.01), f"tela 27 pol 16:9: {r['largura_tela']:.1f} x {r['altura_tela']:.1f} cm")
confere(perto(r["vfov"], math.degrees(2 * math.atan(h / 2 / 70))) and perto(r["vfov"], 27.0, 0.1), f"FOV vertical 27 pol a 70 cm = {r['vfov']:.1f} graus")
confere(perto(r["hfov"], math.degrees(2 * math.atan(w / 2 / 70))) and perto(r["hfov"], 46.2, 0.1), f"FOV horizontal 27 pol a 70 cm = {r['hfov']:.1f} graus")
confere(r["lateral_angulo"] is None and perto(r["hfov_total"], r["hfov"]), "uma tela: sem angulo lateral; total = horizontal")
confere(perto(r["largura_x"], w + f.MARGEM_QUADRO_CM, 0.01) and perto(r["profundidade_y"], f.ESPESSURA_PAINEL_CM, 0.01), "uma tela: largura e profundidade")
# proporcoes
for chave, (a, b) in f.ASPECTOS.items():
    wd, ht = f.dimensoes_tela(50.0, (a, b))
    confere(perto(math.hypot(wd, ht), 50.0, 1e-6) and perto(wd / ht, a / b, 1e-6), f"proporcao {chave}: diagonal e razao")
confere(f.aspecto_de("custom", (4, 3)) == (4.0, 3.0), "proporcao personalizada")
# monotonia: mais perto = mais FOV; tela maior = mais FOV
confere(f.calcular(ent(dist=60.0))["hfov"] > f.calcular(ent(dist=80.0))["hfov"], "mais perto da tela, maior o FOV")
confere(f.calcular(ent(diag=32 * POL))["vfov"] > f.calcular(ent())["vfov"], "tela maior, maior o FOV")

# ---- tela curva: bordas mais perto => mais FOV horizontal; vertical igual
plana = f.calcular(ent(diag=34 * POL, aspecto="21:9", dist=80.0))
curva = f.calcular(ent(diag=34 * POL, aspecto="21:9", dist=80.0, curva=1000))
confere(curva["hfov"] > plana["hfov"] and perto(curva["vfov"], plana["vfov"], 1e-9), f"curva 1000R: horizontal {curva['hfov']:.1f} > plana {plana['hfov']:.1f}; vertical igual")
confere(f.calcular(ent(diag=34 * POL, aspecto="21:9", dist=80.0, curva=4000))["hfov"] < curva["hfov"], "curva mais suave (4000R) fica entre a plana e a 1000R")
confere(curva["profundidade_y"] > plana["profundidade_y"], "tela curva aumenta a profundidade (flecha)")

# ---- triplo: telas identicas, sem moldura => total = 3 x horizontal, angulo lateral = horizontal
t = f.calcular(ent(triplo=True))
confere(perto(t["hfov_total"], 3 * t["hfov"], 0.01), f"triplo sem moldura: total {t['hfov_total']:.1f} = 3 x {t['hfov']:.1f}")
confere(perto(t["lateral_angulo"], t["hfov"], 0.01), f"triplo sem moldura: angulo lateral = FOV da tela ({t['lateral_angulo']:.1f})")
confere(t["fita_interna"] < t["fita_externa"] and t["largura_x"] > 2.5 * t["largura_tela"] * 0.9, "triplo: medidas de fita coerentes (interna < externa)")
confere(perto(t["largura_x"], t["fita_externa"] + 2 * f.ESPESSURA_PAINEL_CM * math.sin(math.radians(t["lateral_angulo"])) + f.MARGEM_QUADRO_CM, 1e-6), "triplo: largura X = fita externa + fundo das laterais + estrutura")
# moldura positiva aumenta angulo e total; negativa diminui; linear-ish
tm = f.calcular(ent(triplo=True, bezel_mm=15.0)); tn = f.calcular(ent(triplo=True, bezel_mm=-10.0))
confere(tm["hfov_total"] > t["hfov_total"] > tn["hfov_total"] and tm["lateral_angulo"] > t["lateral_angulo"] > tn["lateral_angulo"], "moldura positiva aumenta e negativa reduz angulo e total")
confere(any("sobrep" in a.lower() for a in tn["avisos"]), "moldura negativa avisa sobreposicao")
# angulo da moldura: para 15 mm a ~ 80 cm
dist_borda = math.hypot(w / 2, 70.0)
confere(perto(tm["bezel_angulo"], math.degrees(math.atan2(1.5, dist_borda)), 0.001), "angulo da moldura = atan(moldura / distancia a borda)")
# geometria da planta: a lateral esta a distancia D do olho
phi = math.radians(tm["lateral_angulo"]); D = 70.0
confere(perto(tm["fita_externa"] / 2, D * math.sin(phi) + tm["largura_tela_lateral"] / 2 * math.cos(phi), 1e-6), "planta: borda externa da lateral")
# laterais diferentes
mx = f.calcular(ent(triplo=True, lateral={"diag": 32 * POL, "aspecto": "16:9", "curva": None}))
confere(mx["hfov_lateral"] > mx["hfov"] and mx["hfov_total"] > t["hfov_total"] and mx["avisos"], "laterais maiores: FOV total maior e aviso de altura diferente")
iguais = f.calcular(ent(triplo=True, lateral={"diag": 27 * POL, "aspecto": "16:9", "curva": None}))
confere(perto(iguais["hfov_total"], t["hfov_total"], 1e-9) and not iguais["avisos"], "laterais iguais a central = triplo normal")
# profundidade do triplo cresce com a distancia e com a moldura
longe = f.calcular(ent(triplo=True, dist=90.0))
confere(longe["profundidade_y"] < t["profundidade_y"] and longe["largura_x"] > t["largura_x"] and longe["lateral_angulo"] < t["lateral_angulo"], "triplo: mais longe, laterais mais abertas (angulo e profundidade menores, largura maior)")
confere(tm["profundidade_y"] > t["profundidade_y"] > f.ESPESSURA_PAINEL_CM, "triplo: profundidade maior que uma tela")

# ---- jogos
v, conj = f.para_jogo(t, "vertical"); hh, tot = f.para_jogo(t, "horizontal")
confere(perto(v, t["vfov"], 1e-9) and conj is None and perto(hh, t["hfov"], 1e-9) and perto(tot, t["hfov_total"], 1e-9), "para_jogo: vertical e horizontal (com o conjunto no triplo)")
confere(f.para_jogo(r, "horizontal")[1] is None, "para_jogo: uma tela nao tem conjunto")
lo, hi = f.faixa(100.0)
confere(perto(lo, 90.0, 1e-9) and perto(hi, 110.0, 1e-9), "faixa de ajuste fino = +-10 %")
confere(dict(f.JOGOS)["iRacing"] == "horizontal" and dict(f.JOGOS)["Le Mans Ultimate"] == "vertical", "iRacing usa horizontal e LMU usa vertical (referencia da calculadora)")

# ---- entradas invalidas: erro claro, nunca excecao inesperada
for nome, e in (("distancia zero", ent(dist=0.0)), ("distancia negativa", ent(dist=-5.0)), ("distancia NaN", ent(dist=float("nan"))), ("diagonal zero", ent(diag=0.0)),
                ("diagonal texto", ent(diag="abc")), ("curvatura forte demais", ent(curva=50, diag=49 * POL, aspecto="32:9")),
                ("proximo demais da curva", ent(curva=1000, dist=0.5)), ("sobreposicao exagerada", ent(triplo=True, bezel_mm=-600.0)), ("moldura NaN", ent(triplo=True, bezel_mm=float("nan")))):
    try:
        f.calcular(e); confere(False, f"invalido ({nome}): deveria recusar")
    except ValueError as ex:
        confere(bool(str(ex)), f"invalido ({nome}): {ex}")
try:
    f.aspecto_de("custom", None); confere(False, "proporcao custom sem valores")
except ValueError:
    confere(True, "proporcao personalizada sem valores e recusada")


# ---- build ad: regressoes da auditoria (geometrias impossiveis, curvatura, proporcao, modelo do triplo)
def recusa(e, trecho=""):
    try:
        f.calcular(e); return False
    except ValueError as ex:
        return trecho in str(ex)
    except Exception:
        return False
confere(recusa(ent(dist=15.0, diag=49 * POL, aspecto="32:9", triplo=True), "360"), "auditoria: triplo 49\" 32:9 a 15 cm (antes 455,7 graus e largura negativa) e recusado")
confere(recusa(ent(dist=15.0, diag=49 * POL, aspecto="32:9", triplo=True, bezel_mm=150.0), "360"), "auditoria: o mesmo com moldura de 15 cm tambem")
confere(recusa(ent(dist=15.0, diag=49 * POL, aspecto=(32.0, 9.0), triplo=True)), "auditoria: proporcao como tupla no triplo impossivel")
for nome, cv in (("negativa", -1000), ("zero", 0), ("NaN", float("nan")), ("infinita", float("inf")), ("texto", "abc")):
    confere(recusa(ent(curva=cv)), f"auditoria: curvatura {nome} e recusada")
    confere(recusa(ent(triplo=True, lateral={"diag": 27 * POL, "aspecto": "16:9", "curva": cv})), f"auditoria: curvatura da lateral {nome} e recusada")
for nome, a_ in (("16:0", (16, 0)), ("0:9", (0, 9)), ("negativa", (-16, 9)), ("NaN", (float("nan"), 9)), ("infinita", (16, float("inf"))), ("texto", ("a", "b")), ("curta", (16,))):
    confere(recusa(ent(aspecto=a_)), f"auditoria: proporcao personalizada {nome} e recusada (tupla direta)")
    try:
        f.aspecto_de("custom", a_); confere(False, f"aspecto_de custom {nome}")
    except ValueError:
        confere(True, f"aspecto_de custom {nome} recusada")
confere(recusa(ent(aspecto="99:1")), "proporcao desconhecida e recusada")
confere(f.calcular(ent(aspecto=(21.0, 9.0)))["hfov"] > f.calcular(ent(aspecto="16:9"))["hfov"], "proporcao valida em tupla continua funcionando")
confere(f.calcular(ent(curva=None))["curva"] is None, "curva None = tela plana")
# modelo do triplo: consistencia entre FOV, angulo lateral, largura X, profundidade Y e fita (planas, curvas e laterais diferentes)
def coerente(r, e):
    D = e["dist"]; phi = math.radians(r["lateral_angulo"]); tot = math.radians(r["hfov_total"])
    ok = 0 < r["hfov_total"] < 360 and r["largura_x"] > 0 and r["profundidade_y"] > 0
    ok = ok and r["fita_interna"] <= r["fita_externa"] + 1e-9 and r["largura_x"] >= r["fita_externa"] + f.MARGEM_QUADRO_CM - 1e-9
    ok = ok and perto(r["lateral_angulo"], r["hfov"] / 2 + r["bezel_angulo"] + r["hfov_lateral"] / 2, 1e-9)
    ok = ok and perto(r["hfov_total"], r["hfov"] + 2 * (r["bezel_angulo"] + r["hfov_lateral"]), 1e-9)
    return ok and all(math.isfinite(v) for v in r.values() if isinstance(v, float))
for nome, e in (("planas", ent(triplo=True, bezel_mm=15.0)), ("curvas 1800R", ent(triplo=True, curva=1800, bezel_mm=15.0)),
                ("curvas 1000R 27\"", ent(triplo=True, curva=1000, bezel_mm=10.0)),
                ("laterais maiores e curvas diferentes", ent(triplo=True, curva=1800, bezel_mm=10.0, lateral={"diag": 32 * POL, "aspecto": "16:9", "curva": 1500})),
                ("laterais menores planas", ent(triplo=True, diag=32 * POL, lateral={"diag": 24 * POL, "aspecto": "16:9", "curva": None}))):
    r = f.calcular(e)
    confere(coerente(r, e), f"triplo coerente ({nome}): total {r['hfov_total']:.1f}, lateral {r['lateral_angulo']:.1f}, X {r['largura_x']:.1f}, Y {r['profundidade_y']:.1f}")
# a borda externa vista do olho tem de ficar na metade do FOV total (mesmo desenho para FOV, angulo e fita)
def meio_total_pela_planta(e):
    r = f.calcular(e); D = e["dist"]; phi = math.radians(r["lateral_angulo"])
    sl = f._tela(D, r["largura_tela_lateral"], r["altura_tela_lateral"], (e.get("lateral") or e).get("curva"))
    t_, n_ = (math.cos(phi), -math.sin(phi)), (-math.sin(phi), -math.cos(phi))
    ex = D * math.sin(phi) + sl["meia_corda"] * t_[0] + sl["flecha"] * n_[0]
    ey = D * math.cos(phi) + sl["meia_corda"] * t_[1] + sl["flecha"] * n_[1]
    return math.degrees(math.atan2(ex, ey)), r["hfov_total"] / 2, 2 * ex, r["fita_externa"]
for e in (ent(triplo=True, curva=1800, bezel_mm=15.0), ent(triplo=True, curva=1000, bezel_mm=0.0), ent(triplo=True, bezel_mm=-8.0, dist=90.0)):
    a_, b_, fx, ft_ = meio_total_pela_planta(e)
    confere(perto(a_, b_, 1e-6) and perto(fx, ft_, 1e-6), f"borda externa na planta = metade do FOV total ({a_:.2f}), fita = 2x posicao ({ft_:.1f} cm)")
# curva aumenta a flecha: na tela curva a borda fica mais perto, entao a lateral pede menos espaco que a plana de mesma largura
rp, rc = f.calcular(ent(triplo=True)), f.calcular(ent(triplo=True, curva=1000))
confere(rc["hfov"] > rp["hfov"] and abs(rc["largura_x"] - rp["largura_x"]) > 0.5, "triplo curvo difere do plano (mesma geometria nas bordas)")
# varredura: so ha resultado valido ou ValueError; nunca excecao inesperada nem numero nao finito
import itertools
rngf = random.Random(7)
estranhos = [None, 0, -1, -1000, float("nan"), float("inf"), -float("inf"), "x", "", [], 1e-9, 1e9]
inesp = 0
for _ in range(1500):
    e = ent(dist=rngf.choice(estranhos + [rngf.uniform(5, 200)]), diag=rngf.choice(estranhos + [rngf.uniform(20, 60) * POL]),
            aspecto=rngf.choice(["16:9", "21:9", "32:9", (16, 9), (rngf.choice(estranhos), 9), "xx", None]), curva=rngf.choice([None] + estranhos[:6] + [1000, 1500, 1800]),
            triplo=rngf.random() < 0.7, bezel_mm=rngf.choice([0.0, 15.0, -20.0, 500.0] + estranhos[:7]))
    try:
        r = f.calcular(e)
        if not all(math.isfinite(v) for v in r.values() if isinstance(v, float)) or r["largura_x"] <= 0 or r["profundidade_y"] <= 0 or (r["triplo"] and not 0 < r["hfov_total"] < 360):
            inesp += 1
    except ValueError:
        pass
    except Exception:
        inesp += 1
confere(inesp == 0, f"varredura de 1500 entradas estranhas: nenhum resultado invalido nem excecao inesperada ({inesp})")

# ---- propriedades com entradas aleatorias
rng = random.Random(7); bons = 0
for _ in range(300):
    e = ent(dist=rng.uniform(40, 150), diag=rng.uniform(20, 55) * POL, aspecto=rng.choice(("16:9", "21:9", "32:9")), triplo=rng.random() < 0.5, bezel_mm=rng.uniform(-5, 40))
    if rng.random() < 0.4: e["curva"] = rng.choice(f.CURVATURAS_MM)
    try:
        q = f.calcular(e)
    except ValueError:
        continue
    ok = 0 < q["vfov"] < 180 and 0 < q["hfov"] < 180 and q["largura_x"] > 0 and q["profundidade_y"] > 0
    if q["triplo"]: ok = ok and q["hfov_total"] >= q["hfov"] and q["lateral_angulo"] > 0 and q["fita_interna"] <= q["fita_externa"] + 1e-9
    bons += ok
confere(bons >= 250, f"propriedades em 300 entradas aleatorias: {bons} validas e coerentes")

# ---- Central: pagina, estado, persistencia
import overlay_iracing as o
import ov_central as c
from PySide6.QtWidgets import QApplication, QDoubleSpinBox
S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); o.salvar_config = lambda x: None
cfg = o.carregar_config(); cfg["travado"] = True
confere(cfg["fov_calc"] == {}, "config: 'fov_calc' nasce vazio")
cl = o.v18_janelas.construir(o); demo = o.Telemetria(demo=True); demo.modo_previa = True
todas = []
for ch, K in cl.items():
    c2 = dict(cfg); c2[K.CHAVE_ATIVO] = False; todas.append(K(c2))
erros, salvos = [], []
cfgc = dict(cfg)
cen = c.Central(todas, {}, cfgc, {"salvar": lambda: salvos.append(1), "registrar_erro": erros.append}, demo.ler, lambda j: type(j)(dict(cfg, travado=True)), "Teste", "1.8.0")
confere("fov" in cen._nav, "Central: item 'Calculadora de FOV' no menu lateral")
cen.show(); cen.ir_para("fov"); app.processEvents()
confere(cen.paginas.currentIndex() == 5 and cen._nav["fov"].isChecked(), "Central: abre a pagina da calculadora")
confere(cen.fov_resultado is not None and perto(cen.fov_resultado["vfov"], 27.0, 0.1), f"Central: resultado inicial (27 pol a 70 cm): {cen.fov_resultado['vfov']:.1f}")
# trocar de unidade nao muda o resultado fisico
antes = cen.fov_resultado["hfov"]
cen._fov_mudou("dist_un", "pol"); cen._fov_widgets["dist"].setValue(70.0 / 2.54); app.processEvents()
confere(cen.fov_resultado is not None and perto(cen.fov_resultado["hfov"], antes, 0.2), "Central: 70 cm = 27,6 pol (mesmo resultado, dentro do arredondamento de 0,1 pol)")
cen._fov_mudou("dist_un", "cm"); cen._fov_widgets["dist"].setValue(70.0)
# exemplo triplo
cen._fov_ex.setCurrentIndex(5); app.processEvents()
confere(cen._fov_est["triplo"] is True and cen.fov_resultado["triplo"] and perto(cen.fov_resultado["hfov_total"], 124.9, 0.2), f"Central: exemplo triplo ({cen.fov_resultado['hfov_total']:.1f})")
confere(cen._fov_widgets["bezel"].isEnabled() and cen._fov_widgets["bezel"].value() == 15.0, "Central: moldura habilitada e preenchida no triplo")
confere(not cen._fov_widgets["lat_diag"].isEnabled(), "Central: laterais diferentes desligado desabilita os campos")
cen._fov_mudou("lat_on", True); app.processEvents()
confere(cen._fov_widgets["lat_diag"].isEnabled(), "Central: laterais diferentes habilita os campos")
# tela unica desabilita moldura
cen._fov_mudou("triplo", False); app.processEvents()
confere(not cen._fov_widgets["bezel"].isEnabled() and not cen.fov_resultado["triplo"], "Central: uma tela desabilita a moldura")
# curva liga o raio
cen._fov_mudou("curva_on", True); app.processEvents()
confere(cen._fov_widgets["curva_r"].isEnabled() and cen.fov_resultado["curva"] == 1800, "Central: tela curva usa o raio escolhido")
# persistencia
confere(salvos and cen.config["fov_calc"]["curva_on"] is True and cen.config["fov_calc"]["curva_r"] == 1800, "Central: entradas salvas no config")
json.dumps(cen.config["fov_calc"])
cen2 = c.Central(todas, {}, dict(cfgc), {"salvar": lambda: None, "registrar_erro": erros.append}, demo.ler, lambda j: type(j)(dict(cfg, travado=True)), "Teste", "1.8.0")
confere(cen2._fov_est["curva_on"] is True and cen2._fov_est["dist"] == 80.0, "Central: reabrir restaura as entradas")
# entrada invalida na tela: mensagem, sem erro registrado
cen._fov_mudou("curva_on", False); cen._fov_mudou("dist", 0.0); app.processEvents()
confere(cen.fov_resultado is None and not erros, "Central: distancia invalida mostra aviso e nao registra erro")
cen._fov_mudou("dist", 75.0); app.processEvents()
confere(cen.fov_resultado is not None, "Central: volta a calcular com dado valido")
# build ad: triplo impossivel (49" 32:9 a 15 cm) mostra aviso na tela, sem resultado e sem erro registrado
for k_, v_ in (("diag", 49.0), ("aspecto", "32:9"), ("curva_on", False), ("triplo", True), ("dist", 15.0)): cen._fov_mudou(k_, v_)
app.processEvents()
confere(cen.fov_resultado is None and not erros, "Central: triplo impossivel (FOV total >= 360) mostra aviso e nao calcula")
cen._fov_mudou("dist", 90.0); cen._fov_mudou("triplo", False); app.processEvents()
confere(cen.fov_resultado is not None, "Central: volta a calcular depois do triplo impossivel")
# config corrompida nao quebra a pagina
cen3 = c.Central(todas, {}, dict(cfgc, fov_calc={"dist": "texto", "triplo": 5, "diag": None, "lixo": 1}), {"salvar": lambda: None, "registrar_erro": erros.append}, demo.ler,
                 lambda j: type(j)(dict(cfg, travado=True)), "Teste", "1.8.0")
confere(cen3._fov_est["dist"] == 70.0 and cen3._fov_est["triplo"] is False and cen3.fov_resultado is not None, "Central: config de FOV corrompida cai nos padroes")
arq = S / "persist.json"; o.ARQ_CONFIG = arq
arq.write_text(json.dumps({"fov_calc": {"dist": 82.0, "triplo": True}}), encoding="utf-8")
confere(o.carregar_config()["fov_calc"] == {"dist": 82.0, "triplo": True}, "persistencia: 'fov_calc' sobrevive ao reiniciar")
arq.write_text(json.dumps({"fov_calc": "quebrado"}), encoding="utf-8")
confere(o.carregar_config()["fov_calc"] == {}, "persistencia: 'fov_calc' corrompido volta a vazio")
confere(not erros, f"nenhum erro registrado ({erros[:3]})")
print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
