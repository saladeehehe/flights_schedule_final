from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import json

# Initialize the WebDriver
driver = webdriver.Chrome()
wait = WebDriverWait(driver, 15)

# Open the flight details webpage
driver.get("https://www.changiairport.com/en/flights/departures.html")

try:
    with open("departures_data.json", "r") as f:
        existing_data = json.load(f)
    existing_data = existing_data.get("flights", [])
except FileNotFoundError:
    existing_data = []

# Load seen_data.txt
try:
    with open("seen_data.txt", "r") as f:
        seen_flights = set(line.strip() for line in f.readlines())
except FileNotFoundError:
    seen_flights = set()

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
        day_elements = driver.find_elements(By.CLASS_NAME, 'react-datepicker__day')
        for elem in day_elements:
            print(f"Found day element: {elem.text} with class: {elem.get_attribute('class')}")
        
        # Locate and click the target day element
        date_element = driver.find_element(By.CLASS_NAME, target_day_class)
        scroll_and_click(date_element)
        print("Date clicked")
        #driver.save_screenshot("screenshot1.png")  # Save a screenshot for debugging
        
        # Wait for the flights list to update
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.data.flightlist'))  # Adjust the selector based on actual flights list container
        )
        print("Flights list should be updated now")
        #driver.save_screenshot("screenshot2.png")  # Save a screenshot to confirm the flights list

    except Exception as e:
        print(f"Date picker not visible or error occurred: {e}")
        driver.save_screenshot("Exception in date picker.png")  # Save a screenshot for debugging


def create_flight_id(flight_number, departure_time):
        return f"{flight_number}_{departure_time}"


###################### PROCESS FLIGHTS WITHIN DAY 
def process_flights(date, flight_elements, start_index, last_time, stop_loop, invalid_gate_count):
    global seen_flights, departure_flights_data
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

            flight_number = flight_element.find_element(By.CSS_SELECTOR, 'span.airport__flight-number').text.strip()
            airline_name = flight_element.find_element(By.CSS_SELECTOR, 'span.airport__name').text.strip()
            destination = flight_element.find_element(By.CSS_SELECTOR, 'div.airport-name').text.strip()
            terminal = flight_element.find_element(By.CSS_SELECTOR, 'div.flightlist__item-terminal').text.strip() or 'Unknown'        
            try:
                # Find the gate number container
                gate_div = flight_element.find_element(By.CSS_SELECTOR, 'div.flightlist__item-boarding div:nth-child(2) span.gate')
                gate_number = gate_div.text.strip()
            except Exception as e:
                gate_number = 'Unknown'  # Assign 'Unknown' if the gate number is not found
            if gate_number == 'Unknown':
                invalid_gate_count += 1
            else:
                invalid_gate_count = 0
            
            if invalid_gate_count >= 3:
                print("Terminating scraping due to 3 consecutive flights without a valid gate number.")
                stop_loop = True
                break
    
            flight_id = create_flight_id(flight_number, departure_datetime_str)

            if flight_id not in seen_flights and gate_number != "Unknown":
                if last_time and unmodified_datetime < last_time - time_threshold:
                    stop_loop = True
                    break
                else:
                    last_time = unmodified_datetime

                seen_flights.add(flight_id)
                departure_flights_data.append({
                    'flight_number': flight_number,
                    'type': 'Departure',
                    'departure_time': departure_datetime_str,
                    'airline_name': airline_name,
                    'destination': destination,
                    'terminal': terminal,
                    'gate_number': gate_number
                })

                last_processed_index = idx

        except Exception as e:
            print("Error processing flight details:", e)

    # check for error in variables
    print (last_time, stop_loop, last_processed_index, invalid_gate_count)
    return last_time, stop_loop, last_processed_index, invalid_gate_count


#############################################################
def scrape_flights_for_date(date):

    # Initialize variables
    last_time = None
    stop_loop = False # to ensure that next day flights are not added in, prevent duplication
    last_processed_index = 0
    invalid_gate_count = 0 

    #select date for flight schedule
    choose_date(date)

    while not stop_loop:
        try:
            flight_elements = driver.find_elements(By.CSS_SELECTOR, 'div.data.flightlist > a.flightlist__item.display-lg')
            last_time, stop_loop, last_processed_index, invalid_gate_count = process_flights(date, flight_elements, last_processed_index, last_time, stop_loop, invalid_gate_count)

            if stop_loop:
                break

            try:
                load_more_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.gray-bg.next-flights')))
                driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                WebDriverWait(driver, 20).until(EC.visibility_of(load_more_button))

                driver.execute_script("arguments[0].click();", load_more_button)
                
                WebDriverWait(driver, 20).until(
                    lambda driver: len(driver.find_elements(By.CSS_SELECTOR, 'div.data.flightlist > a.flightlist__item.display-lg')) > len(flight_elements)
                )
            except Exception as e:
                print("No more flights to load or error clicking the button:", e)
                break

        except Exception as e:
            print("Error loading flights or clicking 'Load More':", e)
            break

    return departure_flights_data

# Main execution
departure_flights_data = []
seen_flights = set()
start_date = datetime.today()
# Loop through the next 3 days
for day in range(3):
    target_date = start_date + timedelta(days=day)
    print(f"Scraping flights for {target_date.strftime('%Y-%m-%d')}")
    flights = scrape_flights_for_date(target_date)
    for flight in flights:
        print(flight)

print(f"Total flights collected: {len(departure_flights_data)}")
driver.quit()

existing_data.extend(departure_flights_data)


# Save updated departure_flights_data to departures_data.json
with open("departures_data.json", "w") as json_file:
    json.dump({"flights": existing_data, "number_of_flights": len(existing_data)}, json_file)

# Append new seen flight IDs to seen_data.txt
with open("seen_data.txt", "a") as seen_file:
    for flight_id in seen_flights:
        seen_file.write(f"{flight_id}\n")
