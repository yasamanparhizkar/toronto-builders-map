import dash
from dash import html, dcc, Output, Input, State, ALL
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

app.title = "Toronto Builders Map"
app.layout = html.Div([
    html.Div([
        # Left: title + subtitle grouped
        html.Div([
            html.H1("Toronto Builders Map"),
            html.P(
                "Your guide to build and connect in Toronto's tech ecosystem",
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
            )
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
    
    
    # Main content: map and resource list side by side
    html.Div([
        html.Div([
            html.P(id="results-info", className="results-info"),
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
        html.Div([
            html.Div(id="resource-list", className="resource-list-scroll")
        ], className="resource-list-container")
    ], className="main-content"),
    # Footer (intentionally left empty for now)
    html.Div([
        
    ])
], className="_dash-container")

# Dynamically generate pills and manage selected types in one callback
@app.callback(
    [
        Output('pill-container', 'children'),
        Output('selected-types-store', 'data'),
    ],
    [
        Input('resources-store', 'data'),
        Input({'type': 'filter-pill', 'index': ALL}, 'n_clicks'),
        Input('event-window-store', 'data')
    ],
    [
        State('selected-types-store', 'data'),
        State({'type': 'filter-pill', 'index': ALL}, 'id'),
    ]
)
def generate_pills_and_update_selection(resources_data, n_clicks_list, selected_window, current_selected, pill_ids):
    import json

    types = compute_unique_types(resources_data)
    pill_filters = types + [EVENTS_PILL]

    # Default: all selected (full state)
    if not current_selected or set(current_selected) == set():
        current_selected = types

    ctx = dash.callback_context
    if not ctx.triggered:
        # Initial load: full state
        current_selected = types
    else:
        trigger = ctx.triggered[0]['prop_id']
        if trigger.startswith('resources-store.'):
            current_selected = types
        else:
            # Pill click
            try:
                trigger_id = json.loads(trigger.split('.')[0])
                clicked_type = trigger_id.get('index')
            except Exception:
                clicked_type = None

            # Only handle place-type pills (not event window)
            if clicked_type and clicked_type in types:
                # FULL STATE: all selected
                if set(current_selected) == set(types):
                    # Clicking any pill: go to partial state with only that pill
                    current_selected = [clicked_type]
                # PARTIAL STATE
                else:
                    if clicked_type in current_selected:
                        # If only one selected and it's clicked again: go back to full state
                        if len(current_selected) == 1:
                            current_selected = types
                        else:
                            # Remove it from selection
                            current_selected = [t for t in current_selected if t != clicked_type]
                    else:
                        # Add it to selection
                        current_selected = current_selected + [clicked_type]

            # Handle EVENTS_PILL as before (optional: you can adapt similar logic if needed)
            elif clicked_type == EVENTS_PILL:
                if EVENTS_PILL in current_selected:
                    current_selected = [t for t in current_selected if t != EVENTS_PILL]
                else:
                    current_selected = current_selected + [EVENTS_PILL]

            # Ensure only valid types
            current_selected = [t for t in current_selected if t in pill_filters]

    # Build pill buttons
    pills = [
        html.Button(
            t,
            id={'type': 'filter-pill', 'index': t},
            className="filter-pill filter-pill--event" if t == EVENTS_PILL else "filter-pill",
            n_clicks=0
        ) for t in pill_filters
    ]

    if EVENTS_PILL in (current_selected or []):
        for tw in EVENT_TIME_WINDOWS:
            pills.append(
                html.Button(
                    tw["label"],
                    id={'type': 'event-window-pill', 'index': tw["value"]},
                    className="filter-pill filter-pill--event" + (" active" if selected_window == tw["value"] else ""),
                    n_clicks=0
                )
            )

    return pills, current_selected

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

@app.callback(
    Output('resources-store', 'data'),
    [Input('event-window-store', 'data')]
)
def update_resources_on_time_window_change(selected_window):
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
def update_markers_info_and_list(selected_types, bounds, resources_data):
    # selected_types here receives the places types AND the 'Only Places with Events' filter
    resources_data = resources_data or []
    # Build list of resources that match selected types and have valid coordinates
    filtered_resources = []
    for info in resources_data:
        if info['lat'] is None or info['lon'] is None:
            continue
        
        # If there are selected types, ensure intersection
        if selected_types and info['types']:
            if not any(t in selected_types for t in info['types']):
                continue
        
        # If EVENTS_PILL is part of selected_types, exclude places with no events attached
        if EVENTS_PILL in selected_types and not info.get('events'):
            continue
        
        filtered_resources.append(info)

    # Markers: show all filtered markers (not limited by view bounds)
    markers = [
        dl.Marker(
            position=[info['lat'], info['lon']],
            children=dl.Popup(
                build_popup_content(
                    info['name'], info['types'], info['notes'], info['url'], info.get('events')
                ),
                maxWidth=350
            )
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
        # Event link(s): show the first event link if present
        event_links = info.get('events') or []
        first_event_link = None
        for e in event_links:
            if e and e.get('url'):
                first_event_link = e
                break
        resource_list_items.append(
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
    filtered_count = len(filtered_resources)
    visible_count = len(visible_resources)
    info_text = f"Showing {visible_count}/{filtered_count} locations on the map"

    return markers, info_text, resource_list_items

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8050))
    app.run(debug=False, host='0.0.0.0', port=port)
