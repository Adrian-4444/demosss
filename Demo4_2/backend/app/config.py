import os

class Settings:
    PROJECT_NAME: str = "Keystroke Dynamics Authentication System"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "7d4bfa846cde6e24db498fe717c385a86d2678bb09827c191a27e7f9a7d3c8c1")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # SQLite local DB as default
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./keystroke_auth.db")
    
    # Keystroke Biometrics Settings
    REQUIRED_TRAINING_SAMPLES: int = 10
    BIOMETRIC_SIMILARITY_THRESHOLD: float = 70.0  # 0 to 100% similarity threshold
    MAX_FAILED_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    
settings = Settings()
