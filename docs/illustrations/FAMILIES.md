# FamÃ­lias de ilustraÃ§Ã£o por produto (Prompt 10, Parte B1)

IlustraÃ§Ãµes vetoriais SVG no estilo **Ã­cone de linha duotone** (traÃ§o branco arredondado
`#F8FAFC` com **um** acento laranja `#F97316` sobre ladrilho escuro `#0F172A`), a mesma
linguagem visual dos SVGs de categoria de `backend/app/static/catalog/`. NÃ£o existe uma
biblioteca que as gere: cada arquivo foi desenhado como cÃ³digo SVG original deste projeto
(sem cÃ³pia de conjuntos de terceiros â€” ver `ILLUSTRATION_CREDITS.md`).

Prioridade no seed: **foto > ilustracao > imagem da categoria**. Desde o lote 2 de fotos (2026-10-26),
45 dos 50 produtos tem FOTO REAL; as ilustracoes abaixo seguem como fallback especifico do proprio
produto (e documentacao do desenho), com uso remanescente: AUD-004, LUV-004, RES-004, OCV-006 e LUV-009.

| Chave (arquivo) | SKUs que a usam | DescriÃ§Ã£o do objeto desenhado |
|---|---|---|
| capacete-de-seguranca | CAP-002, CAP-003, CAP-004, CAP-005 | Capacete de seguranÃ§a com aba frontal e crista de ventilaÃ§Ã£o (aba em acento). |
| oculos-de-protecao | OCV-001, OCV-002, OCV-004, OCV-005, OCV-006 | Ã“culos de proteÃ§Ã£o de lente ampla com elÃ¡stico nas duas laterais (elÃ¡stico em acento). |
| luva-de-raspa | EPI-LUV-002, LUV-004, LUV-006, LUV-009 | Luva de couro com cinco dedos, polegar e punho de seguranca; faixa do punho em acento. |
| luva-nitrilica | LUV-005 | Luva descartavel fina, dedos longos e punho reto curto; linha do punho em acento. |
| luva-anticorte | LUV-007 | Luva tricotada com faixa pontilhada de aderÃªncia no dorso (pontos em acento). |
| luva-latex | LUV-008 | Luva de lÃ¡tex forrada com punho longo reto (gauntlet); linha inferior do punho em acento. |
| mascara-descartavel | EPI-RES-003, RES-004, RES-007 | Respirador descartÃ¡vel tipo concha com tiras laterais e costura nasal (costura em acento). |
| respirador-panoramico | RES-008 | MÃ¡scara de rosto inteiro com viseira, vÃ¡lvula/falante inferior e tiras (viseira interna em acento). |
| protetor-plug | AUD-001, AUD-004 | Par de plugs (cÃ¡psulas) ligados por cordÃ£o em U (cordÃ£o em acento). |
| abafador-capacete | AUD-003 | Conchas protetoras suspensas no arco/crista de capacete (conchas em acento). |
| botina | BOT-004 | Botina (cano curto) com duas fileiras de cadarÃ§os e sola destacada (sola em acento). |
| bota-de-seguranca | BOT-002, BOT-003 | Bota de cano alto com trÃªs fileiras de cadarÃ§os e sola destacada (sola em acento). |
| sapato-de-seguranca | BOT-005 | Sapato baixo de seguranÃ§a com bico reforÃ§ado e sola (sola em acento). |
| talabarte | QUE-002 | Talabarte: mosquetÃ£o superior (em acento), faceia tecidual com costuras e anel em D inferior. |
| cinto-seguranca | QUE-003 | CinturÃ£o abdominal: faixa horizontal com fivela central (fivela em acento). |
| trava-queda | QUE-004 | Trava-queda: corpo com corda acima, seta interna de deslize (em acento) e mosquetÃ£o abaixo. |
| furadeira | FUR-001 | Furadeira de impacto pistola: corpo, mandril, cabo e broca (broca em acento). |
| furadeira-de-bancada | FUR-002 | Prensa-furadeira de bancada: base, coluna, cabeÃ§ote, mesa e broca (broca em acento). |
| esmerilhadeira | FUR-003 | Esmerilhadeira angular: disco com coifa, corpo horizontal e pegador superior (cubo do disco em acento). |
| serra-circular | FUR-004 | Serra circular: corpo com alÃ§a em D e disco exposto com cubo (cubo do disco em acento). |
| retifica | FUR-005 | RetÃ­fica reta (die grinder): corpo cilÃ­ndrico longo, pinÃ§a e ponta (ponta em acento). |
| compressor | MAQ-005 | Compressor de ar: tanque horizontal, motor acima com alÃ§a e manÃ´metro (manÃ´metro em acento). |
| prensa-hidraulica | MAQ-006 | Prensa hidrÃ¡ulica: pranchas superior/inferior, colunas, cilindro e Ãªmbolo central (Ãªmbolo em acento). |
| politriz | MAQ-007 | Politriz de bancada: motor central sobre base e dois rebolos nas pontas (rebolo esquerdo em acento). |
| serra-de-bancada | MAQ-008 | Serra de bancada: mesa com lÃ¢mina emergindo pelo rasgo (lÃ¢mina em acento). |
| bomba-agua | MAQ-009 | Bomba d'Ã¡gua autoaspirante: voluta circular com flange de saÃ­da e motor lateral (cubo da voluta em acento). |

Cobertura: 26 famÃ­lias, 40 produtos (37 Ã  venda + CAP-005/OCV-006/LUV-009 fora de linha).
`MAQ-010` (Torno de Bancada Descontinuado, INACTIVE) fica SEM ilustraÃ§Ã£o especÃ­fica e usa o
fallback da categoria (maquinas-estacionarias.svg) â€” produto invisÃ­vel no catÃ¡logo.

## IlustraÃ§Ãµes padrÃ£o de categoria refeitas (mesmos nomes de arquivo)

Os arquivos `backend/app/static/catalog/protecao-respiratoria.svg` (antes parecido com um
olho) e `backend/app/static/catalog/protecao-maos.svg` (antes uma forma ambÃ­gua) foram
REDESENHADOS no padrÃ£o 512 desta fase, mantendo o nome do arquivo para nÃ£o quebrar a
resoluÃ§Ã£o existente (`resolve_category_image_path`). Os demais SVGs de categoria foram
mantidos como estÃ£o.
