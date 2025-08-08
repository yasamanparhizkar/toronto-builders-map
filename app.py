import dash
from dash import html, dcc, Output, Input, State, ALL
import dash_leaflet as dl
from pyairtable import Table
import os
from dash.exceptions import PreventUpdate

from dotenv import load_dotenv
load_dotenv()

# Load Airtable credentials from environment variables
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_ID = os.getenv('AIRTABLE_TABLE_ID')
#AIRTABLE_FORM_URL = os.getenv('AIRTABLE_FORM_URL', '#')

if not (AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_TABLE_ID):
    raise RuntimeError("Missing Airtable environment variables.")

# Helper to fetch safely, case-insensitive
def get_field(fields, *keys):
    for k in keys:
        if k in fields:
            return fields[k]
        # Case-insensitive fallback
        for kk in fields:
            if kk.lower() == k.lower():
                return fields[kk]
    return None

table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID)
resources = table.all()
resources_by_id = {r.get('id'): r for r in resources}

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
                html.P("No description available", className="notes notes--empty"),
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
    types = get_field(fields, 'type', 'Type')
    if types and not isinstance(types, list):
        types = [types]
    lat = get_field(fields, 'lat', 'latitude', 'Lat', 'Latitude')
    lon = get_field(fields, 'lon', 'longitude', 'Lon', 'Longitude', 'Lng', 'Long')
    lat, lon = normalize_lat_lon(lat, lon)
    name = get_field(fields, 'name', 'Name') or "Unnamed Location"
    notes = get_field(fields, 'description', 'Notes') or ""
    url = get_field(fields, 'Google Maps link', 'url', 'URL', 'Link') or '#'
    return {
        'id': r.get('id'),
        'name': name,
        'types': types or [],
        'lat': lat,
        'lon': lon,
        'notes': notes,
        'url': url
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

# --- Filter logic: build set of unique types, ensure 'Library' is included ---
type_options = set()
for r in resources:
    t = get_field(r.get('fields', {}), 'type', 'Type')
    if isinstance(t, list):  # Multi-select
        type_options.update(t)
    elif t:
        type_options.add(t)
type_options.add("Library")  # Always show 'Library'
type_options = sorted(type_options)

app = dash.Dash(__name__, external_stylesheets=[
    'https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;500;600;700&display=swap'
])

app.title = "Toronto Builders Map"
app.layout = html.Div([
    html.Div([
        html.H1("Toronto Builders Map"),
        html.P(
            "Your guide to build and connect in Toronto's tech ecosystem",
            className="subtitle"
        ),
        html.A(
            "✨ Submit a New Place",
            href="https://airtable.com/appFThl6Aw8IKOBif/pag8AhtZ5GOZlZ1bJ/form",
            target="_blank",
            className="filter-pill active",
            style={
                "fontSize": "1.08rem",
                "marginTop": "4px",
                "marginBottom": "12px",
                "fontWeight": 600,
                "display": "inline-block",
                "textDecoration": "none",
                "cursor": "pointer"
            }
        )
    ], className="header-container"),
    
    # Filter section
    html.Div([
        html.Div([
            html.Span("Filter by type:", className="filter-label"),
            html.Div([
                html.Button(
                    type_option,
                    id={'type': 'filter-pill', 'index': type_option},
                    className="filter-pill active",
                    n_clicks=0
                ) for type_option in type_options
            ], className="pill-container")
        ], className="filter-content")
    ], className="filter-container"),
    
    # Hidden store to track selected types
    dcc.Store(id='selected-types-store', data=type_options),
    
    # Main content: map and resource list side by side
    html.Div([
        html.Div([
            dl.Map(
                id="main-map", 
                center=[43.65, -79.38], 
                zoom=12, 
                style={'height': '70vh', 'width': '100%'}, 
                children=[
                    dl.TileLayer(
                        url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                    ),
                    dl.LayerGroup(id="marker-layer")
                ]
            )
        ], style={
            'flex': '2',
            'minWidth': '0',
            'paddingRight': '24px'
        }, className="map-container"),
        html.Div([            html.Div(id="resource-list", className="resource-list-scroll")
        ], className="resource-list-container")
    ], className="main-content"),
    # Footer info
    html.Div([
        html.P(id="results-info", className="results-info")
    ])
], className="_dash-container")

@app.callback(
    Output('selected-types-store', 'data'),
    [Input({'type': 'filter-pill', 'index': ALL}, 'n_clicks')],
    [State('selected-types-store', 'data')]
)
def update_selected_types(n_clicks_list, current_selected):
    ctx = dash.callback_context
    if not ctx.triggered:
        return type_options  # Start with all selected
    
    # Get which button was clicked
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if button_id != '{}':  # Make sure it's a valid button click
        import json
        button_info = json.loads(button_id)
        clicked_type = button_info['index']
        
        # Toggle the clicked type
        if clicked_type in current_selected:
            current_selected = [t for t in current_selected if t != clicked_type]
        else:
            current_selected = current_selected + [clicked_type]
    
    return current_selected

@app.callback(
    [Output({'type': 'filter-pill', 'index': type_option}, 'className') for type_option in type_options],
    [Input('selected-types-store', 'data')]
)
def update_pill_styles(selected_types):
    return [
        "filter-pill active" if type_option in selected_types else "filter-pill"
        for type_option in type_options
    ]

@app.callback(
    [Output('marker-layer', 'children'), Output('results-info', 'children'), Output('resource-list', 'children')],
    [Input('selected-types-store', 'data'), Input('main-map', 'bounds')]
)
def update_markers_info_and_list(selected_types, bounds):
    # Build list of resources that match selected types and have valid coordinates
    filtered_resources = []
    for r in resources:
        info = extract_resource_info(r)
        if info['lat'] is None or info['lon'] is None:
            continue
        # If there are selected types, ensure intersection
        if selected_types and info['types']:
            if not any(t in selected_types for t in info['types']):
                continue
        filtered_resources.append(info)

    # Markers: show all filtered markers (not limited by view bounds)
    markers = [
        dl.Marker(
            position=[info['lat'], info['lon']],
            children=dl.Popup(build_popup_content(info['name'], info['types'], info['notes'], info['url']), maxWidth=350)
        )
        for info in filtered_resources
    ]

    # Sidebar list: only items within current view bounds
    visible_resources = [
        info for info in filtered_resources
        if is_within_bounds(info['lat'], info['lon'], bounds)
    ]

    resource_list_items = []
    for info in visible_resources:
        type_badges = build_type_badges(info['types'])
        resource_list_items.append(
            html.Div([
                html.H4(info['name'], className="resource-item-title"),
                html.Div(type_badges, className="type-badges") if type_badges else None,
                (dcc.Markdown(info['notes'], link_target="_blank", className="notes notes--compact") if info['notes'] else html.P("No description available", className="notes notes--empty notes--compact")),
                (html.A('📍 View on Google Maps', href=info['url'], target='_blank', className="google-maps-link google-maps-link--small") if info['url'] and info['url'] != '#' else None)
            ], className='resource-item')
        )

    # Info text
    filtered_count = len(filtered_resources)
    visible_count = len(visible_resources)
    info_text = [
        f"💡 Showing {visible_count} of {filtered_count} filtered locations in current view.",
        html.Br(),
        f"Filtered by: {', '.join(selected_types)}" if selected_types else ""
    ]

    return markers, info_text, resource_list_items

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8050))
    app.run(debug=False, host='0.0.0.0', port=port)
