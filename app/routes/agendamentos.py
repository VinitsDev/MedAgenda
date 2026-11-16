from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import recepcionista_required
from app.services import agendamento_service
from app.services.errors import AcessoNegado, ErroDeNegocio, NaoEncontrado

agendamentos_bp = Blueprint("agendamentos", __name__, url_prefix="/agendamentos")


def _carregar(agendamento_id):
    try:
        return agendamento_service.obter(current_user, agendamento_id)
    except NaoEncontrado:
        abort(404)
    except AcessoNegado:
        abort(403)


@agendamentos_bp.route("/")
@recepcionista_required
def lista():
    busca = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "").strip()[:20]
    pagina = max(request.args.get("page", 1, type=int), 1)

    try:
        resultado = agendamento_service.listar_todos(
            current_user, busca=busca, status_texto=status, pagina=pagina
        )
    except ErroDeNegocio as erro:
        flash(str(erro), "danger")
        status = ""
        resultado = agendamento_service.listar_todos(
            current_user, busca=busca, status_texto=None, pagina=pagina
        )

    return render_template(
        "agendamentos/lista.html", agendamentos=resultado, busca=busca, status=status
    )


@agendamentos_bp.route("/meus")
@login_required
def meus():
    if current_user.eh_recepcionista:
        return redirect(url_for("agendamentos.lista"))

    pagina = max(request.args.get("page", 1, type=int), 1)
    try:
        resultado = agendamento_service.listar_do_paciente(current_user, pagina)
    except ErroDeNegocio as erro:
        flash(str(erro), "info")
        return redirect(url_for("main.index"))
    return render_template("agendamentos/meus.html", agendamentos=resultado)


@agendamentos_bp.route("/novo/<int:disponibilidade_id>", methods=["GET", "POST"])
@login_required
def novo(disponibilidade_id):
    valores = {}
    if request.method == "POST":
        valores = request.form
        try:
            agendamento = agendamento_service.criar(
                current_user, disponibilidade_id, cpf=request.form.get("cpf")
            )
        except NaoEncontrado:
            abort(404)
        except AcessoNegado:
            abort(403)
        except ErroDeNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash("Consulta agendada com sucesso.", "success")
            return redirect(
                url_for("agendamentos.detalhe", agendamento_id=agendamento.id)
            )

    try:
        disponibilidade = agendamento_service.horario_para_agendar(
            current_user, disponibilidade_id
        )
    except NaoEncontrado:
        abort(404)
    except ErroDeNegocio as erro:
        if request.method == "GET":  # no POST, o erro já foi mostrado acima
            flash(str(erro), "danger")
        return redirect(url_for("disponibilidades.consulta"))

    return render_template(
        "agendamentos/confirmar.html", disponibilidade=disponibilidade, valores=valores
    )


@agendamentos_bp.route("/<int:agendamento_id>")
@login_required
def detalhe(agendamento_id):
    agendamento = _carregar(agendamento_id)
    return render_template("agendamentos/detalhe.html", agendamento=agendamento)


@agendamentos_bp.route("/<int:agendamento_id>/cancelar", methods=["POST"])
@login_required
def cancelar(agendamento_id):
    try:
        agendamento_service.cancelar(current_user, agendamento_id)
    except NaoEncontrado:
        abort(404)
    except AcessoNegado:
        abort(403)
    except ErroDeNegocio as erro:
        flash(str(erro), "danger")
    else:
        flash("Agendamento cancelado.", "success")
    return redirect(url_for("agendamentos.detalhe", agendamento_id=agendamento_id))

@agendamentos_bp.route("/<int:agendamento_id>/remarcar", methods=["GET", "POST"])
@login_required
def remarcar(agendamento_id):
    if request.method == "POST":
        try:
            novo = agendamento_service.remarcar(
                current_user,
                agendamento_id,
                request.form.get("disponibilidade_id", type=int),
            )
        except NaoEncontrado:
            abort(404)
        except AcessoNegado:
            abort(403)
        except ErroDeNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash("Consulta remarcada com sucesso.", "success")
            return redirect(url_for("agendamentos.detalhe", agendamento_id=novo.id))

    pagina = max(request.args.get("page", 1, type=int), 1)
    try:
        agendamento, horarios = agendamento_service.horarios_para_remarcar(
            current_user, agendamento_id, pagina
        )
    except NaoEncontrado:
        abort(404)
    except AcessoNegado:
        abort(403)
    except ErroDeNegocio as erro:
        if request.method == "GET":  # no POST, o erro já foi mostrado acima
            flash(str(erro), "danger")
        return redirect(url_for("agendamentos.detalhe", agendamento_id=agendamento_id))

    return render_template(
        "agendamentos/remarcar.html", agendamento=agendamento, horarios=horarios
    )


@agendamentos_bp.route("/<int:agendamento_id>/status", methods=["POST"])
@recepcionista_required
def alterar_status(agendamento_id):
    try:
        agendamento_service.alterar_status(
            current_user, agendamento_id, request.form.get("status")
        )
    except NaoEncontrado:
        abort(404)
    except AcessoNegado:
        abort(403)
    except ErroDeNegocio as erro:
        flash(str(erro), "danger")
    else:
        flash("Status atualizado.", "success")
    return redirect(url_for("agendamentos.detalhe", agendamento_id=agendamento_id))