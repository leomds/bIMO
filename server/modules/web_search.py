import logging

logger = logging.getLogger(__name__)

def handle(action_input: dict) -> dict:
    logger.info(f"[MODULE: web_search] Pesquisando web por: {action_input}")
    return {
        "success": True, "mocked_action": "Busca na internet realizada"
    }