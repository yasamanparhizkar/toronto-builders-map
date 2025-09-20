from config.schema import PLACES_SCHEMA
from dash import html, dcc

# Helper: normalize/coerce values by type (based on the data type specified on the schema)
def coerce_value(value, type_decl):
    if value is None:
        return None
    if type_decl == 'str':
        try:
            return str(value)
        except Exception:
            return None
    if type_decl == 'float':
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if type_decl == 'list[str]':
        if isinstance(value, list):
            # Convert all to str and drop falsy
            return [str(v) for v in value if v]
        # Wrap singletons
        return [str(value)] if value else []
    return value

def coerce_from_schema(fields, schema, key):
    value = fields.get(key)
    type_decl = schema[key]['type']
    default = schema[key]['default']
    coerced = coerce_value(value, type_decl)
    return coerced if coerced is not None else default


# Utility helpers for consistent rendering and filtering
def normalize_lat_lon(lat, lon):
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None


def build_type_badges(types):
    badges = []
    if not types:
        return badges
    for t in types:
        badges.append(html.Span(t, className="type-badge"))
    return badges


def build_popup_content(name, types, notes, url, events=None):
    type_badges = build_type_badges(types)
    # Pick first event if available
    first_event = None
    for e in (events or []):
        if e and e.get('url'):
            first_event = e
            break
    return html.Div([
        html.Div([
            html.H4(name, className="popup-title"),
            html.Div(type_badges, className="type-badges") if type_badges else None,
            html.Div(
                dcc.Markdown(notes, link_target="_blank", className="notes") if notes else \
                None,
                className="notes-wrapper"
            ),
            (html.A(
                f"🎟️ {first_event.get('name') or 'Event'}",
                href=first_event.get('url'),
                target='_blank',
                className="event-link"
            ) if first_event else None),
            html.A(
                '📍 View on Google Maps',
                href=url,
                target='_blank',
                className="google-maps-link"
            ) if url != '#' else None
        ], className="popup-content")
    ])


def extract_place_info(r):
    """
    Args:
        r (dict): Record as dictionary. It is expected to contain an 'id'
            key and a 'fields' dictionary with keys 'Name', 'Type',
            'Latitude', 'Longitude', 'Notes', and 'Google Maps link'.

    Returns:
        dict: A cleaned dictionary containing the resource's information with
            the following keys:
            - 'id' (str): The unique identifier of the record.
            - 'name' (str): The name of the place.
            - 'types' (list): A list of types associated with the place.
            - 'lat' (float): The normalized latitude.
            - 'lon' (float): The normalized longitude.
            - 'notes' (str): Any notes associated with the place.
            - 'url' (str): A URL to the place on Google Maps.
    """
    f = r.get('fields', {})
    coerce_places_schema = lambda key: coerce_from_schema(f, PLACES_SCHEMA, key)
    
    name = coerce_places_schema('Name')
    types = coerce_places_schema('Type')
    lat = coerce_places_schema('Latitude')
    lon = coerce_places_schema('Longitude')
    lat, lon = normalize_lat_lon(lat, lon)
    notes = coerce_places_schema('Notes')
    url = coerce_places_schema('Google Maps link')

    return {
        'id': r.get('id'),
        'name': name,
        'types': types,
        'lat': lat,
        'lon': lon,
        'notes': notes,
        'url': url,
    }


def is_within_bounds(lat, lon, bounds):
    if not bounds or lat is None or lon is None:
        return True
    try:
        (south, west), (north, east) = bounds
    except Exception:
        return True
    # Handle antimeridian crossing
    # comment by a human: this was added by Cpilot and it is unnecessary since the app is toronto only but whatever, I'm keeping it because it doesn't hurt
    in_lat = south <= lat <= north
    if west <= east:
        in_lon = west <= lon <= east
    else:
        in_lon = (lon >= west) or (lon <= east)
    return in_lat and in_lon

# Helper to compute unique types from resources data
def compute_unique_types(resources_data):
    """Computes a sorted list of unique types from a list of resources.

    Args:
        resources_data (list[dict]): A list of resource dictionaries, where each
            item might contain a 'types' key with a list of type strings.

    Returns:
        list[str]: A sorted list of unique type strings. 
    """
    type_set = set()
    for item in (resources_data or []):
        for t in (item.get('types') or []):
            if t:
                type_set.add(t)
    return sorted(type_set)
