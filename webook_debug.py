import requests
from bs4 import BeautifulSoup
import re

def debug_webook_search():
    """Debug the webook search page to understand its structure"""
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Connection': 'keep-alive',
    }
    
    url = "https://webook.com/en/search?q=KSA"
    
    try:
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Content length: {len(response.content)}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Save the HTML for inspection
        with open('webook_search_debug.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print("Saved HTML to webook_search_debug.html")
        
        # Look for various link patterns
        print("\n=== ANALYZING LINKS ===")
        all_links = soup.find_all('a', href=True)
        print(f"Total links found: {len(all_links)}")
        
        experience_links = []
        for link in all_links:
            href = link.get('href', '')
            if 'experience' in href.lower():
                experience_links.append(href)
        
        print(f"Links containing 'experience': {len(experience_links)}")
        for link in experience_links[:5]:  # Show first 5
            print(f"  {link}")
        
        # Look for data-testid attributes
        print("\n=== DATA-TESTID ELEMENTS ===")
        testid_elements = soup.find_all(attrs={'data-testid': True})
        print(f"Elements with data-testid: {len(testid_elements)}")
        
        event_testids = []
        for elem in testid_elements:
            testid = elem.get('data-testid', '')
            if any(keyword in testid.lower() for keyword in ['item', 'event', 'experience']):
                event_testids.append(testid)
                if elem.name == 'a' and elem.get('href'):
                    print(f"  Event link: {elem.get('href')} (testid: {testid})")
        
        print(f"Event-related testids: {len(set(event_testids))}")
        
        # Look for grid containers that might hold events
        print("\n=== GRID CONTAINERS ===")
        grid_containers = soup.find_all(['div'], class_=re.compile(r'grid'))
        print(f"Grid containers found: {len(grid_containers)}")
        
        for i, container in enumerate(grid_containers[:3]):  # Check first 3
            print(f"\nGrid {i+1}:")
            print(f"  Classes: {container.get('class', [])}")
            child_links = container.find_all('a', href=True)
            print(f"  Child links: {len(child_links)}")
            for link in child_links[:3]:
                print(f"    {link.get('href', 'No href')}")
        
        # Look for common event card patterns
        print("\n=== POTENTIAL EVENT CARDS ===")
        
        # Based on your HTML, look for cards with images and titles
        cards_with_images = soup.find_all(['div', 'a'], class_=re.compile(r'(card|item|experience)'))
        print(f"Potential cards: {len(cards_with_images)}")
        
        # Look for elements containing "Fast Fit" or other event names
        print("\n=== EVENT NAME SEARCH ===")
        fast_fit_elements = soup.find_all(string=re.compile(r'Fast Fit|Introductory|Session', re.IGNORECASE))
        print(f"Elements mentioning event keywords: {len(fast_fit_elements)}")
        
        for elem in fast_fit_elements[:3]:
            parent = elem.parent if hasattr(elem, 'parent') else None
            if parent:
                print(f"  Text: '{elem.strip()}'")
                print(f"  Parent tag: {parent.name}")
                print(f"  Parent classes: {parent.get('class', [])}")
                
                # Look for link in parent or ancestors
                link_parent = parent
                for _ in range(5):  # Check up to 5 levels up
                    if link_parent and link_parent.name == 'a' and link_parent.get('href'):
                        print(f"  Found link: {link_parent.get('href')}")
                        break
                    link_parent = link_parent.parent if hasattr(link_parent, 'parent') else None
        
        # Check if the page might be loading content dynamically
        print("\n=== DYNAMIC CONTENT CHECK ===")
        scripts = soup.find_all('script')
        print(f"Script tags found: {len(scripts)}")
        
        for script in scripts:
            if script.string and any(keyword in script.string.lower() for keyword in ['react', 'vue', 'angular', 'ajax', 'fetch']):
                print("  Found script with dynamic loading keywords")
                break
        
        # Look for any JSON data that might contain event info
        json_scripts = soup.find_all('script', type='application/json')
        print(f"JSON script tags: {len(json_scripts)}")
        
        # Check if there are any error messages or empty state indicators
        print("\n=== PAGE CONTENT ANALYSIS ===")
        page_text = soup.get_text().lower()
        
        if 'no results' in page_text or 'not found' in page_text:
            print("  Page contains 'no results' text")
        
        if 'loading' in page_text:
            print("  Page contains 'loading' text")
            
        if len(page_text) < 1000:
            print("  Page has very little text content - might be loading dynamically")
        
        print(f"\nPage text length: {len(page_text)} characters")
        print(f"First 500 characters: {page_text[:500]}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_webook_search()