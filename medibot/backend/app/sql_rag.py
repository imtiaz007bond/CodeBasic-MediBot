"""Guarded SQL RAG. The database is read-only from this chain and SQL is SELECT-only."""
import re, sqlite3, json
from pathlib import Path
from .config import DATABASE_PATH
from .llm import generate
SCHEMA = """claims(claim_id TEXT, patient_id TEXT, patient_name TEXT, department TEXT, claim_type TEXT, diagnosis_code TEXT, insurer TEXT, claimed_amount REAL, approved_amount REAL, status TEXT, submitted_date TEXT, resolved_date TEXT)
maintenance_tickets(ticket_id TEXT, equipment_name TEXT, equipment_id TEXT, category TEXT, campus TEXT, issue_type TEXT, fault_code TEXT, raised_by TEXT, raised_date TEXT, resolved_date TEXT, status TEXT, resolution_note TEXT)"""
BLOCKED = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|grant|revoke|exec|execute)\b",re.I)
def clean_sql(raw: str) -> str:
    raw=re.sub(r"```(?:sql)?", "", raw, flags=re.I).strip().strip("`")
    match=re.search(r"\b(select|with)\b[\s\S]*",raw,re.I)
    if not match: raise ValueError("The generated query was not a SELECT statement")
    sql=match.group(0).strip().rstrip("; ")
    if ";" in sql or BLOCKED.search(sql) or not re.match(r"^(select|with)\b",sql,re.I): raise ValueError("Only a single read-only SELECT query is permitted")
    # SQL identifiers/table references are constrained to the provided schema.
    if re.search(r"\b(from|join)\s+(?!claims\b|maintenance_tickets\b)[A-Za-z_][A-Za-z0-9_]*",sql,re.I): raise ValueError("Query references a table outside the approved schema")
    return sql

def sql_rag_chain(question: str) -> str:
    """1) LLM generates SQL; 2) sanitize; 3) execute and verbalize result."""
    raw=generate("You translate questions into SQLite SQL. Use only claims and maintenance_tickets. Output one SELECT statement only, no markdown. Never query patient_name or patient_id unless explicitly asked. Use the actual schema provided.",f"Schema:\n{SCHEMA}\nQuestion: {question}\nSQL:")
    if raw.startswith("LLM is not configured"):
        return raw
    sql=clean_sql(raw)
    uri=f"file:{Path(DATABASE_PATH).resolve()}?mode=ro"
    with sqlite3.connect(uri,uri=True,timeout=5) as conn:
        conn.row_factory=sqlite3.Row
        conn.set_progress_handler(lambda: 1, 500000)
        rows=[dict(r) for r in conn.execute(sql).fetchmany(200)]
    answer=generate("Answer the user's database question using only the query result. State when no rows match. Do not infer beyond the result.",f"Question: {question}\nSQL: {sql}\nResult rows: {json.dumps(rows,default=str)}")
    return answer

def run_sql(question: str):
    raw=generate("You translate questions into SQLite SQL. Use only claims and maintenance_tickets. Output one SELECT statement only, no markdown. Never query patient_name or patient_id unless explicitly asked.",f"Schema:\n{SCHEMA}\nQuestion: {question}\nSQL:")
    sql=clean_sql(raw)
    with sqlite3.connect(f"file:{Path(DATABASE_PATH).resolve()}?mode=ro",uri=True) as conn:
        conn.row_factory=sqlite3.Row; rows=[dict(r) for r in conn.execute(sql).fetchmany(200)]
    return sql,rows
