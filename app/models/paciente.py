from app.extensions import db


class Paciente(db.Model):
    __tablename__ = "paciente"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    cpf = db.Column(db.String(11), unique=True, nullable=False)
    data_nascimento = db.Column(db.Date, nullable=False)
    telefone = db.Column(db.String(20))
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), unique=True, nullable=True)

    usuario = db.relationship("Usuario", backref=db.backref("paciente", uselist=False))
    agendamentos = db.relationship("Agendamento", back_populates="paciente")