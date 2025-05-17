#!/usr/bin/env python3

import os
import sys
import time
import argparse
import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import re
import traceback

class SeleniumPatentDownloader:
    def __init__(self, output_dir="patents", headless=True, debug=False):
        """Initialize the patent downloader with Selenium for dynamic content."""
        self.output_dir = output_dir
        self.headless = headless
        self.debug = debug
        self.base_url = "https://patents.google.com/"
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        if self.debug:
            self.debug_dir = os.path.join(self.output_dir, "debug")
            os.makedirs(self.debug_dir, exist_ok=True)
        
        # Initialize WebDriver
        self._initialize_driver()
    
    def _initialize_driver(self):
        """Initialize the Chrome WebDriver."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        try:
            service = Service()
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            # Initialize a session for downloads
            self.session = requests.Session()
        except Exception as e:
            print(f"Error initializing WebDriver: {str(e)}")
            raise
    
    def close(self):
        """Close the WebDriver."""
        if hasattr(self, 'driver'):
            self.driver.quit()
    
    def save_debug_info(self, filename, type='screenshot'):
        """Save debug information (screenshot or HTML source)."""
        if not self.debug:
            return
            
        try:
            if type == 'screenshot':
                file_path = os.path.join(self.debug_dir, f"{filename}.png")
                self.driver.save_screenshot(file_path)
                print(f"Saved screenshot to: {file_path}")
            elif type == 'html':
                file_path = os.path.join(self.debug_dir, f"{filename}.html")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print(f"Saved HTML source to: {file_path}")
            elif type == 'text':
                file_path = os.path.join(self.debug_dir, f"{filename}.txt")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(filename))  # In this case, filename is actually the content
                print(f"Saved text content to: {file_path}")
        except Exception as e:
            print(f"Error saving debug info: {str(e)}")
    
    def search_patents(self, query, max_results=10, language="en"):
        """Search for patents using the given query."""
        # Properly format the search URL for Google Patents
        search_url = f"{self.base_url}?q={quote_plus(query)}&hl={language}"
        print(f"Searching with URL: {search_url}")
        
        patents_found = []
        
        try:
            # Navigate to the search URL
            self.driver.get(search_url)
            
            # Wait for page to load with multiple potential selectors
            wait_selectors = [
                (By.CSS_SELECTOR, "search-results, .search-results, .results-container"),
                (By.TAG_NAME, "search-result"),
                (By.CSS_SELECTOR, "article.result, .result-item, .card"),
                (By.CSS_SELECTOR, "a[href*='/patent/']")
            ]
            
            # Try each selector with a short timeout
            results_loaded = False
            for by, selector in wait_selectors:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    print(f"Results loaded with selector: {selector}")
                    results_loaded = True
                    break
                except TimeoutException:
                    continue
            
            # If we still haven't found results, wait longer with a more generic selector
            if not results_loaded:
                try:
                    print("Waiting longer for results to load...")
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    # Just wait a bit more for any JavaScript to run
                    time.sleep(5)
                except TimeoutException:
                    print("Timed out waiting for results")
            
            # Save debug info
            if self.debug:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.save_debug_info(f"search_{timestamp}", 'screenshot')
                self.save_debug_info(f"search_{timestamp}", 'html')
            
            # Parse results using multiple methods
            patents_found = self._extract_search_results(max_results)
            
            if not patents_found:
                print("No patents found using selectors. Trying direct methods...")
                
                # Try direct patent search if query might contain patent IDs
                patents_found = self._try_direct_patent_search(query, max_results)
            
            return patents_found
            
        except Exception as e:
            print(f"Error during search: {str(e)}")
            if self.debug:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.save_debug_info(f"search_error_{timestamp}", 'screenshot')
                self.save_debug_info(f"search_error_{timestamp}", 'html')
                self.save_debug_info(f"error_details_{timestamp}", 'text')
            return []
    
    def _extract_search_results(self, max_results):
        """Extract patent information from search results."""
        patents_found = []
        
        # Try multiple selectors for search results
        selectors = [
            "search-result", 
            ".search-result", 
            "article.result", 
            ".result-item", 
            "[data-result-number]",
            ".gs_r",  # Google Scholar-like results
            "a[href*='/patent/']"  # Direct links to patents
        ]
        
        for selector in selectors:
            try:
                results = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if results:
                    print(f"Found {len(results)} results with selector: {selector}")
                    break
            except:
                results = []
        
        if not results:
            print("No search results found with any selector")
            return patents_found
        
        for i, result in enumerate(results[:max_results]):
            try:
                patent_info = self._extract_patent_from_result(result)
                if patent_info:
                    patents_found.append(patent_info)
                    print(f"Found: {patent_info['id']} - {patent_info['title']}")
            except Exception as e:
                print(f"Error extracting patent {i+1}: {str(e)}")
        
        # If we didn't find patents through results, try to find direct links
        if not patents_found:
            try:
                links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/patent/']")
                processed_ids = set()
                
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href and '/patent/' in href:
                            parts = href.split('/patent/')
                            if len(parts) > 1:
                                patent_id = parts[1].split('/')[0]
                                if patent_id and patent_id not in processed_ids:
                                    processed_ids.add(patent_id)
                                    
                                    # Try to get title
                                    try:
                                        title = link.text.strip()
                                        if not title:
                                            parent = link.find_element(By.XPATH, "./..")
                                            title = parent.text.strip()
                                    except:
                                        title = f"Patent {patent_id}"
                                    
                                    patents_found.append({
                                        'id': patent_id,
                                        'title': title,
                                        'link': f"{self.base_url}patent/{patent_id}/en"
                                    })
                                    
                                    print(f"Found from link: {patent_id} - {title}")
                                    
                                    if len(patents_found) >= max_results:
                                        break
                    except Exception as e:
                        print(f"Error processing link: {str(e)}")
                        continue
            except Exception as e:
                print(f"Error finding patent links: {str(e)}")
        
        return patents_found
    
    def _extract_patent_from_result(self, result):
        """Extract patent information from a single search result."""
        patent_id = None
        title = None
        
        try:
            # Try to extract the patent ID from data attribute
            try:
                patent_id = result.get_attribute('data-docid') or result.get_attribute('data-id')
            except:
                pass
            
            # Try to extract the patent ID from the link
            if not patent_id:
                try:
                    links = result.find_elements(By.CSS_SELECTOR, "a[href*='/patent/']")
                    if links:
                        href = links[0].get_attribute('href')
                        if href and '/patent/' in href:
                            parts = href.split('/patent/')
                            if len(parts) > 1:
                                patent_id = parts[1].split('/')[0]
                except:
                    pass
            
            # Try to extract the title
            for title_selector in ['.result-title', '.patent-title', 'h3', 'h4', '.title']:
                try:
                    title_elem = result.find_element(By.CSS_SELECTOR, title_selector)
                    title = title_elem.text.strip()
                    if title:
                        break
                except:
                    pass
            
            # If no title found, try getting any text from the result
            if not title:
                try:
                    title = result.text.strip()
                    # If title is very long, truncate it
                    if len(title) > 100:
                        title = title[:100] + "..."
                except:
                    pass
            
            # If we have a patent ID, create the patent info
            if patent_id:
                return {
                    'id': patent_id,
                    'title': title or f"Patent {patent_id}",
                    'link': f"{self.base_url}patent/{patent_id}/en"
                }
        
        except Exception as e:
            print(f"Error extracting patent details: {str(e)}")
        
        return None
    
    def _try_direct_patent_search(self, query, max_results):
        """Try to search for patents directly by potential patent numbers in query."""
        patents_found = []
        
        # Check if query contains potential patent IDs
        words = query.split()
        potential_ids = []
        
        # Look for patterns that might be patent IDs
        for word in words:
            # Common patent prefixes
            if any(word.startswith(prefix) for prefix in ["US", "EP", "WO", "GB", "CN", "JP", "CA"]):
                potential_ids.append(word)
            # Numbers that might be patent numbers
            elif len(word) >= 6 and word.isdigit():
                potential_ids.append(word)
        
        # If no potential IDs found, return empty list
        if not potential_ids:
            return []
            
        print(f"Found potential patent IDs in query: {potential_ids}")
        
        # Try each potential ID
        for patent_id in potential_ids[:max_results]:
            try:
                patent_url = f"{self.base_url}patent/{patent_id}/en"
                print(f"Trying direct patent URL: {patent_url}")
                
                self.driver.get(patent_url)
                
                # Wait briefly for page to load
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                except:
                    pass
                
                # Check if it's a valid patent page by looking for title
                try:
                    title_elem = self.driver.find_element(By.CSS_SELECTOR, "h1, .patent-title, [data-patent-title]")
                    title = title_elem.text.strip()
                    
                    patents_found.append({
                        'id': patent_id,
                        'title': title or f"Patent {patent_id}",
                        'link': patent_url
                    })
                    
                    print(f"Found direct patent: {patent_id} - {title}")
                except NoSuchElementException:
                    print(f"URL {patent_url} does not appear to be a valid patent page")
                
                # Save debug info
                if self.debug:
                    self.save_debug_info(f"direct_{patent_id}", 'screenshot')
                    self.save_debug_info(f"direct_{patent_id}", 'html')
            
            except Exception as e:
                print(f"Error checking direct patent {patent_id}: {str(e)}")
                continue
        
        return patents_found
    
    def download_patent(self, patent_id):
        """Download a single patent PDF."""
        try:
            # Generate the URL for the patent page
            patent_url = f"{self.base_url}/patent/{patent_id}/en"
            print(f"Patent URL: {patent_url}")
            
            # Navigate to the patent page
            self.driver.get(patent_url)
            
            # Wait for the page to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "title"))
                )
            except Exception as e:
                print(f"Timeout waiting for patent page to load: {str(e)}")
            
            # Take a screenshot if debug is enabled
            if self.debug:
                try:
                    screenshot_path = os.path.join(self.debug_dir, f"patent_{patent_id}.png")
                    self.driver.save_screenshot(screenshot_path)
                    print(f"Saved screenshot to: {screenshot_path}")
                except Exception as e:
                    print(f"Error saving screenshot: {str(e)}")
            
            # Extract the patent title
            title = ""
            try:
                title = self.driver.title
                # Remove "Google Patents" and other common suffixes from title
                title = re.sub(r' - Google Patents$', '', title)
                title = re.sub(r' - Patents\.com - Google Patents$', '', title)
                
                # Remove patent ID from title (it's often included at the beginning)
                title = re.sub(f'^{patent_id} - ', '', title)
                
                print(f"Patent title: {title}")
            except Exception as e:
                print(f"Could not extract patent title: {str(e)}")
            
            # Sanitize title for filename use
            sanitized_title = ""
            if title:
                # Replace invalid filename characters and limit length
                sanitized_title = re.sub(r'[\\/*?:"<>|]', '', title)  # Remove invalid filename chars
                sanitized_title = re.sub(r'\s+', '_', sanitized_title)  # Replace spaces with underscores
                sanitized_title = sanitized_title[:100]  # Limit length to avoid too long filenames
            
            # Look for PDF download link
            pdf_link = None
            
            # Method 1: Try to find PDF link in the page
            try:
                pdf_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='.pdf']")
                for link in pdf_links:
                    href = link.get_attribute('href')
                    if href and '.pdf' in href:
                        pdf_link = href
                        print(f"Found PDF link: {pdf_link}")
                        break
            except Exception as e:
                print(f"Error finding PDF link: {str(e)}")
            
            # Method 2: Try to extract from page source
            if not pdf_link:
                try:
                    pattern = r'href="(https://[^"]+\.pdf)"'
                    match = re.search(pattern, self.driver.page_source)
                    if match:
                        pdf_link = match.group(1)
                        print(f"Found PDF link in source: {pdf_link}")
                except Exception as e:
                    print(f"Error extracting PDF link from source: {str(e)}")
            
            # Method 3: Construct PDF link (fallback)
            if not pdf_link:
                # Common format for Google Patents PDF URLs
                base_id = re.sub(r'([A-Z]\d+)[A-Z]?\d*$', r'\1', patent_id)
                pdf_link = f"https://patentimages.storage.googleapis.com/pdfs/{base_id}.pdf"
                print(f"Using constructed PDF link: {pdf_link}")
            
            # Download the PDF
            if pdf_link:
                try:
                    # Determine output filename
                    if sanitized_title:
                        pdf_filename = f"{patent_id}_{sanitized_title}.pdf"
                    else:
                        pdf_filename = f"{patent_id}.pdf"
                        
                    output_path = os.path.join(self.output_dir, pdf_filename)
                    
                    # Download the PDF using requests
                    response = requests.get(pdf_link, timeout=20)
                    
                    if response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            f.write(response.content)
                        print(f"Successfully downloaded PDF to: {output_path}")
                        return True
                    else:
                        print(f"Failed to download PDF: Status code {response.status_code}")
                except Exception as e:
                    print(f"Error downloading PDF: {str(e)}")
            
            # If PDF download failed, save the HTML source
            try:
                # Determine output HTML filename
                if sanitized_title:
                    html_filename = f"{patent_id}_{sanitized_title}.html"
                else:
                    html_filename = f"{patent_id}.html"
                    
                html_path = os.path.join(self.output_dir, html_filename)
                
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print(f"Saved HTML source to: {html_path}")
            except Exception as e:
                print(f"Error saving HTML: {str(e)}")
                
            return False
            
        except Exception as e:
            print(f"Error processing patent {patent_id}: {str(e)}")
            if self.debug:
                print(traceback.format_exc())
            return False
    
    def download_patents_from_search(self, query, max_results=10, language="en"):
        """Search for patents and download the results."""
        print(f"Searching for patents: {query}")
        
        patents = self.search_patents(query, max_results, language)
        
        if not patents:
            print("No patents found.")
            return 0, 0
        
        print(f"Found {len(patents)} patents. Preparing to download up to {max_results}.")
        
        downloaded = 0
        for i, patent in enumerate(patents[:max_results]):
            print(f"\nDownloading patent {i+1}/{min(len(patents), max_results)}: {patent['id']}")
            if self.download_patent(patent['id']):
                downloaded += 1
            time.sleep(2)  # Avoid overloading the server
            
        return downloaded, min(len(patents), max_results)
    
    def download_specific_patent(self, patent_id):
        """Download a specific patent by its ID."""
        print(f"Attempting to download specific patent: {patent_id}")
        return self.download_patent(patent_id)

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Download patents from Google Patents using Selenium')
    parser.add_argument('query', type=str, nargs='?', help='Search query for patents')
    parser.add_argument('--max', type=int, default=10, help='Maximum number of patents to download')
    parser.add_argument('--output', type=str, default='patents', help='Output directory for downloaded patents')
    parser.add_argument('--language', type=str, default='en', help='Language for patents')
    parser.add_argument('--visible', action='store_true', help='Run Chrome in visible mode (not headless)')
    parser.add_argument('--patent-id', type=str, help='Download a specific patent by ID')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    downloader = SeleniumPatentDownloader(
        output_dir=args.output,
        headless=not args.visible,
        debug=args.debug
    )
    
    try:
        if args.patent_id:
            # Download a specific patent
            success = downloader.download_specific_patent(args.patent_id)
            if success:
                print("Patent download completed successfully")
            else:
                print("Failed to download patent")
                sys.exit(1)
        elif args.query:
            # Search and download patents
            downloaded, total = downloader.download_patents_from_search(
                args.query, 
                max_results=args.max,
                language=args.language
            )
            
            print(f"\nDownloaded {downloaded} out of {total} patents")
            
            if args.debug:
                print("\nNote: Debug mode was enabled. Check the debug directory for detailed logs.")
                
            if downloaded == 0:
                print("\nWarning: No patents were downloaded.")
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)
    finally:
        downloader.close()

if __name__ == "__main__":
    main() 