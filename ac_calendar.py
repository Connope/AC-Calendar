from __future__ import print_function
import datetime
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import json
from bs4 import BeautifulSoup
import requests
import calendar
from ics import Event

def read_config():
    """
    Reads config.txt. Retrieves the list of villagers, the island name, the time zone and the calendar
    name. Google Calendar and icalender are set to true if they are equal to 1 in the config file.
    """
    config = 'config.txt'
    time_zones = 'timezones.txt'
    with open(config, 'r') as infile:
        content = infile.readlines() 
        
    with open(time_zones, 'r') as infile:
        valid_times = infile.readlines() 
        
    villagers = []
    for villager in content[:10]:
        villager_name = villager.strip()
        if villager_name[-1] != '_':
            villagers.append(villager_name[villager_name.find('=') + 1:].strip())
    
    island = content[10].strip()
    if island[-1] != '_':
        island = island[island.find('=') + 1:].strip()
    else:
        island = None
        
    time_zone = content[11][content[11].find('=') + 1:].strip()
    if time_zone + '\n' not in valid_times:
        time_zone = 'Etc/GMT'
    
    calendar_name = content[12][content[12].find('=') + 1:].strip()
    
    if content[13][content[13].find('=') + 1:].strip() == "1":
        google_calendar = True
    else:
        google_calendar = False
    
    if content[14][content[14].find('=') + 1:].strip() == "1":
        icalendar = True
    else:
        icalendar = False
    
    return villagers, island, time_zone, calendar_name, google_calendar, icalendar
	
def calendar_auth():
    """
    This is mostly copied from Google's Python Quickstart guide at
    https://developers.google.com/calendar/quickstart/python.
    """
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('calendar', 'v3', credentials=creds)
    return service
	
def make_new_google_calendar(service, time_zone, calendar_name):
    """
    Adds a new calendar to the user's Google Calendar with the given name and timezone. Service is
    retrieved from calendar_auth.
    """
    calendars_dict = service.calendarList().list().execute()
    # Check if a calendar with the given name already exists and ask the user if they would like to 
    # delete it or stop the process if so.
    for calendar in calendars_dict['items']:
        if calendar['summary'] == calendar_name:
            user_preference = input(f"Google Calendar {calendar_name} already exists. Would you like to delete this calendar and create a new calendar? Y/N \n")
            if user_preference.upper() == 'Y':
                service.calendars().delete(calendarId = calendar['id']).execute()
            else:
                print("Please change calendar_name in config.txt")
                return 0
    
    calendar = {
    'summary': calendar_name,
    'timeZone': time_zone
    }
    
    new_calendar = service.calendars().insert(body = calendar).execute()
    return new_calendar['id']
	
def make_new_icalendar():
    """
    Sets up a string to act as an ical file. Set up in this way to mirror the Google Calendar
    implementation.
    """
    return "BEGIN:VCALENDAR\n\n"
	
def retrieve_villager_data():
    """
    Retrieves a list of villagers and their birthdays. These are output as a dictionary villager_data
    with keys being villager names and values being villager birthdays in a list formatted as [day, month].
    """
    
    # Retrieve the table of villager information.
    url = 'https://animalcrossing.fandom.com/wiki/Villager_list_(New_Horizons)'
    html_content = requests.get(url).text
    soup = BeautifulSoup(html_content, "lxml")
    villager_table = soup.find_all("table", attrs = {"class": "roundy"})[1].find("table")
    
    # Dictionary with calendar months and their number
    month_to_number = {calendar.month_name[i]: i for i in range(len(calendar.month_name))}
    
    # Go through the villager information table line by line and make a dictionary containing villagers and their
    # birthdays.
    villager_data = dict()
    for row in villager_table.find_all("tr")[1:]:
        data = row.find_all("td")
        villager_name = data[0].get_text(strip = 'True')
        villager_birthday = data[4].get_text(strip = 'True')[:-2].partition(" ")
        # Deals with villagers with different names in different regions
        if "NA" and "PAL" in villager_name:
            villager_name_NA = villager_name[:villager_name.index("NA")]
            villager_name_PAL = villager_name[villager_name.index("NA") + 2:villager_name.index("PAL")]
            villager_data[villager_name_NA.lower()] = [villager_birthday[2], str(month_to_number[villager_birthday[0]])]
            villager_data[villager_name_PAL.lower()] = [villager_birthday[2], str(month_to_number[villager_birthday[0]])]
        else:
            villager_data[villager_name.lower()] = [villager_birthday[2], str(month_to_number[villager_birthday[0]])]
    return villager_data

