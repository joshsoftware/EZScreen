# AI Processing Pipeline - AI-Powered Recruitment Platform

> **Source of Truth**: This document is the authoritative reference for AI pipeline architecture, prompt engineering, extraction schemas, matching/scoring logic, and document parsing.
>
> For the overall system architecture and workflow diagrams, see [SYSTEM_DESIGN.md](../architecture/SYSTEM_DESIGN.md) §7 Workflows.
> For JSONB schema definitions stored in the database, see [DB_DESIGN.md](../architecture/DB_DESIGN.md) §5.

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [AI Prompt Engineering](#2-ai-prompt-engineering)
3. [Matching Score Formula](#3-matching-score-formula)
4. [Document Parsing](#4-document-parsing)

> **Related**: For full prompt evaluation results, JD/Resume test profiles, and all 8 parsed JSON match outputs, see [PROMPT_EVALUATION_REPORT.md](../PROMPT_EVALUATION_REPORT.md).

---

## 1. Pipeline Overview

There are two AI pipelines for Phase 1. Both follow the same pattern: **API enqueues task → broker delivers → worker processes → worker writes results to DB**.

```mermaid
---
config:
  layout: elk
---
flowchart LR
 subgraph PA["Pipeline A: Job Description Parsing"]
    direction LR
        PA1["HR uploads JD"]
        PA2["Backend API<br>saves file to S3<br>creates JD record (draft)"]
        PA3["Enqueue<br>parse-jd task"]
        PA4["Worker picks up task"]
        PA5["① LLM extraction: skills, qualifications,<br>responsibilities, location, type<br>② Fuzzy-map keys to schema<br>③ Write results to DB"]
  end
    PA1 --> PA2
    PA2 --> PA3
    PA3 --> PA4
    PA4 --> PA5

     PA1:::actor
     PA2:::backend
     PA3:::queue
     PA4:::queue
     PA5:::process
    classDef actor fill:#3b82f6,stroke:#2563eb,stroke-width:2px,color:white
    classDef backend fill:#10b981,stroke:#059669,stroke-width:2px,color:white
    classDef queue fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:white
    classDef ai fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:white
    classDef process fill:#f3f4f6,stroke:#9ca3af,stroke-width:2px,color:#1f2937
    style PA fill:transparent,stroke:transparent,stroke-width:2px,stroke-dasharray: 5 5
```

```mermaid
---
config:
  layout: elk
---
flowchart LR
 subgraph PB["Pipeline B: Resume Parsing + Matching"]
    direction LR
        PB1["Candidate submits resume"]
        PB2["Backend API<br>saves file to S3<br>creates application (applied)"]
        PB3["Enqueue<br>parse-resume task"]
        PB4["Worker picks up task"]
        PB5["① Download resume from S3<br>② LLM extraction: primary_skills, secondary_skills,<br>domain_expertise, experience, education, certs<br>③ Calculate total_years<br>④ Fetch JD extracted_data from DB<br>⑤ LLM matching: score, matched/missing skills<br>⑥ Write results to DB"]
  end
    PB1 --> PB2
    PB2 --> PB3
    PB3 --> PB4
    PB4 --> PB5

     PB1:::actor
     PB2:::backend
     PB3:::queue
     PB4:::queue
     PB5:::process

    classDef actor fill:#3b82f6,stroke:#2563eb,stroke-width:2px,color:white
    classDef backend fill:#10b981,stroke:#059669,stroke-width:2px,color:white
    classDef queue fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:white
    classDef ai fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:white
    classDef process fill:#f3f4f6,stroke:#9ca3af,stroke-width:2px,color:#1f2937
    style PB fill:transparent,stroke:transparent,stroke-width:2px,stroke-dasharray: 5 5
```

---

## 2. AI Prompt Engineering

The system uses three sequential LLM prompts. Each prompt is designed to return **strict JSON only**, stored directly as JSONB in the database. No markdown, code fences, or explanatory text is permitted in the response.

---

### A. Resume Parsing Prompt

**Input**: Raw resume text extracted from PDF/DOCX via Docling.

```text
You are an expert resume parser specializing in tech and business resumes.
Your task is to meticulously extract specific information and return it as a valid JSON object.

Rules:
- STRICTLY adhere to the JSON schema.
- If information is not explicitly present, set the value to null or an empty list (e.g., []).
  Do NOT guess.
- Primary skills are core, hard skills (e.g., programming languages, specific frameworks).
  Secondary skills are softer skills or less central technologies.
- Domain expertise should be a list of industries or business areas
  (e.g., 'Finance', 'E-commerce', 'Logistics').
- Skills should be concise keywords/tokens, not full sentences.
  Deduplicate and normalize them.
- CRITICAL: For each work experience role, you MUST find and provide the "start_date" and
  "end_date". If the end date is ongoing, use "present".
- Output ONLY the JSON object. Do NOT include any markdown, code fences, or explanatory
  text before or after the JSON.

Schema:
{
  "primary_skills": ["string"],
  "secondary_skills": ["string"],
  "domain_expertise": ["string"],
  "relevant_experience": {
    "total_years": "number or null",
    "roles": [
      {
        "title": "string or null",
        "company": "string or null",
        "start_date": "string or null",
        "end_date": "string or null",
        "years": "number or null",
        "highlights": ["string"]
      }
    ]
  },
  "education_certificates": [
    {
      "name": "string",
      "issuer": "string or null",
      "year": "string or null",
      "type": "degree or certification"
    }
  ]
}
```

**Key constraints**:
- `total_years` must be calculated from role dates — do not copy a self-reported figure from the resume.
- Current roles use `"end_date": "present"` and tenure is computed up to today's date.

---

### B. Job Description Parsing Prompt

**Input**: Raw JD JSON payload (or text) sent from the user.

```text
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
```

**Key constraints**: Return `null` for any field not explicitly mentioned. Do not infer or hallucinate values.

---

### C. Candidate–JD Matching Prompt

**Input**: Both parsed JSONs (resume + JD) already stored in DB, injected into the prompt.

```text
You are an expert technical recruiter and data analyst.
Compare the given candidate resume with the job description and calculate a match score based strictly on the predefined evaluation criteria below.
Return STRICT JSON only, no commentary.

### Candidate Resume (parsed JSON):
__RESUME_JSON__

### Job Description (parsed JSON):
__JD_JSON__

### Predefined Evaluation Criteria (Total: 100 Points)

1. Must-Have Skills (40 Points):
   - Calculate the percentage of JD must-have skills found in the resume.
   - Multiply that percentage by 40.
   - A skill is considered found when there is explicit evidence in the candidate's primary_skills, secondary_skills, or experience.
   - Normalize equivalent technology names before matching.
   - Do not infer a skill from a job title.

2. Relevant Experience (30 Points):
   - Calculate Relevant Experience ONLY by comparing the candidate's professional experience with the JD's MUST-HAVE skills and their required years.
   - For each JD must-have skill, identify the candidate's experience with that skill using experience.roles[].highlights and the corresponding role dates/years.
   - A skill counts as professional experience only when the role's highlights explicitly show that the candidate used or worked with that skill.
   - Do not use primary_skills or secondary_skills alone to determine years of experience.
   - Do not infer experience from a job title.
   - If the same must-have skill appears in multiple roles, combine the relevant experience periods without double-counting overlapping periods.
   - If the candidate has no role-specific evidence for a required must-have skill, candidate_years = 0.0.
   - If required_years is specified for a must-have skill:
     skill_experience_ratio = min(candidate_years / required_years, 1.0)
   - If required_years is not specified:
     skill_experience_ratio = 1.0 if meaningful professional experience exists, otherwise 0.0.
   - Calculate relevant_experience_percentage as the average of all must-have skill experience ratios.
   - Calculate experience_score = relevant_experience_percentage × 30.
   - Round experience_score to 2 decimal places.
   - Do not use the candidate's total_years alone to award experience points. The score must reflect experience with the JD's must-have skills.

3. Good-to-Have Skills (20 Points):
   - Calculate the percentage of JD good-to-have skills found.
   - Multiply that percentage by 20.
   - Normalize equivalent technology names before matching.
   - Do not infer a skill from a job title.

4. Qualifications & Domain (Maximum 10 Points):
   - Award 10 points if they have at least one exact degree/qualification match.
   - Award 5 points if their best match is a somewhat related field.
   - Award 5 points if they have a relevant certificate that comes under qualifications.
   - Award 0 points if completely unrelated and lacking relevant certificates.
   - Consider domain expertise if relevant to the JD.
   - If the JD has no qualification requirements, qualifications_score = 10 and qualification_match = true.

### Instructions:

1. Compare candidate's skills with JD must-have and good-to-have skills.
2. Calculate Relevant Experience specifically from the candidate's experience with the JD's must-have skills and their required years.
3. Use role highlights and role dates/years as the evidence for skill-specific experience.
4. Systematically calculate the score for each of the 4 criteria.
5. Sum the scores to get a total out of 100.
6. Convert the total to a 0.0–10.0 scale:
   match_score = total_score / 10
7. Output reasoning in 2–4 short bullet points.
8. Do not change the predefined weighting: 40 + 30 + 20 + 10 = 100.

### Output Format (STRICT JSON):

{
  "score_breakdown": {
    "must_have_skills_score": 32.0,
    "experience_score": 24.5,
    "good_to_have_skills_score": 15.0,
    "qualifications_score": 10.0
  },
  "match_score": 8.15,
  "reasoning": [
    "Strong coverage of the JD's must-have skills.",
    "The candidate has relevant experience with most required skills but has less experience than required for one must-have skill.",
    "Qualifications and good-to-have skills are largely aligned with the JD."
  ],
  "matched_skills": {
    "must_have": ["..."],
    "good_to_have": ["..."]
  },
  "missing_skills": {
    "must_have": ["..."],
    "good_to_have": ["..."]
  },
  "must_have_experience": [
    {
      "skill": "Java",
      "required_years": 3.0,
      "candidate_years": 4.0,
      "skill_experience_ratio": 1.0,
      "meets_requirement": true
    },
    {
      "skill": "Spring Boot",
      "required_years": 3.0,
      "candidate_years": 2.0,
      "skill_experience_ratio": 0.67,
      "meets_requirement": false
    }
  ],
  "qualification_match": true,
  "experience_match": false
}
```

> **Human-in-the-loop**: The AI matching score is an advisory signal, not an automated decision. No candidate is automatically rejected based on matching score alone. HR must explicitly review and confirm every status transition.

---

## 3. Matching Score Formula

The final `match_score` (0.0–10.0) is derived from a **100-point rubric** evaluated by the LLM matching prompt. The four criteria and their point allocations are:

```
  total_points (max 100) =
      must_have_skills_score     (max 40)
    + experience_score           (max 30)
    + good_to_have_skills_score  (max 20)
    + qualifications_score       (max 10)

  match_score = total_points / 10
```

| Max Points | Criterion | Scoring Logic |
|:-----------:|-----------|---------------|
| **40** | Must-Have Skills | `(matched / total must-haves) × 40` |
| **30** | Relevant Experience | Full 30 if meets/exceeds min years; pro-rated otherwise; 0 if `total_years` is null or 0 |
| **20** | Good-to-Have Skills | `(matched / total good-to-haves) × 20` |
| **10** | Qualifications & Domain | 10 = exact match · 5 = related field or relevant cert · 0 = unrelated |

The `match_score` is stored as a denormalised `float` column on the `applications` table to allow fast `ORDER BY match_score DESC` queries without recomputation.

> **Edge cases**:
> - If the JD specifies no minimum experience, the candidate receives the full 30 points provided `total_years` is not null/0.
> - If the JD has no `good_to_have` skills, that component scores 0 (not redistributed).
> - If `qualifications` list is empty in the JD, the prompt falls back to evaluating domain relevance.

> **Evaluation data**: The formula was validated against 8 test combinations (4 candidate profiles × 2 JDs). See [PROMPT_EVALUATION_REPORT.md](./PROMPT_EVALUATION_REPORT.md) for full results.

---

## 4. Document Parsing

Before the LLM can extract structured data, the raw file must be converted to clean plain text / Markdown. **Docling** is the selected parsing library for this step.

### Selected Library: Docling

Docling was chosen after evaluating 5 libraries across 6 document styles (graphical CVs, table-heavy CVs, two-column layouts, simple CVs, dense CVs, and standard JDs).

| Capability | Docling |
|---|---|
| Multi-column / sidebar reading order | ✅ Correct |
| Markdown table reconstruction | ✅ Flawless |
| Bullet point preservation | ✅ Clean `-` bullets |
| Graphical / image-heavy layout | ✅ Excellent |
| Execution | Local (no cloud API, no cost) |
| Known limitation | On dense-header PDFs, name/contact can be displaced to the bottom (PDF artifact — handled by LLM prompt) |

> **Full evaluation**: See [PDF_PARSING_LIBRARIES.md](../tools_research/PDF_PARSING_LIBRARIES.md) for the complete comparison table across all 5 libraries and 6 document types.

### Parsing Flow

```mermaid
flowchart TD
    classDef actor fill:#3b82f6,stroke:#2563eb,stroke-width:2px,color:white;
    classDef backend fill:#10b981,stroke:#059669,stroke-width:2px,color:white;
    classDef process fill:#f3f4f6,stroke:#9ca3af,stroke-width:2px,color:#1f2937;
    classDef ai fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:white;

    Upload["Uploaded file (PDF or DOCX)"]:::actor
    Detect["File type detection<br>(MIME type + magic bytes check)"]:::backend

    Upload --> Detect

    PDF["PDF path<br>Docling<br>(layout-aware text + Markdown extract)"]:::process
    DOCX["DOCX path<br>Docling<br>(paragraph + table extraction)"]:::process

    Detect --> PDF
    Detect --> DOCX

    Output["Clean Markdown string<br>(passed to LLM prompt)"]:::ai

    PDF --> Output
    DOCX --> Output
```

Supported input formats: **PDF, DOCX**. Files are validated by MIME type and magic byte signature — not just file extension — before processing begins.

---

