"""Standalone CrewAI RAG helpers backed by the shared Chroma index."""

import os

from core.rag_store import RAG_CHROMA_DIR, RAG_COLLECTION_NAME, RAG_SOURCE_DIR, index_rag_files


def build_rag_tool(api_key):
    """Create a CrewAI RAG tool that indexes and searches the shared source directory."""
    rag_config = {
        "vectordb": {
            "provider": "chromadb",
            "config": {
                "collection_name": RAG_COLLECTION_NAME,
                "dir": RAG_CHROMA_DIR,
            },
        },
        "embedding_model": {
            "provider": "google-generativeai",
            "config": {
                "model": "models/embedding-001",
                "api_key": api_key,
            },
        },
    }

    try:
        from crewai_tools import RagTool

        rag_tool = RagTool(config=rag_config)
        add_method = getattr(rag_tool, "add", None)
        if callable(add_method):
            try:
                add_method(data_type="directory", path=RAG_SOURCE_DIR)
            except TypeError:
                add_method(path=RAG_SOURCE_DIR)
        return rag_tool
    except Exception:
        from crewai_tools import DirectorySearchTool

        return DirectorySearchTool(
            directory=RAG_SOURCE_DIR,
            collection_name=RAG_COLLECTION_NAME,
            config=rag_config,
        )


def build_rag_agent(api_key, model_name="gemini-2.5-flash"):
    """Return a simple CrewAI agent configured to answer from the shared documents."""
    from crewai import Agent, Crew, LLM, Process, Task

    rag_tool = build_rag_tool(api_key)
    agent = Agent(
        role="RAG Assistant",
        goal="Answer questions using the indexed clinical document knowledge base.",
        backstory="You answer only from retrieved document context and cite the source passages.",
        tools=[rag_tool] if rag_tool else [],
        llm=LLM(model=model_name, temperature=0.2),
        verbose=True,
    )
    task = Task(
        description="Answer this question using the knowledge base: {question}",
        expected_output="A grounded answer from the indexed documents.",
        agent=agent,
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential)


def refresh_rag_index(force=False):
    """Index the shared source directory into Chroma before a CrewAI run."""
    return index_rag_files(force=force)


if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY before running the demo.")

    refresh_rag_index(force=False)
    crew = build_rag_agent(api_key)
    result = crew.kickoff(inputs={"question": "Summarize the main policy."})
    print(result)
