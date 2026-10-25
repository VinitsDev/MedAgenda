from datetime import datetime, timezone

from app.extensions import db
from app.models.enums import StatusAgendamento


class Agendamento(db.Model):
    __tablename__ = "agendamento"

    id = db.Column(db.Integer, primary_key=True)
    disponibilidade_id = db.Column(db.Integer, db.ForeignKey("disponibilidade.id"), nullable=False)
    paciente_id = db.Column(db.Integer, db.ForeignKey("paciente.id"), nullable=False)
    status = db.Column(
        db.Enum(StatusAgendamento, native_enum=False, length=20),
        nullable=False,
        default=StatusAgendamento.AGENDADO,
    )
    data_criacao = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    disponibilidade = db.relationship("Disponibilidade", back_populates="agendamentos")
    paciente = db.relationship("Paciente", back_populates="agendamentos")

    __table_args__ = (
        db.Index(
            "uq_agendamento_ativo_por_horario",
            "disponibilidade_id",
            unique=True,
            postgresql_where=db.text("status = 'AGENDADO'"),
        ),
    )