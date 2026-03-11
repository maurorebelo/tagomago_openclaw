# Estratégia de arquitetura e pipeline para análise de correlações entre Welltory, Apple Health e sono em DuckDB

## Objetivo

Este documento descreve a estratégia recomendada para um agente de IA implementar uma pipeline de análise de correlações entre dados do Welltory, Apple Health e sono, usando DuckDB como camada intermediária.

O foco é transformar exports imperfeitos e heterogêneos em uma base analítica confiável, com prioridade para HRV, sono, atividade, sinais vitais, features diárias derivadas e correlações com plausibilidade fisiológica.

Este documento não inclui scripts nem SQL, porque eles já foram salvos separadamente. O propósito aqui é explicar a estratégia, a razão por trás dela, o desenho da arquitetura e como os scripts devem ser usados por um agente no contexto do skill do OpenClaw.

## Contexto do problema

A arquitetura atual já está muito próxima do ideal porque usa DuckDB como camada intermediária. Isso é especialmente adequado para projetos de HRV, wearables analytics e self-tracking, porque os exports costumam ser grandes, irregulares e parcialmente incompletos.

Dois problemas são extremamente comuns:

### 1. Parse incompleto do XML

Exports de Apple Health frequentemente geram sessões fragmentadas, tipos diferentes por versão de iOS, eventos em formato longo ou largo e inconsistência entre sono, atividade e sinais vitais.

### 2. Campos vazios do Welltory

Campos como energy, stress e health frequentemente vêm vazios porque são scores derivados, dependem de baseline pessoal e nem sempre são persistidos no export bruto.

Por isso, a estratégia correta não é tentar reconstruir esses campos como se fossem dados primários, e sim usar os sinais fisiológicos que realmente importam.

## Princípio central da estratégia

A análise deve ser construída em camadas.

RAW DATA  
↓  
NORMALIZED TABLES  
↓  
DAILY FEATURE TABLE  
↓  
CORRELATION / MODELS / RANKING

Essa separação existe por três razões:

### 1. Reduz ruído

Os dados brutos vêm em formatos diferentes, com campos ausentes, granularidades inconsistentes e nomes variáveis.

### 2. Aumenta reprodutibilidade

Uma vez que as tabelas normalizadas e a tabela diária existam, qualquer análise pode ser refeita sem reparsear tudo.

### 3. Evita conclusões ruins

Correlacionar diretamente exports brutos tende a gerar correlações fracas, muita perda por missing e resultados sem plausibilidade fisiológica.

## Propósito da arquitetura

O objetivo do desenho proposto é criar uma pipeline que permita ao agente:

- aceitar dados brutos imperfeitos
- consolidar sinais fisiológicos relevantes
- trabalhar com unidade analítica diária
- produzir features comparáveis ao longo do tempo
- ranquear as correlações que importam de verdade
- manter um fluxo robusto mesmo quando o export vier incompleto

A arquitetura foi pensada para priorizar insights utilizáveis em vez de obsessão por completude total do parse.

## Filosofia de dados

### Dados primários devem vencer dados derivados

Sempre que houver conflito entre um score interpretado do app e uma métrica fisiológica real, o agente deve priorizar a métrica fisiológica real.

### Features úteis devem ser criadas após normalização

A análise principal não deve acontecer nas tabelas raw. Ela deve acontecer sobre features diárias derivadas, como baseline de HRV, razão entre HRV atual e baseline, proxies de stress e recovery, score de sono, lag de atividade física e consistência circadiana.

### Hipóteses fisiológicas devem guiar as correlações

Não vale a pena gerar uma matriz gigante com todas as colunas possíveis. O agente deve priorizar associações com plausibilidade fisiológica.

## Fonte de verdade

### Welltory

Tratar principalmente como fonte de:
- RMSSD
- SDNN
- pNN50
- LF/HF
- mean_hr
- resting_hr
- qualidade de medição, quando existir

### Apple Health

Tratar como fonte complementar para:
- sono
- atividade diária
- sinais vitais adicionais
- HRV SDNN paralelo
- resting heart rate
- respiratory rate
- SpO2
- mindful sessions
- VO2max
- walking heart rate average

### Scores do app

Campos como energy, stress e health não devem ser o eixo central da análise. Eles podem ser ignorados se vierem vazios.

## Estrutura conceitual das tabelas

### 1. Tabelas raw

Armazenam os eventos ou registros o mais próximo possível do formato original já parseado.

Exemplos:
- medições do Welltory
- sessões de sono do Apple Health
- quantidades do Apple Health
- mindful sessions

### 2. Tabelas normalizadas

Transformam o raw em entidades consistentes.

Exemplos:
- sleep_nights
- hrv_daily
- activity_daily
- physiology_daily

