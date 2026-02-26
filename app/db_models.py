"""
SQLAlchemy ORM models for database tables
"""
from sqlalchemy import Column, Integer, String, Date, TIMESTAMP, Text, ForeignKey
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class PredictionRequest(Base):
    """Model for prediction requests"""
    __tablename__ = "prediction_requests"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(String(36), unique=True, index=True, nullable=False)
    species = Column(String(50), nullable=False, index=True)
    province = Column(String(100), nullable=False, index=True)
    city = Column(String(100), nullable=False, index=True)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Relationship to predictions
    predictions = relationship("Prediction", back_populates="request", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PredictionRequest(id={self.id}, request_id={self.request_id}, species={self.species})>"


class Prediction(Base):
    """Model for individual predictions"""
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(String(36), ForeignKey("prediction_requests.request_id"), nullable=False, index=True)
    prediction_date = Column(Date, nullable=False, index=True)
    predicted_harvest = Column(DOUBLE, nullable=False)
    confidence_lower = Column(DOUBLE, nullable=True)
    confidence_upper = Column(DOUBLE, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    
    # Relationship to request
    request = relationship("PredictionRequest", back_populates="predictions")
    
    def __repr__(self):
        return f"<Prediction(id={self.id}, date={self.prediction_date}, harvest={self.predicted_harvest})>"
