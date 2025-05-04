# Legal Document Processor

This tool processes legal document PDFs to extract structured information using AI analysis.

## Prerequisites

- Python 3.7+
- Required packages (install with `pip install -r requirements.txt`):
  - PyPDF2
  - crewai
  - crewai-tools
  - langchain
  - dotenv
  - pydantic

## Usage

### Processing All PDFs in a Directory

```bash
python process_supreme_court_pdfs.py
```

This will process all PDF files in the default directory (`scrapers/supreme-court/2024/`) and save results to `results/supreme-court/2024/`.

### Command Line Options

```bash
python process_supreme_court_pdfs.py --pdf-dir "path/to/pdfs" --results-dir "path/to/results" --file-pattern "*.pdf"
```

#### Available Options

| Option | Description | Default |
|--------|-------------|---------|
| `--pdf-dir` | Directory containing PDF files | `scrapers/supreme-court/2024/` |
| `--results-dir` | Directory to save results | `results/supreme-court/2024/` |
| `--single-file` | Process only a specific PDF file | None |
| `--file-pattern` | Pattern to match PDF filenames | `*.pdf` |
| `--keep-output` | Do not delete the output.json file | False |
| `--retries` | Number of retries for failed documents | 2 |
| `--retry-delay` | Delay in seconds between retries | 60 |
| `--skip-existing` | Skip files that already have results | False |
| `--limit` | Limit the number of files to process | None |

### Examples

#### Process a Single File

```bash
python process_supreme_court_pdfs.py --single-file "path/to/document.pdf"
```

#### Process Only Files with a Specific Pattern

```bash
python process_supreme_court_pdfs.py --file-pattern "*appeal*.pdf"
```

#### Skip Files That Already Have Results

```bash
python process_supreme_court_pdfs.py --skip-existing
```

#### Process a Limited Number of Files

```bash
python process_supreme_court_pdfs.py --limit 5
```

## Output

For each processed PDF, the script creates a JSON file with structured information about the legal document. The JSON files are saved in the results directory.

If any files fail to process, a `failed_files.json` file is created in the results directory listing the failed files and error messages.

## Troubleshooting

- If the script fails, check the error messages in the console output or the `failed_files.json` file.
- Increase the number of retries with `--retries` for more attempts at processing problematic files.
- Use the `--keep-output` option to keep the intermediate output file for debugging.

## License

This tool is intended for research and educational purposes only. 