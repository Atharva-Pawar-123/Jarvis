import json
import logging
import threading
import datetime
import uuid
import os
import chromadb
from rank_bm25 import BM25Okapi

import config

class HybridRAGMemory:
    """
    Hybrid RAG System combining BM25 keyword search and ChromaDB semantic search,
    with Reciprocal Rank Fusion (RRF) for optimal context retrieval.
    """
    def __init__(self, llm_engine):
        self.llm = llm_engine
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        self.facts_col = self.chroma_client.get_or_create_collection("jarvis_facts")
        self.convs_col = self.chroma_client.get_or_create_collection("jarvis_conversations")
        self.docs_col = self.chroma_client.get_or_create_collection("jarvis_documents")
        
        # Initialize BM25
        self.bm25_corpus = []
        self.bm25_metadata = [] # stores dicts: {"text": str, "source": str, "metadata": dict}
        self.bm25_index = None
        self._load_bm25()
        
        logging.info("HybridRAGMemory initialized successfully.")

    def _load_bm25(self):
        if config.BM25_CORPUS.exists():
            try:
                with open(config.BM25_CORPUS, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data and isinstance(data[0], str):
                        self.bm25_corpus = data
                        self.bm25_metadata = [{"text": d, "source": "legacy", "metadata": {}, "id": ""} for d in data]
                    else:
                        self.bm25_corpus = [d['text'] for d in data]
                        self.bm25_metadata = data
                self._rebuild_bm25()
            except Exception as e:
                logging.error(f"Failed to load BM25 corpus: {e}")
        else:
            self._rebuild_bm25()

    def _save_bm25(self):
        try:
            with open(config.BM25_CORPUS, 'w', encoding='utf-8') as f:
                json.dump(self.bm25_metadata, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save BM25 corpus: {e}")

    def _rebuild_bm25(self):
        if self.bm25_corpus:
            tokenized = [doc.lower().split() for doc in self.bm25_corpus]
            self.bm25_index = BM25Okapi(tokenized)
        else:
            self.bm25_index = None

    def add_fact(self, fact: str, metadata: dict = None):
        """Store a fact via semantic and keyword memory."""
        metadata = metadata or {}
        doc_id = str(uuid.uuid4())
        
        # 1. Semantic (ChromaDB)
        emb = self.llm.embed(fact)
        self.facts_col.add(
            ids=[doc_id],
            embeddings=[emb],
            documents=[fact],
            metadatas=[metadata]
        )
        
        # 2. Keyword (BM25)
        self.bm25_corpus.append(fact)
        self.bm25_metadata.append({"text": fact, "source": "fact", "metadata": metadata, "id": doc_id})
        self._rebuild_bm25()
        self._save_bm25()
        
        logging.info(f"Learned new fact: {fact}")

    def add_conversation_summary(self, summary: str, timestamp: str):
        doc_id = str(uuid.uuid4())
        metadata = {"timestamp": timestamp}
        
        emb = self.llm.embed(summary)
        self.convs_col.add(
            ids=[doc_id],
            embeddings=[emb],
            documents=[summary],
            metadatas=[metadata]
        )
        
        self.bm25_corpus.append(summary)
        self.bm25_metadata.append({"text": summary, "source": "conversation", "metadata": metadata, "id": doc_id})
        self._rebuild_bm25()
        self._save_bm25()

    def ingest_document(self, file_path: str) -> str:
        """Reads a file, chunks it, and embeds it into knowledge base."""
        if not os.path.exists(file_path):
            return f"Error: File {file_path} not found."
            
        ext = os.path.splitext(file_path)[1].lower()
        text = ""
        
        try:
            if ext == '.pdf':
                import fitz # PyMuPDF
                with fitz.open(file_path) as doc:
                    for page in doc:
                        text += page.get_text() + "\n"
            elif ext == '.docx':
                import docx
                doc = docx.Document(file_path)
                text = "\n".join([p.text for p in doc.paragraphs])
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
        except Exception as e:
            return f"Failed to read file {file_path}. {str(e)}"
            
        if not text.strip():
            return "File appears to be empty."
            
        # Chunking (500 words, 50 word overlap)
        words = text.split()
        chunk_size = 500
        overlap = 50
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            
        # Embed and Store
        base_name = os.path.basename(file_path)
        timestamp = datetime.datetime.now().isoformat()
        
        # Embed batch
        embeddings = self.llm.embed_batch(chunks)
        
        for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
            doc_id = f"{base_name}_{uuid.uuid4().hex[:8]}"
            metadata = {"source_file": base_name, "chunk": idx, "total": len(chunks), "date": timestamp}
            
            self.docs_col.add(
                ids=[doc_id],
                embeddings=[emb],
                documents=[chunk_text],
                metadatas=[metadata]
            )
            
            self.bm25_corpus.append(chunk_text)
            self.bm25_metadata.append({"text": chunk_text, "source": "document", "metadata": metadata, "id": doc_id})
            
        self._rebuild_bm25()
        self._save_bm25()
        
        return f"Ingested {len(chunks)} chunks from {base_name}, sir."

    def search(self, query: str, n_results: int = 5, collection: str = "all") -> list:
        """Hybrid Search combining Semantic + BM25 using RRF."""
        semantic_results = []
        try:
            emb = self.llm.embed(query)
            
            cols_to_search = []
            if collection == "all":
                cols_to_search = [self.facts_col, self.convs_col, self.docs_col]
            elif collection == "facts":
                cols_to_search = [self.facts_col]
            elif collection == "documents":
                cols_to_search = [self.docs_col]
                
            for col in cols_to_search:
                # Get more than n_results to allow good re-ranking fusion
                res = col.query(query_embeddings=[emb], n_results=n_results * 2)
                for i in range(len(res['documents'][0])):
                    doc = res['documents'][0][i]
                    dist = res['distances'][0][i]
                    meta = res['metadatas'][0][i] if res['metadatas'][0] else {}
                    # Convert distance to a similarity score (lower dist = higher sim)
                    score = max(0, 1.0 - (dist / 2.0))
                    semantic_results.append({"text": doc, "score": score, "metadata": meta})
                    
            # Sort semantic results
            semantic_results.sort(key=lambda x: x["score"], reverse=True)
            semantic_results = semantic_results[:n_results * 2]
        except Exception as e:
            logging.error(f"Semantic search failed: {e}")

        # BM25 Keyword Search
        bm25_results = []
        if self.bm25_index:
            try:
                tokenized_query = query.lower().split()
                scores = self.bm25_index.get_scores(tokenized_query)
                # Get top indices
                top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_results * 2]
                
                max_score = max(scores) if scores.size > 0 and max(scores) > 0 else 1.0
                
                for idx in top_indices:
                    if scores[idx] > 0:
                        bm25_results.append({
                            "text": self.bm25_metadata[idx]["text"],
                            "score": scores[idx] / max_score, # Normalize
                            "metadata": self.bm25_metadata[idx]["metadata"]
                        })
            except Exception as e:
                logging.error(f"BM25 search failed: {e}")

        # Reciprocal Rank Fusion (RRF)
        fused = {}
        k = 60 # RRF constant
        
        for rank, item in enumerate(semantic_results):
            text = item["text"]
            fused[text] = {"text": text, "metadata": item["metadata"], "rrf_score": 1.0 / (rank + 1 + k)}
            
        for rank, item in enumerate(bm25_results):
            text = item["text"]
            if text in fused:
                fused[text]["rrf_score"] += 1.0 / (rank + 1 + k)
            else:
                fused[text] = {"text": text, "metadata": item["metadata"], "rrf_score": 1.0 / (rank + 1 + k)}
                
        # Sort by RRF score
        final_list = list(fused.values())
        final_list.sort(key=lambda x: x["rrf_score"], reverse=True)
        
        return final_list[:n_results]

    def get_relevant_context(self, query: str) -> str:
        results = self.search(query, n_results=3)
        if not results:
            return ""
            
        context_str = "RELEVANT MEMORY (Use this if helpful, ignore if irrelevant):\n"
        for r in results:
            context_str += f"- {r['text']}\n"
        return context_str.strip()

    def extract_and_store_facts(self, user_text: str, assistant_response: str):
        """Runs in background to extract learnable facts from the conversation turn."""
        def _extract_task():
            prompt = [
                {"role": "system", "content": (
                    "Extract any learnable facts, preferences, or important information from this exchange. "
                    "Return a JSON array of fact strings. Max 3 facts. "
                    "Return [] if nothing worth storing. Return ONLY the JSON array. No markdown."
                )},
                {"role": "user", "content": f"User: {user_text}\nJARVIS: {assistant_response}"}
            ]
            try:
                res = self.llm._generate_blocking(prompt, self.llm.FAST_MODEL)
                import json, re
                
                # Cleanup markdown and parse
                res = res.strip()
                if res.startswith("```json"): res = res[7:]
                if res.startswith("```"): res = res[3:]
                if res.endswith("```"): res = res[:-3]
                
                try:
                    facts = json.loads(res.strip())
                except json.JSONDecodeError:
                    match = re.search(r'\[.*\]', res, re.DOTALL)
                    if match:
                        facts = json.loads(match.group(0))
                    else:
                        facts = []
                        
                if isinstance(facts, list):
                    for fact in facts:
                        if isinstance(fact, str) and len(fact) > 5:
                            self.add_fact(fact)
            except Exception as e:
                logging.warning(f"Fact extraction failed in background: {e}")

        threading.Thread(target=_extract_task, daemon=True).start()

    def clear_all(self):
        # We delete by recreating the DB or wiping data
        try:
            self.chroma_client.delete_collection("jarvis_facts")
            self.chroma_client.delete_collection("jarvis_conversations")
            self.chroma_client.delete_collection("jarvis_documents")
            self.facts_col = self.chroma_client.create_collection("jarvis_facts")
            self.convs_col = self.chroma_client.create_collection("jarvis_conversations")
            self.docs_col = self.chroma_client.create_collection("jarvis_documents")
            
            self.bm25_corpus = []
            self.bm25_metadata = []
            self.bm25_index = None
            self._save_bm25()
            
            logging.info("Memory cleared completely, sir.")
        except Exception as e:
            logging.error(f"Error clearing memory: {e}")
