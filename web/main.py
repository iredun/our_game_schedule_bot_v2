from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from core.config import get_settings
from db.session import get_session
from services.calendar_service import CalendarService
from web.api.telegram import router as telegram_api_router
from web.routes.pages import router as pages_router


settings = get_settings()
WEB_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
app.include_router(pages_router)
app.include_router(telegram_api_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/calendar/{token}.ics", tags=["calendar"])
def calendar_feed(token: str, session: Session = Depends(get_session)) -> Response:
    service = CalendarService(session)
    calendar_token, games = service.get_games_by_token(token)
    if calendar_token is None:
        raise HTTPException(status_code=404, detail="Calendar token not found")

    calendar_name = calendar_token.user.display_name or f"user-{calendar_token.user_id}"
    body = service.render_ical(calendar_name=calendar_name, games=games)
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'inline; filename="{token}.ics"',
            "Cache-Control": "private, max-age=300",
        },
    )
