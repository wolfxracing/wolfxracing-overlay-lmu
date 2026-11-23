# -*- coding: utf-8 -*-
"""Teste de MIGRACAO ae -> (build do pacote) do overlay LMU em copia ISOLADA (diretorio temporario; a instalacao real nunca e tocada).
Uso: python3 verificar_migracao.py --ae-zip WolfxRacing_1.8_ae_instalar.zip --pacote-completo <pasta do pacote de atualizacao ja extraido>
                                  [--incremental-ax instalar_buildAX_lmu.zip]
Confere: (1) o ZIP incremental da ax, sozinho, NAO leva a ae ate a az (lista os arquivos ausentes/divergentes); (2) o pacote completo leva; (3) dados do usuario
(config, recordes, pit, cronograma, historico, emblemas/marca editados, log) ficam byte a byte iguais e a config carrega com os valores do usuario;
(4) backup dos arquivos substituidos; (5) idempotencia; (6) rejeicao de pacote incompleto ou divergente e rollback durante a troca de arquivos;
(7) o programa migrado roda as suites novas."""
import os, sys, json, shutil, hashlib, tempfile, zipfile, subprocess, argparse, re
ap = argparse.ArgumentParser()
ap.add_argument("--ae-zip", required=True); ap.add_argument("--pacote-completo", required=True); ap.add_argument("--incremental-ax", default="")
a = ap.parse_args()
ambiente_teste = dict(os.environ)
ambiente_teste.setdefault("QT_QPA_PLATFORM", "offscreen")
falhas, ok = [], 0
def confere(c, m):
    global ok
    if c: ok += 1; print("OK   ", m)
    else: falhas.append(m); print("FALHA", m)
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def arvore(raiz, ignorar=("backup_pre_", "__pycache__", "logs_testes")):
    r = {}
    for d, ds, fs in os.walk(raiz):
        ds[:] = [x for x in ds if not x.startswith(ignorar)]
        for f in fs:
            p = os.path.join(d, f); r[os.path.relpath(p, raiz).replace(os.sep, "/")] = sha(p)
    return r
TMP = tempfile.mkdtemp(prefix="migracao_")
PROG = os.path.join(a.pacote_completo, "programa")
INFO = json.load(open(os.path.join(a.pacote_completo, "PACOTE.json"), encoding="utf-8"))
ALVO = INFO["build"]
confere(os.path.isdir(PROG) and os.path.isfile(os.path.join(a.pacote_completo, "atualizar_lmu.py")), "pacote completo extraido (atualizar_lmu.py + programa/)")
def nova_copia_ae(nome):
    d = os.path.join(TMP, nome); os.makedirs(d)
    with zipfile.ZipFile(a.ae_zip) as z:
        for n in z.namelist():
            if n.startswith("lmu/") and not n.endswith("/"):
                t = os.path.join(d, n[4:]); os.makedirs(os.path.dirname(t), exist_ok=True); open(t, "wb").write(z.read(n))
    return d
def build(d):
    m = re.search(r'^BUILD\s*=\s*"([^"]+)"', open(os.path.join(d, "overlay_iracing.py"), encoding="utf-8").read(), re.M); return m.group(1)
