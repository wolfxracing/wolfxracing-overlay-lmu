# -*- coding: utf-8 -*-
"""v1.8: logica pura (ov_v18): vazao, marcha, destino, ultrapassagem, hibrido, sessao, calendario, paleta daltonica, adaptador de dados."""
import os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ov_v18 as v

falhas, _ok = [], 0
def confere(c, msg):
    global _ok
    if c: _ok += 1; print("OK   ", msg)
    else: falhas.append(msg); print("FALHA", msg)

def ent(t, rpm=6000, ace=1.0, lh=100.0, marcha=3, vel=150.0, **k):
    e = {"agora": t, "rpm": rpm, "rpm_max": 8000.0, "acel": ace, "inst_lh": lh, "marcha": marcha, "vel_kmh": vel, "valido": True, "volta": 1,
         "consumo": {"ultima_lv": 2.5, "medio_lv": 2.4}}
    e.update(k); return e

# ---- faixas e celulas
confere(v.coluna_rpm(2800, 8000) == 0 and v.coluna_rpm(8000, 8000) == v.N_COLS - 1 and v.coluna_rpm(1000, 8000) == 0, "coluna_rpm: limites e abaixo do minimo")
confere(v.coluna_rpm(float("nan"), 8000) is None and v.coluna_rpm(5000, 0) is None, "coluna_rpm: dado invalido devolve None")
confere(v.linha_acel(0) == 0 and v.linha_acel(1.0) == 10 and v.linha_acel(0.5) == 5, "linha_acel")
confere([v.faixa_acel(a) for a in (1.0, 0.7, 0.4, 0.1, 0.0)] == ["FLAT", "HIGH", "MID", "LOW", "COAST"], "faixa_acel: cinco faixas")

# ---- vazao / destino: litros = L/h x dt
c = v.Coletor()
for i in range(41):
    r = c.atualizar(ent(i * 0.1, lh=120.0))
confere(abs(r["destino"]["total_l"] - 120.0 / 3600.0 * 4.0) < 1e-6, f"destino: litros integrados ({r['destino']['total_l']:.5f})")
confere(r["destino"]["faixas"][0]["nome"] == "FLAT" and abs(r["destino"]["faixas"][0]["parcela"] - 1.0) < 1e-9, "destino: tudo a fundo = 100% em FLAT")
cel = r["vazao"]["celulas"][10][v.coluna_rpm(6000, 8000)]
confere(cel is not None and abs(cel - 120.0) < 1e-6, "vazao: media da celula (acelerador 100%, 6000 rpm)")
confere(r["vazao"]["atual"] == (10, v.coluna_rpm(6000, 8000)), "vazao: celula atual")
c.atualizar(ent(5.0, rpm=4000, ace=0.0, lh=10.0)); c.atualizar(ent(5.1, rpm=4000, ace=0.0, lh=10.0))
confere(c.resumo(ent(5.2))["vazao"]["celulas"][0][v.coluna_rpm(4000, 8000)] == 10.0, "vazao: celula de acelerador 0%")
# pausa/menu nao somam
c2 = v.Coletor(); c2.atualizar(ent(0.0)); r2 = c2.atualizar(ent(30.0))
confere(r2["destino"]["total_l"] == 0.0, "destino: intervalo longo (pausa) nao entra na soma")
# fora da pista / invalido
c3 = v.Coletor()
for i in range(5): r3 = c3.atualizar(ent(i * 0.1, valido=False))
confere(r3["vazao"]["amostras"] == 0, "vazao: nao coleta fora da pista/box")
for ruim in (dict(lh=None), dict(lh=-5.0), dict(lh=float("nan")), dict(rpm=0)):
    c4 = v.Coletor()
    try:
        for i in range(3): rr = c4.atualizar(ent(i * 0.1, **ruim))
        confere(rr["vazao"]["amostras"] == 0, f"vazao: entrada invalida ignorada {ruim}")
    except Exception as ex:
        confere(False, f"vazao: entrada invalida levantou {ex}")
# carro diferente (rpm_max muda): mapa recomeca
c5 = v.Coletor()
for i in range(4): c5.atualizar(ent(i * 0.1))
e = ent(0.5); e["rpm_max"] = 11000.0
confere(c5.atualizar(e)["vazao"]["amostras"] <= 1, "vazao: troca de carro (rpm_max) zera o mapa")

# ---- marcha: so acelerador pleno e > 20 km/h; L/100 km = (L/h) / (km/h) x 100
c6 = v.Coletor()
for i in range(10): r6 = c6.atualizar(ent(i * 0.1, lh=100.0, vel=200.0, marcha=4))       # 50 L/100 km
m4 = next(m for m in r6["marcha"]["marchas"] if m["marcha"] == 4)
col = v.coluna_rpm(6000, 8000)
confere(abs(m4["celulas"][col] - 50.0) < 1e-6, f"marcha: L/100 km correto ({m4['celulas'][col]})")
confere(abs(m4["parcela"] - 1.0) < 1e-9 and m4["rpm_max"] == 6000 and "rpm_troca" not in m4, "marcha: parcela do tempo e RPM maximo observado")
c7 = v.Coletor()
for i in range(10): r7 = c7.atualizar(ent(i * 0.1, ace=0.5, marcha=4))
confere(r7["marcha"]["marchas"] == [], "marcha: acelerador parcial nao entra")
c8 = v.Coletor()
for i in range(10): r8 = c8.atualizar(ent(i * 0.1, vel=5.0, marcha=2))
confere(all(all(x is None for x in m["celulas"]) for m in r8["marcha"]["marchas"]), "marcha: abaixo de 20 km/h nao calcula L/100 km")
confere(v.Coletor().atualizar(ent(0, marcha=0))["marcha"]["marchas"] == [] and v.Coletor().atualizar(ent(0, marcha=-1))["marcha"]["marchas"] == [], "marcha: neutro e re ignorados")

# ---- stint: zera ao sair dos boxes
c9 = v.Coletor()
for i in range(20): c9.atualizar(ent(i * 0.1, box=False))
conta = c9.resumo(ent(2.0))["destino"]["stint_l"]
c9.atualizar(ent(2.1, box=True)); c9.atualizar(ent(2.2, box=False))
confere(conta > 0 and c9.resumo(ent(2.3))["destino"]["stint_l"] < conta, "stint: recomeca depois dos boxes")

# ---- ultrapassagem
def rel(gaps, **extra):
    return {"atras": [dict({"numero": str(i), "nome": "Piloto Teste %d" % i, "gap": g, "eu": False, "na_box": False, "volta_rel": 0, "mesma_classe": False,
                            "classe_cor": (255, 220, 60)}, **extra) for i, g in enumerate(gaps, 1)]}
