"""
Planet Atlas Integration Wrapper for Haven

Generates a 3D planet visualization with POI markers using Plotly.
Integrates with Haven's database for planet and POI data.
"""

import numpy as np
import plotly.graph_objects as go
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# POI Categories with icons (matching Planet_Atlas)
POI_CATEGORIES = [
    '-', 'Base', 'Waypoint', 'Outpost', 'Resource', 'Archive', 'Freighter',
    'Settlement', 'Sentinel Pillar', 'Autophage Camp', 'Beacon',
    'Historical', 'Industry', 'Portal', 'Drop Pod', 'Starship'
]

# Color palette (matching Planet_Atlas)
COLOR_LIST = [
    '#FC422D', '#FF8C00', '#FFD700', '#32CD32', '#00FFFF', '#1E90FF',
    '#BA55D3', '#FF9AC7', '#FFFFFF', '#424242', '#8B0000', '#8B4513',
    '#B8860B', '#218121', '#00A1A1', '#191970', '#8B008B', '#A35076',
    '#A6A6A6', '#000000'
]

# Symbol options
SYMBOLS_3D = ['circle', 'square', 'diamond', 'x', 'cross']


def generate_planet_html(planet_name: str, planet_id: int, system_name: str, pois: list,
                         biome: str = None, glyph_code: str = None) -> str:
    """
    Generate a complete HTML page with 3D planet visualization and POI management.

    Args:
        planet_name: Name of the planet
        planet_id: Database ID of the planet
        system_name: Name of the parent system
        pois: List of POI dictionaries with lat, lon, name, color, symbol, category
        biome: Optional biome type for planet color theming
        glyph_code: Optional portal glyph code

    Returns:
        Complete HTML string with embedded Plotly visualization
    """
    # Generate the Plotly figure
    fig = create_planet_figure(planet_name, pois, biome)

    # Convert figure to HTML div
    plot_div = fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={'displayModeBar': False, 'scrollZoom': False}
    )

    # Generate POI list HTML
    poi_list_html = generate_poi_list_html(pois)

    # Generate category options
    category_options = '\n'.join([
        f'<option value="{cat}">{cat}</option>' for cat in POI_CATEGORIES
    ])

    # Generate color palette
    color_palette = '\n'.join([
        f'<div class="color-btn" data-color="{c}" style="background-color: {c};"></div>'
        for c in COLOR_LIST
    ])

    # Generate symbol palette
    symbol_icons = {'circle': '●', 'square': '■', 'diamond': '◆', 'x': '✖', 'cross': '✚'}
    symbol_palette = '\n'.join([
        f'<div class="symbol-btn" data-symbol="{s}">{symbol_icons[s]}</div>'
        for s in SYMBOLS_3D
    ])

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{planet_name} - Planet Atlas</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #020617 0%, #0f172a 50%, #020617 100%);
            color: #e2e8f0;
            font-family: 'Roboto Mono', monospace;
            min-height: 100vh;
        }}

        .nav-bar {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(10px);
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            z-index: 1000;
            border-bottom: 1px solid #1a5c6b;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }}

        .nav-bar a {{
            color: #22d3ee;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: color 0.2s;
        }}

        .nav-bar a:hover {{
            color: #67e8f9;
        }}

        .planet-title {{
            color: #9d4edd;
            font-size: 18px;
            font-weight: 600;
            text-shadow: 0 0 10px rgba(157, 78, 221, 0.5);
        }}

        .system-name {{
            color: #64748b;
            font-size: 12px;
        }}

        .main-container {{
            display: flex;
            margin-top: 60px;
            height: calc(100vh - 60px);
        }}

        .globe-container {{
            flex: 1;
            min-width: 0;
        }}

        .side-panel {{
            width: 350px;
            background: rgba(18, 26, 35, 0.9);
            border-left: 1px solid #1a5c6b;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            transition: transform 0.3s ease, opacity 0.3s ease;
        }}

        .side-panel.collapsed {{
            transform: translateX(100%);
            opacity: 0;
            pointer-events: none;
        }}

        .toggle-panel-btn {{
            position: fixed;
            top: 80px;
            right: 360px;
            width: 32px;
            height: 32px;
            background: rgba(26, 92, 107, 0.9);
            border: 1px solid #22d3ee;
            border-radius: 4px;
            color: #22d3ee;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            z-index: 100;
            transition: all 0.3s ease;
        }}

        .toggle-panel-btn:hover {{
            background: #22d3ee;
            color: #0d1117;
        }}

        .toggle-panel-btn.panel-hidden {{
            right: 10px;
        }}

        .panel-header {{
            padding: 16px;
            border-bottom: 1px solid #1a5c6b;
            background: rgba(26, 92, 107, 0.2);
        }}

        .panel-header h2 {{
            margin: 0;
            color: #67e8f9;
            font-size: 14px;
            font-weight: 400;
            letter-spacing: 2px;
        }}

        .search-box {{
            margin-top: 12px;
        }}

        .search-input {{
            width: 100%;
            padding: 8px 12px;
            background: #0f172a;
            border: 1px solid #1a5c6b;
            border-radius: 4px;
            color: #e2e8f0;
            font-family: inherit;
            font-size: 12px;
        }}

        .search-input:focus {{
            outline: none;
            border-color: #22d3ee;
            box-shadow: 0 0 5px rgba(34, 211, 238, 0.3);
        }}

        .search-input::placeholder {{
            color: #64748b;
        }}

        .poi-count {{
            font-size: 10px;
            color: #64748b;
            margin-top: 8px;
        }}

        .panel-content {{
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }}

        .poi-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}

        .poi-item {{
            display: flex;
            align-items: center;
            padding: 10px;
            margin-bottom: 8px;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid #1a5c6b;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .poi-item:hover {{
            background: rgba(34, 211, 238, 0.1);
            border-color: #22d3ee;
        }}

        .poi-color {{
            width: 12px;
            height: 12px;
            border-radius: 2px;
            margin-right: 10px;
            flex-shrink: 0;
        }}

        .poi-info {{
            flex: 1;
            min-width: 0;
        }}

        .poi-name {{
            font-size: 13px;
            color: #e2e8f0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .poi-coords {{
            font-size: 10px;
            color: #64748b;
        }}

        .poi-actions {{
            display: flex;
            gap: 4px;
        }}

        .poi-btn {{
            width: 24px;
            height: 24px;
            border: none;
            background: transparent;
            color: #64748b;
            cursor: pointer;
            border-radius: 4px;
            font-size: 12px;
        }}

        .poi-btn:hover {{
            background: rgba(34, 211, 238, 0.2);
            color: #22d3ee;
        }}

        .poi-btn.delete:hover {{
            background: rgba(251, 113, 133, 0.2);
            color: #fb7185;
        }}

        .add-poi-form {{
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #1a5c6b;
        }}

        .form-title {{
            color: #22d3ee;
            font-size: 12px;
            letter-spacing: 1px;
            margin-bottom: 12px;
        }}

        .form-row {{
            margin-bottom: 10px;
        }}

        .form-row label {{
            display: block;
            font-size: 10px;
            color: #94a3b8;
            margin-bottom: 4px;
        }}

        .form-row input, .form-row select, .form-row textarea {{
            width: 100%;
            padding: 8px 10px;
            background: #0f172a;
            border: 1px solid #1a5c6b;
            border-radius: 4px;
            color: #e2e8f0;
            font-family: inherit;
            font-size: 12px;
        }}

        .form-row input:focus, .form-row select:focus, .form-row textarea:focus {{
            outline: none;
            border-color: #22d3ee;
            box-shadow: 0 0 5px rgba(34, 211, 238, 0.3);
        }}

        .coord-row {{
            display: flex;
            gap: 8px;
        }}

        .coord-row > div {{
            flex: 1;
        }}

        .color-palette, .symbol-palette {{
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-top: 4px;
        }}

        .color-btn {{
            width: 22px;
            height: 22px;
            border: 1px solid #475569;
            cursor: pointer;
            transition: transform 0.1s;
        }}

        .color-btn:hover {{
            transform: scale(1.1);
        }}

        .color-btn.selected {{
            border: 2px solid white;
            box-shadow: 0 0 8px currentColor;
        }}

        .symbol-btn {{
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #1e293b;
            border: 1px solid #475569;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            color: #e2e8f0;
        }}

        .symbol-btn:hover {{
            background: #22d3ee;
            color: #0d1117;
        }}

        .symbol-btn.selected {{
            background: #22d3ee;
            color: #0d1117;
            border-color: white;
        }}

        .btn-submit {{
            width: 100%;
            padding: 12px;
            margin-top: 16px;
            background: linear-gradient(135deg, #047857 0%, #065f46 100%);
            border: 1px solid #10b981;
            border-radius: 6px;
            color: white;
            font-family: inherit;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 1px;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .btn-submit:hover {{
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.4);
        }}

        .empty-state {{
            text-align: center;
            padding: 40px 20px;
            color: #64748b;
        }}

        .empty-state .icon {{
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.5;
        }}

        .toast {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            background: rgba(16, 185, 129, 0.9);
            color: white;
            border-radius: 6px;
            font-size: 13px;
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s;
            z-index: 2000;
        }}

        .toast.show {{
            opacity: 1;
            transform: translateY(0);
        }}

        .toast.error {{
            background: rgba(239, 68, 68, 0.9);
        }}

        /* Plotly overrides */
        .js-plotly-plot .plotly {{
            background: transparent !important;
        }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <a href="javascript:history.back()">
            <span>←</span>
            <span>Back to System</span>
        </a>
        <div style="text-align: center;">
            <div class="planet-title">{planet_name}</div>
            <div class="system-name">{system_name} System</div>
        </div>
        <div style="color: #64748b; font-size: 11px;">
            {glyph_code if glyph_code else ''}
        </div>
    </nav>

    <div class="main-container">
        <div class="globe-container">
            {plot_div}
        </div>

        <button class="toggle-panel-btn" id="toggle-panel" title="Toggle POI Panel">☰</button>

        <div class="side-panel" id="side-panel">
            <div class="panel-header">
                <h2>POINTS OF INTEREST</h2>
                <div class="search-box">
                    <input type="text" class="search-input" id="poi-search" placeholder="Search POIs...">
                </div>
                <div class="poi-count" id="poi-count">{len(pois)} POI(s) registered</div>
            </div>
            <div class="panel-content" id="panel-content">
                <ul class="poi-list" id="poi-list">
                    {poi_list_html if poi_list_html else """
                    <div class="empty-state">
                        <div class="icon">&#128205;</div>
                        <div>No POIs recorded yet</div>
                        <div style="font-size: 11px; margin-top: 8px;">Add your first point below</div>
                    </div>
                    """}
                </ul>

                <div class="add-poi-form">
                    <div class="form-title">+ ADD NEW POI</div>
                    <form id="poi-form" onsubmit="return submitPOI(event)">
                        <div class="form-row">
                            <label>NAME</label>
                            <input type="text" id="poi-name" placeholder="POI Name" required>
                        </div>

                        <div class="form-row coord-row">
                            <div>
                                <label>LATITUDE (-90 to 90)</label>
                                <input type="number" id="poi-lat" step="0.01" min="-90" max="90" placeholder="0.00" required>
                            </div>
                            <div>
                                <label>LONGITUDE (-180 to 180)</label>
                                <input type="number" id="poi-lon" step="0.01" min="-180" max="180" placeholder="0.00" required>
                            </div>
                        </div>

                        <div class="form-row">
                            <label>CATEGORY</label>
                            <select id="poi-category">
                                {category_options}
                            </select>
                        </div>

                        <div class="form-row">
                            <label>COLOR</label>
                            <div class="color-palette" id="color-palette">
                                {color_palette}
                            </div>
                            <input type="hidden" id="poi-color" value="#00C2B3">
                        </div>

                        <div class="form-row">
                            <label>SYMBOL</label>
                            <div class="symbol-palette" id="symbol-palette">
                                {symbol_palette}
                            </div>
                            <input type="hidden" id="poi-symbol" value="circle">
                        </div>

                        <div class="form-row">
                            <label>DESCRIPTION (optional)</label>
                            <textarea id="poi-desc" rows="2" placeholder="Notes about this location..."></textarea>
                        </div>

                        <button type="submit" class="btn-submit">💾 SAVE POI</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        const planetId = {planet_id};

        // --- PANEL TOGGLE ---
        const toggleBtn = document.getElementById('toggle-panel');
        const sidePanel = document.getElementById('side-panel');
        let panelVisible = true;

        toggleBtn.addEventListener('click', () => {{
            panelVisible = !panelVisible;
            sidePanel.classList.toggle('collapsed', !panelVisible);
            toggleBtn.classList.toggle('panel-hidden', !panelVisible);
            toggleBtn.textContent = panelVisible ? '☰' : '◀';
            toggleBtn.title = panelVisible ? 'Hide POI Panel' : 'Show POI Panel';
        }});

        // --- POI SEARCH ---
        const searchInput = document.getElementById('poi-search');
        const poiList = document.getElementById('poi-list');
        const poiCountEl = document.getElementById('poi-count');
        const allPois = Array.from(poiList.querySelectorAll('.poi-item'));

        searchInput.addEventListener('input', (e) => {{
            const query = e.target.value.toLowerCase().trim();
            let visibleCount = 0;

            allPois.forEach(poi => {{
                const name = poi.querySelector('.poi-name')?.textContent.toLowerCase() || '';
                const coords = poi.querySelector('.poi-coords')?.textContent.toLowerCase() || '';
                const matches = name.includes(query) || coords.includes(query);
                poi.style.display = matches ? 'flex' : 'none';
                if (matches) visibleCount++;
            }});

            poiCountEl.textContent = query
                ? `${{visibleCount}} of {len(pois)} POI(s) shown`
                : `{len(pois)} POI(s) registered`;
        }});

        // --- SCROLL EVENT FIX ---
        // Prevent scroll events on side panel from affecting the globe
        const panelContent = document.getElementById('panel-content');
        panelContent.addEventListener('wheel', (e) => {{
            e.stopPropagation();
        }}, {{ passive: true }});

        sidePanel.addEventListener('wheel', (e) => {{
            e.stopPropagation();
        }}, {{ passive: true }});

        // Color palette selection
        document.querySelectorAll('.color-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                document.getElementById('poi-color').value = btn.dataset.color;
            }});
        }});

        // Symbol palette selection
        document.querySelectorAll('.symbol-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.symbol-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                document.getElementById('poi-symbol').value = btn.dataset.symbol;
            }});
        }});

        // Set defaults
        document.querySelector('.color-btn[data-color="#00FFFF"]')?.classList.add('selected');
        document.querySelector('.symbol-btn[data-symbol="circle"]')?.classList.add('selected');

        function showToast(message, isError = false) {{
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.toggle('error', isError);
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }}

        async function submitPOI(event) {{
            event.preventDefault();

            const data = {{
                name: document.getElementById('poi-name').value,
                latitude: parseFloat(document.getElementById('poi-lat').value),
                longitude: parseFloat(document.getElementById('poi-lon').value),
                category: document.getElementById('poi-category').value,
                color: document.getElementById('poi-color').value,
                symbol: document.getElementById('poi-symbol').value,
                description: document.getElementById('poi-desc').value
            }};

            try {{
                const response = await fetch(`/api/planets/${{planetId}}/pois`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(data)
                }});

                if (response.ok) {{
                    showToast('POI saved successfully!');
                    setTimeout(() => location.reload(), 1000);
                }} else {{
                    const error = await response.json();
                    showToast(error.detail || 'Failed to save POI', true);
                }}
            }} catch (err) {{
                showToast('Network error: ' + err.message, true);
            }}
        }}

        async function deletePOI(poiId) {{
            if (!confirm('Delete this POI?')) return;

            try {{
                const response = await fetch(`/api/planets/pois/${{poiId}}`, {{
                    method: 'DELETE'
                }});

                if (response.ok) {{
                    showToast('POI deleted');
                    document.querySelector(`[data-poi-id="${{poiId}}"]`)?.remove();
                }} else {{
                    showToast('Failed to delete POI', true);
                }}
            }} catch (err) {{
                showToast('Network error', true);
            }}
        }}
    </script>
