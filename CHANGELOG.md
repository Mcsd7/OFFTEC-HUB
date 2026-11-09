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
