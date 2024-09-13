from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import json 
import os


# Configure Chrome options for headless mode
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode
chrome_options.add_argument("--disable-gpu")  # Disable GPU usage
chrome_options.add_argument("--window-size=1920,1080")  # Set window size to avoid issues with some elements not being visible
chrome_options.add_argument("--no-sandbox")  # Bypass OS security model
chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems in Docker
chrome_options.add_argument("--disable-extensions")  # Disable extensions

# Initialize the WebDriver with Chrome options
driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, 20)


# Open the flight details webpage
driver.get("https://www.changiairport.com/en/flights/departures.html")

# Path to the JSON file
json_file_path = "departure_flights_1.json"

# Check if the file exists
if os.path.exists(json_file_path):
    # Load the JSON file into a dictionary if it exists
    with open(json_file_path, "r") as json_file:
        loaded_data = json.load(json_file)
    
    # Convert the list of flights back into a dictionary keyed by 'flight_id'
    departure_flights_dict = {flight['flight_id']: flight for flight in loaded_data['flights']}
    print(f"Total flights loaded: {len(departure_flights_dict)}")

else:
    # Initialize an empty dictionary if the file does not exist
    departure_flights_dict = {}
    print("No existing data found. Starting with an empty flight dictionary.")



def scroll_and_click(element):
    """Scrolls to an element and clicks it using JavaScript."""
    driver.execute_script("arguments[0].scrollIntoView(true);", element)
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(element))
    driver.execute_script("arguments[0].click();", element)

def choose_date(date):
    """Selects a date from the date picker and waits for the flights list to load."""
    try:
        # Click the calendar input to open the date picker
        calendar_input = driver.find_element(By.CSS_SELECTOR, 'div.react-datepicker__input-container input[type="button"]')
        if calendar_input:
            print("Calendar button found")
        scroll_and_click(calendar_input)

        # Wait for the date picker to be visible
        date_picker = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.CLASS_NAME, 'react-datepicker__month'))
        )
        print("Date picker is visible")

        # Generate the correct class name with two digits for the day
        day_str = f"{date.day:03d}"
        target_day_class = f"react-datepicker__day--{day_str}"
        
        # Debug: Print all available day elements
        #day_elements = driver.find_elements(By.CLASS_NAME, 'react-datepicker__day')
        #for elem in day_elements:
        #    print(f"Found day element: {elem.text} with class: {elem.get_attribute('class')}")
        
        # Locate and click the target day element
        date_element = driver.find_element(By.CLASS_NAME, target_day_class)
        scroll_and_click(date_element)
        print("Date clicked")
        driver.save_screenshot("screenshot1.png")  # Save a screenshot for debugging
        
        # Wait for the flights list to update
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.data.flightlist'))  # Adjust the selector based on actual flights list container
        )
        print("Flights list should be updated now")
        driver.save_screenshot("screenshot2.png")  # Save a screenshot to confirm the flights list

    except Exception as e:
        print(f"Date picker not visible or error occurred: {e}")
        driver.save_screenshot("Exception in date picker.png")  # Save a screenshot for debugging


def create_flight_id(flight_number, departure_time):
        return f"{flight_number}_{departure_time}"

def update_or_add_flight(flight_dict, new_flight):
    """Updates an existing flight or adds a new one in the dictionary."""
    flight_id = new_flight['flight_id']
    flight_gate = new_flight['gate_number']
    if flight_id in flight_dict:
        if "NEW GATE" in new_flight['flight_status'] or "RE-TIMED" in new_flight['flight_status']:
            flight_dict[flight_id] = new_flight  # Update the existing flight
    elif flight_id not in flight_dict and flight_gate != "Unknown":
        flight_dict[flight_id] = new_flight  # Add new flight if not found

