# -*- coding: utf-8 -*-
"""v1.7.0 - leitor de telemetria .ibt (arquivo sintetico no formato do iRacing), melhor volta da pasta e carga automatica."""
import os, sys, struct, tempfile, time, threading
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import ov_ibt as ib, ov_coach as co

falhas = []
def confere(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)

L = 4000.0
CURVAS = (800.0, 2000.0, 3200.0)
APICE = {800.0: 80.0, 2000.0: 120.0, 3200.0: 70.0}
def vel_em(x, ritmo=1.0):
    for xc in CURVAS:
        va = APICE[xc]; ini = xc - 100.0
        if ini <= x < xc: return (200.0 - (200.0 - va) * (x - ini) / (xc - ini)) * ritmo
        if xc <= x < xc + 120.0: return (va + (200.0 - va) * (x - xc) / 120.0) * ritmo
    return 200.0 * ritmo
def freio_em(x): return 0.9 if any(xc - 100.0 <= x < xc - 10.0 for xc in CURVAS) else 0.0
def marcha_em(v): return 2 if v < 100 else (3 if v < 150 else 5)

VARS = [("Speed", 4, "f"), ("Brake", 4, "f"), ("Throttle", 4, "f"), ("Gear", 4, "i"), ("LapDistPct", 4, "f"),
        ("LapCurrentLapTime", 4, "f"), ("Lap", 4, "i"), ("OnPitRoad", 1, "?"), ("PlayerTrackSurface", 4, "i"),
        ("IsOnTrack", 1, "?"), ("LapLastLapTime", 4, "f")]
def escrever_ibt(caminho, voltas, pista="Pista Teste", carro="GT3 Teste", comprimento_km=4.0, taxa=60):
    """voltas: lista de dicts {ritmo, boxes, fora}. Gera registros a 60 Hz com o 'Lap' virando na linha e o
    LapCurrentLapTime zerando so depois (como no iRacing real)."""
    offs, pos = [], 0
    for nome, tam, cod in VARS:
        offs.append(pos); pos += tam
    buf_len = pos
    registros, ultimo = [], 0.0
    for n, cfg in enumerate(voltas):
        x, t = 0.0, 0.0
        while x < L:
            v = vel_em(x, cfg.get("ritmo", 1.0))
            clt = t if (t > 0.3 or n == 0) else (ultimo + t)
            reg = struct.pack("<f", v / 3.6) + struct.pack("<f", freio_em(x)) + struct.pack("<f", 0.0 if freio_em(x) else 1.0) \
                + struct.pack("<i", marcha_em(v)) + struct.pack("<f", x / L) + struct.pack("<f", clt) + struct.pack("<i", n) \
                + struct.pack("<?", bool(cfg.get("boxes"))) + struct.pack("<i", 1 if cfg.get("fora") else 3) \
                + struct.pack("<?", True) + struct.pack("<f", ultimo)
            registros.append(reg)
            x += v / 3.6 / taxa; t += 1.0 / taxa
        ultimo = t
    yaml = (f"---\nWeekendInfo:\n TrackDisplayName: {pista}\n TrackConfigName: GP\n TrackLength: {comprimento_km:.4f} km\n"
            f"DriverInfo:\n DriverCarIdx: 3\n Drivers:\n - CarIdx: 0\n   CarScreenName: Carro De Outro Piloto\n   CarPath: outro\n"
            f" - CarIdx: 3\n   CarScreenName: {carro}\n   CarPath: gt3teste\n - CarIdx: 4\n   CarScreenName: Mais Um\n   CarPath: mais\n...\n").encode("latin-1")
    vho = 144
    sio = vho + 144 * len(VARS)
    buf_off = sio + len(yaml)
    cab = bytearray(144)
    struct.pack_into("<10i", cab, 0, 2, 1, taxa, 0, len(yaml), sio, len(VARS), vho, 1, buf_len)
    struct.pack_into("<ii", cab, 48, 0, buf_off)
    struct.pack_into("<qddii", cab, 112, 0, 0.0, 0.0, len(voltas), len(registros))
    vh = bytearray()
    tipos = {"f": 4, "i": 2, "?": 1}
    for (nome, tam, cod), off in zip(VARS, offs):
        h = bytearray(144)
        struct.pack_into("<iii", h, 0, tipos[cod], off, 1)
        h[16:16 + len(nome)] = nome.encode()
        vh += h
    Path(caminho).write_bytes(bytes(cab) + bytes(vh) + yaml + b"".join(registros))

