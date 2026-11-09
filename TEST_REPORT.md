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
