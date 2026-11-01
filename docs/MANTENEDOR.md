# Guia do mantenedor: publicar uma versão

1. Atualize `CHANGELOG.md` e o número da versão (`VERSAO` no programa principal, se mudou).
2. Rode os testes: `overlay\executar_testes_lmu.bat` (e as validações do `ROTEIRO_VALIDACAO*.txt` no jogo, quando possível).
3. Se o dash mudou: `cd dash/tools && python build_sport.py --so lmu && python check_sport.py`; copie o `.simhubdash` gerado para `dash/` e atualize os prints em `docs/imagens`.
4. Crie o pacote: `python tools/empacotar.py` (gera `dist/wolfxracing-overlay-lmu-vX.Y.Z.zip`, sem arquivos pessoais).
5. Faça o commit e a *tag*: `git tag -a vX.Y.Z -m "..." && git push --tags`.
6. No GitHub: *Releases > Draft a new release*, escolha a tag, cole as notas do CHANGELOG e anexe o `.zip`, o `.simhubdash` e o `.streamDeckProfile`.
7. Antes de publicar, confira que o pacote **não** contém `config*.json`, logs, recordes, mapas, logos de marcas ou emblemas.
