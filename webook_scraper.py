import requests
from bs4 import BeautifulSoup
import csv
from typing import List, Dict, Optional
import time
import re
from urllib.parse import urljoin, urlparse

BASE_URL = "https://webook.com"
SEARCH_URL = "https://webook.com/en/search?q=KSA"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Connection': 'keep-alive',
}


def log(msg: str):
    print(f"[LOG] {msg}")


def fetch_html(url: str, session: requests.Session) -> Optional[BeautifulSoup]:
    """Fetch HTML content with session for cookie persistence"""
    try:
        response = session.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.exceptions.RequestException as e:
        log(f"Request error for {url}: {e}")
        return None


def accept_cookies(session: requests.Session) -> bool:
    """Accept cookies on the initial page load"""
    try:
        log("Loading main page and accepting cookies...")
        response = session.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for the cookie consent banner
        cookie_banner = soup.find('div', {'id': 'cookie_consent'})
        if cookie_banner:
            log("Cookie banner found - cookies should be accepted automatically on next request")
            return True
        else:
            log("No cookie banner found - proceeding...")
            return True
            
    except Exception as e:
        log(f"Error handling cookies: {e}")
        return False


def extract_event_links(soup: BeautifulSoup) -> List[str]:
    """Extract event page links from search results"""
    event_links = []
    
    # Look for experience/event links based on the HTML structure
    # From the HTML, events have href="/en/experiences/..." pattern
    links = soup.find_all('a', href=True)
    
    for link in links:
        href = link.get('href', '')
        
        # Look for experience links that contain event data
        if '/en/experiences/' in href and 'data-testid' in link.attrs:
            full_url = urljoin(BASE_URL, href)
            if full_url not in event_links:
                event_links.append(full_url)
                log(f"Found event link: {full_url}")
    
    log(f"Found {len(event_links)} unique event links")
    return event_links


def clean_text(text: str) -> str:
    """Clean and normalize text content"""
    if not text:
        return 'N/A'
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove common unwanted elements
    text = re.sub(r'(Read more|Book Online|From|VAT included)', '', text, flags=re.IGNORECASE)
    
    return text.strip() if text.strip() else 'N/A'


def extract_price(soup: BeautifulSoup) -> str:
    """Extract price information"""
    price = 'N/A'
    
    # Look for price in the booking section
    price_elements = soup.find_all('span', string=re.compile(r'\d+'))
    
    for elem in price_elements:
        # Check if this looks like a price (has digits and is in a pricing context)
        text = elem.get_text(strip=True)
        if text.isdigit() and len(text) <= 6:  # Reasonable price range
            parent = elem.find_parent()
            if parent and any(keyword in parent.get_text().lower() for keyword in ['from', 'price', 'sar', 'currency']):
                price = text
                break
    
    # Also look for currency symbols or explicit price mentions
    if price == 'N/A':
        price_pattern = r'(\d+)\s*(?:SAR|SR|ريال)'
        price_match = re.search(price_pattern, soup.get_text(), re.IGNORECASE)
        if price_match:
            price = price_match.group(1)
    
    return price


def extract_dates(soup: BeautifulSoup) -> tuple:
    """Extract start and end dates"""
    start_date = 'N/A'
    end_date = 'N/A'
    
    # Look for date information in various sections
    date_containers = soup.find_all(['div', 'p'], string=re.compile(r'\d{1,2}\s+\w+\s+\d{4}'))
    
    for container in date_containers:
        text = container.get_text(strip=True)
        
        # Look for date patterns like "12 March 2025 - 16 October 2025"
        date_range_pattern = r'(\d{1,2}\s+\w+\s+\d{4})\s*-\s*(\d{1,2}\s+\w+\s+\d{4})'
        range_match = re.search(date_range_pattern, text)
        
        if range_match:
            start_date = range_match.group(1).strip()
            end_date = range_match.group(2).strip()
            break
        
        # Look for single date pattern
        single_date_pattern = r'(\d{1,2}\s+\w+\s+\d{4})'
        single_match = re.search(single_date_pattern, text)
        
        if single_match and start_date == 'N/A':
            start_date = single_match.group(1).strip()
    
    return start_date, end_date


def extract_location(soup: BeautifulSoup) -> str:
    """Extract location information"""
    location = 'N/A'
    
    # Look for location in various places
    # From HTML structure, location appears near text like "Riyadh, Saudi Arabia"
    location_patterns = [
        r'([^,]+,\s*Saudi Arabia)',
        r'(Riyadh|Jeddah|Al Khobar|Dammam|Mecca|Medina)[^,]*,?\s*Saudi Arabia'
    ]
    
    page_text = soup.get_text()
    
    for pattern in location_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            break
    
    # Also look for specific location elements
    if location == 'N/A':
        location_divs = soup.find_all(['div', 'p'], string=re.compile(r'Saudi Arabia', re.IGNORECASE))
        for div in location_divs:
            text = div.get_text(strip=True)
            if 'Saudi Arabia' in text and len(text) < 50:  # Reasonable location text
                location = text
                break
    
    return clean_text(location)


