from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles # Import this
from fastapi.responses import FileResponse # Import this
from app.routers import v1
import os

app = FastAPI(
    title="RedactAI API",
    description="Privacy-First API",
    version="1.0.0"
)

# Mount the static directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(v1.router)

# Serve the HTML file on the homepage
@app.get("/")
def read_root():
    return FileResponse('app/static/index.html')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)