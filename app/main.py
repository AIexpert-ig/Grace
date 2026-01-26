from fastapi import FastAPI
from app.routers import staff # Ensure this import is here

app = FastAPI(title="GRACE AI Infrastructure")

# This MUST be here to handle /staff/escalate
app.include_router(staff.router, prefix="/staff")

@app.get("/")
async def root():
    return {"message": "Grace Gateway Online"}