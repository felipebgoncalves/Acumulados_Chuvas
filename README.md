# Acumulados de Chuva

Aplicação em Streamlit para consulta e visualização dos maiores acumulados de chuva nas últimas 24 horas nos municípios do Espírito Santo.

O projeto integra diferentes fontes de dados, normaliza os registros para um contrato comum e apresenta o maior acumulado encontrado por município.

## Fontes de dados

- CEMADEN;
- ANA;
- INMET;
- PMVV / Plugfield;
- CEPDEC / SIMET, consultando diretamente 29 estações.

## Resultado exibido

A aplicação mantém a característica original do projeto:

- mapa dos municípios com acumulado registrado;
- ranking dos maiores acumulados;
- lista textual dos acumulados de chuva em 24h.

Além disso, foram adicionadas informações operacionais de apoio:

- cards de resumo;
- status das fontes;
- tooltip do mapa com fonte e estação;
- snapshots JSON dos acumulados consolidados.

## Regra de consolidação

Cada fonte retorna os acumulados em um formato comum. Depois da coleta:

1. os registros sem chuva são descartados;
2. os dados são ordenados por acumulado;
3. para cada município, permanece apenas o maior acumulado encontrado;
4. o resultado final é exibido na interface.

## Contrato de dados

O contrato mínimo usado pela interface é:

```text
Município
Prec_mm
Instituição
```

O contrato estendido usado internamente é:

```text
Município
Prec_mm
Instituição
Estação
Latitude
Longitude
Altitude
DataHoraReferencia
Fonte
Observação
```

## Variáveis e secrets necessários

Configure as variáveis no `.env` para execução local ou em `st.secrets` no Streamlit Cloud.

```text
ANA_ID
ANA_PWD
INMET_API_TOKEN
PMVV_API_Key
PMVV_Username
PMVV_PASSWORD
grant_type
client_id
client_secret
api_key
```

As credenciais da PMVV/Plugfield são usadas para consultar estações e dados horários de chuva do município de Vila Velha.

As URLs públicas da CEPDEC e da PMVV estão em `app/config/settings.py`; não precisam ser cadastradas como secrets.
As chaves são sensíveis a maiúsculas/minúsculas. Use `grant_type=client_credentials`.
O campo `scope` não é enviado: o valor testado foi rejeitado pelo servidor com `invalid_scope`.
Cadastre essas mesmas chaves em **Settings → Secrets** no Streamlit Cloud; o `.env` local não é enviado ao GitHub.

## Como rodar localmente

Instale as dependências:

```bash
poetry install
```

Execute o app:

```bash
poetry run streamlit run app.py
```

## Testes

Execute:

```bash
poetry run pytest -q
```

Os testes cobrem:

- normalização de dados;
- regra de consolidação do `Joiner`;
- comportamento básico dos coletores;
- importação da aplicação principal.

## Snapshots

A aplicação salva snapshots JSON dos acumulados consolidados em:

```text
data/snapshots/
```

Essa pasta é ignorada pelo Git para evitar commits automáticos de arquivos gerados durante a execução.

## Base de estações

O catálogo CEPDEC fica no dicionário `CEPDEC` em `app/codEstacoes.py`, com as 29 estações configuradas.
As duas estações de Vargem Alta permanecem separadas na lista geral; a consolidação por município mantém o maior acumulado.
Coordenadas e altitude são obtidas por `/v1/estacoes`.
Os metadados locais já usados pela ANA e pelo INMET foram preservados em `data/stations_ana_inmet.json`, sem dependência de outra API.

### Coleta CEPDEC

- Um token por coleta; até quatro consultas de estações simultâneas, em paralelo com as outras fontes.
- Consulta `/v1/observacoes?estacao=...&intervalo_minutos=15`, com paginação por `cursor`/`next_cursor`, da mais recente para a mais antiga.
- Soma `dados.PRECIPITACAO_MM` em `(agora UTC - 24 horas, agora UTC]`; não mistura registros horários e de 15 minutos.
- Remove horários duplicados e descarta valores ausentes, negativos, não finitos, qualidade diferente de `VALIDO` ou registros com flags.
- Espera 96 leituras por estação e sinaliza lacunas maiores que 16 minutos (tolerância de um minuto para o relógio).
- Dados incompletos permanecem com aviso em `Observação`, listas, mapa e status **Parcial**. Estações sem leitura não são tratadas como chuva zero.
- Falhas em páginas posteriores preservam as leituras já obtidas, com aviso. Falha geral de autenticação/consulta aparece como **Falha**, com erro sanitizado.
- Limite de dez páginas por estação e detecção de cursor repetido evitam consultas ilimitadas; interrupções são sinalizadas.
- Acumulados válidos iguais a zero continuam fora dos rankings, como nas demais fontes; avisos de cobertura aparecem mesmo quando não há chuva.

## Deploy

O projeto continua recomendado para execução no Streamlit.

O GitHub Actions é usado como apoio operacional para validação contínua, executando testes em pushes para `main` e `development`, além de pull requests.

## Limitações conhecidas

- Algumas fontes externas podem ficar lentas ou indisponíveis.
- O CEMADEN permanece usando `verify=False` por necessidade da fonte atual.
- Snapshots gerados no Streamlit Cloud podem ser efêmeros dependendo do ambiente de execução.
- O acumulado PMVV/Plugfield é calculado por `/data/sensor`, somando as leituras dos sensores de chuva em milímetros nas últimas 24 horas. Os endpoints agrupados `/data/hourly` e `/data/daily` não são usados pelo collector.
