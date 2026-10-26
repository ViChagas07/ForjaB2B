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
