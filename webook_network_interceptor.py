from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
import requests
from typing import List, Dict, Any

def log(msg: str):
    print(f"[LOG] {msg}")

class WeBookNetworkInterceptor:
    def __init__(self):
        self.setup_driver()
        self.api_calls = []
        
    def setup_driver(self):
        """Setup Chrome driver with network logging enabled"""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        
        # Enable logging for network requests
        chrome_options.add_argument('--enable-logging')
        chrome_options.add_argument('--log-level=0')
        chrome_options.add_argument('--v=1')
        
        # Enable performance logging to capture network traffic
        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        try:
            # Use webdriver-manager to automatically handle ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            log("Chrome driver with network logging initialized successfully")
        except Exception as e:
            log(f"Error initializing Chrome driver with webdriver-manager: {e}")
            log("Trying alternative approach...")
            
            # Fallback: try without webdriver-manager
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                log("Chrome driver initialized with fallback method")
            except Exception as e2:
                log(f"Fallback also failed: {e2}")
                log("Chrome installation issues detected. Let's try a manual approach...")
                raise
    
    def get_network_logs(self) -> List[Dict]:
        """Extract network logs from browser"""
        try:
            logs = self.driver.get_log('performance')
            network_requests = []
            
            for log_entry in logs:
                message = json.loads(log_entry['message'])
                
                # Filter for network events
                if message.get('message', {}).get('method') in [
                    'Network.requestWillBeSent',
                    'Network.responseReceived'
                ]:
                    network_requests.append(message)
            
            return network_requests
        except Exception as e:
            log(f"Error getting network logs: {e}")
            return []
    
    def analyze_network_traffic(self) -> List[str]:
        """Analyze network traffic to find API endpoints"""
        log("Analyzing network traffic...")
        
        network_logs = self.get_network_logs()
        api_endpoints = []
        
        for log_entry in network_logs:
            try:
                message = log_entry.get('message', {})
                method = message.get('method')
                params = message.get('params', {})
                
                if method == 'Network.requestWillBeSent':
                    request = params.get('request', {})
                    url = request.get('url', '')
                    request_method = request.get('method', '')
                    
                    # Look for API endpoints
                    if any(keyword in url.lower() for keyword in [
                        'api', 'graphql', 'search', 'experience', 'event', 'contentful', 'cms'
                    ]):
                        api_info = {
                            'url': url,
                            'method': request_method,
                            'headers': request.get('headers', {}),
                            'postData': request.get('postData', '')
                        }
                        
                        if url not in [ep['url'] for ep in api_endpoints]:
                            api_endpoints.append(api_info)
                            log(f"Found API endpoint: {request_method} {url}")
                            
                            # If it has post data, log it
                            if api_info['postData']:
                                log(f"  POST data: {api_info['postData'][:200]}...")
                
            except Exception as e:
                continue
        
        return api_endpoints
    
    def save_network_analysis(self, api_endpoints: List[Dict]):
        """Save network analysis to file"""
        try:
            with open('webook_api_endpoints.json', 'w', encoding='utf-8') as f:
                json.dump(api_endpoints, f, indent=2, ensure_ascii=False)
            log(f"Saved {len(api_endpoints)} API endpoints to webook_api_endpoints.json")
            
            # Also create a summary file
            with open('webook_api_summary.txt', 'w', encoding='utf-8') as f:
                f.write("WeBook.com API Endpoints Analysis\n")
                f.write("=" * 50 + "\n\n")
                
                for i, endpoint in enumerate(api_endpoints, 1):
                    f.write(f"{i}. {endpoint['method']} {endpoint['url']}\n")
                    
                    # Add key headers
                    if endpoint['headers']:
                        f.write("   Headers:\n")
                        for key, value in endpoint['headers'].items():
                            if key.lower() in ['authorization', 'x-api-key', 'content-type']:
                                f.write(f"     {key}: {value}\n")
                    
                    # Add POST data if present
                    if endpoint['postData']:
                        f.write(f"   POST Data: {endpoint['postData'][:100]}...\n")
                    
                    f.write("\n")
            
            log("Saved API summary to webook_api_summary.txt")
            
        except Exception as e:
            log(f"Error saving network analysis: {e}")
    
    def test_api_endpoints(self, api_endpoints: List[Dict]) -> List[Dict]:
        """Test the discovered API endpoints directly"""
        log("Testing discovered API endpoints...")
        
        results = []
        
        for i, endpoint in enumerate(api_endpoints, 1):
            log(f"Testing endpoint {i}/{len(api_endpoints)}: {endpoint['url']}")
            
            try:
                # Prepare headers
                headers = endpoint.get('headers', {})
                
                # Make the request
                if endpoint['method'].upper() == 'POST':
                    response = requests.post(
                        endpoint['url'],
                        headers=headers,
                        data=endpoint.get('postData', ''),
                        timeout=10
                    )
                else:
                    response = requests.get(
                        endpoint['url'],
                        headers=headers,
                        timeout=10
                    )
                
                result = {
                    'url': endpoint['url'],
                    'method': endpoint['method'],
                    'status_code': response.status_code,
                    'content_type': response.headers.get('content-type', ''),
                    'content_length': len(response.content),
                    'sample_content': response.text[:500] if response.text else ''
                }
                
                results.append(result)
                
                log(f"  Status: {response.status_code}, Type: {result['content_type']}, Size: {result['content_length']}")
                
                # If it looks like event data, save it
                if (response.status_code == 200 and 
                    'json' in result['content_type'].lower() and 
                    any(keyword in response.text.lower() for keyword in ['experience', 'event', 'session', 'fast fit'])):
                    
                    filename = f"webook_api_response_{i}.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    log(f"  💾 Saved promising response to {filename}")
                
            except Exception as e:
                log(f"  ❌ Error testing endpoint: {e}")
                results.append({
                    'url': endpoint['url'],
                    'method': endpoint['method'],
                    'status_code': 'ERROR',
                    'error': str(e)
                })
        
        return results
    
    def intercept_webook_traffic(self):
        """Main method to intercept WeBook traffic"""
        log("🕵️  Starting WeBook.com network traffic interception...")
        
        try:
            # Navigate to the search page
            search_url = "https://webook.com/en/search?q=KSA"
            log(f"🌐 Loading: {search_url}")
            
            self.driver.get(search_url)
            
            # Wait and let the page load completely
            log("⏳ Waiting for page to load and make API calls...")
            time.sleep(15)  # Give plenty of time for all requests
            
            # Try scrolling to trigger more requests
            log("📜 Scrolling to trigger additional requests...")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(5)
            
            # Try typing in search box if it exists
            try:
                search_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="search"], input[placeholder*="search" i]')
                if search_inputs:
                    log("🔍 Found search input, trying to trigger search...")
                    search_input = search_inputs[0]
                    search_input.clear()
                    search_input.send_keys("Fast Fit")
                    time.sleep(3)
                    
                    # Look for search button
                    search_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Search') or contains(@aria-label, 'search')]")
                    if search_buttons:
                        search_buttons[0].click()
                        log("🎯 Clicked search button")
                        time.sleep(10)
            except:
                log("⚠️  Could not interact with search - continuing...")
            
            # Try different URLs to trigger more API calls
            test_urls = [
                "https://webook.com/en/search?q=Saudi+Arabia",
                "https://webook.com/en/search?q=Riyadh",
                "https://webook.com/en/search?q=fitness",
                "https://webook.com/en/experiences"
            ]
            
            for test_url in test_urls:
                log(f"🌐 Testing: {test_url}")
                self.driver.get(test_url)
                time.sleep(8)
            
            # Analyze all captured network traffic
            api_endpoints = self.analyze_network_traffic()
            
            if not api_endpoints:
                log("❌ No API endpoints found in network traffic")
                return []
            
            # Save the analysis
            self.save_network_analysis(api_endpoints)
            
            # Test the endpoints directly
            test_results = self.test_api_endpoints(api_endpoints)
            
            return api_endpoints, test_results
            
        except Exception as e:
            log(f"❌ Error during traffic interception: {e}")
            return [], []
    
    def close(self):
        """Close the driver"""
        if hasattr(self, 'driver'):
            self.driver.quit()
            log("🔚 Driver closed")

