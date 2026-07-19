"""AI Contract Analysis Service using Gemini 2.5 Pro."""
import os
import json
import httpx
from typing import List, Dict, Any

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"

ANALYSIS_PROMPT = """You are an expert contract negotiation attorney. Analyze the following contract and provide a structured risk assessment.

For each clause you identify, provide:
1. clause_type: Category (e.g., "termination", "liability", "intellectual_property", "payment", "confidentiality", "indemnification", "non_compete", "governing_law")
2. risk_level: One of ["low", "medium", "high", "critical"]
3. explanation: Clear explanation of the risk in 2-3 sentences
4. suggested_revision: A concrete, improved version of the clause language
5. original_text: The exact text from the contract

Also provide:
- overall_risk_score: A number from 0-100 where 0=no risk, 100=extremely risky
- summary: A 3-4 sentence executive summary of the contract's risk profile

Respond ONLY in valid JSON with this exact structure:
{
  "overall_risk_score": <number>,
  "summary": "<string>",
  "clauses": [
    {
      "clause_type": "<string>",
      "risk_level": "<low|medium|high|critical>",
      "explanation": "<string>",
      "suggested_revision": "<string>",
      "original_text": "<string>"
    }
  ]
}

CONTRACT TEXT:
"""


async def analyze_contract(contract_text: str) -> Dict[str, Any]:
    """Send contract text to Gemini 2.5 Pro and parse structured analysis."""

    if not GEMINI_API_KEY:
        # Fallback: return demo analysis for development/testing
        return _generate_demo_analysis(contract_text)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            json={
                "contents": [{
                    "parts": [{"text": ANALYSIS_PROMPT + contract_text}]
                }],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 8192,
                    "responseMimeType": "application/json"
                }
            }
        )
        response.raise_for_status()
        data = response.json()

        # Extract JSON from response
        text_content = data["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text_content)
        return result


def _generate_demo_analysis(contract_text: str) -> Dict[str, Any]:
    """Generate a realistic demo analysis when no API key is configured."""
    text_preview = contract_text[:500].lower()

    # Simple heuristic demo based on contract content
    clauses = []

    if "termination" in text_preview or "terminate" in text_preview:
        clauses.append({
            "clause_type": "termination",
            "risk_level": "high",
            "explanation": "The termination clause allows the counterparty to terminate with only 30 days notice while requiring 90 days from your side. This creates an asymmetric power dynamic.",
            "suggested_revision": "Either party may terminate this agreement with 60 days written notice. In the event of material breach, termination may be immediate upon written notice.",
            "original_text": "Either party may terminate this agreement with thirty (30) days written notice."
        })

    if "liability" in text_preview or "indemnif" in text_preview:
        clauses.append({
            "clause_type": "liability",
            "risk_level": "critical",
            "explanation": "The liability cap is set at 6 months of fees, which is insufficient for a contract of this scope. Data breach liabilities alone could exceed this amount significantly.",
            "suggested_revision": "Each party's aggregate liability shall not exceed the greater of (i) twelve (12) months of fees paid under this agreement, or (ii) $500,000. Liability for data breaches, IP infringement, and confidentiality violations shall be uncapped.",
            "original_text": "Company's liability shall not exceed six (6) months of fees paid under this agreement."
        })

    if "intellectual property" in text_preview or "ip " in text_preview or "ownership" in text_preview:
        clauses.append({
            "clause_type": "intellectual_property",
            "risk_level": "medium",
            "explanation": "The IP assignment clause grants the counterparty broad rights to any improvements or derivative works, potentially capturing your pre-existing IP.",
            "suggested_revision": "Each party retains ownership of its pre-existing intellectual property. Improvements to pre-existing IP shall remain with the original owner. New jointly-created IP shall be owned equally unless otherwise agreed in writing.",
            "original_text": "All intellectual property created during the term of this agreement shall be owned by Company."
        })

    if "payment" in text_preview or "fee" in text_preview:
        clauses.append({
            "clause_type": "payment",
            "risk_level": "medium",
            "explanation": "Net-60 payment terms create significant cash flow pressure. Industry standard is Net-30, and this should be negotiated down.",
            "suggested_revision": "Payment terms shall be Net-30 from the date of invoice. Late payments subject to 1.5% monthly service charge.",
            "original_text": "Payment shall be due within sixty (60) days of invoice date."
        })

    if not clauses:
        clauses = [
            {
                "clause_type": "general",
                "risk_level": "medium",
                "explanation": "Contract contains standard language but lacks specific protections around data ownership and termination rights. Recommend adding explicit data deletion requirements post-termination.",
                "suggested_revision": "Upon termination or expiration, Company shall return or securely destroy all Customer data within 30 days and provide written certification of destruction.",
                "original_text": "Upon termination, each party shall return confidential information."
            }
        ]

    risk_score = min(85, 30 + len(clauses) * 15)

    return {
        "overall_risk_score": risk_score,
        "summary": f"This contract contains {len(clauses)} flagged provisions with asymmetric risk allocation favoring the counterparty. Key concerns include termination imbalance, insufficient liability caps, and broad IP assignments. Immediate negotiation recommended on high-risk clauses before execution.",
        "clauses": clauses
    }