c10 = v.Coletor()
for i in range(31):
    r10 = c10.atualizar(ent(i * 0.1, relativo=rel([2.5 - 0.1 * i * 0.3, 5.0])))
nums = [x["numero"] for x in r10["ultrapassagem"]["carros"]]
confere(nums == ["1"], f"ultrapassagem: so o carro perto e fechando alerta ({nums})")
confere(r10["ultrapassagem"]["carros"][0]["fecha"] > 0.05, "ultrapassagem: velocidade de aproximacao positiva")
c11 = v.Coletor()
for i in range(31): r11 = c11.atualizar(ent(i * 0.1, relativo=rel([2.5 + 0.03 * i])))
confere(r11["ultrapassagem"]["carros"] == [], "ultrapassagem: carro se afastando nao alerta")
c12 = v.Coletor()
for i in range(31): r12 = c12.atualizar(ent(i * 0.1, relativo=rel([0.8])))
confere(len(r12["ultrapassagem"]["carros"]) == 1, "ultrapassagem: colado (<1 s) alerta mesmo sem aproximar")
# o alerta segura 2 s depois que o carro some (nao pisca)
r13 = c12.atualizar(ent(3.2, relativo={"atras": []}))
confere(len(r13["ultrapassagem"]["carros"]) == 1, "ultrapassagem: alerta nao pisca ao perder o carro por 1 ciclo")
r14 = c12.atualizar(ent(6.0, relativo={"atras": []}))
confere(r14["ultrapassagem"]["carros"] == [], "ultrapassagem: alerta some depois de ~2 s")
c15 = v.Coletor()
for i in range(31): r15 = c15.atualizar(ent(i * 0.1, relativo=rel([0.8], na_box=True)))
confere(r15["ultrapassagem"]["carros"] == [], "ultrapassagem: carro nos boxes ignorado")
c16 = v.Coletor()
for i in range(31): r16 = c16.atualizar(ent(i * 0.1, relativo=rel([0.8], volta_rel=-1)))
confere(r16["ultrapassagem"]["carros"] == [], "ultrapassagem: carro de outra volta ignorado (padrao)")
c17 = v.Coletor()
for i in range(31): r17 = c17.atualizar(ent(i * 0.1, relativo=rel([0.8], mesma_classe=True), ultrap_so_outras=True))
confere(r17["ultrapassagem"]["carros"] == [], "ultrapassagem: opcao 'so outras classes' ignora a minha")
c18 = v.Coletor()
for i in range(31): r18 = c18.atualizar(ent(i * 0.1, relativo=rel([4.0 - 0.05 * i]), ultrap_limite=5.0))
confere(len(r18["ultrapassagem"]["carros"]) == 1, "ultrapassagem: limite de 5 s avisa mais cedo")
c19 = v.Coletor()
for i in range(31): r19 = c19.atualizar(ent(i * 0.1, relativo=rel([4.0 - 0.05 * i]), ultrap_limite=3.0))
confere(len(r19["ultrapassagem"]["carros"]) == 0 or r19["ultrapassagem"]["carros"][0]["gap"] <= 3.0, "ultrapassagem: limite de 3 s so avisa dentro de 3 s")
confere(v.nome_curto("Istvan Fodor") == "Istvan FODOR" and v.nome_curto("Madonna") == "Madonna" and v.nome_curto(None) == "", "nome_curto")

# ---- atras_por_distancia (LMU)
L = 5000.0
carros = [{"id": 1, "pct": 0.50, "box": False, "classe_id": "A", "numero": "1", "nome": "Eu"},
          {"id": 2, "pct": 0.49, "box": False, "classe_id": "B", "numero": "2", "nome": "Atras perto", "cor": (1, 2, 3), "classe_nome": "B"},
          {"id": 3, "pct": 0.51, "box": False, "classe_id": "B", "numero": "3", "nome": "Na frente"},
          {"id": 4, "pct": 0.20, "box": False, "classe_id": "B", "numero": "4", "nome": "Longe"},
          {"id": 5, "pct": 0.495, "box": True, "classe_id": "B", "numero": "5", "nome": "Boxes"}]
at = v.atras_por_distancia(carros, 1, 50.0, L)
confere([a["numero"] for a in at] == ["2"] and abs(at[0]["gap"] - 1.0) < 1e-9, f"atras_por_distancia: so o de tras, perto, fora dos boxes ({[a['numero'] for a in at]})")
carros[1]["pct"] = 0.999     # virada da linha de chegada: 0.5 -> carro em 0.999 esta 0.501 voltas atras (= na frente por 0.499): nao e "atras" proximo
confere(v.atras_por_distancia(carros, 1, 50.0, L) == [], "atras_por_distancia: carro distante pela virada nao alerta")
carros2 = [{"id": 1, "pct": 0.005, "box": False, "classe_id": "A"}, {"id": 2, "pct": 0.995, "box": False, "classe_id": "A", "numero": "2"}]
confere(len(v.atras_por_distancia(carros2, 1, 50.0, L)) == 1, "atras_por_distancia: atras na virada da linha (0.995 -> 0.005)")
confere(v.atras_por_distancia([], 1, 50.0, L) == [] and v.atras_por_distancia(carros, 99, 50.0, L) == [] and v.atras_por_distancia(carros, 1, 50.0, 0) == [], "atras_por_distancia: entradas vazias/invalidas")

# ---- hibrido
c20 = v.Coletor()
for i in range(21):
    r20 = c20.atualizar(ent(i * 0.1, volta=1, hibrido={"carga": 0.6, "deploy": None, "ativo": i % 2 == 0}))
confere(r20["hibrido"] is not None and abs(r20["hibrido"]["carga"] - 0.6) < 1e-9, "hibrido: carga")
confere(0.4 < r20["hibrido"]["deploy"] < 0.6, f"hibrido: deploy medido pelo tempo ativo ({r20['hibrido']['deploy']:.2f})")
r21 = c20.atualizar(ent(2.2, volta=2, hibrido={"carga": 0.55, "deploy": None, "ativo": True}))
confere(r21["hibrido"]["ult_carga"] == 0.6 and r21["hibrido"]["ult_deploy"] is not None, "hibrido: guarda a ultima leitura da volta anterior (nao a do instante da troca)")
confere(v.Coletor().atualizar(ent(0))["hibrido"] is None, "hibrido: carro sem dado -> None (a janela avisa)")
confere(v.Coletor().atualizar(ent(0, hibrido={"carga": float("nan")}))["hibrido"] is None, "hibrido: carga invalida -> None")
confere(v.Coletor().atualizar(ent(0, hibrido={"carga": 1.7, "ativo": False}))["hibrido"]["carga"] == 1.0, "hibrido: carga limitada a 0..1")

