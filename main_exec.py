import datetime
from crewai import Agent, Crew, Task
import yaml
from crewai_tools import PDFSearchTool
from pydantic import BaseModel, Field
from typing import Dict
import os
import signal
import sys
from openai import OpenAI
from dotenv import load_dotenv
from crewai import Agent, Task
from qdrant_client import QdrantClient
from crewai_tools import QdrantVectorSearchTool
import agentops

# Add signal handler for graceful termination
def signal_handler(sig, frame):
    print('\nCleaning up and exiting...')
    if 'session' in globals():
        try:
            agentops.end_session()
            print("AgentOps session ended gracefully")
        except Exception as e:
            print(f"Error ending AgentOps session: {e}")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Load environment variables first
load_dotenv()

# Set OpenAI model explicitly to GPT-4o
os.environ['OPENAI_MODEL_NAME'] = 'gpt-4o'

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize AgentOps with more complete configuration
try:
    agentops.init(
        api_key=os.getenv("AGENTOPS_API_KEY"),
        fail_safe=True,
        default_tags=["legal_compliance_check", "employment_agreement", "gpt-4o"],
        log_level="INFO",  # Set to INFO to see more detailed logs including URLs
        endpoint="https://api.agentops.ai",  # Explicitly set the endpoint
    )

    # Output the dashboard URL
    print("AgentOps Dashboard URL: https://app.agentops.ai")

    # Start a session and capture the session object
    session = agentops.start_session(tags=["execution_run"])

    # Extract the trace ID from the span object, which provides a better identifier
    session_id = "unknown"
    try:
        if hasattr(session, 'span') and hasattr(session.span, 'context') and hasattr(session.span.context, 'trace_id'):
            # Convert the hex trace ID to a readable string
            trace_id_hex = format(session.span.context.trace_id, 'x')
            session_id = trace_id_hex
        elif hasattr(session, 'id'):
            session_id = session.id
        elif hasattr(session, 'session_id'):
            session_id = session.session_id
    except Exception as e:
        print(f"Info: Could not extract detailed session ID: {str(e)}")

    print(f"AgentOps session started - Session ID: {session_id}")
    print(f"Check your session at: https://app.agentops.ai/sessions")
except Exception as e:
    print(f"Warning: AgentOps initialization failed: {str(e)}")
    print("Continuing without AgentOps telemetry...")
    session = None
    session_id = None

# Clean up and simplify - remove all debug printing
files = {
    'agents': 'config/agents.yaml',
    'tasks': 'config/tasks.yaml'
}

configs = {}
for config_type, file_path in files.items():
    with open(file_path, 'r') as file:
        configs[config_type] = yaml.safe_load(file)

agents_config = configs['agents']
tasks_config = configs['tasks']

# ---------------------- Define Tools ------------------------
qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

def get_openai_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

supreme_court_collection_name = "supreme_court_judgments"
appeal_court_collection_name = "appeal_court_judgments"
law_knowledge_base_collection_name = "legal-docs"

# Default PDF path - can be overridden
pdf_path = "test_pdf/Nathaniel - Employment Agreement - Standord (1).pdf"

pdf_search_tool = PDFSearchTool()

qdrant_supreme_court_tool = QdrantVectorSearchTool(
    qdrant_url=os.getenv("QDRANT_URL"),
    qdrant_api_key=os.getenv("QDRANT_API_KEY"),
    collection_name=supreme_court_collection_name,
    limit=3,
    score_threshold=0.35
)

qdrant_appeal_court_tool = QdrantVectorSearchTool(
    qdrant_url=os.getenv("QDRANT_URL"),
    qdrant_api_key=os.getenv("QDRANT_API_KEY"),
    collection_name=appeal_court_collection_name,
    limit=3,
    score_threshold=0.35
)

law_knowledge_base = QdrantVectorSearchTool(
    qdrant_url=os.getenv("QDRANT_URL"),
    qdrant_api_key=os.getenv("QDRANT_API_KEY"),
    collection_name=law_knowledge_base_collection_name,
    limit=3,
    score_threshold=0.35
)

# ---------------------- Define Pydantic Model for JSON Output ------------------------
class ClauseJSONFile(BaseModel):
    """
    Pydantic model for structured output of legal clauses extraction.
    Keys are the legal clauses, values are the legal reasoning for extraction.
    """
    clauses: Dict[str, str] = Field(
        description="Dictionary where keys are legal clause names and values are legal reasoning"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "clauses": {
                    "legal clause 01": "Legal reasoning behind extracting that from the agreement",
                    "legal clause 02": "Legal reasoning behind extracting that from the agreement"
                }
            }
        }

# ---------------------- Define Agents ------------------------
agreement_summarizer = Agent(
    config=agents_config['agreement_summarizer'],
    tools=[pdf_search_tool],
    verbose=True,
    respect_context_window=True,
    llm="gpt-4o-mini",
    max_retry_limit=3
)

agreement_clause_extractor = Agent(
    config=agents_config['agreement_clause_extractor'],
    tools=[pdf_search_tool],
    verbose=True,
    llm="gpt-4o-mini",
    max_retry_limit=3
)

legal_clause_validator = Agent(
    config=agents_config['legal_clause_validator'],
    tools=[pdf_search_tool],
    verbose=True,
    allow_delegation=True,
    llm="gpt-4o-mini",
    max_retry_limit=3
)

create_vector_query_agent = Agent(
    config=agents_config['create_vector_query_agent'],
    verbose=True,
    allow_delegation=True,
    llm="gpt-4o-mini",
    max_retry_limit=3
)

supreme_court_judgements_extractor = Agent(
    config=agents_config['supreme_court_judgements_extractor'],
    tools=[qdrant_supreme_court_tool],
    verbose=True,
    llm="gpt-4o-mini",
    max_retry_limit=3
)

