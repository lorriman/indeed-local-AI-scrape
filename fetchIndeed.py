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
def query_ollama(prompt, model=config['ollama_model']):
    response = requests.post(
        f"{config['ollama_endpoint']}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False}
    )
    return json.loads(response.text)['response'].strip()

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

# Save data to Excel with formatting
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
        time.sleep(30)

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
                      
                        
                        # Updated degree prompt
                        degree_prompt = f"In the following text, is a degree required? Answer with 'Yes degree' or 'No degree' followed by a period and then give the snippet of degree text you found but no more than 50 words.  Here is the text: \"{full_text}\""
                        qwen_answer = query_ollama(degree_prompt)
                        degree_required = qwen_answer.split('.')[0].strip()
                        
                        # Get summary
                        summary_prompt = f"Give a 20 word summary of this job in this text:\"{full_text}\""
                        summary = query_ollama(summary_prompt)
                        short_summary = summary[:config['max_cell_length']]
                        #summary_prompt = f"{config['summary_prompt']}. Here is the text:\"{full_text}\""
                        #summary = query_ollama(summary_prompt)
                        #summary = summary[:config['max_cell_length']]
                        
                        data.append({
                            'short_summary': short_summary,
                            #'job_summary': summary,
                            'degree_required': degree_required,
                            'degree_details': qwen_answer,
                            'link': href
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