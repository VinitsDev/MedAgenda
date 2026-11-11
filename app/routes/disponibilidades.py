from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import recepcionista_required
from app.services import disponibilidade_service, profissional_service
from app.services.errors import AcessoNegado, ErroDeNegocio, NaoEncontrado

disponibilidades_bp = Blueprint("disponibilidades", __name__, url_prefix="/horarios")


@disponibilidades_bp.route("/")
@login_required
def consulta():
    profissional_id = request.args.get("profissional", type=int)
    especialidade_id = request.args.get("especialidade", type=int)
    data = request.args.get("data", "").strip()[:10]
    pagina = max(request.args.get("page", 1, type=int), 1)

    try:
        horarios = disponibilidade_service.consultar_livres(
            profissional_id, especialidade_id, data, pagina
        )
    except ErroDeNegocio as erro:
        flash(str(erro), "danger")
        data = ""
        horarios = disponibilidade_service.consultar_livres(
            profissional_id, especialidade_id, None, pagina
        )

    return render_template(
        "disponibilidades/consulta.html",
        horarios=horarios,
        profissionais=disponibilidade_service.profissionais_para_filtro(),
        especialidades=profissional_service.especialidades_disponiveis(),
        profissional_id=profissional_id,
        especialidade_id=especialidade_id,
        data=data,
    )


@disponibilidades_bp.route(
    "/profissional/<int:profissional_id>", methods=["GET", "POST"]
)
@recepcionista_required
def gerenciar(profissional_id):
    valores = {}
    if request.method == "POST":
        valores = request.form
        try:
            quantidade = disponibilidade_service.gerar(
                current_user,
                profissional_id,
                data_texto=request.form.get("data"),
                inicio_texto=request.form.get("hora_inicio"),
                fim_texto=request.form.get("hora_fim"),
                duracao_texto=request.form.get("duracao"),
            )
        except NaoEncontrado:
            abort(404)
        except AcessoNegado:
            abort(403)
        except ErroDeNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash(
                "1 horário gerado com sucesso."
                if quantidade == 1
                else f"{quantidade} horários gerados com sucesso.",
                "success",
            )
            return redirect(
                url_for("disponibilidades.gerenciar", profissional_id=profissional_id)
            )

    pagina = max(request.args.get("page", 1, type=int), 1)
    try:
        profissional, horarios = disponibilidade_service.listar_do_profissional(
            current_user, profissional_id, pagina
        )
    except NaoEncontrado:
        abort(404)
    except AcessoNegado:
        abort(403)

    return render_template(
        "disponibilidades/gerenciar.html",
        profissional=profissional,
        horarios=horarios,
        valores=valores,
    )


@disponibilidades_bp.route("/<int:disponibilidade_id>/remover", methods=["POST"])
@recepcionista_required
def remover(disponibilidade_id):
    pagina = max(request.form.get("page", 1, type=int), 1)
    try:
        profissional_id = disponibilidade_service.obter(disponibilidade_id).profissional_id
        disponibilidade_service.remover(current_user, disponibilidade_id)
    except NaoEncontrado:
        abort(404)
    except AcessoNegado:
        abort(403)
    except ErroDeNegocio as erro:
        flash(str(erro), "danger")
    else:
        flash("Horário removido.", "success")

    return redirect(
        url_for("disponibilidades.gerenciar", profissional_id=profissional_id, page=pagina)
    )