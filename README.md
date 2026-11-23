# NFe Auto Entry

Automação em Python para ler arquivos XML de NF-e e auxiliar no preenchimento de informações em um sistema web usando Playwright.

> Projeto demonstrativo. Não inclua XMLs reais, dados fiscais, credenciais, certificados ou informações de clientes neste repositório.

## Tecnologias

- Python
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

3. Copie `.env.example` para `.env`.
4. Preencha as variáveis no arquivo `.env` com os dados do seu ambiente autorizado:

| Variável | Descrição |
|---|---|
| `GDOOR_BASE_URL` | Endereço base do sistema |
| `GDOOR_PRODUCTS_URL` | Endereço da tela de cadastro de produtos |
| `GDOOR_EMAIL` | Usuário de acesso |
| `GDOOR_PASSWORD` | Senha de acesso |

O arquivo `.env` é ignorado pelo Git e não deve ser enviado ao repositório.

## Arquivos XML

Coloque os XMLs de teste na pasta `notasXMLs/`. Essa pasta é ignorada pelo Git para evitar a publicação de documentos fiscais.

Use somente arquivos fictícios ou dados devidamente anonimizados em demonstrações.

## Estrutura

- `main.py`: ponto de entrada e menu da aplicação.
- `src/nfe/`: leitura e interpretação dos arquivos XML.
- `src/browser/`: autenticação e automação com Playwright.
- `tests/`: testes automatizados do parser XML.
- `notasXMLs/`: arquivos XML locais; não são enviados ao repositório.
- `dist/` e `build/`: artefatos gerados pelo empacotamento.

## Execução

```bash
python main.py
```

O programa solicita o identificador da nota e abre o navegador para realizar o preenchimento. Revise todas as informações no sistema antes de salvar.

## Segurança

- Credenciais são lidas de variáveis de ambiente.
- Arquivos `.env`, XMLs fiscais e certificados são ignorados pelo Git.
- Nunca reutilize senhas de produção em projetos de demonstração.
- A automação deve ser utilizada somente em sistemas e contas para os quais você tenha autorização.

## Aviso

Este projeto é fornecido para fins de estudo e demonstração. Ajustes nos seletores e no fluxo podem ser necessários conforme a versão do sistema utilizado.
