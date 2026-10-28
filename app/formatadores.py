def formatar_cpf(cpf):
    cpf = cpf or ""
    if len(cpf) != 11 or not cpf.isdigit():
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def formatar_telefone(telefone):
    telefone = telefone or ""
    if not telefone.isdigit():
        return telefone
    if len(telefone) == 11:
        return f"({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}"
    if len(telefone) == 10:
        return f"({telefone[:2]}) {telefone[2:6]}-{telefone[6:]}"
    return telefone


def formatar_data(data):
    return data.strftime("%d/%m/%Y") if data else ""