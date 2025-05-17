# Patent Scraper

A powerful set of Python tools for downloading patents from Google Patents, focused on chemistry, pharmaceutical, and scientific patents without requiring any API keys.

## Features

- **Topic-Based Patent Extraction**: Search and extract multiple patents based on topics
- **Direct Patent ID Downloads**: Download specific patents by their IDs (most reliable method)
- **Multiple Download Methods**: Both simple requests-based and robust Selenium-based downloaders
- **PDF and HTML Extraction**: Get patents in PDF format when available, with HTML fallback
- **Descriptive Filenames**: Files saved with both patent ID and title for easy identification
- **Duplicate Detection**: Smart handling of patent variants with the same base ID
- **Comprehensive Logging**: Detailed logs and debugging information
- **Command-Line Interface**: Easy to use in scripts and automation workflows

## Examples of Topics You Can Search

The script has been tested successfully with various scientific and technical topics including:
- Ammonia synthesis
- Vaccines
- Drug delivery
- Catalytic converters
- Polymer composites
- Antibiotics
- Carbon capture

## Requirements

- Python 3.6+
- Required Python packages (install using `pip install -r requirements.txt`):
  ```
  requests
  beautifulsoup4
  selenium
  urllib3
  ```
- For the Selenium-based downloader:
  - Google Chrome browser
  - ChromeDriver (matching your Chrome version)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/GrennMilo/PatentsScaper.git
   cd PatentsScaper
   ```

2. Install required packages:
   ```
   pip install -r requirements.txt
   ```

3. Ensure Chrome and ChromeDriver are installed for Selenium functionality

## Usage

### Topic-Based Extraction and Download (Recommended)

The most powerful approach is to use the topic extractor to search, extract, and download patents in one go:

```bash
python topic_patent_extractor.py "ammonia synthesis" --max 30 --visible --debug
```

This will:
1. Search for patents related to "ammonia synthesis"
2. Extract up to 30 patent IDs
3. Download each patent PDF with filename format: `PATENT_ID_Title_Of_The_Patent.pdf`
4. Provide detailed logs and save debugging information

Recent successful searches include:
- `python topic_patent_extractor.py "vaccines" --max 10 --visible --debug`
- `python topic_patent_extractor.py "ammonia" --max 15 --visible --debug`

### Downloading by Patent ID (Most Reliable Method)

For specific patents, use the patent ID directly:

```bash
python download_patents.py --patent-id US9370745B2 --debug
```

For better visibility during the process:

```bash
python selenium_patent_downloader.py --patent-id US10953088B2 --visible
```

### Different Downloader Scripts

This repository contains three main scripts:

1. **topic_patent_extractor.py** - Most comprehensive tool for topic searching and downloading
   ```
   python topic_patent_extractor.py "drug delivery" --max 20
   ```

2. **selenium_patent_downloader.py** - Robust downloader that handles JavaScript
   ```
   python selenium_patent_downloader.py "catalytic converter" --max 5
   ```

3. **patent_downloader.py** - Simple requests-based downloader (limited functionality)
   ```
   python patent_downloader.py --patent-id US10584047B2
   ```

4. **download_patents.py** - Wrapper script that combines the above tools
   ```
   python download_patents.py --patent-id US11833153B2
   ```

## Advanced Options

### Improved Filenames

All downloaded patents are saved using both the patent ID and title in the filename:

```
US10953088B2_Vaccine_compositions_for_porcine_epidemic_diarrhea_virus_and_porcine_deltacoronavirus.pdf
```

Benefits:
- Instantly identify a patent's subject from the filename
- Maintain proper organization and searchability
- Preserve the unique patent ID for reference
- Automatically sanitized to remove invalid characters

### Debugging Support

Enable debugging to get detailed information about the download process:

```bash
python topic_patent_extractor.py "carbon capture" --debug
```

With debugging enabled, the scripts will:
- Save screenshots of each step (with Selenium)
- Store HTML page sources
- Generate detailed logs
- Create JSON records of download status
- Help identify issues with searches or downloads

### Browser Visibility

When using Selenium-based downloaders, you can watch the browser in action:

```bash
python selenium_patent_downloader.py "antibiotics" --visible
```

## Command Line Arguments for Topic Patent Extractor

| Argument | Description | Default | Required |
|----------|-------------|---------|----------|
| `topic` | Topic to search for patents | | Yes |
| `--max` | Maximum number of patents to extract and download | 10 | No |
| `--output` | Output directory for downloaded patents | "patents" | No |
| `--visible` | Run Chrome in visible mode | False | No |
| `--debug` | Enable debug mode | False | No |

## Command Line Arguments for Individual Patent Tools

| Argument | Description | Default | Required |
|----------|-------------|---------|----------|
| `query` | Search query for patents | | Yes (unless using `--patent-id`) |
| `--max` | Maximum number of patents to download | 10 | No |
| `--output` | Output directory for patents | "patents" | No |
| `--language` | Language for patents | "en" | No |
| `--visible` | (Selenium only) Run Chrome in visible mode | False | No |
| `--patent-id` | Download a specific patent by ID | | No |
| `--debug` | Enable debug mode | False | No |

## Troubleshooting

### Common Issues and Solutions

1. **No patents found for search query**
   - **Cause**: Google Patents uses complex JavaScript that is difficult to scrape
   - **Solution**: Try using a more specific search term or use direct patent IDs

2. **Browser closes unexpectedly**
   - **Cause**: Session timeout or Chrome/ChromeDriver compatibility issues
   - **Solution**: Update Chrome and ChromeDriver to matching versions and use the `--visible` flag to monitor the process

3. **PDF downloads fail**
   - **Cause**: Patent might not have a PDF available or URL structure changed
   - **Solution**: The script will automatically save the HTML version as fallback

4. **Script crashes with Selenium errors**
   - **Cause**: Element not found due to page structure changes
   - **Solution**: Use the `--debug` flag to save screenshots and HTML for analysis

### Tips for Improved Results

1. **Use specific search terms**
   - More specific queries yield better results (e.g., "ammonia synthesis catalyst" vs just "ammonia")

2. **Prefer direct patent IDs**
   - When possible, search for patents manually first, then use their IDs with `--patent-id`

3. **Check debug information**
   - Enable `--debug` and examine screenshots in the `patents/debug` directory

4. **Handle rate limiting**
   - If you encounter 429 errors, add delays between downloads with the `--delay` option

## Project Structure

```
PatentsScaper/
├── topic_patent_extractor.py      # Main topic-based search and download tool
├── selenium_patent_downloader.py  # Selenium-based patent downloader
├── patent_downloader.py           # Simple requests-based downloader
├── download_patents.py            # Wrapper script for easy usage
├── requirements.txt               # Python dependencies
├── .gitignore                     # Git ignore configuration
├── README.md                      # This documentation
└── patents/                       # Output directory for patents
    └── .gitkeep                   # Placeholder to maintain directory structure
```

## License

MIT License

## Contributing

Contributions are welcome! Feel free to submit pull requests or open issues to improve the functionality.

## Acknowledgements

This tool was developed to help researchers download chemistry and pharmaceutical patents from Google Patents without requiring API keys. While Google Patents' structure as a single-page application presents challenges for automated extraction, this tool provides multiple approaches to maximize success rates. 