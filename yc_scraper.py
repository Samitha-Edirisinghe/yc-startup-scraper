import requests
import pandas as pd
import time
import random
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from urllib.parse import quote_plus
import logging
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class YCStartupScraper:
    def __init__(self, max_startups=500, use_headless=True):
        """
        Initialize the YC Startup Scraper
        """
        self.max_startups = max_startups
        self.startups_data = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        # Initialize Selenium driver
        chrome_options = Options()
        if use_headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def discover_api_endpoint(self):
        """
        Simplified API discovery without performance logs
        """
        logger.info("Discovering API endpoints...")
        
        # Try known YC API endpoints
        test_endpoints = [
            "https://api.ycombinator.com/v0.1/companies",
            "https://www.ycombinator.com/graphql",
            "https://api.ycombinator.com/graphql",
            "https://www.ycombinator.com/companies/companies.json"
        ]
        
        for endpoint in test_endpoints:
            try:
                response = self.session.get(endpoint, timeout=10)
                if response.status_code == 200:
                    logger.info(f"Found accessible endpoint: {endpoint}")
                    return endpoint
            except:
                continue
        
        logger.warning("Could not find direct API. Will use web scraping approach.")
        return None
    
    def scrape_via_api(self, api_endpoint):
        """
        Scrape using the discovered API endpoint
        """
        logger.info(f"Scraping via API: {api_endpoint}")
        
        try:
            # Try GraphQL API approach
            if 'graphql' in api_endpoint:
                graphql_query = {
                    "query": """
                    query {
                        companies {
                            id
                            name
                            batch
                            shortDescription
                            website
                        }
                    }
                    """
                }
                
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                }
                
                response = self.session.post(api_endpoint, json=graphql_query, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                if 'data' in data and 'companies' in data['data']:
                    companies = data['data']['companies']
                    for company in companies[:self.max_startups]:
                        self.startups_data.append({
                            'name': company.get('name', 'N/A'),
                            'batch': company.get('batch', 'N/A'),
                            'description': company.get('shortDescription', '')[:200],
                            'founders': [],
                            'linkedin_urls': [],
                            'company_url': company.get('website', '')
                        })
                    
                    logger.info(f"Successfully scraped {len(self.startups_data)} companies via GraphQL API")
                    return
                else:
                    logger.error("GraphQL response doesn't contain expected data structure")
            
            # Try REST API approach
            response = self.session.get(api_endpoint, timeout=30)
            response.raise_for_status()
            
            try:
                data = response.json()
                
                # Handle different response structures
                if isinstance(data, list):
                    companies = data
                elif isinstance(data, dict):
                    if 'companies' in data:
                        companies = data['companies']
                    elif 'results' in data:
                        companies = data['results']
                    elif 'data' in data:
                        companies = data['data']
                    else:
                        # Try to extract companies from dictionary
                        companies = []
                        for key, value in data.items():
                            if isinstance(value, list):
                                companies = value
                                break
                else:
                    companies = []
                
                for i, company in enumerate(companies[:self.max_startups]):
                    # Extract data with fallbacks
                    name = company.get('name') or company.get('companyName') or company.get('title', f'Company_{i+1}')
                    batch = company.get('batch') or company.get('ycBatch') or company.get('season', 'Unknown')
                    description = company.get('shortDescription') or company.get('description') or company.get('pitch', '')[:200]
                    
                    # Extract founders if available
                    founders = []
                    linkedin_urls = []
                    if 'founders' in company:
                        if isinstance(company['founders'], list):
                            for founder in company['founders']:
                                if isinstance(founder, dict):
                                    founders.append(founder.get('name', ''))
                                    linkedin_urls.append(founder.get('linkedinUrl') or founder.get('linkedin', ''))
                                elif isinstance(founder, str):
                                    founders.append(founder)
                    
                    self.startups_data.append({
                        'name': name,
                        'batch': batch,
                        'description': description,
                        'founders': founders,
                        'linkedin_urls': linkedin_urls,
                        'company_url': company.get('website') or company.get('url') or ''
                    })
                    
                    if (i + 1) % 50 == 0:
                        logger.info(f"Processed {i + 1} companies...")
                
                logger.info(f"Successfully scraped {len(self.startups_data)} companies via API")
                
            except json.JSONDecodeError:
                logger.error(f"API returned non-JSON response. Content type: {response.headers.get('content-type')}")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
        except Exception as e:
            logger.error(f"Error in API scraping: {e}")
    
    def scrape_via_selenium(self):
        """
        Main Selenium scraping method
        """
        logger.info("Starting Selenium scraping...")
        
        url = "https://www.ycombinator.com/companies"
        self.driver.get(url)
        time.sleep(3)
        
        # Scroll to load more companies (infinite scroll)
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 20
        
        while len(self.startups_data) < self.max_startups and scroll_attempts < max_scroll_attempts:
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Extract company data
            self.extract_companies_from_page()
            
            # Check if we need to scroll more
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                scroll_attempts += 1
                logger.info(f"No new content loaded. Attempt {scroll_attempts}/{max_scroll_attempts}")
                # Try clicking "Load More" if it exists
                try:
                    load_more_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Load More') or contains(text(), 'Show More')]")
                    load_more_button.click()
                    time.sleep(2)
                except:
                    pass
            else:
                scroll_attempts = 0
                last_height = new_height
            
            logger.info(f"Companies scraped so far: {len(self.startups_data)}")
    
    def extract_companies_from_page(self):
        """
        Extract companies from the current page view
        """
        try:
            # Look for company cards using multiple selector strategies
            selectors = [
                "a[href*='/companies/']",
                "div[class*='company']",
                "div[class*='Company']",
                "._company_lx2j5_1",
                "._companyContainer_1ogg8_1"
            ]
            
            company_elements = []
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 10:  # Found substantial number of elements
                        company_elements = elements
                        logger.info(f"Found {len(elements)} elements with selector: {selector}")
                        break
                except:
                    continue
            
            # Process each company element
            for element in company_elements[len(self.startups_data):]:
                if len(self.startups_data) >= self.max_startups:
                    break
                
                try:
                    company_data = self.extract_company_data(element)
                    if company_data:
                        self.startups_data.append(company_data)
                        if len(self.startups_data) % 10 == 0:
                            logger.info(f"Scraped {len(self.startups_data)} companies")
                except Exception as e:
                    logger.debug(f"Error extracting company data: {e}")
        
        except Exception as e:
            logger.error(f"Error in extract_companies_from_page: {e}")
    
    def extract_company_data(self, element):
        """
        Extract data from a single company element
        """
        try:
            # Get text content
            text = element.text.strip()
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Extract name (usually first line)
            name = lines[0] if lines else "Unknown"
            
            # Extract batch using regex
            batch = "Unknown"
            for line in lines:
                batch_match = re.search(r'(W|S|F)\d{2,4}', line, re.IGNORECASE)
                if batch_match:
                    batch = batch_match.group(0).upper()
                    break
            
            # Extract description (look for the longest line that's not the name or batch)
            description = ""
            for line in lines[1:]:  # Skip first line (name)
                if not re.search(r'(W|S|F)\d{2,4}', line, re.IGNORECASE) and len(line) > 10:
                    description = line[:200]
                    break
            
            # Get company URL
            company_url = ""
            try:
                href = element.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        company_url = f"https://www.ycombinator.com{href}"
                    elif "ycombinator.com/companies/" in href:
                        company_url = href
            except:
                pass
            
            return {
                'name': name,
                'batch': batch,
                'description': description,
                'founders': [],
                'linkedin_urls': [],
                'company_url': company_url
            }
            
        except Exception as e:
            logger.debug(f"Error in extract_company_data: {e}")
            return None
    
    def enrich_founder_data(self):
        """
        Enrich startup data with founder information
        """
        logger.info(f"Starting founder data enrichment for {len(self.startups_data)} startups...")
        
        for i, startup in enumerate(self.startups_data):
            if i % 10 == 0:
                logger.info(f"Enriching startup {i+1}/{len(self.startups_data)}...")
            
            # Skip if we already have founder data
            if startup['founders']:
                continue
            
            # Try to get founder data from company page
            if startup.get('company_url'):
                try:
                    self.driver.get(startup['company_url'])
                    time.sleep(1)
                    
                    # Try to find founder names
                    founder_selectors = [
                        "//*[contains(text(), 'Founder') or contains(text(), 'Co-founder') or contains(text(), 'CEO')]/following-sibling::div",
                        "//h3[contains(text(), 'Team') or contains(text(), 'Founder')]/following::div",
                        "//*[contains(@class, 'founder')]",
                        "//*[contains(@class, 'team-member')]"
                    ]
                    
                    for selector in founder_selectors:
                        try:
                            elements = self.driver.find_elements(By.XPATH, selector)
                            for element in elements[:3]:  # Limit to 3 founders
                                text = element.text.strip()
                                if text and len(text.split()) >= 2 and len(text) < 50:
                                    startup['founders'].append(text)
                                    
                                    # Try to find LinkedIn profile
                                    linkedin_url = self.find_linkedin_profile(text, startup['name'])
                                    if linkedin_url:
                                        startup['linkedin_urls'].append(linkedin_url)
                        except:
                            continue
                    
                    # If still no founders, try a broader search
                    if not startup['founders']:
                        page_text = self.driver.find_element(By.TAG_NAME, "body").text
                        # Look for patterns that might indicate founder names
                        import re
                        # Simple pattern: Capitalized words (likely names)
                        potential_names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', page_text[:2000])
                        for name in potential_names[:2]:  # Take first 2 as potential founders
                            startup['founders'].append(name)
                
                except Exception as e:
                    logger.debug(f"Could not enrich {startup['name']}: {e}")
            
            time.sleep(0.5)  # Rate limiting
    
    def find_linkedin_profile(self, founder_name, company_name):
        """
        Find LinkedIn profile for a founder
        """
        try:
            # Search on Google
            search_query = f"{founder_name} {company_name} LinkedIn"
            self.driver.get(f"https://www.google.com/search?q={quote_plus(search_query)}")
            time.sleep(1)
            
            # Look for LinkedIn links
            links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='linkedin.com/in/']")
            if links:
                linkedin_url = links[0].get_attribute("href")
                # Clean URL
                if '&' in linkedin_url:
                    linkedin_url = linkedin_url.split('&')[0]
                return linkedin_url
        
        except:
            pass
        
        return None
    
    def save_to_csv(self, filename="yc_startups.csv"):
        """
        Save scraped data to CSV file
        """
        if not self.startups_data:
            logger.warning("No data to save")
            return None
        
        # Prepare data for CSV
        csv_data = []
        for startup in self.startups_data:
            csv_data.append({
                'Company Name': startup['name'],
                'Batch': startup['batch'],
                'Short Description': startup['description'],
                'Founder Name(s)': '; '.join(startup['founders']) if startup['founders'] else 'Not found',
                'Founder LinkedIn URL(s)': '; '.join(startup['linkedin_urls']) if startup['linkedin_urls'] else 'Not found'
            })
        
        df = pd.DataFrame(csv_data)
        
        # Save to CSV
        df.to_csv(filename, index=False, encoding='utf-8')
        logger.info(f"Data saved to {filename} ({len(df)} rows)")
        
        # Also save to Google Sheets format
        gsheet_filename = filename.replace('.csv', '_google_sheets.csv')
        df.to_csv(gsheet_filename, index=False)
        logger.info(f"Google Sheets format saved to {gsheet_filename}")
        
        return df
    
    def run(self):
        """
        Main execution method
        """
        logger.info(f"Starting YC Startup Scraper (target: {self.max_startups} startups)")
        
        start_time = time.time()
        
        try:
            # First try API approach
            api_endpoint = self.discover_api_endpoint()
            
            if api_endpoint:
                logger.info(f"Attempting to use API endpoint: {api_endpoint}")
                self.scrape_via_api(api_endpoint)
            
            # If API didn't get enough data or failed, use Selenium
            if len(self.startups_data) < self.max_startups:
                logger.info(f"Using Selenium to scrape remaining companies. Currently have: {len(self.startups_data)}")
                self.scrape_via_selenium()
            
            # Enrich founder data
            if self.startups_data:
                logger.info("Enriching founder data...")
                self.enrich_founder_data()
            
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
        finally:
            self.driver.quit()
        
        # Save results
        if self.startups_data:
            df = self.save_to_csv()
            
            # Summary statistics
            total_startups = len(self.startups_data)
            startups_with_founders = sum(1 for s in self.startups_data if s['founders'])
            startups_with_linkedin = sum(1 for s in self.startups_data if s['linkedin_urls'])
            
            print(f"\n{'='*60}")
            print("SCRAPING COMPLETE - SUMMARY")
            print('='*60)
            print(f"Total startups scraped: {total_startups}")
            print(f"Startups with founder info: {startups_with_founders} ({startups_with_founders/total_startups:.1%})")
            print(f"Startups with LinkedIn URLs: {startups_with_linkedin} ({startups_with_linkedin/total_startups:.1%})")
            print(f"Time elapsed: {time.time() - start_time:.2f} seconds")
            
            # Print sample
            if total_startups > 0:
                print(f"\nSample of scraped data (first 3):")
                print('-' * 60)
                for i, startup in enumerate(self.startups_data[:3]):
                    print(f"\n{i+1}. {startup['name']} ({startup['batch']})")
                    print(f"   Description: {startup['description'][:100]}...")
                    print(f"   Founders: {', '.join(startup['founders'][:2]) if startup['founders'] else 'None'}")
                    print(f"   LinkedIn URLs: {len(startup['linkedin_urls'])}")
            
            print(f"\n Complete dataset saved to 'yc_startups.csv' ({total_startups} companies)")
        
        else:
            print(" No data was scraped")
        
        return self.startups_data


# Main execution
if __name__ == "__main__":
    print("Y Combinator Startup Scraper")
    print("=" * 50)
    
    try:
        # Configuration
        MAX_STARTUPS = 500
        HEADLESS_MODE = False  # Set to True for production, False for debugging
        
        # Create scraper instance
        scraper = YCStartupScraper(max_startups=MAX_STARTUPS, use_headless=HEADLESS_MODE)
        
        # Run scraper
        results = scraper.run()
        
        if results:
            print(f"\n Successfully scraped {len(results)} YC startups!")
            print("Files created:")
            print("   - yc_startups.csv (main data file)")
            print("   - yc_startups_google_sheets.csv (Google Sheets format)")
            print("\n Neext steps:")
            print("   1. Submit yc_startups.csv as your main deliverable")
            print("   2. Include this Python script")
            print("   3. Record a brief summary on komododecks.com")
        else:
            print("\n Scraping failed. Check the logs above for errors.")
            
    except KeyboardInterrupt:
        print("\n\n️ Scraping interrupted by user.")
    except Exception as e:
        print(f"\n Fatal error: {e}")
        import traceback
        traceback.print_exc()
