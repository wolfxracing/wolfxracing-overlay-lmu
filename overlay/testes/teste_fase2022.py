"""Testes automatizados da Fase 20.2.2: teclas de atalho globais para o Stream Deck.

  1) mapa de teclas (ov_nucleo): sem duplicados, F13..F24, todo alvo existe no overlay
  2) DespachanteTeclas: repeticao rapida, atalho desconhecido, erro dentro do atalho
  3) EscutaTeclas com uma API falsa do Windows: registro, falhas parciais, fila, desligar e liberar
  4) integracao: o overlay inteiro (principal()) recebe atalhos pela API falsa e aciona o MESMO que o menu da bandeja
  5) arquivos de apoio (fechar_overlay.bat, ATALHOS_STREAM_DECK.txt)

Executar: py -3.12 testes\\teste_fase2022.py   (ou executar_testes.bat). Nao precisa do iRacing aberto.
ATENCAO: a API do Windows (RegisterHotKey) e SIMULADA aqui. A confirmacao real (o Stream Deck apertando o atalho
com o overlay aberto) esta no ROTEIRO_VALIDACAO.txt (teste 13)."""
import os, sys, json, tempfile, queue, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.argv = ["x", "--demo"]
PACOTE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PACOTE)
from pathlib import Path
import overlay_iracing as o
import ov_nucleo as n
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

S = Path(tempfile.mkdtemp(prefix="overlay_testes_2022_"))
o.ARQ_LOG = S / "log.txt"; o.ARQ_CONFIG = S / "cfg_inexistente.json"
o.ARQ_PENDENTE = S / "pendente.json"; o.ARQ_COMPARACAO = S / "comparacao.csv"; o.ARQ_HISTORICO = S / "historico.csv"
o.ARQ_RECORDES = S / "recordes.json"; o.ARQ_PNEUS = S / "pneus.json"; o.ARQ_MAPAS = S / "mapas.json"


def log():
    return o.ARQ_LOG.read_text(encoding="utf-8") if o.ARQ_LOG.exists() else ""


class ApiFalsa:
    """Imita a API do Windows: guarda o que foi registrado e entrega 'teclas apertadas' pela fila."""
    def __init__(self, ocupados=(), falha_preparar=False):
        self.q, self.reg, self.liberados = queue.Queue(), {}, []
        self.ocupados, self.falha_preparar, self.encerrado = set(ocupados), falha_preparar, False

    def preparar(self):
        if self.falha_preparar:
            raise RuntimeError("sem fila de mensagens")
        return 4242

    def registrar(self, codigo, mods, vk):
        if (mods & ~n.MOD_NOREPEAT, vk) in self.ocupados:
            return False, "ja usada por outro programa (erro 1409)"
        self.reg[codigo] = (mods, vk)
        return True, ""

    def liberar(self, codigo):
        self.liberados.append(codigo)

    def esperar(self):
        return self.q.get()

    def encerrar(self, id_thread):
        assert id_thread == 4242
        self.encerrado = True
        self.q.put(None)

    def apertar(self, codigo):
        self.q.put(codigo)


def codigo(id_):
    return n.ID_BASE_TECLA + [a.id for a in n.ATALHOS].index(id_)


# ====================================================================================================
# 1) MAPA DE TECLAS
# ====================================================================================================
assert n.VERSAO_NUCLEO == "20.2.2"
assert n.validar_atalhos() == [], n.validar_atalhos()
assert len(n.ATALHOS) == 31 and len({a.id for a in n.ATALHOS}) == 31
assert len({(a.mods, a.fn) for a in n.ATALHOS}) == 31                         # nenhuma combinacao repetida
assert all(13 <= a.fn <= 24 and n.VK_F13 <= a.vk <= 0x87 for a in n.ATALHOS)
assert n.ATALHOS[0].nome == "Ctrl+Alt+Shift+F13" and n.atalho_por_id("perfil_treino").nome == "Ctrl+Alt+F14"
assert n.atalho_por_id("sair").nome == "Ctrl+Alt+F22" and n.atalho_por_id("sair").vk == 0x7C + 9
assert n.atalho_por_id("nao_existe") is None
# as 12 janelas, os 4 perfis e os controles estao todos no mapa
janelas = [a for a in n.ATALHOS if a.id.startswith("janela_")]
assert len(janelas) == 19 and {a.alvo for a in janelas} == {
    "mostrar_telemetria", "mostrar_voltas", "mostrar_relativo", "mostrar_classificacao", "mostrar_mapa", "mostrar_radar",
    "mostrar_pneus", "mostrar_setores", "mostrar_clima", "mostrar_danos", "mostrar_combustivel", "mostrar_forca_g",
    "mostrar_luz_abs", "mostrar_luz_tc", "mostrar_retorno", "mostrar_estrategia",
    "mostrar_consumo", "mostrar_delta_trace", "mostrar_curvas"}   # 1.3.0 (Alt+F13..F16) e build q (Alt+F17..F19)
