import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from db.database import Base, engine
from routes import artifact_routes, document_routes


Base.metadata.create_all(bind=engine)

os.makedirs("uploads/table", exist_ok=True)
os.makedirs("uploads/image", exist_ok=True)
os.makedirs("uploads/attachment", exist_ok=True)
os.makedirs("generated_docs", exist_ok=True)

app = FastAPI(title="Documentation Module")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(document_routes.router)
app.include_router(artifact_routes.router)

@app.get("/")
async def root():
    return {"message": "Documentation Module API"}


if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
