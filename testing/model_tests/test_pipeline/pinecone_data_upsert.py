import os
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
from openai import OpenAI
import PyPDF2
from pathlib import Path

# Load API keys
load_dotenv()
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)
pinecone_api_key = os.getenv("PINECONE_API_KEY")

# Initialize Pinecone
pc = Pinecone(api_key=pinecone_api_key)

# Define index name and namespaces
index_name = "judgments-index"
APPEAL_NAMESPACE = "appeal_court"
SUPREME_NAMESPACE = "supreme_court"

def init_pinecone_index():
    """Initialize or recreate Pinecone index with correct dimensions."""
    # Check if the index exists, if not create it
    if index_name not in pc.list_indexes().names():
        pc.create_index(
            name=index_name,
            dimension=3072,  # text-embedding-3-large dimension
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        print(f"✅ Created a new Pinecone index: {index_name}")
    else:
        # Delete existing index if dimensions don't match
        try:
            index = pc.Index(index_name)
            desc = index.describe_index_stats()
            if desc.dimension != 3072:  # Check if dimensions match
                print(f"🔄 Recreating index with correct dimensions...")
                pc.delete_index(index_name)
                pc.create_index(
                    name=index_name,
                    dimension=3072,  # text-embedding-3-large dimension
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
                print(f"✅ Recreated index with correct dimensions")
        except Exception as e:
            print(f"❌ Error checking index dimensions: {str(e)}")
            return None
    
    # Connect to the index
    return pc.Index(index_name)

# Initialize or recreate index with correct dimensions
index = init_pinecone_index()
if index is None:
    print("Failed to initialize Pinecone index")
    exit(1)
print("✅ Pinecone index initialized successfully!")

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text content from a PDF file and clean unnecessary whitespace while preserving meaning."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                # Extract text from page
                page_text = page.extract_text()
                # Clean the text while preserving sentence structure
                page_text = ' '.join(line.strip() for line in page_text.split('\n') if line.strip())
                text += page_text + " "
            return text.strip()
    except Exception as e:
        print(f"Error processing {pdf_path}: {str(e)}")
        return ""

def generate_embedding(text: str):
    """Generates an embedding for a given text using OpenAI."""
    try:
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-large"
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {str(e)}")
        return None

def process_directory(directory_path: str, namespace: str):
    """Process all PDFs in a directory and upsert them to Pinecone."""
    pdf_files = list(Path(directory_path).glob("*.pdf"))
    print(f"\nFound {len(pdf_files)} PDF files in {directory_path}")
    
    if not pdf_files:
        print(f"⚠️ No PDF files found in directory: {directory_path}")
        return
        
    batch_size = 10
    vectors_batch = []
    total_chunks_processed = 0
    total_vectors_upserted = 0
    
    for pdf_file in pdf_files:
        print(f"\n📄 Processing {pdf_file.name}...")
        
        # Extract text from PDF
        text = extract_text_from_pdf(str(pdf_file))
        if not text:
            print(f"⚠️ No text extracted from {pdf_file.name}")
            continue
            
        print(f"✓ Extracted {len(text)} characters from {pdf_file.name}")
        
        # Split text into larger, more meaningful chunks (4000 characters with 200 char overlap)
        chunk_size = 4000
        overlap = 200
        chunks = []
        
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            if len(chunk) < 100:  # Skip very small chunks
                continue
            chunks.append(chunk)
        
        print(f"✓ Split into {len(chunks)} chunks")
        
        for i, chunk in enumerate(chunks):
            embedding = generate_embedding(chunk)
            if embedding:
                # Create a more descriptive ID that includes file info
                chunk_id = f"{pdf_file.stem}_p{i}"
                
                # Store more metadata for better context
                vector = {
                    "id": chunk_id,
                    "values": embedding,
                    "metadata": {
                        "filename": pdf_file.name,
                        "chunk_number": i,
                        "text": chunk,
                        "file_type": "judgment",
                        "court_type": namespace.split("_")[0],  # "appeal" or "supreme"
                        "total_chunks": len(chunks)
                    }
                }
                vectors_batch.append(vector)
                total_chunks_processed += 1
                
                if len(vectors_batch) >= batch_size:
                    try:
                        index.upsert(vectors=vectors_batch, namespace=namespace)
                        total_vectors_upserted += len(vectors_batch)
                        print(f"✅ Upserted batch of {len(vectors_batch)} vectors (Total: {total_vectors_upserted})")
                        vectors_batch = []
                    except Exception as e:
                        print(f"❌ Error upserting batch: {str(e)}")
                        print(f"Error details: {str(e)}")
                        vectors_batch = []
        
    # Upsert any remaining vectors
    if vectors_batch:
        try:
            index.upsert(vectors=vectors_batch, namespace=namespace)
            total_vectors_upserted += len(vectors_batch)
            print(f"✅ Upserted final batch of {len(vectors_batch)} vectors")
        except Exception as e:
            print(f"❌ Error upserting final batch: {str(e)}")
            print(f"Error details: {str(e)}")
    
    print(f"\n📊 Summary for {namespace}:")
    print(f"- Total PDF files processed: {len(pdf_files)}")
    print(f"- Total chunks processed: {total_chunks_processed}")
    print(f"- Total vectors upserted: {total_vectors_upserted}")

def main():
    # Check if directories exist
    appeal_dir = "../../Judgments/Appeal"  # Updated relative path
    supreme_dir = "../../Judgments/Supreme"  # Updated relative path
    
    if not Path(appeal_dir).exists():
        print(f"❌ Appeal Court directory not found: {appeal_dir}")
        return
    if not Path(supreme_dir).exists():
        print(f"❌ Supreme Court directory not found: {supreme_dir}")
        return
    
    # Process Appeal Court documents
    print("\n🔄 Processing Appeal Court documents...")
    process_directory(appeal_dir, APPEAL_NAMESPACE)
    
    # Process Supreme Court documents
    print("\n🔄 Processing Supreme Court documents...")
    process_directory(supreme_dir, SUPREME_NAMESPACE)
    
    # Verify data in index
    try:
        stats = index.describe_index_stats()
        print("\n📊 Index Statistics:")
        print(f"Total vector count: {stats.total_vector_count}")
        print(f"Namespaces: {list(stats.namespaces.keys())}")
        for ns, ns_stats in stats.namespaces.items():
            print(f"- {ns}: {ns_stats.vector_count} vectors")
    except Exception as e:
        print(f"❌ Error getting index stats: {str(e)}")
    
    print("\n✅ Document processing complete!")

if __name__ == "__main__":
    main()