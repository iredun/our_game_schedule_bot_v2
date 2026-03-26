from telegram import InlineKeyboardButton, InlineKeyboardMarkup


TYPE_TEXT_ADD = {
    "i": "",
    "i+1": " от меня +1",
    "not_sure": " (под вопросом)",
}

REPLY_MARKUP = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("Я играю", callback_data="i"),
            InlineKeyboardButton("+1 от меня", callback_data="i+1"),
            InlineKeyboardButton("-1 от меня", callback_data="i-1"),
        ],
        [
            InlineKeyboardButton("Я под вопросом", callback_data="not_sure"),
            InlineKeyboardButton("Я не играю", callback_data="not_play"),
        ],
        [
            InlineKeyboardButton("Решить вопросы 😎", callback_data="check_not_sure"),
        ],
    ]
)
