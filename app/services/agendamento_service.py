"""Regras de negócio dos agendamentos (criar, consultar, cancelar, remarcar e concluir)."""
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager, joinedload

from app.extensions import db
from app.models import (
    Agendamento,
    Disponibilidade,
    Paciente,
    Profissional,
    StatusAgendamento,
    StatusDisponibilidade,
)
from app.services import disponibilidade_service, paciente_service, validacoes
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


def _conflito_do_paciente(paciente_id, disponibilidade, ignorar_agendamento_id=None):
    """Outro agendamento ATIVO do paciente que se sobreponha ao horário, ou None.

    Critério: existente.inicio < novo_fim E existente.fim > novo_inicio.
    Na remarcação, o próprio agendamento é ignorado (o horário dele será liberado).
    """
    consulta = (
        db.select(Disponibilidade)
        .join(Agendamento, Agendamento.disponibilidade_id == Disponibilidade.id)
        .where(
            Agendamento.paciente_id == paciente_id,
            Agendamento.status == StatusAgendamento.AGENDADO,
            Disponibilidade.data == disponibilidade.data,
            Disponibilidade.hora_inicio < disponibilidade.hora_fim,
            Disponibilidade.hora_fim > disponibilidade.hora_inicio,
        )
    )
    if ignorar_agendamento_id is not None:
        consulta = consulta.where(Agendamento.id != ignorar_agendamento_id)
    return db.session.scalars(consulta.limit(1)).first()


def _mensagem_conflito(conflito):
    return (
        f"Este paciente já tem um agendamento das {conflito.hora_inicio:%H:%M} "
        f"às {conflito.hora_fim:%H:%M} neste dia, que conflita com este horário."
    )


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


def _travar_horarios(ids):
    """Trava vários horários sempre em ordem crescente de id (evita deadlock)."""
    linhas = db.session.scalars(
        db.select(Disponibilidade)
        .where(Disponibilidade.id.in_(ids))
        .order_by(Disponibilidade.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    return {d.id: d for d in linhas}


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
    # nem com médicos diferentes.
    conflito = _conflito_do_paciente(paciente.id, disponibilidade)
    if conflito is not None:
        _recusar(_mensagem_conflito(conflito))

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


def _motivo_nao_remarcavel(agendamento, disponibilidade):
    if agendamento.status != StatusAgendamento.AGENDADO:
        return "Só é possível remarcar agendamentos com status Agendado."
    if _inicio(disponibilidade) <= _agora():
        return "Este horário já começou ou passou e não pode mais ser remarcado."
    return None


def horarios_para_remarcar(usuario, agendamento_id, pagina=1):
    """Tela de remarcação (GET): horários livres do MESMO profissional. Nada é gravado."""
    agendamento = obter(usuario, agendamento_id)
    motivo = _motivo_nao_remarcavel(agendamento, agendamento.disponibilidade)
    if motivo:
        raise ErroDeNegocio(motivo)

    horarios = disponibilidade_service.consultar_livres(
        profissional_id=agendamento.disponibilidade.profissional_id, pagina=pagina
    )
    return agendamento, horarios


def remarcar(usuario, agendamento_id, nova_disponibilidade_id):
    """Antigo vira REMARCADO e libera o horário; nasce um novo AGENDADO. Mesma transação."""
    agendamento = obter(usuario, agendamento_id)
    if nova_disponibilidade_id is None:
        raise ErroDeNegocio("Escolha o novo horário.")
    antiga_id = agendamento.disponibilidade_id
    if nova_disponibilidade_id == antiga_id:
        raise ErroDeNegocio("Escolha um horário diferente do atual.")

    horarios = _travar_horarios([antiga_id, nova_disponibilidade_id])
    antiga = horarios.get(antiga_id)
    nova = horarios.get(nova_disponibilidade_id)
    if nova is None:
        db.session.rollback()
        raise NaoEncontrado("Horário não encontrado.")
    db.session.refresh(agendamento)  # relê o status depois da trava

    motivo = _motivo_nao_remarcavel(agendamento, antiga)
    if motivo:
        _recusar(motivo)
    if nova.profissional_id != antiga.profissional_id:
        _recusar("Só é possível remarcar para outro horário do mesmo profissional.")
    motivo = _motivo_indisponivel(nova)
    if motivo:
        _recusar(motivo)

    conflito = _conflito_do_paciente(
        agendamento.paciente_id, nova, ignorar_agendamento_id=agendamento.id
    )
    if conflito is not None:
        _recusar(_mensagem_conflito(conflito))

    novo = Agendamento(
        disponibilidade_id=nova.id,
        paciente_id=agendamento.paciente_id,
        status=StatusAgendamento.AGENDADO,
    )
    agendamento.status = StatusAgendamento.REMARCADO
    antiga.status = StatusDisponibilidade.DISPONIVEL
    nova.status = StatusDisponibilidade.OCUPADO
    db.session.add(novo)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio(
            "Este horário acabou de ser ocupado por outra pessoa. Escolha outro."
        )
    return novo


def alterar_status(usuario, agendamento_id, novo_status_texto):
    """Só a recepção. Permitidos: AGENDADO -> CONCLUIDO e AGENDADO -> CANCELADO."""
    exigir_recepcionista(usuario)
    novo = StatusAgendamento.__members__.get((novo_status_texto or "").strip().upper())
    if novo is None:
        raise ErroDeNegocio("Status inválido.")
    if novo == StatusAgendamento.CANCELADO:
        return cancelar(usuario, agendamento_id)
    if novo == StatusAgendamento.REMARCADO:
        raise ErroDeNegocio("O status Remarcado só é atribuído pela remarcação.")
    if novo != StatusAgendamento.CONCLUIDO:
        raise ErroDeNegocio("Um agendamento não pode voltar para Agendado.")

    agendamento = obter(usuario, agendamento_id)
    disponibilidade = _travar_horario(agendamento.disponibilidade_id)
    db.session.refresh(agendamento)

    if agendamento.status != StatusAgendamento.AGENDADO:
        _recusar("Só é possível concluir agendamentos com status Agendado.")
    if _inicio(disponibilidade) > _agora():
        _recusar("Só é possível concluir o atendimento depois do início do horário.")

    agendamento.status = StatusAgendamento.CONCLUIDO  # o horário continua OCUPADO

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio("Não foi possível concluir. Tente novamente.")
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