# Legal Document ETL Pipeline

This repository contains the Extract, Transform, Load (ETL) pipeline for processing legal documents from Sri Lankan courts. The pipeline handles the extraction of legal documents from court websites, processing of PDF files, and loading the structured data into a MongoDB database.

## 🏗️ Pipeline Architecture

```
ETL/
├── scrapers/                  # Web scraping components
│   ├── supreme-court/        # Supreme Court scraper
│   ├── appeal-court/         # Court of Appeal scraper
│   ├── supriecourt.py        # Supreme Court scraper implementation
│   ├── appealcourt.py        # Court of Appeal scraper implementation
│   └── update_json.py        # JSON update utilities
├── pdf_processing_scripts/   # PDF processing components
│   ├── data_creation/       # Data creation scripts
│   └── data_injection/      # Data injection scripts
└── process_output_pdfs.py   # Main PDF processing script
```

## 🚀 Components

### 1. Web Scrapers (`scrapers/`)
- **Supreme Court Scraper**: Extracts judgments from the Supreme Court website
- **Court of Appeal Scraper**: Extracts judgments from the Court of Appeal website
- **JSON Update Utilities**: Tools for managing and updating scraped data

### 2. PDF Processing (`pdf_processing_scripts/`)
- **Data Creation**: Scripts for creating structured data from PDFs
- **Data Injection**: Scripts for injecting processed data into the database

### 3. Main Processing Script (`process_output_pdfs.py`)
The main script that orchestrates the entire ETL process:
- Processes PDF files from the scrapers' output directory
- Extracts structured data using legal document processing
- Inserts data into MongoDB
- Handles retries and error management

## 🛠️ Usage

### Processing PDF Files

```bash
python process_output_pdfs.py [options]
```

#### Options:
- `--base-dir`: Base directory containing year folders (default: "scrapers/output")
- `--start-year`: Start year for processing (default: 2020)
- `--end-year`: End year for processing (default: 2024)
- `--results-dir`: Directory to save results (default: "results/appeal-court/")
- `--keep-output`: Do not delete output.json after processing
- `--skip-mongodb`: Skip inserting data into MongoDB
- `--retries`: Number of retries for failed documents (default: 2)
- `--retry-delay`: Delay in seconds between retries (default: 60)
- `--skip-existing`: Skip files that already have results
- `--limit`: Limit the number of files to process
- `--output-file`: Path to output JSON file

### Running Scrapers

#### Supreme Court:
```bash
python scrapers/supriecourt.py
```

#### Court of Appeal:
```bash
python scrapers/appealcourt.py
```

## 🔄 Data Flow

1. **Extraction**: Legal documents are scraped from court websites
2. **Transformation**: PDFs are processed to extract structured data
3. **Loading**: Processed data is stored in MongoDB

## 📦 Dependencies

- Python 3.x
- MongoDB
- Required Python packages (to be listed in requirements.txt)

## ⚠️ Requirements

- OpenAI API key (set as environment variable `OPENAI_API_KEY`)
- MongoDB connection
- Sufficient disk space for PDF storage
- Internet connection for web scraping

## 🛡️ Error Handling

The pipeline includes robust error handling:
- Automatic retries for failed document processing
- Detailed error logging
- Skip functionality for already processed files
- MongoDB insertion error handling

## 📝 Notes

- The pipeline is designed to handle large volumes of legal documents
- Processing can be customized through command-line arguments
- Results are stored in a structured directory hierarchy by year and month
