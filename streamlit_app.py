import streamlit as st
import requests
import os
import time
import datetime
import json
from pathlib import Path

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("uploaded_pdfs")
UPLOAD_DIR.mkdir(exist_ok=True)

# API URL
API_URL = "http://localhost:8000"

st.title("Legal Document Analysis")
st.write("Upload a PDF document for legal analysis using CrewAI")

# Session state for tracking jobs and documents
if "jobs" not in st.session_state:
    st.session_state.jobs = {}
if "documents" not in st.session_state:
    st.session_state.documents = {}

# Side panel for seeing job history and documents
with st.sidebar:
    st.header("Navigation")
    tab1, tab2 = st.tabs(["Job History", "Documents"])
    
    with tab1:
        if st.button("Refresh Job List"):
            try:
                response = requests.get(f"{API_URL}/jobs")
                if response.status_code == 200:
                    jobs_data = response.json()["jobs"]
                    for job in jobs_data:
                        st.session_state.jobs[job["session_id"]] = job
            except Exception as e:
                st.error(f"Error fetching jobs: {str(e)}")
        
        # Check log files button
        if st.button("Check Log Files"):
            try:
                with st.spinner("Checking log files..."):
                    response = requests.get(f"{API_URL}/check-log-file")
                    if response.status_code == 200:
                        log_data = response.json()
                        st.write("### Log File Status")
                        
                        # Show current directory
                        st.write(f"**Current directory:** {log_data['current_directory']}")
                        
                        # Show found log files
                        for file_type, file_paths in log_data['log_files_found'].items():
                            if file_paths:
                                st.write(f"**{file_type}** found at:")
                                for path in file_paths:
                                    st.write(f"- {path}")
                            else:
                                st.write(f"**{file_type}** not found")
                        
                        # Show log contents in expandable sections
                        if log_data['log_contents']:
                            st.write("### Log Contents")
                            for file_path, content in log_data['log_contents'].items():
                                with st.expander(f"Contents of {file_path}"):
                                    st.code(content)
                    else:
                        st.error(f"Error checking log files: {response.status_code} - {response.text}")
            except Exception as e:
                st.error(f"Error checking log files: {str(e)}")
        
        # Show job history
        for session_id, job in st.session_state.jobs.items():
            with st.expander(f"Job: {session_id[:8]} - {job.get('status', 'unknown')}"):
                st.write(f"**User:** {job.get('user_name', 'unknown')}")
                st.write(f"**Status:** {job.get('status', 'unknown')}")
                st.write(f"**Started:** {job.get('trigger_start_time', 'unknown')}")
                if "finish_time" in job and job["finish_time"]:
                    st.write(f"**Finished:** {job['finish_time']}")
                if "agentops_url" in job and job["agentops_url"]:
                    st.write(f"**AgentOps URL:** {job['agentops_url']}")
                
                # Show logs and report if available
                if "log_file" in job and job["log_file"]:
                    with st.expander("View Logs"):
                        st.code(job["log_file"])
                
                if "report" in job and job["report"]:
                    with st.expander("View Report"):
                        st.markdown(job["report"])
    
    with tab2:
        if st.button("Refresh Document List"):
            try:
                response = requests.get(f"{API_URL}/documents")
                if response.status_code == 200:
                    documents_data = response.json()["documents"]
                    for doc in documents_data:
                        st.session_state.documents[doc["document_id"]] = doc
            except Exception as e:
                st.error(f"Error fetching documents: {str(e)}")
        
        # Show document list
        for doc_id, doc in st.session_state.documents.items():
            with st.expander(f"Document: {doc['filename']}"):
                st.write(f"**Uploaded by:** {doc.get('user_name', 'unknown')}")
                st.write(f"**Upload time:** {doc.get('upload_time', 'unknown')}")
                st.write(f"**Document ID:** {doc_id}")
                
                # Show associated sessions
                if "associated_sessions" in doc and doc["associated_sessions"]:
                    st.write("**Associated Analysis Sessions:**")
                    for session_id in doc["associated_sessions"]:
                        short_id = session_id[:8]
                        status = "unknown"
                        if session_id in st.session_state.jobs:
                            status = st.session_state.jobs[session_id].get("status", "unknown")
                        st.write(f"- Session {short_id} - Status: {status}")

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    # File upload widget
    uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"])
    
    user_name = st.text_input("Your username", value="testuser")
    
    if uploaded_file is not None:
        # Save the uploaded file
        file_path = UPLOAD_DIR / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"File saved: {file_path}")
        
        # Submit button
        if st.button("Analyze Document"):
            try:
                with st.spinner("Submitting document for analysis..."):
                    # Get current date for report_date
                    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                    
                    response = requests.post(
                        f"{API_URL}/analyze-document",
                        json={
                            "user_name": user_name,
                            "pdf_path": str(file_path)
                        }
                    )
                    
                    if response.status_code == 200:
                        job_data = response.json()
                        st.session_state.jobs[job_data["session_id"]] = job_data
                        
                        st.success(f"Job submitted successfully: {job_data['session_id']}")
                        st.write(f"Status: {job_data['status']}")
                        st.write(f"Expected completion: {job_data['expected_finish_time']}")
                        
                        # Start polling for status updates
                        with st.spinner("Processing document..."):
                            # Poll for 5 seconds to show it's working
                            time.sleep(5)
                            st.write("Document processing has started. Check the job in the sidebar for updates.")
                    else:
                        st.error(f"Error: {response.status_code} - {response.text}")
            except Exception as e:
                st.error(f"Error submitting document: {str(e)}")

with col2:
    st.subheader("About")
    st.write("""
    This app analyzes legal documents using the CrewAI framework.
    
    The process includes:
    1. Document summarization
    2. Clause extraction and validation
    3. Relevant legal precedent search
    4. Compliance evaluation
    5. Final report generation
    
    The analysis may take several minutes to complete.
    """)
    
    st.subheader("Job Status")
    st.write("""
    - **Queued**: Document is waiting to be processed
    - **Running**: Analysis is in progress
    - **Success**: Analysis completed successfully
    - **Failed**: Analysis encountered an error
    
    View detailed logs and reports in the Job History panel.
    """)
    
    st.subheader("Documents")
    st.write("""
    All uploaded documents are stored and can be viewed in the Documents tab.
    Each document can have multiple analysis sessions associated with it.
    """) 