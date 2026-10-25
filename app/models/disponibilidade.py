from app.extensions import db
from app.models.enums import StatusDisponibilidade


class Disponibilidade(db.Model):
    __tablename__ = "disponibilidade"

    id = db.Column(db.Integer, primary_key=True)
    profissional_id = db.Column(db.Integer, db.ForeignKey("profissional.id"), nullable=False)
    data = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fim = db.Column(db.Time, nullable=False)
    status = db.Column(
        db.Enum(StatusDisponibilidade, native_enum=False, length=20),
        nullable=False,
        default=StatusDisponibilidade.DISPONIVEL,
    )

    profissional = db.relationship("Profissional", back_populates="disponibilidades")
    agendamentos = db.relationship("Agendamento", back_populates="disponibilidade")

    __table_args__ = (
        db.UniqueConstraint("profissional_id", "data", "hora_inicio", name="uq_horario_profissional"),
        db.CheckConstraint("hora_fim > hora_inicio", name="ck_hora_fim_maior"),
    )