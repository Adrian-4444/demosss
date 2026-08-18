from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

class KeystrokeInput(BaseModel):
    hold_times: List[float] = Field(..., description="List of hold times in milliseconds for each keypress")
    flight_times: List[float] = Field(..., description="List of flight times between key releases and key presses")
    latencies: List[float] = Field(..., description="List of press-to-press latencies")
    typing_speed: float = Field(..., description="Typing speed in keys per second")
    backspace_count: int = Field(default=0)
    error_rate: float = Field(default=0.0)

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    keystroke_samples: List[KeystrokeInput] = Field(..., min_items=10)

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    keystroke_data: KeystrokeInput
    simulation_type: str = "None"  # 'None', 'CredentialStuffing', 'Bot', 'Impersonation'

class OTPValidation(BaseModel):
    email: EmailStr
    otp: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    user: UserResponse

class AuthLogResponse(BaseModel):
    id: int
    timestamp: datetime
    status: bool
    similarity_score: Optional[float] = None
    confidence_score: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    flagged_anomalies: Optional[str] = None
    user_agent: Optional[str] = None
    client_ip: Optional[str] = None
    simulation_type: str

    class Config:
        from_attributes = True

class UserStatsResponse(BaseModel):
    total_logins: int
    failed_logins: int
    avg_speed: float
    avg_hold: float
    avg_similarity: float
    history: List[AuthLogResponse]

class AdminStatsResponse(BaseModel):
    total_users: int
    total_attempts: int
    failed_attempts: int
    compromised_prevented: int
    daily_logins: List[dict]
    anomalies_distribution: List[dict]
    recent_attempts: List[AuthLogResponse]
