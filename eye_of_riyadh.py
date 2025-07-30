import requests
from bs4 import BeautifulSoup
import csv
from typing import List, Dict, Optional
import time
import re

BASE_URL = "https://www.eyeofriyadh.com/events/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Connection': 'keep-alive',
}


def log(msg: str):
    print(f"[LOG] {msg}")


def build_search_url(query: str) -> str:
    return f"{BASE_URL}index.php?s={query}&search_post_type=place&fcity=&fcat=&count=&sort-by=&sort="


def fetch_html(url: str) -> Optional[BeautifulSoup]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.exceptions.RequestException as e:
        log(f"Request error for {url}: {e}")
        return None


def clean_text(text: str) -> str:
    """Remove extra spaces and unwanted labels like REGISTER, ADD TO CALENDAR."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'(REGISTER|ADD TO CALENDAR ▼.*?iCal Calendar)', '', text, flags=re.IGNORECASE)
    return text.strip()


def parse_event_page(url: str) -> Dict[str, str]:
    soup = fetch_html(url)
    if not soup:
        return {
            'Full Name': 'N/A',
            'Date & Time': 'N/A',
            'City': 'N/A',
            'Detailed Description': 'N/A'
        }

    # Extract title
    title_tag = soup.find('h1', style=lambda val: val and 'font-size:22px;' in val)
    full_name = title_tag.get_text(strip=True) if title_tag else 'N/A'

    # Extract date/time and city
    date_time, city = 'N/A', 'N/A'
    title_container = title_tag.find_parent('div') if title_tag else None
    if title_container:
        divs = title_container.find_all('div')
        if len(divs) >= 2:
            date_time = clean_text(divs[0].get_text(strip=True))
            city = clean_text(divs[1].get_text(strip=True))

    # Extract detailed description - try multiple approaches
    full_description = 'N/A'
    
    # Debug: Let's see what divs with styles we can find
    all_divs_with_style = soup.find_all('div', style=True)
    log(f"Found {len(all_divs_with_style)} divs with style attributes")
    
    # Look for divs with background-color in their style
    bg_divs = [div for div in all_divs_with_style if 'background-color' in div.get('style', '').lower()]
    log(f"Found {len(bg_divs)} divs with background-color")
    
    # Method 1: Find ALL FAFAFA divs and pick the one with substantial content
    fafafa_divs = soup.find_all('div', style=lambda val: val and 'background-color:#FAFAFA' in val and 'border:1px solid #DEDEDE' in val)
    
    log(f"Found {len(fafafa_divs)} FAFAFA divs with border")
    
    desc_div = None
    for i, div in enumerate(fafafa_divs):
        text = div.get_text(strip=True)
        log(f"FAFAFA Div {i+1}: {len(text)} characters - '{text[:100]}...'")
        
        # Look for the div with substantial content that looks like a description
        if len(text) > 200 and any(keyword.lower() in text.lower() for keyword in ['summit', 'conference', 'annual', 'ksa', 'saudi']):
            log(f"Selected FAFAFA Div {i+1} as description div")
            desc_div = div
            break
    
    if desc_div:
        log("Found description FAFAFA div")
        
        # Check for paragraphs first
        paragraphs = desc_div.find_all('p')
        log(f"Found {len(paragraphs)} paragraphs in the description div")
        
        if paragraphs:
            description_parts = []
            for i, p in enumerate(paragraphs):
                text = p.get_text(strip=True)
                log(f"Paragraph {i+1}: '{text[:100]}...' (length: {len(text)})")
                if text:
                    description_parts.append(text)
            full_description = '\n\n'.join(description_parts)
        else:
            # If no paragraphs, get all text from the div
            full_description = desc_div.get_text(separator="\n", strip=True)
            log(f"Using div text directly: '{full_description[:100]}...' (length: {len(full_description)})")
    else:
        # Method 2: Try all FAFAFA divs without border requirement
        fafafa_divs_no_border = soup.find_all('div', style=lambda val: val and 'background-color:#FAFAFA' in val)
        log(f"Found {len(fafafa_divs_no_border)} FAFAFA divs (without border requirement)")
        
        for i, div in enumerate(fafafa_divs_no_border):
            text = div.get_text(strip=True)
            log(f"FAFAFA Div {i+1} (no border): {len(text)} characters - '{text[:100]}...'")
            
            # Look for the div with substantial content that looks like a description
            if len(text) > 200 and any(keyword.lower() in text.lower() for keyword in ['summit', 'conference', 'annual', 'ksa', 'saudi']):
                log(f"Selected FAFAFA Div {i+1} (no border) as description div")
                desc_div = div
                
                paragraphs = desc_div.find_all('p')
                if paragraphs:
                    description_parts = []
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if text:
                            description_parts.append(text)
                    full_description = '\n\n'.join(description_parts)
                else:
                    full_description = desc_div.get_text(separator="\n", strip=True)
                break
        else:
                # Method 4: Look for divs that might contain event descriptions
                # Try finding divs with substantial text content
                for div in all_divs_with_style:
                    text = div.get_text(strip=True)
                    # Look for divs with substantial content that might be descriptions
                    if len(text) > 100 and any(keyword in text.lower() for keyword in ['summit', 'conference', 'event', 'ksa', 'saudi']):
                        log(f"Found potential description div with {len(text)} characters")
                        full_description = text
                        break
                
                if full_description == 'N/A':
                    # Method 5: Search for text content that looks like event descriptions
                    # Look for any element containing substantial text about the event
                    page_text = soup.get_text()
                    
                    # Try to find description-like content by looking for patterns
                    import re
                    
                    # Look for paragraphs that mention the event name or related keywords
                    event_keywords = ['summit', 'conference', 'transformation', 'ksa', 'saudi', 'logistics', 'ports']
                    
                    # Find all text blocks that might be descriptions
                    all_elements = soup.find_all(['p', 'div', 'span'])
                    for element in all_elements:
                        text = element.get_text(strip=True)
                        if (len(text) > 100 and 
                            any(keyword.lower() in text.lower() for keyword in event_keywords) and
                            'annual' in text.lower()):
                            log(f"Found potential description in {element.name}: {text[:100]}...")
                            full_description = text
                            break
                    
                    # If still nothing, try a more aggressive search in the raw HTML
                    if full_description == 'N/A':
                        log("Trying raw HTML text search...")
                        
                        # Look for the expected description pattern in raw HTML
                        html_str = str(soup)
                        
                        # Search for text patterns that look like descriptions
                        desc_patterns = [
                            r'The.*?Annual.*?Summit.*?KSA.*?[\.!]',
                            r'Saudi Arabia.*?transformation.*?[\.!]',
                            r'[A-Z][^<>]*?summit.*?[A-Z][^<>]*?conference.*?[\.!]'
                        ]
                        
                        for pattern in desc_patterns:
                            matches = re.findall(pattern, html_str, re.IGNORECASE | re.DOTALL)
                            if matches:
                                # Clean up HTML tags from the match
                                clean_match = re.sub(r'<[^>]+>', '', matches[0])
                                clean_match = re.sub(r'\s+', ' ', clean_match).strip()
                                if len(clean_match) > 50:
                                    log(f"Found description via regex: {clean_match[:100]}...")
                                    full_description = clean_match
                                    break
    
    # Clean the description
    if full_description != 'N/A':
        full_description = clean_text(full_description)
        # Remove HTML entities
        full_description = full_description.replace('&amp;', '&').replace('&nbsp;', ' ')
    
    log(f"Final description length: {len(full_description) if full_description != 'N/A' else 0} characters")
    if full_description != 'N/A' and len(full_description) > 0:
        log(f"Description preview: {full_description[:100]}...")

    return {
        'Full Name': full_name,
        'Date & Time': date_time,
        'City': city,
        'Detailed Description': full_description
    }


def parse_event_block(block) -> Dict[str, str]:
    def find_text(style_substr: str) -> str:
        div = block.find('div', style=lambda val: val and style_substr in val)
        return div.get_text(strip=True) if div else 'N/A'

    def find_link_text(style_substr: str) -> (str, str):
        div = block.find('div', style=lambda val: val and style_substr in val)
        if div:
            a_tag = div.find('a', style=lambda val: val and 'font-weight:700' in val)
            if a_tag:
                return a_tag.get_text(strip=True), a_tag.get('href', 'N/A')
        return 'N/A', 'N/A'

    name, relative_url = find_link_text('padding:3px 10px;')
    full_url = relative_url if relative_url.startswith('http') else f"{BASE_URL}{relative_url}"
    raw_desc = find_text('margin-bottom:10px;')
    short_desc = clean_text(raw_desc.replace('\xa0', ' ')) if raw_desc != 'N/A' else 'N/A'

    brief_event = {
        'Name': name,
        'Date': find_text('padding:0px 10px 3px 10px;'),
        'Venue (Brief)': find_text('padding:0px 10px 10px 10px').replace('\xa0', ''),
        'Short Description': short_desc,
        'URL': full_url
    }

    log(f"Fetching details from: {full_url}")
    time.sleep(1)  # Be respectful to the server
    full_details = parse_event_page(full_url)
    return {**brief_event, **full_details}


def scrape_eyeofriyadh_events(query: str = "KSA") -> List[Dict[str, str]]:
    url = build_search_url(query)
    log(f"Scraping event list from: {url}")

    soup = fetch_html(url)
    if not soup:
        return []

    event_blocks = soup.find_all(
        'div',
        style=lambda val: val and 'margin-bottom:25px;' in val and 'border-bottom' in val
    )

    if not event_blocks:
        log("No event blocks found. The site layout may have changed.")
        return []

    log(f"Found {len(event_blocks)} events. Parsing...")
    events = []
    for i, block in enumerate(event_blocks, 1):
        log(f"Processing event {i}/{len(event_blocks)}")
        try:
            event = parse_event_block(block)
            events.append(event)
        except Exception as e:
            log(f"Error processing event {i}: {e}")
            continue
    
    return events


def save_events_to_csv(events: List[Dict[str, str]], filename: str):
    if not events:
        log("No events to write to CSV.")
        return

    keys = events[0].keys()
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=keys)
            writer.writeheader()
            writer.writerows(events)
        log(f"Saved {len(events)} events to {filename}")
    except IOError as e:
        log(f"Failed to save CSV: {e}")


# Main Execution
if __name__ == "__main__":
    # First, let's test with just one event to debug
    log("Testing with first event only for debugging...")
    
    # Get the search page first
    url = build_search_url("KSA")
    soup = fetch_html(url)
    if soup:
        event_blocks = soup.find_all(
            'div',
            style=lambda val: val and 'margin-bottom:25px;' in val and 'border-bottom' in val
        )
        
        if event_blocks:
            log(f"Found {len(event_blocks)} events")
            
            # Test with first event
            first_block = event_blocks[0]
            test_event = parse_event_block(first_block)
            
            # Save the HTML of the first event page for manual inspection
            def find_link_text(block, style_substr: str) -> (str, str):
                div = block.find('div', style=lambda val: val and style_substr in val)
                if div:
                    a_tag = div.find('a', style=lambda val: val and 'font-weight:700' in val)
                    if a_tag:
                        return a_tag.get_text(strip=True), a_tag.get('href', 'N/A')
                return 'N/A', 'N/A'
            
            name, relative_url = find_link_text(first_block, 'padding:3px 10px;')
            full_url = relative_url if relative_url.startswith('http') else f"{BASE_URL}{relative_url}"
            
            # Save HTML for inspection
            html_soup = fetch_html(full_url)
            if html_soup:
                with open('debug_event_page.html', 'w', encoding='utf-8') as f:
                    f.write(str(html_soup))
                log(f"Saved HTML content to debug_event_page.html for inspection")
                
                # Also look for all divs and their styles
                all_divs = html_soup.find_all('div', style=True)
                log(f"All styled divs in the page:")
                for i, div in enumerate(all_divs[:10]):  # Show first 10
                    style = div.get('style', '')
                    text_preview = div.get_text(strip=True)[:100]
                    log(f"Div {i+1}: style='{style}' text='{text_preview}'...")
            
            log(f"Test event result: {test_event}")
    
    # Now run the full scraper
    log("\nRunning full scraper...")
    events = scrape_eyeofriyadh_events("KSA")
    save_events_to_csv(events, "eyeofriyadh_ksa_events_detailed.csv")
    
    # Print a sample of the extracted descriptions for verification
    if events:
        log("\nSample descriptions extracted:")
        for i, event in enumerate(events[:2]):  # Show first 2 events
            log(f"\nEvent {i+1}: {event['Name']}")
            desc = event['Detailed Description']
            if desc != 'N/A' and len(desc) > 200:
                log(f"Description: {desc[:200]}...")
            else:
                log(f"Description: {desc}")