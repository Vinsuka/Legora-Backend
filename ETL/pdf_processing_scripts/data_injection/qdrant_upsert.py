import os
import uuid
import time
import pdfplumber
from openai import OpenAI
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException
from qdrant_client.models import PointStruct, Distance, VectorParams

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
    timeout=60  # Increase default timeout to 60 seconds
)

# Extract text from PDF
def extract_text_from_pdf(pdf_path):
    text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text.strip())
    return text

# Generate OpenAI embeddings
def get_openai_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def batch_upsert(qdrant, collection_name, points, batch_size=20, max_retries=3):
    """Upload points to Qdrant in batches with retry logic"""
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        retry_count = 0
        while retry_count < max_retries:
            try:
                qdrant.upsert(collection_name=collection_name, points=batch)
                print(f"Successfully uploaded batch {i//batch_size + 1} of {(len(points) + batch_size - 1)//batch_size}")
                break
            except ResponseHandlingException as e:
                retry_count += 1
                if retry_count == max_retries:
                    print(f"Failed to upload batch after {max_retries} retries. Error: {str(e)}")
                    raise
                print(f"Retry {retry_count}/{max_retries} after error: {str(e)}")
                time.sleep(2 ** retry_count)  # Exponential backoff

# Store text and embeddings in Qdrant
def load_pdf_to_qdrant(pdf_path, qdrant, collection_name):
    # Extract text from PDF
    text_chunks = extract_text_from_pdf(pdf_path)
    
    # Create Qdrant collection
    if qdrant.collection_exists(collection_name):
        qdrant.delete_collection(collection_name)
    qdrant.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
    )

    # Store embeddings
    points = []
    for chunk in text_chunks:
        embedding = get_openai_embedding(chunk)
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={"text": chunk}
        ))
    batch_upsert(qdrant, collection_name, points)

# Process all PDFs in a directory
def process_pdfs_in_directory(folder_path, qdrant, collection_name):
    # Create Qdrant collection if it doesn't exist
    if not qdrant.collection_exists(collection_name):
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )
    
    # Get list of PDF files in the directory
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"No PDF files found in {folder_path}")
        return
    
    print(f"Found {len(pdf_files)} PDF files. Processing...")
    
    # Process each PDF file
    for pdf_file in pdf_files:
        pdf_path = os.path.join(folder_path, pdf_file)
        print(f"Processing {pdf_file}...")
        
        try:
            # Extract text from PDF
            text_chunks = extract_text_from_pdf(pdf_path)
            
            if not text_chunks:
                print(f"No text was extracted from {pdf_file}")
                continue
            
            # Store embeddings
            points = []
            for chunk in text_chunks:
                embedding = get_openai_embedding(chunk)
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={"text": chunk, "source": pdf_file}
                ))
            
            if points:
                batch_upsert(qdrant, collection_name, points)
                print(f"Successfully processed {pdf_file} and added {len(points)} chunks to {collection_name}")
        except Exception as e:
            print(f"Error processing {pdf_file}: {str(e)}")
            print("Continuing with next file...")
            continue
    
    print(f"All PDF files in {folder_path} have been processed.")

# Example usage
if __name__ == "__main__":
    folder_path = "LABOURACT"  # Replace with your folder path
    collection_name = "legal-docs"   # Replace with your collection name
    process_pdfs_in_directory(folder_path, qdrant_client, collection_name)

