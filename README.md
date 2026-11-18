# MedAgenda

Aplicação web para gerenciar um consultório médico: cadastro de pacientes e profissionais, disponibilidade de horários e agendamento de consultas, com autenticação e dois perfis de acesso.

## Funcionalidades

**Cliente** (cria a própria conta pela tela pública)
- Consulta os profissionais e os horários livres, com filtro por profissional, especialidade e data
- Agenda, remarca e cancela as próprias consultas
- Acompanha o histórico dos próprios agendamentos
- Consulta e atualiza o próprio cadastro

**Recepcionista** (administrador)
- Cadastra e edita pacientes, com busca por nome ou CPF
- Cadastra e edita profissionais e especialidades, com o vínculo N:N entre eles
- Gera os horários de atendimento de cada profissional
- Agenda para qualquer paciente (informando o CPF), remarca, cancela e conclui atendimentos
- Consulta todos os agendamentos, com filtro por status e busca por paciente

Os profissionais não fazem login: existem apenas como cadastro. A recepcionista nunca se cadastra pela tela pública: é criada por um comando (veja abaixo).

## Tecnologias

- Python e Flask 3.1
- Flask-SQLAlchemy / SQLAlchemy 2.1, Flask-Migrate (Alembic)
- Flask-Login (sessão) e Flask-WTF (proteção CSRF)
- PostgreSQL 18, driver `psycopg2-binary`
- HTML, Jinja2 e Bootstrap 5.3 (via CDN), com tema próprio em `app/static/css/medagenda.css`

## Arquitetura

O código segue três camadas:

```
routes (blueprints)  ->  services  ->  models
```

- **routes:** recebem a requisição, chamam o service e traduzem o resultado em tela, `flash` ou erro HTTP.
- **services:** concentram as regras de negócio e a autorização. Não importam nada do Flask. Recebem o usuário como parâmetro e sinalizam problemas com `ErroDeNegocio`, `NaoEncontrado` e `AcessoNegado`.
- **models:** entidades SQLAlchemy e constraints do banco.

### Decisões de segurança

- A autorização é conferida **no service**, e não só na rota ou no HTML. Esconder um botão é conforto; a regra real fica no service.
- Cada registro é protegido por dono (`obter`), o que evita IDOR: um cliente não abre nem altera o agendamento de outro.
- No agendamento por cliente, o CPF vindo do formulário é ignorado: o paciente é sempre o do usuário logado.
- Senhas guardadas com hash (scrypt, via Werkzeug). Logout apenas por `POST`. Todo `POST` exige token CSRF.
- O redirecionamento pós-login valida o parâmetro `next`.
- Buscas com `ilike` escapam os curingas `%` e `_`.
- A constraint do banco é a barreira final contra corrida (todo `commit` trata `IntegrityError`).

## Regras de negócio

**Disponibilidade**
- Cada linha é um horário agendável. A recepção informa dia, início, fim e duração, e o sistema gera os horários.
- Duração entre 10 e 120 minutos, no máximo 48 horários por geração, e a duração precisa dividir o intervalo.
- Não há sobreposição de horários do mesmo profissional no mesmo dia, nem horários no passado.
- Um horário só pode ser removido se nunca teve agendamento (nem cancelado).

**Agendamento**
- Criar: o horário precisa estar livre e no futuro. Agendamento e horário mudam na mesma transação, com `SELECT ... FOR UPDATE` no horário.
- Existe no máximo um agendamento ativo por horário (índice único parcial no PostgreSQL).
- O mesmo paciente não pode ter dois agendamentos ativos que se sobreponham, nem com médicos diferentes.
- Cancelar: só `AGENDADO` que ainda não começou. O horário volta a ficar disponível.
- Remarcar: só `AGENDADO` futuro, e só para outro horário **do mesmo profissional**. O agendamento antigo vira `REMARCADO` e nasce um novo `AGENDADO`.
- Concluir: só a recepção, e só depois do início do horário.
- Não há exclusão de registros: o histórico é preservado.

## Como rodar (Windows, PowerShell)

Pré-requisitos: Python, PostgreSQL e Git.

1. Clone o repositório:

```powershell
git clone https://github.com/VinitsDev/MedAgenda.git
cd MedAgenda
```

2. Crie e ative o ambiente virtual, e instale as dependências:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Crie o banco `medagenda` no PostgreSQL (pelo pgAdmin ou pelo `createdb`).

4. Crie o arquivo `.env` a partir do exemplo e preencha os valores:

```powershell
Copy-Item .env.example .env
```

Variáveis principais:

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Chave secreta da aplicação (use um valor longo e aleatório) |
| `DATABASE_URL` | URL do banco, **com o driver explícito**: `postgresql+psycopg2://usuario:senha@localhost:5432/medagenda` |

Sem o `+psycopg2`, o SQLAlchemy 2.1 tenta usar o `psycopg3` e a conexão falha.

5. Aplique as migrações:

```powershell
flask --app run db upgrade
```

6. Crie a recepcionista (o comando pede os dados):

```powershell
flask --app run criar-recepcionista
```

7. Suba o servidor:

```powershell
flask --app run run --debug
```

Acesse `http://127.0.0.1:5000`. Clientes se cadastram em **Criar conta**.

> O arquivo `.env` guarda a chave secreta e a senha do banco. Ele está no `.gitignore` e **nunca** deve ser commitado.

## Estrutura do projeto

```
MedAgenda/
  app/
    __init__.py         create_app(): extensões, blueprints, filtros e erros
    extensions.py       db, migrate, login_manager, csrf
    decorators.py       recepcionista_required
    commands.py         comando criar-recepcionista
    formatadores.py     formatação de CPF, telefone e data
    erros_http.py       páginas de erro 400, 403 e 404
    models/             usuario, paciente, especialidade, profissional,
                        disponibilidade, agendamento, enums
    routes/             main, auth, pacientes, especialidades, profissionais,
                        disponibilidades, agendamentos
    services/           regras de negócio, validações, permissões e tempo
    templates/          Jinja2 (base.html, uma pasta por módulo)
    static/             CSS e favicon
  migrations/           migrações do banco (Flask-Migrate)
  config.py  run.py  requirements.txt  .env.example
```

## Limitações conhecidas

- O CPF é validado apenas pelo tamanho (11 dígitos), sem o dígito verificador.
- A checagem de sobreposição de horários não é atômica: duas gerações simultâneas no mesmo dia e profissional podem passar juntas. A solução definitiva é uma *exclusion constraint* no PostgreSQL.
- O conflito de horários do mesmo paciente também não é atômico em acessos simultâneos.
- Data e hora usam o fuso do servidor, que precisa ser o do consultório.
- Não existe vínculo entre o agendamento remarcado e o novo, nem o status "faltou".
- Não há campo "ativo" no profissional: sem exclusão, um profissional não pode ser desativado.
- A página de erro 500 usa a tela padrão do Flask.
- A lista de especialidades não é paginada.

## Licença

Veja o arquivo [LICENSE](LICENSE).