def main():
    """Main execution"""
    interceptor = None
    
    try:
        interceptor = WeBookNetworkInterceptor()
        api_endpoints, test_results = interceptor.intercept_webook_traffic()
        
        if api_endpoints:
            log("\n" + "="*50)
            log("📊 NETWORK INTERCEPTION SUMMARY")
            log("="*50)
            log(f"🔍 Found {len(api_endpoints)} API endpoints")
            log(f"🧪 Tested {len(test_results)} endpoints")
            
            # Show the most promising endpoints
            log("\n🎯 Most promising API endpoints:")
            for i, endpoint in enumerate(api_endpoints[:5], 1):
                log(f"{i}. {endpoint['method']} {endpoint['url']}")
            
            log("\n📁 Files created:")
            log("   - webook_api_endpoints.json (Full API details)")
            log("   - webook_api_summary.txt (Human readable summary)")
            log("   - webook_api_response_*.json (API response samples)")
            
            log("\n💡 Next steps:")
            log("   1. Check the JSON response files for event data")
            log("   2. Use the API endpoints to build a direct API scraper")
            log("   3. Look for GraphQL endpoints if available")
        else:
            log("❌ No API endpoints discovered")
            log("💡 This could mean:")
            log("   - The site uses WebSocket connections")
            log("   - API calls are made after user interaction")
            log("   - The content is server-side rendered")
            log("   - Anti-bot detection is blocking network inspection")
        
    except Exception as e:
        log(f"❌ Main execution error: {e}")
    finally:
        if interceptor:
            interceptor.close()

if __name__ == "__main__":
    main()