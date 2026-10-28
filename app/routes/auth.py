from datetime import date
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.services import auth_service
from app.services.errors import ErroDeNegocio

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _destino_seguro(destino):
    if not destino or not destino.startswith("/") or destino.startswith("//") or "\\" in destino:
        return None
    partes = urlparse(destino)
    if partes.scheme or partes.netloc:
        return None
    return destino


def _converter_data(texto):
    try:
        return date.fromisoformat(texto or "")
    except ValueError:
        return None


@auth_bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    dados = {}
    if request.method == "POST":
        dados = request.form
        try:
            auth_service.registrar_cliente(
                nome=request.form.get("nome"),
                email=request.form.get("email"),
                senha=request.form.get("senha"),
                cpf=request.form.get("cpf"),
                data_nascimento=_converter_data(request.form.get("data_nascimento")),
                telefone=request.form.get("telefone"),
            )
        except ErroDeNegocio as erro:
            flash(str(erro), "danger")
        else:
            flash("Conta criada! Faça login para continuar.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/cadastro.html", dados=dados)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        try:
            usuario = auth_service.autenticar(
                request.form.get("email"), request.form.get("senha")
            )
        except ErroDeNegocio as erro:
            flash(str(erro), "danger")
        else:
            login_user(usuario)
            return redirect(_destino_seguro(request.args.get("next")) or url_for("main.index"))

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("auth.login"))