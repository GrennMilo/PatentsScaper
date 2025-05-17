#!/usr/bin/env python3

import os
import sys
import argparse
import subprocess

def main():
    parser = argparse.ArgumentParser(description='Download chemistry and pharmaceutical patents from Google Patents')
    parser.add_argument('--query', type=str, default="chemistry pharmaceutical", 
                       help='Search query (default: "chemistry pharmaceutical")')
    parser.add_argument('--cpc', type=str, default="A61K,C07,C08,C09",
                       help='CPC classification codes (comma-separated, default: A61K,C07,C08,C09)')
    parser.add_argument('--language', type=str, default="en", 
                       help='Patent language (default: "en" for English)')
    parser.add_argument('--num', type=int, default=10, 
                       help='Number of patents to download (default: 10)')
    parser.add_argument('--output', type=str, default="patents", 
                       help='Output directory for patents (default: "patents")')
    parser.add_argument('--method', type=str, choices=['simple', 'selenium'], default='selenium',
                       help='Download method to use: simple (requests) or selenium (default: selenium)')
    parser.add_argument('--visible', action='store_true',
                       help='Make the browser visible (only for selenium method)')
    parser.add_argument('--patent-id', type=str,
                       help='Directly download a specific patent ID (e.g., "US10123456")')
    parser.add_argument('--debug', action='store_true',
                        help='Enable additional debugging output')
    
    args = parser.parse_args()
    
    # Create a custom script for direct patent download if patent-id is provided
    if args.patent_id:
        print(f"Direct patent download mode for ID: {args.patent_id}")
        create_direct_download_script(args.patent_id, args.output, args.method == 'selenium', args.visible)
        return 0
    
    # Prepare the command to run
    if args.method == 'simple':
        script = 'patent_downloader.py'
        command = [
            sys.executable,
            script,
            f"--query={args.query}",
            f"--cpc={args.cpc}",
            f"--language={args.language}",
            f"--num={args.num}",
            f"--output={args.output}"
        ]
        
        if args.debug:
            # For the simple method, debug info is already built in
            pass
    else:  # selenium
        script = 'selenium_patent_downloader.py'
        command = [
            sys.executable,
            script,
            f"--query={args.query}",
            f"--cpc={args.cpc}",
            f"--language={args.language}",
            f"--num={args.num}",
            f"--output={args.output}"
        ]
        
        # Set headless mode based on --visible flag
        if args.visible:
            command.append("--headless=false")
            
        if args.debug:
            # Debug info already built into the updated selenium script
            pass
    
    # Ensure the specified script exists
    if not os.path.exists(script):
        print(f"Error: Script {script} not found in the current directory.")
        print("Make sure you're running this command from the directory containing the downloader scripts.")
        return 1
    
    # Make sure the output directory exists
    os.makedirs(args.output, exist_ok=True)
    
    print(f"Running: {' '.join(command)}")
    
    # Execute the command
    try:
        subprocess.run(command, check=True)
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error running {script}: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        return 130

def create_direct_download_script(patent_id, output_dir="patents", use_selenium=True, visible=False):
    """Create and run a script to download a specific patent ID directly"""
    script_path = os.path.join(output_dir, "download_single_patent.py")
    
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Write a simple script to download just one patent
    with open(script_path, 'w') as f:
        f.write(f"""#!/usr/bin/env python3

import os
import sys
import requests
from urllib.parse import quote_plus
""")
        
        if use_selenium:
            f.write("""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
""")
            
        f.write(f"""
def main():
    patent_id = "{patent_id}"
    output_dir = "{output_dir}"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Attempting to download patent {{patent_id}}...")
    
    # Construct the patent URL - using correct format for Google Patents
    patent_url = f"https://patents.google.com/patent/{{patent_id}}/en"
    output_pdf = os.path.join(output_dir, f"{{patent_id}}.pdf")
    output_html = os.path.join(output_dir, f"{{patent_id}}.html")
    
""")
        
        if use_selenium:
            f.write(f"""
    # Set up Selenium WebDriver
    chrome_options = Options()
    {"" if visible else 'chrome_options.add_argument("--headless=new")'}
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set up session for downloading
        session = requests.Session()
        
        # Navigate to the patent page
        print(f"Opening: {{patent_url}}")
        driver.get(patent_url)
        
        # Wait for page to load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Save screenshot for debugging
        driver.save_screenshot(os.path.join(output_dir, f"{{patent_id}}_page.png"))
        
        # Save HTML for debugging
        with open(output_html, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print(f"Saved HTML to: {{output_html}}")
        
        # Try to extract title
        try:
            title_elem = driver.find_element(By.CSS_SELECTOR, "h1, .patent-title, [data-patent-title]")
            title = title_elem.text.strip()
            print(f"Patent title: {{title}}")
        except:
            print("Could not extract title")
        
        # Try multiple PDF URLs
        pdf_urls = [
            f"https://patents.google.com/patent/pdf/{{patent_id}}.pdf",
            f"https://patents.google.com/patent/{{patent_id}}.pdf",
            f"https://patents.google.com/patent/{{patent_id}}/en/pdf",
            f"https://patents.google.com/patent/{{patent_id}}/pdf",
            f"https://patentimages.storage.googleapis.com/pdfs/{{patent_id}}.pdf"
        ]
        
        # Get cookies from Selenium to use with requests
        selenium_cookies = driver.get_cookies()
        for cookie in selenium_cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        
        success = False
        for pdf_url in pdf_urls:
            try:
                print(f"Trying PDF URL: {{pdf_url}}")
                response = session.get(pdf_url, stream=True, timeout=10)
                
                if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
                    with open(output_pdf, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    print(f"Successfully downloaded PDF to: {{output_pdf}}")
                    success = True
                    break
            except Exception as e:
                print(f"Error with URL {{pdf_url}}: {{str(e)}}")
        
        if not success:
            print("Could not download PDF directly. Saved HTML version instead.")
        
        driver.quit()
        
    except Exception as e:
        print(f"Error: {{str(e)}}")
""")
        else:
            f.write("""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    try:
        # First get the patent page
        print(f"Requesting: {patent_url}")
        response = requests.get(patent_url, headers=headers)
        
        # Save HTML for debugging
        with open(output_html, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"Saved HTML to: {output_html}")
        
        # Try multiple PDF URLs
        pdf_urls = [
            f"https://patents.google.com/patent/pdf/{patent_id}.pdf",
            f"https://patents.google.com/patent/{patent_id}.pdf",
            f"https://patents.google.com/patent/{patent_id}/en/pdf",
            f"https://patents.google.com/patent/{patent_id}/pdf",
            f"https://patentimages.storage.googleapis.com/pdfs/{patent_id}.pdf"
        ]
        
        success = False
        for pdf_url in pdf_urls:
            try:
                print(f"Trying PDF URL: {pdf_url}")
                response = requests.get(pdf_url, headers=headers, stream=True, timeout=10)
                
                if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
                    with open(output_pdf, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    print(f"Successfully downloaded PDF to: {output_pdf}")
                    success = True
                    break
            except Exception as e:
                print(f"Error with URL {pdf_url}: {str(e)}")
        
        if not success:
            print("Could not download PDF directly. Saved HTML version instead.")
            
    except Exception as e:
        print(f"Error: {str(e)}")
""")
        
        f.write("""
if __name__ == "__main__":
    main()
""")
    
    # Make the script executable
    try:
        os.chmod(script_path, 0o755)
    except:
        pass
    
    print(f"Created download script: {script_path}")
    
    # Run the script
    try:
        subprocess.run([sys.executable, script_path], check=True)
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error running direct download script: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 