assert {a.alvo for a in n.ATALHOS if a.tipo == "perfil"} == {"auto", "Treino", "Classificacao", "Corrida"}
assert {a.alvo for a in n.ATALHOS if a.tipo == "perfil"} - {"auto"} == set(n.PERFIS)        # nomes iguais aos dos perfis reais
assert {a.alvo for a in n.ATALHOS if a.tipo == "chamar"} == {"zerar_pico_g", "limpar_impactos", "pedir_pit", "cancelar_pit", "sair"}
# codigos: ida e volta; fora da faixa = desconhecido
assert n.atalho_por_codigo(n.ID_BASE_TECLA) is n.ATALHOS[0]
assert n.atalho_por_codigo(n.ID_BASE_TECLA + 21).id == "sair" and n.atalho_por_codigo(n.ID_BASE_TECLA + 26).id == "pedir_pit" and n.atalho_por_codigo(n.ID_BASE_TECLA + 27).id == "cancelar_pit" and n.atalho_por_codigo(n.ID_BASE_TECLA + 28).id == "janela_consumo" and n.atalho_por_codigo(n.ID_BASE_TECLA + 29).id == "janela_delta_trace" and n.atalho_por_codigo(n.ID_BASE_TECLA + 30).id == "janela_curvas" and n.atalho_por_codigo(n.ID_BASE_TECLA + 31) is None
assert n.atalho_por_codigo(0) is None and n.atalho_por_codigo(-5) is None
assert n.ID_BASE_TECLA + len(n.ATALHOS) <= 0xBFFF                                           # faixa permitida do Windows
# o validador acusa os defeitos
A = n.AtalhoGlobal
assert any("repetido" in e for e in n.validar_atalhos([A("a", "x", 7, 13, "chamar", "x"), A("a", "y", 7, 14, "chamar", "x")]))
assert any("mesma combinacao" in e for e in n.validar_atalhos([A("a", "x", 7, 13, "chamar", "x"), A("b", "y", 7, 13, "chamar", "x")]))
assert any("fora de F13" in e for e in n.validar_atalhos([A("a", "x", 7, 12, "chamar", "x")]))
assert any("sem modificador" in e for e in n.validar_atalhos([A("a", "x", 0, 13, "chamar", "x")]))
assert any("tipo desconhecido" in e for e in n.validar_atalhos([A("a", "x", 7, 13, "voar", "x")]))
# toda chave "alternar" existe na configuracao padrao do overlay (ou e o item especial auto_modo)
cfg0 = o.carregar_config()
for a in n.ATALHOS:
    if a.tipo == "alternar":
        assert a.alvo in cfg0, a.alvo
print("1) mapa de teclas: 31 atalhos, sem conflito, F13..F24, alvos existentes OK")

# ====================================================================================================
# 2) DESPACHANTE
# ====================================================================================================
chamadas, erros, eventos, relogio = [], [], [], [100.0]
def executor(tipo, alvo):
    if alvo == "quebra":
        raise RuntimeError("defeito")
    chamadas.append((tipo, alvo))
