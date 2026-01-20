# app/services/ai/prompt_templates.py
"""
AI Prompt Templates
Strict JSON-only prompts for JD extraction
"""

JD_EXTRACTION_SYSTEM_PROMPT = """You are a precise job description parser. Extract structured information from job descriptions.

CRITICAL RULES:
1. Return ONLY valid JSON - no markdown, no explanations, no preamble
2. Use exactly these field names
3. Return null for missing information
4. For skills, return array of strings
5. Be concise but accurate

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
}"""


def get_jd_extraction_prompt(jd_text: str) -> str:
    """Generate extraction prompt for a JD"""
    return f"""Extract the following information from this job description:

Job Description:
{jd_text}

Extract:
- Bill Rate: hourly/annual rate (e.g., "$50/hr", "$100k/year")
- Duration: contract length (e.g., "6 months", "1 year")
- Experience Required: years of experience (e.g., "5+ years")
- GBAMS or RGS ID: any ID number mentioned
- Location: work location (city, state, remote status)
- Skills: list of technical skills and requirements
- Role Description: brief summary of the role (max 2 sentences)
- MSP Owner: managed service provider name if mentioned

Return ONLY valid JSON with the structure specified in system prompt. No markdown formatting."""


JD_EXTRACTION_USER_PROMPT_TEMPLATE = """Job Description:
{jd_text}

Return structured extraction as JSON only."""