# TanureFindPrice

MVP local para validar o fluxo:

```text
OAuth → products/search → catalog_product/items → filtro por moeda/preço → resultado
```

## Requisitos

- Python 3.12 ou superior
- Uma aplicação criada no Mercado Livre DevCenter
- Cloudflare Quick Tunnel para a autenticação inicial ou para uma nova autorização

## Como executar o projeto

### 1. Primeira configuração

#### Criar a aplicação no Mercado Livre

1. Acesse o Mercado Livre DevCenter e crie uma aplicação para o Mercado Livre Brasil.
2. Na página de detalhes da aplicação, localize o `Client ID` e o `Client Secret`.
3. Configure o OAuth da aplicação com:
   - Authorization Code;
   - Refresh Token;
   - PKCE;
   - Mercado Livre como site/mercado da aplicação.
4. Mantenha desabilitadas as permissões e recursos que não são necessários para este MVP.
5. Cadastre a Redirect URI HTTPS que será usada pelo Cloudflare Quick Tunnel, terminando em `/callback`.

A Redirect URI precisa ser exatamente igual em todos os lugares: no DevCenter, no arquivo `.env` e na URL enviada ao OAuth. Diferenças de protocolo, domínio, porta, caminho ou barra final podem invalidar a autorização.

#### Configurar o arquivo `.env`

Na raiz do projeto, copie `.env.example` para `.env` e preencha os valores da sua aplicação:

```env
ML_CLIENT_ID=seu_client_id
ML_CLIENT_SECRET=seu_client_secret
ML_REDIRECT_URI=https://seu-subdominio.trycloudflare.com/callback
```

O `Client Secret` é uma credencial privada. Nunca o coloque no código, no `config.json`, em commits, screenshots, mensagens ou logs. Se ele já tiver sido exposto, gere um novo secret no DevCenter.

### 2. Execução normal do projeto

Abra um terminal e vá para a pasta do projeto:

```powershell
cd C:\caminho\para\TanureFindPrice
```

Se ainda não instalou as dependências, crie o ambiente virtual e instale-as:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Em um terminal, inicie o Cloudflare Quick Tunnel:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

O Cloudflare exibirá uma URL HTTPS semelhante a:

```text
https://seu-subdominio.trycloudflare.com
```

Acrescente `/callback` para formar a Redirect URI completa:

```text
https://seu-subdominio.trycloudflare.com/callback
```

Se essa URL mudou desde a última execução do `cloudflared`, atualize:

1. a Redirect URI no Mercado Livre DevCenter;
2. `ML_REDIRECT_URI` no `.env`.

Mantenha o terminal do Cloudflare aberto. Em outro terminal, execute:

```powershell
python main.py
```

O programa escuta o callback local em `127.0.0.1:8000/callback`; o Quick Tunnel encaminha a URL HTTPS pública para esse servidor local.

### 3. Autenticação inicial

Na CLI, escolha:

```text
1 - Configurar/autenticar Mercado Livre
```

O programa irá:

1. iniciar temporariamente o servidor local de callback;
2. gerar `state` e os valores PKCE;
3. abrir o navegador na página de autorização do Mercado Livre;
4. aguardar a autorização do usuário;
5. receber o authorization code pelo callback;
6. validar o `state` recebido;
7. trocar o code por `access_token` e `refresh_token`;
8. salvar os tokens em `data/tokens.json`.

Não é necessário copiar tokens manualmente. A aplicação não exibe tokens nem `Client Secret` no terminal.

### 4. Execuções posteriores

Depois da autenticação inicial:

- o `access_token` é reutilizado enquanto estiver válido;
- o programa faz refresh automático quando necessário;
- o novo `refresh_token` substitui o anterior;
- normalmente não é necessário autenticar novamente;
- o Cloudflare Tunnel não é necessário para executar buscas já autenticadas.

Para executar uma busca posteriormente, basta iniciar:

```powershell
python main.py
```

e escolher:

```text
5 - Executar busca
```

O Cloudflare Tunnel só precisa estar ativo quando a opção de autenticação for usada, porque o callback OAuth precisa alcançar o servidor local.

Como o projeto usa Quick Tunnel, a URL pode mudar quando o `cloudflared` é reiniciado. Se isso acontecer, para autenticar novamente:

1. atualize a Redirect URI no DevCenter;
2. atualize `ML_REDIRECT_URI` no `.env`;
3. mantenha o novo túnel aberto;
4. escolha novamente `1 - Configurar/autenticar Mercado Livre`.

Uma mudança de URL não invalida automaticamente tokens já salvos, mas a URL correta é obrigatória para uma nova autorização.

### 5. Quando o token precisa ser renovado

Quando o `access_token` expira, o programa tenta renová-lo automaticamente usando o `refresh_token` salvo.

Não altere tokens manualmente normalmente. O Mercado Livre retorna um novo `refresh_token` durante o refresh, e o programa substitui o anterior em `data/tokens.json`.

Será necessária uma nova autorização se o refresh token estiver:

- inválido;
- expirado;
- revogado;
- já utilizado ou substituído por outro token.

Nesse caso:

1. inicie o Cloudflare Quick Tunnel;
2. confirme que a Redirect URI do DevCenter e do `.env` está correta;
3. execute `python main.py`;
4. escolha `1 - Configurar/autenticar Mercado Livre`.

## Funcionamento da busca

O programa pesquisa produtos de catÃ¡logo e depois seus anÃºncios vinculados:

```text
GET /products/search?status=active&site_id=MLB&q=...&limit=20
        ↓
GET /products/{catalog_product_id}/items
```

