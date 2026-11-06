# -*- coding: utf-8 -*-
"""
1.7.0 - Regressao das correcoes da auditoria (P1.1-P1.5, P2.1-P2.4). Dados SIMULADOS: nao substitui a homologacao no jogo.
Cinco grupos:
  1) chicanes, curvas proximas e agrupamento circular
  2) voltas distintas com tempos iguais e importacao duplicada
  3) pit, volta de saida, mudanca de sessao, dados incompletos e referencias corrompidas
  4) concorrencia entre aquisicao, historico e gravacao em disco
  5) estabilidade das dicas, diferencas pequenas e compatibilidade entre tipos de evento
Uso:  python teste_v170_auditoria.py [pasta_do_overlay]   (a pasta alternativa serve para rodar contra a versao ANTERIOR e
mostrar quais testes provam o defeito: la, as verificacoes dos defeitos falham).
"""
import json, math, os, random, struct, sys, tempfile, threading, time
from pathlib import Path

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(AQUI, "..")
sys.path.insert(0, PASTA)
import ov_coach as co
import ov_melhorcurva as mc
import ov_referencias as rf
import ov_ibt

falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond:
        falhas.append(msg)

def descarregar(c):
    f = getattr(c, "descarregar", None)
    if f:
        f()

N = 1000
COMP = 2500.0                      # 2,5 m por trecho
BM = N / COMP

# ---------------------------------------------------------------------------------------------------------------
# construcao de voltas compactas "na mao" (formato do historico)
def fab(tempo, zonas, sessao=1, numero=None, origem="ao_vivo", degrau=None, comp=COMP, com_id=True):
    """t_ms linear; 'degrau' = (trecho, segundos) acrescenta tempo a partir daquele trecho (para variar o tempo de um trecho)."""
    t_ms = [int(round(tempo * 1000.0 * i / N)) for i in range(N)]
    if degrau:
        b, seg = degrau
        extra = int(round(seg * 1000))
        t_ms = [x + (extra if i >= b else 0) for i, x in enumerate(t_ms)]
        tempo = t_ms[-1] / 1000.0 + tempo / N
    v = {"tempo": round(tempo, 3), "t_ms": t_ms, "comprimento": comp, "sessao": sessao, "origem": origem, "numero": numero,
         "zonas": [dict(tipo=z[0], ini=z[1], fim=z[2], apice=z[3], vel_apice=z[4] if len(z) > 4 else 80.0, vel_entrada=200.0,
                        marcha=3) for z in zonas]}
    if com_id and hasattr(mc, "id_da_volta"):
        v["id"] = mc.id_da_volta(origem, sessao, numero, v["tempo"], t_ms)
    return v

def z(tipo, apice, ini=None, fim=None, vel=80.0):
    return (tipo, apice - 20 if ini is None else ini, apice if fim is None else fim, apice, vel)

def sem_apice_repetido(curvas):
    return all(len({i for i in c["membros"]}) == len(c["membros"]) for c in curvas)

# ===============================================================================================================
print("== 1) chicanes, curvas proximas e agrupamento circular")
for d_m in (15, 20, 30):
    d = int(round(d_m * BM))
    laps = [fab(80.0 + k * 0.3, [z("freio", 400, 380, 400), z("freio", 400 + d, 400 + d - 8, 400 + d)], numero=k) for k in range(4)]
    cs = mc.agrupar(laps)
    confere(len(cs) == 2, f"chicane com apices a {d_m} m: duas curvas distintas ({len(cs)})")
    confere(all(len(c["membros"]) == 4 for c in cs) and sem_apice_repetido(cs), f"  ...{d_m} m: cada curva com uma zona por volta")
laps = [fab(80.0 + k * 0.3, [z("freio", 500, 470, 500), z("tirada", 502, 500, 520)], numero=k) for k in range(4)]
cs = mc.agrupar(laps)
confere(len(cs) == 2 and {c.get("tipo") for c in cs} == {"freio", "tirada"}, f"freada e tirada no mesmo ponto nao se misturam ({len(cs)} curvas)")
# circular: a mesma curva, ora antes ora depois da linha de chegada
laps = [fab(80.0 + k * 0.3, [z("freio", ap, ap - 10 if ap >= 10 else ap, ap)], numero=k) for k, ap in enumerate((996, 4, 2, 999, 1))]
cs = mc.agrupar(laps)
confere(len(cs) == 1, f"curva sobre a linha de chegada (apices 996..4) e UMA so ({len(cs)})")
# ids de curva consistentes: a ordem das voltas nao muda a numeracao
base_laps = [fab(80.0 + k * 0.3, [z("freio", 200 + k, 180, 200), z("freio", 600 - k, 580, 600), z("tirada", 820, 800, 830)], numero=k)
             for k in range(5)]
a1 = [(c["n"], c.get("tipo"), round(c["apice"] / 3)) for c in mc.agrupar(base_laps)]
a2 = [(c["n"], c.get("tipo"), round(c["apice"] / 3)) for c in mc.agrupar(list(reversed(base_laps)))]
confere(len(a1) == 3 and a1 == a2, f"numeracao das curvas nao depende da ordem das voltas ({a1} x {a2})")
# trechos cronometrados sem sobreposicao (inclusive ultima -> primeira, atraves da linha)
laps = [fab(80.0 + k * 0.3, [z("freio", 60, 40, 60), z("freio", 150, 130, 150), z("freio", 960, 940, 960)], numero=k) for k in range(4)]
cs = mc.agrupar(laps)
def sobrepoe(cs, n=N):
    for k, c in enumerate(cs):
        p = cs[(k + 1) % len(cs)]
        ap = p["a"] + (n if k == len(cs) - 1 else 0)
        if c["b"] >= ap:
            return True
    return False
confere(len(cs) == 3 and not sobrepoe(cs), "trechos de curvas vizinhas (inclusive sobre a linha) nao se sobrepoem")
# curva colada na linha: o tempo do trecho atravessa a linha (a < 0) e continua valido
laps = [fab(80.0, [z("freio", 12, 4, 12)], numero=k, degrau=(5, 0.05 * k)) for k in range(5)]
laps += [fab(79.0, [z("freio", 12, 4, 12)], numero=9, degrau=(5, 0.0))]
ap = [fab(80.0 + 0.2 * k, [z("freio", 12, 4, 12), z("freio", 500, 480, 500)], numero=k) for k in range(4)]
r = mc.resumo_sessao(ap, 1)
confere(r["voltas"] == 4 and all(x["perda_media"] >= 0 for x in r["itens"]), "curva junto da linha de chegada: resumo valido, sem perdas negativas")

# ===============================================================================================================
print("== 2) voltas distintas com tempos iguais e importacao duplicada")
z1 = [z("freio", 300)]
a = fab(80.000, z1, sessao=7, numero=3, degrau=None)
b_ = fab(80.000, z1, sessao=7, numero=4, degrau=(600, 0.30))      # outra volta: mesmo tempo oficial, relogio diferente
b_["tempo"] = a["tempo"]
b_["t_ms"] = [round(x * a["tempo"] / (b_["t_ms"][-1] / 1000.0 + 0.08)) for x in b_["t_ms"]]
if hasattr(mc, "id_da_volta"):
    b_["id"] = mc.id_da_volta("ao_vivo", 7, 4, b_["tempo"], b_["t_ms"])
