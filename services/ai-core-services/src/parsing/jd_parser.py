import json
from src.llm.client import OllamaClient
from src.core.logger import logger
from src.parsing.schemas import ParsedJDData

class JDParser:
    def __init__(self):
        self.llm_client = OllamaClient()

    async def parse_jd_text(self, jd_text: str) -> dict:
        """Parses JD text or JSON string using LLM to conform to ParsedJDData schema."""
        prompt = self._build_prompt(jd_text)
        
        logger.info("Sending JD parsing prompt to LLM")
        response = await self.llm_client.openai_chat_generate(prompt=prompt, temperature=0.1, timeout=60.0)
        
        raw_json = response.response.strip()
        try:
            # Basic cleanup in case LLM wraps it in markdown blocks
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            if raw_json.startswith("```"):
                raw_json = raw_json[3:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]
                
            parsed_data = json.loads(raw_json.strip())
            
            # Use Pydantic to ensure the structure matches before returning it as dict
            validated_data = ParsedJDData(**parsed_data)
            return validated_data.model_dump()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON output for JD: {e}\nRaw Output: {response.response}")
            raise ValueError("LLM returned invalid JSON for JD")
        except Exception as e:
            logger.error(f"Failed to validate JD schema: {e}\nRaw Output: {raw_json}")
            raise ValueError(f"LLM returned JSON that does not match schema: {e}")

    def _build_prompt(self, jd_text: str) -> str:
        # Prevent prompt injection issues if the jd_text contains `{` or `}`
        # by passing it dynamically without formatting it into the system rules directly if possible,
        # but here we just replace `{` with `{{` for f-strings if needed, 
        # or we can use normal string replacement.
        prompt = """
You are an expert job description parser. Parse this JD systematically.
Return ONLY a JSON object in this format:
{
  "title": null,
  "company": null,
  "company_description": null,
  "experience_required": {
    "min_years": null,
    "max_years": null
  },
  "skills": {
    "must_have": ["skill1", "skill2"],
    "good_to_have": ["skill1", "skill2"]
  },
  "qualifications": ["degree1", "degree2"],
  "responsibilities": ["resp1", "resp2"],
  "location": null,
  "employment_type": "Full-time"
}

### Job Description Text:
__JD_TEXT__
"""
        return prompt.replace("__JD_TEXT__", jd_text)

jd_parser = JDParser()
