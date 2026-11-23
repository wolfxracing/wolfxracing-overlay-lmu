# -*- coding: utf-8 -*-
"""Build bb: regressoes do validador de release e dos comandos GitHub (tools/validar_release.py + release.yml).
O GitHub e SIMULADO (executor falso e um `gh` falso no PATH): nada e criado, excluido ou publicado em lugar nenhum.
Defeito reproduzido pela auditoria: `gh release view` com erro HTTP 503 fazia validar() devolver lista vazia (= liberar)."""
import hashlib, json, os, re, stat, subprocess, sys, tempfile, shutil
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import validar_release as V

falhas, _ok = [], 0
def confere(c, m):
    global _ok
    if c: _ok += 1
    else: falhas.append(m); print("FALHA", m)

SHA = "a" * 40
OUTRO = "b" * 40
REPO = "dono/repo"

def fake(rotas, log=None):
    """Executor falso. rotas: lista de (predicado(args), (rc, out, err)); a primeira que casar responde."""
    def ex(args, binario=False, timeout=0):
        if log is not None: log.append(list(args))
        for pred, resp in rotas:
            if pred(args):
                rc, out, err = resp(args) if callable(resp) else resp
                if binario and isinstance(out, str): out = out.encode()
                return rc, out, err
        return 1, "", "HTTP 404: Not Found (rota nao simulada: %s)" % " ".join(args)
    return ex

def lista(*releases):
    return lambda a: a[0] == "api" and "--paginate" in a
def resp_lista(*rels): return (0, json.dumps([list(rels)]), "")
def rel(tag, draft, id=1, **kw):
    d = {"tag_name": tag, "draft": draft, "id": id, "assets": [], "html_url": "https://x/" + tag, "target_commitish": SHA}
    d.update(kw); return d

# ---------------------------------------------------------------- estado_release / Indeterminado
for nome, resposta in {"503": (1, "", "gh: HTTP 503: Service Unavailable"), "403": (1, "", "HTTP 403: Resource not accessible"), "rede": (1, "", "dial tcp: i/o timeout"),
                       "timeout_do_gh": (-1, "", "Command timed out"), "json_invalido": (0, "<html>erro</html>", ""), "formato_inesperado": (0, json.dumps({"message": "x"}), ""),
                       "item_sem_campos": (0, json.dumps([[{"foo": 1}]]), "")}.items():
    ex = fake([(lista(), resposta)])
    try:
        V.estado_release("v1.8.2", REPO, ex); levantou = False
    except V.Indeterminado:
        levantou = True
    confere(levantou, f"estado_release: '{nome}' e INDETERMINADO (nao vira 'inexistente')")

confere(V.estado_release("v1.8.2", REPO, fake([(lista(), resp_lista())]))[0] == "inexistente", "estado_release: lista lida e sem a tag = inexistente")
confere(V.estado_release("v1.8.2", REPO, fake([(lista(), resp_lista(rel("v1.8.1", False)))]))[0] == "inexistente", "estado_release: outra tag publicada nao conta")
confere(V.estado_release("v1.8.2", REPO, fake([(lista(), resp_lista(rel("v1.8.2", True)))]))[0] == "rascunho", "estado_release: rascunho")
confere(V.estado_release("v1.8.2", REPO, fake([(lista(), resp_lista(rel("v1.8.2", False)))]))[0] == "publicada", "estado_release: publicada")
confere(V.estado_release("v1.8.2", REPO, fake([(lista(), resp_lista(rel("v1.8.2", True, 1), rel("v1.8.2", False, 2)))]))[0] == "publicada", "estado_release: rascunho + publicada da mesma tag = publicada (a mais restritiva)")

# ---------------------------------------------------------------- validar() (repositorio temporario)
def repo_temp(versao="1.8.2", changelog_versao=None, com_origin=True):
    d = tempfile.mkdtemp(prefix="wolfx_rel_")
    run = lambda *a: subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, check=True).stdout.strip()
    run("init", "-q", "-b", "main"); run("config", "user.email", "t@t"); run("config", "user.name", "t")
    os.makedirs(os.path.join(d, "overlay"))
    open(os.path.join(d, "CHANGELOG.md"), "w", encoding="utf-8").write("# H\n\n## [%s] - 2026-11-22\n" % (changelog_versao or versao))
    open(os.path.join(d, "overlay", "overlay_iracing.py"), "w", encoding="utf-8").write('VERSAO_PRODUTO = "%s"\nBUILD = "bb"\n' % versao)
    run("add", "-A"); run("commit", "-q", "-m", "c")
    if com_origin:
        origem = d + "_origem"
        subprocess.run(["git", "clone", "-q", "--bare", d, origem], check=True, capture_output=True)
        run("remote", "add", "origin", origem); run("fetch", "-q", "origin", "main")
    return d, run, run("rev-parse", "HEAD")

