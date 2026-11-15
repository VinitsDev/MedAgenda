"""Regras de negócio dos agendamentos (criar, consultar e cancelar)."""
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from app.extensions import db
from app.models import (
    Agendamento,
    Disponibilidade,
    Paciente,
    Profissional,
    StatusAgendamento,
    StatusDisponibilidade,
)
from app.services import paciente_service, validacoes
from app.services.errors import AcessoNegado, ErroDeNegocio, NaoEncontrado
from app.services.permissoes import exigir_recepcionista

POR_PAGINA = 10


def _agora():
    # Mesma convenção da Fase 5: hora de parede do consultório, sem fuso.
    return datetime.now()


def _inicio(disponibilidade):
    return datetime.combine(disponibilidade.data, disponibilidade.hora_inicio)


def _recusar(mensagem):
    """Solta a trava do horário (rollback) e devolve a mensagem ao usuário."""
    db.session.rollback()
    raise ErroDeNegocio(mensagem)


def _paciente_do_cliente(usuario):
    paciente = paciente_service.paciente_do_usuario(usuario)
    if paciente is None:
        raise ErroDeNegocio(
            "Nenhum cadastro de paciente está vinculado à sua conta. Procure a recepção."
        )
    return paciente


def _resolver_paciente(usuario, cpf):
    """Recepção escolhe o paciente pelo CPF; cliente só agenda para si.

    Para o cliente, o CPF vindo do formulário é IGNORADO: mesmo que alguém
    adultere o campo, o paciente é sempre o do usuário logado.
    """
    if usuario.eh_recepcionista:
        cpf = validacoes.validar_cpf(cpf)
        paciente = db.session.scalar(db.select(Paciente).filter_by(cpf=cpf))
        if paciente is None:
            raise ErroDeNegocio(
                "Não há paciente cadastrado com este CPF. Cadastre o paciente antes de agendar."
            )
        return paciente
    return _paciente_do_cliente(usuario)


def _motivo_indisponivel(disponibilidade):
    """Devolve o motivo (texto) se o horário não pode ser agendado, ou None."""
    if disponibilidade.status != StatusDisponibilidade.DISPONIVEL:
        return "Este horário não está mais disponível."
    if _inicio(disponibilidade) <= _agora():
        return "Este horário já passou."
    return None


