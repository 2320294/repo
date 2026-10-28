"""Visualização 3D experimental da arquitetura e dos elementos elétricos do DXF.
Módulo isolado: não altera o DXF nem os cálculos do projeto.
"""
import io
import json
import math
import re

import streamlit as st
import streamlit.components.v1 as components
import ezdxf


def _xy(ent):
    t = ent.dxftype()
    try:
        if t == "LINE":
            return [(float(ent.dxf.start.x), float(ent.dxf.start.y)), (float(ent.dxf.end.x), float(ent.dxf.end.y))]
        if t == "LWPOLYLINE":
            return [(float(p[0]), float(p[1])) for p in ent.get_points(format="xy")]
        if t == "POLYLINE":
            return [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in ent.vertices]
    except Exception:
        pass
    return []


def _nome_ambiente(poly, textos):
    # Associa o rótulo interno mais próximo do centro da caixa delimitadora.
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    internos = []
    for t in textos:
        x, y = t["x"], t["y"]
        inside = False
        j = len(poly) - 1
        for i in range(len(poly)):
            xi, yi = poly[i]; xj, yj = poly[j]
            if ((yi > y) != (yj > y)) and x < (xj-xi) * (y-yi) / ((yj-yi) or 1e-12) + xi:
                inside = not inside
            j = i
        if inside:
            internos.append((math.hypot(x-cx, y-cy), t["nome"]))
    if internos:
        return min(internos)[1]
    return "Ambiente"


def _extrair_modelo(dxf_bytes):
    if not dxf_bytes:
        return None
    if isinstance(dxf_bytes, bytes):
        stream = io.StringIO(dxf_bytes.decode("utf-8", errors="ignore"))
    elif isinstance(dxf_bytes, str):
        stream = io.StringIO(dxf_bytes)
    else:
        stream = dxf_bytes
    doc = ezdxf.read(stream)
    msp = doc.modelspace()
    polys, doors, texts, markers = [], [], [], []
    for e in msp:
        layer = str(e.dxf.layer if e.dxf.hasattr("layer") else "").upper().strip()
        typ = e.dxftype()
        if layer == "IA_AMBIENTES" and typ in ("LWPOLYLINE", "POLYLINE"):
            pts = _xy(e)
            if len(pts) >= 3:
                polys.append(pts)
        elif layer == "IA_PORTAS":
            pts = _xy(e)
            if len(pts) >= 2:
                doors.append([pts[0], pts[-1]])
        elif layer == "IA_TEXTOS" and typ in ("TEXT", "MTEXT"):
            try:
                txt = e.text if typ == "MTEXT" else e.dxf.text
                ins = e.dxf.insert
                texts.append({"nome": str(txt).strip(), "x": float(ins.x), "y": float(ins.y)})
            except Exception:
                pass
        # Se o DXF de entrada já possuir símbolos elétricos, tenta reconhecê-los
        # pelo nome da camada; não interpreta camadas arquitetônicas como elétrica.
        elif any(k in layer for k in ("ILUMIN", "TOMADA", "INTERRUP", "QDC", "ELETRICA", "ELÉTRICA")):
            try:
                if typ == "INSERT":
                    p = e.dxf.insert
                    markers.append({"x": float(p.x), "y": float(p.y), "kind": layer})
                elif typ == "CIRCLE":
                    p = e.dxf.center
                    markers.append({"x": float(p.x), "y": float(p.y), "kind": layer})
            except Exception:
                pass
    rooms = [{"points": p, "name": _nome_ambiente(p, texts)} for p in polys]
    allpts = [p for r in rooms for p in r["points"]] + [p for d in doors for p in d]
    if not allpts:
        return {"rooms": [], "doors": [], "markers": [], "bounds": [0, 0, 10, 10]}
    xs, ys = [p[0] for p in allpts], [p[1] for p in allpts]
    return {"rooms": rooms, "doors": doors, "markers": markers,
            "bounds": [min(xs), min(ys), max(xs), max(ys)]}


