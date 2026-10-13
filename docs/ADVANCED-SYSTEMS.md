# Sistemas avançados — arquitetura e auditoria

## Componentes reutilizados

- `core/generator.py`, `core/utils.py` e `words.py`: geração existente, aleatoriedade do sistema, normalização e dicionários de verbos em inglês, português e espanhol.
- `platforms/` e `core/platform_base.py`: registro das 18 plataformas, formatos, credenciais, intervalos e consultas existentes.
- `core/session.py`, `core/worker.py`, `core/server.py`: execução fora da interface, cancelamento, eventos e API local autenticada.
- `core/preferences.py` e `core/config.py`: gravação atômica e diretório de dados por usuário.
- `ui/app.js`, `styles.css`, `themes.css`, `i18n.js`, `translations.js`: navegação, componentes, nove escolhas de aparência e sete idiomas.
- `tests/`: regressões Python e JavaScript, com HTTP simulado nos testes e sem credenciais reais.

## Contratos e decisões

Os módulos novos usam apenas a biblioteca padrão e `requests`, já existente. `advanced_generator` compila padrões e filtra candidatos localmente; `identity` adapta os verificadores existentes para estados explícitos; `storage` mantém sessões, eventos idempotentes, histórico, favoritos e presets em SQLite. `features` coordena tarefas e expõe contratos para a API local, sem dependências circulares.

Estados: AVAILABLE, TAKEN, UNKNOWN, RATE_LIMITED, AUTH_REQUIRED, ERROR, UNSUPPORTED. Ausência de perfil não confirma cadastro. A nova consulta não contorna bloqueios nem troca proxies. Credenciais permanecem apenas em memória. Consultas simultâneas à mesma plataforma são espaçadas; execução antiga e Identity Checker não iniciam consultas ao mesmo tempo.

Analytics não grava tokens, proxies nem nomes nos eventos. Nomes são mantidos somente no histórico necessário do Identity Checker e nos favoritos. UUIDs identificam sessões; chaves de evento evitam duplicações. SQLite usa WAL, transações, chave estrangeira e migrações versionadas. Sessões interrompidas pelo encerramento são recuperadas como interrupted. Falhas de persistência são expostas, sem fingir salvamento; banco corrompido é preservado em arquivo de recuperação.

Estatísticas novas começam na instalação desta versão: arquivos antigos de nomes não são convertidos em verificações, porque não contêm evidência ou identificadores de sessão.

## Referências de semântica

