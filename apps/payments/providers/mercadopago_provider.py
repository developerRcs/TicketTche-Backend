"""
Mercado Pago payment gateway implementation.
Uses the Payments API (POST /v1/payments) — Checkout Transparente.
Compatible with both TEST and production credentials.

Required settings:
    MP_ACCESS_TOKEN  — private access token (backend only)
    MP_PUBLIC_KEY    — public key (exposed to frontend)
    MP_WEBHOOK_SECRET — used to validate incoming webhook signatures (optional)
"""
import uuid
from decimal import Decimal
from typing import Optional

import requests as http_client

from apps.payments.gateway import (
    PaymentGateway,
    PaymentMethod,
    PaymentRequest,
    PaymentResponse,
    PaymentStatus,
    RefundResponse,
)

MP_API_BASE = "https://api.mercadopago.com"


class MercadoPagoGateway(PaymentGateway):
    def __init__(self):
        from django.conf import settings
        self.access_token = settings.MP_ACCESS_TOKEN

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": str(uuid.uuid4()),
        }

    def _parse_status(self, status: str, status_detail: str = "") -> PaymentStatus:
        if status == "approved":
            return PaymentStatus.APPROVED
        if status in ("rejected", "cancelled"):
            return PaymentStatus.REJECTED
        if status == "refunded":
            return PaymentStatus.REFUNDED
        return PaymentStatus.PENDING

    def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        cpf = request.metadata.get("payer_cpf", "").replace(".", "").replace("-", "").replace("/", "")
        first_name = request.metadata.get("payer_first_name") or request.metadata.get("payer_name", "").split(" ", 1)[0]
        last_name = request.metadata.get("payer_last_name") or (request.metadata.get("payer_name", "").split(" ", 1)[1] if " " in request.metadata.get("payer_name", "") else first_name)

        payload: dict = {
            "transaction_amount": float(request.amount),
            "description": f"TicketTchê - {request.reference}",
            "external_reference": request.reference,
            "payer": {
                "email": request.payer_email,
                "first_name": first_name,
                "last_name": last_name,
                "identification": {"type": "CPF", "number": cpf},
            },
        }

        if request.method == PaymentMethod.PIX:
            payload["payment_method_id"] = "pix"

        else:
            card = request.card_data
            if not card:
                raise ValueError("card_data required for card payments")
            payload["payment_method_id"] = request.metadata.get("mp_payment_method_id", "master")
            payload["token"] = card.number  # tokenized by MP SDK on frontend
            payload["installments"] = card.installments or 1
            if request.metadata.get("issuer_id"):
                payload["issuer_id"] = int(request.metadata["issuer_id"])

        resp = http_client.post(
            f"{MP_API_BASE}/v1/payments",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        data = resp.json()

        if resp.status_code not in (200, 201):
            return PaymentResponse(
                gateway_id="",
                status=PaymentStatus.REJECTED,
                method=request.method,
                amount=request.amount,
                reference=request.reference,
                raw_response=data,
            )

        payment_id = str(data.get("id", ""))
        status = self._parse_status(data.get("status", "pending"), data.get("status_detail", ""))

        response = PaymentResponse(
            gateway_id=payment_id,
            status=status,
            method=request.method,
            amount=request.amount,
            reference=request.reference,
            raw_response=data,
        )
        response.raw_response["mp_payment_id"] = payment_id

        if request.method == PaymentMethod.PIX:
            poi = data.get("point_of_interaction", {})
            tx_data = poi.get("transaction_data", {})
            response.pix_qr_code = tx_data.get("qr_code", "")
            response.pix_qr_code_image = tx_data.get("qr_code_base64", "")

        return response

    def capture_payment(self, gateway_id: str) -> PaymentResponse:
        return self.get_payment_status(gateway_id)

    def get_payment_status(self, gateway_id: str) -> PaymentResponse:
        resp = http_client.get(
            f"{MP_API_BASE}/v1/payments/{gateway_id}",
            headers=self._headers(),
            timeout=30,
        )
        data = resp.json()
        status = self._parse_status(data.get("status", "pending"), data.get("status_detail", ""))

        return PaymentResponse(
            gateway_id=gateway_id,
            status=status,
            method=PaymentMethod.PIX,
            amount=Decimal(str(data.get("transaction_amount", "0"))),
            reference=data.get("external_reference", ""),
            raw_response=data,
        )

    def refund_payment(self, gateway_id: str, amount: Optional[Decimal] = None) -> RefundResponse:
        body = {}
        if amount:
            body["amount"] = float(amount)

        resp = http_client.post(
            f"{MP_API_BASE}/v1/payments/{gateway_id}/refunds",
            headers=self._headers(),
            json=body,
            timeout=30,
        )
        success = resp.status_code in (200, 201)
        return RefundResponse(
            gateway_id=gateway_id,
            status=PaymentStatus.REFUNDED if success else PaymentStatus.REJECTED,
            amount=amount or Decimal("0.00"),
            reference="",
        )
