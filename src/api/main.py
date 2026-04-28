from datetime import date
from typing import Literal

import ee
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from climate.aras_eval import ArasDiagram
from climate.data_fetcher import ArasenseDataFetcher
from common.gee import get_earth_engine_status, get_project_id, initialize_earth_engine
from flood.graph_builder import ArasenseGraphBuilder


app = FastAPI(
    title="Arasense API",
    version="1.0.0",
    description="Minimal FastAPI backend for Arasense climate diagnostics and flood graph summaries.",
)


def model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


class ClimateDiagnosticRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(50, gt=0, le=500)
    start_date: date
    end_date: date
    variable: Literal["temperature", "precipitation", "all_euro_cordex"] = "temperature"
    ref_dataset: str = "ERA5-Land"
    fast_mode: bool = True


class FloodGraphRequest(BaseModel):
    west: float = Field(..., ge=-180, le=180)
    south: float = Field(..., ge=-90, le=90)
    east: float = Field(..., ge=-180, le=180)
    north: float = Field(..., ge=-90, le=90)
    scale: int = Field(2000, ge=250, le=10000)


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Arasense Climate Console</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
  <style>
    :root {
      --bg: #06151d;
      --bg-soft: #0b2029;
      --panel: rgba(10, 29, 37, 0.86);
      --panel-strong: rgba(8, 22, 29, 0.94);
      --line: rgba(121, 214, 196, 0.16);
      --text: #ebf9f4;
      --muted: #9bc9c0;
      --accent: #8bf0c7;
      --accent-strong: #29c48a;
      --amber: #ffd88a;
      --danger: #ff8f8f;
      --shadow: 0 30px 60px rgba(0, 0, 0, 0.24);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--text);
      font-family: "Space Grotesk", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(41, 196, 138, 0.16), transparent 26%),
        radial-gradient(circle at 90% 10%, rgba(255, 216, 138, 0.14), transparent 18%),
        linear-gradient(180deg, #031017 0%, var(--bg) 100%);
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.48), transparent 90%);
    }
    main {
      max-width: 1320px;
      margin: 0 auto;
      padding: 24px 24px 80px;
      position: relative;
      z-index: 1;
    }
    .nav, .hero, .workspace, .results-grid, .footer-panel {
      backdrop-filter: blur(18px);
    }
    .nav {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 28px;
      padding: 16px 20px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(7, 20, 26, 0.74);
      box-shadow: var(--shadow);
    }
    .brand-mark {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .brand-icon {
      width: 44px;
      height: 44px;
      border-radius: 14px;
      background: linear-gradient(135deg, rgba(139,240,199,0.22), rgba(41,196,138,0.78));
      display: grid;
      place-items: center;
      color: #04130f;
      font-weight: 700;
    }
    .brand-copy strong {
      display: block;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      font-size: 12px;
      color: var(--accent);
    }
    .brand-copy span {
      color: var(--muted);
      font-size: 14px;
    }
    .nav-links {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }
    .pill {
      text-decoration: none;
      border-radius: 999px;
      padding: 11px 16px;
      font-size: 14px;
      border: 1px solid var(--line);
      color: var(--text);
      background: rgba(255,255,255,0.04);
    }
    .pill.primary {
      color: #03140f;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      border-color: transparent;
      font-weight: 700;
    }
    .hero {
      display: grid;
      grid-template-columns: 1.25fr 0.75fr;
      gap: 22px;
      margin-bottom: 22px;
    }
    .hero-card, .hero-side, .panel, .footer-panel {
      border: 1px solid var(--line);
      border-radius: 28px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }
    .hero-card {
      padding: 34px;
      background:
        radial-gradient(circle at top right, rgba(139,240,199,0.14), transparent 22%),
        linear-gradient(160deg, rgba(10, 29, 37, 0.92), rgba(6, 19, 25, 0.96));
    }
    .hero-side {
      padding: 26px;
      background:
        linear-gradient(160deg, rgba(18, 55, 63, 0.94), rgba(7, 20, 26, 0.96));
    }
    .eyebrow {
      display: inline-block;
      margin-bottom: 14px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 12px;
      color: var(--accent);
    }
    h1, h2, h3 {
      margin: 0;
      font-family: "Fraunces", serif;
      font-weight: 700;
      letter-spacing: -0.03em;
    }
    h1 {
      font-size: clamp(44px, 7vw, 88px);
      line-height: 0.95;
      max-width: 760px;
      margin-bottom: 18px;
    }
    .lead {
      max-width: 760px;
      color: var(--muted);
      line-height: 1.7;
      font-size: 18px;
      margin-bottom: 28px;
    }
    .hero-stats {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }
    .stat {
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 16px;
      background: rgba(255,255,255,0.03);
    }
    .stat strong {
      display: block;
      font-size: 28px;
      color: var(--accent);
      margin-bottom: 6px;
    }
    .hero-side p, .hero-side li, .stat span {
      color: var(--muted);
      line-height: 1.6;
    }
    .hero-side ul {
      padding-left: 18px;
      margin: 16px 0 0;
    }
    .workspace {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 22px;
      margin-bottom: 22px;
    }
    .panel {
      padding: 22px;
      background: var(--panel-strong);
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 16px;
    }
    .panel-header p {
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.6;
      max-width: 680px;
    }
    .badge {
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 12px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--amber);
      background: rgba(255, 216, 138, 0.12);
      border: 1px solid rgba(255, 216, 138, 0.2);
      white-space: nowrap;
    }
    #map {
      height: 620px;
      border-radius: 22px;
      border: 1px solid var(--line);
      overflow: hidden;
      position: relative;
    }
    .map-fallback {
      display: none;
      place-items: center;
      text-align: center;
      padding: 24px;
      height: 620px;
      border-radius: 22px;
      border: 1px solid rgba(255, 143, 143, 0.28);
      background: rgba(255, 143, 143, 0.08);
      color: var(--text);
    }
    .map-tools {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 14px;
    }
    .tool {
      border-radius: 16px;
      border: 1px solid var(--line);
      padding: 14px 16px;
      background: rgba(255,255,255,0.03);
      color: var(--muted);
    }
    .tool strong {
      display: block;
      color: var(--text);
      margin-bottom: 4px;
    }
    .controls {
      display: grid;
      gap: 16px;
    }
    .control-card {
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 18px;
      background: rgba(255,255,255,0.03);
    }
    .mode-tabs {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 12px;
    }
    .mode-tab {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
      cursor: pointer;
      background: rgba(255,255,255,0.03);
      color: var(--muted);
      text-align: center;
      font-weight: 700;
    }
    .mode-tab.active {
      background: linear-gradient(135deg, rgba(139,240,199,0.18), rgba(41,196,138,0.34));
      color: var(--text);
      border-color: rgba(139,240,199,0.36);
    }
    form {
      display: grid;
      gap: 12px;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    label {
      display: grid;
      gap: 6px;
      font-size: 13px;
      color: var(--muted);
    }
    input, select, textarea, button {
      width: 100%;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(3, 18, 23, 0.9);
      color: var(--text);
      padding: 12px 14px;
      font: inherit;
    }
    textarea {
      min-height: 360px;
      resize: vertical;
      font-family: "Space Grotesk", sans-serif;
    }
    button {
      cursor: pointer;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      color: #042016;
      border-color: transparent;
    }
    .secondary {
      background: rgba(255,255,255,0.04);
      color: var(--text);
      border-color: var(--line);
    }
    .meta-line {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 12px;
    }
    .chip {
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 12px;
      color: var(--muted);
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--line);
    }
    .results-grid {
      display: grid;
      grid-template-columns: 0.8fr 1.2fr;
      gap: 22px;
      margin-bottom: 22px;
    }
    .results-stack {
      display: grid;
      gap: 22px;
    }
    .insight-list {
      display: grid;
      gap: 12px;
      margin-top: 16px;
    }
    .insight {
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.03);
    }
    .insight strong {
      display: block;
      margin-bottom: 4px;
      color: var(--accent);
    }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }
    .metric {
      padding: 14px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
    }
    .metric strong {
      display: block;
      margin-bottom: 6px;
      font-size: 24px;
      color: var(--accent);
    }
    .footer-panel {
      padding: 22px;
      background: rgba(7, 20, 26, 0.8);
      border: 1px solid var(--line);
      border-radius: 24px;
    }
    .status.ok { color: var(--accent); }
    .status.error { color: var(--danger); }
    .leaflet-container {
      background: #09212b;
      font-family: "Space Grotesk", sans-serif;
    }
    .diagram-shell {
      border-radius: 22px;
      border: 1px solid var(--line);
      background: radial-gradient(circle at top, rgba(139,240,199,0.08), transparent 32%), rgba(255,255,255,0.02);
      min-height: 420px;
      padding: 16px;
    }
    .diagram-shell svg {
      width: 100%;
      height: 100%;
      min-height: 380px;
      display: block;
    }
    .diagram-placeholder {
      min-height: 380px;
      display: grid;
      place-items: center;
      text-align: center;
      color: var(--muted);
      line-height: 1.7;
    }
    .subpanel-grid {
      display: grid;
      grid-template-columns: 0.9fr 1.1fr;
      gap: 22px;
      margin-top: 22px;
    }
    .table-shell {
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      background: rgba(255,255,255,0.02);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
    }
    th {
      color: var(--muted);
      font-weight: 500;
      background: rgba(255,255,255,0.03);
    }
    td strong {
      color: var(--text);
    }
    .chart-shell {
      border-radius: 22px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.02);
      min-height: 360px;
      padding: 16px;
    }
    .chart-shell svg {
      width: 100%;
      height: 100%;
      min-height: 320px;
      display: block;
    }
    .legend-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    .legend-swatch {
      width: 12px;
      height: 12px;
      border-radius: 999px;
    }
    @media (max-width: 980px) {
      .hero, .workspace, .results-grid, .row, .hero-stats, .metric-grid, .map-tools, .subpanel-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="nav">
      <div class="brand-mark">
        <div class="brand-icon">A</div>
        <div class="brand-copy">
          <strong>Arasense Climate Console</strong>
          <span>Map-first geospatial diagnostics for local testing</span>
        </div>
      </div>
      <div class="nav-links">
        <a class="pill" href="/healthz">Health</a>
        <a class="pill primary" href="/docs">API Docs</a>
      </div>
    </section>

    <section class="hero">
      <div class="hero-card">
        <div class="eyebrow">Spatial intelligence workbench</div>
        <h1>Next-level climate tech, running directly on your machine.</h1>
        <p class="lead">
          This console combines a live geospatial map, climate model diagnostics, and flood topology
          summaries in one interface. Click the map to set a climate point, drag a box for flood analysis,
          and inspect structured outputs without leaving the page.
        </p>
        <div class="hero-stats">
          <div class="stat"><strong>Live</strong><span>Map-driven spatial input selection</span></div>
          <div class="stat"><strong>GEE</strong><span>Earth Engine-backed climate retrieval</span></div>
          <div class="stat"><strong>FastAPI</strong><span>Local backend with deployable surface</span></div>
        </div>
      </div>
      <aside class="hero-side">
        <h2>Workflow</h2>
        <p>Use the interface in this order for the cleanest results.</p>
        <ul>
          <li>Click the map to position the climate ROI center and radius.</li>
          <li>Shift-drag on the map to define a flood bounding box.</li>
          <li>Run diagnostics and inspect structured metrics in the console below.</li>
        </ul>
        <div class="meta-line">
          <span class="chip">Project: valid-shine-488311-d6</span>
          <span class="chip">Mode: local</span>
          <span class="chip">Docs: /docs</span>
        </div>
      </aside>
    </section>

    <section class="workspace">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>Spatial Command Map</h2>
            <p>Single click sets the climate analysis point. Hold <strong>Shift</strong> and drag to draw a flood bounding box.</p>
          </div>
          <div class="badge" id="map-status">Map ready</div>
        </div>
        <div id="map"></div>
        <div class="map-fallback" id="map-fallback">
          <div>
            <h3 style="margin-bottom:10px;">Map failed to load</h3>
            <p style="margin:0; color:var(--muted);">The external map library did not load in the browser. Reload the page or check browser console/network access.</p>
          </div>
        </div>
        <div class="map-tools">
          <div class="tool">
            <strong>Climate target</strong>
            <span id="climate-target">Lat 41.9028, Lon 12.4964, Radius 20 km</span>
          </div>
          <div class="tool">
            <strong>Flood box</strong>
            <span id="flood-target">West 11.0, South 44.2, East 11.3, North 44.4</span>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>Mission Controls</h2>
            <p>Drive both analysis modes from the same console. The forms stay editable after map selection.</p>
          </div>
        </div>

        <div class="controls">
          <div class="control-card">
            <div class="mode-tabs">
              <div class="mode-tab active" data-target="climate-card">Climate Engine</div>
              <div class="mode-tab" data-target="flood-card">Flood Engine</div>
            </div>
          </div>

          <div class="control-card" id="climate-card">
            <h3>Climate Diagnostic</h3>
            <form id="climate-form">
              <div class="row">
                <label>Latitude<input name="lat" id="climate-lat" type="number" step="any" value="41.9028"></label>
                <label>Longitude<input name="lon" id="climate-lon" type="number" step="any" value="12.4964"></label>
              </div>
              <div class="row">
                <label>Radius (km)<input name="radius_km" id="climate-radius" type="number" step="any" value="20"></label>
                <label>Variable
                  <select name="variable">
                    <option value="temperature">temperature</option>
                    <option value="precipitation">precipitation</option>
                    <option value="all_euro_cordex">all_euro_cordex</option>
                  </select>
                </label>
              </div>
              <div class="row">
                <label>Start Date<input name="start_date" type="date" value="2014-01-01"></label>
                <label>End Date<input name="end_date" type="date" value="2014-01-31"></label>
              </div>
              <div class="row">
                <label>Reference Dataset<input name="ref_dataset" type="text" value="ERA5-Land"></label>
                <label>Fast Mode
                  <select name="fast_mode">
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
              </div>
              <div class="row">
                <button type="submit">Run Climate Diagnostic</button>
                <button class="secondary" type="button" id="snap-rome">Reset to Rome</button>
              </div>
            </form>
          </div>

          <div class="control-card" id="flood-card" style="display:none;">
            <h3>Flood Graph Summary</h3>
            <form id="flood-form">
              <div class="row">
                <label>West<input name="west" id="flood-west" type="number" step="any" value="11.0"></label>
                <label>South<input name="south" id="flood-south" type="number" step="any" value="44.2"></label>
              </div>
              <div class="row">
                <label>East<input name="east" id="flood-east" type="number" step="any" value="11.3"></label>
                <label>North<input name="north" id="flood-north" type="number" step="any" value="44.4"></label>
              </div>
              <div class="row">
                <label>Scale<input name="scale" type="number" step="1" value="4000"></label>
                <button type="submit" style="align-self:end;">Run Flood Summary</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </section>

    <section class="results-grid">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>Operational Summary</h2>
            <p>The panel below surfaces the most relevant interpretation from the most recent request.</p>
          </div>
          <div class="badge status ok" id="request-status">Idle</div>
        </div>
        <div class="metric-grid" id="metric-grid">
          <div class="metric"><strong>0</strong><span>Reference points</span></div>
          <div class="metric"><strong>0</strong><span>Models or nodes</span></div>
          <div class="metric"><strong>0</strong><span>Edges or top score</span></div>
        </div>
        <div class="insight-list" id="insights">
          <div class="insight"><strong>Ready</strong><span>Select a point or bounding box, then run an analysis.</span></div>
        </div>
      </div>

      <div class="results-stack">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Aras Diagram</h2>
              <p>Climate runs render a live alpha-beta diagnostic view here. Flood runs keep the last diagram until the next climate request.</p>
            </div>
          </div>
          <div class="diagram-shell" id="diagram-shell">
            <div class="diagram-placeholder" id="diagram-placeholder">
              Run a climate diagnostic to generate the Aras diagram.
            </div>
          </div>
        </div>

        <div class="subpanel-grid">
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Model Ranking</h2>
                <p>Sorted by total error so the strongest model rises to the top immediately.</p>
              </div>
            </div>
            <div class="table-shell" id="ranking-shell">
              <div class="diagram-placeholder" style="min-height:260px;">Run a climate diagnostic to populate the ranking table.</div>
            </div>
          </div>

          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Climate Time Series</h2>
                <p>Reference vs. top model trajectories across the selected period.</p>
              </div>
            </div>
            <div class="chart-shell" id="series-shell">
              <div class="diagram-placeholder" style="min-height:300px;">Run a climate diagnostic to plot the reference and model series.</div>
            </div>
            <div class="legend-row" id="series-legend"></div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Response Console</h2>
              <p>Raw JSON stays visible for validation, debugging, and API confidence checks.</p>
            </div>
          </div>
          <textarea id="response" readonly>{
  "message": "Run a climate or flood request from the controls above."
}</textarea>
        </div>
      </div>
    </section>

    <section class="footer-panel">
      <div class="panel-header">
        <div>
          <h2>Service Snapshot</h2>
          <p>This local console is a map-first interface on top of the same FastAPI service you can later ship to Cloud Run.</p>
        </div>
      </div>
      <div class="meta-line">
        <span class="chip">GET /healthz</span>
        <span class="chip">POST /api/climate/diagnostic</span>
        <span class="chip">POST /api/flood/graph-summary</span>
      </div>
    </section>
  </main>

  <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const responseBox = document.getElementById('response');
    const requestStatus = document.getElementById('request-status');
    const metricGrid = document.getElementById('metric-grid');
    const insights = document.getElementById('insights');
    const diagramShell = document.getElementById('diagram-shell');
    const diagramPlaceholder = document.getElementById('diagram-placeholder');
    const rankingShell = document.getElementById('ranking-shell');
    const seriesShell = document.getElementById('series-shell');
    const seriesLegend = document.getElementById('series-legend');
    const climateTarget = document.getElementById('climate-target');
    const floodTarget = document.getElementById('flood-target');
    const mapStatus = document.getElementById('map-status');

    const climateLat = document.getElementById('climate-lat');
    const climateLon = document.getElementById('climate-lon');
    const climateRadius = document.getElementById('climate-radius');
    const floodWest = document.getElementById('flood-west');
    const floodSouth = document.getElementById('flood-south');
    const floodEast = document.getElementById('flood-east');
    const floodNorth = document.getElementById('flood-north');
    const mapFallback = document.getElementById('map-fallback');

    if (typeof window.L === 'undefined') {
      document.getElementById('map').style.display = 'none';
      mapFallback.style.display = 'grid';
      mapStatus.textContent = 'Map library unavailable';
    } else {
      const map = L.map('map', { zoomControl: true }).setView([42.5, 12.8], 5);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map);

      let climateMarker = L.marker([Number(climateLat.value), Number(climateLon.value)]).addTo(map);
      let climateCircle = L.circle([Number(climateLat.value), Number(climateLon.value)], {
        radius: Number(climateRadius.value) * 1000,
        color: '#8bf0c7',
        weight: 2,
        fillColor: '#8bf0c7',
        fillOpacity: 0.14
      }).addTo(map);
      let floodRect = L.rectangle([[Number(floodSouth.value), Number(floodWest.value)], [Number(floodNorth.value), Number(floodEast.value)]], {
        color: '#ffd88a',
        weight: 2,
        fillColor: '#ffd88a',
        fillOpacity: 0.12
      }).addTo(map);

      function updateClimateVisual() {
        const lat = Number(climateLat.value);
        const lon = Number(climateLon.value);
        const radiusKm = Number(climateRadius.value);
        climateMarker.setLatLng([lat, lon]);
        climateCircle.setLatLng([lat, lon]);
        climateCircle.setRadius(radiusKm * 1000);
        climateTarget.textContent = `Lat ${lat.toFixed(4)}, Lon ${lon.toFixed(4)}, Radius ${radiusKm} km`;
      }

      function updateFloodVisual() {
        const west = Number(floodWest.value);
        const south = Number(floodSouth.value);
        const east = Number(floodEast.value);
        const north = Number(floodNorth.value);
        floodRect.setBounds([[south, west], [north, east]]);
        floodTarget.textContent = `West ${west.toFixed(3)}, South ${south.toFixed(3)}, East ${east.toFixed(3)}, North ${north.toFixed(3)}`;
      }

      updateClimateVisual();
      updateFloodVisual();

      climateLat.addEventListener('input', updateClimateVisual);
      climateLon.addEventListener('input', updateClimateVisual);
      climateRadius.addEventListener('input', updateClimateVisual);
      floodWest.addEventListener('input', updateFloodVisual);
      floodSouth.addEventListener('input', updateFloodVisual);
      floodEast.addEventListener('input', updateFloodVisual);
      floodNorth.addEventListener('input', updateFloodVisual);

      map.on('click', (event) => {
        climateLat.value = event.latlng.lat.toFixed(4);
        climateLon.value = event.latlng.lng.toFixed(4);
        updateClimateVisual();
        mapStatus.textContent = 'Climate point updated';
      });

      let dragStart = null;
      let draftRect = null;
      map.getContainer().style.cursor = 'crosshair';

      map.on('mousedown', (event) => {
        if (!event.originalEvent.shiftKey) {
          return;
        }
        dragStart = event.latlng;
        if (draftRect) {
          map.removeLayer(draftRect);
        }
        draftRect = L.rectangle([dragStart, dragStart], {
          color: '#ffb347',
          dashArray: '6 6',
          weight: 1
        }).addTo(map);
        map.dragging.disable();
        mapStatus.textContent = 'Drawing flood box';
      });

      map.on('mousemove', (event) => {
        if (!dragStart || !draftRect) {
          return;
        }
        draftRect.setBounds(L.latLngBounds(dragStart, event.latlng));
      });

      map.on('mouseup', (event) => {
        if (!dragStart) {
          return;
        }
        const bounds = L.latLngBounds(dragStart, event.latlng);
        floodWest.value = bounds.getWest().toFixed(3);
        floodSouth.value = bounds.getSouth().toFixed(3);
        floodEast.value = bounds.getEast().toFixed(3);
        floodNorth.value = bounds.getNorth().toFixed(3);
        updateFloodVisual();
        if (draftRect) {
          map.removeLayer(draftRect);
          draftRect = null;
        }
        dragStart = null;
        map.dragging.enable();
        mapStatus.textContent = 'Flood box updated';
      });

      document.getElementById('snap-rome').addEventListener('click', () => {
        climateLat.value = '41.9028';
        climateLon.value = '12.4964';
        climateRadius.value = '20';
        map.setView([41.9028, 12.4964], 8);
        updateClimateVisual();
        mapStatus.textContent = 'Reset to Rome';
      });
    }

    document.querySelectorAll('.mode-tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.mode-tab').forEach((node) => node.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('climate-card').style.display = tab.dataset.target === 'climate-card' ? 'block' : 'none';
        document.getElementById('flood-card').style.display = tab.dataset.target === 'flood-card' ? 'block' : 'none';
      });
    });

    function setStatus(text, kind) {
      requestStatus.textContent = text;
      requestStatus.className = `badge status ${kind}`;
    }

    function setInsights(items) {
      insights.innerHTML = items.map((item) => `<div class="insight"><strong>${item.title}</strong><span>${item.text}</span></div>`).join('');
    }

    function setMetrics(values) {
      metricGrid.innerHTML = values.map((item) => `<div class="metric"><strong>${item.value}</strong><span>${item.label}</span></div>`).join('');
    }

    function renderArasDiagram(metrics) {
      if (!metrics || !metrics.length) {
        diagramShell.innerHTML = '<div class="diagram-placeholder">No climate metrics available for diagram rendering.</div>';
        return;
      }

      const width = 760;
      const height = 420;
      const pad = 56;
      const values = [];
      metrics.forEach((item) => {
        values.push(item.alpha, item.beta);
      });
      const maxVal = Math.max(0.5, ...values.map((value) => Math.abs(Number(value || 0)))) * 1.2;
      const toX = (value) => pad + ((value + maxVal) / (2 * maxVal)) * (width - pad * 2);
      const toY = (value) => height - pad - ((value + maxVal) / (2 * maxVal)) * (height - pad * 2);
      const colors = ['#8bf0c7', '#ffd88a', '#7cc8ff', '#ff9bb3', '#d8b4fe', '#fca36b', '#5eead4'];

      const circles = [0.1, 0.2, 0.3, 0.4, 0.5].map((r) => {
        const rr = ((r * (width - pad * 2)) / (2 * maxVal));
        return `<circle cx="${toX(0)}" cy="${toY(0)}" r="${rr}" fill="none" stroke="rgba(255,255,255,0.12)" stroke-dasharray="4 6" />`;
      }).join('');

      const labels = metrics.map((item, index) => {
        const x = toX(Number(item.alpha));
        const y = toY(Number(item.beta));
        const color = colors[index % colors.length];
        return `
          <circle cx="${x}" cy="${y}" r="6" fill="${color}" />
          <text x="${x + 10}" y="${y - 10}" fill="#dffcf1" font-size="12">${item.name}</text>
        `;
      }).join('');

      diagramShell.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Aras Diagram">
          <rect x="0" y="0" width="${width}" height="${height}" rx="18" fill="transparent"></rect>
          ${circles}
          <line x1="${toX(-maxVal)}" y1="${toY(0)}" x2="${toX(maxVal)}" y2="${toY(0)}" stroke="rgba(255,255,255,0.25)" />
          <line x1="${toX(0)}" y1="${toY(-maxVal)}" x2="${toX(0)}" y2="${toY(maxVal)}" stroke="rgba(255,255,255,0.25)" />
          <text x="${width / 2}" y="${height - 16}" text-anchor="middle" fill="#9bc9c0" font-size="13">Bias ratio - 1 (alpha)</text>
          <text x="18" y="${height / 2}" text-anchor="middle" fill="#9bc9c0" font-size="13" transform="rotate(-90 18 ${height / 2})">Variability ratio - 1 (beta)</text>
          ${labels}
        </svg>
      `;
    }

    function renderRankingTable(metrics) {
      if (!metrics || !metrics.length) {
        rankingShell.innerHTML = '<div class="diagram-placeholder" style="min-height:260px;">No model ranking available.</div>';
        return;
      }
      const ordered = [...metrics].sort((a, b) => a.error_total_pct - b.error_total_pct);
      rankingShell.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Model</th>
              <th>Error %</th>
              <th>Alpha</th>
              <th>Beta</th>
              <th>Corr</th>
            </tr>
          </thead>
          <tbody>
            ${ordered.map((item, index) => `
              <tr>
                <td><strong>${index + 1}</strong></td>
                <td>${item.name}</td>
                <td>${Number(item.error_total_pct).toFixed(2)}</td>
                <td>${Number(item.alpha).toFixed(3)}</td>
                <td>${Number(item.beta).toFixed(3)}</td>
                <td>${Number(item.correlation).toFixed(3)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    function buildLinePath(points, width, height, pad, minVal, maxVal) {
      const toX = (index, total) => pad + (index / Math.max(total - 1, 1)) * (width - pad * 2);
      const toY = (value) => height - pad - ((value - minVal) / Math.max(maxVal - minVal, 1e-9)) * (height - pad * 2);
      return points.map((value, index) => `${index === 0 ? 'M' : 'L'} ${toX(index, points.length)} ${toY(value)}`).join(' ');
    }

    function renderSeriesChart(referenceSeries, modelSeries, bestModelName) {
      const referenceEntries = Object.entries(referenceSeries || {});
      if (!referenceEntries.length || !bestModelName || !modelSeries || !modelSeries[bestModelName]) {
        seriesShell.innerHTML = '<div class="diagram-placeholder" style="min-height:300px;">No time series available.</div>';
        seriesLegend.innerHTML = '';
        return;
      }

      const modelEntries = Object.entries(modelSeries[bestModelName]);
      const mergedDates = referenceEntries
        .map(([date]) => date)
        .filter((date) => Object.prototype.hasOwnProperty.call(modelSeries[bestModelName], date));
      const refValues = mergedDates.map((date) => Number(referenceSeries[date]));
      const modelValues = mergedDates.map((date) => Number(modelSeries[bestModelName][date]));
      const allValues = [...refValues, ...modelValues];
      const minVal = Math.min(...allValues);
      const maxVal = Math.max(...allValues);
      const width = 760;
      const height = 340;
      const pad = 42;
      const refPath = buildLinePath(refValues, width, height, pad, minVal, maxVal);
      const modelPath = buildLinePath(modelValues, width, height, pad, minVal, maxVal);

      seriesShell.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Climate time series">
          <rect x="0" y="0" width="${width}" height="${height}" rx="18" fill="transparent"></rect>
          <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="rgba(255,255,255,0.2)" />
          <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="rgba(255,255,255,0.2)" />
          <path d="${refPath}" fill="none" stroke="#8bf0c7" stroke-width="3" />
          <path d="${modelPath}" fill="none" stroke="#ffd88a" stroke-width="3" />
          <text x="${pad}" y="${pad - 12}" fill="#9bc9c0" font-size="12">Max ${maxVal.toFixed(2)}</text>
          <text x="${pad}" y="${height - 16}" fill="#9bc9c0" font-size="12">Min ${minVal.toFixed(2)}</text>
          <text x="${width / 2}" y="${height - 10}" text-anchor="middle" fill="#9bc9c0" font-size="12">${mergedDates[0]} to ${mergedDates[mergedDates.length - 1]}</text>
        </svg>
      `;
      seriesLegend.innerHTML = `
        <div class="legend-item"><span class="legend-swatch" style="background:#8bf0c7;"></span>Reference</div>
        <div class="legend-item"><span class="legend-swatch" style="background:#ffd88a;"></span>${bestModelName}</div>
      `;
    }

    async function submitJson(url, payload, mode) {
      setStatus('Running', 'ok');
      responseBox.value = JSON.stringify({ loading: true, url, payload }, null, 2);
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const text = await response.text();
        let data = null;
        try {
          data = JSON.parse(text);
          responseBox.value = JSON.stringify(data, null, 2);
        } catch {
          responseBox.value = text;
        }
        if (!response.ok) {
          throw new Error(data && data.detail ? data.detail : `HTTP ${response.status}`);
        }
        if (mode === 'climate') {
          const best = data.metrics && data.metrics.length ? data.metrics.reduce((a, b) => (a.error_total_pct < b.error_total_pct ? a : b)) : null;
          renderArasDiagram(data.metrics);
          renderRankingTable(data.metrics);
          renderSeriesChart(data.reference_series, data.model_series, best ? best.name : null);
          setMetrics([
            { value: String(data.reference_points || 0), label: 'Reference points' },
            { value: String((data.models || []).length), label: 'Models benchmarked' },
            { value: best ? best.name : '-', label: 'Lowest error model' }
          ]);
          setInsights([
            { title: 'Climate run completed', text: `Fetched ${data.reference_points || 0} reference points for the selected ROI.` },
            { title: 'Best current model', text: best ? `${best.name} with ${best.error_total_pct.toFixed(2)}% total error.` : 'No model metrics returned.' },
            { title: 'Coverage', text: `Variable ${payload.variable} from ${payload.start_date} to ${payload.end_date}.` }
          ]);
        } else {
          setMetrics([
            { value: String(data.nodes || 0), label: 'Graph nodes' },
            { value: String(data.edges || 0), label: 'Hydro edges' },
            { value: `${data.rows || 0} x ${data.cols || 0}`, label: 'Grid shape' }
          ]);
          setInsights([
            { title: 'Flood graph created', text: `Built topology across ${data.rows || 0} rows and ${data.cols || 0} columns.` },
            { title: 'Terrain summary', text: `Mean normalized elevation ${Number(data.mean_normalized_elevation || 0).toFixed(3)}, slope ${Number(data.mean_normalized_slope || 0).toFixed(3)}.` },
            { title: 'Selected extent', text: `West ${payload.west}, South ${payload.south}, East ${payload.east}, North ${payload.north}.` }
          ]);
        }
        setStatus('Success', 'ok');
      } catch (error) {
        setStatus('Error', 'error');
        setInsights([
          { title: 'Request failed', text: error.message },
          { title: 'Check inputs', text: 'Verify the selected dates, geometry, and Earth Engine availability.' }
        ]);
        setMetrics([
          { value: '0', label: 'Valid output' },
          { value: '1', label: 'Request attempted' },
          { value: 'ERR', label: 'Status' }
        ]);
      }
    }

    document.getElementById('climate-form').addEventListener('submit', (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      submitJson('/api/climate/diagnostic', {
        lat: Number(form.get('lat')),
        lon: Number(form.get('lon')),
        radius_km: Number(form.get('radius_km')),
        start_date: form.get('start_date'),
        end_date: form.get('end_date'),
        variable: form.get('variable'),
        ref_dataset: form.get('ref_dataset'),
        fast_mode: form.get('fast_mode') === 'true'
      }, 'climate');
    });

    document.getElementById('flood-form').addEventListener('submit', (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      submitJson('/api/flood/graph-summary', {
        west: Number(form.get('west')),
        south: Number(form.get('south')),
        east: Number(form.get('east')),
        north: Number(form.get('north')),
        scale: Number(form.get('scale'))
      }, 'flood');
    });
  </script>
</body>
</html>"""


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return get_earth_engine_status()


@app.post("/api/climate/diagnostic")
def climate_diagnostic(payload: ClimateDiagnosticRequest) -> dict:
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date.")

    try:
        project_id = initialize_earth_engine()
        roi = ee.Geometry.Point([payload.lon, payload.lat]).buffer(payload.radius_km * 1000)
        fetcher = ArasenseDataFetcher(project_id)
        results = fetcher.get_climate_data(
            geometry=roi,
            start_date=payload.start_date.isoformat(),
            end_date=payload.end_date.isoformat(),
            variable=payload.variable,
            ref_dataset=payload.ref_dataset,
            fast_mode=payload.fast_mode,
        )
        if not results:
            raise HTTPException(status_code=404, detail="No climate data returned for the selected inputs.")

        model_names = list(results.keys())
        reference_series = results[model_names[0]]["reference"]
        model_series = [results[name]["model"] for name in model_names]
        aras = ArasDiagram(reference_series, model_series, model_names)

        metrics = []
        for item in aras.results:
            metrics.append(
                {
                    "name": item["name"],
                    "alpha": float(item["alpha"]),
                    "beta": float(item["beta"]),
                    "correlation": float(item["r"]),
                    "kge": float(item["kge"]),
                    "error_total_pct": float(item["e_total"]),
                }
            )

        return {
            "project_id": project_id,
            "input": model_to_dict(payload),
            "reference_points": int(len(reference_series)),
            "models": model_names,
            "metrics": metrics,
            "reference_series": {
                idx.strftime("%Y-%m-%d"): float(value) for idx, value in reference_series.items()
            },
            "model_series": {
                name: {
                    idx.strftime("%Y-%m-%d"): float(value)
                    for idx, value in results[name]["model"].items()
                }
                for name in model_names
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/flood/graph-summary")
def flood_graph_summary(payload: FloodGraphRequest) -> dict:
    if payload.west >= payload.east or payload.south >= payload.north:
        raise HTTPException(status_code=400, detail="Bounding box is invalid.")

    try:
        project_id = initialize_earth_engine()
        region = ee.Geometry.Rectangle([payload.west, payload.south, payload.east, payload.north])
        builder = ArasenseGraphBuilder(project_id)
        graph, shape = builder.build_hydrological_graph(region, scale=payload.scale)

        feature_means = graph.x.mean(dim=0).tolist() if graph.x.numel() else [0.0, 0.0]
        return {
            "project_id": project_id,
            "input": model_to_dict(payload),
            "rows": int(shape[0]),
            "cols": int(shape[1]),
            "nodes": int(graph.num_nodes),
            "edges": int(graph.edge_index.shape[1]),
            "mean_normalized_elevation": float(feature_means[0]),
            "mean_normalized_slope": float(feature_means[1]),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
