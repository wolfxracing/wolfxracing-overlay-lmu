# -*- coding: utf-8 -*-
"""Build ba (1.8.2): atualizador completo do LMU. Gera o pacote a partir do codigo deste repositorio e o aplica em copias isoladas:
(1) --simular sem escrever; (2) trava ATIVA (processo vivo) recusa, tanto na atualizacao real quanto no --simular (codigo 4);
(3) trava ORFA (PID morto, trava vazia antiga) e removida com aviso e a atualizacao conclui; (4) dados do usuario byte a byte iguais;
(5) reversao com arquivo REALMENTE bloqueado (Windows: handle aberto sem FILE_SHARE_DELETE; nos demais sistemas, PermissionError injetado);
(6) pacote adulterado e pasta invalida; (7) idempotencia; (8) o conteudo de programa\\ e igual ao zip de codigo da mesma fonte."""
import os, sys, json, time, shutil, hashlib, tempfile, zipfile, subprocess, importlib.util
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import gerar_atualizador_lmu as ger
import inventario_release as inv

falhas, _ok = [], 0
def confere(c, m):
    global _ok
    if c: _ok += 1
    else: falhas.append(m); print("FALHA", m)
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def arvore(raiz):
    r = {}
    for d, ds, fs in os.walk(raiz):
        for f in fs:
            p = os.path.join(d, f); r[os.path.relpath(p, raiz).replace(os.sep, "/")] = sha(p)
    return r

TMP = tempfile.mkdtemp(prefix="atualizador_")
PKG = os.path.join(TMP, "pacote"); os.makedirs(PKG)
zip_pkg, programa, info = ger.montar("HEAD", True, TMP)
with zipfile.ZipFile(zip_pkg) as z: z.extractall(PKG)
confere(info["build"] == "bb" and info["versao"] == "1.8.2", "pacote identifica versao e build (%s, %s)" % (info["versao"], info["build"]))
confere(set(os.listdir(PKG)) >= {"atualizar_lmu.py", "ATUALIZAR_LMU.bat", "MANIFESTO_SHA256.txt", "PACOTE.json", "programa", "verificacao", "LEIA-ME_ATUALIZACAO_LMU.txt"}, "conteudo do pacote")
SCRIPT = os.path.join(PKG, "atualizar_lmu.py")

