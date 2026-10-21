import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
ROOT = Path(__file__).resolve().parents[2]
# Docker mounts the corpus at /app/data; local runs default to repository-root/data.
DATA_DIR = Path(os.getenv("DATA_DIR", str((Path(__file__).resolve().parents[2] / "data"))))
DATA_DIR = DATA_DIR.resolve()
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "mediassist.db")))
if not DATABASE_PATH.is_absolute(): DATABASE_PATH = (Path(__file__).resolve().parents[1] / DATABASE_PATH).resolve()
COLLECTION_ACCESS = {
    "general": ["doctor", "nurse", "billing_executive", "technician", "admin"],
    "clinical": ["doctor", "admin"],
    "nursing": ["doctor", "nurse", "admin"],
    "billing": ["billing_executive", "admin"],
    "equipment": ["technician", "admin"],
}
ROLE_COLLECTIONS = {role: [c for c, roles in COLLECTION_ACCESS.items() if role in roles] for role in ["doctor", "nurse", "billing_executive", "technician", "admin"]}
DEMO_USERS = {
    "dr.mehta": ("doctor123", "doctor"),
    "nurse.priya": ("nurse123", "nurse"),
    "billing.ravi": ("billing123", "billing_executive"),
    "tech.anand": ("tech123", "technician"),
    "admin.sys": ("admin123", "admin"),
}
