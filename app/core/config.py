import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Variables obligatorias
    OPENAI_API_KEY: str
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_PHONE_NUMBER: str
    GOOGLE_SHEET_NAME: str
    
    # --- CREDENCIALES DE GOOGLE (Doble sistema) ---
    # Archivo físico (para local) - Lo hacemos opcional
    GOOGLE_CREDENTIALS_FILE: Optional[str] = "google_credentials.json"
    # Contenido JSON (para Railway) - Nuevo
    GOOGLE_CREDENTIALS_JSON: Optional[str] = None
    
    # Otras variables (Opcionales para evitar errores si no están en .env)
    SLACK_WEBHOOK_URL: Optional[str] = None
    APIFY_TOKEN: Optional[str] = None

    # Variables de Identidad
    AGENT_NAME: str = "Pedro"
    COMPANY_NAME: str = "Violet Wave"
    NICHE: str = "Odontólogos y Clínicas Dentales"

    class Config:
        env_file = ".env"
        extra = "ignore" 

settings = Settings()