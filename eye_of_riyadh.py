import requests
from bs4 import BeautifulSoup
import csv

def scrape_eyeofriyadh_events(query="KSA"):
    """
    Scrapes event data from eyeofriyadh.com for a given query (e.g., "KSA").

    Args:
        query (str): The search term for events. Defaults to "KSA".

    Returns:
        list: A list of dictionaries, where each dictionary represents an event.
    """
    base_url = "https://www.eyeofriyadh.com/events/"
    search_url = f"{base_url}index.php?s={query}&search_post_type=place&fcity=&fcat=&count=&sort-by=&sort="
    
    # Define headers to mimic a web browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Connection': 'keep-alive',
    }
    
    events_data = []

    print(f"Attempting to scrape events from: {search_url}")

    try:
        response = requests.get(search_url, headers=headers, timeout=10) # Added timeout
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all event blocks. The style attribute is quite specific, using a partial match.
        # This selector targets the main div container for each event listing.
        event_blocks = soup.find_all('div', style=lambda value: value and 'margin-bottom:25px; display: block; padding: 10px; border-bottom:1px solid #ADB0B6;' in value)

        if not event_blocks:
            print("No event blocks found with the specified styling. The website's HTML structure might have changed.")
            print("Consider inspecting the page HTML again to find updated selectors.")
            return []

        for block in event_blocks:
            # Extract Date
            date_element = block.find('div', style=lambda value: value and 'color:#666A73; padding:0px 10px 3px 10px;' in value)
            event_date = date_element.text.strip() if date_element else 'N/A'

            # Extract Name and its relative URL
            name_link_div = block.find('div', style=lambda value: value and 'color:#666A73; padding:3px 10px;' in value)
            event_name = 'N/A'
            event_relative_url = 'N/A'
            if name_link_div:
                name_element = name_link_div.find('a', style=lambda value: value and 'color:#000; font-weight:700; font-size:12px;letter-spacing: 0px; line-height:18px;' in value)
                if name_element:
                    event_name = name_element.text.strip()
                    event_relative_url = name_element.get('href', 'N/A')

            # Extract Venue
            venue_element = block.find('div', style=lambda value: value and 'color:#ADB0B6;padding:0px 10px 10px 10px' in value)
            event_venue = venue_element.text.strip().replace('\t', '').replace('\xa0', '') if venue_element else 'N/A' # Clean up tabs and non-breaking spaces

            # Extract Description
            description_element = block.find('div', style=lambda value: value and 'color:#666A73; margin-bottom:10px;' in value)
            event_description = description_element.text.strip() if description_element else 'N/A'

            # Construct full URL for 'More Details'
            event_full_url = f"{base_url}{event_relative_url}" if event_relative_url and not event_relative_url.startswith('http') else event_relative_url

            events_data.append({
                'Name': event_name,
                'Date': event_date,
                'Venue': event_venue,
                'Description': event_description,
                'URL': event_full_url
            })

    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err} (URL: {search_url})")
    except requests.exceptions.ConnectionError as err:
        print(f"Error connecting to the server: {err} (URL: {search_url})")
    except requests.exceptions.Timeout as err:
        print(f"The request timed out: {err} (URL: {search_url})")
    except requests.exceptions.RequestException as err:
        print(f"An unknown error occurred: {err} (URL: {search_url})")
    except Exception as e:
        print(f"An unexpected error occurred during parsing: {e}")

    return events

# --- Main execution ---
if __name__ == "__main__":
    ksa_events = scrape_eyeofriyadh_events("KSA")

    if ksa_events:
        csv_file_name = 'eyeofriyadh_ksa_events.csv'
        # Get keys from the first dictionary to use as CSV headers
        keys = ksa_events[0].keys()
        
        try:
            with open(csv_file_name, 'w', newline='', encoding='utf-8') as output_file:
                dict_writer = csv.DictWriter(output_file, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(ksa_events)
            print(f"Successfully scraped {len(ksa_events)} events and saved them to {csv_file_name}")
        except IOError as e:
            print(f"Error writing to CSV file {csv_file_name}: {e}")
    else:
        print("No events were scraped or an error occurred during the scraping process.")