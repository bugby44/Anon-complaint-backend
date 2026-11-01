import secrets
import os
from fpdf import FPDF
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel,HttpUrl,field_validator
from fastapi import FastAPI,HTTPException,Header,Depends,Path,Response
from sqlalchemy import String, Text, create_engine,LargeBinary
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

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

class Report(Base):
    __tablename__ = "reports"

    id:Mapped[int] = mapped_column(primary_key=True)
    pdf:Mapped[bytes]=mapped_column(LargeBinary,deferred=True)


Base.metadata.create_all(engine)


class ComplaintIn(BaseModel):
    category: Literal["Security","Harassment","Corruption","Technical","Other"]
    description: str
    url: HttpUrl | None = None

    @field_validator("url", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return v or None

NEXT_STATUS = {
    "SUBMITTED": "UNDER REVIEW",
    "UNDER REVIEW": "RESOLVED",
    "RESOLVED": None,
}


class StatusUp(BaseModel):
    status: Literal["SUBMITTED", "UNDER REVIEW", "RESOLVED"]


def safe(text):
    return str(text).encode("latin-1", "replace").decode("latin-1")


def build_report(complaints, category, status):
    filters = []
    if category:
        filters.append(f"category: {category}")
    if status:
        filters.append(f"status: {status}")
    subtitle = ", ".join(filters) if filters else "all complaints"

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Complaints Report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"{len(complaints)} complaints ({subtitle})", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    for c in complaints:
        pdf.set_font("Arial", "B", 10)
        pdf.multi_cell(0, 6, f"{c.hex_code}   {c.category}   {c.status}")
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 6, safe(c.description))
        pdf.multi_cell(0, 6, safe(f"proof: {c.url or 'none'}"))
        pdf.ln(4)

    return bytes(pdf.output())


def require_mod(x_mod_password: str = Header(...)):
    if not secrets.compare_digest(x_mod_password, MOD_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid credentials")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://rdchampion.me"

    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")
@app.post("/complaints",tags=["Public"])
def create_complaint(data:ComplaintIn):
    """
       Submit an anonymous complaint.

       Category must be one of: Security, Harassment, Corruption, Technical, Other.
       Returns a hex code, save it, it's the only way to check your status later.
       """
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
    """
    Enter hex code of the complaint to get its status.
    """
    with SessionLocal() as session:
        complaint=session.query(Complaint).filter(Complaint.hex_code==complaint_id).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        return {"category":complaint.category,"status":complaint.status}


@app.get("/mod/complaints",dependencies=[Depends(require_mod)],tags=["Moderator"])
def get_data(category:str | None=None, status:str | None=None):
    """
    Enter the mod password to get access to all complaints.

    Complaints can be filtered by category or status.

    """
    with SessionLocal() as session:
        query=session.query(Complaint)
        if category:
            query=query.filter(Complaint.category==category)
        if status:
            query=query.filter(Complaint.status==status)

        results=query.all()
        pdf_bytes=build_report(results, category, status)

        session.add(Report(pdf=pdf_bytes))
        session.commit()
        return Response(content=pdf_bytes, media_type="application/pdf",headers={"Content-Disposition": 'attachment; filename="complaints.pdf"'},)


@app.patch("/mod/complaints/{complaint_id}",dependencies=[Depends(require_mod)],tags=["Moderator"])
def update_status(complaint_id:str, status:StatusUp):
    """
    Enter the mod password to update the status of a complaint.

    Status moves in order: SUBMITTED to UNDER REVIEW to RESOLVED.
    Skipping a step or going backwards is rejected with a 409.
    """
    with SessionLocal() as session:
        complaint = session.query(Complaint).filter(Complaint.hex_code == complaint_id).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        if status.status != NEXT_STATUS.get(complaint.status):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot move from {complaint.status} to {status.status}",
            )

        complaint.status = status.status
        session.commit()
        return {"hex_code": complaint.hex_code, "status": complaint.status}
