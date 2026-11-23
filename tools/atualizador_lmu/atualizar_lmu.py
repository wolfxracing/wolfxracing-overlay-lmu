# -*- coding: utf-8 -*-
"""Atualiza uma pasta do WolfxRacing Overlay LMU para a build deste pacote (lida de PACOTE.json).

Codigos de saida: 0 ok | 1 falhou (e foi desfeito) | 2 pasta de destino invalida | 3 reversao INCOMPLETA (restaure o backup indicado)
                  | 4 ja existe uma atualizacao em andamento nesta pasta (trava ATIVA)."""

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path


AQUI = Path(__file__).resolve().parent
ORIGEM = AQUI / "programa"
MANIFESTO = AQUI / "MANIFESTO_SHA256.txt"
PACOTE = AQUI / "PACOTE.json"
NOME_TRAVA = ".atualizar_lmu.lock"
TRAVA_MAX_IDADE_S = 6 * 3600        # nenhuma atualizacao dura horas: trava mais velha que isso e considerada orfa mesmo se o PID existir (PID reaproveitado)
TRAVA_CRIACAO_S = 30                # trava sem conteudo valido mais nova que isso esta sendo criada por outro processo
SO_SE_FALTAR_DIRS = {"emblemas", "marca", "referencias"}
SO_SE_FALTAR_ARQ = re.compile(
    r"^(config.*\.json|recordes_pessoais\.json|pit_entradas.*\.json|cronograma\.json|.*\.ini|amigos.*\.json)$",
    re.I,
)
IGNORAR = re.compile(
    r"(^|/)(__pycache__|logs_testes|backup_pre_[^/]*)(/|$)|(^|/)(overlay_log\.txt|emblemas_faltando.*\.txt)$|\.pyc$",
    re.I,
)


def dados_pacote():
    """{'versao', 'build', 'commit', ...} gravado pelo gerador; sem ele o pacote e recusado."""
    try:
        dados = json.loads(PACOTE.read_text(encoding="utf-8"))
        if not all(isinstance(dados.get(c), str) and dados[c] for c in ("versao", "build", "commit")):
            raise ValueError("campos obrigatorios ausentes")
        return dados
    except (OSError, ValueError) as erro:
        raise ValueError(f"PACOTE.json invalido ou ausente: {erro}")


def sha(caminho):
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def arquivo_interno(pasta, rel):
    caminho = pasta / rel
    if caminho.resolve() != caminho:
        raise ValueError(f"Caminho redirecionado: {caminho}")
    return caminho


def build_de(pasta):
    try:
        texto = (pasta / "overlay_iracing.py").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "?"
    achado = re.search(r'^BUILD\s*=\s*"([^"]+)"', texto, re.M)
    return achado.group(1) if achado else "?"


def validar_pacote(build_esperado):
    """Confere inventario, hashes, sintaxe e identificacao antes de escrever."""
    esperado = {}
    caminhos = set()
    for linha in MANIFESTO.read_text(encoding="utf-8").splitlines():
        entrada = re.fullmatch(r"([0-9a-f]{64})  (.+)", linha)
        if entrada is None:
            raise ValueError("Linha inválida no manifesto de SHA-256")
        digest, rel = entrada.groups()
        partes = rel.split("/")
        chave = rel.casefold()
        if any(not parte or parte in (".", "..") or parte != parte.rstrip(". ") for parte in partes):
            raise ValueError(f"Caminho inválido no manifesto: {rel!r}")
        if any(c in rel for c in "\\:*?\"<>|\x00") or chave in caminhos or IGNORAR.search(rel):
            raise ValueError(f"Caminho inválido ou duplicado no manifesto: {rel!r}")
        caminhos.add(chave)
        esperado[rel] = digest
    encontrados = {
        caminho.relative_to(ORIGEM).as_posix()
        for caminho in ORIGEM.rglob("*")
        if caminho.is_file() and not IGNORAR.search(caminho.relative_to(ORIGEM).as_posix())
    }
    if esperado.keys() != encontrados or "overlay_lmu.py" not in esperado or "overlay_iracing.py" not in esperado:
        ausentes = sorted(esperado.keys() - encontrados)
        extras = sorted(encontrados - esperado.keys())
        raise ValueError(f"Inventário do programa inválido. Ausentes: {ausentes}. Extras: {extras}.")
    for rel, digest in esperado.items():
        origem = arquivo_interno(ORIGEM, rel)
        if origem.suffix == ".py":
            dados = origem.read_bytes()
            if hashlib.sha256(dados).hexdigest() != digest:
                raise ValueError(f"SHA-256 diferente do manifesto: {rel}")
            compile(dados, rel, "exec")
        elif sha(origem) != digest:
            raise ValueError(f"SHA-256 diferente do manifesto: {rel}")
    if build_de(ORIGEM) != build_esperado:
        raise ValueError(f"O programa do pacote não é da build {build_esperado}")
    return esperado


