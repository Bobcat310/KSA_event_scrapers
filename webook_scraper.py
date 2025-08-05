from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import csv
import time
import re
from typing import List, Dict, Optional

def log(msg: str):
    print(f"[LOG] {msg}")

class WeBookScraper:
    def __init__(self, headless: bool = True):
        self.setup_driver(headless)
        self.wait = WebDriverWait(self.driver, 15)
        
    def setup_driver(self, headless: bool):
        """Setup Chrome driver with options"""
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # Disable images and CSS for faster loading
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            log("Chrome driver initialized successfully")
        except Exception as e:
            log(f"Error initializing Chrome driver: {e}")
            log("Make sure ChromeDriver is installed and in your PATH")
            raise
    
    def accept_cookies(self) -> bool:
        """Accept cookies if banner appears"""
        try:
            log("Checking for cookie banner...")
            
            # Wait for page to load first
            time.sleep(3)
            
            # Look for cookie banner and accept button
            cookie_selectors = [
                'button:contains("Accept all")',
                'button[data-testid*="cookie"]',
                'button[class*="cookie"]',
                'button:contains("Accept")',
                '[id*="cookie"] button',
                '.cookie button'
            ]
            
            for selector in cookie_selectors:
                try:
                    if 'contains' in selector:
                        # For text-based selectors, use XPath
                        xpath = f"//button[contains(text(), 'Accept all') or contains(text(), 'Accept')]"
                        button = self.driver.find_element(By.XPATH, xpath)
                    else:
                        button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if button.is_displayed():
                        log("Found cookie accept button, clicking...")
                        button.click()
                        time.sleep(2)
                        return True
                        
                except NoSuchElementException:
                    continue
            
            log("No cookie banner found or already accepted")
            return True
            
        except Exception as e:
            log(f"Error handling cookies: {e}")
            return False
    
    def wait_for_content_load(self) -> bool:
        """Wait for dynamic content to load"""
        try:
            log("Waiting for content to load...")
            
            # Wait for React app to load
            self.wait.until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Wait for React/JavaScript to initialize
            time.sleep(8)  # Increased wait time
            
            # Try to wait for specific content indicators
            content_loaded = False
            max_attempts = 10
            
            for attempt in range(max_attempts):
                log(f"Content check attempt {attempt + 1}/{max_attempts}")
                
                # Check for various indicators that content has loaded
                indicators = [
                    'a[href*="experience"]',
                    '[data-testid*="item"]', 
                    '.grid a',
                    'h1, h2, h3',
                    'img[alt*="Session"]',
                    'img[alt*="Fast Fit"]',
                    '[class*="card"]',
                    'div[class*="grid"]',
                    'button:contains("Book")',
                    'span:contains("From")'
                ]
                
                for indicator in indicators:
                    try:
                        if 'contains' in indicator:
                            # Use XPath for text-based searches
                            if 'Book' in indicator:
                                elements = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Book')]")
                            elif 'From' in indicator:
                                elements = self.driver.find_elements(By.XPATH, "//span[contains(text(), 'From')]")
                            else:
                                elements = []
                        else:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                        
                        if elements:
                            log(f"✅ Content loaded - found {len(elements)} elements with: {indicator}")
                            content_loaded = True
                            break
                    except Exception as e:
                        continue
                
                if content_loaded:
                    break
                
                # Additional wait between attempts
                time.sleep(3)
                
                # Try scrolling to trigger content loading
                if attempt % 3 == 0:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    self.driver.execute_script("window.scrollTo(0, 0);")
            
            # Final check - even if no specific indicators found, check if page content increased
            page_source_length = len(self.driver.page_source)
            log(f"Final page source length: {page_source_length} characters")
            
            if page_source_length > 10000:  # Reasonable threshold for loaded content
                log("✅ Content appears to be loaded based on page size")
                content_loaded = True
            
            return content_loaded
            
        except TimeoutException:
            log("⏰ Timeout waiting for content to load")
            return False
        except Exception as e:
            log(f"❌ Error waiting for content: {e}")
            return False
    
    def get_event_links(self) -> List[str]:
        """Extract event links from the page"""
        log("Extracting event links...")
        
        event_links = []
        
        # First, let's see what's actually on the page
        page_source = self.driver.page_source
        log(f"Page source length: {len(page_source)} characters")
        
        # Save current page for debugging
        with open('webook_current_page_debug.html', 'w', encoding='utf-8') as f:
            f.write(page_source)
        log("Saved current page to webook_current_page_debug.html")
        
        # Try different approaches to find event links
        all_links = self.driver.find_elements(By.TAG_NAME, 'a')
        log(f"Found {len(all_links)} total anchor tags")
        
        # Check all links for potential events
        for link in all_links:
            try:
                href = link.get_attribute('href')
                text = link.text.strip()
                classes = link.get_attribute('class') or ''
                data_testid = link.get_attribute('data-testid') or ''
                
                if href:
                    log(f"Found link: {href} | text: '{text[:50]}' | testid: '{data_testid}'")
                    
                    # Look for experience links
                    if '/en/experiences/' in href or '/experience' in href:
                        if href not in event_links:
                            event_links.append(href)
                            log(f"✅ Added event link: {href}")
                    
                    # Also check for links with event-related text
                    elif any(keyword in text.lower() for keyword in ['session', 'fit', 'training', 'workout', 'fast fit']):
                        if href not in event_links:
                            event_links.append(href)
                            log(f"✅ Added event link (by text): {href}")
            except Exception as e:
                continue
        
        # If no links found, try searching in page source directly
        if not event_links:
            log("No direct links found, searching page source...")
            
            # Look for href patterns in the HTML source
            import re
            href_patterns = [
                r'href=["\']([^"\']*?/en/experiences/[^"\']*?)["\']',
                r'href=["\']([^"\']*?experience[^"\']*?)["\']'
            ]
            
            for pattern in href_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                for match in matches:
                    if match.startswith('/'):
                        full_url = f"https://webook.com{match}"
                    elif match.startswith('http'):
                        full_url = match
                    else:
                        continue
                    
                    if full_url not in event_links:
                        event_links.append(full_url)
                        log(f"✅ Found event URL in source: {full_url}")
        
        # Try clicking load more or search buttons if present
        if not event_links:
            log("Trying to trigger content loading...")
            try:
                # Look for search button
                search_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Search') or contains(@class, 'search')]")
                for button in search_buttons:
                    if button.is_displayed():
                        log("Clicking search button...")
                        button.click()
                        time.sleep(5)
                        break
                
                # Look for load more buttons
                load_more_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Load') or contains(text(), 'More') or contains(@class, 'load')]")
                for button in load_more_buttons:
                    if button.is_displayed():
                        log("Clicking load more button...")
                        button.click()
                        time.sleep(5)
                        break
                
                # Try scrolling to bottom to trigger infinite scroll
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                
                # Re-check for links after interactions
                all_links = self.driver.find_elements(By.TAG_NAME, 'a')
                for link in all_links:
                    try:
                        href = link.get_attribute('href')
                        if href and ('/en/experiences/' in href or '/experience' in href):
                            if href not in event_links:
                                event_links.append(href)
                                log(f"✅ Found event link after interaction: {href}")
                    except:
                        continue
                        
            except Exception as e:
                log(f"Error during content loading attempts: {e}")
        
        # If still no events, let's try alternative URLs or direct navigation
        if not event_links:
            log("No events found in search, trying alternative approaches...")
            
            # Try different search terms or pages
            alternative_urls = [
                "https://webook.com/en/search?q=Saudi+Arabia",
                "https://webook.com/en/search?q=Riyadh", 
                "https://webook.com/en/search?q=fitness",
                "https://webook.com/en/search?q=Fast+Fit",
                "https://webook.com/en/experiences",
                "https://webook.com/en/"
            ]
            
            for alt_url in alternative_urls:
                try:
                    log(f"Trying alternative URL: {alt_url}")
                    self.driver.get(alt_url)
                    time.sleep(5)
                    
                    links = self.driver.find_elements(By.TAG_NAME, 'a')
                    for link in links:
                        href = link.get_attribute('href')
                        if href and '/en/experiences/' in href:
                            if href not in event_links:
                                event_links.append(href)
                                log(f"✅ Found event link from {alt_url}: {href}")
                    
                    if event_links:
                        break
                        
                except Exception as e:
                    log(f"Error trying {alt_url}: {e}")
                    continue
        
        log(f"🔍 Total unique event links found: {len(event_links)}")
        return event_links
    
    def extract_event_details(self, url: str) -> Dict[str, str]:
        """Extract details from individual event page"""
        log(f"Extracting details from: {url}")
        
        try:
            self.driver.get(url)
            self.wait_for_content_load()
            
            # Initialize data structure
            event_data = {
                'Site': 'webook.com',
                'Name': 'N/A',
                'Start Date': 'N/A',
                'End Date': 'N/A',
                'Location': 'N/A',
                'Price': 'N/A',
                'Description': 'N/A',
                'URL': url
            }
            
            # Extract name
            name_selectors = [
                'h1[class*="heading"]',
                'h1',
                '[data-testid="event-title"]',
                '.title'
            ]
            
            for selector in name_selectors:
                try:
                    name_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    name = name_element.text.strip()
                    if name and len(name) > 5:
                        event_data['Name'] = name
                        log(f"Found name: {name}")
                        break
                except:
                    continue
            
            # Extract dates
            page_text = self.driver.page_source
            date_patterns = [
                r'(\d{1,2}\s+\w+\s+\d{4})\s*-\s*(\d{1,2}\s+\w+\s+\d{4})',
                r'(\d{1,2}\s+\w+\s+\d{4})'
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, page_text)
                if matches:
                    if len(matches[0]) == 2:  # Date range
                        event_data['Start Date'] = matches[0][0]
                        event_data['End Date'] = matches[0][1]
                    else:  # Single date
                        event_data['Start Date'] = matches[0]
                    break
            
            # Extract location
            location_selectors = [
                '[class*="location"]',
                'p:contains("Saudi Arabia")',
                '[data-testid*="location"]'
            ]
            
            # Use XPath for text-based search
            try:
                location_element = self.driver.find_element(
                    By.XPATH, 
                    "//p[contains(text(), 'Saudi Arabia') or contains(text(), 'Riyadh') or contains(text(), 'Jeddah')]"
                )
                event_data['Location'] = location_element.text.strip()
                log(f"Found location: {event_data['Location']}")
            except:
                # Fallback to page text search
                location_match = re.search(r'([^,\n]+,?\s*Saudi Arabia)', page_text, re.IGNORECASE)
                if location_match:
                    event_data['Location'] = location_match.group(1).strip()
            
            # Extract price
            try:
                price_element = self.driver.find_element(
                    By.XPATH, 
                    "//span[contains(text(), 'From')]/following-sibling::*//span[text()[matches(.,'^\\d+$')]] | //span[text()[matches(.,'^\\d+$')]]"
                )
                price = price_element.text.strip()
                if price.isdigit():
                    event_data['Price'] = price
                    log(f"Found price: {price}")
            except:
                # Fallback to text search
                price_match = re.search(r'(?:From\s+)?(\d+)(?:\s*SAR|\s*SR)?', page_text)
                if price_match:
                    event_data['Price'] = price_match.group(1)
            
            # Extract description
            description_selectors = [
                '[data-testid="event-description"]',
                'h2:contains("About") + *',
                '.description',
                '[class*="about"]'
            ]
            
            try:
                # Look for "About" section
                about_heading = self.driver.find_element(By.XPATH, "//h2[contains(text(), 'About')]")
                # Get the next sibling or parent's next content
                desc_container = about_heading.find_element(By.XPATH, "./following-sibling::*")
                description = desc_container.text.strip()
                if description and len(description) > 20:
                    event_data['Description'] = description[:500] + '...' if len(description) > 500 else description
                    log(f"Found description: {description[:100]}...")
            except:
                # Fallback: look for any substantial text content
                try:
                    text_elements = self.driver.find_elements(By.XPATH, "//p[string-length(text()) > 50]")
                    for elem in text_elements:
                        text = elem.text.strip()
                        if any(keyword in text.lower() for keyword in ['session', 'experience', 'training', 'workout']):
                            event_data['Description'] = text[:500] + '...' if len(text) > 500 else text
                            break
                except:
                    pass
            
            log(f"Extracted: {event_data['Name']} | {event_data['Location']} | {event_data['Price']}")
            return event_data
            
        except Exception as e:
            log(f"Error extracting details from {url}: {e}")
            return {
                'Site': 'webook.com',
                'Name': 'Error',
                'Start Date': 'N/A',
                'End Date': 'N/A',
                'Location': 'N/A',
                'Price': 'N/A',
                'Description': f'Error: {str(e)}',
                'URL': url
            }
    
    def scrape_events(self) -> List[Dict[str, str]]:
        """Main scraping method"""
        log("Starting WeBook.com scraping with Selenium...")
        
        try:
            # Navigate to search page
            search_url = "https://webook.com/en/search?q=KSA"
            log(f"🌐 Navigating to: {search_url}")
            self.driver.get(search_url)
            
            # Accept cookies
            self.accept_cookies()
            
            # Wait for content to load
            content_loaded = self.wait_for_content_load()
            if not content_loaded:
                log("⚠️  Content loading seems incomplete, but proceeding...")
            
            # Save page source for debugging
            with open('webook_selenium_debug.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            log("💾 Saved loaded page source to webook_selenium_debug.html")
            
            # Get event links
            event_links = self.get_event_links()
            
            # If no links found through scraping, try known event URLs as fallback
            if not event_links:
                log("🔄 No events found through scraping, trying fallback URLs...")
                
                # Based on the HTML snippets you provided, let's try some known patterns
                fallback_urls = [
                    "https://webook.com/en/experiences/introductory-session",
                    "https://webook.com/en/experiences/introductory-session-1", 
                    "https://webook.com/en/experiences/introductory-session-fast-fit-al-narjis-branch-ladies-gents",
                    "https://webook.com/en/experiences/introductory-session-fast-fit-al-khalidiyyah-branch-ladies-gents",
                    "https://webook.com/en/experiences/introductory-session-fast-fit-al-rakah-branch-ladies-gents",
                    "https://webook.com/en/experiences/introductory-session-fast-fit-al-waha-branch-gents-only"
                ]
                
                log(f"🎯 Testing {len(fallback_urls)} fallback URLs...")
                
                for url in fallback_urls:
                    try:
                        # Test if the URL exists
                        self.driver.get(url)
                        time.sleep(3)
                        
                        # Check if we get a valid page (not 404)
                        page_title = self.driver.title.lower()
                        if 'not found' not in page_title and '404' not in page_title and len(page_title) > 5:
                            event_links.append(url)
                            log(f"✅ Valid fallback URL found: {url}")
                        else:
                            log(f"❌ Invalid URL: {url}")
                            
                    except Exception as e:
                        log(f"❌ Error testing {url}: {e}")
                        continue
            
            if not event_links:
                log("❌ No event links found. Possible issues:")
                log("   1. Website structure has changed")
                log("   2. Geographic restrictions")
                log("   3. Search results are empty for 'KSA'")
                log("   4. JavaScript anti-bot detection")
                log("   5. Site may require login or specific headers")
                return []
            
            # Extract details from each event
            events = []
            for i, link in enumerate(event_links, 1):
                log(f"🎫 Processing event {i}/{len(event_links)}: {link}")
                try:
                    event_data = self.extract_event_details(link)
                    events.append(event_data)
                    
                    # Be respectful - add delay between requests
                    time.sleep(3)
                    
                except Exception as e:
                    log(f"❌ Error processing event {i}: {e}")
                    # Add a placeholder entry so we don't lose the URL
                    events.append({
                        'Site': 'webook.com',
                        'Name': f'Error processing event {i}',
                        'Start Date': 'N/A',
                        'End Date': 'N/A', 
                        'Location': 'N/A',
                        'Price': 'N/A',
                        'Description': f'Error: {str(e)}',
                        'URL': link
                    })
                    continue
            
            return events
            
        except Exception as e:
            log(f"❌ Error in main scraping: {e}")
            return []
    
    def save_to_csv(self, events: List[Dict[str, str]], filename: str = "webook_events.csv"):
        """Save events to CSV with proper formatting"""
        if not events:
            log("No events to save")
            return
        
        # Define clear column headers
        fieldnames = [
            'Site',           # Source website
            'Name',           # Event name
            'Start Date',     # Event start date
            'End Date',       # Event end date (if applicable)
            'Location',       # Event location
            'Price',          # Event price
            'Description',    # Event description
            'URL'            # Event page URL
        ]
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # Clean and validate data before writing
                cleaned_events = []
                for event in events:
                    cleaned_event = {}
                    for field in fieldnames:
                        value = event.get(field, 'N/A')
                        # Clean the value
                        if isinstance(value, str):
                            value = value.strip()
                            # Remove any problematic characters for CSV
                            value = re.sub(r'[\r\n]+', ' ', value)
                            value = re.sub(r'\s+', ' ', value)
                        cleaned_event[field] = value
                    cleaned_events.append(cleaned_event)
                
                writer.writerows(cleaned_events)
            
            log(f"✅ Successfully saved {len(events)} events to {filename}")
            
            # Print summary statistics
            log("\n" + "="*50)
            log("SCRAPING SUMMARY")
            log("="*50)
            log(f"Total events extracted: {len(events)}")
            log(f"CSV file created: {filename}")
            
            # Count events by location
            locations = {}
            prices = []
            for event in cleaned_events:
                loc = event.get('Location', 'Unknown')
                locations[loc] = locations.get(loc, 0) + 1
                
                price = event.get('Price', 'N/A')
                if price != 'N/A' and price.isdigit():
                    prices.append(int(price))
            
            log(f"\nEvents by location:")
            for location, count in sorted(locations.items()):
                log(f"  {location}: {count} events")
            
            if prices:
                log(f"\nPrice range: {min(prices)} - {max(prices)} SAR")
                log(f"Average price: {sum(prices)//len(prices)} SAR")
            
            # Print detailed sample
            log(f"\nFirst 3 events preview:")
            log("-" * 50)
            for i, event in enumerate(cleaned_events[:3], 1):
                log(f"\n{i}. {event['Name']}")
                log(f"   📍 Location: {event['Location']}")
                log(f"   💰 Price: {event['Price']} SAR")
                log(f"   📅 Date: {event['Start Date']}")
                if event['End Date'] != 'N/A':
                    log(f"   📅 End Date: {event['End Date']}")
                log(f"   🔗 URL: {event['URL']}")
                if len(event['Description']) > 50:
                    log(f"   📝 Description: {event['Description'][:100]}...")
                else:
                    log(f"   📝 Description: {event['Description']}")
            
            log("="*50)
                
        except Exception as e:
            log(f"❌ Error saving CSV: {e}")
            raise
    
    def close(self):
        """Close the driver"""
        if hasattr(self, 'driver'):
            self.driver.quit()
            log("Driver closed")

def main():
    """Main execution function"""
    scraper = None
    start_time = time.time()
    
    try:
        log("🚀 Starting WeBook.com Event Scraper")
        log("="*50)
        
        # Set headless=False to see the browser in action (for debugging)
        scraper = WeBookScraper(headless=True)
        
        # Scrape events
        events = scraper.scrape_events()
        
        # Save to CSV with proper formatting
        if events:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"webook_events_{timestamp}.csv"
            scraper.save_to_csv(events, filename)
            
            # Also save a simple filename for easy access
            scraper.save_to_csv(events, "webook_events_latest.csv")
            
        else:
            log("❌ No events were extracted")
            log("Check the debug HTML files to see what was loaded:")
            log("  - webook_selenium_debug.html")
        
        # Final execution summary
        execution_time = time.time() - start_time
        log(f"\n⏱️  Total execution time: {execution_time:.2f} seconds")
        log("🏁 Scraping completed!")
        
    except KeyboardInterrupt:
        log("\n⚠️  Scraping interrupted by user")
    except Exception as e:
        log(f"❌ Main execution error: {e}")
        import traceback
        log(f"Full traceback: {traceback.format_exc()}")
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()