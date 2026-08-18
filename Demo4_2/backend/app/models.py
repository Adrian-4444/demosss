from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, LargeBinary, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")  # 'user', 'admin'
    
    # Brute force lockout fields
    is_locked = Column(Boolean, default=False)
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Biometric profiles
    ml_model_blob = Column(LargeBinary, nullable=True)  # Saved scikit-learn model
    trained_algorithm = Column(String, nullable=True)  # E.g., 'Random Forest', 'SVM'
    baseline_stats = Column(Text, nullable=True)  # JSON representation of mean vectors
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    samples = relationship("KeystrokeSample", back_populates="user", cascade="all, delete-orphan")
    logs = relationship("AuthLog", back_populates="user", cascade="all, delete-orphan")


class KeystrokeSample(Base):
    __tablename__ = "keystroke_samples"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Features serialized as JSON strings for DB portability
    hold_times_json = Column(Text, nullable=False)
    flight_times_json = Column(Text, nullable=False)
    latencies_json = Column(Text, nullable=False)
    
    typing_speed = Column(Float, nullable=False)
    backspace_count = Column(Integer, default=0)
    error_rate = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="samples")


class AuthLog(Base):
    __tablename__ = "auth_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(Boolean, nullable=False)  # True = success, False = failed
    
    # Biometric scoring
    similarity_score = Column(Float, nullable=True)  # 0 to 100
    confidence_score = Column(Float, nullable=True)   # 0 to 100
    risk_score = Column(Float, nullable=True)         # 0 to 100
    risk_level = Column(String, nullable=True)         # 'Low', 'Medium', 'High'
    flagged_anomalies = Column(Text, nullable=True)    # JSON string list
    
    # Device details
    user_agent = Column(String, nullable=True)
    client_ip = Column(String, nullable=True)
    simulation_type = Column(String, default="None")  # E.g., 'CredentialStuffing', 'Bot'
    
    user = relationship("User", back_populates="logs")
