from math import radians, sin, cos, asin, sqrt

from flask import Flask, request, jsonify, render_template_string

# ---------- CHANGE THESE ----------
TARGET_LAT = 10.937290 
TARGET_LON = 76.958365  
RADIUS_M = 200           # allowed radius in metres
MAX_ACCURACY_M = 200      # reject if GPS accuracy is worse than this
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSe10RF6MCqOqbCYuEk2Lms6CHBEG_alKklN7LEllBi0kEZydQ/viewform?usp=header"
# ----------------------------------

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
<title>Attendance</title>
<style>
 body{font-family:Arial;max-width:420px;margin:30px auto;padding:0 16px}
 button{width:100%;padding:12px;font-size:16px;background:#1a73e8;color:#fff;border:0;border-radius:6px}
 button:disabled{background:#999}
 #msg{margin-top:12px;font-weight:bold}
</style></head><body>
<p id="info">Checking location...</p>
<button id="btn" onclick="verify()" style="display:none">Try again</button>
<div id="msg"></div>
<script>
function verify(){
  const msg=document.getElementById('msg');
  const btn=document.getElementById('btn');
  msg.style.color='black';
  if(!navigator.geolocation){msg.style.color='red';msg.textContent='Geolocation not supported';return;}
  btn.style.display='none';
  msg.textContent='Getting your location...';
  let best=null, done=false;

  async function finish(){
    if(done||!best) return;
    done=true;
    navigator.geolocation.clearWatch(watchId);
    clearTimeout(timer);
    try{
      const r=await fetch('/check',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({lat:best.coords.latitude,lon:best.coords.longitude,
          accuracy:best.coords.accuracy})});
      const d=await r.json();
      if(d.ok){
        msg.style.color='green';
        msg.textContent='';
        window.location.replace(d.url);
        setTimeout(()=>{msg.innerHTML='<a href="'+d.url+'" style="font-size:18px">Tap here to open the form</a>';},4000);
        return;
      }
      msg.style.color='red';
      msg.textContent=d.message;
    }catch(e){
      msg.style.color='red';msg.textContent='Network error. Try again.';
    }
    btn.style.display='block';
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
    btn.style.display='block';
  },{enableHighAccuracy:true,maximumAge:0});

  const timer=setTimeout(()=>{
    if(!best){
      done=true;
      navigator.geolocation.clearWatch(watchId);
      msg.style.color='red';
      msg.textContent='Could not get location. Try again.';
      btn.style.display='block';
    } else finish();
  },15000);
}
window.onload=verify;
</script></body></html>
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
                       message=f"GPS accuracy too low ({acc:.0f} m). Move outdoors and retry.")

    dist = haversine_m(lat, lon, TARGET_LAT, TARGET_LON)
    if dist > RADIUS_M:
        return jsonify(ok=False,
                       message=f"You are {dist:.0f} m away. Must be within {RADIUS_M} m.")

    return jsonify(ok=True, message=f"Location verified ({dist:.0f} m).", url=FORM_URL)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
