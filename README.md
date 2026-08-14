# Projeto Doutrinador

Sistema de apoio ao estudo da Doutrina do Amanhecer, com respostas explicativas
fundamentadas exclusivamente no acervo autorizado.

> O Doutrinador não cria Doutrina. Ele pesquisa, organiza, relaciona e explica
> aquilo que encontra fundamento nas fontes doutrinárias autorizadas.

## Versão 0.6 — Fontes visuais e interação por voz

A versão 0.6 acrescenta uma referência de imagem opcional a cada fonte e
recursos de acessibilidade por voz:

- `image_url` guarda somente o endereço HTTP ou HTTPS onde a imagem permanece
  arquivada; o banco não copia o arquivo;
- `image_description` oferece texto alternativo para leitores de tela;
- a imagem acompanha o documento, os trechos indexados e as citações, sendo
  exibida no acervo, na resposta e na janela **Abrir trecho exato**;
- **Ouvir instruções** e **Ouvir resposta** usam a síntese de voz do navegador;
- **Fazer pergunta por voz** reconhece a fala em português, envia a pergunta e
  lê a resposta automaticamente.

Os controles detectam a disponibilidade dos recursos de voz e continuam
permitindo o uso por texto quando eles não existem. O navegador solicitará
permissão para o microfone. O servidor do Doutrinador não armazena o áudio;
dependendo do navegador, o reconhecimento pode usar o serviço de voz do seu
fornecedor.

Use apenas endereços de imagem confiáveis: a imagem é carregada diretamente do
servidor informado. A descrição da imagem deve transmitir o que nela é
doutrinariamente relevante sem acrescentar interpretações não documentadas.

## Versão 0.5 — Respostas Doutrinárias com RAG

A versão 0.5 implementa recuperação aumentada por geração (RAG). O acervo é
consultado no momento da pergunta e continua sendo a única base de conhecimento
autorizada. Os documentos **não são usados para treinar uma IA**.

O fluxo é:

1. dividir cada fonte em trechos, preservando título, seção e página;
2. combinar busca lexical BM25 e similaridade semântica vetorial;
3. selecionar os trechos mais relevantes, respeitando a precedência A–D;
4. gerar uma explicação limitada aos trechos recuperados;
5. verificar os identificadores das citações e recusar respostas sem fundamento;
6. registrar pergunta, trechos consultados e resposta para auditoria.

A Constituição do Doutrinador fica em
`src/doutrinador/constitution.py` e é sempre enviada ao modelo como instrução
de sistema. Trechos recuperados são tratados como dados não confiáveis, para que
instruções eventualmente contidas nas fontes não alterem essas regras.

## Instalação e execução

Use Python 3.11 ou superior:

```powershell
.\instalar.ps1
.\iniciar.ps1
```

Ou execute diretamente:

```powershell
$env:PYTHONPATH="src"
python -m doutrinador.presentation.api
```

A aplicação fica em `http://127.0.0.1:8000`; Swagger e ReDoc ficam em
`/docs` e `/redoc`. O banco é criado automaticamente em
`data/doutrinador.db`. Bancos das versões anteriores são migrados e indexados
sem perda dos documentos existentes.

### Provedor de LLM

Sem uma chave, a aplicação usa um gerador extrativo local e auditável. Para
habilitar respostas explicativas pela Responses API da OpenAI:

```powershell
$env:OPENAI_API_KEY="sua-chave"
$env:DOUTRINADOR_LLM_MODEL="gpt-5.6-luna"  # opcional
.\iniciar.ps1
```

A chave não deve ser gravada no repositório. O modelo recebe apenas a pergunta,
a Constituição e os trechos selecionados; nenhuma ferramenta de internet é
oferecida ao gerador.

## Preservar seções e páginas

Quebras de formulário no texto avançam a página. Extrações também podem usar
marcadores explícitos e cabeçalhos Markdown:

```text
[[PÁGINA: 12]]
# Livre-arbítrio
Texto da seção...

[[SEÇÃO: Responsabilidade]]
Continuação na mesma página...
```

Cada citação devolve um `passage_id` e um `source_url`. Na interface, o botão
**Abrir trecho exato** mostra o mesmo texto efetivamente entregue ao gerador,
com sua seção e página.

## Rotas principais

- `GET /health`: estado, versão e modo de geração;
- `POST /documents`: cadastra e indexa uma fonte;
- `GET /documents`: lista o acervo;
- `GET /documents/{id}/passages`: lista os trechos indexados;
- `GET /passages/{id}`: abre um trecho exato;
- `POST /ask`: pesquisa e responde com citações verificadas;
- `GET /interactions`: consulta o log auditável;
- `PUT /documents/{id}` e `GET /documents/{id}/history`: governança de metadados.

Quando o acervo não sustenta a pergunta, a resposta é:

> Não encontrei fundamento suficiente nas fontes doutrinárias disponíveis
> para responder a essa questão com segurança.

## Testes

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

`tests/fixtures/doctrinal_questions.json` contém as perguntas doutrinárias
pré-avaliadas. A suíte também cobre recuperação lexical e semântica,
localização de trechos, recusa por evidência insuficiente, citações inválidas,
migração, persistência e auditoria.
Também são verificados URLs de imagem, propagação visual nas citações e a
presença dos controles de acessibilidade por voz.

## Arquitetura

- `domain`: documentos, passagens, citações e respostas;
- `application`: casos de uso e contratos independentes de tecnologia;
- `infrastructure`: chunking, busca híbrida, SQLite e provedores de resposta;
- `presentation`: API FastAPI e interface web;
- `tests`: regras constitucionais, integração e avaliações doutrinárias.
