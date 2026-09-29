import secrets

from pydantic import BaseModel,HttpUrl,field_validator
from fastapi import FastAPI,HTTPException
from sqlalchemy import String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

engine = create_engine(
    "sqlite:///./complaints.db",
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True)
    hex_code: Mapped[str] = mapped_column(
        String(16), unique=True, index=True, default=lambda: secrets.token_hex(8)
    )
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="under review")


Base.metadata.create_all(engine)


class ComplaintIn(BaseModel):
    category: str
    description: str
    url: HttpUrl | None = None

    @field_validator("url", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return v or None

class StatusUp(BaseModel):
    status: str

app = FastAPI()




@app.get("/")
def basic():
    return {"message": "Hello, World!"}

@app.post("/complaints")
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


@app.get("/complaints/{complaint_id}")
def get_status(complaint_id:str):
    with SessionLocal() as session:
        complaint=session.query(Complaint).filter(Complaint.hex_code==complaint_id).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        return {"category":complaint.category,"status":complaint.status}