with tempfile.TemporaryDirectory() as pasta:
    pasta = Path(pasta)
    arq = pasta / "gt3teste_pista teste 2026-11-01 10-00-00.ibt"
    escrever_ibt(arq, [{"boxes": True}, {"ritmo": 1.0}, {"ritmo": 1.03}, {"ritmo": 1.0, "fora": True}, {"ritmo": 1.0}])
    info = ib.info_ibt(arq)
    confere(info["pista"] == "Pista Teste" and info["carro"] == "GT3 Teste" and abs(info["comprimento"] - 4000.0) < 1 and info["taxa"] == 60, f"info da sessao ({info['pista']}, {info['carro']}, {info['comprimento']})")
    info, voltas = ib.voltas_ibt(arq)
    confere(len(voltas) == 5, f"5 voltas separadas pela variavel Lap ({len(voltas)})")
    confere([v["valida"] for v in voltas] == [False, True, True, False, True], f"validade das voltas ({[v['motivo'] for v in voltas]})")
    confere(voltas[0]["motivo"] == "passou pelos boxes" and voltas[3]["motivo"] == "saiu da pista", "motivos: boxes e fora da pista")
    melhor = ib.melhor_volta(voltas)
    confere(melhor is voltas[2], "melhor volta = a mais rapida entre as validas")
    confere(abs(melhor["t"][-1] - melhor["tempo"]) < 0.05, f"tempo decorrido pela contagem de registros ({melhor['t'][-1]:.2f} x {melhor['tempo']:.2f}), mesmo com o LapCurrentLapTime atrasado")
    ref = ib.referencia_de_volta(info, melhor, "propria", "teste")
    zonas = co.zonas_de_frenagem(ref)
    confere(len(zonas) == 3 and [z["marcha_apice"] for z in zonas] == [2, 3, 2], f"referencia vinda do .ibt: 3 zonas, marchas {[z['marcha_apice'] for z in zonas]}")
    achou = ib.melhor_volta_da_pasta(pasta, "Pista Teste", "GT3 Teste", 4000.0)
    confere(achou is not None and achou[0].name == arq.name and abs(achou[1]["tempo"] - melhor["tempo"]) < 1e-6, "melhor volta da pasta (pista + carro + comprimento)")
    confere(ib.melhor_volta_da_pasta(pasta, "Outra Pista", "GT3 Teste", 4000.0) is None, "outra pista: nada")
    confere(ib.melhor_volta_da_pasta(pasta, "Pista Teste", "Outro Carro", 4000.0) is None, "outro carro: nada")
    confere(ib.melhor_volta_da_pasta(pasta, "Pista Teste", "GT3 Teste", 6500.0) is None, "outro layout (comprimento): nada")
    confere(ib.melhor_volta_da_pasta(pasta / "nao_existe", "Pista Teste", "GT3 Teste", 4000.0) is None, "pasta inexistente: None, sem erro")
    (pasta / "lixo.ibt").write_bytes(b"isto nao e um ibt" * 20)
    (pasta / "vazio.ibt").write_bytes(b"")
    confere(ib.melhor_volta_da_pasta(pasta, "Pista Teste", "GT3 Teste", 4000.0) is not None, "arquivos corrompidos sao ignorados")
    try:
        ib.info_ibt(pasta / "lixo.ibt"); confere(False, "ibt invalido devia falhar")
    except ib.ErroIbt:
        confere(True, "ibt invalido: ErroIbt")

    # carga automatica em segundo plano, pelo Telemetria
    import overlay_iracing as o
    class Falso: pass
    tele = Falso()
    tele.v17_coach = co.Coach(co.BibliotecaReferencias(pasta / "ref"))
    tele.v17_coach.definir_contexto("Pista Teste", "GT3 Teste", 4000.0)
    tele.v17_ibt_pasta = pasta
    tele.config_coach_ibt_auto = True
    o._carregar_ibt_se_preciso(tele)
    for _ in range(100):
        if tele.v17_coach.ref_propria is not None: break
        time.sleep(0.05)
    r = tele.v17_coach.ref_propria
    confere(r is not None and abs(r["tempo"] - melhor["tempo"]) < 0.05 and r["origem"] == "propria", "referencia propria carregada sozinha do .ibt (segundo plano)")
    for _ in range(40):
        if list((pasta / "ref").glob("*.json")): break
        time.sleep(0.05)
    confere(len(list((pasta / "ref").glob("*.json"))) == 1, "e salva na biblioteca")
    n_antes = __import__("threading").active_count()
    o._carregar_ibt_se_preciso(tele)
    confere(__import__("threading").active_count() <= n_antes, "so procura uma vez por pista/carro")
    tele2 = Falso(); tele2.v17_coach = co.Coach(co.BibliotecaReferencias(pasta / "ref2")); tele2.v17_coach.definir_contexto("Pista Teste", "GT3 Teste", 4000.0)
    tele2.v17_ibt_pasta = pasta; tele2.config_coach_ibt_auto = False
    o._carregar_ibt_se_preciso(tele2); time.sleep(0.3)
    confere(tele2.v17_coach.ref_propria is None, "com a opcao desligada nao carrega")
    for t_ in threading.enumerate():                       # espera o segundo plano terminar antes de apagar a pasta
        if t_.name == "coach-ibt": t_.join(20)
    confere(len(tele.v17_coach._voltas()) >= 1, "1.7.0: as voltas validas do .ibt tambem alimentam o historico por curva")
    confere(tele2.v17_coach.definir_propria(dict(ref, tempo=ref["tempo"] + 1.0)) is True and tele2.v17_coach.definir_propria(ref) is True
            and tele2.v17_coach.definir_propria(dict(ref, tempo=ref["tempo"] + 5.0)) is False, "definir_propria so aceita volta mais rapida")

