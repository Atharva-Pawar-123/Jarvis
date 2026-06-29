import logging
from typing import Generator, List, Dict, Union, Any

import requests

import config
from modules.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class LLMEngine:
    """
    Interface to the LLM backend (Gemini API or local Ollama).

    Handles connection verification, response generation, and graceful
    fallback to local Ollama if the primary Gemini API is unreachable.
    """

    def __init__(self) -> None:
        """Initialize the LLM engine based on config."""
        self.backend = config.LLM_BACKEND.lower()
        self.gemini_key = config.GEMINI_API_KEY
        self.is_degraded = False  # Track if we fell back to Ollama
        self._genai_client = None

        logger.info(f"Initializing LLM engine — Backend: {self.backend.upper()}")

        if self.backend == "gemini":
            if not self.gemini_key:
                logger.warning("GEMINI_API_KEY is empty. Falling back to Ollama.")
                self.backend = "ollama"
            else:
                try:
                    from google import genai
                    self._genai_client = genai.Client(api_key=self.gemini_key)
                    logger.info(f"Gemini API configured (Model: {config.GEMINI_MODEL})")
                except ImportError:
                    logger.error("google-genai not installed. Falling back to Ollama.")
                    self.backend = "ollama"
                except Exception as exc:
                    logger.warning(f"Gemini API test failed: {exc}. Falling back to Ollama.")
                    self.backend = "ollama"
                    self.is_degraded = True

        if self.backend == "ollama":
            if not self.is_ollama_available():
                raise RuntimeError(
                    f"Ollama is not running at {config.OLLAMA_HOST}. "
                    "Please start Ollama or configure a valid Gemini API key."
                )
            logger.info(f"Ollama engine ready (Model: {config.OLLAMA_MODEL})")

    def is_ollama_available(self) -> bool:
        """Check if local Ollama is reachable."""
        try:
            response = requests.get(config.OLLAMA_HOST, timeout=5)
            return response.status_code == 200
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return False

    def generate(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
    ) -> Union[str, Generator[str, None, None]]:
        """
        Generate a response from the configured LLM.
        """
        try:
            if self.backend == "gemini":
                try:
                    return self._generate_gemini(messages, stream)
                except Exception as e:
                    logger.warning(f"Gemini generation failed: {e}. Switching to Ollama for this turn.")
                    self.is_degraded = True
                    if self.is_ollama_available():
                        if stream:
                            return self._generate_ollama_stream(messages)
                        else:
                            return self._generate_ollama_blocking(messages)
                    else:
                        logger.warning("Ollama is also unavailable — both LLM backends are down.")
                        raise RuntimeError("Both LLM backends are unavailable.")
            else:
                if stream:
                    return self._generate_ollama_stream(messages)
                else:
                    return self._generate_ollama_blocking(messages)
        except Exception as exc:
            logger.error(f"Critical LLM failure (Both Primary and Fallback failed): {exc}")
            error_msg = "I'm having trouble reaching my reasoning engine, sir. I'll continue to monitor your commands, but my responses may be limited."
            if stream:
                def err_gen():
                    yield error_msg
                return err_gen()
            return error_msg

    def _generate_gemini(self, messages: List[Dict[str, str]], stream: bool) -> Union[str, Generator[str, None, None]]:
        from google.genai import types

        # Extract system prompt and build contents
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=content)]))
            elif role == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=content)]))

        gen_config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=config.GEMINI_TEMPERATURE,
        )

        if stream:
            def gemini_streamer():
                _in_tokens = 0
                _out_tokens = 0
                response = self._genai_client.models.generate_content_stream(
                    model=config.GEMINI_MODEL,
                    contents=contents,
                    config=gen_config,
                )
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                    # Capture usage from the final chunk
                    try:
                        um = chunk.usage_metadata
                        if um and um.prompt_token_count:
                            _in_tokens = um.prompt_token_count
                            _out_tokens = um.candidates_token_count or 0
                    except Exception:
                        pass
                # Record after stream ends
                try:
                    if _in_tokens:
                        CostTracker.get().record(
                            model=config.GEMINI_MODEL,
                            input_tokens=_in_tokens,
                            output_tokens=_out_tokens,
                            backend="gemini",
                        )
                except Exception:
                    pass
            return gemini_streamer()
        else:
            response = self._genai_client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=contents,
                config=gen_config,
            )
            # Track token cost
            try:
                um = response.usage_metadata
                CostTracker.get().record(
                    model=config.GEMINI_MODEL,
                    input_tokens=um.prompt_token_count or 0,
                    output_tokens=um.candidates_token_count or 0,
                    backend="gemini",
                )
            except Exception:
                pass
            return response.text.strip()

    def _generate_ollama_blocking(self, messages: List[Dict[str, str]]) -> str:
        import ollama as ollama_client
        client = ollama_client.Client(host=config.OLLAMA_HOST)
        response = client.chat(
            model=config.OLLAMA_MODEL,
            messages=messages,
            options={
                "temperature": config.OLLAMA_TEMPERATURE,
                "num_thread": config.OLLAMA_NUM_THREADS,
                "num_gpu": getattr(config, "OLLAMA_NUM_GPU", 0),
            },
        )
        # Record Ollama usage ($0 cost — local inference)
        # Use attribute access since response is an ollama.ChatResponse object
        try:
            in_tokens = getattr(response, "prompt_eval_count", 0) or 0
            out_tokens = getattr(response, "eval_count", 0) or 0
            CostTracker.get().record(
                model=config.OLLAMA_MODEL,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                backend="ollama",
            )
        except Exception:
            pass
        return response.message.content.strip()

    def _generate_ollama_stream(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        import ollama as ollama_client
        client = ollama_client.Client(host=config.OLLAMA_HOST)
        stream = client.chat(
            model=config.OLLAMA_MODEL,
            messages=messages,
            options={
                "temperature": config.OLLAMA_TEMPERATURE,
                "num_thread": config.OLLAMA_NUM_THREADS,
                "num_gpu": getattr(config, "OLLAMA_NUM_GPU", 0),
            },
            stream=True,
        )
        for chunk in stream:
            # chunk is an ollama.ChatResponse object, use attribute access
            content = getattr(chunk.message, "content", "") if chunk.message else ""
            if content:
                yield content

    def generate_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
    ) -> Dict[str, Any]:
        """
        Generate a response with tool schemas.
        Returns a dictionary:
        {
            "content": "Text response if any",
            "tool_calls": [
                {
                    "name": "tool_name",
                    "arguments": {"arg1": "val"}
                }
            ]
        }
        """
        if self.backend == "gemini" and not self.is_degraded:
            try:
                return self._generate_gemini_tools(messages, tools)
            except Exception as e:
                err_msg = str(e).replace('\n', ' ')
                logger.warning(f"Gemini tools generation failed: {err_msg[:150]}. Falling back to Ollama.")
                self.is_degraded = True
                
        if self.is_ollama_available():
            return self._generate_ollama_tools(messages, tools)
            
        raise RuntimeError("Both LLM backends are unavailable for tool calling.")

    def _generate_gemini_tools(self, messages: List[Dict[str, str]], tools: List[Dict]) -> Dict[str, Any]:
        from google.genai import types

        # Convert simple JSON schema tools to Gemini Tool declarations
        gemini_tools = []
        declarations = []
        
        for t in tools:
            # We assume t is in standard OpenAI/JSON Schema format
            name = t.get("name", "")
            desc = t.get("description", "")
            params = t.get("parameters", {})
            
            # Very basic conversion for standard JSON schemas to Gemini types
            properties = {}
            for k, v in params.get("properties", {}).items():
                prop_type_str = v.get("type", "string").upper()
                prop_type = getattr(types.Type, prop_type_str, types.Type.STRING)
                properties[k] = types.Schema(
                    type=prop_type,
                    description=v.get("description", ""),
                )
            
            declaration = types.FunctionDeclaration(
                name=name,
                description=desc,
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties=properties,
                    required=params.get("required", [])
                )
            )
            declarations.append(declaration)

        if declarations:
            gemini_tools.append(types.Tool(function_declarations=declarations))

        # Build contents
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=content)]))
            elif role == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=content)]))
            elif role == "tool":
                # Handle tool response messages
                tool_name = msg.get("name", "unknown")
                # Ensure we pass dict for tool_response
                import json
                try:
                    tool_data = json.loads(content)
                except:
                    tool_data = {"result": content}
                
                contents.append(
                    types.Content(
                        role="function", 
                        parts=[
                            types.Part.from_function_response(
                                name=tool_name,
                                response=tool_data
                            )
                        ]
                    )
                )

        gen_config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.1, # Low temp for tool calling
            tools=gemini_tools if gemini_tools else None
        )

        response = self._genai_client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=contents,
            config=gen_config,
        )

        result = {
            "content": response.text.strip() if response.text else "",
            "tool_calls": []
        }
        
        # Extract tool calls if any
        if response.function_calls:
            for fc in response.function_calls:
                # Need to convert proto MapComposite to standard dict
                args = {}
                if hasattr(fc, 'args') and fc.args is not None:
                    try:
                        # Depending on the exact proto version, we convert
                        args = dict(fc.args)
                    except:
                        pass
                
                result["tool_calls"].append({
                    "name": fc.name,
                    "arguments": args
                })

        return result

    def _generate_ollama_tools(self, messages: List[Dict[str, str]], tools: List[Dict]) -> Dict[str, Any]:
        import ollama as ollama_client
        client = ollama_client.Client(host=config.OLLAMA_HOST)
        
        # Convert standard schema to Ollama format
        ollama_tools = []
        for t in tools:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": t.get("name"),
                    "description": t.get("description"),
                    "parameters": t.get("parameters", {})
                }
            })
            
        # Re-map "tool" role to "tool" in ollama
        ollama_msgs = []
        for msg in messages:
            if msg["role"] == "tool":
                ollama_msgs.append({
                    "role": "tool",
                    "content": msg["content"]
                })
            else:
                ollama_msgs.append(msg)

        response = client.chat(
            model=config.OLLAMA_MODEL,
            messages=ollama_msgs,
            tools=ollama_tools if ollama_tools else None,
            options={
                "temperature": 0.1,
            },
        )
        
        result = {
            "content": getattr(response.message, "content", "") or "",
            "tool_calls": []
        }
        
        if hasattr(response.message, "tool_calls") and response.message.tool_calls:
            for tc in response.message.tool_calls:
                result["tool_calls"].append({
                    "name": getattr(tc.function, "name", ""),
                    "arguments": getattr(tc.function, "arguments", {})
                })
                
        return result

