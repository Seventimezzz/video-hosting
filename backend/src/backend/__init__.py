from fastapi import FastAPI

from backend.routes.authorization.auth import router as auth_router
from backend.routes.video.video import router as video_router

app = FastAPI()


app.include_router(auth_router)
app.include_router(video_router)


@app.get("/health")
def health():
    return {"status": "ok"}
