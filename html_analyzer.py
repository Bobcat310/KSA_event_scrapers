import re
from bs4 import BeautifulSoup

def analyze_html_file(filename):
    """Analyze the saved HTML file to find description content"""
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"File {filename} not found")
        return
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    print("=== HTML CONTENT ANALYSIS ===")
    print(f"Total HTML length: {len(html_content)} characters")
    
    # Look for the expected description text
    description_keywords = ['Smart Ports', 'Logistics', 'Summit', 'two-day', 'conference', 'Jeddah', 'Vision 2030']
    
    print("\n=== SEARCHING FOR DESCRIPTION CONTENT ===")
    for keyword in description_keywords:
        if keyword.lower() in html_content.lower():
            print(f"✓ Found keyword: '{keyword}'")
            
            # Find the context around this keyword
            pattern = rf'.{{0,200}}{re.escape(keyword)}.{{0,200}}'
            matches = re.finditer(pattern, html_content, re.IGNORECASE | re.DOTALL)
            for i, match in enumerate(matches):
                if i < 2:  # Show first 2 matches
                    print(f"  Context {i+1}: ...{match.group()}...")
        else:
            print(f"✗ Missing keyword: '{keyword}'")
    
    # Look for all divs with FAFAFA background
    print("\n=== FAFAFA DIVS ANALYSIS ===")
    fafafa_divs = soup.find_all('div', style=lambda val: val and 'fafafa' in val.lower())
    print(f"Found {len(fafafa_divs)} divs with FAFAFA styling")
    
    for i, div in enumerate(fafafa_divs):
        print(f"\nFAFAFA Div {i+1}:")
        print(f"  Style: {div.get('style', 'N/A')}")
        print(f"  Content length: {len(div.get_text(strip=True))}")
        print(f"  Content preview: {div.get_text(strip=True)[:200]}...")
        print(f"  HTML: {str(div)[:300]}...")
    
    # Look for any div containing substantial description-like content
    print("\n=== POTENTIAL DESCRIPTION DIVS ===")
    all_divs = soup.find_all('div')
    description_divs = []
    
    for div in all_divs:
        text = div.get_text(strip=True)
        if len(text) > 100:  # Substantial content
            # Check if it contains description-like keywords
            if any(keyword.lower() in text.lower() for keyword in ['summit', 'conference', 'transformation', 'logistics']):
                description_divs.append((div, text))
    
    print(f"Found {len(description_divs)} divs with potential description content")
    
    for i, (div, text) in enumerate(description_divs[:3]):  # Show top 3
        print(f"\nPotential Description Div {i+1}:")
        print(f"  Style: {div.get('style', 'N/A')}")
        print(f"  Class: {div.get('class', 'N/A')}")
        print(f"  Content length: {len(text)}")
        print(f"  Content: {text[:300]}...")
        print(f"  HTML structure: {div.name}")
        
        # Check parent and children
        if div.parent:
            print(f"  Parent: {div.parent.name} with style: {div.parent.get('style', 'N/A')}")
    
    # Look for any script tags that might be loading content dynamically
    print("\n=== DYNAMIC CONTENT CHECK ===")
    scripts = soup.find_all('script')
    print(f"Found {len(scripts)} script tags")
    
    for script in scripts:
        if script.string and ('description' in script.string.lower() or 'content' in script.string.lower()):
            print("Found script with description/content keywords:")
            print(f"  {script.string[:200]}...")

if __name__ == "__main__":
    analyze_html_file('debug_event_page.html')