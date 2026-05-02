import logging

logger = logging.getLogger(__name__)

def handle(action_input: dict) -> dict:
    logger.info(f"[MODULE: alexa] Comando Alexa: {action_input}")
    return {
        "success": True, "mocked_action": "Comando enviado para skill da Alexa"
    }