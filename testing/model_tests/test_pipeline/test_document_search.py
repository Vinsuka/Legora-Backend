from dotenv import load_dotenv
import os
from tools.pinecone_rag_tool import DocumentSearchTool

# Load environment variables
load_dotenv()

def test_search_tool():
    # Initialize the search tools for both namespaces
    appeal_search_tool = DocumentSearchTool(
        index_name="judgments-index",
        environment="custom-embeddings",
        top_k=5,
        similarity_threshold=0.0001,  # Very low threshold to see all results
        namespace="appeal_court"
    )
    
    supreme_search_tool = DocumentSearchTool(
        index_name="judgments-index",
        environment="custom-embeddings",
        top_k=5,
        similarity_threshold=0.0001,  # Very low threshold to see all results
        namespace="supreme_court"
    )
    
    # Test query
    test_query = "The learned Magistrate of Matara ordered on 11.12.2014 to implement certain practical recommendations"
    
    print("\n=== Testing Appeal Court Search ===")
    print("Query:", test_query)
    print("\nResults:")
    appeal_results = appeal_search_tool._run(query=test_query, top_k=5)
    print(appeal_results)
    
    print("\n=== Testing Supreme Court Search ===")
    print("Query:", test_query)
    print("\nResults:")
    supreme_results = supreme_search_tool._run(query=test_query, top_k=5)
    print(supreme_results)

def test_with_different_queries():
    # Initialize one search tool
    search_tool = DocumentSearchTool(
        index_name="judgments-index",
        environment="custom-embeddings",
        top_k=3,
        similarity_threshold=0.0001,  # Very low threshold to see all results
        namespace="appeal_court"  # Test with appeal court namespace
    )
    
    # List of test queries
    test_queries = [
        "Environmental Authority recommendations",
        "Magistrate of Matara",
        "company premises implementation",
        "Central Environmental Authority",
    ]
    
    print("\n=== Testing Multiple Queries ===")
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("Results:")
        results = search_tool._run(query=query, top_k=3)
        print(results)
        print("-" * 80)

if __name__ == "__main__":
    # Check for API keys
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("PINECONE_API_KEY"):
        print("Please set OPENAI_API_KEY and PINECONE_API_KEY in your .env file")
        exit(1)
    
    # Run the tests
    print("Running search tool tests...")
    test_search_tool()
    
    print("\nRunning multiple query tests...")
    test_with_different_queries() 