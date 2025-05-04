import requests
from bs4 import BeautifulSoup
import urllib.parse
import os
import re
import time

# Step 1: Set up the URL, headers, and keywords
url = "https://courtofappeal.lk/?page_id=10825"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.183 Safari/537.36"
}
keywords = ["EPF", "ETF", "Termination"]  # Replace with your actual keywords

# Step 2: Send a GET request with headers and retry mechanism
max_retries = 5
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
            print("Max retries exceeded. Exiting.")
            exit()

# Step 3: Parse the HTML content with BeautifulSoup
print("Parsing HTML content")
soup = BeautifulSoup(response.text, 'html.parser')

# Step 4: Locate the table and iterate through tbody rows
print("Locating the table")
table = soup.find("table")
if table is None:
    print("Table not found")
    exit()

print("Table found, locating rows")
rows = table.find("tbody").find_all("tr")

downloaded_files = []
for row in rows:
    # Step 5: Locate the relevant columns
    columns = row.find_all("td")
    if len(columns) < 3:
        continue  # Skip rows without enough columns

    # Extract the keywords text from the appropriate column (adjust index as needed)
    keywords_text = columns[4].get_text().strip()  # Assuming keywords are in the second column
    print(f"Keywords in row: {keywords_text}")
    
    # Check if any of the keywords are in this column
    if any(keyword.lower() in keywords_text.lower() for keyword in keywords):
        print(f"Matching keywords found: {keywords_text}")
        
        # Locate the button with 'melsta-name' attribute in the last column (adjust index if needed)
        button = columns[-1].find("button", {"melsta-name": True})
        if button:
            # Extract and format the 'melsta-name' attribute
            melsta_name = button['melsta-name']
            print(f"Found button with melsta-name: {melsta_name}")

            # Format the file name to match the URL pattern
            formatted_name = melsta_name.lower().replace(" ", "_").replace("-", "_").replace(".", "_").replace("(", "").replace(")", "")
            formatted_name = formatted_name.replace("_pdf_pdf", "_pdf.pdf")
            print(f"Formatted name: {formatted_name}")

            # Construct the download URL
            pdf_url = f"https://courtofappeal.lk/wp-content/plugins/melstaalfresco/assets/data/{formatted_name}"
            pdf_name = formatted_name
            print(f"Constructed PDF URL: {pdf_url}")
            
            # Step 6: Download the PDF
            try:
                print(f"Downloading PDF from {pdf_url}")
                pdf_response = requests.get(pdf_url)
                pdf_response.raise_for_status()
                
                # Save PDF to 'downloaded_pdfs' folder
                pdf_path = os.path.join("downloaded_pdfs", pdf_name)
                os.makedirs("downloaded_pdfs", exist_ok=True)
                with open(pdf_path, "wb") as pdf_file:
                    pdf_file.write(pdf_response.content)
                    
                downloaded_files.append(pdf_path)
                print(f"Downloaded: {pdf_path}")
            except requests.exceptions.RequestException as e:
                print(f"Failed to download {pdf_url}: {e}")

print(f"Downloaded files: {downloaded_files}")