# OFFTEC HUB 2.0 — Plano de implementação

O trabalho será feito em etapas sequenciais. Cada etapa termina com testes, atualização deste plano e dos relatórios, checkpoint Git confirmado e só então o início da etapa seguinte.

| Etapa | Escopo | Evidência de conclusão |
|---|---|---|
| 1. Diagnóstico, backup e estabilização | Inventariar frontend, FastAPI, WebView/Termux, dados, integrações externas, scripts, endpoints e controles; preservar o estado atual. | Backup verificável, diagnóstico documentado, testes de base e commit. |
| 2. Provedores de IA | Cadastro persistente e seguro, edição/substituição/remoção, provedor padrão e teste real de conexão Gemini/Groq/OpenAI/compatíveis. | Testes com mocks e, se houver credenciais, conexão real documentada. |
| 3. Assistência IA e operações | Registro central de ferramentas, schemas, permissões, confirmação e execução backend validada. | Operações reais cobertas por testes. |
| 4. ReaDroid assistido | Análise preservada, workspace isolado, plano confirmado, alterações e validação/compilação possível. | Fluxo completo com cópias de teste e falhas explícitas. |
| 5. OFFTEC AI | Substituir navegação Sysguard-ASM por chat persistente, contexto, provedores, cancelamento e ferramentas. | Conversas e tool calling reais cobertos por testes. |
| 6. Codex CLI | Detectar instalação/versão/autenticação/capacidades; encaminhar tarefas em workspace restrito usando sintaxe instalada. | Teste real quando ambiente e autenticação permitirem; limites registrados. |
| 7. Integração das ferramentas | Auditoria individual de ReaDroid, PortAI, NetScope, APK Lab, tradução, segurança, pacotes e programação. | Matriz de ações UI/API e testes por módulo. |
| 8. Interface e experiência | Navegação, estados, progresso, erros, responsividade e remoção de controles sem ação. | Verificação da interface e fluxos no ambiente disponível. |
| 9. Segurança e desempenho | Sessão, validação, caminhos, allowlists, isolamento, limites, cancelamento e concorrência em dispositivo modesto. | Testes de segurança e limites registrados. |
| 10. Testes finais e compilação | Auditoria consolidada, testes automatizados, build debug Android e instruções de instalação. | APK em `android/app/build/outputs/apk/debug/app-debug.apk`, relatório final e commit. |

## Decisões técnicas iniciais

- Manter o backend FastAPI local em loopback e o frontend empacotado no WebView enquanto a auditoria não demonstrar necessidade de mudança.
- Não versionar `backend/data/`, tokens, bancos locais, uploads, builds ou propriedades locais Android. O backup privado preserva o estado completo do checkout.
- Reutilizar ReaDroid, OffTec PortAI e NetScope por seus adaptadores existentes; verificar disponibilidade e contratos antes de ampliar cada integração.
- Não iniciar etapas futuras até confirmar o commit da etapa corrente.

## Dependências externas a confirmar

- Checkouts ReaDroid e OffTec PortAI e script NetScope configuráveis no Termux.
- JADX e Apktool instalados para descompilação avançada.
- Credenciais/modelos dos provedores para chamadas reais.
- Codex CLI autenticado para teste real na etapa 6.
- Android SDK/Gradle e dispositivo Android para validação de instalação, WebView e Termux:RUN_COMMAND.

## Reformulação da experiência OFFTEC HUB 2.2

Base preservada: commit `25b1764c15183e7d57ec48fe6a382a12d706906d`. Backup integral externo e verificado no caminho indicado em `PROGRESS.md`.

| Fase | Entrega | Verificação |
|---|---|---|
| A. Serviços compartilhados | Consolidar o acesso às configurações de IA já existentes sem migrar/remover credenciais; expandir provedores (OpenRouter/custom OpenAI-compatible); catálogo de modelos e seleção padrão; APIs seguras para projetos autorizados e arquivos/workspaces. | Testes de CRUD legado, modelos, credenciais ocultas, catálogo autenticado e validação de paths. |
| B. Fluxos de conversa | Manter CHAT IA com a API global e histórico próprio; dar ao Codex chat completo, independente, persistente e baseado em execuções reais do Codex CLI; contextos podem começar sem projeto e projetos são escolhidos por lista. | Cobertura mockada separada por chat e teste real Codex somente se CLI autenticado/funcional. |
| C. Interface e seleção | Aba exclusiva Configuração de IA; CHAT IA em página própria; Codex em chat separado; atalhos de projetos/arquivos e eliminação progressiva de campos path duplicados; estados loading/erro/cancelamento. | Auditoria dos controles e fluxos no frontend, parser JS e build Android. |
| D. Integração de ferramentas | Reutilizar o serviço global nas funções inteligentes compatíveis, com degradação explícita para integrações externas que tenham configuração/contrato próprio. | Matriz ferramenta → backend → dependências; não inferir sucesso por renderização/import. |
| E. Fechamento | Executar suítes, smokes isolados, build APK, atualizar os três relatórios e commit por fase. | `pytest`, validação JS/Python, Gradle com override AAPT2, `git status` limpo e hash/artefato. |

Limite de segurança: o Codex nunca recebe automaticamente modos de bypass; escrita permanece confirmada e isolada em cópia. Um projeto ausente dá acesso de conversa somente leitura a um workspace vazio. Nenhuma chamada via API global substitui o Codex real.
