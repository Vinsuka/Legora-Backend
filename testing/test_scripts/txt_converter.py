import os
import fitz  # PyMuPDF

# Directories
pdf_directory = "judgements"
txt_output_directory = "judgement-txt/txt_files"

# Loop over each PDF file in the source directory and maintain the directory structure
for root, _, files in os.walk(pdf_directory):
    for pdf_filename in files:
        if pdf_filename.endswith(".pdf"):
            # Construct the full PDF path
            pdf_path = os.path.join(root, pdf_filename)
            
            # Recreate the directory structure in the output directory
            relative_path = os.path.relpath(root, pdf_directory)  # Get the relative path under 'output'
            txt_dir = os.path.join(txt_output_directory, relative_path)
            os.makedirs(txt_dir, exist_ok=True)
            
            # Define the TXT file path, changing the extension to .txt
            txt_filename = f"{os.path.splitext(pdf_filename)[0]}.txt"
            txt_path = os.path.join(txt_dir, txt_filename)

            # Open the PDF and extract text
            with fitz.open(pdf_path) as pdf_document:
                text = ""
                for page_num in range(pdf_document.page_count):
                    page = pdf_document[page_num]
                    text += page.get_text()

            # Write the extracted text to the TXT file
            with open(txt_path, "w", encoding="utf-8") as txt_file:
                txt_file.write(text)

            print(f"Converted {pdf_path} to {txt_path}")

print("All PDF files have been converted to TXT files with the same directory structure.")
