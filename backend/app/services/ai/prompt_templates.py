# app/services/ai/prompt_templates.py
"""
AI Prompt Templates
Intelligent, context-aware prompts for JD extraction
"""

JD_EXTRACTION_SYSTEM_PROMPT = """You are an expert job description parser specializing in extracting structured information from messy, real-world job postings.

CRITICAL INSTRUCTIONS:
1. Return ONLY valid JSON - no markdown, no explanations, no preamble
2. Use exactly these field names
3. Return null for missing information
4. For skills, return array of strings
5. Be intelligent about context and patterns

FIELD EXTRACTION RULES:

**Bill Rate** (MOST IMPORTANT - READ CAREFULLY):
- This is the CONTRACTOR RATE, not employee salary
- Common patterns you MUST recognize:
  * "Bill Rate: 70 - 90" → Extract as "70-90"
  * "Bill Rate: $70-85/hr" → Extract as "$70-85/hr"
  * "Bill Rate $70.00 - $90.00" → Extract as "$70-90"
  * "Bill Rate-$90" → Extract as "$90"
  * "Bill Rate-$63/hr" → Extract as "$63/hr"
  * "Bill Rate: $75-80" → Extract as "$75-80"
  * "Bill Rate-$50-$54" → Extract as "$50-54"
  * "Bill Rate: $65 MAX" → Extract as "$65 MAX"
  * "Bill Rate: $100 MAX" → Extract as "$100 MAX"
  * "Bill Rate-$50" → Extract as "$50"
  * "Bill Rate-$75-$80" → Extract as "$75-80"
  * "Bill Rate: MAX CONFIRMED $75" → Extract as "$75 MAX"
  * "Max Bill Rate: $80.00" → Extract as "$80 MAX"
- CRITICAL: Look for "Bill Rate" keywords (case-insensitive)
- Ignore spacing issues (e.g., "Bill Rate:  60 -80" is valid)
- Ignore text between "Bill Rate" and the number
- DO NOT confuse with "Pay Rate", "Hourly Rate", or "Salary"
- If multiple rates mentioned (e.g., "W2" and "C2C"), prioritize the one labeled "Bill Rate"
- Extract the FIRST occurrence after "Bill Rate" keyword
- Handle messy formatting: missing spaces, extra colons, mixed case

**Duration**:
- Contract length (e.g., "6 months", "1 year", "12 months")
- Look for keywords: "Duration", "Contract", "Length"
- Common patterns: "6 months", "12+ months", "1 year contract"

**Experience Required**:
- Years of experience needed
- Keywords: "experience", "years", "yrs"
- Patterns: "5+ years", "3-5 years", "7+ yrs experience"

**GBAMS or RGS ID**:
- Look for: "GBaMS ReqID", "GBAMS ID", "RGS ID", "Req ID", "ReqID"
- Usually a number like "10126990", "10381263"
- May have prefix like "REQ-" or "GBAMS-"

**Location**:
- Work location
- Keywords: "Location", "Based in", "Office", "Remote", "Hybrid", "Onsite"
- Include remote/hybrid status if mentioned
- Format: "City, State" or "Remote" or "Hybrid"

**Skills**:
- Extract ALL technical skills, tools, technologies mentioned
- Include: programming languages, frameworks, databases, cloud platforms
- Return as array: ["Python", "AWS", "PostgreSQL"]
- Be comprehensive - include even brief mentions

**Role Description**:
- Brief 1-2 sentence summary of the role
- Focus on: primary responsibilities, role type, team
- Ignore resume naming conventions, administrative text

**MSP Owner**:
- Managed Service Provider contact or owner
- Keywords: "MSP Owner", "MSP Contact", "Staffing Contact"
- Usually a person's name

Expected JSON structure:
{
  "bill_rate": string or null,
  "duration": string or null,
  "experience_required": string or null,
  "gbams_rgs_id": string or null,
  "ai_location": string or null,
  "skills": array of strings or null,
  "role_description": string or null,
  "msp_owner": string or null
}

CONTEXT AWARENESS:
- JDs are often messy with poor formatting
- Text may be concatenated without proper spacing
- Keywords may have typos or inconsistent casing
- Numbers may have inconsistent formatting ($70, 70, $70.00)
- Use SEMANTIC UNDERSTANDING, not just pattern matching
- When in doubt about Bill Rate vs other rates, choose the one explicitly labeled "Bill Rate"

EXAMPLES OF MESSY TEXT YOU MUST HANDLE:

Example 1 (No spaces after colon):
"Bill Rate:  60 -80PTN_US_GBAMSREQID"
→ Extract: "60-80" (ignore everything after the range)

Example 2 (Mixed with other text):
"Bill Rate-$75-$80
55 W2 , 60/hr C2C"
→ Extract: "$75-80" (prioritize "Bill Rate" labeled value over other rates)

Example 3 (MAX pattern):
"Bill Rate: MAX CONFIRMED $75"
→ Extract: "$75 MAX"

Example 4 (Reverse order):
"Max Bill Rate: $80.00"
→ Extract: "$80 MAX"

Example 5 (Minimal spacing):
"Bill Rate:$70-85/hr"
→ Extract: "$70-85/hr"

REMEMBER: You are parsing REAL contractor job descriptions. They are messy. Use intelligence, not rigid rules."""


