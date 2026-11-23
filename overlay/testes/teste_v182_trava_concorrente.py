# -*- coding: utf-8 -*-
"""Build bb: exclusao mutua REAL da trava do atualizador LMU, com varios processos do sistema operacional disputando a mesma pasta.
Cobre: trava orfa disputada por 3 processos (nunca dois dentro ao mesmo tempo), trava ativa respeitada, liberar so pelo dono."""
import json, os, subprocess, sys, tempfile, time, shutil
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
ATU = os.environ.get("WOLFX_ATU_DIR") or os.path.join(RAIZ, "tools", "atualizador_lmu")   # WOLFX_ATU_DIR: rodar o mesmo teste contra uma versao anterior
falhas = 0
def confere(c, m):
    global falhas
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas += 1

TRABALHADOR = r'''
import json, os, sys, time
sys.path.insert(0, sys.argv[1])
import atualizar_lmu as A
from pathlib import Path
destino = Path(sys.argv[2]); inicio = float(sys.argv[3]); rodadas = int(sys.argv[4]); segura = float(sys.argv[5])
while time.time() < inicio: time.sleep(0.001)
res = {"pid": os.getpid(), "obteve": 0, "recusou": 0, "violacoes": 0, "liberou_mal": 0}
for _ in range(rodadas):
    trava, msg = A.tomar_trava(destino)
    if trava is None:
        res["recusou"] += 1; time.sleep(0.01); continue
    res["obteve"] += 1
    marca = destino / ("dentro." + str(os.getpid()))
    marca.write_text("x")
    outros = [n for n in os.listdir(destino) if n.startswith("dentro.") and n != marca.name]
    if outros: res["violacoes"] += 1
    time.sleep(segura)
    outros = [n for n in os.listdir(destino) if n.startswith("dentro.") and n != marca.name]
    if outros: res["violacoes"] += 1
    marca.unlink()
    ok, m = A.liberar_trava(trava)
    if not ok: res["liberou_mal"] += 1
print(json.dumps(res))
'''


def rodar_filhos(comandos, timeout=180):
    """Lanca todos os comandos juntos; saida de cada um vai para um arquivo. Devolve [(codigo, stdout, stderr)]."""
    pasta_saida = tempfile.mkdtemp(prefix="wolfx_saida_"); procs = []
    for i, cmd in enumerate(comandos):
        fo = open(os.path.join(pasta_saida, "%d.out" % i), "w+", encoding="utf-8"); fe = open(os.path.join(pasta_saida, "%d.err" % i), "w+", encoding="utf-8")
        procs.append((subprocess.Popen(cmd, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL), fo, fe))
    res = []
    for p, fo, fe in procs:
        try: p.wait(timeout=timeout)
        except subprocess.TimeoutExpired: p.kill(); p.wait()
        fo.close(); fe.close()
        res.append((p.returncode, open(fo.name, encoding="utf-8", errors="replace").read(), open(fe.name, encoding="utf-8", errors="replace").read()))
    shutil.rmtree(pasta_saida, ignore_errors=True)
    return res

def ultimo_json(saida, erro):
    try: return json.loads(saida.strip().splitlines()[-1])
    except Exception: return {"erro": (saida + erro)[-400:]}

def lancar(n, destino, rodadas, segura, atraso=1.5):
    ini = time.time() + atraso
    cmds = [[sys.executable, "-I", "-c", TRABALHADOR, ATU, destino, str(ini), str(rodadas), str(segura)] for _ in range(n)]
    return [ultimo_json(o, e) for _, o, e in rodar_filhos(cmds)]

sys.path.insert(0, ATU)
import atualizar_lmu as A

def pasta():
    return tempfile.mkdtemp(prefix="wolfx_trava_")

def orfa(d):
    # PID que nao existe mais: sobe e encerra um processo real
    p = subprocess.Popen([sys.executable, "-c", "pass"]); p.wait()
    with open(os.path.join(d, A.NOME_TRAVA), "w", encoding="utf-8") as f:
        json.dump({"pid": p.pid, "inicio": time.time() - 10, "maquina": A.socket.gethostname(), "token": "antigo"}, f)

# 1) trava orfa disputada por 3 processos reais, varias rodadas: exclusao mutua
for rodada in range(4):
    d = pasta(); orfa(d)
    r = lancar(3, d, rodadas=8, segura=0.05)
    confere(all("erro" not in x for x in r), f"orfa x3 (rodada {rodada}): processos terminaram sem erro {[x.get('erro') for x in r if 'erro' in x]}")
    confere(sum(x.get("violacoes", 0) for x in r) == 0, f"orfa x3 (rodada {rodada}): nunca dois processos dentro ao mesmo tempo")
    confere(sum(x.get("obteve", 0) for x in r) >= 1, f"orfa x3 (rodada {rodada}): a trava orfa foi assumida ({[x.get('obteve') for x in r]})")
    confere(sum(x.get("liberou_mal", 0) for x in r) == 0, f"orfa x3 (rodada {rodada}): cada processo liberou a PROPRIA trava")
    confere(not os.path.exists(os.path.join(d, A.NOME_TRAVA)), f"orfa x3 (rodada {rodada}): nao sobrou trava")
    shutil.rmtree(d, ignore_errors=True)

