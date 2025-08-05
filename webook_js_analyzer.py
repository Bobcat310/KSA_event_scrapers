import requests
import re
import json
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Set

def log(msg: str):
    print(f"[LOG] {msg}")

class WeBookJSAnalyzer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        self.found_endpoints = set()
        self.potential_apis = []

    def extract_js_files(self, html_content: str, base_url: str) -> List[str]:
        """Extract JavaScript file URLs from HTML"""
        js_files = []
        
        # Find script tags with src
        script_pattern = r'<script[^>]+src=["\']([^"\']+)["\'][^>]*>'
        scripts = re.findall(script_pattern, html_content, re.IGNORECASE)
        
        for script in scripts:
            if script.startswith('http'):
                js_files.append(script)
            elif script.startswith('/'):
                js_files.append(urljoin(base_url, script))
            else:
                js_files.append(urljoin(base_url + '/', script))
        
        # Also look for module preloads
        preload_pattern = r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']modulepreload["\']'
        preloads = re.findall(preload_pattern, html_content, re.IGNORECASE)
        
        for preload in preloads:
            if preload.startswith('http'):
                js_files.append(preload)
            elif preload.startswith('/'):
                js_files.append(urljoin(base_url, preload))
        
        return list(set(js_files))

    def analyze_js_file(self, js_url: str) -> Dict:
        """Analyze a JavaScript file for API endpoints"""
        log(f"Analyzing JS file: {js_url}")
        
        try:
            response = self.session.get(js_url, timeout=10)
            if response.status_code != 200:
                return {'url': js_url, 'status': 'failed', 'endpoints': []}
            
            js_content = response.text
            endpoints = []
            
            # Patterns to look for API endpoints
            api_patterns = [
                # API URLs
                r'["\']https?://[^"\']*api[^"\']*["\']',
                r'["\']https?://[^"\']*graphql[^"\']*["\']',
                r'["\']https?://[^"\']*contentful[^"\']*["\']',
                
                # Relative API paths
                r'["\'][/]?api[/][^"\']*["\']',
                r'["\'][/]?graphql[^"\']*["\']',
                r'["\'][/]?v\d+[/][^"\']*["\']',
                
                # Common API patterns
                r'["\'][^"\']*search[^"\']*["\']',
                r'["\'][^"\']*experience[s]?[^"\']*["\']',
                r'["\'][^"\']*event[s]?[^"\']*["\']',
                
                # Content management
                r'["\']https://[^"\']*contentful[^"\']*["\']',
                r'["\']https://cdn\.contentful\.com[^"\']*["\']',
                
                # Generic endpoints
                r'baseURL\s*[:=]\s*["\']([^"\']+)["\']',
                r'apiUrl\s*[:=]\s*["\']([^"\']+)["\']',
                r'endpoint\s*[:=]\s*["\']([^"\']+)["\']',
            ]
            
            for pattern in api_patterns:
                matches = re.findall(pattern, js_content, re.IGNORECASE)
                for match in matches:
                    # Clean up the match
                    if isinstance(match, tuple):
                        match = match[0] if match[0] else match[1]
                    
                    clean_match = match.strip('\'"')
                    if clean_match and len(clean_match) > 3:
                        endpoints.append(clean_match)
                        self.found_endpoints.add(clean_match)
            
            # Look for specific webook.com patterns
            webook_patterns = [
                r'webook\.com[^"\']*',
                r'vy53kjqs34an',  # Contentful space ID from your HTML
                r'space[s]?["\']:\s*["\']([^"\']+)["\']',
                r'accessToken["\']:\s*["\']([^"\']+)["\']'
            ]
            
            for pattern in webook_patterns:
                matches = re.findall(pattern, js_content, re.IGNORECASE)
                endpoints.extend(matches)
            
            return {
                'url': js_url,
                'status': 'success',
                'size': len(js_content),
                'endpoints': list(set(endpoints))
            }
            
        except Exception as e:
            log(f"Error analyzing {js_url}: {e}")
            return {'url': js_url, 'status': 'error', 'error': str(e), 'endpoints': []}

    def test_potential_endpoints(self) -> List[Dict]:
        """Test discovered endpoints to see which ones work"""
        log("Testing discovered endpoints...")
        
        working_endpoints = []
        
        # Convert relative URLs to absolute
        base_url = "https://webook.com"
        test_endpoints = []
        
        for endpoint in self.found_endpoints:
            if endpoint.startswith('http'):
                test_endpoints.append(endpoint)
            elif endpoint.startswith('/'):
                test_endpoints.append(base_url + endpoint)
            elif not endpoint.startswith('#') and '.' not in endpoint:
                test_endpoints.append(f"{base_url}/api/{endpoint}")
        
        # Add some common API patterns to test
        common_patterns = [
            f"{base_url}/api/search",
            f"{base_url}/api/experiences",
            f"{base_url}/api/events",
            f"{base_url}/graphql",
            "https://cdn.contentful.com/spaces/vy53kjqs34an/entries",
            "https://api.contentful.com/spaces/vy53kjqs34an/entries",
        ]
        
        test_endpoints.extend(common_patterns)
        test_endpoints = list(set(test_endpoints))
        
        for endpoint in test_endpoints:
            try:
                log(f"Testing: {endpoint}")
                
                # Try different approaches
                test_params = [
                    {},
                    {'q': 'KSA'},
                    {'search': 'KSA'},
                    {'query': 'KSA'},
                    {'content_type': 'experience'},
                    {'content_type': 'event'}
                ]
                
                for params in test_params:
                    try:
                        response = self.session.get(endpoint, params=params, timeout=5)
                        
                        result = {
                            'url': endpoint,
                            'params': params,
                            'status_code': response.status_code,
                            'content_type': response.headers.get('content-type', ''),
                            'size': len(response.content)
                        }
                        
                        if response.status_code == 200:
                            log(f"✅ Success: {endpoint} - {response.status_code}")
                            
                            # Check if it's JSON
                            if 'json' in result['content_type'].lower():
                                try:
                                    json_data = response.json()
                                    result['json_sample'] = str(json_data)[:500]
                                    
                                    # Check if it contains event-like data
                                    json_str = str(json_data).lower()
                                    if any(keyword in json_str for keyword in ['experience', 'event', 'session', 'fast fit', 'saudi']):
                                        result['likely_events'] = True
                                        log(f"🎯 Potential events data found!")
                                        
                                        # Save full response
                                        filename = f"webook_api_response_{len(working_endpoints)}.json"
                                        with open(filename, 'w', encoding='utf-8') as f:
                                            json.dump(json_data, f, indent=2, ensure_ascii=False)
                                        result['saved_to'] = filename
                                        log(f"💾 Saved response to {filename}")
                                except:
                                    result['json_sample'] = response.text[:500]
                            else:
                                result['text_sample'] = response.text[:200]
                            
                            working_endpoints.append(result)
                            break  # Found working params, move to next endpoint
                        
                        elif response.status_code in [401, 403]:
                            log(f"🔒 Auth required: {endpoint}")
                            result['needs_auth'] = True
                            working_endpoints.append(result)
                            break
                        
                    except requests.RequestException:
                        continue
                        
            except Exception as e:
                log(f"Error testing {endpoint}: {e}")
                continue
        
        return working_endpoints

    def analyze_webook(self):
        """Main analysis function"""
        log("🔍 Starting WeBook.com JavaScript Analysis...")
        
        # Get the main page
        base_url = "https://webook.com"
        search_url = "https://webook.com/en/search?q=KSA"
        
        try:
            log(f"Fetching: {search_url}")
            response = self.session.get(search_url, timeout=10)
            html_content = response.text
            
            # Extract JavaScript files
            js_files = self.extract_js_files(html_content, base_url)
            log(f"Found {len(js_files)} JavaScript files")
            
            # Analyze each JS file
            js_analysis = []
            for js_file in js_files[:10]:  # Limit to first 10 to avoid overload
                analysis = self.analyze_js_file(js_file)
                js_analysis.append(analysis)
                
                if analysis['endpoints']:
                    log(f"Found {len(analysis['endpoints'])} potential endpoints in {js_file}")
            
            # Test the endpoints
            working_endpoints = self.test_potential_endpoints()
            
            # Save results
            results = {
                'js_files': js_files,
                'js_analysis': js_analysis,
                'all_endpoints': list(self.found_endpoints),
                'working_endpoints': working_endpoints
            }
            
            with open('webook_js_analysis.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            # Print summary
            log("\n" + "="*50)
            log("📊 JAVASCRIPT ANALYSIS SUMMARY")
            log("="*50)
            log(f"JavaScript files analyzed: {len(js_files)}")
            log(f"Total endpoints discovered: {len(self.found_endpoints)}")
            log(f"Working endpoints: {len(working_endpoints)}")
            
            if working_endpoints:
                log("\n🎯 Working endpoints found:")
                for endpoint in working_endpoints:
                    status = endpoint['status_code']
                    url = endpoint['url']
                    if endpoint.get('likely_events'):
                        log(f"  ⭐ {url} (Status: {status}) - LIKELY EVENTS DATA!")
                    else:
                        log(f"  ✅ {url} (Status: {status})")
            
            log(f"\n📁 Results saved to: webook_js_analysis.json")
            
            if not working_endpoints:
                log("\n💡 No working endpoints found. This could mean:")
                log("   - APIs require authentication")
                log("   - APIs use POST requests with specific payloads")
                log("   - Content is generated server-side")
                log("   - Anti-bot measures are in place")
                
                log("\n🔄 Alternative approaches:")
                log("   1. Try the manual browser method")
                log("   2. Look for GraphQL introspection")
                log("   3. Check for hidden API documentation")
            
            return results
            
        except Exception as e:
            log(f"Error during analysis: {e}")
            return None

def main():
    """Main execution"""
    analyzer = WeBookJSAnalyzer()
    results = analyzer.analyze_webook()
    
    if results and results['working_endpoints']:
        log("\n🚀 Next steps:")
        log("1. Check the saved JSON response files")
        log("2. Use the working endpoints to build an API scraper")
        log("3. Run: python3 webook_manual_api_finder.py convert")

if __name__ == "__main__":
    main()