"""Interactive Web Dashboard generator and lightweight local server for GitSize.

Zero-dependency implementation using Python's standard library (http.server, webbrowser, json).
Generates a responsive, modern HTML5/Vanilla CSS dashboard with interactive charts,
real-time search filters, dark/light themes, and file analytics.
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from pathlib import Path
import threading
from typing import Any
import webbrowser

from gitsize import __version__


def generate_dashboard_html(data: dict[str, Any]) -> str:
    """Generate a self-contained, standalone HTML5 dashboard with embedded data."""
    json_payload = json.dumps(data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GitSize Dashboard — Repository Storage Analyzer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #090D16;
      --bg-card: rgba(17, 24, 39, 0.75);
      --bg-card-hover: rgba(26, 36, 56, 0.85);
      --border: rgba(255, 255, 255, 0.08);
      --border-accent: rgba(99, 102, 241, 0.3);
      --text-main: #F3F4F6;
      --text-muted: #9CA3AF;
      --text-dim: #6B7280;
      --primary: #6366F1;
      --primary-gradient: linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #EC4899 100%);
      --accent-cyan: #06B6D4;
      --accent-emerald: #10B981;
      --accent-amber: #F59E0B;
      --accent-rose: #F43F5E;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
      --radius: 12px;
      --shadow-glow: 0 0 25px rgba(99, 102, 241, 0.15);
    }}

    [data-theme="light"] {{
      --bg: #F8FAFC;
      --bg-card: rgba(255, 255, 255, 0.85);
      --bg-card-hover: rgba(241, 245, 249, 0.95);
      --border: rgba(0, 0, 0, 0.08);
      --border-accent: rgba(99, 102, 241, 0.3);
      --text-main: #0F172A;
      --text-muted: #475569;
      --text-dim: #94A3B8;
      --shadow-glow: 0 10px 25px rgba(0, 0, 0, 0.05);
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: var(--font-sans);
      background-color: var(--bg);
      color: var(--text-main);
      min-height: 100vh;
      line-height: 1.5;
      background-image: 
        radial-gradient(at 10% 20%, rgba(99, 102, 241, 0.12) 0px, transparent 50%),
        radial-gradient(at 90% 80%, rgba(236, 72, 153, 0.08) 0px, transparent 50%);
      background-attachment: fixed;
      padding-bottom: 60px;
    }}

    .container {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 0 24px;
    }}

    /* Top Navigation Bar */
    header {{
      backdrop-filter: blur(16px);
      background: var(--bg-card);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 16px 0;
    }}

    .nav-content {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
    }}

    .logo-badge {{
      width: 40px;
      height: 40px;
      border-radius: 10px;
      background: var(--primary-gradient);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      color: white;
      font-size: 1.25rem;
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
    }}

    .brand-title {{
      font-size: 1.35rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      background: var(--primary-gradient);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    .brand-version {{
      font-size: 0.75rem;
      padding: 2px 8px;
      background: rgba(99, 102, 241, 0.15);
      border: 1px solid var(--border-accent);
      border-radius: 9999px;
      color: #A5B4FC;
      font-family: var(--font-mono);
      font-weight: 500;
    }}

    .repo-pill {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 6px 14px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border);
      border-radius: 30px;
      font-size: 0.85rem;
      color: var(--text-muted);
    }}

    .repo-path {{
      font-family: var(--font-mono);
      color: var(--text-main);
      max-width: 280px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .branch-badge {{
      background: rgba(16, 185, 129, 0.15);
      color: var(--accent-emerald);
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 2px 10px;
      border-radius: 9999px;
      font-weight: 600;
      font-size: 0.75rem;
      display: flex;
      align-items: center;
      gap: 5px;
    }}

    .header-actions {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .btn {{
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
      text-decoration: none;
      border: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-main);
    }}

    .btn:hover {{
      background: rgba(255, 255, 255, 0.1);
      border-color: var(--primary);
      transform: translateY(-1px);
    }}

    .btn-primary {{
      background: var(--primary-gradient);
      color: white;
      border: none;
      box-shadow: 0 4px 14px rgba(99, 102, 241, 0.3);
    }}

    .btn-primary:hover {{
      box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45);
    }}

    /* Hero Metric Cards */
    .hero-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 20px;
      margin: 32px 0;
    }}

    .metric-card {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 22px;
      backdrop-filter: blur(12px);
      transition: all 0.25s ease;
      position: relative;
      overflow: hidden;
    }}

    .metric-card:hover {{
      border-color: var(--border-accent);
      box-shadow: var(--shadow-glow);
      transform: translateY(-2px);
    }}

    .metric-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: var(--primary-gradient);
      opacity: 0;
      transition: opacity 0.3s;
    }}

    .metric-card:hover::before {{
      opacity: 1;
    }}

    .metric-label {{
      font-size: 0.82rem;
      font-weight: 500;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }}

    .metric-value {{
      font-size: 1.85rem;
      font-weight: 800;
      color: var(--text-main);
      letter-spacing: -0.02em;
      margin-bottom: 4px;
    }}

    .metric-subtitle {{
      font-size: 0.8rem;
      color: var(--text-dim);
    }}

    /* Main Content Sections */
    .analytics-grid {{
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 24px;
      margin-bottom: 32px;
    }}

    @media (max-width: 992px) {{
      .analytics-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    .card {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 24px;
      backdrop-filter: blur(12px);
    }}

    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }}

    .card-title {{
      font-size: 1.15rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    /* Tabbed Navigation */
    .tabs-nav {{
      display: flex;
      gap: 8px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
      overflow-x: auto;
      padding-bottom: 2px;
    }}

    .tab-btn {{
      padding: 10px 18px;
      background: transparent;
      border: none;
      border-bottom: 2px solid transparent;
      color: var(--text-muted);
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
      white-space: nowrap;
    }}

    .tab-btn:hover {{
      color: var(--text-main);
    }}

    .tab-btn.active {{
      color: var(--primary);
      border-bottom-color: var(--primary);
    }}

    .tab-badge {{
      background: rgba(255, 255, 255, 0.08);
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 0.72rem;
      font-family: var(--font-mono);
    }}

    /* Search and Filters Bar */
    .filter-bar {{
      display: flex;
      gap: 12px;
      margin-bottom: 20px;
      flex-wrap: wrap;
    }}

    .search-input {{
      flex: 1;
      min-width: 240px;
      padding: 10px 16px;
      background: rgba(0, 0, 0, 0.2);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text-main);
      font-size: 0.88rem;
      outline: none;
      transition: border-color 0.2s;
    }}

    .search-input:focus {{
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
    }}

    /* Data Tables */
    .table-container {{
      overflow-x: auto;
      border-radius: 8px;
      border: 1px solid var(--border);
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.88rem;
    }}

    th {{
      background: rgba(0, 0, 0, 0.25);
      color: var(--text-muted);
      font-weight: 600;
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
      text-transform: uppercase;
      font-size: 0.74rem;
      letter-spacing: 0.05em;
    }}

    td {{
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
      color: var(--text-main);
    }}

    tr:last-child td {{
      border-bottom: none;
    }}

    tr:hover td {{
      background: rgba(255, 255, 255, 0.02);
    }}

    .path-cell {{
      font-family: var(--font-mono);
      font-size: 0.82rem;
      max-width: 380px;
      word-break: break-all;
    }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      font-family: var(--font-mono);
    }}

    .badge-py {{ background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }}
    .badge-md {{ background: rgba(168, 85, 247, 0.15); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.3); }}
    .badge-toml {{ background: rgba(234, 179, 8, 0.15); color: #FACC15; border: 1px solid rgba(234, 179, 8, 0.3); }}
    .badge-other {{ background: rgba(107, 114, 128, 0.15); color: #9CA3AF; border: 1px solid rgba(107, 114, 128, 0.3); }}
    .badge-deleted {{ background: rgba(244, 63, 94, 0.15); color: #FB7185; border: 1px solid rgba(244, 63, 94, 0.3); }}
    .badge-active {{ background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); }}

    .size-bar-container {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .size-bar {{
      height: 6px;
      border-radius: 3px;
      background: var(--primary-gradient);
      min-width: 4px;
    }}

    /* Storage Distribution Meter */
    .storage-meter {{
      display: flex;
      height: 12px;
      border-radius: 6px;
      overflow: hidden;
      margin: 16px 0;
      background: rgba(255, 255, 255, 0.05);
    }}

    .meter-segment {{
      height: 100%;
      transition: width 0.3s ease;
    }}

    /* Recommendations / Alerts */
    .alert-card {{
      background: rgba(16, 185, 129, 0.08);
      border: 1px solid rgba(16, 185, 129, 0.25);
      border-radius: 10px;
      padding: 16px;
      display: flex;
      align-items: flex-start;
      gap: 14px;
      margin-bottom: 16px;
    }}

    .alert-icon {{
      font-size: 1.4rem;
      line-height: 1;
    }}

    .alert-title {{
      font-weight: 600;
      color: var(--accent-emerald);
      margin-bottom: 4px;
    }}

    .alert-desc {{
      font-size: 0.85rem;
      color: var(--text-muted);
    }}

    /* Footer */
    footer {{
      margin-top: 48px;
      text-align: center;
      font-size: 0.82rem;
      color: var(--text-dim);
    }}
  </style>
</head>
<body>

  <!-- Top Navigation Bar -->
  <header>
    <div class="container nav-content">
      <div style="display: flex; align-items: center; gap: 16px;">
        <a href="#" class="brand">
          <div class="logo-badge">GS</div>
          <div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="brand-title">GitSize</span>
              <span class="brand-version">v{__version__}</span>
            </div>
          </div>
        </a>

        <div class="repo-pill">
          <span>📁</span>
          <span class="repo-path" id="repo-root" title="">Loading repo...</span>
          <div class="branch-badge" id="branch-badge">main</div>
        </div>
      </div>

      <div class="header-actions">
        <button class="btn" id="theme-toggle">🌓 Theme</button>
        <button class="btn" id="export-json-btn">📥 Export JSON</button>
        <button class="btn btn-primary" id="export-md-btn">📄 Export Markdown</button>
      </div>
    </div>
  </header>

  <main class="container">
    <!-- Top Hero Metric Cards -->
    <div class="hero-grid">
      <div class="metric-card">
        <div class="metric-label">Working Tree Storage</div>
        <div class="metric-value" id="stat-wt-size">--</div>
        <div class="metric-subtitle" id="stat-wt-files">0 files actively scanned</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">Git Local Metadata (.git)</div>
        <div class="metric-value" id="stat-git-size">--</div>
        <div class="metric-subtitle">Local commit database & packfiles</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">Historical Blobs</div>
        <div class="metric-value" id="stat-history-size">--</div>
        <div class="metric-subtitle" id="stat-history-count">0 total historical blobs</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">.gitignore Hygiene</div>
        <div class="metric-value" style="color: var(--accent-emerald);" id="stat-ignore-status">Clean</div>
        <div class="metric-subtitle" id="stat-ignore-desc">0 missing ignore rules detected</div>
      </div>
    </div>

    <!-- Storage Distribution Bar -->
    <div class="card" style="margin-bottom: 24px;">
      <div class="card-header">
        <div class="card-title">Storage Breakdown by File Extension</div>
        <span style="font-size: 0.8rem; color: var(--text-dim);" id="ext-summary">Proportional disk usage</span>
      </div>
      <div class="storage-meter" id="storage-meter"></div>
      <div id="storage-legend" style="display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.78rem;"></div>
    </div>

    <!-- Tabbed Explorer View -->
    <div class="card">
      <div class="tabs-nav">
        <button class="tab-btn active" data-tab="files">
          <span>📁 Largest Working Tree Files</span>
          <span class="tab-badge" id="tab-count-files">0</span>
        </button>
        <button class="tab-btn" data-tab="history">
          <span>⏳ Git History Explorer</span>
          <span class="tab-badge" id="tab-count-history">0</span>
        </button>
        <button class="tab-btn" data-tab="types">
          <span>📊 File-Type Analytics</span>
          <span class="tab-badge" id="tab-count-types">0</span>
        </button>
        <button class="tab-btn" data-tab="ignore">
          <span>🛡️ .gitignore Recommendations</span>
          <span class="tab-badge" id="tab-count-ignore">0</span>
        </button>
      </div>

      <!-- Tab 1: Working Tree Files -->
      <div class="tab-pane active" id="pane-files">
        <div class="filter-bar">
          <input type="text" class="search-input" id="search-files" placeholder="Filter files by path or name...">
          <select class="btn" id="filter-ext" style="background: rgba(0,0,0,0.2);">
            <option value="all">All File Types</option>
          </select>
        </div>

        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th style="width: 60px;">Rank</th>
                <th>File Path</th>
                <th style="width: 100px;">Extension</th>
                <th style="width: 130px; text-align: right;">Size</th>
                <th style="width: 180px;">Visual Impact</th>
              </tr>
            </thead>
            <tbody id="files-table-body">
              <tr><td colspan="5" style="text-align: center; color: var(--text-dim);">No files scanned.</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tab 2: Git History Explorer -->
      <div class="tab-pane" id="pane-history" style="display: none;">
        <div class="alert-card" style="background: rgba(99, 102, 241, 0.08); border-color: rgba(99, 102, 241, 0.25);">
          <div class="alert-icon">💡</div>
          <div>
            <div class="alert-title" style="color: var(--primary);">Understanding Git Historical Blobs</div>
            <div class="alert-desc">
              Files that have been deleted from your current working tree (marked as <span class="badge badge-deleted">Deleted in WT</span>)
              still reside permanently in Git history packfiles. Unless history is pruned, these files are downloaded on every <code>git clone</code>.
            </div>
          </div>
        </div>

        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th style="width: 100px;">Blob SHA</th>
                <th>Historical Path</th>
                <th style="width: 120px; text-align: right;">Object Size</th>
                <th>Introducing Commit</th>
                <th style="width: 140px; text-align: center;">Status</th>
              </tr>
            </thead>
            <tbody id="history-table-body">
              <tr><td colspan="5" style="text-align: center; color: var(--text-dim);">No historical blobs found.</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tab 3: File Type Analytics -->
      <div class="tab-pane" id="pane-types" style="display: none;">
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Extension</th>
                <th style="text-align: right;">File Count</th>
                <th style="text-align: right;">Total Storage</th>
                <th style="text-align: right;">% of Working Tree</th>
                <th style="width: 220px;">Distribution</th>
              </tr>
            </thead>
            <tbody id="types-table-body">
              <tr><td colspan="5" style="text-align: center; color: var(--text-dim);">No file types.</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tab 4: .gitignore Audit -->
      <div class="tab-pane" id="pane-ignore" style="display: none;">
        <div id="ignore-content">
          <div class="alert-card">
            <div class="alert-icon">✅</div>
            <div>
              <div class="alert-title">Clean .gitignore Health</div>
              <div class="alert-desc">
                No standard development artifacts (like <code>.env</code>, <code>node_modules/</code>, or <code>__pycache__/</code>)
                are left unignored in this repository.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>

  <footer>
    <div class="container">
      GitSize v{__version__} — Lightweight Git Storage & Repository Analyzer &bull; Built with Python 3 Standard Library
    </div>
  </footer>

  <script>
    // Embedded JSON payload from GitSize scan
    const DATA = {json_payload};

    // Color palette for extensions
    const EXT_COLORS = [
      '#6366F1', '#EC4899', '#06B6D4', '#10B981', '#F59E0B', 
      '#8B5CF6', '#3B82F6', '#14B8A6', '#F97316', '#64748B'
    ];

    function initDashboard() {{
      const repo = DATA.repository || {{}};
      const wt = DATA.working_tree || {{}};
      const history = DATA.history || {{}};
      const recs = DATA.ignore_recommendations || [];

      // Top repo pills
      document.getElementById('repo-root').textContent = repo.root_path || 'Repository';
      document.getElementById('repo-root').title = repo.root_path || '';
      document.getElementById('branch-badge').textContent = repo.current_branch || 'main';

      // Hero Metrics
      document.getElementById('stat-wt-size').textContent = wt.formatted_total_size || '0 B';
      document.getElementById('stat-wt-files').textContent = `${{wt.total_files || 0}} files actively scanned`;
      document.getElementById('stat-git-size').textContent = repo.formatted_git_dir_size || '0 B';
      document.getElementById('stat-history-size').textContent = history.formatted_total_size || '0 B';
      document.getElementById('stat-history-count').textContent = `${{history.total_blobs_found || 0}} historical blobs tracked`;

      // .gitignore Status
      if (recs.length > 0) {{
        document.getElementById('stat-ignore-status').textContent = `${{recs.length}} Warnings`;
        document.getElementById('stat-ignore-status').style.color = 'var(--accent-amber)';
        document.getElementById('stat-ignore-desc').textContent = 'Recommended patterns missing from .gitignore';
      }} else {{
        document.getElementById('stat-ignore-status').textContent = 'Clean (100%)';
        document.getElementById('stat-ignore-status').style.color = 'var(--accent-emerald)';
        document.getElementById('stat-ignore-desc').textContent = 'No standard unignored artifacts detected';
      }}

      // Badges
      document.getElementById('tab-count-files').textContent = wt.largest_files?.length || 0;
      document.getElementById('tab-count-history').textContent = history.top_blobs?.length || 0;
      document.getElementById('tab-count-types').textContent = wt.file_type_breakdown?.length || 0;
      document.getElementById('tab-count-ignore').textContent = recs.length;

      renderStorageMeter(wt.file_type_breakdown || []);
      renderFilesTable(wt.largest_files || []);
      renderHistoryTable(history.top_blobs || []);
      renderTypesTable(wt.file_type_breakdown || []);
      renderIgnoreTab(recs);
      populateExtFilter(wt.file_type_breakdown || []);
    }}

    function renderStorageMeter(types) {{
      const meter = document.getElementById('storage-meter');
      const legend = document.getElementById('storage-legend');
      meter.innerHTML = '';
      legend.innerHTML = '';

      if (!types.length) return;

      types.slice(0, 8).forEach((t, i) => {{
        const color = EXT_COLORS[i % EXT_COLORS.length];
        
        // Segment
        const seg = document.createElement('div');
        seg.className = 'meter-segment';
        seg.style.width = `${{t.percentage}}%`;
        seg.style.backgroundColor = color;
        seg.title = `${{t.extension}}: ${{t.formatted_size}} (${{t.percentage}}%)`;
        meter.appendChild(seg);

        // Legend
        const leg = document.createElement('div');
        leg.style.display = 'flex';
        leg.style.alignItems = 'center';
        leg.style.gap = '6px';
        leg.innerHTML = `<span style="width: 8px; height: 8px; border-radius: 50%; background:${{color}};"></span>
                         <span style="font-weight:600;">${{t.extension}}</span>
                         <span style="color:var(--text-dim);">${{t.formatted_size}} (${{t.percentage}}%)</span>`;
        legend.appendChild(leg);
      }});
    }}

    function renderFilesTable(files) {{
      const tbody = document.getElementById('files-table-body');
      tbody.innerHTML = '';

      if (!files.length) {{
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-dim);">No files scanned.</td></tr>';
        return;
      }}

      const maxSize = files[0]?.size_bytes || 1;

      files.forEach((f, idx) => {{
        const tr = document.createElement('tr');
        const pct = Math.max(4, Math.round((f.size_bytes / maxSize) * 100));

        let badgeClass = 'badge-other';
        if (f.extension === '.py') badgeClass = 'badge-py';
        else if (f.extension === '.md') badgeClass = 'badge-md';
        else if (f.extension === '.toml') badgeClass = 'badge-toml';

        tr.innerHTML = `
          <td style="color: var(--text-dim); font-weight: 600;">#${{idx + 1}}</td>
          <td class="path-cell">${{escapeHtml(f.relative_path)}}</td>
          <td><span class="badge ${{badgeClass}}">${{escapeHtml(f.extension)}}</span></td>
          <td style="text-align: right; font-weight: 600; font-family: var(--font-mono);">${{f.formatted_size}}</td>
          <td>
            <div class="size-bar-container">
              <div class="size-bar" style="width: ${{pct}}%;"></div>
              <span style="font-size: 0.72rem; color: var(--text-dim);">${{f.size_bytes.toLocaleString()}} B</span>
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    function renderHistoryTable(blobs) {{
      const tbody = document.getElementById('history-table-body');
      tbody.innerHTML = '';

      if (!blobs.length) {{
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-dim);">No historical Git blobs found.</td></tr>';
        return;
      }}

      blobs.forEach(b => {{
        const tr = document.createElement('tr');
        const statusBadge = b.is_deleted_in_working_tree
          ? '<span class="badge badge-deleted">Deleted in WT</span>'
          : '<span class="badge badge-active">Active in WT</span>';

        tr.innerHTML = `
          <td><code style="color: #A5B4FC;">${{b.short_hash}}</code></td>
          <td class="path-cell">${{escapeHtml(b.path)}}</td>
          <td style="text-align: right; font-weight: 600; font-family: var(--font-mono);">${{b.formatted_size}}</td>
          <td style="font-size: 0.8rem; color: var(--text-muted);">${{escapeHtml(b.commit_ref || 'N/A')}}</td>
          <td style="text-align: center;">${{statusBadge}}</td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    function renderTypesTable(types) {{
      const tbody = document.getElementById('types-table-body');
      tbody.innerHTML = '';

      if (!types.length) {{
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-dim);">No extensions recorded.</td></tr>';
        return;
      }}

      types.forEach((t, i) => {{
        const tr = document.createElement('tr');
        const color = EXT_COLORS[i % EXT_COLORS.length];
        tr.innerHTML = `
          <td style="font-weight: 600;"><span class="badge badge-other">${{escapeHtml(t.extension)}}</span></td>
          <td style="text-align: right; font-family: var(--font-mono);">${{t.count.toLocaleString()}}</td>
          <td style="text-align: right; font-weight: 600; font-family: var(--font-mono);">${{t.formatted_size}}</td>
          <td style="text-align: right; font-family: var(--font-mono);">${{t.percentage}}%</td>
          <td>
            <div class="size-bar" style="width: ${{t.percentage}}%; background: ${{color}};"></div>
          </td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    function renderIgnoreTab(recs) {{
      const container = document.getElementById('ignore-content');
      if (!recs.length) return;

      container.innerHTML = `
        <div class="alert-card" style="background: rgba(245, 158, 11, 0.08); border-color: rgba(245, 158, 11, 0.25);">
          <div class="alert-icon">⚠️</div>
          <div>
            <div class="alert-title" style="color: var(--accent-amber);">Oversized or Sensitive Artifacts Detected</div>
            <div class="alert-desc">
              The following paths exist on disk but are not covered by <code>.gitignore</code>. Consider adding them to prevent accidental commits.
            </div>
          </div>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Suggested Pattern</th>
                <th>Category</th>
                <th>Detected Location</th>
                <th>Unignored Size</th>
                <th>Recommendation Reason</th>
              </tr>
            </thead>
            <tbody>
              ${{recs.map(r => `
                <tr>
                  <td><code style="color: var(--accent-amber); font-weight: bold;">${{escapeHtml(r.suggested_pattern)}}</code></td>
                  <td>${{escapeHtml(r.category)}}</td>
                  <td class="path-cell">${{escapeHtml(r.detected_path)}}</td>
                  <td style="font-family: var(--font-mono); font-weight: 600;">${{r.formatted_size}}</td>
                  <td style="font-size: 0.82rem; color: var(--text-muted);">${{escapeHtml(r.reason)}}</td>
                </tr>
              `).join('')}}
            </tbody>
          </table>
        </div>
      `;
    }}

    function populateExtFilter(types) {{
      const select = document.getElementById('filter-ext');
      types.forEach(t => {{
        const opt = document.createElement('option');
        opt.value = t.extension;
        opt.textContent = `${{t.extension}} (${{t.count}})`;
        select.appendChild(opt);
      }});
    }}

    // Tab switching logic
    document.querySelectorAll('.tab-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const tab = btn.dataset.tab;
        document.getElementById('pane-files').style.display = tab === 'files' ? 'block' : 'none';
        document.getElementById('pane-history').style.display = tab === 'history' ? 'block' : 'none';
        document.getElementById('pane-types').style.display = tab === 'types' ? 'block' : 'none';
        document.getElementById('pane-ignore').style.display = tab === 'ignore' ? 'block' : 'none';
      }});
    }});

    // Live search & extension filtering
    function filterFiles() {{
      const query = document.getElementById('search-files').value.toLowerCase();
      const ext = document.getElementById('filter-ext').value;
      const allFiles = DATA.working_tree?.largest_files || [];

      const filtered = allFiles.filter(f => {{
        const matchesQuery = f.relative_path.toLowerCase().includes(query);
        const matchesExt = (ext === 'all') || (f.extension === ext);
        return matchesQuery && matchesExt;
      }});

      renderFilesTable(filtered);
    }}

    document.getElementById('search-files').addEventListener('input', filterFiles);
    document.getElementById('filter-ext').addEventListener('change', filterFiles);

    // Theme toggle
    document.getElementById('theme-toggle').addEventListener('click', () => {{
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', next);
    }});

    // Download handlers
    document.getElementById('export-json-btn').addEventListener('click', () => {{
      const blob = new Blob([JSON.stringify(DATA, null, 2)], {{ type: 'application/json' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'gitsize-report.json';
      a.click();
      URL.revokeObjectURL(url);
    }});

    document.getElementById('export-md-btn').addEventListener('click', () => {{
      window.open('report.md', '_blank');
    }});

    function escapeHtml(str) {{
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }}

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', initDashboard);
  </script>
</body>
</html>
"""


class GitSizeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Custom request handler that serves the generated dashboard on root request."""

    dashboard_html: str = ""

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            content = self.dashboard_html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            super().do_GET()

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy HTTP request console logging
        pass


def start_local_dashboard_server(
    data: dict[str, Any],
    port: int = 8080,
    open_browser: bool = True,
) -> tuple[HTTPServer, str]:
    """Start a lightweight background HTTP server and open the dashboard in browser.

    Args:
        data: Structured JSON report dictionary.
        port: Starting TCP port to bind.
        open_browser: Whether to trigger system browser launch.

    Returns:
        Tuple of (HTTPServer instance, url string).
    """
    html_content = generate_dashboard_html(data)

    class CustomHandler(GitSizeHTTPRequestHandler):
        dashboard_html = html_content

    server: HTTPServer | None = None
    actual_port = port
    for p in range(port, port + 20):
        try:
            server = HTTPServer(("127.0.0.1", p), CustomHandler)
            actual_port = p
            break
        except OSError:
            continue

    if server is None:
        raise OSError(f"Could not bind to any TCP port between {port} and {port + 20}.")

    url = f"http://127.0.0.1:{actual_port}/"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    if open_browser:
        webbrowser.open(url)

    return server, url
