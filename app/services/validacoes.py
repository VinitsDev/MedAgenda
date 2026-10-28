import re
from datetime import date

from app.services.errors import ErroDeNegocio


def somente_digitos(texto):
    return re.sub(r"\D", "", texto or "")


def converter_data(texto):
    try:
        return date.fromisoformat(texto or "")
    except ValueError:
        return None


def validar_nome(nome):
    nome = (nome or "").strip()
    if not nome or len(nome) > 120:
        raise ErroDeNegocio("Informe um nome de até 120 caracteres.")
    return nome


def validar_cpf(cpf):
    cpf = somente_digitos(cpf)
    if len(cpf) != 11:
        raise ErroDeNegocio("Informe um CPF com 11 dígitos.")
    return cpf


def validar_data_nascimento(data_nascimento):
    if data_nascimento is None or not (date(1900, 1, 1) <= data_nascimento <= date.today()):
        raise ErroDeNegocio("Informe uma data de nascimento válida.")
    return data_nascimento


def validar_telefone(telefone):
    telefone = somente_digitos(telefone)
    if len(telefone) > 20:
        raise ErroDeNegocio("Telefone muito longo.")
    return telefone or None