def _travar_horario(disponibilidade_id):
    """SELECT ... FOR UPDATE: quem chegar depois espera o commit de quem chegou antes."""
    disponibilidade = db.session.scalar(
        db.select(Disponibilidade)
        .where(Disponibilidade.id == disponibilidade_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if disponibilidade is None:
        raise NaoEncontrado("Horário não encontrado.")
    return disponibilidade


def obter(usuario, agendamento_id):
    agendamento = db.session.get(Agendamento, agendamento_id)
    if agendamento is None:
        raise NaoEncontrado("Agendamento não encontrado.")
    if not usuario.eh_recepcionista and agendamento.paciente.usuario_id != usuario.id:
        raise AcessoNegado("Você não tem acesso a este agendamento.")
    return agendamento


def horario_para_agendar(usuario, disponibilidade_id):
    """Tela de confirmação (GET). Nada é gravado aqui."""
    if not usuario.eh_recepcionista:
        _paciente_do_cliente(usuario)

    disponibilidade = db.session.scalar(
        db.select(Disponibilidade)
        .options(
            joinedload(Disponibilidade.profissional).selectinload(Profissional.especialidades)
        )
        .where(Disponibilidade.id == disponibilidade_id)
    )
    if disponibilidade is None:
        raise NaoEncontrado("Horário não encontrado.")

    motivo = _motivo_indisponivel(disponibilidade)
    if motivo:
        raise ErroDeNegocio(motivo)
    return disponibilidade


def criar(usuario, disponibilidade_id, cpf=None):
    paciente = _resolver_paciente(usuario, cpf)
    disponibilidade = _travar_horario(disponibilidade_id)

    motivo = _motivo_indisponivel(disponibilidade)
    if motivo:
        _recusar(motivo)

    # O mesmo paciente não pode ter dois agendamentos ativos que se sobreponham,
    # nem com médicos diferentes. Critério: existente.inicio < novo_fim E existente.fim > novo_inicio.
    conflito = db.session.scalars(
        db.select(Disponibilidade)
        .join(Agendamento, Agendamento.disponibilidade_id == Disponibilidade.id)
        .where(
            Agendamento.paciente_id == paciente.id,
            Agendamento.status == StatusAgendamento.AGENDADO,
            Disponibilidade.data == disponibilidade.data,
            Disponibilidade.hora_inicio < disponibilidade.hora_fim,
            Disponibilidade.hora_fim > disponibilidade.hora_inicio,
        )
        .limit(1)
    ).first()
    if conflito is not None:
        _recusar(
            f"Este paciente já tem um agendamento das {conflito.hora_inicio:%H:%M} "
            f"às {conflito.hora_fim:%H:%M} neste dia, que conflita com este horário."
        )

    agendamento = Agendamento(
        disponibilidade_id=disponibilidade.id,
        paciente_id=paciente.id,
        status=StatusAgendamento.AGENDADO,
    )
    disponibilidade.status = StatusDisponibilidade.OCUPADO
    db.session.add(agendamento)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio(
            "Este horário acabou de ser ocupado por outra pessoa. Escolha outro."
        )
    return agendamento


def cancelar(usuario, agendamento_id):
    agendamento = obter(usuario, agendamento_id)
    disponibilidade = _travar_horario(agendamento.disponibilidade_id)
    db.session.refresh(agendamento)  # relê o status depois da trava

    if agendamento.status != StatusAgendamento.AGENDADO:
        _recusar("Só é possível cancelar agendamentos com status Agendado.")
    if _inicio(disponibilidade) <= _agora():
        _recusar("Este horário já começou ou passou e não pode mais ser cancelado.")

    agendamento.status = StatusAgendamento.CANCELADO
    disponibilidade.status = StatusDisponibilidade.DISPONIVEL

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio("Não foi possível cancelar. Tente novamente.")
    return agendamento


def _consulta_base():
    return (
        db.select(Agendamento)
        .join(Agendamento.disponibilidade)
        .join(Disponibilidade.profissional)
        .join(Agendamento.paciente)
        .options(
            contains_eager(Agendamento.disponibilidade).contains_eager(
                Disponibilidade.profissional
            ),
            contains_eager(Agendamento.paciente),
        )
        .order_by(
            Disponibilidade.data.desc(),
            Disponibilidade.hora_inicio.desc(),
            Agendamento.id.desc(),
        )
    )


def listar_do_paciente(usuario, pagina=1, por_pagina=POR_PAGINA):
    """'Meus agendamentos' do cliente: todos os status, mais recente primeiro."""
    paciente = _paciente_do_cliente(usuario)
    consulta = _consulta_base().where(Agendamento.paciente_id == paciente.id)
    return db.paginate(consulta, page=pagina, per_page=por_pagina, error_out=False)


def listar_todos(usuario, busca=None, status_texto=None, pagina=1, por_pagina=POR_PAGINA):
    """Tela da recepção: filtro por status e busca por nome ou CPF do paciente."""
    exigir_recepcionista(usuario)
    consulta = _consulta_base()

    termo = (busca or "").strip()
    if termo:
        filtros = [Paciente.nome.ilike(f"%{validacoes.escapar_like(termo)}%", escape="\\")]
        digitos = validacoes.somente_digitos(termo)
        if digitos:
            filtros.append(Paciente.cpf.like(f"{digitos}%"))
        consulta = consulta.where(or_(*filtros))

    texto = (status_texto or "").strip().upper()
    if texto:
        status = StatusAgendamento.__members__.get(texto)
        if status is None:
            raise ErroDeNegocio("O status do filtro é inválido.")
        consulta = consulta.where(Agendamento.status == status)

    return db.paginate(consulta, page=pagina, per_page=por_pagina, error_out=False)