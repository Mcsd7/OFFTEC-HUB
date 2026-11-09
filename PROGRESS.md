# Progresso — OFFTEC HUB 2.1

## Estado atual

- OFFTEC HUB 2.0, etapas 1–10: concluído no checkpoint `a02ad8f`. Esta continuação trata da correção da integração Codex e de um fallback nativo.
- Checkpoint 2.1 criado antes das alterações: `7e724b1694b0b08da4e87c95396724e22208a538`.
- Commits de implementação já salvos: `22758bf` (backend/fallback/testes) e `20c767a` (interface). Fechamento e artefato 2.1 seguem abaixo.

## Estado inicial do Git

- Branch: `main`, alinhada com `origin/main` no início da atividade.
- Commit de base: `b7e763c` (`Create OFFTEC HUB download site`).
- Os arquivos do OFFTEC HUB atual estavam quase todos não rastreados; o HEAD continha somente a versão anterior do site (`index.html`, `script.js`, `styles.css`).
- Existiam alterações/arquivos de projeto não rastreados antes do início. Foram preservados e serão incluídos no primeiro checkpoint após revisão, sem dados locais ou segredos.

## Backup

- Arquivo: `backup local privado`.
- Criado sem sobrescrever cópia anterior, fora do checkout, permissão `0600`; diretório de backups `0700`.
- Tamanho compactado: 298 MiB; inclui o checkout completo e `.git`, inclusive dados locais ignorados.
- O arquivo foi listado após a criação para confirmar que o tar é legível.

## Diagnóstico inicial

- Frontend: HTML/CSS/JS em `frontend/`; páginas Visão geral, APK Lab, Dev Studio, Programar com IA, Terminal Center, Security Lab, System Monitor, Módulos e Histórico. Chamadas ao backend são centralizadas em `/api/v1` e a UI recebe eventos por WebSocket.
- Backend: FastAPI em `backend/main.py`, SQLite para histórico; sessão local em `backend/data/session.token`; uploads e sessões de tradução sob `backend/data/`.
- Android/WebView: atividade Java empacota os assets, integra seletor SAF/exportação e solicita ao Termux scripts fixos para instalar/iniciar o backend.
- Integrações: adaptadores dinâmicos para ReaDroid e OffTec PortAI; NetScope carregado de checkout externo. JADX/Apktool dependem de executáveis no ambiente.
- IA existente: programação com IA e configuração básica de provedores existem; isso não demonstra ainda persistência/edição/remoção/teste de conexão completos nem chat universal.
- Sysguard-ASM: README informa que está desabilitado por falta de fonte/interface distribuível; a UI atual ainda contém uma página de monitor ligada ao inventário de módulos.
- Banco e uploads locais estão presentes no dispositivo e ignorados pelo Git. A política de exclusão está no `.gitignore`.
- Suíte existente: **13 passaram** (`python -m pytest -q`), com avisos de depreciação FastAPI/Starlette/asyncio.
- Integração real Android ainda requer instalação em aparelho; dependências externas/credenciais variam por ambiente.

## Concluído

- Inspeção inicial da estrutura e estado Git.
- Backup completo verificado.
- Diagnóstico e plano registrados nesta etapa.

## Resultado da auditoria de controles e contratos

- Os controles do frontend usam o despachante `data-action`; navegação, upload/exportação e ações dos módulos possuem rotas associadas no código revisado. A validação automatizada cobre fluxos selecionados, não todos os controles visuais.
- Não foi possível declarar todas as ações funcionais apenas pela inspeção: chamadas a ReaDroid/PortAI/NetScope e invocação de comandos dependem de ferramentas/checkouts do Termux; RUN_COMMAND e SAF precisam de aparelho.
- Limitações concretas já documentadas: Sysguard-ASM não está distribuível no estado atual; o centro de IA é atualmente programação assistida/configuração, não chat completo; provedores existentes não cobrem todo o ciclo pedido na etapa 2.
- Configurações de caminho no Dev Studio e execução de pacotes exigem atenção na auditoria específica de segurança e UX das etapas 7–9.

