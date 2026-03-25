from loguru import logger

from anagnosi.rag.rag import get_rag_from_md_notes


class PromptGenerator:
    def generate(self, query: str):
        retrieved = get_rag_from_md_notes(query)
        context_text = "\n\n".join([
            f"### Source: {chunk['source']} (chunk #{chunk['chunk_index']})\n{chunk['content']}"
            for chunk in retrieved
        ])

        system_prompt = (
            "You are a helpful assistant that answers questions based on the provided context. "
            "If the context doesn't contain relevant information, say so honestly. "
            "Cite your sources when possible."
        )

        prompt = f"""<|system|>\n{system_prompt}\n
        <|context|>\n{context_text}\n
        <|user|>\n{query}\n
        <|assistant|>"""

        return prompt

if __name__ == '__main__':
    promt_generator = PromptGenerator()
    logger.info(promt_generator.generate("Am I know something about Docker?"))