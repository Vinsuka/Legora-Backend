import os
import json
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
import glob
from PyPDF2 import PdfReader

# Load environment variables
load_dotenv()

def extract_text_from_pdf(pdf_path):
    """Extract and clean text from a PDF file."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    
    # Clean the text
    text = ' '.join(text.split())  # Remove extra whitespace and newlines
    text = text.replace('"', '\\"')  # Escape double quotes
    return text

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def find_pdf_path(pdf_filename, base_pdf_dir):
    """
    Search for a PDF file in all subdirectories of the base PDF directory.
    Returns the full path if found, None otherwise.
    """
    # Search in all subdirectories
    search_pattern = os.path.join(base_pdf_dir, "**", pdf_filename)
    matches = glob.glob(search_pattern, recursive=True)
    
    if matches:
        return matches[0]  # Return the first match
    return None

def prepare_training_data(csv_path, pdf_base_dir):
    """
    Prepare training data from the benchmark dataset CSV file.
    Returns a list of training examples in the required format.
    """
    df = pd.read_csv(csv_path, skiprows=1)  # Skip the first row if it's metadata
    
    print("Available columns:", df.columns.tolist())
    print("\nFirst few rows of data:")
    print(df.head())
    
    training_data = []
    
    for _, row in df.iterrows():
        pdf_path = find_pdf_path(row['File Name'], pdf_base_dir)
        if not pdf_path:
            print(f"⚠️ Warning: Could not find PDF file {row['File Name']} in {pdf_base_dir}")
            continue

        # Create the assistant content dictionary
        assistant_content = {
            "clause_text": row["Clause Text"],
            "clause_type": row["Clause Type"],
            "compliance_status": row["Gold Compliance"],
            "legal_justification": row["Legal Justification"],
        }

        pdf_text = extract_text_from_pdf(pdf_path)

        # Append the training message in proper format
        example = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a legal document analyzer. Extract and classify legal clauses from the given text. Return the information in a structured JSON format."
                },
                {
                    "role": "user",
                    "content": f"Extract and classify the legal clause from this contract: {pdf_text}"
                },
                {
                    "role": "assistant",
                    "content": json.dumps(assistant_content, ensure_ascii=False)
                }
            ]
        }
        training_data.append(example)

    return training_data

def save_training_data(training_data, output_path):
    """
    Save training data to a JSONL file.
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for example in training_data:
            f.write(json.dumps(example, ensure_ascii=False) + '\n')

def create_fine_tuning_job(training_file_id):
    """
    Create a fine-tuning job using the prepared training data.
    """
    try:
        response = client.fine_tuning.jobs.create(
            training_file=training_file_id,
            model="gpt-4o-mini",
            hyperparameters={
                "n_epochs": 10
            }
        )
        print(f"Fine-tuning job created successfully. Job ID: {response.id}")
        return response.id
    except Exception as e:
        print(f"Error creating fine-tuning job: {e}")
        return None

def main():
    # Paths
    csv_path = "testing/model_tests/dataset/csv/benchmark_dataset.csv"
    pdf_base_dir = "testing/model_tests/dataset/pdfs"
    training_data_path = "training_data.jsonl"
    
    try:
        # Prepare training data
        print("Preparing training data...")
        training_data = prepare_training_data(csv_path, pdf_base_dir)
        
        if not training_data:
            print("No training data was generated. Please check the CSV file and PDF paths.")
            return
            
        # Save training data
        print("Saving training data...")
        save_training_data(training_data, training_data_path)
        
        # Upload training file to OpenAI
        print("Uploading training file to OpenAI...")
        with open(training_data_path, 'rb') as f:
            training_file = client.files.create(
                file=f,
                purpose='fine-tune'
            )
        
        # Create fine-tuning job
        print("Creating fine-tuning job...")
        job_id = create_fine_tuning_job(training_file.id)
        
        if job_id:
            print(f"Fine-tuning job created successfully with ID: {job_id}")
            print("You can monitor the progress of the fine-tuning job using the OpenAI dashboard.")
        else:
            print("Failed to create fine-tuning job.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
