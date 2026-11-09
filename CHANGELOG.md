# Changelog

## 2026-11-09 — OFFTEC HUB 2.2 · serviços compartilhados

- OpenRouter e catálogo de modelos API foram integrados ao serviço global de provedores existente; configuração salva permanece no arquivo protegido e a chave não é retornada.
- PortAI tradução compartilha a API global, com provider offline preservado quando não há configuração. Destino automático exclusivo evita sobrescrever a origem.
- Adicionado histórico SQLite independente para chat Codex real, incluindo modo sem projeto, contexto recente e continuidade no workspace selecionado.
- Adicionada aplicação confirmada de alterações Codex, com backup privado, validação de paths e bloqueio de conflito contra arquivos modificados desde a cópia.
- Corrigida execução do Codex em workspace vazio com commit Git-base vazio.
- Testes da fase: 45 passaram; seleção visual classifica projetos autorizados e inclui o workspace do HUB. Tarefa Codex real sem projeto e tarefa real em projeto temporário foram executadas.

## 2026-11-09 — OFFTEC HUB 2.2 · experiência e chats separados

- Navegação separa Configuração de IA, Chat IA por API e Codex CLI real; Codex deixou de ser um formulário embutido no chat convencional.
- Chat API e Codex exibem conversas, histórico, envio/cancelamento e mensagens de execução. Codex seleciona projeto visualmente ou pode responder sem projeto em modo somente leitura.
- Codex mostra método/versão/autenticação, eventos/saída/arquivos e permite tentar o fallback; aplicar projeto exige confirmação, salva backups e recusa conflitos.
- Removidos campos manuais de path no Dev Studio, Programar com IA, Codex e destino de tradução; o seletor APK Android existente foi mantido.
- 46 ações frontend mapeadas para handlers; WebView Android visual permanece sem teste em aparelho.

## 2026-11-09 — OFFTEC HUB 2.2 · validação final

- `python -m pytest -q`: 46 testes passaram; `py_compile`, `node --check` e `git diff --check` passaram.
- CHAT IA real por API e tarefa Codex em projeto temporário foram executados; configuração externa de IA não teve chamada real por falta de par credencial/modelo validado.
- APK debug compilado pelo Gradle com override AAPT2 e verificado por integridade ZIP e presença de Manifest, DEX e assets.
- APK `android/app/build/outputs/apk/debug/app-debug.apk`: 48.161 bytes; SHA-256 `5858606ac9e98d2ca81b6f39225edba04cc1db0bae64d839b6d5f95a2a760c8d`.
- Backup integral e backup anterior preservados. Nenhum APK instalado em aparelho porque ADB/dispositivo não estavam disponíveis.

## 2026-11-09 — Etapa 1

- Criado backup completo com nome único fora do checkout e acesso restrito.
- Registrados o plano de implementação, estado Git inicial e diagnóstico de arquitetura em `IMPLEMENTATION_PLAN.md` e `PROGRESS.md`.
- Testes existentes executados: 13 passaram.
- Build Android debug confirmado com o override AAPT2 local.
- Nenhuma alteração funcional nesta etapa.
- Checkpoint Git da etapa 1 criado em `main`.

## 2026-11-09 — Etapa 2

- Adicionado CRUD seguro e persistente para provedores, seleção padrão e migração do formato anterior.
- Adicionado teste real de catálogo/modelo para confirmar autenticação e existência do modelo.
- API nunca retorna API Key; erros de autenticação/modelo são claros e não incluem corpos de resposta do provedor.
- Frontend permite adicionar, editar, testar, selecionar padrão e remover.
- Testes: 16 passaram; `node --check` e `py_compile` passaram. Sem credenciais presentes para teste real externo.

## 2026-11-09 — Etapa 3

- Criado registro central de operações IA com schemas estritos, allowlist, permissões e confirmação em escrita.
- Adicionados endpoints de catálogo e execução autenticados, com resultados reais e histórico.
- Testes: 18 passaram; compilação Python passou.

## 2026-11-09 — Etapa 4

