# Pipeline de Coleta de Dados Ranqueados de League of Legends

Pipeline automatizado, resiliente e em conformidade com os limites de taxa da Riot Games, projetado para coletar datasets de partidas ranqueadas de alto nivel (Challenger, Grao-Mestre e Mestre) utilizando a API oficial da Riot Games para pesquisa academica (Iniciacao Cientifica) e aplicacoes de Machine Learning.

[English Version (README.md)](README.md)

---

## 1. Visao Geral

O pipeline extrai estatisticas detalhadas de partidas e participantes em salas de alto MMR, normalizando a resposta bruta da API em um dataset tabular estruturado contendo **108 variaveis por participante** (10 linhas por partida).

### Principais Funcionalidades
- **Conformidade com Limite de Taxa:** Limitador de taxa por algoritmo Token Bucket com janela deslizante, gerenciando simultaneamente os limites de curto prazo (20 req/1s) e longo prazo (100 req/120s) da Riot com margem preventiva de 10%, alem de tratamento reativo com backoff para respostas HTTP 429 (`Retry-After`).
- **Diversidade de Jogadores:** Varredura em grafo por busca em largura (*Breadth-First Search*), iniciando pelas sementes dos elos mais altos (Challenger, Grao-Mestre e Mestre) e descobrindo novos participantes dinamicamente a cada partida minerada.
- **Checkpointing e Deduplicacao:** Persistencia atomica de estado (`data/state_<platform>.json`), evitando consultas duplicadas e permitindo pausar e retomar a execucao sem perda de progresso.
- **Armazenamento Duplo:** Gravacao sincronizada em formato colunar Apache Parquet com compressao Snappy (`data/ranked_matches.parquet`) e formato tabular CSV (`data/ranked_matches.csv`).
- **Conjunto Abrangente de Features:** 108 colunas por registro cobrindo contexto da partida, lado do mapa (Blue/Red Side), combate, distribuicao de dano, estruturas, economia de rotas, visao, mecanica de skillshots, conjuracoes de habilidades, pings de comunicacao, itens e runas.

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
│   ├── main.py                  # Ponto de entrada CLI
│   ├── config/settings.py       # Configuracao e validacao de ambiente com Pydantic
│   ├── core/
│   │   ├── rate_limiter.py      # Limitador de taxa Token Bucket
│   │   ├── http_client.py       # Cliente HTTP resiliente com retries e backoff
│   │   └── exceptions.py        # Classes de excecao do dominio
│   ├── riot/
│   │   ├── routing.py           # Mapeamento de plataforma para cluster regional
│   │   ├── league_api.py        # Coletor de sementes da League-v4
│   │   └── match_api.py         # Coletor de partidas e detalhes da Match-v5
│   ├── models/
│   │   ├── api_models.py        # Modelos Pydantic da resposta bruta da API
│   │   └── dataset_models.py    # Modelo formal do schema de 108 features
│   └── pipeline/
│       ├── normalizer.py        # Motor de extracao e transformacao de features
│       ├── state_manager.py     # Gerenciador de checkpoints e deduplicacao
│       ├── storage.py           # Gravador atomico em Parquet e CSV
│       └── orchestrator.py      # Loop principal de orquestracao da coleta
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

### 4.1 Coleta de Dados

Executar a coleta com limite de tempo:
```bash
# Execucao padrao por 8 horas (Challenger, Grao-Mestre e Mestre do BR1)
python3 src/main.py collect --hours 8.0

# Execucao em segundo plano no Linux
nohup python3 src/main.py collect --hours 8.0 > crawler.log 2>&1 &
```

Coletar a partir de outros servidores regionais:
```bash
# Coreia (KR)
python3 src/main.py collect -p KR --hours 8.0

# America do Norte (NA1)
python3 src/main.py collect -p NA1 --hours 8.0

# Europa Ocidental (EUW1)
python3 src/main.py collect -p EUW1 --hours 8.0
```

Coletar uma quantidade exata de partidas:
```bash
python3 src/main.py collect -n 500
```

### 4.2 Verificacao de Status
Exibir total de partidas coletadas, jogadores visitados, tamanho da fila e tamanho dos datasets em disco:
```bash
python3 src/main.py status
```

### 4.3 Exportar Parquet para CSV
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
