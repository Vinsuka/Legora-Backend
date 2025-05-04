import warnings
warnings.filterwarnings('ignore')

import os
from dotenv import load_dotenv, find_dotenv
import yaml
from crewai import Agent, Process, Task, Crew
from crewai_tools import FileReadTool
from crewai_tools import FileWriterTool, TXTSearchTool
import pandas as pd
from typing import List, Dict, Union, Tuple, Any
from pydantic import BaseModel, Field
import tempfile
from pathlib import Path
import shutil
import PyPDF2
from crewai.utilities.events import crewai_event_bus
from types import MethodType
from langchain.tools import BaseTool
from typing import Optional
import json

#------------------------------------------------------------------#  
######## Monkey patch AgentOps integration #########################
#------------------------------------------------------------------#
class MonkeyPatch:
    @staticmethod
    def apply_patches():
        # Create a dummy agentops module to handle imports
        import sys
        sys.modules['agentops'] = type('agentops', (), {
            'ToolEvent': lambda *args, **kwargs: None,
            'ErrorEvent': lambda *args, **kwargs: None,
            'init': lambda *args, **kwargs: None,
            '__file__': 'dummy_agentops.py'
        })
        
        # Save the original emit method
        original_emit = crewai_event_bus.emit
        
        # Create a new emit method that skips agentops events
        def new_emit(self, source, event):
            # Skip agentops-related events that would cause errors
            if hasattr(event, 'tool_name') or hasattr(event, 'error'):
                # These are the problematic events
                return
            # Call the original emit for other events
            try:
                original_emit(source, event)
            except AttributeError:
                # Ignore AttributeError for agentops
                pass
        
        # Replace the emit method
        crewai_event_bus.emit = MethodType(new_emit, crewai_event_bus)

# Apply patches to disable agentops
MonkeyPatch.apply_patches()

#------------------------------------------------------------------#  
######## Load environment variables #################################
#------------------------------------------------------------------#
def load_env():
    _ = load_dotenv(find_dotenv())

def get_openai_api_key():
    load_env()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    return openai_api_key

os.environ['OPENAI_MODEL_NAME'] = 'gpt-4o-mini'
# Disable agentops integration
os.environ['AGENTOPS_DISABLED'] = 'true'
os.environ['CREWAI_DISABLE_TELEMETRY'] = 'true'
os.environ['CREWAI_DISABLE_AGENTOPS'] = 'true'

files = {
    'agents': 'config/agents.yaml',
    'tasks': 'config/tasks.yaml'
}

#------------------------------------------------------------------#  
######## Load configurations from YAML files #######################
#------------------------------------------------------------------#
configs = {}
for config_type, file_path in files.items():
    with open(file_path, 'r') as file:
        configs[config_type] = yaml.safe_load(file)

#------------------------------------------------------------------#  
######## Assign loaded configurations to specific variables ########
#------------------------------------------------------------------#
agents_config = configs['agents']
tasks_config = configs['tasks']

#------------------------------------------------------------------#  
######## Define Pydantic models for expected output ################
#------------------------------------------------------------------#
class FinalJSONFile(BaseModel):
    pdf_file_name: str = Field(description="Name of the judgment PDF file")
    case_type: str = Field(description="Type of case (e.g., civil, criminal)")
    case_name: str = Field(description="Name of the legal case")
    case_number: str = Field(description="Unique identifier for the case")
    judges: str = Field(description="Names of judges presiding over the case")
    case_subtype: str = Field(description="Subtypes of the case", default_factory=list)
    court: str = Field(description="Court where the case was heard (Supreme Court | Appeal Court)")
    summary: str = Field(description="Brief summary of the case")
    complianceList: str = Field(description="List of compliance directives and reasoning")

class ClassifyPDFs(BaseModel):
    case_type: str = Field(description="Type of case (civil or criminal)", enum=["civil", "criminal"])
    reasoning: str = Field(description="Explanation for why this case is classified as civil or criminal based on the given context")

