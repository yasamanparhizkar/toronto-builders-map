import dash
from dash import html, dcc, Output, Input, State, ALL
import dash_leaflet as dl
from pyairtable import Table
import os
from config.helpers import *

from dotenv import load_dotenv
load_dotenv()

# Load Airtable credentials from environment variables
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_ID = os.getenv('AIRTABLE_TABLE_ID')

if not (AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_TABLE_ID):
    raise RuntimeError("Missing Airtable environment variables.")

table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID)
resources = table.all()
resources_by_id = {r.get('id'): r for r in resources}

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
        # Right: CTA button
        html.A(
            "Submit a New Place",
            href="https://airtable.com/appFThl6Aw8IKOBif/pag8AhtZ5GOZlZ1bJ/form",
            target="_blank",
            className="header-cta filter-pill active",
        )
    ], className="header-container"),
    
    # Filter section
    html.Div([
        html.Div([
            html.Div([
                html.Span("Filter by type:", className="filter-label")
            ]),
            html.Div(id="pill-container", className="pill-container"),
            html.P(id="results-info", className="notes")
        ], className="filter-content")
    ], className="filter-container"),
    
    # Hidden stores
    dcc.Store(id='resources-store', data=[extract_resource_info(r) for r in resources]),
    dcc.Store(id='selected-types-store', data=[]),
    
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
    ],
    [
        State('selected-types-store', 'data'),
        State({'type': 'filter-pill', 'index': ALL}, 'id'),
    ]
)
def generate_pills_and_update_selection(resources_data, n_clicks_list, current_selected, pill_ids):
    import json
    # Compute unique types from resources
    types = compute_unique_types(resources_data)

    # Build pill buttons
    pills = [
        html.Button(
            t,
            id={'type': 'filter-pill', 'index': t},
            className="filter-pill",
            n_clicks=0
        ) for t in types
    ]

    # Determine what triggered the callback
    ctx = dash.callback_context
    if not ctx.triggered:
        # Initial load: select all types
        return pills, types

    trigger = ctx.triggered[0]['prop_id']
    # If resources changed, reset selected types to all
    if trigger.startswith('resources-store.'):
        return pills, types

    # Otherwise, a pill was clicked -> toggle selection
    try:
        trigger_id = json.loads(trigger.split('.')[0])
        clicked_type = trigger_id.get('index')
    except Exception:
        clicked_type = None

    # Start from current_selected, but ensure it's a subset of available types
    current_selected = [t for t in (current_selected or []) if t in types]
    if clicked_type:
        if clicked_type in current_selected:
            current_selected = [t for t in current_selected if t != clicked_type]
        else:
            current_selected = current_selected + [clicked_type]

    return pills, current_selected

# Update pill styles using pattern-matching output
@app.callback(
    Output({'type': 'filter-pill', 'index': ALL}, 'className'),
    [Input('selected-types-store', 'data')],
    [State({'type': 'filter-pill', 'index': ALL}, 'id')]
)
def update_pill_styles_dynamic(selected_types, pill_ids):
    selected_set = set(selected_types or [])
    classes = []
    for pid in (pill_ids or []):
        label = pid.get('index') if isinstance(pid, dict) else None
        classes.append("filter-pill active" if label in selected_set else "filter-pill")
    return classes

@app.callback(
    [Output('marker-layer', 'children'), Output('results-info', 'children'), Output('resource-list', 'children')],
    [Input('selected-types-store', 'data'), Input('main-map', 'bounds')],
    [State('resources-store', 'data')]
)
def update_markers_info_and_list(selected_types, bounds, resources_data):
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
