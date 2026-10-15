import os

class Settings:
    # URL base del servicio Core (Django)
    CORE_URL: str = os.getenv("CORE_URL", "http://core:8000")
    
    # Token de autenticación de servicio compartido con Core
    CORE_SERVICE_TOKEN: str = os.getenv("CORE_SERVICE_TOKEN", "")
    
    # Orígenes permitidos para CORS (por ser widget embebible en sitios de terceros, por defecto "*")
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # Puerto del servicio
    PORT: int = int(os.getenv("PORT", "8006"))

settings = Settings()
