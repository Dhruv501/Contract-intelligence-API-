from typing import List, Dict, Any
import re
from app.database import get_document, get_extracted_fields

class ContractAuditor:
    """Audit contracts for risky clauses"""
    
    def __init__(self):
        self.risk_patterns = {
            "auto_renewal_short_notice": {
                "pattern": r"auto[-\s]?renew(?:al)?.*?(?:notice|written\s+notice).*?(\d+)\s*(?:day|days)",
                "severity": "high",
                "check": lambda m: int(m.group(1)) < 30 if m.group(1) else False
            },
            "unlimited_liability": {
                "pattern": r"(?:unlimited|no\s+limit|without\s+limit).*?liability",
                "severity": "critical",
                "check": lambda m: True
            },
            "broad_indemnity": {
                "pattern": r"indemnif(?:y|ies).*?(?:all|any|any\s+and\s+all).*?(?:loss|damage|claim|liability)",
                "severity": "high",
                "check": lambda m: True
            },
            "no_termination_right": {
                "pattern": r"(?:may\s+not\s+terminate|cannot\s+terminate|no\s+right\s+to\s+terminate)",
                "severity": "medium",
                "check": lambda m: True
            },
            "exclusive_terms": {
                "pattern": r"exclusive.*?(?:vendor|supplier|provider)",
                "severity": "medium",
                "check": lambda m: True
            }
        }
    
    async def audit_document(self, document_id: str) -> List[Dict[str, Any]]:
        """Audit a document for risky clauses"""
        findings = []
        
        doc = await get_document(document_id)
        if not doc:
            return findings
        
        text = doc["text_content"]
        text_lower = text.lower()
        
        # Check each risk pattern
        for risk_name, risk_config in self.risk_patterns.items():
            pattern = risk_config["pattern"]
            matches = re.finditer(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
            
            for match in matches:
                if risk_config["check"](match):
                    # Find the context around the match
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    evidence = text[start:end]
                    
                    # Get page number
                    from app.pdf_processor import get_page_from_position
                    page = get_page_from_position(text, match.start())
                    
                    findings.append({
                        "risk_type": risk_name,
                        "severity": risk_config["severity"],
                        "description": self._get_risk_description(risk_name),
                        "evidence": evidence.strip(),
                        "char_range": [match.start(), match.end()],
                        "page": page,
                        "document_id": document_id
                    })
        
        # Additional checks using extracted fields
        extracted = await get_extracted_fields(document_id)
        if extracted:
            # Check auto-renewal notice period
            if extracted.get("auto_renewal"):
                renewal_text = extracted["auto_renewal"].lower()
                notice_match = re.search(r"(\d+)\s*(?:day|days)", renewal_text)
                if notice_match:
                    days = int(notice_match.group(1))
                    if days < 30:
                        findings.append({
                            "risk_type": "auto_renewal_short_notice",
                            "severity": "high",
                            "description": f"Auto-renewal clause requires only {days} days notice (recommended: 30+ days)",
                            "evidence": extracted["auto_renewal"],
                            "char_range": None,
                            "page": None,
                            "document_id": document_id
                        })
            
            # Check liability cap
            liability_cap = extracted.get("liability_cap")
            if liability_cap is None:
                # Check if there's unlimited liability mentioned
                if "unlimited" in text_lower and "liability" in text_lower:
                    findings.append({
                        "risk_type": "unlimited_liability",
                        "severity": "critical",
                        "description": "No liability cap found, potential unlimited liability exposure",
                        "evidence": "Unlimited liability clause detected",
                        "char_range": None,
                        "page": None,
                        "document_id": document_id
                    })
        
        return findings
    
    def _get_risk_description(self, risk_type: str) -> str:
        """Get human-readable description of risk"""
        descriptions = {
            "auto_renewal_short_notice": "Auto-renewal clause with less than 30 days notice period",
            "unlimited_liability": "Unlimited liability clause detected",
            "broad_indemnity": "Broad indemnity clause that may expose party to excessive risk",
            "no_termination_right": "Clause that restricts or prevents termination rights",
            "exclusive_terms": "Exclusive vendor/supplier terms that limit flexibility"
        }
        return descriptions.get(risk_type, "Potential risk detected in contract")

auditor = ContractAuditor()


