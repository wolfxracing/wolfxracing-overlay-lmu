# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ov_amigos as am
falhas = []
def confere(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)
a = am.preparar("Ana; João Silva\nZé, ana")
confere(len(a) == 3, f"texto vira lista sem repeticao ({a})")
confere(am.eh_amigo("Ana Souza", a) and not am.eh_amigo("Diana Souza", a), "'Ana' casa com palavra inteira, nao com 'Diana'")
confere(am.eh_amigo("Joao Pedro SILVA", a), "nome composto: todas as palavras, sem acento nem caixa")
confere(not am.eh_amigo("Joao Pedro", a) and not am.eh_amigo("", a) and not am.eh_amigo(None, a), "falta palavra / vazio: nao casa")
confere(not am.eh_amigo("Ana", ()) and am.preparar(None) == () and am.preparar(["", "  "]) == (), "lista vazia: ninguem e amigo")
confere(len(am.preparar([f"piloto{i}" for i in range(500)])) == 200, "limite de 200 amigos")
print("RESULTADO:", "OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
