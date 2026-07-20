"""Stripe payment integration for ContractPilot."""
import os
import stripe
from fastapi import Request, HTTPException

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID_PRO")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")


def create_checkout_session(user_id: int, customer_email: str) -> dict:
    """Create a Stripe Checkout session for Pro subscription."""
    if not stripe.api_key or not STRIPE_PRICE_ID:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    session = stripe.checkout.Session.create(
        customer_email=customer_email,
        line_items=[{
            "price": STRIPE_PRICE_ID,
            "quantity": 1,
        }],
        mode="subscription",
        success_url=f"{APP_URL}/pricing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{APP_URL}/pricing",
        metadata={"user_id": str(user_id)}
    )
    return {"checkout_url": session.url, "session_id": session.id}


def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """Process Stripe webhook events."""
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        return {
            "type": "checkout.completed",
            "user_id": int(session["metadata"]["user_id"]),
            "customer_id": session["customer"],
            "subscription_id": session["subscription"]
        }

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        return {
            "type": "subscription.cancelled",
            "subscription_id": subscription["id"]
        }

    return {"type": "ignored"}
