# Famílias de ilustração por produto (Prompt 10, Parte B1)

Ilustrações vetoriais SVG no estilo **ícone de linha duotone** (traço branco arredondado
`#F8FAFC` com **um** acento laranja `#F97316` sobre ladrilho escuro `#0F172A`), a mesma
linguagem visual dos SVGs de categoria de `backend/app/static/catalog/`. Não existe uma
biblioteca que as gere: cada arquivo foi desenhado como código SVG original deste projeto
(sem cópia de conjuntos de terceiros — ver `ILLUSTRATION_CREDITS.md`).

Prioridade no seed: **foto > ilustração > imagem da categoria**. A foto real é definida em
`PHOTO_MAPPING.md`; esta tabela cobre os produtos SEM foto.

| Chave (arquivo) | SKUs que a usam | Descrição do objeto desenhado |
|---|---|---|
| capacete-de-seguranca | CAP-002, CAP-003, CAP-004, CAP-005 | Capacete de segurança com aba frontal e crista de ventilação (aba em acento). |
| oculos-de-protecao | OCV-001, OCV-002, OCV-004, OCV-005, OCV-006 | Óculos de proteção de lente ampla com elástico nas duas laterais (elástico em acento). |
| luva-de-raspa | EPI-LUV-002, LUV-004, LUV-006, LUV-009 | Luva de couro com cinco dedos, polegar e punho de seguranca; faixa do punho em acento. |
| luva-nitrilica | LUV-005 | Luva descartavel fina, dedos longos e punho reto curto; linha do punho em acento. |
| luva-anticorte | LUV-007 | Luva tricotada com faixa pontilhada de aderência no dorso (pontos em acento). |
| luva-latex | LUV-008 | Luva de látex forrada com punho longo reto (gauntlet); linha inferior do punho em acento. |
| mascara-descartavel | EPI-RES-003, RES-004, RES-007 | Respirador descartável tipo concha com tiras laterais e costura nasal (costura em acento). |
| respirador-panoramico | RES-008 | Máscara de rosto inteiro com viseira, válvula/falante inferior e tiras (viseira interna em acento). |
| protetor-plug | AUD-001, AUD-004 | Par de plugs (cápsulas) ligados por cordão em U (cordão em acento). |
| abafador-capacete | AUD-003 | Conchas protetoras suspensas no arco/crista de capacete (conchas em acento). |
| botina | BOT-004 | Botina (cano curto) com duas fileiras de cadarços e sola destacada (sola em acento). |
| bota-de-seguranca | BOT-002, BOT-003 | Bota de cano alto com três fileiras de cadarços e sola destacada (sola em acento). |
| sapato-de-seguranca | BOT-005 | Sapato baixo de segurança com bico reforçado e sola (sola em acento). |
| talabarte | QUE-002 | Talabarte: mosquetão superior (em acento), faceia tecidual com costuras e anel em D inferior. |
| cinto-seguranca | QUE-003 | Cinturão abdominal: faixa horizontal com fivela central (fivela em acento). |
| trava-queda | QUE-004 | Trava-queda: corpo com corda acima, seta interna de deslize (em acento) e mosquetão abaixo. |
| furadeira | FUR-001 | Furadeira de impacto pistola: corpo, mandril, cabo e broca (broca em acento). |
| furadeira-de-bancada | FUR-002 | Prensa-furadeira de bancada: base, coluna, cabeçote, mesa e broca (broca em acento). |
| esmerilhadeira | FUR-003 | Esmerilhadeira angular: disco com coifa, corpo horizontal e pegador superior (cubo do disco em acento). |
| serra-circular | FUR-004 | Serra circular: corpo com alça em D e disco exposto com cubo (cubo do disco em acento). |
| retifica | FUR-005 | Retífica reta (die grinder): corpo cilíndrico longo, pinça e ponta (ponta em acento). |
| compressor | MAQ-005 | Compressor de ar: tanque horizontal, motor acima com alça e manômetro (manômetro em acento). |
| prensa-hidraulica | MAQ-006 | Prensa hidráulica: pranchas superior/inferior, colunas, cilindro e êmbolo central (êmbolo em acento). |
| politriz | MAQ-007 | Politriz de bancada: motor central sobre base e dois rebolos nas pontas (rebolo esquerdo em acento). |
| serra-de-bancada | MAQ-008 | Serra de bancada: mesa com lâmina emergindo pelo rasgo (lâmina em acento). |
| bomba-agua | MAQ-009 | Bomba d'água autoaspirante: voluta circular com flange de saída e motor lateral (cubo da voluta em acento). |

Cobertura: 26 famílias, 40 produtos (37 à venda + CAP-005/OCV-006/LUV-009 fora de linha).
`MAQ-010` (Torno de Bancada Descontinuado, INACTIVE) fica SEM ilustração específica e usa o
fallback da categoria (maquinas-estacionarias.svg) — produto invisível no catálogo.

## Ilustrações padrão de categoria refeitas (mesmos nomes de arquivo)

Os arquivos `backend/app/static/catalog/protecao-respiratoria.svg` (antes parecido com um
olho) e `backend/app/static/catalog/protecao-maos.svg` (antes uma forma ambígua) foram
REDESENHADOS no padrão 512 desta fase, mantendo o nome do arquivo para não quebrar a
resolução existente (`resolve_category_image_path`). Os demais SVGs de categoria foram
mantidos como estão.
