# Projeto Doutrinador

Sistema de apoio ao estudo da Doutrina do Amanhecer, com respostas explicativas
fundamentadas exclusivamente no acervo autorizado.

> O Doutrinador não cria Doutrina. Ele pesquisa, organiza, relaciona e explica
> aquilo que encontra fundamento nas fontes doutrinárias autorizadas.

## Versão 0.7 — HTTPS na rede local e microfone

A correção 0.7.1 acrescenta acesso simultâneo pela rede local e pela VPN
WireGuard, com certificado válido para os dois endereços e regra de firewall
restrita à sub-rede VPN.

A versão 0.7 serve o Doutrinador em:

```text
https://192.168.10.105:8000
```

O HTTPS é necessário para que navegadores tratem a aplicação como contexto
seguro e liberem o microfone. O inicializador gera uma autoridade certificadora
local e um certificado de servidor com os endereços `192.168.10.105`,
`10.66.66.1`, `127.0.0.1` e o nome `localhost`. A autoridade precisa ser instalada como confiável em **cada
dispositivo cliente**; simplesmente ignorar o aviso do navegador pode não
liberar o microfone.

Para navegadores com reconhecimento de fala nativo, ele continua sendo usado.
Nos demais navegadores modernos com `getUserMedia` e `MediaRecorder`, a interface
grava até 15 segundos e envia o áudio ao endpoint `/voice/transcribe`. O áudio
é mantido apenas em memória, não é gravado no banco nem em disco, e é enviado
ao provedor OpenAI para transcrição quando a chave está configurada.

"Qualquer navegador" significa aqui navegadores modernos que implementem captura
de áudio. Dispositivos muito antigos ou administrados por políticas que bloqueiam
o microfone continuarão sem acesso a esse recurso.

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
.\instalar_certificado_windows.ps1
.\iniciar.ps1
```

`instalar.ps1` cria um ambiente virtual `.venv`, evitando conflitos com a
instalação global do Python. `instalar_certificado_windows.ps1` pede confirmação
antes de confiar na autoridade local para o usuário atual.

Para permitir acesso de outros equipamentos, abra o PowerShell como
Administrador e execute uma vez:

```powershell
.\configurar_firewall_windows.ps1
```

A configuração cria uma regra para a sub-rede local no perfil **Privado** e outra
regra restrita à rede VPN `10.66.66.0/24`, válida mesmo quando o adaptador
WireGuard está classificado como rede Pública. Recomenda-se reservar
`192.168.10.105` para o computador servidor no DHCP do roteador.

### Acesso fora da rede local pela VPN WireGuard

Com a configuração padrão deste projeto, use:

```text
Notebook servidor: 10.66.66.1
Celular Android:    10.66.66.2
Endereço no celular: https://10.66.66.1:8000
```

No notebook, o par do celular deve ter `AllowedIPs = 10.66.66.2/32`. No celular,
o par do notebook deve ter `AllowedIPs = 10.66.66.0/24` (ou, no mínimo,
`10.66.66.1/32`) e `PersistentKeepalive = 25`. O `Endpoint` do celular deve ser o
IP público ou domínio dinâmico da residência e a porta UDP usada pelo WireGuard.
No roteador, essa porta UDP precisa ser encaminhada ao notebook
`192.168.10.105`.

Depois de atualizar esta versão:

1. encerre o Doutrinador;
2. execute `iniciar.ps1`; a primeira execução desta atualização renova o
   certificado para incluir os dois endereços;
3. execute `configurar_firewall_windows.ps1` como Administrador;
4. instale o novo `data\certificates\doutrinador-ca.crt` no Android;
5. ative o WireGuard no celular e abra `https://10.66.66.1:8000`.

Se o WireGuard não mostrar uma negociação recente quando o celular estiver no
4G/5G, o problema ocorre antes do Doutrinador. Verifique o encaminhamento UDP,
o endereço público configurado no `Endpoint` e se o provedor residencial usa
CGNAT. Não exponha diretamente a porta TCP 8000 no roteador: o acesso externo
deve passar pelo túnel VPN.

Os endereços podem ser alterados antes da execução:

```powershell
$env:DOUTRINADOR_HTTPS_IP="192.168.10.105"
$env:DOUTRINADOR_VPN_IP="10.66.66.1"
$env:DOUTRINADOR_VPN_NETWORK="10.66.66.0/24"
```

### Confiar no certificado em outros dispositivos

Depois da primeira instalação, transfira apenas este arquivo aos dispositivos:

```text
data\certificates\doutrinador-ca.crt
```

Instale-o no repositório de autoridades certificadoras confiáveis do sistema ou
do navegador e reinicie o navegador. Em outro computador Windows, copie o
arquivo e importe-o em **Usuário Atual → Autoridades de Certificação Raiz
Confiáveis**. Android, iOS, macOS e Firefox podem exigir a importação manual nas
configurações de certificados.

Nunca compartilhe `doutrinador-server.key`: ele é a chave privada do servidor.

### Transcrição para navegadores sem reconhecimento nativo

Configure uma chave no mesmo PowerShell antes de iniciar:

```powershell
$env:DOUTRINADOR_TRANSCRIPTION_API_KEY="sua-chave"
.\iniciar.ps1
```

Se `OPENAI_API_KEY` já estiver configurada, ela também será aceita. A chave fica
somente no servidor e nunca é enviada ao navegador. O modelo padrão é
`gpt-4o-mini-transcribe`; pode ser alterado com
`DOUTRINADOR_TRANSCRIPTION_MODEL`.

Para desenvolvimento estritamente local, ainda é possível executar diretamente:

```powershell
$env:PYTHONPATH="src"
python -m doutrinador.presentation.api
```

A aplicação principal fica em `https://192.168.10.105:8000`; Swagger e ReDoc
ficam em `/docs` e `/redoc`. O banco é criado automaticamente em
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
- `GET /voice/capabilities`: suporte e limites da interação por voz;
- `POST /voice/transcribe`: recebe áudio e devolve a pergunta transcrita;
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
