import requests
from bs4 import BeautifulSoup
import os
import json
import time

# Step 1: Load JSON file and parse page IDs with year and month
json_file_path = 'supreme_court_run.json'
output_dir = 'supreme-court'

with open(json_file_path, 'r') as file:
    pages = json.load(file)

# Define headers for requests
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.183 Safari/537.36"
}

max_retries = 5
downloaded_files = []

# Step 2: Iterate over each page_id in the JSON data
for page in pages:
    page_id = page["page_id"]
    year = page["year"]
    month = page["month"]

    # Construct the URL for the current page
    url = f"https://supremecourt.lk/?page_id={page_id}"
    print(f"Processing URL: {url} for year {year}, month {month}")

    # Step 3: Send a GET request with retry mechanism
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}: Sending request to {url}")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            print("Request successful")
            break
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)  # Wait for 5 seconds before retrying
            else:
                print("Max retries exceeded. Skipping this page.")
                continue  # Move to the next page if max retries exceeded

    # Step 4: Parse the HTML content with BeautifulSoup
    print("Parsing HTML content")
    soup = BeautifulSoup(response.text, 'html.parser')

    # Step 5: Locate the table and rows
    print("Locating the table")
    table = soup.find("table")
    if table is None:
        print("Table not found. Skipping this page.")
        continue

    rows = table.find("tbody").find_all("tr")

    # Step 6: Process each row and download all PDFs
    for row in rows:
        columns = row.find_all("td")
        if len(columns) < 3:
            continue  # Skip rows without enough columns

        # Look for an <a> tag with href in the last column
        pdf_link = columns[-1].find("a", href=True)
        if pdf_link:
            relative_url = pdf_link['href']
            # Construct the full PDF URL from the relative path
            pdf_url = f"https://supremecourt.lk{relative_url}"
            print(f"Found PDF link: {pdf_url}")

            # Extract filename from the doc_id parameter
            try:
                filename_param = relative_url.split('filename=')[-1]
                pdf_name = filename_param.strip()
                print(f"PDF filename: {pdf_name}")
            except IndexError:
                print(f"Could not extract filename from URL: {relative_url}")
                continue

            # Define path based on year and month
            pdf_output_dir = os.path.join(output_dir, str(year), f"{month:02d}")
            os.makedirs(pdf_output_dir, exist_ok=True)
            pdf_path = os.path.join(pdf_output_dir, pdf_name)

            # Step 7: Download the PDF
            try:
                print(f"Downloading PDF from {pdf_url}")
                pdf_response = requests.get(pdf_url)
                pdf_response.raise_for_status()
                
                # Save PDF
                with open(pdf_path, "wb") as pdf_file:
                    pdf_file.write(pdf_response.content)
                    
                downloaded_files.append(pdf_path)
                print(f"Downloaded: {pdf_path}")
                time.sleep(1) 
            except requests.exceptions.RequestException as e:
                print(f"Failed to download {pdf_url}: {e}")

print(f"Downloaded files: {downloaded_files}")
