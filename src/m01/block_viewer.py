"""3D viewer of the preliminary block model (M01B, P6).

Writes one self-contained HTML page (data embedded; Three.js is loaded from
cdnjs). The viewer is audit evidence, not decoration: it overlays topography,
drillholes, composites and blocks, and keeps UNKNOWN, extrapolated and
PARTIAL blocks visible and filterable. It shows a categorical assignment; it
does not show grades, resources or an interpreted geological model.
"""

import csv
import json
from collections import defaultdict
from math import isfinite
from pathlib import Path

from src.m01.block_model import (
    DEFAULT_GRID,
    DEFAULT_TOPOGRAPHY_PATH,
    GridSpec,
    TopographySurface,
    read_topography,
)

_ROOT = Path(__file__).resolve().parents[2]
_PROCESSED = _ROOT / "data" / "processed" / "m01b"
DEFAULT_OUTPUT_PATH = _ROOT / "outputs" / "figures" / "IMP002_block_model_3d_M01B.html"
DEFAULT_COLLAR_PATH = _ROOT / "data" / "raw" / "collar.csv"

DOMAINS = ["DIO", "POR", "BRX", "REG", "UNKNOWN"]
DOMAIN_COLORS = ["#4C78A8", "#F58518", "#E45756", "#C2A12F", "#9E9E9E"]
STATUS_NAMES = ["Soportado (<= R1)", "Extrapolado (R1 a R2)", "Sin soporte (UNKNOWN)"]
STATUS_COLORS = ["#2E9E5B", "#F2B134", "#9E9E9E"]
TOPO_NAMES = ["ROCK", "PARTIAL", "OUTSIDE_TOPO_COVERAGE"]
TOPO_COLORS = ["#8D6E63", "#26C6DA", "#D81B60"]
SURFACE_STEP_FACTOR = 0.5  # surface nodes every half block

Row = dict[str, str]


def sample_surface(surface: TopographySurface, grid: GridSpec) -> dict[str, object]:
    """Evaluate the surface on a regular node grid; uncovered nodes are None."""
    step_x = grid.dx * SURFACE_STEP_FACTOR
    step_y = grid.dy * SURFACE_STEP_FACTOR
    nx = int(round(grid.nx * grid.dx / step_x)) + 1
    ny = int(round(grid.ny * grid.dy / step_y)) + 1
    xs = [grid.x0 + i * step_x for i in range(nx)]
    ys = [grid.y0 + j * step_y for j in range(ny)]
    z: list[list[float | None]] = []
    for y in ys:
        row = []
        for x in xs:
            value = surface.elevation(x, y)
            row.append(None if value is None else round(value, 2))
        z.append(row)
    return {"x": xs, "y": ys, "z": z}


