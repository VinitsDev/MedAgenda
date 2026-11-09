from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Especialidade, Profissional
from app.services import validacoes
from app.services.errors import ErroDeNegocio, NaoEncontrado
from app.services.permissoes import exigir_recepcionista

POR_PAGINA = 10


def especialidades_disponiveis():
    consulta = db.select(Especialidade).order_by(func.lower(Especialidade.nome))
    return db.session.scalars(consulta).all()


def obter(profissional_id):
    profissional = db.session.get(Profissional, profissional_id)
    if profissional is None:
        raise NaoEncontrado("Profissional não encontrado.")
    return profissional


def listar(busca=None, especialidade_id=None, pagina=1, por_pagina=POR_PAGINA):
    consulta = (
        db.select(Profissional)
        .options(selectinload(Profissional.especialidades))
        .order_by(func.lower(Profissional.nome), Profissional.id)
    )

    termo = (busca or "").strip()
    if termo:
        consulta = consulta.where(
            Profissional.nome.ilike(f"%{validacoes.escapar_like(termo)}%", escape="\\")
        )
    if especialidade_id:
        consulta = consulta.where(
            Profissional.especialidades.any(Especialidade.id == especialidade_id)
        )

    return db.paginate(consulta, page=pagina, per_page=por_pagina, error_out=False)


def _carregar_especialidades(ids):
    try:
        ids = {int(i) for i in ids}
    except (TypeError, ValueError):
        raise ErroDeNegocio("Especialidade inválida.")
    if not ids:
        raise ErroDeNegocio("Selecione ao menos uma especialidade.")

    encontradas = db.session.scalars(
        db.select(Especialidade).where(Especialidade.id.in_(ids))
    ).all()
    if len(encontradas) != len(ids):
        raise ErroDeNegocio("Especialidade inválida.")
    return encontradas


def _registro_em_uso(registro, ignorar_id=None):
    consulta = db.select(Profissional).where(Profissional.registro == registro)
    if ignorar_id is not None:
        consulta = consulta.where(Profissional.id != ignorar_id)
    return db.session.scalar(consulta) is not None


def cadastrar(usuario, nome, registro, telefone, especialidade_ids):
    exigir_recepcionista(usuario)

    nome = validacoes.validar_nome(nome)
    registro = validacoes.validar_registro(registro)
    telefone = validacoes.validar_telefone(telefone)
    especialidades = _carregar_especialidades(especialidade_ids)

    if _registro_em_uso(registro):
        raise ErroDeNegocio("Já existe um profissional com este registro.")

    profissional = Profissional(nome=nome, registro=registro, telefone=telefone)
    profissional.especialidades = especialidades
    db.session.add(profissional)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio("Já existe um profissional com este registro.")
    return profissional


def atualizar(usuario, profissional_id, nome, registro, telefone, especialidade_ids):
    exigir_recepcionista(usuario)
    profissional = obter(profissional_id)

    nome = validacoes.validar_nome(nome)
    registro = validacoes.validar_registro(registro)
    telefone = validacoes.validar_telefone(telefone)
    especialidades = _carregar_especialidades(especialidade_ids)

    if _registro_em_uso(registro, ignorar_id=profissional.id):
        raise ErroDeNegocio("Já existe outro profissional com este registro.")

    profissional.nome = nome
    profissional.registro = registro
    profissional.telefone = telefone
    profissional.especialidades = especialidades

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio("Já existe outro profissional com este registro.")
    return profissional