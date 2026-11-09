# Progresso — OFFTEC HUB 2.0

## Estado atual

- Etapa atual: **6 — Integração do Codex CLI**.
- Etapa 1: concluída no checkpoint `39e2619`. Etapa 2: concluída e confirmada no commit imediatamente anterior ao início da Etapa 3.
- Não iniciar a etapa 2 até o checkpoint da etapa 1 estar confirmado.

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
