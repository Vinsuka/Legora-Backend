from crewai import Agent, Task, Crew
from supreme_court_tool import SupremeCourtSearchTool
import os

# Initialize the Supreme Court search tool
supreme_court_tool = SupremeCourtSearchTool(
    pinecone_api_key=os.getenv("PINECONE_API_KEY"),
    environment=os.getenv("PINECONE_ENVIRONMENT"),
    model_dir=os.getenv("LOCAL_MODEL_DIR", ".")  # Path to your local embedding model
)

# Create specialized agents
legal_researcher = Agent(
    role='Legal Research Specialist',
    goal='Conduct thorough research on Supreme Court judgements and create comprehensive legal analysis',
    backstory="""You are an experienced legal researcher with expertise in analyzing Supreme Court judgements. 
    Your strength lies in finding relevant case law and extracting key legal principles.""",
    verbose=True,
    allow_delegation=True,
    tools=[supreme_court_tool],
    llm="gpt-4o-mini"
)

legal_analyst = Agent(
    role='Legal Analyst',
    goal='Analyze and synthesize legal research findings into clear, actionable insights',
    backstory="""You are a skilled legal analyst with years of experience in interpreting Supreme Court decisions
    and explaining their implications in clear, concise language.""",
    verbose=True,
    allow_delegation=True,
    llm="gpt-4o-mini"
)

# Define tasks
research_task = Task(
    description="""
    Research Supreme Court judgements related to the following topics:
    1. Constitutional rights
    2. Recent landmark decisions in the last 2 years
    3. Precedent-setting cases
    
    For each topic:
    - Find relevant cases
    - Extract key principles and holdings
    - Note any dissenting opinions
    - Identify trends in judicial reasoning
    
    Compile your findings in a structured format.
    """,
    expected_output="A structured report with key findings, implications, and trends in Supreme Court judgements.",
    agent=legal_researcher
)

analysis_task = Task(
    description="""
    Using the research provided:
    1. Synthesize the key findings into a comprehensive report
    2. Identify common themes and evolving legal principles
    3. Analyze the potential implications for future cases
    4. Highlight any shifts in judicial interpretation
    
    Create a detailed report that would be valuable for legal professionals.
    """,
    expected_output="A comprehensive report with key findings, implications, and trends in Supreme Court judgements.",
    agent=legal_analyst
)

# Create and run the crew
crew = Crew(
    agents=[legal_researcher, legal_analyst],
    tasks=[research_task, analysis_task],
    verbose=2
)

def test_crew_execution():
    result = crew.kickoff()
    assert result is not None
    print("\nLegal Research and Analysis Report:")
    print("-" * 80)
    print(result)

if __name__ == "__main__":
    test_crew_execution()