- Resultados ReaDroid isolados por upload e fluxo IA de plano, confirmação e workspace separado.
- Adicionados estado/cancelamento cooperativo e opção de build Gradle offline com consentimento separado.
- Testes: 19 passaram; compilação Python passou.

## 2026-11-09 — Etapa 5

- Adicionada aba OFFTEC AI com histórico SQLite, seleção/teste de provedores, chat e tool calling real.
- Ações de escrita aguardam confirmação; geração tem status e cancelamento cooperativo.
- Removido Sysguard-ASM do inventário visível e mantido System Monitor local.
- Testes: 24 passaram; Python compilou. Streaming permanece pendente.

## 2026-11-09 — Etapa 6

- Criada integração Codex CLI com detecção por versão/ajuda, cópia de projeto isolada, comando fixo JSONL e registro de resultados.
- Confirmação antes da execução; exclusão de arquivos comuns de segredo e de caches/builds; nenhum modo de aprovação automática.
- 28 testes passaram. O runtime Codex local não inicia por falha de símbolo nativo Node; teste real permanece indisponível.

## 2026-11-09 — Etapa 7

- Auditoria de endpoints e controles; paths de análise/tradução agora são limitados e saídas não podem atingir a origem.
- Ferramentas contextuais incluem DNS, NetScope, Manifest e testes de projeto com confirmação.
- Falhas de adaptador ReaDroid são tratadas. 29 testes passaram.

## 2026-11-09 — Etapa 8

- Adicionados polling, feedback, cancelamento de processo Codex, chat com cancelamento e UI das tarefas.
- Validado que as ações `data-action` mapeiam para handlers; JavaScript passou no parser tree-sitter.
- 30 testes passaram. Teste visual em dispositivo continua pendente.


## 2026-11-09 — Etapa 10

- Auditoria final dos módulos, ações frontend, APIs, comunicação CORS/WebView e validação de caminhos.
- Smoke HTTP isolado confirmou health, bootstrap, dashboard autenticado e preflight Private Network.
- 31 testes passaram; Python compilou; JavaScript passou no parser tree-sitter.
- Build debug Android concluído com o override AAPT2 local. APK gerado e validado em `android/app/build/outputs/apk/debug/app-debug.apk` (43.725 bytes; SHA-256 `e85e44626be09b3553d61cbabb97220a0d73b525113297342a36328076a061a2`).
- Limites: sem credenciais de provedor/modelo real utilizáveis; Codex CLI bloqueado pelo runtime Node; análise real ReaDroid/PortAI/NetScope e instalação Android dependem de fixture/aparelho.
- Configuração local de provedores, dados locais e backup foram preservados; não foram incluídos no commit.


## 2026-11-09 — OFFTEC HUB 2.1 · Codex CLI + Codex Fallback

- Diagnóstico identificou `LD_LIBRARY_PATH` apontando para a libc++ privada do pacote Codex, que não contém o símbolo exigido pelo Node; o wrapper PATH também reintroduz esse caminho para processos filhos. Não foi alterada a instalação global.
- Integração principal usa o launcher Termux POSIX do pacote. Novo Codex Fallback inicia o ELF `codex.bin` diretamente, com `CODEX_SELF_EXE` e bibliotecas do pacote. Ambos completaram tarefas reais.
- OFFTEC AI mostra versão, autenticação, método ativo, saúde/erro dos launchers, seleção automática/principal/fallback, teste real read-only, progresso JSONL, resposta, arquivos e cancelamento. Falhas oferecem nova tentativa pelo fallback.
- Proteções: cópia isolada, validação de projeto existente, sandbox de escrita/read-only, sessão efêmera para smoke test, timeout, cancelamento em grupo e redação de credenciais.
- 38 testes passaram (12 focados em Codex). Tarefas reais main/fallback e execução API real passaram.
- Build debug concluído com override AAPT2. APK: `android/app/build/outputs/apk/debug/app-debug.apk` (44.770 bytes; SHA-256 `e8544011baaf3e9751e1a2fd79d0b6a27006a1552a6da309f26b778700399853`).
- Warnings de chaves `approval_policy`/`sandbox_mode` antigas em `~/.codex/config.toml` permanecem sem alteração.
