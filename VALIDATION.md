# Validação da v7.5

**41 testes locais passaram: 34 em Python e 7 em JavaScript.**

A entrega inclui testes de isolamento dos dados por usuário, gravação em pastas novas, separação entre recursos e dados no executável, preservação dos 13 serviços e seis modos, preferências atômicas, idioma, intervalos, batch, cancelamento, progresso e busca com erros de escrita.

As integrações externas usam simulação nos testes, sem chaves reais. A disponibilidade real em cada serviço não foi validada de ponta a ponta. O executável é compilado para Windows x64; não foi validado em uma máquina limpa de outra pessoa. A captura de tela da janela nativa teve falhas na ferramenta de automação durante a entrega anterior; não há validação manual completa de arrastar e redimensionar. A interface e o F11 foram conferidos no navegador na v7.4.

O workflow do GitHub só pode ser confirmado depois de executar no novo repositório. Nenhuma publicação remota foi feita nesta preparação.

Primeira abertura sem configurações prévias conferida no navegador: escolha de idioma, criação de preferências na nova pasta e caminho de resultados sem nome da conta.

## Atualização v7.5.1

Seletor de idioma personalizado na primeira abertura e nas configurações. Verificação visual e por teclado no navegador; sintaxe JavaScript conferida. Os 41 testes locais foram executados novamente após adicionar a persistência da barra lateral e passaram.

Barra lateral recolhível e persistente, navegação com rolagem, logos locais e controles vetoriais alinhados adicionados à v7.5.1.

No navegador: seleção por teclado, salvamento e reabertura do idioma, menus escuro/claro, recolher/reabrir a barra e persistência após recarregar, rolagem até Bluesky e logos das 13 plataformas. Os controles nativos foram redesenhados com SVGs de mesmo tamanho e alinhamento central; a captura da janela nativa ainda não foi validada nesta atualização.

## Atualização v7.6

49 testes locais passaram (42 Python + 7 JavaScript), incluindo modo direto com proxies antigos, modo de proxy opcional, 18 plataformas, respostas rigorosas das novas APIs, recusa de credenciais e esperas de Retry-After. Consultas reais por conexão direta retornaram perfis conhecidos de Minecraft, Chess.com e Lichess, e ausência explícita para nomes de exemplo nas três. Lichess teve falha transitória de conexão na primeira consulta de ausência e respondeu na segunda tentativa. X e Kick foram validados com respostas simuladas e documentação oficial; nenhum token real foi fornecido. Não há garantia de acesso irrestrito em todos os serviços ou validação completa das 18 plataformas na rede de outros usuários.

A implementação final das três novas consultas públicas também foi executada diretamente com HTTP Session sem proxies de ambiente: perfil existente e ausência explícita classificados corretamente em Minecraft, Chess.com e Lichess. No app, Minecraft concluiu dois nomes de teste com progresso de 100%, zero erros e resultado salvo. UI conferida com 18 plataformas, seis modos, proxies desativados por padrão e campo de token obrigatório para X.

## Atualização v7.7

Galeria de aparência com miniaturas: claro, escuro, céu estrelado, Dracula, Nord, Catppuccin Mocha, Tokyo Night, Rosé Pine e seguir o sistema. Prévia instantânea e persistência usam o fluxo existente de preferências atômicas. Céu desenhado em canvas local, com limite de densidade, resolução e quadros; animação interrompida com a janela oculta e movimento reduzido respeitado. Opção de manter o céu estático. Novos textos disponíveis nos sete idiomas.

Galeria e aparência do céu inspecionadas visualmente no navegador. As capturas acompanham a entrega. A suíte de testes da v7.6 não foi executada novamente nesta atualização. A compilação do executável Windows é feita com PyInstaller; a limitação anterior de validação da janela nativa continua aplicável.


## Atualização v8.0 — sistemas avançados

