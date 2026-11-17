# -*- coding: utf-8 -*-
"""Tela de filtros do cronograma (menu da bandeja / Central). Qt; a logica fica em ov_cronograma.

Build al: tudo vale AO VIVO (cada marcacao grava no config em memoria e atualiza a previa da tela, do painel Calendario e da Central);
Salvar grava em disco, Cancelar volta ao que estava. Botao e arrastar-e-soltar para importar um novo PDF 'Season Schedule'."""
import copy
import datetime as _dt

import ov_cronograma as cr


def importar_com_dialogo(pasta, pai=None, escolher_arquivo=None, confirmar=None, caminho=None):
    """Escolhe o PDF/TXT, importa para a pasta do overlay e conta o resultado. Retorna o dicionario de importar_arquivo (ou None se cancelou).
    escolher_arquivo/confirmar existem para os testes (sem janelas)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    import os
    if caminho is None:
        if escolher_arquivo is not None:
            caminho = escolher_arquivo()
        else:
            inicio = os.path.join(os.path.expanduser("~"), "Downloads")
            caminho = QFileDialog.getOpenFileName(pai, "Escolher o PDF Season Schedule do iRacing", inicio if os.path.isdir(inicio) else "",
                                                  "Cronograma do iRacing (*.pdf *.txt)")[0]
    if not caminho:
        return None

    def rodar():
        if QApplication.instance() is not None and escolher_arquivo is None:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            return cr.importar_arquivo(caminho, pasta)
        finally:
            if QApplication.instance() is not None and escolher_arquivo is None:
                QApplication.restoreOverrideCursor()
    res = rodar()
    if res["precisa_pypdf"]:
        pergunta = ("Para ler o PDF o overlay precisa de um componente pequeno (pypdf).\n\nInstalar agora? (precisa de internet; leva alguns segundos)")
        if confirmar is not None:
            quer = confirmar(pergunta)
        else:
            quer = QMessageBox.question(pai, "Instalar leitor de PDF", pergunta) == QMessageBox.Yes
        if quer:
            if confirmar is None and QApplication.instance() is not None:
                QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                ok, motivo = cr.instalar_pypdf()
            finally:
                if confirmar is None and QApplication.instance() is not None:
                    QApplication.restoreOverrideCursor()
            if ok:
                res = rodar()
            else:
                res["msg"] = "Não consegui instalar o leitor de PDF: " + (motivo or "erro desconhecido") + " Alternativa: atualizar_cronograma.bat."
        else:
            res["msg"] = "Importação cancelada: falta o leitor de PDF (pypdf). Alternativa: atualizar_cronograma.bat."
    return res


def abrir_dialogo(config, dados, salvar, aplicar, pai=None, pasta=None, escolher_arquivo=None, confirmar=None, agora_fn=None):
    """Mostra a tela. Os filtros valem ao vivo; Salvar grava e liga o aviso, Cancelar desfaz. Retorna True se o piloto salvou."""
    from PySide6.QtCore import QTime, Qt, QTimer
    from PySide6.QtGui import QBrush, QColor
    from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                                   QListWidgetItem, QPushButton, QSpinBox, QDoubleSpinBox, QTimeEdit, QVBoxLayout, QWidget)
    agora_fn = agora_fn or (lambda: _dt.datetime.now(_dt.timezone.utc))
    original = {"filtros": copy.deepcopy(config.get("cronograma_filtros")), "ativo": config.get("cronograma_ativo"), "cal": config.get("mostrar_calendario")}
    est = {"dados": dados}
    f = cr.filtros_validos(config.get("cronograma_filtros"))

    class Dialogo(QDialog):
        def dragEnterEvent(self, e):
            if e.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith((".pdf", ".txt")) for u in e.mimeData().urls()):
                e.acceptProposedAction()

        def dropEvent(self, e):
            for u in e.mimeData().urls():
                if u.toLocalFile().lower().endswith((".pdf", ".txt")):
                    importar(u.toLocalFile())
                    break

    dlg = Dialogo(pai)
    dlg.setAcceptDrops(True)
    dlg.setWindowTitle("Cronograma de corridas: filtros e avisos")
    dlg.resize(680, 820)
    lay = QVBoxLayout(dlg)

    # ---- fonte + importar
    topo = QHBoxLayout()
    info = QLabel()
    info.setWordWrap(True)
    topo.addWidget(info, 1)
    b_imp = QPushButton("Importar novo cronograma (PDF)…")
    b_imp.setToolTip("Escolha o PDF 'Season Schedule' da nova temporada (ou arraste o arquivo para esta tela).")
    b_imp.setEnabled(bool(pasta))
    topo.addWidget(b_imp)
    lay.addLayout(topo)
    status = QLabel("")
    status.setWordWrap(True)
    lay.addWidget(status)

    # ---- series
    busca = QLineEdit()
    busca.setPlaceholderText("Buscar série...")
    lay.addWidget(busca)
    lista = QListWidget()
    lay.addWidget(lista, 1)
    barra = QHBoxLayout()
    b_vis = QPushButton("Marcar as visíveis")
    b_lim = QPushButton("Desmarcar todas")
    cont = QLabel("")
    barra.addWidget(b_vis)
    barra.addWidget(b_lim)
    barra.addWidget(cont, 1)
    lay.addLayout(barra)
    lay.addWidget(QLabel("Séries marcadas (vazio = qualquer série). Os demais filtros se somam (E); dentro de cada lista vale qualquer item (OU)."))

    # ---- demais filtros
    form = QFormLayout()
    pistas = QLineEdit(", ".join(f["pistas"]))
    pistas.setPlaceholderText("ex.: spa, monza, daytona")
    carros = QLineEdit(", ".join(f["carros"]))
    carros.setPlaceholderText("ex.: porsche, mx-5")
    form.addRow("Pista contém:", pistas)
    form.addRow("Carro contém:", carros)
    caixas = QWidget()
    hl = QHBoxLayout(caixas)
    hl.setContentsMargins(0, 0, 0, 0)
    cls = {}
    for c in cr.CLASSES:
        cb = QCheckBox(c)
        cb.setChecked(c in f["classes"])
        cls[c] = cb
        hl.addWidget(cb)
    form.addRow("Classe da série (como no iRacing):", caixas)
    usar_j = QCheckBox("Só corridas dentro deste horário (horário local)")
    usar_j.setChecked(f["janela"])
    ini, fim = QTimeEdit(QTime.fromString(f["ini"], "HH:mm")), QTimeEdit(QTime.fromString(f["fim"], "HH:mm"))
    for t in (ini, fim):
        t.setDisplayFormat("HH:mm")
    jl = QHBoxLayout()
    jl.addWidget(usar_j)
    jl.addWidget(ini)
    jl.addWidget(QLabel("até"))
    jl.addWidget(fim)
    form.addRow("Janela:", jl)
    ant = QSpinBox()
    ant.setRange(1, 240)
    ant.setSuffix(" min")
    ant.setValue(f["antecedencia_min"])
    form.addRow("Avisar com antecedência de:", ant)
    fuso_auto = QCheckBox("Usar o fuso horário do Windows (recomendado)")
    fuso_auto.setChecked(f["fuso_auto"])
    fuso_info = QLabel("")
    fuso = QDoubleSpinBox()
    fuso.setRange(-12, 14)
    fuso.setSingleStep(0.5)
    fuso.setValue(f["fuso_h"])
    fuso.setSuffix(" h do UTC")
    fuso.setEnabled(not f["fuso_auto"])
    form.addRow("Fuso dos horários:", fuso_auto)
    form.addRow("", fuso_info)
    form.addRow("Fuso fixo (só sem o do Windows):", fuso)
    lay.addLayout(form)

    # ---- previa ao vivo
    lay.addWidget(QLabel("Prévia ao vivo: próximas corridas com estes filtros (as laranjas já entram no aviso)"))
    previa = QListWidget()
    previa.setFixedHeight(190)
    previa.setSelectionMode(QListWidget.NoSelection)
    lay.addWidget(previa)
    resumo = QLabel("")
    resumo.setWordWrap(True)
    lay.addWidget(resumo)

    bt = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    desligar = bt.addButton("Desligar o aviso", QDialogButtonBox.DestructiveRole)
    lay.addWidget(bt)
    bt.accepted.connect(dlg.accept)
    bt.rejected.connect(dlg.reject)
    resultado = {"desligar": False}

    # ---- logica
    def marcadas():
        return [lista.item(i).text() for i in range(lista.count()) if lista.item(i).checkState() == Qt.Checked]

    def sep(t):
        return [x.strip() for x in t.replace(";", ",").split(",") if x.strip()]

    def ler_filtros():
        return cr.filtros_validos({
            "series": marcadas(), "pistas": sep(pistas.text()), "carros": sep(carros.text()), "classes": [c for c, cb in cls.items() if cb.isChecked()],
            "janela": usar_j.isChecked(), "ini": ini.time().toString("HH:mm"), "fim": fim.time().toString("HH:mm"),
            "antecedencia_min": ant.value(), "fuso_h": fuso.value(), "fuso_auto": fuso_auto.isChecked()})

    def desenhar_previa():
        previa.clear()
        d, filtros = est["dados"], ler_filtros()
        fuso.setEnabled(not fuso_auto.isChecked())
        fuso_info.setText("Os horários seguem o relógio deste computador: " + cr.fuso_txt(filtros, agora_fn()) + " (hoje)."
                          if filtros["fuso_auto"] else "Fuso fixo: " + cr.fuso_txt(filtros, agora_fn()) + ". Confira se bate com o seu Windows.")
        n_m = len(marcadas())
        cont.setText(f"{n_m} série(s) marcada(s)")
        if not d:
            resumo.setText("Sem cronograma carregado. Use o botão acima para importar o PDF Season Schedule do iRacing.")
            return
        if not cr.tem_filtro(filtros):
            resumo.setText("Marque ao menos um filtro (série, pista, carro, classe ou horário) para ver as corridas aqui. Sem filtro o overlay não avisa nada.")
            return
        agora = agora_fn()
        todas = cr.proximas(d, filtros, agora, 500)
        for it in todas[:8]:
            li = QListWidgetItem(cr.linha_previa(it))
            if it.get("alerta"):
                li.setForeground(QBrush(QColor(255, 150, 40)))
            elif it.get("em_andamento"):
                li.setForeground(QBrush(QColor(90, 200, 120)))
            previa.addItem(li)
        if todas:
            alertas = sum(1 for it in todas if it.get("alerta"))
            resumo.setText(f"{len(todas)} corrida(s) nas próximas 72 h" + (f" (mostrando as 8 primeiras); {alertas} em aviso agora." if len(todas) > 8 else f"; {alertas} em aviso agora."))
        else:
            dica = cr.dica_vazio(d, filtros, agora)
            resumo.setText("Nenhuma corrida nas próximas 72 h com estes filtros. " + dica)

    def ao_mudar(*_):
        """Ao vivo: grava na memoria (painel real e previa da Central leem daqui) e redesenha a previa da tela."""
        config["cronograma_filtros"] = ler_filtros()
        config["cronograma_ativo"] = True
        desenhar_previa()

    def preencher_info():
        d = est["dados"]
        sem = len(cr.sem_horario(d)) if d else 0
        info.setText(("Fonte: " + str(d.get("fonte", "")) + "  |  gerado em " + str(d.get("gerado_em", "")) + f"\n{len(d.get('series', []))} séries; {sem} sem horário automático (o PDF não informa) não geram aviso.")
                     if d else "cronograma.json não encontrado. Importe o PDF Season Schedule com o botão ao lado.")

    def preencher_lista(manter):
        lista.blockSignals(True)
        lista.clear()
        for nome in (cr.listar_series(est["dados"]) if est["dados"] else []):
            it = QListWidgetItem(nome)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if nome in manter else Qt.Unchecked)
            lista.addItem(it)
        lista.blockSignals(False)
        filtrar(busca.text())

    def filtrar(txt):
        t = cr._norm(txt)
        for i in range(lista.count()):
            lista.item(i).setHidden(bool(t) and t not in cr._norm(lista.item(i).text()))

    def marcar_visiveis():
        lista.blockSignals(True)
        for i in range(lista.count()):
            if not lista.item(i).isHidden():
                lista.item(i).setCheckState(Qt.Checked)
        lista.blockSignals(False)
        ao_mudar()

    def desmarcar_todas():
        lista.blockSignals(True)
        for i in range(lista.count()):
            lista.item(i).setCheckState(Qt.Unchecked)
        lista.blockSignals(False)
        ao_mudar()

    def importar(caminho=None):
        antes = set(marcadas())
        res = importar_com_dialogo(pasta, dlg, escolher_arquivo=escolher_arquivo, confirmar=confirmar, caminho=caminho)
        if res is None:
            return
        if not res["ok"]:
            status.setStyleSheet("color:#e05555;")
            status.setText(res["msg"])
            return
        est["dados"] = res["dados"]
        existentes = set(cr.listar_series(res["dados"]))
        sumiram = sorted(antes - existentes)
        preencher_info()
        preencher_lista(antes & existentes)
        txt = res["msg"] + " Já foi gravado em disco (o Cancelar só desfaz os filtros)."
        if sumiram:
            txt += f" Atenção: {len(sumiram)} série(s) que você tinha marcado não existem neste cronograma: " + ", ".join(sumiram[:4]) + ("..." if len(sumiram) > 4 else "") + "."
        status.setStyleSheet("color:#4caf70;")
        status.setText(txt)
        ao_mudar()

    preencher_info()
    preencher_lista(set(f["series"]))
    busca.textChanged.connect(filtrar)
    lista.itemChanged.connect(ao_mudar)
    b_vis.clicked.connect(marcar_visiveis)
    b_lim.clicked.connect(desmarcar_todas)
    b_imp.clicked.connect(lambda: importar())
    pistas.textChanged.connect(ao_mudar)
    carros.textChanged.connect(ao_mudar)
    for cb in cls.values():
        cb.toggled.connect(ao_mudar)
    usar_j.toggled.connect(ao_mudar)
    ini.timeChanged.connect(ao_mudar)
    fim.timeChanged.connect(ao_mudar)
    ant.valueChanged.connect(ao_mudar)
    fuso.valueChanged.connect(ao_mudar)
    fuso_auto.toggled.connect(ao_mudar)
    dlg.importar = importar                                   # (testes) mesmo caminho do botao e do arrastar-e-soltar
    dlg._desenhar_previa = desenhar_previa
    relogio = QTimer(dlg)                                     # a contagem regressiva da previa anda sozinha
    relogio.timeout.connect(desenhar_previa)
    relogio.start(1000)
    desenhar_previa()

    def ao_desligar():
        resultado["desligar"] = True
        dlg.accept()
    desligar.clicked.connect(ao_desligar)
    aceito = dlg.exec() == QDialog.Accepted
    relogio.stop()
    if not aceito:                                            # Cancelar / fechar: volta ao que estava antes de abrir
        config["cronograma_filtros"] = original["filtros"] if original["filtros"] is not None else {}
        config["cronograma_ativo"] = original["ativo"]
        if original["cal"] is not None:
            config["mostrar_calendario"] = original["cal"]
        return False
    config["cronograma_filtros"] = ler_filtros()
    if resultado["desligar"]:
        config["cronograma_ativo"] = False
    else:
        config["cronograma_ativo"] = True
        config["mostrar_calendario"] = True          # o aviso aparece no painel Calendario
    salvar(config)
    aplicar()
    return True
