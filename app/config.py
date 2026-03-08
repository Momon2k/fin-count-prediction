"""
Configuration management for the ML Service
"""
import os
import json
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""
    
    # API Configuration
    app_name: str = "Fingerlings Forecast ML Service"
    version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = int(os.getenv("PORT", "8000"))
    
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = environment == "development"
    
    # CORS Configuration
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:3001,https://*.railway.app,https://*.vercel.app",
        validation_alias="ALLOWED_ORIGINS"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        if not self.allowed_origins or self.allowed_origins.strip() == "":
            return ["*"]

        raw = self.allowed_origins.strip()

        if raw[0] in ("[", "{"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(origin).strip() for origin in parsed if str(origin).strip()]
            except json.JSONDecodeError:
                pass

        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    
    # Model Configuration
    models_dir: str = "app/models"
    unified_model_path: str = "app/models/unified_model.pkl"
    label_encoders_path: str = "app/models/label_encoders.pkl"
    categorical_encoder_path: str = "app/models/categorical_encoder.pkl"
    scaler_path: str = "app/models/scaler.pkl"
    tilapia_model_path: str = ""
    bangus_model_path: str = ""
    
    # Prediction Configuration
    max_forecast_days: int = 365
    default_forecast_days: int = 30
    
    # Database Configuration
    database_url: str = os.getenv("DATABASE_URL", "")
    database_echo: bool = debug  # Log SQL queries in debug mode


# Global settings instance
settings = Settings()
