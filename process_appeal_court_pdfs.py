#!/usr/bin/env python3
"""
Script to process all PDF files in the appeal court 2025/ directory
Uses the process_legal_document function from judgements-classifier.py
"""

import os
import sys
import glob
import json
import time
import argparse
import traceback
import subprocess
from pathlib import Path
import importlib.util
import dotenv

dotenv.load_dotenv()

# Import the process_legal_document function from judgements-classifier.py
# Load the module with the hyphenated filename
spec = importlib.util.spec_from_file_location("judgements_classifier", "judgements-classifier.py")
judgements_classifier = importlib.util.module_from_spec(spec)
sys.modules["judgements_classifier"] = judgements_classifier
spec.loader.exec_module(judgements_classifier)

# Get the required functions
process_legal_document = judgements_classifier.process_legal_document
get_openai_api_key = judgements_classifier.get_openai_api_key

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Process legal PDF documents.')
    parser.add_argument('--pdf-dir', type=str, default="ETL/scrapers/appeal-court/2020/",
                        help='Directory containing PDF files to process (default: ETL/scrapers/appeal-court/2020/)')
    parser.add_argument('--results-dir', type=str, default="results/appeal-court/2020/",
                        help='Directory to save results (default: results/appeal-court/2020/)')
    parser.add_argument('--single-file', type=str, default=None,
                        help='Process only a specific PDF file (provide the full path)')
    parser.add_argument('--file-pattern', type=str, default="*.pdf",
                        help='Pattern to match PDF filenames (default: *.pdf)')
    parser.add_argument('--keep-output', action='store_true',
                        help='Do not delete the output.json file after processing')
    parser.add_argument('--skip-mongodb', action='store_true',
                        help='Skip inserting data into MongoDB')
    parser.add_argument('--retries', type=int, default=2,
                        help='Number of retries for failed documents (default: 2)')
    parser.add_argument('--retry-delay', type=int, default=60,
                        help='Delay in seconds between retries (default: 60)')
    parser.add_argument('--skip-existing', action='store_true',
                        help='Skip files that already have results')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit the number of files to process')
    parser.add_argument('--output-file', type=str, default="output_appeal_court.json",
                        help='Path to output JSON file (default: output_appeal_court.json)')
    return parser.parse_args()

def process_pdf_with_retry(pdf_file, results_dir, output_file, args):
    """Process a PDF file with retry logic."""
    pdf_filename = os.path.basename(pdf_file)
    result_filename = f"{Path(pdf_filename).stem}.json"
    result_path = os.path.join(results_dir, result_filename)
    
    # Skip if the result already exists and skip_existing is True
    if args.skip_existing and os.path.exists(result_path):
        print(f"⏭️ Skipping {pdf_filename} - result already exists at {result_path}")
        return True, None
    
    # Try processing the file with retries
    max_retries = max(0, args.retries)
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"🔄 Retry attempt {attempt}/{max_retries} for {pdf_filename}")
                time.sleep(args.retry_delay)
            
            # Process the PDF file
            # Override the default output file in the process_legal_document function
            # This is a workaround to pass a different output file path
            original_os_path_abspath = os.path.abspath
            def custom_abspath(path):
                if path == "output.json":
                    return output_file
                return original_os_path_abspath(path)
            
            # Apply the monkey patch
            os.path.abspath = custom_abspath
            
            try:
                result = process_legal_document(pdf_file)
            finally:
                # Restore the original function
                os.path.abspath = original_os_path_abspath
            
            # Check if the output file was created
            if os.path.exists(output_file):
                # Copy the content to the results directory
                with open(output_file, 'r') as src_file:
                    content = src_file.read()
                    
                    with open(result_path, 'w') as dest_file:
                        dest_file.write(content)
                
                print(f"✅ Successfully processed {pdf_filename} and saved results to {result_path}")
                
                # Call metadata-creation.py to insert data into MongoDB if not skipped
                if not args.skip_mongodb:
                    try:
                        print(f"📊 Inserting data from {output_file} into MongoDB (appeal_court_judgments collection)...")
                        subprocess.run([sys.executable, "metadata-creation.py", "--collection", "appeal_court_judgments", "--input-file", output_file], check=True)
                        print(f"✅ Successfully inserted data into MongoDB")
                        # The metadata-creation.py script handles the deletion of output.json
                    except subprocess.CalledProcessError as e:
                        print(f"❌ Error inserting data into MongoDB: {str(e)}")
                        # Clean up the output file if there was an error and we're not keeping it
                        if not args.keep_output:
                            try:
                                os.remove(output_file)
                            except Exception as e:
                                print(f"Warning: Could not remove output file: {str(e)}")
                else:
                    # Clean up the output file if not keeping it and skipping MongoDB
                    if not args.keep_output:
                        try:
                            os.remove(output_file)
                        except Exception as e:
                            print(f"Warning: Could not remove output file: {str(e)}")
                
                return True, None
            else:
                error_msg = f"Failed to create output for {pdf_filename}"
                print(f"⚠️ {error_msg}")
                
                if attempt < max_retries:
                    continue  # Try again
                else:
                    return False, error_msg
        
        except Exception as e:
            error_msg = f"Error processing {pdf_filename}: {str(e)}"
            print(f"❌ {error_msg}")
            traceback.print_exc()
            
            if attempt < max_retries:
                continue  # Try again
            else:
                return False, error_msg
    
    return False, f"Maximum retries exceeded for {pdf_filename}"