def extract_description(soup: BeautifulSoup) -> str:
    """Extract event description"""
    description = 'N/A'
    
    # Look for description in the "About" section
    about_section = soup.find('h2', string='About')
    if about_section:
        desc_container = about_section.find_next_sibling()
        if desc_container:
            # Get all paragraphs in the description
            paragraphs = desc_container.find_all('p')
            if paragraphs:
                desc_parts = []
                for p in paragraphs:
                    text = clean_text(p.get_text())
                    if text and text != 'N/A':
                        desc_parts.append(text)
                description = '\n\n'.join(desc_parts)
            else:
                description = clean_text(desc_container.get_text())
    
    # Fallback: look for any substantial text blocks that might be descriptions
    if description == 'N/A':
        text_blocks = soup.find_all(['div', 'section'], string=re.compile(r'.{100,}'))
        for block in text_blocks:
            text = clean_text(block.get_text())
            if len(text) > 100 and any(keyword in text.lower() for keyword in ['session', 'experience', 'workout', 'training']):
                description = text[:500] + '...' if len(text) > 500 else text
                break
    
    return description


def parse_event_page(url: str, session: requests.Session) -> Dict[str, str]:
    """Parse individual event page and extract all details"""
    log(f"Parsing event page: {url}")
    
    soup = fetch_html(url, session)
    if not soup:
        return {
            'Site': 'webook.com',
            'Name': 'N/A',
            'Start Date': 'N/A',
            'End Date': 'N/A',
            'Location': 'N/A',
            'Price': 'N/A',
            'Description': 'N/A',
            'URL': url
        }
    
    # Extract name from h1
    name = 'N/A'
    h1_tag = soup.find('h1', class_=re.compile(r'text-heading-L'))
    if h1_tag:
        name = clean_text(h1_tag.get_text())
    
    # Extract other details
    start_date, end_date = extract_dates(soup)
    location = extract_location(soup)
    price = extract_price(soup)
    description = extract_description(soup)
    
    event_data = {
        'Site': 'webook.com',
        'Name': name,
        'Start Date': start_date,
        'End Date': end_date,
        'Location': location,
        'Price': price,
        'Description': description,
        'URL': url
    }
    
    log(f"Extracted: {name} | {location} | {price}")
    return event_data


def scrape_webook_events() -> List[Dict[str, str]]:
    """Main scraping function"""
    log("Starting WeBook.com scraper...")
    
    session = requests.Session()
    
    # Accept cookies first
    if not accept_cookies(session):
        log("Failed to handle cookies, continuing anyway...")
    
    # Get search results page
    log(f"Fetching search results from: {SEARCH_URL}")
    soup = fetch_html(SEARCH_URL, session)
    
    if not soup:
        log("Failed to fetch search results")
        return []
    
    # Extract event links
    event_links = extract_event_links(soup)
    
    if not event_links:
        log("No event links found. The site structure may have changed.")
        return []
    
    # Parse each event page
    events = []
    for i, link in enumerate(event_links, 1):
        log(f"Processing event {i}/{len(event_links)}")
        try:
            event_data = parse_event_page(link, session)
            events.append(event_data)
            
            # Be respectful to the server
            time.sleep(2)
            
        except Exception as e:
            log(f"Error processing event {i}: {e}")
            continue
    
    return events


def save_events_to_csv(events: List[Dict[str, str]], filename: str = "webook_events.csv"):
    """Save events to CSV file"""
    if not events:
        log("No events to save")
        return
    
    fieldnames = ['Site', 'Name', 'Start Date', 'End Date', 'Location', 'Price', 'Description', 'URL']
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(events)
        
        log(f"Saved {len(events)} events to {filename}")
        
        # Print sample of extracted data
        log("\nSample extracted events:")
        for i, event in enumerate(events[:3]):
            log(f"\nEvent {i+1}:")
            log(f"  Name: {event['Name']}")
            log(f"  Location: {event['Location']}")
            log(f"  Price: {event['Price']}")
            log(f"  Start Date: {event['Start Date']}")
            
    except IOError as e:
        log(f"Failed to save CSV: {e}")


# Main execution
if __name__ == "__main__":
    events = scrape_webook_events()
    save_events_to_csv(events)