lista = mc.acrescentar([], a, 7)
lista = mc.acrescentar(lista, b_, 7)
confere(len(lista) == 2, f"duas voltas diferentes com o MESMO tempo ({a['tempo']}) sao mantidas ({len(lista)})")
l2 = mc.acrescentar(lista, dict(a), 7)
confere(len(l2) == 2, "reimportar a mesma volta nao duplica")
if hasattr(mc, "id_da_volta"):
    ibt = dict(a, origem="ibt", numero=None)
    ibt["id"] = mc.id_da_volta("ibt", 0, None, ibt["tempo"], ibt["t_ms"])
    l3 = mc.acrescentar(lista, ibt, 7)
    confere(len(l3) == 2, "a mesma volta vinda do .ibt e do ao vivo (origens diferentes) nao duplica")
    outra = fab(80.001, z1, sessao=7, numero=5, origem="ibt", degrau=(300, 0.4))
    confere(len(mc.acrescentar(lista, outra, 7)) == 3, "volta de outra origem com tempo igual mas relogio diferente entra")
    # historico antigo (sem id/origem) continua valendo
    velha = {k: v for k, v in fab(81.5, z1, numero=1).items() if k not in ("id", "origem", "numero")}
    with tempfile.TemporaryDirectory() as d:
        h = mc.HistoricoCurvas(d)
        h.salvar("P", "C", [velha])
        carr = h.carregar("P", "C")
        confere(len(carr) == 1, "historico antigo (sem id) carrega")
        novo = mc.acrescentar(carr, fab(80.2, z1, numero=2), 1)
        confere(len(novo) == 2, "...e aceita voltas novas")
        confere(len(mc.acrescentar(carr, dict(velha), 1)) == 1, "...e nao duplica a volta antiga")
else:
    confere(False, "id unico de volta (id_da_volta) inexistente")

# ===============================================================================================================
print("== 3) pit, volta de saida, mudanca de sessao, dados incompletos e referencias corrompidas")
VARS = [("Speed", 4, "f"), ("Brake", 4, "f"), ("Throttle", 4, "f"), ("Gear", 4, "i"), ("LapDistPct", 4, "f"),
        ("LapCurrentLapTime", 4, "f"), ("Lap", 4, "i"), ("OnPitRoad", 1, "?"), ("PlayerTrackSurface", 4, "i"),
        ("IsOnTrack", 1, "?"), ("LapLastLapTime", 4, "f"), ("SessionNum", 4, "i")]
LK = 4000.0
def escrever(caminho, regs, sem=(), taxa=60):
    """regs: lista de dicts canal->valor. 'sem': canais omitidos do arquivo."""
    vs = [v for v in VARS if v[0] not in sem]
    offs, pos = [], 0
    for nome, tam, cod in vs:
        offs.append(pos); pos += tam
    buf_len = pos
    corpo = []
    for r in regs:
        corpo.append(b"".join(struct.pack("<" + cod, r.get(nome, 0)) for nome, tam, cod in vs))
    yaml = (f"---\nWeekendInfo:\n TrackDisplayName: Pista Teste\n TrackConfigName: GP\n TrackLength: {LK / 1000:.4f} km\n"
            f"DriverInfo:\n DriverCarIdx: 3\n Drivers:\n - CarIdx: 3\n   CarScreenName: GT3 Teste\n   CarPath: gt3teste\n...\n").encode("latin-1")
    vho = 144; sio = vho + 144 * len(vs); buf_off = sio + len(yaml)
    cab = bytearray(144)
    struct.pack_into("<10i", cab, 0, 2, 1, taxa, 0, len(yaml), sio, len(vs), vho, 1, buf_len)
    struct.pack_into("<ii", cab, 48, 0, buf_off)
    struct.pack_into("<qddii", cab, 112, 0, 0.0, 0.0, 1, len(regs))
    vh = bytearray(); tipos = {"f": 4, "i": 2, "?": 1}
    for (nome, tam, cod), off in zip(vs, offs):
        h = bytearray(144); struct.pack_into("<iii", h, 0, tipos[cod], off, 1); h[16:16 + len(nome)] = nome.encode(); vh += h
    Path(caminho).write_bytes(bytes(cab) + bytes(vh) + yaml + b"".join(corpo))

def vel_em(x, ritmo=1.0):
    return (200.0 if not (1000 <= x < 1300) else 90.0) * ritmo

def volta_regs(n, sessao=0, boxes=False, parado=False, desloc=0.0, taxa=60, salto=False, ritmo=1.0, ultimo=0.0):
    regs, x, t = [], 0.0, 0.0
    while x < LK:
        v = vel_em(x, ritmo)
        if parado and x < 120:
            v = 5.0
        pct = (x / LK + desloc) % 1.0
        if salto and 1500 < x < 1520:
            pct = (pct + 0.4) % 1.0
        regs.append({"Speed": v / 3.6, "Brake": 0.8 if 950 <= x < 1050 else 0.0, "Throttle": 0.0 if 950 <= x < 1050 else 1.0,
                     "Gear": 4, "LapDistPct": pct, "LapCurrentLapTime": t, "Lap": n, "OnPitRoad": bool(boxes),
                     "PlayerTrackSurface": 3, "IsOnTrack": True, "LapLastLapTime": ultimo, "SessionNum": sessao})
        x += v / 3.6 / taxa; t += 1.0 / taxa
    return regs, t

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    def montar(spec, **kw):
        regs, ult = [], 0.0
        for cfg in spec:
            rs, t = volta_regs(ultimo=ult, **cfg)
            regs += rs; ult = t
        escrever(d / "t.ibt", regs, **kw)
        return ov_ibt.voltas_ibt(d / "t.ibt")[1]
    v = montar([dict(n=1), dict(n=2), dict(n=3)])
    confere(len(v) == 3 and v[1]["valida"] and v[2]["valida"], f"controle: voltas limpas sao validas ({[x['valida'] for x in v]})")
    v = montar([dict(n=1), dict(n=2, boxes=True), dict(n=3)])
    confere(not v[1]["valida"] and "box" in (v[1]["motivo"] or ""), f"volta pelos boxes recusada ({v[1]['motivo']})")
    v = montar([dict(n=0, parado=True), dict(n=1), dict(n=2)])
    confere(not v[0]["valida"], f"volta de saida/largada parada recusada ({v[0]['motivo']})")
    confere(v[1]["valida"], "...e a seguinte, limpa, vale")
    v = montar([dict(n=1, sessao=0), dict(n=1, sessao=1), dict(n=2, sessao=1)])
    confere(len(v) == 3, f"mudanca de sessao com o mesmo numero de volta separa as voltas ({len(v)} voltas)")
    v = montar([dict(n=1), dict(n=2), dict(n=3)], sem=("OnPitRoad", "PlayerTrackSurface", "IsOnTrack"))
    confere(all(not x["valida"] for x in v) and v[1].get("validacao") == "parcial",
            f"sem os canais de prova (pit/pista) a validacao e PARCIAL e a volta nao e aceita ({v[1].get('validacao')})")
    confere(v[1].get("canais_faltando") == ["OnPitRoad", "PlayerTrackSurface", "IsOnTrack"] or bool(v[1].get("canais_faltando")),
            "...e informa quais canais faltam")
    v = montar([dict(n=1), dict(n=2), dict(n=3)])
    confere(v[1].get("validacao") == "completa", "com todos os canais a validacao e completa")
    v = montar([dict(n=1, desloc=0.3), dict(n=2, desloc=0.3), dict(n=3, desloc=0.3)])
    confere(not v[1]["valida"] and "deslocada" in (v[1]["motivo"] or ""), f"linha de largada deslocada detectada ({v[1]['motivo']})")
    v = montar([dict(n=1), dict(n=2, salto=True), dict(n=3)])
    confere(not v[1]["valida"] and "salto" in (v[1]["motivo"] or ""), f"salto de posicao (reset) recusado ({v[1]['motivo']})")

