from app.services.errors import AcessoNegado


def exigir_recepcionista(usuario):
    if not usuario.eh_recepcionista:
        raise AcessoNegado("Apenas a recepção pode realizar esta ação.")