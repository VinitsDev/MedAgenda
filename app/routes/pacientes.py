from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import recepcionista_required
from app.services import paciente_service
from app.services.errors import AcessoNegado, ErroDeNegocio, NaoEncontrado
from app.services.validacoes import converter_data

pacientes_bp = Blueprint("pacientes", __name__, url_prefix="/pacientes")


def _carregar(paciente_id):
    try:
        return paciente_service.obter(current_user, paciente_id)
    except NaoEncontrado:
        abort(404)
    except AcessoNegado:
        abort(403)


@pacientes_bp.route("/")
@recepcionista_required
def lista():
    busca = request.args.get("q", "").strip()[:100]
    pagina = request.args.get("page", 1, type=int)
    resultado = paciente_service.listar(current_user, busca=busca, pagina=max(pagina, 1))
    return render_template("pacientes/lista.html", pacientes=resultado, busca=busca)


@pacientes_bp.route("/novo", methods=["GET", "POST"])
@recepcionista_required
def novo():
    valores = {}
    if request.method == "POST":
        valores = request.form
        try:
            paciente = paciente_service.cadastrar(
                current_user,
                nome=request.form.get("nome"),
                cpf=request.form.get("cpf"),
                data_nascimento=converter_data(request.form.get("data_nascimento")),
                telefone=request.form.get("telefone"),
            )
        except ErroDeNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash("Paciente cadastrado com sucesso.", "success")
            return redirect(url_for("pacientes.detalhe", paciente_id=paciente.id))

    return render_template(
        "pacientes/form.html",
        titulo="Novo paciente",
        valores=valores,
        documentos_editaveis=True,
        cancelar_url=url_for("pacientes.lista"),
    )


@pacientes_bp.route("/meu")
@login_required
def meu():
    paciente = paciente_service.paciente_do_usuario(current_user)
    if paciente is None:
        flash("Nenhum cadastro de paciente está vinculado à sua conta.", "info")
        return redirect(url_for("main.index"))
    return redirect(url_for("pacientes.detalhe", paciente_id=paciente.id))


@pacientes_bp.route("/<int:paciente_id>")
@login_required
def detalhe(paciente_id):
    paciente = _carregar(paciente_id)
    return render_template("pacientes/detalhe.html", paciente=paciente)


@pacientes_bp.route("/<int:paciente_id>/editar", methods=["GET", "POST"])
@login_required
def editar(paciente_id):
    paciente = _carregar(paciente_id)

    if request.method == "POST":
        valores = request.form
        try:
            paciente_service.atualizar(
                current_user,
                paciente_id,
                nome=request.form.get("nome"),
                telefone=request.form.get("telefone"),
                cpf=request.form.get("cpf"),
                data_nascimento=converter_data(request.form.get("data_nascimento")),
            )
        except ErroDeNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash("Cadastro atualizado.", "success")
            return redirect(url_for("pacientes.detalhe", paciente_id=paciente_id))
    else:
        valores = {
            "nome": paciente.nome,
            "cpf": paciente.cpf,
            "data_nascimento": paciente.data_nascimento.isoformat(),
            "telefone": paciente.telefone or "",
        }

    return render_template(
        "pacientes/form.html",
        titulo="Editar paciente",
        valores=valores,
        documentos_editaveis=current_user.eh_recepcionista,
        cancelar_url=url_for("pacientes.detalhe", paciente_id=paciente_id),
    )