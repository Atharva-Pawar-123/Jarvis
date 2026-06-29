import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import config
import numpy as np
from modules.utils import robust_json_parse

logger = logging.getLogger(__name__)


class LongTermMemory:
    """
    Manages long-term storage of user-related facts using both 
    key-value pairs and semantic vector search.
    """

    def __init__(self) -> None:
        self.data_dir = Path(config.BASE_DIR) / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.kv_path = self.data_dir / "long_term_memory.json"
        self.vector_path = self.data_dir / "semantic_memory.json"
        
        self.kv_data: Dict[str, Any] = self._load_kv()
        self.semantic_data: List[Dict[str, Any]] = self._load_semantic()
        
        self._lock = threading.Lock()
        self._model = None # Lazy-loaded SentenceTransformer

    def _load_kv(self) -> Dict[str, Any]:
        if self.kv_path.exists():
            try:
                return json.loads(self.kv_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.error(f"Failed to load KV memory: {exc}")
        return {}

    def _load_semantic(self) -> List[Dict[str, Any]]:
        if self.vector_path.exists():
            try:
                return json.loads(self.vector_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.error(f"Failed to load semantic memory: {exc}")
        return []

    def _save(self) -> None:
        try:
            with self._lock:
                self.kv_path.write_text(json.dumps(self.kv_data, indent=4), encoding="utf-8")
                self.vector_path.write_text(json.dumps(self.semantic_data, indent=4), encoding="utf-8")
        except Exception as exc:
            logger.error(f"Failed to save memory: {exc}")

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading semantic embedding model...")
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Embedding model loaded.")

    def store_semantic(self, text: str, metadata: Optional[dict] = None) -> None:
        """Store a text string with its vector embedding."""
        self._ensure_model()
        embedding = self._model.encode(text).tolist()
        
        entry = {
            "text": text,
            "embedding": embedding,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        
        with self._lock:
            self.semantic_data.append(entry)
        self._save()

    def query_semantic(self, query: str, top_k: int = 3) -> List[str]:
        """Search for the most relevant facts using cosine similarity."""
        if not self.semantic_data:
            return []
            
        self._ensure_model()
        query_vec = self._model.encode(query)
        
        results = []
        for entry in self.semantic_data:
            vec = np.array(entry["embedding"])
            # Cosine similarity
            score = np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec))
            results.append((score, entry["text"]))
            
        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [text for score, text in results[:top_k] if score > 0.4]

    def get_context_string(self, query: Optional[str] = None) -> str:
        """
        Returns a context string. If query is provided, includes semantic results.
        """
        facts = []
        if self.kv_data:
            facts.extend([f"{k}: {v}" for k, v in self.kv_data.items()])
            
        if query:
            semantic_facts = self.query_semantic(query)
            facts.extend(semantic_facts)
            
        if not facts:
            return ""
            
        return "\n".join(facts)

    def update_kv(self, key: str, value: Any) -> None:
        with self._lock:
            self.kv_data[key] = value
        self._save()

    def get_kv(self, key: str) -> Optional[Any]:
        return self.kv_data.get(key)

    def extract_facts_background(self, user_text: str, assistant_response: str, llm_engine: Any) -> None:
        threading.Thread(
            target=self._extract_logic,
            args=(user_text, assistant_response, llm_engine),
            daemon=True
        ).start()

    def _extract_logic(self, user_text: str, assistant_response: str, llm_engine: Any) -> None:
        prompt = f"""Extract any permanent personal facts or preferences about the user from this exchange.
User: "{user_text}"
Assistant: "{assistant_response}"

Return a JSON object with keys like "name", "job", "hobbies", etc.
If no facts, return {{}}.
Return ONLY the JSON."""

        try:
            response_text = llm_engine.generate([{"role": "user", "content": prompt}])
            if "{" in response_text and "}" in response_text:
                json_str = response_text[response_text.find("{"):response_text.rfind("}")+1]
                new_facts = robust_json_parse(json_str)
                for k, v in new_facts.items():
                    self.update_kv(k, v)
                    # Also store semantically for fuzzy retrieval
                    self.store_semantic(f"User {k} is {v}")
        except Exception as exc:
            logger.error(f"Fact extraction failed: {exc}")

    def get_user_profile_summary(self) -> str:
        """
        Returns a natural language summary of the user's known profile.
        """
        if not self.kv_data:
            return "The user is unknown. Address them as 'sir'."
            
        summary = f"The user's name is {self.kv_data.get('user_name', 'sir')}."
        if 'profession' in self.kv_data:
            summary += f" Their profession is {self.kv_data['profession']}."
        if 'interests' in self.kv_data:
            summary += f" They are interested in {', '.join(self.kv_data['interests'])}."
            
        return summary

    def auto_dream(self, llm_engine: Any) -> None:
        """
        Consolidates recent memory logs into a dense MEMORY.md file
        and updates long-term storage, to be run on shutdown.
        """
        logger.info("Initiating autoDream memory consolidation sequence...")
        # A lightweight version for laptop-optimized JARVIS
        prompt = f"""You are autoDream, a memory consolidation process.
Review the following known facts about the user:
{json.dumps(self.kv_data, indent=2)}

Synthesize these facts into a compact, highly optimized Markdown document summarizing the user's profile, preferences, and state.
Keep it under 500 words. Return only the Markdown content."""
        try:
            dream_content = llm_engine.generate([{"role": "system", "content": prompt}])
            memory_file = self.data_dir / "MEMORY.md"
            memory_file.write_text(dream_content, encoding="utf-8")
            logger.info("autoDream sequence complete. MEMORY.md updated.")
        except Exception as exc:
            logger.error(f"autoDream failed: {exc}")



