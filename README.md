# Y Combinator Startup Scraper

## Overview
This project scrapes approximately **500 startups** from the Y Combinator company directory and enriches each record with founder names and LinkedIn profiles. The solution uses a **hybrid scraping strategy**—API discovery first, with a Selenium-based fallback—to ensure reliable data coverage despite dynamic content loading.

## Data Extracted
For each startup, the following fields are collected:

- Company Name  
- YC Batch (e.g., W25, S24)  
- Short Description  
- Founder Name(s)  
- Founder LinkedIn URL(s)

## Approach Summary
- **API-first strategy:** Attempts to use Y Combinator’s internal API endpoints when available  
- **Selenium fallback:** Handles infinite scroll and dynamic rendering when API access is restricted  
- **Infinite scroll handling:** Automatically scrolls and detects newly loaded companies until the target count is reached  
- **Founder enrichment:** Visits individual company pages to extract founder names  
- **LinkedIn discovery:** Uses Google/DuckDuckGo search with careful rate limiting  
- **Error resilience:** Multiple selector fallbacks, logging, and intelligent delays  

## Project Structure
```
.
├── yc_scraper.py
├── yc_startups.csv
├── yc_startups_google_sheets.csv
├── requirements.txt
└── README.md
```

## Setup & Installation
```bash
pip install -r requirements.txt
```

## Running the Scraper
```bash
python yc_scraper.py
```

### Configuration Options
These values can be adjusted inside `yc_scraper.py`:
```python
MAX_STARTUPS = 500
HEADLESS_MODE = False
```

## Output
- Clean CSV files with labeled columns  
- ~500 unique YC startups scraped  
- Batch detected using regex patterns  
- Founder and LinkedIn data included where publicly available  

## Performance & Reliability
- Scroll-based loading to prevent duplicate processing  
- Persistent sessions for faster requests  
- Configurable rate limits  
- Detailed logging for progress tracking  

## Notes
This project was built strictly for **educational and assessment purposes** using publicly available information, with conservative request timing to respect external services.
