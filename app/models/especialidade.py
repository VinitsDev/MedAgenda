from app.extensions import db

profissional_especialidade = db.Table(
    "profissional_especialidade",
    db.Column("profissional_id", db.Integer, db.ForeignKey("profissional.id"), primary_key=True),
    db.Column("especialidade_id", db.Integer, db.ForeignKey("especialidade.id"), primary_key=True),
)


class Especialidade(db.Model):
    __tablename__ = "especialidade"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)

    profissionais = db.relationship(
        "Profissional",
        secondary=profissional_especialidade,
        back_populates="especialidades",
    )