d = n.DespachanteTeclas(executor, relogio=lambda: relogio[0], ao_erro=lambda c, e: erros.append((c, repr(e))), ao_evento=eventos.append)
assert d.tratar(codigo("perfil_corrida")) == "ok" and chamadas == [("perfil", "Corrida")]
assert "Ctrl+Alt+F16" in eventos[-1] and "Corrida" in eventos[-1]
relogio[0] += 0.10
assert d.tratar(codigo("perfil_corrida")) == "repeticao" and len(chamadas) == 1          # rebote/toque duplo ignorado
assert d.tratar(codigo("perfil_treino")) == "ok" and len(chamadas) == 2                  # outro atalho nao e afetado
relogio[0] += n.INTERVALO_MIN_ATALHO + 0.01
assert d.tratar(codigo("perfil_corrida")) == "ok" and len(chamadas) == 3                 # passado o intervalo, vale de novo
assert d.tratar(0) == "desconhecido" and d.tratar(n.ID_BASE_TECLA + 999) == "desconhecido" and len(chamadas) == 3
d2 = n.DespachanteTeclas(executor, atalhos=(A("x", "Quebra", 7, 13, "alternar", "quebra"),), ao_erro=lambda c, e: erros.append((c, repr(e))))
assert d2.tratar(n.ID_BASE_TECLA) == "erro" and erros and "defeito" in erros[0][1] and "Ctrl+Alt+Shift+F13" in erros[0][0]
assert n.DespachanteTeclas(executor, atalhos=(A("x", "Quebra", 7, 13, "alternar", "quebra"),)).tratar(n.ID_BASE_TECLA) == "erro"   # sem ao_erro
print("2) despachante: repeticao, desconhecido e erro isolado OK")

# ====================================================================================================
# 3) ESCUTA com API falsa
# ====================================================================================================
api = ApiFalsa()
e = n.EscutaTeclas(api)
n_ok, falhas = e.iniciar()
assert n_ok == 31 and falhas == [] and len(api.reg) == 31
assert all(m & n.MOD_NOREPEAT for m, _ in api.reg.values())                  # sem repeticao ao segurar a tecla
assert api.reg[codigo("janela_telemetria")] == (n.MODS_JANELAS | n.MOD_NOREPEAT, 0x7C)
assert api.reg[codigo("sair")] == (n.MODS_CONTROLES | n.MOD_NOREPEAT, 0x7C + 9)
assert e.iniciar() == (31, [])                                              # iniciar de novo nao duplica nada
for c in (codigo("janela_radar"), codigo("perfil_treino"), codigo("janela_radar")):
    api.apertar(c)
t0 = time.time(); recebidos = []
while len(recebidos) < 3 and time.time() - t0 < 3:
    recebidos += e.retirar(); time.sleep(0.01)
assert recebidos == [codigo("janela_radar"), codigo("perfil_treino"), codigo("janela_radar")], recebidos
assert e.retirar() == []
e.parar()
assert api.encerrado and sorted(api.liberados) == sorted(api.reg) and e.registrados == []     # liberou todos os atalhos
e.parar()                                                                                      # parar de novo: sem erro

# combinacao ocupada por outro programa: so ela falha, o resto funciona e a falha diz qual foi
api = ApiFalsa(ocupados={(n.MODS_CONTROLES, 0x7C + 3)})                         # Ctrl+Alt+F16 = perfil Corrida
e = n.EscutaTeclas(api)
n_ok, falhas = e.iniciar()
assert n_ok == 30 and len(falhas) == 1 and falhas[0][0].id == "perfil_corrida" and "1409" in falhas[0][1]
api.apertar(codigo("janela_mapa")); time.sleep(0.2)
assert e.retirar() == [codigo("janela_mapa")]
e.parar()
assert codigo("perfil_corrida") not in api.liberados and len(api.liberados) == 30        # so libera o que registrou

# a API quebra ao preparar: nao derruba, registra o erro e nao fica esperando
api = ApiFalsa(falha_preparar=True)
e = n.EscutaTeclas(api)
assert e.iniciar() == (0, []) and "sem fila" in e.erro
e.parar()
print("3) escuta (API falsa): registro, falha parcial, fila, desligar e liberar OK")

# fora do Windows nao ha API real (o overlay segue funcionando sem atalhos)
if sys.platform != "win32":
    assert o.criar_api_teclas() is None
# a implementacao real expoe a mesma interface que a falsa
for nome in ("preparar", "registrar", "liberar", "esperar", "encerrar"):
    assert callable(getattr(n.ApiTeclasWindows, nome)), nome

# ====================================================================================================
# 4) INTEGRACAO: o overlay inteiro recebe os atalhos e aciona o mesmo que o menu da bandeja
# ====================================================================================================
api_int = ApiFalsa()
o.criar_api_teclas = lambda: api_int
salvos = []
o.salvar_config = lambda c: salvos.append(c)
resultado = {}


