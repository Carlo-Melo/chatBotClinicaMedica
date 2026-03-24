def build_human_handoff_message() -> str:
    return (
        "Tudo bem. Vou pausar o atendimento automatico e encaminhar sua conversa para nossa equipe.\n\n"
        "Se quiser voltar para o bot depois, escreva 'voltar para o bot'."
    )


def build_ai_resumed_message() -> str:
    return (
        "Atendimento automatico reativado.\n\n"
        "Posso ajudar com agendamento, duvidas gerais ou direcionar para suporte humano."
    )
