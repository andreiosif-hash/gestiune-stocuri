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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = FastAPI(title="API Gestiune Stocuri Mobilă")

# Configurare CORS pentru Frontend (Svelte)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurare conectare la baza de date MySQL (Aiven Cloud prin Environment Variables)
DB_HOST = os.getenv("DB_HOST", "mysql-2b58dbb-mysql-gestiune-stocuri.f.aivencloud.com")
DB_USER = os.getenv("DB_USER", "avnadmin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = int(os.getenv("DB_PORT", "27889"))
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


# CONFIGURARE FONT PENTRU DIACRITICE (UTF-8)
FONT_NAME = 'ArialCustom'
FONT_BOLD_NAME = 'ArialBoldCustom'

try:
    win_fonts = "C:\\Windows\\Fonts"
    arial_path = os.path.join(win_fonts, "arial.ttf")
    arial_bd_path = os.path.join(win_fonts, "arialbd.ttf")

    if os.path.exists(arial_path) and os.path.exists(arial_bd_path):
        pdfmetrics.registerFont(TTFont(FONT_NAME, arial_path))
        pdfmetrics.registerFont(TTFont(FONT_BOLD_NAME, arial_bd_path))
    else:
        pdfmetrics.registerFont(TTFont(FONT_NAME, "DejaVuSans.ttf"))
        pdfmetrics.registerFont(TTFont(FONT_BOLD_NAME, "DejaVuSans-Bold.ttf"))
except Exception:
    FONT_NAME = 'Helvetica'
    FONT_BOLD_NAME = 'Helvetica-Bold'


# Modele de date Pydantic
class ProdusCreate(BaseModel):
    nume: str
    categorie_id: int
    sku: str
    culoare: str = ""
    material: str = ""
    dimensiune: str = ""
    pret_achizitie: float
    pret_vanzare: float
    stoc_curent: int
    stoc_minim_alerta: int = 2


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
                    v.id AS varianta_id,
                    p.nume AS produs_nume,
                    v.sku,
                    v.culoare,
                    v.material,
                    v.dimensiune,
                    v.pret_achizitie,
                    v.pret_vanzare,
                    v.stoc_curent,
                    p.stoc_minim_alerta,
                    c.nume AS categorie_nume
                FROM variante_produse v
                JOIN produse p ON v.produs_id = p.id
                JOIN categorii c ON p.categorie_id = c.id
                ORDER BY v.id DESC
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
            cursor.execute("SELECT id FROM produse WHERE nume = %s", (produs.nume,))
            existent = cursor.fetchone()

            if existent:
                produs_id = existent["id"]
            else:
                cursor.execute(
                    "INSERT INTO produse (nume, categorie_id, stoc_minim_alerta) VALUES (%s, %s, %s)",
                    (produs.nume, produs.categorie_id, produs.stoc_minim_alerta)
                )
                produs_id = cursor.lastrowid

            query_varianta = """
                INSERT INTO variante_produse 
                (produs_id, sku, culoare, material, dimensiune, pret_achizitie, pret_vanzare, stoc_curent)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query_varianta, (
                produs_id,
                produs.sku,
                produs.culoare,
                produs.material,
                produs.dimensiune,
                produs.pret_achizitie,
                produs.pret_vanzare,
                produs.stoc_curent
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
                "UPDATE variante_produse SET stoc_curent = %s WHERE id = %s",
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
            cursor.execute("DELETE FROM variante_produse WHERE id = %s", (varianta_id,))
            conn.commit()
            return {"message": "Varianta a fost ștearsă!"}
    finally:
        conn.close()


@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    SUM(pret_achizitie * stoc_curent) as valoare_achizitie,
                    SUM(pret_vanzare * stoc_curent) as valoare_vanzare,
                    SUM(stoc_curent) as total_stoc
                FROM variante_produse
            """)
            totale = cursor.fetchone()

            cursor.execute("""
                SELECT COUNT(*) as stoc_critic 
                FROM variante_produse v
                JOIN produse p ON v.produs_id = p.id
                WHERE v.stoc_curent <= p.stoc_minim_alerta
            """)
            critic = cursor.fetchone()

            cursor.execute("""
                SELECT c.nume as categorie, SUM(v.stoc_curent) as stoc
                FROM variante_produse v
                JOIN produse p ON v.produs_id = p.id
                JOIN categorii c ON p.categorie_id = c.id
                GROUP BY c.nume
            """)
            stoc_categorii = cursor.fetchall()

            cursor.execute("""
                SELECT p.nume as produs, SUM(v.stoc_curent) as stoc
                FROM variante_produse v
                JOIN produse p ON v.produs_id = p.id
                GROUP BY p.nume
                ORDER BY stoc DESC
                LIMIT 5
            """)
            top_produse = cursor.fetchall()

            val_achizitie = float(totale["valoare_achizitie"] or 0)
            val_vanzare = float(totale["valoare_vanzare"] or 0)

            return {
                "valoare_achizitie": val_achizitie,
                "valoare_vanzare": val_vanzare,
                "profit_potential": val_vanzare - val_achizitie,
                "stoc_critic": critic["stoc_critic"],
                "total_stoc": totale["total_stoc"] or 0,
                "stoc_categorii": stoc_categorii,
                "top_produse": top_produse
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
                FROM variante_produse v
                JOIN produse p ON v.produs_id = p.id
                ORDER BY p.nume ASC
            """
            cursor.execute(query)
            produse = cursor.fetchall()
    finally:
        conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    elements = []

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName=FONT_BOLD_NAME,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=15
    )

    cell_style = ParagraphStyle(
        'TableCell',
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155")
    )

    header_style = ParagraphStyle(
        'TableHeader',
        fontName=FONT_BOLD_NAME,
        fontSize=10,
        leading=13,
        textColor=colors.whitesmoke
    )

    elements.append(Paragraph("Raport Inventar Stocuri - Mobilă", title_style))
    elements.append(Spacer(1, 10))

    data = [[
        Paragraph("Produs", header_style),
        Paragraph("SKU", header_style),
        Paragraph("Stoc", header_style),
        Paragraph("Preț Achiziție", header_style),
        Paragraph("Preț Vânzare", header_style)
    ]]

    for p in produse:
        data.append([
            Paragraph(str(p["produs_nume"]), cell_style),
            Paragraph(str(p["sku"]), cell_style),
            Paragraph(str(p["stoc_curent"]), cell_style),
            Paragraph(f"{float(p['pret_achizitie']):.2f} lei", cell_style),
            Paragraph(f"{float(p['pret_vanzare']):.2f} lei", cell_style)
        ])

    col_widths = [160, 110, 50, 110, 110]

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
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
                FROM variante_produse v
                JOIN produse p ON v.produs_id = p.id
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