## Verificações de build

- `gradle -p android :app:assembleDebug -Pandroid.aapt2FromMavenOverride="$PWD/android/aapt2"`: **BUILD SUCCESSFUL** (31 tarefas, todas atualizadas).
- APK debug verificado em `android/app/build/outputs/apk/debug/app-debug.apk`.

## Fechamento da etapa 1

- Diagnóstico e plano registrados; backup verificado; testes Python e build debug aprovados.
- Nenhuma alteração funcional foi feita.
- Checkpoint Git criado: `chore: checkpoint etapa 1 diagnóstico e backup`.
- Hash confirmado no encerramento: consultar `git log -1` (branch `main`, árvore limpa).
- A Etapa 2 adiciona CRUD por ID, teste de conexão, validação de modelo/Base URL, migração de configuração legada e persistência atômica.
- Credenciais reais: nenhuma configuração presente no início do trabalho (confirmado pelo backup); portanto, teste de rede com credencial real não executado.
- Testes da Etapa 2: 16 passaram; JavaScript validado com `node --check`; Python validado com `py_compile`.
- Durante a primeira execução da suíte houve escrita indevida em `backend/data/ai-provider.json` por causa de monkeypatch incompleto no teste legado. O backup confirma que o arquivo não existia; o arquivo gerado pelo teste foi removido e o teste foi corrigido para injetar o caminho temporário nos dois módulos.
- Próxima atividade: Etapa 3 — registro de operações contextualizadas com schemas, allowlist e confirmação.

### Etapa 3 — concluída

- Registro central com descrições, schemas, permissões e requisito de confirmação.
- Operações reais registradas: métricas, inventário de módulos, análise de projeto via PortAI, inspeção do APK enviado via ReaDroid e criação confirmada de projeto vazio.
- Endpoint protegido publica o catálogo e valida/executa somente IDs registrados; não aceita comandos shell. Registra sucesso/rejeição/falha no histórico.
- 18 testes passaram, incluindo execução de métricas/módulos/análise e rejeição de parâmetros extras/operação desconhecida/confirmação ausente.
- Próximo: implementar plano/workspace isolado de reconstrução assistida; ferramenta ainda não é automaticamente chamada pelo chat, que será integrado na Etapa 5.

### Etapa 4 — concluída com limites declarados

- Resultados ReaDroid agora ficam em diretórios por upload; metadados reais da operação alimentam o plano IA.
- Criados endpoints de plano, aplicação e estado/cancelamento. O plano exige confirmação antes de copiar arquivos. Workspace isolado do APK original e da análise preservada.
- UI APK Lab mostra plano, limitações, arquivos e progresso. Build Gradle só roda com autorização explícita, `--offline` e timeout.
- Cancelamento é cooperativo: impede cópia/escrita no próximo ponto seguro, mas uma chamada HTTP já enviada ao provedor pode terminar antes do estado final.
- Fontes originais não são declaradas como recuperadas. Análises estáticas/DEX e bibliotecas nativas podem deixar workspace incompleto; build não é garantido.
- 19 testes passaram, incluindo fluxo com provedor mock, confirmação, cópia isolada e hash do APK original preservado.
- Próxima atividade: chat/histórico persistente e tool calling na aba OFFTEC AI.

### Etapa 5 — concluída com limites declarados

- Nova aba OFFTEC AI com criação/renomeação/exclusão confirmada de conversas e histórico persistido em SQLite.
- Gemini e APIs compatíveis usam tool calling nativo; ferramentas registradas de leitura executam no backend e seus resultados reais retornam à conversa. Escrita em projeto/criação de projeto pede confirmação e parâmetros ficam visíveis.
- Seleção de provedor/modelo configurado, teste de conexão, erros, progresso e cancelamento cooperativo. Respostas renderizam blocos de código com cópia.
- Sysguard-ASM removido da lista de módulos da UI; System Monitor continua exibindo métricas reais.
- Testes: 24 passaram, incluindo tool call real via registro com provedor mock, confirmação de escrita, persistência e cancelamento cooperativo.
- Limitações: streaming não implementado; cancelamento espera a chamada HTTP já enviada retornar antes de descartar resposta/evitar operações posteriores. Arquivos gerados por ferramenta são gravados no workspace de projeto e apresentados como resultado, sem gerenciador de anexos dedicado.
- Próxima atividade: detectar e encaminhar tarefas ao Codex CLI usando apenas sintaxe verificada localmente.

