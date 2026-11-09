from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.decorators import recepcionista_required
from app.services import especialidade_service
from app.services.errors import AcessoNegado, ErroDeNegocio, NaoEncontrado

especialidades_bp = Blueprint("especialidades", __name__, url_prefix="/especialidades")


def _carregar(especialidade_id):
    try:
        return especialidade_service.obter(current_user, especialidade_id)
    except NaoEncontrado:
        abort(404)
    except AcessoNegado:
        abort(403)


@especialidades_bp.route("/")
@recepcionista_required
def lista():
    especialidades = especialidade_service.listar(current_user)
    return render_template("especialidades/lista.html", especialidades=especialidades)


@especialidades_bp.route("/nova", methods=["GET", "POST"])
@recepcionista_required
def nova():
    valores = {}
    if request.method == "POST":
        valores = request.form
        try:
            especialidade_service.criar(current_user, request.form.get("nome"))
        except ErroDeNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash("Especialidade cadastrada.", "success")
            return redirect(url_for("especialidades.lista"))

    return render_template(
        "especialidades/form.html", titulo="Nova especialidade", valores=valores
    )


@especialidades_bp.route("/<int:especialidade_id>/editar", methods=["GET", "POST"])
@recepcionista_required
def editar(especialidade_id):
    especialidade = _carregar(especialidade_id)

    if request.method == "POST":
        valores = request.form
        try:
            especialidade_service.atualizar(
                current_user, especialidade_id, request.form.get("nome")
            )
        except ErroDeNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash("Especialidade atualizada.", "success")
            return redirect(url_for("especialidades.lista"))
    else:
        valores = {"nome": especialidade.nome}

    return render_template(
        "especialidades/form.html", titulo="Editar especialidade", valores=valores
    )