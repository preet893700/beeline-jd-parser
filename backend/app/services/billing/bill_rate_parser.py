# app/services/billing/bill_rate_parser.py
"""
Bill Rate Parser
Deterministic min/max extraction from already-extracted bill_rate strings

CRITICAL RULES:
- Input: bill_rate string (from AI or fallback extractor)
- Output: {min_bill_rate: float | null, max_bill_rate: float | null}
- NO AI calls
- NO re-parsing JD text
- NO regex duplication from fallback extractor
"""

import re
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class BillRateParser:
    """
    Parse min/max bill rates from already-extracted bill_rate strings
    This is pure post-processing - NOT extraction
    """
    
    @staticmethod
    def parse(bill_rate: Optional[str]) -> Dict[str, Optional[float]]:
        """
        Parse min/max from bill_rate string
        
        Args:
            bill_rate: Already-extracted bill rate (from AI or fallback)
            
        Returns:
            {"min_bill_rate": float | None, "max_bill_rate": float | None}
            
        Examples:
            "$70-$85" → {min: 70, max: 85}
            "$70" → {min: None, max: 70}
            "$80 MAX" → {min: None, max: 80}
            None → {min: None, max: None}
        """
        # Default result
        result = {
            "min_bill_rate": None,
            "max_bill_rate": None
        }
        
        # Handle null/empty
        if not bill_rate or not bill_rate.strip():
            return result
        
        try:
            # Clean input
            cleaned = bill_rate.strip()
            
            # CASE 1: Range format (e.g., "$70-$85", "$70 - $85/hr")
            # Pattern: numbers separated by dash
            range_match = re.search(
                r'\$?\s*(\d+(?:\.\d+)?)\s*-\s*\$?\s*(\d+(?:\.\d+)?)',
                cleaned,
                re.IGNORECASE
            )
            
            if range_match:
                min_val = float(range_match.group(1))
                max_val = float(range_match.group(2))
                
                result["min_bill_rate"] = min_val
                result["max_bill_rate"] = max_val
                
                logger.debug(f"Parsed range: '{bill_rate}' → min={min_val}, max={max_val}")
                return result
            
            # CASE 2: Single value (with or without MAX/CONFIRMED)
            # Pattern: extract first number found
            single_match = re.search(
                r'\$?\s*(\d+(?:\.\d+)?)',
                cleaned,
                re.IGNORECASE
            )
            
            if single_match:
                value = float(single_match.group(1))
                
                # CRITICAL: Only set max_bill_rate
                # DO NOT infer min from max
                result["min_bill_rate"] = None
                result["max_bill_rate"] = value
                
                logger.debug(f"Parsed single: '{bill_rate}' → max={value}")
                return result
            
            # CASE 3: Unparsable
            logger.warning(f"Could not parse bill_rate: '{bill_rate}'")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing bill_rate '{bill_rate}': {e}")
            return result
    
    @staticmethod
    def parse_batch(bill_rates: list[Optional[str]]) -> list[Dict[str, Optional[float]]]:
        """
        Parse multiple bill rates efficiently
        
        Args:
            bill_rates: List of bill_rate strings
            
        Returns:
            List of {min_bill_rate, max_bill_rate} dicts
        """
        return [BillRateParser.parse(rate) for rate in bill_rates]


# Convenience function for single-line usage
def parse_bill_rate(bill_rate: Optional[str]) -> Dict[str, Optional[float]]:
    """Parse min/max from bill_rate string"""
    return BillRateParser.parse(bill_rate)