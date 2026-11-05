# ruff: noqa: RUF001 - vocabulario intencional em cirilico/arabe/japones/coreano/chines
"""Mensagem amigavel de degradacao do assistente (11 locales).

Usada quando o LLM local esta desligado, sem LM Studio ou falhou. Nunca
substitui a resposta neutra de seguranca (bloqueio/off-topic): e apenas o
aviso de "modo catalogo", acompanhado dos cartoes deterministicos que o
backend conseguir montar. Texto puro, sem HTML/links.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.modules.ai.domain.formatting import format_brl, format_foreign_amount
from app.modules.ai.domain.types import Locale

_DEMO_MODE: dict[str, str] = {
    "pt-BR": (
        "O assistente de IA está em modo demonstração local. "
        "Veja no README como rodar o modelo no LM Studio."
    ),
    "en": (
        "The AI assistant is in local demo mode. "
        "See the README for how to run the model with LM Studio."
    ),
    "es": (
        "El asistente de IA está en modo demostración local. "
        "Consulta el README para ejecutar el modelo con LM Studio."
    ),
    "ar": (
        "مساعد الذكاء الاصطناعي في وضع العرض المحلي. "
        "راجع README لمعرفة كيفية تشغيل النموذج في LM Studio."
    ),
    "de": (
        "Der KI-Assistent läuft im lokalen Demo-Modus. "
        "Im README steht, wie du das Modell mit LM Studio startest."
    ),
    "fr": (
        "L'assistant IA est en mode démonstration local. "
        "Consultez le README pour lancer le modèle avec LM Studio."
    ),
    "it": (
        "L'assistente IA è in modalità dimostrazione locale. "
        "Consulta il README per avviare il modello con LM Studio."
    ),
    "ja": (
        "AIアシスタントはローカルデモモードです。"
        "LM Studioでモデルを実行する方法はREADMEをご覧ください。"
    ),
    "ko": (
        "AI 어시스턴트가 로컬 데모 모드입니다. "
        "LM Studio에서 모델을 실행하는 방법은 README를 참고하세요."
    ),
    "ru": (
        "ИИ-ассистент работает в локальном демо-режиме. "
        "В README описано, как запустить модель в LM Studio."
    ),
    "zh-CN": "AI 助手当前处于本地演示模式。请参阅 README 了解如何使用 LM Studio 运行模型。",
}


def demo_mode_response(locale: Locale) -> str:
    """Aviso traduzido de modo demonstracao (fallback pt-BR)."""
    return _DEMO_MODE.get(locale.value, _DEMO_MODE["pt-BR"])


_CATALOG_MODE: dict[str, str] = {
    "pt-BR": (
        "Assistente em modo catálogo: posso mostrar produtos, preços e "
        "informações da loja."
    ),
    "en": "Assistant in catalog mode: I can show products, prices and store information.",
    "es": (
        "Asistente en modo catálogo: puedo mostrar productos, precios e "
        "información de la tienda."
    ),
    "ar": "المساعد في وضع الكتالوج: يمكنني عرض المنتجات والأسعار ومعلومات المتجر.",
    "de": (
        "Assistent im Katalogmodus: Ich kann Produkte, Preise und Informationen "
        "zum Shop anzeigen."
    ),
    "fr": (
        "Assistant en mode catalogue : je peux afficher les produits, les prix "
        "et les informations de la boutique."
    ),
    "it": (
        "Assistente in modalità catalogo: posso mostrare prodotti, prezzi e "
        "informazioni del negozio."
    ),
    "ja": "アシスタントはカタログモードです。商品、価格、ストア情報を表示できます。",
    "ko": "어시스턴트가 카탈로그 모드입니다. 제품, 가격 및 스토어 정보를 보여드릴 수 있습니다.",
    "ru": "Ассистент в режиме каталога: я могу показать товары, цены и информацию о магазине.",
    "zh-CN": "助手处于目录模式：我可以显示产品、价格和商店信息。",
}

_CATALOG_RESULTS: dict[str, str] = {
    "pt-BR": "Encontrei estas opções no catálogo:",
    "en": "I found these options in the catalog:",
    "es": "Encontré estas opciones en el catálogo:",
    "ar": "وجدت هذه الخيارات في الكتالوج:",
    "de": "Ich habe diese Optionen im Katalog gefunden:",
    "fr": "J'ai trouvé ces options dans le catalogue :",
    "it": "Ho trovato queste opzioni nel catalogo:",
    "ja": "カタログで次のオプションが見つかりました:",
    "ko": "카탈로그에서 다음 옵션을 찾았습니다:",
    "ru": "Я нашёл такие варианты в каталоге:",
    "zh-CN": "我在目录中找到了这些选项：",
}

_MORE_RESULTS: dict[str, str] = {
    "pt-BR": "Aqui estão mais opções do catálogo:",
    "en": "Here are more catalog options:",
    "es": "Aquí hay más opciones del catálogo:",
    "ar": "إليك المزيد من خيارات الكتالوج:",
    "de": "Hier sind weitere Katalogoptionen:",
    "fr": "Voici d'autres options du catalogue :",
    "it": "Ecco altre opzioni del catalogo:",
    "ja": "カタログの他のオプションです:",
    "ko": "카탈로그의 추가 옵션입니다:",
    "ru": "Вот ещё варианты из каталога:",
    "zh-CN": "以下是目录中的更多选项：",
}

_EXISTENCE_FOUND: dict[str, str] = {
    "pt-BR": "Sim, encontrei estas opções:",
    "en": "Yes, I found these options:",
    "es": "Sí, encontré estas opciones:",
    "ar": "نعم، وجدت هذه الخيارات:",
    "de": "Ja, ich habe diese Optionen gefunden:",
    "fr": "Oui, j'ai trouvé ces options :",
    "it": "Sì, ho trovato queste opzioni:",
    "ja": "はい、次のオプションが見つかりました:",
    "ko": "네, 다음 옵션을 찾았습니다:",
    "ru": "Да, я нашёл такие варианты:",
    "zh-CN": "是的，我找到了这些选项：",
}

_EXISTENCE_NEAR: dict[str, str] = {
    "pt-BR": "Não encontrei exatamente esse produto, mas encontrei estas opções próximas:",
    "en": "I could not find that exact product, but I found these close options:",
    "es": "No encontré exactamente ese producto, pero encontré estas opciones cercanas:",
    "ar": "لم أجد هذا المنتج بالتحديد، لكن وجدت هذه الخيارات المشابهة:",
    "de": "Ich konnte das genaue Produkt nicht finden, aber diese ähnlichen Optionen:",
    "fr": "Je n'ai pas trouvé ce produit exactement, mais voici des options proches :",
    "it": "Non ho trovato esattamente quel prodotto, ma queste opzioni simili:",
    "ja": "その商品は正確には見つかりませんでしたが、近いオプションがあります:",
    "ko": "해당 제품을 정확히 찾지 못했지만 비슷한 옵션을 찾았습니다:",
    "ru": "Точно такой товар не нашёл, но вот похожие варианты:",
    "zh-CN": "没有找到完全匹配的产品，但找到了这些相近选项：",
}

_EXISTENCE_NOT_FOUND: dict[str, str] = {
    "pt-BR": "Não encontrei esse produto no catálogo.",
    "en": "I could not find that product in the catalog.",
    "es": "No encontré ese producto en el catálogo.",
    "ar": "لم أجد هذا المنتج في الكتالوج.",
    "de": "Ich konnte dieses Produkt nicht im Katalog finden.",
    "fr": "Je n'ai pas trouvé ce produit dans le catalogue.",
    "it": "Non ho trovato questo prodotto nel catalogo.",
    "ja": "その商品はカタログに見つかりませんでした。",
    "ko": "해당 제품을 카탈로그에서 찾지 못했습니다.",
    "ru": "Я не нашёл этот товар в каталоге.",
    "zh-CN": "目录中没有找到该产品。",
}

_EXISTENCE_CATEGORIES: dict[str, str] = {
    "pt-BR": "Categorias disponíveis: {categories}.",
    "en": "Available categories: {categories}.",
    "es": "Categorías disponibles: {categories}.",
    "ar": "الفئات المتاحة: {categories}.",
    "de": "Verfügbare Kategorien: {categories}.",
    "fr": "Catégories disponibles : {categories}.",
    "it": "Categorie disponibili: {categories}.",
    "ja": "利用可能なカテゴリ: {categories}。",
    "ko": "사용 가능한 카테고리: {categories}.",
    "ru": "Доступные категории: {categories}.",
    "zh-CN": "可用类别：{categories}。",
}

_EXISTENCE_INVITE: dict[str, str] = {
    "pt-BR": "Descreva o que você precisa e eu ajudo a encontrar uma alternativa.",
    "en": "Tell me what you need and I can help find an alternative.",
    "es": "Cuéntame qué necesitas y te ayudo a encontrar una alternativa.",
    "ar": "صف ما تحتاجه وسأساعدك في إيجاد بديل.",
    "de": "Beschreiben Sie, was Sie brauchen, und ich helfe bei einer Alternative.",
    "fr": "Décrivez ce dont vous avez besoin et je vous aide à trouver une alternative.",
    "it": "Descrivi cosa ti serve e ti aiuto a trovare un'alternativa.",
    "ja": "必要なものを教えていただければ、代替品探しをお手伝いします。",
    "ko": "필요한 것을 설명해 주시면 대안을 찾아드리겠습니다.",
    "ru": "Опишите, что вам нужно, и я помогу найти альтернативу.",
    "zh-CN": "请描述您的需求，我可以帮您寻找替代品。",
}


def catalog_mode_response(locale: Locale) -> str:
    return _CATALOG_MODE.get(locale.value, _CATALOG_MODE["pt-BR"])


def catalog_results_response(locale: Locale) -> str:
    return _CATALOG_RESULTS.get(locale.value, _CATALOG_RESULTS["pt-BR"])


def more_results_response(locale: Locale) -> str:
    return _MORE_RESULTS.get(locale.value, _MORE_RESULTS["pt-BR"])


def existence_found_response(locale: Locale) -> str:
    return _EXISTENCE_FOUND.get(locale.value, _EXISTENCE_FOUND["pt-BR"])


def existence_near_response(locale: Locale) -> str:
    return _EXISTENCE_NEAR.get(locale.value, _EXISTENCE_NEAR["pt-BR"])


def existence_not_found_response(locale: Locale, *, categories: tuple[str, ...] = ()) -> str:
    parts = [_EXISTENCE_NOT_FOUND.get(locale.value, _EXISTENCE_NOT_FOUND["pt-BR"])]
    if categories:
        template = _EXISTENCE_CATEGORIES.get(locale.value, _EXISTENCE_CATEGORIES["pt-BR"])
        parts.append(template.format(categories=", ".join(categories[:3])))
    parts.append(_EXISTENCE_INVITE.get(locale.value, _EXISTENCE_INVITE["pt-BR"]))
    return " ".join(parts)


_GREETING: dict[str, str] = {
    "pt-BR": "Olá! Como posso ajudar com o catálogo Forja?",
    "en": "Hello! How can I help you with the Forja catalog?",
    "es": "¡Hola! ¿Cómo puedo ayudarte con el catálogo Forja?",
    "ar": "مرحبًا! كيف يمكنني مساعدتك في كتالوج Forja؟",
    "de": "Hallo! Wie kann ich Ihnen mit dem Forja-Katalog helfen?",
    "fr": "Bonjour ! Comment puis-je vous aider avec le catalogue Forja ?",
    "it": "Ciao! Come posso aiutarti con il catalogo Forja?",
    "ja": "こんにちは！Forjaカタログについてお手伝いできますか？",
    "ko": "안녕하세요! Forja 카탈로그에서 무엇을 도와드릴까요?",
    "ru": "Здравствуйте! Чем я могу помочь по каталогу Forja?",
    "zh-CN": "您好！我能帮您了解 Forja 目录吗？",
}

_INFO: dict[str, str] = {
    "pt-BR": (
        "Para condições comerciais, pedidos ou políticas, acesse sua conta ou fale "
        "com o time Forja."
    ),
    "en": (
        "For commercial terms, orders or policies, access your account or contact the Forja team."
    ),
    "es": (
        "Para condiciones comerciales, pedidos o políticas, accede a tu cuenta o "
        "contacta al equipo Forja."
    ),
    "ar": ("للشروط التجارية أو الطلبات أو السياسات، ادخل إلى حسابك أو تواصل مع فريق Forja."),
    "de": (
        "Für Geschäftsbedingungen, Bestellungen oder Richtlinien greifen Sie auf Ihr "
        "Konto zu oder kontaktieren Sie das Forja-Team."
    ),
    "fr": (
        "Pour les conditions commerciales, les commandes ou les politiques, accédez "
        "à votre compte ou contactez l'équipe Forja."
    ),
    "it": (
        "Per condizioni commerciali, ordini o politiche, accedi al tuo account o "
        "contatta il team Forja."
    ),
    "ja": (
        "商取引条件、ご注文、ポリシーについては、アカウントにアクセスするか"
        "Forjaチームまでお問い合わせください。"
    ),
    "ko": ("상업 조건, 주문 또는 정책은 계정에 로그인하거나 Forja 팀에 문의하세요."),
    "ru": (
        "По коммерческим условиям, заказам или правилам войдите в аккаунт или "
        "свяжитесь с командой Forja."
    ),
    "zh-CN": "有关商业条款、订单或政策，请登录账户或联系 Forja 团队。",
}

_PRICE_ASC: dict[str, str] = {
    "pt-BR": "A opção mais econômica que encontrei é {name}. Veja o cartão abaixo.",
    "en": "The most affordable option I found is {name}. See the card below.",
    "es": "La opción más económica que encontré es {name}. Consulta la tarjeta de abajo.",
    "ar": "الخيار الأكثر اقتصاديًا الذي وجدته هو {name}. راجع البطاقة أدناه.",
    "de": "Die günstigste Option, die ich gefunden habe, ist {name}. Siehe Karte unten.",
    "fr": "L'option la plus économique que j'ai trouvée est {name}. Voir la fiche ci-dessous.",
    "it": "L'opzione più economica che ho trovato è {name}. Vedi la scheda qui sotto.",
    "ja": "見つけた中で最もお手頃なのは {name} です。下のカードをご覧ください。",
    "ko": "가장 경제적인 옵션은 {name}입니다. 아래 카드를 확인하세요.",
    "ru": "Самый доступный вариант, который я нашёл: {name}. См. карточку ниже.",
    "zh-CN": "我找到的最经济选项是 {name}。请查看下方卡片。",
}

_PRICE_DESC: dict[str, str] = {
    "pt-BR": "A opção mais cara que encontrei é {name}. Veja o cartão abaixo.",
    "en": "The most expensive option I found is {name}. See the card below.",
    "es": "La opción más cara que encontré es {name}. Consulta la tarjeta de abajo.",
    "ar": "الخيار الأغلى الذي وجدته هو {name}. راجع البطاقة أدناه.",
    "de": "Die teuerste Option, die ich gefunden habe, ist {name}. Siehe Karte unten.",
    "fr": "L'option la plus chère que j'ai trouvée est {name}. Voir la fiche ci-dessous.",
    "it": "L'opzione più costosa che ho trovato è {name}. Vedi la scheda qui sotto.",
    "ja": "見つけた中で最も高いのは {name} です。下のカードをご覧ください。",
    "ko": "가장 비싼 옵션은 {name}입니다. 아래 카드를 확인하세요.",
    "ru": "Самый дорогой вариант, который я нашёл: {name}. См. карточку ниже.",
    "zh-CN": "我找到的最贵选项是 {name}。请查看下方卡片。",
}


_PRICE_VISITOR_NOTE: dict[str, str] = {
    "pt-BR": (
        "Os preços são consultivos para visitantes; entre na conta para ver o valor da sua empresa."
    ),
    "en": "Prices are consultive for visitors; sign in to see your company price.",
    "es": (
        "Los precios son consultivos para visitantes; inicia sesión para ver el precio "
        "de tu empresa."
    ),
    "ar": "الأسعار للزوار عند الطلب؛ سجّل الدخول لرؤية سعر شركتك.",
    "de": (
        "Preise sind für Besucher auf Anfrage; melden Sie sich an, um Ihren Firmenpreis zu sehen."
    ),
    "fr": (
        "Les prix sont consultatifs pour les visiteurs ; connectez-vous pour voir le "
        "prix de votre entreprise."
    ),
    "it": (
        "I prezzi sono consultivi per i visitatori; accedi per vedere il prezzo della tua azienda."
    ),
    "ja": "価格は訪問者にはお問い合わせください。ログインすると貴社価格を確認できます。",
    "ko": "가격은 방문자에게 문의 사항입니다. 로그인하면 회사 가격을 확인할 수 있습니다.",
    "ru": (
        "Цены для посетителей предоставляются по запросу; войдите, чтобы увидеть "
        "цену вашей компании."
    ),
    "zh-CN": "访客价格需咨询；登录后可查看贵司价格。",
}


def greeting_response(locale: Locale) -> str:
    return _GREETING.get(locale.value, _GREETING["pt-BR"])


def info_response(locale: Locale) -> str:
    return _INFO.get(locale.value, _INFO["pt-BR"])


_PRICE_QUESTION_KNOWN: dict[str, str] = {
    "pt-BR": "O preço de {name} aparece no cartão abaixo.",
    "en": "The price of {name} is shown in the card below.",
    "es": "El precio de {name} aparece en la tarjeta de abajo.",
    "ar": "سعر {name} يظهر في البطاقة أدناه.",
    "de": "Der Preis von {name} steht in der Karte unten.",
    "fr": "Le prix de {name} apparaît dans la fiche ci-dessous.",
    "it": "Il prezzo di {name} è nella scheda qui sotto.",
    "ja": "{name} の価格は下のカードに表示されています。",
    "ko": "{name}의 가격은 아래 카드에 표시되어 있습니다.",
    "ru": "Цена {name} указана в карточке ниже.",
    "zh-CN": "{name} 的价格显示在下方卡片中。",
}

_PRICE_QUESTION_VISITOR: dict[str, str] = {
    "pt-BR": "O preço de {name} é consultivo para visitantes.",
    "en": "The price of {name} is consultive for visitors.",
    "es": "El precio de {name} es consultivo para visitantes.",
    "ar": "سعر {name} للزوار عند الطلب.",
    "de": "Der Preis von {name} ist für Besucher auf Anfrage.",
    "fr": "Le prix de {name} est consultatif pour les visiteurs.",
    "it": "Il prezzo di {name} è consultivo per i visitatori.",
    "ja": "{name} の価格は訪問者にはお問い合わせください。",
    "ko": "{name}의 가격은 방문자에게 문의 사항입니다.",
    "ru": "Цена {name} для посетителей предоставляется по запросу.",
    "zh-CN": "{name} 的价格对访客需咨询。",
}


def price_question_response(locale: Locale, *, name: str, visitor: bool) -> str:
    """Resposta deterministica de preco (o VALOR fica no cartao, nunca no texto)."""
    if visitor:
        template = _PRICE_QUESTION_VISITOR.get(locale.value, _PRICE_QUESTION_VISITOR["pt-BR"])
        note = _PRICE_VISITOR_NOTE.get(locale.value, _PRICE_VISITOR_NOTE["pt-BR"])
        return f"{template.format(name=name)} {note}"
    template = _PRICE_QUESTION_KNOWN.get(locale.value, _PRICE_QUESTION_KNOWN["pt-BR"])
    return template.format(name=name)


_LOGIN_REQUIRED: dict[str, str] = {
    "pt-BR": "Entre na sua conta para consultar o carrinho ou os pedidos da sua empresa.",
    "en": "Sign in to view your cart or your company's orders.",
    "es": "Inicia sesión para consultar el carrito o los pedidos de tu empresa.",
    "ar": "سجّل الدخول لعرض سلة التسوق أو طلبات شركتك.",
    "de": (
        "Melden Sie sich an, um Ihren Warenkorb oder die Bestellungen Ihres Unternehmens zu sehen."
    ),
    "fr": "Connectez-vous pour consulter votre panier ou les commandes de votre entreprise.",
    "it": "Accedi per consultare il carrello o gli ordini della tua azienda.",
    "ja": "カートや貴社の注文を確認するにはログインしてください。",
    "ko": "장바구니나 회사 주문을 확인하려면 로그인하세요.",
    "ru": "Войдите, чтобы посмотреть корзину или заказы вашей компании.",
    "zh-CN": "请登录后查看购物车或贵司订单。",
}

_NOT_FOUND: dict[str, str] = {
    "pt-BR": "Não encontrei esse pedido na sua conta.",
    "en": "I could not find that order in your account.",
    "es": "No encontré ese pedido en tu cuenta.",
    "ar": "لم أجد هذا الطلب في حسابك.",
    "de": "Ich konnte diese Bestellung in Ihrem Konto nicht finden.",
    "fr": "Je n'ai pas trouvé cette commande dans votre compte.",
    "it": "Non ho trovato quell'ordine nel tuo account.",
    "ja": "その注文はアカウント内に見つかりませんでした。",
    "ko": "해당 주문을 계정에서 찾을 수 없습니다.",
    "ru": "Не удалось найти этот заказ в вашем аккаунте.",
    "zh-CN": "未在您的账户中找到该订单。",
}

_CLARIFY: dict[str, str] = {
    "pt-BR": "Pode enviar o nome/SKU do produto ou o número do pedido?",
    "en": "Could you send the product name/SKU or the order number?",
    "es": "¿Puedes enviar el nombre/SKU del producto o el número del pedido?",
    "ar": "هل يمكنك إرسال اسم/رمز المنتج أو رقم الطلب؟",
    "de": "Können Sie den Produktnamen/SKU oder die Bestellnummer senden?",
    "fr": "Pouvez-vous envoyer le nom/SKU du produit ou le numéro de commande ?",
    "it": "Puoi inviare il nome/SKU del prodotto o il numero dell'ordine?",
    "ja": "商品名/SKUまたは注文番号を送ってください。",
    "ko": "제품명/SKU 또는 주문 번호를 보내주세요.",
    "ru": "Пришлите название/SKU товара или номер заказа.",
    "zh-CN": "请发送产品名称/SKU 或订单号。",
}

_TOOL_ERROR: dict[str, str] = {
    "pt-BR": "Não consegui consultar agora. Tente de novo em instantes.",
    "en": "I could not check that right now. Please try again shortly.",
    "es": "No pude consultar ahora. Inténtalo de nuevo en unos instantes.",
    "ar": "لم أتمكن من التحقق الآن. حاول مرة أخرى بعد قليل.",
    "de": "Ich konnte das gerade nicht prüfen. Bitte versuchen Sie es gleich noch einmal.",
    "fr": "Je n'ai pas pu vérifier maintenant. Réessayez dans un instant.",
    "it": "Non sono riuscito a verificare ora. Riprova tra poco.",
    "ja": "今は確認できませんでした。しばらくしてからもう一度お試しください。",
    "ko": "지금은 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.",
    "ru": "Не удалось проверить сейчас. Повторите попытку чуть позже.",
    "zh-CN": "现在无法查询，请稍后重试。",
}


def login_required_response(locale: Locale) -> str:
    return _LOGIN_REQUIRED.get(locale.value, _LOGIN_REQUIRED["pt-BR"])


def not_found_response(locale: Locale) -> str:
    return _NOT_FOUND.get(locale.value, _NOT_FOUND["pt-BR"])


def clarify_response(locale: Locale) -> str:
    return _CLARIFY.get(locale.value, _CLARIFY["pt-BR"])


def tool_error_response(locale: Locale) -> str:
    return _TOOL_ERROR.get(locale.value, _TOOL_ERROR["pt-BR"])


_PRICE_CAPPED_NOTE: dict[str, str] = {
    "pt-BR": "A busca considerou os resultados mais relevantes do catálogo.",
    "en": "The search considered the most relevant catalog results.",
    "es": "La búsqueda consideró los resultados más relevantes del catálogo.",
    "ar": "اعتبرها البحث من بين نتائج الكتالوج الأكثر صلة.",
    "de": "Die Suche berücksichtigte die relevantesten Katalogergebnisse.",
    "fr": "La recherche a pris en compte les résultats les plus pertinents du catalogue.",
    "it": "La ricerca ha considerato i risultati più pertinenti del catalogo.",
    "ja": "検索はカタログの関連性の高い結果を対象にしています。",
    "ko": "검색은 카탈로그의 가장 관련성 높은 결과를 대상으로 했습니다.",
    "ru": "Поиск учитывал наиболее релевантные результаты каталога.",
    "zh-CN": "搜索已考虑目录中最相关的结果。",
}


def price_sort_response(
    locale: Locale,
    *,
    name: str,
    visitor: bool,
    capped: bool = False,
    direction: str = "asc",
) -> str:
    """Resposta deterministica para "mais barato"/"mais caro" (sem inventar valor)."""
    table = _PRICE_DESC if direction == "desc" else _PRICE_ASC
    template = table.get(locale.value, table["pt-BR"])
    text = template.format(name=name)
    if capped:
        text = f"{text} {_PRICE_CAPPED_NOTE.get(locale.value, _PRICE_CAPPED_NOTE['pt-BR'])}"
    if visitor:
        text = f"{text} {_PRICE_VISITOR_NOTE.get(locale.value, _PRICE_VISITOR_NOTE['pt-BR'])}"
    return text


_MINIMUM_ORDER: dict[str, str] = {
    "pt-BR": (
        "O pedido mínimo é por produto: cada item mostra a quantidade mínima no "
        "cartão (por exemplo, 6, 10, 12 ou 24 unidades). Não há um valor mínimo "
        "único de pedido; o carrinho valida a quantidade mínima do item."
    ),
    "en": (
        "The minimum order is per product: each item shows its minimum quantity "
        "on the card (for example, 6, 10, 12 or 24 units). There is no single "
        "minimum order value; the cart validates each item's minimum quantity."
    ),
    "es": (
        "El pedido mínimo es por producto: cada artículo muestra la cantidad "
        "mínima en la tarjeta (por ejemplo, 6, 10, 12 o 24 unidades). No hay un "
        "valor mínimo único de pedido; el carrito valida la cantidad mínima."
    ),
    "ar": (
        "الحد الأدنى للطلب يُحدد لكل منتج: تعرض البطاقة الحد الأدنى للكمية "
        "(مثلاً 6 أو 10 أو 12 أو 24 وحدة). لا توجد قيمة دنيا موحدة للطلب؛ "
        "تتحقق السلة من الحد الأدنى لكمية المنتج."
    ),
    "de": (
        "Der Mindestbestellwert gilt pro Produkt: Jeder Artikel zeigt die "
        "Mindestmenge auf der Karte (z. B. 6, 10, 12 oder 24 Stück). Es gibt "
        "keinen einheitlichen Mindestbestellwert; der Warenkorb prüft die "
        "Mindestmenge des Artikels."
    ),
    "fr": (
        "La commande minimum est définie par produit : chaque article affiche "
        "la quantité minimale sur la fiche (par exemple 6, 10, 12 ou 24 unités). "
        "Il n'y a pas de montant minimum unique ; le panier vérifie la quantité "
        "minimale de l'article."
    ),
    "it": (
        "L'ordine minimo è per prodotto: ogni articolo mostra la quantità minima "
        "nella scheda (ad esempio 6, 10, 12 o 24 unità). Non c'è un valore minimo "
        "unico; il carrello verifica la quantità minima dell'articolo."
    ),
    "ja": (
        "最小注文数量は商品ごとに決まります。カードに最小数量(例: 6、10、12、24個)"
        "が表示されます。注文全体の一律の最低金額はありません。カートが商品ごとの"
        "最小数量を確認します。"
    ),
    "ko": (
        "최소 주문 수량은 상품별로 정해집니다. 카드에 최소 수량(예: 6, 10, 12, "
        "24개)이 표시됩니다. 전체 주문의 단일 최소 금액은 없으며, 장바구니가 "
        "상품별 최소 수량을 확인합니다."
    ),
    "ru": (
        "Минимальный заказ определяется по товару: в карточке указано "
        "минимальное количество (например, 6, 10, 12 или 24 шт.). Единого "
        "минимального значения заказа нет; корзина проверяет минимальное "
        "количество товара."
    ),
    "zh-CN": (
        "最低订购量按商品设置: 卡片会显示该商品的最小数量 (例如 6、10、12 或 24 件)。"
        "没有统一的订单最低金额; 购物车会校验该商品的最小数量。"
    ),
}


def minimum_order_response(locale: Locale) -> str:
    return _MINIMUM_ORDER.get(locale.value, _MINIMUM_ORDER["pt-BR"])


_PRICE_UNVERIFIED: dict[str, str] = {
    "pt-BR": (
        "Não consegui validar os valores desta resposta. Veja os cartões abaixo "
        "para os preços corretos."
    ),
    "en": (
        "I could not validate the values in this answer. See the cards below for "
        "the correct prices."
    ),
    "es": (
        "No pude validar los valores de esta respuesta. Consulta las tarjetas de "
        "abajo para los precios correctos."
    ),
    "ar": "لم أتمكن من التحقق من القيم في هذه الإجابة. راجع البطاقات أدناه للأسعار الصحيحة.",
    "de": (
        "Ich konnte die Werte in dieser Antwort nicht prüfen. Die korrekten Preise "
        "stehen in den Karten unten."
    ),
    "fr": (
        "Je n'ai pas pu valider les valeurs de cette réponse. Les prix corrects "
        "figurent dans les fiches ci-dessous."
    ),
    "it": (
        "Non ho potuto validare i valori di questa risposta. I prezzi corretti sono "
        "nelle schede qui sotto."
    ),
    "ja": "この回答の値を確認できませんでした。正しい価格は下のカードをご覧ください。",
    "ko": "이 답변의 값을 확인할 수 없습니다. 올바른 가격은 아래 카드를 확인하세요.",
    "ru": "Не удалось проверить значения в этом ответе. Правильные цены указаны в карточках ниже.",
    "zh-CN": "无法验证此回答中的数值。正确价格请查看下方卡片。",
}


def price_unverified_response(locale: Locale) -> str:
    return _PRICE_UNVERIFIED.get(locale.value, _PRICE_UNVERIFIED["pt-BR"])


_GROUNDING_FALLBACK: dict[str, str] = {
    "pt-BR": "Não consegui validar os detalhes desta resposta. Veja os cartões abaixo.",
    "en": "I could not validate the details in this answer. See the cards below.",
    "es": "No pude validar los detalles de esta respuesta. Consulta las tarjetas de abajo.",
    "ar": "لم أتمكن من التحقق من تفاصيل هذه الإجابة. راجع البطاقات أدناه.",
    "de": "Ich konnte die Details dieser Antwort nicht prüfen. Siehe Karten unten.",
    "fr": "Je n'ai pas pu valider les détails de cette réponse. Voir les fiches ci-dessous.",
    "it": "Non ho potuto validare i dettagli di questa risposta. Vedi le schede qui sotto.",
    "ja": "この回答の詳細を確認できませんでした。下のカードをご覧ください。",
    "ko": "이 답변의 세부 정보를 확인할 수 없습니다. 아래 카드를 확인하세요.",
    "ru": "Не удалось проверить детали этого ответа. См. карточки ниже.",
    "zh-CN": "无法验证此回答的详细信息。请查看下方卡片。",
}


def grounding_fallback_response(locale: Locale) -> str:
    return _GROUNDING_FALLBACK.get(locale.value, _GROUNDING_FALLBACK["pt-BR"])


_PRICE_ACCESS: dict[str, str] = {
    "pt-BR": "Para comparar preços e ver a opção mais barata, entre na sua conta com CNPJ.",
    "en": "To compare prices and see the cheapest option, sign in with your company account.",
    "es": (
        "Para comparar precios y ver la opción más barata, inicia sesión con tu cuenta de empresa."
    ),
    "ar": "لمقارنة الأسعار ورؤية الخيار الأرخص، سجّل الدخول بحساب شركتك.",
    "de": (
        "Um Preise zu vergleichen und die günstigste Option zu sehen, melden "
        "Sie sich mit Ihrem Firmenkonto an."
    ),
    "fr": (
        "Pour comparer les prix et voir l'option la moins chère, connectez-vous "
        "avec votre compte entreprise."
    ),
    "it": (
        "Per confrontare i prezzi e vedere l'opzione più economica, accedi con "
        "il tuo account aziendale."
    ),
    "ja": "価格を比較して最も安いオプションを確認するには、企業アカウントでログインしてください。",
    "ko": "가격을 비교하고 가장 저렴한 옵션을 확인하려면 회사 계정으로 로그인하세요.",
    "ru": "Чтобы сравнить цены и увидеть самый доступный вариант, войдите в корпоративный аккаунт.",
    "zh-CN": "要比较价格并查看最便宜的选项，请使用企业账户登录。",
}


def price_access_response(locale: Locale) -> str:
    return _PRICE_ACCESS.get(locale.value, _PRICE_ACCESS["pt-BR"])


_CURRENCY_CONFIRMATION: dict[str, str] = {
    "pt-BR": (
        "Os preços do catálogo são em R$. Você quis dizer {amount} ou {brl_amount}? "
        "Confirme o valor em reais, por favor."
    ),
    "en": (
        "Catalog prices are in BRL. Did you mean {amount} or {brl_amount}? "
        "Please confirm the amount in BRL."
    ),
    "es": (
        "Los precios del catálogo son en R$. ¿Quisiste decir {amount} o {brl_amount}? "
        "Confirma el valor en reales, por favor."
    ),
    "ar": (
        "أسعار الكتالوج بالريال البرازيلي (R$). هل تقصد {amount} أم {brl_amount}؟ "
        "يرجى تأكيد القيمة بالريال البرازيلي."
    ),
    "de": (
        "Die Katalogpreise sind in BRL. Meinten Sie {amount} oder {brl_amount}? "
        "Bitte bestätigen Sie den Betrag in BRL."
    ),
    "fr": (
        "Les prix du catalogue sont en R$. Voulez-vous dire {amount} ou {brl_amount} ? "
        "Merci de confirmer le montant en reais."
    ),
    "it": (
        "I prezzi del catalogo sono in R$. Intendevi {amount} o {brl_amount}? "
        "Conferma l'importo in reais, per favore."
    ),
    "ja": (
        "カタログの価格はR$ (ブラジルレアル) です。{amount} ですか、それとも "
        "{brl_amount} ですか? レアルでの金額を確認してください。"
    ),
    "ko": (
        "카탈로그 가격은 R$(브라질 헤알)입니다. {amount}인가요, 아니면 "
        "{brl_amount}인가요? 헤알 기준 금액을 확인해 주세요."
    ),
    "ru": (
        "Цены в каталоге указаны в BRL. Вы имели в виду {amount} или {brl_amount}? "
        "Подтвердите сумму в реалах."
    ),
    "zh-CN": (
        "目录价格以巴西雷亚尔 (R$) 计价。您是指 {amount} 还是 {brl_amount}? 请确认雷亚尔金额。"
    ),
}


def currency_confirmation_response(
    locale: Locale,
    *,
    minimum: float | None,
    maximum: float | None,
    currency: str,
) -> str:
    """Pedido unico de confirmacao quando a moeda citada nao pode ser aplicada."""
    values = [value for value in (minimum, maximum) if value is not None]
    if not values:
        amount = f"? {currency}".strip()
        brl_amount = "R$ ?"
    else:
        amount = " - ".join(format_foreign_amount(value, currency, locale) for value in values)
        brl_amount = " - ".join(format_brl(value, locale) for value in values)
    template = _CURRENCY_CONFIRMATION.get(locale.value, _CURRENCY_CONFIRMATION["pt-BR"])
    return template.format(amount=amount, brl_amount=brl_amount)


# ---------------------------------------------------------------------------
# Operacoes de catalogo: marcas, visao geral, contagem e faixa de preco
# ---------------------------------------------------------------------------

_BRAND_LIST_INTRO: dict[str, str] = {
    "pt-BR": "Marcas disponíveis:",
    "en": "Available brands:",
    "es": "Marcas disponibles:",
    "ar": "العلامات التجارية المتاحة:",
    "de": "Verfügbare Marken:",
    "fr": "Marques disponibles :",
    "it": "Marche disponibili:",
    "ja": "利用可能なブランド:",
    "ko": "사용 가능한 브랜드:",
    "ru": "Доступные бренды:",
    "zh-CN": "可用品牌：",
}

_BRAND_LIST_FOR: dict[str, str] = {
    "pt-BR": "Marcas disponíveis para {query}:",
    "en": "Available brands for {query}:",
    "es": "Marcas disponibles para {query}:",
    "ar": "العلامات التجارية المتاحة لـ {query}:",
    "de": "Verfügbare Marken für {query}:",
    "fr": "Marques disponibles pour {query} :",
    "it": "Marche disponibili per {query}:",
    "ja": "{query} の利用可能なブランド:",
    "ko": "{query}의 사용 가능한 브랜드:",
    "ru": "Доступные бренды для {query}:",
    "zh-CN": "{query} 的可用品牌：",
}

_BRAND_LIST_EMPTY: dict[str, str] = {
    "pt-BR": "Não encontrei marcas no catálogo para esse filtro.",
    "en": "I found no brands in the catalog for that filter.",
    "es": "No encontré marcas en el catálogo para ese filtro.",
    "ar": "لم أجد علامات تجارية في الكتالوج بهذا الفلتر.",
    "de": "Ich fand keine Marken im Katalog für diesen Filter.",
    "fr": "Je n'ai trouvé aucune marque dans le catalogue pour ce filtre.",
    "it": "Non ho trovato marchi nel catalogo con quel filtro.",
    "ja": "その条件に合うブランドはカタログに見つかりませんでした。",
    "ko": "해당 조건의 브랜드를 카탈로그에서 찾지 못했습니다.",
    "ru": "Бренды по этому фильтру не найдены в каталоге.",
    "zh-CN": "该筛选条件下目录中没有找到品牌。",
}

_BRAND_LIST_NEXT: dict[str, str] = {
    "pt-BR": "Diga o nome de uma marca para ver os produtos.",
    "en": "Tell me a brand name to see its products.",
    "es": "Dime el nombre de una marca para ver sus productos.",
    "ar": "اذكر اسم علامة تجارية لعرض منتجاتها.",
    "de": "Nennen Sie eine Marke, um die Produkte zu sehen.",
    "fr": "Indiquez une marque pour voir ses produits.",
    "it": "Dimmi il nome di una marca per vedere i prodotti.",
    "ja": "ブランド名を教えていただければ商品を表示します。",
    "ko": "브랜드 이름을 알려주시면 제품을 보여드리겠습니다.",
    "ru": "Назовите бренд, чтобы увидеть товары.",
    "zh-CN": "告诉我品牌名称即可查看产品。",
}

_BRAND_PRODUCTS_INTRO: dict[str, str] = {
    "pt-BR": "Produtos da marca {brand}:",
    "en": "Products from {brand}:",
    "es": "Productos de la marca {brand}:",
    "ar": "منتجات العلامة {brand}:",
    "de": "Produkte der Marke {brand}:",
    "fr": "Produits de la marque {brand} :",
    "it": "Prodotti del marchio {brand}:",
    "ja": "{brand} の製品:",
    "ko": "{brand} 제품:",
    "ru": "Товары бренда {brand}:",
    "zh-CN": "{brand} 的产品：",
}

_BRAND_AMBIGUOUS: dict[str, str] = {
    "pt-BR": "Encontrei mais de uma marca parecida com {brand}: {candidates}. Qual delas?",
    "en": "I found more than one brand similar to {brand}: {candidates}. Which one?",
    "es": "Encontré más de una marca parecida a {brand}: {candidates}. ¿Cuál?",
    "ar": "وجدت أكثر من علامة مشابهة لـ {brand}: {candidates}. أيها؟",
    "de": "Ich habe mehrere ähnliche Marken zu {brand} gefunden: {candidates}. Welche?",
    "fr": "J'ai trouvé plusieurs marques proches de {brand} : {candidates}. Laquelle ?",
    "it": "Ho trovato più marchi simili a {brand}: {candidates}. Quale?",
    "ja": "{brand} に似たブランドが複数あります: {candidates}。どれですか?",
    "ko": "{brand}와 비슷한 브랜드가 여러 개 있습니다: {candidates}. 어느 것인가요?",
    "ru": "Нашёл несколько похожих брендов для {brand}: {candidates}. Какой?",
    "zh-CN": "找到多个与 {brand} 相近的品牌：{candidates}。哪一个？",
}

_BRAND_NOT_FOUND: dict[str, str] = {
    "pt-BR": "Não encontrei a marca {brand} no catálogo. Marcas disponíveis: {available}.",
    "en": "I could not find the brand {brand} in the catalog. Available brands: {available}.",
    "es": "No encontré la marca {brand} en el catálogo. Marcas disponibles: {available}.",
    "ar": "لم أجد العلامة {brand} في الكتالوج. العلامات المتاحة: {available}.",
    "de": "Ich konnte die Marke {brand} nicht im Katalog finden. Verfügbare Marken: {available}.",
    "fr": (
        "Je n'ai pas trouvé la marque {brand} dans le catalogue. "
        "Marques disponibles : {available}."
    ),
    "it": "Non ho trovato il marchio {brand} nel catalogo. Marche disponibili: {available}.",
    "ja": (
        "カタログに {brand} というブランドは見つかりませんでした。"
        "利用可能なブランド: {available}。"
    ),
    "ko": "카탈로그에서 {brand} 브랜드를 찾지 못했습니다. 사용 가능한 브랜드: {available}.",
    "ru": "Бренд {brand} не найден в каталоге. Доступные бренды: {available}.",
    "zh-CN": "目录中没有找到品牌 {brand}。可用品牌：{available}。",
}

_BRAND_EMPTY: dict[str, str] = {
    "pt-BR": "Não encontrei produtos da marca {brand} para esse filtro.",
    "en": "I found no products from {brand} for that filter.",
    "es": "No encontré productos de la marca {brand} con ese filtro.",
    "ar": "لم أجد منتجات من العلامة {brand} بهذا الفلتر.",
    "de": "Ich fand keine Produkte der Marke {brand} für diesen Filter.",
    "fr": "Je n'ai trouvé aucun produit de la marque {brand} pour ce filtre.",
    "it": "Non ho trovato prodotti del marchio {brand} con quel filtro.",
    "ja": "その条件で {brand} の製品は見つかりませんでした。",
    "ko": "해당 조건에서 {brand} 제품을 찾지 못했습니다.",
    "ru": "По этому фильтру товаров бренда {brand} не найдено.",
    "zh-CN": "该筛选条件下没有找到 {brand} 的产品。",
}

_OVERVIEW: dict[str, str] = {
    "pt-BR": "A loja tem {total} produtos em {count} categorias: {categories}.",
    "en": "The store has {total} products in {count} categories: {categories}.",
    "es": "La tienda tiene {total} productos en {count} categorías: {categories}.",
    "ar": "يحتوي المتجر على {total} منتجًا في {count} فئات: {categories}.",
    "de": "Der Shop hat {total} Produkte in {count} Kategorien: {categories}.",
    "fr": "La boutique compte {total} produits dans {count} catégories : {categories}.",
    "it": "Il negozio ha {total} prodotti in {count} categorie: {categories}.",
    "ja": "ストアには {count} カテゴリに {total} 商品があります: {categories}。",
    "ko": "스토어에는 {count}개 카테고리에 {total}개 제품이 있습니다: {categories}.",
    "ru": "В магазине {total} товаров в {count} категориях: {categories}.",
    "zh-CN": "商店在 {count} 个类别中有 {total} 件产品：{categories}。",
}

_OVERVIEW_FILTERED: dict[str, str] = {
    "pt-BR": "Sim, temos {total} produtos nestas categorias de {query}: {categories}.",
    "en": "Yes, we have {total} products in these {query} categories: {categories}.",
    "es": "Sí, tenemos {total} productos en estas categorías de {query}: {categories}.",
    "ar": "نعم، لدينا {total} منتجًا في فئات {query} التالية: {categories}.",
    "de": "Ja, wir haben {total} Produkte in diesen Kategorien für {query}: {categories}.",
    "fr": "Oui, nous avons {total} produits dans ces catégories {query} : {categories}.",
    "it": "Sì, abbiamo {total} prodotti in queste categorie {query}: {categories}.",
    "ja": "はい、{query} のカテゴリに {total} 商品があります: {categories}。",
    "ko": "네, {query} 카테고리에 {total}개 제품이 있습니다: {categories}.",
    "ru": "Да, у нас {total} товаров в категориях {query}: {categories}.",
    "zh-CN": "是的，我们在这些{query}类别中有 {total} 件产品：{categories}。",
}

_OVERVIEW_NONE: dict[str, str] = {
    "pt-BR": "Não encontrei categorias para {query} no catálogo.",
    "en": "I found no categories for {query} in the catalog.",
    "es": "No encontré categorías para {query} en el catálogo.",
    "ar": "لم أجد فئات لـ {query} في الكتالوج.",
    "de": "Ich fand keine Kategorien für {query} im Katalog.",
    "fr": "Je n'ai trouvé aucune catégorie pour {query} dans le catalogue.",
    "it": "Non ho trovato categorie per {query} nel catalogo.",
    "ja": "カタログに {query} のカテゴリは見つかりませんでした。",
    "ko": "카탈로그에서 {query} 카테고리를 찾지 못했습니다.",
    "ru": "Категории для {query} не найдены в каталоге.",
    "zh-CN": "目录中没有找到 {query} 的类别。",
}

_PRICE_RANGE: dict[str, str] = {
    "pt-BR": "A faixa de preço de {query} é de {minimum} a {maximum} ({count} produtos).",
    "en": "The price range for {query} is {minimum} to {maximum} ({count} products).",
    "es": "El rango de precio de {query} es de {minimum} a {maximum} ({count} productos).",
    "ar": "نطاق سعر {query} من {minimum} إلى {maximum} ({count} منتجًا).",
    "de": "Die Preisspanne für {query} liegt zwischen {minimum} und {maximum} ({count} Produkte).",
    "fr": "La fourchette de prix pour {query} va de {minimum} à {maximum} ({count} produits).",
    "it": "La fascia di prezzo per {query} va da {minimum} a {maximum} ({count} prodotti).",
    "ja": "{query} の価格帯は {minimum} から {maximum} です（{count} 商品）。",
    "ko": "{query}의 가격대는 {minimum}부터 {maximum}까지입니다({count}개 제품).",
    "ru": "Диапазон цен для {query}: от {minimum} до {maximum} ({count} товаров).",
    "zh-CN": "{query} 的价格范围是 {minimum} 到 {maximum}（{count} 件产品）。",
}

_PRICE_RANGE_EMPTY: dict[str, str] = {
    "pt-BR": "Não encontrei preços para {query} no catálogo.",
    "en": "I found no prices for {query} in the catalog.",
    "es": "No encontré precios para {query} en el catálogo.",
    "ar": "لم أجد أسعارًا لـ {query} في الكتالوج.",
    "de": "Ich fand keine Preise für {query} im Katalog.",
    "fr": "Je n'ai trouvé aucun prix pour {query} dans le catalogue.",
    "it": "Non ho trovato prezzi per {query} nel catalogo.",
    "ja": "カタログに {query} の価格は見つかりませんでした。",
    "ko": "카탈로그에서 {query} 가격을 찾지 못했습니다.",
    "ru": "Цены для {query} не найдены в каталоге.",
    "zh-CN": "目录中没有找到 {query} 的价格。",
}

_COUNT: dict[str, str] = {
    "pt-BR": "Temos {count} produtos no catálogo.",
    "en": "We have {count} products in the catalog.",
    "es": "Tenemos {count} productos en el catálogo.",
    "ar": "لدينا {count} منتجًا في الكتالوج.",
    "de": "Wir haben {count} Produkte im Katalog.",
    "fr": "Nous avons {count} produits dans le catalogue.",
    "it": "Abbiamo {count} prodotti nel catalogo.",
    "ja": "カタログには {count} 商品あります。",
    "ko": "카탈로그에 {count}개 제품이 있습니다.",
    "ru": "В каталоге {count} товаров.",
    "zh-CN": "目录中共有 {count} 件产品。",
}

_COUNT_FILTERED: dict[str, str] = {
    "pt-BR": "Temos {count} produtos para {filter}.",
    "en": "We have {count} products for {filter}.",
    "es": "Tenemos {count} productos para {filter}.",
    "ar": "لدينا {count} منتجًا لـ {filter}.",
    "de": "Wir haben {count} Produkte für {filter}.",
    "fr": "Nous avons {count} produits pour {filter}.",
    "it": "Abbiamo {count} prodotti per {filter}.",
    "ja": "{filter} の商品は {count} 件です。",
    "ko": "{filter} 제품은 {count}개입니다.",
    "ru": "Для {filter} найдено {count} товаров.",
    "zh-CN": "{filter} 共有 {count} 件产品。",
}

_COUNT_EMPTY: dict[str, str] = {
    "pt-BR": "Não encontrei produtos para {filter} no catálogo.",
    "en": "I found no products for {filter} in the catalog.",
    "es": "No encontré productos para {filter} en el catálogo.",
    "ar": "لم أجد منتجات لـ {filter} في الكتالوج.",
    "de": "Ich fand keine Produkte für {filter} im Katalog.",
    "fr": "Je n'ai trouvé aucun produit pour {filter} dans le catalogue.",
    "it": "Non ho trovato prodotti per {filter} nel catalogo.",
    "ja": "カタログに {filter} の商品は見つかりませんでした。",
    "ko": "카탈로그에서 {filter} 제품을 찾지 못했습니다.",
    "ru": "Товары для {filter} не найдены в каталоге.",
    "zh-CN": "目录中没有找到 {filter} 的产品。",
}

_MORE_SUFFIX: dict[str, str] = {
    "pt-BR": "e mais {count}",
    "en": "and {count} more",
    "es": "y {count} más",
    "ar": "و{count} أخرى",
    "de": "und {count} weitere",
    "fr": "et {count} de plus",
    "it": "e altri {count}",
    "ja": "ほか {count} 件",
    "ko": "외 {count}개",
    "ru": "и ещё {count}",
    "zh-CN": "以及另外 {count} 个",
}


def _table(table: dict[str, str], locale: Locale) -> str:
    return table.get(locale.value, table["pt-BR"])


def _with_more(items: list[str], total: int, locale: Locale) -> str:
    text = ", ".join(items)
    remaining = max(0, total - len(items))
    if remaining:
        text = f"{text}; {_table(_MORE_SUFFIX, locale).format(count=remaining)}"
    return text


def brand_list_response(
    locale: Locale,
    *,
    brands: Sequence[tuple[str, int]],
    total: int,
    query: str | None = None,
) -> str:
    if not brands:
        return _table(_BRAND_LIST_EMPTY, locale)
    listed = [f"{name} ({count})" for name, count in brands[:15]]
    intro = (
        _table(_BRAND_LIST_FOR, locale).format(query=query)
        if query
        else _table(_BRAND_LIST_INTRO, locale)
    )
    return f"{intro} {_with_more(listed, total, locale)} {_table(_BRAND_LIST_NEXT, locale)}"


def brand_products_response(locale: Locale, *, brand: str) -> str:
    return _table(_BRAND_PRODUCTS_INTRO, locale).format(brand=brand)


def brand_ambiguous_response(
    locale: Locale, *, brand: str, candidates: Sequence[str]
) -> str:
    return _table(_BRAND_AMBIGUOUS, locale).format(
        brand=brand, candidates=", ".join(candidates[:3])
    )


def brand_not_found_response(
    locale: Locale, *, brand: str, available: Sequence[str]
) -> str:
    return _table(_BRAND_NOT_FOUND, locale).format(
        brand=brand, available=", ".join(available[:5]) or "-"
    )


def brand_empty_response(locale: Locale, *, brand: str) -> str:
    return _table(_BRAND_EMPTY, locale).format(brand=brand)


def catalog_overview_response(
    locale: Locale,
    *,
    total_products: int,
    categories: Sequence[tuple[str, int]],
    category_query: str | None = None,
) -> str:
    if not categories:
        return _table(_OVERVIEW_NONE, locale).format(query=category_query or "")
    listed = [f"{name} ({count})" for name, count in categories[:8]]
    text = _with_more(listed, len(categories), locale)
    if category_query:
        return _table(_OVERVIEW_FILTERED, locale).format(
            total=total_products,
            count=len(categories),
            query=category_query,
            categories=text,
        )
    return _table(_OVERVIEW, locale).format(
        total=total_products, count=len(categories), categories=text
    )


def price_range_response(
    locale: Locale,
    *,
    query: str | None,
    minimum: Decimal | None,
    maximum: Decimal | None,
    count: int,
) -> str:
    label = query or _table(
        {
            "pt-BR": "catálogo",
            "en": "the catalog",
            "es": "el catálogo",
            "ar": "الكتالوج",
            "de": "den Katalog",
            "fr": "le catalogue",
            "it": "il catalogo",
            "ja": "カタログ",
            "ko": "카탈로그",
            "ru": "каталог",
            "zh-CN": "目录",
        },
        locale,
    )
    if minimum is None or maximum is None or count <= 0:
        return _table(_PRICE_RANGE_EMPTY, locale).format(query=label)
    if minimum == maximum:
        return _table(_PRICE_RANGE, locale).format(
            query=label,
            minimum=format_brl(float(minimum), locale),
            maximum=format_brl(float(maximum), locale),
            count=count,
        )
    return _table(_PRICE_RANGE, locale).format(
        query=label,
        minimum=format_brl(float(minimum), locale),
        maximum=format_brl(float(maximum), locale),
        count=count,
    )


def count_products_response(
    locale: Locale,
    *,
    total: int,
    query: str | None = None,
    brand: str | None = None,
    category: str | None = None,
) -> str:
    label = brand or query or category
    if total <= 0:
        return _table(_COUNT_EMPTY, locale).format(filter=label or "-")
    if label:
        return _table(_COUNT_FILTERED, locale).format(count=total, filter=label)
    return _table(_COUNT, locale).format(count=total)
