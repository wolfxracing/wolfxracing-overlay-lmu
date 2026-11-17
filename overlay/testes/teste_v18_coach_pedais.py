# -*- coding: utf-8 -*-
"""Build ap: Pedais do Coach. % de freio-alvo, trail braking (freio que desce aos poucos), soltar e acelerar da referencia,
feedback com a sua % de freio, janela nova posicionavel/centralizavel, registro (config, menu, Central)."""
import os, sys, tempfile
from pathlib import Path
RAIZ = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import ov_coach as co
import overlay_iracing as ov

falhas, _ok = [], 0
def confere(c, msg):
    global _ok
    if c: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

N, COMP = 1000, 2300.0
def referencia():
    vel, freio, acel, marcha, t = [], [], [], [], []
    for i in range(N):
        f, a, v = 0.0, 1.0, 200.0
        if 200 <= i <= 212:                       # freada seca: sobe a 95% e solta de vez (sem trail)
            f = 0.95 if i <= 206 else max(0.0, 0.95 - (i - 206) * 0.2)
            v = 200 - (i - 200) * 6
        if 213 <= i <= 230:
            a = 0.3 + (i - 213) * 0.04              # volta a acelerar aos poucos
            v = 125 + (i - 213) * 3
        if 500 <= i <= 545:                       # trail braking: pico 90% em 505 e desce devagar ate 12% em 545
            f = 0.90 * (i - 500) / 5 if i < 505 else 0.90 - (0.90 - 0.12) * (i - 505) / 40.0
            v = 210 - (i - 500) * 2.2
        if 546 <= i <= 560:
            a = 0.2 if i < 552 else 0.55 + (i - 552) * 0.05    # tirou o pe e depois acelera
            v = 112 + (i - 546) * 2
        vel.append(v); freio.append(round(f, 3)); acel.append(round(a, 3)); marcha.append(3); t.append(i * 0.085)
    return co.nova_referencia("Pista Teste", "Carro Teste", "propria", COMP, 85.0, vel, freio, acel, marcha, t)

ref = referencia()
zs = co.zonas_de_frenagem(ref)
confere(len(zs) == 2, f"duas zonas de frenagem na referencia ({len(zs)})")
p1 = co.plano_freio(ref, dict(zs[0], tipo="freio"))
p2 = co.plano_freio(ref, dict(zs[1], tipo="freio"))
confere(p1["pico_pct"] == 95 and not p1["trail"], f"zona 1: pico 95% sem trail ({p1})")
confere(p2["pico_pct"] == 90 and p2["trail"] and p2["trail_m"] > 60, f"zona 2: pico 90% COM trail longo ({p2})")
confere(p2["freio_apice_pct"] > 0, f"trail: ainda ha freio no apice ({p2['freio_apice_pct']}%)")
confere(p1["acel_saida_pct"] is not None and 0 <= p1["acel_saida_pct"] <= 100, f"plano traz o acelerador de saida ({p1['acel_saida_pct']}%)")
confere(co.plano_freio(ref, {"tipo": "tirada", "ini": 0}) is None, "tirada nao tem plano de freio")

def fase(b, v=None):
    return co.fase_pedais(ref, b, v)
confere(fase(203)["fase"] == "frear" and fase(203)["alvo_freio_pct"] >= 90, "no inicio da freada: FREIE com % alvo")
confere(fase(520)["fase"] == "trail", f"depois do pico com trail: TRAIL ({fase(520)['fase']})")
confere(fase(520)["alvo_freio_pct"] is not None and fase(520)["alvo_freio_pct"] < 90, "trail: alvo cai (nao e o pico)")
confere(fase(209)["fase"] == "soltar_freio", f"freada seca solta de vez: SOLTE O FREIO ({fase(209)['fase']})")
confere(fase(550)["fase"] == "soltar", f"acelerador baixo sem freio: SOLTE O ACELERADOR ({fase(550)['fase']})")
confere(fase(222)["fase"] == "acelerar" and fase(222)["alvo_acel_pct"] is not None, f"retomada: ACELERE ({fase(222)['fase']})")
confere(fase(100)["fase"] == "fundo", "reta: PE FUNDO")
confere(fase(100)["freio_ref_pct"] == 0 and fase(100)["acel_ref_pct"] == 100, "marca da referencia (freio 0%, acel 100%)")
# antecipacao pela velocidade: a 250 km/h olha ~0,35 s (~24 m = ~10 bins) a frente
confere(fase(192, 250.0)["fase"] == "frear" and fase(192, None)["fase"] == "fundo", "a velocidade antecipa a instrucao")
ref_sem_acel = dict(ref); ref_sem_acel["acel"] = None
confere(co.fase_pedais(ref_sem_acel, 100)["fase"] == "fundo", "referencia antiga sem acelerador nao quebra")

