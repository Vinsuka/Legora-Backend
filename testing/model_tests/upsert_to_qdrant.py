import os
import uuid
import time
import pdfplumber
from transformers import AutoTokenizer, AutoModel
import torch
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException
from qdrant_client.models import PointStruct, Distance, VectorParams
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Initialize Legal BERT model and tokenizer
model_name = "nlpaueb/legal-bert-base-uncased"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)

# Initialize Qdrant client
qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
    timeout=60
)

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text.strip())
    return text

def get_legal_bert_embedding(text, max_length=512):
    """Generate embeddings using Legal BERT"""
    # Tokenize the text
    inputs = tokenizer(
        text,
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors="pt"
    ).to(device)
    
    # Generate embeddings
    with torch.no_grad():
        outputs = model(**inputs)
        # Use the [CLS] token embedding as the document embedding
        embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
    
    return embeddings[0]  # Return the first (and only) embedding

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

def process_pdfs_in_directory(base_path, court_type, year, month, qdrant):
    """Process PDFs in a specific directory and upsert to Qdrant"""
    # Create directory path
    dir_path = os.path.join(base_path, court_type, str(year), f"{month:02d}")
    
    if not os.path.exists(dir_path):
        print(f"Directory not found: {dir_path}")
        return
    
    # Get list of PDF files
    pdf_files = [f for f in os.listdir(dir_path) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"No PDF files found in {dir_path}")
        return
    
    print(f"Found {len(pdf_files)} PDF files in {dir_path}. Processing...")
    
    # Process each PDF file
    for pdf_file in tqdm(pdf_files, desc=f"Processing {court_type} {year}-{month:02d}"):
        pdf_path = os.path.join(dir_path, pdf_file)
        
        try:
            # Extract text from PDF
            text_chunks = extract_text_from_pdf(pdf_path)
            
            if not text_chunks:
                print(f"No text was extracted from {pdf_file}")
                continue
            
            # Store embeddings
            points = []
            for chunk in text_chunks:
                embedding = get_legal_bert_embedding(chunk)
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding.tolist(),
                    payload={"text": chunk}
                ))
            
            if points:
                # Use different collection based on court type
                collection_name = "appeal_court_judgements_2" if court_type == "appeal-court" else "supreme_court_judgements_2"
                batch_upsert(qdrant, collection_name, points)
                print(f"Successfully processed {pdf_file} and added {len(points)} chunks to {collection_name}")
        except Exception as e:
            print(f"Error processing {pdf_file}: {str(e)}")
            continue

def main():
    base_path = "ETL/scrapers"
    
    # Create collections if they don't exist
    collections = {
        "appeal_court_judgements_2": "Appeal Court Judgements",
        "supreme_court_judgements_2": "Supreme Court Judgements"
    }
    
    for collection_name, description in collections.items():
        if not qdrant_client.collection_exists(collection_name):
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE)  # Legal BERT embedding size is 768
            )
            print(f"Created collection: {collection_name} ({description})")
    
    # Process both court types
    court_types = ["appeal-court", "supreme-court"]
    years = range(2020, 2025)  # 2020 to 2024
    months = range(1, 13)  # 1 to 12
    
    for court_type in court_types:
        for year in years:
            for month in months:
                process_pdfs_in_directory(
                    base_path,
                    court_type,
                    year,
                    month,
                    qdrant_client
                )

if __name__ == "__main__":
    main() 