from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Paciente
from app.services import validacoes
from app.services.errors import AcessoNegado, ErroDeNegocio, NaoEncontrado

POR_PAGINA = 10


def _exigir_recepcionista(usuario):
    if not usuario.eh_recepcionista:
        raise AcessoNegado("Apenas a recepção pode realizar esta ação.")


def _escapar_like(texto):
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def obter(usuario, paciente_id):
    paciente = db.session.get(Paciente, paciente_id)
    if paciente is None:
        raise NaoEncontrado("Paciente não encontrado.")
    if not usuario.eh_recepcionista and paciente.usuario_id != usuario.id:
        raise AcessoNegado("Você não tem acesso a este cadastro.")
    return paciente


def paciente_do_usuario(usuario):
    return db.session.scalar(db.select(Paciente).filter_by(usuario_id=usuario.id))


def listar(usuario, busca=None, pagina=1, por_pagina=POR_PAGINA):
    _exigir_recepcionista(usuario)

    consulta = db.select(Paciente).order_by(Paciente.nome, Paciente.id)
    termo = (busca or "").strip()
    if termo:
        filtros = [Paciente.nome.ilike(f"%{_escapar_like(termo)}%", escape="\\")]
        digitos = validacoes.somente_digitos(termo)
        if digitos:
            filtros.append(Paciente.cpf.like(f"{digitos}%"))
        consulta = consulta.where(or_(*filtros))

    return db.paginate(consulta, page=pagina, per_page=por_pagina, error_out=False)


def cadastrar(usuario, nome, cpf, data_nascimento, telefone=None):
    _exigir_recepcionista(usuario)

    nome = validacoes.validar_nome(nome)
    cpf = validacoes.validar_cpf(cpf)
    data_nascimento = validacoes.validar_data_nascimento(data_nascimento)
    telefone = validacoes.validar_telefone(telefone)

    if db.session.scalar(db.select(Paciente).filter_by(cpf=cpf)) is not None:
        raise ErroDeNegocio("Já existe um paciente com este CPF.")

    paciente = Paciente(
        nome=nome, cpf=cpf, data_nascimento=data_nascimento, telefone=telefone
    )
    db.session.add(paciente)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio("Já existe um paciente com este CPF.")
    return paciente


def atualizar(usuario, paciente_id, nome, telefone, cpf=None, data_nascimento=None):
    paciente = obter(usuario, paciente_id)

    novo_nome = validacoes.validar_nome(nome)
    novo_telefone = validacoes.validar_telefone(telefone)

    if usuario.eh_recepcionista:
        novo_cpf = validacoes.validar_cpf(cpf)
        nova_data = validacoes.validar_data_nascimento(data_nascimento)
        duplicado = db.session.scalar(
            db.select(Paciente).where(Paciente.cpf == novo_cpf, Paciente.id != paciente.id)
        )
        if duplicado is not None:
            raise ErroDeNegocio("Já existe outro paciente com este CPF.")
        paciente.cpf = novo_cpf
        paciente.data_nascimento = nova_data

    paciente.nome = novo_nome
    paciente.telefone = novo_telefone
    if paciente.usuario is not None:
        paciente.usuario.nome = novo_nome

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio("Já existe outro paciente com este CPF.")
    return paciente