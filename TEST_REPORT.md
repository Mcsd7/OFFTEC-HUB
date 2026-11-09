# Relatório de testes

## Etapa 1 — Base do projeto

### Automatizados

- Comando: `python -m pytest -q`
- Resultado: **13 passed**, 27 avisos em 9,81 s.
- Avisos: `on_event` do FastAPI e APIs deprecadas do Starlette/asyncio. Não houve falha.

### Backup

- Arquivo compactado criado em `backup local privado` com modo `0600`.
- `tar -tzf` listou o conteúdo até os arquivos de referência Git sem erro.

### Android

- Comando: `gradle -p android :app:assembleDebug -Pandroid.aapt2FromMavenOverride="$PWD/android/aapt2"`
- Resultado: **BUILD SUCCESSFUL**, 31 tarefas atualizadas.
- APK confirmado: `android/app/build/outputs/apk/debug/app-debug.apk`.

### Validação manual ainda necessária

- Abrir/instalar no dispositivo Android, verificar o seletor SAF e a exportação.
- Confirmar permissões Termux:RUN_COMMAND e inicialização do backend no dispositivo.
- Integrações dependentes de checkouts externos e provedores ainda não foram exercitadas nesta auditoria inicial.

## Etapa 2 — Provedores de IA

- `python -m pytest -q`: **16 passed**, 33 avisos de depreciação (sem falhas). Cobertura inclui CRUD, persistência/permissões, preservação de chave ao editar, catálogo de modelos com mock, autenticação negada, modelo inexistente e Base URL insegura.
- `node --check frontend/assets/js/app.js`: não executado com sucesso; o binário Node do Termux não inicia (`cannot locate symbol _ZNSt6__ndk113__hash_memoryEPKvm`).
- `python -m py_compile backend/providers.py backend/ai_coding.py backend/main.py backend/models.py`: passou.
- Teste real com credencial: não executado; não havia configuração de provedor no backup inicial.
- Sem arquivo de configuração de provedor no estado final do teste; dados da Etapa 1 preservados.

## Etapa 3 — Operações IA

- `python -m pytest -q`: **18 passed**, 35 avisos de depreciação.
- Cobertura nova: catálogo do registro, chamadas reais de métricas/módulos/análise de projeto, schemas sem parâmetros adicionais, operação não registrada e confirmação obrigatória para criação de projeto.
- `python -m py_compile backend/tool_registry.py backend/main.py backend/models.py`: passou.

## Etapa 4 — ReaDroid assistido

- `python -m pytest -q`: **19 passed**, 39 avisos de depreciação.
- Teste mock percorre upload, análise ReaDroid, plano, rejeição sem confirmação e aplicação em cópia; SHA-256 do APK original permanece igual.
- `py_compile` dos módulos de rebuild, tarefas e rotas: passou.
- Não foi possível validar JADX/Apktool/compilação de APK real nesta máquina; checkouts externos/credenciais reais indisponíveis.
- Limite: cancelamento cooperativo não interrompe imediatamente uma chamada HTTP em andamento ao provedor.

## Etapa 5 — OFFTEC AI

- `python -m pytest -q`: **24 passed**, 48 avisos de depreciação.
- Cobertura: conversas, mensagens persistidas, rename/delete com confirmação, tool call adaptado a OpenAI, execução real de `modules.list` no fluxo de chat, escrita protegida por confirmação e cancelamento cooperativo.
- `py_compile`: backend alterado passou.
- Node está instalado, mas falha ao iniciar por símbolo nativo ausente. Esprima disponível no ambiente não entende optional chaining/nullish coalescing já usados pelo frontend; validação sintática JS ainda não disponível.
- Streaming e dispositivo Android não testados nesta etapa.

## Etapa 6 — Codex CLI

- `python -m pytest -q`: **28 passed**, 51 avisos de depreciação.
- `py_compile backend/codex_cli.py backend/main.py backend/models.py`: passou.
- Testes mockados cobrem descoberta de flags/versão, cópia isolada e exclusão de `.env`/chaves; tarefa mock confirma argv fixo sem `--yolo` ou `--full-auto`.
- Teste real: bloqueado. Executável detectado, mas `codex --version` e `codex --help` falham porque Node não carrega símbolo C++ nativo. Autenticação só pode ser confirmada executando uma tarefa real; permanece sem validação.
- Sintaxe baseada em OpenAI Docs: `codex exec --json --sandbox workspace-write <prompt>`; implementação ainda exige que a ajuda da instalação confirme esses parâmetros antes de habilitar execução.

## Etapa 7 — integração dos módulos