d, run, head = repo_temp()
ok_exec = fake([(lista(), resp_lista())])
confere(V.validar("v1.8.2", head, REPO, True, d, ok_exec) == [], "validar: caso feliz (tag inexistente, HEAD = ponta da main, sem release)")
confere(any("indeterminado" in e for e in V.validar("v1.8.2", head, REPO, True, d, fake([(lista(), (1, "", "HTTP 503"))]))), "validar: 503 do GitHub BLOQUEIA (defeito reproduzido pela auditoria)")
confere(any("indeterminado" in e for e in V.validar("v1.8.2", head, REPO, True, d, fake([(lista(), (1, "", "HTTP 403"))]))), "validar: 403 BLOQUEIA")
confere(any("indeterminado" in e for e in V.validar("v1.8.2", head, REPO, True, d, fake([(lista(), (0, "lixo", ""))]))), "validar: resposta ilegivel BLOQUEIA")
confere(any("PUBLICADA" in e for e in V.validar("v1.8.2", head, REPO, True, d, fake([(lista(), resp_lista(rel("v1.8.2", False)))]))), "validar: release publicada BLOQUEIA")
confere(V.validar("v1.8.2", head, REPO, True, d, fake([(lista(), resp_lista(rel("v1.8.2", True)))])) == [], "validar: rascunho antigo NAO bloqueia")
confere(any("repositorio nao informado" in e for e in V.validar("v1.8.2", head, "", True, d, ok_exec)), "validar: sem repositorio no modo GitHub BLOQUEIA (antes pulava a conferencia)")
confere(any("nao e o commit em execucao" in e for e in V.validar("v1.8.2", OUTRO, REPO, True, d, ok_exec)), "validar: SHA diferente do checkout BLOQUEIA")
confere(any("CHANGELOG" in e for e in V.validar("v1.8.3", head, REPO, True, d, ok_exec)), "validar: versao da tag diferente do CHANGELOG/VERSAO_PRODUTO BLOQUEIA")
run("tag", "v1.8.2", head)
confere(V.validar("v1.8.2", head, REPO, True, d, ok_exec) == [], "validar: tag existente apontando para o commit = ok")
run("commit", "-q", "--allow-empty", "-m", "novo"); novo = run("rev-parse", "HEAD")
confere(any("ja existe e aponta para" in e for e in V.validar("v1.8.2", novo, REPO, True, d, ok_exec)), "validar: tag existente apontando para OUTRO commit BLOQUEIA")
run("tag", "-d", "v1.8.2")
confere(any("nao e a ponta da main" in e for e in V.validar("v1.8.2", novo, REPO, True, d, ok_exec)), "validar: tag nova fora da ponta da main BLOQUEIA")
run("remote", "set-url", "origin", d + "_inexistente")
confere(any("git fetch" in e for e in V.validar("v1.8.2", novo, REPO, True, d, ok_exec)), "validar: falha do git fetch BLOQUEIA (antes era ignorada)")
shutil.rmtree(d, ignore_errors=True); shutil.rmtree(d + "_origem", ignore_errors=True)
confere(V.validar("1.8.2", SHA, REPO, True, RAIZ, ok_exec)[0].startswith("a tag"), "validar: tag sem o 'v' e recusada")

# ---------------------------------------------------------------- excluir_rascunho
def rotas_excluir(estado_lista, atual_por_id, delete=(0, "", ""), log=None):
    return fake([(lista(), estado_lista),
                 (lambda a: a[:2] == ["api", "-X"] and a[2] == "DELETE", delete),
                 (lambda a: a[0] == "api" and re.fullmatch(r"repos/dono/repo/releases/\d+", a[-1]) is not None, atual_por_id)], log)

