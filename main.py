from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from bson.objectid import ObjectId # Para buscar por ID
from dotenv import load_dotenv
import os
import httpx # Para geocoding
import cloudinary
import cloudinary.uploader
from database import check_db_connection, db
from auth import router as auth_router 
from datetime import datetime

load_dotenv()

# Configuración Cloudinary (Ya la tienes)
cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.include_router(auth_router)

# --- COLECCIÓN PRINCIPAL ---
reviews_collection = db["reviews"] # [cite: 333]

@app.on_event("startup")
def startup_event():
    check_db_connection()

# --- HOME: Listado de Reseñas y Mapa ---
@app.get("/")
async def home(request: Request, search_address: str = None):
    user = request.session.get('user')
    reviews = list(reviews_collection.find({}))
    
    # Lógica para centrar el mapa (Requisito: Búsqueda) 
    map_center = [36.7213, -4.4214] # Málaga por defecto
    if search_address:
         async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://nominatim.openstreetmap.org/search?q={search_address}&format=json",
                headers={'User-Agent': 'ReViewsApp/1.0'}
            )
            data = resp.json()
            if data:
                map_center = [float(data[0]['lat']), float(data[0]['lon'])]

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "user": user, 
        "reviews": reviews,
        "map_center": map_center
    })

# --- DETALLES DE UNA RESEÑA  ---
@app.get("/review/{id}")
async def review_detail(request: Request, id: str):
    user = request.session.get('user')
    if not user: return RedirectResponse("/")
    
    # Buscar reseña por ID
    review = reviews_collection.find_one({"_id": ObjectId(id)})
    
    return templates.TemplateResponse("detail.html", {
        "request": request, 
        "user": user, 
        "review": review
    })

# --- CREAR RESEÑA [cite: 349] ---
@app.post("/add")
async def add_review(
    request: Request, 
    establishment: str = Form(...), 
    address: str = Form(...),
    rating: int = Form(...), # Valoración 0-5
    image: UploadFile = File(None)
):
    user = request.session.get('user')
    token_data = request.session.get('token_data') # Datos técnicos del token
    
    if not user: return RedirectResponse("/")

    # 1. Subir Imagen
    image_url = ""
    if image and image.filename:
        try:
            res = cloudinary.uploader.upload(image.file)
            image_url = res.get("secure_url")
        except: pass

    # 2. Geocoding (Dirección -> Coordenadas) 
    lat, lon = 0.0, 0.0
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"https://nominatim.openstreetmap.org/search?q={address}&format=json",
                headers={'User-Agent': 'ReViewsApp/1.0'}
            )
            data = resp.json()
            if data:
                lat, lon = float(data[0]['lat']), float(data[0]['lon'])
        except: pass

    # 3. Guardar todo (incluyendo datos técnicos del token) [cite: 350, 351]
    new_review = {
        "establishment": establishment,
        "address": address,
        "rating": rating,
        "coordinates": {"lat": lat, "lon": lon},
        "image_url": image_url,
        # Datos del autor y token
        "author_email": user['email'],
        "author_name": user['name'],
        "token_details": token_data # Aquí guardamos el token completo
    }

    reviews_collection.insert_one(new_review)
    return RedirectResponse(url="/", status_code=303)