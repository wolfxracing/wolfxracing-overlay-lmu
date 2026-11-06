# -*- coding: utf-8 -*-
"""v1.7.0 - resumo de stint, coach de ritmo e decisao das falas (sem voz real)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ov_coach_ritmo as cr
import ov_voz as vz

falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

def fb(n, nota, m, dv=0.0, g=0):
    return {"n": n, "freada_m": m, "nota": nota, "dif_vel": dv, "gravidade": g}
ac = cr.AcumuladorStint()
confere(ac.resumo() is None and not ac.registrar(None) and not ac.registrar({"feedbacks": []}), "sem dados: nada a resumir")
for _ in range(4):
    ac.registrar({"tempo": 92.0, "diferenca_ref": 0.3, "feedbacks": [fb(1, "perfeita", 2.0), fb(2, "cedo", 25.0, -4.0, 2), fb(3, "boa", -6.0, 0.5, 0)]})
r = ac.resumo()
confere(r["voltas"] == 4 and [c["n"] for c in r["piores"]] == [2], f"pior curva do stint = C2 ({[c['n'] for c in r['piores']]})")
confere("C2" in r["texto"] and "cedo" in r["texto"] and "4 de 4" in r["texto"], f"texto: {r['texto']}")
ac2 = cr.AcumuladorStint(max_voltas=3)
for _ in range(10): ac2.registrar({"feedbacks": [fb(1, "boa", 1.0)]})
confere(len(ac2.voltas) == 3 and ac2.resumo()["texto"].startswith("Sem ponto fraco"), "limite de voltas lembradas e stint limpo")

tend = {"voltas": [(i, t, 1) for i, t in enumerate([93.2, 92.4, 92.1, 92.3, 92.0, 92.8], 1)], "stint_atual": 1, "inclinacao": 0.0, "consistencia": 0.3}
x = cr.coach_ritmo(tend)
confere(abs(x["alvo"] - (92.0 + 92.1 + 92.3) / 3) < 1e-9, f"alvo = media das 3 melhores do stint ({x['alvo']:.3f})")
confere(x["situacao"] == "bem_acima" and x["dif"] > 0.6, f"ultima volta bem acima do alvo (+{x['dif']:.2f})")
confere(cr.coach_ritmo({"voltas": [(1, 92.0, 1), (2, 92.1, 1)], "stint_atual": 1})["alvo"] is None, "menos de 3 voltas: sem alvo")
confere(cr.coach_ritmo(None) is None, "sem tendencia: None")
tend2 = dict(tend, inclinacao=0.12)
confere(cr.coach_ritmo(tend2)["queda"] is True, "inclinacao positiva forte = ritmo caindo")
# combustivel
c = cr._combustivel(20, 52.0, 2.5, 0.5)                       # precisa 51.25 -> sobra
confere(c["estado"] == "ok" and c["folga_l"] > 0, "combustivel sobra")
c = cr._combustivel(20, 49.0, 2.5, 0.5)                       # precisa 51.25 -> falta 2.25 -> 0.1125 L/volta = 4.5%
confere(c["estado"] == "poupar" and abs(c["poupar_pct"] - 4.5) < 0.1, f"poupar ~4,5% por volta ({c['poupar_pct']:.1f})")
c = cr._combustivel(20, 40.0, 2.5, 0.5)
confere(c["estado"] == "parada", "falta muito: pede parada, nao economia")
confere(cr._combustivel(None, 40.0, 2.5, 0.5) is None and cr._combustivel(20, None, 2.5, 0.5) is None, "sem dados: None")
confere("Alvo 1:32.133" in cr.texto_ritmo(cr.coach_ritmo(tend, 20, 49.0, 2.5)) and "poupe 5%" in cr.texto_ritmo(cr.coach_ritmo(tend, 20, 49.0, 2.5)),
        f"texto do ritmo: {cr.texto_ritmo(cr.coach_ritmo(tend, 20, 49.0, 2.5))}")

# voz
fala, rel = [], [0.0]
loc = vz.Locutor(lambda t: fala.append(t) or True, lambda: rel[0])
def coach(n, dist, fase="adiante", marcha=3, feedback=None, rv=None, total=9):
    return {"estado": "ok", "proxima": {"n": n, "dist_m": dist, "fase": fase, "marcha": marcha, "total": total, "contagem": None},
            "feedback": feedback, "resumo_volta": rv}
confere(loc.processar(coach(1, 100)) is None and not fala, "voz desligada por padrao: nao fala")
loc.ativo = True
confere(loc.processar(coach(1, 300)) is None and not fala, "curva longe: nao anuncia")
confere(loc.processar(coach(1, 200)) == "Curva 1, marcha 3", "anuncia curva e marcha")
rel[0] += 0.5
confere(loc.processar(coach(1, 150)) is None and len(fala) == 1, "nao repete o anuncio da mesma curva")
rel[0] += 3.0
f1 = fb(1, "cedo", 14.0, -3.0, 1)
confere(loc.processar(coach(2, 400, feedback=f1)) == "Curva 1, freou cedo, 14 metros", "avalia freada com problema por voz")
rel[0] += 0.5
confere(loc.processar(coach(2, 200, feedback=fb(9, "tarde", -20.0, 0, 1))) is None, "limite de uma frase a cada 2 s")
rel[0] += 2.5
confere(loc.processar(coach(2, 200, feedback=f1)) == "Curva 2, marcha 3", "frase perdida pelo limite nao e repetida; segue o anuncio")
for k in range(3):
    rel[0] += 3.0; loc.processar(coach(3, 500, feedback=fb(1, "perfeita", 1.0)))
rel[0] += 3.0
confere(loc.processar(coach(3, 500, feedback=fb(1, "perfeita", 1.0))) == "Curva 1, freada perfeita", "elogia 1 a cada 4 perfeitas")
rel[0] += 3.0
confere(loc.processar(coach(3, 450), no_carro=False) is None, "nada de fala fora do carro")
rel[0] += 3.0
conf = loc.processar(coach(3, 450), ritmo={"combustivel": {"estado": "poupar", "poupar_pct": 4.5}})
confere(conf == "Poupe 5 por cento de combustivel por volta", f"avisa combustivel ({conf})")
rel[0] += 3.0
confere(loc.processar(coach(3, 450), ritmo={"combustivel": {"estado": "poupar", "poupar_pct": 4.5}}) is None, "nao repete o aviso de combustivel")
loc2 = vz.Locutor(lambda t: (_ for _ in ()).throw(RuntimeError("voz quebrou")), lambda: 0.0); loc2.ativo = True
confere(loc2.processar(coach(1, 100)) is None, "erro no backend de voz nao propaga")
confere(vz.FalaWindows().falar("teste") in (True, False), "backend de voz fora do Windows nao levanta excecao")

print("RESULTADO:", "OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
