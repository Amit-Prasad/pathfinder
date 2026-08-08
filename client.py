import json
import logging
import re
import requests
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel
from google import genai
from google.genai import types

from pathfinder.config import GEMINI_API_KEY, OPENROUTER_API_KEY, USE_VERTEXAI, GCP_PROJECT, GCP_LOCATION, MODEL_NAME, DEEPSEEK_API_KEY, MOONSHOT_API_KEY, OPENAI_API_KEY

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY, openrouter_api_key: str = OPENROUTER_API_KEY):
        self.client = None
        self.vertex_client = None
        self.studio_client = None
        self.openrouter_api_key = openrouter_api_key
        self.deepseek_api_key = DEEPSEEK_API_KEY
        self.moonshot_api_key = MOONSHOT_API_KEY
        self.openai_api_key = OPENAI_API_KEY
        self.last_model_used = "unknown"
        
        try:
            # Always try to initialize Vertex AI client if GCP project is set or if USE_VERTEXAI is enabled
            client_args = {
                "vertexai": True,
                "http_options": types.HttpOptions(timeout=180000)
            }
            if GCP_PROJECT:
                client_args["project"] = GCP_PROJECT
            if GCP_LOCATION:
                client_args["location"] = GCP_LOCATION
            logger.info(f"Initializing google-genai client with Vertex AI (project={GCP_PROJECT}, location={GCP_LOCATION})")
            self.vertex_client = genai.Client(**client_args)
        except Exception as e:
            logger.warning(f"Could not initialize Vertex AI Client: {e}")

        try:
            if api_key:
                logger.info("Initializing google-genai client with AI Studio developer API key.")
                self.studio_client = genai.Client(
                    api_key=api_key,
                    http_options=types.HttpOptions(timeout=180000)
                )
        except Exception as e:
            logger.warning(f"Could not initialize AI Studio Client: {e}")

        # Set default client
        if USE_VERTEXAI:
            self.client = self.vertex_client
        else:
            self.client = self.studio_client or self.vertex_client

    def _select_random_fallback(self, exclude: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
        import random
        candidates = []
        if (self.studio_client or self.vertex_client) and exclude != "gemini":
            gemini_models = ["gemini-2.5-flash", "gemini-2.5-pro"]
            candidates.append(("gemini", random.choice(gemini_models)))
        if self.deepseek_api_key and exclude != "deepseek":
            deepseek_models = ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-reasoner"]
            candidates.append(("deepseek", random.choice(deepseek_models)))
        if self.moonshot_api_key and exclude != "moonshot":
            kimi_models = ["moonshot-v1-32k", "moonshot-v1-128k"]
            candidates.append(("moonshot", random.choice(kimi_models)))
        if self.openai_api_key and exclude != "openai":
            openai_models = ["gpt-4o", "gpt-4o-mini"]
            candidates.append(("openai", random.choice(openai_models)))
        
        if not candidates:
            return None, None
        return random.choice(candidates)

    def query(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        search: bool = False,
        response_schema: Optional[Type[BaseModel]] = None,
        temperature: float = 0.2,
        provider: str = "gemini",
        model: Optional[str] = None,
        use_vertex: Optional[bool] = None,
    ) -> str:
        """
        Sends a query to either Gemini, OpenRouter, DeepSeek or Moonshot and returns the text response.
        Updates self.last_model_used with the exact model that served the response.
        """
        self.last_model_used = "unknown"
        if provider != "gemini":
            use_vertex = False

        # Randomize temperature dynamically from (0, 1] for all models except Kimi and reasoning models
        active_model = model or MODEL_NAME or ""
        is_fixed_temp = (
            "kimi" in active_model.lower() or 
            provider.lower() == "kimi" or 
            "deepseek-reasoner" in active_model.lower() or
            "reasoner" in active_model.lower() or
            "o1-" in active_model.lower() or
            "o3-" in active_model.lower() or
            active_model.lower() == "o1"
        )
        if not is_fixed_temp:
            import random
            # random.uniform(a, b) generates a random float N such that a <= N <= b
            # We want (0, 1], so we use a tiny positive float as the lower bound
            temperature = round(random.uniform(0.0001, 1.0), 4)
            logger.info(f"Randomized temperature to {temperature} for model '{active_model}'")

        if (provider in ("deepseek", "moonshot", "kimi", "openai")) and not use_vertex:
            if provider == "deepseek":
                api_key = self.deepseek_api_key
                url = "https://api.deepseek.com/chat/completions"
                target_model = model or "deepseek-chat"
                if not api_key:
                    raise ValueError("DEEPSEEK_API_KEY is not configured in config.py or environment.")
            elif provider == "openai":
                api_key = self.openai_api_key
                url = "https://api.openai.com/v1/chat/completions"
                target_model = model or "gpt-4o"
                if not api_key:
                    raise ValueError("OPENAI_API_KEY is not configured in config.py or environment.")
            else:
                api_key = self.moonshot_api_key
                url = "https://api.moonshot.ai/v1/chat/completions"
                target_model = model or "moonshot-v1-8k"
                if not api_key:
                    raise ValueError("MOONSHOT_API_KEY (or KIMI_API_KEY) is not configured in config.py or environment.")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            
            user_content = prompt
            if response_schema:
                schema_str = json.dumps(response_schema.model_json_schema(), indent=2)
                user_content += f"\n\nIMPORTANT: You must respond with a JSON object that strictly adheres to the following JSON schema:\n{schema_str}"
            
            messages.append({"role": "user", "content": user_content})
            
            # Determine max_tokens based on model capability
            if provider in ("deepseek", "moonshot", "kimi", "openai") or target_model.startswith("kimi-") or "deepseek" in target_model or "gpt-" in target_model:
                max_tokens = 8192
            else:
                max_tokens = 4096

            payload = {
                "model": target_model,
                "messages": messages,
                "max_tokens": max_tokens,
            }
            
            # Disable thinking mode on DeepSeek non-reasoner models to prevent timeout/exhaustion issues
            if provider == "deepseek" and target_model != "deepseek-reasoner":
                payload["thinking"] = {"type": "disabled"}
            
            is_openai_reasoning = (
                provider == "openai" and 
                ("o1-" in target_model.lower() or "o3-" in target_model.lower() or target_model.lower() == "o1")
            )
            if is_openai_reasoning:
                # OpenAI reasoning models do not support temperature parameters
                pass
            elif target_model in ("kimi-k2.7-code", "kimi-k2.6", "kimi-k2.5") or target_model.startswith("kimi-"):
                payload["temperature"] = 1.0
            else:
                payload["temperature"] = temperature
            
            if response_schema:
                # Legacy moonshot-v1 models do not support response_format (JSON mode) via the API payload
                if not (provider == "moonshot" and target_model.startswith("moonshot-v1-")):
                    payload["response_format"] = {"type": "json_object"}
                
            try:
                logger.info(f"Querying {provider} model '{target_model}'...")
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=900
                )
                response.raise_for_status()
                resp_json = response.json()
                
                self.last_model_used = target_model
                logger.info(f"Received {provider} response from model: {self.last_model_used}")
                
                choices = resp_json.get("choices", [])
                if not choices:
                    raise ValueError(f"{provider} returned empty choices: {resp_json}")
                return choices[0].get("message", {}).get("content", "")
            except Exception as e:
                logger.error(f"Error querying {provider}: {e}")
                raise e

        elif provider == "openrouter" and not use_vertex:
            if not self.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY is not configured in config.py or environment.")
            
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/momentus/pathfinder",
                "X-Title": "Pathfinder",
            }
            
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            
            # For JSON schema mode, we add instructions to prompt to be safe
            user_content = prompt
            if response_schema:
                schema_str = json.dumps(response_schema.model_json_schema(), indent=2)
                user_content += f"\n\nIMPORTANT: You must respond with a JSON object that strictly adheres to the following JSON schema:\n{schema_str}"
            
            messages.append({"role": "user", "content": user_content})
            
            target_model = model or "openrouter/free"
            payload = {
                "model": target_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4096,
            }
            
            if response_schema:
                payload["response_format"] = {"type": "json_object"}
            
            try:
                logger.info(f"Querying OpenRouter model '{target_model}' (timeout=15s)...")
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=15  # detect "not fast enough"
                )
                response.raise_for_status()
                resp_json = response.json()
                
                self.last_model_used = resp_json.get("model", target_model)
                logger.info(f"Received OpenRouter response from model: {self.last_model_used}")
                
                choices = resp_json.get("choices", [])
                if not choices:
                    raise ValueError(f"OpenRouter returned empty choices: {resp_json}")
                return choices[0].get("message", {}).get("content", "")
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.warning(f"OpenRouter call did not respond fast enough ({e}). Falling back to alternative model...")
                fallback_provider, fallback_model = self._select_random_fallback(exclude="openrouter")
                if fallback_provider:
                    logger.info(f"Fallback selected: provider={fallback_provider}, model={fallback_model}")
                    return self.query(
                        prompt=prompt,
                        system_instruction=system_instruction,
                        search=search,
                        response_schema=response_schema,
                        temperature=temperature,
                        provider=fallback_provider,
                        model=fallback_model,
                        use_vertex=use_vertex,
                    )
                else:
                    logger.error("No alternative fallback models configured with API keys.")
                    raise e
            except Exception as e:
                logger.error(f"Error querying OpenRouter: {e}")
                raise e
        else:
            # Default to Gemini
            active_client = self.client
            if use_vertex is True:
                active_client = self.vertex_client
            elif use_vertex is False:
                active_client = self.studio_client

            if not active_client:
                raise ValueError(f"Gemini Client (use_vertex={use_vertex}) is not initialized.")
                
            tools = []
            if search:
                tools.append(types.Tool(google_search=types.GoogleSearch()))

            config_args = {
                "temperature": temperature,
            }
            if system_instruction:
                config_args["system_instruction"] = system_instruction
            if tools:
                config_args["tools"] = tools
            if response_schema:
                config_args["response_mime_type"] = "application/json"
                config_args["response_schema"] = response_schema

            config = types.GenerateContentConfig(**config_args)
            target_model = model or MODEL_NAME

            try:
                logger.info(f"Querying Gemini/Vertex model '{target_model}' (use_vertex={use_vertex or (active_client == self.vertex_client)})...")
                response = active_client.models.generate_content(
                    model=target_model,
                    contents=prompt,
                    config=config,
                )
                self.last_model_used = target_model
                return response.text or ""
            except Exception as e:
                logger.error(f"Error querying Gemini/Vertex: {e}")
                raise e

    def query_json(
        self,
        prompt: str,
        schema: Type[BaseModel],
        system_instruction: Optional[str] = None,
        search: bool = False,
        temperature: float = 0.1,
        provider: str = "gemini",
        model: Optional[str] = None,
        use_vertex: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Queries the model and parses the response according to the provided Pydantic model.
        """
        response_text = self.query(
            prompt=prompt,
            system_instruction=system_instruction,
            search=search,
            response_schema=schema,
            temperature=temperature,
            provider=provider,
            model=model,
            use_vertex=use_vertex,
        )
        
        # Clean text from potential markdown code blocks
        cleaned_text = response_text.strip()
        match = re.search(r"```json\n(.*?)```", cleaned_text, re.DOTALL)
        if match:
            cleaned_text = match.group(1).strip()
        else:
            match = re.search(r"```\n(.*?)```", cleaned_text, re.DOTALL)
            if match:
                cleaned_text = match.group(1).strip()
            else:
                cleaned_text = cleaned_text.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode response as JSON: {response_text}. Error: {e}")
            raise ValueError(f"Invalid JSON returned from LLM: {response_text}") from e