def dados_usuario(d):
    cfg = {"classificacao_layout": "classico", "elementos_classificacao_pos": {"ncars": [-12, 3]},
           "elementos_classificacao_estilo": {"ncars": {"fonte": "orbitron", "tam": 150, "negrito": True, "italico": True, "cor": "#ffcc00"}},
           "delta_trace_elementos_pos": {"grafico": [5, 7]}, "x_lmu_energia": 498, "idioma": "pt", "travado": True}
    arqs = {"config_lmu.json": json.dumps(cfg), "config.json": json.dumps({"idioma": "pt"}), "recordes_pessoais.json": json.dumps({"Sarthe": 205.3}),
            "pit_entradas.json": "{}", "cronograma.json": json.dumps({"series": []}), "overlay_log.txt": "log do usuario\n",
            "referencias/historico/historico__minha_pista__meu_carro.json": "{\"v\": 1}", "referencias/minha_propria.json": "{\"v\": 2}",
            "emblemas/meu_emblema_editado.png": "PNGFAKE", "marca/logo_wolfxracing.png": "LOGO-DO-USUARIO"}
    for rel, txt in arqs.items():
        p = os.path.join(d, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf-8").write(txt)
    return list(arqs)
def aplicar(dest, pacote=a.pacote_completo, extra=()):
    return subprocess.run([sys.executable, os.path.join(pacote, "atualizar_lmu.py"), dest, *extra], capture_output=True, text=True)

alvo_py = sorted(r for r in arvore(PROG) if r.endswith(".py") and "/" not in r)
# (1) o incremental da ax sozinho
if a.incremental_ax:
    inc = nova_copia_ae("so_incremental_ax")
    with zipfile.ZipFile(a.incremental_ax) as z: z.extractall(inc)
    ar = arvore(inc); ausentes = [r for r in alvo_py if r not in ar]; divergentes = [r for r in alvo_py if r in ar and ar[r] != arvore(PROG)[r]]
    confere(build(inc) != ALVO and len(ausentes) + len(divergentes) >= 9, f"incremental da ax sobre a ae NAO chega na {ALVO}: {len(ausentes)} .py da raiz ausentes + {len(divergentes)} divergentes ({', '.join((ausentes + divergentes)[:12])}...)")
# (2) pacote completo sobre a ae, com dados do usuario
d = nova_copia_ae("ae_para_az"); confere(build(d) == "ae", f"copia de partida na build ae ({build(d)})")
usr = dados_usuario(d); antes_usr = {r: sha(os.path.join(d, r)) for r in usr}; antes_arv = arvore(d)
sim = aplicar(d, extra=("--simular",)); confere(sim.returncode == 0 and arvore(d) == antes_arv, "--simular nao altera nada")
r = aplicar(d); print(r.stdout.strip()[-400:])
confere(r.returncode == 0, f"atualizador rc=0 (rc={r.returncode})")
confere(build(d) == ALVO, f"build apos a migracao = {build(d)}")
dep = arvore(d); pk = arvore(PROG)
protegidos = set(usr)
diverge = [rel for rel, h in pk.items() if rel not in protegidos and dep.get(rel) != h and not any(rel.startswith(x + "/") for x in ("emblemas", "marca", "referencias")) and not re.match(r"^(config.*\.json|recordes_pessoais\.json|pit_entradas.*\.json|cronograma\.json)$", rel)]
confere(diverge == [], f"todo arquivo do programa (inclusive os {len(alvo_py)} .py da raiz) igual ao pacote depois da migracao (divergentes: {diverge[:5]})")
confere(all(sha(os.path.join(d, rel)) == h for rel, h in antes_usr.items()), "dados do usuario byte a byte iguais (config, recordes, pit, cronograma, historico, referencia propria, emblema, marca, log)")
bks = [x for x in os.listdir(d) if x.startswith("backup_pre_build" + ALVO.upper() + "_")]
confere(len(bks) == 1 and all(os.path.exists(os.path.join(d, bks[0], r_)) for r_ in ("ov_janela_lmu.py", "overlay_iracing.py")), "backup dos arquivos substituidos criado")
confere(sha(os.path.join(d, bks[0], "overlay_iracing.py")) == antes_arv["overlay_iracing.py"], "backup guarda a versao ae original")
# config do usuario ainda carrega com os valores dele (carregador real do programa, no diretorio migrado)
cod = ("import os,sys; sys.argv=['x','--demo']; sys.path.insert(0,os.getcwd()); import overlay_iracing as o, overlay_lmu as m\n"
       "m.redirecionar_arquivos(os.getcwd()); c=m.carregar_config_lmu(); print('CFG', c['classificacao_layout'], c['elementos_classificacao_estilo']['ncars']['fonte'], c['delta_trace_elementos_pos']['grafico'], c['x_lmu_energia'])\n"
       "print('BUILD', o.BUILD)")
p = subprocess.run([sys.executable, "-c", cod], cwd=d, capture_output=True, text=True, env=ambiente_teste)
confere(p.returncode == 0 and {"CFG classico orbitron [5, 7] 498", "BUILD " + ALVO} <= set(p.stdout.splitlines()),
        f"carregador real usa os valores da configuracao LMU (rc={p.returncode}: {p.stdout.strip()[:100]})")
# (5) idempotencia
r2 = aplicar(d); confere(r2.returncode == 0 and "0 novos, 0 a atualizar" in r2.stdout, "segunda aplicacao: nada a fazer (idempotente)")
# (7) suites novas rodam no diretorio migrado
for t in ("teste_v18_ncars_lmu.py", "teste_v18_negrito_italico.py"):
    pr = subprocess.run([sys.executable, os.path.join("testes", t)], cwd=d, capture_output=True, text=True, env=ambiente_teste, timeout=600)
    ult = [l for l in pr.stdout.splitlines() if "ok," in l][-1:]
    confere(pr.returncode == 0, f"{t} no diretorio migrado: rc={pr.returncode} {ult}")
# (6) rejeicao de um pacote diferente do manifesto, antes de mutar o destino
d2 = nova_copia_ae("destino_para_rejeicao"); dados_usuario(d2); antes2 = arvore(d2)
pk2 = os.path.join(TMP, "pacote_divergente"); shutil.copytree(a.pacote_completo, pk2)
controle = os.path.join(pk2, "programa", "ov_janela_lmu.py")
with open(controle, "rb") as arquivo:
    original = arquivo.read()
with open(controle, "ab") as arquivo:
    arquivo.write(b"\n# Conteudo divergente do manifesto, sintaxe valida\n")
r3 = aplicar(d2, pacote=pk2)
confere(r3.returncode == 1 and "SHA-256" in r3.stdout and arvore(d2) == antes2,
        "hash divergente rejeitado sem alterar o destino")
with open(controle, "wb") as arquivo:
    arquivo.write(original)
os.remove(os.path.join(pk2, "programa", "ov_i18n.py"))
r5 = aplicar(d2, pacote=pk2)
confere(r5.returncode == 1 and "ov_i18n.py" in r5.stdout and arvore(d2) == antes2,
        "arquivo ausente rejeitado sem alterar o destino")
# Falha durante a troca, depois de instalar os arquivos novos. Funciona tambem fora do Windows.
injetar_falha = """
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("atualizador", sys.argv[1])
atualizador = importlib.util.module_from_spec(spec)
spec.loader.exec_module(atualizador)
trocar = atualizador.os.replace

def trocar_com_bloqueio(origem, destino):
    if Path(destino).name == "ov_janela_lmu.py":
        raise PermissionError("arquivo bloqueado para o teste de rollback")
    return trocar(origem, destino)

atualizador.os.replace = trocar_com_bloqueio
sys.exit(atualizador.main([sys.argv[2]]))
"""
r6 = subprocess.run(
    [sys.executable, "-c", injetar_falha, os.path.join(a.pacote_completo, "atualizar_lmu.py"), d2],
    capture_output=True, text=True,
)
confere(r6.returncode == 1 and "revertidas" in r6.stdout and arvore(d2) == antes2,
        "falha na troca reverte substituicoes e remove arquivos novos")
# destino invalido
r4 = aplicar(os.path.join(TMP, "nao_existe")); confere(r4.returncode == 2, "destino que nao e o overlay LMU: rc=2 e nada alterado")
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{ok} ok, {len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