def build_viewer_data(
    grid: GridSpec,
    domain_rows: list[Row],
    composite_rows: list[Row],
    collar_rows: list[Row],
    surface_grid: dict[str, object],
) -> dict[str, object]:
    """Compact, JSON-serializable data for the page. AIR blocks are not drawn."""
    hole_names: list[str] = []
    hole_index: dict[str, int] = {}
    arrays: dict[str, list] = {key: [] for key in ("ix", "iy", "iz", "dom", "st", "tp", "mx", "dist", "hole", "id")}
    n_air = 0
    for r in domain_rows:
        topo = r["topo_state"]
        if topo == "AIR":
            n_air += 1
            continue
        status = r["assign_status"]
        domain = r["domain_id"]
        arrays["id"].append(int(r["block_id"]))
        arrays["ix"].append(int(r["ix"]))
        arrays["iy"].append(int(r["iy"]))
        arrays["iz"].append(int(r["iz"]))
        arrays["dom"].append(DOMAINS.index(domain) if domain in DOMAINS else len(DOMAINS) - 1)
        arrays["st"].append(
            0 if status == "ASSIGNED_SUPPORTED" else 1 if status == "ASSIGNED_EXTRAPOLATED" else 2
        )
        arrays["tp"].append(TOPO_NAMES.index(topo) if topo in TOPO_NAMES else 2)
        arrays["mx"].append(1 if r.get("mixed_flag") == "1" else 0)
        dist = _to_float(r.get("nearest_dist_m"))
        arrays["dist"].append(None if dist is None else round(dist, 1))
        name = r.get("nearest_hole_id") or ""
        if name and name not in hole_index:
            hole_index[name] = len(hole_names)
            hole_names.append(name)
        arrays["hole"].append(hole_index.get(name, -1))

    by_hole: dict[str, list[tuple[float, float, float, float]]] = defaultdict(list)
    comp_points: dict[str, list] = {"x": [], "y": [], "z": [], "dom": []}
    for r in composite_rows:
        x, y, z = (_to_float(r.get(k)) for k in ("x", "y", "z"))
        if x is None or y is None or z is None:
            continue
        depth = _to_float(r.get("from_m")) or 0.0
        by_hole[r["hole_id"]].append((depth, x, y, z))
        code = (r.get("lith_code") or "").strip()
        comp_points["x"].append(round(x, 2))
        comp_points["y"].append(round(y, 2))
        comp_points["z"].append(round(z, 2))
        comp_points["dom"].append(DOMAINS.index(code) if code in DOMAINS else len(DOMAINS) - 1)

    collars = {r["hole_id"]: r for r in collar_rows}
    holes = []
    for name in sorted(by_hole):
        pts = [(x, y, z) for _, x, y, z in sorted(by_hole[name])]
        collar = collars.get(name)
        if collar:
            cx, cy, cz = (_to_float(collar.get(k)) for k in ("x", "y", "z"))
            if None not in (cx, cy, cz):
                pts.insert(0, (cx, cy, cz))
        holes.append({"id": name, "pts": [[round(v, 2) for v in p] for p in pts]})

    return {
        "grid": {
            "x0": grid.x0, "y0": grid.y0, "z0": grid.z0,
            "dx": grid.dx, "dy": grid.dy, "dz": grid.dz,
            "nx": grid.nx, "ny": grid.ny, "nz": grid.nz,
        },
        "domains": DOMAINS,
        "domain_colors": DOMAIN_COLORS,
        "status_names": STATUS_NAMES,
        "status_colors": STATUS_COLORS,
        "topo_names": TOPO_NAMES,
        "topo_colors": TOPO_COLORS,
        "blocks": arrays,
        "hole_names": hole_names,
        "n_air_blocks": n_air,
        "n_blocks_total": len(domain_rows),
        "composites": comp_points,
        "holes": holes,
        "surface": surface_grid,
    }


