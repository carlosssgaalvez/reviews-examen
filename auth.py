import os
from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from database import db # Usamos db directamente
from datetime import datetime

# Colección de usuarios (opcional, pero buena práctica)
users_collection = db["users"]

router = APIRouter()
oauth = OAuth()

oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

@router.get("/login")
async def login(request: Request):
    redirect_uri = request.url_for('auth')
    # Parche HTTPS para Vercel
    if "vercel.app" in str(redirect_uri):
        redirect_uri = str(redirect_uri).replace("http://", "https://")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth")
async def auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        
        if user_info:
            # Guardamos al usuario en la sesión
            request.session['user'] = dict(user_info)
            # --- NUEVO: Guardamos el TOKEN completo para cumplir requisitos del examen ---
            # El examen pide timestamps de emisión y caducidad [cite: 346]
            request.session['token_data'] = {
                "access_token": token.get("access_token"),
                "expires_at": token.get("expires_at"),
                "created_at": datetime.now().timestamp() # Timestamp actual como emisión
            }
        
        return RedirectResponse(url='/')
    except Exception as e:
        print(f"Error auth: {e}")
        return RedirectResponse(url='/')

@router.get("/logout")
async def logout(request: Request):
    request.session.pop('user', None)
    request.session.pop('token_data', None)
    return RedirectResponse(url='/')