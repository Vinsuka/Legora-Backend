import json
import os

def update_supreme_court_json():
    # Read the current JSON file
    with open('ETL/scrapers/supreme_court_run.json', 'r') as f:
        data = json.load(f)
    
    # Update each entry
    for entry in data:
        # Update page_id by adding 2
        entry['page_id'] += 2
        
        # Update month and year
        if entry['month'] == 12:
            entry['month'] = 1
            entry['year'] += 1
        else:
            entry['month'] += 1
    
    # Write back to the file
    with open('ETL/scrapers/supreme_court_run.json', 'w') as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    update_supreme_court_json() 