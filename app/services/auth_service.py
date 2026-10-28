import re
from datetime import date

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Paciente, Papel, Usuario
from app.services.errors import ErroDeNegocio

TAMANHO_MIN_SENHA = 8
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _somente_digitos(texto):
    return re.sub(r"\D", "", texto or "")


def _validar_credenciais(nome, email, senha):
    nome = (nome or "").strip()
    email = (email or "").strip().lower()

    if not nome or len(nome) > 120:
        raise ErroDeNegocio("Informe um nome de até 120 caracteres.")
    if not EMAIL_RE.match(email) or len(email) > 255:
        raise ErroDeNegocio("Informe um e-mail válido.")
    if len(senha or "") < TAMANHO_MIN_SENHA:
        raise ErroDeNegocio(f"A senha deve ter pelo menos {TAMANHO_MIN_SENHA} caracteres.")
    return nome, email


def _email_em_uso(email):
    return db.session.scalar(db.select(Usuario).filter_by(email=email)) is not None


def registrar_cliente(nome, email, senha, cpf, data_nascimento, telefone=None):
    nome, email = _validar_credenciais(nome, email, senha)
    cpf = _somente_digitos(cpf)
    telefone = _somente_digitos(telefone) or None

    if len(cpf) != 11:
        raise ErroDeNegocio("Informe um CPF com 11 dígitos.")
    if data_nascimento is None or not (date(1900, 1, 1) <= data_nascimento <= date.today()):
        raise ErroDeNegocio("Informe uma data de nascimento válida.")
    if _email_em_uso(email):
        raise ErroDeNegocio("Este e-mail já está cadastrado.")

    paciente = db.session.scalar(db.select(Paciente).filter_by(cpf=cpf))
    if paciente is not None:
        if paciente.usuario_id is not None:
            raise ErroDeNegocio("Já existe uma conta para este CPF.")
        if paciente.data_nascimento != data_nascimento:
            raise ErroDeNegocio("Não foi possível vincular este CPF. Procure a recepção.")
    else:
        paciente = Paciente(
            nome=nome, cpf=cpf, data_nascimento=data_nascimento, telefone=telefone
        )
        db.session.add(paciente)

    usuario = Usuario(nome=nome, email=email, papel=Papel.CLIENTE)
    usuario.definir_senha(senha)
    paciente.usuario = usuario
    db.session.add(usuario)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio("E-mail ou CPF já cadastrado.")
    return usuario


def criar_recepcionista(nome, email, senha):
    nome, email = _validar_credenciais(nome, email, senha)
    if _email_em_uso(email):
        raise ErroDeNegocio("Este e-mail já está cadastrado.")

    usuario = Usuario(nome=nome, email=email, papel=Papel.RECEPCIONISTA)
    usuario.definir_senha(senha)
    db.session.add(usuario)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio("Este e-mail já está cadastrado.")
    return usuario


def autenticar(email, senha):
    email = (email or "").strip().lower()
    usuario = db.session.scalar(db.select(Usuario).filter_by(email=email))
    if usuario is None or not usuario.conferir_senha(senha or ""):
        raise ErroDeNegocio("E-mail ou senha inválidos.")
    return usuario