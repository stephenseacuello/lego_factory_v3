"""
Invoice PDF Generation Service
================================
Generates professional PDF invoices.
"""
from datetime import date
from typing import Dict, Any
import io


class InvoicePDFService:
    def __init__(self, session):
        self.session = session

    def generate_invoice_pdf(self, invoice_id: str) -> Dict[str, Any]:
        """Generate invoice PDF. Returns PDF bytes or error."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas
        except ImportError:
            return self._generate_text_invoice(invoice_id)

        from services.erp.financial_service import FinancialService
        service = FinancialService(self.session)

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Header
        c.setFont("Helvetica-Bold", 20)
        c.drawString(1 * inch, height - 1 * inch, "LEGO Factory")
        c.setFont("Helvetica", 10)
        c.drawString(1 * inch, height - 1.3 * inch, "Smart Manufacturing Platform")

        c.setFont("Helvetica-Bold", 14)
        c.drawString(1 * inch, height - 2 * inch, f"INVOICE #{invoice_id}")

        c.setFont("Helvetica", 10)
        c.drawString(1 * inch, height - 2.4 * inch, f"Date: {date.today().isoformat()}")
        c.drawString(1 * inch, height - 2.6 * inch, "Payment Terms: Net 30")

        # Table header
        y = height - 3.2 * inch
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1 * inch, y, "Item")
        c.drawString(4 * inch, y, "Qty")
        c.drawString(5 * inch, y, "Unit Price")
        c.drawString(6.5 * inch, y, "Total")

        c.line(1 * inch, y - 5, 7.5 * inch, y - 5)

        # Sample line items
        y -= 20
        c.setFont("Helvetica", 10)
        items = [
            ("LEGO Brick Set - Custom", 100, 12.50),
            ("3D Printing Service", 50, 8.75),
            ("Assembly & QC", 1, 250.00),
        ]
        subtotal = 0
        for desc, qty, price in items:
            total = qty * price
            subtotal += total
            c.drawString(1 * inch, y, desc)
            c.drawString(4 * inch, y, str(qty))
            c.drawString(5 * inch, y, f"${price:.2f}")
            c.drawString(6.5 * inch, y, f"${total:.2f}")
            y -= 18

        # Totals
        y -= 10
        c.line(5 * inch, y, 7.5 * inch, y)
        y -= 18
        c.drawString(5 * inch, y, f"Subtotal: ${subtotal:.2f}")
        tax = subtotal * 0.08
        y -= 18
        c.drawString(5 * inch, y, f"Tax (8%): ${tax:.2f}")
        y -= 18
        c.setFont("Helvetica-Bold", 11)
        c.drawString(5 * inch, y, f"TOTAL: ${subtotal + tax:.2f}")

        # Footer
        c.setFont("Helvetica", 8)
        c.drawString(1 * inch, 0.5 * inch, "LEGO Factory | Smart Manufacturing Platform | Payment due within 30 days")

        c.save()
        buffer.seek(0)

        return {
            'invoice_id': invoice_id,
            'pdf_bytes': buffer.getvalue(),
            'filename': f'invoice_{invoice_id}.pdf',
            'size_bytes': len(buffer.getvalue()),
        }

    def _generate_text_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Fallback text invoice when reportlab is not available."""
        lines = [
            "=" * 50,
            "LEGO Factory - INVOICE",
            "=" * 50,
            f"Invoice #: {invoice_id}",
            f"Date: {date.today().isoformat()}",
            "Payment Terms: Net 30",
            "-" * 50,
            f"{'Item':<30} {'Qty':>5} {'Price':>8} {'Total':>8}",
            "-" * 50,
            f"{'LEGO Brick Set':<30} {'100':>5} {'$12.50':>8} {'$1250.00':>8}",
            f"{'3D Printing':<30} {'50':>5} {'$8.75':>8} {'$437.50':>8}",
            f"{'Assembly & QC':<30} {'1':>5} {'$250.00':>8} {'$250.00':>8}",
            "-" * 50,
            f"{'Subtotal:':>45} $1,937.50",
            f"{'Tax (8%):':>45} $155.00",
            f"{'TOTAL:':>45} $2,092.50",
            "=" * 50,
        ]
        content = '\n'.join(lines)
        return {
            'invoice_id': invoice_id,
            'text_content': content,
            'format': 'text',
            'note': 'Install reportlab for PDF generation',
        }