### Etapa 6 — integração implementada; uso real bloqueado pelo runtime local

- Adicionada tela Codex CLI, diagnóstico, teste de leitura e encaminhamento de tarefas a uma cópia temporária do projeto.
- Detecção executa `codex --version`, `codex --help` e `codex exec --help`; só habilita tarefa se reconhecer suporte JSONL e sandbox `workspace-write`.
- Execução usa lista fixa `codex exec --json --sandbox workspace-write PROMPT`, `cwd` restrito à cópia e confirmação explícita. Não usa `--yolo`, `--full-auto`, flags de aprovação automática, shell arbitrário nem altera o projeto original.
- Copia exclui VCS, builds, dependências pesadas e arquivos comuns de segredos. Registra resposta, eventos JSONL, erros e mudanças; logs privados ficam em modo 0600.
- OpenAI Docs confirma `codex exec`, progresso `--json`, sandbox e que `--full-auto` não deve mais ser usado: https://learn.chatgpt.com/docs/non-interactive-mode
- Testes: 28 passaram, incluindo detecção de features com help mockado, execução mockada em cópia, ausência de flags de bypass e exclusão de arquivos secretos.
- Bloqueio para validação real: `codex` está instalado, mas o wrapper Node falha ao iniciar (`_ZNSt6__ndk113__hash_memoryEPKvm`); versão, ajuda, autenticação e execução real não puderam ser confirmadas. O app reporta indisponível até runtime funcional. O botão de smoke test executará o teste real quando corrigido.
- Próxima atividade: auditoria funcional dos módulos e ligação contextual com as operações reais disponíveis.

### Etapa 7 — auditoria/correções principais concluídas

- ReaDroid: análise, resultados isolados por upload, Manifest/JADX/Apktool, inspeção, resultados e reconstrução assistida.
- PortAI: análise validada dentro de HOME/temporário; tradução revisável e destino externo permitido só em áreas autorizadas.
- NetScope e DNS: funções existentes e ferramentas de consulta contextual registradas; indisponibilidade externa é reportada sem fingir execução.
- APK Lab: todos os quatro modos apontam para o endpoint de operação; erros de carregamento do adaptador ReaDroid agora são tratados.
- Programar com IA: edição de projeto via ferramenta exige confirmação; testes reconhecidos estão disponíveis como operação confirmada na camada de ferramentas.
- System Monitor, terminal/pacotes, Security Lab e OFFTEC AI permanecem conectados a operações/rotas concretas; Sysguard removido da lista visível.
- Foram bloqueados paths fora do HOME/temporário na análise PortAI/tradução e destinos de tradução que cruzam ou substituem a origem.
- Testes: 29 passaram; `py_compile` em todos os módulos passou. Checkouts ReaDroid/PortAI/NetScope reais não estão instalados neste ambiente, então não houve execução de suas ferramentas externas reais.
- Próxima atividade: concluir estados visuais, responsividade, feedback de tarefas e cancelamento do Codex.

### Etapa 8 — concluída no ambiente disponível

