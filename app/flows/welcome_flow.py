def build_main_menu(name: str | None = None) -> str:
    greeting = f"Oi, {name}!" if name else "Oi!"
    return (
        f"{greeting} Sou a assistente virtual da clinica.\n\n"
        "Posso te ajudar com:\n"
        "1. Agendar consulta\n"
        "2. Falar com um atendente\n"
        "3. Tirar duvidas gerais\n\n"
        "Me diga o numero da opcao ou escreva o que voce precisa."
    )
