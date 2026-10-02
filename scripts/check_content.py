#!/usr/bin/env python3
# Verificador de salud del contenido del demo de OnePlay.
# - Streams live (live.json): sigue la cadena que hace falta para reproducir (lista maestra → primera variante →
#   primer segmento). Solo la maestra no basta: puede ser un fichero estático que sigue en pie con las variantes muertas.
# - Pelis/series (movies_all.json + series_episodes_*.json): comprueba que el
#   fichero exacto sigue existiendo en archive.org via la metadata API
#   (NUNCA con HEAD masivo: archive.org rate-limitea y da falsos muertos).
# - Auto-reparación: si una peli muere y scripts/mirrors.json tiene un espejo
#   vivo para ese stream_id, conmuta el direct_source y reescribe movies_all.json.
# Salida: reports/health.json + código de salida 0 (sano u auto-reparado) / 1 (hay bajas).
# Lo ejecuta el workflow check-content diariamente; también sirve en local.
import json, re, sys, time, glob, urllib.parse, urllib.request

UA = "OnePlay/6.7 (health-check)"
ARCHIVE_RE = re.compile(r"https://archive\.org/download/([^/]+)/(.+)$")

def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(400000)

def archive_files(item, attempts=4):
    """Lista de ficheros del ítem, o None si el ítem no existe.
    Reintenta con paciencia: una respuesta vacía puede ser rate-limit, no muerte."""
    for i in range(attempts):
        try:
            raw = fetch(f"https://archive.org/metadata/{item}", timeout=40)
            data = json.loads(raw)
            if data.get("files"):
                return {f["name"] for f in data["files"]}
            # {} o sin files: puede ser ítem borrado O rate-limit -> reintentar
        except Exception:
            pass
        time.sleep(6 * (i + 1))
    return None

def probe_file(url):
    """Sonda Range directa al fichero (otra infra que la metadata API).
    Última palabra antes de declarar algo muerto: 200/206 = vivo."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-400"})
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                if r.status in (200, 206):
                    return True
        except Exception:
            pass
        time.sleep(5)
    return False

def fetch_playlist(url):
    """Una lista m3u8 y la dirección final tras las redirecciones (base de sus entradas relativas)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(400000).decode("utf-8", "replace"), r.geturl()

def first_entry(playlist):
    for line in playlist.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None

def live_stream_alive(url):
    """(vivo, motivo). Un directo vive si se puede REPRODUCIR, no si responde su lista maestra: FRANCE 24, CGTN y NASA
    estuvieron meses con la maestra en 200 y las variantes en 400/404 o sin DNS, y la app solo podía dar «Reconectando»."""
    playlist, base = fetch_playlist(url)
    if not playlist.lstrip().startswith("#EXTM3U"):
        return False, "la maestra no es una lista m3u8"
    entry = first_entry(playlist)
    if entry is None:
        return False, "la maestra no tiene entradas"
    if "#EXT-X-STREAM-INF" in playlist:
        playlist, base = fetch_playlist(urllib.parse.urljoin(base, entry))
        if not playlist.lstrip().startswith("#EXTM3U"):
            return False, "la variante no es una lista m3u8"
        entry = first_entry(playlist)
        if entry is None:
            return False, "la variante no tiene segmentos"
    req = urllib.request.Request(urllib.parse.urljoin(base, entry),
                                 headers={"User-Agent": UA, "Range": "bytes=0-1023"})
    with urllib.request.urlopen(req, timeout=20) as r:
        if r.status not in (200, 206):
            return False, f"el segmento responde {r.status}"
    return True, ""

def check_live():
    dead = []
    for ch in json.load(open("live.json")):
        url = ch.get("direct_source", "")
        ok, reason = False, ""
        for _ in range(2):
            try:
                ok, reason = live_stream_alive(url)
                if ok:
                    break
            except Exception as e:
                reason = f"{type(e).__name__}: {e}"[:160]
            time.sleep(3)
        if not ok:
            dead.append({"tipo": "live", "id": ch["stream_id"], "nombre": ch["name"], "url": url, "motivo": reason})
        time.sleep(0.5)
    return dead

