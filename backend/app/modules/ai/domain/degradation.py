"""Mensagem amigavel de degradacao do assistente (11 locales).

Usada quando o LLM local esta desligado, sem LM Studio ou falhou. Nunca
substitui a resposta neutra de seguranca (bloqueio/off-topic): e apenas o
aviso de "modo demonstracao", acompanhado dos cartoes deterministicos que o
backend conseguir montar. Texto puro, sem HTML/links.
"""

from __future__ import annotations

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
        "В README описано, как запустить модель в LM Studio."  # noqa: RUF001
    ),
    "zh-CN": "AI 助手当前处于本地演示模式。请参阅 README 了解如何使用 LM Studio 运行模型。",
}


def demo_mode_response(locale: Locale) -> str:
    """Aviso traduzido de modo demonstracao (fallback pt-BR)."""
    return _DEMO_MODE.get(locale.value, _DEMO_MODE["pt-BR"])


_GREETING: dict[str, str] = {
    "pt-BR": "Olá! Como posso ajudar com o catálogo Forja?",
    "en": "Hello! How can I help you with the Forja catalog?",
    "es": "¡Hola! ¿Cómo puedo ayudarte con el catálogo Forja?",
    "ar": "مرحبًا! كيف يمكنني مساعدتك في كتالوج Forja؟",
    "de": "Hallo! Wie kann ich Ihnen mit dem Forja-Katalog helfen?",
    "fr": "Bonjour ! Comment puis-je vous aider avec le catalogue Forja ?",
    "it": "Ciao! Come posso aiutarti con il catalogo Forja?",
    "ja": "こんにちは！Forjaカタログについてお手伝いできますか？",  # noqa: RUF001
    "ko": "안녕하세요! Forja 카탈로그에서 무엇을 도와드릴까요?",
    "ru": "Здравствуйте! Чем я могу помочь по каталогу Forja?",
    "zh-CN": "您好！我能帮您了解 Forja 目录吗？",  # noqa: RUF001
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
        "свяжитесь с командой Forja."  # noqa: RUF001
    ),
    "zh-CN": "有关商业条款、订单或政策，请登录账户或联系 Forja 团队。",  # noqa: RUF001
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
    "zh-CN": "访客价格需咨询；登录后可查看贵司价格。",  # noqa: RUF001
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
    "ru": "Не удалось найти этот заказ в вашем аккаунте.",  # noqa: RUF001
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
    "ru": "Не удалось проверить сейчас. Повторите попытку чуть позже.",  # noqa: RUF001
    "zh-CN": "现在无法查询，请稍后重试。",  # noqa: RUF001
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
    "ru": "Не удалось проверить значения в этом ответе. Правильные цены указаны в карточках ниже.",  # noqa: RUF001
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
    "ru": "Не удалось проверить детали этого ответа. См. карточки ниже.",  # noqa: RUF001
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
    "zh-CN": "要比较价格并查看最便宜的选项，请使用企业账户登录。",  # noqa: RUF001
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