def render_html(data: dict[str, object]) -> str:
    payload = json.dumps(data, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    return _TEMPLATE.replace("__DATA__", payload)


def write_viewer(data: dict[str, object], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(data), encoding="utf-8")


def run_m01b_visualizer(
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    grid: GridSpec = DEFAULT_GRID,
    domains_path: str | Path = _PROCESSED / "blocks_domains.csv",
    composites_path: str | Path = _PROCESSED / "composites.csv",
    collar_path: str | Path = DEFAULT_COLLAR_PATH,
    topography_path: str | Path = DEFAULT_TOPOGRAPHY_PATH,
) -> dict[str, object]:
    """Build the page from the generated CSV files and the topography."""
    domain_rows = _read_rows(domains_path)
    composite_rows = _read_rows(composites_path)
    collar_rows = _read_rows(collar_path)
    points, _ = read_topography(topography_path)
    surface_grid = sample_surface(TopographySurface(points), grid)
    data = build_viewer_data(grid, domain_rows, composite_rows, collar_rows, surface_grid)
    write_viewer(data, output_path)
    return data


def _read_rows(path: str | Path) -> list[Row]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _to_float(value: object) -> float | None:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


_TEMPLATE = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Modelo de bloques preliminar 3D</title>
<style>
:root{--bg:#14181d;--panel:#1d232b;--ink:#e8ecf1;--muted:#9aa6b2;--line:#303a45;--accent:#4C9BE8}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);font:13px/1.45 system-ui,Segoe UI,Roboto,sans-serif}
#view{position:fixed;inset:0 0 0 320px}
#panel{position:fixed;inset:0 auto 0 0;width:320px;overflow:auto;background:var(--panel);border-right:1px solid var(--line);padding:14px 16px 24px}
h1{font-size:15px;margin:0 0 4px}
h2{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:16px 0 6px}
.note{color:var(--muted);font-size:12px}
label{display:flex;align-items:center;gap:8px;margin:3px 0;cursor:pointer}
.sw{width:12px;height:12px;border-radius:3px;flex:none}
select,input[type=range]{width:100%}
select{background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:5px}
.row{display:flex;gap:8px;align-items:center}.row span{width:44px;color:var(--muted);flex:none}
#info{margin-top:8px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg)}
#tip{position:fixed;right:14px;bottom:14px;max-width:300px;padding:8px 10px;background:var(--panel);border:1px solid var(--line);border-radius:8px;display:none;z-index:5}
.warn{border-left:3px solid #F2B134;padding:4px 8px;margin-top:10px;color:var(--muted);font-size:12px}
@media(max-width:700px){#panel{position:static;width:auto;max-height:45vh}#view{position:static;height:55vh}}
</style>
</head>
<body>
<div id="panel">
  <h1>Modelo de bloques preliminar</h1>
  <div class="note">Asignación categórica de dominio. No hay estimación de leyes, ni recursos, ni modelo geológico interpretado.</div>
  <div id="info"></div>
  <h2>Colorear por</h2>
  <select id="colorby">
    <option value="domain">Dominio</option>
    <option value="status">Estado de asignación (soporte)</option>
    <option value="topo">Estado topográfico</option>
    <option value="mixed">Contacto cercano (mixed_flag)</option>
  </select>
  <div id="legend"></div>
  <h2>Capas</h2>
  <div id="layers"></div>
  <h2>Bloques: dominio</h2><div id="f-dom"></div>
  <h2>Bloques: soporte</h2><div id="f-st"></div>
  <h2>Bloques: topografía</h2><div id="f-tp"></div>
  <h2>Recorte por índice de bloque</h2><div id="clip"></div>
  <h2>Opacidad de bloques</h2><input id="opacity" type="range" min="0.1" max="1" step="0.05" value="0.9">
  <div class="warn">Los bloques AIR no se dibujan (están sobre la superficie). Los bloques UNKNOWN, extrapolados y PARTIAL se mantienen visibles y filtrables. Clic en un bloque para ver sus datos.</div>
</div>
<div id="view"></div>
<div id="tip"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const D=__DATA__;
(function(){
const G=D.grid,B=D.blocks,N=B.ix.length;
const hex=h=>new THREE.Color(h);
const SX=G.nx*G.dx,SY=G.ny*G.dy,SZ=G.nz*G.dz;
const L=(x,y,z)=>new THREE.Vector3(x-G.x0,y-G.y0,z-G.z0);
const view=document.getElementById('view');
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
view.appendChild(renderer.domElement);
const scene=new THREE.Scene();scene.background=new THREE.Color(0x14181d);
const camera=new THREE.PerspectiveCamera(45,1,1,20000);camera.up.set(0,0,1);
scene.add(new THREE.AmbientLight(0xffffff,0.62));
const sun=new THREE.DirectionalLight(0xffffff,0.75);sun.position.set(-300,-500,900);scene.add(sun);

/* simple orbit control */
const target=new THREE.Vector3(SX/2,SY/2,SZ/3);
let rad=Math.max(SX,SY,SZ)*1.5,theta=-2.3,phi=1.0;
function place(){const s=Math.sin(phi);camera.position.set(target.x+rad*s*Math.cos(theta),target.y+rad*s*Math.sin(theta),target.z+rad*Math.cos(phi));camera.lookAt(target);}
let drag=null;
const cv=renderer.domElement;
cv.addEventListener('contextmenu',e=>e.preventDefault());
cv.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,pan:e.button===2||e.shiftKey,moved:false};cv.setPointerCapture(e.pointerId);});
cv.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>2)drag.moved=true;drag.x=e.clientX;drag.y=e.clientY;
 if(drag.pan){const k=rad*0.0016;const r=new THREE.Vector3().subVectors(camera.position,target);const right=new THREE.Vector3().crossVectors(camera.up,r).normalize();const up=new THREE.Vector3().crossVectors(r,right).normalize();target.addScaledVector(right,dx*k).addScaledVector(up,dy*k);}
 else{theta-=dx*0.006;phi=Math.min(Math.max(phi-dy*0.006,0.05),Math.PI-0.05);}place();});