- OFFTEC AI e Codex têm estado de execução, polling, mensagens de erro, cancelar, cartões de conversa/provedor e apresentação de código/resultados.
- Codex agora executa como tarefa cancelável; cancelar encerra o processo local e guarda status/resultado.
- APK assistido exibe plano, resultados disponíveis, limitações, progresso e cancelamento; operações longas do chat/AI/Codex não bloqueiam o ciclo principal do backend.
- Mapeamento estático frontend: 39 ações com `data-action`, nenhuma sem ramo correspondente no dispatcher.
- `tree-sitter-javascript` parseou `frontend/assets/js/app.js` sem erro. O Node CLI do Termux continua sem iniciar, portanto execução de JavaScript em navegador real não foi possível.
- Testes backend: 30 passaram; módulos Codex compilados. Build/instalação WebView real será feito na etapa 10.
- Limites restantes: respostas em streaming não estão habilitadas; Codex registra eventos JSONL ao concluir, com indicador de tarefa, sem renderizar cada evento ao vivo.
- Próxima atividade: hardened paths, dados locais, limites, concorrência e tratamento de segredos.

### Etapa 9 — segurança e desempenho concluída

- Diretórios de dados, uploads, traduções e workspaces recebem permissões privadas; token de sessão, banco, log e arquivos enviados/sessões de tradução recebem permissões restritas quando suportadas pelo sistema de arquivos.
- Execuções potencialmente pesadas do backend foram limitadas a uma por vez para reduzir pressão de memória no dispositivo.
- Programação assistida e execução de testes de projeto exigem confirmação explícita também no backend; os testes cobrem a recusa sem confirmação e o fluxo confirmado.
- Erros de tradução não incluem texto potencialmente sensível em logs/respostas.
- Verificações desta etapa: `python -m pytest -q` — 31 testes passaram; `git diff --check` — sem erros. Os testes Python foram executados antes do fechamento desta etapa; nenhuma nova suíte foi executada durante o encerramento seguro.
- Revisão do diff: somente nove arquivos da implementação/testes e este registro de progresso; sem arquivos de segredo ou dados locais incluídos.
- Checkpoint Git de segurança e desempenho criado junto com este registro; o hash final é confirmado pelo `git log -1`.
- Próxima atividade: Etapa 10 — auditoria final, testes finais e compilação do APK debug. Ainda não iniciada.


### Etapa 10 — testes finais e compilação concluída

- Auditoria final dos módulos e contratos: 40 ações declaradas no frontend; revisão do dispatcher, rotas API, adaptadores locais, autenticação e validação de caminhos. ReaDroid, PortAI e NetScope foram importados com sucesso; módulos locais detectados conforme o ambiente.
- Testes backend: `python -m pytest -q` — **31 passaram**, 53 avisos de depreciação.
- Todos os módulos Python passaram em `py_compile`; `frontend/assets/js/app.js` e `diagnostics.js` passaram no parser tree-sitter. `git diff --check` sem erros.
- Integração HTTP isolada em diretório temporário: health, bootstrap sob origem `appassets.androidplatform.net`, dashboard autenticado/CORS e preflight Private Network responderam 200. Não alterou o banco ou uploads locais.
- Provedores: cobertura automatizada com mocks aprovada. Configuração local existente foi preservada; suas 17 entradas usam modelo literal `test-model`, portanto não servem para validar credenciais/serviço real. Nenhuma chave foi exibida ou enviada.
- Codex: integração coberta por mocks; teste real indisponível porque o wrapper Node falha ao carregar símbolo nativo. Foi detectado material de autenticação, sem leitura ou exposição.
- Integrações ReaDroid/PortAI/NetScope foram importadas, mas não houve análise real de APK, projeto ou captura de rede; não foi fornecido artefato de teste e as permissões dependem do aparelho. Android/WebView não foi instalado em dispositivo.
- Build: `gradle -p android :app:assembleDebug -Pandroid.aapt2FromMavenOverride="$PWD/android/aapt2"` — **BUILD SUCCESSFUL**. APK validado como ZIP/APK com `AndroidManifest.xml`, `classes.dex` e assets.
- APK: `android/app/build/outputs/apk/debug/app-debug.apk`, 43.725 bytes, SHA-256 `e85e44626be09b3553d61cbabb97220a0d73b525113297342a36328076a061a2`.
- Backup existente e dados locais foram preservados. Nenhum arquivo de dados locais entrou no commit.
- Checkpoint final da Etapa 10: será informado pelo commit desta atualização.