# ---- sessao
s = v.sessao({"restante": 345.0, "decorrido": 255.0})
confere(s["modo"] == "tempo" and s["texto"] == "05:45" and abs(s["fracao"] - 0.425) < 1e-9, f"sessao: tempo ({s})")
confere(v.fmt_relogio(3725) == "1:02:05" and v.fmt_relogio(-5) == "00:00", "sessao: formato do relogio")
s2 = v.sessao({"voltas_rest": 7, "voltas_total": 10})
confere(s2["modo"] == "voltas" and s2["texto"] == "7 voltas" and abs(s2["fracao"] - 0.3) < 1e-9, "sessao: por voltas")
confere(v.sessao({}) is None and v.sessao({"restante": float("nan")}) is None and v.sessao({"restante": -3}) is None and v.sessao({"restante": 9e9}) is None, "sessao: sem dado ou invalido -> None")
confere(v.sessao({"restante": 100.0})["fracao"] is None, "sessao: sem 'decorrido' nao inventa a fracao")

# ---- calendario
txt = "nome,classe,inicio,duracao_min,registro_min,repete_min\n# comentario\nGT3,B,20:15,45,15\nF4,D,2026-11-10 18:00,35,10,60\nruim,x,sem-hora,45\n,,,\n"
itens, erros = v.ler_calendario(txt)
confere(len(itens) == 2 and len(erros) == 1 and "linha" in erros[0], f"calendario: 2 corridas, 1 linha com erro ({len(itens)}, {erros})")
agora = dt.datetime(2026, 11, 6, 20, 0)
pr = v.proximas(itens, agora, 4)
confere(pr[0]["nome"] == "GT3" and pr[0]["inicio"] == dt.datetime(2026, 11, 6, 20, 15) and abs(pr[0]["ate_inicio_s"] - 900) < 1, f"calendario: proxima diaria ({pr[0]['inicio']})")
confere(abs(pr[0]["reg_s"] - 1800) < 1, "calendario: fechamento do registro")
agora2 = dt.datetime(2026, 11, 6, 20, 30)
pr2 = v.proximas(itens, agora2, 4)
confere(pr2[0]["em_andamento"] and pr2[0]["nome"] == "GT3", "calendario: corrida em andamento aparece")
pr3 = v.proximas(itens, dt.datetime(2026, 11, 10, 18, 40), 4)
f4 = [x for x in pr3 if x["nome"] == "F4"][0]
confere(f4["inicio"] == dt.datetime(2026, 11, 10, 19, 0) or f4["em_andamento"], f"calendario: repeticao a cada 60 min ({f4['inicio']})")
confere(v.ler_calendario("")[0] == [] and v.ler_calendario(None)[0] == [], "calendario: vazio")
pv, _e = v.ler_calendario("a;b;09:00;30\n")
confere(len(pv) == 1, "calendario: separador ponto e virgula")
pv2, e2 = v.ler_calendario("a,b,25:99,30\na,b,09:00,0\na,b,09:00,30,99\n")
confere(pv2 == [] and len(e2) == 3, "calendario: hora/duracao/registro invalidos descartados")
confere(len(v.exemplo_calendario()) == 4, "calendario: exemplo")

# ---- servico: calendario le o arquivo e so recarrega quando muda
import tempfile, time
pasta = tempfile.mkdtemp()
sv = v.Servico(pasta)
r = sv.montar({"no_carro": True, "velocidade": 100.0}, {}, {}, 1.0, dt.datetime(2026, 11, 6, 20, 0))
confere(r["calendario"] == [] and "calendario_corridas.csv" in r["calendario_aviso"], "servico: sem arquivo -> aviso com o nome do arquivo")
open(os.path.join(pasta, "calendario_corridas.csv"), "w", encoding="utf-8").write("GT3,B,20:15,45,15\n")
r = sv.montar({"no_carro": True, "velocidade": 100.0}, {}, {}, 30.0, dt.datetime(2026, 11, 6, 20, 0))
confere(len(r["calendario"]) == 1 and r["calendario_aviso"] == "", "servico: le o CSV quando aparece")
open(os.path.join(pasta, "calendario_corridas.csv"), "w", encoding="utf-8").write("ruim\n")
os.utime(os.path.join(pasta, "calendario_corridas.csv"), (time.time() + 5, time.time() + 5))
r = sv.montar({"no_carro": True, "velocidade": 100.0}, {}, {}, 60.0, dt.datetime(2026, 11, 6, 20, 0))
confere(r["calendario"] == [] and "erro" in r["calendario_aviso"].lower(), "servico: arquivo com erro -> aviso, sem derrubar")

# ---- adaptador de dados
dados = {"no_carro": True, "replay": False, "velocidade": 120.0, "rpm": 5000.0, "rpm_max": 8000.0, "acelerador": 0.9, "marcha": 3, "volta": 4,
         "consumo": {"inst_lh": 90.0}, "relativo": {"eu": {"na_box": False}, "atras": [], "tempo_restante": 600.0, "voltas_restantes": None}}
e = v.entrada_de_dados(dados, {"decorrido": 300.0}, 1.0)
confere(e["valido"] and e["inst_lh"] == 90.0 and e["restante"] == 600.0 and e["decorrido"] == 300.0, "entrada_de_dados: campos basicos")
confere(not v.entrada_de_dados(dict(dados, replay=True), {}, 1.0)["valido"] and not v.entrada_de_dados(dict(dados, no_carro=False), {}, 1.0)["valido"], "entrada_de_dados: replay/fora do carro = invalido")
confere(not v.entrada_de_dados(dict(dados, relativo={"eu": {"na_box": True}, "atras": []}), {}, 1.0)["valido"], "entrada_de_dados: nos boxes = invalido")
e2 = v.entrada_de_dados({"no_carro": True, "velocidade": 100.0, "v18_atras": [{"numero": "9", "gap": 1.0}]}, {}, 1.0)
confere(e2["relativo"]["atras"][0]["numero"] == "9", "entrada_de_dados: usa 'v18_atras' quando nao ha relativo (LMU)")
try:
    v.entrada_de_dados(None, None, 1.0); v.entrada_de_dados({}, {}, 1.0)
    confere(True, "entrada_de_dados: dados vazios nao levantam erro")
except Exception as ex:
    confere(False, f"entrada_de_dados: dados vazios levantaram {ex}")
class _Tele:
    def _extra_v18(self): raise RuntimeError("falha de leitura")
