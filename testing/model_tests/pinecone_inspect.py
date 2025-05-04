import os
from pinecone import Pinecone
from dotenv import load_dotenv
from openai import OpenAI

# Load API keys from .env
load_dotenv()
pinecone_api_key = os.getenv("PINECONE_API_KEY")
index_name = "judgments-index"  # Change if your index name is different
namespace = "appeal_court"      # Change to "supreme_court" or other as needed

# Initialize Pinecone client
pc = Pinecone(api_key=pinecone_api_key)
index = pc.Index(index_name)

# 1. Print index stats (shows vector count per namespace)
print("=== Index Stats ===")
stats = index.describe_index_stats()
print(stats)

# 2. List all vector IDs in the namespace (for serverless indexes)
try:
    print("\n=== Listing Vector IDs in Namespace ===")
    # This may not be available for all index types; if not, skip to step 3
    ids = []
    response = index.list(namespace=namespace)
    for v in response['vectors']:
        ids.append(v['id'])
    print(f"Found {len(ids)} vector IDs in namespace '{namespace}'.")
    print("Sample IDs:", ids[:5])
except Exception as e:
    print("Could not list vector IDs directly:", e)

# 3. Fetch a few vectors by ID (if you know some IDs, use them; else, try brute force)
# If you don't know any IDs, you can try to query for all vectors using a dummy vector
# or use the stats to estimate how many vectors are present.

# Optionally, try to fetch by a known pattern if you used e.g. "filename_chunk_0"
sample_ids = [f"chunk_{i}" for i in range(5)]  # Adjust this pattern as needed

print("\n=== Fetching Sample Vectors ===")
for vid in sample_ids:
    try:
        result = index.fetch(ids=[vid], namespace=namespace)
        print(f"ID: {vid} ->", result)
    except Exception as e:
        print(f"Error fetching {vid}:", e)

# 4. (Optional) Query for all vectors using a dummy vector and high topK
import numpy as np

print("\n=== Querying for All Vectors (topK=100) ===")
dummy_vector = np.zeros(1536).tolist()  # Use the correct dimension for your index
try:
    query_result = index.query(
        vector=dummy_vector,
        top_k=100,
        include_values=True,
        include_metadata=True,
        namespace=namespace
    )
    print(f"Found {len(query_result['matches'])} matches.")
    for match in query_result['matches'][:5]:
        print("ID:", match['id'])
        print("Score:", match['score'])
        print("Metadata:", match.get('metadata'))
        print("---")
except Exception as e:
    print("Error querying vectors:", e)

print("\n=== Semantic Search with OpenAI Embeddings ===")
query_text = "Magistrate of Matara Central Environmental Authority"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    # Generate embedding for the query
    response = client.embeddings.create(
        input=query_text,
        model="text-embedding-3-small"  # Use the same model as your upserts
    )
    query_embedding = response.data[0].embedding

    # Query Pinecone with the embedding
    query_result = index.query(
        vector=query_embedding,
        top_k=5,
        include_values=False,
        include_metadata=True,
        namespace=namespace
    )
    print(f"Found {len(query_result['matches'])} matches.")
    for match in query_result['matches']:
        print("ID:", match['id'])
        print("Score:", match['score'])
        print("Metadata:", match.get('metadata'))
        print("---")
except Exception as e:
    print("Error running embedding-based search:", e)