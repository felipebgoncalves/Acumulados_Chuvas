# Manual de utilização da API SIMET-ES

**Público:** instituições parceiras e sistemas consumidores, sem permissão administrativa
**Versão:** 1.0 - 06/10/2026

## 1. Objetivo

Este manual mostra como obter o token, montar uma requisição e utilizar todas as
rotas disponíveis para consumidores não administrativos. Ele não contém operações
de cadastro, alteração ou revogação de parceiros.

## 2. Endereços

Use uma variável para evitar trocar a URL em todas as requisições:

| Ambiente | URL base atual no servidor |
|---|---|
| Homologação | `http://localhost:8001` |
| Produção | `http://localhost:8000` |

Esses endereços são locais ao servidor. A instituição deverá receber o domínio HTTPS
oficial quando a TI concluir a publicação. Para testes atuais, utilize homologação.
O Swagger (`/docs`), o ReDoc e o `/openapi.json` estão desativados em homologação e
produção.

Nos exemplos, `{{base_url}}` representa a URL base escolhida.

## 3. Credenciais recebidas

A instituição recebe, por canais seguros e separados:

- `client_id` do cliente criado no Keycloak;
- `client_secret` do cliente;
- uma X-API-Key emitida para o ACT;
- URL base da API;
- endpoint de token.

Nunca coloque `client_secret`, token JWT ou X-API-Key em código-fonte, Git, e-mail
aberto, prints ou logs.

## 4. Obter o token JWT

Envie `POST` para:

```text
https://sistemas.cb.es.gov.br/keycloak/realms/sistemas-cepdec/protocol/openid-connect/token
```

O corpo usa `application/x-www-form-urlencoded`:

| Campo | Valor |
|---|---|
| `grant_type` | `client_credentials` |
| `client_id` | client recebido da administração |
| `client_secret` | segredo recebido da administração |

Exemplo com cURL:

```bash
curl -X POST "https://sistemas.cb.es.gov.br/keycloak/realms/sistemas-cepdec/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=SEU_CLIENT_ID" \
  --data-urlencode "client_secret=SEU_CLIENT_SECRET"
```

A resposta esperada contém `access_token`, `token_type=Bearer`, `expires_in=300` e
`scope` com `simet:read`. Não existe refresh token no fluxo Client Credentials. Ao
expirar, solicite outro token.

## 5. Cabeçalhos das consultas

Todas as rotas de dados exigem:

```http
Authorization: Bearer <access_token>
X-API-Key: <x-api-key recebida>
Accept: application/json
```

Os três endpoints de saúde são públicos e não exigem esses cabeçalhos.

## 6. Regras comuns dos parâmetros

- Parâmetros de consulta são adicionados depois de `?` e separados por `&`.
- Booleanos usam `true` ou `false`.
- Datas e horas usam ISO 8601 e devem informar fuso, por exemplo
  `2026-10-01T00:00:00Z` ou `2026-10-01T00:00:00-03:00`.
- Para repetir `estacao` ou `variavel`, repita o nome do parâmetro.
- Códigos de estação aceitam letras, números e sublinhado, com até 40 caracteres.
- O acesso final sempre respeita as estações autorizadas para a instituição.

## 7. Rotas públicas de saúde

### 7.1 `GET /health/live`

Confirma que o processo da API está ativo. Não consulta o Oracle e não exige
autenticação. Não possui parâmetros.

```bash
curl "{{base_url}}/health/live"
```

### 7.2 `GET /health/ready`

Confirma que a API está pronta e que o Oracle está acessível. Não exige autenticação
e não possui parâmetros. Retorna HTTP 200 quando pronta ou 503 quando indisponível.

```bash
curl "{{base_url}}/health/ready"
```

### 7.3 `GET /v1/saude`

Fornece a saúde versionada do serviço e o estado do banco. Não exige autenticação e
não possui parâmetros.

```bash
curl "{{base_url}}/v1/saude"
```

## 8. Catálogos

### 8.1 `GET /v1/instituicoes`

Lista instituições mantenedoras das estações meteorológicas.

| Parâmetro | Tipo | Obrigatório | Padrão | Descrição |
|---|---|---|---|---|
| `somente_ativas` | booleano | não | `true` | Quando `false`, inclui instituições inativas. |

