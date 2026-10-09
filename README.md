# Maketek — Gestão inteligente de stock

Maketek é uma aplicação web em português, com verde como cor principal, pensada para pequenos negócios e lojas. Este pacote inclui a aplicação Flask, modelos de dados, templates, estilos, segurança básica e configuração de implantação no Render.

## Funcionalidades incluídas

- Painel com produtos ativos, unidades, valor estimado ao custo e alertas de stock baixo.
- Cadastro e edição de produtos com SKU único, categoria, localização, unidade, fornecedor, custo, preço, mínimo, máximo e notas.
- Movimentações de entrada, saída e contagem física, guardando saldo anterior, saldo posterior, variação, motivo, referência, operador e data.
- Bloqueio de saídas que deixariam o saldo negativo.
- Arquivo lógico de produtos sem apagar o histórico.
- Pesquisa e filtros por nome, SKU, fornecedor, categoria e estado do stock.
- Exportação CSV do catálogo e do histórico de movimentações.
- Proteção CSRF nos formulários, sessão com cookies HttpOnly/SameSite e login opcional via variáveis de ambiente.
- Endpoint `/health` para verificação do serviço.
- Valores apresentados em AOA por defeito.

## Colocar no Render sem pagar

1. Descompacta este ZIP no telemóvel/computador.
2. Envia todos os ficheiros e pastas para um repositório GitHub.
3. No Render, escolhe **New → Blueprint** e liga o repositório que contém `render.yaml`.
4. Confirma que o serviço usa o plano **Free**.
5. Em Environment, define `ADMIN_USERNAME` e `ADMIN_PASSWORD` com valores fortes. O `SECRET_KEY` é gerado pelo Blueprint.
6. Faz o deploy e abre o endereço `onrender.com`.
7. Para experimentar, abre `/demo` uma vez para carregar produtos de exemplo. Depois podes criar os teus próprios produtos.

Comandos alternativos se criares o serviço manualmente:
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app --workers 1 --threads 4 --timeout 120`
- **Health Check Path:** `/health`
- **Runtime:** Python 3

## Atenção aos limites do plano gratuito do Render

O serviço web gratuito pode adormecer após 15 minutos sem tráfego e demorar cerca de um minuto a voltar. O sistema de ficheiros é efémero: a base de dados SQLite local pode perder os dados em reinícios, spin-down ou novos deploys. A base de dados PostgreSQL gratuita do Render expira após 30 dias e não oferece backups no plano gratuito. Por isso, a configuração deste pacote **não cria automaticamente uma base de dados Render paga nem gratuita**.

**Usa a instalação Render Free como demonstração, com dados de teste. Não uses este armazenamento SQLite em Render Free para o inventário oficial de uma empresa.** Para dados reais, liga uma base de dados PostgreSQL com persistência e backups adequados, adicionando a respetiva `DATABASE_URL` nas variáveis de ambiente. Confirma sempre os limites e condições atuais do fornecedor antes de guardar dados importantes. O código aceita `DATABASE_URL` PostgreSQL e utiliza o driver psycopg v3.

## Segurança e configuração

- Sem `ADMIN_USERNAME` e `ADMIN_PASSWORD`, o sistema funciona sem autenticação, em modo de demonstração. **Não publiques dados reais neste modo.**
- Nunca guardes palavras-passe no código ou no repositório. Define-as no painel Environment do Render.
- O segredo `SECRET_KEY` deve ser aleatório e privado.
- A autenticação incluída é um único administrador, não um sistema multiempresa ou permissões por equipa.
- O CSV exportado pode conter informação comercial. Guarda-o num local privado.
- Faz testes com dados fictícios antes de usar a aplicação numa operação real.

## Executar localmente

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abre `http://127.0.0.1:8000`. Localmente, os dados ficam em SQLite no ambiente da aplicação. Para ativar login local, define `ADMIN_USERNAME`, `ADMIN_PASSWORD` e `SECRET_KEY` no ambiente ou usa um `.env` com python-dotenv instalado localmente (não incluído nem necessário no Render).

## Estrutura

```text
Maketek/
├── app.py
├── requirements.txt
├── render.yaml
├── .env.example
├── .gitignore
├── README.md
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── login.html
│   ├── product_form.html
│   ├── movement_form.html
│   ├── movements.html
│   └── error.html
└── static/
    ├── style.css
    └── app.js
```

## Limites conhecidos desta versão

Esta é uma versão inicial funcional, não um ERP completo. Não inclui sincronização WhatsApp, faturação fiscal, integrações bancárias, leitor de código de barras, compras/vendas integradas, previsão de procura, multiempresa, múltiplos utilizadores/perfis, backups automáticos nem migrações de esquema. Estas funções exigem planeamento e testes específicos.
