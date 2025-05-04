# Testing Framework

This directory contains the testing framework for the Legal Document Analysis System. It includes various test suites, sample outputs, and testing scripts to ensure the reliability and accuracy of the system components.

## 📁 Directory Structure

```
testing/
├── model_tests/           # Model testing and evaluation
│   ├── FineTunning/      # Fine-tuning experiments
│   ├── test_pipeline/    # Pipeline testing
│   ├── dataset/          # Test datasets
│   └── contracts/        # Contract testing
├── embeddings/           # Embedding model testing
├── sample_outputs/      # Sample outputs for reference
├── test_pdf/            # Test PDF documents
└── test_scripts/        # Testing utilities and scripts
```

## 🧪 Testing Components

### 1. Model Tests (`model_tests/`)
- **Fine-tuning Tests**: Experiments with model fine-tuning
  - `openai_model_finetune.py`: OpenAI model fine-tuning implementation
- **Pipeline Tests**: End-to-end pipeline testing
- **Vector Database Tests**:
  - `pinecone_inspect.py`: Pinecone vector database inspection
  - `upsert_to_qdrant.py`: Qdrant vector database operations
  - `upsert_mongodb_data_to_qdrant.py`: MongoDB to Qdrant data migration

### 2. Embedding Tests (`embeddings/`)
- **CrewAI Integration**:
  - `test_2_crewai_flow.py`: CrewAI workflow testing
- **Court Document Processing**:
  - `supreme_court_tool.py`: Supreme Court document processing tests

### 3. Test Scripts (`test_scripts/`)
- **Document Processing**:
  - `judgement_classifier.ipynb`: Judgment classification testing
  - `txt_converter.py`: Text conversion utilities
- **Search and Retrieval**:
  - `hybrid_search.py`: Hybrid search implementation testing
- **Web Scraping**:
  - `scraper.py`: Web scraping functionality tests
- **Core Testing**:
  - `main.py`: Main testing script
  - `helper.py`: Testing utilities
  - `legal_judge.py`: Legal judgment processing tests

## 🛠️ Usage

### Running Model Tests

```bash
# Fine-tuning tests
python model_tests/openai_model_finetune.py

# Vector database tests
python model_tests/pinecone_inspect.py
python model_tests/upsert_to_qdrant.py
```

### Running Embedding Tests

```bash
# CrewAI workflow testing
python embeddings/test_2_crewai_flow.py

# Supreme Court document processing
python embeddings/supreme_court_tool.py
```

### Running Test Scripts

```bash
# Main testing script
python test_scripts/main.py

# Hybrid search testing
python test_scripts/hybrid_search.py
```

## 📊 Test Data

- `test_pdf/`: Contains sample PDF documents for testing
- `sample_outputs/`: Reference outputs for comparison
- `model_tests/dataset/`: Test datasets for model evaluation
- `model_tests/contracts/`: Contract documents for testing

## 🔍 Testing Methodology

1. **Model Testing**:
   - Fine-tuning performance evaluation
   - Vector database operations verification
   - Pipeline integration testing

2. **Embedding Testing**:
   - CrewAI workflow validation
   - Document processing accuracy
   - Integration with vector databases

3. **Script Testing**:
   - Document classification accuracy
   - Text conversion reliability
   - Search and retrieval performance
   - Web scraping functionality

## 📝 Notes

- Test results are stored in respective directories
- Sample outputs serve as reference for expected results
- Test scripts include error handling and logging
- Regular testing is recommended before deployment

## ⚠️ Requirements

- Python 3.x
- Required Python packages (to be listed in requirements.txt)
- Access to vector databases (Pinecone/Qdrant)
- OpenAI API key for fine-tuning tests
- MongoDB connection for database tests