## OFFTEC HUB 2.1 — Codex CLI e fallback

### Diagnóstico e causa

- `codex` no PATH é um link para `@mmmbuto/codex-cli-termux/bin/codex.js`, pacote `0.163.0-termux.2`; o binário interno reporta `codex-cli 0.163.0`. Plataforma observada: Termux ARM64, Android API 36; o `codex.bin` declara alvo `aarch64-linux-android` e API mínima 29.
- A causa do erro era o `LD_LIBRARY_PATH` herdado apontar para o `bin/` do pacote Codex. Essa pasta contém `libc++_shared.so` sem `std::__ndk1::__hash_memory(void const*, unsigned long)`, símbolo solicitado pelo Node 26.13.0. A libc++ do Termux contém o símbolo. `env -u LD_LIBRARY_PATH node --version` e `env -u LD_LIBRARY_PATH codex --version` funcionam; o wrapper Node, porém, recoloca seu caminho privado para processos filhos e uma tarefa real pelo shim ainda falhou com o mesmo erro.
- O comando `codex` do ambiente global e suas bibliotecas não foram modificados. O OFFTEC usa o launcher POSIX fornecido pelo pacote no caminho principal e invoca `codex.bin` diretamente no Codex Fallback.

### Implementação e execução

- Detecção consulta executável, versão, `--help`, `exec --help` e `login status`; status mostra autenticação, versão, métodos disponíveis e erro detalhado do shim de PATH.
- Integração principal: launcher Termux incluído no pacote; fallback independente: ELF `codex.bin`, com ambiente nativo configurado (`CODEX_SELF_EXE`, `LD_LIBRARY_PATH`). Seleção automática escolhe um método funcional/autenticado; erro de spawn principal pode tentar fallback antes de iniciar a tarefa; a interface também oferece retry explícito pelo fallback após falha.
- Execuções usam `exec --json --sandbox workspace-write -C <workspace> <prompt>`. Teste de conexão usa `--sandbox read-only --ephemeral`. Nenhum flag de bypass é usado.
- stdout JSONL, stderr, eventos, resposta, arquivos alterados e método são publicados no status da tarefa; buffers são limitados e valores semelhantes a credenciais são redigidos. Cancelar encerra o grupo de processos.
- Nenhuma instalação global, configuração Codex, segredo, dado local ou backup foi editado/removido. Arquivos gerados permanecem no workspace isolado e não substituem o projeto original.

### Validação 2.1

- Tarefas reais pelo launcher principal e pelo binário fallback criaram, respectivamente, `main-real.txt` (`MAIN_OK`) e `fallback-real.txt` (`FALLBACK_OK`) apenas nas cópias isoladas; ambos retornaram resposta e manifesto de arquivo.
- Uma tarefa real pelo endpoint `/api/v1/codex/run` completou pelo principal com status `success`, 9 eventos retornados, resposta e `api-real.txt` (`API_CODEX_OK`) no workspace temporário. O projeto de origem permaneceu intacto. Dados de API/task usados no smoke ficaram em diretório temporário e foram removidos.
- `python -m pytest -q`: **38 passaram**, 53 avisos de depreciação. Foco Codex: 12 passaram, incluindo detecção/versão/autenticação, dois launchers, retry pré-spawn, args/sandbox, cancelamento, erros/redaction, arquivos e segurança de paths.
- Python compilou, `node --check` passou usando `env -u LD_LIBRARY_PATH` (sem alterar o ambiente global), ações frontend mapeadas e `git diff --check` limpo.
- Build Android debug: **BUILD SUCCESSFUL**, override AAPT2 existente. APK: `android/app/build/outputs/apk/debug/app-debug.apk`, 44.770 bytes, SHA-256 `e8544011baaf3e9751e1a2fd79d0b6a27006a1552a6da309f26b778700399853`; ZIP/APK contém Manifest, DEX e a nova interface Codex.
- Em tarefas reais, Codex ainda emitiu avisos de duas entradas antigas `projects.*.approval_policy`/`sandbox_mode` em `~/.codex/config.toml`; não alterei essa configuração do usuário.
- Checkpoint pré-alteração e commits de backend/interface identificados acima; commit de fechamento registrado após esta atualização.

