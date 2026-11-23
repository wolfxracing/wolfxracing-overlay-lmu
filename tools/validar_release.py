#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confere, ANTES de montar qualquer ativo, que a publicacao esta presa ao commit certo. Falha (exit 1) com a lista de problemas.

  python tools/validar_release.py --tag v1.8.2 --sha <GITHUB_SHA> [--repo dono/nome] [--sem-github]

Regras:
 1. a tag tem a forma vX.Y.Z e bate com o primeiro `## [X.Y.Z]` do CHANGELOG.md e com VERSAO_PRODUTO de overlay/overlay_iracing.py;
 2. se a tag JA existe, ela aponta exatamente para o commit em execucao (o fluxo nao empacota outro commit);
 3. se a tag NAO existe (disparo manual), o commit em execucao tem de ser a ponta da main (nao se publica de ramo avulso);
 4. o commit em execucao e o checkout (HEAD) sao o mesmo;
 5. nao existe release PUBLICADA com essa tag (release publicada nunca e reescrita; so rascunho de uma execucao anterior pode ser refeito);
 6. (build bb) QUALQUER resposta indeterminada do GitHub (erro 5xx, 403, rede, JSON invalido, timeout) BLOQUEIA: so 'release inexistente' liberada de forma
    positiva (a lista de releases foi lida com sucesso e a tag nao esta nela) deixa seguir.

