# -*- coding: utf-8 -*-
"""
Testes automaticos do LMU 1.2.0 (Luz do ABS, Luz do TC, Retorno a pista, Estrategia de pneus e grafico de pedais da Telemetria).
Usam o JOGO FALSO de teste_lmu.py: provam o desenho do codigo, NAO provam que o LMU real entrega os dados assim.
Execucao: python testes\\teste_lmu_v12.py
"""
import os
import sys
import time
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import teste_lmu as T                                   # noqa: E402  (jogo falso e utilitarios; nao executa os testes)
from teste_lmu import confere, grupo, lmu                # noqa: E402


def dados_com(jogo, relogio=None, antes=None):
    tel, rel = T.telemetria(jogo, relogio)
    if antes:
        antes(tel, rel)
    return tel, rel, tel.ler()


def teste_luzes():
    grupo("v1.2.0 - Luz do ABS e Luz do TC (dados do jogo)")
    m = T.preparar_modulo()
    j = T.cenario_corrida()
    tel, rel = T.telemetria(j)
    d = tel.ler()
    confere(d["abs"] is False and d["luz_tc"] == {"ativa": False, "patinagem": 0.0, "estado": "jogo"}, "luzes apagadas por padrao")

    class Ctx:
        pass
    # liga mTCActive / mABSActive direto na memoria do jogo falso
    orig = j.preencher

    def com_flags(dados, abs_=False, tc=False):
        orig(dados)
        t = dados.telemetry.telemInfo[dados.telemetry.playerVehicleIdx]
        t.mABSActive, t.mTCActive = abs_, tc
    for abs_, tc in ((True, False), (False, True), (True, True)):
        j.preencher = lambda dados, a=abs_, c=tc: com_flags(dados, a, c)
        rel.avancar(0.2)
        j.et += 0.2
        d = tel.ler()
        confere(d["abs"] is abs_ and d["luz_tc"]["ativa"] is tc, f"ABS={abs_} TC={tc} chegam as janelas")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    cfg = m.carregar_config_lmu()
    cfg["travado"] = True
    labs, ltc = m.base.JanelaLuzAbs(dict(cfg)), m.base.JanelaLuzTc(dict(cfg))
    confere(labs.sinal(d) is True and ltc.sinal(d) is True, "as duas janelas acendem com os dados do jogo")
    d2 = dict(d, abs=False, luz_tc={"ativa": False, "patinagem": 0.0, "estado": "jogo"})
    confere(labs.sinal(d2) is False and ltc.sinal(d2) is False, "e apagam")


def teste_retorno():
    grupo("v1.2.0 - Retorno a pista (PARE / CEDA / LIVRE)")
    m = T.preparar_modulo()
    j = T.cenario_corrida()
    j.vel_ms = (0.0, 0.0, 0.0)                                  # jogador parado
    j.superficie = 2                                            # grama nas 4 rodas
    j.carros[3].dist = 9000.0                                   # jogador
    j.carros[2].dist = 8500.0                                   # 500 m atras
    j.carros[2].vel = 60.0
    for c in j.carros:
        if c.id not in (3, 4):
            c.dist = 3000.0 + 1000.0 * c.id
    tel, rel = T.telemetria(j)
    res = None
    for k in range(12):                                         # 1,2 s: o carro de tras anda e a velocidade e medida
        rel.avancar(0.1)
        j.et += 0.1
        j.carros[2].dist = (j.carros[2].dist + 6.0) % j.comprimento
        res = tel.ler()["retorno"]
    confere(res is not None and res["visivel"] is True, "parado na grama: aviso aparece")
    confere(res["segundos"] is not None and 5.0 < res["segundos"] < 12.0, f"segundos ate o de tras chegar ({res['segundos']})")
    confere(res["estado"] in ("pare", "ceda", "livre"), "estado valido")
    # volta para o asfalto andando: avisa por mais 1,5 s e depois some
    j.superficie, j.vel_ms = 0, (0.0, 0.0, -50.0)
    for k in range(3):
        rel.avancar(0.1)
        j.et += 0.1
        res = tel.ler()["retorno"]
    confere(res["visivel"] is True, "persiste um instante apos voltar a pista")
    for k in range(25):
        rel.avancar(0.1)
        j.et += 0.1
        res = tel.ler()["retorno"]
    confere(res["visivel"] is False, "some depois")
    # no grid antes da largada nao avisa
    j2 = T.cenario_corrida()
    j2.fase, j2.vel_ms = 3, (0.0, 0.0, 0.0)
    tel2, rel2 = T.telemetria(j2)
    r2 = None
    for k in range(25):
        rel2.avancar(0.1)
        j2.et += 0.1
        r2 = tel2.ler()["retorno"]
    confere(r2 is not None and r2["visivel"] is False, "volta de apresentacao/grid: sem aviso")
    # no box nao avisa
    j3 = T.cenario_corrida()
    j3.carros[3].box, j3.vel_ms, j3.superficie = True, (0.0, 0.0, 0.0), 0
    tel3, rel3 = T.telemetria(j3)
    r3 = None
    for k in range(25):
        rel3.avancar(0.1)
        j3.et += 0.1
        r3 = tel3.ler()["retorno"]
    confere(r3 is not None and r3["visivel"] is False, "no box: sem aviso")
    # nova sessao reinicia
    j.sessao = 6
    rel.avancar(0.5)
    tel.ler()
    confere(tel._v12_sessao[0] == 6, "nova sessao reinicia o historico")