#------------------------------------------------------------------#
######## Define callback function ##################################
#------------------------------------------------------------------#
def callback_function(output):
    """
    Callback function for task completion
    Args:
        output: The task output object
    """
    # Do something after the task is completed
    print(f"Task completed! Output: {output}")

def validate_agent_output(result: str) -> Tuple[bool, Union[str, Dict[str, Any]]]:
    """
    Validates if the agent's output follows the expected JSON format.
    
    Args:
        result (str): JSON string output from the agent
        
    Returns:
        Tuple[bool, Union[str, Dict]]: (success, data/error_message)
    """
    # Expected fields based on FinalJSONFile class
    expected_fields = [
        'name', 'caseNumber', 'caseType', 'caseSubType', 'court', 'sourceUrl', 
        'judges', 'processTags', 'behaviourTags', 'outcomeTags', 'propertyTags',
        'familyTags', 'commercialTags', 'laborTags', 'fundamentalRightTags', 
        'criminalTags', 'summary'
    ]
    
    try:
        # Try to parse the JSON string
        data = json.loads(result)
        
        if not isinstance(data, dict) and not isinstance(data, list):
            return (False, "JSON output must be either an object or an array")
        
        # If it's a list, validate each item
        if isinstance(data, list):
            for idx, item in enumerate(data):
                if not isinstance(item, dict):
                    return (False, f"Item at index {idx} is not a valid JSON object")
                
                # Check if all expected fields are present
                missing_fields = [field for field in expected_fields if field not in item]
                if missing_fields:
                    return (False, f"Item at index {idx} is missing required fields: {', '.join(missing_fields)}")
        
        # If it's a single object, validate it
        else:
            # Check if all expected fields are present
            missing_fields = [field for field in expected_fields if field not in data]
            if missing_fields:
                return (False, f"Missing required fields: {', '.join(missing_fields)}")
        
        # Check that caseType is either 'civil' or 'criminal'
        def validate_case_type(obj):
            if 'caseType' in obj and obj['caseType'] not in ['civil', 'criminal']:
                return False
            return True
        
        if isinstance(data, list):
            invalid_items = [idx for idx, item in enumerate(data) if not validate_case_type(item)]
            if invalid_items:
                return (False, f"Items at indices {invalid_items} have invalid 'caseType' values (must be 'civil' or 'criminal')")
        else:
            if not validate_case_type(data):
                return (False, "Field 'caseType' has invalid value (must be 'civil' or 'criminal')")
        
        # If all validations pass, return the validated data
        return (True, result)
        
    except json.JSONDecodeError as e:
        return (False, f"Failed to parse JSON: {str(e)}")
    except Exception as e:
        return (False, f"Validation error: {str(e)}")

#------------------------------------------------------------------#  
######## Initialize tools ##########################################
#------------------------------------------------------------------#
file_read_tool = FileReadTool()
txt_rag_tool = TXTSearchTool()

# Custom helper function to handle JSON file operations
def json_file_writer(filename, content, directory=None, should_append=False):
    """
    Custom function to write or append to JSON files
    
    Args:
        filename (str): Name of the JSON file
        content (str): JSON content to write/append to the file
        directory (str): Directory where the file is located
        should_append (bool): Whether to append to existing file
        
    Returns:
        str: Success message
    """
    try:
        # Handle absolute paths
        if os.path.isabs(filename):
            filepath = filename
        else:
            # Construct the full path
            filepath = os.path.join(directory or os.getcwd(), filename)
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
        # Parse the new content
        try:
            new_data = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON content: {str(e)}")
            return f"Error parsing JSON content: {str(e)}"
        
        # Check if file exists and should append
        file_exists = os.path.isfile(filepath)
        
        if file_exists and should_append:
            # Read existing JSON file
            try:
                with open(filepath, 'r') as existing_file:
                    existing_data = json.load(existing_file)
            except json.JSONDecodeError:
                print("Warning: Existing file not valid JSON, treating as new file")
                existing_data = []
            except Exception as e:
                print(f"Error reading existing JSON file: {str(e)}")
                return f"Error reading existing JSON file: {str(e)}"
            
            # Handle different data types for appending
            if isinstance(existing_data, list):
                if isinstance(new_data, list):
                    # Append list to list
                    existing_data.extend(new_data)
                else:
                    # Append single object to list
                    existing_data.append(new_data)
            else:
                # If existing data is not a list, convert to list and append
                if isinstance(new_data, list):
                    existing_data = [existing_data] + new_data
                else:
                    existing_data = [existing_data, new_data]
            
            data_to_write = existing_data
        else:
            data_to_write = new_data
            
        # Write the data
        try:
            with open(filepath, 'w') as f:
                json.dump(data_to_write, f, indent=2)
            print(f"Successfully wrote JSON to {filepath}")
            return f"Content successfully {'appended to' if should_append else 'written to'} {filepath}"
        except Exception as e:
            print(f"Error writing to file: {str(e)}")
            return f"Error writing to file: {str(e)}"
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return f"An error occurred: {str(e)}"

