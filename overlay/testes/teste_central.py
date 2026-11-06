# -*- coding: utf-8 -*-
"""v1.6.0 - central de configuracoes (janela interativa): usa os mesmos itens do menu da bandeja."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.argv = ["x", "--demo"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pathlib import Path
import overlay_iracing as o
import ov_central as c
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu

S = Path(tempfile.mkdtemp()); o.ARQ_LOG = S / "l.txt"; o.ARQ_CONFIG = S / "c.json"
app = QApplication([]); salvos = []; o.salvar_config = lambda c_: salvos.append(1)
falhas = []
def confere(cond, msg):
    print(("OK    " if cond else "FALHA ") + msg)
    if not cond: falhas.append(msg)

cfg = o.carregar_config(); cfg["travado"] = True
subs = []
def todas(cl):
    for s in cl.__subclasses__():
        subs.append(s); todas(s)
janelas = [o.JanelaTelemetria(cfg), o.JanelaVoltas(cfg), o.JanelaRelativo(cfg), o.JanelaClassificacao(cfg), o.JanelaMapa(cfg),
           o.JanelaRadar(cfg), o.JanelaBandeiras(cfg), o.JanelaTrafego(cfg), o.JanelaMinimapa(cfg), o.JanelaAuxiliar(cfg),
           o.JanelaUltimoContato(cfg), o.JanelaPitEntrada(cfg), o.JanelaClima(cfg), o.JanelaPneus(cfg)]
menu = QMenu(); acoes = {}; chamadas = []
def adicionar(chave, valor):
    a = QAction(chave, menu); a.setCheckable(True); a.setChecked(bool(valor))
    a.toggled.connect(lambda v, k=chave: (cfg.__setitem__(k, bool(v)), chamadas.append((k, v))))
    acoes[chave] = a
for j in janelas:
    adicionar(j.CHAVE_ATIVO, cfg[j.CHAVE_ATIVO])
for k in ("travado", "tema_sport", "radar_auto", "auxiliar_sempre", "pit_sempre", "telemetria_barra", "mostrar_grafico"):
    adicionar(k, cfg.get(k, False))
demo = o.Telemetria(demo=True)
def previa(j):
    c2 = dict(cfg); c2[j.CHAVE_ATIVO] = False; c2["travado"] = True
    return type(j)(c2)
g = {"opacidade": lambda v: chamadas.append(("opac", v)), "restaurar": lambda: chamadas.append(("rest",)),
     "salvar": lambda: salvos.append(1), "modo_perfil": lambda m: chamadas.append(("perfil", m))}
cen = c.Central(janelas, acoes, cfg, g, demo.ler, previa, "iRacing", "1.6.0")
cen.mostrar()
confere(cen.isVisible(), "central abre")
confere(len(cen._cartoes) == len(janelas), f"um cartao por janela ({len(cen._cartoes)})")
confere(all(chave in c.PAINEIS for chave in (j.CHAVE for j in janelas)), "todos os paineis tem titulo e descricao")

# 1) ligar/desligar pelo cartao dispara o MESMO item do menu
cartao = cen._cartoes["bandeiras"]
estado = acoes["mostrar_bandeiras"].isChecked()
cartao["interruptor"].setChecked(not estado)
confere(acoes["mostrar_bandeiras"].isChecked() == (not estado) and ("mostrar_bandeiras", not estado) in chamadas, "interruptor do cartao aciona o item do menu")
# 2) mudanca feita fora (atalho/perfil) aparece na central
acoes["mostrar_bandeiras"].setChecked(estado)
cen._atualizar_estado_leve()
confere(cartao["interruptor"].isChecked() == estado, "mudanca feita pelo atalho/perfil reflete na central")
# 3) filtros
cen._ao_categoria("Automáticos"); 
vis = [k for k, q in cen._cartoes.items() if not q["quadro"].isHidden()]
confere(set(vis) >= {"bandeiras", "trafego", "auxiliar", "contato", "pit", "radar"} and "pneus" not in vis, f"filtro Automaticos ({vis})")
cen._ao_categoria("Todos"); cen.busca.setText("minimapa")
vis = [k for k, q in cen._cartoes.items() if not q["quadro"].isHidden()]
confere(vis == ["minimapa"], f"busca por 'minimapa' ({vis})")
cen.busca.setText("")
# 4) detalhe: escala + extras + previa
cen.abrir_detalhe("auxiliar")
confere(cen.paginas.currentIndex() == 2 and cen.det_titulo.text() == "Auxiliar de sessão", "abre o detalhe do painel")
cen.det_escala.setValue(150)
confere(abs(janelas[9].escala - 1.5) < 1e-6, "escala do painel muda na hora")
confere(cen.det_extras.count() == 1, "extras do painel (Auxiliar: mostrar tambem durante a sessao)")
cen._ciclo(forcar=True)
confere(cen.det_previa._pix is not None and not cen.det_previa._pix.isNull(), "previa ao vivo renderiza")
cen.det_escala.setValue(100)
# 5) aparencia e perfis
cen.ir_para("aparencia"); cen.sl_opac.setValue(60)
confere(("opac", 0.6) in chamadas, "slider de opacidade chama o gancho")
cen.ir_para("perfis"); cen._radios["Corrida"].click()
confere(("perfil", "Corrida") in chamadas, "perfil escolhido pela central")
# 6) travar pela pagina inicial
cen.ir_para("inicio")
antes = acoes["travado"].isChecked(); cen._set_acao("travado", not antes)
confere(acoes["travado"].isChecked() == (not antes) and "Destravadas" in cen.lb_travado.text() or antes is False, "travar/destravar pela central")
# 7) imagens
out = os.environ.get("OVERLAY_PREVIAS", "")
for nome, destino in (("inicio", "inicio"), ("paineis", "paineis"), ("detalhe", "detalhe"), ("aparencia", "aparencia")):
    pass
if out:
    for pagina, arq in (("inicio", "central_inicio.png"), ("paineis", "central_paineis.png"), ("aparencia", "central_aparencia.png")):
        cen.ir_para(pagina); app.processEvents(); cen.grab().save(os.path.join(out, arq))
    cen.abrir_detalhe("pit"); app.processEvents(); cen.grab().save(os.path.join(out, "central_detalhe.png"))
    cen.ir_para("perfis"); app.processEvents()

print("\n" + ("TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)"))
sys.exit(1 if falhas else 0)
