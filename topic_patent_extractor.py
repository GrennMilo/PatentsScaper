import os
import re
import time
import json
import argparse
import traceback
from datetime import datetime
from urllib.parse import quote, quote_plus
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests

class PatentTopicExtractor:
    def __init__(self, topic, output_dir='patents', max_results=10, visible=False, debug=False):
        """Initialize the patent extractor."""
        self.topic = topic
        self.output_dir = output_dir
        self.max_results = max_results
        self.debug = debug
        self.visible = visible
        self.patent_ids = []
        self.base_url = 'https://patents.google.com'
        self.language = 'en'
        self.driver = None
        
        # Create output directory
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Create debug directory if needed
        if debug and not os.path.exists(os.path.join(output_dir, 'debug')):
            os.makedirs(os.path.join(output_dir, 'debug'))
        
        # Initialize the driver
        self.driver = self._initialize_driver()
    
    def _initialize_driver(self):
        """Initialize the Chrome driver with appropriate options."""
        options = Options()
        if not self.visible:
            options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
        
        try:
            driver = webdriver.Chrome(options=options)
            driver.implicitly_wait(10)
            return driver
        except Exception as e:
            print(f"Error initializing Chrome driver: {str(e)}")
            raise
    
    def get_search_url(self):
        """Get the search URL for the topic."""
        # Construct a more specific query to get better results
        query = self.topic.strip()
        
        # Use more specific search parameters
        params = {
            'q': query,
            'hl': self.language,
            'num': 100,  # Request more results per page
            'tbm': 'pts'  # Specifically request patents
        }
        
        # Build the URL with parameters
        url = f"{self.base_url}/?{'&'.join(f'{k}={quote_plus(str(v))}' for k, v in params.items())}"
        return url
    
    def _wait_for_search_results(self, timeout=20):
        """Wait for search results to appear on the page."""
        try:
            # Use multiple selectors to wait for search results
            selectors = [
                "article", 
                ".search-result", 
                "a[href*='/patent/']", 
                ".gs_ri",
                "h3",
                "[data-docid]"
            ]
            
            # Try each selector
            for selector in selectors:
                try:
                    WebDriverWait(self.driver, timeout/len(selectors)).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    print(f"Search results found using selector: {selector}")
                    return True
                except TimeoutException:
                    continue
                
            # If none of the selectors worked, try a more general approach
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda d: len(d.page_source) > 10000  # Assume large page means content loaded
                )
                print("Page appears to be loaded based on page size")
                return True
            except:
                pass
                
            # If we're still here, the page might not have loaded properly
            print("Timed out waiting for search results. Will try to proceed anyway.")
            return False
        except Exception as e:
            print(f"Error while waiting for search results: {str(e)}")
            return False
    
    def save_debug_info(self, prefix, info_type='both'):
        """Save screenshot and/or HTML source for debugging."""
        try:
            # Create debug directory if it doesn't exist
            debug_dir = os.path.join(self.output_dir, 'debug')
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
                
            if info_type in ['screenshot', 'both']:
                # Save screenshot
                try:
                    screenshot_path = os.path.join(debug_dir, f"{prefix}.png")
                    self.driver.save_screenshot(screenshot_path)
                    print(f"Saved screenshot to: {screenshot_path}")
                except Exception as e:
                    if self.debug:
                        print(f"Error saving screenshot: {str(e)}")
            
            if info_type in ['html', 'both']:
                # Save HTML source
                try:
                    html_path = os.path.join(debug_dir, f"{prefix}.html")
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(self.driver.page_source)
                    print(f"Saved HTML source to: {html_path}")
                except Exception as e:
                    if self.debug:
                        print(f"Error saving HTML source: {str(e)}")
                        
        except Exception as e:
            print(f"Error saving debug info: {str(e)}")
    
    def _retry_with_fallback(self, func, retries=3, *args, **kwargs):
        """Retry a function with error handling and driver reinitialization if needed."""
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print(f"Error in attempt {attempt+1}/{retries}: {str(e)}")
                
                # If this is our last attempt, re-raise the exception
                if attempt == retries - 1:
                    raise
                
                # If the session is invalid, reinitialize the driver
                if "invalid session id" in str(e).lower() or "session deleted" in str(e).lower():
                    print("Browser session is invalid. Reinitializing driver...")
                    try:
                        self.driver.quit()
                    except:
                        pass  # Ignore errors during quit
                    
                    self.driver = self._initialize_driver()
                
                # Otherwise, wait and retry
                time.sleep(2 * (attempt + 1))

    def _is_valid_patent_id(self, patent_id):
        """Check if a string looks like a valid patent ID."""
        if not patent_id:
            return False
            
        # Most patent IDs start with 2 letters (country code) followed by numbers
        # Common formats: USxxxxxx, US-xxxxxx, USxxxxxxxA, etc.
        pattern = r'^[A-Z]{2}\d{4,}[A-Z]?\d*$'
        return bool(re.match(pattern, patent_id))
        
    def _normalize_patent_id(self, patent_id):
        """Normalize patent ID to avoid duplicates."""
        if not patent_id:
            return None
                
        # Remove suffix like B1, B2, A1, etc.
        base_id = re.sub(r'([A-Z]\d+)[A-Z]\d*$', r'\1', patent_id)
        # Also handle case where US patents might have a leading 0
        if base_id.startswith('US0'):
            base_id = 'US' + base_id[3:].lstrip('0')
        elif base_id.startswith('US'):
            base_id = 'US' + base_id[2:].lstrip('0')
            
        return base_id
        
    def _add_patent_id(self, patent_id):
        """Add a patent ID to the list, avoiding duplicates."""
        if not patent_id or not self._is_valid_patent_id(patent_id):
            return False
                
        normalized_id = self._normalize_patent_id(patent_id)
            
        # Check if we already have this patent or a variant
        for existing_id in self.patent_ids:
            if self._normalize_patent_id(existing_id) == normalized_id:
                return False
            
        self.patent_ids.append(patent_id)
        print(f"Found patent ID: {patent_id}")
        return True
    
    def _save_patent_ids(self):
        """Save the list of patent IDs to a file."""
        if not self.patent_ids:
            return
            
        output_file = os.path.join(self.output_dir, f"{self.topic.replace(' ', '_')}_patent_ids.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            for patent_id in self.patent_ids:
                f.write(f"{patent_id}\n")
                
        print(f"Saved {len(self.patent_ids)} patent IDs to: {output_file}")
    
    def search_patents(self):
        """Search for patents and extract their IDs."""
        if not self.topic:
            print("Error: Search topic is required")
            return False
            
        # Clear previous results
        self.patent_ids = []
        
        # Try with regular search first
        try:
            search_success = self._try_search_methods()
            
            # If we didn't find any patents, try alternative search queries
            if not search_success or len(self.patent_ids) < min(5, self.max_results):
                print("Initial search yielded few results. Trying alternative queries...")
                
                # Save original topic
                original_topic = self.topic
                
                # Try with quotes
                if ' ' in self.topic:
                    print(f"Trying search with quotes: \"{self.topic}\"")
                    self.topic = f"\"{self.topic}\""
                    if self._try_search_methods() and len(self.patent_ids) >= min(5, self.max_results):
                        return True
                        
                # Try with advanced search operators
                self.topic = original_topic
                print(f"Trying advanced search: {self.topic} patent")
                self.topic = f"{self.topic} patent"
                if self._try_search_methods() and len(self.patent_ids) >= min(5, self.max_results):
                    return True
                    
                # Restore original topic
                self.topic = original_topic
            
            # Save the patent IDs to a file if we found any
            if self.patent_ids:
                self._save_patent_ids()
                print(f"Found {len(self.patent_ids)} patent IDs")
                return True
            else:
                print("No patents found for the specified topic.")
                return False
        except Exception as e:
            print(f"Error in search_patents: {str(e)}")
            if self.debug:
                print(traceback.format_exc())
            return False

    def _try_search_methods(self):
        """Try different search methods to extract patent IDs."""
        try:
            search_url = self.get_search_url()
            print(f"Searching for patents about: {self.topic}")
            print(f"Search URL: {search_url}")
            
            try:
                # Load the search page
                self.driver.get(search_url)
                
                # Wait for search results to load
                self._wait_for_search_results()
                
                if self.debug:
                    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                    self.save_debug_info(f"search_{current_time}")
                
                # Extract patent IDs using different methods
                self._extract_patent_ids()
                
                # If we need more results, try scrolling
                if len(self.patent_ids) < self.max_results:
                    self._scroll_and_extract_more_patents()
                    
                    # Try alternative extraction methods if we have few patents
                    if len(self.patent_ids) < min(10, self.max_results):
                        print("Few patents found with primary methods, trying alternative extraction...")
                        self._extract_patent_ids_from_links()
                        
                        if len(self.patent_ids) < min(10, self.max_results):
                            self._extract_patent_ids_from_source()
                
                return len(self.patent_ids) > 0
                
            except Exception as e:
                print(f"Error during patent search: {str(e)}")
                if self.debug:
                    print(traceback.format_exc())
                    self.save_debug_info("search_error")
                return False
                
        except Exception as e:
            print(f"Error in search methods: {str(e)}")
            if self.debug:
                print(traceback.format_exc())
            return False
    
    def _scroll_and_extract_more_patents(self):
        """Scroll down the page to load more results and extract patents."""
        previous_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 10  # Limit scrolling to prevent infinite loops
            
        print(f"Scrolling to load more patents (up to {self.max_results})...")
            
        while len(self.patent_ids) < self.max_results and scroll_attempts < max_scroll_attempts:
            # Scroll down
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for content to load
            
            # Try to click "Show more results" or "Next" buttons
            try:
                # Look for "Show more" button
                more_buttons = self.driver.find_elements(By.XPATH, 
                    "//button[contains(text(), 'more') or contains(text(), 'More') or contains(@aria-label, 'more')]")
                
                # Also look for pagination buttons
                pagination_buttons = self.driver.find_elements(By.XPATH,
                    "//button[contains(text(), 'Next') or contains(@aria-label, 'Next page')]")
                
                # Combine all potential buttons
                all_buttons = more_buttons + pagination_buttons
                
                for button in all_buttons:
                    if button.is_displayed() and button.is_enabled():
                        try:
                            # Scroll the button into view
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
                            time.sleep(1)
                            
                            # Click the button
                            button.click()
                            print("Clicked navigation button to load more results")
                            time.sleep(3)  # Wait for new results to load
                            break
                        except Exception as e:
                            print(f"Failed to click button: {str(e)}")
                            continue
            except Exception as e:
                if self.debug:
                    print(f"No pagination buttons found or error clicking them: {str(e)}")
            
            # Extract patents from the newly loaded content
            self._extract_patent_ids()
            
            # Check if we found new patents
            if len(self.patent_ids) > previous_count:
                previous_count = len(self.patent_ids)
                print(f"Found {len(self.patent_ids)} patents so far...")
                scroll_attempts = 0  # Reset counter if we found new patents
            else:
                scroll_attempts += 1
                
            # Take a screenshot in debug mode
            if self.debug:
                self.save_debug_info(f"search_scroll_{scroll_attempts}", 'screenshot')
            
        if scroll_attempts >= max_scroll_attempts:
            print("Reached maximum scroll attempts without finding new patents")
    
    def _extract_patent_ids(self):
        """Extract patent IDs from search results using multiple methods."""
        # Method 1: Find patent IDs in the URLs - this is usually the most reliable
        try:
            links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/patent/']")
            for link in links:
                try:
                    href = link.get_attribute('href')
                    if href and '/patent/' in href:
                        parts = href.split('/patent/')
                        if len(parts) > 1:
                            patent_id = parts[1].split('/')[0].split('?')[0]  # Remove any query params
                            self._add_patent_id(patent_id)
                            
                            if len(self.patent_ids) >= self.max_results:
                                return
                except Exception as e:
                    continue
        except Exception as e:
            print(f"Error extracting patent IDs from links: {str(e)}")
        
        # Method 2: Try to find elements with data attributes - less reliable but works for some patents
        try:
            results = self.driver.find_elements(By.CSS_SELECTOR, "[data-docid], [data-id]")
            for result in results:
                try:
                    patent_id = result.get_attribute('data-docid') or result.get_attribute('data-id')
                    self._add_patent_id(patent_id)
                    
                    if len(self.patent_ids) >= self.max_results:
                        return
                except:
                    continue
        except Exception as e:
            print(f"Error extracting patent IDs from data attributes: {str(e)}")
        
        # Method 3: Look for patent ID patterns in text of elements
        try:
            # Look for elements that might contain patent IDs
            potential_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                "h3, h4, .result-title, .patent-title, .search-result, article, .title")
            
            for element in potential_elements:
                try:
                    text = element.text.strip()
                    pattern = r'\b([A-Z]{2}\d{4,}[A-Z]?\d*)\b'
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if self._add_patent_id(match) and len(self.patent_ids) >= self.max_results:
                            return
                except:
                    continue
        except Exception as e:
            print(f"Error extracting patent IDs from text: {str(e)}")
    
    def _extract_patent_ids_from_links(self):
        """Extract patent IDs by finding all links containing patent patterns."""
        try:
            # Get all links and texts
            elements = self.driver.find_elements(By.TAG_NAME, "a") + self.driver.find_elements(By.TAG_NAME, "div")
            
            # First pass: check link URLs and texts
            for element in elements:
                try:
                    # Check link href
                    if element.tag_name == 'a':
                        href = element.get_attribute('href') or ""
                        if '/patent/' in href:
                            parts = href.split('/patent/')
                            if len(parts) > 1:
                                patent_id = parts[1].split('/')[0].split('?')[0]
                                if self._add_patent_id(patent_id) and len(self.patent_ids) >= self.max_results:
                                    return
                    
                    # Check text for patent IDs
                    text = element.text.strip()
                    pattern = r'\b([A-Z]{2}\d{4,}[A-Z]?\d*)\b'
                    matches = re.findall(pattern, text)
                    for match in matches:
                        if self._add_patent_id(match) and len(self.patent_ids) >= self.max_results:
                            return
                except:
                    continue
                    
            # Second pass: more aggressive search in page source
            source = self.driver.page_source
            pattern = r'/patent/([A-Z]{2}\d{4,}[A-Z]?\d*)'
            matches = re.findall(pattern, source)
            for match in matches:
                if self._add_patent_id(match) and len(self.patent_ids) >= self.max_results:
                    return
            
            # Third pass: look for any strings that match patent ID patterns
            pattern = r'\b([A-Z]{2}\d{4,}[A-Z]?\d*)\b'
            matches = re.findall(pattern, source)
            for match in matches:
                if self._add_patent_id(match) and len(self.patent_ids) >= self.max_results:
                    return
            
        except Exception as e:
            print(f"Error in alternative extraction method: {str(e)}")
    
    def _extract_patent_ids_from_source(self):
        """Extract patent IDs from the page source directly."""
        try:
            source = self.driver.page_source
            
            # Method 1: Look for patent links in the source
            pattern = r'href=["\']/patent/([A-Z]{2}\d{4,}[A-Z]?\d*)["\']'
            matches = re.findall(pattern, source)
            for match in matches:
                self._add_patent_id(match)
                
            # Method 2: Look for patent IDs in data attributes
            pattern = r'data-(?:id|docid)=["\']((?:[A-Z]{2}\d{4,}|US\d{6,})[A-Z]?\d*)["\']'
            matches = re.findall(pattern, source)
            for match in matches:
                self._add_patent_id(match)
                
            # Method 3: Look for patent IDs in text
            pattern = r'(?:patent|publication)\s+(?:number|id|#|no\.?|num\.?)\s*[:\-]?\s*([A-Z]{2}\d{4,}[A-Z]?\d*)'
            matches = re.findall(pattern, source, re.IGNORECASE)
            for match in matches:
                self._add_patent_id(match)
                
            # Method 4: General pattern for potential patent IDs (less strict)
            pattern = r'[>"\'\s]([A-Z]{2}\d{6,}[A-Z]?\d*)[\s<"\']'
            matches = re.findall(pattern, source)
            for match in matches:
                self._add_patent_id(match)
                
            if self.debug:
                print(f"Found {len(self.patent_ids)} unique patent IDs from source extraction")
                
        except Exception as e:
            print(f"Error extracting patent IDs from source: {str(e)}")
    
    def download_patent(self, patent_id):
        """Download a single patent PDF."""
        try:
            # Generate the URL for the patent page
            patent_url = f"{self.base_url}/patent/{patent_id}/en"
            print(f"Fetching patent from URL: {patent_url}")
            
            # Load the patent page
            self.driver.get(patent_url)
            
            # Wait for the page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "title"))
            )
            
            # Save debug info if needed
            if self.debug:
                self.save_debug_info(f"patent_{patent_id}")
            
            # Get the patent title
            try:
                title = self.driver.title
                print(f"Patent title: {title}")
            except:
                print("Could not extract patent title")
            
            # Try to find the download link using multiple methods
            pdf_url = None
            
            # Method 1: Look for PDF link in the page
            try:
                pdf_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='.pdf']")
                for link in pdf_links:
                    href = link.get_attribute('href')
                    if href and href.endswith('.pdf'):
                        pdf_url = href
                        print(f"Found PDF link in page: {pdf_url}")
                        break
            except Exception as e:
                print(f"Error finding PDF link: {str(e)}")
            
            # Method 2: Check for PDF URL in source
            if not pdf_url:
                try:
                    source = self.driver.page_source
                    matches = re.findall(r'(https://[^"\']+\.pdf)', source)
                    if matches:
                        pdf_url = matches[0]
                        print(f"Found PDF URL in source: {pdf_url}")
                except Exception as e:
                    print(f"Error finding PDF URL in source: {str(e)}")
            
            # Method 3: Construct a common format URL
            if not pdf_url:
                # Try to construct a URL based on common patterns
                base_id = re.sub(r'([A-Z]\d+)[A-Z]\d*$', r'\1', patent_id)
                pdf_url = f"https://patentimages.storage.googleapis.com/pdfs/{base_id}.pdf"
                print(f"Using constructed PDF URL: {pdf_url}")
            
            # If we found a PDF URL, download it
            if pdf_url:
                pdf_path = os.path.join(self.output_dir, f"{patent_id}.pdf")
                
                try:
                    # Download the PDF file
                    response = requests.get(pdf_url, timeout=30)
                    
                    if response.status_code == 200 and response.headers.get('Content-Type') == 'application/pdf':
                        with open(pdf_path, 'wb') as f:
                            f.write(response.content)
                        print(f"Successfully downloaded PDF to: {pdf_path}")
                        return True
                    else:
                        print(f"Failed to download PDF: Status code {response.status_code}")
                        # Save the HTML source for debugging
                        if self.debug:
                            error_path = os.path.join(self.output_dir, f"{patent_id}.html")
                            with open(error_path, 'w', encoding='utf-8') as f:
                                f.write(response.text)
                            print(f"Saved error response to: {error_path}")
                except Exception as e:
                    print(f"Error downloading PDF: {str(e)}")
            
            # If we couldn't download the PDF, save the HTML source
            html_path = os.path.join(self.output_dir, f"{patent_id}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print(f"Saved HTML source to: {html_path}")
            
            return False
            
        except Exception as e:
            print(f"Error processing patent {patent_id}: {str(e)}")
            return False
    
    def download_all_patents(self):
        """Download all extracted patents one by one."""
        if not self.patent_ids:
            print("No patent IDs found. Cannot download patents.")
            return 0
        
        # Remove duplicates by normalizing
        normalized_ids = {}
        for patent_id in self.patent_ids:
            normalized = self._normalize_patent_id(patent_id)
            if normalized not in normalized_ids:
                normalized_ids[normalized] = patent_id
        
        # Use the deduplicated list
        deduplicated_patents = list(normalized_ids.values())
        print(f"After removing duplicates, downloading {len(deduplicated_patents)} unique patents.")
        
        successful_downloads = 0
        
        # Create a record of download status
        download_record = {}
        record_file = os.path.join(self.output_dir, f"{self.topic.replace(' ', '_')}_download_record.json")
        
        # Initialize the record file
        for patent_id in deduplicated_patents:
            download_record[patent_id] = {"status": "pending", "path": "", "error": ""}
        
        # Save initial record
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(download_record, f, indent=2)
        
        # Download each patent
        for i, patent_id in enumerate(deduplicated_patents):
            print(f"\nDownloading patent {i+1}/{len(deduplicated_patents)}: {patent_id}")
            
            try:
                success = self.download_patent(patent_id)
                if success:
                    successful_downloads += 1
                    download_record[patent_id]["status"] = "success"
                    download_record[patent_id]["path"] = os.path.join(self.output_dir, f"{patent_id}.pdf")
                else:
                    download_record[patent_id]["status"] = "failed"
                    download_record[patent_id]["error"] = "Could not download PDF"
            except Exception as e:
                print(f"Error downloading patent {patent_id}: {str(e)}")
                download_record[patent_id]["status"] = "error"
                download_record[patent_id]["error"] = str(e)
            
            # Update the record file after each download
            with open(record_file, 'w', encoding='utf-8') as f:
                json.dump(download_record, f, indent=2)
            
            # Add a delay to avoid overloading the server
            time.sleep(2)
        
        print(f"\nDownload complete. Successfully downloaded {successful_downloads} out of {len(deduplicated_patents)} patents.")
        return successful_downloads
    
    def run(self):
        """Run the patent extractor process."""
        try:
            print(f"\nStep 1: Searching for patents on topic: {self.topic}")
            
            # Search for patents and extract IDs
            if not self.search_patents():
                print("Failed to find patents. Please try a different topic or search method.")
                return False
            
            # Download patents if IDs were found
            if self.patent_ids:
                print(f"\nStep 2: Downloading {len(self.patent_ids)} patents")
                self.download_all_patents()
                return True
            
            return False
        except Exception as e:
            print(f"Error during patent extraction: {str(e)}")
            if self.debug:
                print(traceback.format_exc())
            return False
        finally:
            # Always close the browser at the end
            try:
                if self.driver:
                    self.driver.quit()
            except:
                pass

def main():
    """Entry point for the script."""
    parser = argparse.ArgumentParser(description='Extract patents from Google Patents based on a topic')
    parser.add_argument('topic', help='Topic to search for patents')
    parser.add_argument('--output', default='patents', help='Output directory for downloaded patents')
    parser.add_argument('--max', type=int, default=10, help='Maximum number of patents to download')
    parser.add_argument('--visible', action='store_true', help='Run with browser visible')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    extractor = PatentTopicExtractor(
        topic=args.topic,
        output_dir=args.output,
        max_results=args.max,
        visible=args.visible,
        debug=args.debug
    )
    
    success = extractor.run()
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())