def bombear(segundos=0.35):
    fim = time.time() + segundos
    while time.time() < fim:
        QCoreApplication.processEvents(); time.sleep(0.01)


def apertar(id_):
    api_int.apertar(codigo(id_)); bombear()


CENARIO = {}
INSTANCIA = []


class AppTeste(QApplication):
    def exec(self):
        return CENARIO["fn"](self)


def fabrica_app(argv):                       # o Qt so admite um QApplication por processo: reaproveita o mesmo
    if not INSTANCIA:
        INSTANCIA.append(AppTeste(argv))
    return INSTANCIA[0]


def cenario_integracao(self):
    if True:
        janelas, bandeja, menu, acoes, *_, trava, visib, timer_teclas, despachante, estado, acao_por_chave = self._refs
        cfg = salvos[-1] if salvos else None
        bombear(0.4)
        esc = estado["escuta"]
        assert esc is not None and len(esc.registrados) == 31 and len(api_int.reg) == 31
        # cada atalho de tipo alternar/perfil aponta para um item real do menu
        for a in n.ATALHOS:
            if a.tipo == "alternar":
                assert a.alvo in acao_por_chave, a.alvo
        assert "atalhos globais: 31 de 31 registrados" in log()
        cfg_vivo = lambda: salvos[-1]

        # janela: liga/desliga como o clique no menu (menu e config andam juntos)
        assert acao_por_chave["mostrar_radar"].isChecked()
        apertar("janela_radar")
        assert not acao_por_chave["mostrar_radar"].isChecked() and cfg_vivo()["mostrar_radar"] is False
        apertar("janela_radar")
        assert acao_por_chave["mostrar_radar"].isChecked() and cfg_vivo()["mostrar_radar"] is True
        # as 12 janelas: cada uma muda a sua propria chave e nenhuma outra
        for a in [x for x in n.ATALHOS if x.id.startswith("janela_")]:
            antes = {k: v for k, v in cfg_vivo().items() if k.startswith("mostrar_")}
            apertar(a.id)
            depois = {k: v for k, v in cfg_vivo().items() if k.startswith("mostrar_")}
            mudou = {k for k in depois if depois[k] != antes[k]}
            assert mudou == {a.alvo}, (a.id, mudou)
            apertar(a.id)
            assert {k: v for k, v in cfg_vivo().items() if k.startswith("mostrar_")} == antes, a.id
        # repeticao rapida (duas teclas em 40 ms) conta uma vez so
        api_int.apertar(codigo("janela_mapa")); api_int.apertar(codigo("janela_mapa")); bombear()
        assert acao_por_chave["mostrar_mapa"].isChecked() is False
        apertar("janela_mapa")
        # perfis
        apertar("perfil_treino")
        c = cfg_vivo()
        assert c["perfil_modo"] == "Treino" and c["perfil_ativo"] == "Treino"
        assert "perfil de exibicao: Treino" in log()
        apertar("perfil_corrida")
        assert cfg_vivo()["perfil_modo"] == "Corrida" and cfg_vivo()["perfil_ativo"] == "Corrida"
        apertar("perfil_classificacao")
        assert cfg_vivo()["perfil_ativo"] == "Classificacao"
        apertar("perfil_auto")
        assert cfg_vivo()["perfil_modo"] == "auto"
        # um perfil recebe a janela que voce ligou/desligou so nele
        apertar("perfil_treino"); apertar("janela_clima")
        assert cfg_vivo()["mostrar_clima"] is False
        apertar("perfil_corrida")
        assert cfg_vivo()["mostrar_clima"] is True and acao_por_chave["mostrar_clima"].isChecked()
        apertar("perfil_treino")
        assert cfg_vivo()["mostrar_clima"] is False and not acao_por_chave["mostrar_clima"].isChecked()
        apertar("janela_clima")
        # controles
        apertar("economia_cpu")
        assert cfg_vivo()["economia_cpu"] is True and o.JanelaBase.MULT_TAXA == 0.5
        apertar("economia_cpu")
        assert cfg_vivo()["economia_cpu"] is False and o.JanelaBase.MULT_TAXA == 1.0
        antes = cfg_vivo()["auto_modo"]; apertar("aparecer_sozinho")
        assert cfg_vivo()["auto_modo"] is (not antes); apertar("aparecer_sozinho")
        antes = cfg_vivo()["travado"]; apertar("travar_posicao")
        assert cfg_vivo()["travado"] is (not antes); apertar("travar_posicao")
        assert cfg_vivo()["travado"] is antes
        apertar("zerar_pico_g"); apertar("limpar_impactos")
        assert "atalho global Ctrl+Alt+F20: Zerar o pico de G" in log() and "Ctrl+Alt+F21" in log()
        # um atalho com defeito nao derruba nada: o proximo continua funcionando
        api_int.apertar(n.ID_BASE_TECLA + 500); bombear()
        apertar("janela_radar"); assert not acao_por_chave["mostrar_radar"].isChecked(); apertar("janela_radar")
        # FECHAR o overlay: chama o mesmo encerramento do "Sair" da bandeja
        pedidos = []; self.quit = lambda: pedidos.append(1)
        apertar("sair")
        assert pedidos == [1] and "Ctrl+Alt+F22: FECHAR o overlay" in log()
        del self.quit
        # desligar as teclas pelo menu: libera os atalhos e para de escutar
        item = acao_por_chave["teclas_globais"]; assert item.isChecked()
        item.setChecked(False); bombear(0.2)
        assert cfg_vivo()["teclas_globais"] is False and estado["escuta"] is None
        assert sorted(api_int.liberados) == sorted(api_int.reg) and "atalhos globais desligados" in log()
        # ligar de novo: registra outra vez
        api_int.reg.clear(); api_int.liberados.clear(); api_int.encerrado = False
        item.setChecked(True); bombear(0.3)
        assert cfg_vivo()["teclas_globais"] is True and len(api_int.reg) == 31 and estado["escuta"] is not None
        apertar("janela_mapa"); assert not acao_por_chave["mostrar_mapa"].isChecked(); apertar("janela_mapa")
        estado["escuta"].parar()                                       # encerra a thread (o aboutToQuit faria o mesmo)
        resultado["ok"] = True
        return 0


