import json
import asyncio
import os
import sys

# Temporarily mock the path so we can import orchestrator agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services", "orchestrator"))

async def test_mistral_insights_output():
    # Example of what Mistral outputs based on our test setup:
    insights_payload = {
        "summary": "The top 10 customers hold 27.5% of total deposits, led primarily by the premium segment in New York and California. Overall retention remains high but risk flags have increased slightly.",
        "key_metrics": {
            "total_count": 10,
            "total_sum": 5000000.0,
            "average": 500000.0,
            "concentration_pct": 27.5,
            "top_region": "New York"
        },
        "trends": [
            {"metric": "concentration", "value": 27.5, "direction": "up", "confidence": 0.95},
            {"metric": "yoy_growth", "value": 12.5, "direction": "up", "confidence": 0.70}
        ],
        "recommendations": [
            "1. Offer exclusive high-yield savings products to the top 10% balance customers to maintain retention.",
            "2. Improve KYC and risk screening for the rapidly growing premium segment.",
            "3. Expand personalized wealth management services in the New York region."
        ],
        "anomalies": [
            {"customer_id": "C092", "balance": 15000000.0, "reason": "Outlier detection (3x std dev)"}
        ]
    }
    
    compliance_payload = {
        "compliant": True,
        "violations": [],
        "masking_required": [
            {"column": "ssn", "mask_type": "MASK_VALUE", "regulation": "GDPR"},
            {"column": "phone", "mask_type": "MASK_VALUE", "regulation": "GDPR"}
        ]
    }

    final_json = {
        "status": "success",
        "results": [{"customer": "Alice", "balance": 500000}, {"customer": "Bob", "balance": 450000}],
        "insights": insights_payload,
        "pipeline": {
            "compliance": compliance_payload
        }
    }
    
    print("--- 🧠 MISTRAL INSIGHTS PREVIEW ---")
    print(json.dumps(final_json, indent=2))

if __name__ == "__main__":
    asyncio.run(test_mistral_insights_output())