```bash
curl "{{base_url}}/v1/instituicoes?somente_ativas=true" \
  -H "Authorization: Bearer $TOKEN" -H "X-API-Key: $API_KEY"
```

### 8.2 `GET /v1/municipios`

Lista municípios.

| Parâmetro | Tipo | Obrigatório | Padrão | Descrição |
|---|---|---|---|---|
| `uf` | texto de 2 caracteres | não | `ES` | Filtra pela sigla da unidade federativa. Pode ser omitido para usar ES. |

```bash
curl "{{base_url}}/v1/municipios?uf=ES" \
  -H "Authorization: Bearer $TOKEN" -H "X-API-Key: $API_KEY"
```

### 8.3 `GET /v1/frequencias`

Lista frequências e intervalos de medição. Não possui parâmetros.

```bash
curl "{{base_url}}/v1/frequencias" \
  -H "Authorization: Bearer $TOKEN" -H "X-API-Key: $API_KEY"
```

### 8.4 `GET /v1/variaveis`

Lista variáveis meteorológicas, unidade, limites e casas decimais.

| Parâmetro | Tipo | Obrigatório | Padrão | Descrição |
|---|---|---|---|---|
| `somente_ativas` | booleano | não | `true` | Quando `false`, inclui variáveis inativas. |

```bash
curl "{{base_url}}/v1/variaveis?somente_ativas=true" \
  -H "Authorization: Bearer $TOKEN" -H "X-API-Key: $API_KEY"
```

## 9. Estações

### 9.1 `GET /v1/estacoes`

Lista as estações autorizadas ao consumidor.

| Parâmetro | Tipo | Obrigatório | Padrão | Descrição |
|---|---|---|---|---|
| `municipio_ibge` | 7 dígitos | não | - | Filtra pelo código IBGE do município. |
| `instituicao` | texto, 1 a 30 | não | - | Filtra pela sigla/código da instituição mantenedora. |
| `somente_ativas` | booleano | não | `true` | Quando `false`, inclui estações inativas autorizadas. |

```bash
curl "{{base_url}}/v1/estacoes?municipio_ibge=3205309&somente_ativas=true" \
  -H "Authorization: Bearer $TOKEN" -H "X-API-Key: $API_KEY"
```

### 9.2 `GET /v1/estacoes/{codigo}`

Consulta uma estação e suas frequências. Substitua `{codigo}` pelo código exato.

| Parâmetro | Local | Obrigatório | Regra |
|---|---|---|---|
| `codigo` | caminho | sim | 1 a 40 caracteres; letras, números e `_`. |

```bash
curl "{{base_url}}/v1/estacoes/EMA_VITORIA_01" \
  -H "Authorization: Bearer $TOKEN" -H "X-API-Key: $API_KEY"
```

## 10. Observações meteorológicas

### 10.1 `GET /v1/observacoes`

Lista observações com paginação por cursor.

| Parâmetro | Tipo | Obrigatório | Padrão/limite | Descrição |
|---|---|---|---|---|
| `estacao` | texto repetível | não | máximo 100 | Filtra um ou mais códigos de estação. |
| `municipio_ibge` | 7 dígitos | não | - | Filtra pelo município. |
| `instituicao` | texto | não | até 30 | Filtra pela instituição mantenedora. |
| `intervalo_minutos` | inteiro | não | 1 a 10080 | Filtra a frequência pelo intervalo. |
| `inicio_utc` | data/hora com fuso | condicional | - | Início inclusivo do período. Exige `fim_utc`. |
| `fim_utc` | data/hora com fuso | condicional | - | Fim do período. Exige `inicio_utc`. |
| `qualidade` | texto | não | até 40 | Filtra o código de qualidade geral. |
| `variavel` | texto repetível | não | máximo 200 | Retorna em `dados` somente as variáveis solicitadas. |
| `cursor` | texto opaco | não | até 500 | Continua a página anterior usando `next_cursor`. |
| `limite` | inteiro | não | padrão 100; 1 a 500 | Quantidade máxima de itens da página. |

