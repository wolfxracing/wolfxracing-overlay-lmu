# -*- coding: utf-8 -*-
"""v1.6.3 - robustez: configuracao atomica, encerramento seguro dos atalhos, aviso de desempenho barato."""
import os, sys, tempfile, threading
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import overlay_iracing as o
import ov_nucleo as n

falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

# ---- configuracao atomica: falha ao substituir preserva o JSON anterior
with tempfile.TemporaryDirectory() as pasta:
    antigo = o.ARQ_CONFIG
    o.ARQ_CONFIG = Path(pasta) / "config.json"
    try:
        o.salvar_config({"a": 1})
        confere(o.ARQ_CONFIG.read_text(encoding="utf-8").count('"a": 1') == 1, "salvar_config grava o JSON")
        confere(not (Path(pasta) / "config.json.tmp").exists(), "sem arquivo temporario sobrando")
        real = os.replace
        def falha(*a, **k): raise OSError("falha simulada")
        os.replace = falha
        try:
            o.salvar_config({"a": 2})
        finally:
            os.replace = real
        confere('"a": 1' in o.ARQ_CONFIG.read_text(encoding="utf-8"), "falha na troca preserva o JSON anterior")
    finally:
        o.ARQ_CONFIG = antigo

# ---- atalhos: thread que nao encerrou nao e esquecida
class API:
    def __init__(self): self.fim = threading.Event()
    def preparar(self): return 1
    def registrar(self, *a): return True, ""
    def esperar(self): self.fim.wait(); return None
    def liberar(self, *a): pass
    def encerrar(self, *a): pass
api = API(); escuta = n.EscutaTeclas(api, atalhos=[]); escuta.iniciar()
th = escuta._thread
confere(escuta.parar(timeout=0.01) is False and escuta._thread is th, "parar() sem encerrar devolve False e mantem a thread")
api.fim.set(); th.join(2)
confere(escuta.parar() is True and escuta._thread is None, "parar() depois do encerramento devolve True")

# ---- desempenho: so ordena quando vai avisar
d = n.Desempenho(); chamadas = [0]; orig = d.estatistica
def contado(nome): chamadas[0] += 1; return orig(nome)
d.estatistica = contado
for i in range(600): d.medir("ciclo", 5.0)
for i in range(1000): d.alerta(i / 30)
confere(chamadas[0] == 0, "ciclo dentro do orcamento nao calcula estatistica")
for i in range(600): d.medir("ciclo", 200.0)
aviso = d.alerta(10000.0)
confere(aviso is not None and "lento" in aviso, "ciclo lento gera aviso")
confere(d.alerta(10001.0) is None, "cooldown de 5 min preservado")

# ---- classificacao: layout so e refeito quando a classificacao muda
class Fake:
    def __init__(self): self.calls = 0; self._altura_base = 170; self.config = {"classificacao_todas": True}
    def _blocos(self, c): self.calls += 1; return []
    def _altura_necessaria(self): return 170
    def aplicar_tamanho(self): pass
    def _repintar(self): pass
fake = Fake(); classif = {"classes": []}; dados = {"conectado": True, "classificacao": classif}
for i in range(30): o.JanelaClassificacao.atualizar(fake, dados)
confere(fake.calls == 1, f"mesmo objeto: layout calculado 1 vez em 30 quadros ({fake.calls})")
o.JanelaClassificacao.atualizar(fake, {"conectado": True, "classificacao": {"classes": []}})
confere(fake.calls == 2, "classificacao nova refaz o layout")
fake.config["classificacao_todas"] = False
o.JanelaClassificacao.atualizar(fake, {"conectado": True, "classificacao": classif})
confere(fake.calls == 3, "mudar 'todas as classes' refaz o layout")
o.JanelaClassificacao.atualizar(fake, {"conectado": False, "classificacao": classif})
confere(fake._blocos_atual == [] and fake.calls == 3, "desconectado limpa os blocos (sem classificacao)")
fake.calls = 0; fake._blocos_atual = ["x"]
o.JanelaClassificacao.atualizar(fake, {"conectado": True, "classificacao": classif})
confere(fake.calls == 1, "reconectar recalcula o layout")

print("RESULTADO:", "OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