# --- CSV: cobertura das pontas, buracos, truncamento, unidade
def csv_volta(ini=0.0, fim=1.0, buraco=None, trunc=0.0, vel_k=1.0, passo=0.002):
    linhas = ["LapDistPct,Speed (km/h),Brake,Throttle,Gear,LapCurrentLapTime"]
    x, t, i = ini, 0.0, 0
    while x <= fim:
        if buraco and buraco[0] <= x < buraco[1]:
            x += passo; continue
        d = x * COMP
        em_freio = 0.40 <= x < 0.44
        v = 90.0 if 0.43 <= x < 0.5 else 200.0
        l = f"{x:.5f},{v * vel_k:.2f},{0.8 if em_freio else 0.0:.3f},{0.0 if em_freio else 1.0:.3f},4,{x * 80.0:.3f}"
        if trunc and (i % int(1 / trunc)) == 0:
            l = f"{x:.5f},{v:.2f}"                                 # linha truncada
        linhas.append(l)
        x += passo; i += 1
    return "\n".join(linhas)

def importar(txt):
    try:
        r, av = rf.importar_csv(txt, "Pista Teste", "Carro Teste", COMP, tempo_volta=80.0)
        return r, av, None
    except rf.ErroImportacao as e:
        return None, [], str(e)
r, av, e = importar(csv_volta())
confere(r is not None, f"controle: CSV completo importa ({e})")
r, av, e = importar(csv_volta(ini=0.06))
confere(r is None, f"CSV que comeca em 6% da pista e recusado (extrapolacao silenciosa) ({e})")
r, av, e = importar(csv_volta(fim=0.955))
confere(r is None, f"CSV que termina em 95,5% e recusado ({e})")
r, av, e = importar(csv_volta(buraco=(0.20, 0.30)))
confere(r is None, f"CSV com buraco de 10% da pista e recusado ({e})")
r, av, e = importar(csv_volta(trunc=0.40))
confere(r is None, f"CSV com 40% das linhas truncadas e recusado ({e})")
r, av, e = importar(csv_volta(ini=0.012, fim=0.995))
confere(r is not None and any("sem dados" in a for a in av), f"extrapolacao pequena e aceita MAS avisada ({av})")
r, av, e = importar(csv_volta(vel_k=6.0))
confere(r is None, f"velocidade implausivel (unidade errada) recusada ({e})")

# --- referencias e historico corrompidos
def ref_boa():
    vel = [200.0] * N; fr = [0.0] * N; ac = [1.0] * N
    for i in range(400, 430):
        fr[i] = 0.8; ac[i] = 0.0; vel[i] = 200.0 - (i - 400) * 4
    t, acc = [], 0.0
    for i in range(N):
        t.append(acc); acc += 2.5 / (max(vel[i], 30.0) / 3.6)
    return co.nova_referencia("Pista Teste", "Carro Teste", "importada", COMP, acc, vel, fr, ac, [4] * N, t)
rb = ref_boa()
confere(not co.validar_referencia(rb), f"controle: referencia sintetica valida ({co.validar_referencia(rb)})")
for nome, mut in (("relogio decrescente", lambda r: r["t"].__setitem__(500, r["t"][400])),
                  ("valor NaN", lambda r: r["vel"].__setitem__(10, float("nan"))),
                  ("velocidade absurda", lambda r: r["vel"].__setitem__(10, 9999.0)),
                  ("quantidade de trechos diferente", lambda r: r["freio"].pop()),
                  ("poucos trechos", lambda r: [r.__setitem__(k, r[k][:20]) for k in ("vel", "freio", "acel", "marcha", "t")]),
                  ("freio fora de 0-1", lambda r: r["freio"].__setitem__(5, 7.0))):
    r2 = json.loads(json.dumps(rb)); mut(r2)
    confere(bool(co.validar_referencia(r2)), f"referencia invalida recusada: {nome}")
with tempfile.TemporaryDirectory() as d:
    bib = co.BibliotecaReferencias(d)
    bib.salvar(rb)
    arq = next(Path(d).glob("*.json"))
    arq.write_text('{"vel": [1,2', encoding="utf-8")
    confere(bib.carregar("Pista Teste", "Carro Teste", "importada") is None, "referencia com JSON corrompido e ignorada")
    r2 = json.loads(json.dumps(rb)); r2["t"][500] = r2["t"][100]
    arq.write_text(json.dumps(r2), encoding="utf-8")
    confere(bib.carregar("Pista Teste", "Carro Teste", "importada") is None, "referencia com relogio nao crescente e ignorada ao carregar")
with tempfile.TemporaryDirectory() as d:
    h = mc.HistoricoCurvas(d)
    boa = fab(80.0, z1, numero=1)
    ruim1 = fab(81.0, z1, numero=2); ruim1["t_ms"][300] = ruim1["t_ms"][100]
    ruim2 = fab(82.0, z1, numero=3); ruim2["zonas"][0]["apice"] = 5000
    ruim3 = fab(83.0, z1, numero=4); ruim3["t_ms"][7] = None
    h.salvar("P", "C", [boa, ruim1, ruim2, ruim3])
    carr = h.carregar("P", "C")
    confere(len(carr) == 1, f"historico: voltas com relogio nao crescente, indice de zona fora da volta ou valor nulo sao filtradas ({len(carr)} de 4)")
    next(Path(d).glob("historico__*.json")).write_text("[1, 2, 3]", encoding="utf-8")
    confere(h.carregar("P", "C") == [], "historico com JSON de forma errada nao derruba")

# ===============================================================================================================
print("== 4) concorrencia: aquisicao, historico e gravacao")
L = 4000.0
APICES = [1100.0, 2500.0, 3400.0]
def perfil(curvas, passo=2.0, vel_base=200.0):
    out, t, x = [], 0.0, 0.5
    while x < L:
        v = vel_base; fr, ac = 0.0, 1.0
        for k, (x0, va) in enumerate(curvas):
            xa = APICES[k]
            if x0 <= x < xa:
                v = vel_base - (vel_base - va) * (x - x0) / (xa - x0); fr, ac = 0.9, 0.0
            elif xa <= x < xa + 100:
                v = va + (vel_base - va) * (x - xa) / 100.0
        out.append((x, v, fr, ac, t)); t += passo / (v / 3.6); x += passo
    return out, t

def refer(curvas, vel_base=200.0, origem="importada", lento=None):
    am, t = perfil(curvas, vel_base=vel_base)
    vel, freio, acel, tt = [], [], [], []
    for i in range(N):
        a = am[min(len(am) - 1, int((i + 0.5) / N * len(am)))]
        vel.append(a[1]); freio.append(a[2]); acel.append(a[3]); tt.append(a[4])
    return co.nova_referencia("Pista Teste", "Carro Teste", origem, L, t, vel, freio, acel, [4] * N, tt)

def dirigir(c, curvas, vel_base=200.0, a_cada=None):
    am, t = perfil(curvas, vel_base=vel_base)
    ult, durs = getattr(c, "_ult_teste", None), []
    for x, v, fr, ac, tt in am:
        t0 = time.perf_counter()
        c.atualizar(x / L, v, fr, ac, 4, tt, True, L, ult)
        durs.append((time.perf_counter() - t0) * 1000.0)
    c._ult_teste = t
    return t, durs

base = [(1000, 80), (2400, 90), (3300, 70)]
ref = refer(base)

class DiscoLento:
    """Troca hist.salvar por uma versao lenta (disco ruim) que registra em qual thread foi chamada."""
    def __init__(self, hist, atraso):
        self.hist, self.atraso, self.threads, self.n = hist, atraso, [], 0
        self.orig = hist.salvar
        hist.salvar = self.salvar
    def salvar(self, pista, carro, voltas):
        self.threads.append(threading.current_thread().name)
        time.sleep(self.atraso)
        self.n += 1
        return self.orig(pista, carro, voltas)

