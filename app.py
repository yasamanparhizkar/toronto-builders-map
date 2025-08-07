import dash
from dash import html, dcc, Output, Input, State, ALL
import dash_leaflet as dl
from pyairtable import Table
import os

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
    # Header section
    html.Div([
        html.H1("Toronto Builders Map"),
        html.P("Your guide to build and connect in Toronto's tech ecosystem", 
               className="subtitle")
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
    
    # Map section
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
    ], className="map-container"),
    
    # Footer info
    html.Div([
        html.P(id="results-info", style={
            'textAlign': 'center', 
            'color': 'var(--text-secondary)', 
            'marginTop': '24px',
            'fontSize': '0.9rem'
        })
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
    [Output('marker-layer', 'children'), Output('results-info', 'children')],
    [Input('selected-types-store', 'data')]
)
def update_markers_and_info(selected_types):
    filtered = []
    total_count = 0
    
    for r in resources:
        fields = r.get('fields', {})
        types = get_field(fields, 'type', 'Type')
        if not types:
            continue
        if not isinstance(types, list):
            types = [types]
        
        # Count all valid locations
        lat = get_field(fields, 'lat', 'latitude')
        lon = get_field(fields, 'lon', 'longitude')
        if lat and lon:
            total_count += 1
            
            # Apply filter
            if selected_types and not any(t in selected_types for t in types):
                continue

            name = get_field(fields, 'name', 'Name') or "Unnamed Location"
            notes = get_field(fields, 'description', 'Notes') or ""
            url = get_field(fields, 'Google Maps link', 'url', 'URL', 'Link') or '#'
            
            # Create type badges
            type_badges = []
            if isinstance(types, list):
                for t in types:
                    type_badges.extend([
                        html.Span(t, style={
                            'background': 'var(--primary-blue)',
                            'color': 'white',
                            'padding': '2px 8px',
                            'borderRadius': '4px',
                            'fontSize': '0.75rem',
                            'fontWeight': '500',
                            'marginRight': '4px',
                            'display': 'inline-block'
                        }),
                        " "
                    ])
            
            popup_content = html.Div([
                html.Div([
                    html.H4(name, style={
                        'margin': '0 0 8px 0',
                        'color': 'var(--text-primary)',
                        'fontSize': '1.1rem',
                        'fontWeight': '600'
                    }),
                    html.Div(type_badges, style={'marginBottom': '12px'}) if type_badges else None,
                    html.Div(
                        dcc.Markdown(notes, link_target="_blank") if notes else 
                        html.P("No description available", style={'color': 'var(--text-secondary)', 'fontStyle': 'italic'}),
                        style={'marginBottom': '16px', 'lineHeight': '1.4'}
                    ),
                    html.A(
                        '📍 View on Google Maps', 
                        href=url, 
                        target='_blank',
                        style={
                            'display': 'inline-block',
                            'padding': '8px 16px',
                            'background': 'var(--primary-blue)',
                            'color': 'white',
                            'textDecoration': 'none',
                            'borderRadius': '6px',
                            'fontSize': '0.9rem',
                            'fontWeight': '500',
                            'transition': 'all 0.2s ease'
                        }
                    ) if url != '#' else None
                ], style={'minWidth': '250px', 'maxWidth': '300px'})
            ])
            
            filtered.append(
                dl.Marker(
                    position=[lat, lon],
                    children=dl.Popup(popup_content, maxWidth=350)
                )
            )
    
    # Create info text
    filtered_count = len(filtered)
    if selected_types:
        info_text = [
            f"💡 Showing {filtered_count} of {total_count} locations ",
            html.Br(),
            f"Filtered by: {', '.join(selected_types)}"
        ]
    else:
        info_text = [
            f"💡 Click on markers to learn more about each location. ",
            html.Br(),
            f"Showing all {total_count} locations across Toronto's AI ecosystem."
        ]
    
    return filtered, info_text

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8050))
    app.run(debug=False, host='0.0.0.0', port=port)
