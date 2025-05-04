import os
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

index = pc.Index("compliance-index")
namespace1 = "legal-court-judgements"
namespace2 = "legal-rules-and-regs"
namespace3 = "legal-clauses"

def get_openai_embedding(text):
    return client.embeddings.create(input=text, model="text-embedding-3-small")["data"][0]["embedding"]

def search_court_judgements(query, top_k=5):
    """
    Search in legal court judgements namespace
    """
    query_embedding = get_openai_embedding(query)
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        namespace=namespace1,
        include_metadata=True
    )
    return [match.metadata['text'] for match in results.matches]

def search_rules_and_regulations(query, top_k=5):
    """
    Search in legal rules and regulations namespace
    """
    query_embedding = get_openai_embedding(query)
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        namespace=namespace2,
        include_metadata=True
    )
    return [match.metadata['text'] for match in results.matches]

def search_legal_clauses(query, top_k=5):
    """
    Search in legal clauses namespace
    """
    query_embedding = get_openai_embedding(query)
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        namespace=namespace3,
        include_metadata=True
    )
    return [match.metadata['text'] for match in results.matches]

def rerank_results(query, results, model="gpt-3.5-turbo"):
    """
    Rerank the retrieved chunks based on their relevance to the query
    """
    if not results:
        return []
        
    # Prepare prompt for reranking
    rerank_prompt = f"""
    Rate the relevance of each text to the query: "{query}"
    Assign a score from 0 to 10, where 10 is most relevant.
    Return only the score, nothing else.
    
    Text: {{text}}
    """
    
    scored_results = []
    for text in results:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": rerank_prompt.format(text=text)}],
            max_tokens=10
        )
        try:
            score = float(response.choices[0].message.content.strip())
            scored_results.append((score, text))
        except ValueError:
            scored_results.append((0, text))
    
    # Sort by score in descending order and return just the texts
    return [text for _, text in sorted(scored_results, reverse=True)]

def generate_legal_response(query):
    """
    Generate a legal response using the search results with reranking
    """
    # Get initial results
    court_judgements = search_court_judgements(query)
    rules_and_regulations = search_rules_and_regulations(query)
    legal_clauses = search_legal_clauses(query)
    
    # Rerank each category of results
    court_judgements = rerank_results(query, court_judgements)
    rules_and_regulations = rerank_results(query, rules_and_regulations)
    legal_clauses = rerank_results(query, legal_clauses)
    
    prompt = f"""
    You are a legal expert. You are given a query and a list of legal documents.
    Your task is to generate a legal response to the query using the provided documents.
    The documents are sorted by relevance to your query.
    Here are the documents:
    
    Court Judgements:
    {court_judgements}
    
    Rules and Regulations:
    {rules_and_regulations}
    
    Legal Clauses:
    {legal_clauses}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "user": prompt, "system": "You are a legal expert. You are given a query and a list of legal documents. Your task is to generate a legal response to the query using the provided documents. The documents are sorted by relevance to your query."}],
        max_tokens=1000
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    query = "What is the legal definition of a breach of contract?"
    response = generate_legal_response(query)
    print(response)