CENARIO["fn"] = cenario_integracao
o.QApplication = fabrica_app
assert o.principal() == 0 and resultado.get("ok")
print("4) integracao (overlay inteiro com API falsa): 12 janelas, 4 perfis, controles, fechar, ligar/desligar teclas OK")

# teclas desligadas na configuracao: nada e registrado
S2 = Path(tempfile.mkdtemp(prefix="overlay_testes_2022b_"))
o.ARQ_CONFIG = S2 / "config.json"
json.dump({"teclas_globais": False}, open(o.ARQ_CONFIG, "w"))
api_int = ApiFalsa(); resultado.clear()


def cenario_desligado(self):
    estado = self._refs[-2]
    bombear(0.3)
    assert estado["escuta"] is None and api_int.reg == {}
    resultado["ok"] = True
    return 0


CENARIO["fn"] = cenario_desligado
# (a trava de instancia unica ja esta com este processo: libera para a segunda execucao do principal)
for ref in QApplication.instance()._refs:
    if ref.__class__.__name__ == "QLockFile":
        ref.unlock()
assert o.principal() == 0 and resultado.get("ok")
print("   teclas desligadas na configuracao: nenhum atalho registrado OK")

# ====================================================================================================
# 5) ARQUIVOS DE APOIO
# ====================================================================================================
bat = Path(PACOTE, "fechar_overlay.bat")
if bat.exists():
    txt = bat.read_text(encoding="utf-8")
    assert "overlay_iracing.py" in txt and "Stop-Process" in txt
    assert "taskkill /im python" not in txt.lower() and "-like '*overlay_iracing.py*'" in txt   # nunca mata outros Python
    assert b"\r\n" in bat.read_bytes()                                                          # quebra de linha do Windows
doc = Path(PACOTE, "ATALHOS_STREAM_DECK.txt")
if doc.exists():
    txt = doc.read_text(encoding="utf-8")
    assert all(a.nome in txt and a.rotulo in txt for a in n.ATALHOS), "documentacao fora de sincronia com o mapa"
print("5) arquivos de apoio (fechar_overlay.bat, ATALHOS_STREAM_DECK.txt) OK")

print("TODOS OS TESTES DA FASE 20.2.2 PASSARAM")
print("(API do Windows SIMULADA: nao substitui a validacao real com o Stream Deck, teste 13 do ROTEIRO_VALIDACAO.txt; arquivos temporarios: %s)" % S)
