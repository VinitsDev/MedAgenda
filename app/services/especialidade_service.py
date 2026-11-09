from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Especialidade
from app.services import validacoes
from app.services.errors import ErroDeNegocio, NaoEncontrado
from app.services.permissoes import exigir_recepcionista


def listar(usuario):
    exigir_recepcionista(usuario)
    consulta = db.select(Especialidade).order_by(func.lower(Especialidade.nome))
    return db.session.scalars(consulta).all()


def obter(usuario, especialidade_id):
    exigir_recepcionista(usuario)
    especialidade = db.session.get(Especialidade, especialidade_id)
    if especialidade is None:
        raise NaoEncontrado("Especialidade não encontrada.")
    return especialidade


def _nome_em_uso(nome, ignorar_id=None):
    consulta = db.select(Especialidade).where(func.lower(Especialidade.nome) == nome.lower())
    if ignorar_id is not None:
        consulta = consulta.where(Especialidade.id != ignorar_id)
    return db.session.scalar(consulta) is not None


def criar(usuario, nome):
    exigir_recepcionista(usuario)
    nome = validacoes.validar_nome_especialidade(nome)
    if _nome_em_uso(nome):
        raise ErroDeNegocio("Já existe uma especialidade com este nome.")

    especialidade = Especialidade(nome=nome)
    db.session.add(especialidade)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio("Já existe uma especialidade com este nome.")
    return especialidade


def atualizar(usuario, especialidade_id, nome):
    especialidade = obter(usuario, especialidade_id)
    nome = validacoes.validar_nome_especialidade(nome)
    if _nome_em_uso(nome, ignorar_id=especialidade.id):
        raise ErroDeNegocio("Já existe uma especialidade com este nome.")

    especialidade.nome = nome
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio("Já existe uma especialidade com este nome.")
    return especialidade