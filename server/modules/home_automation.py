import logging

logger = logging.getLogger(__name__)

def handle(action_input: dict) -> dict:
    logger.info(f"[MODULE: home_automation] Ação solicitada: {action_input}")
    return {
        "success": True, 
        "mocked_action": f"Ligando/Desligando dispositivo: {action_input.get('device')}"
    }