dd = {"no_carro": True, "velocidade": 100.0}
erros_ = []
v.alimentar(v.Servico(None), _Tele(), dd, {}, 1.0, erros_.append)
confere(dd.get("v18") is not None and len(erros_) == 1, "alimentar: falha na leitura extra vira registro de erro e o ciclo segue")
dd2 = {"v18": {"x": 1}}
v.alimentar(v.Servico(None), _Tele(), dd2, {}, 1.0)
confere(dd2["v18"] == {"x": 1}, "alimentar: nao sobrescreve o v18 da demonstracao")

# ---- paleta daltonica
confere(v.remapear_rgb("padrao", 60, 200, 90) == (60, 200, 90) and v.remapear_rgb("inexistente", 60, 200, 90) == (60, 200, 90), "daltonismo: padrao nao muda nada")
for modo in ("deuteranopia", "protanopia", "tritanopia"):
    for cor in ((255, 255, 255), (128, 128, 128), (0, 0, 0), (170, 170, 185)):
        confere(v.remapear_rgb(modo, *cor) == cor, f"daltonismo {modo}: cor sem saturacao {cor} inalterada")
bom, ruim = v.remapear_rgb("deuteranopia", 60, 200, 90), v.remapear_rgb("deuteranopia", 235, 60, 60)
hb, hr = v._rgb_hsv(*bom)[0], v._rgb_hsv(*ruim)[0]
confere(180 < hb < 250 and 10 < hr < 50, f"deuteranopia: verde -> azul ({hb:.0f} graus), vermelho -> laranja ({hr:.0f} graus)")
amar = v.remapear_rgb("deuteranopia", 250, 200, 40)
confere(abs(v._rgb_hsv(*amar)[0] - hr) > 15, "deuteranopia: o amarelo (aviso) fica distinto do vermelho remapeado")
bomp, ruimp = v.remapear_rgb("protanopia", 60, 200, 90), v.remapear_rgb("protanopia", 235, 60, 60)
confere(v._rgb_hsv(*ruimp)[2] >= v._rgb_hsv(235, 60, 60)[2], "protanopia: o vermelho remapeado fica mais claro (nao mais escuro)")
trit = v.remapear_rgb("tritanopia", 70, 200, 235)
confere(v._rgb_hsv(*trit)[0] > 250, "tritanopia: azul/ciano -> violeta")
confere(v.remapear_rgb("tritanopia", 60, 200, 90) == (60, 200, 90), "tritanopia: o verde nao muda")
for modo in v.MODOS_DALTONISMO:
    ok = all(all(0 <= x <= 255 for x in v.remapear_rgb(modo, r, g, b)) for r in range(0, 256, 51) for g in range(0, 256, 51) for b in range(0, 256, 51))
    confere(ok, f"daltonismo {modo}: todos os canais ficam entre 0 e 255")

# ---- demonstracao
ex = v.exemplo(2.0)
confere(all(k in ex for k in ("vazao", "marcha", "destino", "ultrapassagem", "hibrido", "sessao", "calendario")), "exemplo: traz todas as chaves")
confere(ex["vazao"]["maximo"] > ex["vazao"]["minimo"] and ex["sessao"]["modo"] == "tempo" and len(ex["calendario"]) == 4, "exemplo: valores coerentes")
confere(abs(sum(f["parcela"] for f in ex["destino"]["faixas"]) - 1.0) < 1e-6, "exemplo: as parcelas do destino somam 100%")

# =====================================================================================================================
# Build y - P1: medias ponderadas pelo TEMPO (a taxa de aquisicao nao pode mudar o resultado)
# =====================================================================================================================
import math, random
COL = v.coluna_rpm(6000, 8000)
def celula(c_, linha=10):
    return c_.resumo(ent(0))["vazao"]["celulas"][linha][COL]
def rodar(tempos, f, **k):
    c_ = v.Coletor()
    for t in tempos:
        c_.atualizar(ent(t, lh=f(t), **k))
    return c_
# (a) reproduz o defeito da auditoria: 4 s a 5 Hz com 50 L/h e 1 s a 60 Hz com 200 L/h (media por contagem daria 169, a correta ~80)
t_lento = [i / 5.0 for i in range(0, 21)]
t_rapido = [4.0 + i / 60.0 for i in range(1, 61)]
f_deg = lambda t: 50.0 if t <= 4.0 else 200.0
cd = rodar(t_lento + t_rapido, f_deg)
esperado = (4 * 50.0 + 1 * 200.0) / 5.0
confere(abs(celula(cd) - esperado) / esperado < 0.02, f"P1: taxa mista 5 Hz + 60 Hz = media no tempo ({celula(cd):.1f} vs {esperado:.1f} L/h)")
# (b) mesmo sinal em 5, 10, 30 e 60 Hz, com e sem jitter: todos devem concordar com a media analitica
f_sen = lambda t: 100.0 + 40.0 * math.sin(2 * math.pi * t / 3.0)
T = 12.0
analitico = 100.0 + 40.0 * (1 - math.cos(2 * math.pi * T / 3.0)) * 3.0 / (2 * math.pi) / T
rng = random.Random(18)
for hz in (5, 10, 30, 60):
    for jit in (0.0, 0.25):
        t = 0.0; ts = [0.0]
        while t < T:
            t += (1.0 / hz) * (1.0 + rng.uniform(-jit, jit)); ts.append(min(t, T + 1.0 / hz))
        cx = rodar(ts, f_sen)
        got = celula(cx); ref = 100.0 + 40.0 * (1 - math.cos(2 * math.pi * ts[-1] / 3.0)) * 3.0 / (2 * math.pi) / ts[-1]
        confere(abs(got - ref) / ref < 0.03, f"P1: {hz} Hz, jitter {int(jit * 100)}%: {got:.1f} vs {ref:.1f} L/h")
# (c) intervalos desiguais aleatorios (10 ms a 400 ms)
for semente in range(5):
    r_ = random.Random(semente); t = 0.0; ts = [0.0]
    while t < 20.0:
        t += r_.uniform(0.01, 0.4); ts.append(t)
    cx = rodar(ts, f_sen)
    ref = 100.0 + 40.0 * (1 - math.cos(2 * math.pi * ts[-1] / 3.0)) * 3.0 / (2 * math.pi) / ts[-1]
    confere(abs(celula(cx) - ref) / ref < 0.06, f"P1: intervalos desiguais (semente {semente}): {celula(cx):.1f} vs {ref:.1f}")
