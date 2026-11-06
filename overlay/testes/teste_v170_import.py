# -*- coding: utf-8 -*-
"""v1.7.0 - importador de CSV de volta de referencia (formatos variados, erros claros) e coach com referencia importada."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import ov_coach as co
import ov_referencias as rf

falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

L = 4000.0
CURVAS = (800.0, 2000.0, 3200.0)
APICE_V = {800.0: 80.0, 2000.0: 120.0, 3200.0: 70.0}
def vel_em(x):
    for xc in CURVAS:
        va = APICE_V[xc]; ini = xc - 100.0
        if ini <= x < xc: return 200.0 - (200.0 - va) * (x - ini) / (xc - ini)
        if xc <= x < xc + 120.0: return va + (200.0 - va) * (x - xc) / 120.0
    return 200.0
def freio_em(x): return 0.9 if any(xc - 100.0 <= x < xc - 10.0 for xc in CURVAS) else 0.0
def marcha_em(v): return 2 if v < 100 else (3 if v < 150 else 5)

def amostras(passo=4.0, blip=False):
    x, t, out, gprev = 0.0, 0.0, [], None
    while x <= L:
        v = vel_em(x); g = marcha_em(v); fr = freio_em(x)
        ac = 0.0 if fr else 1.0
        if blip and gprev is not None and g < gprev: ac = 0.6          # blip automatico na reducao
        gprev = g
        out.append((x / L, x, v, fr, ac, g, t))
        t += passo / (v / 3.6); x += passo
    return out, t

def csv_iracing(am, sep=",", dec=".", pct100=False, unidade="ms", freio100=False, meta=False, sem=()):
    cols = [("LapDistPct", lambda a: a[0] * (100 if pct100 else 1)), ("LapDist", lambda a: a[1]),
            ({"ms": "Speed", "kmh": "Speed (km/h)", "mph": "Speed (mph)"}[unidade],
             lambda a: a[2] / {"ms": 3.6, "kmh": 1.0, "mph": 1.609344}[unidade]),
            ("Brake", lambda a: a[3] * (100 if freio100 else 1)), ("Throttle", lambda a: a[4]), ("Gear", lambda a: a[5]),
            ("LapCurrentLapTime", lambda a: a[6])]
    cols = [c for c in cols if c[0] not in sem]
    linhas = []
    if meta:
        linhas += ["Garage 61 export", "Track: Teste, Car: GT3", ""]
    linhas.append(sep.join(c[0] for c in cols))
    for a in am:
        linhas.append(sep.join(f"{c[1](a):.4f}".replace(".", dec) if not isinstance(c[1](a), int) else str(c[1](a)) for c in cols))
    return "\n".join(linhas)

am, T = amostras()
ref, av = rf.importar_csv(csv_iracing(am), "Pista Teste", "GT3 Teste", L)
confere(not co.validar_referencia(ref), "CSV estilo iRacing (m/s, 0-1) vira referencia valida")
confere(abs(ref["tempo"] - T) < 0.5, f"tempo de volta ~ {T:.1f} s ({ref['tempo']:.1f})")
z = co.zonas_de_frenagem(ref)
confere(len(z) == 3, f"3 zonas de frenagem ({len(z)})")
confere(all(abs(a["vel_apice"] - APICE_V[xc]) < 5.0 for a, xc in zip(z, CURVAS)), "velocidades de apice preservadas")
confere([a["marcha_apice"] for a in z] == [2, 3, 2], f"marchas de apice {[a['marcha_apice'] for a in z]}")
confere(abs(z[0]["ini"] / 1000.0 * L - 700.0) < 10.0, "ponto de freada da C1 perto de 700 m")

for nome, kw in (("ponto-e-virgula + virgula decimal", dict(sep=";", dec=",")), ("posicao em 0-100", dict(pct100=True)),
                 ("velocidade em km/h", dict(unidade="kmh")), ("velocidade em mph", dict(unidade="mph")),
                 ("freio em 0-100", dict(freio100=True)), ("linhas de metadados no inicio", dict(meta=True))):
    r2, _ = rf.importar_csv(csv_iracing(am, **kw), "P", "C", L)
    confere(len(co.zonas_de_frenagem(r2)) == 3 and abs(r2["tempo"] - T) < 0.5, nome)

r3, av3 = rf.importar_csv(csv_iracing(am, sem=("LapDistPct",)), "P", "C", L)
confere(len(co.zonas_de_frenagem(r3)) == 3, "sem LapDistPct: usa a distancia em metros + comprimento")
r4, av4 = rf.importar_csv(csv_iracing(am, sem=("LapCurrentLapTime",)), "P", "C", L)
confere(abs(r4["tempo"] - T) < 1.0 and len(co.zonas_de_frenagem(r4)) == 3, f"sem coluna de tempo: integrado da velocidade ({r4['tempo']:.1f})")
r5, av5 = rf.importar_csv(csv_iracing(am, sem=("Throttle",)), "P", "C", L)
confere(any("acelerador" in a for a in av5) and len(co.zonas_de_frenagem(r5)) == 3, "sem acelerador: aviso, mas importa")
confere(rf.importar_csv(csv_iracing(am), "P", "C", L, tempo_volta=T + 1.0)[0]["tempo"] == T + 1.0, "tempo oficial da volta pode ser informado")

amb, _ = amostras(blip=True)
rb, _ = rf.importar_csv(csv_iracing(amb), "P", "C", L)
pico = max(rb["acel"][int(790 / L * 1000):int(840 / L * 1000)])
confere(pico > 0.9, "acelerador firme na saida da curva preservado apos a correcao do blip")
confere(max(rb["acel"][int(700 / L * 1000):int(770 / L * 1000)]) < 0.05, "blip da reducao 5->3 removido na frenagem")

# erros claros
def erra(texto, trecho, msg):
    try:
        rf.importar_csv(texto, "P", "C", L); confere(False, msg + " (devia falhar)")
    except rf.ErroImportacao as e:
        confere(trecho in str(e), f"{msg}: '{e}'")
erra("a,b\n1,2\n" * 30, "colunas de velocidade", "arquivo sem colunas conhecidas")
erra("LapDistPct,Speed\n0,1\n" * 5, "muito curto", "arquivo muito curto")
erra(csv_iracing(am, sem=("Brake",)), "freio", "sem freio")
erra(csv_iracing(am, sem=("Gear",)), "marcha", "sem marcha")
meia = csv_iracing(am[: len(am) // 2])
erra(meia, "volta inteira", "volta pela metade")
zerado = csv_iracing([(a[0], a[1], a[2], 0.0, a[4], a[5], a[6]) for a in am])
erra(zerado, "frenagem", "freio zerado")

# coach usando a referencia importada
with tempfile.TemporaryDirectory() as pasta:
    bib = co.BibliotecaReferencias(pasta)
    c = co.Coach(bib); c.definir_contexto("Pista Teste", "GT3 Teste", L)
    comp = c.definir_importada(ref)
    confere(comp == "ok" and c.fonte_ativa() == "importada" and len(bib.listar()) == 1, "coach aceita e salva a referencia importada")
    x, t, cont = 0.0, 0.0, set()
    while x < L:
        v = vel_em(x)
        s = c.atualizar(x / L, v, freio_em(x), 0.0 if freio_em(x) else 1.0, marcha_em(v), t, True, L, None)
        if s["proxima"] and s["proxima"]["contagem"]: cont.add(s["proxima"]["contagem"])
        t += 3.0 / (v / 3.6); x += 3.0
    confere({"3", "2", "1", "FREIE"} <= cont, f"contagem 3-2-1-FREIE guiada pela referencia importada ({sorted(cont)})")
    confere(s["fonte"] == "importada" and s["tem_importada"], "resumo indica a fonte importada")
    # modo automatico: a mais rapida entre a propria e a importada
    c.ref_propria = dict(ref, origem="propria", tempo=ref["tempo"] - 1.0)
    confere(c.referencia_ativa()["origem"] == "propria", "automatico: propria mais rapida vence a importada")
    c.ref_propria = dict(ref, origem="propria", tempo=ref["tempo"] + 1.0)
    confere(c.referencia_ativa()["origem"] == "importada", "automatico: importada mais rapida vence a propria")
    c.ref_importada = dict(ref, origem="importada", carro="Outro Carro Qualquer", tempo=ref["tempo"] - 5.0)
    confere(c.referencia_ativa()["origem"] == "propria", "automatico: importada de OUTRO carro nao vence a propria")
    c.ref_propria = None
    confere(c.referencia_ativa()["origem"] == "importada", "automatico: so a importada existe, usa a importada")
    c.ref_importada = ref
    c.modo = "propria"
    confere(c.referencia_ativa() is None and c.resumo()["estado"] == "gravando", "modo 'propria' ignora a importada")
    # outra pista: referencia incompativel e recusada
    c2 = co.Coach(bib); c2.definir_contexto("Pista Teste", "GT3 Teste", 6500.0)
    confere(c2.definir_importada(ref) == "incompativel", "referencia de outro layout e recusada")
    # pasta de entrada
    ent = Path(pasta) / "entrada"; ent.mkdir()
    (ent / "volta.csv").write_text(csv_iracing(am), encoding="utf-8")
    (ent / "ruim.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    confere([p.name for p in rf.listar_csv(ent)].count("volta.csv") == 1, "lista os CSV da pasta de entrada")
    r6, _ = rf.importar_arquivo(ent / "volta.csv", "P", "C", L)
    confere(r6["fonte"] == "volta.csv", "importar_arquivo guarda o nome do arquivo como origem")
    (ent / "latin.csv").write_bytes(csv_iracing(am).replace("Brake", "Brake").encode("latin-1"))
    confere(rf.importar_arquivo(ent / "latin.csv", "P", "C", L)[0] is not None, "arquivo em latin-1")


# --- CSV real do Garage 61 (amostra de 1 volta, sem coluna de tempo; o tempo vem do nome do arquivo) ---
import pathlib as _pl
_g61 = next((_pl.Path(__file__).parent / "dados").glob("Garage 61 - *.csv"))
confere(rf.tempo_do_nome(_g61.name) == 82.572, "tempo da volta lido do nome do arquivo do Garage 61")
confere(rf.tempo_do_nome("minha_volta.csv") is None, "sem tempo no nome devolve None")
_r, _av = rf.importar_arquivo(_g61, "Summit Point Raceway", "Global Mazda MX-5 Cup", comprimento=3200)
confere(abs(_r["tempo"] - 82.572) < 1e-6, "importa CSV do Garage 61 com o tempo do nome")
confere(70 < min(_r["vel"]) and 195 < max(_r["vel"]) < 215, "velocidade em m/s convertida para km/h no CSV do Garage 61")
confere(len(_r["_zonas"]) >= 4, "zonas de frenagem achadas no CSV do Garage 61")

print("RESULTADO:", "OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