## Reformulação da experiência — auditoria e checkpoints

- Início sobre o checkpoint preservado `25b1764c15183e7d57ec48fe6a382a12d706906d`; árvore Git estava limpa (`main`, ahead 14 de origin).
- Backup novo integral e verificado: `backup local privado` (312.401.642 bytes, modo `0600`, SHA-256 `[hash omitido]`). Inclui checkout, `.git`, dados ignorados e estado local; o backup anterior não foi alterado.
- Inventário arquitetural: frontend single-page em `frontend/assets/js/app.js`; API FastAPI em `backend/main.py`; credenciais globais no `backend/providers.py`; histórico comum em SQLite (`backend/database/store.py`); integração Codex isolada em `backend/codex_cli.py`/`services/codex_tasks.py`; seletor Android SAF em `MainActivity.java`.
- Achados: provedores já têm CRUD e chave protegida, mas a configuração está embutida em Programar com IA; lista de modelos é validada/testada, não oferecida como catálogo selecionável; OFFTEC AI é chat persistente porém ocupa formulário; Codex é um formulário, aparece duplicado dentro de OFFTEC AI, exige path digitado e não tem conversas Codex persistentes. Dev Studio oferece select de projeto mas também caminho manual; APK usa seletor de arquivo WebView; DNS e tradução ainda pedem valores técnicos.
- Nenhuma configuração local foi lida/exibida ou editada durante o inventário; dados locais e chave existentes permanecem intactos.
- Etapas seguintes serão divididas em arquitetura/backend compartilhado, experiência/interface com chats separados e verificação/build. Ver detalhes em `IMPLEMENTATION_PLAN.md`.

### Fase A — serviços compartilhados e backend (implementada)

- OpenRouter foi adicionado ao provedor global existente; Gemini/Groq/OpenAI/OpenRouter e endpoints OpenAI-compatible/custom usam o mesmo armazenamento protegido. Há consulta de modelos da chave temporária antes do cadastro e atualização de modelos para provedores salvos; respostas e logs de erro não retornam credenciais.
- A tradução PortAI agora usa a API global cadastrada quando disponível. Sem IA global, mantém o provider offline existente. A pasta de tradução pode ser criada automaticamente, com identificador único e proteção contra sobrescrita.
- Histórico de conversas Codex usa tabelas SQLite próprias, independente do CHAT IA. Conversas sem projeto executam Codex CLI real com sandbox somente leitura; projeto selecionado exige confirmação e a cópia isolada pode continuar como contexto entre turnos.
- Adicionada aplicação de alterações do workspace ao projeto original somente após confirmação. O backend verifica conflitos contra o baseline, bloqueia caminhos/symlinks/arquivos secretos, guarda cópias dos arquivos substituídos e desfaz gravações parciais se houver falha.
- Corrigido workspace vazio do Codex com commit Git base permitido sem arquivos.
- Testes de backend após esta fase: **45 passaram**; compilação Python e JavaScript, `node --check` com `LD_LIBRARY_PATH` removido e `git diff --check` passaram. O catálogo visual de projetos detecta tipo e mantém o workspace HUB selecionável.
- Testes reais do novo fluxo Codex: pergunta via API sem projeto concluída com resposta persistida; tarefa Codex em projeto temporário criou arquivo no workspace isolado e manteve a origem intacta. Os mecanismos main/fallback e seus testes reais anteriores permanecem no checkpoint 2.1.

### Fase B — telas e seleção visual (implementada)

