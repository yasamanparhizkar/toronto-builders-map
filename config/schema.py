SCHEMA = {
    'Name': {
        'type': 'str',
        'default': 'Unnamed Location',
    },
    'Notes': {
        'type': 'str',
        'default': '',
    },
    'Type': {
        # Airtable may return a single string or a list of strings
        'type': 'list[str]',
        'default': [],
    },
    'Latitude': {
        'type': 'float',
        'default': None,
    },
    'Longitude': {
        'type': 'float',
        'default': None,
    },
    'Google Maps link': {
        'type': 'str',
        'default': '#',
    },
    'Address': {
        'type': 'str',
        'default': '',
    },
}

# Schema for the Events table
EVENTS_SCHEMA = {
    'Name': {
        'type': 'str',
        'default': 'Event',
    },
    'Notes': {
        'type': 'str',
        'default': '',
    },
    'Place': {
        # Linked record to Places; Airtable returns list of record IDs (or names in some views)
        'type': 'list[str]',
        'default': [],
    },
    'Name (from Place)': {
        # Lookup from Places; Airtable lookups typically return arrays
        'type': 'list[str]',
        'default': [],
    },
    'Address (from Place)': {
        'type': 'list[str]',
        'default': [],
    },
    'Recurrence': {
        'type': 'str',
        'default': '',
    },
    'Date (if not recurrent)': {
        'type': 'str',
        'default': '',
    },
    'When (if recurrent)': {
        'type': 'str',
        'default': '',
    },
    'Official Link': {
        'type': 'str',
        'default': '',
    },
}