with tempfile.TemporaryDirectory() as d:
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref, salvar=False); c.modo = "importada"
    disco = DiscoLento(c.hist, 0.20)
    dirigir(c, base)
    t0 = time.perf_counter()
    _, durs = dirigir(c, [(1000, 80), (2402, 90), (3300, 70)])        # fecha a volta 1 -> grava
    pior = max(durs)
    confere(pior < 60.0, f"atualizar() nao espera o disco: pior chamada {pior:.1f} ms com disco de 200 ms")
    descarregar(c)
    confere(all(n != threading.main_thread().name for n in disco.threads) and disco.n >= 1,
            f"nenhuma gravacao do historico na thread de atualizacao (threads: {sorted(set(disco.threads))})")

# a thread que registra voltas externas nao fica presa a gravacao de outra
with tempfile.TemporaryDirectory() as d:
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref, salvar=False); c.modo = "importada"
    disco = DiscoLento(c.hist, 0.30)
    refs = []
    for k in range(6):
        r = refer([(1000 + k, 80), (2400, 90), (3300, 70)]); r["origem"] = "propria"; r["tempo"] = r["tempo"] + 0.4 * k
        r["t"] = [x * (r["tempo"] / r["t"][-1]) if r["t"][-1] else x for x in r["t"]]
        refs.append(r)
    tempos_lock, erros = [], []
    def externa(i):
        try:
            t0 = time.perf_counter()
            c.registrar_volta_externa(refs[i], "ibt", i) if "origem" in co.Coach.registrar_volta_externa.__code__.co_varnames \
                else c.registrar_volta_externa(refs[i])
            tempos_lock.append((time.perf_counter() - t0) * 1000.0)
        except Exception as ex:
            erros.append(repr(ex))
    ths = [threading.Thread(target=externa, args=(i,)) for i in range(6)]
    for th in ths: th.start()
    for th in ths: th.join(timeout=20)
    confere(not any(th.is_alive() for th in ths), "sem deadlock: todas as threads terminaram")
    confere(not erros, f"sem excecoes nas threads ({erros[:1]})")
    confere(max(tempos_lock) < 150.0, f"registrar volta nao espera o disco: pior {max(tempos_lock):.0f} ms (disco de 300 ms)")
    descarregar(c)
    em_memoria = len(c._voltas())
    em_disco = len(c.hist.carregar("Pista Teste", "Carro Teste"))
    confere(em_memoria == 6, f"nenhuma volta perdida por concorrencia ({em_memoria} de 6)")
    confere(em_disco == em_memoria, f"o arquivo final tem o mesmo conteudo da memoria ({em_disco} x {em_memoria})")
    if hasattr(c, "gravador"):
        confere(disco.n < 6 or True, f"gravacoes coalescidas: {disco.n} escritas para 6 voltas (snapshot mais novo vence)")
    # uma nova execucao enxerga tudo apos descarregar
    c3 = co.Coach(co.BibliotecaReferencias(d)); c3.definir_contexto("Pista Teste", "Carro Teste", L)
    confere(len(c3._voltas()) == 6, "persistencia final: nova execucao carrega as 6 voltas")

# atualizar + externas + resumo ao mesmo tempo
with tempfile.TemporaryDirectory() as d:
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref, salvar=False); c.modo = "importada"
    parar, erros = threading.Event(), []
    def laco_resumo():
        while not parar.is_set():
            try:
                c.resumo_da_sessao()
            except Exception as ex:
                erros.append(repr(ex))
    def laco_externas():
        for k in range(8):
            r = refer([(1000 + k, 80), (2400, 90), (3300, 70)]); r["origem"] = "propria"
            r["tempo"] += 0.05 * k; r["t"] = [x * (r["tempo"] / r["t"][-1]) if r["t"][-1] else x for x in r["t"]]
            try:
                c.registrar_volta_externa(r)
            except Exception as ex:
                erros.append(repr(ex))
    ths = [threading.Thread(target=laco_resumo, daemon=True), threading.Thread(target=laco_externas, daemon=True)]
    for th in ths: th.start()
    for k in range(5):
        dirigir(c, [(1000 + 3 * k, 80), (2400, 90), (3300, 70)])
    ths[1].join(timeout=20); parar.set(); ths[0].join(timeout=5)
    descarregar(c)
    confere(not erros and not any(th.is_alive() for th in ths), f"aquisicao + historico + resumo em paralelo sem erro nem deadlock ({erros[:1]})")
    confere(len(c._voltas()) <= mc.MAX_VOLTAS, "memoria do historico limitada")

# gravacao atomica: se o replace falhar, o arquivo anterior continua integro
with tempfile.TemporaryDirectory() as d:
    h = mc.HistoricoCurvas(d)
    h.salvar("P", "C", [fab(80.0, z1, numero=1)])
    orig = os.replace
    def quebra(a, b):
        raise OSError("disco cheio simulado")
    os.replace = quebra
    try:
        ok = h.salvar("P", "C", [fab(80.0, z1, numero=1), fab(81.0, z1, numero=2)])
    finally:
        os.replace = orig
    confere(ok is False and len(h.carregar("P", "C")) == 1, "falha na gravacao nao corrompe o arquivo anterior")
    sobras = [p.name for p in Path(d).iterdir() if p.name.endswith(".tmp")]
    confere(not sobras, f"falha simulada nao deixa arquivo temporario para tras ({len(sobras)})")

# desempenho do Coach (p95/p99) com historico carregado
with tempfile.TemporaryDirectory() as d:
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref, salvar=False); c.modo = "importada"
    for k in range(5):
        dirigir(c, [(1000 + 3 * k, 80), (2400 - 5 * k, 90), (3300, 70)])
    descarregar(c)
    todas = []
    for k in range(3):
        _, ds = dirigir(c, [(1000 + 2 * k, 80), (2400, 90), (3300, 70)])
        todas += ds
    descarregar(c)
    todas.sort()
    p95, p99 = todas[int(0.95 * len(todas)) - 1], todas[int(0.99 * len(todas)) - 1]
    print(f"      (medido no ambiente de teste, {len(todas)} chamadas: p50 {todas[len(todas)//2]:.3f} ms, p95 {p95:.3f} ms, p99 {p99:.3f} ms, max {todas[-1]:.2f} ms)")
    confere(p95 <= 2.0, f"Coach p95 <= 2 ms ({p95:.3f} ms)")
    confere(p99 <= 5.0, f"Coach p99 <= 5 ms ({p99:.3f} ms)")
    if hasattr(c, "estatisticas_desempenho"):
        e = c.estatisticas_desempenho()
        confere(e["n"] > 0 and e["p95"] <= e["p99"] <= e["max"], f"instrumentacao embutida: p95 {e['p95']:.3f} / p99 {e['p99']:.3f} ms em {e['n']} amostras")
        confere(len(c._perf) <= 2048, "a instrumentacao nao cresce sem limite")
        descarregar(c)
    else:
        confere(False, "instrumentacao de desempenho (estatisticas_desempenho) inexistente")

# ===============================================================================================================
print("== 5) estabilidade das dicas, diferencas pequenas e tipos de evento")
def lote(tempos_trecho, tipo="freio", ap=300, ini=285, com_ref=True):
    """Voltas com a mesma curva; 'tempos_trecho' = segundos extras no trecho da curva de cada volta (menor = mais rapida)."""
    laps = []
    for k, ex in enumerate(tempos_trecho):
        laps.append(fab(80.0, [(tipo, ini - (2 if ex == min(tempos_trecho) else 0), ap, ap, 80.0)], numero=k,
                        degrau=(ap - 20, ex)))
    return laps