# 2) pasta limpa, 2 processos
d = pasta(); r = lancar(2, d, rodadas=10, segura=0.03)
confere(sum(x.get("violacoes", 0) for x in r) == 0 and sum(x.get("obteve", 0) for x in r) >= 2, f"limpa x2: exclusao mutua e progresso ({[x.get('obteve') for x in r]})")
shutil.rmtree(d, ignore_errors=True)

# 3) trava ATIVA (dono vivo = este processo) e respeitada por 3 processos: todos recusam e a trava continua intacta
d = pasta(); t, m = A.tomar_trava(__import__("pathlib").Path(d))
confere(t is not None, "dono toma a trava")
antes = open(os.path.join(d, A.NOME_TRAVA), encoding="utf-8").read()
# o dono real e ESTE processo (PID vivo); os trabalhadores sao outros PIDs
r = lancar(3, d, rodadas=5, segura=0.01, atraso=0.5)
confere(all(x.get("obteve", 1) == 0 and x.get("recusou", 0) == 5 for x in r), f"trava ativa: 3 processos recusam todas as tentativas {r}")
confere(open(os.path.join(d, A.NOME_TRAVA), encoding="utf-8").read() == antes, "trava ativa: conteudo intacto (ninguem a moveu nem trocou)")

# 4) so o dono libera
import atualizar_lmu
atualizar_lmu._DONOS[str(__import__("pathlib").Path(d) / A.NOME_TRAVA)] = "token-de-outro"
ok, msg = A.liberar_trava(__import__("pathlib").Path(d) / A.NOME_TRAVA)
confere((not ok) and os.path.exists(os.path.join(d, A.NOME_TRAVA)), f"liberar com token errado nao apaga a trava ({msg})")
A._DONOS.clear()
ok, msg = A.liberar_trava(__import__("pathlib").Path(d) / A.NOME_TRAVA)
confere((not ok) and os.path.exists(os.path.join(d, A.NOME_TRAVA)), "quem nao e dono nao apaga a trava")
shutil.rmtree(d, ignore_errors=True)


# 5) o cenario do auditor, deterministico: A julga a trava ORFA e fica parado nesse ponto; B tenta tomar a trava nesse intervalo.
#    Sem a guarda, B cria/mexe na trava e A passa por cima (os dois ficam 'donos'); com a guarda, B espera e depois ve a trava ATIVA de A.
CORRIDA = r"""
import json, os, sys, time
sys.path.insert(0, sys.argv[1])
import atualizar_lmu as A
from pathlib import Path
destino = Path(sys.argv[2]); papel = sys.argv[3]; inicio = float(sys.argv[4])
if papel == "A":
    orig = A.estado_trava
    def lento(trava, agora=None):
        r = orig(trava, agora)
        if r[0] == "orfa": time.sleep(1.2)           # A ja julgou 'orfa' e demora a agir
        return r
    A.estado_trava = lento
while time.time() < inicio: time.sleep(0.001)
if papel == "B": time.sleep(0.4)
trava, msg = A.tomar_trava(destino)
obteve = trava is not None
if obteve:
    time.sleep(1.5)
    try: atual = json.loads(trava.read_text(encoding="utf-8"))
    except Exception: atual = {}
    dono_ainda = atual.get("pid") == os.getpid()
else:
    dono_ainda = False
print(json.dumps({"papel": papel, "obteve": obteve, "dono_ainda": dono_ainda}))
"""
def corrida():
    d = pasta(); orfa(d); ini = time.time() + 1.0
    res = [ultimo_json(o, e) for _, o, e in rodar_filhos([[sys.executable, "-I", "-c", CORRIDA, ATU, d, papel, str(ini)] for papel in ("A", "B")])]
    shutil.rmtree(d, ignore_errors=True)
    return res
r = corrida()
obtiveram = [x for x in r if x.get("obteve")]
confere(all("erro" not in x for x in r), f"corrida A/B: sem erro {r}")
confere(len(obtiveram) == 1, f"corrida A/B: exatamente um processo fica com a trava (obtiveram: {[x['papel'] for x in obtiveram]})")
confere(all(x.get("dono_ainda") for x in obtiveram), "corrida A/B: quem obteve a trava continua dono dela ate o fim (ninguem a moveu)")

print("\n%d falha(s)" % falhas if falhas else "\nOK")
sys.exit(1 if falhas else 0)
