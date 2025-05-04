import requests
from bs4 import BeautifulSoup
import os
import json
import time

# Step 1: Load JSON file and parse page IDs with year and month
json_file_path = 'appeal_court_run.json'
output_dir = 'appeal-court'

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
    url = f"https://courtofappeal.lk/?page_id={page_id}"
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

        # Locate the button with 'melsta-name' attribute in the last column
        button = columns[-1].find("button", {"melsta-name": True})
        if button:
            melsta_name = button['melsta-name']
            print(f"Found button with melsta-name: {melsta_name}")

            # Format the file name to match the URL pattern
            formatted_name = melsta_name.lower().replace(" ", "_").replace("-", "_").replace(".", "_").replace("(", "").replace(")", "")
            formatted_name = formatted_name.replace("_pdf_pdf", "_pdf.pdf")
            print(f"Formatted name: {formatted_name}")

            # Construct the download URL
            pdf_url = f"https://courtofappeal.lk/wp-content/plugins/melstaalfresco/assets/data/{formatted_name}"
            pdf_name = formatted_name

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