# ---------------------------------------------------------------- trava de instancia (ativa x orfa)
def processo_vivo(pid):
    """True se existe um processo com esse PID (Windows: OpenProcess/GetExitCodeProcess; demais: kill 0)."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        h = k32.OpenProcess(0x1000, 0, pid)               # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() == 5           # acesso negado = existe (de outro usuario/protegido); 87 = nao existe
        try:
            codigo = ctypes.c_ulong()
            return bool(k32.GetExitCodeProcess(h, ctypes.byref(codigo))) and codigo.value == 259   # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def estado_trava(trava, agora=None):
    """('livre'|'ativa'|'orfa', detalhe). Ativa = o dono (PID) existe, esta na mesma maquina e a trava e recente."""
    agora = time.time() if agora is None else agora
    try:
        texto = trava.read_text(encoding="utf-8")
        idade = agora - trava.stat().st_mtime
    except FileNotFoundError:
        return "livre", ""
    except OSError as erro:
        return "ativa", f"trava ilegivel ({erro})"
    try:
        info = json.loads(texto)
        pid = int(info["pid"])
        maquina = str(info.get("maquina", ""))
        inicio = float(info.get("inicio", 0))
    except (ValueError, KeyError, TypeError):
        if idade < TRAVA_CRIACAO_S:
            return "ativa", "trava recem-criada por outro processo"
        return "orfa", f"trava sem conteudo valido, parada ha {int(idade)} s"
    if agora - inicio > TRAVA_MAX_IDADE_S and idade > TRAVA_MAX_IDADE_S:
        return "orfa", f"trava de PID {pid} com mais de {TRAVA_MAX_IDADE_S // 3600} h"
    if maquina and maquina != socket.gethostname():
        return "ativa", f"trava criada em outra maquina ({maquina}), PID {pid}"
    if processo_vivo(pid):
        return "ativa", f"processo {pid} em execucao"
    return "orfa", f"PID {pid} nao existe mais"


def tomar_trava(destino):
    """Cria a trava. Devolve (arquivo_da_trava | None, mensagem). Trava ORFA e removida (com aviso); trava ATIVA recusa."""
    trava = destino / NOME_TRAVA
    for _ in range(3):
        try:
            with trava.open("x", encoding="utf-8") as arquivo:
                arquivo.write(json.dumps({"pid": os.getpid(), "inicio": time.time(), "maquina": socket.gethostname()}))
            return trava, ""
        except FileExistsError:
            estado, detalhe = estado_trava(trava)
            if estado == "ativa":
                return None, f"outra atualização está em andamento nesta pasta ({detalhe}). Aguarde terminar."
            if estado == "orfa":
                try:
                    antes = trava.read_text(encoding="utf-8", errors="replace")
                    descartada = destino / f"{NOME_TRAVA}.orfa_{os.getpid()}_{int(time.time())}"
                    os.replace(trava, descartada)
                    if descartada.read_text(encoding="utf-8", errors="replace") != antes:      # outro processo trocou a trava no meio
                        return None, "a trava mudou durante a verificação; tente de novo."
                    descartada.unlink()
                    print(f"Aviso: trava órfã de uma atualização interrompida removida ({detalhe}).")
                except OSError as erro:
                    return None, f"não foi possível remover a trava órfã {trava}: {erro}. Apague esse arquivo e rode de novo."
    return None, "não foi possível obter a trava; tente de novo."


def planejar(destino, esperado):
    plano = {"novo": [], "igual": [], "atualizar": [], "preservado": []}
    for rel, digest in sorted(esperado.items()):
        if politica(rel) and (destino / rel).exists():
            plano["preservado"].append(rel)
            continue
        arquivo = arquivo_interno(destino, rel)
        if not arquivo.exists():
            plano["novo"].append(rel)
        elif not arquivo.is_file():
            raise ValueError(f"Esperado arquivo no destino: {arquivo}")
        elif sha(arquivo) == digest:
            plano["igual"].append(rel)
        else:
            plano["atualizar"].append(rel)
    return plano


def politica(rel):
    topo, separador, _ = rel.partition("/")
    return topo in SO_SE_FALTAR_DIRS or (not separador and SO_SE_FALTAR_ARQ.fullmatch(topo) is not None)


def criar_pastas(destino, pai, criadas):
    faltantes = []
    while pai != destino and not pai.exists():
        faltantes.append(pai)
        pai = pai.parent
    for pasta in reversed(faltantes):
        pasta.mkdir()
        criadas.append(pasta)


def desfazer(destino, backup, temporaria, trocados, pastas_criadas):
    erros = []
    for rel, sobrescrito in reversed(trocados):
        try:
            alvo = arquivo_interno(destino, rel)
            if sobrescrito:
                restaurado = temporaria / "restauracao"
                shutil.copy2(backup / rel, restaurado)
                os.replace(restaurado, alvo)
            else:
                alvo.unlink(missing_ok=True)
        except (OSError, ValueError) as erro:
            erros.append(f"{rel}: {erro}")
    for pasta in reversed(pastas_criadas):
        try:
            pasta.rmdir()
        except OSError as erro:
            erros.append(f"{pasta}: {erro}")
    return erros


def aplicar(destino, esperado, plano, build):
    atualizados = set(plano["atualizar"])
    mudancas = plano["novo"] + plano["atualizar"]
    backup = None
    with tempfile.TemporaryDirectory(prefix=".atualizacao_", dir=destino, ignore_cleanup_errors=True) as pasta_temp:
        temporaria = Path(pasta_temp)
        preparada = temporaria / "programa"
        trocados, pastas_criadas = [], []
        try:
            for rel in mudancas:
                arquivo = preparada / rel
                arquivo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(arquivo_interno(ORIGEM, rel), arquivo)
                if sha(arquivo) != esperado[rel]:
                    raise ValueError(f"SHA-256 diferente ao preparar {rel}")
            if atualizados:
                prefixo = time.strftime(f"backup_pre_build{build.upper()}_%Y%m%d_%H%M%S_")
                backup = Path(tempfile.mkdtemp(prefix=prefixo, dir=destino))
                for rel in plano["atualizar"]:
                    copia = backup / rel
                    copia.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(arquivo_interno(destino, rel), copia)
            for rel in mudancas:
                alvo = arquivo_interno(destino, rel)
                sobrescrito = rel in atualizados
                if not sobrescrito and alvo.exists():
                    raise ValueError(f"O destino passou a existir durante a atualização: {rel}")
                criar_pastas(destino, alvo.parent, pastas_criadas)
                os.replace(preparada / rel, alvo)
                trocados.append((rel, sobrescrito))
            if build_de(destino) != build:
                raise ValueError(f"BUILD após atualizar difere de {build!r}")
        except (OSError, ValueError, KeyboardInterrupt) as erro:
            print(f"FALHA na atualização: {erro}")
            erros = desfazer(destino, backup, temporaria, trocados, pastas_criadas)
            if erros:
                print(f"Recuperação incompleta. Backup: {backup}")
                for detalhe in erros:
                    print(f"  {detalhe}")
                return 3
            print("As alterações desta atualização foram revertidas.")
            return 1
    print(f"OK: atualizado para a build {build}. Backup: {backup or '(nenhum arquivo substituído)'}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("destino")
    parser.add_argument("--simular", action="store_true")
    argumentos = parser.parse_args(argv)
    destino = Path(argumentos.destino).resolve()
    if not (destino / "overlay_lmu.py").is_file():
        print(f"ERRO: '{destino}' não parece a pasta do overlay LMU.")
        return 2
    try:
        pacote = dados_pacote()
        build = pacote["build"]
        esperado = validar_pacote(build)
        print(f"Pacote: LMU {pacote['versao']} build {build} (commit {pacote['commit'][:12]})")
        if argumentos.simular:
            estado, detalhe = estado_trava(destino / NOME_TRAVA)
            if estado == "ativa":
                print(f"ERRO: outra atualização está em andamento nesta pasta ({detalhe}). A atualização real seria recusada.")
                return 4
            plano = planejar(destino, esperado)
            mostrar_plano(destino, plano, build)
            if estado == "orfa":
                print(f"Aviso: há uma trava órfã ({detalhe}); a atualização real a removerá e seguirá.")
            for acao in ("novo", "atualizar"):
                for rel in plano[acao]:
                    print(f"  [{acao}] {rel}")
            return 0
        trava, mensagem = tomar_trava(destino)
        if trava is None:
            print(f"ERRO: {mensagem}")
            return 4
        try:
            plano = planejar(destino, esperado)
            mostrar_plano(destino, plano, build)
            if not plano["novo"] and not plano["atualizar"]:
                print(f"OK: build {build} já instalada.")
                return 0
            return aplicar(destino, esperado, plano, build)
        finally:
            try:
                trava.unlink()
            except OSError as erro:
                print(f"Aviso: não foi possível apagar a trava {trava}: {erro}. Ela é reconhecida como órfã na próxima execução.")
    except (OSError, ValueError, SyntaxError) as erro:
        print(f"ERRO ao validar o pacote ou preparar a atualização: {erro}")
    return 1


def mostrar_plano(destino, plano, build):
    print(f"Pasta: {destino}\nBuild atual: {build_de(destino)}  ->  nova: {build}")
    print(
        f"{len(plano['novo'])} novos, {len(plano['atualizar'])} a atualizar, "
        f"{len(plano['igual'])} já iguais, {len(plano['preservado'])} preservados"
    )


if __name__ == "__main__":
    sys.exit(main())
