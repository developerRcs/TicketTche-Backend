"""
Payment gateway abstraction layer.

This module provides an abstract interface for payment processing.
To integrate a real payment provider (Stripe, Mercado Pago, PagSeguro, etc.),
create a concrete implementation of PaymentGateway and configure it
via PAYMENT_GATEWAY_CLASS in Django settings.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PIX = "pix"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


@dataclass
class CardData:
    """Data required for credit or debit card payment."""
    holder_name: str
    number: str  # Should be tokenized in production — never store raw
    expiry_month: int
    expiry_year: int
    cvv: str  # Should be tokenized in production
    installments: int = 1


@dataclass
class PixData:
    """Data required for Pix payment."""
    payer_document: str  # CPF or CNPJ
    payer_name: str


@dataclass
class PaymentRequest:
    """Unified payment request passed to the gateway."""
    amount: Decimal
    currency: str
    method: PaymentMethod
    description: str
    reference: str  # Order reference
    payer_email: str
    card_data: Optional[CardData] = None
    pix_data: Optional[PixData] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class PaymentResponse:
    """Unified response returned by the gateway."""
    gateway_id: str        # Provider-specific transaction ID
    status: PaymentStatus
    method: PaymentMethod
    amount: Decimal
    reference: str
    pix_qr_code: Optional[str] = None    # QR code string for Pix
    pix_qr_code_image: Optional[str] = None  # Base64 QR image for Pix
    pix_expiry: Optional[str] = None     # ISO datetime string
    redirect_url: Optional[str] = None  # For 3DS or redirect flows
    raw_response: dict = field(default_factory=dict)


@dataclass
class RefundResponse:
    gateway_id: str
    status: PaymentStatus
    amount: Decimal
    reference: str


class PaymentGateway(ABC):
    """
    Abstract base class for payment gateway integrations.

    To implement a new provider:
    1. Create a class that extends PaymentGateway
    2. Implement all abstract methods
    3. Set PAYMENT_GATEWAY_CLASS in Django settings to the dotted path of your class

    Example:
        PAYMENT_GATEWAY_CLASS = "apps.payments.providers.mercadopago.MercadoPagoGateway"
    """

    @abstractmethod
    def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        """
        Initiate a payment transaction.

        For card payments: charges the card or creates a pending authorization.
        For Pix: generates QR code and returns it in the response.
        """
        ...

    @abstractmethod
    def capture_payment(self, gateway_id: str) -> PaymentResponse:
        """
        Capture a previously authorized payment.
        Only relevant for credit card pre-authorization flows.
        """
        ...

    @abstractmethod
    def get_payment_status(self, gateway_id: str) -> PaymentResponse:
        """
        Check the current status of a payment transaction.
        Used for polling Pix payment confirmation.
        """
        ...

    @abstractmethod
    def refund_payment(self, gateway_id: str, amount: Optional[Decimal] = None) -> RefundResponse:
        """
        Refund a captured payment, fully or partially.
        If amount is None, refunds the full amount.
        """
        ...


def get_gateway() -> PaymentGateway:
    """
    Returns the configured payment gateway instance.

    Configure via settings.PAYMENT_GATEWAY_CLASS.
    Falls back to StubGateway in development.
    """
    from django.conf import settings
    from django.utils.module_loading import import_string

    gateway_class_path = getattr(
        settings,
        "PAYMENT_GATEWAY_CLASS",
        "apps.payments.providers.stub.StubGateway",
    )
    gateway_class = import_string(gateway_class_path)
    return gateway_class()
