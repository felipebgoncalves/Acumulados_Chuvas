# Acumulados de Chuva

Aplicação em Streamlit para consulta e visualização dos maiores acumulados de chuva nas últimas 24 horas nos municípios do Espírito Santo.

O projeto integra diferentes fontes de dados, normaliza os registros para um contrato comum e apresenta o maior acumulado encontrado por município.

## Fontes de dados

- CEMADEN;
- ANA;
- INMET;
- SATDES, usando apenas estações CEPDEC e INCAPER.

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
```

## Variáveis e secrets necessários

Configure as variáveis no `.env` para execução local ou em `st.secrets` no Streamlit Cloud.

```text
ANA_ID
ANA_PWD
INMET_API_TOKEN
```

As variáveis da API Plugfield/Vila Velha podem permanecer configuradas para uso futuro:

```text
VV_API_Key
VV_Username
VV_PASSWORD
```

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

A base de metadados de estações do SATDES fica em:

```text
data/stations_satdes.json
```

Ela é usada para complementar os dados com município, instituição, latitude, longitude e altitude quando essas informações estão disponíveis.

## Deploy

O projeto continua recomendado para execução no Streamlit.

O GitHub Actions é usado como apoio operacional para validação contínua, executando testes em pushes para `main` e `development`, além de pull requests.

## Limitações conhecidas

- Algumas fontes externas podem ficar lentas ou indisponíveis.
- O CEMADEN permanece usando `verify=False` por necessidade da fonte atual.
- Snapshots gerados no Streamlit Cloud podem ser efêmeros dependendo do ambiente de execução.
- A API Plugfield/Vila Velha ainda não foi integrada ao fluxo principal.