def rodar(destino, *extra, pacote=PKG):
    p = subprocess.run([sys.executable, os.path.join(pacote, "atualizar_lmu.py"), destino, *extra], capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr

USUARIO = {"config_lmu.json": b'{"idioma": "pt", "x": 1}', "recordes_pessoais.json": b'{"spa": 123.4}', "cronograma.json": b'{"eventos": [1,2,3]}',
           "pit_entradas.json": b'{"pit": 1}', "pit_entradas_v2.json": b'{"pit": 2}', "overlay_log.txt": b"meu log antigo\n", "emblemas/meu_emblema.png": b"PNG-MEU",
           "marca/minha_marca.png": b"MARCA-MINHA", "referencias/historico.csv": b"a,b\n1,2\n"}
def instalacao_antiga(nome):
    """Copia isolada de uma instalacao ANTIGA: arquivos do programa com conteudo/versao diferentes, alguns ausentes, mais os dados do usuario."""
    d = os.path.join(TMP, nome); os.makedirs(d)
    for rel, dados in programa.items():
        if rel.startswith(("emblemas/", "marca/", "referencias/")): continue
        p = os.path.join(d, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(dados)
    ip = os.path.join(d, "overlay_iracing.py"); t = open(ip, encoding="utf-8").read().replace('BUILD = "bb"', 'BUILD = "ae"')
    open(ip, "w", encoding="utf-8").write(t)
    lista = sorted(r for r in programa if r.endswith(".py") and "/" not in r and r not in ("overlay_lmu.py", "overlay_iracing.py"))
    for rel in lista[:3]:                                       # alterados
        open(os.path.join(d, rel), "ab").write(b"\n# versao antiga\n")
    for rel in lista[3:5]:                                      # ausentes
        os.remove(os.path.join(d, rel))
    for rel, dados in USUARIO.items():
        p = os.path.join(d, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(dados)
    return d
def dados_ok(d): return all(os.path.exists(os.path.join(d, r)) and open(os.path.join(d, r), "rb").read() == v for r, v in USUARIO.items())
def build(d):
    import re
    return re.search(r'^BUILD\s*=\s*"([^"]+)"', open(os.path.join(d, "overlay_iracing.py"), encoding="utf-8").read(), re.M).group(1)
def igual_ao_pacote(d):
    ref = {r: hashlib.sha256(b).hexdigest() for r, b in programa.items() if not r.startswith(("emblemas/", "marca/", "referencias/"))}
    atual = arvore(d)
    return [r for r, h in ref.items() if atual.get(r) != h and r not in USUARIO]

# ---- 1. simular nao escreve
d = instalacao_antiga("sim"); antes = arvore(d)
rc, out = rodar(d, "--simular")
confere(rc == 0 and "a atualizar" in out and "build bb" in out, "simular: rc 0 e plano (%d, %s)" % (rc, out.strip().splitlines()[-1][:80] if out.strip() else ""))
confere(arvore(d) == antes, "simular nao escreve nada")
rc, out = rodar(os.path.join(TMP, "nao_existe"))
confere(rc == 2, "pasta invalida: rc 2")

# ---- 2. trava ATIVA (processo vivo de verdade)
d = instalacao_antiga("ativa"); antes = arvore(d)
filho = subprocess.Popen([sys.executable, "-c", "import sys,time; sys.stdout.write('ok\\n'); sys.stdout.flush(); time.sleep(120)"], stdout=subprocess.PIPE, text=True)
try:
    filho.stdout.readline()
    open(os.path.join(d, ".atualizar_lmu.lock"), "w", encoding="utf-8").write(json.dumps({"pid": filho.pid, "inicio": time.time(), "maquina": __import__("socket").gethostname()}))
    antes = arvore(d)
    rc, out = rodar(d)
    confere(rc == 4 and "em andamento" in out, "trava ativa: atualizacao real recusada (rc %d)" % rc)
    rc_s, out_s = rodar(d, "--simular")
    confere(rc_s == 4, "trava ativa: --simular tambem retorna 4, igual a real (rc %d)" % rc_s)
    confere(arvore(d) == antes, "trava ativa: nada foi escrito e a trava do outro processo continua")
finally:
    filho.kill(); filho.wait()
# agora o dono morreu: a mesma trava passa a ser orfa
rc_s, out_s = rodar(d, "--simular")
confere(rc_s == 0 and "órfã" in out_s, "dono morto: --simular reconhece trava orfa e retorna 0 (rc %d)" % rc_s)
rc, out = rodar(d)
confere(rc == 0 and "órfã" in out and build(d) == "bb", "dono morto: atualizacao remove a trava orfa e conclui (rc %d)" % rc)
confere(not os.path.exists(os.path.join(d, ".atualizar_lmu.lock")) and not [x for x in os.listdir(d) if x.startswith(".atualizar_lmu.lock")], "nenhuma trava sobra")

# ---- 3. trava orfa: PID inexistente e trava vazia antiga
d = instalacao_antiga("orfa")
morto = subprocess.Popen([sys.executable, "-c", "pass"]); morto.wait()
open(os.path.join(d, ".atualizar_lmu.lock"), "w", encoding="utf-8").write(json.dumps({"pid": morto.pid, "inicio": time.time(), "maquina": __import__("socket").gethostname()}))
rc, out = rodar(d, "--simular"); confere(rc == 0 and "órfã" in out, "PID inexistente: --simular rc 0 com aviso (rc %d)" % rc)
rc, out = rodar(d); confere(rc == 0 and build(d) == "bb" and dados_ok(d), "PID inexistente: atualiza, dados do usuario intactos (rc %d)" % rc)
d = instalacao_antiga("vazia")
lk = os.path.join(d, ".atualizar_lmu.lock"); open(lk, "w").close(); velho = time.time() - 3600; os.utime(lk, (velho, velho))
rc, out = rodar(d); confere(rc == 0 and build(d) == "bb", "trava vazia antiga e orfa: atualiza (rc %d)" % rc)
d = instalacao_antiga("recente")
lk = os.path.join(d, ".atualizar_lmu.lock"); open(lk, "w").close()
rc, out = rodar(d); confere(rc == 4, "trava vazia RECEM-criada conta como ativa: rc 4 (rc %d)" % rc)

# ---- 4. preservacao, backup, idempotencia
d = instalacao_antiga("preserva"); antes_user = {r: open(os.path.join(d, r), "rb").read() for r in USUARIO}
rc, out = rodar(d)
confere(rc == 0 and out.strip().splitlines()[-1].startswith("OK: atualizado para a build bb"), "atualizacao completa: rc 0 (%s)" % out.strip().splitlines()[-1][:70])
confere(dados_ok(d), "dados do usuario byte a byte iguais (config, recordes, cronograma, pit, log, emblemas, marca, referencias)")
confere(igual_ao_pacote(d) == [], "todo arquivo do programa igual ao pacote depois da atualizacao (divergentes: %s)" % igual_ao_pacote(d)[:5])
bks = [x for x in os.listdir(d) if x.startswith("backup_pre_buildBB_")]
confere(len(bks) == 1 and os.path.exists(os.path.join(d, bks[0], "overlay_iracing.py")), "backup dos arquivos substituidos criado")
rc, out = rodar(d); confere(rc == 0 and "já instalada" in out, "idempotente: segunda execucao nao faz nada")
confere(not [x for x in os.listdir(d) if x.startswith((".atualizacao_", ".atualizar_lmu.lock"))], "sem temporarios nem trava depois da atualizacao")

# ---- 5. reversao com arquivo bloqueado
d = instalacao_antiga("reversao"); antes = arvore(d)
alvo_rel = sorted(r for r, b in programa.items() if r.endswith(".py") and "/" not in r and os.path.exists(os.path.join(d, r)) and sha(os.path.join(d, r)) != hashlib.sha256(b).hexdigest())[-1]
if sys.platform == "win32":
    bloqueio = open(os.path.join(d, alvo_rel), "rb")            # handle aberto sem FILE_SHARE_DELETE: o Windows nao deixa trocar o arquivo
    try:
        rc, out = rodar(d)
    finally:
        bloqueio.close()
    modo = "arquivo REALMENTE bloqueado pelo Windows"
else:
    espec = importlib.util.spec_from_file_location("atualizar_lmu_ba", SCRIPT); mod = importlib.util.module_from_spec(espec); espec.loader.exec_module(mod)
    real = os.replace
    def bloqueado(a, b, *r, **k):
        if str(b).replace(os.sep, "/").endswith("/" + alvo_rel): raise PermissionError(13, "arquivo em uso (simulado)")
        return real(a, b, *r, **k)
    mod.os.replace = bloqueado
    import io, contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf): rc = mod.main([d])
    finally:
        mod.os.replace = real
    out = buf.getvalue(); modo = "PermissionError injetado (so Windows tem bloqueio real)"
print("reversao:", modo, "->", alvo_rel, "rc", rc)
confere(rc == 1 and "revertidas" in out, "reversao (%s): rc 1 e alteracoes revertidas" % modo)
restante = {r: h for r, h in arvore(d).items() if not r.startswith(("backup_pre_", ".atualizacao_"))}
confere(restante == {r: h for r, h in antes.items()}, "reversao: arvore identica a de antes (diferencas: %s)" % sorted(set(restante.items()) ^ set(antes.items()))[:3])
confere(not os.path.exists(os.path.join(d, ".atualizar_lmu.lock")), "reversao: trava removida")
rc, out = rodar(d); confere(rc == 0 and build(d) == "bb" and dados_ok(d), "depois de liberar o arquivo, a atualizacao conclui")

# ---- 6. pacote adulterado
adul = os.path.join(TMP, "pacote_adulterado"); shutil.copytree(PKG, adul)
p = os.path.join(adul, "programa", "overlay_lmu.py"); open(p, "ab").write(b"\n# adulterado\n")
d = instalacao_antiga("adulterado"); antes = arvore(d)
rc, out = rodar(d, pacote=adul); confere(rc == 1 and "SHA-256 diferente" in out and arvore(d) == antes, "pacote adulterado: recusado sem tocar na pasta (rc %d)" % rc)
inc = os.path.join(TMP, "pacote_incompleto"); shutil.copytree(PKG, inc); os.remove(os.path.join(inc, "programa", "ov_dados.py"))
rc, out = rodar(d, pacote=inc); confere(rc == 1 and "Ausentes" in out and arvore(d) == antes, "pacote incompleto: recusado (rc %d)" % rc)
sem = os.path.join(TMP, "pacote_sem_info"); shutil.copytree(PKG, sem); os.remove(os.path.join(sem, "PACOTE.json"))
rc, out = rodar(d, pacote=sem); confere(rc == 1 and "PACOTE.json" in out and arvore(d) == antes, "pacote sem PACOTE.json: recusado (rc %d)" % rc)

# ---- 7. conteudo do pacote igual ao zip de codigo da mesma fonte (arvore de trabalho)
saida_cod = os.path.join(TMP, "cod"); os.makedirs(saida_cod)
fonte = inv.arquivos_da_arvore()
zc = os.path.join(saida_cod, "repo-v.zip")
sys.path.insert(0, os.path.join(RAIZ, "tools")); import empacotar
with zipfile.ZipFile(zc, "w") as z:
    for rel, dados in sorted(fonte.items()):
        if not empacotar.excluido(rel): z.writestr("repo/" + rel, dados)
iguais, so_atual, dif = ger.comparar_com_codigo(programa, zc)
confere(dif == [], "programa\\ igual ao zip de codigo, byte a byte (diferentes: %s)" % dif[:5])
confere(all(r.split("/")[-1] in empacotar.EXC_ARQ or r.split("/")[0] in empacotar.EXC_DIRS or r.startswith("emblemas/") or r.startswith("referencias/") for r in so_atual), "so faltam no zip de codigo os arquivos que o empacotador exclui de proposito (%s)" % so_atual[:6])

print(f"\n{_ok} ok, {len(falhas)} falha(s)")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if falhas else 0)
