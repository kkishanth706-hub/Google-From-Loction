import os
from math import radians, sin, cos, asin, sqrt

from flask import Flask, request, jsonify, render_template_string

# ---------- LOCATION SETTINGS ----------
CENTER_LAT = 10.942657
CENTER_LNG = 76.955587
DEFAULT_RADIUS_M =30    # allowed radius in metres
IPHONE_RADIUS_M = 70      # iPhones often give rough GPS; lower this for stricter checking
MAX_ACCURACY_M = 80       # reject if GPS accuracy is worse than this
# ---------------------------------------

# Embed link of the Google Form (Send -> "<>" tab -> copy the src="..." value).
# Set it in Vercel -> Settings -> Environment Variables as FORM_EMBED_URL.
# It stays on the server and is sent to the browser only AFTER the location check passes.
FORM_EMBED_URL = os.environ.get("FORM_EMBED_URL", "https://claude.ai/chat/61873fad-6504-48c5-9ef4-88c7ce41d517")

app = Flask(__name__)


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * R * asin(sqrt(a))


PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Hall Attendance Verification</title>
<style>
 body{margin:0;font-family:Arial,sans-serif}
 #location-display{position:fixed;top:10px;right:10px;background:rgba(255,255,255,.9);
   padding:10px;border-radius:8px;box-shadow:0 4px 8px rgba(0,0,0,.2);font-size:14px;z-index:999}
 #form-container{display:flex;justify-content:center;align-items:center;min-height:100vh;text-align:center;padding:0 12px}
 #form-container iframe{border:none;box-shadow:0 4px 8px rgba(0,0,0,.2);width:100%;max-width:700px;height:90vh}
 h2{color:#333}
 button{padding:10px 20px;font-size:16px;background:#1a73e8;color:#fff;border:0;border-radius:6px;margin-top:10px}
</style>
</head>
<body>
<div id="location-display">Detecting your location...</div>
<div id="form-container"><h2>Loading...</h2></div>
<script>
const box = document.getElementById('form-container');
const info = document.getElementById('location-display');

function showError(title, note){
  box.innerHTML = '<div><h2>'+title+'</h2><p style="color:red">'+(note||'')+
    '</p><button onclick="checkAccess()">Try again</button></div>';
}

function checkAccess(){
  box.innerHTML = '<h2>Loading...</h2>';
  if(!navigator.geolocation){ showError('Geolocation is not supported by your browser.'); return; }
  let best = null, done = false;

  async function finish(){
    if(done || !best) return;
    done = true;
    navigator.geolocation.clearWatch(watchId);
    clearTimeout(timer);
    info.textContent = 'Your Location: Lat '+best.coords.latitude.toFixed(6)+
                       ', Lng '+best.coords.longitude.toFixed(6);
    try{
      const r = await fetch('/check', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({lat:best.coords.latitude, lon:best.coords.longitude,
                              accuracy:best.coords.accuracy})});
      const d = await r.json();
      if(d.ok){
        box.innerHTML = '';
        const f = document.createElement('iframe');
        f.src = d.url;
        f.setAttribute('frameborder','0');
        box.appendChild(f);
      } else {
        showError(d.message, 'If iPhone user: enable "Precise Location" in Settings, then try again.');
      }
    }catch(e){ showError('Network error.', 'Check your internet and try again.'); }
  }

  const watchId = navigator.geolocation.watchPosition(pos => {
    if(!best || pos.coords.accuracy < best.coords.accuracy) best = pos;
    info.textContent = 'Improving GPS accuracy: '+Math.round(best.coords.accuracy)+' m...';
    if(best.coords.accuracy <= 30) finish();
  }, () => {
    done = true;
    navigator.geolocation.clearWatch(watchId);
    clearTimeout(timer);
    showError('Location access is required to open this form.',
              'If iPhone user: use Chrome or the Google app (avoid Safari).');
  }, {enableHighAccuracy:true, maximumAge:0});

  const timer = setTimeout(() => {
    if(!best){
      done = true;
      navigator.geolocation.clearWatch(watchId);
      showError('Could not get your location.', 'Move near a window or outdoors and retry.');
    } else finish();
  }, 15000);
}

document.addEventListener('DOMContentLoaded', checkAccess);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/check", methods=["POST"])
def check():
    d = request.get_json(force=True)
    try:
        lat, lon = float(d["lat"]), float(d["lon"])
        acc = float(d.get("accuracy", 0))
    except (KeyError, ValueError):
        return jsonify(ok=False, message="Invalid location data")

    if acc > MAX_ACCURACY_M:
        return jsonify(ok=False,
                       message=f"GPS accuracy too low ({acc:.0f} m).")

    ua = request.headers.get("User-Agent", "")
    radius = IPHONE_RADIUS_M if any(x in ua for x in ("iPhone", "iPad", "iPod")) else DEFAULT_RADIUS_M

    dist = haversine_m(lat, lon, CENTER_LAT, CENTER_LNG)
    if dist > radius:
        return jsonify(ok=False,
                       message="Access Denied: You are not within the allowed location range.")

    if not FORM_EMBED_URL:
        return jsonify(ok=False, message="Server is not configured. Contact the organiser.")

    return jsonify(ok=True, url=FORM_EMBED_URL)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