### 3. Tabela de features diárias

É a tabela mais importante. Deve concentrar, por dia:
- a melhor medição fisiológica do Welltory
- os dados da noite correspondente
- atividade diária
- sinais vitais do Apple Health
- features derivadas
- lags

### 4. Camada analítica

Aqui entram:
- correlações
- rankings
- comparações por grupos
- lag analysis
- regressões e modelos mais robustos, em versões futuras

## Unidade analítica principal: o dia

A unidade recomendada é o nível diário.

### Regra crítica

O sono deve ser associado à data de despertar, não à data do início do sono.

Exemplo:
- começou a dormir em 2026-03-09 à noite
- acordou em 2026-03-10 pela manhã

Então esse sono pertence analiticamente a 2026-03-10.

## Estratégia para o Welltory

### Seleção da melhor medição diária

Priorizar:
1. a primeira medição da manhã
2. medições entre aproximadamente 4h e 12h
3. melhor qualidade de sinal, se disponível
4. proximidade de um horário estável

### O que realmente usar

Os campos mais úteis do Welltory são:
- RMSSD
- SDNN
- mean HR
- resting HR
- pNN50
- LF/HF como suporte secundário

### O que evitar

Não construir a análise principal em cima de:
- energy
- stress
- health

## Estratégia para o Apple Health

### Sono

O Apple Health representa o sono como sessões, muitas vezes fragmentadas. Isso exige reconstrução por noite.

O agente deve:
- agrupar sessões por data de despertar
- somar estágios de sono
- calcular duração total
- calcular deep sleep, REM, awake e in bed
- calcular eficiência do sono quando possível

### Atividade

Agregar por dia, com foco em:
- passos
- energia ativa
- energia basal
- minutos de exercício
- voos/subidas
- workouts, quando existirem

### Fisiologia

Complementar com:
- HRV SDNN
- resting heart rate
- heart rate
- respiratory rate
- oxygen saturation
- VO2max
- walking heart rate average
- mindful sessions

## Tabela mais importante: daily_features

A tabela daily_features é o centro da estratégia.

Ela deve concentrar, por date_local:
- medição principal do Welltory
- noite reconstruída do Apple Health
- atividade diária
- fisiologia diária complementar
- features derivadas
- lags

Com essa tabela, o agente consegue:
- rodar correlação rapidamente
- gerar ranking das associações
- aplicar filtros
- testar hipóteses
- evoluir para regressão

## Features derivadas que realmente importam

### 1. Baseline de HRV

Média móvel de RMSSD e SDNN em dias anteriores.

Razão: HRV absoluta entre pessoas é pouco comparável; importa a relação com o próprio baseline.

### 2. Razão de HRV

RMSSD atual dividido pelo baseline recente.

Razão: melhor indicador de recuperação relativa do que o valor bruto.

### 3. Delta de heart rate

mean HR atual menos baseline recente.

Razão: aumento da FC em relação ao baseline costuma sinalizar maior carga fisiológica.

### 4. Sleep score

Combinação de:
- duração do sono
- deep sleep
- eficiência

### 5. Recovery proxy

Combinação padronizada de:
- RMSSD
- SDNN
- HR

### 6. Stress proxy

Combinação padronizada de:
- HR alto
- RMSSD baixo
- SDNN baixo
- eventualmente LF/HF

### 7. Activity load proxy

Combinação padronizada de:
- passos
- energia ativa
- minutos de exercício

### 8. Consistência circadiana

Diferença entre horário de dormir atual e mediana recente.

### 9. Lag de atividade

Exemplos:
- passos do dia anterior
- energia ativa do dia anterior
- exercício do dia anterior

## Correlações que merecem prioridade

Focar em pares com hipótese fisiológica forte.

### Sono → HRV e recuperação
- duração do sono → RMSSD
- deep sleep → RMSSD
- eficiência do sono → RMSSD
- sono fragmentado → stress proxy
- despertares → stress proxy

### Atividade → HRV
- exercício → recovery proxy
- active energy → recovery proxy
- passos → recovery proxy
- atividade do dia anterior → RMSSD do dia seguinte

### Ritmo circadiano
- mudança no horário de dormir → RMSSD
- inconsistência de horário → stress proxy

### Apple Health physiology → Welltory physiology
- Apple HRV SDNN → RMSSD do Welltory como referência paralela
- Apple resting HR → mean HR / stress proxy
- respiratory rate → stress proxy

### Mindful sessions
- mindful minutes → RMSSD
- mindful minutes → stress proxy

## O que não fazer

### 1. Não usar todas as colunas possíveis
Isso cria exploração caótica e baixa confiabilidade.

### 2. Não tratar Apple HRV e RMSSD como equivalentes
Eles podem andar juntos, mas não são a mesma métrica.