# integracao: Coach.atualizar devolve 'pedais' e o plano da proxima zona; o resumo antigo continua igual
with tempfile.TemporaryDirectory() as tmp:
    c = co.Coach(co.BibliotecaReferencias(Path(tmp) / "r"))
    c.definir_contexto("Pista Teste", "Carro Teste", COMP)
    c.definir_propria(ref, salvar=False)
    r = c.atualizar(0.19, 200.0, 0.0, 1.0, 5, 16.0, True, COMP, 0.0)
    confere(r.get("estado") == "ok", "coach com referencia: ok")
    confere((r.get("pedais") or {}).get("fase") in ("fundo", "frear"), f"resumo traz 'pedais' ({r.get('pedais')})")
    confere(r["pedais"].get("freio_pct") == 0 and r["pedais"].get("acel_pct") == 100, "sua % ao vivo vai junto (freio 0, acel 100)")
    pr = r.get("proxima") or {}
    confere(pr.get("plano", {}).get("pico_pct") == 95 and pr["plano"]["trail"] is False, f"proxima freada traz plano ({pr.get('plano')})")
    r = c.atualizar(0.47, 200.0, 0.0, 1.0, 5, 40.0, True, COMP, 0.0)
    confere((r.get("proxima") or {}).get("plano", {}).get("trail") is True, "a zona 2 anuncia trail braking")
    r2 = c.atualizar(0.52, 150.0, 0.70, 0.0, 4, 44.0, True, COMP, 0.0)
    confere(r2["pedais"]["freio_pct"] == 70 and r2["pedais"]["fase"] == "trail", "no meio do trail: sua freada 70% e fase TRAIL")
    confere(c.resumo()["pedais"] == r2["pedais"], "resumo() repete o ultimo estado dos pedais")

# feedback com a sua % de freio e trail
with tempfile.TemporaryDirectory() as tmp:
    c = co.Coach(co.BibliotecaReferencias(Path(tmp) / "r"))
    c.definir_contexto("Pista Teste", "Carro Teste", COMP)
    c.definir_propria(ref, salvar=False)
    for b in range(480, 600):
        f = 0.0
        if 495 <= b <= 510:
            f = 0.75 if b < 505 else 0.75 - (b - 505) * 0.1     # voce freia 75% e solta rapido (quase sem trail)
        c.rec.registrar(b, 150.0, f, 0.0 if f else 1.0, 3, b * 0.085, True)
    fb = c._avaliar(co.todas_as_zonas(ref)[1], COMP)
    confere(fb is not None and fb.get("freio_pico_pct") == 75, f"feedback: seu pico de freio 75% ({fb and fb.get('freio_pico_pct')})")
    confere("ref 90%" in (fb or {}).get("freio_txt", ""), f"feedback compara com a referencia ({fb and fb.get('freio_txt')})")
    confere("trail" in (fb or {}).get("freio_txt", ""), "feedback fala do trail da referencia")
    confere("texto" in fb and fb["texto"].startswith("C"), "o texto original do feedback continua igual")

# janela nova: registrada, posicionavel, centralizavel e desenha sem erro
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
import ov_v18_janelas as jan18
classes = jan18.construir(ov)
confere("coach_pedais" in classes, "janela 'coach_pedais' registrada nas janelas v1.8")
cfg = dict(ov.carregar_config()) if hasattr(ov, "carregar_config") else None
confere(cfg is not None and "x_coach_pedais" in cfg and cfg["mostrar_coach_pedais"] is False and "escala_x_coach_pedais" in cfg,
        "config padrao: posicao, escala e desligada por padrao")
cfg["travado"] = False
j = classes["coach_pedais"](cfg)
confere(j.CHAVE_ATIVO == "mostrar_coach_pedais" and "Pedais do Coach" in j.ROTULO_MENU, "rotulo de menu")
dados = ov.Telemetria._vazio(); dados["conectado"] = True
dados["coach"] = {"estado": "ok", "pedais": dict(r2["pedais"]), "proxima": r.get("proxima")}
j.atualizar(dados)
img = j.grab()
confere(not img.isNull() and img.width() > 100, "janela pinta com dados reais")
dados["coach"] = None
cfg["travado"] = True
j.atualizar(dados); confere(not j.grab().isNull(), "travada e sem coach: mensagem de espera, sem erro")
cfg["travado"] = False
j.atualizar(dados); confere(not j.grab().isNull(), "destravada e sem coach: pinta o exemplo")
j.move(5, 7)
confere(j.centralizar(True, False) and j.config["x_coach_pedais"] == j.x() and j.y() == 7, "centralizar horizontal grava x e mantem y")
confere(j.centralizar(True, True) and j.config["y_coach_pedais"] == j.y(), "centralizar na tela inteira")
for el in ("fase", "barras", "plano"):
    cfg["elementos_coach_pedais"] = {el: False}
    j.recarregar_layout() if hasattr(j, "recarregar_layout") else None
    j.atualizar(dados); confere(not j.grab().isNull(), f"elemento '{el}' desligado nao quebra")

# Central e menus
import ov_central
confere("coach_pedais" in ov_central.PAINEIS, "Central lista 'Pedais do Coach'")
for nome in ("overlay_iracing.py",):
    fonte = (RAIZ / nome).read_text(encoding="utf-8")
    confere("Centralizar na tela (horizontal)" in fonte, f"menu da bandeja tem Centralizar ({nome})")
lmu = RAIZ / "overlay_lmu.py"
if lmu.exists():
    confere("Centralizar na tela (horizontal)" in lmu.read_text(encoding="utf-8"), "menu da bandeja LMU tem Centralizar")

print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
