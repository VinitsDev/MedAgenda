from flask import Blueprint, render_template

from app.decorators import recepcionista_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/recepcao")
@recepcionista_required
def recepcao():
    return "Área da recepção (rota de teste, será removida)"