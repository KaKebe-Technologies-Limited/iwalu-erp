"""
Mock EFRIS provider for development, tests, and demos.

Generates deterministic-looking fiscal data so the full sales → receipt flow
can be exercised end-to-end without hitting any real EFRIS service.
"""
import hashlib
import uuid
from .base import FiscalizationProvider, FiscalResult


class MockProvider(FiscalizationProvider):
    name = 'mock'

    def submit_invoice(self, payload: dict) -> FiscalResult:
        # Deterministic FDN based on the invoice reference for reproducibility
        ref = payload.get('invoiceReference', uuid.uuid4().hex)
        digest = hashlib.sha256(str(ref).encode()).hexdigest()[:12].upper()

        fdn = f'MOCK-{digest}'
        invoice_id = f'MI-{uuid.uuid4().hex[:10].upper()}'
        verification_code = digest[:8]
        qr_code = (
            f'https://efris.ura.go.ug/invoice/verify?'
            f'fdn={fdn}&code={verification_code}'
        )

        return FiscalResult(
            success=True,
            fdn=fdn,
            invoice_id=invoice_id,
            verification_code=verification_code,
            qr_code=qr_code,
            raw_response={
                'provider': 'mock',
                'fdn': fdn,
                'invoice_id': invoice_id,
                'verification_code': verification_code,
                'qr_code': qr_code,
                'echo_payload': payload,
            },
        )
