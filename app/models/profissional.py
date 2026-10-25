from app.extensions import db
from app.models.especialidade import profissional_especialidade


class Profissional(db.Model):
    __tablename__ = "profissional"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    registro = db.Column(db.String(30), unique=True, nullable=False)
    telefone = db.Column(db.String(20))

    especialidades = db.relationship(
        "Especialidade",
        secondary=profissional_especialidade,
        back_populates="profissionais",
    )
    disponibilidades = db.relationship("Disponibilidade", back_populates="profissional")