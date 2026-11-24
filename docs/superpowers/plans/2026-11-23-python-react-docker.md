# Python + React em Docker — plano de implementação

**Objetivo:** substituir a interface Streamlit por FastAPI + React sem alterar os cálculos de chuva, as fontes ou as regras do ranking.

**Arquitetura:** o backend reutiliza `app/dataCollector.py`, `Joiner`, configurações e coordenadas existentes. Uma coleta em segundo plano abastece um snapshot em memória com TTL; o frontend React consulta uma API JSON, preservando a última leitura durante atualizações. Docker Compose sobe API e frontend; nginx serve o build React e encaminha `/api` e `/assets` ao backend.

**Visual:** identidade CEPDEC com laranja, cinza e bege da imagem fornecida, usando o símbolo já existente em `img/logo_cepdec.png`; mapa, ranking, listas e status continuam disponíveis.

## Etapas

- [x] Criar serviço de coleta desacoplado do Streamlit, com serialização JSON, status por fonte e cache/atualização protegidos contra coletas duplicadas.
- [x] Criar endpoints FastAPI de saúde e dashboard, com testes sem chamadas externas.
- [x] Criar frontend React responsivo com mapa, filtros, ranking, listas, avisos e estado de carregamento.
- [x] Criar Dockerfiles e Compose, documentar segredos e execução.
- [x] Rodar testes, build, Compose e verificar os endpoints e a interface localmente.

## Restrições

- Nenhuma credencial no frontend, no repositório ou nas imagens Docker.
- A lista geral mantém registros repetidos e limite visual de 60.
- O ranking principal mantém apenas o maior acumulado por município.
- Uma falha de fonte não pode impedir a apresentação das outras.
- Esta experiência permanece isolada na branch `pyhton_react`.
