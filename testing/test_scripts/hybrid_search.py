import re
import os
import tiktoken
from openai import OpenAI
from pinecone import Pinecone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up OpenAI API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# Define index
INDEX_NAME = "judgements-new"
NAMESPACE = "appealcourt-judgements-new"

# Initialize Pinecone index
index = pc.Index(INDEX_NAME)
print("✅ Pinecone index initialized!")

# Load tokenizer for token estimation
tokenizer = tiktoken.get_encoding("cl100k_base")

def get_openai_embedding(text):
    """Generate embeddings using OpenAI's text-embedding-3-small model."""
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def extract_metadata_from_query(query):
    """Extract structured metadata from the natural language query."""
    metadata_filters = {}
    
    # Extract judge names - completely revised pattern to handle different sentence structures
    # This will look for names before "was the judge" or after "judge"
    judge_match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+was\s+the\s+judge', query)
    if not judge_match:
        # Try alternate pattern (judge Name)
        judge_match = re.search(r'judge\s+([A-Z][a-z]+\s+[A-Z][a-z]+)', query)
    
    if judge_match:
        judge_name = judge_match.group(1).lower()
        metadata_filters["judges"] = judge_name
        print(f"✓ Found judge: {judge_name}")
    
    # Extract case types
    if re.search(r'\bcriminal\b', query, re.IGNORECASE):
        metadata_filters["case_type"] = "criminal"
        print("✓ Found case type: criminal")
    elif re.search(r'\bcivil\b', query, re.IGNORECASE):
        metadata_filters["case_type"] = "civil"
        print("✓ Found case type: civil")
    
    # Extract case subtypes
    labor_match = re.search(r'\b(labor|labour)\b', query, re.IGNORECASE)
    if labor_match:
        metadata_filters["case_subtype"] = "labor"
        print("✓ Found case subtype: labor")
        
    property_match = re.search(r'\bproperty\b', query, re.IGNORECASE)
    if property_match:
        metadata_filters["case_subtype"] = "property"
        print("✓ Found case subtype: property")
        
    commercial_match = re.search(r'\bcommercial\b', query, re.IGNORECASE)
    if commercial_match:
        metadata_filters["case_subtype"] = "commercial"
        print("✓ Found case subtype: commercial")
        
    fundamental_rights_match = re.search(r'\b(fundamental rights|fundamental right)\b', query, re.IGNORECASE)
    if fundamental_rights_match:
        metadata_filters["case_subtype"] = "fundamental right"
        print("✓ Found case subtype: fundamental right")
    
    # Extract courts
    if re.search(r'\bcourt of appeal\b', query, re.IGNORECASE):
        metadata_filters["court"] = "COURT_OF_APPEAL"
    
    # Extract case numbers (if specifically mentioned)
    case_num_match = re.search(r'case\s+number\s+([A-Za-z0-9/\-]+)', query, re.IGNORECASE)
    if case_num_match:
        metadata_filters["case_number"] = case_num_match.group(1)
    
    # Extract more specific tags from the query
    
    # Process tags (common legal procedures)
    for process_tag in ['certiorari', 'mandamus', 'habeas corpus', 'writ petition', 'appeal']:
        if re.search(r'\b' + process_tag + r'\b', query, re.IGNORECASE):
            metadata_filters["process_tags"] = process_tag
            print(f"✓ Found process tag: {process_tag}")
            break
            
    # Behavior tags
    for behavior_tag in ['negligence', 'misconduct', 'arbitrary', 'unreasonable']:
        if re.search(r'\b' + behavior_tag + r'\b', query, re.IGNORECASE):
            metadata_filters["behaviour_tags"] = behavior_tag
            print(f"✓ Found behavior tag: {behavior_tag}")
            break
    
    # Criminal tags
    for criminal_tag in ['murder', 'assault', 'rape', 'drug', 'trafficking']:
        if re.search(r'\b' + criminal_tag + r'\b', query, re.IGNORECASE):
            metadata_filters["criminal_tags"] = criminal_tag
            print(f"✓ Found criminal tag: {criminal_tag}")
            break
    
    return metadata_filters