SÃ£o mantidos somente resultados com `currency_id == BRL` e `price <= target_price`. Os anÃºncios sÃ£o deduplicados por `item_id` e ordenados pelo menor preÃ§o. A saÃ­da inclui `price`, `item_id`, `seller_id`, `condition`, `listing_type_id` e `catalog_product_id`.

O programa nÃ£o usa `/sites/MLB/search`, `/items/{item_id}` ou `sale_price` neste fluxo.

O MVP não calcula cupons, frete, cashback, benefícios personalizados, preço de checkout ou preço por quantidade.

## Anúncios de um produto de catálogo

A CLI tambÃ©m permite consultar anÃºncios vinculados a um produto de catÃ¡logo usando a opÃ§Ã£o `6 - Buscar anÃºncios por catalog_product_id`.

Essa opção usa a seguinte rota REST:

```text
GET /products/{catalog_product_id}/items?limit=100&offset=0
```

Ela usa o access token OAuth existente e retorna, quando o Mercado Livre disponibiliza vencedores:

- `item_id`;
- `price`;
- `currency_id`;
- `seller_id`;
- `listing_type_id`;
- outros campos devolvidos pela API.

Essa rota foi identificada na implementação pública [`getCatalogProductItems`](https://github.com/paulononaka/mcp-mercado-livre/blob/main/src/actions.ts). Ela usa a API REST do Mercado Livre; não usa scraping, GraphQL ou dependências do MCP.

O endpoint não está descrito nas páginas oficiais atualmente usadas pelo projeto e deve ser tratado como recurso não documentado. O Mercado Livre pode retornar `404 No winners found` mesmo quando `/products/{catalog_product_id}` existe. Nesse caso, não há anúncios vencedores disponíveis para esse catálogo através dessa rota; o programa informa a situação e não inventa `ITEM_ID`s.

Para testar o catálogo `MLB22598384`, escolha a opção de consulta e informe esse ID. A resposta pode variar conforme a disponibilidade atual de anúncios vencedores.

## Solução de problemas

| Problema | O que verificar |
|---|---|
| Credenciais ausentes | Confirme se `.env` existe na raiz e contém `ML_CLIENT_ID`, `ML_CLIENT_SECRET` e `ML_REDIRECT_URI`. |
| Redirect URI inválida | Confirme que a URL é HTTPS, termina em `/callback` e é idêntica no DevCenter e no `.env`. |
| URL do Cloudflare mudou | Atualize a Redirect URI no DevCenter e `ML_REDIRECT_URI`; depois faça a autenticação novamente. |
| HTTP 401 | O access token expirou ou não é válido. O programa tenta refresh; se falhar, faça nova autenticação. |
| Refresh token inválido | Inicie o túnel, corrija a Redirect URI e use novamente a opção de autenticação. |
| Cloudflare Tunnel não está rodando | Inicie `cloudflared tunnel --url http://127.0.0.1:8000` antes de autenticar. |
| Porta 8000 ocupada | Encerre o processo que usa a porta e tente novamente. O callback do programa usa `127.0.0.1:8000`. |
| Erro de conexão | Verifique internet, Cloudflare, firewall e se a API do Mercado Livre está acessível. |
| O navegador não abre | Copie a URL de autorização exibida pelo ambiente ou abra manualmente em um navegador; mantenha o programa aguardando o callback. |
| Callback não chega | Confirme que o túnel encaminha para `http://127.0.0.1:8000` e que o caminho público termina em `/callback`. |

## Segurança

- Nunca faça commit de `.env`.
- Nunca faça commit de `data/tokens.json`.
- Nunca publique `Client Secret`, `access_token` ou `refresh_token`.
- Não coloque tokens em `config.json`.
- Confirme que `.env` e `data/tokens.json` estão listados no `.gitignore`.
- Restrinja o acesso local aos arquivos que contêm credenciais.

O arquivo `data/config.json` contém apenas produtos e configurações da busca. Os tokens ficam separados em `data/tokens.json`.

## Uso rápido

Primeira autenticação:

```powershell
cd C:\caminho\para\TanureFindPrice
.\.venv\Scripts\Activate.ps1
cloudflared tunnel --url http://127.0.0.1:8000
```

Em outro terminal:

```powershell
cd C:\caminho\para\TanureFindPrice
.\.venv\Scripts\Activate.ps1
python main.py
```

Escolha `1 - Configurar/autenticar Mercado Livre`.

Execuções posteriores, com tokens válidos:

```powershell
cd C:\caminho\para\TanureFindPrice
.\.venv\Scripts\Activate.ps1
python main.py
```

Escolha `5 - Executar busca`. Nessa situação, o Cloudflare Tunnel normalmente não precisa estar ativo.

## Arquivos

- `data/config.json`: produtos e limites de busca.
- `data/tokens.json`: access token, refresh token e dados de expiração; não deve ser compartilhado.
- `.env`: credenciais da aplicação e Redirect URI; não deve ser commitado.

## Testes

```powershell
python -m unittest discover -s tests -v
```

Os testes usam respostas simuladas e não fazem chamadas reais ao Mercado Livre.

## Limitações do MVP

Este MVP não implementa polling automático, banco de anúncios, histórico, vendedores, reputação, deduplicação, alertas, Telegram, frete, cashback, cupons ou preço de checkout.

## Documentação oficial

- [Itens e buscas](https://developers.mercadolivre.com.br/itens-e-buscas)
- [API de preços](https://developers.mercadolivre.com.br/pt_br/api-de-precos)
- [Autenticação e autorização](https://developers.mercadolivre.com.br/autenticacao-e-autorizacao)
