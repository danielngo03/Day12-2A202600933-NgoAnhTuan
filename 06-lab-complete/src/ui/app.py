from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src/ is on sys.path so we can import project modules
_src = Path(__file__).resolve().parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import chainlit as cl
from chainlit.input_widget import Select, Slider, Switch

from core.config import load_settings
from core.utils import read_json
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question

# ─── Auth ────────────────────────────────────────────────────────────────────

AUTH_USER = os.getenv("CHAINLIT_AUTH_USER", "admin")
AUTH_PASSWORD = os.getenv("CHAINLIT_AUTH_PASSWORD", "admin")


@cl.password_auth_callback
def auth_callback(username: str, password: str) -> cl.User | None:
    if username == AUTH_USER and password == AUTH_PASSWORD:
        return cl.User(identifier=username, metadata={"role": "admin"})
    return None


# ─── Model / Embedding Configs ────────────────────────────────────────────────

LLM_OPTIONS = {
    "gemini-2.0-flash-lite": {
        "label": "🧠 Gemini 2.0 Flash Lite (Google)",
        "provider": "gemini",
    },
    "o4-mini": {
        "label": "⚡ o4-mini (OpenAI)",
        "provider": "openai",
    },
    "nvidia/nemotron-3.5-content-safety:free": {
        "label": "🛡️ Nemotron Content Safety (OpenRouter – Free)",
        "provider": "openrouter",
    },
}

EMBEDDING_OPTIONS = {
    "sentence-transformers/all-MiniLM-L6-v2": "🏠 MiniLM-L6-v2 (Local)",
    "nvidia/llama-nemotron-embed-vl-1b-v2:free": "☁️  Nemotron Embed (OpenRouter – Free)",
}

DEFAULT_LLM = "gemini-2.0-flash-lite"
DEFAULT_EMBEDDING = "sentence-transformers/all-MiniLM-L6-v2"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_index(settings, embedding_model: str) -> LocalEmbeddingIndex | None:
    embeddings_path = settings.paths.embeddings_json
    if not embeddings_path.exists():
        return None
    try:
        index = LocalEmbeddingIndex.load(settings=settings, embeddings_path=embeddings_path)
        return index
    except Exception as exc:
        print(f"[ui] Failed to load index: {exc}")
        return None


def _format_sources(titles: list[str], doc_ids: list[str]) -> str:
    if not titles:
        return ""
    lines = ["\n\n---\n📚 **Sources retrieved:**"]
    for i, (title, doc_id) in enumerate(zip(titles, doc_ids), 1):
        lines.append(f"{i}. **{title}**  \n   `DOI: {doc_id}`")
    return "\n".join(lines)


def _pipeline_status(settings) -> str:
    parts = []
    if settings.paths.raw_records_json.exists():
        try:
            raw = read_json(settings.paths.raw_records_json)
            parts.append(f"✅ Raw records: **{len(raw)}** papers cached")
        except Exception:
            parts.append("⚠️ Raw records file exists but could not be read")
    else:
        parts.append("❌ No raw records – run `python script/run_phase1.py` first")

    if settings.paths.clean_csv.exists():
        parts.append(f"✅ Clean dataset: `{settings.paths.clean_csv.name}`")
    else:
        parts.append("❌ No clean dataset")

    if settings.paths.embeddings_json.exists():
        parts.append("✅ Embedding index: ready")
    else:
        parts.append("❌ No embedding index")

    if settings.paths.baseline_metrics.exists():
        try:
            m = read_json(settings.paths.baseline_metrics)
            hit = m.get("retrieval_hit_rate", 0.0)
            f1 = m.get("mean_token_f1", 0.0)
            parts.append(f"✅ Baseline eval: hit_rate={hit:.1%} | token_F1={f1:.1%}")
        except Exception:
            parts.append("✅ Baseline metrics file exists")
    else:
        parts.append("❌ No baseline evaluation metrics")

    return "\n".join(f"- {p}" for p in parts)


# ─── Chat Lifecycle ───────────────────────────────────────────────────────────

@cl.on_chat_start
async def on_chat_start():
    settings = load_settings()
    cl.user_session.set("settings", settings)

    # Determine available models based on configured API keys
    available_llm = []
    for model_id, info in LLM_OPTIONS.items():
        provider = info["provider"]
        has_key = (
            (provider == "gemini" and settings.google_api_key)
            or (provider == "openai" and settings.openai_api_key)
            or (provider == "openrouter" and settings.openrouter_api_key)
        )
        if has_key:
            available_llm.append((model_id, info["label"]))

    if not available_llm:
        available_llm = [(DEFAULT_LLM, LLM_OPTIONS[DEFAULT_LLM]["label"])]

    # Build Chat Settings widgets
    llm_choices = [cl.input_widget.Select(
        id="llm_model",
        label="🤖 LLM Model",
        values=[m[0] for m in available_llm],
        initial_value=available_llm[0][0],
    )]

    embed_choices = cl.input_widget.Select(
        id="embedding_model",
        label="🔢 Embedding Model",
        values=list(EMBEDDING_OPTIONS.keys()),
        initial_value=DEFAULT_EMBEDDING,
    )
    top_k_slider = cl.input_widget.Slider(
        id="top_k",
        label="🔍 Top-K Retrieval",
        initial=float(settings.top_k),
        min=1,
        max=10,
        step=1,
    )

    await cl.ChatSettings([llm_choices[0], embed_choices, top_k_slider]).send()

    # Store session defaults
    cl.user_session.set("llm_model", available_llm[0][0])
    cl.user_session.set("embedding_model", DEFAULT_EMBEDDING)
    cl.user_session.set("top_k", settings.top_k)

    # Load index
    index = _load_index(settings, DEFAULT_EMBEDDING)
    cl.user_session.set("index", index)

    # Welcome message
    status = _pipeline_status(settings)
    index_status = "✅ **Index loaded and ready.**" if index else "⚠️ **Index not found** – please run the pipeline first (`python script/run_phase1.py`)."

    welcome = f"""# 🔬 Lab10 – RAG Research Assistant

Welcome! I can answer questions about scholarly papers indexed from the **Crossref API** on the topic of *agentic retrieval augmented generation*.

## Pipeline Status
{status}

## Index Status
{index_status}

---
**How to use:**
- Ask me about papers, authors, topics, or publication dates.
- Use the ⚙️ settings panel to switch LLM models or embedding models.
- Example: *"What papers discuss retrieval augmented generation?"*
"""
    await cl.Message(content=welcome, author="System").send()


