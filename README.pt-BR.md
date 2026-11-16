# Pipeline e CLI de Coleta de Dados de League of Legends

CLI interativa e pipeline automatizado, resiliente e em conformidade com os limites de taxa da Riot Games, projetado para coletar datasets de partidas de League of Legends com filtros configuraveis de regioes, elos, filas e regras de partida utilizando a API oficial da Riot Games para pesquisa academica (Iniciacao Cientifica) e aplicacoes de Machine Learning.

[English Version (README.md)](README.md)

---

## 1. Visao Geral

O pipeline extrai estatisticas detalhadas de partidas e participantes, normalizando a resposta bruta da API da Riot em um dataset tabular estruturado contendo **108 variaveis por participante** (ate 10 linhas por partida).

### Principais Funcionalidades
- **CLI Interativa e Assistente de Filtros Pre-Requisicao:** Permite selecionar regioes, elos, divisoes, filas, janelas de tempo, duracao das partidas, exclusao de rendicoes, campeoes, rotas, lado do mapa e modo de descoberta antes de enviar qualquer requisicao para a API.
- **Cobertura Completa de Elos e Multi-Regiao:** Colhe sementes de jogadores tanto nos elos de topo (`CHALLENGER`, `GRANDMASTER`, `MASTER`) quanto nos elos padrao (`DIAMOND` ate `IRON`, divisoes `I` a `IV`), com suporte a coleta em uma ou multiplas plataformas (`BR1,KR,NA1,EUW1`, etc.).
- **Conformidade com Limite de Taxa:** Limitador Token Bucket com janela deslizante gerenciando os limites de curto prazo (20 req/1s) e longo prazo (100 req/120s) da Riot com margem preventiva de 10%, alem de backoff reativo para respostas HTTP 429 (`Retry-After`).
- **Modos de Diversidade de Jogadores:** Escolha entre descoberta em grafo por busca em largura (enfileirando os participantes das partidas) ou coleta restrita apenas aos jogadores dos elos selecionados (`--no-discover`).
- **Checkpointing e Deduplicacao:** Persistencia atomica de estado (`data/state_<platform>.json`), evitando consultas duplicadas e permitindo pausar e retomar sem perda de progresso.
- **Armazenamento Duplo e Filtragem Offline:** Gravacao sincronizada em Apache Parquet (compressao Snappy) e CSV, alem do subcomando `filter` para filtrar e exportar datasets ja coletados.

---

## 2. Estrutura de Diretorios

```
ml-lol/
├── .context/
│   ├── 01-spec.md               # Especificacoes funcionais e schema das 108 variaveis
│   ├── 02-plan.md               # Arquitetura do sistema e responsabilidade dos modulos
│   └── 03-tasks.md              # Checklist de tarefas de engenharia e verificacao
├── .env                         # Configuracao local com a chave da Riot (ignorado pelo git)
├── .env.example                 # Modelo de variaveis de ambiente
├── .gitignore                   # Regras de exclusao de versionamento
├── README.md                    # Documentacao principal (Ingles)
├── README.pt-BR.md              # Documentacao principal (Portugues)
├── requirements.txt             # Dependencias Python
├── pyproject.toml               # Metadados do pacote Python
├── data/
│   ├── README.md                # Dicionario de dados e codebook (Ingles)
│   ├── README.pt-BR.md          # Dicionario de dados e codebook (Portugues)
│   ├── ranked_matches.parquet   # Dataset colunar comprimido
│   ├── ranked_matches.csv       # Dataset em formato tabular CSV
│   └── state_br1.json           # Arquivo de checkpoint e controle de estado
├── src/
│   ├── main.py                  # Ponto de entrada CLI (interactive, collect, filter, export, status)
│   ├── cli/
│   │   └── interactive.py       # Menus interativos, assistente de filtros e resumo pre-execucao
│   ├── config/settings.py       # Configuracao e validacao de ambiente com Pydantic
│   ├── core/
│   │   ├── rate_limiter.py      # Limitador de taxa Token Bucket
│   │   ├── http_client.py       # Cliente HTTP resiliente com retries e backoff
│   │   └── exceptions.py        # Classes de excecao do dominio
│   ├── riot/
│   │   ├── routing.py           # Mapeamento de plataforma para cluster regional
│   │   ├── league_api.py        # Coletor de sementes da League-v4 (Apex e Standard tiers)
│   │   └── match_api.py         # Coletor de partidas e detalhes da Match-v5
│   ├── models/
│   │   ├── api_models.py        # Modelos Pydantic da resposta bruta da API
│   │   ├── dataset_models.py    # Modelo formal do schema de 108 features
│   │   └── filter_models.py     # Schemas CollectionFilterConfig e DatasetFilterConfig
│   └── pipeline/
│       ├── normalizer.py        # Motor de extracao de features e filtragem de partidas
│       ├── state_manager.py     # Gerenciador de checkpoints e deduplicacao
│       ├── storage.py           # Gravador atomico em Parquet/CSV e exportador filtrado
│       └── orchestrator.py      # Orquestrador de coleta para uma ou multiplas regioes
└── tests/                       # Suite de testes unitarios e de integracao
```

---

## 3. Instalacao e Configuracao

