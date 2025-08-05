import requests
import json
import csv
from typing import List, Dict, Optional
import time
import re
from bs4 import BeautifulSoup

def log(msg: str):
    print(f"[LOG] {msg}")

class WeBookEnhancedScraper:
    def __init__(self):
        self.base_url = "https://webook.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/html, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Referer': 'https://webook.com/en/search?q=KSA',
        })
        self.events = []

    def save_response_for_debug(self, url: str, response_text: str, response_type: str):
        """Save response content for debugging"""
        try:
            filename = f"debug_response_{len(self.events)}_{response_type}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"<!-- URL: {url} -->\n")
                f.write(response_text)
            log(f"💾 Saved {response_type} response to {filename}")
        except Exception as e:
            log(f"Error saving debug file: {e}")

    def try_api_with_different_methods(self, endpoint: str) -> Optional[str]:
        """Try different HTTP methods and headers for API endpoints"""
        
        # Different header combinations to try
        header_variations = [
            # Standard API headers
            {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            },
            # AJAX-style headers
            {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            },
            # GraphQL headers
            {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Apollo-Require-Preflight': 'true',
            },
            # Basic fetch headers
            {
                'Accept': '*/*',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Dest': 'empty',
            }
        ]
        
        # Try GET with different headers
        for i, headers in enumerate(header_variations):
            try:
                temp_headers = self.session.headers.copy()
                temp_headers.update(headers)
                
                response = requests.get(endpoint, headers=temp_headers, timeout=10)
                
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if 'application/json' in content_type:
                        try:
                            data = response.json()
                            log(f"✅ Got JSON with header variation {i+1}")
                            return json.dumps(data, indent=2)
                        except:
                            pass
                    
                    # Even if not JSON, save for analysis
                    self.save_response_for_debug(endpoint, response.text, f"GET_variation_{i+1}")
                    
            except Exception as e:
                continue
        
        # Try POST requests (some APIs only respond to POST)
        post_payloads = [
            {},  # Empty POST
            {'query': 'KSA'},
            {'search': 'KSA'},
            {'country': 'SA'},
            {'location': 'Saudi Arabia'},
        ]
        
        for payload in post_payloads:
            try:
                response = self.session.post(
                    endpoint, 
                    json=payload if payload else None,
                    data=payload if payload else None,
                    timeout=10
                )
                
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if 'application/json' in content_type:
                        try:
                            data = response.json()
                            log(f"✅ Got JSON with POST payload: {payload}")
                            return json.dumps(data, indent=2)
                        except:
                            pass
                    
                    self.save_response_for_debug(endpoint, response.text, f"POST_{str(payload)[:20]}")
                    
            except Exception as e:
                continue
        
        return None

    def extract_data_from_html_responses(self) -> List[Dict]:
        """Try to extract event data from HTML responses we got"""
        log("\n🔍 Analyzing HTML responses for embedded data...")
        
        events = []
        
        # Look for saved debug files
        import glob
        import os
        
        html_files = glob.glob("debug_response_*.html")
        log(f"Found {len(html_files)} HTML response files to analyze")
        
        for html_file in html_files:
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # Try to find JSON data embedded in HTML
                json_events = self.extract_json_from_html(html_content)
                events.extend(json_events)
                
                # Try to find structured data in script tags
                script_events = self.extract_from_script_tags(html_content)
                events.extend(script_events)
                
                # Try to parse as React/Next.js initial props
                props_events = self.extract_from_initial_props(html_content)
                events.extend(props_events)
                
            except Exception as e:
                log(f"Error analyzing {html_file}: {e}")
                continue
        
        return events

    def extract_json_from_html(self, html_content: str) -> List[Dict]:
        """Extract JSON data embedded in HTML"""
        events = []
        
        # Look for JSON data patterns
        json_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
            r'window\.__DATA__\s*=\s*({.+?});',
            r'window\.__APOLLO_STATE__\s*=\s*({.+?});',
            r'__NEXT_DATA__"\s*type="application/json">({.+?})</script>',
            r'"props"\s*:\s*({.+?"pageProps".+?})',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, html_content, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    events.extend(self.parse_nested_json_for_events(data))
                except:
                    continue
        
        return events

    def extract_from_script_tags(self, html_content: str) -> List[Dict]:
        """Extract data from script tags"""
        events = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            scripts = soup.find_all('script')
            
            for script in scripts:
                if script.string:
                    script_content = script.string
                    
                    # Look for event-like data in script content
                    if any(keyword in script_content.lower() for keyword in ['event', 'experience', 'fast fit', 'session']):
                        # Try to extract JSON from script
                        json_matches = re.findall(r'\{[^{}]*(?:"(?:title|name|event)")[^{}]*\}', script_content)
                        for match in json_matches:
                            try:
                                data = json.loads(match)
                                event = self.parse_single_event_from_json(data)
                                if event:
                                    events.append(event)
                            except:
                                continue
        except:
            pass
        
        return events

    def extract_from_initial_props(self, html_content: str) -> List[Dict]:
        """Extract from Next.js initial props or similar patterns"""
        events = []
        
        # Look for Next.js __NEXT_DATA__
        next_data_pattern = r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>'
        matches = re.findall(next_data_pattern, html_content, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                events.extend(self.parse_nested_json_for_events(data))
            except:
                continue
        
        return events

    def parse_nested_json_for_events(self, data: Dict, path: str = "") -> List[Dict]:
        """Recursively search JSON data for event-like objects"""
        events = []
        
        if isinstance(data, dict):
            # Check if this object looks like an event
            if self.looks_like_event(data):
                event = self.parse_single_event_from_json(data)
                if event:
                    events.append(event)
            
            # Recurse into nested objects
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    events.extend(self.parse_nested_json_for_events(value, f"{path}.{key}"))
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    events.extend(self.parse_nested_json_for_events(item, f"{path}[{i}]"))
        
        return events

    def looks_like_event(self, obj: Dict) -> bool:
        """Check if a JSON object looks like an event"""
        if not isinstance(obj, dict):
            return False
        
        # Must have some kind of title/name
        has_title = any(key in obj for key in ['title', 'name', 'displayName', 'eventName'])
        
        # Should have event-related fields
        event_fields = ['date', 'startDate', 'endDate', 'location', 'venue', 'price', 'description', 'slug']
        has_event_fields = sum(1 for field in event_fields if field in obj) >= 2
        
        # Check if title contains event-like terms
        title_text = str(obj.get('title', obj.get('name', ''))).lower()
        has_event_terms = any(term in title_text for term in ['session', 'experience', 'event', 'summit', 'conference'])
        
        return has_title and (has_event_fields or has_event_terms)

    def parse_single_event_from_json(self, data: Dict) -> Optional[Dict]:
        """Parse a single event from JSON data"""
        if not self.looks_like_event(data):
            return None
        
        # Extract fields
        name = data.get('title') or data.get('name') or data.get('displayName') or 'N/A'
        
        # Extract location
        location = 'N/A'
        for loc_field in ['location', 'venue', 'address', 'city']:
            if loc_field in data:
                loc_data = data[loc_field]
                if isinstance(loc_data, str):
                    location = loc_data
                    break
                elif isinstance(loc_data, dict):
                    location = loc_data.get('name') or loc_data.get('city') or str(loc_data)
                    break
        
        # Extract dates
        start_date = data.get('startDate') or data.get('date') or data.get('eventDate') or 'N/A'
        end_date = data.get('endDate') or 'N/A'
        
        # Extract price
        price = 'N/A'
        if 'price' in data:
            price_data = data['price']
            if isinstance(price_data, (int, float)):
                price = str(price_data)
            elif isinstance(price_data, dict):
                price = str(price_data.get('amount', price_data.get('value', 'N/A')))
        
        # Extract description
        description = data.get('description') or data.get('summary') or 'N/A'
        
        # Build URL
        url = 'N/A'
        if 'slug' in data:
            url = f"https://webook.com/en/experiences/{data['slug']}"
        elif 'url' in data:
            url = data['url']
        
        return {
            'Site': 'webook.com',
            'Name': str(name),
            'Start Date': str(start_date),
            'End Date': str(end_date),
            'Location': str(location),
            'Price': str(price),
            'Description': str(description)[:500] if description != 'N/A' else 'N/A',
            'URL': str(url)
        }

    def try_known_working_urls(self) -> List[Dict]:
        """Try URLs we know should have event data"""
        log("\n🎯 Trying known working URLs...")
        
        events = []
        
        # URLs from the HTML samples you provided
        known_urls = [
            "https://webook.com/en/experiences/introductory-session",
            "https://webook.com/en/experiences/introductory-session-1",
            "https://webook.com/en/experiences/introductory-session-fast-fit-al-narjis-branch-ladies-gents",
            "https://webook.com/en/experiences/introductory-session-fast-fit-al-khalidiyyah-branch-ladies-gents",
            "https://webook.com/en/experiences/introductory-session-fast-fit-al-rakah-branch-ladies-gents",
            "https://webook.com/en/experiences/introductory-session-fast-fit-al-waha-branch-gents-only",
        ]
        
        for url in known_urls:
            try:
                log(f"Fetching: {url}")
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    # Save for analysis
                    self.save_response_for_debug(url, response.text, "known_url")
                    
                    # Try to extract event data from this page
                    event = self.extract_event_from_page(response.text, url)
                    if event:
                        events.append(event)
                        log(f"✅ Extracted event: {event['Name']}")
                else:
                    log(f"❌ Status {response.status_code}")
                    
                time.sleep(2)  # Be respectful
                
            except Exception as e:
                log(f"❌ Error fetching {url}: {e}")
                continue
        
        return events

    def extract_event_from_page(self, html_content: str, url: str) -> Optional[Dict]:
        """Extract event data from an individual event page"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract name from title or h1
            name = 'N/A'
            title_tag = soup.find('title')
            if title_tag:
                name = title_tag.get_text().strip()
            
            h1_tag = soup.find('h1')
            if h1_tag and len(h1_tag.get_text().strip()) > len(name):
                name = h1_tag.get_text().strip()
            
            # Extract other data from JSON-LD or meta tags
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    ld_data = json.loads(json_ld.string)
                    if isinstance(ld_data, list):
                        ld_data = ld_data[0]
                    
                    if ld_data.get('@type') == 'Event':
                        return {
                            'Site': 'webook.com',
                            'Name': ld_data.get('name', name),
                            'Start Date': ld_data.get('startDate', 'N/A'),
                            'End Date': ld_data.get('endDate', 'N/A'),
                            'Location': str(ld_data.get('location', {}).get('name', 'N/A')),
                            'Price': str(ld_data.get('offers', {}).get('price', 'N/A')),
                            'Description': ld_data.get('description', 'N/A'),
                            'URL': url
                        }
                except:
                    pass
            
            # Fallback: extract from page structure
            if name != 'N/A':
                # Look for location in text
                location = 'N/A'
                location_patterns = [
                    r'(Riyadh|Jeddah|Al Khobar|Dammam).*?Saudi Arabia',
                    r'(Riyadh|Jeddah|Al Khobar|Dammam)',
                ]
                
                page_text = soup.get_text()
                for pattern in location_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        location = match.group(0)
                        break
                
                # Look for price
                price = 'N/A'
                price_match = re.search(r'(\d+)\s*(?:SAR|SR|ريال)', page_text)
                if price_match:
                    price = price_match.group(1)
                
                return {
                    'Site': 'webook.com',
                    'Name': name,
                    'Start Date': 'N/A',
                    'End Date': 'N/A',
                    'Location': location,
                    'Price': price,
                    'Description': 'N/A',
                    'URL': url
                }
        
        except Exception as e:
            log(f"Error extracting from page: {e}")
        
        return None

    def scrape_all_events(self) -> List[Dict]:
        """Main scraping method"""
        log("🚀 Starting WeBook Enhanced Scraping...")
        log("=" * 50)
        
        all_events = []
        
        # Step 1: Try API endpoints with different methods
        log("\n🔧 Trying API endpoints with enhanced methods...")
        api_endpoints = [
            f"{self.base_url}/api/search",
            f"{self.base_url}/api/events",
            f"{self.base_url}/api/experiences",
            f"{self.base_url}/api/getEvents",
            f"{self.base_url}/api/getExperiences",
        ]
        
        for endpoint in api_endpoints:
            log(f"Trying enhanced API calls for: {endpoint}")
            response = self.try_api_with_different_methods(endpoint)
            if response:
                # If we got JSON response, try to parse it
                try:
                    data = json.loads(response)
                    events = self.parse_nested_json_for_events(data)
                    all_events.extend(events)
                except:
                    pass
        
        # Step 2: Try known working URLs
        known_events = self.try_known_working_urls()
        all_events.extend(known_events)
        
        # Step 3: Analyze HTML responses for embedded data
        html_events = self.extract_data_from_html_responses()
        all_events.extend(html_events)
        
        # Remove duplicates
        if all_events:
            unique_events = []
            seen = set()
            
            for event in all_events:
                key = (event['Name'].lower(), event['URL'])
                if key not in seen:
                    seen.add(key)
                    unique_events.append(event)
            
            log(f"\n🎯 Total unique events found: {len(unique_events)}")
            return unique_events
        
        log("\n❌ No events found with enhanced methods")
        return []

def save_to_csv(events: List[Dict], filename: str = "webook_enhanced_events.csv"):
    """Save events to CSV"""
    if not events:
        log("No events to save")
        return
    
    fieldnames = ['Site', 'Name', 'Start Date', 'End Date', 'Location', 'Price', 'Description', 'URL']
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(events)
        
        log(f"✅ Saved {len(events)} events to {filename}")
        
        # Print summary
        log(f"\nSample events:")
        for i, event in enumerate(events[:3], 1):
            log(f"{i}. {event['Name']}")
            log(f"   📍 {event['Location']}")
            log(f"   💰 {event['Price']}")
            log(f"   🔗 {event['URL']}")
            
    except Exception as e:
        log(f"❌ Error saving CSV: {e}")

def main():
    """Main execution"""
    scraper = WeBookEnhancedScraper()
    events = scraper.scrape_all_events()
    
    if events:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        save_to_csv(events, f"webook_enhanced_events_{timestamp}.csv")
        save_to_csv(events, "webook_enhanced_events_latest.csv")
        
        log("\n🎉 Enhanced scraping completed!")
    else:
        log("\n💡 No events found even with enhanced methods.")
        log("📁 Check the debug_response_*.html files to see what the servers returned")

if __name__ == "__main__":
    main()