- `python -m pytest -q`: **29 passed**, 51 avisos de depreciação.
- `python -m py_compile backend/*.py backend/core/*.py backend/database/*.py backend/modules/*.py backend/services/*.py`: passou.
- Testes incluem DNS real `localhost`, allowlist/schema de operações e rejeição de diretórios e saídas inseguras.
- ReaDroid, PortAI e NetScope dependem de checkouts externos ausentes neste ambiente e permanecem sem validação funcional real.

## Etapa 8 — Interface/tarefas

- `python -m pytest -q`: **30 passed**, 53 avisos.
- `tree-sitter-javascript` analisou `frontend/assets/js/app.js`: sem erro sintático.
- Script de inventário encontrou 39 ações `data-action` e zero ações sem handler.
- Node não executa por símbolo nativo ausente; WebView/dispositivo real não disponível.
- Codex e chat têm polling/cancelamento, com eventos JSONL Codex apresentados somente no resultado final, não em streaming.


## Etapa 10 — auditoria final e APK debug

### Testes executados

- `python -m pytest -q`: **31 passed**, 53 avisos de depreciação (FastAPI/Starlette/asyncio), sem falhas. Abrange API/backend, provedores com mocks, persistência e histórico, tool calling, fluxo de reconstrução/ReaDroid com mocks, OFFTEC AI, Codex com mocks, segurança e paths.
- `python -m py_compile $(rg --files backend -g '*.py' | sort)`: passou para todos os módulos Python.
- Parser tree-sitter JavaScript: `frontend/assets/js/app.js` e `frontend/assets/js/diagnostics.js` sem erro sintático.
- Auditoria estática: controles `data-action`, dispatcher, rotas de API/WebSocket e ponte WebView/Termux revisados; `git diff --check` passou.
- Smoke test HTTP real em processo isolado com `OFFTEC_HUB_DATA` temporário: `/health`, bootstrap da origem `https://appassets.androidplatform.net`, `/dashboard` com token e CORS, preflight Private Network — respostas 200. O diretório temporário foi encerrado/removido; dados locais existentes não foram utilizados.
- Adaptadores locais: import de ReaDroid, PortAI e NetScope passou; inventário reportou ReaDroid/PortAI prontos, NetScope disponível somente para leitura e System Monitor pronto. Import não equivale a análise funcional real.

### Limitações de validação real

- Provedores: testes automatizados usam mocks. A configuração local foi preservada, mas possui 17 registros repetidos com o modelo `test-model`; nenhuma chamada externa real foi feita, pois essa configuração não comprova credencial/modelo utilizável. Nenhuma chave foi revelada.
- Codex CLI: teste real bloqueado pelo wrapper Node instalado, que falha ao iniciar com símbolo C++ nativo ausente (`_ZNSt6__ndk113__hash_memoryEPKvm`). Os fluxos com Codex foram testados com mocks.
- ReaDroid e PortAI: testes de API do projeto usam adaptadores simulados; não foi realizada análise real de APK nem projeto. NetScope foi importado, mas não foi executada leitura real de conexões. Não havia fixture definida para essas operações e o acesso Android a `/proc/net` pode ser restrito.
- Android: o APK compilou, mas não foi instalado nem aberto em dispositivo; SAF, Termux:RUN_COMMAND e WebView em Chromium real permanecem pendentes de dispositivo. O smoke HTTP valida o contrato de origem/CORS com o backend, não a execução da ponte dentro do Android.

### Compilação e artefato

- Comando: `gradle -p android :app:assembleDebug -Pandroid.aapt2FromMavenOverride="$PWD/android/aapt2"`.
- Resultado: **BUILD SUCCESSFUL**, 31 tarefas (3 executadas, 28 atualizadas).
- APK confirmado e legível como ZIP/APK, contendo Manifest, DEX e assets: `android/app/build/outputs/apk/debug/app-debug.apk`.
- Tamanho: 43.725 bytes. SHA-256: `e85e44626be09b3553d61cbabb97220a0d73b525113297342a36328076a061a2`.


## OFFTEC HUB 2.1 — Codex CLI e Codex Fallback

### Diagnóstico comprovado

- `command -v codex`: `/data/data/com.termux/files/usr/bin/codex`, link para `@mmmbuto/codex-cli-termux/bin/codex.js`, versão de pacote `0.163.0-termux.2`; Node `v26.13.0`. Plataforma Termux `arm64-v8a`, Android API 36; `codex.bin` é ELF AArch64 para Android API 29+.
- Com o ambiente original, `codex --version` e `codex --help` falhavam ao carregar Node com símbolo `_ZNSt6__ndk113__hash_memoryEPKvm` ausente. `LD_LIBRARY_PATH` continha o `bin/` do pacote Codex. A biblioteca nesse diretório não exporta o símbolo; `/data/data/com.termux/files/usr/lib/libc++_shared.so` exporta. Com `LD_LIBRARY_PATH` removido, Node e comandos de help/status passam.
- O teste real do shim Node com esse caminho removido ainda falhou ao iniciar subprocesso durante uma tarefa, pois o wrapper injeta novamente o diretório privado para filhos. O launcher POSIX distribuído pelo pacote e o ELF direto foram usados nos métodos do app. Nenhuma alteração foi feita à instalação global.