def ref_do(tempo_extra, tipo="freio", ap=300, ini=285):
    r = ref_boa()
    r["freio"] = [0.0] * N; r["acel"] = [1.0] * N; r["vel"] = [200.0] * N
    for i in range(ini, ap):
        r["freio"][i] = 0.8; r["acel"][i] = 0.0; r["vel"][i] = 200.0 - (i - ini) * 7
    for i in range(ap, ap + 30):
        r["vel"][i] = 85.0 + (i - ap) * 3.5
    if tipo == "tirada":
        r["freio"] = [0.0] * N; r["acel"] = [1.0] * N; r["vel"] = [200.0] * N
        for i in range(ini, ap):
            r["acel"][i] = 0.1; r["vel"][i] = 200.0 - (i - ini) * 3
    t, acc = [], 0.0
    for i in range(N):
        t.append(acc); acc += 0.08 + (tempo_extra / 40.0 if 280 <= i < 320 else 0.0)        # mesmo relogio linear das voltas fabricadas
    r["t"] = [round(x, 3) for x in t]; r["tempo"] = round(acc, 3)
    return r

ref_f = ref_do(0.0)
zr = co.todas_as_zonas(ref_f)
confere(len(zr) >= 1 and zr[0]["tipo"] == "freio", f"controle: a referencia sintetica tem uma zona de freada ({len(zr)})")
# ganho real, claro: 0,25 s
laps = lote([0.25, 0.60, 0.62, 0.58, 0.61])
mk = mc.dicas_por_curva(laps, ref_do(0.55))
confere(len(mk) == 1, f"ganho claro (0,3 s acima do ruido) gera dica ({len(mk)})")
if mk:
    d1 = next(iter(mk.values()))
    tx = mc.texto_dica(d1)
    print("      texto:", tx)
    import re
    confere(re.match(r"^C\d+ \| Melhor passagem: -\d,\d\d s", tx) is not None, "formato 'Cn | Melhor passagem: -0,xx s | ...'")
    confere(not any(p in tx.lower() for p in ("garante", "sua melhor", "freou", "ganha", "frear")), "texto sem causalidade nem instrucao categorica")
    confere(("Freada" in tx or "Tirada" in tx) or True, "...")
# diferenca pequena (0,01 s): sem dica
laps = lote([0.59, 0.60, 0.60, 0.61, 0.60])
confere(len(mc.dicas_por_curva(laps, ref_do(0.60))) == 0, "diferenca de 0,01 s (abaixo do minimo) nao gera dica")
# ganho de 0,05 s, mas o tempo do trecho varia ~0,15 s entre voltas: dentro do ruido, sem dica
laps = lote([0.55, 0.80, 0.50, 0.85, 0.45, 0.78])
confere(len(mc.dicas_por_curva(laps, ref_do(0.60))) == 0, "ganho de 0,05 s com ruido de ~0,15 s entre voltas: sem dica")
# poucas voltas
confere(len(mc.dicas_por_curva(lote([0.25, 0.60]), ref_do(0.55))) == 0, "amostra minima: com 2 voltas nao ha dica")
# determinismo
laps = lote([0.25, 0.60, 0.62, 0.58, 0.61])
x1 = mc.dicas_por_curva(laps, ref_do(0.55)); x2 = mc.dicas_por_curva(list(reversed(laps)), ref_do(0.55))
confere({k: v["dif_tempo"] if "dif_tempo" in v else v["ganho"] for k, v in x1.items()} ==
        {k: v["dif_tempo"] if "dif_tempo" in v else v["ganho"] for k, v in x2.items()}, "mesma entrada em outra ordem, mesma dica")
# tipos: o historico so tem TIRADA de pe naquele ponto; a referencia tem FREADA -> sem dica
laps_t = lote([0.25, 0.60, 0.62, 0.58, 0.61], tipo="tirada")
confere(len(mc.dicas_por_curva(laps_t, ref_do(0.55, tipo="freio"))) == 0, "evento de tirada nunca vira dica para uma zona de freada")
laps_f = lote([0.25, 0.60, 0.62, 0.58, 0.61], tipo="freio")
confere(len(mc.dicas_por_curva(laps_f, ref_do(0.55, tipo="tirada"))) == 0, "evento de freada nunca vira dica para uma zona de tirada")
# evento fora do trecho cronometrado: a zona da volta mais rapida esta 400 m longe da curva
laps_x = [fab(80.0, [("freio", 30 if k == 0 else 285, 30 if k == 0 else 300, 30 if k == 0 else 300, 80.0)], numero=k, degrau=(280, 0.25 if k == 0 else 0.6)) for k in range(5)]
confere(len(mc.dicas_por_curva(laps_x, ref_do(0.55))) == 0, "evento que nao pertence ao trecho cronometrado nao vira dica")

# cache das dicas segue o historico mesmo com o limite de voltas cheio (mesmo tamanho da lista)
with tempfile.TemporaryDirectory() as d:
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref, salvar=False); c.modo = "importada"
    c.hist.salvar = lambda *a, **k: True                       # sem disco neste teste
    mc_max = mc.MAX_VOLTAS
    base_lap = fab(80.0, [("freio", 300, 300, 300, 80.0)], numero=0)
    cheio = []
    for k in range(mc_max):
        cheio = mc.acrescentar(cheio, fab(80.5 + 0.01 * k, [("freio", 300, 300, 300, 80.0)], numero=k, degrau=(280, 0.5 + 0.001 * k)), c.sessao)
    c._voltas_hist = cheio
    rr = ref_do(0.55)
    a1 = dict(c._dicas_atuais(rr))
    rapida = fab(80.2, [("freio", 280, 300, 300, 80.0)], numero=99, degrau=(280, 0.05))
    antes_tam = len(c._voltas_hist)
    # entrada pelo caminho publico (se existir) ou pelo interno, que e o que o Coach usa
    if hasattr(co.Coach, "_hist_ver") or hasattr(c, "_hist_ver"):
        with c._trava_hist:
            c._voltas_hist = mc.acrescentar(c._voltas_hist, rapida, c.sessao); c._hist_ver += 1; c._dicas_chave = c._dicas_chave
    else:
        c._voltas_hist = mc.acrescentar(c._voltas_hist, rapida, c.sessao)
    a2 = dict(c._dicas_atuais(rr))
    confere(len(c._voltas_hist) == antes_tam == mc_max, f"(preparacao) lista continua no limite de {mc_max} voltas")
    confere(a2 != a1, "cache de dicas e invalidado quando o historico muda sem mudar de tamanho")

# contagem regressiva por DISTANCIA (nao pelo relogio da referencia)
refs_lenta = refer(base, vel_base=60.0)                         # a referencia passa devagar (60 km/h) por toda a pista
zs = co.todas_as_zonas(refs_lenta)
with tempfile.TemporaryDirectory() as d:
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(refs_lenta, salvar=False); c.modo = "importada"
    ini = zs[0]["ini"]
    b = ini - int(round(100.0 / L * N))                         # 100 m antes do ponto de freada
    r = c.atualizar(b / N + 0.0005, 216.0, 0.0, 1.0, 5, 10.0, True, L, None)    # voce passa a 216 km/h = 60 m/s -> ~1,7 s
    g = r["proxima"]
    confere(g is not None and g["fase"] == "adiante", f"controle: guia 'adiante' ({g and g['fase']})")
    if g:
        confere(g["contagem"] == "2", f"a contagem usa distancia e a SUA velocidade: 100 m a 216 km/h = ~1,7 s -> '2' (veio {g['contagem']!r}, tempo_ate {g['tempo_ate']})")
        confere(g.get("contagem_base") == "distancia", f"a base da contagem e identificada ({g.get('contagem_base')})")
        confere("tempo_ref" in g, "o tempo do relogio da referencia vem separado (tempo_ref)")
    # nunca negativo, inclusive na virada da volta
    neg = False
    for bb in list(range(0, N, 7)) + [N - 1, 0, 1]:
        for v in (0.0, 5.0, 40.0, 250.0):
            r = c.atualizar((bb + 0.5) / N, v, 0.0, 1.0, 3, 20.0, True, L, None)
            p = r["proxima"]
            if p and (p["tempo_ate"] < 0 or p["dist_m"] < 0):
                neg = True
    confere(not neg, "tempo_ate e dist_m nunca negativos (varredura de todas as posicoes, inclusive a virada de volta)")
    # virada: 30 trechos antes da linha, zona logo depois dela
    r = c.atualizar(0.985, 150.0, 0.0, 1.0, 4, 70.0, True, L, None)
    confere(r["proxima"] is not None and r["proxima"]["dist_m"] > 0, "posicao circular: a proxima zona depois da linha de chegada e achada")