log = []
e = V.excluir_rascunho("v1.8.2", REPO, rotas_excluir(resp_lista(rel("v1.8.2", False)), (0, json.dumps(rel("v1.8.2", False)), ""), log=log))
confere(e and not any("DELETE" in a for a in log), "excluir_rascunho: release PUBLICADA nunca e excluida (nenhum DELETE enviado)")
log = []
e = V.excluir_rascunho("v1.8.2", REPO, rotas_excluir((1, "", "HTTP 503"), (0, "{}", ""), log=log))
confere(e and not any("DELETE" in a for a in log), "excluir_rascunho: 503 ao listar -> bloqueia, nenhum DELETE")
log = []
e = V.excluir_rascunho("v1.8.2", REPO, rotas_excluir(resp_lista(rel("v1.8.2", True, 7)), (1, "", "HTTP 502"), log=log))
confere(e and not any("DELETE" in a for a in log), "excluir_rascunho: falha ao reconfirmar o rascunho -> bloqueia, nenhum DELETE")
log = []
e = V.excluir_rascunho("v1.8.2", REPO, rotas_excluir(resp_lista(rel("v1.8.2", True, 7)), (0, json.dumps(rel("v1.8.2", False, 7)), ""), log=log))
confere(e and not any("DELETE" in a for a in log), "excluir_rascunho: virou publicada entre a listagem e a reconfirmacao -> NAO exclui")
log = []
e = V.excluir_rascunho("v1.8.2", REPO, rotas_excluir(resp_lista(rel("v1.8.2", True, 7)), (0, json.dumps(rel("v1.8.9", True, 7)), ""), log=log))
confere(e and not any("DELETE" in a for a in log), "excluir_rascunho: id com outra tag -> NAO exclui")
log = []
e = V.excluir_rascunho("v1.8.2", REPO, rotas_excluir(resp_lista(rel("v1.8.2", True, 7)), (0, json.dumps(rel("v1.8.2", True, 7)), ""), log=log))
dels = [i for i, a in enumerate(log) if "DELETE" in a]; gets = [i for i, a in enumerate(log) if a[-1].endswith("/releases/7") and "DELETE" not in a and "-X" not in a]
confere(e == [] and len(dels) == 1 and gets and gets[-1] < dels[0] and log[dels[0]][-1].endswith("/releases/7"), "excluir_rascunho: rascunho confirmado POR ID imediatamente antes do unico DELETE")
e = V.excluir_rascunho("v1.8.2", REPO, rotas_excluir(resp_lista(rel("v1.8.2", True, 7)), (0, json.dumps(rel("v1.8.2", True, 7)), ""), delete=(1, "", "HTTP 500")))
confere(e != [], "excluir_rascunho: falha do DELETE e reportada")
confere(V.excluir_rascunho("v1.8.2", REPO, rotas_excluir(resp_lista(), (0, "{}", ""))) == [], "excluir_rascunho: nada a excluir = ok")

# ---------------------------------------------------------------- conferir_anexos
tmp = tempfile.mkdtemp(prefix="wolfx_anx_")
arq = os.path.join(tmp, "Overlay iRacing.streamDeckProfile"); open(arq, "wb").write(b"conteudo-bom")
sha_ok = hashlib.sha256(b"conteudo-bom").hexdigest()
def com_anexo(**a):
    base = {"id": 55, "name": "Overlay.iRacing.streamDeckProfile", "size": 12}; base.update(a)
    return rel("v1.8.2", True, 7, assets=[base])
def ex_anexos(release, baixa=(0, b"conteudo-bom", "")):
    return fake([(lista(), resp_lista(release)), (lambda a: "Accept: application/octet-stream" in a, baixa)])
