import logging

logger = logging.getLogger(__name__)

def handle(action_input: dict) -> dict:
    logger.info(f"[MODULE: calendar] Ação de Calendário: {action_input}")
    return {
        "success": True, "mocked_action": "Evento inserido/consultado no calendário"
    }