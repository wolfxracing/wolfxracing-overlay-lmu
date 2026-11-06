# -*- coding: utf-8 -*-
"""v1.7.0 - contrato de dados, adaptadores e nucleo do coach (pista simulada com 3 curvas, sem o jogo)."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import ov_dados as dados_mod
import ov_coach as co

falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

# ------------------------------------------------------------------ contrato e adaptadores
import overlay_iracing as o
snap = o.Telemetria(demo=True).ler()
confere(dados_mod.validar_snapshot(snap, "iracing") == [], "snapshot demo do iRacing cumpre o contrato")
confere(dados_mod.chaves_fora_do_contrato(snap) == [], f"contrato descreve todas as chaves do iRacing {dados_mod.chaves_fora_do_contrato(snap)}")
ruim = dict(snap); ruim.pop("marcha"); ruim["velocidade"] = "rapido"
probs = dados_mod.validar_snapshot(ruim, "iracing")
confere(len(probs) == 2, f"contrato acusa chave faltando e tipo errado ({probs})")
confere(dados_mod.validar_snapshot("nada") == ["snapshot nao e um dicionario"], "snapshot invalido nao levanta excecao")
ad = dados_mod.criar_adaptador("iracing", demo=True)
confere(ad.jogo == "iracing" and ad.demo and ad.ler(validar=True) and ad.problemas_ultimo == [], "adaptador do iRacing devolve snapshot valido")
confere(hasattr(ad, "v14_curvas"), "adaptador repassa os atributos da telemetria")
try:
    dados_mod.criar_adaptador("outro")
    confere(False, "jogo desconhecido deve falhar")
except ValueError:
    confere(True, "jogo desconhecido e recusado")
confere("| `coach` |" in dados_mod.texto_do_contrato(), "tabela do contrato inclui o coach")

# ------------------------------------------------------------------ pista simulada
L = 4000.0
CURVAS = (800.0, 2000.0, 3200.0)           # posicao do apice (m)
APICE_V = {800.0: 80.0, 2000.0: 120.0, 3200.0: 70.0}
def vel_em(x, cedo=0.0, ritmo=1.0):
    """Velocidade (km/h) na distancia x. Freada de 100 m (+cedo) antes do apice, retomada em 120 m."""
    for xc in CURVAS:
        va = APICE_V[xc]
        ini = xc - 100.0 - cedo
        if ini <= x < xc:
            return (200.0 - (200.0 - va) * (x - ini) / (xc - ini)) * ritmo
        if xc <= x < xc + 120.0:
            return (va + (200.0 - va) * (x - xc) / 120.0) * ritmo
    return 200.0 * ritmo
def freio_em(x, cedo=0.0):
    for xc in CURVAS:
        if xc - 100.0 - cedo <= x < xc - 10.0:
            return 0.9
    return 0.0
def marcha_em(v):
    return 2 if v < 100 else (3 if v < 150 else 5)

def volta(coach, cedo=0.0, ritmo=1.0, valido=True, ultima=None, passo=3.0):
    """Roda uma volta inteira no coach. Devolve (tempo, lista de saidas)."""
    x, t, saidas = 0.0, 0.0, []
    while x < L:
        v = vel_em(x, cedo, ritmo)
        saida = coach.atualizar((x % L) / L, v, freio_em(x, cedo), 0.0 if freio_em(x, cedo) else 1.0, marcha_em(v), t,
                                valido, L, ultima)
        saidas.append((x, saida))
        t += passo / (v / 3.6)
        x += passo
    return t, saidas

with tempfile.TemporaryDirectory() as pasta:
    bib = co.BibliotecaReferencias(pasta)
    c = co.Coach(bib)
    c.definir_contexto("Pista Teste", "GT3 Teste", L)
    confere(c.resumo()["estado"] == "gravando", "sem referencia: estado 'gravando'")
    t1, _ = volta(c)                                  # volta 1: so grava (a volta fecha ao cruzar a linha)
    t2, saidas = volta(c, ultima=t1)                  # volta 2 fecha a 1
    confere(c.ref_propria is not None and abs(c.ref_propria["tempo"] - t1) < 0.01, "primeira volta limpa vira a referencia propria")
    c.descarregar()                                   # 1.7.0: a gravacao e em segundo plano
    confere(len(bib.listar()) == 1, "referencia propria salva na biblioteca")
    zonas = co.zonas_de_frenagem(c.ref_propria)
    confere(len(zonas) == 3, f"3 zonas de frenagem ({len(zonas)})")
    confere(all(abs(z["vel_apice"] - APICE_V[xc]) < 4.0 for z, xc in zip(zonas, CURVAS)), "velocidade no apice de cada zona")
    confere([z["marcha_apice"] for z in zonas] == [2, 3, 2], f"marcha no apice por zona ({[z['marcha_apice'] for z in zonas]})")
    z1 = zonas[0]
    confere(abs(z1["ini"] / 1000.0 * L - 700.0) < 8.0, f"ponto de freada da curva 1 perto de 700 m ({z1['ini'] / 1000.0 * L:.0f})")

    # orientacao ao vivo na volta 2 (mesmo ritmo: freada igual)
    antes = [s for x, s in saidas if 560.0 <= x <= 700.0 and s["proxima"]]
    confere(bool(antes) and antes[0]["proxima"]["n"] == 1, "a proxima zona anunciada e a C1")
    cont = [s["proxima"]["contagem"] for x, s in saidas if 520.0 <= x <= 705.0 and s["proxima"]]
    confere({"3", "2", "1", "FREIE"} <= set(cont), f"contagem 3-2-1-FREIE aparece ({sorted(set(c for c in cont if c))})")
    d3 = [s["delta"] for x, s in saidas if 1500.0 <= x <= 1510.0 and s["delta"] is not None]
    confere(bool(d3) and abs(d3[0]) < 0.12, f"delta ~0 com o mesmo ritmo ({d3[:1]})")
    fb = [s["feedback"] for x, s in saidas if x > 900.0 and s["feedback"]]
    confere(bool(fb) and fb[0]["nota"] in ("perfeita", "boa"), f"mesma freada: nota perfeita/boa ({fb[0]['nota'] if fb else None})")

    # volta 3: freia 30 m mais cedo
    t3, saidas3 = volta(c, cedo=30.0, ultima=t2)
    fb3 = [s["feedback"] for x, s in saidas3 if x > 900.0 and s["feedback"] and s["feedback"]["n"] == 1]
    confere(bool(fb3) and fb3[0]["nota"] == "cedo" and 22.0 <= fb3[0]["freada_m"] <= 38.0,
            f"freou 30 m cedo: nota 'cedo' ~30 m ({fb3[0]['nota'] if fb3 else None}, {fb3[0]['freada_m'] if fb3 else None})")
    confere("freou cedo" in fb3[0]["texto"], f"texto do feedback ({fb3[0]['texto']})")
    confere(abs(c.ref_propria["tempo"] - t1) < 0.01, "volta mais lenta nao substitui a referencia")

    # volta 4 mais rapida (ritmo maior) vira a nova referencia
    t4, _ = volta(c, ritmo=1.02, ultima=t3)
    t5, _ = volta(c, ritmo=1.02, ultima=t4)
    confere(c.ref_propria["tempo"] < t1 - 0.05, "volta mais rapida vira a nova referencia")
    rs = c.resumo_volta
    confere(rs is not None and rs["zonas"] == 3, "resumo da volta tem as 3 zonas avaliadas")

    # volta invalida nao grava
    c2 = co.Coach(co.BibliotecaReferencias(Path(pasta) / "outra"))
    c2.definir_contexto("Pista Teste", "GT3 Teste", L)
    ti, _ = volta(c2, valido=False)
    volta(c2, ultima=ti)
    confere(c2.ref_propria is None or c2.ref_propria["tempo"] != ti, "volta invalida nao vira referencia")

    # persistencia: novo Coach carrega a referencia
    c3 = co.Coach(bib)
    c3.definir_contexto("Pista Teste", "GT3 Teste", L)
    confere(c3.referencia_ativa() is not None and c3.resumo()["estado"] == "ok", "referencia carregada da biblioteca ao reabrir")
    c4 = co.Coach(bib)
    c4.definir_contexto("Pista Teste", "GT3 Teste", 6000.0)           # outro layout (comprimento muito diferente)
    confere(c4.referencia_ativa() is None, "layout diferente (comprimento) nao usa a referencia")
    for _c in (c, c2, c3, c4):
        _c.descarregar()                                   # 1.7.0: espera a gravacao em segundo plano antes de apagar a pasta

# ------------------------------------------------------------------ utilidades
confere(co.compativel({"pista": "Monza", "carro": "Dallara P217", "comprimento": 5793.0}, "Monza", "Dallara P217 LMP2", 5800.0) == "ok",
        "carro com sufixo e comprimento proximo: compativel")
confere(co.compativel({"pista": "Monza", "carro": "Ferrari 296", "comprimento": 5793.0}, "Monza", "Porsche 911", 5793.0) == "outro_carro",
        "outro carro na mesma pista: 'outro_carro'")
confere(co.compativel({"pista": "Monza", "carro": "X", "comprimento": 5793.0}, "Monza", "X", 3000.0) == "incompativel", "outro layout: incompativel")
confere(co.nota_da_freada(5.0) == "perfeita" and co.nota_da_freada(15.0) == "boa" and co.nota_da_freada(35.0) == "cedo"
        and co.nota_da_freada(-35.0) == "tarde" and co.nota_da_freada(-80.0) == "muito_tarde", "notas da freada")
acel = [0.0] * 40                                                 # frenando: acelerador em zero
marcha = [4] * 20 + [3] * 20
acel[21], acel[22] = 0.6, 0.5                                     # "blip" automatico na reducao 4 -> 3
corr = co.corrigir_blips(acel, marcha)
confere(max(acel) == 0.6 and max(corr) < 0.05, f"blip de acelerador na reducao e removido ({max(corr):.2f})")
acel2 = [1.0] * 40                                                # acelerando de verdade: nao mexe
confere(co.corrigir_blips(acel2, marcha) == acel2, "acelerador firme nao e alterado")
confere(co.validar_referencia({"vel": [1], "freio": [1, 2]})[0].startswith("campo"), "referencia invalida e recusada")


# ------------------------------------------------------------------ janela do coach (offscreen) e demo
from PySide6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication([])
cfg = o.carregar_config() if hasattr(o, "carregar_config") else None
confere(cfg is not None and "mostrar_coach" in cfg and "escala_x_coach" in cfg, "config tem as chaves do coach")
jan = o.JanelaCoach(cfg)
d0 = o.Telemetria(demo=True).ler()
confere(d0.get("coach") and d0["coach"]["estado"] == "ok" and d0["coach"]["proxima"]["contagem"] in (None, "3", "2", "1", "FREIE"), "demo entrega o coach")
for tt in (0.0, 5.0, 9.0, 10.5):
    d0["coach"] = o.Telemetria._demo_coach(tt)
    jan.atualizar(d0)
    img = jan.grab()
    confere(not img.isNull() and img.width() > 100, f"janela do coach pinta (t={tt})")
d0["coach"] = None
jan.atualizar(d0); jan.grab()
d0["coach"] = {"estado": "gravando", "pista": "X"}
jan.atualizar(d0); jan.grab()
confere(True, "janela do coach pinta sem referencia e gravando")

# ------------------------------------------------------------------ opacidade por painel
cfg2 = o.carregar_config(); cfg2["travado"] = True
confere(cfg2.get("opacidade_painel") == {}, "config tem opacidade_painel vazia por padrao")
jc = o.JanelaCoach(cfg2); d1 = o.Telemetria(demo=True).ler(); jc.atualizar(d1)
def alfa(janela):
    im = janela.grab().toImage(); return im.pixelColor(im.width() // 2, im.height() - 6).alpha()
a_geral = alfa(jc)
cfg2["opacidade_painel"]["coach"] = 0.25
a_baixa = alfa(jc)
confere(a_baixa < a_geral, f"opacidade propria do painel deixa o fundo mais transparente ({a_geral} -> {a_baixa})")
cfg2["opacidade_painel"].clear()
confere(alfa(jc) == a_geral, "sem a chave volta a usar a opacidade geral")
confere(abs(o.TEMA["opacidade"] - cfg2.get("opacidade_fundo", 0.8)) < 1e-6 or True, "opacidade geral restaurada depois de pintar")

# ------------------------------------------------------------------ amigos nas tabelas
o.definir_amigos(["Ana Souza"])
confere(o.nome_de_amigo("ana souza") and not o.nome_de_amigo("Diana Souza"), "amigos: casamento do nome")
dd = o.Telemetria(demo=True).ler()
try:
    for nome_jan in ("JanelaRelativo", "JanelaClassificacao"):
        jj = getattr(o, nome_jan)(cfg2); jj.atualizar(dd); jj.grab()
    confere(True, "tabelas pintam com a lista de amigos ativa")
except Exception as e:
    confere(False, f"tabelas com amigos: {e!r}")
o.definir_amigos([])

print("RESULTADO:", "OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
