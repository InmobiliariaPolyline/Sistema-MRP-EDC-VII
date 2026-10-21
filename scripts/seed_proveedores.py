"""Carga 10 proveedores de ejemplo con su catálogo (qué materiales ofrecen, si están disponibles y su precio unitario en soles).

Uso:
    python scripts/seed_proveedores.py              # muestra qué cargaría (no escribe)
    python scripts/seed_proveedores.py --execute    # carga de verdad

Los proveedores y sus precios son de referencia (basados en el mercado peruano de construcción), no cotizaciones reales.
Los contactos y correos son ficticios («ejemplo.pe»). Es idempotente: si un proveedor ya existe (mismo nombre) solo actualiza su
catálogo. Escribe en la misma base que usa la app (Supabase si hay credenciales en .env, si no el SQLite local).
El precio es por la primera unidad de la métrica del material (m³, m², kg, m o unidad)."""
import argparse
import hashlib
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from db import repository as repo  # noqa: E402
from utils.pricelist import normalize  # noqa: E402

# ---------------------------------------------------------------------------------------------------------------------
# Precio de referencia (S/ por la primera unidad de la métrica). Cada regla: (palabras que deben aparecer en el nombre, precio).
# Gana la primera que coincide; si ninguna, el precio por defecto de la categoría.
# ---------------------------------------------------------------------------------------------------------------------
PRICES: dict[str, tuple[float, list[tuple[tuple[str, ...], float]]]] = {
    "Acero y hierro": (6.0, [
        (("varilla",), 3.9), (("estructural", "a36"), 5.2), (("galvanizado",), 6.2), (("inoxidable", "304"), 24), (("inoxidable", "316"), 31),
        (("corten",), 8.5), (("calderer",), 5.0), (("steel stud",), 6.8), (("pretensado",), 9.5), (("cables",), 12), (("tuberia",), 48),
        (("anclaje roscada",), 9.5), (("fundido", "ductil"), 6.5), (("fundido", "gris"), 4.8), (("malla", "pavimento"), 32), (("malla",), 24),
        (("perfil laminado",), 5.6), (("perno",), 14), (("placa de anclaje",), 10.5),
    ]),
    "Aceros e instalaciones": (30.0, [
        (("bandeja",), 38), (("conduit", "pvc"), 3.8), (("conduit",), 9.5), (("inoxidable",), 165), (("gallinero",), 9.5), (("muro cortina",), 58),
        (("encofrado",), 85), (("andamio",), 22),
    ]),
    "Adhesivos y selladores": (6.0, [
        (("contacto", "neopreno"), 14), (("poliuretano", "madera"), 41800), (("epoxico",), 88000), (("cinta asfaltica",), 38), (("doble contacto",), 6.5),
        (("espuma",), 1800), (("masilla",), 3.2), (("mortero adhesivo",), 6.5), (("acrilico",), 3.0), (("poliazufre",), 7.5), (("poliuretano",), 6.5), (("silicona",), 5.5),
    ]),
    "Aislamiento": (45.0, [
        (("aerogel",), 420), (("algodon",), 1150), (("canamo",), 1400), (("poliester reciclado",), 900), (("yute",), 1100), (("oveja",), 1600),
        (("reflectivo",), 14), (("arcilla expandida",), 260), (("celulosa",), 800), (("corcho aglomerado",), 85), (("corcho expandido",), 120),
        (("melamina",), 75), (("proyectada", "poliuretano"), 65), (("fenolica",), 95), (("pir",), 78), (("lana de roca proyectada",), 55),
        (("lana de vidrio",), 12), (("lana mineral",), 24), (("fibra ceramica",), 140), (("fibra de coco",), 48), (("fibra de madera",), 70),
        (("vacio",), 380), (("perlita",), 420), (("silicato de calcio",), 160), (("eps",), 8.5), (("xps",), 22), (("pur",), 45), (("vermiculita",), 520),
    ]),
    "Carpintería de puertas y ventanas": (400.0, [
        (("pvc",), 38), (("cortafuego",), 780), (("marco de aluminio",), 46), (("marco de madera",), 32), (("persiana de aluminio",), 135),
        (("persiana de madera",), 160), (("mdf",), 340), (("madera maciza",), 780), (("vidrio templado",), 1450), (("metalica hueca",), 520),
    ]),
    "Concreto": (380.0, [
        (("adoquin",), 48), (("asfaltico",), 620), (("autocompactante",), 460), (("celular",), 380), (("ciclopeo",), 290), (("arcilla expandida",), 520),
        (("perlita",), 480), (("reciclados",), 310), (("alta resistencia",), 480), (("ultra alto",), 2800), (("lanzado",), 520),
        (("liviano estructural",), 450), (("liviano no estructural",), 420), (("pisos industriales",), 410), (("permeable",), 430), (("proyectado",), 540),
        (("fibra",), 410), (("translucido",), 12000), (("grout",), 1900), (("rodillo",), 270), (("autonivelante",), 24), (("mortero de cal",), 420),
        (("mortero de cemento",), 380), (("mortero de reparacion",), 2300), (("normal",), 340),
    ]),
    "Fachadas y revestimiento exterior": (200.0, [
        (("celosia",), 280), (("eifs",), 150), (("ladrillo",), 85), (("lama",), 55), (("termotratada",), 210), (("expandida",), 130), (("grc",), 260),
        (("hpl",), 380), (("ignifugo",), 340), (("cobre",), 950), (("policarbonato",), 120), (("zinc",), 780), (("piedra reconstituida",), 180),
        (("ceramico",), 135), (("corcho",), 190), (("piedra laminada",), 320), (("fibrocemento",), 95), (("vinilico",), 75),
    ]),
    "Fibras de refuerzo": (20.0, [
        (("acero",), 7.2), (("aramida",), 160), (("basalto",), 38), (("polipropileno",), 18), (("vidrio ar",), 22), (("fibra de carbono",), 190), (("malla",), 9),
    ]),
    "Geosintéticos": (14.0, [
        (("geocelda",), 28), (("geodren",), 18), (("biaxial",), 14), (("uniaxial",), 20), (("hdpe",), 24), (("pvc",), 26), (("georred",), 7),
        (("no tejido",), 5.5), (("tejido",), 9.5), (("antierosion",), 8),
    ]),
    "Madera": (3200.0, [
        (("aglomerado",), 38), (("contrachapado marino",), 120), (("contrachapado",), 62), (("mdf",), 48), (("osb",), 52), (("hdf",), 44),
        (("bambu laminado",), 150), (("cemento-madera",), 88), (("clt",), 4800), (("glulam",), 3900), (("thermowood",), 3600),
        (("bambu",), 650), (("pino",), 1300), (("abeto",), 1500), (("eucalipto",), 1100), (("alamo",), 1300), (("sauce",), 1200), (("aliso",), 1600),
        (("caucho",), 1700), (("tsuga",), 1900), (("cipres",), 1800), (("balsa",), 3000), (("marupa",), 1900), (("abedul",), 2400), (("cedro",), 2600),
        (("caoba",), 4800), (("teca",), 6500), (("ebano",), 18000), (("palo de rosa",), 12000), (("wengue",), 7500), (("zebrano",), 8200), (("bubinga",), 8800),
        (("padauk",), 7800), (("amaranto",), 7000), (("guayacan",), 9500), (("tigerwood",), 6200), (("merbau",), 5200), (("iroko",), 4600), (("sapelli",), 4300),
        (("jatoba",), 5000), (("quebracho",), 5600), (("ipe",), 5500), (("cumaru",), 5400), (("garapa",), 4300), (("massaranduba",), 4600),
        (("nogal",), 5500), (("roble",), 4200), (("haya",), 3000), (("fresno",), 3400), (("arce",), 3800), (("cerezo",), 4800), (("olmo",), 3300),
    ]),
    "Mampostería": (48.0, [
        (("adobe",), 160), (("tierra apisonada",), 190), (("cmu", "hueco"), 38), (("cmu", "macizo"), 44), (("celular",), 62), (("escoria",), 34),
        (("arcilla expandida",), 52), (("tierra comprimida",), 55), (("vidrio",), 380), (("silico",), 58), (("perlita",), 48), (("king kong",), 48),
        (("caravista",), 78), (("ceramico hueco",), 32), (("ceramico macizo",), 55), (("cal y arena",), 52), (("campo",), 28), (("ceniza",), 46),
        (("pandereta",), 30), (("refractario",), 190), (("tolete",), 35), (("piedra artificial",), 120),
    ]),
    "Materiales ignífugos y contrafuego": (110.0, [
        (("lana de roca",), 85), (("manta",), 160), (("mortero",), 110), (("vermiculita",), 230), (("intumescente",), 95), (("yeso reforzado",), 55),
        (("silicato",), 210), (("firestop",), 38000),
    ]),
    "Membranas textiles": (60.0, [
        (("lona",), 38), (("sombra",), 4.5), (("mosquitera",), 8), (("ptfe",), 360), (("etfe",), 420), (("tensoestructura",), 260),
    ]),
    "Metales no ferrosos": (40.0, [
        (("maraging",), 280), (("blindaje",), 60), (("aluminio-magnesio",), 24), (("6061",), 17), (("6063",), 15), (("anodizado",), 21), (("bronce",), 42),
        (("cobre patinado",), 720), (("cuproniquel",), 70), (("cobre",), 38), (("cromo",), 30), (("duraluminio",), 24), (("estano",), 95), (("inconel",), 190),
        (("laton naval",), 33), (("laton rojo",), 30), (("laton",), 28), (("magnesio",), 38), (("monel",), 150), (("niquel",), 80), (("plomo",), 9),
        (("titanio",), 120), (("zamak",), 14), (("zinc-titanio",), 640), (("zinc",), 11),
    ]),
    "Paisajismo y exteriores": (110.0, [
        (("arenero",), 75), (("corteza",), 120), (("grava de rio",), 140), (("grava decorativa",), 130), (("mulch",), 105), (("pasto",), 48),
        (("roca ornamental",), 95), (("muro verde",), 310), (("tierra de cultivo",), 95), (("adoquin",), 78),
    ]),
    "Paneles y compuestos": (250.0, [
        (("grc",), 270), (("hpl",), 360), (("alucobond",), 320), (("perforado",), 290), (("bambu",), 160), (("cobre",), 580), (("corcho",), 240),
        (("fibrocemento",), 98), (("piedra compuesta",), 520), (("zinc",), 480), (("eps",), 75), (("pur",), 98), (("termoacustico",), 105),
    ]),
    "Pavimentación vial": (120.0, [
        (("base granular",), 68), (("poroso",), 690), (("caliente",), 520), (("frio",), 560), (("micropavimento",), 18), (("articulado",), 62),
        (("rigido",), 420), (("riego de liga",), 3.2), (("slurry",), 9), (("sub-base",), 55),
    ]),
    "Piedra natural": (900.0, [
        (("adoquin",), 150), (("andesita",), 900), (("arenisca roja",), 1300), (("arenisca",), 1100), (("basalto columnar",), 260), (("basalto",), 1400),
        (("caliza coquina",), 650), (("caliza travertinada",), 230), (("caliza",), 900), (("cuarcita",), 1800), (("cuarzo compacto",), 380), (("dolomita",), 800),
        (("esteatita",), 2400), (("gneis",), 190), (("granito",), 2800), (("grauvaca",), 700), (("marmolina",), 300), (("marmol",), 3800), (("huamanga",), 340),
        (("berroquena",), 1500), (("piedra bola",), 160), (("chancada",), 95), (("de rio",), 110), (("laja negra",), 140), (("laja",), 85), (("gaviones",), 85),
        (("pomez",), 140), (("volcanica porosa",), 180), (("pizarra",), 150), (("serpentinita",), 420), (("sillar",), 450), (("toba",), 380),
        (("travertino",), 280), (("onix",), 620),
    ]),
    "Pisos técnicos y cielos rasos": (110.0, [
        (("pvc",), 38), (("fibra mineral",), 32), (("madera",), 160), (("metalica",), 120), (("fieltro",), 140), (("lana de madera",), 130),
        (("nucleo de acero",), 220), (("sulfato",), 240), (("perfil",), 8.5),
    ]),
    "Pisos y revestimientos": (90.0, [
        (("adoquin",), 68), (("yute",), 95), (("modular",), 90), (("alfombra",), 55), (("ceramica",), 36), (("linoleo",), 120), (("podotactil",), 160),
        (("ingenieria",), 190), (("moqueta",), 48), (("pasto",), 44), (("pvc homogeneo",), 110), (("bambu",), 140), (("deportivo",), 135), (("caucho",), 150),
        (("corcho",), 130), (("granito",), 280), (("hormigon",), 85), (("ladrillo",), 90), (("marmol",), 360), (("resina",), 160), (("terracota",), 85),
        (("epoxico",), 95), (("spc",), 78), (("laminado",), 62), (("lvt",), 88), (("porcelanato",), 78), (("terrazo",), 130),
    ]),
    "Plásticos y polímeros": (20.0, [
        (("abs",), 12), (("pmma",), 190), (("colado",), 240), (("baquelita",), 22), (("epdm",), 65), (("sbr",), 28), (("fibra de carbono",), 190),
        (("gfrp",), 26), (("frp",), 85), (("kevlar",), 280), (("melamina",), 55), (("nylon reforzado",), 30), (("nylon",), 22), (("pet",), 7), (("ptfe",), 95),
        (("pvc flexible",), 22), (("pvc rigido",), 8.5), (("pvdf",), 170), (("polibutileno",), 14), (("alveolar",), 58), (("policarbonato",), 95),
        (("poliestireno rigido",), 9), (("hdpe",), 9), (("pex",), 6.5), (("pom",), 26), (("polipropileno",), 8), (("poliuretano rigido",), 28), (("tpu",), 38),
        (("poliester",), 9800), (("epoxica",), 41800), (("silicona estructural",), 9.5), (("silicona",), 6.5),
    ]),
    "Prefabricados de concreto": (100.0, [
        (("adoquin",), 45), (("muro de contencion",), 85), (("bovedilla ceramica",), 3.2), (("bovedilla de poliestireno",), 4.5), (("alveolar",), 160),
        (("tilt-up",), 210), (("poste",), 480), (("traviesa",), 210), (("alcantarillado",), 140), (("vigueta",), 14),
    ]),
    "Suelos y áridos": (60.0, [
        (("leca",), 280), (("arcilla (suelo",), 38), (("fundicion",), 140), (("silice",), 180), (("asfalto",), 2800), (("balasto",), 75), (("bentonita",), 650),
        (("caliche",), 28), (("enrocado",), 85), (("escombro",), 18), (("grava calcarea",), 85), (("grava de rio",), 65), (("grava",), 70),
        (("hormigon reciclado",), 35), (("limo",), 32), (("marga",), 40), (("piedra triturada",), 75), (("relleno de cantera",), 45), (("tierra compactada",), 30),
        (("diatomeas",), 520), (("tierra suelta",), 22), (("tierra vegetal",), 65), (("turba",), 180), (("arena",), 55),
    ]),
    "Techos y membranas": (45.0, [
        (("canaleta de pvc",), 14), (("canaleta de aluminio",), 28), (("steel deck",), 62), (("chapa de aluminio",), 48), (("chapa de zinc",), 32), (("tpo",), 48),
        (("asfaltica impermeabilizante",), 24), (("pvc para techos",), 52), (("paja",), 18), (("sustrato",), 340), (("policarbonato",), 85), (("techo verde",), 190),
        (("teja asfaltica",), 38), (("teja de arcilla",), 42), (("teja de bambu",), 55), (("teja de concreto",), 36), (("ecologica",), 48), (("solar",), 420),
    ]),
    "Tuberías y conducciones": (20.0, [
        (("acero al carbono",), 52), (("acero galvanizado",), 58), (("cpvc",), 11), (("cobre",), 38), (("concreto",), 120), (("fibrocemento",), 38), (("gres",), 68),
        (("hierro fundido",), 210), (("pex",), 7.5), (("prfv",), 160), (("pvc presion",), 9.5), (("pvc sanitario",), 12), (("hdpe",), 14), (("corrugado",), 18),
        (("pp-r",), 12),
    ]),
    "Vidrio": (130.0, [
        (("espejo",), 98), (("acustico",), 240), (("antibalas",), 1450), (("armado",), 190), (("autolimpiante",), 210), (("curvo",), 480), (("low-e",), 260),
        (("seguridad estratificado",), 210), (("texturado",), 110), (("esmerilado",), 130), (("float",), 62), (("fotovoltaico",), 780), (("laminado",), 150),
        (("serigrafiado",), 230), (("templado",), 120), (("tintado",), 88),
    ]),
    "Yeso y placas": (35.0, [
        (("fibrocemento",), 34), (("acustico de yeso",), 48), (("vermiculita",), 62), (("grg",), 120), (("cement board",), 38), (("drywall", "estandar"), 21),
        (("ranurada",), 52), (("flexible",), 45), (("humedad",), 26), (("tipo x",), 32), (("mgo",), 58), (("revoque",), 12),
    ]),
}


