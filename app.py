import dash
from dash import html, dcc, Output, Input, State, ALL, no_update
import dash_leaflet as dl
import os
from config.helpers import *
from config.schema import EVENTS_SCHEMA
from services.data_loader import load_places_and_events

from dotenv import load_dotenv
load_dotenv()

# Load Airtable credentials from environment variables
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_PLACES_TABLE_ID = os.getenv('AIRTABLE_PLACES_TABLE_ID')
AIRTABLE_EVENTS_TABLE_ID = os.getenv('AIRTABLE_EVENTS_TABLE_ID')

MAP_CENTER = [43.65, -79.38]
EVENTS_PILL = "Only Places with Events"
EVENT_TIME_WINDOW_DAYS = 14
EVENT_TIME_WINDOWS = [
    {"label": "Within 7 days", "value": 7},
    {"label": "Within 2 weeks", "value": 14},
    {"label": "Within 1 month", "value": 30},
]

if not (AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_PLACES_TABLE_ID and AIRTABLE_EVENTS_TABLE_ID):
    raise RuntimeError("Missing Airtable environment variables (API key, base id, places table id, or events table id).")


app = dash.Dash(__name__, external_stylesheets=[
    'https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;500;600;700&display=swap'
])

app.title = "Toronto Builders Guide"
app.layout = html.Div([
    html.Div([
        # Left: title + subtitle grouped
        html.Div([
            html.H1("Toronto Builders Guide"),
            html.P(
                "Where to Work, Meet & Build. Your guide to Toronto's tech ecosystem",
                className="subtitle"
            )
        ], className="header-meta"),
        # Right: CTA buttons (wrapped in a Div)
        html.Div([
            html.A(
                "📍 Submit a New Place",
                href="https://airtable.com/appFThl6Aw8IKOBif/pag8AhtZ5GOZlZ1bJ/form",
                target="_blank",
                className="header-cta filter-pill active",
            ),
            html.A(
                "📅 Submit a New Event",
                href="https://airtable.com/appFThl6Aw8IKOBif/pagc4ThCUWv4SOF6l/form",
                target="_blank",
                className="header-cta filter-pill active header-cta--event",
            ),
            html.Iframe(
                src="https://ghbtns.com/github-btn.html?user=yasamanparhizkar&repo=toronto-builders-map&type=star&count=true&size=large",
                style={"border": "none", "overflow": "hidden", "width": "170px", "height": "30px"},
                width="170",
                height="30",
                title="GitHub"
            ),
        ], className="header-cta-container")
    ], className="header-container"),
    
    # Filter section
    html.Div([
        html.Div([
            html.Div([
                html.Span(className="filter-label")
            ]),
            html.Div(id="pill-container", className="pill-container")
        ], className="filter-content")
    ], className="filter-container"),
    
    # Hidden stores
    dcc.Store(id='resources-store'),
    dcc.Store(id='selected-types-store', data=[]),
    dcc.Store(id='event-window-store', data=EVENT_TIME_WINDOW_DAYS),
    dcc.Interval(id='startup-refresh', interval=100, n_intervals=0, max_intervals=1),  
    
    
    # Main content: map and resource list side by side
    html.Div([
        html.Div([
            html.P(id="results-info", className="results-info"),
            dl.Map(
                id="main-map", 
                center=MAP_CENTER, 
                zoom=12, 
                style={'height': '70vh', 'width': '100%'}, 
                children=[
                    dl.TileLayer(
                        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
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
        html.Div([
            html.Div(id="resource-list", className="resource-list-scroll")
        ], className="resource-list-container")
    ], className="main-content"),
    # Footer (intentionally left empty for now)
    html.Div([
        
    ])
], className="_dash-container")

"""
Performance refactor: separate concerns so clicking pills doesn't re-render children.

1) Build pills only from resources data (types) and always include event-window pills in a group.
2) Update selection state from clicks in a small callback (no DOM rebuild).
3) Toggle container class to show/hide the event-window group based on EVENTS_PILL selection.
4) Independently set active style for event-window pills from event-window-store.
"""

# 1) Build pills (types + EVENTS_PILL + event-window group)
@app.callback(
    Output('pill-container', 'children'),
    Input('resources-store', 'data')
)
def build_pills(resources_data):
    types = compute_unique_types(resources_data)
    pill_filters = types + [EVENTS_PILL]

    # Base type pills + EVENTS_PILL
    pills = [
        html.Button(
            t,
            id={'type': 'filter-pill', 'index': t},
            className="filter-pill filter-pill--event" if t == EVENTS_PILL else "filter-pill",
            n_clicks=0
        ) for t in pill_filters
    ]

    # Always add the event window group; visibility is controlled by container class
    window_pills = [
        html.Button(
            tw["label"],
            id={'type': 'event-window-pill', 'index': tw["value"]},
            className="filter-pill filter-pill--event",
            n_clicks=0
        ) for tw in EVENT_TIME_WINDOWS
    ]
    pills.append(html.Div(window_pills, className='event-window-group'))
    return pills

# 2) Update selected types from clicks (keep original selection rules)
@app.callback(
    Output('selected-types-store', 'data'),
    Input({'type': 'filter-pill', 'index': ALL}, 'n_clicks'),
    [State('resources-store', 'data'), State('selected-types-store', 'data'), State({'type': 'filter-pill', 'index': ALL}, 'id')]
)
def update_selected_types(n_clicks_list, resources_data, current_selected, pill_ids):
    import json
    types = compute_unique_types(resources_data)
    pill_filters = types + [EVENTS_PILL]

    # Default: all selected (full state)
    if not current_selected or set(current_selected) == set():
        current_selected = types

    ctx = dash.callback_context
    # If nothing was clicked yet (all are None/0), keep/show full set
    if not ctx.triggered or not any(n_clicks_list or []):
        return types

    trigger = ctx.triggered[0]['prop_id']
    try:
        trigger_id = json.loads(trigger.split('.')[0])
        clicked_type = trigger_id.get('index')
    except Exception:
        clicked_type = None

    if clicked_type and clicked_type in types:
        # FULL STATE: all selected
        if set(current_selected) == set(types):
            return [clicked_type]
        # PARTIAL STATE
        if clicked_type in current_selected:
            # If only one selected and it's clicked again: go back to full state
            if len(current_selected) == 1:
                return types
            # Remove it from selection
            return [t for t in current_selected if t != clicked_type]
        else:
            # Add it to selection
            return current_selected + [clicked_type]
    elif clicked_type == EVENTS_PILL:
        if EVENTS_PILL in current_selected:
            return [t for t in current_selected if t != EVENTS_PILL]
        else:
            return current_selected + [EVENTS_PILL]

    # Fallback: ensure only valid types
    return [t for t in (current_selected or []) if t in pill_filters]

# Initialize selection when resources arrive and no selection set yet
@app.callback(
    Output('selected-types-store', 'data', allow_duplicate=True),
    Input('resources-store', 'data'),
    State('selected-types-store', 'data'),
    prevent_initial_call=True
)
def init_selected_types(resources_data, current_selected):
    if current_selected:
        return no_update
    return compute_unique_types(resources_data)

# Update event-window-store when the event-window pills are clicked
@app.callback(
    Output('event-window-store', 'data'),
    [Input({'type': 'event-window-pill', 'index': ALL}, 'n_clicks')],
    [State({'type': 'event-window-pill', 'index': ALL}, 'id'),
     State('event-window-store', 'data')]
)
def refresh_event_time_window(n_clicks_list, pill_ids, current_window):
    if not n_clicks_list or not pill_ids:
        return current_window
    # Find which pill was clicked most recently
    for n, pid in zip(n_clicks_list, pill_ids):
        if n and pid:
            return pid['index']
    return current_window

# Update pill styles using pattern-matching output
@app.callback(
    Output({'type': 'filter-pill', 'index': ALL}, 'className'),
    [Input('selected-types-store', 'data')],
    [State({'type': 'filter-pill', 'index': ALL}, 'id')]
)
def update_filter_pill_styles(selected_types, pill_ids):
    selected_set = set(selected_types or [])
    classes = []
    for pid in (pill_ids or []):
        label = pid.get('index') if isinstance(pid, dict) else None
        base = "filter-pill filter-pill--event" if label == EVENTS_PILL else "filter-pill"
        if label in selected_set:
            classes.append(f"{base} active")
        else:
            classes.append(base)
    return classes

# 3) Toggle visibility of the event-window group without rebuilding
@app.callback(
    Output('pill-container', 'className'),
    Input('selected-types-store', 'data')
)
def toggle_event_window_group(selected_types):
    css = 'pill-container'
    if EVENTS_PILL in (selected_types or []):
        css += ' show-event-window'
    return css

# 4) Independently activate the correct event-window pill based on the store
@app.callback(
    Output({'type': 'event-window-pill', 'index': ALL}, 'className'),
    [Input('event-window-store', 'data')],
    [State({'type': 'event-window-pill', 'index': ALL}, 'id')]
)
def update_event_window_pill_styles(selected_window, pill_ids):
    classes = []
    for pid in (pill_ids or []):
        base = 'filter-pill filter-pill--event'
        if pid and pid.get('index') == selected_window:
            classes.append(base + ' active')
        else:
            classes.append(base)
    return classes

@app.callback(
    Output('resources-store', 'data'),
    [Input('event-window-store', 'data'),
     Input('startup-refresh', 'n_intervals')]  # <--- Add this input
)
def update_resources_on_time_window_change(selected_window, n_intervals):
    # Reload places and events with the new interval
    places_by_id, place_id_to_events = load_places_and_events(
        AIRTABLE_API_KEY,
        AIRTABLE_BASE_ID,
        AIRTABLE_PLACES_TABLE_ID,
        AIRTABLE_EVENTS_TABLE_ID,
        interval_days=selected_window
    )
    # Prepare data for the store
    return [
        {**extract_place_info(p), 'events': place_id_to_events.get(p.get('id'), [])}
        for p in places_by_id.values()
    ]

@app.callback(
    [Output('marker-layer', 'children'),
     Output('results-info', 'children'),
     Output('resource-list', 'children')],
    [Input('selected-types-store', 'data'), Input('main-map', 'bounds')],
    [State('resources-store', 'data')]
)
def update_markers_info_and_list(selected_types, bounds, places_data):
    # center coordinates for sorting places
    center_lat, center_lon = get_center_from_map_bounds(bounds, MAP_CENTER)
    
    # selected_types here receives the places types AND the 'Only Places with Events' filter
    places_data = places_data or []
    # Build list of resources that match selected types and have valid coordinates
    fiiltered_places = []
    for info in places_data:
        if info['lat'] is None or info['lon'] is None:
            continue
        
        # If there are selected types, ensure intersection
        if selected_types and info['types']:
            if not any(t in selected_types for t in info['types']):
                continue
        
        # If EVENTS_PILL is part of selected_types, exclude places with no events attached
        if EVENTS_PILL in selected_types and not info.get('events'):
            continue
        
        fiiltered_places.append(info)

    # Markers: show all filtered markers (not limited by view bounds)
    markers = [
        dl.Marker(
            position=[info['lat'], info['lon']],
            children=dl.Popup(
                build_popup_content(
                    info['name'], info['types'], info['notes'], info['url'], info.get('events')
                ),
                maxWidth=350,
                autoPanPadding=[70, 70]
            )
        )
        for info in fiiltered_places
    ]

    # Sidebar list: only items within current view bounds
    visible_places = [
        info for info in fiiltered_places
        if is_within_bounds(info['lat'], info['lon'], bounds)
    ]
    
    # sort by distance too the center
    visible_places.sort(key=lambda place: rough_distance(center_lat, center_lon, place['lat'], place['lon']))

    places_list_items = []
    for info in visible_places:
        type_badges = build_type_badges(info['types'])
        # Event link(s): show the first event link if present
        event_links = info.get('events') or []
        first_event_link = None
        for e in event_links:
            if e and e.get('url'):
                first_event_link = e
                break
        places_list_items.append(
            html.Div([
                html.H4(info['name'], className="resource-item-title"),
                html.Div(type_badges, className="type-badges") if type_badges else None,
                (html.A(
                    f"📅 {first_event_link.get('name') or 'Event'}",
                    href=first_event_link.get('url'),
                    target='_blank',
                    className="event-link event-link--small"
                ) if first_event_link else None),
                (dcc.Markdown(info['notes'], link_target="_blank", className="notes notes--compact") if info['notes'] else None),
                (html.A('📍 View on Google Maps', href=info['url'], target='_blank', className="google-maps-link google-maps-link--small") if info['url'] and info['url'] != '#' else None)
            ], className='resource-item')
        )

    # Info text
    filtered_count = len(fiiltered_places)
    visible_count = len(visible_places)
    info_text = f"Showing {visible_count}/{filtered_count} locations on the map"

    return markers, info_text, places_list_items

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8050))
    app.run(debug=False, host='0.0.0.0', port=port)
