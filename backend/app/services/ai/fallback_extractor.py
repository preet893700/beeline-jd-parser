# app/services/ai/fallback_extractor.py
"""
Fallback Regex-Based Extractor
Used as last resort when AI extraction fails or misses critical fields
"""

import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class FallbackExtractor:
    """
    Regex-based extraction fallback
    Only used when AI misses critical fields like bill_rate
    """
    
    @staticmethod
    def extract_bill_rate(jd_text: str) -> Optional[str]:
        """
        Extract bill rate using comprehensive regex patterns
        Handles all known messy formats
        """
        # Normalize text for matching
        text = jd_text.lower()
        
        # Pattern priority (most specific to least specific)
        patterns = [
            # Pattern 1: "Bill Rate: MAX CONFIRMED $75"
            (r'bill\s*rate[:\s-]*max\s*(?:confirmed\s*)?\$?\s*(\d+(?:\.\d+)?)', 
             lambda m: f"${m.group(1)} MAX"),
            
            # Pattern 2: "Max Bill Rate: $80.00"
            (r'max\s*bill\s*rate[:\s]*\$?\s*(\d+(?:\.\d+)?)', 
             lambda m: f"${m.group(1)} MAX"),
            
            # Pattern 3: "Bill Rate: $70-85/hr" or "Bill Rate-$75-$80"
            (r'bill\s*rate[:\s-]*\$?\s*(\d+(?:\.\d+)?)\s*-\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:/hr)?',
             lambda m: f"${m.group(1)}-${m.group(2)}{'/hr' if '/hr' in m.group(0) else ''}"),
            
            # Pattern 4: "Bill Rate: $65 MAX" or "Bill Rate $100 MAX"
            (r'bill\s*rate[:\s-]*\$?\s*(\d+(?:\.\d+)?)\s*max',
             lambda m: f"${m.group(1)} MAX"),
            
            # Pattern 5: "Bill Rate: $70.00" or "Bill Rate-$50"
            (r'bill\s*rate[:\s-]*\$?\s*(\d+(?:\.\d+)?)\s*(?:/hr)?',
             lambda m: f"${m.group(1)}{'/hr' if '/hr' in m.group(0) else ''}"),
            
            # Pattern 6: "Bill Rate: 60 -80" (spaces in range)
            (r'bill\s*rate[:\s]*(\d+)\s*-\s*(\d+)',
             lambda m: f"${m.group(1)}-${m.group(2)}"),
        ]
        
        for pattern, formatter in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    result = formatter(match)
                    # Normalize decimal: $70.00 → $70
                    result = re.sub(r'\$(\d+)\.00', r'$\1', result)
                    logger.info(f"Fallback extracted bill_rate: {result}")
                    return result
                except Exception as e:
                    logger.warning(f"Fallback formatting error: {e}")
                    continue
        
        return None
    
    @staticmethod
    def extract_duration(jd_text: str) -> Optional[str]:
        """Extract duration using regex"""
        patterns = [
            r'duration[:\s]*(\d+\+?\s*(?:months?|yrs?|years?))',
            r'contract\s*(?:length|duration)[:\s]*(\d+\+?\s*(?:months?|yrs?|years?))',
            r'(\d+\+?\s*(?:months?|years?)\s*(?:contract)?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, jd_text, re.IGNORECASE)
            if match:
                duration = match.group(1)
                # Normalize
                duration = re.sub(r'mo(?:nth)?s?', 'months', duration, flags=re.IGNORECASE)
                duration = re.sub(r'yr(?:s)?', 'year', duration, flags=re.IGNORECASE)
                return duration.strip()
        
        return None
    
    @staticmethod
    def extract_gbams_id(jd_text: str) -> Optional[str]:
        """Extract GBAMS/RGS ID"""
        patterns = [
            r'gbams\s*req(?:id)?[:\s]*(\d+)',
            r'rgs\s*id[:\s]*(\d+)',
            r'req\s*id[:\s]*(\d+)',
            r'requisition[:\s]*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, jd_text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def extract_location(jd_text: str) -> Optional[str]:
        """Extract location"""
        patterns = [
            r'location[:\s]*([^\n]+)',
            r'based\s*in[:\s]*([^\n]+)',
            r'office[:\s]*([^\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, jd_text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                # Clean up
                location = re.sub(r'[~`]', '', location)
                # Truncate at next field
                location = re.split(r'(?:duration|experience|skills|msp)', location, flags=re.IGNORECASE)[0]
                return location.strip()[:100]  # Max 100 chars
        
        return None
    
    @staticmethod
    def extract_msp_owner(jd_text: str) -> Optional[str]:
        """Extract MSP owner"""
        patterns = [
            r'msp\s*owner[:\s]*([^\n]+)',
            r'msp\s*contact[:\s]*([^\n]+)',
            r'staffing\s*(?:contact|owner)[:\s]*([^\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, jd_text, re.IGNORECASE)
            if match:
                owner = match.group(1).strip()
                # Clean up - take only name portion
                owner = re.split(r'(?:location|duration|gbams)', owner, flags=re.IGNORECASE)[0]
                return owner.strip()[:100]
        
        return None
    
    @staticmethod
    def enhance_extraction(
        ai_result: Dict[str, Any],
        original_jd: str
    ) -> Dict[str, Any]:
        """
        Enhance AI extraction with fallback patterns
        Only fills in missing critical fields
        
        PERFORMANCE NOTE: Only processes fields that are actually missing
        """
        enhanced = ai_result.copy()
        
        # Define critical fields with their extractors
        # Order by importance
        critical_fields = [
            ('bill_rate', FallbackExtractor.extract_bill_rate),
            ('gbams_rgs_id', FallbackExtractor.extract_gbams_id),
            ('duration', FallbackExtractor.extract_duration),
            ('ai_location', FallbackExtractor.extract_location),
            ('msp_owner', FallbackExtractor.extract_msp_owner),
        ]
        
        # Only process fields that are missing (performance optimization)
        for field_name, extractor_func in critical_fields:
            if not enhanced.get(field_name):
                try:
                    fallback_value = extractor_func(original_jd)
                    if fallback_value:
                        enhanced[field_name] = fallback_value
                        logger.info(f"Fallback filled {field_name}: {fallback_value}")
                except Exception as e:
                    logger.warning(f"Fallback extraction failed for {field_name}: {e}")
                    continue
        
        return enhanced