#!/usr/bin/env python3
"""Imprime as notas de uma versao a partir do CHANGELOG.md (usado pelo fluxo de release)."""
import os, re, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
versao = (sys.argv[1] if len(sys.argv) > 1 else "").lstrip("v")
texto = open(os.path.join(raiz, "CHANGELOG.md"), encoding="utf-8").read()
m = re.search(r"## \[" + re.escape(versao) + r"\][^\n]*\n(.*?)(?=\n## \[|\Z)", texto, re.S)
print((m.group(1).strip() if m else "Veja o CHANGELOG.md.") + "\n")
