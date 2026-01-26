from fastapi import FastAPI
from app.routers import staff

app = FastAPI(title="GRACE AI Infrastructure")

# Inclusion of the Operations Layer
app.include_router(staff.router, prefix="/staff", tags=["operations"])

@app.get("/health")
async def health_check():
    return {"status": "operational", "version": "1.0.0"}