def main():
    """
    Main function to process PDFs in the specified directory
    """
    # Parse command line arguments
    args = parse_arguments()
    
    # Set the OpenAI API key
    api_key = get_openai_api_key()
    if not api_key:
        print("Error: OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
        sys.exit(1)
    
    # Get the absolute path for the output file
    output_file = os.path.abspath(args.output_file)
    
    # Determine which PDF files to process
    if args.single_file:
        if not os.path.isfile(args.single_file):
            print(f"Error: The specified file '{args.single_file}' does not exist.")
            sys.exit(1)
        pdf_files = [args.single_file]
        print(f"Processing single file: {args.single_file}")
    else:
        # Directory containing the PDF files
        pdf_directory = args.pdf_dir
        
        if not os.path.isdir(pdf_directory):
            print(f"Warning: Directory '{pdf_directory}' does not exist. Creating it...")
            try:
                # Create the directory if it doesn't exist
                os.makedirs(pdf_directory, exist_ok=True)
            except Exception as e:
                print(f"Error creating directory: {str(e)}")
                sys.exit(1)
        
        # Find all PDF files in the directory and its subdirectories
        pdf_pattern = os.path.join(pdf_directory, "**", args.file_pattern)
        pdf_files = glob.glob(pdf_pattern, recursive=True)
        
        if not pdf_files:
            print(f"No files matching pattern '{args.file_pattern}' found in {pdf_directory}")
            return
        
        # Sort files by name for consistent processing order
        pdf_files.sort()
        
        # Apply limit if specified
        if args.limit is not None and args.limit > 0:
            if len(pdf_files) > args.limit:
                print(f"Limiting processing to {args.limit} of {len(pdf_files)} files")
                pdf_files = pdf_files[:args.limit]
        
        print(f"Found {len(pdf_files)} files to process")
    
    # Create results directory
    results_dir = args.results_dir
    try:
        os.makedirs(results_dir, exist_ok=True)
    except Exception as e:
        print(f"Error creating results directory: {str(e)}")
        sys.exit(1)
    
    # Process each PDF file
    success_count = 0
    failed_files = []
    error_messages = {}
    
    print(f"Starting processing at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    start_time = time.time()
    
    for i, pdf_file in enumerate(pdf_files):
        pdf_filename = os.path.basename(pdf_file)
        print(f"\n[{i+1}/{len(pdf_files)}] Processing {pdf_filename}...")
        
        # Process with retry logic
        success, error = process_pdf_with_retry(pdf_file, results_dir, output_file, args)
        
        if success:
            success_count += 1
        else:
            failed_files.append(pdf_filename)
            error_messages[pdf_filename] = error
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Print summary
    print("\n" + "="*50)
    print(f"Processing complete at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total elapsed time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
    print(f"Files processed: {success_count}/{len(pdf_files)} successfully")
    
    if failed_files:
        print(f"\nFailed files ({len(failed_files)}):")
        for failed_file in failed_files:
            error_msg = error_messages.get(failed_file, "Unknown error")
            print(f"  - {failed_file}: {error_msg}")
        
        # Save the list of failed files with error messages
        failed_files_path = os.path.join(results_dir, "failed_files.json")
        try:
            with open(failed_files_path, 'w') as f:
                json.dump(error_messages, f, indent=2)
            print(f"Failed files list saved to {failed_files_path}")
        except Exception as e:
            print(f"Error saving failed files list: {str(e)}")
    
    # We no longer need to clean up output.json here as it's handled by dataset-creation.py or in process_pdf_with_retry

if __name__ == "__main__":
    main() 