def teste_estrategia():
    grupo("v1.2.0 - Estrategia de pneus (chuva x seco)")
    m = T.preparar_modulo()
    j = T.cenario_corrida()
    tel, rel = T.telemetria(j)
    d = tel.ler()
    e = d["estrategia"]
    confere(e is not None and e["meu_pneu"] == "seco" and e["meu_pneu_nome"] == "Medium", "pneu atual: seco (Medium)")
    confere(e["vantagem"] is None and e["rivais_outro"] == 0, "sem vantagem estimada e sem contagem de rivais (o LMU nao informa)")
    # pista encharcando com pneu de seco: o aviso sobe ate TROCAR
    j.chuva, j.umidade, j.nuvens = 0.6, 0.9, 6
    acao = None
    for k in range(60):
        rel.avancar(1.0)
        j.et += 1.0
        acao = tel.ler()["estrategia"]
    confere(acao is not None and acao["acao"] in ("prepare", "trocar") and acao["alvo"] == "chuva", f"chuva forte, pneu de seco: {acao and acao['acao']} -> chuva")
    # corrida antes da largada
    j2 = T.cenario_corrida()
    j2.fase = 2
    tel2, rel2 = T.telemetria(j2)
    e2 = tel2.ler()["estrategia"]
    confere(e2["pre_largada"] is True, "grid: modo pre-largada")
    j2.fase = 5
    rel2.avancar(1.0)
    j2.et += 1.0
    tel2.ler()
    rel2.avancar(1.0)
    confere(tel2.ler()["estrategia"]["pre_largada"] is False, "largou: sai da pre-largada")
    # sessao de qualificacao na garagem
    j3 = T.cenario_corrida()
    j3.sessao = 6
    j3.carros[3].box = True
    tel3, _ = T.telemetria(j3)
    confere(tel3.ler()["estrategia"]["pre_largada"] is True, "qualificacao na garagem: pre-largada")


def teste_janelas_e_menu():
    grupo("v1.2.0 - janelas, grafico unificado e configuracao")
    m = T.preparar_modulo()
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    cfg = m.carregar_config_lmu()
    cfg["travado"] = True
    for chave in ("mostrar_luz_abs", "mostrar_luz_tc", "mostrar_retorno", "mostrar_estrategia", "inputs_segundos",
                  "retorno_pare", "luz_tc_cor", "x_luz_abs", "escala_luz_tc"):
        confere(chave in cfg, f"config LMU tem {chave}")
    confere("mostrar_inputs" not in cfg and "x_inputs" not in cfg, "nao existe janela Inputs separada")
    base = m.base
    base.definir_tema(True, 0.8, False, True)
    d = base.Telemetria(demo=True).ler()
    for estilo, vidro in (("glass", True), ("sport", False)):
        base.definir_tema(True, 0.8, not vidro, vidro)
        for cls in (base.JanelaTelemetria, base.JanelaLuzAbs, base.JanelaLuzTc, base.JanelaRetorno, base.JanelaEstrategia):
            w = cls(dict(cfg))
            w.show()
            for k in range(30):
                w.atualizar(d)
            w.repaint()
            img = w.grab().toImage()
            confere(not img.isNull() and img.width() > 10, f"{cls.__name__} desenha ({estilo})")
    base.definir_tema(True, 0.8, False, True)
    # dados vazios (jogo fechado) nao quebram
    for cls in (base.JanelaTelemetria, base.JanelaLuzAbs, base.JanelaLuzTc, base.JanelaRetorno, base.JanelaEstrategia):
        w = cls(dict(cfg))
        w.show()
        w.atualizar(base.Telemetria._vazio())
        w.repaint()
    confere(True, "janelas aceitam dados vazios")
    # grafico da Telemetria com marcas do jogo
    jt = base.JanelaTelemetria(dict(cfg, inputs_marca_tc=True))
    jt.show()
    j = T.cenario_corrida()
    tel, rel = T.telemetria(j)
    for k in range(60):
        rel.avancar(0.03)
        j.et += 0.03
        jt.atualizar(tel.ler())
    jt.repaint()
    confere(len(jt.hist) >= 30, "grafico acumula amostras do jogo")


