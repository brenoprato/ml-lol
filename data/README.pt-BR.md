# Dicionario de Dados e Codebook do Dataset de League of Legends

Dicionario de Dados e Codebook oficial do dataset coletado via API oficial da Riot Games para Pesquisa Cientifica (Iniciacao Cientifica - IC) e aplicacoes de Machine Learning.

[English Version (README.md)](README.md)

---

## 1. Metadados do Dataset

- **Fonte dos Dados:** API oficial da Riot Games (`LEAGUE-V4` e `MATCH-V5`).
- **Elos Alvo:** Ranqueada Solo/Duo do topo da tabela (Challenger, Grao-Mestre e Mestre).
- **Fila Alvo:** Queue ID `420` (`RANKED_SOLO_5x5`).
- **Granularidade:** **10 linhas por partida** (cada linha representa 1 participante individual).
- **Formatos de Arquivo:**
  - `data/ranked_matches.parquet`: Formato colunar comprimido com Snappy, preservando tipos estritos (recomendado para Python, Pandas, Polars, Scikit-learn).
  - `data/ranked_matches.csv`: Formato tabular delimitado UTF-8 (recomendado para Excel, Google Planilhas e inspecao direta).
- **Arquivo de Checkpoint:** `data/state_<platform>.json` (Rastreia jogadores visitados e partidas processadas, garantindo zero duplicacao de partidas entre execucoes).

---

## 2. Dicionario Completo das 108 Colunas

### 2.1 Contexto da Partida, Identificacao e Lado (10 colunas)
| Nome da Coluna | Tipo de Dado | Descricao |
| :--- | :--- | :--- |
| `match_id` | `string` | Identificador unico da partida na Riot (ex: `BR1_3275903146`). |
| `game_version` | `string` | Versao do patch do jogo (ex: `14.4.1`). |
| `game_duration` | `int64` | Duracao total da partida em **segundos**. |
| `queue_id` | `int64` | Identificador da fila (`420` para Ranqueada Solo/Duo). |
| `game_creation` | `int64` | Timestamp (epoch em milissegundos) de criacao do jogo. |
| `game_ended_in_surrender` | `bool` | `True` se a partida terminou antecipadamente por rendicao. |
| `puuid` | `string` | Identificador persistente e criptografado do jogador na Riot. |
| `summoner_name` | `string` | Nome de invocador / Riot ID do jogador. |
| `team_id` | `int64` | Identificador do time: `100` para Lado Azul (*Blue Side*), `200` para Lado Vermelho (*Red Side*). |
| `side` | `string` | Lado do mapa: **`BLUE`** ou **`RED`**. |

### 2.2 Rota, Campeao e Variavel Alvo (6 colunas)
| Nome da Coluna | Tipo de Dado | Descricao |
| :--- | :--- | :--- |
| `team_position` | `string` | Rota principal: `TOP`, `JUNGLE`, `MIDDLE`, `BOTTOM` (ADC) ou `UTILITY` (Suporte). |
| `individual_position` | `string` | Rota individual detectada pelo pareamento da Riot. |
| `champion_id` | `int64` | ID numerico do campeao. |
| `champion_name` | `string` | Nome do campeao jogado (ex: `Aatrox`, `Ahri`, `Yasuo`). |
| `champ_level` | `int64` | Nivel final alcancado pelo campeao (1 - 18). |
| `win` | `int64` | **Variavel Alvo:** `1` para Vitoria, `0` para Derrota. |

