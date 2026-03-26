from loguru import logger


class PromptGenerator:
    def generate(self, query: str, retrieved_chunks: list[dict]):
        context_text = "\n\n".join([
            f"### Source File: {chunk['source']}.md (Chunk #{chunk['chunk_index']})\n{chunk['content']}"
            for chunk in retrieved_chunks
        ])

        system_prompt = (
            "You are a helpful assistant that answers questions based on the provided context. "
            "If the context doesn't contain relevant information, say so honestly. "
            "ALWAYS cite your sources using the exact filename from the context, like: "
            "(Source: filename.md, Chunk #X). "
            "If multiple chunks from the same file are used, list the chunk numbers. "
            "If information comes from multiple files, cite each one separately."
        )

        prompt = f"""<|system|>\n{system_prompt}\n
        <|context|>\n{context_text}\n
        <|user|>\n{query}\n
        <|assistant|>"""

        return prompt

if __name__ == '__main__':
    prompt_generator = PromptGenerator()
    logger.info(prompt_generator.generate("Am I know something about Docker?"))
