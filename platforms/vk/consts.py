from vkbottle import Callback, Keyboard, KeyboardButtonColor


TYPE_TEXT_ADD = {
    "i": "",
    "i+1": " от меня +1",
    "not_sure": " (под вопросом)",
}

REPLY_MARKUP = (
    Keyboard(inline=True)
    .add(
        Callback("Я играю", payload={"cmd": "i"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    .add(
        Callback("+1 от меня", payload={"cmd": "i+1"}),
        color=KeyboardButtonColor.PRIMARY,
    )
    .add(
        Callback("-1 от меня", payload={"cmd": "i-1"}),
        color=KeyboardButtonColor.NEGATIVE,
    )
    .row()
    .add(
        Callback("Я под вопросом", payload={"cmd": "not_sure"}),
        color=KeyboardButtonColor.SECONDARY,
    )
    .add(
        Callback("Я не играю", payload={"cmd": "not_play"}),
        color=KeyboardButtonColor.SECONDARY,
    )
    .row()
    .add(
        Callback("Решить вопросы", payload={"cmd": "check_not_sure"}),
        color=KeyboardButtonColor.PRIMARY,
    )
    .get_json()
)