### 2.3 Combate, KDA e Sequencias de Abates (16 colunas)
| Nome da Coluna | Tipo de Dado | Descricao |
| :--- | :--- | :--- |
| `kills` | `int64` | Numero de campeoes inimigos abatidos. |
| `deaths` | `int64` | Numero de vezes que o jogador morreu. |
| `assists` | `int64` | Numero de assistencias em abates. |
| `kda` | `double` | Razao calculada: `(kills + assists) / max(1, deaths)`. |
| `kill_participation` | `double` | Porcentagem de participacao do jogador nos abates do time (`0.0` a `1.0`). |
| `solo_kills` | `int64` | Numero de abates 1x1 conquistados sem assistencia de aliados. |
| `double_kills` | `int64` | Quantidade de *Double Kills* (2 abates em sequencia). |
| `triple_kills` | `int64` | Quantidade de *Triple Kills* (3 abates em sequencia). |
| `quadra_kills` | `int64` | Quantidade de *Quadra Kills* (4 abates em sequencia). |
| `penta_kills` | `int64` | Quantidade de *Penta Kills* (5 abates em sequencia). |
| `first_blood_kill` | `bool` | `True` se o jogador conquistou o Primeiro Abate (*First Blood*). |
| `first_blood_assist` | `bool` | `True` se o jogador deu assistencia no Primeiro Abate. |
| `largest_killing_spree` | `int64` | Maior sequencia de abates consecutivos sem morrer. |
| `largest_multi_kill` | `int64` | Maior numero de abates simultaneos em combate. |
| `longest_time_spent_living` | `int64` | Maior tempo continuo vivo sem morrer (em segundos). |
| `total_time_spent_dead` | `int64` | Tempo total acumulado esperando renascer (em segundos). |

### 2.4 Distribuicao de Dano, Curas, Escudos e Controle de Grupo (16 colunas)
| Nome da Coluna | Tipo de Dado | Descricao |
| :--- | :--- | :--- |
| `total_damage_dealt_to_champions` | `int64` | Dano total causado a campeoes inimigos. |
| `physical_damage_dealt_to_champions` | `int64` | Dano fisico causado a campeoes inimigos. |
| `magic_damage_dealt_to_champions` | `int64` | Dano magico causado a campeoes inimigos. |
| `true_damage_dealt_to_champions` | `int64` | Dano verdadeiro causado a campeoes inimigos. |
| `team_damage_percentage` | `double` | Participacao percentual do jogador no dano total do time (`0.0` a `1.0`). |
| `damage_per_minute` | `double` | DPM (Dano causado a campeoes por minuto de jogo). |
| `total_damage_taken` | `int64` | Dano total recebido e absorvido de todas as fontes. |
| `physical_damage_taken` | `int64` | Dano fisico recebido. |
| `magic_damage_taken` | `int64` | Dano magico recebido. |
| `true_damage_taken` | `int64` | Dano verdadeiro recebido. |
| `damage_self_mitigated` | `int64` | Dano mitigado/bloqueado por armadura, resistencia magica e escudos proprios. |
| `total_heal` | `int64` | Quantidade total de vida curada/regenerada em si. |
| `total_heals_on_teammates` | `int64` | Cura aplicada em campeoes aliados. |
| `total_damage_shielded_on_teammates` | `int64` | Dano bloqueado por escudos concedidos a aliados. |
| `time_ccing_others` | `int64` | Duracao total (em segundos) de controle de grupo (CC) aplicado em inimigos. |
| `total_time_cc_dealt` | `int64` | Duracao total de efeitos de controle e debuffs aplicados. |

### 2.5 Estruturas, Torres e Objetivos Neutros (14 colunas)
| Nome da Coluna | Tipo de Dado | Descricao |
| :--- | :--- | :--- |
| `damage_dealt_to_buildings` | `int64` | Dano total causado a estruturas (torres + inibidores). |
| `damage_dealt_to_turrets` | `int64` | Dano especifico causado a torres. |
| `damage_dealt_to_objectives` | `int64` | Dano causado a monstros epicos (Dragoes, Baroes, Arautos, Vastilarvas). |
| `turret_kills` | `int64` | Numero de torres destruidas diretamente (ultimo golpe). |
| `turret_takedowns` | `int64` | Numero de destruicoes de torres com participacao do jogador. |
| `turrets_lost` | `int64` | Quantidade de torres perdidas na rota do jogador. |
| `turret_plates_taken` | `int64` | Barricadas de torre (*plates*) destruidas antes dos 14 minutos. |
| `inhibitor_kills` | `int64` | Numero de inibidores destruidos diretamente. |
| `inhibitor_takedowns` | `int64` | Numero de inibidores destruidos com participacao do jogador. |
| `first_tower_kill` | `bool` | `True` se o jogador destruiu a Primeira Torre do jogo. |
| `first_tower_assist` | `bool` | `True` se o jogador participou da destruicao da Primeira Torre. |
| `dragon_kills` | `int64` | Numero de Dragoes abatidos pelo jogador. |
| `baron_kills` | `int64` | Numero de Baroes abatidos pelo jogador. |
| `objectives_stolen` | `int64` | Monstros epicos roubados do time inimigo (*steals*). |

