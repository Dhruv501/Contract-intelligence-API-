import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

def extract_structured_fields(text: str) -> Dict[str, Any]:
    """Extract structured fields from contract text"""
    result = {
        "parties": [],
        "effective_date": None,
        "term": None,
        "governing_law": None,
        "payment_terms": None,
        "termination": None,
        "auto_renewal": None,
        "confidentiality": None,
        "indemnity": None,
        "liability_cap": None,
        "signatories": []
    }
    
    text_lower = text.lower()
    
    # Extract parties (common patterns) - improved
    party_patterns = [
        r"(?:between|by and between)\s+([A-Z][A-Za-z0-9\s&,\.\-']+?)(?:\s+and\s+|\s+,\s+)([A-Z][A-Za-z0-9\s&,\.\-']+?)(?:\s+\(|,|\.|$|;|\n)",
        r"party\s+(?:a|1)[\s:]+([A-Z][A-Za-z0-9\s&,\.\-']+?)(?:\s+party\s+(?:b|2)|$|;|\n)",
        r"party\s+(?:b|2)[\s:]+([A-Z][A-Za-z0-9\s&,\.\-']+?)(?:$|\.|,|;|\n)",
        r"([A-Z][A-Za-z0-9\s&,\.\-']+?)\s+and\s+([A-Z][A-Za-z0-9\s&,\.\-']+?)(?:\s+herein|$|\.|,|;|\n)",
        r"this\s+agreement\s+is\s+between\s+([A-Z][A-Za-z0-9\s&,\.\-']+?)\s+and\s+([A-Z][A-Za-z0-9\s&,\.\-']+?)"
    ]
    
    for pattern in party_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            parties = [p.strip() for p in match.groups() if p and len(p.strip()) > 2]
            for party in parties:
                # Filter out common false positives
                if (len(party) > 3 and 
                    party not in result["parties"] and 
                    party.lower() not in ["party", "parties", "agreement", "contract", "document"]):
                    result["parties"].append(party)
    
    # Extract effective date - improved patterns
    date_patterns = [
        r"effective\s+(?:date|as\s+of)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"effective\s+(?:date|as\s+of)[\s:]+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
        r"this\s+agreement\s+is\s+effective\s+(?:as\s+of\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"this\s+agreement\s+is\s+effective\s+(?:as\s+of\s+)?([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
        r"dated[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"dated[:\s]+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
        r"executed\s+(?:on\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"executed\s+(?:on\s+)?([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})"
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["effective_date"] = match.group(1).strip()
            break
    
    # Extract term/duration
    term_patterns = [
        r"term\s+(?:of\s+)?(?:this\s+)?(?:agreement|contract)[\s:]+(\d+)\s+(?:year|month|day)",
        r"initial\s+term[\s:]+(\d+)\s+(?:year|month|day)",
        r"duration[\s:]+(\d+)\s+(?:year|month|day)"
    ]
    
    for pattern in term_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["term"] = match.group(0)
            break
    
    # Extract governing law
    law_patterns = [
        r"governed\s+by\s+(?:the\s+)?(?:laws?|law)\s+of\s+([A-Z][A-Za-z\s,]+?)(?:\.|,|$)",
        r"governing\s+law[\s:]+([A-Z][A-Za-z\s,]+?)(?:\.|,|$)",
        r"laws?\s+of\s+([A-Z][A-Za-z\s,]+?)(?:\s+shall\s+govern|\.|,|$)"
    ]
    
    for pattern in law_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["governing_law"] = match.group(1).strip()
            break
    
    # Extract payment terms
    payment_patterns = [
        r"payment\s+(?:terms?|shall\s+be)[\s:]+([A-Za-z0-9\s,\.\$]+?)(?:\.|,|$)",
        r"invoice\s+(?:shall\s+be\s+)?(?:paid|due)[\s:]+([A-Za-z0-9\s,\.\$]+?)(?:\.|,|$)"
    ]
    
    for pattern in payment_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["payment_terms"] = match.group(1).strip()
            break
    
    # Extract termination
    termination_patterns = [
        r"termination[\s:]+([A-Za-z0-9\s,\.]+?)(?:\.|,|$)",
        r"may\s+terminate[\s:]+([A-Za-z0-9\s,\.]+?)(?:\.|,|$)"
    ]
    
    for pattern in termination_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["termination"] = match.group(1).strip()
            break
    
    # Extract auto-renewal
    renewal_patterns = [
        r"auto[-\s]?renew(?:al)?[\s:]+([A-Za-z0-9\s,\.]+?)(?:\.|,|$)",
        r"automatically\s+renew(?:s|ed)?[\s:]+([A-Za-z0-9\s,\.]+?)(?:\.|,|$)",
        r"renew(?:s|ed)?\s+automatically[\s:]+([A-Za-z0-9\s,\.]+?)(?:\.|,|$)"
    ]
    
    for pattern in renewal_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["auto_renewal"] = match.group(1).strip()
            break
    
    # Extract confidentiality - improved to capture more context
    conf_patterns = [
        r"confidential(?:ity)?[\s:]+([A-Za-z0-9\s,\.\(\)]+?)(?:\.|,|$|;|\n)",
        r"non[-\s]?disclosure[\s:]+([A-Za-z0-9\s,\.\(\)]+?)(?:\.|,|$|;|\n)",
        r"confidential\s+information[\s:]+([A-Za-z0-9\s,\.\(\)]+?)(?:\.|,|$|;|\n)",
        r"confidential\s+information\s+means[\s:]+([A-Za-z0-9\s,\.\(\)]+?)(?:\.|,|$|;|\n)",
        r"confidential\s+information\s+shall\s+mean[\s:]+([A-Za-z0-9\s,\.\(\)]+?)(?:\.|,|$|;|\n)",
        r"([A-Za-z0-9\s,\.\(\)]+?)\s+shall\s+be\s+deemed\s+confidential",
        r"confidential\s+information\s+includes[\s:]+([A-Za-z0-9\s,\.\(\)]+?)(?:\.|,|$|;|\n)"
    ]
    
    for pattern in conf_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            extracted = match.group(1).strip() if match.lastindex else match.group(0).strip()
            if len(extracted) > 10:  # Only if meaningful content
                result["confidentiality"] = extracted[:500]  # Limit length
                break
        if result["confidentiality"]:
            break
    
    # Extract indemnity
    indemnity_patterns = [
        r"indemnif(?:y|ies)[\s:]+([A-Za-z0-9\s,\.]+?)(?:\.|,|$)",
        r"shall\s+indemnify[\s:]+([A-Za-z0-9\s,\.]+?)(?:\.|,|$)"
    ]
    
    for pattern in indemnity_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["indemnity"] = match.group(1).strip()
            break
    
    # Extract liability cap
    liability_patterns = [
        r"liability\s+(?:cap|limit)[\s:]+([\$£€]?\s*\d+(?:,\d{3})*(?:\.\d{2})?)\s*([A-Z]{3})?",
        r"maximum\s+liability[\s:]+([\$£€]?\s*\d+(?:,\d{3})*(?:\.\d{2})?)\s*([A-Z]{3})?"
    ]
    
    for pattern in liability_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount = match.group(1).strip()
            currency = match.group(2) if match.group(2) else "USD"
            result["liability_cap"] = {
                "amount": amount,
                "currency": currency
            }
            break
    
    # Extract signatories
    signatory_patterns = [
        r"(?:signed|executed)\s+by[\s:]+([A-Z][A-Za-z\s]+?)[\s:]+(?:title|as)[\s:]+([A-Z][A-Za-z\s]+?)(?:\.|,|$)",
        r"([A-Z][A-Za-z\s]+?)[\s:]+(?:title|as)[\s:]+([A-Z][A-Za-z\s]+?)(?:\.|,|$)"
    ]
    
    for pattern in signatory_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match.groups()) >= 2:
                result["signatories"].append({
                    "name": match.group(1).strip(),
                    "title": match.group(2).strip()
                })
    
    return result


