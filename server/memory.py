import logging
import time
import uuid
from pathlib import Path

try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self):
        self.enabled = chromadb is not None
        self._initialized = False
        self.client = None
        self.collection = None

        if not self.enabled:
            logger.warning("[MEMORY] ChromaDB não instalado. Memória desativada.")

    def _get_persist_dir(self) -> str:
        """
        Resolve o diretório de persistência em runtime (não no import),
        para que o config já tenha detectado o Network Volume corretamente.
        """
        from server.config import config
        return config.memory_db_path

    def _ensure_initialized(self):
        """Inicialização lazy — só conecta ao banco quando for usar."""
        if self._initialized or not self.enabled:
            return

        persist_dir = self._get_persist_dir()
        logger.info(f"[MEMORY] Inicializando ChromaDB em: {persist_dir}")

        try:
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=persist_dir)
            self.collection = self.client.get_or_create_collection(name="bimo_conversations")
            self._initialized = True
            logger.info("[MEMORY] Banco de memórias pronto.")
        except Exception as e:
            logger.error(f"[MEMORY] Falha ao inicializar ChromaDB: {e}")
            self.enabled = False

    def add_memory(self, user_text: str, bimo_text: str):
        self._ensure_initialized()
        if not self.enabled or self.collection is None:
            return

        doc_id = str(uuid.uuid4())
        document = f"Usuário: {user_text}\nBIMO: {bimo_text}"
        try:
            self.collection.add(
                documents=[document],
                metadatas=[{"timestamp": time.time()}],
                ids=[doc_id],
            )
            logger.debug("[MEMORY] Lembrança guardada.")
        except Exception as e:
            logger.error(f"[MEMORY] Erro ao salvar memória: {e}")

    def retrieve_relevant(self, query: str, n_results: int = 3) -> str:
        self._ensure_initialized()
        if not self.enabled or self.collection is None:
            return ""

        try:
            count = self.collection.count()
            if count == 0:
                return ""

            results = self.collection.query(
                query_texts=[query],
                n_results=min(n_results, count),
            )
            docs = results.get("documents")
            if not docs or not docs[0]:
                return ""
            return "\n".join(docs[0])
        except Exception as e:
            logger.error(f"[MEMORY] Erro ao buscar memórias: {e}")
            return ""


memory_manager = MemoryManager()