106 testes passaram: 96 Python e 10 JavaScript. Incluem a suíte anterior, os nove temas e a preferência de animação, além de 57 testes novos no total. Foram verificadas gramática, regras, limites, unicidade, estimativas, esgotamento, cancelamento, contadores, denominadores, filtros, UUIDs, SQLite, migração de schema, recuperação de sessões interrompidas, corrupção preservada, schema futuro não sobrescrito, escrita concorrente, exportação, favoritos, presets, autenticação local, URLs seguras, HTTP inesperado, timeout, cooldown, sugestões automáticas e integração dos três sistemas.

Comando local: `python -m unittest discover -s tests -q`, com USERNAMEGEN_DATA_DIR apontando para uma pasta temporária do workspace. JavaScript: `node --test --test-isolation=none tests/test_i18n.cjs tests/test_search.cjs tests/test_features.cjs`. A execução inicial do runner Node com processos separados recebeu EPERM do ambiente; o mesmo conjunto passou sem isolamento em subprocessos. O workflow GitHub executa os três arquivos diretamente com Node.

APIs simuladas aparecem apenas nos testes automatizados. Na interface real, geração local de seis nomes, seleção e envio para Minecraft concluíram seis consultas: cinco perfis existentes (TAKEN) e uma ausência explícita (UNKNOWN), sem erros. Roblox confirmou builderman ocupado. Kick sem credenciais recebeu AUTH_REQUIRED, e PlayStation recebeu UNSUPPORTED sem chamar o endpoint experimental. Analytics mostrou sete verificações HTTP efetivamente tentadas, seis ocupados e três estados sem confirmação, sem nomes falsamente classificados como AVAILABLE. CSV exportou 11 eventos reais com UUIDs de sessão; JSON confirmou os mesmos dados. Essa conferência não valida as outras APIs em contas de terceiros.

UI: navegação nas três páginas, filtros por status, envio de seleção, preset salvo, favorito salvo e troca para espanhol conferidos no navegador. Após reiniciar o processo, o histórico de consultas continuou disponível. Screenshots da entrega usam operações reais na pasta temporária de QA, que não acompanha o código público. Gráficos têm interação por clique/teclado, estados vazios e cores dos temas. A inspeção visual no navegador não substitui validação da janela nativa em outro computador; essa limitação continua aplicável.

O executável Windows x64 é compilado com PyInstaller, e o código público exclui banco de dados, preferências, proxies, logs, favoritos e dados de QA. Detalhes, contratos, arquivos e limitações estão em docs/ADVANCED-SYSTEMS.md. Nenhuma publicação remota no GitHub foi feita.

Revisão da inicialização nativa: downloads habilitados em pywebview.settings e links externos abertos no navegador. Teste de inicialização com backend simulado confirmou as duas opções. A gravação pelo diálogo de download nativo ainda depende de conferência manual na janela Windows.

## Atualização v8.1

Inspeção visual no navegador: monograma vetorial no onboarding, barra de título e sidebar; creeper no painel Minecraft; seletor de idioma e botão lateral sem rotação. A escolha de tela cheia foi salva automaticamente em startup_mode e permaneceu na reabertura das configurações. O desktop lê essa preferência antes de criar a janela, passando fullscreen ao pywebview e sincronizando o estado inicial dos controles. A primeira abertura em tela cheia na janela nativa ainda não foi conferida manualmente. Os testes automatizados da v8.0 não foram executados novamente nesta revisão.

Ícone PNG e ICO foram reexportados da mesma geometria sem depender de fontes instaladas. Carregamento usa pulsação de opacidade e respeita movimento reduzido. Executável Windows x64 compilado novamente; código público mantém dados pessoais fora da distribuição.

## Atualização v8.2

Nome visível padronizado como UIsername no título, barra superior, marca lateral e boas-vindas nos sete idiomas. Fonte Segoe UI Bold restaurada para o u., com posicionamento calculado pelas dimensões visíveis dos glifos. PNG e ICO reexportados da mesma fonte, mantendo centralização. Onboarding conferido visualmente no navegador. Executável recompilado; suíte automatizada não executada novamente nesta revisão.
