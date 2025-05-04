from transformers import AutoTokenizer, AutoModel
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
import torch
import uuid
import os
import openai
from pypdf import PdfReader
from openai import OpenAI

# ---------- CONFIGURATION ----------
COLLECTION_NAME = "legal_chunks"
MODEL_NAME = "nlpaueb/legal-bert-base-uncased"

# ---------- INITIALIZE MODELS ----------
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model = AutoModel.from_pretrained(MODEL_NAME)
qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
    timeout=60
)

# ---------- UTILITIES ----------
def chunk_text(text, chunk_size=200, overlap=50):
    words = text.split()
    return [
        ' '.join(words[i:i+chunk_size])
        for i in range(0, len(words), chunk_size - overlap)
    ]

def get_embedding(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state[:, 0, :].squeeze().tolist()

def create_collection():
    qdrant.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=768, distance=Distance.COSINE)
    )

def store_legal_document(doc_id, raw_text):
    chunks = chunk_text(raw_text)
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=get_embedding(chunk),
            payload={"text": chunk, "doc_id": doc_id}
        )
        for chunk in chunks
    ]
    qdrant.upsert(collection_name=COLLECTION_NAME, points=points)

def retrieve_legal_chunks(clause_text, top_k=3):
    embedding = get_embedding(clause_text)
    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=embedding,
        top=top_k,
        with_payload=True
    )
    return [
        {
            "matched_law": r.payload["text"],
            "similarity_score": r.score,
            "doc_id": r.payload.get("doc_id", "unknown")
        }
        for r in results
    ]

def generate_openai_justification(clause_text, retrieved_chunks):
    if not retrieved_chunks:
        return "No relevant legal references found for compliance evaluation."

    context = "\n\n".join([chunk["matched_law"] for chunk in retrieved_chunks])
    prompt = f"""You are a legal compliance expert.
Clause from Contract:
\"\"\"{clause_text}\"\"\"

Relevant Legal References:
\"\"\"{context}\"\"\"

Does this clause comply with the referenced legal rules? Justify your answer."""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ---------- MAIN EXECUTION ----------
if __name__ == "__main__":
    # Step 1: Create Qdrant collection
    create_collection()

    # Step 2: Read legal text from a court judgment PDF
    reader = PdfReader("judgements/appeal-court/2020/01/1_24022023_ca_phc_73_2015_pdf.pdf")
    all_text = ""
    for page in reader.pages:
        all_text += page.extract_text() + "\n"

    # Step 3: Store legal document chunks
    store_legal_document("appeal_2020_case_001", all_text)

    # Step 4: Define a clause to test compliance
    clause = "The company should inform the tribunal within 72 hours."
    results = retrieve_legal_chunks(clause)

    print("\n📝 Clause:")
    print(clause)

    print("\n📚 Matched Legal Chunks:")
    for res in results:
        print("-", res["matched_law"], f"(score: {res['similarity_score']:.2f})")

    # Step 5: Get legal justification from OpenAI
    response = generate_openai_justification(clause, results)
    print("\n🤖 LLM Justification:")
    print(response)
