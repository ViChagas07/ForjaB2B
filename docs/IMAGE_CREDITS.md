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

---

## Lote 2 — fotos nomeadas por produto (2026-10-26)

Origem declarada pelo responsável ao enviá-las: destinam-se aos produtos do catálogo
(nomes de produto no arquivo). A licença/origem de cada uma permanece **[PREENCHER]**
quando não dedutível; onde o EXIF Artist/Copyright indica autor, registro como
"inferido do EXIF" (sem verificação independente de licença). Saídas otimizadas
(640×640 WebP ≤ 80 KB, sem EXIF/GPS) em `frontend/public/catalog/photos/`; originais
em `assets-src/photos-inbox/`.

| Saída (SKU) | Arquivo original | Autor | source_url | Licença | license_url |
|---|---|---|---|---|---|
| aud-003.webp | Abafador de Ruído Acoplado ao Capacete.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| maq-009.webp | Bomba d'Água Autoaspirante.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| bot-002.webp | Bota de Segurança Bico Composite.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| bot-003.webp | Botas de Segurança Impermeáveis.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| bot-004.webp | Botina Eletricista.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| cap-002.webp | Capacete de Segurança Classe A Aba Frontal.webp | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| cap-003.webp | Capacete de Segurança Classe B com Jugular.webp | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| cap-004.webp | Capacete de Segurança Conjugado.webp | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| cap-005.webp | Capacete de Segurança Descontinuado.png | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| que-003.webp | Cinturão de Segurança Abdominal.webp | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| maq-005.webp | Compressor de Ar 100L.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| fur-003.webp | Esmerilhadeira Angular 115mm.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| fur-001.webp | Furadeira de Impacto 850W.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| fur-002.webp | Furadeiras de Bancada 500W.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| luv-007.webp | Luva Anticorte Nível 5.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| luv-008.webp | Luva de Látex Forrada.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| epi-luv-002.webp | Luva de Raspa Premium.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| luv-006.webp | Luva de Vaqueta Petroleira.jpg | Jonathan Cooper (inferido do EXIF Artist) | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| luv-005.webp | Luva Nitrílica Descartável.jpg | Anton Shoutvin (inferido do EXIF Artist) | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| res-007.webp | Máscara de Proteção PFF1.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| ocv-002.webp | Oculos de Proteção Fumê.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| maq-007.webp | Politriz de Bancada.jpg | AdventistAsia (inferido do EXIF Copyright; Artist continha placeholder) | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| maq-006.webp | Prensa Hidráulica 15T.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| aud-001.webp | Protetor Auricular Plug Silicone.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| res-008.webp | Respirador Panorâmico.jpg | [PREENCHER] (EXIF Artist vazio) | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| epi-res-003.webp | Respirador PFF2.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| fur-005.webp | Retífica Reta 500W.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| bot-005.webp | Sapato de Segurança Sport.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| fur-004.webp | Serra Circular 7 14.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| maq-008.webp | Serra de Bancada 10.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| que-002.webp | Talabarte Duplo I e Y.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| maq-010.webp | Torno de Bancada.jpg | Lars H. Knudsen (inferido do EXIF Artist/Copyright) | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| que-004.webp | Trava Queda Deslizante.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| ocv-001.webp | Óculos de Proteção Incolor.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| ocv-005.webp | Óculos de Proteção para Sobrepor.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| ocv-004.webp | Óculos de Segurança Antiembaçante.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |

---

## Lote 3 — variantes com a mesma foto do responsável (2026-10-27)

A MESMA foto fornecida pelo responsável (já registrada no Lote 2) aplicada também nas
variantes do produto, a pedido do dono ("ponha as imagens que lhe solicitei adequadamente
nelas"). Origem/autor/licença: idênticos à entrada do Lote 2 do arquivo original.

| Saída (SKU) | Arquivo original | Autor | source_url | Licença | license_url |
|---|---|---|---|---|---|
| aud-004.webp | Protetor Auricular Plug Silicone.jpg (mesma foto do Lote 2) | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| luv-004.webp | Luva de Raspa Premium.jpg (mesma foto do Lote 2) | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |

---

## Lote 4 � fotos do responsável (2026-10-28)

Fotos fornecidas pelo dono do projeto com o nome do produto no arquivo
("guie-se pelo nome da imagem"). Substituem as saídas do Lote 3 e estreiam a
foto do RES-004. Origem/autor/licença: a confirmar pelo responsável (mesmo
padrão dos lotes anteriores).

| Saída (SKU) | Arquivo original | Autor | source_url | Licença | license_url |
|---|---|---|---|---|---|
| luv-004.webp | Luvas de Raspa Premium.webp | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| aud-004.webp | Protetor Auricular Plug Moldável.jpg | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
| res-004.webp | Respirador PFF2 Sem Válvula.webp | [PREENCHER] | [PREENCHER] | [PREENCHER] | [PREENCHER] |
