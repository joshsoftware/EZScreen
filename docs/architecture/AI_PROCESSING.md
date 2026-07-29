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
5. [Task Execution & Chaining](#5-task-execution--chaining)

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
        PA5["① Download file from S3<br>② LLM extraction: skills, qualifications,<br>responsibilities, location, type<br>③ Fuzzy-map keys to schema<br>④ Write results to DB"]
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

The system sends structured prompts to the LLM for each processing step. The prompts are designed to always return **valid JSON** so the output can be stored directly as JSONB in the database.

### Job Description Extraction

**Input**: Raw JD text (extracted from uploaded document or fetched from URL)

**Prompt instructs the LLM to extract**:

| Field | Type | Description |
|-------|------|-------------|
| `required_skills` | array | Must-have skills explicitly stated |
| `preferred_skills` | array | Good-to-have or bonus skills |
| `minimum_experience_years` | number | Minimum years explicitly mentioned |
| `preferred_experience_years` | number | Preferred/ideal years if mentioned |
| `education_requirements` | array | Degrees required |
| `certifications` | array | Professional certifications required or preferred |
| `job_type` | string | full-time / part-time / contract / internship |
| `work_mode` | string | remote / hybrid / on-site |
| `location` | string | City and country if mentioned |
| `salary_range` | object | min, max, currency if mentioned |
| `responsibilities` | array | Key duties of the role |
| `role_summary` | string | 2-3 sentence overview |

**Constraints applied in prompt**: Return `null` for any field not explicitly found. Do not infer or hallucinate values.

---

### Resume Extraction

**Input**: Raw text extracted from PDF or DOCX resume file

**Prompt instructs the LLM to extract**:

| Field | Type | Description |
|-------|------|-------------|
| `candidate_summary` | string | 2-3 sentence professional summary |
| `primary_skills` | array | Core technical skills |
| `secondary_skills` | array | Supporting technical skills |
| `domain_expertise` | array | Industry/domain knowledge |
| `experience` | array | Each role: company, title, start/end date, responsibilities |
| `total_experience_years` | number | Calculated from all roles (no overlaps) |
| `education` | array | Degree, field, institution, year |
| `certifications` | array | Named certifications |
| `languages` | array | Languages with proficiency level |

**Constraints applied in prompt**: Calculate `total_experience_years` accurately accounting for overlapping roles. Do not count current employer tenure beyond the present date.

---

### Candidate-JD Matching

**Input**: JD `extracted_data` JSONB + Resume `parsed_data` JSONB (both already stored in DB)

**Prompt instructs the LLM to compare and score**:

| Output field | Type | Description |
|-------------|------|-------------|
| `skills_match.score` | 0.0-1.0 | Fraction of required skills matched |
| `skills_match.matched_skills` | array | Skills found in both JD and resume |
| `skills_match.missing_skills` | array | JD required skills absent from resume |
| `experience_match.score` | 0.0-1.0 | Experience level match |
| `experience_match.years_required` | number | From JD |
| `experience_match.years_candidate_has` | number | From resume |
| `education_match.score` | 0.0-1.0 | Education requirements met |
| `education_match.meets_requirements` | boolean | Whether minimum education requirements are satisfied |
| `overall_fit.score` | 0.0-10.0 | Weighted overall match |
| `overall_fit.recommendation` | string | strong_fit / moderate_fit / weak_fit / not_suitable |
| `overall_fit.strengths` | array | Notable positives |
| `overall_fit.concerns` | array | Notable gaps |
| `overall_fit.summary` | string | 2-3 paragraph analysis |

> **Human-in-the-loop**: The AI matching score is an advisory signal, not an automated decision. No candidate is automatically rejected based on matching score alone. HR must explicitly review and confirm every status transition.

---

## 3. Matching Score Formula

The final `matching_score` (0-10) stored on the application is a weighted average of the three sub-scores:

```
  matching_score =
      ( skills_match.score    × 0.40
      + experience_match.score × 0.35
      + education_match.score  × 0.25 ) × 10
```

| Weight | Dimension | Rationale |
|--------|-----------|-----------|
| 40% | Skills match | Most direct signal of capability |
| 35% | Experience match | Seniority and role relevance |
| 25% | Education match | Threshold signal, not a differentiator |

The score is stored as a denormalised `float` column on the applications table to allow fast `ORDER BY matching_score DESC` queries without re-computing.

> **Edge case**: If a dimension cannot be evaluated (e.g., the JD has no education requirements), that dimension scores 0 for the component. This ensures the formula always produces a valid result.

---

## 4. Document Parsing

Before the LLM can extract structured data, the raw file must be converted to plain text. The document parser handles this step:

```mermaid
flowchart TD
    %% Define color classes
    classDef actor fill:#3b82f6,stroke:#2563eb,stroke-width:2px,color:white;
    classDef backend fill:#10b981,stroke:#059669,stroke-width:2px,color:white;
    classDef queue fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:white;
    classDef ai fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:white;
    classDef process fill:#f3f4f6,stroke:#9ca3af,stroke-width:2px,color:#1f2937;

    Upload["Uploaded file (PDF or DOCX)"]:::actor
    Detect["File type detection<br>(MIME type + magic bytes check)"]:::backend
    
    Upload --> Detect

    PDF["PDF path<br>PDF parsing library<br>(page-by-page text extract)"]:::process
    DOCX["DOCX path<br>DOCX parsing library<br>(paragraph extraction)"]:::process

    Detect --> PDF
    Detect --> DOCX

    Output["Plain text string<br>(passed to LLM prompt)"]:::ai
    
    PDF --> Output
    DOCX --> Output
```

Supported input formats: PDF, DOCX. Files are validated by MIME type and magic byte signature - not just file extension - before processing begins.

---

## 5. Task Execution & Chaining

### Task Types

| Task | Input | Output | Status Update |
|------|-------|--------|---------------|
| `parse-jd` | JD record ID | `extracted_data` JSONB | `draft` → `processing` → `draft_parsed` (or `extraction_failed`) |
| `parse-resume` | Application ID | `parsed_data` JSONB | `applied` → `processing` |
| `match-candidate` | Application ID | `matching_result` JSONB, `matching_score`, `years_of_experience` | `processing` → `screened` |
| `send-email` | Template + recipient | Email sent | N/A |

### Task Chaining

The `parse-resume` and `match-candidate` tasks are chained:
1. When `parse-resume` completes successfully, it automatically enqueues `match-candidate` for the same application
2. `match-candidate` fetches the JD's `extracted_data` from the database
3. Runs the LLM matching prompt
4. Writes `matching_result`, `matching_score`, and `years_of_experience` to the application record
5. Updates application status to `screened`

### Reliability

| Concern | Approach |
|---------|----------|
| Retry policy | 3 retries with exponential backoff (e.g. 30s, 120s, 300s) |
| Dead-letter queue | Failed tasks after max retries go to DLQ for investigation |
| Idempotency | Tasks check current record status before processing - safe to re-run |
| Observability | Task start, completion, and failure all written to application logs |