def advanced_hybrid_search(query, top_k=5):
    """Perform hybrid search combining metadata filtering and semantic search."""
    # 1. Extract metadata filters from the query
    metadata_filters = extract_metadata_from_query(query)
    print(f"📋 Using metadata filters: {metadata_filters}")
    
    # 2. Generate embedding for semantic search
    query_embedding = get_openai_embedding(query)
    
    # 3. Perform hybrid search
    # If we have metadata filters, apply them
    if metadata_filters:
        # For metadata search and semantic search separately
        print("🔍 Performing two-stage hybrid search...")
        
        # First do a pure semantic search
        semantic_results = index.query(
            namespace=NAMESPACE,
            vector=query_embedding,
            top_k=top_k * 3,  # Get more results to filter
            include_metadata=True
        )
        
        print(f"Found {len(semantic_results['matches'])} initial semantic matches")
        
        # Then filter the results manually for metadata matches
        filtered_matches = []
        for match in semantic_results["matches"]:
            is_match = True
            
            # Check all metadata conditions
            for key, value in metadata_filters.items():
                # Handle array/list fields (all tag fields)
                if key.endswith('_tags') or key in ['judges', 'case_subtype']:
                    field_str = str(match["metadata"].get(key, "")).lower()
                    
                    # For tag fields, we want to see if the value is contained in the field
                    if value.lower() not in field_str:
                        is_match = False
                        break
                elif key == "case_type":
                    # Case type handling (same as before)
                    metadata_case_type = str(match["metadata"].get(key, "")).lower()
                    if "[" in metadata_case_type and "]" in metadata_case_type:
                        type_match = re.search(r"'([^']+)'", metadata_case_type)
                        if type_match:
                            metadata_case_type = type_match.group(1)
                    
                    if value.lower() != metadata_case_type:
                        is_match = False
                        break
                else:
                    # Direct match for other fields
                    if str(match["metadata"].get(key, "")).lower() != value.lower():
                        is_match = False
                        break
            
            if is_match:
                filtered_matches.append(match)
        
        # Use the filtered results if we found any
        if filtered_matches:
            print(f"✅ Found {len(filtered_matches)} matches after filtering")
            results = {"matches": filtered_matches[:top_k]}
        else:
            # Fall back to pure semantic search if no matches
            print("⚠️ No matches with metadata filters, using semantic search only...")
            results = index.query(
                namespace=NAMESPACE,
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
    else:
        # Pure semantic search if no metadata filters
        print("🔍 Performing semantic search only...")
        results = index.query(
            namespace=NAMESPACE,
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
    
    return results

def search_judgements(query, top_k=5):
    """
    Search for judgements using hybrid search and display the results.
    
    Args:
        query (str): The search query
        top_k (int): Number of results to return
    
    Returns:
        dict: The search results
    """
    print("\n🔍 Running hybrid search for:", query)
    results = advanced_hybrid_search(query, top_k=top_k)

    print("\n🔍 Hybrid Search Results:")
    for i, match in enumerate(results["matches"], 1):
        metadata = match["metadata"]
        print(f"Result #{i} - Score: {match['score']:.4f}")
        print(f"Case: {metadata.get('case_name', 'N/A')}")
        print(f"Case Number: {metadata.get('case_number', 'N/A')}")
        print(f"Judges: {metadata.get('judges', 'Not specified')}")
        print(f"Type: {metadata.get('case_type', 'Not specified')}")
        print(f"Subtype: {metadata.get('case_subtype', 'Not specified')}")
        
        # Display relevant tags if they exist and aren't empty
        if metadata.get('process_tags') and str(metadata['process_tags']) != '[]':
            print(f"Process Tags: {metadata['process_tags']}")
        if metadata.get('behaviour_tags') and str(metadata['behaviour_tags']) != '[]':
            print(f"Behaviour Tags: {metadata['behaviour_tags']}")
        if metadata.get('outcome_tags') and str(metadata['outcome_tags']) != '[]':
            print(f"Outcome Tags: {metadata['outcome_tags']}")
            
        # Show any specific domain tags
        domain_tags = []
        for tag_field in ['labor_tags', 'property_tags', 'commercial_tags', 
                         'fundamental_right_tags', 'criminal_tags']:
            if metadata.get(tag_field) and str(metadata[tag_field]) != '[]':
                domain_tags.append(f"{tag_field.replace('_tags', '').capitalize()}: {metadata[tag_field]}")
        
        if domain_tags:
            print(f"Domain-Specific Tags: {', '.join(domain_tags)}")
            
        print(f"Source: {metadata.get('source_url', 'N/A')}")
        print(f"Summary: {metadata.get('summary', 'N/A')[:150]}...")
        print("-" * 80)
    
    return results

if __name__ == "__main__":
    # Example usage
    sample_query = "What are the civil cases which include labour disputes?"
    search_judgements(sample_query) 
