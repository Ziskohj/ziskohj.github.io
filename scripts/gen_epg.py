#!/usr/bin/env python3
# Genera xmltv.xml para el demo de OnePlay, SIEMPRE centrado en la hora actual (UTC).
# Portable (macOS y el runner Linux del GitHub Action). Lo ejecuta el workflow refresh-epg cada 6h.
from datetime import datetime, timezone, timedelta
from xml.sax.saxutils import escape

# (epg_channel_id, display-name)
CHANNELS = [
    ("france24.en", "FRANCE 24 English"),
    ("dw.en",       "DW English"),
    ("cgtn.en",     "CGTN News"),
    ("bloomberg.us","Bloomberg TV"),
    ("france24.es", "FRANCE 24 Espanol"),
    ("dw.es",       "DW Espanol"),
    ("france24.fr", "FRANCE 24 Francais"),
    ("dw.de",       "DW Deutsch"),
    ("redbull.tv",  "Red Bull TV"),
    ("tagesschau",  "Tagesschau 24"),
    ("demo.cine",   "Cine Demo 24/7"),
    ("demo.bipbop", "Canal Test BipBop"),
    ("demo.hls",    "Canal Prueba HLS"),
    ("aljazeera.en","Al Jazeera English"),
    ("aljazeera.ar","Al Jazeera Arabic"),
    ("cbsnews.us",  "CBS News 24/7"),
    ("cna.sg",      "CNA Singapore"),
    ("wion.in",     "WION"),
    ("rtve24h.es",  "24 Horas (RTVE)"),
    ("trtworld",    "TRT World"),
    ("tv5monde.info","TV5Monde Info"),
    ("france24.ar", "FRANCE 24 Arabic"),
    ("arirang.kr",  "Arirang TV"),
    ("bloomberg.eu","Bloomberg TV Europe"),
    ("cgtndoc.en",  "CGTN Documentary"),
    ("bloombergqt.us","Bloomberg Originals"),
    ("tracesport.int","Trace Sport Stars"),
]

