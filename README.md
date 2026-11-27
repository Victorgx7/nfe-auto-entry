# NFe Auto Entry

Automação em Python para ler arquivos XML de NF-e e auxiliar no preenchimento de informações em um sistema web usando Playwright.

> Projeto demonstrativo. Não inclua XMLs reais, dados fiscais, credenciais, certificados ou informações de clientes neste repositório.

## Tecnologias

- Python
- CustomTkinter
- Playwright
- xmltodict
- python-dotenv

## Requisitos

- Python 3.10+
- Navegador Chromium instalado pelo Playwright
- Acesso autorizado ao sistema de destino

## Configuração

1. Crie e ative um ambiente virtual.
2. Instale as dependências:

```bash
pip install -r requirements.txt
playwright install chromium
```

3. Opcionalmente, copie `.env.example` para `.env` e ajuste as URLs do seu ambiente autorizado:

| Variável | Descrição |
|---|---|
| `GDOOR_BASE_URL` | Origem do sistema, por exemplo `https://app.gdoorweb.com.br` |
| `GDOOR_PRODUCTS_URL` | Endereço da tela de cadastro de produtos |

O usuário informa email e senha na tela de login ao abrir o aplicativo. Essas credenciais não são lidas nem armazenadas no `.env`.

## Arquivos XML

Na tela de consulta de produtos, use **Adicionar XML às Notas** para validar um XML de NF-e e copiá-lo para `notasXMLs/`; o original permanece no local escolhido. Uma cópia idêntica não é duplicada e arquivos diferentes com o mesmo nome recebem um sufixo. Essa pasta é ignorada pelo Git para evitar a publicação de documentos fiscais. O cadastro de produtos também permite selecionar um XML diretamente.

Use somente arquivos fictícios ou dados devidamente anonimizados em demonstrações.

## Estrutura

- `main.py`: ponto de entrada e menu da aplicação.
- `src/nfe/`: leitura, interpretação e armazenamento local dos XMLs.
- `src/browser/`: autenticação e automação com Playwright.
- `tests/`: testes automatizados do parser e da lógica de importação.
- `notasXMLs/`: arquivos XML locais; não são enviados ao repositório.
- `dist/` e `build/`: artefatos gerados pelo empacotamento.

## Execução

```bash
python main.py
```

Depois de abrir o Gdoor:

- **Consultar produtos no sistema**: consulta os itens dos XMLs em `notasXMLs/` e mostra o progresso, a quantidade consultada e quantos não foram encontrados.
- **Cadastrar produtos**: selecione um XML. A aplicação processa os produtos do arquivo, preenche os campos de cadastro e aciona Salvar. Não há verificação automática de duplicidade; confira os produtos e os resultados no Gdoor.
- **Importar nota**: informe o identificador da nota. A aplicação lê os XMLs de `notasXMLs/` e preenche a nota no sistema. Revise as informações e salve manualmente no Gdoor.

## Executável independente (Windows)

O arquivo `NFeAutoEntry.spec` gera um único `.exe` contendo a aplicação, as dependências Python e o Chromium do Playwright. Execute os comandos abaixo na pasta raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean .\NFeAutoEntry.spec
```

O resultado será `dist\NFeAutoEntry.exe`. A pessoa que usar o programa precisa baixar somente esse executável; email e senha são informados na tela de login. Como o navegador vai dentro do arquivo, o `.exe` será grande.

## Testes

Execute os testes automatizados com:

```bash
python -m unittest discover -s tests -v
```

## Segurança

- Credenciais são lidas de variáveis de ambiente.
- Arquivos `.env`, XMLs fiscais e certificados são ignorados pelo Git.
- Nunca reutilize senhas de produção em projetos de demonstração.
- A automação deve ser utilizada somente em sistemas e contas para os quais você tenha autorização.

## Aviso

Este projeto é fornecido para fins de estudo e demonstração. Ajustes nos seletores e no fluxo podem ser necessários conforme a versão do sistema utilizado.
