# Relatório de revisão — Maketek / Render

## Estrutura esperada no repositório

Os ficheiros `app.py`, `requirements.txt` e `render.yaml` ficam na raiz do repositório. As pastas `templates/` e `static/` também ficam nessa mesma raiz. Não coloques tudo dentro de um documento `.txt`, `.md` ou `.html`.

## Configuração verificada

- Runtime: Python (`runtime: python`)
- Versão Python definida: 3.12.8
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app --workers 1 --threads 4 --timeout 120`
- Health check: `/health`
- Dependências declaradas em `requirements.txt`, incluindo Flask, Flask-SQLAlchemy, Flask-WTF, Gunicorn e psycopg v3
- Rotas de formulários POST verificadas para token CSRF
- Templates verificados quanto a referências `url_for` não existentes (a função `static` do Flask é válida)
- Ficheiros compilados `__pycache__/*.pyc` removidos do pacote final
- Credenciais de administrador configuradas como variáveis a preencher no Render (`sync: false`), para evitar publicar o painel sem autenticação por omissão

## Limite desta revisão

A sintaxe Python foi compilada e o YAML foi analisado. A verificação de dependências e execução real não pôde ser concluída neste ambiente porque não há acesso à Internet para instalar as bibliotecas Python. Portanto, isto é uma revisão estática, não uma garantia de que o deploy será bem-sucedido em qualquer configuração.

## Antes de usar

1. Cria/usa um repositório GitHub e coloca o conteúdo desta pasta diretamente na raiz do repositório.
2. No Render, escolhe **New → Blueprint** e liga esse repositório.
3. Quando solicitado, define `ADMIN_USERNAME` e `ADMIN_PASSWORD` como segredos fortes e únicos.
4. Confirma que o serviço está a usar o plano pretendido e consulta os logs do deploy se falhar.
5. Sem `DATABASE_URL`, a app usa SQLite. No Render Free o disco é efémero, pelo que os dados podem desaparecer. Usa apenas dados de demonstração até existir uma base de dados persistente e uma estratégia de cópias de segurança.


## Erro mostrado nos registos (9 de outubro de 2026)
A captura de ecrã mostra `failed to read dockerfile: open Dockerfile: no such file or directory`. Isso significa que o serviço Render está a usar o runtime Docker, mas o repositório não tem `Dockerfile` na raiz esperada (ou o caminho configurado está errado). Foi adicionado um `Dockerfile` baseado em `python:3.12-slim` e um `.dockerignore`. Também foi documentada a alternativa de criar um serviço via Blueprint, usando o runtime Python definido em `render.yaml`.

Validação realizada: estrutura e ficheiros de configuração revistos; a compilação Python pode ser verificada separadamente. Não foi executada uma build Docker real neste ambiente, por isso o deploy no Render continua a ser o teste final.