# (d) a taxa nao muda o resultado: o mesmo sinal constante por partes em 5 Hz e 60 Hz da o mesmo valor
f_dg = lambda t: 60.0 if (t % 2.0) < 1.0 else 140.0
a5 = celula(rodar([i / 5.0 for i in range(0, 101)], f_dg)); a60 = celula(rodar([i / 60.0 for i in range(0, 1201)], f_dg))
confere(abs(a5 - a60) < 6.0, f"P1: 5 Hz e 60 Hz concordam ({a5:.1f} vs {a60:.1f})")
# (e) pausas/intervalos longos e dados invalidos continuam fora da media
cp = v.Coletor()
for i in range(11): cp.atualizar(ent(i * 0.1, lh=100.0))
cp.atualizar(ent(60.0, lh=900.0))                      # volta de uma pausa de 59 s: dt invalido, nao pesa
for i in range(1, 11): cp.atualizar(ent(60.0 + i * 0.1, lh=100.0))
confere(abs(celula(cp) - 100.0) < 1e-6, f"P1: pausa longa nao entra na media ({celula(cp):.2f})")
ci_ = v.Coletor()
for i in range(21): ci_.atualizar(ent(i * 0.1, lh=100.0 if i % 3 else float("nan")))
confere(abs(celula(ci_) - 100.0) < 1e-6, "P1: amostras invalidas (NaN) nao entram na media")
cv = v.Coletor()
for i in range(21): cv.atualizar(ent(i * 0.1, lh=100.0, valido=(i % 4 != 0)))
confere(abs(celula(cv) - 100.0) < 1e-6, "P1: amostras fora da pista nao entram")
confere(v.Coletor().atualizar(ent(0.0))["vazao"]["celulas"][10][COL] is None, "P1: uma unica amostra (sem duracao) nao cria celula")
# (f) eficiencia por marcha: mesma regra (L/100 km ponderado pelo tempo)
cm = v.Coletor()
for t in t_lento + t_rapido: cm.atualizar(ent(t, lh=f_deg(t), vel=200.0, marcha=4))
m4 = next(m for m in cm.resumo(ent(0))["marcha"]["marchas"] if m["marcha"] == 4)
esperado_m = esperado / 200.0 * 100.0
confere(abs(m4["celulas"][COL] - esperado_m) / esperado_m < 0.02, f"P1: marcha com taxa mista ({m4['celulas'][COL]:.1f} vs {esperado_m:.1f} L/100 km)")
for hz in (5, 10, 30, 60):
    r_ = random.Random(hz); t = 0.0; ts = [0.0]
    while t < 12.0:
        t += (1.0 / hz) * (1.0 + r_.uniform(-0.2, 0.2)); ts.append(t)
    cm2 = v.Coletor()
    for t in ts: cm2.atualizar(ent(t, lh=f_sen(t), vel=180.0, marcha=3))
    m3 = next(m for m in cm2.resumo(ent(0))["marcha"]["marchas"] if m["marcha"] == 3)
    ref = (100.0 + 40.0 * (1 - math.cos(2 * math.pi * ts[-1] / 3.0)) * 3.0 / (2 * math.pi) / ts[-1]) / 180.0 * 100.0
    confere(abs(m3["celulas"][COL] - ref) / ref < 0.03, f"P1: marcha a {hz} Hz com jitter ({m3['celulas'][COL]:.1f} vs {ref:.1f})")
cm3 = v.Coletor()
for i in range(21): cm3.atualizar(ent(i * 0.1, lh=100.0, vel=200.0 if i % 2 else 10.0, marcha=2))
confere(abs(next(m for m in cm3.resumo(ent(0))["marcha"]["marchas"] if m["marcha"] == 2)["celulas"][COL] - 50.0) < 1e-6, "P1: marcha abaixo de 20 km/h continua fora da media")
# destino/litros continuam integrados (regressao)
cl_ = v.Coletor()
for t in t_lento + t_rapido: cl_.atualizar(ent(t, lh=120.0))
confere(abs(cl_.resumo(ent(0))["destino"]["total_l"] - 120.0 / 3600.0 * 5.0) < 1e-6, "P1: litros do destino seguem integrados no tempo")

# =====================================================================================================================
# Build y - P2: identidade estavel no alerta de ultrapassagem (numeros repetidos em classes diferentes)
# =====================================================================================================================
def carro(i, numero, gap, classe, nome=None, **k):
    d = {"id": i, "idx": i, "numero": str(numero), "nome": nome or f"Piloto {i}", "gap": gap, "eu": False, "na_box": False, "volta_rel": 0,
         "mesma_classe": False, "classe_cor": (1, 2, 3), "classe_nome": classe}
    d.update(k); return d
# dois carros #5 (GT3 e LMP2): um fecha, outro se afasta; so o que fecha alerta e o historico nao se mistura
c1 = v.Coletor()
for i in range(31):
    t = i * 0.1
    r1 = c1.atualizar(ent(t, relativo={"atras": [carro(10, 5, 2.5 - 0.1 * i * 0.3, "LMP2"), carro(20, 5, 2.5 + 0.05 * i, "GT3")]}))
al = r1["ultrapassagem"]["carros"]
confere([a["id"] for a in al] == [10], f"P2: dois #5 de classes diferentes: so o id 10 (que fecha) alerta ({[a['id'] for a in al]})")
# a ordem na lista pode trocar a cada ciclo sem misturar historicos
c2 = v.Coletor()
for i in range(31):
    lst = [carro(10, 5, 2.5 - 0.03 * i, "LMP2"), carro(20, 5, 2.5 + 0.05 * i, "GT3")]
    if i % 2: lst.reverse()
    r2 = c2.atualizar(ent(i * 0.1, relativo={"atras": lst}))
confere([a["id"] for a in r2["ultrapassagem"]["carros"]] == [10], "P2: a ordem da lista nao mistura os historicos")
# dois carros #5 AMBOS fechando: dois alertas distintos
c3 = v.Coletor()
for i in range(31):
    r3 = c3.atualizar(ent(i * 0.1, relativo={"atras": [carro(10, 5, 2.5 - 0.03 * i, "LMP2"), carro(20, 5, 2.8 - 0.03 * i, "GT3")]}))
confere(sorted(a["id"] for a in r3["ultrapassagem"]["carros"]) == [10, 20], "P2: dois #5 fechando geram dois alertas (nada fundido)")
# o mesmo numero numa classe sem 'id' (fallback): numero + classe + nome separam os carros
c4 = v.Coletor()
for i in range(31):
    a_ = carro(None, 5, 2.5 - 0.03 * i, "LMP2", "Ana A"); b_ = carro(None, 5, 2.5 + 0.05 * i, "GT3", "Bia B")
    a_.pop("id"); a_.pop("idx"); b_.pop("id"); b_.pop("idx")
    r4 = c4.atualizar(ent(i * 0.1, relativo={"atras": [a_, b_]}))
