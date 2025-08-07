import dash
from dash import html, dcc
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

markers = []
for r in resources:
    fields = r.get('fields', {})
    lat = get_field(fields, 'lat', 'latitude')
    lon = get_field(fields, 'lon', 'longitude')
    if lat and lon:
        popup_items = [
            html.B(get_field(fields, 'name', 'Name') or "Unnamed"),
            html.Br(),
            get_field(fields, 'description', 'Notes') or "",
            html.Br(),
            html.A('Google Maps', href=get_field(fields, 'Google Maps link', 'url', 'URL', 'Link') or '#', target='_blank')
        ]
        markers.append(
            dl.Marker(
                position=[lat, lon],
                children=dl.Popup(popup_items)
            )
        )

app = dash.Dash(__name__)
app.layout = html.Div([
    html.H1("Toronto AI Builders Map"),
    dl.Map(center=[43.65, -79.38], zoom=12, style={'height': '70vh', 'width': '100%'}, children=[
        dl.TileLayer(),
        dl.LayerGroup(markers)
    ]),
    #html.A("Add resource", href=AIRTABLE_FORM_URL, target='_blank', style={'display': 'block', 'marginTop': '1em'})
])

if __name__ == '__main__':
    app.run(debug=True)