cv.addEventListener('pointerup',e=>{const was=drag&&!drag.moved;drag=null;if(was)pick(e);});
cv.addEventListener('wheel',e=>{e.preventDefault();rad*=Math.exp(e.deltaY*0.001);rad=Math.min(Math.max(rad,50),12000);place();},{passive:false});
function resize(){const w=view.clientWidth,h=view.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();}
addEventListener('resize',resize);

/* layers */
const layers={};
function addLayer(key,label,obj,on){layers[key]={obj,label};obj.visible=on;scene.add(obj);}
// grid box
const box=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(SX,SY,SZ)),new THREE.LineBasicMaterial({color:0x56626f}));
box.position.set(SX/2,SY/2,SZ/2);addLayer('box','Caja del grid',box,true);
// topography surface
(function(){const S=D.surface,nx=S.x.length,ny=S.y.length,pos=[],idx=[],ok=[];
 for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){const z=S.z[j][i];const v=z===null?[S.x[i]-G.x0,S.y[j]-G.y0,0]:[S.x[i]-G.x0,S.y[j]-G.y0,z-G.z0];pos.push(...v);ok.push(z!==null);}
 for(let j=0;j<ny-1;j++)for(let i=0;i<nx-1;i++){const a=j*nx+i,b=a+1,c=a+nx,d=c+1;if(ok[a]&&ok[b]&&ok[c]&&ok[d]){idx.push(a,b,c,b,d,c);}}
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setIndex(idx);g.computeVertexNormals();
 const m=new THREE.Mesh(g,new THREE.MeshLambertMaterial({color:0x8fa3b5,transparent:true,opacity:0.32,side:THREE.DoubleSide,depthWrite:false}));
 const w=new THREE.LineSegments(new THREE.WireframeGeometry(g),new THREE.LineBasicMaterial({color:0xb8c7d6,transparent:true,opacity:0.18}));
 const grp=new THREE.Group();grp.add(m);grp.add(w);addLayer('topo','Topografía (superficie evaluada)',grp,true);})();
// drillholes
(function(){const grp=new THREE.Group();
 D.holes.forEach(h=>{const p=h.pts.map(q=>L(q[0],q[1],q[2]));if(p.length<2)return;grp.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(p),new THREE.LineBasicMaterial({color:0xffffff})));});
 const c=D.holes.filter(h=>h.pts.length).map(h=>L(h.pts[0][0],h.pts[0][1],h.pts[0][2]));
 const pts=new THREE.Points(new THREE.BufferGeometry().setFromPoints(c),new THREE.PointsMaterial({color:0xffee58,size:6,sizeAttenuation:false}));grp.add(pts);
 addLayer('holes','Sondajes y collares',grp,true);})();
