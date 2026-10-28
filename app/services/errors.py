class ErroDeNegocio(Exception):
    """Regra de negócio violada. A mensagem já está pronta para o usuário."""


class NaoEncontrado(Exception):
    """O registro pedido não existe."""


class AcessoNegado(Exception):
    """O usuário está logado, mas não tem permissão para este registro."""