confere(V.conferir_anexos(REPO, "v1.8.2", [arq], ex_anexos(com_anexo(digest="sha256:" + sha_ok))) == [], "anexos: digest igual ao local (nome com espaco normalizado para ponto)")
confere(V.conferir_anexos(REPO, "v1.8.2", [arq], ex_anexos(com_anexo(digest="sha256:" + "0" * 64))) != [], "anexos: digest diferente BLOQUEIA")
confere(V.conferir_anexos(REPO, "v1.8.2", [arq], ex_anexos(com_anexo(digest=None))) == [], "anexos: sem digest, baixa e confere o CONTEUDO (ok)")
confere(V.conferir_anexos(REPO, "v1.8.2", [arq], ex_anexos(com_anexo(digest=None), (0, b"conteudo-ruim", ""))) != [], "anexos: sem digest, conteudo baixado diferente BLOQUEIA (mesmo com tamanho igual)")
confere(V.conferir_anexos(REPO, "v1.8.2", [arq], ex_anexos(com_anexo(digest=None, size=999), (0, b"conteudo-bom", ""))) == [], "anexos: o tamanho nao e criterio (conteudo igual passa)")
confere(V.conferir_anexos(REPO, "v1.8.2", [arq], ex_anexos(com_anexo(digest=None), (1, b"", "HTTP 500"))) != [], "anexos: sem digest e download falhou BLOQUEIA")
confere(V.conferir_anexos(REPO, "v1.8.2", [arq], ex_anexos(com_anexo(digest="md5:abc"), (0, b"conteudo-ruim", ""))) != [], "anexos: digest nao-SHA-256 nao e aceito (baixa e compara)")
confere(V.conferir_anexos(REPO, "v1.8.2", [arq], ex_anexos(rel("v1.8.2", True, 7, assets=[]))) != [], "anexos: anexo ausente BLOQUEIA")
confere(V.conferir_anexos(REPO, "v1.8.2", [arq], ex_anexos(rel("v1.8.2", True, 7, assets=[{"id": 55, "name": "Overlay.iRacing.streamDeckProfile", "digest": "sha256:" + sha_ok}, {"id": 56, "name": "intruso.exe", "digest": "sha256:" + "1" * 64}]))) != [], "anexos: anexo inesperado BLOQUEIA")
confere(V.conferir_anexos(REPO, "v1.8.2", [arq], fake([(lista(), (1, "", "HTTP 503"))])) != [], "anexos: 503 ao ler a release BLOQUEIA")
shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------- pre_publicacao
def ex_pre(releases, tag_resp, extra=()):
    return fake([(lista(), releases), (lambda a: a[0] == "api" and "/git/ref/tags/" in a[-1], tag_resp), *extra])
rasc = resp_lista(rel("v1.8.2", True, 7, target_commitish=SHA))
tag_ok = (0, json.dumps({"object": {"sha": SHA, "type": "commit"}}), "")
confere(V.pre_publicacao(REPO, "v1.8.2", SHA, ex_pre(rasc, (1, "", "HTTP 404: Not Found"))) == [], "pre-publicacao: rascunho mira o alvo e a tag ainda nao existe = ok")
confere(V.pre_publicacao(REPO, "v1.8.2", OUTRO, ex_pre(rasc, (1, "", "HTTP 404: Not Found"))) != [], "pre-publicacao: rascunho mira OUTRO commit BLOQUEIA")
confere(V.pre_publicacao(REPO, "v1.8.2", SHA, ex_pre(rasc, tag_ok)) == [], "pre-publicacao: tag existente = alvo ok")
confere(V.pre_publicacao(REPO, "v1.8.2", OUTRO, ex_pre(rasc, tag_ok)) != [], "pre-publicacao: tag existente aponta para outro commit BLOQUEIA")
anot = (0, json.dumps({"object": {"sha": "c" * 40, "type": "tag"}}), "")
confere(V.pre_publicacao(REPO, "v1.8.2", SHA, ex_pre(rasc, anot, [(lambda a: "/git/tags/" in a[-1], (0, json.dumps({"object": {"sha": SHA}}), ""))])) == [], "pre-publicacao: tag anotada resolvida para o commit")
confere(V.pre_publicacao(REPO, "v1.8.2", SHA, ex_pre(rasc, (1, "", "HTTP 503: Service Unavailable"))) != [], "pre-publicacao: 503 ao consultar a tag BLOQUEIA (nao e 'tag inexistente')")
confere(V.pre_publicacao(REPO, "v1.8.2", SHA, ex_pre(resp_lista(rel("v1.8.2", False)), tag_ok)) != [], "pre-publicacao: release ja publicada BLOQUEIA")
confere(V.pre_publicacao(REPO, "v1.8.2", SHA, ex_pre(resp_lista(), tag_ok)) != [], "pre-publicacao: release inexistente BLOQUEIA")
confere(V.pre_publicacao(REPO, "v1.8.2", SHA, ex_pre((1, "", "HTTP 502"), tag_ok)) != [], "pre-publicacao: falha ao ler a release BLOQUEIA")

