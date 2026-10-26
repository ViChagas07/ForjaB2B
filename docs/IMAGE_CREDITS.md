# Créditos das imagens (fotos e ilustrações)

As fotos de produto foram fornecidas pelo responsável, que declarou que **vêm do Pexels**.
Este projeto não consegue verificar licença nem origem: registramos **apenas o que é
dedutível** do nome do arquivo/EXIF e o que o responsável declarou. O que não é dedutível
fica como `[PREENCHER]` para o responsável completar.

Ferramentas/imagens de terceiros usadas como referência de desenho: nenhuma (as ilustrações
SVG são originais deste projeto — ver `docs/illustrations/ILLUSTRATION_CREDITS.md`).

## Fotos aplicadas no catálogo (frontend/public/catalog/photos/)

| Arquivo otimizado | SKU | Arquivo original | Autor | source_url | Licença | license_url |
|---|---|---|---|---|---|---|
| bot-001.webp | BOT-001 | botina-1242304473-30156647.jpg | [PREENCHER] | [PREENCHER] | Pexels License (declarado pelo responsável) | https://www.pexels.com/license/ |
| epi-cap-001.webp | EPI-CAP-001 | capacete-para-obra-38070.jpg | [PREENCHER] | [PREENCHER] | Pexels License (declarado pelo responsável) | https://www.pexels.com/license/ |
| maq-par-004.webp | MAQ-PAR-004 | furadeira-3877525.jpg | [PREENCHER] | [PREENCHER] | Pexels License (declarado pelo responsável) | https://www.pexels.com/license/ |
| que-001.webp | QUE-001 | kit-antiqueda-34019840.jpg | [PREENCHER] | [PREENCHER] | Pexels License (declarado pelo responsável) | https://www.pexels.com/license/ |
| luv-003.webp | LUV-003 | luva-de-obra-8488007.jpg | [PREENCHER] | [PREENCHER] | Pexels License (declarado pelo responsável) | https://www.pexels.com/license/ |
| res-006.webp | RES-006 | mascara-de-gas-3435524-5499417.jpg | [PREENCHER] | [PREENCHER] | Pexels License (declarado pelo responsável) | https://www.pexels.com/license/ |
| res-005.webp | RES-005 | máscara-respiradora-8487784.jpg | [PREENCHER] | [PREENCHER] | Pexels License (declarado pelo responsável) | https://www.pexels.com/license/ |
| aud-002.webp | AUD-002 | protetor-auricular-6791514.jpg | [PREENCHER] | [PREENCHER] | Pexels License (declarado pelo responsável) | https://www.pexels.com/license/ |
| ocv-003.webp | OCV-003 | óculos-de-obra51320673-8352127.jpg | [PREENCHER] | [PREENCHER] | Pexels License (declarado pelo responsável) | https://www.pexels.com/license/ |

## Fotos não aplicadas (para decisão do responsável — ver PHOTO_MAPPING.md)

| Arquivo original | Autor | source_url | Observação |
|---|---|---|---|
| bota-e-luva-de-obra-kindelmedia-8488037.jpg | "Kindel Media" (inferido do nome do arquivo — `kindelmedia-8488037`) | https://www.pexels.com/photo/8488037/ | Padrão `pexels-<autor>-<id>`; não aplicada (cena mista capacete + luvas). |
| kit-parafuso-7285983.jpg | "Karolina Grabowska (Kaboompics)" (inferido do EXIF Artist) | [PREENCHER] | Não aplicada (não existe produto do tipo). |
| colete-de-obra-436474929-17858119.jpg | [PREENCHER] | [PREENCHER] | Não aplicada (sem produto colete; rosto identificável). |
| régua-de-medição-5493674.jpg | [PREENCHER] | [PREENCHER] | Não aplicada (sem produto de medição). |
| turquesa-2160382064-36847981.jpg | [PREENCHER] | [PREENCHER] | Não aplicada (SKU incerto). |

## Registro de alterações nas fotos (pipeline)

Recorte quadrado central (ou composição em fundo neutro `#F4F2ED` quando o recorte cortaria
o objeto), redimensionamento para 640×640, conversão para WebP (qualidade adaptativa, ≤ 80 KB)
e **remoção total de metadados (EXIF/GPS)**. Processado por `scripts/optimize_catalog_photos.py`;
originais preservados em `assets-src/photos-inbox/` (ignorado pelo Git, não servido).
