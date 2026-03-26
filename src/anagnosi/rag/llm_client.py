import json

import requests
import torch
from loguru import logger
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

from anagnosi.rag.metadata_store import init_metadata_db
from anagnosi.rag.prompt_generator import PromptGenerator
from anagnosi.rag.rag import get_collection, get_embedder, sync_documents_to_collection
from anagnosi.settings import settings


class LocalTransformersLLM:
    def __init__(self, model_name: str = "HuggingFaceTB/SmolLM2-135M-Instruct", device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        logger.debug(f"Loading model: {model_name} on {device}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name, dtype=torch.float16 if device == "cuda" else torch.float32, device_map="auto" if device == "cuda" else None)

        self.pipe = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            device=0 if device == "cuda" else -1,
            temperature=0.1,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )
        logger.info("Model loaded successfully")

    def generate(self, prompt: str) -> str:
        try:
            result = self.pipe(prompt)
            full_text = result[0]["generated_text"]
            if "<|assistant|>" in full_text:
                return full_text.split("<|assistant|>")[-1].strip()
            return full_text[len(prompt):].strip()
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return f"Error: {e}"


class OllamaLLMClient:
    def __init__(self, base_url: str, model: str, timeout: int, temperature: float, num_ctx: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.options = {"temperature": temperature, "num_ctx": num_ctx,}

        logger.debug(f"Ollama client initialized: {base_url} | model: {model}")

        if not self._health_check():
            logger.warning(f"Could not connect to Ollama at {base_url}")

    def _health_check(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/", timeout=10)
            return response.status_code == 200
        except requests.RequestException as e:
            logger.error(f"Health check failed: {e}")
            return False

    def generate(self, prompt: str, stream: bool = False) -> str:
        url = f"{self.base_url}/api/generate"

        payload = {"model": self.model, "prompt": prompt, "stream": stream, "options": self.options}

        try:
            logger.debug(f"Sending request to Ollama: {len(prompt)} chars")

            response = requests.post(url, json=payload, timeout=self.timeout, stream=stream)
            response.raise_for_status()

            if stream:
                full_response = []
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            full_response.append(chunk["response"])
                        if chunk.get("done"):
                            break
                return "".join(full_response).strip()
            else:
                result = response.json()
                return result.get("response", "").strip()

        except requests.Timeout:
            logger.error(f"Request timed out after {self.timeout}s")
            return "Error: Request timeout. The model may be loading or the prompt is too long."
        except requests.ConnectionError:
            logger.error(f"Could not connect to Ollama at {self.base_url}")
            return f"Error: Cannot connect to Ollama server at {self.base_url}. Is it running?"
        except requests.HTTPError as e:
            logger.error(f"HTTP error: {e} - Response: {response.text}")
            return f"Error: HTTP {response.status_code} - {response.text}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"Error: {type(e).__name__} - {str(e)}"

    def generate_stream(self, prompt: str):
        url = f"{self.base_url}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": True, "options": self.options}

        try:
            logger.debug(f"Streaming request to Ollama: {len(prompt)} chars")
            response = requests.post(url, json=payload, timeout=self.timeout, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if "response" in chunk:
                        yield chunk["response"]
                    if chunk.get("done"):
                        break

        except requests.Timeout:
            logger.error(f"Stream request timed out after {self.timeout}s")
            yield "\n[Error: Request timeout]\n"
        except requests.ConnectionError:
            logger.error(f"Could not connect to Ollama at {self.base_url}")
            yield f"\n[Error: Cannot connect to {self.base_url}]\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"\n[Error: {type(e).__name__}]\n"


if __name__ == '__main__':
    init_metadata_db()
    sync_documents_to_collection(get_collection(), get_embedder(), force_reindex=True)

    ollamallmclient = OllamaLLMClient(base_url=settings.ollama_base_url, model=settings.ollama_default_model, timeout=settings.ollama_default_timeout, temperature=settings.ollama_default_temperature, num_ctx=settings.ollama_default_num_ctx)
    promt_generator = PromptGenerator()
    prompt = promt_generator.generate("What is docker?")
    logger.info(prompt)
    logger.info(ollamallmclient.generate(prompt))
