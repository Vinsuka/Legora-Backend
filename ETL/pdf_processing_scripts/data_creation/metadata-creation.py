import json
import os
import sys
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import openai
from pathlib import Path

# Load environment variables
load_dotenv()

# OpenAI API key setup
openai.api_key = os.getenv("OPENAI_API_KEY")

# MongoDB connection parameters from .env
MONGO_USERNAME = os.getenv("username", "dunith20200471")
MONGO_PASSWORD = os.getenv("Password", "cveJrDEdS7bYeFwk")
MONGO_URI = os.getenv("MONGO_URI", f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@fypcust0.abd2d.mongodb.net/?retryWrites=true&w=majority&appName=fypcust0")
DB_NAME = os.getenv("MONGO_DB_NAME", "legal_documents")
COLLECTION_NAME = os.getenv("MONGO_COLLECTION", "judgments")

def connect_to_mongodb():
    """Establish connection to MongoDB."""
    try:
        # Create a new client and connect to the server using ServerApi
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
        
        # Send a ping to confirm a successful connection
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
        
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        print(f"Connected to MongoDB: {DB_NAME}.{COLLECTION_NAME}")
        return collection
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        sys.exit(1)

def format_data_with_openai(data):
    """Format data using OpenAI API if needed."""
    try:
        # This is a simple example - adjust based on your specific formatting needs
        response = openai.chat.completions.create(
            model="gpt-4o",  # or other appropriate model
            messages=[
                {"role": "system", "content": "You're a data formatter for legal judgments. Format the following data into a structured object with appropriate fields like case_name, judgment_date, court, judges, summary, full_text, etc."},
                {"role": "user", "content": f"Format this data: {json.dumps(data)}"}
            ],
            response_format={"type": "json_object"}
        )
        
        # Extract the formatted JSON from the response
        formatted_data = json.loads(response.choices[0].message.content)
        return formatted_data
    except Exception as e:
        print(f"Error formatting data with OpenAI: {e}")
        # Fall back to using the original data
        return data

def process_json_file(file_path, collection):
    """Process the JSON file and insert into MongoDB."""
    try:
        # Check if file exists
        if not Path(file_path).exists():
            print(f"File not found: {file_path}")
            return False
        
        # Read the JSON file
        with open(file_path, 'r', encoding='utf-8') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                print(f"Error: {file_path} is not a valid JSON file")
                return False
        
        # Handle both single document and list of documents
        if isinstance(data, dict):
            documents = [data]
        elif isinstance(data, list):
            documents = data
        else:
            print(f"Error: Unexpected data format in {file_path}")
            return False
        
        # Format and insert each document
        inserted_count = 0
        for doc in documents:
            formatted_doc = format_data_with_openai(doc)
            result = collection.insert_one(formatted_doc)
            if result.inserted_id:
                inserted_count += 1
        
        print(f"Successfully inserted {inserted_count} documents into MongoDB")
        return True
    except Exception as e:
        print(f"Error processing file: {e}")
        return False

def delete_file(file_path):
    """Delete the file after successful processing."""
    try:
        os.remove(file_path)
        print(f"Successfully deleted: {file_path}")
        return True
    except Exception as e:
        print(f"Error deleting file: {e}")
        return False

def main():
    file_path = "output.json"
    
    # Connect to MongoDB
    collection = connect_to_mongodb()
    
    # Process the file and insert data into MongoDB
    success = process_json_file(file_path, collection)
    
    # Delete the file if processing was successful
    if success:
        delete_file(file_path)

if __name__ == "__main__":
    main()
