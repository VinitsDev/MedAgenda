"""Regras de negócio da disponibilidade (horários agendáveis dos profissionais)."""
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import (
    Agendamento,
    Disponibilidade,
    Especialidade,
    Profissional,
    StatusDisponibilidade,
)
from app.services import profissional_service, validacoes
from app.services.errors import ErroDeNegocio, NaoEncontrado
from app.services.permissoes import exigir_recepcionista

POR_PAGINA = 10
DURACAO_MINIMA = 10      # minutos
DURACAO_MAXIMA = 120     # minutos
MAX_HORARIOS_POR_GERACAO = 48


def _agora():
    # Data e hora de parede do consultório (a tabela não guarda fuso).
    return datetime.now()


def _minutos(hora):
    return hora.hour * 60 + hora.minute


def profissionais_para_filtro():
    consulta = db.select(Profissional).order_by(func.lower(Profissional.nome), Profissional.id)
    return db.session.scalars(consulta).all()


def obter(disponibilidade_id):
    disponibilidade = db.session.get(Disponibilidade, disponibilidade_id)
    if disponibilidade is None:
        raise NaoEncontrado("Horário não encontrado.")
    return disponibilidade


def listar_do_profissional(usuario, profissional_id, pagina=1, por_pagina=POR_PAGINA):
    """Tela de gerenciamento (só recepção): horários de hoje em diante."""
    exigir_recepcionista(usuario)
    profissional = profissional_service.obter(profissional_id)

    consulta = (
        db.select(Disponibilidade)
        .options(selectinload(Disponibilidade.agendamentos))
        .where(
            Disponibilidade.profissional_id == profissional.id,
            Disponibilidade.data >= _agora().date(),
        )
        .order_by(Disponibilidade.data, Disponibilidade.hora_inicio)
    )
    paginacao = db.paginate(consulta, page=pagina, per_page=por_pagina, error_out=False)
    return profissional, paginacao


def consultar_livres(profissional_id=None, especialidade_id=None, data_texto=None,
                     pagina=1, por_pagina=POR_PAGINA):
    """Consulta geral: só horários DISPONIVEIS e futuros, com filtros opcionais."""
    agora = _agora()
    futuro = or_(
        Disponibilidade.data > agora.date(),
        and_(
            Disponibilidade.data == agora.date(),
            Disponibilidade.hora_inicio > agora.time(),
        ),
    )

    consulta = (
        db.select(Disponibilidade)
        .options(
            joinedload(Disponibilidade.profissional).selectinload(Profissional.especialidades)
        )
        .where(Disponibilidade.status == StatusDisponibilidade.DISPONIVEL, futuro)
        .order_by(
            Disponibilidade.data, Disponibilidade.hora_inicio, Disponibilidade.profissional_id
        )
    )

    if profissional_id:
        consulta = consulta.where(Disponibilidade.profissional_id == profissional_id)
    if especialidade_id:
        consulta = consulta.where(
            Disponibilidade.profissional.has(
                Profissional.especialidades.any(Especialidade.id == especialidade_id)
            )
        )

    texto = (data_texto or "").strip()
    if texto:
        dia = validacoes.converter_data(texto)
        if dia is None:
            raise ErroDeNegocio("A data do filtro é inválida.")
        consulta = consulta.where(Disponibilidade.data == dia)

    return db.paginate(consulta, page=pagina, per_page=por_pagina, error_out=False)


def gerar(usuario, profissional_id, data_texto, inicio_texto, fim_texto, duracao_texto):
    """Gera os horários de [inicio, fim) em fatias de 'duracao' minutos."""
    exigir_recepcionista(usuario)
    profissional = profissional_service.obter(profissional_id)

    dia = validacoes.converter_data(data_texto)
    inicio = validacoes.converter_hora(inicio_texto)
    fim = validacoes.converter_hora(fim_texto)
    if dia is None:
        raise ErroDeNegocio("Informe uma data válida.")
    if inicio is None:
        raise ErroDeNegocio("Informe um horário de início válido (HH:MM).")
    if fim is None:
        raise ErroDeNegocio("Informe um horário de fim válido (HH:MM).")
    if fim <= inicio:
        raise ErroDeNegocio("O horário de fim deve ser depois do início.")

    try:
        duracao = int((duracao_texto or "").strip())
    except (TypeError, ValueError):
        raise ErroDeNegocio("Informe a duração em minutos (número inteiro).")
    if not DURACAO_MINIMA <= duracao <= DURACAO_MAXIMA:
        raise ErroDeNegocio(
            f"A duração deve estar entre {DURACAO_MINIMA} e {DURACAO_MAXIMA} minutos."
        )

    total = _minutos(fim) - _minutos(inicio)
    if total % duracao != 0:
        raise ErroDeNegocio(
            f"A duração de {duracao} min não divide o intervalo de {total} min. "
            "Ajuste o fim ou a duração."
        )
    quantidade = total // duracao
    if quantidade > MAX_HORARIOS_POR_GERACAO:
        raise ErroDeNegocio(
            f"Isso geraria {quantidade} horários; o máximo por geração é "
            f"{MAX_HORARIOS_POR_GERACAO}."
        )

    if datetime.combine(dia, inicio) <= _agora():
        raise ErroDeNegocio("Não é possível gerar horários no passado.")

    # Sobreposição: existente.inicio < novo_fim E existente.fim > novo_inicio.
    # Como os horários gerados cobrem [inicio, fim) sem buracos, uma única consulta
    # sobre o intervalo inteiro basta.
    conflito = db.session.scalars(
        db.select(Disponibilidade)
        .where(
            Disponibilidade.profissional_id == profissional.id,
            Disponibilidade.data == dia,
            Disponibilidade.hora_inicio < fim,
            Disponibilidade.hora_fim > inicio,
        )
        .order_by(Disponibilidade.hora_inicio)
        .limit(1)
    ).first()
    if conflito is not None:
        raise ErroDeNegocio(
            f"Já existe o horário de {conflito.hora_inicio:%H:%M} às "
            f"{conflito.hora_fim:%H:%M} neste dia, que conflita com o intervalo informado."
        )

    passo = timedelta(minutes=duracao)
    atual = datetime.combine(dia, inicio)
    for _ in range(quantidade):
        proximo = atual + passo
        db.session.add(
            Disponibilidade(
                profissional_id=profissional.id,
                data=dia,
                hora_inicio=atual.time(),
                hora_fim=proximo.time(),
                status=StatusDisponibilidade.DISPONIVEL,
            )
        )
        atual = proximo

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio(
            "Não foi possível gerar os horários: já existe horário conflitante. "
            "Confira a lista e tente de novo."
        )
    return quantidade


def remover(usuario, disponibilidade_id):
    exigir_recepcionista(usuario)
    disponibilidade = obter(disponibilidade_id)

    total = db.session.scalar(
        db.select(func.count(Agendamento.id)).where(
            Agendamento.disponibilidade_id == disponibilidade.id
        )
    )
    if total:
        raise ErroDeNegocio(
            "Este horário tem agendamento no histórico e não pode ser removido."
        )

    db.session.delete(disponibilidade)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErroDeNegocio(
            "Este horário acabou de receber um agendamento e não pode ser removido."
        )