- Navegação agora separa `Configuração de IA`, `Chat IA` e `Codex CLI`. O painel antigo que embutia Codex dentro do chat de API foi removido.
- Configuração global oferece CRUD/teste, seleção de modelo pela API ou opção personalizada e URL Base automática para endpoints conhecidos. Programar com IA apenas reutiliza o provedor padrão; não pede uma segunda chave.
- CHAT IA ocupa uma área de conversa dedicada, mantém histórico existente, permite nova conversa/renomear/excluir, seleciona provedores/modelos cadastrados e pode cancelar geração. A geração API permanece sem streaming incremental.
- Codex agora tem interface de conversa própria com histórico SQLite, projeto visual opcional, modo sem projeto, seletor principal/fallback, status/autenticação, retry fallback, cancelamento, saída real e manifesto. Projetos são executados em cópias; ação separada e confirmada aplica mudanças após verificar baseline e salvar backups.
- Caminhos manuais removidos de Codex, Dev Studio, Programar com IA e destino de tradução; traduções escolhem destino automaticamente. O seletor Android SAF existente continua selecionando APK.
- Auditoria estática encontrou 46 ações no dispatcher sem ação ausente; o seletor visual apresenta projetos de `~/Projects` e o workspace `~/HUB`, com tipo detectado. Somente arquivos/pastas nas raízes autorizadas aparecem.
- Limites para validação final: não há WebView Android/adb disponível para teste visual instalado; não foi feita consulta a API de modelo real porque a configuração local não comprova chave/modelo utilizável. Catálogo real, conexão e traduções têm cobertura mockada.

### Fase C — verificação final e APK (concluída)

- Suíte completa: `python -m pytest -q` — **46 passaram**, 61 avisos de depreciação existentes de FastAPI/Starlette/asyncio. Inclui APIs, provedores/modelos, segredo não retornado, persistência dos dois históricos, seleção de projeto, paths, chat sem projeto, cópia Codex, confirmação/backup/conflito de aplicação, tradução global, arquivos APK e regressões estáticas da UI.
- Todos os módulos backend passaram em `py_compile`; `env -u LD_LIBRARY_PATH node --check frontend/assets/js/app.js` e `git diff --check` passaram.
- Smoke real Codex pela rota API, sem projeto: status `success`, método `main`, duas mensagens persistidas e resposta do CLI.
- Smoke real Codex em projeto temporário: tarefa escreveu `result.txt` contendo `REAL_CODEX_CHAT_TASK_OK` na cópia; origem permaneceu intacta. Main/Fallback real previamente testados no checkpoint 2.1; nesta alteração, o chat persistente usa o mesmo seletor de método e o fallback tem cobertura automatizada.
- Provedores externos via API: catálogo/conexão/chat/tradução cobertos por mocks; não executada chamada real porque não há combinação de credencial/modelo comprovadamente utilizável. Nenhuma chave foi lida ou exposta nesta etapa.
- Build debug: `gradle -p android :app:assembleDebug -Pandroid.aapt2FromMavenOverride="$PWD/android/aapt2"` — **BUILD SUCCESSFUL**, 31 tarefas, 3 executadas e 28 atualizadas. APK verificado por `unzip -t` e presença de Manifest/DEX/assets.
- APK: `android/app/build/outputs/apk/debug/app-debug.apk`, 48.161 bytes, SHA-256 `5858606ac9e98d2ca81b6f39225edba04cc1db0bae64d839b6d5f95a2a760c8d`.
- Backup integral da reforma preservado em `backup local privado` (SHA-256 `[hash omitido]`); backup 2.0 anterior inalterado.
- Commits de implementação: `061fdf734a8dea9d2574645de364488a23937b38` (backend) e `eefbaed1ee1d0e59732695a51bbb51478f6cf180` (interface). Hash do commit final será o HEAD do fechamento dos relatórios.
- ADB/aparelho Android não estão disponíveis neste ambiente; validação touch/SAF/WebView instalado permanece pendente. Catálogo visual limitado a projetos de primeiro nível em `~/Projects` e `~/HUB`; não foi adicionado seletor SAF genérico de pastas.
