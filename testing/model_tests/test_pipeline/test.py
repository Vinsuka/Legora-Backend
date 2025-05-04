from crewai import Agent, Crew, Task, Process
from crewai.project import CrewBase, agent, task, crew, before_kickoff, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
import os
from dotenv import load_dotenv
from tools.pinecone_rag_tool import DocumentSearchTool

# Load environment variables
load_dotenv()

@CrewBase
class ResearchCrew:
    """A crew that performs research using a document knowledge base."""

    agents: List[BaseAgent]
    tasks: List[Task]

    def __init__(self):
        # Initialize document search tools for both namespaces
        self.appeal_search_tool = DocumentSearchTool(
            index_name="judgments-index",
            environment="custom-embeddings",  # Update with your Pinecone environment
            top_k=5,
            similarity_threshold=0.7,
            namespace="appeal_court"
        )
        self.supreme_search_tool = DocumentSearchTool(
            index_name="judgments-index",
            environment="custom-embeddings",  # Update with your Pinecone environment
            top_k=5,
            similarity_threshold=0.7,
            namespace="supreme_court"
        )

    @before_kickoff
    def prepare_inputs(self, inputs):
        if not inputs:
            inputs = {}
        inputs['clause'] = inputs.get('clause', "Artificial Intelligence")
        return inputs

    @agent
    def appeal_researcher(self) -> Agent:
        return Agent(
            role="Appeal Court Research Analyst",
            goal="Find and analyze relevant information from Appeal Court judgments",
            backstory="You are an expert research analyst with access to Appeal Court documents.",
            tools=[self.appeal_search_tool],
            llm="gpt-4o-mini",
            verbose=True
        )

    @agent
    def supreme_researcher(self) -> Agent:
        return Agent(
            role="Supreme Court Research Analyst",
            goal="Find and analyze relevant information from Supreme Court judgments",
            backstory="You are an expert research analyst with access to Supreme Court documents.",
            tools=[self.supreme_search_tool],
            llm="gpt-4o-mini",
            verbose=True
        )

    @agent
    def researcher(self) -> Agent:
        return Agent(
            role="General Research Analyst",
            goal="Find and analyze relevant information from all judgments",
            backstory="You are an expert research analyst with access to all court documents.",
            tools=[self.appeal_search_tool, self.supreme_search_tool],
            llm="gpt-4o-mini",
            verbose=True
        )

    @agent
    def reporting_analyst(self) -> Agent:
        return Agent(
            role="Reporting Analyst",
            goal="Create detailed reports based on research findings",
            backstory="You are a meticulous analyst who creates clear and comprehensive reports from research data.",
            tools=[self.appeal_search_tool, self.supreme_search_tool],  # Add tools if needed
            llm="gpt-4o-mini",
            verbose=True
        )

    @task
    def appeal_research_task(self) -> Task:
        return Task(
            description="""Research the given clause using the Appeal Court document search tool.
            1. Search for relevant information about {clause}
            2. Analyze the search results and identify key insights
            3. Synthesize the information into a coherent response
            4. Include relevance scores and citations in your analysis""",
            expected_output="A detailed analysis with citations and references to the Appeal Court knowledge base.",
            agent=self.appeal_researcher()
        )

    @task
    def supreme_research_task(self) -> Task:
        return Task(
            description="""Research the given clause using the Supreme Court document search tool.
            1. Search for relevant information about {clause}
            2. Analyze the search results and identify key insights
            3. Synthesize the information into a coherent response
            4. Include relevance scores and citations in your analysis""",
            expected_output="A detailed analysis with citations and references to the Supreme Court knowledge base.",
            agent=self.supreme_researcher()
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.appeal_researcher(), self.supreme_researcher()],
            tasks=[self.appeal_research_task(), self.supreme_research_task()],
            process=Process.sequential,
            verbose=True,
        )

if __name__ == "__main__": 
    # Create a .env file with your API keys before running
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("PINECONE_API_KEY"):
        print("Please set OPENAI_API_KEY and PINECONE_API_KEY in your .env file")
        exit(1)
    
    crew = ResearchCrew().crew()
    output = crew.kickoff(inputs={"clause": "The learned Magistrate of Matara ordered on 11.12.2014 to implement certain practical recommendations by the Central Environmental Authority for the company premises within a time period of two months."})
    print(output)
