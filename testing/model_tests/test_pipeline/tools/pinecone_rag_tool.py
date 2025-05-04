from typing import Type, List, Dict, Any, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from pinecone import Pinecone, ServerlessSpec
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

class DocumentSearchInput(BaseModel):
    """Input schema for DocumentSearchTool."""
    query: str = Field(..., description="The query to search in the knowledge base.")
    top_k: int = Field(default=3, description="Number of most relevant documents to retrieve.")

class DocumentSearchTool(BaseTool):
    name: str = "document_search"
    description: str = """
    A tool for searching through documents using semantic search.
    Returns relevant text passages based on the query.
    Use this tool to find relevant information from the knowledge base.
    """
    args_schema: Type[BaseModel] = DocumentSearchInput

    _pc: Pinecone = PrivateAttr()
    _index: object = PrivateAttr()
    _namespace: str = PrivateAttr()
    _top_k: int = PrivateAttr()
    _similarity_threshold: float = PrivateAttr()
    _embeddings: object = PrivateAttr()

    def __init__(
        self,
        index_name: str,
        environment: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        namespace: str = ""
    ):
        """Initialize the tool with the given parameters."""
        super().__init__()
        
        # Initialize private attributes
        self._index_name = index_name
        self._environment = environment
        self._top_k = top_k
        self._similarity_threshold = similarity_threshold
        self._namespace = namespace
        
        # Initialize Pinecone
        self._pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self._index = self._pc.Index(index_name)
        
        # Initialize OpenAI embeddings
        self._embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

    def _run(self, query: str, top_k: Optional[int] = None) -> str:
        """Run the tool on the given query."""
        try:
            # Generate embedding for the query using OpenAI
            response = self._embeddings.embed_query(query)
            query_embedding = response

            # Use the provided top_k if specified, otherwise use the default
            k = top_k if top_k is not None else self._top_k

            # Search Pinecone
            results = self._index.query(
                vector=query_embedding,
                top_k=k,
                namespace=self._namespace,
                include_metadata=True
            )

            # Format results
            formatted_results = []
            for match in results.matches:
                if match.score >= self._similarity_threshold:
                    result = {
                        'text': match.metadata.get('text', ''),
                        'score': match.score,
                        'metadata': match.metadata
                    }
                    formatted_results.append(result)

            return json.dumps(formatted_results, indent=2)

        except Exception as e:
            return f"Error searching documents: {str(e)}"

    def add_documents(self, texts: List[str], chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        """Add documents to the search index.
        
        Args:
            texts (List[str]): List of text documents to add
            chunk_size (int): Size of text chunks
            chunk_overlap (int): Overlap between chunks
        """
        # Split texts into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = []
        for text in texts:
            chunks.extend(text_splitter.split_text(text))
        
        # Get embeddings for chunks
        embeddings = self._embeddings.embed_documents(chunks)
        
        # Prepare vectors for upserting
        vectors = []
        for i, (embedding, chunk) in enumerate(zip(embeddings, chunks)):
            vectors.append({
                'id': f'chunk_{i}',
                'values': embedding,
                'metadata': {'text': chunk}
            })
        
        # Upsert to Pinecone in batches
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self._index.upsert(vectors=batch, namespace=self._namespace)

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embeddings for the given text."""
        try:
            response = self._embeddings.embed_query(text)
            return response
        except Exception as e:
            print(f"Error generating embedding: {str(e)}")
            return None 