# ja existe referencia MAIS LENTA (de uma sessao anterior): a busca no .ibt ainda a atualiza
with tempfile.TemporaryDirectory() as p2:
    p2 = Path(p2); arq2 = p2 / "x.ibt"
    escrever_ibt(arq2, [{"boxes": True}, {"ritmo": 1.0}, {"ritmo": 1.05}])
    info2, v2 = ib.voltas_ibt(arq2); rapida = ib.melhor_volta(v2)
    lenta = ib.referencia_de_volta(info2, [v for v in v2 if v["valida"] and v is not rapida][0], "propria", "antiga")
    class F: pass
    tt = F(); tt.v17_coach = co.Coach(co.BibliotecaReferencias(p2 / "r")); tt.v17_coach.definir_contexto("Pista Teste", "GT3 Teste", 4000.0)
    tt.v17_coach.definir_propria(lenta); tt.v17_ibt_pasta = p2; tt.config_coach_ibt_auto = True
    import overlay_iracing as o2
    o2._carregar_ibt_se_preciso(tt)
    for _ in range(100):
        if tt.v17_coach.ref_propria["tempo"] < lenta["tempo"] - 0.5: break
        time.sleep(0.05)
    for t_ in threading.enumerate():
        if t_.name == "coach-ibt": t_.join(20)
    confere(tt.v17_coach.ref_propria["tempo"] < lenta["tempo"] - 0.5, "referencia antiga mais lenta e atualizada pela volta mais rapida do .ibt")

for t_ in threading.enumerate():
    if t_.name == "coach-ibt": t_.join(20)
print("RESULTADO:", "OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