O período máximo configurado é de 366 dias. `inicio_utc` e `fim_utc` devem ser
enviados juntos. Sem período, a rota consulta os registros mais recentes de forma
paginada.

```bash
curl "{{base_url}}/v1/observacoes?estacao=EMA_VITORIA_01&estacao=EMA_SERRA_01&inicio_utc=2026-10-01T00:00:00Z&fim_utc=2026-10-02T00:00:00Z&variavel=TEMPERATURA&limite=100" \
  -H "Authorization: Bearer $TOKEN" -H "X-API-Key: $API_KEY"
```

A resposta possui `items` e `next_cursor`. Quando `next_cursor` não for nulo,
repita os mesmos filtros e envie o cursor recebido:

```text
GET /v1/observacoes?...&cursor=VALOR_DE_NEXT_CURSOR
```

Não altere nem tente interpretar o cursor.

### 10.2 `GET /v1/observacoes/ultimas`

Retorna a observação mais recente de cada combinação estação/frequência dentro dos
filtros. Não aceita período nem cursor.

| Parâmetro | Tipo | Obrigatório | Padrão/limite | Descrição |
|---|---|---|---|---|
| `estacao` | texto repetível | não | máximo 100 | Filtra uma ou mais estações. |
| `municipio_ibge` | 7 dígitos | não | - | Filtra pelo município. |
| `instituicao` | texto | não | até 30 | Filtra pela instituição mantenedora. |
| `intervalo_minutos` | inteiro | não | 1 a 10080 | Filtra a frequência. |
| `qualidade` | texto | não | até 40 | Filtra a qualidade geral. |
| `variavel` | texto repetível | não | máximo 200 | Projeta somente as variáveis indicadas. |
| `limite` | inteiro | não | padrão 100; 1 a 500 | Quantidade máxima de itens. |

```bash
curl "{{base_url}}/v1/observacoes/ultimas?estacao=EMA_VITORIA_01&variavel=TEMPERATURA&limite=100" \
  -H "Authorization: Bearer $TOKEN" -H "X-API-Key: $API_KEY"
```

## 11. Formato das observações

Cada item inclui, entre outros campos:

- estação, município e instituição mantenedora;
- frequência e `intervalo_minutos`;
- `data_hora_utc`;
- layout e qualidade geral;
- objeto `dados`, com as variáveis meteorológicas;
- lista `flags`, com alertas de qualidade por variável.

## 12. Respostas HTTP

| HTTP | Interpretação e ação |
|---|---|
| 200 | Requisição concluída. |
| 401 | JWT ou X-API-Key ausente, inválido, expirado ou revogado. Solicite novo JWT e confirme a chave. |
| 403 | Scope, instituição ou estação não autorizada. Não tente contornar; contate a administração. |
| 404 | Recurso ou estação não encontrado. |
| 422 | Parâmetro inválido ou combinação de filtros inconsistente. |
| 429 | Limite de requisições excedido. Aguarde o tempo indicado por `Retry-After`. |
| 503 | Oracle ou controle de acesso temporariamente indisponível. Tente novamente com espera progressiva. |

## 13. Boas práticas de integração

- Reutilize o JWT até próximo da expiração e obtenha outro quando necessário.
- Nunca solicite um token novo para cada chamada de dados.
- Use `limite` e paginação; não faça consultas enormes em paralelo.
- Respeite HTTP 429 e o cabeçalho `Retry-After`.
- Implemente retentativa com espera progressiva apenas para falhas temporárias.
- Armazene `client_secret` e X-API-Key em mecanismo de segredos, nunca no código.
- Registre o `X-Request-ID` retornado para facilitar o suporte, sem registrar credenciais.

## 14. Checklist do consumidor

- [ ] Recebi URL base, `client_id`, `client_secret` e X-API-Key por canais seguros.
- [ ] Consigo obter JWT com `simet:read`.
- [ ] Envio `Authorization` e `X-API-Key` nas rotas de dados.
- [ ] Consigo consultar `/v1/estacoes` e somente vejo estações autorizadas.
- [ ] Minha paginação reutiliza `next_cursor` sem alterá-lo.
- [ ] Minha aplicação trata 401, 403, 429 e 503.
- [ ] Nenhuma credencial aparece no código, Git ou logs.