### Requisitos
- Python 3.11 ou superior
- Chave valida da Riot Games API ([Riot Developer Portal](https://developer.riotgames.com/))

### Passos
1. Clone o repositorio e navegue ate o diretorio raiz:
   ```bash
   git clone <url_do_repositorio>
   cd ml-lol
   ```

2. Crie e ative o ambiente virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Instale as dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure as variaveis de ambiente:
   ```bash
   cp .env.example .env
   ```
   Edite o arquivo `.env` e insira sua chave da Riot:
   ```env
   RIOT_API_KEY=RGAPI-sua-chave-aqui
   DEFAULT_PLATFORM=BR1
   DEFAULT_REGION=americas
   TARGET_QUEUE_ID=420
   ```

---

## 4. Como Executar

### 4.1 Modo CLI Interativo (Recomendado)

Execute o script sem argumentos (ou usando `interactive` / `collect -i`) para abrir o menu interativo e o assistente passo a passo de filtros. Nenhuma requisicao a API da Riot e disparada antes de voce revisar o resumo e confirmar:

```bash
# Abrir o menu principal interativo
python3 src/main.py

# Ou ir direto para o assistente de configuracao de filtros
python3 src/main.py collect -i
```

### 4.2 Coleta Direta por Flags de Linha de Comando

Voce tambem pode passar todos os filtros diretamente via terminal (ideal para automacao ou execucao em segundo plano com `-y` para pular a confirmacao):

```bash
# Coleta multi-regiao (Brasil + Coreia), Diamante+, ultimos 7 dias, sem rendicoes
python3 src/main.py collect -p BR1,KR --tiers CHALLENGER,GRANDMASTER,MASTER,DIAMOND --divisions I --days-back 7 --exclude-surrenders --hours 8.0 -y

# Coletar 200 partidas com campeoes especificos no patch 14.4
python3 src/main.py collect -p BR1 --patch 14.4 --champions Ahri,LeeSin --positions MIDDLE,JUNGLE -n 200 -y

# Modo estrito: consultar apenas jogadores Challenger sem descobrir outros participantes
python3 src/main.py collect -p BR1 --only-challenger --no-discover --dataset-name challenger_estrito -y

# Execucao em segundo plano no Linux
nohup python3 src/main.py collect --hours 8.0 -y > crawler.log 2>&1 &
```

#### Opcoes de Filtro do Subcomando `collect`

| Flag | Descricao | Padrao |
| :--- | :--- | :--- |
| `-i, --interactive` | Abre o assistente interativo de filtros antes de iniciar | `False` |
| `-p, --platform` | Plataforma(s) separadas por virgula (ex: `BR1`, `BR1,KR,NA1`) | `BR1` |
| `-r, --region` | Roteamento regional manual para plataforma unica (`americas`, `europe`, `asia`, `sea`) | Automatico |
| `--tiers` | Elos separados por virgula (`CHALLENGER` ate `IRON`) | `CHALLENGER,GRANDMASTER,MASTER` |
| `--divisions` | Divisoes para elos padrao (`I,II,III,IV`) | `I` |
| `--max-pages` | Maximo de paginas por divisao para elos padrao (`1`-`20`) | `1` |
| `-q, --queue` | ID da fila (`420`: Solo/Duo, `440`: Flex, `400`: Normal, `450`: ARAM, `0`: Todas) | `420` |
| `--match-type` | Tipo de partida (`ranked`, `normal`, `tourney`, `tutorial`, `all`) | Automatico |
| `--days-back` | Coletar apenas partidas dos ultimos N dias | Nenhum |
| `--start-time` / `--end-time` | Limites de tempo em timestamp epoch (segundos) | Nenhum |
| `--min-duration` / `--max-duration` | Duracao minima e maxima da partida em segundos | `300` / Nenhum |
| `--exclude-surrenders` | Ignorar partidas encerradas por rendicao | `False` |
| `--patch` | Filtrar por prefixo de versao do jogo (ex: `14.4`) | Nenhum |
| `--champions` | Lista de campeoes separados por virgula para filtrar partidas | Nenhum |
| `--positions` | Rotas mantidas no dataset (`TOP,JUNGLE,MIDDLE,BOTTOM,UTILITY`) | Nenhum |
| `--side` | Filtrar lado do mapa (`BLUE` ou `RED`) | Nenhum |
| `--no-discover` | Desativa descoberta em grafo (consulta apenas sementes dos elos escolhidos) | `False` |
| `--hours` | Duracao maxima em horas (`0` para ilimitado) | `8.0` |
| `-n, --target-matches` | Quantidade alvo de partidas unicas a coletar | Ilimitado |
| `--format` | Formato de saida (`both`, `parquet`, `csv`) | `both` |
| `--dataset-name` | Prefixo do arquivo de saida dentro de `data/` | `ranked_matches` |
| `--max-per-player` | Maximo de partidas consultadas por jogador (`1`-`100`) | `10` |
| `--only-challenger` | Atalho para `--tiers CHALLENGER` | `False` |
| `--reset-state` | Limpa o checkpoint antes de iniciar | `False` |
| `-y, --yes` | Pula a confirmacao interativa antes de comecar | `False` |

### 4.3 Filtragem Offline de Dataset Existente

Filtre um arquivo Parquet ou CSV ja coletado sem realizar nenhuma requisicao a Riot:

```bash
python3 src/main.py filter --champions Ahri,Orianna --positions MIDDLE --side BLUE --win 1 --min-duration 1200 -o data/ahri_blue_wins.csv
```

### 4.4 Verificacao de Status
Exibir total de partidas coletadas, jogadores visitados, tamanho da fila e tamanho dos datasets em disco:
```bash
python3 src/main.py status
```

### 4.5 Exportar Parquet para CSV
Exportar a qualquer momento a base acumulada em Parquet para CSV:
```bash
python3 src/main.py export -o data/ranked_matches.csv
```

---

## 5. Testes Automatizados

Executar a suite completa de testes:
```bash
pytest -v
```

---

## 6. Documentacao do Dataset

O dicionario completo de dados com definicoes de todas as 108 colunas, tipos de dados e tabelas de codigos esta documentado em:
- [data/README.pt-BR.md](data/README.pt-BR.md) (Portugues)
- [data/README.md](data/README.md) (Ingles)