### Testes executados

- `python -m pytest -q`: **38 passed**, 53 avisos de depreciação já conhecidos (FastAPI/Starlette/asyncio).
- `python -m pytest -q tests/test_api.py -k 'codex_'`: **12 passed**. Cobertura: descoberta do shim e dos launchers Termux, versão e features reais/falsas, status positivo e negativo de autenticação, método principal, fallback nativo, retry apenas se Popen principal falhar antes da execução, sandbox `read-only`/`workspace-write`, `--ephemeral`, JSONL, stderr, exit code, redaction, cancelamento, confirmação, retorno de arquivos e cópia isolada.
- Tarefa real pelo launcher principal: **success**; criou `main-real.txt` contendo `MAIN_OK` na cópia e retornou resposta/eventos/manifestações.
- Tarefa real pelo binário nativo fallback: **success**; criou `fallback-real.txt` contendo `FALLBACK_OK` na cópia e retornou resposta/eventos/manifestações.
- Teste real via API `/api/v1/codex/run`: **success**, método `main`, 9 eventos observados, resposta real e `api-real.txt` contendo `API_CODEX_OK` no workspace. A origem não foi alterada. O banco/dados desta validação estavam em tempdir.
- Execuções de escrita usaram `--sandbox workspace-write`; teste de conexão usa `--sandbox read-only --ephemeral`. Nenhum `--yolo`, `--full-auto`, `--approve-for-me` ou `--dangerously-bypass-*` é incluído.
- `python -m py_compile` de todos os módulos backend: passou. `env -u LD_LIBRARY_PATH node --check` nos dois arquivos JS: passou. Inventário estático: 42 ações frontend, sem handler ausente. `git diff --check`: passou.
- Build debug: `gradle -p android :app:assembleDebug -Pandroid.aapt2FromMavenOverride="$PWD/android/aapt2"` — **BUILD SUCCESSFUL**, 31 tarefas (3 executadas, 28 atualizadas). APK contém Manifest, DEX e novo painel Codex/Fallback.

### Arquivos e segurança

- Alterações só são executadas na cópia isolada sob `backend/data/codex_workspaces/<run_id>`; o original não é sobrescrito. Retorno inclui resposta, eventos, status, erros redigidos e lista dos arquivos modificados.
- Processo usa grupo próprio, timeout de 900 segundos e cancelamento por SIGTERM/SIGKILL do grupo. Saída JSONL/stderr tem limite e redação de padrões de credenciais.
- A configuração Codex contém duas entradas de projeto antigas não reconhecidas (`approval_policy` e `sandbox_mode`); aparecem como avisos na execução. Foram preservadas sem alterações.
- Não foi feita instalação nem upgrade do Node/Codex global. O comando `codex` lançado diretamente do shell ainda falha enquanto herdar o `LD_LIBRARY_PATH` problemático; a integração OFFTEC usa o launcher nativo funcional e informa a falha detalhada do shim PATH.
- Teste em WebView/Android instalado não executado; build e assets do APK foram verificados.

### APK

- Caminho: `android/app/build/outputs/apk/debug/app-debug.apk`.
- Tamanho: 44.770 bytes. SHA-256: `e8544011baaf3e9751e1a2fd79d0b6a27006a1552a6da309f26b778700399853`.


## OFFTEC HUB 2.2 — experiência unificada, CHAT IA e Codex CLI

### Backup e estado preservado

- Backup completo criado antes das alterações, sem sobrescrever o backup 2.0/2.1: `backup local privado`.
- Tamanho: 312.401.642 bytes; modo `0600`; SHA-256 `[hash omitido]`. O arquivo foi listado com `tar -tzf`.
- O trabalho partiu do commit `25b1764c15183e7d57ec48fe6a382a12d706906d`, sem alterações na configuração/API Key local nem nos artefatos anteriores.

### Serviços/backend

