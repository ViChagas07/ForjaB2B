"""Normalizacao de consulta para os campos do catalogo (pt-BR e en).

O catalogo e indexado majoritariamente em pt-BR/en (com parte em es/ar). O
roteador devolve `query_pt`/`query_en` a partir de um dicionario deterministico
de conceitos; se nenhum conceito for reconhecido (ou o idioma nao tiver termo
confiavel), o LLM de classificacao preenche os campos. A consulta original
continua sendo enviada como sinal adicional.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.ai.application.lexicon import term_present
from app.modules.ai.domain.types import Locale

_L = Locale


@dataclass(frozen=True, kw_only=True)
class ProductConcept:
    pt: str
    en: str
    terms: dict[Locale, tuple[str, ...]]


PRODUCT_CONCEPTS: tuple[ProductConcept, ...] = (
    ProductConcept(
        pt="capacete",
        en="helmet",
        terms={
            _L.PT_BR: ("capacete", "capacetes"),
            _L.EN: ("helmet", "helmets"),
            _L.ES: ("casco", "cascos"),
            _L.DE: ("helm", "helme"),
            _L.FR: ("casque", "casques"),
            _L.IT: ("casco", "caschi"),
            _L.RU: ("шлем",),
            _L.AR: ("خوذة", "خوذات", "خوذ"),
            _L.JA: ("ヘルメット",),
            _L.KO: ("헬멧",),
            _L.ZH_CN: ("头盔", "頭盔"),
        },
    ),
    ProductConcept(
        pt="luvas",
        en="gloves",
        terms={
            _L.PT_BR: ("luva", "luvas"),
            _L.EN: ("glove", "gloves"),
            _L.ES: ("guante", "guantes"),
            _L.DE: ("handschuh", "handschuhe"),
            _L.FR: ("gant", "gants"),
            _L.IT: ("guanto", "guanti"),
            _L.RU: ("перчатк",),
            _L.AR: ("قفاز", "قفازات"),
            _L.JA: ("手袋", "グローブ"),
            _L.KO: ("장갑",),
            _L.ZH_CN: ("手套", "手袋"),
        },
    ),
    ProductConcept(
        pt="botas",
        en="boots",
        terms={
            _L.PT_BR: ("bota", "botas"),
            _L.EN: ("boot", "boots"),
            _L.ES: ("bota", "botas"),
            _L.DE: ("stiefel",),
            _L.FR: ("botte", "bottes"),
            _L.IT: ("stivale", "stivali"),
            _L.RU: ("сапог",),
            _L.AR: ("حذاء", "أحذية"),
            _L.JA: ("ブーツ",),
            _L.KO: ("부츠",),
            _L.ZH_CN: ("靴子",),
        },
    ),
    ProductConcept(
        pt="respirador",
        en="respirator",
        terms={
            _L.PT_BR: ("respirador", "respiradores"),
            _L.EN: ("respirator", "respirators", "mask"),
            _L.ES: ("respirador", "respiradores", "mascarilla"),
            _L.DE: ("atemschutzmaske", "atemschutzmasken", "maske"),
            _L.FR: ("respirateur", "respirateurs", "masque"),
            _L.IT: ("respiratore", "respiratori", "maschera"),
            _L.RU: ("респиратор", "маска"),
            _L.AR: ("جهاز تنفس", "كمامة"),
            _L.JA: ("マスク", "呼吸器"),
            _L.KO: ("마스크", "호흡기"),
            _L.ZH_CN: ("口罩", "呼吸器"),
        },
    ),
    ProductConcept(
        pt="oculos",
        en="goggles",
        terms={
            _L.PT_BR: ("oculos", "óculos", "protetor ocular"),
            _L.EN: ("goggles", "safety glasses", "eye protection"),
            _L.ES: ("gafas", "gafas de seguridad", "proteccion ocular", "protección ocular"),
            _L.DE: ("schutzbrille", "schutzbrillen", "brille"),
            _L.FR: ("lunettes de protection", "lunettes"),
            _L.IT: ("occhiali protettivi", "occhiali"),
            _L.RU: ("очки", "защитные очки"),
            _L.AR: ("نظارات", "نظارة"),
            _L.JA: ("ゴーグル", "保護メガネ", "メガネ"),
            _L.KO: ("고글", "보안경", "안경"),
            _L.ZH_CN: ("护目镜", "護目鏡", "眼镜", "眼鏡"),
        },
    ),
    ProductConcept(
        pt="protetor auricular",
        en="ear protection",
        terms={
            _L.PT_BR: ("abafador", "abafadores", "protetor auricular"),
            _L.EN: ("earmuff", "earmuffs", "ear protection", "hearing protection"),
            _L.ES: ("orejeras", "proteccion auditiva", "protección auditiva"),
            _L.DE: ("gehorschutz", "gehörschutz", "ohrenschutzer", "ohrenschützer"),
            _L.FR: ("protection auditive", "protecteur auditif", "bouchons d'oreille"),
            _L.IT: ("cuffie antirumore", "protezione uditiva"),
            _L.RU: ("наушник", "защита слуха"),
            _L.AR: ("واقي سمع", "حماية السمع"),
            _L.JA: ("耳栓", "防音"),
            _L.KO: ("귀마개", "청력 보호"),
            _L.ZH_CN: ("耳塞", "护耳", "護耳"),
        },
    ),
    ProductConcept(
        pt="cinto",
        en="belt",
        terms={
            _L.PT_BR: ("cinto", "cintos", "cinto de seguranca", "cinto de segurança"),
            _L.EN: ("belt", "belts", "harness"),
            _L.ES: ("cinturon", "cinturón", "cinturones", "arnes", "arnés"),
            _L.DE: ("gurtel", "gürtel", "gurt"),
            _L.FR: ("ceinture", "ceintures", "harnais"),
            _L.IT: ("cintura", "cinture", "imbracatura"),
            _L.RU: ("ремень", "ремн", "обвязка"),
            _L.AR: ("حزام", "أحزمة"),
            _L.JA: ("ベルト", "ハーネス"),
            _L.KO: ("벨트", "하네스"),
            _L.ZH_CN: ("腰带", "腰帶", "安全带", "安全帶"),
        },
    ),
    ProductConcept(
        pt="furadeira",
        en="drill",
        terms={
            _L.PT_BR: ("furadeira", "furadeiras"),
            _L.EN: ("drill", "drills"),
            _L.ES: ("taladro", "taladros"),
            _L.DE: ("bohrmaschine", "bohrmaschinen"),
            _L.FR: ("perceuse", "perceuses"),
            _L.IT: ("trapano", "trapani"),
            _L.RU: ("дрель", "дрел"),
            _L.AR: ("مثقاب", "مثاقب"),
            _L.JA: ("ドリル",),
            _L.KO: ("드릴",),
            _L.ZH_CN: ("电钻", "電鑽"),
        },
    ),
    ProductConcept(
        pt="serra",
        en="saw",
        terms={
            _L.PT_BR: ("serra", "serras"),
            _L.EN: ("saw", "saws"),
            _L.ES: ("sierra", "sierras"),
            _L.DE: ("sage", "säge", "sagen", "sägen"),
            _L.FR: ("scie", "scies"),
            _L.IT: ("sega", "seghe"),
            _L.RU: ("пила", "пилы"),
            _L.AR: ("منشار", "مناشير"),
            _L.JA: ("のこぎり",),
            _L.KO: ("톱",),
            _L.ZH_CN: ("锯子", "鋸子"),
        },
    ),
    ProductConcept(
        pt="martelo",
        en="hammer",
        terms={
            _L.PT_BR: ("martelo", "martelos"),
            _L.EN: ("hammer", "hammers"),
            _L.ES: ("martillo", "martillos"),
            _L.DE: ("hammer",),
            _L.FR: ("marteau", "marteaux"),
            _L.IT: ("martello", "martelli"),
            _L.RU: ("молоток", "молотк"),
            _L.AR: ("مطرقة", "مطارق"),
            _L.JA: ("ハンマー",),
            _L.KO: ("망치",),
            _L.ZH_CN: ("锤子", "錘子"),
        },
    ),
    ProductConcept(
        pt="alicate",
        en="pliers",
        terms={
            _L.PT_BR: ("alicate", "alicates"),
            _L.EN: ("pliers",),
            _L.ES: ("alicate", "alicates"),
            _L.DE: ("zange", "zangen"),
            _L.FR: ("pince", "pinces"),
            _L.IT: ("pinza", "pinze"),
            _L.RU: ("плоскогубц",),
            _L.AR: ("كماشة",),
            _L.JA: ("ペンチ",),
            _L.KO: ("펜치",),
            _L.ZH_CN: ("钳子", "鉗子"),
        },
    ),
    ProductConcept(
        pt="trena",
        en="tape measure",
        terms={
            _L.PT_BR: ("trena", "trenas"),
            _L.EN: ("tape measure", "measuring tape"),
            _L.ES: ("cinta metrica", "cinta métrica"),
            _L.DE: ("massband", "maßband"),
            _L.FR: ("metre ruban", "mètre ruban"),
            _L.IT: ("metro a nastro",),
            _L.RU: ("рулетк",),
            _L.AR: ("شريط قياس",),
            _L.JA: ("メジャー",),
            _L.KO: ("줄자",),
            _L.ZH_CN: ("卷尺",),
        },
    ),
    ProductConcept(
        pt="ferramenta",
        en="tool",
        terms={
            _L.PT_BR: ("ferramenta", "ferramentas"),
            _L.EN: ("tool", "tools"),
            _L.ES: ("herramienta", "herramientas"),
            _L.DE: ("werkzeug", "werkzeuge"),
            _L.FR: ("outil", "outils"),
            _L.IT: ("strumento", "strumenti"),
            _L.RU: ("инструмент",),
            _L.AR: ("أداة", "أدوات"),
            _L.JA: ("工具",),
            _L.KO: ("공구",),
            _L.ZH_CN: ("工具",),
        },
    ),
    ProductConcept(
        pt="equipamento",
        en="equipment",
        terms={
            _L.PT_BR: ("equipamento", "equipamentos"),
            _L.EN: ("equipment", "gear"),
            _L.ES: ("equipo", "equipos"),
            _L.DE: ("ausrustung", "ausrüstung", "ausstattung"),
            _L.FR: ("equipement", "équipement"),
            _L.IT: ("attrezzatura",),
            _L.RU: ("оборудован",),
            _L.AR: ("معدات",),
            _L.JA: ("装備",),
            _L.KO: ("장비",),
            _L.ZH_CN: ("装备", "裝備"),
        },
    ),
    ProductConcept(
        pt="produto",
        en="product",
        terms={
            _L.PT_BR: ("produto", "produtos"),
            _L.EN: ("product", "products"),
            _L.ES: ("producto", "productos"),
            _L.DE: ("produkt", "produkte"),
            _L.FR: ("produit", "produits"),
            _L.IT: ("prodotto", "prodotti"),
            _L.RU: ("товар", "продукт"),
            _L.AR: ("منتج", "منتجات"),
            _L.JA: ("製品", "商品"),
            _L.KO: ("제품", "상품"),
            _L.ZH_CN: ("产品", "產品", "商品"),
        },
    ),
    ProductConcept(
        pt="seguranca",
        en="safety",
        terms={
            _L.PT_BR: ("seguranca", "segurança"),
            _L.EN: ("safety",),
            _L.ES: ("seguridad",),
            _L.DE: ("sicherheit",),
            _L.FR: ("securite", "sécurité"),
            _L.IT: ("sicurezza",),
            _L.RU: ("безопасност",),
            _L.AR: ("أمان", "سلامة"),
            _L.JA: ("安全",),
            _L.KO: ("안전",),
            _L.ZH_CN: ("安全",),
        },
    ),
)


def normalize_query(message: str) -> tuple[str, str]:
    """Devolve (query_pt, query_en) a partir dos conceitos reconhecidos."""
    pt_terms: list[str] = []
    en_terms: list[str] = []
    for concept in PRODUCT_CONCEPTS:
        if any(term_present(message, term) for term in concept.terms[_L.PT_BR]):
            pt_terms.append(concept.pt)
            en_terms.append(concept.en)
            continue
        if any(
            term_present(message, term)
            for locale, terms in concept.terms.items()
            if locale not in (_L.PT_BR, _L.EN)
            for term in terms
        ):
            pt_terms.append(concept.pt)
            en_terms.append(concept.en)
            continue
        if any(term_present(message, term) for term in concept.terms[_L.EN]):
            pt_terms.append(concept.pt)
            en_terms.append(concept.en)
    return " ".join(dict.fromkeys(pt_terms)), " ".join(dict.fromkeys(en_terms))