# Standard file writer tool for JSON and non-JSON files
file_writer_tool = FileWriterTool()

#------------------------------------------------------------------#
################### Creating Agents ###################
#------------------------------------------------------------------#
summarizer_agent = Agent(
  config=agents_config['summarizer_agent'],
  tools=[file_read_tool, txt_rag_tool],
  verbose=True,
  allow_delegation=True,
  respect_context_window=True,
  max_retries=3
)

categorizer_agent = Agent(
  config=agents_config['document_classifier_agent'],
  tools=[file_read_tool, txt_rag_tool],
  verbose=True,
  allow_delegation=True,
  max_retries=3
)

metadata_extractor = Agent(
    config=agents_config['meta_data_creation_agent'],
    tools=[file_read_tool, txt_rag_tool],
    verbose=True,
    allow_delegation=True,
    max_retries=3
)

complience_extractor = Agent(
    config=agents_config['complience_extractor'],
    tools=[file_read_tool, txt_rag_tool],
    verbose=True,
    allow_delegation=True,
    max_retries=3
)

JSON_file_writer = Agent(
    config=agents_config['json_creation_agent'],
    tools=[file_writer_tool, file_read_tool, txt_rag_tool],
    verbose=True,
    allow_delegation=True,
    function_calling_llm="gpt-4o",
    max_retries=3
)

#------------------------------------------------------------------#
################### Creating Tasks ###################
#------------------------------------------------------------------#
summarization_task = Task(
  config=tasks_config['summarize_legal_document'],
  agent=summarizer_agent,
  tools=[file_read_tool, txt_rag_tool],
  async_execution=False,
  max_retries=5
)

categorization_task = Task(
  config=tasks_config['classify_legal_document'],
  agent=categorizer_agent,
  tools=[file_read_tool, txt_rag_tool],
  async_execution=False,
  max_retries=5
)

metadata_extraction_task = Task(
  config=tasks_config['extract_legal_metadata'],
  agent=metadata_extractor,
  tools=[file_read_tool, txt_rag_tool],
  context=[
    summarization_task
  ],
  async_execution=False,
  max_retries=5
)

complience_extraction_task = Task(
  config=tasks_config['extract_legal_compliance'],
  agent=complience_extractor,
  tools=[file_read_tool, txt_rag_tool],
  async_execution=False,
  max_retries=5
)

json_file_writer_task = Task(
  config=tasks_config['generate_legal_json'],
  agent=JSON_file_writer,
  tools=[file_writer_tool, file_read_tool, txt_rag_tool],
  context=[
    summarization_task,
    categorization_task,
    metadata_extraction_task,
    complience_extraction_task
  ],
  input_variables={
    "output_file_path": "{output_file_path}",
    "file_exists": "{file_exists}",
    "should_append": "{should_append}"
  },
  max_retries=5
)

#------------------------------------------------------------------#
################### Creating Crew ###################
#------------------------------------------------------------------#
crew = Crew(
  agents=[
    summarizer_agent,
    categorizer_agent,
    metadata_extractor,
    complience_extractor,
    JSON_file_writer
  ],
  tasks=[
    summarization_task,
    categorization_task,
    metadata_extraction_task,
    complience_extraction_task,
    json_file_writer_task
  ],
  verbose=True,
  process=Process.sequential,
  output_log_file='output_log.txt',
  planning=True,
  planning_llm="gpt-4o",
  max_rpm=10
)

