import os
import io
import csv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import pymysql

# Module ReportLab pentru generare PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = FastAPI(title="API Gestiune Stocuri Mobilă")

# Configurare CORS pentru a permite accesul din Frontend (Svelte)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurare conectare la baza de date MySQL (Aiven Cloud)
DB_HOST = os.getenv("DB_HOST", "mysql-2b58dbb-andreiiosif00-c9fa.g.aivencloud.com")
DB_USER = os.getenv("DB_USER", "avnadmin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")  # Citită din mediul de rulare
DB_PORT = int(os.getenv("DB_PORT", "24340"))
DB_NAME = os.getenv("DB_NAME", "defaultdb")


def get_db_connection():
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare conectare Baza de Date: {str(e)}")


# Modele de date Pydantic
class ProdusCreate(BaseModel):
    produs_nume: str
    categorie_id: int
    sku: str
    culoare: str
    material: str
    dimensiune: str
    pret_achizitie: float
    pret_vanzare: float
    stoc_curent: int
    stoc_minim_alerta: int


class StocUpdate(BaseModel):
    stoc_curent: int


@app.get("/")
def read_root():
    return {"message": "API Gestiune Stocuri Mobilă este funcțional!"}


@app.get("/api/produse")
def get_produse():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    v.varianta_id,
                    p.nume AS produs_nume,
                    v.sku,
                    v.culoare,
                    v.material,
                    v.dimensiune,
                    v.pret_achizitie,
                    v.pret_vanzare,
                    v.stoc_curent,
                    v.stoc_minim_alerta,
                    c.nume AS categorie_nume
                FROM VarianteProdus v
                JOIN Produse p ON v.produs_id = p.produs_id
                JOIN Categorii c ON p.categorie_id = c.categorie_id
                ORDER BY v.varianta_id DESC
            """
            cursor.execute(query)
            produse = cursor.fetchall()
            return produse
    finally:
        conn.close()


@app.post("/api/produse")
def create_produs(produs: ProdusCreate):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Inserare sau preluare produs de bază
            cursor.execute("SELECT produs_id FROM Produse WHERE nume = %s", (produs.produs_nume,))
            existent = cursor.fetchone()

            if existent:
                produs_id = existent["produs_id"]
            else:
                cursor.execute(
                    "INSERT INTO Produse (nume, categorie_id) VALUES (%s, %s)",
                    (produs.produs_nume, produs.categorie_id)
                )
                produs_id = cursor.lastrowid

            # 2. Inserare variantă de produs
            query_varianta = """
                INSERT INTO VarianteProdus 
                (produs_id, sku, culoare, material, dimensiune, pret_achizitie, pret_vanzare, stoc_curent, stoc_minim_alerta)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query_varianta, (
                produs_id,
                produs.sku,
                produs.culoare,
                produs.material,
                produs.dimensiune,
                produs.pret_achizitie,
                produs.pret_vanzare,
                produs.stoc_curent,
                produs.stoc_minim_alerta
            ))
            conn.commit()
            return {"message": "Produs adăugat cu succes!"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Eroare la adăugarea produsului: {str(e)}")
    finally:
        conn.close()


@app.put("/api/variante/{varianta_id}/stoc")
def update_stoc(varianta_id: int, stoc_data: StocUpdate):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE VarianteProdus SET stoc_curent = %s WHERE varianta_id = %s",
                (stoc_data.stoc_curent, varianta_id)
            )
            conn.commit()
            return {"message": "Stoc actualizat cu succes!"}
    finally:
        conn.close()


@app.delete("/api/variante/{varianta_id}")
def delete_varianta(varianta_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM VarianteProdus WHERE varianta_id = %s", (varianta_id,))
            conn.commit()
            return {"message": "Varianta a fost ștearsă!"}
    finally:
        conn.close()


@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Valoare totală stoc achiziție și vânzare
            cursor.execute("""
                SELECT 
                    SUM(pret_achizitie * stoc_curent) as valoare_achizitie,
                    SUM(pret_vanzare * stoc_curent) as valoare_vanzare,
                    SUM(stoc_curent) as total_stoc
                FROM VarianteProdus
            """)
            totale = cursor.fetchone()

            # Produse în stoc critic
            cursor.execute("""
                SELECT COUNT(*) as stoc_critic 
                FROM VarianteProdus 
                WHERE stoc_curent <= stoc_minim_alerta
            """)
            critic = cursor.fetchone()

            val_achizitie = float(totale["valoare_achizitie"] or 0)
            val_vanzare = float(totale["valoare_vanzare"] or 0)

            return {
                "valoare_achizitie": val_achizitie,
                "valoare_vanzare": val_vanzare,
                "profit_potential": val_vanzare - val_achizitie,
                "stoc_critic": critic["stoc_critic"],
                "total_stoc": totale["total_stoc"] or 0
            }
    finally:
        conn.close()


@app.get("/api/raport/pdf")
def export_pdf():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    p.nume AS produs_nume,
                    v.sku,
                    v.stoc_curent,
                    v.pret_achizitie,
                    v.pret_vanzare
                FROM VarianteProdus v
                JOIN Produse p ON v.produs_id = p.produs_id
            """
            cursor.execute(query)
            produse = cursor.fetchall()
    finally:
        conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, alignment=1)

    elements.append(Paragraph("Raport Inventar Stocuri - Mobilă", title_style))
    elements.append(Spacer(1, 20))

    data = [["Produs", "SKU", "Stoc", "Preț Achiziție", "Preț Vânzare"]]
    for p in produse:
        data.append([
            p["produs_nume"],
            p["sku"],
            str(p["stoc_curent"]),
            f"{p['pret_achizitie']:.2f} lei",
            f"{p['pret_vanzare']:.2f} lei"
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)

    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=raport_stoc.pdf"}
    )


@app.get("/api/raport/csv")
def export_csv():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    p.nume AS produs_nume,
                    v.sku,
                    v.culoare,
                    v.material,
                    v.stoc_curent,
                    v.pret_achizitie,
                    v.pret_vanzare
                FROM VarianteProdus v
                JOIN Produse p ON v.produs_id = p.produs_id
            """
            cursor.execute(query)
            rows = cursor.fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Produs", "SKU", "Culoare", "Material", "Stoc Curent", "Pret Achizitie (lei)", "Pret Vanzare (lei)"])

    for r in rows:
        writer.writerow([
            r["produs_nume"],
            r["sku"],
            r["culoare"],
            r["material"],
            r["stoc_curent"],
            f"{r['pret_achizitie']:.2f}",
            f"{r['pret_vanzare']:.2f}"
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=raport_stoc.csv"}
    )