def check_villager_data(villager, villager_data):
    """
    Checks to make sure the villager is a valid villager. Returns its data if so, and 0
    otherwise.
    """
    # Check the villager's name to make sure they are valid.
    if villager.lower() not in villager_data:
        return 0
    else:
        return villager_data[villager.lower()]
        
def format_birthday(this_villager_data):
    """
    Formats and returns the villager's birthday and the day after in the format
    required.
    """

    # Checks if the villager's birthday has already happened this year and sets their next
    # birthday to next year if so.
    current_date = datetime.datetime.now()
    current_year = current_date.year
    birthday = datetime.datetime(current_year, int(this_villager_data[1]), int(this_villager_data[0]))
    if birthday < current_date:
        birthday = datetime.datetime(current_year + 1, int(this_villager_data[1]), int(this_villager_data[0]))
    birth_after_day = birthday + datetime.timedelta(days = 1)
    
    # Appends leading 0's to 1 digit months and days so dates can be written is YYYY-MM-DD format
    # as required by the Google Calendar API.
    month = lambda date : date.month if len(str(date.month)) == 2 else "0" + str(date.month)
    day = lambda date: date.day if len(str(date.day)) == 2 else "0" + str(date.day)

    birthday = f"{birthday.year}-{month(birthday)}-{day(birthday)}"
    birth_after_day = f"{birth_after_day.year}-{month(birth_after_day)}-{day(birth_after_day)}"
    return birthday, birth_after_day
    
def event_setup(villager, island, time_zone, birthday, birth_after_day):
    """
    Sets up the event in the required format, ready to be added to Google Calendar
    or an iCalendar file.
    """
    event = {
            'summary': f"{villager}'s birthday",
            'start': {
                'date': birthday,
                'timeZone': time_zone,
            },
            'end': {
                'date': birth_after_day,
                'timeZone': time_zone,
            },
            'recurrence': [f'RRULE:FREQ=YEARLY;BYMONTHDAY={birthday[8:10]};BYMONTH={birthday[5:7]}'],
        }
    if not not island:
        event['location'] = island
    
    return event
    
def add_to_google_calendar(service, calendar_id, event):
    """
    Adds the event to the Google Calendar.
    """
    return service.events().insert(calendarId = calendar_id, body = event).execute()
    
def add_to_icalendar(icalendar_object, event):
    """
    Adds the event to the iCalendar string.
    """
    ical_event = Event()
    ical_event.name = event['summary']
    ical_event.begin = event['start']['date']
    if 'location' in event:
        ical_event.location = event['location']
    ical_event.make_all_day()
    ical_event_string = f"{str(ical_event)[:-10]}{event['recurrence'][0]}\n\n{str(ical_event)[-10:]}"
    icalendar_object += f"{ical_event_string}\n\n"
    return icalendar_object


def main():	
    villagers, island, time_zone, calendar_name, google_calendar, icalendar = read_config()
    if google_calendar:
        service = calendar_auth()
        calendar_id = make_new_google_calendar(service, time_zone, calendar_name)
        if calendar_id == 0:
            google_calendar = False
    if icalendar:
        icalendar_object = make_new_icalendar()
        
    villager_data = retrieve_villager_data()

    for villager in villagers:
        this_villager_data = check_villager_data(villager, villager_data)
        if this_villager_data == 0:
            print(f"{villager} is not a valid villager. Please check to make sure you have entered their name correctly.")
            continue
        else:
            birthday, birth_after_day = format_birthday(this_villager_data)
            event = event_setup(villager, island, time_zone, birthday, birth_after_day)
            if google_calendar:
                add_to_google_calendar(service, calendar_id, event)
                print(f"Successfully added {villager}'s birthday to Google Calendar")
            if icalendar:
                add_to_icalendar(icalendar_object, event)
            print(f"Successfully added {villager}'s birthday to iCalendar")

    if icalendar:
        icalendar_object += f'END:VCALENDAR'
        with open('Animal_Crossing_Calendar.ics', 'w') as f:
            f.write(str(icalendar_object))
		
if __name__ == "__main__":
	main()
