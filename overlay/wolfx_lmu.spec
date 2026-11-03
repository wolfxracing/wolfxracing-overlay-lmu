# -*- mode: python ; coding: utf-8 -*-
# Receita do PyInstaller (versao EXE, pasta unica). Gerada para a versao 1.6.3.
# Uso: gerar_exe*.bat (nao precisa editar). Config, logs, emblemas e bandeiras ficam AO LADO do .exe.
a = Analysis(
    ['overlay_lmu.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'PIL', 'IPython', 'pytest',
             'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick',
             'PySide6.Qt3DCore', 'PySide6.QtMultimedia', 'PySide6.QtPdf', 'PySide6.QtSql', 'PySide6.QtTest',
             'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtBluetooth', 'PySide6.QtSensors', 'irsdk', 'yaml'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WolfxRacing_LMU',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # sem UPX: menos falso positivo de antivirus
    console=False,             # sem janela preta (erros vao para o overlay_log*.txt ao lado do .exe)
    icon='wolfxracing.ico',
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='WolfxRacing_LMU')
