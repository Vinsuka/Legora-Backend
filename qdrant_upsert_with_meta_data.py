import os
import uuid
import time
import pdfplumber
from openai import OpenAI
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException
from qdrant_client.models import PointStruct, Distance, VectorParams
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import os.path
import sys

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Qdrant client
qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
    timeout=60  # Increase default timeout to 60 seconds
)

# MongoDB connection parameters
MONGO_USERNAME = os.getenv("username", "dunith20200471")
MONGO_PASSWORD = os.getenv("Password", "cveJrDEdS7bYeFwk")
MONGO_URI = os.getenv("MONGO_URI", f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@fypcust0.abd2d.mongodb.net/?retryWrites=true&w=majority&appName=fypcust0")
DB_NAME = os.getenv("MONGO_DB_NAME", "legal_documents")
COLLECTION_NAME = "supreme_court_judgments"  # Directly use the correct collection name

# Initialize MongoDB client
try:
    # Create a new client and connect to the server using ServerApi
    mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
    
    # Send a ping to confirm a successful connection
    mongo_client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
    
    db = mongo_client[DB_NAME]
    collection = db[COLLECTION_NAME]
    print(f"Connected to MongoDB: {DB_NAME}.{COLLECTION_NAME}")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    sys.exit(1)

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

# Extract filename from path
def extract_filename(path):
    return os.path.basename(path)

# Find a file recursively in a directory structure
def find_pdf_file(base_dir, filename):
    """
    Recursively search for a PDF file with the given filename within a directory structure
    
    Args:
        base_dir (str): The base directory to start the search
        filename (str): The name of the file to search for
        
    Returns:
        str: Full path to the file if found, None otherwise
    """
    for root, dirs, files in os.walk(base_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None

# Process civil cases from MongoDB and upsert to Qdrant
def process_civil_cases(base_pdf_dir, qdrant, collection_name):
    # Create Qdrant collection if it doesn't exist
    if not qdrant.collection_exists(collection_name):
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )
    
    # Query MongoDB for civil cases with case-insensitive search
    case_type_query = {"case_type": {"$regex": "civil", "$options": "i"}}
    civil_cases = collection.find(case_type_query)
    count = collection.count_documents(case_type_query)
    
    if count == 0:
        print("No civil cases found in MongoDB")
        return
    
    print(f"Found {count} civil cases. Processing...")
    
    # Process each civil case
    processed_count = 0
    skipped_count = 0
    
    for case in civil_cases:
        # Extract filename from the path
        pdf_filename = extract_filename(case["pdf_file_name"])
        
        # Search for the PDF file recursively
        pdf_path = find_pdf_file(base_pdf_dir, pdf_filename)
        
        if not pdf_path:
            print(f"PDF file not found: {pdf_filename}")
            skipped_count += 1
            continue
        
        print(f"Processing {pdf_filename}...")
        
        try:
            # Extract text from PDF
            text_chunks = extract_text_from_pdf(pdf_path)
            
            if not text_chunks:
                print(f"No text was extracted from {pdf_filename}")
                skipped_count += 1
                continue
            
            # Create metadata from MongoDB document
            metadata = {
                "case_name": case.get("case_name", ""),
                "case_number": case.get("case_number", ""),
                "judges": case.get("judges", []),
                "case_subtype": case.get("case_subtype", []),
                "court": case.get("court", ""),
                "outcome_tags": case.get("outcome_tags", []),
                "labor_tags": case.get("labor_tags", []),
                "summary": case.get("summary", ""),
                "complianceList": case.get("complianceList", []),
                "source": pdf_filename
            }
            
            # Store embeddings with metadata
            points = []
            for chunk in text_chunks:
                embedding = get_openai_embedding(chunk)
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={"text": chunk, **metadata}
                ))
            
            if points:
                batch_upsert(qdrant, collection_name, points)
                print(f"Successfully processed {pdf_filename} and added {len(points)} chunks to {collection_name}")
                processed_count += 1
        except Exception as e:
            print(f"Error processing {pdf_filename}: {str(e)}")
            print("Continuing with next file...")
            skipped_count += 1
            continue
    
    print(f"All civil cases have been processed. Successfully processed {processed_count} cases, skipped {skipped_count} cases.")

# Example usage
if __name__ == "__main__":
    pdf_dir = "ETL/scrapers/supreme-court/2024/"  # Base directory containing the PDF files
    collection_name = "supreme_court_judgments"    # Replace with your collection name
    process_civil_cases(pdf_dir, qdrant_client, collection_name)
