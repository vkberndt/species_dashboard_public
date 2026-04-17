import os
import psycopg2
import psycopg2.extras
from flask import Flask, render_template_string, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
DATABASE_URL = os.environ["DATABASE_URL"]


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def load_species_data(days):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT species, COUNT(*) AS count
                FROM public.species_logins
                WHERE ts >= NOW() - make_interval(days := %s)
                GROUP BY species
                ORDER BY count DESC
            """, (days,))
            return cur.fetchall()


def load_diet_data(days):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT d.diet, SUM(l.cnt) AS total
                FROM (
                    SELECT species, COUNT(*) AS cnt
                    FROM public.species_logins
                    WHERE ts >= NOW() - make_interval(days := %s)
                    GROUP BY species
                ) l
                JOIN public.species_diets d ON l.species = d.species
                GROUP BY d.diet
                ORDER BY total DESC
            """, (days,))
            return cur.fetchall()


def load_top_by_diet(days, diet, limit=5):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT l.species, COUNT(*) AS count
                FROM public.species_logins l
                JOIN public.species_diets d ON l.species = d.species
                WHERE l.ts >= NOW() - make_interval(days := %s)
                  AND d.diet = %s
                GROUP BY l.species
                ORDER BY count DESC
                LIMIT %s
            """, (days, diet, limit))
            return cur.fetchall()


TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Species Dashboard</title>
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700;900&family=Raleway:wght@300;400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <style>
    :root {
      --bg:        #0e0e0f;
      --surface:   #181819;
      --surface2:  #1f1f21;
      --border:    #2e2e32;
      --amber:     #c8852a;
      --amber-lt:  #e8a84a;
      --bone:      #d6ccb4;
      --muted:     #6b6b72;
      --text:      #e8e4d8;
      --carni:     #c0392b;
      --herbi:     #27ae60;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Raleway', sans-serif;
      font-weight: 400;
      min-height: 100vh;
    }

    body::before {
      content: '';
      position: fixed;
      inset: 0;
      background-image: repeating-linear-gradient(
        0deg, transparent, transparent 2px,
        rgba(255,255,255,0.012) 2px, rgba(255,255,255,0.012) 4px
      );
      pointer-events: none;
      z-index: 0;
    }

    .wrap { position: relative; z-index: 1; max-width: 1100px; margin: 0 auto; padding: 48px 24px 80px; }

    header { margin-bottom: 48px; }
    .header-eyebrow {
      font-size: 11px; font-weight: 600; letter-spacing: 0.25em;
      text-transform: uppercase; color: var(--amber); margin-bottom: 10px;
    }
    h1 {
      font-family: 'Cinzel', serif;
      font-size: clamp(2rem, 5vw, 3.2rem);
      font-weight: 900; color: var(--bone); line-height: 1.1;
      letter-spacing: 0.04em;
      text-shadow: 0 0 40px rgba(200,133,42,0.25);
    }
    h1 span { color: var(--amber-lt); }
    .header-rule {
      margin-top: 18px; height: 1px;
      background: linear-gradient(90deg, var(--amber) 0%, transparent 60%);
    }

    .filter-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 40px; }
    .filter-bar label {
      font-size: 12px; font-weight: 600; letter-spacing: 0.15em;
      text-transform: uppercase; color: var(--muted);
    }
    .filter-bar select {
      background: var(--surface2); color: var(--text);
      border: 1px solid var(--border); border-radius: 4px;
      padding: 8px 14px; font-family: 'Raleway', sans-serif;
      font-size: 14px; font-weight: 500; cursor: pointer;
      outline: none; transition: border-color 0.2s;
    }
    .filter-bar select:hover, .filter-bar select:focus { border-color: var(--amber); }
    .filter-bar button {
      background: var(--amber); color: #0e0e0f; border: none; border-radius: 4px;
      padding: 8px 20px; font-family: 'Raleway', sans-serif;
      font-size: 13px; font-weight: 700; letter-spacing: 0.08em;
      text-transform: uppercase; cursor: pointer; transition: background 0.2s;
    }
    .filter-bar button:hover { background: var(--amber-lt); }

    .stats-row {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 16px; margin-bottom: 40px;
    }
    .stat-card {
      background: var(--surface); border: 1px solid var(--border);
      border-top: 2px solid var(--amber); padding: 20px; border-radius: 4px;
    }
    .stat-label {
      font-size: 10px; font-weight: 600; letter-spacing: 0.2em;
      text-transform: uppercase; color: var(--muted); margin-bottom: 8px;
    }
    .stat-value {
      font-family: 'Cinzel', serif; font-size: 2rem;
      font-weight: 700; color: var(--amber-lt); line-height: 1;
    }

    .card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 4px; padding: 28px; margin-bottom: 24px;
    }
    .card-title {
      font-family: 'Cinzel', serif; font-size: 13px; font-weight: 700;
      letter-spacing: 0.12em; text-transform: uppercase; color: var(--amber);
      margin-bottom: 24px; padding-bottom: 12px; border-bottom: 1px solid var(--border);
    }

    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
    @media (max-width: 700px) { .grid-2 { grid-template-columns: 1fr; } }

    .leaderboard-item {
      display: flex; align-items: center; gap: 14px;
      padding: 10px 0; border-bottom: 1px solid var(--border);
    }
    .leaderboard-item:last-child { border-bottom: none; }
    .lb-rank { font-family: 'Cinzel', serif; font-size: 11px; font-weight: 700; color: var(--muted); width: 20px; flex-shrink: 0; }
    .lb-bar-wrap { flex: 1; position: relative; height: 4px; background: var(--surface2); border-radius: 2px; }
    .lb-bar { height: 100%; border-radius: 2px; transition: width 0.6s ease; }
    .lb-bar.herbi { background: var(--herbi); }
    .lb-bar.carni { background: var(--carni); }
    .lb-name { font-size: 13px; font-weight: 500; color: var(--text); min-width: 120px; }
    .lb-count { font-family: 'Cinzel', serif; font-size: 13px; font-weight: 700; color: var(--amber-lt); text-align: right; min-width: 40px; }

    .empty { text-align: center; padding: 60px 20px; color: var(--muted); font-size: 14px; letter-spacing: 0.05em; }
    .empty strong { display: block; font-family: 'Cinzel', serif; font-size: 18px; color: var(--border); margin-bottom: 8px; }

    canvas { max-height: 340px; }
  </style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="header-eyebrow">Path of Titans — Server Analytics</div>
    <h1>Species <span>Dashboard</span></h1>
    <div class="header-rule"></div>
  </header>

  <form class="filter-bar" method="get" action="/">
    <label for="days">Time range</label>
    <select name="days" id="days">
      {% for opt in [1, 3, 7, 14, 30] %}
      <option value="{{ opt }}" {% if opt == days %}selected{% endif %}>
        Last {{ opt }} day{% if opt != 1 %}s{% endif %}
      </option>
      {% endfor %}
    </select>
    <button type="submit">Apply</button>
  </form>

  {% if not species_data %}
  <div class="empty">
    <strong>No Data Yet</strong>
    Waiting for players to spawn on the server.
  </div>
  {% else %}

  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-label">Total Spawns</div>
      <div class="stat-value">{{ total_spawns }}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Unique Species</div>
      <div class="stat-value">{{ species_data | length }}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Carnivore Spawns</div>
      <div class="stat-value" style="color: var(--carni);">{{ carni_total }}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Herbivore Spawns</div>
      <div class="stat-value" style="color: var(--herbi);">{{ herbi_total }}</div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Species Distribution</div>
    <canvas id="speciesChart"></canvas>
  </div>

  <div class="grid-2">
    <div class="card">
      <div class="card-title">🥦 Top Herbivores</div>
      {% if top_herbi %}
        {% set max_h = top_herbi[0].count %}
        {% for row in top_herbi %}
        <div class="leaderboard-item">
          <div class="lb-rank">#{{ loop.index }}</div>
          <div style="flex:1">
            <div class="lb-name">{{ row.species }}</div>
            <div class="lb-bar-wrap">
              <div class="lb-bar herbi" style="width: {{ (row.count / max_h * 100)|int }}%"></div>
            </div>
          </div>
          <div class="lb-count">{{ row.count }}</div>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty"><strong>—</strong>No herbivore data.</div>
      {% endif %}
    </div>

    <div class="card">
      <div class="card-title">🍖 Top Carnivores</div>
      {% if top_carni %}
        {% set max_c = top_carni[0].count %}
        {% for row in top_carni %}
        <div class="leaderboard-item">
          <div class="lb-rank">#{{ loop.index }}</div>
          <div style="flex:1">
            <div class="lb-name">{{ row.species }}</div>
            <div class="lb-bar-wrap">
              <div class="lb-bar carni" style="width: {{ (row.count / max_c * 100)|int }}%"></div>
            </div>
          </div>
          <div class="lb-count">{{ row.count }}</div>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty"><strong>—</strong>No carnivore data.</div>
      {% endif %}
    </div>
  </div>

  <div class="card" style="max-width: 480px; margin: 0 auto;">
    <div class="card-title">Carnivores vs Herbivores</div>
    <canvas id="dietChart"></canvas>
  </div>

  <script>
    const speciesCtx = document.getElementById('speciesChart').getContext('2d');
    new Chart(speciesCtx, {
      type: 'bar',
      data: {
        labels: {{ species_labels | tojson }},
        datasets: [{
          data: {{ species_counts | tojson }},
          backgroundColor: '#c8852a',
          borderColor: '#e8a84a',
          borderWidth: 1,
          borderRadius: 2,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            ticks: { color: '#6b6b72', font: { family: 'Raleway', size: 11 }, maxRotation: 45 },
            grid: { color: '#2e2e32' }
          },
          y: {
            ticks: { color: '#6b6b72', font: { family: 'Raleway', size: 11 } },
            grid: { color: '#2e2e32' }
          }
        }
      }
    });

    const dietCtx = document.getElementById('dietChart').getContext('2d');
    new Chart(dietCtx, {
      type: 'doughnut',
      data: {
        labels: {{ diet_labels | tojson }},
        datasets: [{
          data: {{ diet_counts | tojson }},
          backgroundColor: ['#c0392b', '#27ae60'],
          borderColor: '#181819',
          borderWidth: 3,
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            labels: { color: '#e8e4d8', font: { family: 'Raleway', size: 13 }, padding: 20 }
          }
        },
        cutout: '60%'
      }
    });
  </script>
  {% endif %}

</div>
</body>
</html>
"""


