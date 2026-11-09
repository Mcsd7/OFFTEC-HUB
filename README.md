# OFFTEC HUB

Aplicativo Android com WebView e um backend FastAPI local no Termux. A API escuta apenas em `127.0.0.1:8765`; o frontend é empacotado como assets do APK e pode mostrar o assistente mesmo antes de o backend iniciar.

## Recursos implementados

- Dashboard com métricas do sistema, status real do Termux/backend, inventário de módulos e histórico SQLite.
- APK Lab ligado ao analisador estático do ReaDroid: upload por seletor Android, inspeção ZIP/DEX/SHA-256, Manifest/permissões, JADX/Apktool, visualização de arquivos gerados e exportação JSON.
- Dev Studio ligado às funções reais do OffTec PortAI: análise de projeto e motor de tradução. Propostas só são gravadas depois da seleção do usuário e em diretório fora do original. O provedor padrão do PortAI é `offline-review`; traduções só aparecem com um provedor real configurado.
- Security Lab chama o NetScope local para leitura de conexões/bytes quando disponível e faz consulta DNS pelo resolvedor do dispositivo.
- Terminal Center consulta pacotes e instala apenas nomes de uma lista fixa, depois de confirmação na interface. A API não recebe comandos shell.
- Monitor de CPU, núcleo, memória, armazenamento, processos visíveis, temperatura disponível e limitação do ambiente sem root.
- WebSocket autenticado para progresso e notificações.

## Integrações e limites conhecidos

ReaDroid e PortAI são adaptadores que reutilizam checkouts já existentes, configuráveis por `OFFTEC_READROID_PATH` e `OFFTEC_PORTAI_PATH` (padrão `~/ReaDroid` e `~/OffTec-PortAI`). NetScope é encontrado em `~/ferramentas/Netscop/netscope.py`. Em outro dispositivo, instale/configure cada projeto separadamente. Não há cópia automática de código ou clone silencioso.

Sysguard-ASM está desabilitado: no ambiente inspecionado há somente um executável ARM64, sem fonte/interface disponível para uma integração distribuível. AI Center é apresentado como não configurado: nenhum provedor de IA é chamado nesta versão. PortAI não promete conversão universal de projetos ou APKs.

Sem root, Android pode bloquear `/proc/net`, ocultar processos e não expor sensores térmicos. O painel mostra ausência de acesso, sem inventar números. JADX e Apktool são opcionais e precisam ser instalados no Termux.

## Primeira configuração no Android/Termux

1. Instale o Termux pela fonte oficial escolhida e mantenha Termux:API da mesma fonte. O APK não instala outro aplicativo silenciosamente.
2. Coloque este checkout em `~/HUB` no Termux.
3. Abra Termux > Settings e habilite `allow-external-apps`. Nas configurações Android do OFFTEC HUB, conceda **Run commands in Termux environment** quando solicitado.
4. No assistente do OFFTEC HUB, toque **Configurar no Termux**. O comando fixo chama `termux/install.sh`, cria um venv privado, instala as dependências Python, prepara o SQLite, inicia o backend em loopback e espera confirmação de `/api/v1/health`.
5. Se a chamada externa estiver desabilitada ou o Termux não estiver instalado, abra o Termux e siga o README. O servidor pode ser encerrado com `bash termux/stop.sh`.

O uso de `Termux:RUN_COMMAND` requer a permissão Android `com.termux.permission.RUN_COMMAND` e a opção `allow-external-apps`; veja a [documentação oficial do Termux](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent). A execução externa amplia o que o APK pode solicitar ao Termux. O app chama apenas o script fixo do instalador, não passa entrada da interface como comando.

Depois de configurado, ao abrir o app o WebView verifica `/api/v1/health` em `127.0.0.1:8765` e solicita ao Termux:RUN_COMMAND que execute o lançador privado do backend se ele estiver indisponível. Isso não exige uma sessão de terminal do Termux aberta; depende do Termux instalado, de `allow-external-apps`, da permissão RUN_COMMAND e da pasta `~/HUB` com o ambiente configurado. O Android ainda pode encerrar processos em segundo plano, por isso o app repete a verificação e permite iniciar novamente. Se a configuração inicial ainda não foi feita, use **Configurar no Termux** uma vez.

## Desenvolvimento e testes

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
python -m pytest -q
python -m backend
```

Documentação OpenAPI disponível em `http://127.0.0.1:8765/api/v1/docs`. O token local é criado em `backend/data/session.token` com permissão restrita. Dados de upload, sessões de tradução e SQLite ficam em `backend/data/`.

## Android

O host WebView fica em `android/`; ele serve HTML/CSS/JS a partir de `frontend/`, usa o seletor SAF para APKs e salva relatórios pelo seletor de destino do Android. Compile com um Android SDK e Gradle 8.10+:

```sh
gradle -p android :app:assembleDebug
```

No Termux, use o AAPT2 nativo em `android/aapt2` como override, pois o AAPT2 Linux distribuído pelo plugin não executa no Android:

```sh
gradle -p android :app:assembleDebug \\
  -Pandroid.aapt2FromMavenOverride="$PWD/android/aapt2"
```

O APK debug é assinado com chave de desenvolvimento. A compilação foi validada neste workspace; ainda falta instalar e exercitar o APK num dispositivo Android real antes de uma distribuição pública.
