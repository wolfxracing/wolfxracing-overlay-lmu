# Como contribuir

Obrigado por querer melhorar o projeto! Este repositório é do **Le Mans Ultimate (LMU)**. O repositório irmão do outro jogo compartilha parte do código (o desenho das janelas); melhorias na base são bem-vindas nos dois.

## Antes de começar

- Procure nas [Issues](../../issues) se o assunto já existe.
- Para bug, abra uma Issue com: versão (`LMU 1.6.0 Sport`), o que esperava x o que aconteceu, passos, **o log** (`overlay/overlay_log_lmu.txt`) e, se possível, um print.
- Para ideia nova, descreva o problema que ela resolve antes da solução.

## Ambiente de desenvolvimento

```text
py -3.12 -m pip install PySide6-Essentials pillow numpy
overlay\executar_testes_lmu.bat          :: todos os testes
overlay\testar_demo_lmu.bat            :: ver as janelas com dados simulados
```

## Regras do projeto

1. **Os testes devem passar** (`executar_testes_lmu.bat`) e novos comportamentos precisam de teste.
2. **Nada inventado:** dado ausente = `None`/`--`. Calculado/estimado = marcar com `~` e documentar o método.
3. **Não inclua** logos ou marcas registradas (jogos, fabricantes, equipes), fontes comerciais, imagens/ícones de terceiros sem licença compatível, nem dados pessoais (config, logs, recordes, mapas, serial do Stream Deck).
4. **Não injete código no jogo** nem leia memória fora das APIs/memória compartilhada oficiais.
5. Textos de interface em **português do Brasil**; código e comentários em português (já é o padrão do projeto).
6. Atualize o `CHANGELOG.md` e a documentação afetada (`docs/`).
7. Mudanças visuais: anexe **antes/depois** (print no modo demo).

## Fluxo

1. Faça um *fork*, crie um branch (`feature/minha-ideia` ou `fix/meu-bug`).
2. Faça commits pequenos e descritivos.
3. Rode os testes e abra o **Pull Request** explicando o quê e por quê.
4. Ao mudar o dash: regenere o `.simhubdash` com `dash/tools/build_sport.py` (sem `--com-logos`) e anexe prints.

Ao contribuir, você concorda que sua contribuição seja licenciada sob a [MIT](LICENSE).
