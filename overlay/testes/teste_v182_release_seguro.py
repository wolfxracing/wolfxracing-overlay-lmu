# -*- coding: utf-8 -*-
"""Build bb/bc: regressoes do validador de release e dos comandos GitHub (tools/validar_release.py + release.yml).
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
confere(any("RASCUNHO" in e for e in V.validar("v1.8.2", head, REPO, True, d, fake([(lista(), resp_lista(rel("v1.8.2", True)))]))), "validar: rascunho anterior BLOQUEIA (build bc: decisao humana, o fluxo nao o exclui)")
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

# ---------------------------------------------------------------- build bc: sem exclusao automatica
fonte_validador = open(os.path.join(RAIZ, "tools", "validar_release.py"), encoding="utf-8").read()
confere(not hasattr(V, "excluir_rascunho"), "build bc: excluir_rascunho() nao existe mais (o fluxo nao exclui release)")
confere("DELETE" not in fonte_validador and "release delete" not in fonte_validador, "build bc: o validador nao contem nenhum comando DELETE / release delete")
confere(V.exigir_inexistente("v1.8.2", REPO, fake([(lista(), resp_lista())])) == [], "exigir_inexistente: nada publicado nem rascunho = ok")
confere(V.exigir_inexistente("v1.8.2", REPO, fake([(lista(), resp_lista(rel("v1.8.2", True)))])) != [], "exigir_inexistente: rascunho anterior BLOQUEIA")
confere(V.exigir_inexistente("v1.8.2", REPO, fake([(lista(), resp_lista(rel("v1.8.2", False)))])) != [], "exigir_inexistente: publicada BLOQUEIA")
confere(V.exigir_inexistente("v1.8.2", REPO, fake([(lista(), (1, "", "HTTP 503"))])) != [], "exigir_inexistente: 503 BLOQUEIA")

# ---------------------------------------------------------------- build bc: resolver_tag / conferir_tag (tag leve x anotada)
ref_leve = lambda sha: (0, json.dumps({"object": {"sha": sha, "type": "commit"}}), "")
ref_anot = lambda obj: (0, json.dumps({"object": {"sha": obj, "type": "tag"}}), "")
obj_tag = lambda sha, tipo="commit": (0, json.dumps({"object": {"sha": sha, "type": tipo}}), "")
def ex_tag(ref, extra=()):
    return fake([(lambda a: "/git/ref/tags/" in a[-1], ref), *extra])
T1 = "c" * 40; T2 = "d" * 40
confere(V.resolver_tag(REPO, "v1.8.2", ex_tag(ref_leve(SHA))) == ("existe", SHA), "resolver_tag: tag leve -> o proprio commit")
confere(V.resolver_tag(REPO, "v1.8.2", ex_tag(ref_anot(T1), [(lambda a: a[-1].endswith("/git/tags/" + T1), obj_tag(SHA))])) == ("existe", SHA), "resolver_tag: tag anotada -> commit apontado")
confere(V.resolver_tag(REPO, "v1.8.2", ex_tag(ref_anot(T1), [(lambda a: a[-1].endswith("/git/tags/" + T1), obj_tag(T2, "tag")), (lambda a: a[-1].endswith("/git/tags/" + T2), obj_tag(SHA))])) == ("existe", SHA), "resolver_tag: tag anotada encadeada -> commit")
confere(V.resolver_tag(REPO, "v1.8.2", ex_tag((1, "", "HTTP 404: Not Found")))[0] == "inexistente", "resolver_tag: 404 = inexistente")
confere(V.resolver_tag(REPO, "v1.8.2", ex_tag((1, "", "HTTP 503")))[0] == "erro", "resolver_tag: 503 = erro (nao inexistente)")
confere(V.resolver_tag(REPO, "v1.8.2", ex_tag((0, "lixo", "")))[0] == "erro", "resolver_tag: JSON invalido = erro")
confere(V.resolver_tag(REPO, "v1.8.2", ex_tag(ref_anot(T1), [(lambda a: "/git/tags/" in a[-1], (1, "", "HTTP 502"))]))[0] == "erro", "resolver_tag: falha ao seguir a tag anotada = erro")
confere(V.conferir_tag(REPO, "v1.8.2", SHA, ex_tag(ref_leve(SHA))) == [], "conferir_tag: tag simples apontando para o commit correto = ok")
confere(V.conferir_tag(REPO, "v1.8.2", SHA, ex_tag(ref_anot(T1), [(lambda a: a[-1].endswith("/git/tags/" + T1), obj_tag(SHA))])) == [], "conferir_tag: tag ANOTADA apontando para o commit correto = ok (a build bb reprovaria: comparava o SHA do objeto da tag)")
confere(V.conferir_tag(REPO, "v1.8.2", SHA, ex_tag(ref_leve(OUTRO))) != [], "conferir_tag: tag apontando para outro commit = erro")
confere(V.conferir_tag(REPO, "v1.8.2", SHA, ex_tag(ref_anot(T1), [(lambda a: a[-1].endswith("/git/tags/" + T1), obj_tag(OUTRO))])) != [], "conferir_tag: tag anotada apontando para outro commit = erro")
confere(V.conferir_tag(REPO, "v1.8.2", SHA, ex_tag((1, "", "HTTP 503"))) != [], "conferir_tag: falha na consulta da tag = erro")
confere(V.conferir_tag(REPO, "v1.8.2", SHA, ex_tag((1, "", "HTTP 404: Not Found"))) != [], "conferir_tag: tag inexistente depois de publicar = erro")

# ---------------------------------------------------------------- build bc: GitHub simulado COM ESTADO, duas execucoes concorrentes
class GitHubFalso:
    """Estado de releases e tags; responde as chamadas que o fluxo faz (python e gh release create/edit do workflow). Registra tudo."""
    def __init__(self):
        self.releases = []; self.tags = {}; self.log = []; self.prox = 1
    def __call__(self, args, binario=False, timeout=0):
        self.log.append(list(args))
        if args[0] == "api" and "--paginate" in args:
            return 0, json.dumps([[dict(r) for r in self.releases]]), ""
        if args[0] == "api" and "/git/ref/tags/" in args[-1]:
            t = args[-1].rsplit("/", 1)[-1]
            return (0, json.dumps({"object": {"sha": self.tags[t], "type": "commit"}}), "") if t in self.tags else (1, "", "HTTP 404: Not Found")
        return 1, "", "HTTP 404: Not Found"
    # o que o workflow faz direto com o gh:
    def criar_rascunho(self, quem, tag, alvo):
        self.log.append(["release", "create", tag, "--draft", "--target", alvo, quem])
        self.releases.append({"tag_name": tag, "draft": True, "id": self.prox, "assets": [], "target_commitish": alvo, "autor": quem}); self.prox += 1
    def publicar(self, quem, tag):
        self.log.append(["release", "edit", tag, "--draft=false", quem])
        alvo = [r for r in self.releases if r["tag_name"] == tag and r["draft"] and r["autor"] == quem] or [r for r in self.releases if r["tag_name"] == tag and r["draft"]]
        if alvo:
            alvo[0]["draft"] = False; self.tags.setdefault(tag, alvo[0]["target_commitish"])
    def deletes(self):
        return [c for c in self.log if any("DELETE" in str(x) or "delete" in str(x) for x in c)]

def fluxo(gh, quem, alvo, passo):
    """Executa o fluxo do workflow por etapas (gerador); cada yield e um ponto onde a outra execucao pode intercalar."""
    if V.exigir_inexistente("v1.8.2", REPO, gh): return "parou: release/rascunho anterior"
    yield
    gh.criar_rascunho(quem, "v1.8.2", alvo)
    yield
    if V.pre_publicacao(REPO, "v1.8.2", alvo, gh): return "parou: pre-publicacao"
    yield
    gh.publicar(quem, "v1.8.2")
    yield
    if V.conferir_tag(REPO, "v1.8.2", alvo, gh): return "parou: tag"
    return "publicou"
def rodar(gh, *gens):
    res = {}; ativos = dict(gens)
    while ativos:
        for nome in list(ativos):
            try: next(ativos[nome])
            except StopIteration as fim: res[nome] = fim.value; del ativos[nome]
    return res

# (a) sequencial: A publica; B chega depois e para no rascunho/publicada existente
gh = GitHubFalso(); r = rodar(gh, ("A", fluxo(gh, "A", SHA, 0)))
r.update(rodar(gh, ("B", fluxo(gh, "B", SHA, 0))))
confere(r == {"A": "publicou", "B": "parou: release/rascunho anterior"} and not gh.deletes(), f"concorrencia (a): A publica, B para; nenhum DELETE ({r})")
# (b) intercaladas desde o inicio (o que o 'concurrency' do workflow impede; aqui sem ele, no pior caso)
gh = GitHubFalso(); r = rodar(gh, ("A", fluxo(gh, "A", SHA, 0)), ("B", fluxo(gh, "B", SHA, 0)))
publicadas = [x for x in gh.releases if not x["draft"]]
confere(not gh.deletes(), f"concorrencia (b): duas execucoes intercaladas nunca enviam DELETE ({r})")
confere(len(publicadas) <= 1 and list(r.values()).count("publicou") <= 1, f"concorrencia (b): no maximo UMA publicacao (dois rascunhos da mesma tag = ninguem publica) ({r})")
confere(all(x["draft"] for x in gh.releases) and len(gh.releases) == 2, "concorrencia (b): os dois rascunhos ficam intactos para decisao humana (nada excluido)")
confere(not any(c[:2] == ["release", "edit"] for c in gh.log), "concorrencia (b): nenhum 'release edit' foi enviado")
# (b2) intercaladas mas B so comeca depois de A criar o rascunho: B para em exigir-inexistente, A publica
gh = GitHubFalso(); ga = fluxo(gh, "A", SHA, 0); next(ga); next(ga)
r = rodar(gh, ("B", fluxo(gh, "B", SHA, 0)), ("A", ga))
confere(r == {"B": "parou: release/rascunho anterior", "A": "publicou"} and not gh.deletes(), f"concorrencia (b2): B para no rascunho de A, A publica, nenhum DELETE ({r})")
# (c) draft=true -> draft=false por fora entre a conferencia e o proximo passo: o fluxo para e nao exclui nada
gh = GitHubFalso(); g = fluxo(gh, "A", SHA, 0); next(g); next(g)       # A ja criou o rascunho
gh.publicar("humano", "v1.8.2")                                           # alguem publica por fora
try: next(g); res = "seguiu"
except StopIteration as fim: res = fim.value
confere(res == "parou: pre-publicacao" and not gh.deletes(), f"draft=true -> draft=false por fora: o fluxo para na pre-publicacao, nenhum DELETE ({res})")
# (d) rascunho deixado por execucao anterior que falhou: o fluxo novo para (nao exclui, nao reaproveita)
gh = GitHubFalso(); gh.criar_rascunho("execucao_que_falhou", "v1.8.2", OUTRO)
r = rodar(gh, ("A", fluxo(gh, "A", SHA, 0)))
confere(r == {"A": "parou: release/rascunho anterior"} and len(gh.releases) == 1 and gh.releases[0]["draft"] and not gh.deletes(), f"rascunho anterior: o fluxo para e deixa o rascunho intacto para decisao humana ({r})")

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
if a[0] == "api" and "/git/ref/tags/" in a[-1]:
    if modo == "publicada": print(json.dumps({"object": {"sha": "c" * 40, "type": "tag"}})); sys.exit(0)
    sys.stderr.write("HTTP 404: Not Found\n"); sys.exit(1)
if a[0] == "api" and "/git/tags/" in a[-1]: print(json.dumps({"object": {"sha": "a" * 40, "type": "commit"}})); sys.exit(0)
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
confere(cli("vazio", "--acao", "exigir-inexistente")[0] == 0, "CLI exigir-inexistente: sem release -> 0")
confere(cli("rascunho", "--acao", "exigir-inexistente")[0] == 1, "CLI exigir-inexistente: rascunho -> 1")
confere(cli("publicada", "--acao", "exigir-inexistente")[0] == 1, "CLI exigir-inexistente: publicada -> 1")
confere(cli("503", "--acao", "exigir-inexistente")[0] == 1, "CLI exigir-inexistente: 503 -> 1")
confere(cli("publicada", "--acao", "conferir-tag", "--sha", SHA)[0] == 0, "CLI conferir-tag: tag ANOTADA resolvida para o commit -> 0")
confere(cli("publicada", "--acao", "conferir-tag", "--sha", OUTRO)[0] == 1, "CLI conferir-tag: commit diferente -> 1")
confere(cli("503", "--acao", "conferir-tag", "--sha", SHA)[0] == 1, "CLI conferir-tag: falha na consulta -> 1")
confere(cli("vazio", "--acao", "excluir-rascunho")[0] != 0, "CLI: a acao excluir-rascunho nao existe mais")
chamadas = open(logf, encoding="utf-8").read()
confere("DELETE" not in chamadas and "delete" not in chamadas, "CLI: nenhuma chamada DELETE/delete chegou ao gh em nenhum cenario")
shutil.rmtree(bindir, ignore_errors=True)

# ---------------------------------------------------------------- release.yml (analise estatica das salvaguardas)
yml = "\n".join(l for l in open(os.path.join(RAIZ, ".github", "workflows", "release.yml"), encoding="utf-8").read().splitlines() if not l.lstrip().startswith("#"))   # sem comentarios
confere("gh release delete" not in yml, "release.yml: nao usa `gh release delete` (exclusao so pelo validador, com reconfirmacao)")
confere("--clobber" not in yml, "release.yml: sem --clobber")
confere(".size -ne" not in yml and "tamanho local" not in yml, "release.yml: sem comparacao so por tamanho")
ordem = [yml.find(k) for k in ("--acao exigir-inexistente", "gh release create", "--acao conferir-anexos", "--acao pre-publicacao", "gh release edit $env:TAG --draft=false", "--acao conferir-tag")]
confere(all(x > 0 for x in ordem) and ordem == sorted(ordem), "release.yml: ordem exigir-inexistente -> criar rascunho -> conferir-anexos -> pre-publicacao -> publicar -> conferir-tag")
confere("excluir-rascunho" not in yml and "DELETE" not in yml and "release delete" not in yml, "release.yml: nenhuma exclusao de release (nem rascunho)")
confere("$ref.object.sha -ne" not in yml, "release.yml: sem comparacao direta do SHA do objeto da tag (tag anotada) depois de publicar")
confere("function Exec" in yml and "$LASTEXITCODE -ne 0" in yml and yml.count("Exec {") >= 6, "release.yml: comandos externos da publicacao passam por Exec (codigo de saida conferido)")
confere("gh release edit $env:TAG --draft=false }" in yml, "release.yml: a publicacao esta dentro de Exec")
_bruto = open(os.path.join(RAIZ, ".github", "workflows", "release.yml"), encoding="utf-8").read()
_m = re.search(r"^concurrency:\n\s+group:\s*(.+)\n\s+cancel-in-progress:\s*(\S+)", _bruto, re.M)
_c = {"group": _m.group(1) if _m else "", "cancel-in-progress": (_m.group(2) == "false") is False if _m else None}
confere(bool(_m) and "github.repository" in _c["group"] and "inputs.tag" in _c["group"] and "github.ref_name" in _c["group"], f"release.yml: concurrency por repositorio e tag ({_c.get('group')})")
confere(_c.get("cancel-in-progress") is False, "release.yml: concurrency sem cancelar publicacao ativa (cancel-in-progress: false)")

print("\n%d ok, %d falha(s)" % (_ok, len(falhas)))
sys.exit(1 if falhas else 0)