</body>
</html>'''

    return html


def create_planet_figure(planet_name: str, pois: list, biome: str = None) -> go.Figure:
    """Create a Plotly 3D globe figure with POI markers."""
    fig = go.Figure()

    # Choose planet surface color based on biome
    biome_colors = {
        'Lush': ['#0d1117', '#1a5c6b'],
        'Toxic': ['#0d1117', '#4a5c1b'],
        'Scorched': ['#0d1117', '#8b4513'],
        'Frozen': ['#0d1117', '#4a6fa5'],
        'Barren': ['#0d1117', '#5c5c5c'],
        'Dead': ['#0d1117', '#3a3a3a'],
        'Exotic': ['#0d1117', '#6b1a6b'],
        'Marsh': ['#0d1117', '#2e5c3a'],
    }
    colors = biome_colors.get(biome, ['#0d1117', '#1a5c6b'])

    # Create sphere surface
    theta = np.linspace(0, 2*np.pi, 100)
    phi = np.linspace(0, np.pi, 100)
    x = 29.5 * np.outer(np.cos(theta), np.sin(phi))
    y = 29.5 * np.outer(np.sin(theta), np.sin(phi))
    z = 29.5 * np.outer(np.ones(100), np.cos(phi))

    fig.add_trace(go.Surface(
        x=x, y=y, z=z,
        colorscale=[[0, colors[0]], [1, colors[1]]],
        opacity=0.4,
        showscale=False,
        hoverinfo='skip'
    ))

    # Add latitude/longitude grid lines
    for i in range(-90, 91, 30):
        lat_rad = np.deg2rad(i)
        lon_rad = np.linspace(0, 2 * np.pi, 100)
        x_grid = 30 * np.cos(lat_rad) * np.cos(lon_rad)
        y_grid = 30 * np.cos(lat_rad) * np.sin(lon_rad)
        z_grid = 30 * np.sin(lat_rad) * np.ones_like(lon_rad)
        fig.add_trace(go.Scatter3d(
            x=x_grid, y=y_grid, z=z_grid, mode='lines',
            line=dict(color='#22d3ee', width=1, dash='dot'),
            hoverinfo='skip', showlegend=False
        ))

    for i in range(0, 361, 45):
        lon_rad = np.deg2rad(i)
        lat_rad = np.linspace(-np.pi / 2, np.pi / 2, 100)
        x_grid = 30 * np.cos(lat_rad) * np.cos(lon_rad)
        y_grid = 30 * np.cos(lat_rad) * np.sin(lon_rad)
        z_grid = 30 * np.sin(lat_rad)
        fig.add_trace(go.Scatter3d(
            x=x_grid, y=y_grid, z=z_grid, mode='lines',
            line=dict(color='#22d3ee', width=1, dash='dot'),
            hoverinfo='skip', showlegend=False
        ))

    # Add POI markers
    if pois:
        # Group by category for legend
        categories = {}
        for poi in pois:
            cat = poi.get('category', '-')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(poi)

        for cat, cat_pois in categories.items():
            lats = [p.get('latitude', 0) for p in cat_pois]
            lons = [p.get('longitude', 0) for p in cat_pois]
            names = [p.get('name', 'Unknown') for p in cat_pois]
            colors_list = [p.get('color', '#22d3ee') for p in cat_pois]
            symbols = [p.get('symbol', 'circle') for p in cat_pois]

            lat_rad = np.deg2rad(lats)
            lon_rad = np.deg2rad(lons)

            px = 30.2 * np.cos(lat_rad) * np.cos(lon_rad)
            py = 30.2 * np.cos(lat_rad) * np.sin(lon_rad)
            pz = 30.2 * np.sin(lat_rad)

            # Map symbol sizes
            symbol_sizes = {'x': 6, 'cross': 14, 'diamond': 9, 'square': 11, 'circle': 12}
            sizes = [symbol_sizes.get(s, 12) for s in symbols]

            fig.add_trace(go.Scatter3d(
                x=px, y=py, z=pz,
                mode='markers',
                name=cat,
                marker=dict(
                    size=sizes,
                    symbol=symbols,
                    color=colors_list,
                    opacity=1.0,
                    line=dict(color=colors_list, width=6)
                ),
                text=names,
                textposition='top center',
                textfont=dict(size=14, color='#67e8f9'),
                customdata=[[lats[i], lons[i]] for i in range(len(lats))],
                hovertemplate='<b>%{text}</b><br>Lat: %{customdata[0]:.2f}<br>Lon: %{customdata[1]:.2f}<extra></extra>'
            ))

    # Configure layout
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, b=0, t=0),
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=0.01,
            xanchor='center',
            x=0.5,
            bgcolor='rgba(13, 17, 23, 0.6)',
            bordercolor='#1a5c6b',
            borderwidth=1
        ),
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            aspectmode='cube',
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5))
        ),
        uirevision='globe'
    )

    return fig


def generate_poi_list_html(pois: list) -> str:
    """Generate HTML for the POI list."""
    if not pois:
        return ''

    html_items = []
    for poi in pois:
        poi_id = poi.get('id', 0)
        name = poi.get('name', 'Unknown')
        lat = poi.get('latitude', 0)
        lon = poi.get('longitude', 0)
        color = poi.get('color', '#22d3ee')
        category = poi.get('category', '-')

        html_items.append(f'''
        <li class="poi-item" data-poi-id="{poi_id}">
            <div class="poi-color" style="background-color: {color};"></div>
            <div class="poi-info">
                <div class="poi-name">{name}</div>
                <div class="poi-coords">{lat:.2f}, {lon:.2f} • {category}</div>
            </div>
            <div class="poi-actions">
                <button class="poi-btn delete" onclick="deletePOI({poi_id})" title="Delete">🗑</button>
            </div>
        </li>
        ''')

    return '\n'.join(html_items)