confere([a["nome"] for a in r4["ultrapassagem"]["carros"]] == ["Ana A"], "P2: sem 'id', numero+classe+nome ainda separam carros com o mesmo numero")
# colisao total (mesmo numero, classe e nome sem id): nao levanta erro e nao mistura (desempate pela ocorrencia)
c5 = v.Coletor()
try:
    for i in range(31):
        x = carro(None, 7, 2.0 - 0.02 * i, "GT3", "Igual"); y = carro(None, 7, 2.4 + 0.02 * i, "GT3", "Igual")
        for q in (x, y): q.pop("id"); q.pop("idx")
        r5 = c5.atualizar(ent(i * 0.1, relativo={"atras": [x, y]}))
    confere(True, "P2: colisao total de identidade nao levanta erro")
except Exception as ex:
    confere(False, f"P2: colisao total levantou {ex}")
# troca de identidade no mesmo id (piloto/numero diferente, ex.: troca de piloto ou slot reaproveitado): historico recomeca
c6 = v.Coletor()
for i in range(31):
    r6 = c6.atualizar(ent(i * 0.1, relativo={"atras": [carro(10, 5, 3.0 - 0.05 * i, "LMP2", "Antigo")]}))
confere(len(r6["ultrapassagem"]["carros"]) == 1, "P2: (pre-condicao) o carro antigo estava alertando")
r7 = c6.atualizar(ent(3.1, relativo={"atras": [carro(10, 9, 2.9, "LMP2", "Novo")]}))
confere(r7["ultrapassagem"]["carros"] == [], "P2: troca de identidade no mesmo id derruba o alerta e nao herda a aproximacao")
for i in range(1, 6):
    r8 = c6.atualizar(ent(3.1 + i * 0.1, relativo={"atras": [carro(10, 9, 2.9, "LMP2", "Novo")]}))
confere(r8["ultrapassagem"]["carros"] == [], "P2: o novo piloto com gap constante nao alerta com o historico do antigo")
# o id reaproveitado depois de sumir da lista tambem comeca limpo
c9 = v.Coletor()
for i in range(31): c9.atualizar(ent(i * 0.1, relativo={"atras": [carro(10, 5, 3.0 - 0.05 * i, "LMP2")]}))
for i in range(31, 36): c9.atualizar(ent(i * 0.1, relativo={"atras": []}))
r9 = c9.atualizar(ent(3.6, relativo={"atras": [carro(10, 5, 2.9, "LMP2")]}))
confere(r9["ultrapassagem"]["carros"] == [] or r9["ultrapassagem"]["carros"][0]["fecha"] is None or r9["ultrapassagem"]["carros"][0]["fecha"] <= 0.05 or r9["ultrapassagem"]["carros"][0]["gap"] <= 1.0, "P2: carro que volta a lista nao reaproveita diferencas antigas")
# integracao com o adaptador: iRacing usa 'idx'; LMU (atras_por_distancia) fornece 'id'
carros_l = [{"id": 1, "pct": 0.50, "box": False, "classe_id": "A", "numero": "1", "nome": "Eu"},
            {"id": 31, "pct": 0.49, "box": False, "classe_id": "B", "numero": "5", "nome": "X", "classe_nome": "GT3"},
            {"id": 32, "pct": 0.485, "box": False, "classe_id": "C", "numero": "5", "nome": "Y", "classe_nome": "LMP2"}]
at = v.atras_por_distancia(carros_l, 1, 50.0, 5000.0)
confere([a["id"] for a in at] == [31, 32] and all(a["numero"] == "5" for a in at), "P2: atras_por_distancia (LMU) entrega o 'id' do carro, mesmo com numeros repetidos")
ex_ir = v.exemplo(1.0)
confere(all("numero" in c for c in ex_ir["ultrapassagem"]["carros"]), "P2: demonstracao continua com o formato esperado pela janela")

# =====================================================================================================================
# Build y - P2: hibrido, 'ultima volta' = ultima leitura valida da volta que acabou
# =====================================================================================================================
ch = v.Coletor()
for i in range(31):                                        # volta 1: carga cai de 0.90 para 0.60 (ultima leitura da volta = 0.60)
    ch.atualizar(ent(i * 0.1, volta=1, hibrido={"carga": 0.90 - 0.01 * i, "deploy": 0.30 + 0.01 * i, "ativo": True}))
ultima_v1 = 0.90 - 0.01 * 30
rh = ch.atualizar(ent(3.1, volta=2, hibrido={"carga": 0.20, "deploy": 0.0, "ativo": False}))         # 1a leitura da volta 2 ja vem diferente
confere(abs(rh["hibrido"]["ult_carga"] - ultima_v1) < 1e-9, f"hibrido: 'ult_carga' = ultima leitura da volta 1 ({rh['hibrido']['ult_carga']:.2f}), nao a da troca (0.20)")
confere(abs(rh["hibrido"]["ult_deploy"] - (0.30 + 0.30)) < 1e-9, "hibrido: 'ult_deploy' = ultimo valor da volta 1")
confere(abs(rh["hibrido"]["carga"] - 0.20) < 1e-9, "hibrido: 'carga' atual continua sendo a leitura atual")
# leituras invalidas no fim da volta: preserva o ultimo valor valido
cj = v.Coletor()
for i in range(21): cj.atualizar(ent(i * 0.1, volta=1, hibrido={"carga": 0.7, "deploy": None, "ativo": i % 2 == 0}))
for i in range(21, 26): cj.atualizar(ent(i * 0.1, volta=1, hibrido={"carga": float("nan"), "ativo": True}))     # sensor sem dado
rj = cj.atualizar(ent(2.6, volta=2, hibrido={"carga": 0.4, "deploy": None, "ativo": True}))
confere(abs(rj["hibrido"]["ult_carga"] - 0.7) < 1e-9, "hibrido: leituras invalidas no fim da volta nao apagam o ultimo valor valido")
rj2 = cj.atualizar(ent(2.7, volta=2, hibrido=None))
confere(rj2["hibrido"] is None, "hibrido: sem dado agora = None (a janela avisa)")
rj3 = cj.atualizar(ent(2.8, volta=2, hibrido={"carga": 0.45, "deploy": None, "ativo": True}))
confere(abs(rj3["hibrido"]["ult_carga"] - 0.7) < 1e-9, "hibrido: o valor da volta anterior sobrevive a uma falha de leitura na volta nova")
# volta que nao anda para frente (reinicio do contador) nao vira 'volta anterior'
ck = v.Coletor()
for i in range(21): ck.atualizar(ent(i * 0.1, volta=5, hibrido={"carga": 0.6, "deploy": None, "ativo": True}))
rk = ck.atualizar(ent(2.1, volta=1, hibrido={"carga": 0.9, "deploy": None, "ativo": True}))
confere(rk["hibrido"]["ult_carga"] is None, "hibrido: contador de voltas que volta atras (reinicio) nao grava volta anterior")
# volta curta demais (< 1 s de dados) nao sobrescreve a anterior valida
cm_ = v.Coletor()
for i in range(21): cm_.atualizar(ent(i * 0.1, volta=1, hibrido={"carga": 0.8, "deploy": None, "ativo": True}))
cm_.atualizar(ent(2.1, volta=2, hibrido={"carga": 0.5, "deploy": None, "ativo": True}))
cm_.atualizar(ent(2.2, volta=3, hibrido={"carga": 0.3, "deploy": None, "ativo": True}))
confere(abs(cm_.resumo(ent(2.3, volta=3, hibrido={"carga": 0.3, "ativo": True}))["hibrido"]["ult_carga"] - 0.8) < 1e-9, "hibrido: volta com menos de 1 s de dados nao sobrescreve a anterior valida")
# sem 'volta' no dado: nada quebra
cn = v.Coletor()
for i in range(15): rn = cn.atualizar(ent(i * 0.1, volta=None, hibrido={"carga": 0.6, "deploy": None, "ativo": True}))
confere(rn["hibrido"] is not None and rn["hibrido"]["ult_carga"] is None, "hibrido: sem numero de volta nao quebra nem inventa volta anterior")

