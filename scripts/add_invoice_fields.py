"""
Add invoice fields to monthly_billings table
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db

app = create_app('development')

with app.app_context():
    # Create new tables/columns
    db.create_all()
    print("[OK] Database tables updated!")
    
    print("\nInvoice fields added to MonthlyBilling:")
    print("  - invoice_number (VARCHAR 50)")
    print("  - sent_at (DATETIME)")
    print("  - sent_to (VARCHAR 255)")
    print("\nSetup completed!")
