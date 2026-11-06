# -*- coding: utf-8 -*-
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ov_backup as bk
falhas = []
def confere(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)
padrao = {"travado": True, "mostrar_coach": True, "escala_coach": 1.0, "escala_x_coach": None, "perfil_ativo": "Corrida", "perfil_modo": "auto",
          "coach_modo": "auto", "opacidade_painel": {}, "perfis": {}}
cfg = dict(padrao, escala_coach=1.5, coach_modo="importada", opacidade_painel={"coach": 0.5}, escala_x_coach=1.2)
txt = bk.exportar(cfg, "iracing", "1.7.0")
novo, av = bk.importar(txt, padrao, "iracing")
confere(novo["escala_coach"] == 1.5 and novo["coach_modo"] == "importada" and novo["opacidade_painel"] == {"coach": 0.5} and av == [], "ida e volta preserva a config")
confere(novo["escala_x_coach"] == 1.2, "escala por eixo (padrao None) aceita numero")
d = json.loads(txt); d["config"].update({"chave_inventada": 1, "mostrar_coach": "sim", "escala_coach": 99, "escala_x_coach": "x"})
novo, av = bk.importar(json.dumps(d), padrao)
confere("chave_inventada" not in novo and novo["mostrar_coach"] is True and novo["escala_x_coach"] is None, "ignora chaves desconhecidas e tipos errados")
confere(novo["escala_coach"] == 4.0 and any("3 item" in a for a in av), f"escala fora do limite e recortada; aviso ({av})")
_, av = bk.importar(bk.exportar(cfg, "lmu", "1.7.0"), padrao, "iracing")
confere(any("outro jogo" in a for a in av), "avisa backup de outro jogo")
for ruim, tr in (("{", "JSON"), ('{"formato": "x"}', "nao e um backup"), ("[1]", "nao e um backup"), (None, "JSON")):
    try:
        bk.importar(ruim, padrao); confere(False, "devia recusar " + str(ruim))
    except bk.ErroBackup as e:
        confere(tr in str(e), f"recusa {ruim!r}: {e}")
padrao["perfis"] = {"Corrida": {"x": 1}}
sem = {k: v for k, v in cfg.items() if k != "perfis"}
novo, _ = bk.importar(bk.exportar(sem, "iracing", "1"), padrao); novo["perfis"]["Corrida"]["x"] = 2
confere(padrao["perfis"]["Corrida"]["x"] == 1, "importar nao altera o dicionario padrao (copia profunda)")
t = bk.resumo_suporte("1.7.0", "iracing", cfg, ["linha %d" % i for i in range(100)], {"Telemetria": "ok"})
confere("1.7.0" in t and "coach" in t and t.count("linha ") == 40 and "Telemetria: ok" in t, "resumo de suporte")
print("RESULTADO:", "OK" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