#------------------------------------------------------------------#
################### PDF to Text Conversion ###################
#------------------------------------------------------------------#
def pdf_to_text(pdf_path: str, temp_dir: str) -> str:
    """
    Convert PDF to text and save in temp directory
    
    Args:
        pdf_path (str): Path to the PDF file
        temp_dir (str): Path to temporary directory
        
    Returns:
        str: Path to the created text file
    """
    try:
        # Create text file path
        text_file_path = Path(temp_dir) / f"{Path(pdf_path).stem}.txt"
        
        # Open and read PDF
        with open(pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text_content = ""
            
            # Extract text from each page
            for page in pdf_reader.pages:
                text_content += page.extract_text()
        
        # Write text content to file
        with open(text_file_path, 'w', encoding='utf-8') as text_file:
            text_file.write(text_content)
            
        return str(text_file_path)
    
    except Exception as e:
        raise Exception(f"Error converting PDF to text: {str(e)}")

def check_and_prepare_json(output_file_path: str) -> dict:
    """
    Check if the output JSON file exists and prepare parameters for appending
    
    Args:
        output_file_path (str): Path to the output JSON file
        
    Returns:
        dict: Parameters for file writing with appropriate append flag
    """
    file_exists = os.path.isfile(output_file_path)
    return {
        "output_file_path": output_file_path,
        "file_exists": file_exists,
        "should_append": file_exists
    }

def process_legal_document(pdf_file_path: str):
    """
    Process a legal document through the CrewAI pipeline
    
    Args:
        pdf_file_path (str): Path to the PDF file
    """
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    try:
        # Convert PDF to text
        text_file_path = pdf_to_text(pdf_file_path, temp_dir)
        
        # Set output file path - use absolute path
        output_file_path = os.path.abspath("output.json")
        print(f"Will save output to: {output_file_path}")
        
        # Check if output file exists and prepare parameters
        json_params = check_and_prepare_json(output_file_path)
        
        # Debug inputs
        print(f"Input parameters:")
        print(f"  - input_file_path: {text_file_path}")
        print(f"  - output_file_path: {output_file_path}")
        print(f"  - file_exists: {json_params['file_exists']}")
        print(f"  - should_append: {json_params['should_append']}")
        
        # First, try direct file writing to see if permissions are correct
        print("Testing direct file writing...")
        try:
            with open(output_file_path, 'w') as f:
                f.write('{\"test\": \"data\"}')
            print(f"Direct file writing test succeeded to {output_file_path}")
            # Read back to verify
            with open(output_file_path, 'r') as f:
                print(f"File content after direct write: {f.read()}")
            
            # Delete the test file after testing to prevent the dummy data from being inserted
            os.remove(output_file_path)
            print(f"Test file removed successfully")
        except Exception as e:
            print(f"Direct file writing test failed: {str(e)}")
        
        # Prepare input for crew
        inputs = {
            "input_file_path": text_file_path,
            "input_pdf_path": pdf_file_path,
            "output_file_path": output_file_path,
            "file_exists": json_params["file_exists"],
            "should_append": json_params["should_append"]
        }
        
        # Execute crew tasks
        print("Starting crew tasks execution...")
        result = crew.kickoff(inputs=inputs)
        print(f"Crew execution completed. Result type: {type(result)}")
        
        # Handle the CrewOutput object correctly
        print(f"Result type: {type(result)}")
        print(f"Result: {str(result)}")
        
        return result
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir)

#------------------------------------------------------------------#
################### Main Execution ###################
#------------------------------------------------------------------#
if __name__ == "__main__":
    pdf_file_path = "scrapers/appeal-court/2024/02/ca_182_2019_pdf.pdf"
    result = process_legal_document(pdf_file_path)
    print("Processing completed:", result)