def renderizar_visualizacao_3d(dxf_bytes, pe_direito=2.8):
    st.subheader("🧊 Visualização 3D do projeto")
    st.caption("Prévia experimental gerada a partir da geometria do DXF de arquitetura. A visualização não modifica a planta nem os cálculos elétricos.")
    try:
        modelo = _extrair_modelo(dxf_bytes)
    except Exception as exc:
        st.error(f"Não foi possível interpretar o DXF para a visualização 3D: {exc}")
        return
    if not modelo or not modelo["rooms"]:
        st.warning("O DXF deste projeto não contém polígonos reconhecidos na camada IA_AMBIENTES. Confira se a planta base está carregada e preparada no padrão do AutoElétrica.")
        return
    c1, c2, c3 = st.columns(3)
    altura = c1.slider("Altura das paredes (m)", 2.2, 4.0, float(min(max(pe_direito or 2.8, 2.2), 4.0)), 0.1, key="ae3d_altura")
    opacidade = c2.slider("Transparência das paredes", 0.15, 0.95, 0.72, 0.05, key="ae3d_opacidade")
    mostrar_portas = c3.checkbox("Destacar portas", True, key="ae3d_portas")
    payload = json.dumps(modelo, ensure_ascii=False).replace("</", "<\\/")
    html = r'''<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;height:100%;overflow:hidden;background:#f1f4f8;font-family:Arial,sans-serif}#view{width:100%;height:590px;display:block}#hud{position:absolute;top:12px;left:12px;background:#fffE;padding:10px 12px;border-radius:9px;color:#26364b;font-size:12px;box-shadow:0 2px 10px #0002}#hud b{display:block;margin-bottom:4px}#help{color:#66758b;margin-top:4px}
</style></head><body><div id="hud"><b>AutoElétrica · Modelo 3D</b>Arraste para girar · Scroll para zoom · Botão direito para deslocar<div id="help">Arquitetura reconstruída do DXF</div></div><div id="view"></div>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script><script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script><script>
const D=__DATA__; const H=__HEIGHT__; const OP=__OPACITY__; const SHOWDOORS=__SHOWDOORS__;
const root=document.getElementById('view');
if(!window.THREE){root.innerHTML='<p style="padding:24px">Não foi possível carregar o motor 3D. Verifique a conexão com a internet e recarregue a página.</p>';}
else {
const scene=new THREE.Scene(); scene.background=new THREE.Color(0xf1f4f8);
const camera=new THREE.PerspectiveCamera(45,root.clientWidth/root.clientHeight,0.01,100000);
const renderer=new THREE.WebGLRenderer({antialias:true}); renderer.setPixelRatio(Math.min(devicePixelRatio,2)); renderer.setSize(root.clientWidth,root.clientHeight); renderer.shadowMap.enabled=true; root.appendChild(renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff,0x8997a8,2.0)); const sun=new THREE.DirectionalLight(0xffffff,2.1);sun.position.set(30,-40,70);scene.add(sun);
const group=new THREE.Group();scene.add(group); const b=D.bounds; const cx=(b[0]+b[2])/2, cy=(b[1]+b[3])/2; const span=Math.max(b[2]-b[0],b[3]-b[1],1); const scale=1;
function v(p,z){return new THREE.Vector3((p[0]-cx)*scale,(p[1]-cy)*scale,z)}
// Piso com polígono triangulado e paredes por segmento, sem alterar a geometria original.
for(const room of D.rooms){let pts=room.points.slice();if(pts.length>2&&Math.hypot(pts[0][0]-pts[pts.length-1][0],pts[0][1]-pts[pts.length-1][1])<1e-5)pts.pop();if(pts.length<3)continue;
 const shape=new THREE.Shape();shape.moveTo((pts[0][0]-cx), (pts[0][1]-cy));for(let i=1;i<pts.length;i++)shape.lineTo(pts[i][0]-cx,pts[i][1]-cy);shape.closePath();
 const floor=new THREE.Mesh(new THREE.ShapeGeometry(shape),new THREE.MeshStandardMaterial({color:0xe4e9ef,side:THREE.DoubleSide,roughness:0.95}));floor.position.z=0;group.add(floor);
 const labelCanvas=document.createElement('canvas');labelCanvas.width=512;labelCanvas.height=96;const ctx=labelCanvas.getContext('2d');ctx.fillStyle='#26364b';ctx.font='bold 34px Arial';ctx.textAlign='center';ctx.fillText(room.name||'Ambiente',256,56);const tex=new THREE.CanvasTexture(labelCanvas);const spr=new THREE.Sprite(new THREE.SpriteMaterial({map:tex,transparent:true,depthTest:false}));let ax=0,ay=0;pts.forEach(p=>{ax+=p[0];ay+=p[1]});spr.position.set((ax/pts.length-cx), (ay/pts.length-cy),0.06);spr.scale.set(Math.min(span*.25,Math.max(span*.09,(room.name||'Ambiente').length*.10)),Math.min(span*.06,.45),1);group.add(spr);
 for(let i=0;i<pts.length;i++){const a=pts[i],bb=pts[(i+1)%pts.length],dx=bb[0]-a[0],dy=bb[1]-a[1],len=Math.hypot(dx,dy);if(len<1e-4)continue;const geo=new THREE.BoxGeometry(len,H,0.12);const mat=new THREE.MeshStandardMaterial({color:0xf8fafc,transparent:true,opacity:OP,roughness:.85,side:THREE.DoubleSide});const wall=new THREE.Mesh(geo,mat);wall.position.set((a[0]+bb[0])/2-cx,(a[1]+bb[1])/2-cy,H/2);wall.rotation.z=Math.atan2(dy,dx);group.add(wall);const edge=new THREE.Line(new THREE.BufferGeometry().setFromPoints([v(a,H),v(bb,H)]),new THREE.LineBasicMaterial({color:0x8493a6,transparent:true,opacity:.8}));group.add(edge);}
}
if(SHOWDOORS){for(const d of D.doors){const pts=[v(d[0],.05),v(d[1],.05)];const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),new THREE.LineBasicMaterial({color:0xf59e0b,linewidth:3}));group.add(line)}}
for(const m of D.markers){const layer=m.kind||'';const color=/ILUMIN/.test(layer)?0xfacc15:/TOMADA/.test(layer)?0x0ea5e9:/INTERRUP/.test(layer)?0x22c55e:0xef4444;const obj=new THREE.Mesh(new THREE.SphereGeometry(Math.max(span*.006,.07),12,8),new THREE.MeshStandardMaterial({color,emissive:color,emissiveIntensity:.2}));obj.position.set(m.x-cx,m.y-cy,H*.92);group.add(obj)}
const floorGrid=new THREE.GridHelper(span*1.4,Math.min(80,Math.max(10,Math.round(span/2))),0xcbd5e1,0xe2e8f0);floorGrid.position.z=-.04;floorGrid.rotation.x=Math.PI/2;scene.add(floorGrid);
const Controls=THREE.OrbitControls;let controls;if(Controls){controls=new Controls(camera,renderer.domElement);controls.enableDamping=true;controls.target.set(0,0,H*.35)}
camera.up.set(0,0,1);camera.position.set(span*1.05,-span*1.2,span*1.05);camera.lookAt(0,0,H*.3);
function resize(){const w=root.clientWidth,h=root.clientHeight;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h)}window.addEventListener('resize',resize);
function animate(){requestAnimationFrame(animate);if(controls)controls.update();renderer.render(scene,camera)}animate();
}
</script></body></html>'''
    html = html.replace("__DATA__", payload).replace("__HEIGHT__", str(float(altura))).replace("__OPACITY__", str(float(opacidade))).replace("__SHOWDOORS__", "true" if mostrar_portas else "false")
    components.html(html, height=610, scrolling=False)
    if modelo["markers"]:
        st.success(f"Modelo carregado: {len(modelo['rooms'])} ambientes e {len(modelo['markers'])} elementos elétricos reconhecidos nas camadas do DXF.")
    else:
        st.info(f"Modelo carregado com {len(modelo['rooms'])} ambientes. O DXF base não contém símbolos elétricos reconhecíveis; a sobreposição elétrica será integrada em uma etapa seguinte, usando os dados reais do projeto gerado.")
