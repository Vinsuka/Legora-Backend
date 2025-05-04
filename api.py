from fastapi import FastAPI, BackgroundTasks, HTTPException
import uvicorn
from pydantic import BaseModel
import asyncio
import datetime
import uuid
import os
import traceback
import json
import io
import logging
import sys
import glob
from typing import Dict, Any, Optional, List, Tuple
import pymongo
from dotenv import load_dotenv

# Import the main exec module
import main_exec

# Load environment variables
load_dotenv()

app = FastAPI(title="Legal Document Analysis API")

# MongoDB setup
MONGO_USERNAME = os.getenv("username", "dunith20200471")
MONGO_PASSWORD = os.getenv("Password", "cveJrDEdS7bYeFwk")
MONGO_URI = os.getenv("MONGO_URI", f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@fypcust0.abd2d.mongodb.net/?retryWrites=true&w=majority&appName=fypcust0")
DB_NAME = os.getenv("MONGO_DB", "legal_analysis")

# Connect to MongoDB
client = pymongo.MongoClient(MONGO_URI)
db = client[DB_NAME]
sessions_collection = db["sessions"]
documents_collection = db["legal_documents"]  # New collection for document data

# Initialize collections if they don't exist
if "sessions" not in db.list_collection_names():
    db.create_collection("sessions")
    print("Created 'sessions' collection")

if "legal_documents" not in db.list_collection_names():
    db.create_collection("legal_documents")
    print("Created 'legal_documents' collection")

# Store active jobs
active_jobs: Dict[str, Dict[str, Any]] = {}

class DocumentRequest(BaseModel):
    user_name: str
    pdf_path: str

class JobResponse(BaseModel):
    session_id: str
    status: str
    agentops_url: Optional[str] = None
    trigger_start_time: str
    expected_finish_time: str
    message: str = ""

# Function to find a file in the current directory and subdirectories
def find_file(filename: str, max_depth: int = 2) -> List[str]:
    """
    Searches for a file in the current directory and subdirectories up to max_depth.
    Returns a list of found file paths.
    """
    found_files = []
    
    # Check current directory
    if os.path.exists(filename):
        found_files.append(filename)
    
    # Check subdirectories
    if max_depth > 0:
        for pattern in [f"*/{filename}", f"*/*/{filename}"]:
            found_files.extend(glob.glob(pattern))
    
    return found_files

# Function to read log file with proper error handling
def read_log_file(filepath: str) -> Tuple[str, bool]:
    """
    Reads a log file and returns its contents and a success flag.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return content, True
    except Exception as e:
        return f"Error reading {filepath}: {str(e)}", False

async def run_crew_pipeline(session_id: str, user_name: str, pdf_path: str):
    """Run the CrewAI pipeline in the background."""
    try:
        # Set up logging to capture CrewAI logs
        log_capture = io.StringIO()
        logger = logging.getLogger("crew_pipeline")
        logger.setLevel(logging.INFO)
        
        # Add handler to capture logs in the string buffer
        string_handler = logging.StreamHandler(log_capture)
        string_handler.setLevel(logging.INFO)
        logger.addHandler(string_handler)
        
        # Add handler to also show logs in terminal
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
        
        # Update job status to running
        active_jobs[session_id]["status"] = "running"
        active_jobs[session_id]["message"] = "CrewAI pipeline execution started"
        
        logger.info(f"Starting CrewAI pipeline execution for session {session_id}")
        
        # Store document metadata
        filename = os.path.basename(pdf_path)
        document_id = str(uuid.uuid4())
        document_data = {
            "document_id": document_id,
            "filename": filename,
            "upload_time": datetime.datetime.now().isoformat(),
            "user_name": user_name,
            "file_path": pdf_path,
            "associated_sessions": [session_id]
        }
        documents_collection.insert_one(document_data)
        
        # Update the active job with document_id
        active_jobs[session_id]["document_id"] = document_id
        
        # Run the CrewAI pipeline
        main_exec.pdf_path = pdf_path  # Set the PDF path for the execution
        
        # Run the crew
        crew_session = None
        try:
            crew = main_exec.crew  # Get the crew instance
            
            # Get current date for report_date
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            
            # Include report_date in the inputs
            result = crew.kickoff(inputs={
                "input_file_path": pdf_path,
                "report_date": current_date
            })
            
            # Try to get the AgentOps URL
            crew_session = main_exec.session
            agentops_url = ""
            if crew_session and hasattr(crew_session, "span") and hasattr(crew_session.span, "context"):
                trace_id = format(crew_session.span.context.trace_id, 'x')
                agentops_url = f"https://app.agentops.ai/sessions/{trace_id}"
            elif hasattr(main_exec, "session_id") and main_exec.session_id:
                agentops_url = f"https://app.agentops.ai/sessions/{main_exec.session_id}"
            
            active_jobs[session_id]["agentops_url"] = agentops_url
            active_jobs[session_id]["status"] = "success"
            active_jobs[session_id]["message"] = "CrewAI pipeline completed successfully"
            
            # Read the report file
            report_content = ""
            report_files = find_file("final_compliance_reporte.md")
            if report_files:
                report_content, _ = read_log_file(report_files[0])
            
            # Read the log file content
            log_content = log_capture.getvalue()
            
            # Look for main_exec.txt file and read its entire content
            main_exec_txt_files = find_file("main_exec.txt")
            if main_exec_txt_files:
                main_exec_log_content, success = read_log_file(main_exec_txt_files[0])
                if success:
                    log_content += f"\n\n=== MAIN EXEC LOG (from {main_exec_txt_files[0]}) ===\n\n" + main_exec_log_content
                else:
                    log_content += f"\n\n{main_exec_log_content}"
            
            # Also check for main_exec.log as a fallback
            else:
                main_exec_log_files = find_file("main_exec.log")
                if main_exec_log_files:
                    main_exec_log_content, success = read_log_file(main_exec_log_files[0])
                    if success:
                        log_content += f"\n\n=== MAIN EXEC LOG (from {main_exec_log_files[0]}) ===\n\n" + main_exec_log_content
                    else:
                        log_content += f"\n\n{main_exec_log_content}"
            
            # Save to MongoDB
            sessions_collection.insert_one({
                "user_name": user_name,
                "session_id": session_id,
                "document_id": document_id,
                "log_file": log_content,
                "report": report_content,
                "finish_time": datetime.datetime.now().isoformat(),
                "status": "success",
                "pdf_path": pdf_path,
                "agentops_url": agentops_url
            })
            
        except Exception as e:
            error_msg = f"Error running CrewAI pipeline: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            
            # Read the log file for error cases too
            log_content = log_capture.getvalue()
            
            # Look for main_exec.txt file in error case as well
            main_exec_txt_files = find_file("main_exec.txt")
            if main_exec_txt_files:
                main_exec_log_content, success = read_log_file(main_exec_txt_files[0])
                if success:
                    log_content += f"\n\n=== MAIN EXEC LOG (from {main_exec_txt_files[0]}) ===\n\n" + main_exec_log_content
                else:
                    log_content += f"\n\n{main_exec_log_content}"
            
            active_jobs[session_id]["status"] = "failed"
            active_jobs[session_id]["message"] = error_msg
            
            # Save to MongoDB
            sessions_collection.insert_one({
                "user_name": user_name,
                "session_id": session_id,
                "document_id": document_id,
                "log_file": log_content,
                "report": "",
                "finish_time": datetime.datetime.now().isoformat(),
                "status": "failed",
                "pdf_path": pdf_path,
                "error": error_msg
            })
            
    except Exception as e:
        error_msg = f"Error in run_crew_pipeline: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        active_jobs[session_id]["status"] = "failed"
        active_jobs[session_id]["message"] = error_msg

@app.post("/analyze-document", response_model=JobResponse)
async def analyze_document(request: DocumentRequest, background_tasks: BackgroundTasks):
    """
    Submit a document for analysis using the CrewAI pipeline.
    """
    try:
        # Check if PDF file exists
        if not os.path.exists(request.pdf_path):
            raise HTTPException(status_code=404, detail=f"PDF file not found at {request.pdf_path}")
        
        # Generate a session ID
        session_id = str(uuid.uuid4())
        
        # Calculate timestamps
        start_time = datetime.datetime.now()
        # Estimate 5 minutes for completion
        expected_finish_time = start_time + datetime.timedelta(minutes=5)
        
        # Store job in active jobs
        active_jobs[session_id] = {
            "session_id": session_id,
            "status": "queued",
            "user_name": request.user_name,
            "pdf_path": request.pdf_path,
            "start_time": start_time.isoformat(),
            "expected_finish_time": expected_finish_time.isoformat(),
            "message": "Job queued successfully"
        }
        
        # Run the pipeline in the background
        background_tasks.add_task(
            run_crew_pipeline,
            session_id=session_id,
            user_name=request.user_name,
            pdf_path=request.pdf_path
        )
        
        # Return response
        return JobResponse(
            session_id=session_id,
            status="queued",
            agentops_url="",  # Will be updated when the job starts
            trigger_start_time=start_time.isoformat(),
            expected_finish_time=expected_finish_time.isoformat(),
            message="Document analysis job queued successfully"
        )
        
    except Exception as e:
        error_msg = f"Error submitting document for analysis: {str(e)}"
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/job-status/{session_id}")
async def get_job_status(session_id: str):
    """
    Get the status of a job by session ID.
    """
    # Check active jobs first
    if session_id in active_jobs:
        return active_jobs[session_id]
    
    # Check MongoDB if not in active jobs
    job = sessions_collection.find_one({"session_id": session_id})
    if job:
        # Convert MongoDB document to dict and remove _id
        job_dict = dict(job)
        if "_id" in job_dict:
            del job_dict["_id"]
        return job_dict
    
    raise HTTPException(status_code=404, detail="Job not found")

@app.get("/jobs")
async def get_all_jobs():
    """
    Get all jobs.
    """
    # Get jobs from MongoDB
    mongo_jobs = list(sessions_collection.find({}, {"_id": 0}))
    
    # Combine with active jobs
    all_jobs = {**active_jobs}
    
    # Add MongoDB jobs that aren't in active jobs
    for job in mongo_jobs:
        if job["session_id"] not in all_jobs:
            all_jobs[job["session_id"]] = job
    
    return {"jobs": list(all_jobs.values())}

@app.get("/documents")
async def get_all_documents():
    """
    Get all documents metadata.
    """
    documents = list(documents_collection.find({}, {"_id": 0}))
    return {"documents": documents}

@app.get("/document/{document_id}")
async def get_document(document_id: str):
    """
    Get document metadata by document ID.
    """
    document = documents_collection.find_one({"document_id": document_id}, {"_id": 0})
    if document:
        # Get all sessions related to this document
        sessions = list(sessions_collection.find({"document_id": document_id}, {"_id": 0}))
        document["sessions"] = sessions
        return document
    
    raise HTTPException(status_code=404, detail="Document not found")

@app.get("/check-log-file")
async def check_log_file():
    """
    Utility endpoint to check if the log file exists and return its contents.
    This is helpful for debugging log file issues.
    """
    # Search for log files in current directory and subdirectories
    main_exec_txt_files = find_file("main_exec.txt")
    main_exec_log_files = find_file("main_exec.log")
    report_files = find_file("final_compliance_reporte.md")
    
    log_files = {
        "main_exec.txt": main_exec_txt_files,
        "main_exec.log": main_exec_log_files,
        "final_compliance_reporte.md": report_files
    }
    
    log_contents = {}
    
    # Try to read main_exec.txt files
    for file_path in main_exec_txt_files:
        content, _ = read_log_file(file_path)
        log_contents[file_path] = content
    
    # Try to read main_exec.log files
    for file_path in main_exec_log_files:
        content, _ = read_log_file(file_path)
        log_contents[file_path] = content
    
    # Try to read final_compliance_reporte.md files
    for file_path in report_files:
        content, _ = read_log_file(file_path)
        log_contents[file_path] = content
    
    return {
        "log_files_found": log_files,
        "current_directory": os.getcwd(),
        "directory_contents": os.listdir(),
        "log_contents": log_contents
    }

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True) 








