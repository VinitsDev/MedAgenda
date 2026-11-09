from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import recepcionista_required
from app.services import profissional_service
from app.services.errors import ErroDeNegocio, NaoEncontrado

profissionais_bp = Blueprint("profissionais", __name__, url_prefix="/profissionais")


def _carregar(profissional_id):
    try:
        return profissional_service.obter(profissional_id)
    except NaoEncontrado:
        abort(404)


@profissionais_bp.route("/")
@login_required
def lista():
    busca = request.args.get("q", "").strip()[:100]
    especialidade_id = request.args.get("especialidade", type=int)
    pagina = request.args.get("page", 1, type=int)
    resultado = profissional_service.listar(
        busca=busca, especialidade_id=especialidade_id, pagina=max(pagina, 1)
    )
    return render_template(
        "profissionais/lista.html",
        profissionais=resultado,
        busca=busca,
        especialidade_id=especialidade_id,
        especialidades=profissional_service.especialidades_disponiveis(),
    )


@profissionais_bp.route("/novo", methods=["GET", "POST"])
@recepcionista_required
def novo():
    valores = {}
    selecionadas = set()
    if request.method == "POST":
        valores = request.form
        selecionadas = set(request.form.getlist("especialidades"))
        try:
            profissional = profissional_service.cadastrar(
                current_user,
                nome=request.form.get("nome"),
                registro=request.form.get("registro"),
                telefone=request.form.get("telefone"),
                especialidade_ids=request.form.getlist("especialidades"),
            )
        except ErroDeNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash("Profissional cadastrado com sucesso.", "success")
            return redirect(
                url_for("profissionais.detalhe", profissional_id=profissional.id)
            )

    return render_template(
        "profissionais/form.html",
        titulo="Novo profissional",
        valores=valores,
        selecionadas=selecionadas,
        especialidades=profissional_service.especialidades_disponiveis(),
        cancelar_url=url_for("profissionais.lista"),
    )


@profissionais_bp.route("/<int:profissional_id>")
@login_required
def detalhe(profissional_id):
    profissional = _carregar(profissional_id)
    return render_template("profissionais/detalhe.html", profissional=profissional)


@profissionais_bp.route("/<int:profissional_id>/editar", methods=["GET", "POST"])
@recepcionista_required
def editar(profissional_id):
    profissional = _carregar(profissional_id)

    if request.method == "POST":
        valores = request.form
        selecionadas = set(request.form.getlist("especialidades"))
        try:
            profissional_service.atualizar(
                current_user,
                profissional_id,
                nome=request.form.get("nome"),
                registro=request.form.get("registro"),
                telefone=request.form.get("telefone"),
                especialidade_ids=request.form.getlist("especialidades"),
            )
        except ErroDeNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash("Cadastro atualizado.", "success")
            return redirect(
                url_for("profissionais.detalhe", profissional_id=profissional_id)
            )
    else:
        valores = {
            "nome": profissional.nome,
            "registro": profissional.registro,
            "telefone": profissional.telefone or "",
        }
        selecionadas = {str(e.id) for e in profissional.especialidades}

    return render_template(
        "profissionais/form.html",
        titulo="Editar profissional",
        valores=valores,
        selecionadas=selecionadas,
        especialidades=profissional_service.especialidades_disponiveis(),
        cancelar_url=url_for("profissionais.detalhe", profissional_id=profissional_id),
    )