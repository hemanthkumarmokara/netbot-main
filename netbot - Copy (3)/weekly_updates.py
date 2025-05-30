import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# Config
CONFLUENCE_BASE_URL = "https://mokararaja138.atlassian.net/wiki"
CONFLUENCE_PAGE_ID = "131445"
CONFLUENCE_EMAIL = "mokararaja138@gmail.com"
CONFLUENCE_API_TOKEN = ""

def fetch_confluence_page():
    url = f"{CONFLUENCE_BASE_URL}/rest/api/content/{CONFLUENCE_PAGE_ID}?expand=body.storage"
    response = requests.get(url, auth=(CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN))
    response.raise_for_status()
    return response.json()["body"]["storage"]["value"]  # HTML content

def extract_updates_table(html):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    # print("tablemh:::   ")
    # print(tables)


    all_data = []


    for table in tables:
        rows = table.find_all("tr")
        current_week = None

        for row in rows:
            cells = row.find_all("td")
            if not cells:
                continue

            # If the first cell contains dates, capture it
            if re.search(r'\d{4}-\d{2}-\d{2}', row.decode()):
                # Extract all datetime values and convert to readable form
                times = row.find_all("time")
                if len(times) >= 2:
                    date1 = times[0]["datetime"]
                    date2 = times[1]["datetime"]
                    current_week = f"{date1} - {date2}"
                # Remove the date cell for consistent indexing
                if len(cells) == 3:
                    cells = cells[1:]

            if len(cells) == 2:
                department = cells[0].get_text(strip=True)
                update = cells[1].get_text(separator="\n", strip=True)
                all_data.append({
                    "week": current_week,
                    "department": department,
                    "update": update
                })
    # print("all data:   ")
    # print(all_data)
    return all_data

import difflib

def extract_update(department: str, week: str):
    html = fetch_confluence_page()
    table_data = extract_updates_table(html)
    print(f"Searching for department: '{department}' and week: '{week}'")

    # Extract start and end from user input week
    try:
        input_start, input_end = week.split(" - ")
        input_start_date = datetime.strptime(input_start.strip(), "%Y-%m-%d")
    except Exception as e:
        print(f"Error parsing input week: {e}")
        return "Invalid input week format."

    best_match = None
    best_score = 0

    for item in table_data:
        print(f"Comparing with week: '{item['week']}' and department: '{item['department']}'")

        try:
            item_start, item_end = item["week"].split(" - ")
            item_start_date = datetime.strptime(item_start.strip(), "%Y-%m-%d")
            item_end_date = datetime.strptime(item_end.strip(), "%Y-%m-%d")
        except Exception as e:
            print(f"Error parsing table week: {e}")
            continue

        # Check if input_start_date falls within item_start_date and item_end_date
        if item_start_date <= input_start_date <= item_end_date:
            # Fuzzy matching on department name
            similarity = difflib.SequenceMatcher(None, department.lower(), item["department"].lower()).ratio()
            print(f"Similarity between '{department}' and '{item['department']}': {similarity:.2f}")

            if similarity > best_score:
                best_score = similarity
                best_match = item

    if best_match and best_score > 0.6:  # threshold 0.6 (adjustable)
        return f"Update for {best_match['department']} during {best_match['week']}:\n{best_match['update']}"
    else:
        return "No matching update found for that department and week."


from dateutil import parser
from dateutil import parser
from datetime import datetime
import re

def normalize_week_string(week_str):
    try:
        week_str = week_str.replace(",", "").strip()
        current_year = datetime.now().year
        parts = re.split(r'\s*-\s*', week_str)

        if len(parts) == 1:
            # Single date like "March 31"
            if not re.search(r'\d{4}', parts[0]):
                parts[0] += f" {current_year}"
            single_date = parser.parse(parts[0], fuzzy=True)
            return f"{single_date.strftime('%Y-%m-%d')} - {single_date.strftime('%Y-%m-%d')}"
        
        elif len(parts) == 2:
            start_raw, end_raw = parts

            # If year is missing, add current year
            if not re.search(r'\d{4}', start_raw):
                start_raw += f" {current_year}"
            if not re.search(r'\d{4}', end_raw):
                end_raw += f" {current_year}"

            start_date = parser.parse(start_raw, fuzzy=True)
            end_date = parser.parse(end_raw, fuzzy=True)

            return f"{start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}"

        else:
            return ""

    except Exception as e:
        print(f"Error parsing week: {e}")
        return ""

# def answer_weekly_update_question(question: str):
#     week_match = re.search(r'week ([\w\s\d\-,]+)', question, re.IGNORECASE)
#     dept_match = re.search(r'update on (.*?) for', question, re.IGNORECASE) or \
#                  re.search(r'update of (.*?) in', question, re.IGNORECASE)

#     week = normalize_week_string(week_match.group(1).strip()) if week_match else ""
#     department = dept_match.group(1).strip() if dept_match else ""

#     if not department or not week:
#         return "Sorry, I couldn't extract the department and week properly from your question."

#     return extract_update(department, week)

def answer_weekly_update_question(department: str, week: str):
    week_normalized = normalize_week_string(week.strip()) if week else ""
    department = department.strip()

    if not department or not week_normalized:
        return "Sorry, I couldn't extract the department and week properly from your question."

    return extract_update(department, week_normalized)
# 
# print("lol")
# print(f"hi helloo   {normalize_week_string("March 31")}")
# print("joj")
# print(f"last   {answer_weekly_update_question("AUD", "Mar 31")}")
# print("non")