### 2.6 Economia, Farm e Ritmo de Early Game (13 colunas)
| Nome da Coluna | Tipo de Dado | Descricao |
| :--- | :--- | :--- |
| `gold_earned` | `int64` | Ouro total recebido ao longo da partida. |
| `gold_spent` | `int64` | Ouro gasto na compra de itens na loja. |
| `gold_per_minute` | `double` | Ouro medio recebido por minuto de jogo (GPM). |
| `bounty_gold` | `int64` | Ouro extra ganho por coletar recompensas (*shutdowns*). |
| `total_minions_killed` | `int64` | Tropas abatidas na rota (Lane CS). |
| `neutral_minions_killed` | `int64` | Monstros neutros da selva abatidos (Jungle CS). |
| `total_ally_jungle_minions_killed` | `int64` | Monstros abatidos na selva aliada. |
| `total_enemy_jungle_minions_killed` | `int64` | **Monstros abatidos na selva inimiga (*Counter-Jungling*)**. |
| `total_cs` | `int64` | CS Total (`total_minions_killed + neutral_minions_killed`). |
| `cs_per_minute` | `double` | Media de tropas/monstros abatidos por minuto (CS/min). |
| `lane_minions_first_10_minutes` | `int64` | Tropas de rota abatidas nos primeiros 10 minutos de jogo. |
| `jungle_cs_before_10_minutes` | `int64` | Monstros da selva abatidos nos primeiros 10 minutos. |
| `early_laning_phase_gold_exp_advantage`| `int64` | Pontuacao de vantagem de ouro/XP obtida na fase de rotas. |

### 2.7 Visao e Controle de Mapa (6 colunas)
| Nome da Coluna | Tipo de Dado | Descricao |
| :--- | :--- | :--- |
| `vision_score` | `int64` | Placar de visao (*Vision Score*) oficial da partida. |
| `vision_score_per_minute` | `double` | Placar de visao gerado por minuto de jogo. |
| `wards_placed` | `int64` | Total de sentinelas colocadas no mapa. |
| `wards_killed` | `int64` | Total de sentinelas inimigas detectadas e destruidas. |
| `control_wards_placed` | `int64` | Sentinelas de controle (*Pink Wards*) colocadas. |
| `vision_wards_bought_in_game` | `int64` | Sentinelas de controle compradas na loja com ouro. |

### 2.8 Mecanica, Skillshots, Habilidades e Pings (16 colunas)
| Nome da Coluna | Tipo de Dado | Descricao |
| :--- | :--- | :--- |
| `skillshots_dodged` | `int64` | **Quantidade de habilidades de mira (*skillshots*) esquivadas.** |
| `skillshots_hit` | `int64` | **Quantidade de habilidades de mira (*skillshots*) acertadas em inimigos.** |
| `enemy_champion_immobilizations` | `int64` | Numero de vezes que imobilizou campeoes inimigos (Stun, Root, Knockup). |
| `spell1_casts` | `int64` | **Quantidade total de vezes que conjurou a habilidade Q.** |
| `spell2_casts` | `int64` | **Quantidade total de vezes que conjurou a habilidade W.** |
| `spell3_casts` | `int64` | **Quantidade total de vezes que conjurou a habilidade E.** |
| `spell4_casts` | `int64` | **Quantidade total de vezes que conjurou a Ultimate (R).** |
| `summoner1_casts` | `int64` | Quantidade de vezes que ativou o Feitiço de Invocador 1 (ex: Flash). |
| `summoner2_casts` | `int64` | Quantidade de vezes que ativou o Feitiço de Invocador 2 (ex: Ignite/TP). |
| `enemy_missing_pings` | `int64` | Pings de "Inimigo Desaparecido" (`?`). |
| `danger_pings` | `int64` | Pings de "Perigo" (`!`). |
| `on_my_way_pings` | `int64` | Pings de "A Caminho". |
| `assist_me_pings` | `int64` | Pings de "Preciso de Ajuda". |
| `all_in_pings` | `int64` | Pings de "All-in" / Avancar. |
| `push_pings` | `int64` | Pings de "Empurrar Rota". |
| `retreat_pings` | `int64` | Pings de "Recuar" / Alerta amarelo. |