def collect_archive_refs():
    refs = []  # (tipo, id, nombre, item, fichero, url)
    for m in json.load(open("movies_all.json")):
        mt = ARCHIVE_RE.match(m.get("direct_source", "") or "")
        if mt:
            refs.append(("movie", m["stream_id"], m["name"], mt.group(1), urllib.parse.unquote(mt.group(2)), m["direct_source"]))
    for path in sorted(glob.glob("series_episodes_*.json")):
        d = json.load(open(path))
        serie = (d.get("info") or {}).get("name", path)
        for season, eps in (d.get("episodes") or {}).items():
            for e in eps:
                u = e.get("direct_source", "")
                mt = ARCHIVE_RE.match(u or "")
                if mt:
                    refs.append(("episode", e.get("id"), f"{serie} ep {e.get('id')}", mt.group(1), urllib.parse.unquote(mt.group(2)), u))
    return refs

def check_archive(refs):
    dead = []
    by_item = {}
    for r in refs:
        by_item.setdefault(r[3], []).append(r)
    for item, group in by_item.items():
        files = archive_files(item)
        for tipo, rid, nombre, _, fichero, url in group:
            missing = (files is None) or (fichero not in files)
            # La metadata puede mentir por rate-limit: solo es baja si la sonda
            # Range directa al fichero también falla.
            if missing and not probe_file(url):
                motivo = "item desaparecido" if files is None else "fichero ausente"
                dead.append({"tipo": tipo, "id": rid, "nombre": nombre, "url": url, "motivo": motivo,
                             "_item": item, "_fichero": fichero})
        time.sleep(4)
    return dead

def confirm_dead(dead):
    """Pasada de confirmación tras enfriamiento: archive.org estrangula con dureza
    las IPs de los runners de GitHub y produce muertes falsas EN MASA (visto el
    10-ago: 32 'bajas' que estaban vivas). La podredumbre no se cura sola; el
    rate-limit sí -> esperar y reverificar cada baja individualmente."""
    if not dead:
        return []
    print(f"{len(dead)} posibles bajas; confirmando tras enfriamiento de 3 min...", flush=True)
    time.sleep(180)
    confirmed = []
    for d in dead:
        alive = probe_file(d["url"])
        if not alive:
            files = archive_files(d["_item"], attempts=3)
            alive = bool(files) and d["_fichero"] in files
        if not alive:
            confirmed.append(d)
        time.sleep(8)
    for d in confirmed:
        d.pop("_item", None); d.pop("_fichero", None)
    return confirmed

def try_heal_movies(dead):
    """Para pelis muertas con espejo en scripts/mirrors.json: verificar el espejo y conmutar."""
    try:
        mirrors = json.load(open("scripts/mirrors.json"))
    except FileNotFoundError:
        return [], dead
    healed, still_dead = [], []
    movies = json.load(open("movies_all.json"))
    changed = False
    for d in dead:
        if d["tipo"] != "movie":
            still_dead.append(d)
            continue
        cands = mirrors.get(str(d["id"]), [])
        new_url = None
        for cand in cands:
            if ARCHIVE_RE.match(cand) and probe_file(cand):
                new_url = cand
                break
        if new_url:
            for m in movies:
                if m["stream_id"] == d["id"]:
                    m["direct_source"] = new_url
                    changed = True
            healed.append({**d, "nuevo": new_url})
        else:
            still_dead.append(d)
    if changed:
        json.dump(movies, open("movies_all.json", "w"), indent=1, ensure_ascii=False)
        open("movies_all.json", "a").write("\n")
    return healed, still_dead

def main():
    live_dead = check_live()
    refs = collect_archive_refs()
    vod_dead = confirm_dead(check_archive(refs))
    healed, vod_dead = try_heal_movies(vod_dead)
    report = {
        "generado": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "chequeado": {"live": len(json.load(open('live.json'))), "vod_refs": len(refs)},
        "auto_reparado": healed,
        "caidos": live_dead + vod_dead,
        "nota": "Streams live que fallan desde runners de EE.UU. pueden ser geo-bloqueo (p.ej. RTVE), no muerte real.",
    }
    import os
    os.makedirs("reports", exist_ok=True)
    json.dump(report, open("reports/health.json", "w"), indent=2, ensure_ascii=False)
    open("reports/health.json", "a").write("\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(1 if report["caidos"] else 0)

if __name__ == "__main__":
    main()
