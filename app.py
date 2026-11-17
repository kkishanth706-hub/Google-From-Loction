"""
Location-restricted form (100 m radius) using Flask.
Run:  pip install flask
      python app.py
NOTE: Phones only give GPS to HTTPS pages. Deploy with HTTPS
      (PythonAnywhere / Render / ngrok) for real use.
"""
import csv
import os
from datetime import datetime
from math import radians, sin, cos, asin, sqrt

from flask import Flask, request, jsonify, render_template_string

# ---------- CHANGE THESE ----------
TARGET_LAT = 11.0168      # latitude of the allowed place
TARGET_LON = 76.9558      # longitude of the allowed place
RADIUS_M = 100            # allowed radius in metres
MAX_ACCURACY_M = 50       # reject if GPS accuracy is worse than this
CSV_FILE = "responses.csv"
# ----------------------------------

app = Flask(__name__)


def haversine_m(lat1, lon1, lat2, lon2):
    """Distance in metres between two lat/lon points."""
    R = 6371000
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * R * asin(sqrt(a))


PAGE = """
<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Attendance Form</title>
<style>
 body{font-family:Arial;max-width:420px;margin:30px auto;padding:0 16px}
 input,button{width:100%;padding:10px;margin:6px 0;font-size:16px;box-sizing:border-box}
 button{background:#1a73e8;color:#fff;border:0;border-radius:6px}
 #msg{margin-top:12px;font-weight:bold}
</style></head><body>
<h2>Attendance Form</h2>
<input id="name" placeholder="Name" required>
<input id="regno" placeholder="Register No / Email" required>
<button onclick="submitForm()">Submit</button>
<div id="msg"></div>
<script>
function submitForm(){
  const name=document.getElementById('name').value.trim();
  const regno=document.getElementById('regno').value.trim();
  const msg=document.getElementById('msg');
  if(!name||!regno){msg.textContent='Fill all fields';return;}
  msg.textContent='Getting your location...';
  if(!navigator.geolocation){msg.textContent='Geolocation not supported';return;}
  navigator.geolocation.getCurrentPosition(async pos=>{
    const r=await fetch('/submit',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name,regno,
        lat:pos.coords.latitude,lon:pos.coords.longitude,
        accuracy:pos.coords.accuracy})});
    const d=await r.json();
    msg.style.color=d.ok?'green':'red';
    msg.textContent=d.message;
  },err=>{msg.style.color='red';msg.textContent='Location permission denied / unavailable';},
  {enableHighAccuracy:true,timeout:15000,maximumAge:0});
}
</script></body></html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/submit", methods=["POST"])
def submit():
    d = request.get_json(force=True)
    try:
        lat, lon = float(d["lat"]), float(d["lon"])
        acc = float(d.get("accuracy", 0))
    except (KeyError, ValueError):
        return jsonify(ok=False, message="Invalid location data")

    if acc > MAX_ACCURACY_M:
        return jsonify(ok=False,
                       message=f"GPS accuracy too low ({acc:.0f} m). Move outdoors and retry.")

    dist = haversine_m(lat, lon, TARGET_LAT, TARGET_LON)
    if dist > RADIUS_M:
        return jsonify(ok=False,
                       message=f"You are {dist:.0f} m away. Must be within {RADIUS_M} m.")

    new_file = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["time", "name", "regno", "lat", "lon", "distance_m"])
        w.writerow([datetime.now().isoformat(timespec="seconds"),
                    d.get("name"), d.get("regno"), lat, lon, round(dist, 1)])
    return jsonify(ok=True, message=f"Submitted ✔ (distance {dist:.0f} m)")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
