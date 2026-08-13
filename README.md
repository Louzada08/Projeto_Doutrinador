# Projeto Doutrinador

Fundação executável da Inteligência Artificial de apoio ao estudo da Doutrina do Amanhecer.

## Início rápido

Na primeira execução da versão 0.4, instale as dependências:

```powershell
.\instalar.ps1
```

No Windows, clique com o botão direito em `iniciar.ps1` e escolha **Executar com PowerShell**, ou execute no terminal:

```powershell
.\iniciar.ps1
```

Depois abra `http://127.0.0.1:8000`. A documentação FastAPI fica em `http://127.0.0.1:8000/docs`.

## Princípio

> O Doutrinador não cria Doutrina. Ele pesquisa, organiza, relaciona e explica aquilo que encontra fundamento nas fontes doutrinárias autorizadas.

Esta versão só responde quando encontra trechos relacionados no acervo cadastrado. Quando não encontra evidência, devolve a mensagem de insuficiência definida pela Constituição.

## Arquitetura

- `domain`: documentos, níveis de fonte, citações e respostas;
- `application`: casos de uso e contratos independentes de tecnologia;
- `infrastructure`: armazenamento SQLite persistente e recuperador lexical inicial;
- `presentation`: API HTTP;
- `tests`: testes das regras constitucionais essenciais.

O recuperador em memória é deliberadamente substituível. Nas próximas etapas, poderá ser trocado por persistência documental, embeddings e banco vetorial sem alterar os casos de uso.

## Executar

No diretório `doutrinador`, use Python 3.11 ou superior:

```powershell
$env:PYTHONPATH="src"
python -m doutrinador.presentation.api
```

A aplicação ficará disponível em `http://127.0.0.1:8000`. O banco será criado automaticamente em `data/doutrinador.db`.

## Rotas

### Verificar serviço

```http
GET /health
```

### Cadastrar documento

```http
POST /documents
Content-Type: application/json

{
  "title": "Documento autorizado",
  "author": "Autoria",
  "source_level": "A",
  "content": "Conteúdo integral ou trecho autorizado.",
  "authenticity_status": "validado",
  "rights_status": "autorizado"
}
```

### Perguntar

```http
POST /ask
Content-Type: application/json

{
  "question": "O que as fontes dizem sobre este assunto?"
}
```

### Listar documentos

```http
GET /documents
```

## Testar

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

## Estado atual

Esta é a versão `0.4.0`: FastAPI, OpenAPI/Swagger, ReDoc, validação Pydantic, página inicial, SQLite, edição auditável de metadados, classificação A-D, recuperação lexical e citações. O banco anterior é preservado. Ainda não inclui autenticação, ingestão automática de PDF, banco vetorial nem modelo generativo.
