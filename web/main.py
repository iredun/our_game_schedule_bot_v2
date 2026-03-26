from fastapi import Depends, FastAPI, HTTPException, Response
from sqlalchemy.orm import Session

from core.config import get_settings
from db.session import get_session
from services.calendar_service import CalendarService


settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/calendar/{token}.ics")
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