appeal_court_judgements_extractor = Agent(
    config=agents_config['appeal_court_judgements_extractor'],
    tools=[qdrant_appeal_court_tool],
    verbose=True,
    llm="gpt-4o-mini",
    max_retry_limit=3
)

law_knowledge_base_extractor = Agent(
    config=agents_config['law_knowledge_base_extractor'],
    tools=[law_knowledge_base],
    verbose=True,
    llm="gpt-4o-mini",
    max_retry_limit=3
)

extracted_data_validator = Agent(
    config=agents_config['extracted_data_validator'],
    verbose=True,
    allow_delegation=True,
    llm="gpt-4o-mini",
    max_retry_limit=3
)

final_compliance_reporte_creation_agent = Agent(
    config=agents_config['final_compliance_reporte_creation_agent'],
    verbose=True,
    llm="gpt-4o-mini",
    max_retry_limit=3
)

# ---------------------- Define Tasks ------------------------
agreement_summarizer_task = Task(
    config=tasks_config['agreement_summarizer_task'],
    agent=agreement_summarizer,
    tools=[pdf_search_tool],
    max_retries=5
)

agreement_clause_extractor_task = Task(
    config=tasks_config['agreement_clause_extractor_task'],
    agent=agreement_clause_extractor,
    tools=[pdf_search_tool],
    output_json=ClauseJSONFile,
    max_retries=5
)

legal_clause_validator_task = Task(
    config=tasks_config['legal_clause_validator_task'],
    agent=legal_clause_validator,
    tools=[pdf_search_tool],
    retry_count=3,
    max_retries=5
)

create_vector_query_task = Task(
    config=tasks_config['create_vector_query_task'],
    agent=create_vector_query_agent,
    context=[
        agreement_summarizer_task
    ],
    max_retries=5
)

supreme_court_judgements_extractor_task = Task(
    config=tasks_config['supreme_court_judgements_extractor_task'],
    agent=supreme_court_judgements_extractor,
    tools=[qdrant_supreme_court_tool],
    context=[
        create_vector_query_task
    ],
    max_retries=5
)

appeal_court_judgements_extractor_task = Task(
    config=tasks_config['appeal_court_judgements_extractor_task'],
    agent=appeal_court_judgements_extractor,
    tools=[qdrant_appeal_court_tool],
    context=[
        create_vector_query_task
    ],
    max_retries=5
)

law_knowledge_base_extractor_task = Task(
    config=tasks_config['law_knowledge_base_extractor_task'],
    agent=law_knowledge_base_extractor,
    tools=[law_knowledge_base],
    context=[
        create_vector_query_task
    ],
    max_retries=5
)

extracted_data_validator_task = Task(
    config=tasks_config['extracted_data_validator_task'],
    agent=extracted_data_validator,
    context=[
        supreme_court_judgements_extractor_task,
        appeal_court_judgements_extractor_task,
        law_knowledge_base_extractor_task
    ],
    max_retries=5
)

final_compliance_reporte_creation_task = Task(
    config=tasks_config['final_compliance_reporte_creation_task'],
    agent=final_compliance_reporte_creation_agent,
    context=[
        extracted_data_validator_task,
        supreme_court_judgements_extractor_task,
        appeal_court_judgements_extractor_task,
        law_knowledge_base_extractor_task
    ],
    output_file="final_compliance_reporte.md",
    max_retries=5
)

# ---------------------- Define Crew ------------------------
crew = Crew(
    agents=[
        agreement_summarizer,
        agreement_clause_extractor,
        legal_clause_validator,
        create_vector_query_agent,
        supreme_court_judgements_extractor,
        appeal_court_judgements_extractor,
        law_knowledge_base_extractor,
        extracted_data_validator,
        final_compliance_reporte_creation_agent
    ],
    tasks=[
        agreement_summarizer_task,
        agreement_clause_extractor_task,
        legal_clause_validator_task,
        create_vector_query_task,
        supreme_court_judgements_extractor_task,
        appeal_court_judgements_extractor_task,
        law_knowledge_base_extractor_task,
        extracted_data_validator_task,
        final_compliance_reporte_creation_task
    ],
    verbose=True,
    output_log_file="main_exec",
    planning_llm="gpt-4o",
)

# Function to run the crew pipeline (instead of running it automatically on import)
def run_crew_pipeline(input_file_path=None):
    """
    Run the CrewAI pipeline with the specified PDF file.
    
    Args:
        input_file_path (str): Path to the PDF file to analyze. If None, uses the default.
    
    Returns:
        dict: Results from the crew execution
    """
    global pdf_path
    
    # Update the PDF path if provided
    if input_file_path:
        pdf_path = input_file_path
    
    print(f"Starting CrewAI pipeline on file: {pdf_path}")
    
    try:

        result = crew.kickoff(
            inputs={
                "input_file_path": pdf_path,
                "report_date": datetime.datetime.now().strftime("%Y-%m-%d")
            }
        )
        return result
    finally:
        # Ensure session is ended properly even if an error occurs
        if session:
            try:
                print(f"Ending AgentOps session with ID: {session_id}")
                # Use the standard approach to end the session first
                agentops.end_session(session)
                print("AgentOps session ended successfully")
            except Exception as e:
                print(f"Warning: Failed to end AgentOps session: {str(e)}")
                # If the above fails, try ending without parameters which works
                # in most cases as it finds the currently active session
                try:
                    agentops.end_session()
                    print("Session ended with default handler")
                except Exception:
                    pass
            print(f"Visit https://app.agentops.ai/sessions to view your sessions")

# Only run if this file is executed directly (not when imported)
if __name__ == "__main__":
    run_crew_pipeline()