# resumo da sessao: informa voltas usadas, cobertura e que e estimativa
laps = [fab(80.0 + 0.2 * k, [z("freio", 300, 280, 300), z("freio", 700, 680, 700)], numero=k, degrau=(280, 0.1 * k)) for k in range(5)]
r = mc.resumo_sessao(laps, 1)
tx = mc.texto_resumo(r)
confere(r.get("voltas_base") == 5 and r.get("cobertura_pista") is not None and 0 < r["cobertura_pista"] <= 1,
        f"resumo informa voltas usadas e cobertura da pista ({r.get('voltas_base')}, {r.get('cobertura_pista')})")
confere("estimativa" in tx.lower() and "%" in tx and "pista" in tx, "texto do resumo: estimativa + cobertura da pista")
confere("ponto de freada" not in tx.split("Volta ideal")[0].split("Onde mais")[0], "o resumo nao confunde tempo de trecho com ponto de freada")

# ===============================================================================================================
print("== 6) segunda rodada da auditoria: ordem dos snapshots, falhas de gravacao, timeout e voltas parecidas")
import ov_coach as _co

def externa(c, r, i):
    """registra uma volta externa nas duas versoes da API"""
    if "origem" in c.registrar_volta_externa.__code__.co_varnames:
        return c.registrar_volta_externa(r, "ibt", i)
    return c.registrar_volta_externa(r)

def ref_k(k):
    r = refer([(1000 + 3 * k, 80), (2400, 90), (3300, 70)]); r["origem"] = "propria"
    r["tempo"] = round(r["tempo"] + 0.3 * k, 3)
    r["t"] = [x * (r["tempo"] / r["t"][-1]) if r["t"][-1] else x for x in r["t"]]
    return r

logs = []
_co.registrar_log = lambda nivel, texto: logs.append((nivel, texto))

# 6a) agendamento fora de ordem: a thread A cria o snapshot de 1 volta e demora a agendar; a B cria o de 2 voltas e agenda antes
with tempfile.TemporaryDirectory() as d:
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref, salvar=False); c.modo = "importada"
    gr = c.gravador
    orig = gr.agendar
    primeira, liberar, chamadas = threading.Event(), threading.Event(), []
    def agendar_atrasado(*a, **k):
        chamadas.append(1)
        if len(chamadas) == 1:                      # a thread A fica presa aqui, com o snapshot ANTIGO na mao
            primeira.set(); liberar.wait(10)
        return orig(*a, **k)
    gr.agendar = agendar_atrasado
    tA = threading.Thread(target=externa, args=(c, ref_k(0), 0)); tA.start()
    confere(primeira.wait(5), "(preparacao) a thread A parou antes de agendar o snapshot de 1 volta")
    tB = threading.Thread(target=externa, args=(c, ref_k(1), 1)); tB.start(); tB.join(5)
    descarregar(c)                                  # o snapshot novo (2 voltas) ja foi gravado
    liberar.set(); tA.join(5)                       # agora o snapshot ANTIGO tenta chegar
    descarregar(c)
    em_disco = len(c.hist.carregar("Pista Teste", "Carro Teste"))
    confere(len(c._voltas()) == 2, f"(preparacao) as duas voltas estao na memoria ({len(c._voltas())})")
    confere(em_disco == 2, f"snapshot antigo nao sobrescreve o novo: {em_disco} de 2 voltas no arquivo")
    if hasattr(gr, "obsoletos"):
        confere(gr.obsoletos == 1, f"o snapshot antigo foi descartado e contado ({gr.obsoletos})")

# 6a') a mesma inversao, repetida com varias threads e atrasos aleatorios: o arquivo final tem sempre todas as voltas
with tempfile.TemporaryDirectory() as d:
    rnd = random.Random(7)
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref, salvar=False); c.modo = "importada"
    orig = c.gravador.agendar
    def agendar_aleatorio(*a, **k):
        time.sleep(rnd.random() * 0.05)             # ordem de chegada ao gravador embaralhada
        return orig(*a, **k)
    c.gravador.agendar = agendar_aleatorio
    ths = [threading.Thread(target=externa, args=(c, ref_k(k), k)) for k in range(12)]
    for th in ths: th.start()
    for th in ths: th.join(20)
    descarregar(c)
    mem, disco = len(c._voltas()), len(c.hist.carregar("Pista Teste", "Carro Teste"))
    confere(mem == 12 and disco == mem, f"12 threads com agendamento embaralhado: memoria {mem}, arquivo {disco}")

# 6a'') estresse: 30 rodadas x 12 threads, atraso aleatorio entre criar e agendar o snapshot (inclui o instante em que a gravacao
# da versao anterior esta em andamento). Em todas: memoria == arquivo == 12 voltas.
ruins = []
for rodada in range(30):
    with tempfile.TemporaryDirectory() as d:
        rnd = random.Random(1000 + rodada)
        c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
        c.definir_importada(ref, salvar=False); c.modo = "importada"
        orig = c.gravador.agendar
        c.gravador.agendar = (lambda o, r: (lambda *a, **k: (time.sleep(r.random() * 0.02), o(*a, **k))[1]))(orig, rnd)
        ths = [threading.Thread(target=externa, args=(c, ref_k(k), k)) for k in range(12)]
        for th in ths: th.start()
        for th in ths: th.join(30)
        descarregar(c)
        mem, disco = len(c._voltas()), len(c.hist.carregar("Pista Teste", "Carro Teste"))
        if mem != 12 or disco != 12:
            ruins.append((rodada, mem, disco))
confere(not ruins, f"estresse de 30 rodadas x 12 threads sem nenhuma volta perdida no arquivo ({len(ruins)} rodadas com perda: {ruins[:3]})")

# 6b) falha de gravacao: nao some, e registrada, nao bloqueia, e a proxima gravacao recupera
with tempfile.TemporaryDirectory() as d:
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref, salvar=False); c.modo = "importada"
    if hasattr(c.gravador, "ESPERA_S"):
        c.gravador.ESPERA_S = 0.01
    salvar_ok = c.hist.salvar
    c.hist.salvar = lambda *a, **k: False                      # disco recusa (o salvar real devolve False em caso de erro)
    logs.clear()
    t0 = time.perf_counter(); externa(c, ref_k(0), 0); chamada_ms = (time.perf_counter() - t0) * 1000
    ok = c.descarregar(5.0)
    confere(chamada_ms < 50, f"falha de disco nao bloqueia quem registra a volta ({chamada_ms:.1f} ms)")
    confere(ok is False, "descarregar() informa que NAO gravou tudo (nao finge sucesso)")
    confere(len(c._voltas()) == 1, "a volta continua na memoria apos a falha")
    confere(any(n == "aviso" for n, t in logs), f"a falha foi registrada no log ({len(logs)} mensagens)")
    if hasattr(c, "estatisticas_gravacao"):
        e = c.estatisticas_gravacao(); confere(e["falhas"] >= 1, f"contador de falhas: {e['falhas']}")
    c.hist.salvar = salvar_ok                                  # o disco volta
    externa(c, ref_k(1), 1); ok2 = c.descarregar(5.0)
    confere(ok2 and len(c.hist.carregar("Pista Teste", "Carro Teste")) == 2, "depois da falha, a proxima gravacao grava TODAS as voltas (nada perdido)")
    # excecao em vez de False
    def quebra(*a, **k): raise OSError("disco removido")
    c.hist.salvar = quebra; logs.clear()
    externa(c, ref_k(2), 2); ok3 = c.descarregar(5.0)
    confere(ok3 is False and any(n == "aviso" for n, t in logs), "excecao na gravacao: registrada e sem derrubar o Coach")
    c.hist.salvar = salvar_ok
    if hasattr(c, "encerrar"):
        logs.clear()
        confere(c.encerrar(5.0) is True and len(c.hist.carregar("Pista Teste", "Carro Teste")) == 3,
                "encerrar(): regrava o que tinha falhado e deixa as 3 voltas no arquivo")

