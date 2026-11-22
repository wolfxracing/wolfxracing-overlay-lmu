# -*- coding: utf-8 -*-
"""Roda TODAS as suites desta pasta (testes/teste_*.py: as da lista oficial + as de robustez), uma por processo, e falha se qualquer uma falhar.

Uso (na pasta overlay):   py -3.12 rodar_todos_os_testes.py            (ou: python3 rodar_todos_os_testes.py)
Opcoes:                   --so TRECHO   roda so as suites cujo nome contem TRECHO      --timeout SEGUNDOS (padrao 900)
Saida: uma linha por teste com o CODIGO DE SAIDA, log completo de cada um em logs_testes/<teste>.log, AMBIENTE.txt (versoes de Python/Qt/NumPy e modo
de renderizacao) e RESUMO.txt. Codigo de saida final: 0 = todos passaram; 1 = algum falhou (ou nao pode importar uma dependencia obrigatoria);
2 = dependencia de teste ausente (veja requirements-teste.txt).
Plataforma Qt: use --plataforma windows para exercitar as fontes do Windows. O padrao respeita QT_QPA_PLATFORM ou usa offscreen."""
import os, sys, subprocess, time, argparse, glob, platform, tempfile, shutil
RAIZ = os.path.dirname(os.path.abspath(__file__))
os.chdir(RAIZ)


def ambiente(plataforma):
    linhas = [f"Python {sys.version.split()[0]} ({platform.platform()})"]
    try:
        import PySide6
        from PySide6 import QtCore
        linhas.append(f"PySide6 {PySide6.__version__} / Qt {QtCore.qVersion()}")
    except ImportError as e:
        linhas.append(f"PySide6 AUSENTE ({e})")
    try:
        import numpy
        linhas.append(f"NumPy {numpy.__version__}")
    except ImportError as e:
        linhas.append(f"NumPy AUSENTE ({e})")
    linhas.append(f"Plataforma Qt solicitada: {plataforma}. Uma suite pode definir a propria plataforma.")
    linhas.append("Pacote: " + ("LMU" if os.path.exists("overlay_lmu.py") else "iRacing"))
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", default="")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--plataforma", default=os.environ.get("QT_QPA_PLATFORM") or "offscreen",
                    help="plataforma Qt solicitada para os testes (por exemplo, offscreen ou windows)")
    a = ap.parse_args()
    amb = ambiente(a.plataforma)
    print("\n".join(amb))
    if any("AUSENTE" in l for l in amb):
        print("FALTA dependencia de teste: pip install -r requirements-teste.txt")
        return 2
    os.makedirs("logs_testes", exist_ok=True)
    open("logs_testes/AMBIENTE.txt", "w", encoding="utf-8").write("\n".join(amb) + "\n")
    env = dict(os.environ, QT_QPA_PLATFORM=a.plataforma, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    testes = sorted(os.path.basename(f) for f in glob.glob(os.path.join("testes", "teste_*.py")))
    testes = [t for t in testes if a.so in t]
    resumo, falhos = [], []
    for t in testes:
        ini = time.time()
        log = os.path.join("logs_testes", t[:-3] + ".log")
        try:
            # build az: cada suite recebe a SUA pasta temporaria. A trava de instancia unica do overlay (overlay_iracing*.lock) fica na pasta
            # temporaria do sistema; compartilhada, ela fazia a suite esperar (ou falhar) se outra execucao ou o overlay aberto em demo a segurasse.
            tmp_suite = tempfile.mkdtemp(prefix="ovt_", dir=os.path.abspath("logs_testes"))
            env_suite = dict(env, TMP=tmp_suite, TEMP=tmp_suite, TMPDIR=tmp_suite)
            with open(log, "w", encoding="utf-8") as fh:
                rc = subprocess.run([sys.executable, os.path.join("testes", t)], stdout=fh, stderr=subprocess.STDOUT, env=env_suite, timeout=a.timeout).returncode
        except subprocess.TimeoutExpired:
            rc = 124
        shutil.rmtree(tmp_suite, ignore_errors=True)
        ultima = ""
        for l in reversed(open(log, encoding="utf-8", errors="replace").read().splitlines()):
            if any(k in l for k in ("ok,", "RESULTADO", "PASSARAM", "Resultado", "falha", "FALHA")):
                ultima = l.strip()[:110]
                break
        linha = f"{t:55s} rc={rc:<3d} {time.time() - ini:6.1f}s | {ultima}"
        print(linha, flush=True)
        resumo.append(linha)
        if rc != 0:
            falhos.append(t)
    fim = f"\n{len(testes)} suites, {len(testes) - len(falhos)} com rc=0, {len(falhos)} com falha" + (": " + ", ".join(falhos) if falhos else "")
    print(fim)
    open("logs_testes/RESUMO.txt", "w", encoding="utf-8").write("\n".join(amb) + "\n\n" + "\n".join(resumo) + fim + "\n")
    return 1 if (falhos or not testes) else 0


if __name__ == "__main__":
    sys.exit(main())
