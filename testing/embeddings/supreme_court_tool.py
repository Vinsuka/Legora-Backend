from typing import List, Dict, Any
from langchain.tools import BaseTool
import pinecone
from testing.embeddings.rag_system import SimpleRAG
import os

class SupremeCourtSearchTool(BaseTool):
    name = "supreme_court_search"
    description = """
    Search through Supreme Court judgements using semantic search.
    Input should be a specific legal query or topic you want to research.
    The tool will return relevant excerpts from Supreme Court judgements.
    """

    def __init__(self, pinecone_api_key: str, environment: str, model_dir: str = "."):
        super().__init__()
        # Initialize Pinecone
        pinecone.init(api_key=pinecone_api_key, environment=environment)
        self.index = pinecone.Index("supreme-court-judgements")
        
        # Initialize RAG system with local model
        self.rag = SimpleRAG(model_dir=model_dir)

    def _run(self, query: str) -> str:
        try:
            # Get embedding for the query using our local model
            query_embedding = self.rag.get_embedding(query)
            
            # Search Pinecone
            search_results = self.index.query(
                namespace="supreme-court-judgements",
                vector=query_embedding.tolist(),
                top_k=5,
                include_metadata=True
            )

            # Format results
            formatted_results = []
            for match in search_results.matches:
                formatted_results.append(
                    f"\nRelevance Score: {match.score:.2f}\n"
                    f"Case: {match.metadata.get('case_name', 'N/A')}\n"
                    f"Year: {match.metadata.get('year', 'N/A')}\n"
                    f"Excerpt: {match.metadata.get('text', 'No excerpt available')}\n"
                    f"Citation: {match.metadata.get('citation', 'N/A')}\n"
                    f"-" * 80
                )

            if not formatted_results:
                return "No relevant Supreme Court judgements found for the given query."

            return "\n".join([
                "Supreme Court Judgements Search Results:",
                *formatted_results,
                "\nAnalysis: These results represent the most semantically relevant Supreme Court judgements for your query."
            ])

        except Exception as e:
            return f"Error searching Supreme Court judgements: {str(e)}"

    def _arun(self, query: str) -> str:
        # Async not implemented
        raise NotImplementedError("Async version not implemented") 