# =====================================================================================================================
# Build z - P2.1: media geral da eficiencia = consumo total / distancia total x 100 (nao media das celulas)
# =====================================================================================================================
def media_ger(cc, marcha_cc=None):
    return cc.resumo(ent(0))["marcha"]["media"]
# (a) caso da auditoria: 9,9 s a 50 L/100 km e 0,1 s a 150 L/100 km, em colunas de RPM diferentes -> 51, nao 100
za = v.Coletor()
for i in range(100):                                       # 10 Hz, 10 s; vel 200 km/h
    t = i * 0.1
    lento = i < 99
    za.atualizar(ent(t, rpm=7000 if lento else 4000, lh=100.0 if lento else 300.0, vel=200.0, marcha=4))
ra = za.resumo(ent(0))["marcha"]
confere(ra["media"] is not None and abs(ra["media"] - 51.0) < 0.6, f"P2.1: media geral temporal ({ra['media']:.1f} L/100 km, esperado ~51, nao 100)")
confere(ra["minimo"] is not None and ra["maximo"] is not None and ra["maximo"] > ra["minimo"] + 50, "P2.1: celulas individuais (melhor/pior) preservadas")
# (b) velocidades, duracoes e frequencias diferentes: litros totais / km totais, a 5 e a 60 Hz, em duas marchas
def cenario(hz, jit=0.0, semente=3):
    r_ = random.Random(semente); cc = v.Coletor(); t = 0.0; L = 0.0; K = 0.0; ant = None
    trechos = [(3.0, 3, 6500, 80.0, 120.0), (1.0, 4, 7500, 250.0, 240.0), (0.5, 5, 5000, 40.0, 150.0), (4.0, 3, 7800, 150.0, 90.0)]
    fim = sum(x[0] for x in trechos); inicio = 0.0
    while t <= fim:
        ac = 0.0; j = 0
        for dur, mar, rpm, lh, vel in trechos:
            if t < ac + dur or dur is trechos[-1][0]:
                break
            ac += dur; j += 1
        dur, mar, rpm, lh, vel = trechos[min(j, len(trechos) - 1)]
        cc.atualizar(ent(t, rpm=rpm, lh=lh, vel=vel, marcha=mar))
        if ant is not None:
            dt = t - ant[0]
            if 0 < dt <= 0.5:
                L += ant[1] / 3600.0 * dt; K += ant[2] / 3600.0 * dt
        ant = (t, lh, vel) if True else None
        # a amostra que chega em t aplica o dt desde a anterior com os valores ATUAIS (mesma regra do Coletor)
        t += (1.0 / hz) * (1.0 + r_.uniform(-jit, jit))
    return cc, fim
for hz, jit in ((5, 0.0), (10, 0.2), (30, 0.2), (60, 0.25)):
    cc, fim = cenario(hz, jit)
    # referencia analitica: integral por trecho (tempo dentro de cada trecho, valores constantes)
    trechos = [(3.0, 80.0, 120.0), (1.0, 250.0, 240.0), (0.5, 40.0, 150.0), (4.0, 150.0, 90.0)]
    ref = sum(d * lh / 3600.0 for d, lh, _ in trechos) / sum(d * vel / 3600.0 for d, _, vel in trechos) * 100.0
    got = media_ger(cc)
    confere(got is not None and abs(got - ref) / ref < 0.06, f"P2.1: {hz} Hz jitter {int(jit * 100)}% duracoes/velocidades diferentes: {got:.1f} vs {ref:.1f} L/100 km")
# (c) a media nao depende da taxa: 5 Hz == 60 Hz para o mesmo sinal
c5_, _ = cenario(5); c60_, _ = cenario(60)
confere(abs(media_ger(c5_) - media_ger(c60_)) / media_ger(c60_) < 0.08, f"P2.1: media geral igual a 5 e 60 Hz ({media_ger(c5_):.1f} vs {media_ger(c60_):.1f})")
# (d) filtros preservados: < 20 km/h, acelerador parcial, invalidos e pausa nao entram na media geral
zf = v.Coletor()
for i in range(21):
    zf.atualizar(ent(i * 0.1, lh=100.0, vel=200.0, marcha=4))                    # 50 L/100 km (entra)
    zf.atualizar(ent(i * 0.1 + 0.05, lh=900.0, vel=10.0, marcha=4))              # < 20 km/h (fora)
zf.atualizar(ent(60.0, lh=900.0, vel=100.0, marcha=4))                           # fim de pausa longa (fora)
confere(abs(media_ger(zf) - 50.0) < 1.0, f"P2.1: filtros (vel minima, pausa) valem na media geral ({media_ger(zf):.1f})")
confere(v.Coletor().resumo(ent(0))["marcha"]["media"] is None, "P2.1: sem dados -> media None")
# (e) troca de carro (rpm_max) zera tambem a media geral
zc = v.Coletor()
for i in range(10): zc.atualizar(ent(i * 0.1, lh=100.0, vel=200.0, marcha=4, rpm_max=8000.0))
zc.atualizar(ent(1.0, lh=100.0, vel=200.0, marcha=4, rpm_max=9500.0))
confere(zc.resumo(ent(0))["marcha"]["media"] is None or zc._marcha_glob[2] <= 0.2, "P2.1: troca de carro (rpm_max) zera a media geral")
# (f) demonstracao coerente
dm = v.exemplo(1.0)["marcha"]
confere(dm["media"] is not None and dm["minimo"] <= dm["media"] <= dm["maximo"], "P2.1: demo com media entre melhor e pior")

