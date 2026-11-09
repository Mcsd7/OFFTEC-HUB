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
