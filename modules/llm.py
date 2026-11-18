import logging
import threading
import time
from typing import List, Dict, Callable
import ollama
import diskcache

import config

class IntelligentLLMEngine:
    """
    PURPOSE: The single brain of JARVIS. Routes queries to the right model based
    on complexity, implements chain-of-thought reasoning, self-reflection, and
    streaming output. Zero cloud API calls. Fully local.
    """

    def __init__(self, system_prompt: str, stream_callback: Callable = None, state_callback: Callable = None, gpu_scheduler = None):
        self.PRIMARY_MODEL = config.PRIMARY_MODEL
        self.FAST_MODEL = config.FAST_MODEL
        self.CODER_MODEL = config.CODER_MODEL
        self.EMBED_MODEL = config.EMBED_MODEL
        self.VISION_MODEL = config.VISION_MODEL

        self.system_prompt = system_prompt
        self.stream_callback = stream_callback
        self.state_callback = state_callback
        self.gpu_scheduler = gpu_scheduler
        
        self.client = ollama.Client(host=config.OLLAMA_HOST)
        self.cache = diskcache.Cache(str(config.CACHE_DIR), size_limit=500 * 1024 * 1024)
        
        self.token_counter = {"primary": 0, "fast": 0, "coder": 0}
        
        # Start pre-warming models
        threading.Thread(target=self.pre_warm, daemon=True).start()
        
        logging.info(f"LLM Engine initialized. Primary: {self.PRIMARY_MODEL} | Fast: {self.FAST_MODEL}")

    def pre_warm(self):
        """Pre-loads models into GPU VRAM."""
        try:
            for model in [self.FAST_MODEL, self.PRIMARY_MODEL, self.CODER_MODEL]:
                self.client.generate(model=model, prompt="hi", keep_alive=config.OLLAMA_KEEP_ALIVE)
            logging.info("All models warm and ready.")
        except Exception as e:
            logging.error(f"Failed to pre-warm models: {e}")

    def generate(self, messages: List[Dict], stream: bool = True, use_cot: bool = False, model: str = None) -> str:
        model = model or self.PRIMARY_MODEL
        
        # Coordinate GPU VRAM allocation if scheduler is attached
        if self.gpu_scheduler and hasattr(self.gpu_scheduler, "prepare_for_llm"):
            try:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.gpu_scheduler.prepare_for_llm())
                except RuntimeError:
                    asyncio.run(self.gpu_scheduler.prepare_for_llm())
            except Exception:
                pass

        retries = 3
        for attempt in range(retries):
            try:
                if use_cot:
                    return self.chain_of_thought(messages, model)
                
                # Prepend the system prompt if not present
                has_system = any(m.get("role") == "system" for m in messages)
                final_messages = messages.copy()
                if not has_system:
                    final_messages.insert(0, {"role": "system", "content": self.system_prompt})
                
                if stream:
                    return self._generate_streaming(final_messages, model)
                else:
                    return self._generate_blocking(final_messages, model)
            except Exception as e:
                logging.warning(f"Ollama generation failed (attempt {attempt+1}/{retries}): {e}")
                time.sleep(2)
        
        raise RuntimeError(f"Ollama is unreachable after {retries} retries.")

    def _generate_streaming(self, messages: List[Dict], model: str) -> str:
        if self.state_callback:
            self.state_callback("thinking")
            
        stream = self.client.chat(model=model, messages=messages, stream=True)
        full_response = ""
        
        for chunk in stream:
            content = chunk.get("message", {}).get("content", "")
            if content:
                full_response += content
                if self.stream_callback:
                    self.stream_callback(content)
                    
        # Token count approximation since stream=True doesn't easily return eval_count in python client sometimes,
        # but we do our best simple count
        self.token_counter["primary" if model == self.PRIMARY_MODEL else "fast"] += len(full_response) // 4
        
        if self.state_callback:
            self.state_callback("idle")
            
        return full_response

    def _generate_blocking(self, messages: List[Dict], model: str) -> str:
        response = self.client.chat(model=model, messages=messages, stream=False)
        content = response.get("message", {}).get("content", "")
        
        # Track usage
        tokens = response.get("eval_count", len(content)//4)
        if model == self.PRIMARY_MODEL:
            self.token_counter["primary"] += tokens
        elif model == self.FAST_MODEL:
            self.token_counter["fast"] += tokens
        elif model == self.CODER_MODEL:
            self.token_counter["coder"] += tokens
            
        return content

    def chain_of_thought(self, messages: List[Dict], model: str = None) -> str:
        model = model or self.PRIMARY_MODEL
        
        # STEP 1: REASONING PASS
        cot_messages = messages.copy()
        cot_system_msg = (
            f"{self.system_prompt}\n"
            "Before answering, work through this step by step inside <thinking> tags. "
            "Consider: what is being asked, what information is needed, what tools "
            "might be required, what could go wrong, and what the ideal answer looks like. "
            "Only after thinking write your final answer outside the <thinking> tags."
        )
        cot_messages.insert(0, {"role": "system", "content": cot_system_msg})
        
        raw_response = self._generate_blocking(cot_messages, model)
        
        # Extract thinking and final answer
        thinking_text = ""
        final_answer = raw_response
        
        if "<thinking>" in raw_response and "</thinking>" in raw_response:
            start = raw_response.find("<thinking>") + len("<thinking>")
            end = raw_response.find("</thinking>")
            thinking_text = raw_response[start:end].strip()
            final_answer = raw_response[end + len("</thinking>"):].strip()
            logging.info(f"JARVIS Internal Thought: {thinking_text}")
        elif "</thinking>" in raw_response:
            final_answer = raw_response.split("</thinking>")[-1].strip()
        
        if not final_answer:
            final_answer = raw_response # fallback
            
        # STEP 2: SELF-REFLECTION PASS
        reflection_prompt = [
            {"role": "system", "content": "Review this response: [" + final_answer + "]\nScore it 1-10 for: accuracy, completeness, JARVIS personality adherence.\nIf any score is below 7, return REVISE with specific improvements.\nIf all scores are 7+, return ACCEPT."}
        ]
        reflection = self._generate_blocking(reflection_prompt, self.FAST_MODEL)
        
        if "REVISE" in reflection:
            revision_messages = messages.copy()
            revision_messages.insert(0, {"role": "system", "content": self.system_prompt})
            revision_messages.append({"role": "assistant", "content": final_answer})
            revision_messages.append({"role": "user", "content": f"Improve the previous response based on these notes: {reflection}"})
            final_answer = self._generate_blocking(revision_messages, model)
            
        # STEP 3: VOICE FORMATTING PASS
        voice_prompt = [
            {"role": "system", "content": "Reformat this response for natural spoken audio. Rules: no markdown, no bullet points, no numbered lists, no URLs spelled out, no special characters. Convert any lists to natural prose. Keep JARVIS personality."},
            {"role": "user", "content": final_answer}
        ]
        
        if self.state_callback:
            self.state_callback("speaking")
            
        if self.stream_callback:
            return self._generate_streaming(voice_prompt, self.FAST_MODEL)
        else:
            return self._generate_blocking(voice_prompt, self.FAST_MODEL)

    def complexity_score(self, user_text: str) -> int:
        cache_key = f"complexity_{user_text}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        prompt = [
            {"role": "user", "content": (
                "Rate the complexity of this request from 1-10. Return only the integer.\n"
                "1-3: simple factual, greetings, basic tasks.\n"
                "4-6: multi-step tasks, requires reasoning.\n"
                "7-10: complex analysis, research, multi-tool orchestration, code projects.\n"
                f"Request: {user_text}"
            )}
        ]
        try:
            res = self._generate_blocking(prompt, self.FAST_MODEL)
            # Find the first integer in the response
            import re
            match = re.search(r'\d+', res)
            score = int(match.group()) if match else 5
            score = max(1, min(10, score))
        except Exception:
            score = 5
            
        self.cache.set(cache_key, score, expire=3600) # 1 hour cache
        return score

    def classify_intent(self, user_text: str) -> dict:
        # Will be implemented fully in intent.py, but leaving here if needed by architectural mistake in prompt, 
        # actually prompt says dual model intent goes to modules/intent.py
        pass

    def generate_code(self, task: str, language: str = "python", existing_code: str = None) -> str:
        sys_msg = (
            f"You are an expert {language} programmer. Write clean, production-ready code.\n"
            "Include proper error handling, docstrings, and type hints.\n"
            "Return ONLY the code. No markdown fences. No explanations before or after."
        )
        messages = [{"role": "system", "content": sys_msg}]
        if existing_code:
            messages.append({"role": "user", "content": f"Existing Code:\n{existing_code}\n\nTask: {task}"})
        else:
            messages.append({"role": "user", "content": task})
            
        return self._generate_blocking(messages, self.CODER_MODEL)

    def fix_code(self, code: str, error: str, language: str = "python") -> str:
        messages = [
            {"role": "system", "content": f"You are an expert {language} programmer. Return ONLY the corrected code. No explanations. No markdown."},
            {"role": "user", "content": f"Broken Code:\n{code}\n\nError:\n{error}\n\nFix this code."}
        ]
        return self._generate_blocking(messages, self.CODER_MODEL)

    def embed(self, text: str) -> list[float]:
        cache_key = f"embed_{text}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        res = self.client.embeddings(model=self.EMBED_MODEL, prompt=text)
        embedding = res.get("embedding", [])
        
        # Max cache 10000 entries roughly checking size limit
        self.cache.set(cache_key, embedding)
        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            return list(executor.map(self.embed, texts))

    def summarize_for_memory(self, conversation: List[Dict]) -> str:
        conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in conversation[-6:]])
        prompt = [
            {"role": "system", "content": "Summarize this conversation in 2-3 sentences capturing only the key facts, decisions made, and user preferences revealed. Be concise."},
            {"role": "user", "content": conv_text}
        ]
        return self._generate_blocking(prompt, self.FAST_MODEL)

    def get_token_usage(self) -> dict:
        return {
            f"{self.PRIMARY_MODEL}": f"{self.token_counter['primary']} tokens - $0.00 (local)",
            f"{self.FAST_MODEL}": f"{self.token_counter['fast']} tokens - $0.00 (local)",
            f"{self.CODER_MODEL}": f"{self.token_counter['coder']} tokens - $0.00 (local)"
        }

    def is_available(self) -> bool:
        import requests
        try:
            r = requests.get(config.OLLAMA_HOST, timeout=2)
            return r.status_code == 200
        except Exception:
            return False
