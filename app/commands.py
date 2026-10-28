import click

from app.services import auth_service
from app.services.errors import ErroDeNegocio


def registrar_comandos(app):
    @app.cli.command("criar-recepcionista")
    @click.option("--nome", prompt="Nome")
    @click.option("--email", prompt="E-mail")
    @click.password_option("--senha")
    def criar_recepcionista(nome, email, senha):
        """Cria um usuário com perfil de recepcionista."""
        try:
            usuario = auth_service.criar_recepcionista(nome, email, senha)
        except ErroDeNegocio as erro:
            raise click.ClickException(str(erro))
        click.echo(f"Recepcionista criado: {usuario.email}")