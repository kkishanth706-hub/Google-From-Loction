import os
import urllib.parse
import urllib.request
from math import radians, sin, cos, asin, sqrt

from flask import Flask, request, jsonify, render_template_string

# ---------- LOCATION SETTINGS ----------
TARGET_LAT = 10.937290 
TARGET_LON = 76.958365 
RADIUS_M = 100            # allowed radius in metres
MAX_ACCURACY_M = 100      # reject if GPS accuracy is worse than this
# ---------------------------------------

# ---------- GOOGLE FORM (kept on the server, never sent to the browser) ----------
# Set these in Vercel -> Settings -> Environment Variables (recommended),
# or type them directly between the quotes below.
FORM_POST_URL = os.environ.get("FORM_POST_URL", "https://forms.gle/r4wBRdXKa5ZVk4yN6")       # .../forms/d/e/<ID>/formResponse
ENTRY_NAME = os.environ.get("ENTRY_NAME", "")             # e.g. entry.1234567890
ENTRY_REGNO = os.environ.get("ENTRY_REGNO", "")           # e.g. entry.2345678901
ENTRY_LOCATION = os.environ.get("ENTRY_LOCATION", "")     # optional, leave empty to skip
# --------------------------------------------------------------------------------

app = Flask(__name__)


def haversine_m(lat1, lon1, lat2, lon2):
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
 button:disabled{background:#999}
 #msg{margin-top:12px;font-weight:bold}
</style></head><body>
<h2>Attendance Form</h2>
<input id="name" placeholder="Name">
<input id="regno" placeholder="Register No">
<button id="btn" onclick="submitForm()">Submit</button>
<div id="msg"></div>
<script>
function submitForm(){
  const name=document.getElementById('name').value.trim();
  const regno=document.getElementById('regno').value.trim();
  const msg=document.getElementById('msg');
  const btn=document.getElementById('btn');
  msg.style.color='black';
  if(!name||!regno){msg.style.color='red';msg.textContent='Fill all fields';return;}
  if(!navigator.geolocation){msg.style.color='red';msg.textContent='Geolocation not supported';return;}
  btn.disabled=true;
  msg.textContent='Getting your location...';
  let best=null, done=false;

  async function finish(){
    if(done||!best) return;
    done=true;
    navigator.geolocation.clearWatch(watchId);
    clearTimeout(timer);
    try{
      const r=await fetch('/submit',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name,regno,
          lat:best.coords.latitude,lon:best.coords.longitude,
          accuracy:best.coords.accuracy})});
      const d=await r.json();
      msg.style.color=d.ok?'green':'red';
      msg.textContent=d.message;
      if(d.ok) return;
    }catch(e){
      msg.style.color='red';msg.textContent='Network error. Try again.';
    }
    btn.disabled=false;
  }

  const watchId=navigator.geolocation.watchPosition(pos=>{
    if(!best||pos.coords.accuracy<best.coords.accuracy) best=pos;
    msg.textContent='Improving GPS accuracy: '+Math.round(best.coords.accuracy)+' m...';
    if(best.coords.accuracy<=30) finish();
  },err=>{
    done=true;
    navigator.geolocation.clearWatch(watchId);
    clearTimeout(timer);
    msg.style.color='red';
    msg.textContent='Location permission denied / unavailable';
    btn.disabled=false;
  },{enableHighAccuracy:true,maximumAge:0});

  const timer=setTimeout(()=>{
    if(!best){
      done=true;
      navigator.geolocation.clearWatch(watchId);
      msg.style.color='red';
      msg.textContent='Could not get location. Try again.';
      btn.disabled=false;
    } else finish();
  },15000);
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

    name = str(d.get("name", "")).strip()[:100]
    regno = str(d.get("regno", "")).strip()[:50]
    if not name or not regno:
        return jsonify(ok=False, message="Fill all fields")

    if acc > MAX_ACCURACY_M:
        return jsonify(ok=False,
                       message=f"GPS accuracy too low ({acc:.0f} m). Move outdoors and retry.")

    dist = haversine_m(lat, lon, TARGET_LAT, TARGET_LON)
    if dist > RADIUS_M:
        return jsonify(ok=False,
                       message=f"You are {dist:.0f} m away. Must be within {RADIUS_M} m.")

    if not (FORM_POST_URL and ENTRY_NAME and ENTRY_REGNO):
        return jsonify(ok=False, message="Server is not configured. Contact the organiser.")

    fields = {ENTRY_NAME: name, ENTRY_REGNO: regno}
    if ENTRY_LOCATION:
        fields[ENTRY_LOCATION] = f"{lat:.6f}, {lon:.6f} ({dist:.0f} m)"

    try:
        req = urllib.request.Request(
            FORM_POST_URL,
            data=urllib.parse.urlencode(fields).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200 or "formResponse" not in resp.geturl():
                raise RuntimeError("Form rejected the response")
    except Exception:
        return jsonify(ok=False, message="Could not save response. Try again.")

    return jsonify(ok=True, message=f"Attendance recorded ✔ (distance {dist:.0f} m)")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
