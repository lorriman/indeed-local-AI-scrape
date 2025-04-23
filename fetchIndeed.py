from playwright.sync_api import sync_playwright
import pandas as pd
import requests
import yaml
import time
import json
import signal
import sys
from xlsxwriter import Workbook

# Load configuration
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

# Initialize Ollama client
import requests
import json


def query_ollama(prompt, model=config['ollama_model']):

    #model needs setting up or else it responds inconsistently 

    # Define the system prompt to enforce instruction-following
    system_prompt = "You are Qwen, created by Alibaba Cloud. Follow the user's instructions exactly without summarizing or altering the task unless explicitly asked."

    # Structure the messages array with system and user roles
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    # Set model parameters (asked an AI for this)
    options = {
        "temperature": 0.7,
        "top_p": 0.8,
        "repeat_penalty": 1.05,
        "top_k": 20,
        "num_ctx": 32000  # Larger context window to handle longish prompts
    }

    # Make the API request to the /api/chat endpoint
    response = requests.post(
        f"{config['ollama_endpoint']}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options
        }
    )

    # Check for a successful response
    if response.status_code != 200:
        raise Exception(f"API request failed with status {response.status_code}: {response.text}")

    # Extract the response content
    return json.loads(response.text)["message"]["content"].strip()

# Signal handler for interruption
def signal_handler(sig, frame):
    print("\nInterrupt received. Saving data to Excel...")
    if data:
        save_to_excel(data)
        print(f"Saved {len(data)} records to datadump.xlsx")
    else:
        print("No data to save.")
    print(f"Missed {timeout_count} items due to timeouts.")
    sys.exit(0)

# Save data to Excel with some formatting
def save_to_excel(data):
    df = pd.DataFrame(data)
    writer = pd.ExcelWriter('datadump.xlsx', engine='xlsxwriter')
    df.to_excel(writer, sheet_name='Jobs', index=False)
    workbook = writer.book
    worksheet = writer.sheets['Jobs']
    
    # Set column width to 5cm (approx 70.87 points)
    for col in range(len(df.columns)):
        worksheet.set_column(col, col, 70.87)
    
    # Set row height to 5cm (approx 141.73 points)
    for row in range(len(df) + 1):  # +1 for header
        worksheet.set_row(row, 141.73)
    
    writer.close()

signal.signal(signal.SIGINT, signal_handler)

data = []
timeout_count = 0

try:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(config['browser_cdp_url'])
        context = browser.contexts[0]
        page = context.new_page()
        page.goto(config['scrape_url'])
        time.sleep(30) #gives us the time to click the captcha

        page_num = 1
        while True:
            job_links = page.locator('h2.jobTitle a.jcs-JobTitle')
            print(f"Found {job_links.count()} job links on page {page_num}")

            for i in range(job_links.count()):
                try:
                    link = job_links.nth(i)
                    href = link.get_attribute('href')
                    link.click()
                    try:
                        page.wait_for_selector('div.jobsearch-HeaderContainer', timeout=10000)
                        job_desc = page.locator('div#jobDescriptionText')
                        text_elements = [text for text in job_desc.locator('//*[text()]').all_inner_texts() if text]
                        full_text = '.'.join(text_elements).strip()
                        print('############ NEW JOB ###########')
                      
                        
                        # 'required' prompt - for job requirements
                        prompt = config['required_prompt']+f"\"{full_text}\""
                        print('######## REQUIRED PROMPT'+prompt[:400]+'...')
                        qwen_answer = query_ollama(prompt)
                        required=''
                        details=''
                        if '.' in qwen_answer: # full-stop/period denotes valid response content as asked for in the query, and avoids exception
                            required = qwen_answer.split('.')[0].strip()
                            print("####REQUIRED\n"+required)
                            details = qwen_answer.split('.', 1)[1].strip()
                            print("####DETAILS\n"+details)                      
                        
                        # Get summary
                        summary_prompt = f"Give a twenty word summary of this job in this text. Maximum 20 words, here is the text:\"{full_text}\""
                        print("######### SUMMARY PROMPT "+summary_prompt[:100]+'...')
                        summary = query_ollama(summary_prompt)
                        short_summary = summary[:config['max_cell_length']]
                        print("####SUMMARY\n"+short_summary)
                        
                        print("######## LINK: "+"https://indeed.com"+href)

                        data.append({
                            'short_summary': short_summary,
                            'required': required,
                            'details': details,
                            'link': "https://indeed.com"+href
                        })
                    except Exception as e:
                        if "Timeout" in str(e):
                            timeout_count += 1
                        print(f"Error processing job description: {e}")
                        continue
                    time.sleep(2)
                except Exception as e:
                    print(f"Error processing job link: {e}")
                    continue

            next_page_link = page.locator(f'a[data-testid="pagination-page-{page_num + 1}"]')
            if next_page_link.count() == 0:
                break
            try:
                next_page_link.click()
                time.sleep(10)
                page_num += 1
            except Exception:
                break

        browser.close()

except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    if data:
        save_to_excel(data)
        print(f"Saved {len(data)} records to datadump.xlsx")
    else:
        print("No data to save.")
    print(f"Missed {timeout_count} items due to timeouts.")