# =====================================================================================================================
# Build z - P2.2: 'RPM maximo observado' (nao 'rpm_troca')
# =====================================================================================================================
zm = v.Coletor()
for i in range(10): zm.atualizar(ent(i * 0.1, rpm=6000 + 100 * i, lh=100.0, vel=200.0, marcha=3))         # sem NENHUMA troca de marcha
mm = next(m for m in zm.resumo(ent(0))["marcha"]["marchas"] if m["marcha"] == 3)
confere(mm["rpm_max"] == 6900 and "rpm_troca" not in mm, "P2.2: campo 'rpm_max' = maior RPM observado a acelerador pleno, sem troca de marcha")
zn = v.Coletor()
for i in range(10): zn.atualizar(ent(i * 0.1, rpm=7000, ace=0.5, lh=100.0, vel=200.0, marcha=3))
confere(all(m.get("rpm_max") is None for m in zn.resumo(ent(0))["marcha"]["marchas"]), "P2.2: acelerador parcial nao registra RPM maximo")

# =====================================================================================================================
# Build aa - redesenho: dados novos de apresentacao (trilha do mapa, RPM atual, consumo agora da marcha)
# =====================================================================================================================
ta = v.Coletor()
seq = [(5000, 0.4), (5000, 0.4), (5600, 0.5), (6200, 0.7), (6800, 0.9), (6800, 0.9)]
for i, (rp, ac) in enumerate(seq): rta = ta.atualizar(ent(i * 0.1, rpm=rp, ace=ac, lh=100.0))
tr = rta["vazao"]["trilha"]
confere(tr == [(4, 4), (5, 5), (7, 6), (9, 7)], f"trilha: so celulas distintas em sequencia, sem repetir a mesma ({tr})")
confere(all(isinstance(x, tuple) and len(x) == 2 for x in tr), "trilha: pares (linha, coluna)")
rta2 = ta.atualizar(ent(10.0, rpm=6800, ace=0.9, lh=100.0))
confere(rta2["vazao"]["trilha"] == [(9, 7)], "trilha: o que passou de 4 s some (sobra a celula atual)")
tb = v.Coletor()
for i in range(10): tb.atualizar(ent(i * 0.1, rpm=5000 + 100 * i, ace=0.5, lh=100.0, rpm_max=8000.0))
tb.atualizar(ent(1.0, rpm=5000, ace=0.5, lh=100.0, rpm_max=9500.0))
confere(len(tb.resumo(ent(1.0, rpm_max=9500.0))["vazao"]["trilha"]) <= 1, "trilha: troca de carro (rpm_max) zera a trilha")
tc = v.Coletor()
for i in range(500): tc.atualizar(ent(i * 0.05, rpm=3000 + (i % 40) * 120, ace=(i % 11) / 10.0, lh=100.0))
confere(len(tc._trilha) <= v.TRILHA_MAX, f"trilha: memoria limitada ({len(tc._trilha)} <= {v.TRILHA_MAX})")
td = v.Coletor()
for i in range(5): td.atualizar(ent(i * 0.1, lh=100.0, valido=False))
confere(td.resumo(ent(0.5))["vazao"]["trilha"] == [], "trilha: amostras fora da pista nao entram")
rv = v.Coletor().resumo(ent(1.0, rpm=6200, mapa_motor=3))["vazao"]
confere(rv["rpm"] == 6200 and rv["mapa_motor"] == 3, "vazao: entrega RPM atual e mapa do motor quando o jogo informa")
confere(v.Coletor().resumo(ent(1.0))["vazao"]["mapa_motor"] is None, "vazao: sem mapa do motor -> None (a janela esconde o campo)")
# consumo agora da marcha (L/100 km instantaneo, so em condicao elegivel)
mg = v.Coletor().resumo(ent(1.0, ace=1.0, lh=100.0, vel=200.0, marcha=3))["marcha"]
confere(abs(mg["agora_l100"] - 50.0) < 1e-9 and mg["rpm"] is not None, "marcha: consumo instantaneo (L/100 km) a acelerador pleno")
confere(v.Coletor().resumo(ent(1.0, ace=0.5, lh=100.0, vel=200.0, marcha=3))["marcha"]["agora_l100"] is None, "marcha: acelerador parcial -> sem consumo instantaneo")
confere(v.Coletor().resumo(ent(1.0, ace=1.0, lh=100.0, vel=10.0, marcha=3))["marcha"]["agora_l100"] is None, "marcha: abaixo de 20 km/h -> sem consumo instantaneo")
confere(v.Coletor().resumo(ent(1.0, ace=1.0, lh=float("nan"), vel=200.0, marcha=3))["marcha"]["agora_l100"] is None, "marcha: dado invalido -> sem consumo instantaneo")
# a apresentacao nao altera os numeros ja auditados
ex = v.exemplo(2.0)
confere(ex["marcha"]["media"] is not None and len(ex["vazao"]["trilha"]) >= 2 and ex["vazao"]["mapa_motor"] == 3, "demo: trilha e mapa do motor presentes")

# =====================================================================================================================
# Build ac - Destino do combustivel: celula atual, parcela parcial, RPM maximo
# =====================================================================================================================
da = v.Coletor()
for i in range(20): da.atualizar(ent(i * 0.1, rpm=7000, ace=1.0, lh=120.0))                      # a fundo
for i in range(20, 30): da.atualizar(ent(i * 0.1, rpm=5000, ace=0.5, lh=60.0))                   # parcial (MID)
for i in range(30, 33): rd = da.atualizar(ent(i * 0.1, rpm=3500, ace=0.0, lh=5.0))               # solto
d_ = rd["destino"]
confere(d_["atual"] == ("COAST", v.coluna_rpm(3500, 8000)), f"destino: celula atual = faixa de acelerador + coluna de RPM ({d_['atual']})")
confere(d_["parcial"] is not None and abs(d_["parcial"] - sum(f["parcela"] for f in d_["faixas"] if f["nome"] in ("HIGH", "MID", "LOW"))) < 1e-9, "destino: parcela parcial = alto + medio + baixo")
soma = sum(f["parcela"] for f in d_["faixas"])
confere(abs(soma - 1.0) < 1e-9, "destino: parcelas somam 100 %")
confere(d_["rpm_max"] == 8000.0, "destino: entrega o RPM maximo do carro")
confere(v.Coletor().resumo(ent(1.0))["destino"]["parcial"] is None, "destino: sem dados, parcial None")
confere(v.Coletor().resumo({"agora": 1.0})["destino"]["atual"] is None, "destino: sem RPM/acelerador, sem celula atual")
confere(v.exemplo(1.0)["destino"]["atual"] is not None, "demo: destino com celula atual")

print(f"\n{_ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