# ---------------------------------------------------------------- CLI com `gh` falso no PATH (codigos de saida de verdade)
bindir = tempfile.mkdtemp(prefix="wolfx_gh_"); logf = os.path.join(bindir, "chamadas.log")
script = os.path.join(bindir, "gh_falso.py")
open(script, "w", encoding="utf-8").write(r'''
import os, sys, json
a = sys.argv[1:]
open(os.environ["GH_LOG"], "a", encoding="utf-8").write(" ".join(a) + "\n")
modo = os.environ.get("GH_MODO", "")
if modo == "503": sys.stderr.write("gh: HTTP 503: Service Unavailable\n"); sys.exit(1)
rels = {"vazio": [], "rascunho": [{"tag_name": "v1.8.2", "draft": True, "id": 7, "assets": []}], "publicada": [{"tag_name": "v1.8.2", "draft": False, "id": 8, "assets": [], "html_url": "u"}]}[modo]
if "--paginate" in a: print(json.dumps([rels])); sys.exit(0)
if a[:3] == ["api", "-X", "DELETE"]: sys.exit(0)
if a[0] == "api" and a[-1].endswith("/releases/7"): print(json.dumps(rels[0])); sys.exit(0)
sys.exit(1)
''')
if os.name == "nt":
    open(os.path.join(bindir, "gh.cmd"), "w").write('@echo off\r\n"%s" "%s" %%*\r\n' % (sys.executable, script))
else:
    p = os.path.join(bindir, "gh"); open(p, "w").write('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, script)); os.chmod(p, 0o755)
def cli(modo, *args):
    env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"], GH_MODO=modo, GH_LOG=logf, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, os.path.join(RAIZ, "tools", "validar_release.py"), "--tag", "v1.8.2", "--repo", REPO, *args], capture_output=True, text=True, env=env, timeout=120)
    return r.returncode, r.stdout + r.stderr
confere(cli("503", "--acao", "estado")[0] == 1, "CLI estado: 503 -> codigo de saida 1")
confere(cli("vazio", "--acao", "estado")[1].strip() == "inexistente", "CLI estado: inexistente")
confere(cli("rascunho", "--acao", "estado")[1].strip() == "rascunho" and cli("publicada", "--acao", "estado")[1].strip() == "publicada", "CLI estado: rascunho e publicada")
open(logf, "w").close()
rc, out = cli("publicada", "--acao", "excluir-rascunho")
confere(rc == 1 and "DELETE" not in open(logf).read(), "CLI excluir-rascunho: release publicada -> codigo 1 e nenhum DELETE chamado")
open(logf, "w").close()
rc, out = cli("503", "--acao", "excluir-rascunho")
confere(rc == 1 and "DELETE" not in open(logf).read(), "CLI excluir-rascunho: 503 -> codigo 1 e nenhum DELETE")
open(logf, "w").close()
rc, out = cli("rascunho", "--acao", "excluir-rascunho")
confere(rc == 0 and open(logf).read().count("DELETE") == 1, "CLI excluir-rascunho: rascunho -> exclui uma vez, codigo 0")
shutil.rmtree(bindir, ignore_errors=True)

# ---------------------------------------------------------------- release.yml (analise estatica das salvaguardas)
yml = "\n".join(l for l in open(os.path.join(RAIZ, ".github", "workflows", "release.yml"), encoding="utf-8").read().splitlines() if not l.lstrip().startswith("#"))   # sem comentarios
confere("gh release delete" not in yml, "release.yml: nao usa `gh release delete` (exclusao so pelo validador, com reconfirmacao)")
confere("--clobber" not in yml, "release.yml: sem --clobber")
confere(".size -ne" not in yml and "tamanho local" not in yml, "release.yml: sem comparacao so por tamanho")
i_exc, i_conf, i_pre, i_pub = (yml.find(k) for k in ("--acao excluir-rascunho", "--acao conferir-anexos", "--acao pre-publicacao", "gh release edit $env:TAG --draft=false"))
confere(0 < i_exc < i_conf < i_pre < i_pub, "release.yml: ordem excluir-rascunho -> conferir-anexos -> pre-publicacao -> publicar")
confere("function Exec" in yml and "$LASTEXITCODE -ne 0" in yml and yml.count("Exec {") >= 5, "release.yml: comandos externos da publicacao passam por Exec (codigo de saida conferido)")
confere("gh release edit $env:TAG --draft=false }" in yml, "release.yml: a publicacao esta dentro de Exec")
confere("if ($LASTEXITCODE -ne 0) { throw \"nao foi possivel ler a tag" in yml, "release.yml: leitura da tag depois de publicar tem o codigo de saida conferido")

print("\n%d ok, %d falha(s)" % (_ok, len(falhas)))
sys.exit(1 if falhas else 0)
