from pyairtable import Table
from collections import defaultdict
from config.helpers import coerce_from_schema
from config.schema import EVENTS_SCHEMA
import os

# for handling one-time events
from datetime import datetime, timedelta


def load_places_and_events(api_key, base_id, places_table_id, events_table_id, start_date=datetime.today(), end_date=None):
    """
    Loads places and their associated events from Airtable tables.

    Args:
        api_key (str): Airtable API key.
        base_id (str): Airtable base ID.
        places_table_id (str): Table ID for places.
        events_table_id (str): Table ID for events.
        start_date (datetime, optional): Start date for filtering one-time events. Defaults to today.
        end_date (datetime, optional): End date for filtering one-time events. Defaults to 14 days after start_date.

    Returns:
        tuple:
            - places_by_id (dict): Mapping of place ID to place record (dict).
            - place_id_to_events (defaultdict[list]): Mapping of place ID to a list of event dicts. Each event dict contains:
                - 'name' (str): Event name
                - 'url' (str): Official link for the event
                - 'recurrence' (str): Recurrence type (e.g., 'Once')
                - 'when' (str or None): Recurrence description (if any)
                - 'date' (datetime or None): Event date (for one-time events)
    """
    if not end_date:
      # add 14 days to start_date
      end_date = start_date + timedelta(days=14)
  
    # Query places
    table = Table(api_key, base_id, places_table_id)
    places = table.all()
    places_by_id = {r.get('id'): r for r in places}

    # Query events and link them to places
    events_table = Table(api_key, base_id, events_table_id)
    events = events_table.all()

    # Build a mapping from place name to id for robustness (in case events reference names)
    place_name_to_id = {}
    for p in places:
        fields = p.get('fields', {})
        name = fields.get('Name')
        if name:
            place_name_to_id[str(name).strip()] = p.get('id')

    place_id_to_events = defaultdict(list)

    for ev in events:
        
        f = ev.get('fields', {})
        
        coerce_events_schema = lambda key: coerce_from_schema(f, EVENTS_SCHEMA, key)
        
        # Filtering conditions
        url = coerce_events_schema('Official Link')
        place_field = coerce_events_schema('Place')
        date = coerce_events_schema('Date (if not recurrent)')
        when = coerce_events_schema('When (if recurrent)')
        recurrence = coerce_events_schema('Recurrence')
        
        if not place_field or not url:
            continue
        if recurrence == 'Once':
            # parse date, which has format like this '2025-10-02T22:00:00.000Z'
            # and check it is between start_date and end_date
            if not date:
                continue
            try:
                date = datetime.strptime(date[:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
            if not (start_date <= date <= end_date):
                continue
            
        ev_item = {
            'name': coerce_events_schema('Name'),
            'url': url,
            'recurrence': recurrence,
            'when': when,
            'date': date
        }
        
        # Determine which place(s) this event is linked to
        place_ids = []
        place_name = coerce_events_schema('Name (from Place)')
        for p in place_field:
            place_ids.append(p)
        if not place_ids and place_name:
            for p in place_name:
                pid = place_name_to_id.get(str(p).strip())
                if pid:
                    place_ids.append(pid)
        for pid in place_ids:
            place_id_to_events[pid].append(ev_item)

    return places_by_id, place_id_to_events
