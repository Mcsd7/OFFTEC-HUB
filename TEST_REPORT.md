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
