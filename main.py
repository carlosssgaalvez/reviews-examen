from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from dotenv import load_dotenv
import os
import cloudinary
import cloudinary.uploader
from database import check_db_connection, db # Importamos db directamente
from auth import router as auth_router 

load_dotenv()

# --- CONFIGURACIÓN CLOUDINARY (IGUAL) ---
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

# --- CONFIGURACIÓN DE COLECCIONES ---
# Mañana cambias "items" por lo que pida el examen (ej: "books", "movies")
items_collection = db["items_genericos"] 

@app.on_event("startup")
def startup_event():
    check_db_connection()

# --- RUTA 1: HOME (Listar cosas) ---
@app.get("/")
async def home(request: Request):
    user_session = request.session.get('user')
    
    # Datos por defecto
    context = {
        "request": request, 
        "user": user_session, 
        "items": []
    }

    if user_session:
        # Recuperar todos los items (o solo los del usuario, según pida el examen)
        # Opción A: Ver todo lo que hay en la BD (tipo muro público)
        items_cursor = items_collection.find({})
        
        # Opción B: Ver solo MIS cosas (descomentar si el examen lo pide)
        # items_cursor = items_collection.find({"owner_email": user_session['email']})
        
        # Convertimos el cursor a lista
        context["items"] = list(items_cursor)
    
    return templates.TemplateResponse("index.html", context)

# --- RUTA 2: AÑADIR (Crear cosas con imagen opcional) ---
@app.post("/add")
async def add_item(
    request: Request, 
    titulo: str = Form(...), # Campo genérico 1
    descripcion: str = Form(...), # Campo genérico 2
    image: UploadFile = File(None)
):
    user_session = request.session.get('user')
    if not user_session:
        return RedirectResponse(url="/")

    # 1. Subir imagen (Código reutilizable siempre)
    image_url = ""
    if image and image.filename:
        try:
            upload_result = cloudinary.uploader.upload(image.file)
            image_url = upload_result.get("secure_url")
        except Exception as e:
            print(f"Error imagen: {e}")

    # 2. Crear el objeto
    new_item = {
        "titulo": titulo,
        "descripcion": descripcion,
        "image_url": image_url,
        "owner_email": user_session['email'],
        "owner_name": user_session['name']
    }

    # 3. Guardar
    items_collection.insert_one(new_item)

    return RedirectResponse(url="/", status_code=303)

# --- RUTA 3: BORRAR (Casi siempre piden borrar) ---
@app.post("/delete")
async def delete_item(request: Request, titulo: str = Form(...)):
    # Borramos por título (o por ID si fuera más complejo)
    items_collection.delete_one({"titulo": titulo})
    return RedirectResponse(url="/", status_code=303)