// composites
(function(){const C=D.composites,pos=[],col=[];
 for(let i=0;i<C.x.length;i++){const v=L(C.x[i],C.y[i],C.z[i]);pos.push(v.x,v.y,v.z);const c=hex(D.domain_colors[C.dom[i]]);col.push(c.r,c.g,c.b);}
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setAttribute('color',new THREE.Float32BufferAttribute(col,3));
 addLayer('comp','Composites (color = litología)',new THREE.Points(g,new THREE.PointsMaterial({size:3,sizeAttenuation:false,vertexColors:true})),false);})();

/* blocks */
const geo=new THREE.BoxGeometry(1,1,1);
const mat=new THREE.MeshLambertMaterial({transparent:true,opacity:0.9});
const mesh=new THREE.InstancedMesh(geo,mat,Math.max(N,1));
mesh.setColorAt(0,new THREE.Color(0xffffff));
addLayer('blocks','Bloques (roca, sin AIR)',mesh,true);
const dummy=new THREE.Object3D();
const visible=new Uint8Array(N);
const f={dom:D.domains.map(()=>true),st:[true,true,true],tp:[true,true,true]};
const clip={x:[0,G.nx-1],y:[0,G.ny-1],z:[0,G.nz-1]};
let mode='domain';
function colorOf(i){
 if(mode==='domain')return D.domain_colors[B.dom[i]];
 if(mode==='status')return D.status_colors[B.st[i]];
 if(mode==='topo')return D.topo_colors[B.tp[i]];
 return B.mx[i]?'#D81B60':'#8e99a4';}
function apply(){let shown=0;const cnt={};
 for(let i=0;i<N;i++){
  const ok=f.dom[B.dom[i]]&&f.st[B.st[i]]&&f.tp[B.tp[i]]&&B.ix[i]>=clip.x[0]&&B.ix[i]<=clip.x[1]&&B.iy[i]>=clip.y[0]&&B.iy[i]<=clip.y[1]&&B.iz[i]>=clip.z[0]&&B.iz[i]<=clip.z[1];
  visible[i]=ok?1:0;
  if(ok){shown++;dummy.position.set((B.ix[i]+0.5)*G.dx,(B.iy[i]+0.5)*G.dy,(B.iz[i]+0.5)*G.dz);dummy.scale.set(G.dx*0.96,G.dy*0.96,G.dz*0.96);}
  else{dummy.position.set(0,0,-1e5);dummy.scale.set(0,0,0);}
  dummy.updateMatrix();mesh.setMatrixAt(i,dummy.matrix);
  mesh.setColorAt(i,hex(colorOf(i)));
  if(ok){const k=D.domains[B.dom[i]];cnt[k]=(cnt[k]||0)+1;}
 }
 mesh.instanceMatrix.needsUpdate=true;if(mesh.instanceColor)mesh.instanceColor.needsUpdate=true;
 document.getElementById('info').innerHTML='Bloques dibujados: <b>'+shown.toLocaleString()+'</b> de '+N.toLocaleString()+' de roca<br>Bloques AIR (no dibujados): '+D.n_air_blocks.toLocaleString()+'<br>Total del grid: '+D.n_blocks_total.toLocaleString()+'<br><span class="note">'+Object.keys(cnt).map(k=>k+' '+cnt[k].toLocaleString()).join(' · ')+'</span>';}
function legend(){const el=document.getElementById('legend');let items=[];
 if(mode==='domain')items=D.domains.map((n,i)=>[n,D.domain_colors[i]]);
 else if(mode==='status')items=D.status_names.map((n,i)=>[n,D.status_colors[i]]);
 else if(mode==='topo')items=D.topo_names.map((n,i)=>[n,D.topo_colors[i]]);
 else items=[['Más de un dominio dentro de R1','#D81B60'],['Un solo dominio','#8e99a4']];
 el.innerHTML=items.map(x=>'<label style="cursor:default"><span class="sw" style="background:'+x[1]+'"></span>'+x[0]+'</label>').join('');}
