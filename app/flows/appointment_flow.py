def build_doctor_prompt(doctors: list[str]) -> str:
    options = "\n".join(f"{index}. {doctor}" for index, doctor in enumerate(doctors, start=1))
    return (
        "Vamos seguir com o agendamento.\n\n"
        "Escolha o medico ou especialidade:\n"
        f"{options}\n\n"
        "Responda com o numero ou com o nome."
    )


def build_invalid_doctor_message(doctors: list[str]) -> str:
    options = "\n".join(f"{index}. {doctor}" for index, doctor in enumerate(doctors, start=1))
    return (
        "Nao consegui identificar a opcao escolhida.\n\n"
        "Escolha uma das opcoes abaixo:\n"
        f"{options}"
    )


def build_date_prompt(doctor: str) -> str:
    return (
        f"Perfeito. Para {doctor}, qual data voce prefere?\n\n"
        "Pode responder, por exemplo, com:\n"
        "- 28/03\n"
        "- 28/03/2026\n"
        "- amanha"
    )


def build_invalid_date_message() -> str:
    return (
        "Nao consegui entender a data desejada.\n"
        "Me envie no formato DD/MM, DD/MM/AAAA ou com termos como 'amanha'."
    )


def build_confirmation_prompt(doctor: str, requested_date: str) -> str:
    return (
        "Confirma este pedido de agendamento?\n\n"
        f"Medico/especialidade: {doctor}\n"
        f"Data desejada: {requested_date}\n\n"
        "Responda com 'sim' para confirmar ou 'nao' para ajustar."
    )


def build_confirmation_retry_message() -> str:
    return "Me responda com 'sim' para confirmar ou 'nao' para voltar e ajustar o agendamento."


def build_success_message(doctor: str, requested_date: str) -> str:
    return (
        "Seu pedido de agendamento foi registrado com sucesso.\n\n"
        f"Medico/especialidade: {doctor}\n"
        f"Data desejada: {requested_date}\n\n"
        "Nossa equipe vai confirmar a disponibilidade e retornar para voce."
    )


def build_restart_message() -> str:
    return "Sem problema. Vamos reiniciar o agendamento. Escolha novamente o medico ou especialidade."
