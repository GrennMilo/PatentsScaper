#!/usr/bin/env python3

import os
import sys
import requests
import time
import re
import argparse
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin
import json
from datetime import datetime
import traceback

class PatentDownloader:
    def __init__(self, output_dir="patents", debug=False):
        """Initialize the patent downloader with configuration."""
        self.output_dir = output_dir
        self.base_url = "https://patents.google.com/"
        self.debug = debug
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        if self.debug:
            self.debug_dir = os.path.join(self.output_dir, "debug")
            os.makedirs(self.debug_dir, exist_ok=True)
        
        # Set up session for consistent cookies
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        })
    
    def save_debug_info(self, content, filename, is_binary=False):
        """Save debug information to file."""
        if not self.debug:
            return
            
        file_path = os.path.join(self.debug_dir, filename)
        mode = 'wb' if is_binary else 'w'
        encoding = None if is_binary else 'utf-8'
        
        with open(file_path, mode, encoding=encoding) as f:
            f.write(content)
        
        print(f"Saved debug info to: {file_path}")
    
    def search_patents(self, query, max_results=10, language="en"):
        """Search for patents using the given query."""
        # Properly format the search URL for Google Patents
        search_url = f"{self.base_url}?q={quote_plus(query)}&hl={language}"
        print(f"Searching with URL: {search_url}")
        
        # A note that this direct request approach has limitations with Google Patents
        # which is a single-page app, and may need Selenium for better results
        try:
            response = self.session.get(search_url, timeout=30)
            
            if self.debug:
                self.save_debug_info(response.text, "search_page.html")
                self.save_debug_info(f"Status Code: {response.status_code}\nURL: {response.url}\n\nHeaders: {json.dumps(dict(response.headers), indent=2)}", 
                                    "search_response_info.txt")
            
            # Check response
            if response.status_code != 200:
                print(f"Error: Received status code {response.status_code} from search")
                return []
                
            # Parse results - Note: Direct HTML parsing may not work well with Google Patents SPA
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Save the soup structure for debugging
            if self.debug:
                self.save_debug_info(str(soup.prettify()), "search_soup.html")
            
            # This is just placeholder logic - direct requests won't work well with Google Patents SPA
            # Real implementation would need Selenium
            patent_links = []
            patents_found = []
            
            # We're just checking if there are any potentially relevant elements
            search_results = soup.select('search-results, .search-results, .results-container, article')
            if search_results:
                print(f"Found potential search results containers: {len(search_results)}")
            else:
                print("No search results containers found in HTML")
            
            # Just logging the general structure for debugging
            print(f"Page title: {soup.title.string if soup.title else 'No title'}")
            print(f"Found {len(patent_links)} potential patent links (note: this method has limitations)")
            
            # Return note about limitations
            print("NOTE: The direct request method has limitations with Google Patents SPA.")
            print("Consider using the Selenium-based downloader for better results.")
            
            return patents_found
            
        except Exception as e:
            print(f"Error searching for patents: {str(e)}")
            if self.debug:
                self.save_debug_info(f"Error searching for patents: {str(e)}", "search_error.txt")
            return []
    
    def download_patent(self, patent_id):
        """Download a single patent by ID."""
        try:
            # Generate the URL for the patent page
            patent_url = f"{self.base_url}/patent/{patent_id}/en"
            print(f"Fetching patent from URL: {patent_url}")
            
            # Download the patent page
            response = self.session.get(patent_url)
            
            if response.status_code != 200:
                print(f"Error: Could not access patent page (status code {response.status_code})")
                if self.debug:
                    debug_path = os.path.join(self.output_dir, f"{patent_id}_error.html")
                    with open(debug_path, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f"Saved error response to: {debug_path}")
                return False
            
            # Parse the page with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract the title
            title = ""
            try:
                title_tag = soup.find('title')
                if title_tag and title_tag.text:
                    title = title_tag.text.strip()
                    # Remove "Google Patents" and other common suffixes from title
                    title = re.sub(r' - Google Patents$', '', title)
                    title = re.sub(r' - Patents\.com - Google Patents$', '', title)
                    
                    # Remove patent ID from title (it's often included at the beginning)
                    title = re.sub(f'^{patent_id} - ', '', title)
                    
                    print(f"Patent title: {title}")
            except Exception as e:
                print(f"Error extracting title: {str(e)}")
            
            # Sanitize title for filename use
            sanitized_title = ""
            if title:
                # Replace invalid filename characters and limit length
                sanitized_title = re.sub(r'[\\/*?:"<>|]', '', title)  # Remove invalid filename chars
                sanitized_title = re.sub(r'\s+', '_', sanitized_title)  # Replace spaces with underscores
                sanitized_title = sanitized_title[:100]  # Limit length to avoid too long filenames
            
            # Look for PDF links
            pdf_url = None
            
            # Method 1: Look for PDF links in the page
            pdf_links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and '.pdf' in href.lower():
                    pdf_links.append(href)
            
            if pdf_links:
                for link in pdf_links:
                    # Make sure the URL is absolute
                    if not link.startswith('http'):
                        if link.startswith('/'):
                            link = f"https://patents.google.com{link}"
                        else:
                            link = f"https://patents.google.com/{link}"
                    
                    pdf_url = link
                    print(f"Found PDF link: {pdf_url}")
                    break
            
            # Method 2: Try common PDF patterns
            if not pdf_url:
                # Try to extract from patterns in the page
                pdf_pattern = r'(https://patentimages\.storage\.googleapis\.com/[^"\']+\.pdf)'
                pdf_matches = re.findall(pdf_pattern, response.text)
                
                if pdf_matches:
                    pdf_url = pdf_matches[0]
                    print(f"Found PDF URL in source: {pdf_url}")
            
            # Method 3: Construct a PDF URL (fallback)
            if not pdf_url:
                # Common format for Google Patents PDF URLs
                base_id = re.sub(r'([A-Z]\d+)[A-Z]\d*$', r'\1', patent_id)
                pdf_url = f"https://patentimages.storage.googleapis.com/pdfs/{base_id}.pdf"
                print(f"Using constructed PDF URL: {pdf_url}")
            
            # Download the PDF if found
            if pdf_url:
                try:
                    # Create filename with patent ID and title if available
                    if sanitized_title:
                        pdf_filename = f"{patent_id}_{sanitized_title}.pdf"
                    else:
                        pdf_filename = f"{patent_id}.pdf"
                    
                    pdf_path = os.path.join(self.output_dir, pdf_filename)
                    
                    pdf_response = self.session.get(pdf_url, stream=True)
                    
                    # Check if the response is actually a PDF
                    if pdf_response.status_code == 200 and 'application/pdf' in pdf_response.headers.get('Content-Type', ''):
                        with open(pdf_path, 'wb') as f:
                            for chunk in pdf_response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        print(f"Successfully downloaded PDF to: {pdf_path}")
                        return True
                    else:
                        print(f"Failed to download PDF. Status code: {pdf_response.status_code}")
                except Exception as e:
                    print(f"Error downloading PDF: {str(e)}")
            
            # If we couldn't get the PDF, save the HTML as a fallback
            if sanitized_title:
                html_filename = f"{patent_id}_{sanitized_title}.html"
            else:
                html_filename = f"{patent_id}.html"
                
            html_path = os.path.join(self.output_dir, html_filename)
            
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"Saved HTML source to: {html_path}")
            
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
            print("No patents found or could not retrieve search results.")
            print("Google Patents is a single-page app that requires JavaScript.")
            print("Consider using the Selenium-based downloader instead.")
            return 0, 0
        
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
    parser = argparse.ArgumentParser(description='Download patents from Google Patents')
    parser.add_argument('query', type=str, nargs='?', help='Search query for patents')
    parser.add_argument('--max', type=int, default=10, help='Maximum number of patents to download')
    parser.add_argument('--output', type=str, default='patents', help='Output directory for downloaded patents')
    parser.add_argument('--language', type=str, default='en', help='Language for patents')
    parser.add_argument('--patent-id', type=str, help='Download a specific patent by ID')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    downloader = PatentDownloader(output_dir=args.output, debug=args.debug)
    
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
            print("Google Patents is a single-page application that requires JavaScript.")
            print("Consider using the selenium_patent_downloader.py script instead.")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main() 