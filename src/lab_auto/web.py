"""Local single-operator web panel for the single-point Raman workflow.

Pure stdlib (`http.server`) — no web framework, no build step, no new dependency,
so the package keeps its PyYAML+pyserial diet and the panel runs offline on the
lab machine. It is a thin presentation layer: every button calls the SAME
workflow code the CLI does (``run_job`` below), so behavior and safety (PWM
interlocks, soft limits, laser-off-on-failure) are identical to ``ramanctl``.

Launch:  python -m lab_auto.web            # serves http://127.0.0.1:8000
Bind is 127.0.0.1 only — this drives a real laser; it must not be on the network.

ponytail: blocking request/response (a single-point run takes a few seconds);
no live streaming, no auth, no tray-scan UI yet. Add those only if asked.
"""

import csv
import dataclasses
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from lab_auto.config import load_workflow_and_devices, validate_sample_id
from lab_auto.errors import ConfigError, DeviceError, SafetyError
from lab_auto.workflow.raman import RamanWorkflow

# One run at a time: a second click must not fire a second laser sequence.
_run_lock = threading.Lock()


def list_workflow_configs(config_dir):
    """Return the *.yaml under config_dir that look like single-point configs."""
    out = []
    for path in sorted(Path(config_dir).glob("*.yaml")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "optics:" in text and "acquisition:" in text and "tray:" not in text:
            out.append(path.name)
    return out


def _read_results(run_dir: Path) -> dict:
    """Pull the spectrum + warnings out of a finished run dir for plotting."""
    def _col(path, value_key):
        x, y, x_type = [], [], "pixel_index"
        if not path.exists():
            return x, y, x_type
        with path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if "wavelength_nm" in row:
                    x_type = "wavelength_nm"
                    x.append(float(row["wavelength_nm"]))
                else:
                    x.append(int(row["pixel_index"]))
                y.append(float(row[value_key]))
        return x, y, x_type

    x, raw, x_type = _col(run_dir / "raw.csv", "intensity_raw")
    _, corrected, _ = _col(run_dir / "corrected.csv", "intensity_corrected")
    warnings = []
    meta_path = run_dir / "metadata.json"
    if meta_path.exists():
        warnings = json.loads(meta_path.read_text(encoding="utf-8")).get("warnings", [])
    return {"x": x, "x_axis_type": x_type, "raw": raw, "corrected": corrected, "warnings": warnings}


def run_job(*, config_path, devices_path=None, mode, sample_id=None) -> dict:
    """Run one single-point job. Same paths the CLI uses; testable in dry/sim.

    mode: 'dry_run' (preview actions, no hardware) | 'simulated' (fake devices,
    real output files) | 'real' (opens hardware, fires the laser).
    """
    workflow_config, devices_config = load_workflow_and_devices(config_path, devices_override=devices_path)
    if sample_id:
        # The override bypasses _parse_sample, so re-apply the path-injection guard.
        validate_sample_id(sample_id)
        workflow_config = dataclasses.replace(
            workflow_config, sample=dataclasses.replace(workflow_config.sample, id=sample_id)
        )
    # Validate optics/acquisition up front for every mode (fail before any move).
    RamanWorkflow.dry_run(workflow_config).validate_single_point_config()

    if mode == "dry_run":
        actions = RamanWorkflow.dry_run(workflow_config).measure_single_point(require_confirmation=False)
        return {"mode": mode, "sample_id": workflow_config.sample.id, "actions": actions}

    if mode == "simulated":
        run_dir = RamanWorkflow.simulated(workflow_config).run_single_point(require_confirmation=False)
        return {"mode": mode, "sample_id": workflow_config.sample.id, "run_dir": str(run_dir), **_read_results(run_dir)}

    if mode == "real":
        from lab_auto.devices.factory import DeviceFactory

        workflow = DeviceFactory().create_single_point_workflow(workflow_config, devices_config)
        try:
            run_dir = workflow.run_single_point(require_confirmation=False)
        finally:
            workflow.close()  # best-effort device teardown + force laser off
        return {"mode": mode, "sample_id": workflow_config.sample.id, "run_dir": str(run_dir), **_read_results(run_dir)}

    raise ConfigError(f"unknown mode: {mode!r}")


# --- HTTP layer --------------------------------------------------------

def _make_handler(config_dir: Path):
    page = _PAGE  # captured below

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            pass

        def _json(self, code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = urlparse(self.path).path
            if route == "/":
                body = page.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if route == "/api/configs":
                return self._json(200, {"configs": list_workflow_configs(config_dir)})
            self._json(404, {"error": "not found"})

        def do_POST(self):
            if urlparse(self.path).path != "/api/run":
                return self._json(404, {"error": "not found"})
            length = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json(400, {"error": "invalid JSON"})

            mode = req.get("mode", "dry_run")
            if mode == "real" and not req.get("confirm"):
                return self._json(400, {"error": "real run requires explicit confirmation"})
            if not req.get("config"):
                return self._json(400, {"error": "no config selected"})
            config_path = config_dir / req["config"]
            devices_path = (config_dir / req["devices"]) if req.get("devices") else None

            if not _run_lock.acquire(blocking=False):
                return self._json(409, {"error": "a run is already in progress"})
            try:
                result = run_job(
                    config_path=config_path,
                    devices_path=devices_path,
                    mode=mode,
                    sample_id=(req.get("sample_id") or "").strip() or None,
                )
                self._json(200, result)
            except (ConfigError, DeviceError, SafetyError) as exc:
                self._json(400, {"error": f"{type(exc).__name__}: {exc}"})
            except Exception as exc:  # noqa: BLE001 - surface anything as a panel error
                self._json(500, {"error": f"{type(exc).__name__}: {exc}"})
            finally:
                _run_lock.release()

    return Handler


def serve(*, host="127.0.0.1", port=8000, config_dir="configs", open_browser=True):
    config_dir = Path(config_dir)
    httpd = ThreadingHTTPServer((host, port), _make_handler(config_dir))
    url = f"http://{host}:{port}"
    print(f"lab_auto web panel -> {url}  (configs: {config_dir.resolve()})")
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        httpd.server_close()


_PAGE = r"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>单点 Raman 控制台</title><style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 system-ui,'Segoe UI',sans-serif;background:#0f1420;color:#dfe6f2}
header{padding:14px 20px;background:#16203a;border-bottom:1px solid #243250;font-weight:600}
main{max-width:920px;margin:0 auto;padding:20px;display:grid;gap:16px}
.card{background:#141b2e;border:1px solid #243250;border-radius:10px;padding:16px 18px}
label{display:block;font-size:13px;color:#9fb0cc;margin:10px 0 4px}
select,input{width:100%;padding:8px 10px;background:#0d1220;border:1px solid #2c3a5c;border-radius:7px;color:#eaf0fb;font-size:14px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.modes{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}
.modes button{flex:1;min-width:130px;padding:11px;border:1px solid #2c3a5c;border-radius:8px;background:#1b2540;color:#dfe6f2;font-size:14px;cursor:pointer}
.modes button:hover{border-color:#3d5a8c}
.modes button.real{background:#3a1620;border-color:#7a2233}
.modes button:disabled{opacity:.5;cursor:not-allowed}
#status{font-size:13px;color:#9fb0cc;min-height:20px}
.err{color:#ff8a9b}.ok{color:#7fe0a3}
pre{background:#0d1220;border:1px solid #243250;border-radius:8px;padding:12px;overflow:auto;font-size:13px;white-space:pre-wrap}
canvas{width:100%;height:300px;background:#0d1220;border:1px solid #243250;border-radius:8px}
.warn{color:#ffcf6b;font-size:13px}
small{color:#6f80a0}
</style></head><body>
<header>单点 Raman 控制台 · lab_auto</header>
<main>
 <div class="card">
  <div class="row">
   <div><label>测量配置 (configs/*.yaml)</label><select id="config"></select></div>
   <div><label>样品编号 sample.id（留空用配置里的）</label><input id="sample" placeholder="如 sample-001"></div>
  </div>
  <label>设备配置 devices（真机用 devices.real.yaml）</label><select id="devices"></select>
  <div class="modes">
   <button onclick="run('dry_run')" title="只预览动作，不碰硬件">① 预览动作 (dry-run)</button>
   <button onclick="run('simulated')" title="假设备，走完整流程并出图">② 模拟跑 (simulated)</button>
   <button class="real" onclick="runReal()" title="真机：会真实开关激光">③ 真机跑 (REAL ⚠)</button>
  </div>
  <p id="status">选择配置后点上面任一按钮。建议顺序：①预览 → ②模拟 → ③真机。</p>
 </div>
 <div class="card" id="out" style="display:none">
  <div id="warns"></div>
  <canvas id="plot" width="880" height="300"></canvas>
  <pre id="text"></pre>
 </div>
</main>
<script>
const $=s=>document.querySelector(s);
async function loadConfigs(){
 const r=await fetch('/api/configs');const d=await r.json();
 const cfg=$('#config'),dev=$('#devices');
 cfg.innerHTML='';dev.innerHTML='<option value="">（用配置文件里的 devices_config）</option>';
 d.configs.forEach(n=>{cfg.add(new Option(n,n));dev.add(new Option(n,n));});
}
function setStatus(msg,cls){const s=$('#status');s.textContent=msg;s.className=cls||'';}
function runReal(){
 if(!confirm('真机模式会真实开关激光。\n确认：激光功率已用半波片程序设好、样品已对到激光点位置？\n（单点测量在当前位置进行，不移动位移台，无需归零。）'))return;
 run('real',true);
}
async function run(mode,confirm){
 setStatus('运行中…（真机/模拟需几秒）');$('#out').style.display='none';
 const body={config:$('#config').value,devices:$('#devices').value,mode,sample_id:$('#sample').value,confirm:!!confirm};
 let d;try{const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});d=await r.json();
  if(!r.ok){setStatus('✗ '+(d.error||r.status),'err');return;}
 }catch(e){setStatus('✗ '+e,'err');return;}
 setStatus('✓ 完成 · 模式 '+d.mode+(d.run_dir?(' · 输出 '+d.run_dir):''),'ok');
 render(d);
}
function render(d){
 $('#out').style.display='block';
 $('#warns').innerHTML=(d.warnings||[]).map(w=>'<div class="warn">⚠ '+w+'</div>').join('');
 const canvas=$('#plot');
 if(d.actions){canvas.style.display='none';$('#text').textContent='动作序列：\n'+d.actions.join('\n');return;}
 canvas.style.display='block';$('#text').textContent='样品编号: '+(d.sample_id||'')+'\nx 轴: '+d.x_axis_type+' · 点数: '+(d.x?d.x.length:0);
 plot(canvas,d.x,d.raw,d.corrected);
}
function plot(c,x,raw,corrected){
 const g=c.getContext('2d'),W=c.width,H=c.height,p=34;g.clearRect(0,0,W,H);
 const series=[['#5b9cff',raw],['#7fe0a3',corrected]].filter(s=>s[1]&&s[1].length);
 if(!x||!x.length){return;}
 const ys=series.flatMap(s=>s[1]);const ymin=Math.min(...ys),ymax=Math.max(...ys);
 const xmin=x[0],xmax=x[x.length-1];
 const sx=v=>p+(v-xmin)/((xmax-xmin)||1)*(W-2*p);
 const sy=v=>H-p-(v-ymin)/((ymax-ymin)||1)*(H-2*p);
 g.strokeStyle='#243250';g.beginPath();g.moveTo(p,p);g.lineTo(p,H-p);g.lineTo(W-p,H-p);g.stroke();
 series.forEach(([color,arr])=>{g.strokeStyle=color;g.lineWidth=1.5;g.beginPath();
  arr.forEach((v,i)=>{const X=sx(x[i]),Y=sy(v);i?g.lineTo(X,Y):g.moveTo(X,Y);});g.stroke();});
 g.fillStyle='#6f80a0';g.font='11px sans-serif';
 g.fillText(xmin.toFixed?xmin.toFixed(1):xmin,p,H-p+14);g.fillText(''+(xmax.toFixed?xmax.toFixed(1):xmax),W-p-30,H-p+14);
}
loadConfigs();
</script></body></html>"""


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="lab_auto.web", description="Local single-point Raman web panel")
    parser.add_argument("--port", type=int, default=8008)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--config-dir", default="configs")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    serve(host=args.host, port=args.port, config_dir=args.config_dir, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
