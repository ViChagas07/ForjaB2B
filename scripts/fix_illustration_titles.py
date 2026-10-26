"""Reescreve os <title> corrompidos pelo SVGO no Windows (one-off)."""

from pathlib import Path
import re

TITLES = {
    "abafador-capacete": "Abafador acoplado ao capacete",
    "bomba-agua": "Bomba d'água autoaspirante",
    "bota-de-seguranca": "Bota de segurança",
    "botina": "Botina de segurança",
    "capacete-de-seguranca": "Capacete de segurança",
    "cinto-seguranca": "Cinturão de segurança",
    "compressor": "Compressor de ar",
    "esmerilhadeira": "Esmerilhadeira angular",
    "furadeira": "Furadeira de impacto",
    "furadeira-de-bancada": "Furadeira de bancada",
    "luva-anticorte": "Luva anticorte",
    "luva-de-raspa": "Luva de raspa",
    "luva-latex": "Luva de látex forrada",
    "luva-nitrilica": "Luva nitrílica descartável",
    "mascara-descartavel": "Máscara descartável PFF",
    "oculos-de-protecao": "Óculos de proteção",
    "politriz": "Politriz de bancada",
    "prensa-hidraulica": "Prensa hidráulica",
    "protetor-plug": "Protetor auricular tipo plug",
    "respirador-panoramico": "Respirador panorâmico",
    "retifica": "Retífica reta",
    "sapato-de-seguranca": "Sapato de segurança",
    "serra-circular": "Serra circular",
    "serra-de-bancada": "Serra de bancada",
    "talabarte": "Talabarte",
    "trava-queda": "Trava-queda",
}

for key, title in TITLES.items():
    path = Path(f"frontend/public/catalog/illustrations/{key}.svg")
    text = path.read_text(encoding="utf-8")
    new = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", text, count=1)
    if new != text:
        path.write_text(new, encoding="utf-8")
        print(f"corrigido: {key}.svg")
print("ok")
