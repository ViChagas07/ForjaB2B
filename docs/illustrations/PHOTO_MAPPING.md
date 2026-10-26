# Mapeamento foto → produto (Prompt 10, Parte A1)

Fotos fornecidas pelo responsável em `frontend/public/brand/` (origem declarada: Pexels).
Classificação por **conteúdo** (as imagens foram inspecionadas visualmente) cruzada com o
**nome do arquivo**. Regras aplicadas: uma foto por produto, um produto por foto, nunca
produto de tipo diferente. Critério para vários produtos do mesmo tipo: o mais genérico ou
o de formato mais próximo do conteúdo da foto (critério registrado por linha).

## Aplicadas (confiança alta)

| Arquivo | Classificação (conteúdo) | SKU escolhido | Confiança | Motivo / critério |
|---|---|---|---|---|
| botina-1242304473-30156647.jpg | Botina de segurança (couro camurça, cano curto, cadarço) | BOT-001 | Alta | Nome do arquivo diz "botina" e o conteúdo mostra botinas de couro; escolhido o produto mais genérico do tipo ("Botina de Segurança Couro"). BOT-002/BOT-003 são "Bota" (cano alto), BOT-004 é variante eletricista. |
| capacete-para-obra-38070.jpg | Capacete de segurança (parede com vários, aba frontal) | EPI-CAP-001 | Alta | Conteúdo inconfundível (capacetes); escolhido o produto mais genérico do tipo ("Capacete de Segurança Pro", seed base). CAP-002/003/004 têm variações específicas (classe/jugular/conjugado). |
| furadeira-3877525.jpg | Parafusadeira de impacto a bateria 20 V | MAQ-PAR-004 | Alta | **O nome do arquivo diz "furadeira", mas o conteúdo mostra parafusadeira de impacto a bateria** (bateria "20V MAX" visível, mandril hexagonal com bit). Nunca associar a FUR-001 (furadeira de impacto 850 W com cabo) seria erro de tipo. Escolhido o produto exato do tipo/spec. |
| kit-antiqueda-34019840.jpg | Cinto paraquedista (arnês completo vestido) | QUE-001 | Alta | Conteúdo mostra arnês tipo paraquedista de corpo inteiro; nome do arquivo reforça ("kit antiqueda"). QUE-001 é o cinto paraquedista genérico. |
| luva-de-obra-8488007.jpg | Luvas de trabalho (3 luvas sintéticas exibidas) | LUV-003 | Alta | Conteúdo mostra luvas de trabalho com dedos e punho; tipo coincide ("luva"). Escolhido o produto mais genérico do tipo ("Luva de Raspa de Couro"). Obs.: o material da foto parece sintético, não couro — registrado. |
| mascara-de-gas-3435524-5499417.jpg | Respirador semifacial com dois filtros | RES-006 | Alta | Conteúdo mostra semifacial com **dois filtros roscados** — coincide com "Respirador Semifacial Duplo Filtro". Não é panorâmico (não cobre o rosto todo). |
| máscara-respiradora-8487784.jpg | Respirador descartável tipo concha **com válvula** | RES-005 | Alta | Conteúdo mostra concha descartável com válvula de exalação visível; RES-004 é "Sem Válvula" (contradiz a foto), RES-005 é o único "com Válvula". |
| protetor-auricular-6791514.jpg | Protetor auricular tipo concha (arco + conchas) | AUD-002 | Alta | Conteúdo mostra conchas com arco cervical/cabiliar; coincide com "Protetor Auricular Tipo Concha". Não é plug (que não tem arco/concha). |
| óculos-de-obra51320673-8352127.jpg | Óculos de proteção ampla visão (lente única + elástico) | OCV-003 | Alta | Conteúdo mostra óculos de lente única ampla com elástico; escolhido o produto de formato mais próximo ("Óculos de Proteção Ampla Visão"). OCV-001/002 são armação convencional, OCV-005 é para sobrepor. |

## Não aplicadas — decisão do responsável