[GitHub Get a user](https://docs.github.com/en/rest/users/users#get-a-user) e [Twitch Get Users](https://dev.twitch.tv/docs/api/reference#get-users) consultam usuários; não garantem que nomes ausentes possam ser cadastrados. [Roblox Accounts](https://create.roblox.com/docs/cloud/reference/features/accounts) documenta o endpoint de validação utilizado pelo aplicativo.


## Gramática do gerador

| Token | Regra |
|---|---|
| `?` | Letra ASCII aleatória, respeitando os grupos habilitados |
| `L`, `U` | Letra minúscula ou maiúscula, respectivamente |
| `#` | Um dígito de 0 a 9 |
| `C`, `V` | Consoante ou vogal ASCII minúscula |
| `word`, `{word}` | Um verbo do dicionário existente, no idioma escolhido, sem acentos |
| `prefix`, `{prefix}` | Um dos prefixos configurados |
| `suffix`, `{suffix}` | Um dos sufixos configurados |
| `+` | Separador de concatenação, não emite caracteres |
| `\` + caractere | Caractere literal; por exemplo `\L` emite L |

Palavras reservadas sem chaves devem terminar antes de um caractere não alfabético ou no fim do padrão. Use chaves para concatenar uma palavra com letras literais: `{word}dev`. L, U, C e V são sempre tokens quando não escapados. Letras e outros caracteres não reservados são literais; também devem estar no conjunto permitido. Padrões podem ter até 128 caracteres. Prefixos e sufixos só entram quando seu token está presente. Listas são separadas por vírgula, ponto e vírgula ou nova linha.

O conjunto padrão contém letras ASCII, números e underscore. Os controles de grupos continuam valendo quando um conjunto personalizado é informado. Outros símbolos imprimíveis ASCII precisam ser explicitamente incluídos em Caracteres permitidos. Caracteres proibidos são sempre removidos. Dicionários usam inglês, português ou espanhol; são os idiomas de palavras já disponíveis no aplicativo, independentemente dos sete idiomas da interface.

Repetições de caracteres adjacentes, blocos repetidos, palavras proibidas e sequências numéricas ascendentes/descendentes de pelo menos três dígitos são filtros separados. O filtro pronunciável exige alternância de vogais e consoantes nas letras; é uma heurística ASCII, sem promessa de naturalidade em todos os idiomas.

Presets: Minimal=`LLLL`; Short Names=`LL#`; Aesthetic=`word_###`; Gaming=`prefix+word+##` com neo/epic/nova; Numeric=`######` com limite de seis dígitos; Dictionary=`word`; Pronounceable=`CVCVCV`; Custom começa nas regras padrão. Os internos podem ser carregados/restaurados e salvos como cópias editáveis. Presets do usuário podem ser criados, renomeados, atualizados e excluídos.

Geração percorre índices sem materializar todas as combinações. Candidatos únicos são mantidos até o limite solicitado (10.000 nomes). Tentativas são limitadas a 1.000.000 e configuráveis. Quando o espaço é pequeno (até 20.000 combinações), a estimativa enumera candidatos para calcular o total distinto aceito. Para grandes espaços simples de largura fixa, o cálculo é exato; com restrições complexas, mostra um limite superior identificado como tal. A sessão informa espaço esgotado, limite de tentativas ou cancelamento; nunca completa artificialmente uma lista com nomes inválidos.

## Uso integrado

1. Abra Advanced Generator, carregue um preset e ajuste as regras.
2. Gere a prévia local. Copie, favorite ou exporte como TXT.
3. Selecione de 1 a 100 nomes e envie para o Identity Checker.
4. Escolha as plataformas, informe credenciais quando necessárias e inicie.
5. Filtre a matriz por texto/status; veja detalhes, sugestões ainda não verificadas, links oficiais e progresso. Sugestões automáticas são opcionais e respeitam o mesmo espaçamento.
6. Exporte resultados em CSV/JSON, com opção de manter só AVAILABLE. Histórico mantém os identificadores de sessão e permite reverificar.
7. Analytics mostra os dados reais das operações novas, incluindo sessões do gerador/verificador antigos. Filtros de período e plataforma afetam métricas, gráficos e exportação. Histórico pesquisável mostra até 200 sessões; CSV exporta os eventos do período.

## Métricas e dados

AVAILABLE e TAKEN entram no denominador da taxa de disponibilidade. UNKNOWN, RATE_LIMITED, AUTH_REQUIRED e UNSUPPORTED são inconclusivos para o gráfico de distribuição, com estados separados na matriz. ERROR conta falhas técnicas e de rede. Formatos rejeitados localmente não contam como verificação HTTP. Novas consultas unificadas são medidas por username/plataforma, uma vez, mesmo com retry; tentativas HTTP extras não duplicam eventos.

Velocidade geral é verificações tentadas divididas pela soma das durações das sessões de consulta; sessões concorrentes de geração local ficam fora desse denominador. Tempo total soma durações de todos os tipos de sessão. Por plataforma, velocidade usa o tempo acumulado das consultas, incluindo esperas, e taxa conclusiva é (AVAILABLE+TAKEN)/verificados. Nomes sugeridos verificados entram no Analytics, mas ficam fora do indicador principal de consistência. O período considera eventos pela hora em que foram registrados; durações são limitadas ao início do filtro.

SQLite `activity.sqlite3` fica no diretório de dados por usuário, junto das preferências existentes. Schema versionado: v1 cria tabelas; v2 preserva o username original em resultados para repetir consultas sem duplicações causadas por normalização. Arquivos corrompidos são preservados com sufixo de recuperação. Versão desconhecida ou erro de acesso não causa sobrescrita; a UI informa a falha. Favoritos, presets e histórico são locais; credenciais não são armazenadas. CSV protege células que poderiam ser interpretadas como fórmulas por planilhas.

## Limitações externas

- PlayStation permanece no módulo antigo, mas no Identity Checker recebe UNSUPPORTED: o endpoint experimental não oferece confirmação suficientemente explícita.
- GitHub, Twitch, Instagram, TikTok, YouTube, Telegram, Steam, GitLab, Bluesky, X, Kick, Minecraft, Chess.com e Lichess consultam identidades/perfis. Ausência permanece UNKNOWN; reserva, bloqueio e cadastro exigem confirmação do próprio serviço.
- Recusa de cadastro sem confirmação de conta existente permanece UNKNOWN. HTTP 400, páginas inesperadas e falhas técnicas nunca geram AVAILABLE.
- Twitch, Steam, X e Kick precisam de credenciais autorizadas. Algumas outras APIs têm chaves opcionais. Acesso, planos e cotas dependem dos serviços.
- Timeout configurável limita as requisições em curso; cancelamento impede novas requisições e interrompe esperas, mas um socket já em uso pode aguardar seu timeout antes de encerrar.
- Retry respeita a espera informada pelo servidor. Esperas acima de 30 segundos são mostradas como RATE_LIMITED e mantidas no controle local de cooldown, sem bloquear a fila por horas. Não há CAPTCHA bypass, rotação de IP ou contorno de restrições no módulo novo.
- Dados antigos em Names não são importados como fatos de Analytics. Gerações e verificações anteriores a esta versão não possuem eventos verificáveis.
- Não há validação de todas as 18 APIs em contas/redes externas, nem publicação remota automática sem repositório configurado.

## Arquivos desta implementação

Criados: `core/advanced_generator.py`, `core/identity.py`, `core/storage.py`, `core/features.py`, `ui/features.js`, `ui/features-model.js`, `ui/features.css`, `tests/test_advanced_systems.py`, `tests/test_features.cjs`, este documento.

Modificados: `app.py`, `core/server.py`, `core/session.py`, `core/worker.py`, `core/config.py`, `ui/index.html`, `ui/app.js`, `ui/translations.js`, `tests/test_preferences.py`, `.gitignore`, `.github/workflows/build-windows.yml`, `README.md`, `PUBLISHING.md`, `VALIDATION.md`.

O intervalo entre usernames das configurações existentes também é aplicado ao Identity Checker, sempre preservando a pausa mínima da plataforma. Esperas configuradas pelo usuário são canceláveis e não são classificadas como limite da API. Nomes de presets personalizados são conteúdo do usuário e permanecem literais ao trocar o idioma.

Exportações por Blob são habilitadas na janela desktop por ALLOW_DOWNLOADS. O renderer Windows abre o diálogo de salvar; links oficiais target=_blank são enviados ao navegador externo. Referência: [Downloads do pywebview](https://pywebview.flowrl.com/examples/downloads).
