import requests
from bs4 import BeautifulSoup
import csv
from typing import List, Dict, Optional
import time
import re
from urllib.parse import urljoin, urlparse, unquote
import json

def log(msg: str):
    print(f"[LOG] {msg}")

class MeetupScraper:
    def __init__(self):
        self.base_url = "https://www.meetup.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        })
        self.events = []

    def get_search_urls(self) -> List[str]:
        """Generate search URLs for different Saudi Arabian cities"""
        
        cities = [
            ("Makkah", "Saudi Arabia"),
            ("Riyadh", "Saudi Arabia"), 
            ("Jeddah", "Saudi Arabia"),
            ("Dammam", "Saudi Arabia"),
            ("al-Khubar", "Saudi Arabia"),
            ("Medina", "Saudi Arabia"),
            ("Khobar", "Saudi Arabia"),
        ]
        
        search_urls = []
        
        for city, country in cities:
            # Different URL patterns for Meetup search
            url_patterns = [
                f"https://www.meetup.com/find/?location={city}--{country}&source=EVENTS",
                f"https://www.meetup.com/find/?location={city}&source=EVENTS", 
                f"https://www.meetup.com/find/?eventType=inPerson&location={city}--{country}",
                f"https://www.meetup.com/find/?eventType=online&location={city}--{country}",
            ]
            search_urls.extend(url_patterns)
        
        # Also try the exact URL pattern from your screenshot
        search_urls.append("https://www.meetup.com/find/?location=sa--Makkah&source=EVENTS")
        
        return search_urls

    def extract_event_links_from_search(self, search_url: str) -> List[str]:
        """Extract event links from search results page"""
        log(f"Searching: {search_url}")
        
        try:
            response = self.session.get(search_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Save search page for debugging
            with open(f'meetup_search_debug_{len(self.events)}.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            
            event_links = set()
            
            # Look for event links in various patterns
            link_selectors = [
                'a[href*="/events/"]',
                'a[data-event-label*="event"]',
                'a[data-testid*="event"]',
                'a[href*="/events/"][href*="?"]',  # Event links with parameters
            ]
            
            for selector in link_selectors:
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link.get('href')
                    if href and '/events/' in href:
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            full_url = urljoin(self.base_url, href)
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            continue
                        
                        # Only add if it looks like an event URL
                        if '/events/' in full_url and re.search(r'/events/\d+', full_url):
                            event_links.add(full_url)
            
            # Also look for JSON data that might contain event URLs
            json_scripts = soup.find_all('script', type='application/json')
            for script in json_scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        self.extract_urls_from_json(data, event_links)
                    except:
                        continue
            
            # Look for React/Next.js data
            react_scripts = soup.find_all('script', string=re.compile(r'__NEXT_DATA__|window\.__'))
            for script in react_scripts:
                if script.string:
                    # Extract URLs from JavaScript data
                    urls = re.findall(r'https://www\.meetup\.com/[^"\']+/events/\d+[^"\']*', script.string)
                    for url in urls:
                        event_links.add(url)
            
            log(f"Found {len(event_links)} event links from {search_url}")
            return list(event_links)
            
        except Exception as e:
            log(f"Error extracting links from {search_url}: {e}")
            return []

    def extract_urls_from_json(self, data, event_links: set, path: str = ""):
        """Recursively extract event URLs from JSON data"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and '/events/' in value and 'meetup.com' in value:
                    if re.search(r'/events/\d+', value):
                        event_links.add(value)
                elif isinstance(value, (dict, list)):
                    self.extract_urls_from_json(value, event_links, f"{path}.{key}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    self.extract_urls_from_json(item, event_links, f"{path}[{i}]")

    def parse_event_page(self, event_url: str) -> Optional[Dict[str, str]]:
        """Parse individual event page to extract event details"""
        log(f"Parsing event: {event_url}")
        
        try:
            response = self.session.get(event_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Initialize event data
            event_data = {
                'Site': 'meetup.com',
                'Name': 'N/A',
                'Date': 'N/A',
                'Venue (Brief)': 'N/A',
                'Short Description': 'N/A',
                'URL': event_url,
                'Full Name': 'N/A',
                'Date & Time': 'N/A',
                'City': 'N/A',
                'Detailed Description': 'N/A'
            }
            
            # Extract event name/title
            title_selectors = [
                'h1',
                '[data-testid*="title"]',
                '.event-title',
                'title'
            ]
            
            for selector in title_selectors:
                title_elem = soup.find(selector)
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    if title_text and len(title_text) > 3:
                        event_data['Name'] = title_text
                        event_data['Full Name'] = title_text
                        break
            
            # Extract from page title if not found
            if event_data['Name'] == 'N/A':
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text(strip=True)
                    # Remove "| Meetup" suffix
                    title_text = re.sub(r'\s*\|\s*Meetup\s*$', '', title_text)
                    event_data['Name'] = title_text
                    event_data['Full Name'] = title_text
            
            # Extract date and time
            datetime_selectors = [
                'time[datetime]',
                '[data-testid*="time"]',
                '[data-testid*="date"]'
            ]
            
            for selector in datetime_selectors:
                time_elem = soup.find(selector)
                if time_elem:
                    # Get datetime attribute
                    datetime_attr = time_elem.get('datetime')
                    if datetime_attr:
                        event_data['Date & Time'] = datetime_attr
                        # Extract just date part
                        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', datetime_attr)
                        if date_match:
                            event_data['Date'] = date_match.group(1)
                    
                    # Also get human-readable text
                    time_text = time_elem.get_text(strip=True)
                    if time_text:
                        event_data['Date & Time'] = time_text
                        event_data['Date'] = time_text.split()[0] if time_text else 'N/A'
                    break
            
            # Extract location/venue
            location_selectors = [
                '[data-testid*="location"]',
                '[data-testid*="venue"]',
                'div:contains("Needs a location")',
                'div:contains("Online event")',
                'div:contains("location")'
            ]
            
            for selector in location_selectors:
                if 'contains' in selector:
                    # Handle text-based selectors
                    location_elem = soup.find('div', string=re.compile(selector.split('"')[1], re.IGNORECASE))
                else:
                    location_elem = soup.find(selector)
                
                if location_elem:
                    location_text = location_elem.get_text(strip=True)
                    if location_text:
                        event_data['Venue (Brief)'] = location_text
                        
                        # Extract city
                        city_match = re.search(r'(Riyadh|Jeddah|Makkah|Dammam|Khobar|Medina)', location_text, re.IGNORECASE)
                        if city_match:
                            event_data['City'] = city_match.group(1)
                        elif 'Saudi Arabia' in location_text:
                            event_data['City'] = 'Saudi Arabia'
                        break
            
            # Extract description
            description_selectors = [
                '#event-details',
                '[data-testid*="description"]',
                '.event-description',
                'div.break-words',
                'div:contains("Details") + div'
            ]
            
            for selector in description_selectors:
                if selector == 'div:contains("Details") + div':
                    # Find Details heading and get next sibling
                    details_heading = soup.find('h2', string='Details')
                    if details_heading:
                        desc_elem = details_heading.find_next_sibling('div')
                    else:
                        desc_elem = None
                else:
                    desc_elem = soup.find(selector)
                
                if desc_elem:
                    # Extract text while preserving some structure
                    description_parts = []
                    
                    # Get all text content
                    for elem in desc_elem.find_all(['p', 'li', 'div'], recursive=True):
                        text = elem.get_text(strip=True)
                        if text and text not in description_parts:
                            description_parts.append(text)
                    
                    if description_parts:
                        full_desc = '\n'.join(description_parts)
                        event_data['Detailed Description'] = full_desc
                        
                        # Create short description (first 200 chars)
                        short_desc = full_desc[:200] + '...' if len(full_desc) > 200 else full_desc
                        event_data['Short Description'] = short_desc
                        break
                    else:
                        # Fallback to plain text
                        desc_text = desc_elem.get_text(strip=True)
                        if desc_text:
                            event_data['Detailed Description'] = desc_text
                            short_desc = desc_text[:200] + '...' if len(desc_text) > 200 else desc_text
                            event_data['Short Description'] = short_desc
                            break
            
            # Extract group/organizer info if available
            group_selectors = [
                'a[href*="/members/"]',
                '.organizer-name',
                '[data-testid*="group"]'
            ]
            
            for selector in group_selectors:
                group_elem = soup.find(selector)
                if group_elem:
                    group_text = group_elem.get_text(strip=True)
                    if group_text and 'organizer' not in event_data['Detailed Description'].lower():
                        event_data['Detailed Description'] += f'\n\nOrganizer: {group_text}'
                    break
            
            # Extract attendee count if available
            attendee_text = soup.find(string=re.compile(r'Attendees?\s*\(\d+\)'))
            if attendee_text:
                attendee_match = re.search(r'(\d+)', attendee_text)
                if attendee_match:
                    count = attendee_match.group(1)
                    event_data['Detailed Description'] += f'\n\nAttendees: {count}'
            
            log(f"✅ Extracted: {event_data['Name']} | {event_data['City']} | {event_data['Date']}")
            return event_data
            
        except Exception as e:
            log(f"❌ Error parsing {event_url}: {e}")
            return None

    def scrape_all_events(self) -> List[Dict[str, str]]:
        """Main scraping method"""
        log("🚀 Starting Meetup.com scraping for Saudi Arabia...")
        log("=" * 60)
        
        all_event_links = set()
        
        # Get search URLs for different cities
        search_urls = self.get_search_urls()
        
        # Extract event links from all search pages
        for search_url in search_urls:
            try:
                event_links = self.extract_event_links_from_search(search_url)
                all_event_links.update(event_links)
                
                # Be respectful with delays
                time.sleep(2)
                
            except Exception as e:
                log(f"❌ Error with search URL {search_url}: {e}")
                continue
        
        log(f"\n🔍 Total unique event links found: {len(all_event_links)}")
        
        if not all_event_links:
            log("❌ No event links found. Possible issues:")
            log("   - Meetup.com structure changed")
            log("   - Geographic restrictions")
            log("   - Need to handle dynamic loading")
            return []
        
        # Parse each event page
        events = []
        for i, event_url in enumerate(all_event_links, 1):
            log(f"\n📅 Processing event {i}/{len(all_event_links)}")
            
            try:
                event_data = self.parse_event_page(event_url)
                if event_data and event_data['Name'] != 'N/A':
                    events.append(event_data)
                else:
                    log(f"⚠️  Skipped event with missing data")
                
                # Be respectful with delays
                time.sleep(3)
                
            except Exception as e:
                log(f"❌ Error processing event {i}: {e}")
                continue
        
        log(f"\n✅ Successfully extracted {len(events)} events")
        return events

def save_to_csv(events: List[Dict[str, str]], filename: str = "meetup_saudi_events.csv"):
    """Save events to CSV with the requested column structure"""
    if not events:
        log("No events to save")
        return
    
    # Use the exact column names requested
    fieldnames = [
        'Site',
        'Name', 
        'Date',
        'Venue (Brief)',
        'Short Description', 
        'URL',
        'Full Name',
        'Date & Time',
        'City',
        'Detailed Description'
    ]
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(events)
        
        log(f"✅ Saved {len(events)} events to {filename}")
        
        # Print summary
        log("\n" + "="*60)
        log("📊 MEETUP.COM SCRAPING SUMMARY")
        log("="*60)
        log(f"Total events extracted: {len(events)}")
        
        # Group by city
        cities = {}
        for event in events:
            city = event.get('City', 'Unknown')
            cities[city] = cities.get(city, 0) + 1
        
        log(f"\nEvents by city:")
        for city, count in sorted(cities.items()):
            log(f"  {city}: {count} events")
        
        # Show sample events
        log(f"\nSample events:")
        for i, event in enumerate(events[:3], 1):
            log(f"\n{i}. {event['Name']}")
            log(f"   📍 {event['City']} | {event['Venue (Brief)']}")
            log(f"   📅 {event['Date & Time']}")
            log(f"   📝 {event['Short Description'][:100]}...")
            log(f"   🔗 {event['URL']}")
            
    except Exception as e:
        log(f"❌ Error saving CSV: {e}")

def main():
    """Main execution"""
    scraper = MeetupScraper()
    events = scraper.scrape_all_events()
    
    if events:
        # Save with timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        save_to_csv(events, f"meetup_saudi_events_{timestamp}.csv")
        save_to_csv(events, "meetup_saudi_events_latest.csv")
        
        log("\n🎉 Meetup.com scraping completed successfully!")
        log("📁 Check the CSV files for complete event data")
        log("🔍 Debug HTML files saved for troubleshooting if needed")
        
    else:
        log("\n💡 No events found. Consider:")
        log("   - Using Selenium for dynamic content")
        log("   - Checking if location searches work differently") 
        log("   - Verifying current Meetup.com URL structure")
        log("📁 Check the debug HTML files to see what was actually loaded")

if __name__ == "__main__":
    main()