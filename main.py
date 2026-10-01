import secrets
import os
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel,HttpUrl,field_validator
from fastapi import FastAPI,HTTPException,Header,Depends,Path
from sqlalchemy import String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

load_dotenv()

MOD_PASSWORD = os.environ["MOD_PASSWORD"]

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./complaints.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)


SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True)
    hex_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, default=lambda: secrets.token_hex(8))
    category: Mapped[str] = mapped_column(String(15))
    description: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="SUBMITTED")


Base.metadata.create_all(engine)


class ComplaintIn(BaseModel):
    category: Literal["Security","Harassment","Corruption","Technical","Other"]
    description: str
    url: HttpUrl | None = None

    @field_validator("url", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return v or None

class StatusUp(BaseModel):
    status: Literal["SUBMITTED", "UNDER REVIEW", "RESOLVED"]


def require_mod(x_mod_password: str = Header(...)):
    if not secrets.compare_digest(x_mod_password, MOD_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid credentials")

app = FastAPI()


@app.post("/complaints",tags=["Public"])
def create_complaint(data:ComplaintIn):
    with SessionLocal() as session:
        complaint=Complaint(
            category = data.category,
            description = data.description,
            url = str(data.url) if data.url else None,
        )
        session.add(complaint)
        session.commit()
        session.refresh(complaint)
        return{"hex_code":complaint.hex_code,"status":complaint.status}


@app.get("/complaints/{complaint_id}",tags=["Public"])
def get_status(complaint_id:str=Path(...,description="Hex code of the complaint",examples="e19e9a09c57f94d1")):
    with SessionLocal() as session:
        complaint=session.query(Complaint).filter(Complaint.hex_code==complaint_id).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        return {"category":complaint.category,"status":complaint.status}


@app.get("/mod/complaints",dependencies=[Depends(require_mod)],tags=["Moderator"])
def get_data(category:str | None=None, status:str | None=None):
    with SessionLocal() as session:
        query=session.query(Complaint)
        if category:
            query=query.filter(Complaint.category==category)
        if status:
            query=query.filter(Complaint.status==status)

        results=query.all()
        return results

@app.patch("/mod/complaints/{complaint_id}",dependencies=[Depends(require_mod)],tags=["Moderator"])
def update_status(complaint_id:str, status:StatusUp):
    with SessionLocal() as session:
        complaint = session.query(Complaint).filter(Complaint.hex_code == complaint_id).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        complaint.status = status.status
        session.commit()
        return {"hex_code": complaint.hex_code, "status": complaint.status}