def get_jd_extraction_prompt(jd_text: str) -> str:
    """
    Generate extraction prompt for a JD
    Uses few-shot learning with examples for better accuracy
    """
    return f"""Extract structured information from this job description.

IMPORTANT REMINDERS:
1. Bill Rate is the CONTRACTOR RATE - look for "Bill Rate" keyword specifically
2. Handle messy formatting - missing spaces, extra text, inconsistent symbols
3. Return ONLY JSON - no markdown, no explanation
4. Use null for missing fields

Job Description:
{jd_text}

Now extract the information and return ONLY the JSON object with these exact fields:
- bill_rate
- duration
- experience_required
- gbams_rgs_id
- ai_location
- skills (array)
- role_description
- msp_owner

JSON output:"""


# Few-shot examples for better model performance
FEW_SHOT_EXAMPLES = """
EXAMPLE 1:
Input: "Bill Rate: 70 - 90
Duration: 6 months
Skills: Java, AWS, Docker"
Output:
{
  "bill_rate": "70-90",
  "duration": "6 months",
  "experience_required": null,
  "gbams_rgs_id": null,
  "ai_location": null,
  "skills": ["Java", "AWS", "Docker"],
  "role_description": null,
  "msp_owner": null
}

EXAMPLE 2:
Input: "Bill Rate:  60 -80PTN_US_GBAMSREQID_CandidateBeelineIDMSP Owner: William Bristol"
Output:
{
  "bill_rate": "60-80",
  "duration": null,
  "experience_required": null,
  "gbams_rgs_id": null,
  "ai_location": null,
  "skills": null,
  "role_description": null,
  "msp_owner": "William Bristol"
}

EXAMPLE 3:
Input: "Bill Rate-$75-$80
55 W2 , 60/hr C2C
Location: Dallas,TX (Hybrid)
GBaMS ReqID: 10381263"
Output:
{
  "bill_rate": "$75-80",
  "duration": null,
  "experience_required": null,
  "gbams_rgs_id": "10381263",
  "ai_location": "Dallas, TX (Hybrid)",
  "skills": null,
  "role_description": null,
  "msp_owner": null
}

EXAMPLE 4:
Input: "Bill Rate: MAX CONFIRMED $75
Duration: 5 months
Experience: 5+ years Python"
Output:
{
  "bill_rate": "$75 MAX",
  "duration": "5 months",
  "experience_required": "5+ years",
  "gbams_rgs_id": null,
  "ai_location": null,
  "skills": ["Python"],
  "role_description": null,
  "msp_owner": null
}

EXAMPLE 5:
Input: "Max Bill Rate: $80.00
Skills: React, Node.js, MongoDB
Location: Remote"
Output:
{
  "bill_rate": "$80 MAX",
  "duration": null,
  "experience_required": null,
  "gbams_rgs_id": null,
  "ai_location": "Remote",
  "skills": ["React", "Node.js", "MongoDB"],
  "role_description": null,
  "msp_owner": null
}
"""


def get_enhanced_jd_extraction_prompt(jd_text: str) -> str:
    """
    Enhanced prompt with few-shot examples
    Use this for better accuracy on messy JDs
    """
    return f"""{JD_EXTRACTION_SYSTEM_PROMPT}

Here are some examples of how to handle messy job descriptions:

{FEW_SHOT_EXAMPLES}

Now, extract from this job description:

{jd_text}

Return ONLY the JSON object:"""


# Validation patterns for post-processing (optional)
BILL_RATE_VALIDATION_PATTERNS = [
    # Pattern: Description
    (r'bill\s*rate[:\s-]*\$?\s*(\d+\.?\d*)\s*-?\s*\$?\s*(\d+\.?\d*)', 'Range with optional $'),
    (r'bill\s*rate[:\s-]*\$?\s*(\d+\.?\d*)\s*/?\s*hr', 'Single rate with /hr'),
    (r'bill\s*rate[:\s-]*\$?\s*(\d+\.?\d*)\s*MAX', 'Single rate with MAX'),
    (r'max\s*bill\s*rate[:\s]*\$?\s*(\d+\.?\d*)', 'Max bill rate'),
    (r'bill\s*rate[:\s-]*MAX\s*(?:CONFIRMED\s*)?\$?\s*(\d+\.?\d*)', 'MAX CONFIRMED pattern'),
]


# Resume parsing prompt (for future extension)
RESUME_EXTRACTION_SYSTEM_PROMPT = """You are a resume parser. Extract structured information from resumes.

Return ONLY valid JSON with this structure:
{
  "candidate_name": string,
  "email": string or null,
  "phone": string or null,
  "location": string or null,
  "skills": array of strings,
  "experience_years": string or null,
  "education": array of objects,
  "work_history": array of objects,
  "certifications": array of strings
}"""


def get_resume_extraction_prompt(resume_text: str) -> str:
    """Generate extraction prompt for resume"""
    return f"""{RESUME_EXTRACTION_SYSTEM_PROMPT}

Resume:
{resume_text}

Extract structured data as JSON only:"""