import requests
from bs4 import BeautifulSoup
import csv
from typing import List, Dict, Optional


BASE_URL = "https://www.eyeofriyadh.com/events/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Connection': 'keep-alive',
}


def log(message: str):
    """Simple logger."""
    print(f"[LOG] {message}")


def build_search_url(query: str) -> str:
    return f"{BASE_URL}index.php?s={query}&search_post_type=place&fcity=&fcat=&count=&sort-by=&sort="


def fetch_html(url: str) -> Optional[BeautifulSoup]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.exceptions.RequestException as e:
        log(f"Request failed: {e}")
        return None


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

    return {
        'Name': name,
        'Date': find_text('padding:0px 10px 3px 10px;'),
        'Venue': find_text('padding:0px 10px 10px 10px').replace('\xa0', ''),
        'Description': find_text('margin-bottom:10px;'),
        'URL': full_url
    }


def scrape_eyeofriyadh_events(query: str = "KSA") -> List[Dict[str, str]]:
    url = build_search_url(query)
    log(f"Scraping events from: {url}")
    
    soup = fetch_html(url)
    if not soup:
        return []

    event_blocks = soup.find_all(
        'div',
        style=lambda val: val and 'margin-bottom:25px;' in val and 'border-bottom' in val
    )

    if not event_blocks:
        log("No event blocks found. The website's structure might have changed.")
        return []

    log(f"Found {len(event_blocks)} event blocks. Parsing...")
    return [parse_event_block(block) for block in event_blocks]


def save_events_to_csv(events: List[Dict[str, str]], filename: str):
    if not events:
        log("No events to write to CSV.")
        return

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=['Name', 'Date', 'Venue', 'Description', 'URL'])
            writer.writeheader()
            writer.writerows(events)
        log(f"Saved {len(events)} events to {filename}")
    except IOError as e:
        log(f"Error writing CSV: {e}")


if __name__ == "__main__":
    events = scrape_eyeofriyadh_events("KSA")
    save_events_to_csv(events, "eyeofriyadh_ksa_events.csv")
