from fastapi import FastAPI

from backend.api import deposits, stats, users, webhooks

app = FastAPI(title="Sales CRM Bot Backend")

app.include_router(deposits.router)
app.include_router(stats.router)
app.include_router(users.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