def teste_principal_v12():
    grupo("v1.2.0 - programa completo com as 4 janelas novas e o menu")
    m = T.preparar_modulo()
    alvo = T.TMP / "config_principal_v12.json"
    m.ARQ_CONFIG_LMU = alvo
    m.redirecionar_arquivos(T.TMP, alvo, T.TMP / "log_principal_v12.txt")
    j = T.cenario_corrida()
    j.superficie, j.vel_ms = 2, (0.0, 0.0, 0.0)
    leitor = lmu.LeitorLMU(abridor=lambda: T.MapaFalso(j), relogio=lambda: time.monotonic())
    estado = {}

    def ao_iniciar(app, janelas, telemetria_, config):
        from PySide6.QtCore import QTimer
        t1 = QTimer()

        def avancar():
            j.et += 0.05
            j.carros[2].dist = (j.carros[2].dist + 3.0) % j.comprimento
        t1.timeout.connect(avancar)
        t1.start(50)
        app._t_teste = t1

        def conferir():
            estado["n"] = len(janelas)
            estado["nomes"] = [type(w).__name__ for w in janelas]
            menu = app._refs[3]
            estado["menu"] = [a.text() for a in menu if hasattr(a, "text")] if hasattr(menu, "__iter__") else []
            estado["acoes"] = sorted(app._refs[-1].keys())
            estado["retorno"] = telemetria_.v12_retorno.lim_pare
            cen = getattr(app, "_central", None)
            estado["central"] = cen is not None
            if cen:
                cen[0].mostrar()
                estado["central_cartoes"] = len(cen[0]._cartoes)
                estado["menu_curto"] = [x.text() for x in cen[1].actions()]
        QTimer.singleShot(1500, conferir)
        QTimer.singleShot(1900, app.quit)
    codigo = m.principal(leitor=leitor, config_extra={"auto_modo": False, "travado": True, "retorno_sempre": True}, ao_iniciar=ao_iniciar)
    confere(codigo == 0, "principal terminou sem erro")
    confere(estado.get("n") == 23, f"23 janelas ({estado.get('n')})")
    for nome in ("JanelaLuzAbs", "JanelaLuzTc", "JanelaRetorno", "JanelaEstrategia"):
        confere(nome in estado.get("nomes", []), f"{nome} criada")
    confere(estado.get("central") and estado.get("central_cartoes", 0) >= 20, f"central de configuracoes criada ({estado.get('central_cartoes')} paineis)")
    confere(any("Abrir configura" in t for t in estado.get("menu_curto", [])) and any("avan" in t for t in estado.get("menu_curto", [])),
            f"menu da bandeja enxuto ({estado.get('menu_curto')})")
    for chave in ("mostrar_luz_abs", "mostrar_luz_tc", "mostrar_retorno", "mostrar_estrategia", "inputs_marca_abs"):
        confere(chave in estado.get("acoes", []), f"menu da bandeja tem {chave}")
    log = T.TMP / "log_principal_v12.txt"
    texto = log.read_text(encoding="utf-8") if log.exists() else ""
    confere("LMU 1.6.3" in texto, "cabecalho do log com a versao 1.6.3")
    confere("Traceback" not in texto and "ERRO" not in texto.upper().replace("ERROS", ""), "nenhum erro no log")


def teste_marcas():
    grupo("v1.3.1 - montadora pelo modelo do carro (sem usar o nome da equipe)")
    m = T.preparar_modulo()
    base = m.base
    casos = [("Manthey EMA #92 911 GT3 R LMGT3", "Porsche"), ("Heart of Racing Team #27 Aston Martin Vantage AMR LMGT3 Evo", "Aston Martin"),
             ("TF Sport #81 Corvette Z06 LMGT3.R", "Corvette"), ("Kessel Racing #57 296 LMGT3", "Ferrari"),
             ("Cadillac Hertz Team Jota #12 V-Series.R", "Cadillac"), ("Alpine Endurance Team #35 A424", "Alpine"),
             ("United Autosports #22 Oreca 07", "Oreca"), ("Genesis Magma Racing #17 GMR-001", "Genesis"),
             ("Toyota Gazoo Racing #7 GR010", "Toyota"), ("Peugeot TotalEnergies #93 9X8", "Peugeot"),
             ("Akkodis ASP Lexus RC F", "Lexus"), ("BMW M Team WRT #31 M4 LMGT3", "BMW"),
             ("Inter Europol Competition #34", "--"), ("Heart of Racing", "--")]
    for texto, esperado in casos:
        confere(base.marca_do_carro(texto, fallback=False) == esperado, f"LMU: '{texto}' -> {esperado}")
    confere(base.marca_do_carro("Zzz Team 5") == "Zzz", "iRacing: sem marca conhecida ainda usa a primeira palavra")
    confere(base.marca_do_carro("Chevrolet Corvette C8.R") == "Corvette", "iRacing: Chevrolet Corvette usa o emblema da Corvette (1.6.2)")
    confere(base.marca_do_carro("") == "--" and base.marca_do_carro(None, fallback=False) == "--", "vazio -> --")


TESTES = [teste_marcas, teste_luzes, teste_retorno, teste_estrategia, teste_janelas_e_menu, teste_principal_v12]

if __name__ == "__main__":
    for t in TESTES:
        try:
            t()
        except Exception:
            T._falhas.append(f"{t.__name__}: excecao")
            print("  EXCECAO em", t.__name__)
            traceback.print_exc()
    print(f"\nResultado LMU 1.2.0: {T._ok} verificacoes ok, {len(T._falhas)} falha(s).")
    for f in T._falhas:
        print(" -", f)
    sys.exit(1 if T._falhas else 0)