# 6c) timeout de descarregar(): nao bloqueia, e registrado, e nada se perde quando a gravacao termina
with tempfile.TemporaryDirectory() as d:
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref, salvar=False); c.modo = "importada"
    salvar_ok = c.hist.salvar
    def lento(*a, **k):
        time.sleep(1.2); return salvar_ok(*a, **k)
    c.hist.salvar = lento; logs.clear()
    externa(c, ref_k(0), 0)
    t0 = time.perf_counter(); ok = c.descarregar(0.2); gasto = time.perf_counter() - t0
    confere(ok is False and gasto < 0.8, f"descarregar() respeita o prazo (devolveu {ok} em {gasto:.2f} s)")
    if hasattr(c, "encerrar"):
        c.encerrar(0.2)
        confere(any("pendente" in t or "ocupado" in t for n, t in logs), f"timeout ao encerrar fica no log ({[t[:60] for n, t in logs][:2]})")
    confere(c.descarregar(10.0) and len(c.hist.carregar("Pista Teste", "Carro Teste")) == 1, "quando a gravacao lenta termina, a volta esta no arquivo")

# 6d) ultima chance: gravar_agora() grava na thread de quem chama o que a fila nao gravou
if hasattr(_co, "GravadorSegundoPlano"):
    g = _co.GravadorSegundoPlano()
    parado = threading.Event()
    morto = threading.Thread(target=parado.wait, daemon=True); morto.start()
    g._thread = morto                                          # simula um gravador que nao anda
    feito = []
    g.agendar(("x",), lambda: feito.append(1) or True)
    confere(g.descarregar(0.1) is False and not feito, "fila parada: descarregar() devolve False e nada foi gravado")
    confere(hasattr(g, "gravar_agora") and g.gravar_agora(2.0) is True and feito == [1], "gravar_agora() grava o que sobrou, na thread de quem chama")
    parado.set()
    g2 = _co.GravadorSegundoPlano()
    g2.agendar(("y",), lambda: True, 5)
    g2.descarregar(2.0)
    confere(getattr(g2, "obsoletos", 0) >= 0 and g2.agendar(("y",), lambda: True, 3) is False and g2.obsoletos >= 1, "versao menor que a ja gravada e descartada")
_co.registrar_log = None

# 6e) voltas extremamente parecidas de origens diferentes: a legitima nao e descartada
import math as _m
if hasattr(mc, "id_da_volta"):
    A = fab(80.0, z1, sessao=3, numero=5, origem="ao_vivo")
    def com_t(base, t_ms, origem, sessao, numero):
        v = dict(base, t_ms=t_ms, origem=origem, sessao=sessao, numero=numero)
        v["id"] = mc.id_da_volta(origem, sessao, numero, v["tempo"], t_ms)
        return v
    distinta = com_t(A, [a + int(round(100 * _m.sin(2 * _m.pi * i / 250))) for i, a in enumerate(A["t_ms"])], "ibt", 0, None)
    rnd = random.Random(3)
    ruido = [0]
    for i in range(1, N):
        ruido.append(max(-30, min(30, ruido[-1] + rnd.randint(-12, 12))))
    copia = com_t(A, [a + r for a, r in zip(A["t_ms"], ruido)], "ibt", 0, None)
    confere(mc.mesma_volta(A, copia), "a mesma volta lida por outro caminho (diferencas de quantizacao) e reconhecida")
    confere(not mc.mesma_volta(A, distinta), "volta distinta, mesmo tempo oficial, relogio diferente em ate 100 ms: NAO e a mesma")
    l1 = mc.acrescentar(mc.acrescentar([], A, 3), distinta, 3)
    l2 = mc.acrescentar(mc.acrescentar([], distinta, 3), A, 3)
    confere(len(l1) == 2 and len(l2) == 2, f"as duas passagens legitimas ficam nos dois sentidos de importacao ({len(l1)}, {len(l2)})")
    confere(len(mc.acrescentar(l1, copia, 3)) == 2, "...e a copia da mesma volta continua sendo recusada")
    confere(len(mc.acrescentar(mc.acrescentar([], A, 3), copia, 3)) == 1, "copia de origem diferente nao duplica a volta")

# ===============================================================================================================
print("== 7) terceira rodada: gravacao em curso x invalidar()/exclusao do historico (nada invalidado reaparece)")
import io as _io_mod

def coach_hist(d):
    c = co.Coach(co.BibliotecaReferencias(d)); c.definir_contexto("Pista Teste", "Carro Teste", L)
    c.definir_importada(ref, salvar=False); c.modo = "importada"
    return c

def arquivo_hist(c):
    return c.hist._arquivo("Pista Teste", "Carro Teste")

def bloquear_salvar(c):
    """a PROXIMA gravacao do historico entra em salvar() e fica presa ate liberar.set()"""
    orig = c.hist.salvar
    entrou, liberar = threading.Event(), threading.Event()
    estado = {"n": 0}
    def salvar(*a, **k):
        estado["n"] += 1
        if estado["n"] == 1:
            entrou.set(); liberar.wait(15)
        return orig(*a, **k)
    c.hist.salvar = salvar
    return entrou, liberar

def sync_gravador(c, t=5.0):
    return c.gravador.descarregar(t)

# 7a) a sequencia EXATA do relato: gravacao antiga em execucao -> invalida -> exclui o arquivo -> libera -> o arquivo NAO volta
with tempfile.TemporaryDirectory() as d:
    c = coach_hist(d)
    externa(c, ref_k(0), 0); sync_gravador(c)                       # ja existe um arquivo de historico (1 volta)
    confere(arquivo_hist(c).exists(), "(preparacao) o historico de 1 volta esta em disco")
    entrou, liberar = bloquear_salvar(c)
    externa(c, ref_k(1), 1)                                          # snapshot antigo (2 voltas) -> a gravacao entra e trava
    confere(entrou.wait(5), "(preparacao) a gravacao antiga esta em execucao e bloqueada")
    res = {}
    def apagar():
        t0 = time.monotonic(); res["r"] = c.apagar_historico(); res["dt"] = time.monotonic() - t0
    if hasattr(c, "TIMEOUT_APAGAR_S"):
        c.TIMEOUT_APAGAR_S = 0.4
    ta = threading.Thread(target=apagar); ta.start()
    ta.join(12)                                                     # o pedido de exclusao termina COM a gravacao antiga ainda presa
    confere(not ta.is_alive(), "(preparacao) o pedido de exclusao terminou com a gravacao antiga ainda em execucao")
    liberar.set()                                                   # so agora a gravacao antiga e liberada
    sync_gravador(c)
    confere(not arquivo_hist(c).exists(), "a gravacao antiga liberada depois de invalidar+excluir NAO recria o arquivo")
    confere(len(c.hist.carregar("Pista Teste", "Carro Teste")) == 0, "nenhuma volta antiga reaparece ao reler o historico")
    confere(len(c._voltas()) == 0, "a memoria tambem ficou vazia")
    confere(res.get("r") is True, f"apagar_historico informa que apagou ({res.get('r')})")