TITLES = {
    "france24.en": ["France 24 News","The World This Week","The Debate","Business Daily","Sport 24","The Interview","Encore!","Reporters","Down to Earth","Talking Europe","Eye on Africa","Access Asia"],
    "dw.en":       ["DW News","The Day","DW Business","Tomorrow Today","Euromaxx","Made in Germany","DocFilm","Sports Life","Arts Unveiled","Eco India","Close Up","Shift"],
    "cgtn.en":     ["CGTN News","The World Today","Global Business","Dialogue","Sports Scene","Culture Express","Tech It Out","The Hub","Full Frame","World Insight","China 24","Across China"],
    "bloomberg.us":["Bloomberg Markets","Balance of Power","Bloomberg Technology","Wall Street Week","Bloomberg Surveillance","The Close","Daybreak","Quicktake","Open Interest","Big Take","Markets Live","Businessweek"],
    "france24.es": ["Noticias France 24","El Debate","Economico","A Fondo","Reporteros","Entre Nosotros","Actualidad","Cultura","Mundo","Express","Aqui Europa","Sin Fronteras"],
    "dw.es":       ["DW Noticias","Al Dia","Economia","Enfoque Europa","Cultura 21","Hecho en Alemania","DocFilm","Vida Sana","En Forma","Global 3000","A Fondo","Camarera"],
    "france24.fr": ["Journal France 24","Le Debat","Economie","Reporters","Element Terre","L'Entretien","Paris Direct","Ici l'Europe","Le Gros Mot","Vous etes ici","Express Orient","A l'Affiche"],
    "dw.de":       ["DW Nachrichten","Der Tag","DW Wirtschaft","Tomorrow Today","Euromaxx","Made in Germany","DokFilm","Sportreportage","Kultur 21","Eco Africa","Close Up","Shift"],
    "redbull.tv":  ["Cliff Diving World Series","Surfing World Tour","Red Bull Rampage","Motocross Live","Freeski World Tour","Red Bull Air Race","Skate Generation","Crashed Ice","MotoGP Files","Who Is JOB","Danny MacAskill","The Ultimate Ride"],
    "tagesschau":  ["Tagesschau","Tagesschau24 Nachrichten","Bericht aus Berlin","Weltspiegel","Wirtschaft vor acht","Sportschau","Auslandsreport","Presseclub","Nachtmagazin","Morgenmagazin","Mittagsmagazin","Brennpunkt"],
    "demo.cine":   ["Cine continuo (demo)","Sesion de tarde (demo)","Clasicos sin cortes","Maraton de cine","Cine de medianoche","Pase VIP","Estrenos demo","Cine familiar","Sesion golfa","Doble sesion","Cine en casa","Palomitas 24/7"],
    "demo.bipbop": ["Patron de prueba BipBop","Test de color","Barras y tonos","Senal de referencia","Calibracion","Test A/V","Sincronia audio-video","Patron SMPTE","Prueba tecnica","Test de latencia","Diagnostico","Monitor de senal"],
    "demo.hls":    ["Stream de prueba HLS","Test adaptativo","Multi-bitrate demo","Prueba de segmentos","Ventana en vivo","Test de bufer","Latencia baja","Failover demo","Prueba de red","Stream continuo","Test 24/7","Senal estable"],
    "aljazeera.en":["Al Jazeera Newshour","Inside Story","The Stream","Witness","101 East","Counting the Cost","The Listening Post","People and Power","Talk to Al Jazeera","Fault Lines","Earthrise","Al Jazeera World"],
    "aljazeera.ar":["Nashrat Al Akhbar","Ma Wara Al Khabar","Al Ittijah Al Muakis","Bila Hudud","Shahid Ala Al Asr","Min Washington","Al Hasad","Hiwar Maftuh","Taht Al Mijhar","Al Waqe Al Arabi","Akhbar Al Iqtisad","Al Alam Hazā Al Sabah"],
    "cbsnews.us":  ["CBS News Roundup","CBS Mornings","America Decides","The Daily Report","CBS Evening News","Face the Nation","48 Hours","60 Minutes","CBS Weekend News","Eye on America","Prime Time","The Takeout"],
    "cna.sg":      ["Asia Now","Singapore Tonight","Asia First","East Asia Tonight","Money Mind","Insight","Talking Point","Undercover Asia","The Big Story","Commentary","Asia Business First","World Tonight"],
    "wion.in":     ["WION Newspoint","Gravitas","India Matters","World View","WION Fineprint","The West Asia Post","WION Sports","Global Leadership Series","Mission Sustainability","WION Wideangle","Business News","WION Live"],
    "rtve24h.es":  ["Telediario 24H","La tarde en 24H","Diario 24","La noche en 24H","Parlamento","Agrosfera","Informe Semanal","Emprende","Zoom Net","La manana en 24H","Economia 24","Deportes 24H"],
    "trtworld":    ["TRT World Now","Newsmakers","Strait Talk","Roundtable","Money Talks","Nexus","Bigger Than Five","Inside America","Off the Grid","Showcase","Across the Balkans","The Newsmakers Weekly"],
    "tv5monde.info":["Le Journal TV5Monde","64 minutes le monde en francais","L'Invite","Internationales","Kiosque","Afrique Presse","Terriennes","Objectif Monde","Maghreb-Orient Express","Destination Francophonie","Le Point Info","Journal du Soir"],
    "france24.ar": ["Mujaz France 24","Hiwar","Dayf wa Massira","Iqtisad","Riyada","Thaqafa","Alam Al Ghad","Nisf Saa Hawl Al Alam","Muraselo France 24","Fi Al Umq","Hasad Al Yaom","Panorama"],
    "arirang.kr":  ["Arirang News","The Point","Korea Today","Peninsula 24","Arirang Business","K-Culture Now","Music Bank Replay","Inside Korea","Diplomatic Talk","Tech Korea","Seoul Tonight","Global Insight"],
    "bloomberg.eu":["Bloomberg Daybreak Europe","Markets Today","The Pulse","Bloomberg Brief","European Close","UK Politics","Bloomberg Real Yield","In the City","Next Big Risk","ETF IQ Europe","Power Players","The Opening Trade"],
    "cgtndoc.en":  ["China Icons","Journeys in Nature","Age of Discovery","The Silk Road","Wild China","Megastructures","Taste of the Land","Time Honored","Voyage of Civilizations","Faces of Asia","Hidden Kingdoms","Living Heritage"],
    "bloombergqt.us":["The Circuit","Storylines","Bloomberg Originals Docs","Hello World","Next in Tech","The Future of Money","Venture","Good Business","Moonshot","City in the Sky","AI IRL","Game Changers"],
    "tracesport.int":["Legends of Football","Sport Stars Daily","Icons: Basketball","Champions Stories","The Golden Era","Rising Stars","Sport Docs","Hall of Fame","Match Point","Speed Kings","Boxing Greats","Olympic Dreams"],
}

# Ventana amplia para aguantar retrasos del cron: desde -4h hasta +20h (24 bloques de 1h).
HOURS_BACK = 4
SPAN = 24
now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
base = now - timedelta(hours=HOURS_BACK)

def fmt(dt): return dt.strftime("%Y%m%d%H%M%S") + " +0000"

lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv generator-info-name="OnePlay Demo EPG">']
for cid, name in CHANNELS:
    lines.append(f'  <channel id="{cid}"><display-name>{escape(name)}</display-name></channel>')
for cid, _ in CHANNELS:
    titles = TITLES[cid]
    for i in range(SPAN):
        s = base + timedelta(hours=i)
        e = base + timedelta(hours=i + 1)
        t = escape(titles[i % len(titles)])
        lines.append(f'  <programme start="{fmt(s)}" stop="{fmt(e)}" channel="{cid}">')
        lines.append(f'    <title>{t}</title>')
        lines.append(f'    <desc>{t} — en directo.</desc>')
        lines.append('  </programme>')
lines.append('</tv>')

with open("xmltv.xml", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"xmltv.xml generado: {len(CHANNELS)} canales, {len(CHANNELS)*SPAN} programas, ventana {fmt(base)} .. {fmt(base + timedelta(hours=SPAN))}")