def process_flights(date, flight_elements, start_index, last_time, stop_loop, flight_dict):
    last_processed_index = start_index
    time_threshold = timedelta(hours=2)

    for idx, flight_element in enumerate(flight_elements[start_index:], start=start_index):
        try:
            # Extracting the time
            time_div = flight_element.find_element(By.CSS_SELECTOR, 'div.flightlist__item-time')
            unmodified_time = None
            updated_time = None

            try:
                previous_time = time_div.find_element(By.CSS_SELECTOR, 'span.previous-time').text.strip()
                updated_time = time_div.text.replace(previous_time, '').strip()
                unmodified_time = previous_time
            except Exception:
                unmodified_time = time_div.text.strip()
                updated_time = unmodified_time

            if '(+1d)' in updated_time:
                flight_date = date + timedelta(days=1)
                updated_time = updated_time.replace('(+1d)', '').strip()
            else:
                flight_date = date

            try:
                departure_time = datetime.strptime(updated_time, '%H:%M').time()
                unmodified_time = datetime.strptime(unmodified_time, '%H:%M').time()
            except ValueError:
                continue

            departure_datetime = datetime.combine(flight_date, departure_time)
            unmodified_datetime = datetime.combine(date, unmodified_time)

            departure_datetime_str = departure_datetime.strftime('%Y-%m-%d %H:%M:%S')
            unmodified_datetime_str = unmodified_datetime.strftime('%Y-%m-%d %H:%M:%S')


            flight_number = flight_element.find_element(By.CSS_SELECTOR, 'span.airport__flight-number').text.strip()
            airline_name = flight_element.find_element(By.CSS_SELECTOR, 'span.airport__name').text.strip()
            destination = flight_element.find_element(By.CSS_SELECTOR, 'div.airport-name').text.strip()
            terminal = flight_element.find_element(By.CSS_SELECTOR, 'div.flightlist__item-terminal').text.strip() or 'Unknown'
            flight_status = flight_element.find_element(By.CSS_SELECTOR, 'div.flightlist__item-status .status').text.strip()

            try:
                # Find the gate number container
                gate_div = flight_element.find_element(By.CSS_SELECTOR, 'div.flightlist__item-boarding div:nth-child(2) span.gate')
                gate_number = gate_div.text.strip()
            except Exception as e:
                gate_number = 'Unknown'  # Assign 'Unknown' if the gate number is not found

            flight_id = create_flight_id(flight_number, unmodified_datetime_str)

            # Construct the new flight dictionary
            new_flight = {
                'flight_id': flight_id,
                'flight_number': flight_number,
                'type': 'Departure',
                'original_departure_time': unmodified_datetime_str,
                'actual_departure_time': departure_datetime_str,
                'airline_name': airline_name,
                'destination': destination,
                'terminal': terminal,
                'gate_number': gate_number,
                'flight_status': flight_status
            }

            # to check whether flights are of the next day 
            if last_time and unmodified_datetime < last_time - time_threshold:
                stop_loop = True
                break
            else:
                last_time = unmodified_datetime

            # Update or add the flight in the dictionary
            update_or_add_flight(flight_dict, new_flight)

            last_processed_index = idx
        except Exception as e:
            print("Error processing flight details:", e)

    return last_time, stop_loop, last_processed_index


def scrape_flights_for_date(date, flight_dict):
    # Initialize variables
    last_time = None
    stop_loop = False
    last_processed_index = 0

    choose_date(date)

    while not stop_loop:
        try:
            flight_elements = driver.find_elements(By.CSS_SELECTOR, 'div.data.flightlist > a.flightlist__item.display-lg')
            last_time, stop_loop, last_processed_index = process_flights(date, flight_elements, last_processed_index, last_time, stop_loop, flight_dict)

            if stop_loop:
                break

            try:
                load_more_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.gray-bg.next-flights')))
                driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                WebDriverWait(driver, 10).until(EC.visibility_of(load_more_button))

                driver.execute_script("arguments[0].click();", load_more_button)
                
                WebDriverWait(driver, 10).until(
                    lambda driver: len(driver.find_elements(By.CSS_SELECTOR, 'div.data.flightlist > a.flightlist__item.display-lg')) > len(flight_elements)
                )
            except Exception as e:
                print("No more flights to load or error clicking the button:", e)
                break

        except Exception as e:
            print("Error loading flights or clicking 'Load More':", e)
            break

def convert_dict_to_list(flight_dict):
    """Convert the flight dictionary to a list."""
    return list(flight_dict.values())

# Main execution
start_date = datetime.today()

for day in range(2):
    target_date = start_date + timedelta(days=day)
    print(f"Scraping flights for {target_date.strftime('%Y-%m-%d')}")
    scrape_flights_for_date(target_date, departure_flights_dict)

# Convert the dictionary to a list of flight details if needed
departure_flights_list = list(departure_flights_dict.values())

# Save the list or dictionary directly to a JSON file
with open("departure_flights_1.json", "w") as json_file:
    json.dump({"flights": departure_flights_list, "number_of_flights": len(departure_flights_list)}, json_file, indent=4)

print(f"Total flights saved: {len(departure_flights_list)}")
driver.quit()
