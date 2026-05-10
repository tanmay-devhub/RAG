import os
from langchain_ollama import OllamaLLM

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")

_llm_instance: OllamaLLM | None = None


def get_llm() -> OllamaLLM:
    """Return a reusable OllamaLLM instance."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = OllamaLLM(base_url=_OLLAMA_BASE_URL, model=_LLM_MODEL)
    return _llm_instance


def generate_answer(question: str, context_chunks: list[str]) -> str:
    """Build a RAG prompt from context chunks and return the LLM's answer string."""
    numbered_context = "\n".join(
        f"[{i + 1}] {chunk}" for i, chunk in enumerate(context_chunks)
    )
    prompt = (
        "You are a helpful assistant. Answer the question using ONLY the context provided below.\n"
        'If the context does not contain enough information, say "I don\'t have enough context to answer this."\n'
        "Do not make up information.\n\n"
        f"Context:\n{numbered_context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )
    llm = get_llm()
    return llm.invoke(prompt)
