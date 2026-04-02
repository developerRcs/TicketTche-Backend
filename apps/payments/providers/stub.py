"""
Stub payment gateway for development and testing.

Simulates realistic payment behavior without calling any external service.
Pix payments show a QR code and auto-approve after 8 seconds (simulates scan).
Card payments are approved instantly.
"""
import time
import uuid
from decimal import Decimal
from typing import Optional

from apps.payments.gateway import (
    PaymentGateway,
    PaymentMethod,
    PaymentRequest,
    PaymentResponse,
    PaymentStatus,
    RefundResponse,
)

# Tracks when each stub Pix payment was created (gateway_id → timestamp)
_PIX_CREATED_AT: dict[str, float] = {}
_PIX_AUTO_APPROVE_SECONDS = 8


class StubGateway(PaymentGateway):
    """
    Development-only stub gateway.
    Pix: returns PENDING + fake QR code, auto-approves after 8s of polling.
    Cards: approved instantly.
    Replace with MercadoPagoGateway in production via PAYMENT_GATEWAY_CLASS.
    """

    def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        gateway_id = f"stub_{uuid.uuid4().hex[:16]}"

        if request.method == PaymentMethod.PIX:
            _PIX_CREATED_AT[gateway_id] = time.time()
            response = PaymentResponse(
                gateway_id=gateway_id,
                status=PaymentStatus.PENDING,
                method=request.method,
                amount=request.amount,
                reference=request.reference,
            )
            response.pix_qr_code = (
                f"00020126580014BR.GOV.BCB.PIX0136{gateway_id}"
                "5204000053039865802BR5925TICKETTCHE PAGAMENTOS"
                "6009SAO PAULO62070503***6304STUB"
            )
            response.pix_qr_code_image = ""
        else:
            # Credit / debit — instant approval
            response = PaymentResponse(
                gateway_id=gateway_id,
                status=PaymentStatus.APPROVED,
                method=request.method,
                amount=request.amount,
                reference=request.reference,
            )

        return response

    def capture_payment(self, gateway_id: str) -> PaymentResponse:
        return PaymentResponse(
            gateway_id=gateway_id,
            status=PaymentStatus.APPROVED,
            method=PaymentMethod.CREDIT_CARD,
            amount=Decimal("0.00"),
            reference="",
        )

    def get_payment_status(self, gateway_id: str) -> PaymentResponse:
        created_at = _PIX_CREATED_AT.get(gateway_id)
        if created_at and (time.time() - created_at) >= _PIX_AUTO_APPROVE_SECONDS:
            status = PaymentStatus.APPROVED
        else:
            status = PaymentStatus.PENDING

        return PaymentResponse(
            gateway_id=gateway_id,
            status=status,
            method=PaymentMethod.PIX,
            amount=Decimal("0.00"),
            reference="",
        )

    def refund_payment(self, gateway_id: str, amount: Optional[Decimal] = None) -> RefundResponse:
        return RefundResponse(
            gateway_id=gateway_id,
            status=PaymentStatus.REFUNDED,
            amount=amount or Decimal("0.00"),
            reference="",
        )
