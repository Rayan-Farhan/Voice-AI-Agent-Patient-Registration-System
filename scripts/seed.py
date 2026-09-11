"""Insert demonstration patients so a fresh deployment has something to query.

Idempotent: re-running will not duplicate the seeded records.
"""

from datetime import date

from app.db import SessionLocal, init_db
from app.models import Patient

SEED_PATIENTS = [
    {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": date(1985, 3, 12),
        "sex": "Female",
        "phone_number": "4155550142",
        "email": "jane.doe@example.com",
        "address_line_1": "1200 Market Street",
        "address_line_2": "Apt 4B",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94102",
        "insurance_provider": "Blue Shield",
        "insurance_member_id": "BS123456789",
        "preferred_language": "English",
        "emergency_contact_name": "John Doe",
        "emergency_contact_phone": "4155550199",
    },
    {
        "first_name": "Carlos",
        "last_name": "Ramirez",
        "date_of_birth": date(1972, 11, 4),
        "sex": "Male",
        "phone_number": "2125550188",
        "address_line_1": "88 Broadway",
        "city": "New York",
        "state": "NY",
        "zip_code": "10004",
        "preferred_language": "Spanish",
    },
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        for record in SEED_PATIENTS:
            exists = (
                db.query(Patient)
                .filter(Patient.phone_number == record["phone_number"])
                .first()
            )
            if exists:
                print(f"skip  {record['first_name']} {record['last_name']} (already present)")
                continue
            db.add(Patient(**record))
            print(f"added {record['first_name']} {record['last_name']}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
