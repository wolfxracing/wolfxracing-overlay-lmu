# -*- coding: utf-8 -*-
"""1.7.0 - 'Melhor por curva' (dica ao vivo) e resumo pos-sessao. Pista sintetica; nao precisa do jogo."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ov_coach as co
import ov_melhorcurva as mc

falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

L = 4000.0
APICES = [1100.0, 2500.0, 3400.0]
def perfil(curvas, passo=2.0):
    """curvas: [(x_freada, vel_apice)]. Devolve amostras (x, vel, freio, acel, tempo) a cada 2 m."""
    out, t = [], 0.0
    x = 0.5
    while x < L:
        v = 200.0
        fr, ac = 0.0, 1.0
        for k, (x0, va) in enumerate(curvas):
            xa = APICES[k]                                   # apice fixo: freando mais tarde, a desaceleracao e mais forte
            if x0 <= x < xa:
                v = 200.0 - (200.0 - va) * (x - x0) / (xa - x0); fr, ac = 0.9, 0.0
            elif xa <= x < xa + 100:
                v = va + (200.0 - va) * (x - xa) / 100.0
        out.append((x, v, fr, ac, t))
        t += passo / (v / 3.6)
        x += passo
    return out, t

def refer(curvas):
    amostras, t = perfil(curvas)
    N = 1000
    vel, freio, acel, tt = [], [], [], []
    for i in range(N):
        a = amostras[min(len(amostras) - 1, int((i + 0.5) / N * len(amostras)))]
        vel.append(a[1]); freio.append(a[2]); acel.append(a[3]); tt.append(a[4])
    return co.nova_referencia("Pista Teste", "Carro Teste", "importada", L, t, vel, freio, acel, [4] * N, tt)

def dirigir(c, curvas):
    amostras, t = perfil(curvas)
    ult = None
    guias = []
    for x, v, fr, ac, tt in amostras:
        r = c.atualizar(x / L, v, fr, ac, 4, tt, True, L, ult)
        if r["proxima"]: guias.append(r["proxima"])
    return t, guias

base = [(1000, 80), (2400, 90), (3300, 70)]
ref = refer(base)
confere(len(co.todas_as_zonas(ref)) == 3, "a pista sintetica tem 3 curvas")

with tempfile.TemporaryDirectory() as d:
    bib = co.BibliotecaReferencias(d)
    c = co.Coach(bib); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref, salvar=False); c.modo = "importada"
    # sessao: voltas com a freada da C1 15 m mais tarde (melhor), C2 variando e C3 igual
    voltas = [[(1015, 80), (2400, 90), (3300, 70)], [(1015, 80), (2380, 90), (3300, 70)],
              [(1000, 80), (2420, 90), (3300, 70)], [(1015, 80), (2410, 90), (3300, 70)],
              [(1000, 80), (2370, 90), (3300, 70)]]
    for v in voltas:
        dirigir(c, v)
    _, guias = dirigir(c, base)                    # a volta seguinte fecha a 5a e roda com historico
    confere(len(c._voltas()) >= 5, f"historico tem as voltas da sessao ({len(c._voltas())})")
    dicas = [g["melhor_sua"] for g in guias if g.get("melhor_sua")]
    confere(any(x["n"] == 1 for x in dicas), "dica 'melhor por curva' aparece na C1")
    d1 = next(x for x in dicas if x["n"] == 1)
    confere(abs(d1["dif_m"] - 15) <= 5 and d1["ganho"] > 0.03, f"C1: freou ~15 m mais tarde e ganha {d1['ganho']:.2f} s ({d1['dif_m']} m)")
    confere(d1["texto"].startswith("C1 | Melhor passagem: -0,") and "depois da referência" in d1["texto"], f"texto: {d1['texto']}")
    confere(not any(x["n"] == 3 for x in dicas), "sem dica onde a sua passagem nao e melhor (C3)")
    confere(c.referencia_ativa() is c.ref_importada or c.modo == "importada", "a referencia principal nao mudou por causa da dica")

    # sem historico suficiente nao ha dica
    c0 = co.Coach(co.BibliotecaReferencias(tempfile.mkdtemp())); c0.definir_contexto("Pista Teste", "Carro Teste", L)
    c0.definir_importada(ref, salvar=False); c0.modo = "importada"
    dirigir(c0, voltas[0]); _, g0 = dirigir(c0, voltas[1])
    confere(not any(g.get("melhor_sua") for g in g0), "com so 1-2 voltas guardadas nao mostra dica")

    # resumo da sessao
    r = c.resumo_da_sessao()
    confere(r["voltas"] >= 5 and r["aviso"] is None, f"resumo usa as voltas da sessao ({r['voltas']})")
    confere(r["itens"] and r["itens"][0]["n"] == 2, f"a curva que mais perde tempo e a C2 (a que varia): C{r['itens'][0]['n'] if r['itens'] else '?'}")
    confere(all(x["perda_media"] >= 0 for x in r["itens"]), "perdas nunca negativas")
    confere(r["potencial_s"] is not None and 0 <= r["potencial_s"] < r["melhor_volta"] and r["ideal_s"] <= r["melhor_volta"],
            f"volta ideal estimada ~{r['ideal_s']:.3f} s (potencial {r['potencial_s']:.2f} s)")
    confere("Onde mais perdeu tempo" in r["texto"] and "C2" in r["texto"], "texto do resumo traz as curvas")

    # persistencia: nova execucao carrega o historico; sessao nova nao tem voltas ainda
    c.descarregar()                                  # 1.7.0: gravacao em segundo plano
    c2 = co.Coach(co.BibliotecaReferencias(d)); c2.sessao += 5
    c2.definir_contexto("Pista Teste", "Carro Teste", L)
    confere(len(c2._voltas()) >= 5, "historico persiste entre execucoes")
    r2 = c2.resumo_da_sessao()
    confere(r2["aviso"] and r2["voltas"] == 0, f"sessao nova: aviso de poucas voltas ({r2['aviso']})")
    # volta externa (.ibt) entra no historico sem contar na sessao
    c2.definir_importada(ref, salvar=False)
    antes = len(c2._voltas())
    amostras, t = perfil([(1030, 80), (2400, 90), (3300, 70)])
    ext = refer([(1030, 80), (2400, 90), (3300, 70)]); ext["origem"] = "propria"
    confere(c2.registrar_volta_externa(ext) and len(c2._voltas()) == antes + 1, "volta externa (.ibt) entra no historico")
    confere(c2.resumo_da_sessao()["voltas"] == 0, "...mas nao conta como volta da sessao")
    # limite de voltas guardadas
    lista = c2._voltas()
    for k in range(60):
        nova = {kk: vv for kk, vv in lista[0].items() if kk != "id"}
        nova.update(tempo=100.0 + k, sessao=1)
        lista = mc.acrescentar(lista, nova, c2.sessao)
    confere(len(lista) == mc.MAX_VOLTAS, f"limite de {mc.MAX_VOLTAS} voltas ({len(lista)})")
    # arquivo corrompido nao derruba
    c2.descarregar()
    arq = next((c2.hist.pasta).glob("historico__*.json"))
    arq.write_text("{ruim", encoding="utf-8")
    confere(c2.hist.carregar("Pista Teste", "Carro Teste") == [], "historico corrompido e ignorado")

print("\n" + ("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")); sys.exit(1 if falhas else 0)