@cl.on_settings_update
async def on_settings_update(new_settings: dict):
    llm_model = new_settings.get("llm_model", DEFAULT_LLM)
    embedding_model = new_settings.get("embedding_model", DEFAULT_EMBEDDING)
    top_k = int(new_settings.get("top_k", 4))

    cl.user_session.set("llm_model", llm_model)
    cl.user_session.set("embedding_model", embedding_model)
    cl.user_session.set("top_k", top_k)

    settings = cl.user_session.get("settings")
    # Reload index with potentially new embedding model
    index = _load_index(settings, embedding_model)
    cl.user_session.set("index", index)

    llm_label = LLM_OPTIONS.get(llm_model, {}).get("label", llm_model)
    embed_label = EMBEDDING_OPTIONS.get(embedding_model, embedding_model)

    await cl.Message(
        content=f"⚙️ **Settings updated!**\n- LLM: {llm_label}\n- Embedding: {embed_label}\n- Top-K: {top_k}",
        author="System",
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    user_input = message.content.strip()
    if not user_input:
        return

    settings = cl.user_session.get("settings")
    index: LocalEmbeddingIndex | None = cl.user_session.get("index")
    llm_model: str = cl.user_session.get("llm_model", DEFAULT_LLM)
    top_k: int = cl.user_session.get("top_k", 4)

    # Show thinking step
    async with cl.Step(name="🔍 Retrieving from corpus") as step:
        if index is None:
            step.output = "❌ Index not loaded. Run `python script/run_phase1.py` to build it."
            await cl.Message(
                content="⚠️ The embedding index is not ready. Please run the pipeline first:\n```bash\nuv run python script/run_phase1.py\n```",
                author="Assistant",
            ).send()
            return

        # RAG retrieval
        try:
            result = answer_question(user_input, settings=settings, index=index, top_k=top_k)
            step.output = f"Retrieved **{len(result.retrieved_doc_ids)}** document(s):\n" + "\n".join(
                f"- {t}" for t in result.retrieved_titles
            )
        except Exception as exc:
            step.output = f"Retrieval error: {exc}"
            await cl.Message(
                content=f"❌ Retrieval failed: {exc}",
                author="Assistant",
            ).send()
            return

    # Build the LLM-enriched answer using configured model
    async with cl.Step(name=f"🤖 Generating answer with {LLM_OPTIONS.get(llm_model, {}).get('label', llm_model)}") as step2:
        try:
            from retrieval.llm import build_llm
            import os

            # Temporarily override model settings
            provider_info = LLM_OPTIONS.get(llm_model, {})
            provider = provider_info.get("provider", "gemini")

            # Build a temporary settings override for the chosen model
            import dataclasses
            override = dataclasses.replace(settings, llm_provider=provider, model_name=llm_model)

            llm = build_llm(override, temperature=0.0)
            context = "\n\n".join(result.retrieved_contexts[:top_k])
            prompt = f"""You are a scholarly research assistant. Answer the user's question based ONLY on the following retrieved paper context. If the context doesn't contain the answer, say so clearly.

Context:
{context}

Question: {user_input}

Answer:"""
            response = llm.invoke(prompt)
            llm_answer = response.content if hasattr(response, "content") else str(response)
            step2.output = "Answer generated."
        except Exception as exc:
            # Fall back to extracted answer from retrieval
            llm_answer = result.answer
            step2.output = f"LLM error ({exc}), using extracted answer."

    # Compose final message
    sources_text = _format_sources(result.retrieved_titles, result.retrieved_doc_ids)
    final_content = f"{llm_answer}{sources_text}"

    elements = []
    if result.retrieved_contexts:
        context_text = "\n\n---\n".join(
            f"**{title}**\n{ctx[:500]}{'…' if len(ctx) > 500 else ''}"
            for title, ctx in zip(result.retrieved_titles, result.retrieved_contexts)
        )
        elements.append(
            cl.Text(
                name="📄 Context Details",
                content=context_text,
                display="side",
            )
        )

    await cl.Message(
        content=final_content,
        elements=elements,
        author="Assistant",
    ).send()
