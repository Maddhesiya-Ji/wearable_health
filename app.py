from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
DB_PATH = Path(__file__).with_name("health_data.sqlite3")

PAGE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Wearable Health Monitor</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#f3f7f7;color:#19343d;font:15px Arial,sans-serif}
header{background:#fff;border-bottom:1px solid #e1e9e9;padding:18px max(calc((100% - 1050px)/2),22px);display:flex;justify-content:space-between;align-items:center}
header strong{font-size:20px;color:#087f73}
main{max-width:1050px;margin:35px auto;padding:0 20px}
h1{margin-bottom:5px}.muted{color:#71838a}
.notice{padding:13px 15px;background:#fff5dc;border:1px solid #f0dfa9;border-radius:10px;margin:22px 0;display:flex;gap:12px;align-items:center}
.notice span{flex:1}.notice b{color:#98700c}
button{border:0;border-radius:8px;padding:10px 14px;background:#0c8d7e;color:#fff;font-weight:bold;cursor:pointer}
button:disabled{opacity:.6}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.card,.panel{background:white;border:1px solid #e1e9e9;border-radius:12px;padding:18px;box-shadow:0 3px 12px #19343d0a}
.card label{color:#71838a}.value{font-size:30px;font-weight:bold;margin:13px 0}.unit{font-size:13px;color:#71838a;font-weight:normal}
.panel{margin-top:16px}.panel h2{font-size:17px;margin:0 0 5px}
canvas{width:100%;height:210px}.table-wrap{overflow:auto}
table{width:100%;border-collapse:collapse;min-width:580px;margin-top:12px}
th,td{text-align:left;padding:11px 8px;border-bottom:1px solid #edf1f1;font-size:13px}
th{font-size:11px;color:#819196}
#connection{font-size:13px;color:#087f73}
footer{text-align:center;color:#8c9a9e;font-size:12px;padding:24px}
@media(max-width:750px){.cards{grid-template-columns:repeat(2,1fr)}.notice{flex-wrap:wrap}}
@media(max-width:430px){main{margin-top:22px}.cards{gap:8px}.card{padding:13px}.value{font-size:24px}}
</style>
</head>
<body>
<header><strong>＋ PulseTrack</strong><span id="connection">Connecting…</span></header>
<main>
  <h1>Your health, at a glance</h1>
  <div class="muted">Smart Wearable Health Monitoring System</div>
  <div class="notice">
    <b>DEMO MODE</b>
    <span>Demo readings are simulated. This student prototype is not a medical device.</span>
    <button id="demo">Start demo readings</button>
  </div>
  <section class="cards">
    <div class="card"><label>Heart rate</label><div class="value"><span id="hr">--</span> <span class="unit">bpm</span></div></div>
    <div class="card"><label>Blood oxygen (SpO₂)</label><div class="value"><span id="spo2">--</span><span class="unit"> %</span></div></div>
    <div class="card"><label>Temperature</label><div class="value"><span id="temp">--</span><span class="unit"> °C</span></div></div>
    <div class="card"><label>Steps</label><div class="value"><span id="steps">--</span></div></div>
  </section>
  <section class="panel">
    <h2>Recent heart rate</h2><div class="muted">Latest stored readings</div>
    <canvas id="chart"></canvas>
  </section>
  <section class="panel">
    <h2>Latest readings</h2><div class="muted">Saved in the local SQLite database</div>
    <div class="table-wrap"><table>
      <thead><tr><th>TIME</th><th>DEVICE</th><th>HEART RATE</th><th>SpO₂</th><th>TEMP</th><th>STEPS</th></tr></thead>
      <tbody id="rows"><tr><td colspan="6">No readings yet.</td></tr></tbody>
    </table></div>
  </section>
  <footer>Educational project prototype · Readings are not for diagnosis or treatment</footer>
</main>
<script>
const byId = id => document.getElementById(id);
let latestReadings = [];
let demoTimer = null;
let demoSteps = 1000;

async function refresh() {
  try {
    const response = await fetch("/api/readings");
    if (!response.ok) throw new Error("Backend error");
    latestReadings = await response.json();
    byId("connection").textContent = "Backend connected";
    render();
  } catch {
    byId("connection").textContent = "Backend unavailable";
  }
}

function render() {
  const r = latestReadings[latestReadings.length - 1];
  if (r) {
    byId("hr").textContent = Math.round(r.heart_rate);
    byId("spo2").textContent = Number(r.spo2).toFixed(1);
    byId("temp").textContent = Number(r.temperature).toFixed(1);
    byId("steps").textContent = Number(r.steps).toLocaleString();
  }
  const rows = [...latestReadings].reverse().slice(0, 10);
  byId("rows").innerHTML = rows.length ? rows.map(x => `
    <tr>
      <td>${new Date(x.created_at).toLocaleTimeString()}</td>
      <td>${escapeHtml(x.device_id)}</td>
      <td>${Number(x.heart_rate).toFixed(0)} bpm</td>
      <td>${Number(x.spo2).toFixed(1)}%</td>
      <td>${Number(x.temperature).toFixed(1)} °C</td>
      <td>${Number(x.steps).toLocaleString()}</td>
    </tr>`).join("") : '<tr><td colspan="6">No readings yet.</td></tr>';
  drawChart();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function drawChart() {
  const canvas = byId("chart");
  const box = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = box.width * ratio;
  canvas.height = 210 * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  const values = latestReadings.slice(-30).map(r => Number(r.heart_rate));
  const width = box.width, height = 210, left = 34, right = 12, top = 15, bottom = 20;
  ctx.font = "11px Arial";
  ctx.strokeStyle = "#e8eeee";
  ctx.fillStyle = "#7c8d92";
  [50, 70, 90, 110, 130].forEach(v => {
    const y = top + (130 - v) / 80 * (height - top - bottom);
    ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(width - right, y); ctx.stroke();
    ctx.fillText(v, 5, y + 4);
  });
  if (values.length < 2) return;
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = left + i * (width - left - right) / (values.length - 1);
    const y = top + (130 - v) / 80 * (height - top - bottom);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.strokeStyle = "#0c9b88"; ctx.lineWidth = 2.5; ctx.stroke();
}

async function sendReading(reading) {
  const response = await fetch("/api/readings", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(reading)
  });
  if (!response.ok) throw new Error(await response.text());
  await refresh();
}

byId("demo").addEventListener("click", () => {
  if (demoTimer) {
    clearInterval(demoTimer);
    demoTimer = null;
    byId("demo").textContent = "Start demo readings";
    return;
  }
  byId("demo").textContent = "Stop demo readings";
  const sendDemo = () => {
    demoSteps += Math.floor(Math.random() * 5);
    sendReading({
      device_id: "browser-demo",
      heart_rate: +(72 + Math.random() * 18).toFixed(1),
      spo2: +(96 + Math.random() * 3).toFixed(1),
      temperature: +(36.4 + Math.random() * 0.8).toFixed(1),
      steps: demoSteps
    }).catch(console.error);
  };
  sendDemo();
  demoTimer = setInterval(sendDemo, 3000);
});

window.addEventListener("resize", drawChart);
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""

def connect_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                heart_rate REAL NOT NULL,
                spo2 REAL NOT NULL,
                temperature REAL NOT NULL,
                steps INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

@app.get("/")
def dashboard():
    return render_template_string(PAGE)

@app.get("/api/health")
def health():
    return jsonify(status="ok", message="Health monitoring backend is running")

@app.get("/api/readings")
def get_readings():
    with connect_db() as db:
        rows = db.execute(
            "SELECT * FROM readings ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return jsonify([dict(row) for row in reversed(rows)])

@app.post("/api/readings")
def add_reading():
    data = request.get_json(silent=True) or {}
    try:
        heart_rate = float(data["heart_rate"])
        spo2 = float(data["spo2"])
        temperature = float(data["temperature"])
        steps = int(data.get("steps", 0))
        device_id = str(data.get("device_id", "wearable"))[:64]

        if not 20 <= heart_rate <= 250:
            raise ValueError("heart_rate must be between 20 and 250")
        if not 50 <= spo2 <= 100:
            raise ValueError("spo2 must be between 50 and 100")
        if not 25 <= temperature <= 45:
            raise ValueError("temperature must be between 25 and 45")
        if not 0 <= steps <= 2_000_000:
            raise ValueError("steps must be between 0 and 2,000,000")
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify(error=str(exc)), 400

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect_db() as db:
        cursor = db.execute(
            """INSERT INTO readings
               (device_id, heart_rate, spo2, temperature, steps, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (device_id, heart_rate, spo2, temperature, steps, created_at),
        )
      
        row = db.execute(
            "SELECT * FROM readings WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return jsonify(dict(row)), 201

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)