function checks(id,names,colors,arr){const el=document.getElementById(id);
 names.forEach((n,i)=>{const lb=document.createElement('label');lb.innerHTML='<input type="checkbox" checked><span class="sw" style="background:'+colors[i]+'"></span>'+n;
  lb.firstChild.addEventListener('change',e=>{arr[i]=e.target.checked;apply();});el.appendChild(lb);});}
checks('f-dom',D.domains,D.domain_colors,f.dom);
checks('f-st',D.status_names,D.status_colors,f.st);
checks('f-tp',D.topo_names,D.topo_colors,f.tp);
(function(){const el=document.getElementById('layers');
 Object.keys(layers).forEach(k=>{const lb=document.createElement('label');lb.innerHTML='<input type="checkbox"'+(layers[k].obj.visible?' checked':'')+'>'+layers[k].label;
  lb.firstChild.addEventListener('change',e=>{layers[k].obj.visible=e.target.checked;});el.appendChild(lb);});})();
(function(){const el=document.getElementById('clip');
 [['x','X (oeste-este)',G.nx],['y','Y (sur-norte)',G.ny],['z','Z (capas)',G.nz]].forEach(([k,name,n])=>{
  const wrap=document.createElement('div');wrap.innerHTML='<div class="note">'+name+'</div>'+
   '<div class="row"><span id="'+k+'a">0</span><input type="range" min="0" max="'+(n-1)+'" value="0"></div>'+
   '<div class="row"><span id="'+k+'b">'+(n-1)+'</span><input type="range" min="0" max="'+(n-1)+'" value="'+(n-1)+'"></div>';
  const [lo,hi]=wrap.querySelectorAll('input');
  const upd=()=>{let a=+lo.value,b=+hi.value;if(a>b){if(document.activeElement===lo){b=a;hi.value=b;}else{a=b;lo.value=a;}}clip[k]=[a,b];document.getElementById(k+'a').textContent=a;document.getElementById(k+'b').textContent=b;apply();};
  lo.addEventListener('input',upd);hi.addEventListener('input',upd);el.appendChild(wrap);});})();
document.getElementById('colorby').addEventListener('change',e=>{mode=e.target.value;legend();apply();});
document.getElementById('opacity').addEventListener('input',e=>{mat.opacity=+e.target.value;});

/* picking */
const ray=new THREE.Raycaster(),mouse=new THREE.Vector2(),tip=document.getElementById('tip');
function pick(e){const r=cv.getBoundingClientRect();mouse.set(((e.clientX-r.left)/r.width)*2-1,-((e.clientY-r.top)/r.height)*2+1);ray.setFromCamera(mouse,camera);
 if(!layers.blocks.obj.visible){tip.style.display='none';return;}
 const hits=ray.intersectObject(mesh).filter(h=>visible[h.instanceId]);
 if(!hits.length){tip.style.display='none';return;}
 const i=hits[0].instanceId,dn=D.domains[B.dom[i]],hole=B.hole[i]>=0?D.hole_names[B.hole[i]]:'—';
 tip.innerHTML='<b>Bloque '+B.id[i]+'</b> (ix '+B.ix[i]+', iy '+B.iy[i]+', iz '+B.iz[i]+')<br>Dominio: <b>'+dn+'</b><br>Soporte: '+D.status_names[B.st[i]]+'<br>Topografía: '+D.topo_names[B.tp[i]]+'<br>Composite más cercano: '+(B.dist[i]===null?'—':B.dist[i]+' m')+' ('+hole+')<br>Contacto cercano (mixed): '+(B.mx[i]?'sí':'no');
 tip.style.display='block';}

legend();apply();resize();place();
(function loop(){requestAnimationFrame(loop);renderer.render(scene,camera);})();
window.__viewer={N,visible,apply,f,clip};
})();
</script>
</body>
</html>
"""
