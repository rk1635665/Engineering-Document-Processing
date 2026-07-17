"""
Run once to populate the database with data equivalent to the frontend's
original mock JSON files, so the app looks identical the first time you
switch it over to the real API. Safe to re-run — it wipes and reseeds.

    python -m app.seed
"""

from datetime import datetime, timedelta, timezone

from .database import Base, engine, SessionLocal
from . import models


def run():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    now = datetime.now(timezone.utc)

    def days_ago(n):
        return now - timedelta(days=n)

    docs = {
#        "doc-1042": models.Document(
#            id="doc-1042", name="PSV-500A_Nameplate.jpg", doc_type="Nameplate",
#            revision="Rev. 2", status="completed", uploaded_at=days_ago(1),
#        ),
#        "doc-1041": models.Document(
#            id="doc-1041", name="Unit-12_PID-0034.pdf", doc_type="P&ID",
#            revision="Rev. C", status="processing", uploaded_at=days_ago(1),
#        ),
#        "doc-1040": models.Document(
#            id="doc-1040", name="NORD-Drive_MX56.png", doc_type="Nameplate",
#            revision="Rev. 1", status="review", uploaded_at=days_ago(2),
#        ),
#        "doc-1039": models.Document(
#            id="doc-1039", name="Compressor-Skid_GA-Drawing.dwg", doc_type="General Arrangement",
#            revision="Rev. B", status="completed", uploaded_at=days_ago(3),
#        ),
#        "doc-1038": models.Document(
#            id="doc-1038", name="Unit-12_PID-0031.pdf", doc_type="P&ID",
#            revision="Rev. D", status="failed", uploaded_at=days_ago(4),
#        ),
#        "doc-1037": models.Document(
#            id="doc-1037", name="PT-220_Nameplate.jpg", doc_type="Nameplate",
#            revision="Rev. 1", status="queued", uploaded_at=days_ago(0),
#        ),
#        "doc-1036": models.Document(
#            id="doc-1036", name="PSV-500B_Nameplate.jpg", doc_type="Nameplate",
#            revision="Rev. 2", status="completed", uploaded_at=days_ago(5),
#        ),
#        "doc-1035": models.Document(
#            id="doc-1035", name="LT-410_Nameplate.jpg", doc_type="Nameplate",
#            revision="Rev. A", status="review", uploaded_at=days_ago(5),
#        ),
#        "doc-1034": models.Document(
#            id="doc-1034", name="Gearbox-Reducer_GA.dwg", doc_type="General Arrangement",
#            revision="Rev. 1", status="completed", uploaded_at=days_ago(6),
#        ),
#        "doc-1033": models.Document(
#            id="doc-1033", name="NORD-Drive_MX56B.png", doc_type="Nameplate",
#            revision="Rev. 2", status="completed", uploaded_at=days_ago(6),
#        ),
    }
    db.add_all(docs.values())

    parts = [
#        ("doc-1042", "PSV-500A", "SA-516 Gr. 70", "2 in x 3 in", "±0.05 mm", 96),
#        ("doc-1037", "PT-220", "SS316L", "1/2 in NPT", "±0.10 mm", 74),
#        ("doc-1040", "MX56-DRV", "Cast Iron GG25", "180 x 140 x 96 mm", "±0.20 mm", 88),
#        ("doc-1041", "FT-0034", "A105", "3 in Sch. 40", "±0.15 mm", 91),
#        ("doc-1038", "TIC-1102", "SS304", "1 in NPT", "±0.05 mm", 62),
#        ("doc-1039", "CMP-SKID-01", "ASTM A36", "4200 x 1800 x 2100 mm", "±1.00 mm", 84),
#        ("doc-1036", "PSV-500B", "SA-516 Gr. 70", "2 in x 3 in", "±0.05 mm", 97),
#        ("doc-1035", "LT-410", "Hastelloy C276", "3/4 in NPT", "±0.08 mm", 69),
#        ("doc-1041", "PIC-2210", "SS316", "1/2 in NPT", "±0.05 mm", 93),
#        ("doc-1034", "GB-REDUCER-7", "Cast Steel WCB", "310 x 220 x 180 mm", "±0.30 mm", 79),
#        ("doc-1038", "XV-0091", "A105", "4 in Sch. 80", "±0.15 mm", 58),
#        ("doc-1033", "MX56-DRV-B", "Cast Iron GG25", "180 x 140 x 96 mm", "±0.20 mm", 95),
    ]
    for doc_id, part_number, material, dimensions, tolerance, confidence in parts:
        db.add(
            models.ExtractedPart(
                document_id=doc_id, part_number=part_number, material=material,
                dimensions=dimensions, tolerance=tolerance, confidence=confidence,
            )
        )

    review_fields = [
#        ("part_number", "Part Number", "PSV-500A", 97),
#        ("manufacturer", "Manufacturer", "Anderson Greenwood", 92),
#        ("material", "Material", "SA-516 Gr. 70", 89),
#        ("set_pressure", "Set Pressure", "150 psig", 95),
#        ("orifice_size", "Orifice Size", "\"D\"", 61),
#        ("tolerance", "Tolerance", "±0.05 mm", 74),
#        ("serial_number", "Serial Number", "SN-88214-C", 58),
    ]
    for field_key, label, value, confidence in review_fields:
        db.add(
            models.ReviewField(
                document_id="doc-1042", field_key=field_key, label=label,
                value=value, confidence=confidence,
            )
        )

    notifications = [
#        ("success", "Extraction completed", "PSV-500A_Nameplate.jpg finished processing at 96% confidence.", 2),
#        ("warning", "Low confidence field", "Serial Number on PSV-500A dropped to 58% — review recommended.", 18),
#        ("danger", "Extraction failed", "Unit-12_PID-0031.pdf could not be parsed. Try re-uploading.", 60),
#        ("info", "Revision comparison ready", "Rev. A vs Rev. B diff for Unit-12 P&ID is ready to view.", 180),
#        ("success", "Document approved", "Compressor-Skid_GA-Drawing.dwg was approved by review.", 1440),
    ]
    for tone, title, message, minutes_ago in notifications:
        db.add(
            models.Notification(
                tone=tone, title=title, message=message,
                created_at=now - timedelta(minutes=minutes_ago),
                read=minutes_ago > 60,
            )
        )

    db.commit()
    db.close()
    print("Seed complete.")


if __name__ == "__main__":
    run()