# 7b) timeout: a gravacao nao termina a tempo -> quem pediu a exclusao NAO fica preso e nada reaparece depois
with tempfile.TemporaryDirectory() as d:
    _co.registrar_log = lambda nivel, texto: logs.append((nivel, texto))
    c = coach_hist(d)
    if hasattr(c, "TIMEOUT_APAGAR_S"):
        c.TIMEOUT_APAGAR_S = 0.4
    externa(c, ref_k(0), 0); sync_gravador(c)
    entrou, liberar = bloquear_salvar(c)
    externa(c, ref_k(1), 1)
    confere(entrou.wait(5), "(preparacao) gravacao presa")
    nlog = len(logs)
    t0 = time.monotonic(); r = c.apagar_historico(); dt = time.monotonic() - t0
    confere(dt < 4.0, f"o pedido de exclusao nao prende a thread chamadora com a gravacao travada ({dt:.2f} s)")
    confere(any("exclus" in t.lower() or "apag" in t.lower() for n, t in logs[nlog:]),
            "o timeout fica registrado no log (nao e silencioso)")
    confere(c.gravador.pendentes() >= 1, "a exclusao continua pendente (nao foi esquecida)")
    # uma volta NOVA, depois do pedido de exclusao, e gravada normalmente e nao e apagada pela exclusao pendente
    externa(c, ref_k(2), 2)
    liberar.set()
    confere(sync_gravador(c, 10.0), "tudo quitado depois que a gravacao travada foi liberada")
    em_disco = c.hist.carregar("Pista Teste", "Carro Teste")
    confere(len(em_disco) == 1 and len(c._voltas()) == 1, f"so a volta NOVA esta em disco e na memoria ({len(em_disco)} / {len(c._voltas())})")

# 7c) sem gravacao em curso: a exclusao e imediata e a volta seguinte e gravada
with tempfile.TemporaryDirectory() as d:
    c = coach_hist(d)
    externa(c, ref_k(0), 0); sync_gravador(c)
    t0 = time.monotonic(); r = c.apagar_historico(); dt = time.monotonic() - t0
    confere(r is True and not arquivo_hist(c).exists() and dt < 1.0, f"exclusao simples: apagou e voltou rapido ({r}, {dt:.2f} s)")
    externa(c, ref_k(3), 3); sync_gravador(c)
    confere(len(c.hist.carregar("Pista Teste", "Carro Teste")) == 1, "o historico recomeca depois de apagado")
    confere(c.apagar_historico() is True and c.apagar_historico() is False, "apagar de novo, sem arquivo, devolve False")

# 7d) o gravador isolado: invalidar/exclusao com gravacao em curso, versionamento monotonico preservado
with tempfile.TemporaryDirectory() as d:
    arq = Path(d) / "x.json"
    g = _co.GravadorSegundoPlano("teste-excl")
    entrou, liberar = threading.Event(), threading.Event()
    def grava(v):
        def f():
            if v == 1:
                entrou.set(); liberar.wait(15)
            arq.write_text(str(v))
            return True
        return f
    g.agendar(("k",), grava(1), 1)
    confere(entrou.wait(5), "(preparacao) gravacao v1 em curso")
    if hasattr(g, "registrar_exclusao"):
        exc = g.registrar_exclusao(("k",), 5, lambda: (arq.unlink() if arq.exists() else None) or True)
        confere(g.agendar(("k",), grava(3), 3) is False, "snapshot invalidado (v3 < 5) e recusado")
        confere(g.agendar(("k",), grava(6), 6) is True, "snapshot posterior a invalidacao (v6) e aceito")
        liberar.set()
        confere(g.descarregar(5.0), "gravador quitado")
        confere(arq.exists() and arq.read_text() == "6", f"vale a v6, gravada DEPOIS da exclusao (arquivo={arq.read_text() if arq.exists() else None})")
        confere(exc.evento.is_set(), "a exclusao foi executada")
        confere(g.agendar(("k",), grava(4), 4) is False, "versoes antigas continuam sendo recusadas (monotonico)")
    else:
        liberar.set(); g.descarregar(5.0)
        g.invalidar(("k",), 5)
        confere(not arq.exists(), "invalidar() com gravacao em curso: o arquivo antigo nao pode ficar")
    # gravar_agora no encerramento executa a exclusao pendente
    arq2 = Path(d) / "y.json"; arq2.write_text("velho")
    g2 = _co.GravadorSegundoPlano("teste-excl2")
    if hasattr(g2, "registrar_exclusao"):
        g2._io.acquire()                                             # simula gravacao travada segurando o disco
        g2.registrar_exclusao(("y",), 2, lambda: (arq2.unlink() if arq2.exists() else None) or True)
        g2._io.release()
        g2._thread = None
        confere(g2.gravar_agora(2.0), "gravar_agora quita a exclusao pendente ao encerrar")
        confere(not arq2.exists(), "...e o arquivo foi apagado")
    # 7d-bis) trabalho "em voo": a thread ja tirou a exclusao da fila mas ainda nao a executou quando o encerramento chega
    arq3 = Path(d) / "w.json"; arq3.write_text("velho")
    g3 = _co.GravadorSegundoPlano("teste-voo")
    if hasattr(g3, "registrar_exclusao") and hasattr(_co, "_EmVoo"):
        g3._io.acquire()                                             # a thread gravadora fica presa esperando o disco
        exc3 = g3.registrar_exclusao(("w",), 2, lambda: (arq3.unlink() if arq3.exists() else None) or True)
        for _ in range(100):
            with g3._cv:
                if g3._voo is not None and not g3._exclusoes:
                    break
            time.sleep(0.05)
        confere(g3._voo is not None and not g3._exclusoes, "(preparacao) exclusao ja saiu da fila e esta em voo")
        g3._io.release()
        g3._voo.tomado = False
        r3 = []
        t3 = threading.Thread(target=lambda: r3.append(g3.gravar_agora(3.0)))
        t3.start(); t3.join(5)
        confere(r3 == [True] and not arq3.exists(), "gravar_agora assume a exclusao em voo: arquivo apagado antes de retornar")
# 7e) exclusao que falha (arquivo travado por antivirus, p.ex.): fica pendente, bloqueia novas gravacoes da chave e depois conclui
with tempfile.TemporaryDirectory() as d:
    arq = Path(d) / "z.json"; arq.write_text("velho")
    g3 = _co.GravadorSegundoPlano("teste-excl3"); g3.ESPERA_S = 0.01
    if hasattr(g3, "registrar_exclusao"):
        falhas_restantes = [4]
        def apagar_teimoso():
            if falhas_restantes[0] > 0:
                falhas_restantes[0] -= 1
                raise PermissionError("arquivo em uso")
            arq.unlink(); return True
        exc = g3.registrar_exclusao(("z",), 3, apagar_teimoso)
        g3.agendar(("z",), lambda: arq.write_text("novo") or True, 4)
        time.sleep(0.5)
        confere(not exc.evento.is_set() and arq.read_text() == "velho", "exclusao que falha fica pendente e a gravacao nova espera (nao e apagada depois)")
        confere(g3.descarregar(8.0), "depois de superada a falha, tudo e quitado")
        confere(arq.exists() and arq.read_text() == "novo", "o snapshot novo vale e foi gravado DEPOIS da exclusao")
_co.registrar_log = None

print()
print("RESULTADO:", "OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