| Arquivo | Classificação (conteúdo) | Motivo de não aplicar | Sugestão |
|---|---|---|---|
| bota-e-luva-de-obra-kindelmedia-8488037.jpg | Cena mista: **capacete amarelo + par de luvas vermelhas** (sem bota na imagem, apesar do nome) | Não corresponde a um único tipo de produto; recorte central destacadamente mostraria um dos objetos cortados. As luvas são as mesmas da foto `luva-de-obra` (Firm Grip vermelha). | Decidir se vira foto de alguma luva (ex.: LUV-004) com composição em fundo neutro, ou descartar. |
| colete-de-obra-436474929-17858119.jpg | Colete refletivo laranja vestido (rosto identificável) | **Não existe produto "colete" no seed.** Regra: nunca associar a produto de tipo diferente. Rosto de pessoa identificável na foto. | Criar produto de colete refletivo ou descartar. |
| kit-parafuso-7285983.jpg | Maleta com brocas e parafusos | Não existe produto "kit de brocas/parafusos" no seed. Crédito do autor derivável do EXIF Artist (Karolina Grabowska / Kaboompics). | Criar produto de acessórios ou descartar. |
| régua-de-medição-5493674.jpg | Nível de bolha em uso sobre drywall | Não existe produto de medição/nível no seed. | Criar produto ou descartar. |
| turquesa-2160382064-36847981.jpg | Luva de couro laranja (raspa) em uso com alicate | Tipo certo (luva de couro), mas o SKU é incerto entre LUV-004 ("Luvas de Raspa Premium") e LUV-006 ("Luva de Vaqueta Petroleira"); nome do arquivo não ajuda. Confiança baixa para o SKU. | Decidir entre LUV-004 e LUV-006 (ou descartar). |

Confiança "alta" = tipo do produto inconfundível no conteúdo E produto coincidente por
nome/formato registrado acima. Confiança "baixa" = tipo certo, SKU exato incerto.

---

## Lote 2 — fotos nomeadas pelo próprio produto (decisão do responsável, 2026-10-26)

O responsável forneceu fotos para os produtos que estavam com ilustração, nomeando cada
arquivo com o nome do produto de destino (`frontend/public/catalog/photos/`, hoje
arquivado em `assets-src/photos-inbox/`). Todas as 36 foram **inspecionadas
visualmente**: o conteúdo bate com o nome/produto (nenhum produto de tipo diferente).
Critérios de desempate registrados abaixo. O pipeline
(`scripts/optimize_catalog_photos.py`) gerou 640×640 WebP ≤ 80 KB sem EXIF/GPS,
idempotente; modo `fit` = composição em fundo neutro (o recorte central cortaria o
objeto), `crop` = recorte quadrado central.

