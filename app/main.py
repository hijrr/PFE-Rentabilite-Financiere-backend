from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import Dashboard, GestionHistorique, GestionProjet, GestionRentabilite, GestionRole, GestionSalaries
from .routers import auth,GestionClient
from .database import Base,engine
app= FastAPI()
#Base.metadata.create_all(bind=engine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(GestionClient.router)
app.include_router(GestionSalaries.router)
app.include_router(GestionRentabilite.router)
app.include_router(GestionProjet.router)
app.include_router(GestionHistorique.router)
app.include_router(GestionRole.router)
app.include_router(Dashboard.router)
@app.get("/ahmeddd")
def read_root():
    return {"Hello": "World rahma  and amine gbh"}   

