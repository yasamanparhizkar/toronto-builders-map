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