| Arquivo original | SKU | Confiança | Motivo / critério |
|---|---|---|---|
| Abafador de Ruído Acoplado ao Capacete.jpg | AUD-003 | Alta | Nome exato; concha + arco no capacete visíveis. |
| Bomba d'Água Autoaspirante.jpg | MAQ-009 | Alta | Nome exato; bomba com voluta e motor. |
| Bota de Segurança Bico Composite.jpg | BOT-002 | Alta | Nome exato; botas de trabalho. |
| Botas de Segurança Impermeáveis.jpg | BOT-003 | Alta | Nome exato; botas de borracha impermeáveis. |
| Botina Eletricista.jpg | BOT-004 | Alta | Nome exato; botina de couro. |
| Capacete de Segurança Classe A Aba Frontal.webp | CAP-002 | Alta | Nome exato; aba frontal visível. |
| Capacete de Segurança Classe B com Jugular.webp | CAP-003 | Alta | Nome exato; jugular visível. |
| Capacete de Segurança Conjugado.webp | CAP-004 | Alta | Nome ≈ exato ("Conjugado(s)"); capacete com viseira + abafador acoplados. |
| Capacete de Segurança Descontinuado.png | CAP-005 | Alta | Nome exato (produto INACTIVE; foto aplicada por consistência). |
| Cinturão de Segurança Abdominal.webp | QUE-003 | Alta | Nome exato; cintura com D-rings (modo fit: recorte cortaria os anéis). |
| Compressor de Ar 100L.jpg | MAQ-005 | Alta | Nome exato; tanque + motor. |
| Esmerilhadeira Angular 115mm.jpg | FUR-003 | Alta | Nome exato; disco + corpo. |
| Furadeira de Impacto 850W.jpg | FUR-001 | Alta | Nome exato; furadeira pistola (modo fit: recorte cortaria o corpo). |
| Furadeiras de Bancada 500W.jpg | FUR-002 | Alta | Nome exato; prensa-furadeira de bancada. |
| Luva Anticorte Nível 5.jpg | LUV-007 | Alta | Nome exato; malha anticorte com faca. |
| Luva de Látex Forrada.jpg | LUV-008 | Alta | Nome exato; luva amarela de látex. |
| Luva de Raspa Premium.jpg | EPI-LUV-002 | Alta | **Nome exato singular "Luva de Raspa Premium" = produto base EPI-LUV-002**; LUV-004 ("Luvas", plural) mantém ilustração. |
| Luva de Vaqueta Petroleira.jpg | LUV-006 | Alta | Nome exato; couro com punho de segurança. |
| Luva Nitrílica Descartável.jpg | LUV-005 | Alta | Nome exato; nitrílica azul descartável (modo fit). |
| Máscara de Proteção PFF1.jpg | RES-007 | Alta | Nome exato; máscara PFF vestida. |
| Oculos de Proteção Fumê.jpg | OCV-002 | Alta | Nome ≈ exato ("Oculos" sem acento no arquivo); lente fumê visível. |
| Politriz de Bancada.jpg | MAQ-007 | Alta | Nome exato; rebolo/politriz de bancada. |
| Prensa Hidráulica 15T.jpg | MAQ-006 | Alta | Nome exato; prensa com colunas. |
| Protetor Auricular Plug Silicone.jpg | AUD-001 | Alta | Nome exato; plug de silicone no ouvido. |
| Respirador Panorâmico.jpg | RES-008 | Alta | Nome exato; máscara de rosto inteiro (modo fit). |
| Respirador PFF2.jpg | EPI-RES-003 | Alta | **Nome exato "Respirador PFF2" = produto base EPI-RES-003**; RES-004 ("...Sem Válvula") mantém ilustração. |
| Retífica Reta 500W.jpg | FUR-005 | Alta | Nome exato; retífica reta. |
| Sapato de Segurança Sport.jpg | BOT-005 | Alta | Nome exato; sapato esportivo de segurança. |
| Serra Circular 7 14.jpg | FUR-004 | Alta | Nome ≈ exato ("7 1/4" sem a barra); lâmina de serra circular (modo fit). |
| Serra de Bancada 10.jpg | MAQ-008 | Alta | Nome exato; serra de bancada em uso. |
| Talabarte Duplo I e Y.jpg | QUE-002 | Alta | Nome exato; talabarte/ganchos em uso na bolsa transversal. |
| Torno de Bancada.jpg | MAQ-010 | Alta | Nome = produto "Torno de Bancada Descontinuado" (INACTIVE; foto aplicada por consistência). |
| Trava Queda Deslizante.jpg | QUE-004 | Alta | Nome exato; sistema de retenção em uso. |
| Óculos de Proteção Incolor.jpg | OCV-001 | Alta | Nome exato; lente incolor (modo fit). |
| Óculos de Proteção para Sobrepor.jpg | OCV-005 | Alta | Nome exato; óculos amplo sobre armação. |
| Óculos de Segurança Antiembaçante.jpg | OCV-004 | Alta | Nome exato; óculos amplo antiembaçante. |

Cobertura resultante: **45 de 50 produtos com foto real**; ilustrações específicas
remanescentes: LUV-004, RES-004, OCV-006 e LUV-009 (todos sem foto fornecida;
LUV-004/RES-004 ativos). Nenhum produto ativo usa mais o fallback de categoria — que
segue existindo como última rede de segurança (`resolve_product_image_path`).
