"""Simulador de envio de e-mail para desenvolvimento e QA.

No futuro, substituir a impressão em console por um cliente SMTP real.
"""


def send_email(recipient: str, subject: str, body: str) -> None:
    """Imprime o e-mail no console, simulando o despacho por SMTP."""
    print(
        "\n===== E-MAIL SIMULADO =====\n"
        f"Para: {recipient}\n"
        f"Assunto: {subject}\n\n"
        f"{body}\n"
        "==========================="
    )