### 3. Não construir a análise ao redor de campos vazios do Welltory
Isso trava o projeto em um problema que não precisa ser resolvido para extrair bons insights.

### 4. Não tentar consertar tudo antes de analisar
A melhor estratégia é:
- congelar uma versão suficiente do raw
- construir as features
- começar a analisar
- depois refinar o parse se necessário

## Razão estratégica para usar DuckDB

DuckDB é uma ótima escolha porque:
- lida muito bem com datasets locais e analíticos
- facilita janelas, agregações e joins
- permite iterar rapidamente
- reduz a necessidade de infraestrutura pesada
- encaixa muito bem em pipelines conduzidas por agente

## Como os scripts devem ser usados pelo agente

### 1. Script de autopopulação das raw_*

Usar primeiro.

Função:
- olhar a DuckDB atual
- identificar automaticamente as tabelas mais prováveis
- popular wellness.raw_*
- registrar auditoria do que foi mapeado

### 2. Script/SQL de validação da autopopulação

Usar em seguida.

Função:
- verificar contagens
- inspecionar cobertura por tabela
- confirmar se as métricas esperadas apareceram
- detectar rapidamente se algo ficou vazio

### 3. SQL de schema

Função:
- padronizar as tabelas raw, normalizadas e de features
- garantir que o pipeline tenha um modelo estável

### 4. SQL de construção das features

Função:
- gerar tabelas normalizadas
- construir daily_features
- criar baselines, proxies, scores e lags

### 5. SQL de correlações

Função:
- medir as associações prioritárias
- ranquear pares importantes
- permitir uma leitura objetiva das relações mais fortes

## Ordem operacional recomendada

### Etapa 1 — preparar raw
Executar a autopopulação das raw_*.

### Etapa 2 — validar
Verificar contagem por tabela, variedade de métricas, datas mínimas e máximas e cobertura suficiente.

### Etapa 3 — construir tabelas normalizadas
Criar:
- sleep_nights
- hrv_daily
- activity_daily
- physiology_daily

### Etapa 4 — construir daily_features
Criar:
- baselines
- razões
- deltas
- scores
- proxies
- lags

### Etapa 5 — rodar correlações prioritárias
Focar nas associações fisiologicamente plausíveis.

### Etapa 6 — interpretar
Produzir um resumo que destaque:
- melhores associações positivas
- melhores associações negativas
- número de pares válidos
- possíveis confundidores
- limitações

## Critérios mínimos de qualidade

Aceitável para exploração:
- cerca de 14 dias pareados

Ideal:
- cerca de 30 dias ou mais

Além disso:
- preferir métricas ajustadas por baseline
- priorizar Spearman quando houver outliers ou não linearidade
- reportar missing e cobertura
- explicitar que correlação não implica causalidade

## Missing data

Missing não deve ser tratado automaticamente como falha fatal.

O agente deve:
- aceitar ausência de energy, stress e health
- aceitar cobertura parcial de métricas do Apple Health
- evitar imputar HRV principal para correlação
- usar cobertura e número de pares válidos como critério de confiança

## Limitações que o agente deve explicar

Toda saída analítica precisa deixar claro que:
- correlação não implica causalidade
- álcool, doença, treino intenso, cafeína, horário da medição e jet lag social podem confundir resultados
- Apple Health pode mudar de granularidade conforme dispositivo e sistema
- HRV é sensível ao contexto da medição
- diferentes métricas de HRV não são intercambiáveis

## Próxima evolução natural

Depois que a estratégia acima estiver funcionando, a evolução recomendada é:
- regressão regularizada
- análise por quartis
- modelos com lag 1 e lag 2
- comparação entre semana útil e fim de semana
- ranking mais robusto com controle de confundidores
- eventualmente modelos de previsão do recovery proxy

## Resumo executivo para o agente

A estratégia correta é:

1. usar DuckDB como camada intermediária
2. aceitar que os exports são imperfeitos
3. ignorar dependência de energy, stress e health
4. tratar HRV e heart rate como sinais principais
5. reconstruir sono por data de despertar
6. agregar atividade e fisiologia diária
7. construir uma tabela daily_features
8. criar proxies, baselines e lags
9. analisar apenas correlações com plausibilidade fisiológica
10. usar os scripts já salvos para automatizar cada etapa

O propósito dessa abordagem é transformar um conjunto de exports bagunçados em uma base confiável para responder perguntas úteis como:
- dormir mais aumenta minha recuperação?
- deep sleep está ligado ao meu RMSSD?
- exercício hoje melhora ou piora minha HRV amanhã?
- mudança no horário de dormir afeta meu stress fisiológico?
- mindful sessions parecem associadas a melhor recuperação?