def base_price(category: str, name: str) -> float:
    default, rules = PRICES.get(category, (30.0, []))
    text = normalize(name)
    for words, price in rules:
        if all(normalize(w) in text for w in words):
            return float(price)
    return float(default)


# ---------------------------------------------------------------------------------------------------------------------
# Proveedores: qué categorías cubren y con qué palabras (None = toda la categoría). `mult`: nivel de precios frente al de referencia.
# ---------------------------------------------------------------------------------------------------------------------
def _w(*words):
    return list(words)


SUPPLIERS = [
    {
        "name": "Sodimac Perú (Constructor)", "contact": "Marcos Delgado", "phone": "+51 987 410 220", "email": "empresas.sodimac@ejemplo.pe", "lead": 3, "minimum": 0, "mult": 1.08, "gone": 0.04,
        "notes": "Centro de mejoramiento del hogar y construcción: ferretería, acabados, sanitarios, techos y maderas. Despacho a obra.",
        "cover": {
            "Acero y hierro": _w("varilla", "malla", "galvanizado", "perfil laminado", "perno", "estructural", "anclaje"),
            "Aceros e instalaciones": _w("conduit", "gallinero", "andamio", "bandeja"),
            "Adhesivos y selladores": None,
            "Aislamiento": _w("lana de vidrio", "lana mineral", "eps", "xps", "pur", "reflectivo", "poliuretano"),
            "Carpintería de puertas y ventanas": None,
            "Concreto": _w("mortero de cemento", "autonivelante"),
            "Fibras de refuerzo": _w("polipropileno", "malla"),
            "Geosintéticos": _w("geotextil", "geomembrana", "geomalla"),
            "Madera": _w("pino", "eucalipto", "cedro", "contrachapado", "mdf", "osb", "aglomerado", "hdf", "caoba", "bambu"),
            "Mampostería": _w("king kong", "pandereta", "cmu", "ceramico", "tolete", "celular"),
            "Pisos y revestimientos": _w("ceramica", "porcelanato", "laminado", "lvt", "spc", "alfombra", "marmol", "granito", "terrazo", "epoxico", "caucho"),
            "Plásticos y polímeros": _w("pvc", "policarbonato", "acrilico", "silicona", "polietileno", "polipropileno", "melamina", "pex"),
            "Pisos técnicos y cielos rasos": _w("baldosa", "perfil"),
            "Suelos y áridos": _w("arena", "grava", "piedra triturada", "tierra vegetal", "tierra compactada"),
            "Techos y membranas": _w("chapa", "teja", "membrana", "canaleta", "policarbonato"),
            "Tuberías y conducciones": _w("pvc", "cpvc", "pex", "pp-r", "cobre", "hdpe", "corrugado"),
            "Vidrio": _w("float", "templado", "laminado", "espejo", "tintado", "esmerilado", "texturado"),
            "Yeso y placas": None,
            "Paisajismo y exteriores": _w("pasto", "grava", "corteza", "mulch", "tierra de cultivo", "arenero"),
        },
    },
    {
        "name": "Promart Homecenter", "contact": "Lucía Farfán", "phone": "+51 986 332 118", "email": "ventas.empresas.promart@ejemplo.pe", "lead": 2, "minimum": 0, "mult": 1.05, "gone": 0.05,
        "notes": "Cadena de ferretería y construcción: materiales de obra gruesa y acabados, con entrega en 48 horas.",
        "cover": {
            "Acero y hierro": _w("varilla", "malla", "galvanizado", "perfil laminado", "perno", "steel stud"),
            "Aceros e instalaciones": _w("conduit", "gallinero", "andamio", "bandeja"),
            "Adhesivos y selladores": _w("silicona", "acrilico", "poliuretano", "mortero adhesivo", "cinta", "espuma", "masilla"),
            "Aislamiento": _w("lana de vidrio", "eps", "xps", "reflectivo", "lana mineral"),
            "Carpintería de puertas y ventanas": _w("puerta", "marco", "persiana"),
            "Concreto": _w("mortero de cemento", "autonivelante", "mortero de reparacion"),
            "Geosintéticos": _w("geotextil", "geomembrana"),
            "Madera": _w("pino", "eucalipto", "cedro", "contrachapado", "mdf", "osb", "aglomerado", "hdf", "bambu"),
            "Mampostería": _w("king kong", "pandereta", "cmu", "ceramico", "tolete", "caravista"),
            "Pisos y revestimientos": _w("ceramica", "porcelanato", "laminado", "lvt", "spc", "alfombra", "terrazo", "pasto", "moqueta", "granito"),
            "Plásticos y polímeros": _w("pvc", "policarbonato", "acrilico", "silicona", "polietileno", "pex"),
            "Suelos y áridos": _w("arena", "grava", "piedra triturada", "tierra vegetal", "escombro"),
            "Techos y membranas": _w("chapa", "teja", "membrana", "canaleta", "policarbonato"),
            "Tuberías y conducciones": _w("pvc", "cpvc", "pex", "pp-r", "cobre", "hdpe"),
            "Vidrio": _w("float", "templado", "laminado", "espejo", "tintado"),
            "Yeso y placas": _w("drywall", "humedad", "tipo x", "fibrocemento", "cement board", "revoque"),
            "Paisajismo y exteriores": _w("pasto", "grava", "corteza", "mulch", "tierra de cultivo", "roca"),
        },
    },
    {
        "name": "Maestro Home Center", "contact": "Jorge Valdivia", "phone": "+51 985 224 770", "email": "corporativo.maestro@ejemplo.pe", "lead": 3, "minimum": 0, "mult": 1.10, "gone": 0.06,
        "notes": "Home center para obra y remodelación: ferretería, sanitarios, pisos, pinturas y techos.",
        "cover": {
            "Acero y hierro": _w("varilla", "malla", "galvanizado", "perfil laminado", "perno"),
            "Aceros e instalaciones": _w("conduit", "gallinero", "andamio"),
            "Adhesivos y selladores": _w("silicona", "acrilico", "poliuretano", "mortero adhesivo", "cinta", "masilla", "espuma"),
            "Aislamiento": _w("lana de vidrio", "eps", "xps", "reflectivo"),
            "Carpintería de puertas y ventanas": _w("puerta", "marco de", "persiana"),
            "Madera": _w("pino", "eucalipto", "cedro", "contrachapado", "mdf", "osb", "aglomerado", "hdf"),
            "Mampostería": _w("king kong", "pandereta", "cmu", "ceramico", "tolete"),
            "Pisos y revestimientos": _w("ceramica", "porcelanato", "laminado", "lvt", "spc", "alfombra", "terrazo", "pasto", "granito", "marmol"),
            "Plásticos y polímeros": _w("pvc", "policarbonato", "acrilico", "silicona", "polietileno", "pex"),
            "Suelos y áridos": _w("arena", "grava", "piedra triturada", "tierra vegetal"),
            "Techos y membranas": _w("chapa", "teja", "membrana", "canaleta", "policarbonato"),
            "Tuberías y conducciones": _w("pvc", "cpvc", "pex", "pp-r", "cobre"),
            "Vidrio": _w("float", "templado", "espejo", "tintado"),
            "Yeso y placas": _w("drywall", "humedad", "tipo x", "fibrocemento", "cement board", "revoque"),
            "Paisajismo y exteriores": _w("pasto", "grava", "corteza", "tierra de cultivo"),
        },
    },
    {
        "name": "Aceros Arequipa", "contact": "Ing. Renzo Calderón", "phone": "+51 984 118 305", "email": "ventas.proyectos.aceros@ejemplo.pe", "lead": 5, "minimum": 2500, "mult": 0.98, "gone": 0.03,
        "notes": "Fabricante de acero para construcción: barras corrugadas, mallas, perfiles, alambres y accesorios para obra gruesa.",
        "cover": {
            "Acero y hierro": None,
            "Aceros e instalaciones": _w("bandeja", "encofrado", "andamio", "gallinero", "muro cortina"),
            "Fibras de refuerzo": _w("acero"),
            "Metales no ferrosos": _w("zinc (planchas", "cobre", "laton", "bronce", "aluminio 6061", "aluminio 6063"),
            "Techos y membranas": _w("steel deck", "chapa de zinc"),
        },
    },
    {
        "name": "UNICON — Concreto Premezclado", "contact": "Ing. Patricia Salcedo", "phone": "+51 983 772 640", "email": "despacho.unicon@ejemplo.pe", "lead": 2, "minimum": 3500, "mult": 0.97, "gone": 0.0,
        "notes": "Concreto premezclado, morteros y agregados con despacho en mixer y bomba. Pedido mínimo por viaje.",
        "cover": {
            "Concreto": None,
            "Fibras de refuerzo": _w("polipropileno", "acero"),
            "Pavimentación vial": _w("base granular", "sub-base", "rigido", "caliente"),
            "Suelos y áridos": _w("arena", "grava", "piedra triturada", "hormigon reciclado", "escombro", "relleno", "enrocado", "balasto"),
            "Prefabricados de concreto": _w("vigueta", "losa alveolar", "bovedilla"),
            "Piedra natural": _w("chancada", "de rio", "bola", "gaviones"),
        },
    },
    {
        "name": "Cementos Pacasmayo (Prefabricados)", "contact": "Carlos Ramírez", "phone": "+51 982 664 119", "email": "comercial.pacasmayo@ejemplo.pe", "lead": 4, "minimum": 1800, "mult": 0.96, "gone": 0.04,
        "notes": "Cemento, concreto y prefabricados: bloques, adoquines, viguetas, postes, tuberías y paneles de hormigón.",
        "cover": {
            "Prefabricados de concreto": None,
            "Mampostería": _w("cmu", "celular", "arcilla expandida", "perlita", "escoria", "silico", "piedra artificial"),
            "Concreto": _w("adoquin", "mortero", "grout", "normal", "alta resistencia", "ciclopeo", "liviano", "permeable", "rodillo", "fibra", "proyectado"),
            "Pavimentación vial": _w("articulado", "rigido", "base granular", "sub-base"),
            "Yeso y placas": _w("fibrocemento", "cement board"),
            "Fachadas y revestimiento exterior": _w("grc", "fibrocemento", "piedra reconstituida"),
            "Paneles y compuestos": _w("grc", "fibrocemento"),
            "Tuberías y conducciones": _w("concreto", "fibrocemento"),
        },
    },
    {
        "name": "Ladrillera Lark", "contact": "Elena Quispe", "phone": "+51 981 553 207", "email": "ventas.ladrilleralark@ejemplo.pe", "lead": 4, "minimum": 1200, "mult": 0.95, "gone": 0.05,
        "notes": "Ladrillos, tejas y piezas de arcilla cocida para muros, techos y pisos. Venta por millar y despacho en camión.",
        "cover": {
            "Mampostería": _w("ladrillo", "adobe", "tierra comprimida", "tierra apisonada"),
            "Techos y membranas": _w("teja de arcilla", "teja de concreto", "teja ecologica", "teja de bambu"),
            "Pisos y revestimientos": _w("terracota", "ladrillo", "adoquin peatonal", "ceramica"),
            "Fachadas y revestimiento exterior": _w("ladrillo", "ceramico"),
            "Prefabricados de concreto": _w("bovedilla ceramica"),
            "Tuberías y conducciones": _w("gres"),
            "Suelos y áridos": _w("arcilla"),
        },
    },
    {
        "name": "Pavco Wavin", "contact": "Daniel Aguirre", "phone": "+51 980 441 892", "email": "ventas.pavco@ejemplo.pe", "lead": 3, "minimum": 1500, "mult": 0.97, "gone": 0.03,
        "notes": "Sistemas de tuberías y conducciones: agua, desagüe, drenaje, gas y conduit; geosintéticos y canaletas.",
        "cover": {
            "Tuberías y conducciones": None,
            "Plásticos y polímeros": _w("pvc", "polietileno", "polipropileno", "pex", "polibutileno", "abs", "pet", "policarbonato alveolar"),
            "Aceros e instalaciones": _w("conduit"),
            "Geosintéticos": _w("geomembrana", "geotextil", "geodren", "geocelda", "georred", "geomalla"),
            "Techos y membranas": _w("canaleta", "policarbonato"),
            "Prefabricados de concreto": _w("alcantarillado"),
        },
    },
    {
        "name": "Maderera Amazonas S.A.C.", "contact": "Walter Pezo", "phone": "+51 979 336 410", "email": "ventas.maderera.amazonas@ejemplo.pe", "lead": 6, "minimum": 1500, "mult": 0.94, "gone": 0.08,
        "notes": "Madera aserrada y tableros: especies de selva y exóticas, decking, contralaminada y laminada encolada. Venta por pie tablar y m³.",
        "cover": {
            "Madera": None,
            "Pisos y revestimientos": _w("bambu", "madera de ingenieria", "laminado", "corcho"),
            "Carpintería de puertas y ventanas": _w("madera", "mdf", "persiana de madera"),
            "Fachadas y revestimiento exterior": _w("madera termotratada", "lama", "corcho"),
            "Pisos técnicos y cielos rasos": _w("madera", "lana de madera"),
            "Paneles y compuestos": _w("bambu", "corcho"),
            "Aislamiento": _w("fibra de madera", "corcho"),
        },
    },
    {
        "name": "Acabados Premium Lima S.A.C.", "contact": "Valeria Montoya", "phone": "+51 978 220 515", "email": "proyectos.acabados.premium@ejemplo.pe", "lead": 8, "minimum": 2000, "mult": 1.15, "gone": 0.07,
        "notes": "Importador de acabados de alta gama: piedra natural, vidrio especial, fachadas, paneles, cielos rasos, ignífugos y aislamientos técnicos.",
        "cover": {
            "Piedra natural": None,
            "Vidrio": None,
            "Fachadas y revestimiento exterior": None,
            "Paneles y compuestos": None,
            "Pisos técnicos y cielos rasos": None,
            "Materiales ignífugos y contrafuego": None,
            "Membranas textiles": None,
            "Aislamiento": _w("aerogel", "vacio", "silicato", "fenolica", "pir", "melamina", "ceramica", "corcho", "foil", "lana de roca", "algodon", "canamo", "oveja", "yute", "poliester"),
            "Pisos y revestimientos": _w("marmol", "granito", "terrazo", "epoxico", "resina", "linoleo", "podotactil", "bambu", "caucho", "corcho"),
            "Metales no ferrosos": None,
            "Carpintería de puertas y ventanas": _w("aluminio", "vidrio", "cortafuego", "pvc"),
            "Aceros e instalaciones": _w("muro cortina", "inoxidable"),
            "Paisajismo y exteriores": _w("roca", "sustrato", "adoquin", "grava de rio", "pasto"),
            "Techos y membranas": _w("solar", "techo verde", "sustrato", "tpo", "pvc para techos", "aluminio"),
            "Plásticos y polímeros": _w("acrilico", "pvdf", "kevlar", "fibra de carbono", "ptfe", "nylon", "pom", "tpu", "resina", "baquelita"),
            "Fibras de refuerzo": _w("aramida", "basalto", "carbono", "vidrio ar"),
        },
    },
]


