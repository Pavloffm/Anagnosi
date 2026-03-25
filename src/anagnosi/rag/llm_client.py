from typing import Optional
import torch
from loguru import logger
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

from anagnosi.rag.prompt_generator import PromptGenerator


class LocalTransformersLLM:
    def __init__(self,model_name: str = "HuggingFaceTB/SmolLM2-135M-Instruct",device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        logger.info(f"Loading model: {model_name} on {device}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name,dtype=torch.float16 if device == "cuda" else torch.float32,device_map="auto" if device == "cuda" else None)

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

if __name__ == '__main__':
    local_transformers_llm = LocalTransformersLLM()
    promt_generator = PromptGenerator()
    promt = promt_generator.generate("What is docker?")
    logger.info(local_transformers_llm.generate(promt))