Outras acoes (usadas pelo workflow de publicacao, cada uma com codigo de saida explicito):
  --acao estado              imprime inexistente|rascunho|publicada (rc 0) ou falha (rc 1) se indeterminado
  --acao excluir-rascunho    confirma que e RASCUNHO imediatamente antes de excluir (por id); nunca exclui release publicada
  --acao conferir-anexos     SHA-256 de cada anexo enviado = SHA-256 local (digest do GitHub ou, sem digest, baixa o anexo e confere o conteudo)
  --acao pre-publicacao      confere SHA da tag/alvo e estado de rascunho antes de `gh release edit --draft=false`"""
import argparse
import json
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args, raiz=None):
    r = subprocess.run(["git", "-C", raiz or RAIZ, *args], capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


# ----------------------------------------------------------------------------- GitHub (build bb)
class Indeterminado(Exception):
    """Resposta do GitHub que nao permite decidir (rede, 5xx, permissao, JSON invalido): o fluxo para."""


def executar_gh(args, binario=False, timeout=180):
    """Roda `gh ...`. Devolve (returncode, stdout, stderr). Excecao de execucao/timeout vira (-1, '', mensagem)."""
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=not binario, timeout=timeout)
        return r.returncode, r.stdout, (r.stderr if not binario else r.stderr.decode("utf-8", "replace"))
    except (OSError, subprocess.SubprocessError) as erro:
        return -1, "", str(erro)


def listar_releases(repo, executar=executar_gh):
    """Todas as releases (inclusive RASCUNHOS). Falha em qualquer pagina -> Indeterminado."""
    rc, out, err = executar(["api", "--paginate", "--slurp", "repos/%s/releases?per_page=100" % repo])
    if rc != 0:
        raise Indeterminado("falha ao listar as releases de %s (gh rc=%s): %s" % (repo, rc, (err or out or "").strip()[:300]))
    try:
        paginas = json.loads(out)
        itens = [x for pag in paginas for x in (pag if isinstance(pag, list) else [pag])]
        if not all(isinstance(x, dict) and "tag_name" in x and "draft" in x for x in itens):
            raise ValueError("formato inesperado")
    except (ValueError, TypeError) as erro:
        raise Indeterminado("resposta invalida do GitHub ao listar releases: %s" % erro)
    return itens


def estado_release(tag, repo, executar=executar_gh):
    """('inexistente'|'rascunho'|'publicada', release_dict|None). Lanca Indeterminado se nao der para saber."""
    achadas = [x for x in listar_releases(repo, executar) if x.get("tag_name") == tag]
    if not achadas:
        return "inexistente", None
    if any(not x.get("draft") for x in achadas):
        return "publicada", [x for x in achadas if not x.get("draft")][0]
    return "rascunho", achadas[0]


def excluir_rascunho(tag, repo, executar=executar_gh):
    """Exclui o rascunho de `tag`. Antes do DELETE le a release PELO ID e exige draft == true e a mesma tag. Nunca exclui release publicada.
    Devolve lista de erros (vazia = excluido ou nao havia nada)."""
    try:
        estado, rel = estado_release(tag, repo, executar)
    except Indeterminado as erro:
        return [str(erro)]
    if estado == "inexistente":
        return []
    if estado == "publicada":
        return ["ja existe uma release PUBLICADA para %s: ela nao e excluida nem reescrita" % tag]
    rid = rel.get("id")
    rc, out, err = executar(["api", "repos/%s/releases/%s" % (repo, rid)])
    if rc != 0:
        return ["nao foi possivel reconfirmar o rascunho %s antes de excluir (gh rc=%s): %s" % (rid, rc, (err or "").strip()[:200])]
    try:
        atual = json.loads(out)
    except ValueError:
        return ["resposta invalida ao reconfirmar o rascunho %s" % rid]
    if atual.get("draft") is not True or atual.get("tag_name") != tag:
        return ["a release %s deixou de ser rascunho de %s ao reconfirmar (draft=%s, tag=%s); nada foi excluido" % (rid, tag, atual.get("draft"), atual.get("tag_name"))]
    rc, out, err = executar(["api", "-X", "DELETE", "repos/%s/releases/%s" % (repo, rid)])
    if rc != 0:
        return ["falha ao excluir o rascunho %s (gh rc=%s): %s" % (rid, rc, (err or "").strip()[:200])]
    return []


def nome_no_github(nome):
    return re.sub(r"[^A-Za-z0-9._-]", ".", nome)


def sha256_arquivo(caminho):
    import hashlib
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def sha256_bytes(dados):
    import hashlib
    return hashlib.sha256(dados).hexdigest()


def conferir_anexos(repo, tag, arquivos, executar=executar_gh):
    """Cada arquivo local precisa existir na release com o MESMO SHA-256. Digest do GitHub quando ha; sem digest, baixa o anexo e confere o
    conteudo. Nunca aceita so o tamanho. Devolve lista de erros."""
    try:
        estado, rel = estado_release(tag, repo, executar)
    except Indeterminado as erro:
        return [str(erro)]
    if rel is None:
        return ["nao ha release/rascunho %s para conferir" % tag]
    erros = []
    enviados = {a.get("name"): a for a in rel.get("assets", [])}
    esperados = set()
    for caminho in arquivos:
        nome = nome_no_github(os.path.basename(caminho))
        esperados.add(nome)
        a = enviados.get(nome)
        if a is None:
            erros.append("anexo %s nao foi enviado" % nome)
            continue
        local = sha256_arquivo(caminho)
        digest = (a.get("digest") or "")
        if digest.startswith("sha256:") and re.fullmatch(r"[0-9a-f]{64}", digest[7:]):
            if digest[7:] != local:
                erros.append("anexo %s: SHA-256 local %s difere do digest do GitHub %s" % (nome, local, digest[7:]))
            continue
        rc, dados, err = executar(["api", "-H", "Accept: application/octet-stream", "repos/%s/releases/assets/%s" % (repo, a.get("id"))], binario=True)
        if rc != 0 or not isinstance(dados, (bytes, bytearray)):
            erros.append("anexo %s sem digest confiavel e o download falhou (gh rc=%s): %s" % (nome, rc, (err or "").strip()[:200]))
        elif sha256_bytes(bytes(dados)) != local:
            erros.append("anexo %s: o conteudo baixado difere do arquivo local" % nome)
    extras = sorted(set(enviados) - esperados)
    if extras:
        erros.append("anexos inesperados na release: %s" % ", ".join(extras))
    return erros


def pre_publicacao(repo, tag, alvo, executar=executar_gh, resolver_tag_local=None):
    """Ultima conferencia antes de `gh release edit --draft=false`. Devolve lista de erros.
    - a release e RASCUNHO (nunca publica por cima de publicada);
    - tag ja existente aponta para `alvo`; tag inexistente: o rascunho mira `alvo` (target_commitish) - o GitHub criara a tag nesse commit."""
    try:
        estado, rel = estado_release(tag, repo, executar)
    except Indeterminado as erro:
        return [str(erro)]
    if estado != "rascunho":
        return ["a release %s esta '%s', nao 'rascunho'; nao ha o que publicar" % (tag, estado)]
    erros = []
    rc, out, err = executar(["api", "repos/%s/git/ref/tags/%s" % (repo, tag)])
    if rc == 0:
        try:
            ref = json.loads(out)
            sha = ref["object"]["sha"]
            if ref["object"].get("type") == "tag":                 # tag anotada: resolve para o commit
                rc2, out2, err2 = executar(["api", "repos/%s/git/tags/%s" % (repo, sha)])
                if rc2 != 0:
                    return ["nao foi possivel resolver a tag anotada %s: %s" % (tag, (err2 or "").strip()[:200])]
                sha = json.loads(out2)["object"]["sha"]
        except (ValueError, KeyError, TypeError):
            return ["resposta invalida do GitHub ao ler a tag %s" % tag]
        if sha != alvo:
            erros.append("a tag %s ja existe e aponta para %s, nao para %s" % (tag, sha, alvo))
    elif "404" in (err or "") or "Not Found" in (err or ""):
        if (rel.get("target_commitish") or "") != alvo:
            erros.append("a tag %s ainda nao existe e o rascunho mira %r, nao %s" % (tag, rel.get("target_commitish"), alvo))
    else:
        erros.append("falha ao consultar a tag %s (gh rc=%s): %s" % (tag, rc, (err or "").strip()[:200]))
    return erros


def validar(tag, sha, repo="", com_github=True, raiz=RAIZ, executar=executar_gh):
    erros = []
    m = re.fullmatch(r"v(\d+\.\d+\.\d+)", tag or "")
    if not m:
        return ["a tag '%s' nao tem a forma vX.Y.Z" % tag]
    versao = m.group(1)
    sha = (sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        erros.append("SHA do commit invalido: %r" % sha)
    texto = open(os.path.join(raiz, "CHANGELOG.md"), encoding="utf-8").read()
    topo = re.search(r"^## \[(\d+\.\d+\.\d+)\]", texto, re.M)
    if not topo or topo.group(1) != versao:
        erros.append("o primeiro '## [X.Y.Z]' do CHANGELOG.md e %s, nao %s" % (topo.group(1) if topo else "ausente", versao))
    fonte = open(os.path.join(raiz, "overlay", "overlay_iracing.py"), encoding="utf-8").read()
    v = re.search(r'^VERSAO_PRODUTO\s*=\s*"([^"]+)"', fonte, re.M)
    b = re.search(r'^BUILD\s*=\s*"([^"]+)"', fonte, re.M)
    if not v or v.group(1) != versao:
        erros.append("VERSAO_PRODUTO em overlay_iracing.py e %s, nao %s" % (v.group(1) if v else "ausente", versao))
    if not b:
        erros.append("BUILD ausente em overlay_iracing.py")
    rc, head, _ = git("rev-parse", "HEAD", raiz=raiz)
    if rc != 0 or head != sha:
        erros.append("o checkout (%s) nao e o commit em execucao (%s)" % (head or "?", sha))
    rc, alvo, _ = git("rev-parse", "--verify", "refs/tags/%s^{commit}" % tag, raiz=raiz)
    if rc == 0:
        if alvo != sha:
            erros.append("a tag %s ja existe e aponta para %s, nao para o commit em execucao %s" % (tag, alvo, sha))
    else:
        rcf, _, errf = git("fetch", "--no-tags", "origin", "main", raiz=raiz)
        rc2, ponta, _ = git("rev-parse", "--verify", "refs/remotes/origin/main", raiz=raiz)
        if rcf != 0:
            erros.append("nao foi possivel atualizar origin/main para conferir a ponta da main (git fetch rc=%s): %s" % (rcf, errf[:200]))
        elif rc2 != 0 or ponta != sha:
            erros.append("a tag %s ainda nao existe e o commit em execucao (%s) nao e a ponta da main (%s)" % (tag, sha, ponta or "?"))
    if com_github:
        if not repo:
            erros.append("repositorio nao informado: sem ele nao ha como conferir as releases existentes (use --sem-github so em teste)")
        else:
            try:
                estado, rel = estado_release(tag, repo, executar)
            except Indeterminado as erro:
                erros.append("estado da release indeterminado, publicacao bloqueada: %s" % erro)
            else:
                if estado == "publicada":
                    erros.append("ja existe uma release PUBLICADA para %s (%s); ela nao e reescrita. Use uma nova versao." % (tag, rel.get("html_url")))
                elif estado == "rascunho":
                    print("aviso: existe um rascunho antigo de %s; sera substituido" % tag)
    return erros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--sha", default="")
    ap.add_argument("--repo", default="")
    ap.add_argument("--sem-github", action="store_true")
    ap.add_argument("--acao", default="validar", choices=["validar", "estado", "excluir-rascunho", "conferir-anexos", "pre-publicacao"])
    ap.add_argument("--arquivos", nargs="*", default=[])
    a = ap.parse_args()
    if a.acao == "estado":
        try:
            estado, _ = estado_release(a.tag, a.repo)
        except Indeterminado as erro:
            print("INDETERMINADO:", erro)
            return 1
        print(estado)
        return 0
    if a.acao in ("excluir-rascunho", "conferir-anexos", "pre-publicacao"):
        if a.acao == "excluir-rascunho":
            erros = excluir_rascunho(a.tag, a.repo)
        elif a.acao == "conferir-anexos":
            erros = conferir_anexos(a.repo, a.tag, a.arquivos)
        else:
            erros = pre_publicacao(a.repo, a.tag, (a.sha or "").lower())
        for e in erros:
            print(" -", e)
        if erros:
            print("%s: RECUSADO" % a.acao)
            return 1
        print("%s: ok" % a.acao)
        return 0
    erros = validar(a.tag, a.sha, a.repo, not a.sem_github)
    if erros:
        print("RELEASE RECUSADA:")
        for e in erros:
            print(" -", e)
        return 1
    print("ok: %s -> commit %s; versao e CHANGELOG conferem" % (a.tag, a.sha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