@app.route("/")
def index():
    days = int(request.args.get("days", 7))
    try:
        species_data = load_species_data(days)
        diet_data    = load_diet_data(days)
        top_herbi    = load_top_by_diet(days, "herbivore")
        top_carni    = load_top_by_diet(days, "carnivore")
    except Exception as e:
        print(f"[ERROR] Database query failed: {e}")
        species_data, diet_data, top_herbi, top_carni = [], [], [], []

    total_spawns  = sum(r["count"] for r in species_data)
    carni_total   = next((r["total"] for r in diet_data if r["diet"] == "carnivore"), 0)
    herbi_total   = next((r["total"] for r in diet_data if r["diet"] == "herbivore"), 0)
    species_labels = [r["species"] for r in species_data]
    species_counts = [r["count"]   for r in species_data]
    diet_labels    = [r["diet"].capitalize() for r in diet_data]
    diet_counts    = [r["total"]   for r in diet_data]

    return render_template_string(
        TEMPLATE,
        days=days,
        species_data=species_data,
        top_herbi=top_herbi,
        top_carni=top_carni,
        total_spawns=total_spawns,
        carni_total=carni_total,
        herbi_total=herbi_total,
        species_labels=species_labels,
        species_counts=species_counts,
        diet_labels=diet_labels,
        diet_counts=diet_counts,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
