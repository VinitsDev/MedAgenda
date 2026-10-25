import enum


class Papel(enum.Enum):
    CLIENTE = "cliente"
    RECEPCIONISTA = "recepcionista"


class StatusDisponibilidade(enum.Enum):
    DISPONIVEL = "disponivel"
    OCUPADO = "ocupado"


class StatusAgendamento(enum.Enum):
    AGENDADO = "agendado"
    CANCELADO = "cancelado"
    REMARCADO = "remarcado"
    CONCLUIDO = "concluido"