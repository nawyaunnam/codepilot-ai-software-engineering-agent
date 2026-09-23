"""Persistent model-tagged vectors; local ONNX or remote OpenAI embeddings."""

from functools import lru_cache

from .config import settings


def model_id():
    return f"{settings.embedding_provider}:{settings.embedding_model}"


@lru_cache(maxsize=2)
def local_model(name):
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=name, cache_dir=settings.embedding_cache_dir)


def embed(texts):
    if settings.embedding_provider == "disabled":
        return []
    if settings.embedding_provider == "openai":
        if not settings.llm_api_key:
            raise ValueError("OpenAI embeddings require LLM_API_KEY")
        from langchain_openai import OpenAIEmbeddings

        provider = OpenAIEmbeddings(
            model=settings.embedding_model, api_key=settings.llm_api_key, request_timeout=60, max_retries=1
        )
        return provider.embed_documents([text[:12000] for text in texts])
    if settings.embedding_provider != "local":
        raise ValueError("EMBEDDING_PROVIDER must be local, openai, or disabled")
    return [v.tolist() for v in local_model(settings.embedding_model).embed(texts)]
