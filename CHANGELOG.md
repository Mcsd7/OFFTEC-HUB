# Changelog

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
