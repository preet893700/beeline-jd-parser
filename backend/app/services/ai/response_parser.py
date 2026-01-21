# app/services/ai/response_parser.py
"""
AI Response Parser
Defensive parsing with intelligent post-processing
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List

from app.models.jd_result import JDExtractionResult, ExtractionStatus
from app.core.exceptions import AIExtractionError

logger = logging.getLogger(__name__)


class AIResponseParser:
    """Parse and validate AI responses with intelligent post-processing"""
    
    @staticmethod
    def parse_extraction_response(
        raw_response: str,
        model_name: str
    ) -> JDExtractionResult:
        """
        Parse AI response to JDExtractionResult
        Handles markdown, extra text, malformed JSON, and intelligently cleans data
        """
        try:
            # Clean response
            cleaned = AIResponseParser._clean_response(raw_response)
            
            # Parse JSON
            data = json.loads(cleaned)
            
            # Validate required structure
            if not isinstance(data, dict):
                raise AIExtractionError("Response is not a JSON object")
            
            # Intelligent post-processing
            data = AIResponseParser._post_process_data(data)
            
            # Build result
            result = JDExtractionResult(
                bill_rate=data.get("bill_rate"),
                duration=data.get("duration"),
                experience_required=data.get("experience_required"),
                gbams_rgs_id=data.get("gbams_rgs_id"),
                ai_location=data.get("ai_location"),
                skills=data.get("skills") if isinstance(data.get("skills"), list) else None,
                role_description=data.get("role_description"),
                msp_owner=data.get("msp_owner"),
                ai_model_used=model_name,
                ai_extraction_status=ExtractionStatus.SUCCESS
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}, Response: {raw_response[:200]}")
            raise AIExtractionError(f"Failed to parse JSON: {str(e)}")
        except Exception as e:
            logger.error(f"Extraction parsing error: {e}")
            raise AIExtractionError(f"Failed to parse extraction: {str(e)}")
    
    @staticmethod
    def _clean_response(text: str) -> str:
        """
        Clean AI response text
        - Remove markdown code blocks
        - Extract JSON from mixed content
        - Strip whitespace
        - Handle common formatting issues
        """
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```\s*', '', text)
        
        # Remove common preambles
        text = re.sub(r'^.*?(?=\{)', '', text, flags=re.DOTALL)
        text = re.sub(r'\}.*?$', '}', text, flags=re.DOTALL)
        
        # Try to extract JSON object
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        
        return text.strip()
    
    @staticmethod
    def _post_process_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligent post-processing of extracted data
        Cleans, normalizes, and validates fields
        """
        processed = data.copy()
        
        # Process bill_rate with intelligent normalization
        if processed.get("bill_rate"):
            processed["bill_rate"] = AIResponseParser._normalize_bill_rate(
                processed["bill_rate"]
            )
        
        # Process duration
        if processed.get("duration"):
            processed["duration"] = AIResponseParser._normalize_duration(
                processed["duration"]
            )
        
        # Process experience
        if processed.get("experience_required"):
            processed["experience_required"] = AIResponseParser._normalize_experience(
                processed["experience_required"]
            )
        
        # Process location
        if processed.get("ai_location"):
            processed["ai_location"] = AIResponseParser._normalize_location(
                processed["ai_location"]
            )
        
        # Process skills - ensure it's a clean list
        if processed.get("skills"):
            processed["skills"] = AIResponseParser._normalize_skills(
                processed["skills"]
            )
        
        # Process GBAMS ID
        if processed.get("gbams_rgs_id"):
            processed["gbams_rgs_id"] = AIResponseParser._normalize_id(
                processed["gbams_rgs_id"]
            )
        
        # Clean role description
        if processed.get("role_description"):
            processed["role_description"] = AIResponseParser._clean_text(
                processed["role_description"]
            )
        
        # Clean MSP owner
        if processed.get("msp_owner"):
            processed["msp_owner"] = AIResponseParser._clean_text(
                processed["msp_owner"]
            )
        
        return processed
    
    @staticmethod
    def _normalize_bill_rate(rate: str) -> str:
        """
        Normalize bill rate to consistent format
        Handles various patterns intelligently
        """
        rate = str(rate).strip()
        
        # Remove extra spaces
        rate = re.sub(r'\s+', ' ', rate)
        
        # Normalize "MAX" patterns
        # "MAX CONFIRMED $75" → "$75 MAX"
        max_match = re.search(r'MAX\s*(?:CONFIRMED\s*)?\$?(\d+(?:\.\d+)?)', rate, re.IGNORECASE)
        if max_match:
            return f"${max_match.group(1)} MAX"
        
        # "Max Bill Rate: $80" → "$80 MAX"
        if re.search(r'max\s*bill\s*rate', rate, re.IGNORECASE):
            num_match = re.search(r'\$?(\d+(?:\.\d+)?)', rate)
            if num_match:
                return f"${num_match.group(1)} MAX"
        
        # Normalize decimal format: $70.00 → $70
        rate = re.sub(r'\$(\d+)\.00', r'$\1', rate)
        
        # Normalize range: "70 - 90" → "70-90"
        rate = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1-\2', rate)
        
        # Ensure $ prefix if numbers present but no $
        if re.search(r'\d', rate) and not re.search(r'\$', rate):
            # Add $ to ranges: "70-90" → "$70-90"
            rate = re.sub(r'^(\d+)', r'$\1', rate)
        
        # Clean up spacing around /hr
        rate = re.sub(r'\s*/\s*hr', '/hr', rate, flags=re.IGNORECASE)
        
        # Remove trailing unnecessary text
        # "$75-80 C2C" → "$75-80"
        rate = re.sub(r'(\$?\d+(?:-\$?\d+)?(?:/hr)?)\s+\w+.*$', r'\1', rate)
        
        return rate.strip()
    
    @staticmethod
    def _normalize_duration(duration: str) -> str:
        """Normalize duration format"""
        duration = str(duration).strip()
        
        # Normalize spacing
        duration = re.sub(r'\s+', ' ', duration)
        
        # Normalize month(s) format
        duration = re.sub(r'(\d+)\s*mo(?:nth)?s?', r'\1 months', duration, flags=re.IGNORECASE)
        
        # Normalize year(s) format
        duration = re.sub(r'(\d+)\s*yr(?:s)?', r'\1 year', duration, flags=re.IGNORECASE)
        
        # Handle + sign: "12+ months"
        duration = re.sub(r'(\d+)\+\s*months', r'\1+ months', duration)
        
        return duration.strip()
    
    @staticmethod
    def _normalize_experience(experience: str) -> str:
        """Normalize experience format"""
        experience = str(experience).strip()
        
        # Normalize spacing
        experience = re.sub(r'\s+', ' ', experience)
        
        # Normalize "yrs" to "years"
        experience = re.sub(r'(\d+)\+?\s*yrs?(?:\s+of)?\s+(?:experience)?', 
                           r'\1+ years', experience, flags=re.IGNORECASE)
        
        # Normalize range: "3-5 years"
        experience = re.sub(r'(\d+)\s*-\s*(\d+)\s*(?:years)?', 
                           r'\1-\2 years', experience, flags=re.IGNORECASE)
        
        return experience.strip()
    
    @staticmethod
    def _normalize_location(location: str) -> str:
        """Normalize location format"""
        location = str(location).strip()
        
        # Normalize spacing
        location = re.sub(r'\s+', ' ', location)
        
        # Capitalize common terms
        location = re.sub(r'\bremote\b', 'Remote', location, flags=re.IGNORECASE)
        location = re.sub(r'\bhybrid\b', 'Hybrid', location, flags=re.IGNORECASE)
        location = re.sub(r'\bonsite\b', 'Onsite', location, flags=re.IGNORECASE)
        
        # Clean up punctuation
        location = re.sub(r'\s*~\s*', '', location)  # Remove tilde markers
        
        return location.strip()
    
    @staticmethod
    def _normalize_skills(skills: Any) -> Optional[List[str]]:
        """Normalize skills list"""
        if not skills:
            return None
        
        if isinstance(skills, str):
            # Split comma-separated string
            skills = [s.strip() for s in skills.split(',')]
        
        if not isinstance(skills, list):
            return None
        
        # Clean each skill
        cleaned_skills = []
        for skill in skills:
            skill = str(skill).strip()
            if skill and len(skill) > 1:  # Skip empty or single-char
                cleaned_skills.append(skill)
        
        return cleaned_skills if cleaned_skills else None
    
    @staticmethod
    def _normalize_id(id_value: str) -> str:
        """Normalize GBAMS/RGS ID"""
        id_value = str(id_value).strip()
        
        # Remove common prefixes if present
        id_value = re.sub(r'^(?:GBAMS|RGS|REQ)[:\s-]*', '', id_value, flags=re.IGNORECASE)
        
        # Extract numeric portion if mixed
        num_match = re.search(r'\d+', id_value)
        if num_match:
            return num_match.group(0)
        
        return id_value.strip()
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean general text fields"""
        text = str(text).strip()
        
        # Normalize spacing
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters that often appear in messy JDs
        text = re.sub(r'[~`]', '', text)
        
        # Truncate very long text (likely extraction errors)
        if len(text) > 500:
            text = text[:497] + "..."
        
        return text.strip()
    
    @staticmethod
    def create_fallback_result(error_msg: str) -> JDExtractionResult:
        """Create a fallback result when extraction fails completely"""
        return JDExtractionResult(
            ai_extraction_status=ExtractionStatus.FAILED,
            role_description=f"Extraction failed: {error_msg}"
        )
    
    @staticmethod
    def validate_bill_rate(bill_rate: Optional[str], original_jd: str) -> Optional[str]:
        """
        Fallback validation: If AI missed bill rate, try regex extraction
        This is a safety net for cases where the AI completely misses it
        """
        if bill_rate:
            return bill_rate  # AI got it, trust it
        
        # Try pattern matching as fallback
        patterns = [
            r'bill\s*rate[:\s-]*\$?\s*(\d+(?:\.\d+)?)\s*-?\s*\$?\s*(\d+(?:\.\d+)?)',
            r'bill\s*rate[:\s-]*\$?\s*(\d+(?:\.\d+)?)\s*(?:/hr)?',
            r'bill\s*rate[:\s-]*MAX\s*(?:CONFIRMED\s*)?\$?\s*(\d+(?:\.\d+)?)',
            r'max\s*bill\s*rate[:\s]*\$?\s*(\d+(?:\.\d+)?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, original_jd, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    # Range
                    return f"${groups[0]}-${groups[1]}"
                else:
                    # Single value
                    return f"${groups[0]}"
        
        return None