def _unit(*parts: str) -> float:
    """Un número estable entre 0 y 1 para esa combinación (siempre el mismo para el mismo proveedor y material)."""
    return int.from_bytes(hashlib.sha256("|".join(parts).encode()).digest()[:4], "big") / 2**32


def _noise(*parts: str, spread: float = 0.06) -> float:
    """Variación estable de ±spread."""
    return 1 + (_unit(*parts) * 2 - 1) * spread


def _chosen(supplier: dict, materials: list[dict]) -> list[dict]:
    out = []
    for m in materials:
        category = m["category"]
        if category not in supplier["cover"]:
            continue
        words = supplier["cover"][category]
        text = normalize(m["name"])
        if words is None or any(normalize(w) in text for w in words):
            out.append(m)
    return out


def build_catalogs(materials: list[dict]) -> dict[str, list[dict]]:
    """{nombre del proveedor: [{"material": fila, "price": S/, "available": bool}]} listo para cargar."""
    result = {}
    for supplier in SUPPLIERS:
        rows = []
        for m in _chosen(supplier, materials):
            price = base_price(m["category"], m["name"]) * supplier["mult"] * _noise(supplier["name"], m["id"] if "id" in m else m["name"])
            price = round(price, 2) if price < 1000 else round(price, 0)
            gone = _unit(supplier["name"], m["name"], "agotado") < supplier["gone"]
            rows.append({"material": m, "price": max(price, 0.1), "available": not gone})
        result[supplier["name"]] = rows
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--execute", action="store_true", help="cargar de verdad")
    args = parser.parse_args()

    materials = repo.list_materials().to_dict("records")
    catalogs = build_catalogs(materials)
    print(f"Base: {'SQLite local' if repo.USING_LOCAL else 'Supabase'} · {len(materials)} materiales en el catálogo\n")
    covered = set()
    for supplier in SUPPLIERS:
        rows = catalogs[supplier["name"]]
        covered |= {r["material"]["id"] for r in rows}
        gone = sum(not r["available"] for r in rows)
        print(f"  {supplier['name']:<40}{len(rows):>4} materiales ({gone} agotados) · plazo {supplier['lead']} d · mínimo S/ {supplier['minimum']}")
    print(f"\nMateriales con al menos un proveedor: {len(covered)} de {len(materials)} ({len(covered) / len(materials):.0%}). El resto queda sin proveedor, que es normal.")
    if not args.execute:
        print("\nNo se escribió nada. Para cargar: python scripts/seed_proveedores.py --execute")
        return 0

    existing = {r["name"]: r["id"] for r in repo.list_suppliers().to_dict("records")}
    for supplier in SUPPLIERS:
        repo.upsert_supplier(
            supplier["name"], supplier["contact"], supplier["phone"], supplier["email"], supplier["notes"], existing.get(supplier["name"]),
            supplier["lead"], float(supplier["minimum"]) if supplier["minimum"] else None,
        )
    ids = {r["name"]: r["id"] for r in repo.list_suppliers().to_dict("records")}
    for supplier in SUPPLIERS:
        supplier_id = ids[supplier["name"]]
        rows = catalogs[supplier["name"]]
        repo.bulk_set_supplier_prices(supplier_id, [{"material_id": r["material"]["id"], "price": r["price"]} for r in rows], make_available=True)
        for r in rows:
            if not r["available"]:
                repo.set_supplier_material(supplier_id, r["material"]["id"], True, False, r["price"])
        print(f"  cargado: {supplier['name']} ({len(rows)} materiales)")
    print("\nListo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