- Provedores cobertos: Gemini, Groq, OpenAI, OpenRouter e OpenAI-compatible/custom. Cobertura usa chaves fictícias em `tmp_path` e `urlopen` mockado; validou consulta de modelos, default, API Key ausente das respostas e reutilização do armazenamento central.
- PortAI tradução: teste mock comprovou uso do `providers.chat` central; sem configuração global o provider offline preservado continua disponível. Destino automático cria pasta exclusiva; aplicação é bloqueada se o destino já existir. O arquivo de origem permanece intacto nos testes.
- Histórico: conversa Chat IA segue no histórico SQLite anterior; conversas Codex usam tabelas próprias, persistem mensagens/contexto e não compartilham conversas entre si.
- Seleção visual: teste API cobre projeto Android, workspace genérico e `~/HUB`; nenhuma operação exige path digitado nas telas atualizadas. Path é validado no backend e não devolvido em detalhes da conversa Codex.
- Codex: workspace sem arquivos agora inicializa com baseline Git vazio. Execução continua em cópia isolada; aplicar arquivo ao original exige `confirmed=true`, valida baseline/conflictos, ignora caminhos inseguros/segredos/deleções e mantém backup privado para arquivos substituídos. Teste cobre confirmação, alteração, backup e conflito após modificação concorrente.

### Interface e integração

- Navegação separa Configuração de IA, Chat IA e Codex CLI. Não existe chamada do painel Codex dentro do chat da API.
- Chat IA mantém histórico, troca provedor/modelo global, cria/renomeia/exclui conversas, exibe loading/erro e permite cancelar. Resposta incremental via streaming não foi implementada; API de chat retorna resposta após a conclusão.
- Codex tem chat independente, histórico, escolha opcional de projeto, pergunta sem projeto em sandbox somente leitura, seleção main/fallback, diagnóstico de versão/autenticação, progresso/cancelamento, resposta e manifesto de arquivos. Projeto usa cópia isolada; alterações ao original só são aplicadas após confirmação.
- Campos manuais de projeto removidos em Codex, Dev Studio e Programar com IA; destino de tradução é automático. Android SAF/WebView existente continua usando seletor nativo de APK.
- Inventário estático: 46 ações `data-action`, todas associadas a handler; `node --check` passou com `LD_LIBRARY_PATH` removido. A árvore da UI foi atualizada sem biblioteca visual externa.

### Testes executados nesta reforma

- `python -m py_compile $(rg --files backend -g '*.py' | sort)`: passou.
- `env -u LD_LIBRARY_PATH node --check frontend/assets/js/app.js`: passou.
- `git diff --check`: passou.
- `python -m pytest -q`: **46 passed**, 61 avisos de depreciação de FastAPI/Starlette/asyncio, sem falhas.
- Teste real Codex, sem projeto, via `POST /api/v1/codex/chat`: `success`, método `main`, conversa com duas mensagens e resposta do CLI persistida. O teste usou diretório de dados temporário.
- Teste real Codex, projeto temporário: o CLI criou `result.txt` com marcador esperado dentro do workspace e a origem permaneceu intacta. Workspace e dados temporários foram removidos ao fim do smoke.
- A execução real anterior de main e fallback Codex permanece registrada na seção 2.1. Nesta reforma, o novo chat encaminha o método selecionado ao mesmo executor; seleção/retry têm cobertura automatizada, mas não foi repetido um smoke real pelo fallback dentro do novo chat.
- Provedor de IA externo: **não executado com rede/credencial real**. Não havia um par chave/modelo demonstravelmente válido para uma chamada autorizada nesta rodada; testes de catálogo, conversa, API compartilhada e tradução foram mockados. Nenhuma credencial foi lida, enviada ou exibida nos testes desta reforma.

### Compilação e limites do dispositivo

- Build: `gradle -p android :app:assembleDebug -Pandroid.aapt2FromMavenOverride="$PWD/android/aapt2"` — **BUILD SUCCESSFUL**, 31 tarefas (3 executadas, 28 atualizadas).
- APK verificado com `unzip -t`; contém `AndroidManifest.xml`, `classes.dex`, `assets/assets/js/app.js` e `assets/assets/css/app.css`.
- Caminho: `android/app/build/outputs/apk/debug/app-debug.apk`.
- Tamanho: 48.161 bytes. SHA-256: `5858606ac9e98d2ca81b6f39225edba04cc1db0bae64d839b6d5f95a2a760c8d`.
- Nenhum `adb`/aparelho Android estava disponível; instalação, toque, acessibilidade e execução real do SAF/WebView continuam pendentes. O navegador de projetos lista raízes autorizadas `~/Projects` (nível imediato) e `~/HUB`; um navegador SAF genérico de pastas não foi criado. Se uma API não implementar tool calling ou saída JSON estruturada, a UI/backend informa para selecionar um modelo compatível.
- Chat IA não faz streaming; Codex retorna eventos/saída por polling durante a execução, não é um terminal interativo persistente. A continuidade é feita por histórico e cópias de workspace entre turnos.

### Commits de implementação

- Backend/serviços: `061fdf734a8dea9d2574645de364488a23937b38`.
- Interface/experiência: `eefbaed1ee1d0e59732695a51bbb51478f6cf180`.
- Commit de relatórios e estado final: consultar o HEAD da branch `main` após este fechamento.
