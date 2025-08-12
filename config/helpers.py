from config.schema import SCHEMA
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


def build_popup_content(name, types, notes, url):
    type_badges = build_type_badges(types)
    return html.Div([
        html.Div([
            html.H4(name, className="popup-title"),
            html.Div(type_badges, className="type-badges") if type_badges else None,
            html.Div(
                dcc.Markdown(notes, link_target="_blank", className="notes") if notes else \
                None,
                className="notes-wrapper"
            ),
            html.A(
                '📍 View on Google Maps',
                href=url,
                target='_blank',
                className="google-maps-link"
            ) if url != '#' else None
        ], className="popup-content")
    ])


def extract_resource_info(r):
    fields = r.get('fields', {})

    name = coerce_value(fields.get('Name'), SCHEMA['Name']['type']) or SCHEMA['Name']['default']

    types = coerce_value(fields.get('Type'), SCHEMA['Type']['type']) or SCHEMA['Type']['default']

    lat = coerce_value(fields.get('Latitude'), SCHEMA['Latitude']['type'])
    lon = coerce_value(fields.get('Longitude'), SCHEMA['Longitude']['type'])
    lat, lon = normalize_lat_lon(lat, lon)

    notes = coerce_value(fields.get('Notes'), SCHEMA['Notes']['type'])
    if notes is None:
        notes = SCHEMA['Notes']['default']

    url = coerce_value(fields.get('Google Maps link'), SCHEMA['Google Maps link']['type']) or SCHEMA['Google Maps link']['default']

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
    in_lat = south <= lat <= north
    if west <= east:
        in_lon = west <= lon <= east
    else:
        in_lon = (lon >= west) or (lon <= east)
    return in_lat and in_lon

# Helper to compute unique types from resources data
def compute_unique_types(resources_data):
    type_set = set()
    for item in (resources_data or []):
        for t in (item.get('types') or []):
            if t:
                type_set.add(t)
    # Always include 'Library' as an option
    type_set.add("Library")
    return sorted(type_set)