### 2.9 Inventario, Feiticos e Runas - IDs (11 colunas)
| Nome da Coluna | Tipo de Dado | Descricao |
| :--- | :--- | :--- |
| `item0` | `int64` | **ID do Item** no Slot 1 do inventario (`0` se vazio). |
| `item1` | `int64` | **ID do Item** no Slot 2 do inventario. |
| `item2` | `int64` | **ID do Item** no Slot 3 do inventario. |
| `item3` | `int64` | **ID do Item** no Slot 4 do inventario. |
| `item4` | `int64` | **ID do Item** no Slot 5 do inventario. |
| `item5` | `int64` | **ID do Item** no Slot 6 do inventario. |
| `item6` | `int64` | **ID do Trinket / Sentinela** (ex: `3340` Amarela, `3364` Vermelha Lente, `3363` Azul). |
| `summoner1_id` | `int64` | **ID do Feitico de Invocador 1** (ex: `4` = Flash, `14` = Ignite). |
| `summoner2_id` | `int64` | **ID do Feitico de Invocador 2**. |
| `primary_rune_tree` | `int64` | **ID da Arvore de Runas Primaria** (`8000`: Precisao, `8100`: Dominacao, `8200`: Feiticaria, `8300`: Inspiracao, `8400`: Determinacao). |
| `secondary_rune_tree` | `int64` | **ID da Arvore de Runas Secundaria**. |

---

## 3. Tabelas de Codigos de Referencia

### 3.1 IDs de Feiticos de Invocador
| ID | Nome em Ingles | Nome em Portugues |
| :--- | :--- | :--- |
| `1` | Cleanse | Purificar |
| `3` | Exhaust | Exaustao |
| `4` | Flash | Flash |
| `6` | Ghost | Fantasma |
| `7` | Heal | Curar |
| `11` | Smite | Golpear |
| `12` | Teleport | Teleporte |
| `14` | Ignite | Incendiar |
| `21` | Barrier | Barreira |

### 3.2 IDs de Arvores de Runas
| ID | Nome da Arvore | Tema |
| :--- | :--- | :--- |
| `8000` | Precisao (*Precision*) | Velocidade de ataque, dano sustentado em combate e execucoes. |
| `8100` | Dominacao (*Domination*) | Dano explosivo (*burst*), acesso a alvos e assassinatos. |
| `8200` | Feiticaria (*Sorcery*) | Escalamento de recursos, poder de habilidade e reducao de tempo de recarga. |
| `8300` | Inspiracao (*Inspiration*) | Utilidade, vantagens economicas e ferramentas criativas. |
| `8400` | Determinacao (*Resolve*) | Durabilidade, escalamento de vida e resistencia a controle de grupo. |

---

## 4. Exemplo de Carregamento em Python (Pandas e Polars)

```python
import pandas as pd

# Carregar o dataset completo em Parquet
df = pd.read_parquet("data/ranked_matches.parquet")

print(f"Total de linhas (participantes): {len(df):,}")
print(f"Total de partidas unicas:       {df['match_id'].nunique():,}")

# Exemplo: Filtrar jogadores da rota do TOP e analisar dano a torres vs ouro
top_laners = df[df["team_position"] == "TOP"]
print(top_laners[["champion_name", "win", "damage_dealt_to_buildings", "gold_per_minute"]].head())
```
