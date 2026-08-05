# Prompt Evaluation Report — Resume-JD Matching System

> **Related**: For the prompt text and scoring formula, see [AI_PROCESSING.md](./architecture/AI_PROCESSING.md).
> This document is the authoritative record of how the matching prompts perform across distinct candidate and JD profiles.

---

## Table of Contents

1. [Test Setup](#1-test-setup)
2. [JD Profiles](#2-jd-profiles)
3. [Candidate Profiles](#3-candidate-profiles)
4. [Full Comparison Table](#4-full-comparison-table)
5. [Appendix A — Parsed JD JSONs](#5-appendix-a--parsed-jd-jsons)
6. [Appendix B — Parsed Resume JSONs](#6-appendix-b--parsed-resume-jsons)
7. [Appendix C — Detailed Match Results](#7-appendix-c--detailed-match-results)

---

## 1. Test Setup

The matching system was evaluated against **8 combinations** — 4 distinct candidate resume profiles crossed with 2 job descriptions — to validate that the prompt handles edge cases correctly (overqualified, unrelated, fresh graduate, no-minimum-experience JDs).

| Dimension | Count |
|-----------|-------|
| Job Descriptions | 2 |
| Candidate Resumes | 4 |
| Total Test Combinations | 8 |

---

## 2. JD Profiles

| ID | Label | Key Must-Have Skills | Experience Required |
|----|-------|----------------------|---------------------|
| **JD 1** | Modern Cloud Backend | Java 17, Spring Boot, JSON/XML, REST APIs, ELK, AWS CloudWatch, SQL | Not specified |
| **JD 2** | Legacy Enterprise | Core Java, Advanced Java, J2EE, EJB, Hibernate, MySQL, SQL, jQuery, HTML5, CSS3, JS | 3–5 years |

---

## 3. Candidate Profiles

| ID | Label | Experience | Key Technologies |
|----|-------|------------|-----------------|
| **Resume 1** | Mid-level Aligned | 4 years | Java, Spring Boot, Hibernate, SQL, J2EE |
| **Resume 2** | Completely Unrelated | 7 years | Web Design, Branding, SEO |
| **Resume 3** | Senior Dev (10+ Years) | 10 years | J2EE, Spring Boot, SOAP, EJB, SQL |
| **Resume 4** | Fresh Graduate (2025) | 0 years | Java, Spring Boot, React, ML, MongoDB |

---

## 4. Full Comparison Table

| Job Description | JD Key Requirements | Candidate Resume | Match Score | Candidate Highlights | Reasoning |
|---|---|---|:---:|---|---|
| **JD 1** | Java 17, Spring Boot, ELK, AWS CloudWatch, SQL. **(No minimum experience)** | **Resume 1:** Mid-level Aligned | **6.3 / 10** | 4 yrs exp. Java, Spring Boot, Hibernate, SQL | Core skills matched (Java, Spring Boot, SQL, REST) but lacks ELK, AWS CloudWatch, Postman, Swagger. Experience maxed (no min specified). No good-to-have matches (Docker, AWS Cloud). Qualification match: B.E. Computer Science. |
| **JD 1** | Java 17, Spring Boot, ELK, AWS CloudWatch, SQL. **(No minimum experience)** | **Resume 2:** Completely Unrelated | **3.0 / 10** | 7 yrs exp. Web Design, Branding, SEO | Zero overlap with required tech skills (Graphic Designer vs Java Developer). Full 30 pts awarded for experience (no minimum; 7 years total). Degree in Design is unrelated to CS/Engineering requirements. |
| **JD 1** | Java 17, Spring Boot, ELK, AWS CloudWatch, SQL. **(No minimum experience)** | **Resume 3:** Senior Dev | **6.3 / 10** | 10 yrs exp. J2EE, Spring Boot, SOAP, EJB | 10 years exceeds non-specified minimum. Strong backend match (Java, Spring Boot, SQL, REST) but lacks ELK, CloudWatch, Postman, Swagger. No Docker/AWS Cloud experience. B.E. Computer Science = qualification match. |
| **JD 1** | Java 17, Spring Boot, ELK, AWS CloudWatch, SQL. **(No minimum experience)** | **Resume 4:** Fresh Graduate | **3.0 / 10** | 0 yrs exp. Java, Spring Boot, React, ML | Core must-haves present (Java, Spring Boot, SQL) but lacks cloud/monitoring tools. Experience score = 0 (total_years is null). Strong qualification match (B.E. Computer Engineering). No good-to-have matches. |
| **JD 2** | J2EE, EJB, Hibernate, jQuery, HTML5/CSS3. **(Requires 3–5 years)** | **Resume 1:** Mid-level Aligned | **9.6 / 10** | 4 yrs exp. Java, Spring Boot, Hibernate, SQL | Matches 10/11 must-haves (only EJB missing). Exceeds 3-year minimum with 4 years. All 6 good-to-have skills matched. B.E. Computer Science fulfills qualifications. |
| **JD 2** | J2EE, EJB, Hibernate, jQuery, HTML5/CSS3. **(Requires 3–5 years)** | **Resume 2:** Completely Unrelated | **3.0 / 10** | 7 yrs exp. Web Design, Branding, SEO | Zero overlap in technical skill sets. Meets experience minimum (7 years) but in an unrelated field. No must-have or good-to-have skill matches. |
| **JD 2** | J2EE, EJB, Hibernate, jQuery, HTML5/CSS3. **(Requires 3–5 years)** | **Resume 3:** Senior Dev | **10.0 / 10** | 10 yrs exp. J2EE, Spring Boot, SOAP, EJB | 100% must-have and good-to-have skill match. 10 years exceeds 3-year minimum. B.E. Computer Science and certifications align strongly. |
| **JD 2** | J2EE, EJB, Hibernate, jQuery, HTML5/CSS3. **(Requires 3–5 years)** | **Resume 4:** Fresh Graduate | **2.8 / 10** | 0 yrs exp. Java, Spring Boot, React, ML | Fails experience minimum (0 years vs 3 required). Only MySQL, Java/JavaScript match; missing J2EE, EJB, Hibernate, frontend stack. Strong academic background and certifications noted. |

---

## 5. Appendix A — Parsed JD JSONs

### JD 1: Modern Cloud Backend

```json
{
  "title": "Java Developer",
  "company": "Company A",
  "company_description": "Company A is relentlessly focused on discovering, developing and delivering innovative solutions that connect our customers to the people they serve through the advanced use of technology. With more than 15 years' experience, they operate in the USA, Australia, Europe, SE Asia and India.",
  "experience_required": {
    "min_years": null,
    "max_years": null
  },
  "skills": {
    "must_have": [
      "Core Java (Java 17)",
      "Spring Boot",
      "JSON",
      "XML",
      "Yaml",
      "Rest API",
      "Postman",
      "Swagger",
      "ELK",
      "AWS CloudWatch",
      "SQL"
    ],
    "good_to_have": [
      "AWS Cloud",
      "Docker",
      "Containers",
      "English Fluency"
    ]
  },
  "qualifications": [
    "M.C.A",
    "B.Sc/MSc Computers",
    "B.E /B.Tech in Computer Science",
    "Engineering or a related field"
  ],
  "responsibilities": [],
  "location": null,
  "employment_type": "Full-time"
}
```

### JD 2: Legacy Enterprise

```json
{
  "title": "Java Developer",
  "company": "Company B",
  "company_description": "Company B is a company that develops enterprise-level applications and provides software solutions.",
  "experience_required": {
    "min_years": 3,
    "max_years": 5
  },
  "skills": {
    "must_have": [
      "Core Java",
      "Advanced Java",
      "J2EE",
      "EJB",
      "Hibernate",
      "MySQL",
      "SQL",
      "jQuery",
      "HTML5",
      "CSS3",
      "JavaScript"
    ],
    "good_to_have": [
      "Oracle",
      "Tomcat",
      "Glassfish",
      "REST web services",
      "SOAP web services",
      "Spring Boot"
    ]
  },
  "qualifications": [],
  "responsibilities": [
    "Develop and maintain Java-based applications",
    "Work with J2EE technologies, EJB, and Hibernate",
    "Build dynamic UI components using jQuery, HTML, CSS, and JavaScript",
    "Participate in requirement analysis, design discussions, and code reviews",
    "Debug issues and provide technical support"
  ],
  "location": "Nagpur",
  "employment_type": "Full-time"
}
```

---

## 6. Appendix B — Parsed Resume JSONs

### Resume 1: Mid-level Aligned (4 Years Experience)

```json
{
  "primary_skills": [
    "Core Java", "Advanced Java", "J2EE", "Hibernate", "Spring Boot",
    "JDBC", "MySQL", "Oracle", "REST", "SOAP", "SQL", "JavaScript",
    "Servlets", "JSP"
  ],
  "secondary_skills": [
    "HTML5", "CSS3", "jQuery", "Apache Tomcat", "GlassFish", "Git",
    "Maven", "Eclipse", "IntelliJ IDEA", "Problem Solving",
    "Communication", "Team Collaboration", "Agile Development"
  ],
  "domain_expertise": [],
  "relevant_experience": {
    "total_years": 4,
    "roles": [
      {
        "title": "Java Developer",
        "company": "ABC Technologies",
        "start_date": "Jul 2022",
        "end_date": "present",
        "years": 2.2,
        "highlights": [
          "Developed enterprise Java applications using Core Java, J2EE, Hibernate, and MySQL",
          "Designed REST APIs and integrated front-end pages using HTML5, CSS3, JavaScript, and jQuery",
          "Optimized SQL queries, improving response time by 35%",
          "Participated in requirement gathering, design discussions, code reviews, testing, and deployment",
          "Resolved production defects and provided technical support"
        ]
      },
      {
        "title": "Software Engineer",
        "company": "XYZ Solutions",
        "start_date": "Jan 2021",
        "end_date": "Jun 2022",
        "years": 1.5,
        "highlights": [
          "Built CRUD modules using JSP, Servlets, JDBC, and Hibernate",
          "Integrated Oracle/MySQL databases and implemented stored procedures",
          "Deployed applications on Apache Tomcat and maintained documentation"
        ]
      }
    ]
  },
  "education_certificates": [
    { "name": "Bachelor of Engineering in Computer Science", "issuer": null, "year": null, "type": "degree" },
    { "name": "Java Programming", "issuer": null, "year": null, "type": "certification" },
    { "name": "Spring Boot Fundamentals", "issuer": null, "year": null, "type": "certification" },
    { "name": "SQL & Database Design", "issuer": null, "year": null, "type": "certification" }
  ]
}
```

### Resume 2: Completely Unrelated (Graphic Designer, 7 Years)

```json
{
  "primary_skills": ["Web Design", "Branding", "Graphic Design", "SEO"],
  "secondary_skills": ["Marketing", "English", "French"],
  "domain_expertise": [],
  "relevant_experience": {
    "total_years": 7,
    "roles": [
      {
        "title": "Senior Graphic Designer",
        "company": "Fauget Studio",
        "start_date": "2020",
        "end_date": "2024",
        "years": 4,
        "highlights": ["Led brand identity and digital design campaigns"]
      },
      {
        "title": "Senior Graphic Designer",
        "company": "Larana, Inc.",
        "start_date": "2017",
        "end_date": "2019",
        "years": 2,
        "highlights": ["Visual design, branding, and client deliverables"]
      }
    ]
  },
  "education_certificates": [
    { "name": "Bachelor of Design", "issuer": "Wardiere University", "year": "2015", "type": "degree" },
    { "name": "Bachelor of Design", "issuer": "Wardiere University", "year": "2019", "type": "degree" }
  ]
}
```

### Resume 3: Senior Dev (10+ Years Experience)

```json
{
  "primary_skills": [
    "Core Java", "Advanced Java", "J2EE", "Spring Boot", "Hibernate",
    "JDBC", "MySQL", "Oracle", "SQL", "REST", "SOAP", "EJB",
    "Servlets", "JSP"
  ],
  "secondary_skills": [
    "HTML5", "CSS3", "JavaScript", "jQuery", "Apache Tomcat", "GlassFish",
    "Git", "Maven", "Jenkins", "IntelliJ IDEA", "Eclipse", "Agile", "SDLC"
  ],
  "domain_expertise": ["Banking", "Human Resources"],
  "relevant_experience": {
    "total_years": 10,
    "roles": [
      {
        "title": "Senior Java Developer",
        "company": "ABC Technologies",
        "start_date": "Jan 2020",
        "end_date": "present",
        "years": 4,
        "highlights": [
          "Designed and developed enterprise Java applications using Spring Boot, Hibernate, and MySQL",
          "Built REST APIs and optimized SQL queries improving performance by 45%",
          "Led code reviews, mentored developers, and collaborated with stakeholders throughout the SDLC"
        ]
      },
      {
        "title": "Java Technical Lead",
        "company": "XYZ Solutions",
        "start_date": "Jun 2016",
        "end_date": "Dec 2019",
        "years": 3.5,
        "highlights": [
          "Delivered J2EE applications using Hibernate, Oracle, and Tomcat",
          "Integrated REST/SOAP services and resolved production issues"
        ]
      },
      {
        "title": "Java Developer",
        "company": "PQR Software",
        "start_date": "Jul 2012",
        "end_date": "May 2016",
        "years": 3.8,
        "highlights": [
          "Developed modules using Core Java, JSP, Servlets, JDBC, Hibernate, HTML, CSS, JavaScript, and jQuery"
        ]
      }
    ]
  },
  "education_certificates": [
    { "name": "Bachelor of Engineering in Computer Science", "issuer": null, "year": null, "type": "degree" },
    { "name": "Oracle Java Certification", "issuer": "Oracle", "year": null, "type": "certification" },
    { "name": "Spring Boot", "issuer": null, "year": null, "type": "certification" },
    { "name": "Agile Scrum", "issuer": null, "year": null, "type": "certification" }
  ]
}
```

### Resume 4: Fresh Graduate (2025)

```json
{
  "primary_skills": [
    "Java", "Spring Boot", "Spring Cloud Gateway", "Eureka",
    "MongoDB", "MySQL", "Express.js", "React.js", "Redux Toolkit",
    ".NET", "REST APIs", "Python", "Machine Learning", "C++"
  ],
  "secondary_skills": [
    "System Design", "Microservices", "Data Structures",
    "Algorithms", "OS Concepts"
  ],
  "domain_expertise": ["E-commerce", "Entertainment"],
  "relevant_experience": {
    "total_years": null,
    "roles": []
  },
  "education_certificates": [
    { "name": "BE Computer Engineering", "issuer": "Savitribai Phule Pune University", "year": "2025", "type": "degree" },
    { "name": "PG-DAC", "issuer": "C-DAC", "year": "2025", "type": "certification" },
    { "name": "Machine Learning", "issuer": "NPTEL", "year": null, "type": "certification" },
    { "name": "XII Science", "issuer": "Maharashtra State Board of Higher Secondary Education", "year": "2021", "type": "degree" },
    { "name": "X General", "issuer": "Maharashtra State Board of Secondary Education", "year": "2019", "type": "degree" }
  ]
}
```

---

## 7. Appendix C — Detailed Match Results

### 7.1 JD 1 × Resume 1 — Mid-level Aligned

```json
{
  "score_breakdown": {
    "must_have_skills_score": 23.3,
    "experience_score": 30.0,
    "good_to_have_skills_score": 0.0,
    "qualifications_score": 10.0
  },
  "match_score": 6.3,
  "reasoning": [
    "Candidate possesses key core skills (Core Java, Spring Boot, SQL, REST) but lacks specific toolset requirements like ELK, AWS CloudWatch, Postman, and Swagger.",
    "Experience score is maximized as there is no minimum year requirement specified in the JD and the candidate has 4 years of experience.",
    "No matches found for 'Good-to-Have' skills such as Docker or AWS Cloud.",
    "Perfect qualification match with a Bachelor of Engineering in Computer Science."
  ],
  "matched_skills": {
    "must_have": ["Core Java", "Spring Boot", "Rest API", "SQL"],
    "good_to_have": []
  },
  "missing_skills": {
    "must_have": ["Java 17", "JSON", "XML", "Yaml", "Postman", "Swagger", "ELK", "AWS CloudWatch"],
    "good_to_have": ["AWS Cloud", "Docker", "Containers", "English Fluency"]
  },
  "qualification_match": true,
  "experience_match": true
}
```

### 7.2 JD 1 × Resume 2 — Completely Unrelated (Graphic Designer)

```json
{
  "score_breakdown": {
    "must_have_skills_score": 0.0,
    "experience_score": 30.0,
    "good_to_have_skills_score": 0.0,
    "qualifications_score": 0.0
  },
  "match_score": 3.0,
  "reasoning": [
    "Candidate has zero overlap with the required technical skill set (Java Developer vs Graphic Designer).",
    "Full points awarded for experience as the JD specifies no minimum years required and candidate has 7 years of professional work.",
    "Candidate's degree in Design is unrelated to the Computer Science/Engineering requirements of the role."
  ],
  "matched_skills": { "must_have": [], "good_to_have": [] },
  "missing_skills": {
    "must_have": ["Core Java", "Java 17", "Spring Boot", "JSON", "XML", "Yaml", "Rest API", "Postman", "Swagger", "ELK", "AWS CloudWatch", "SQL"],
    "good_to_have": ["AWS Cloud", "Docker", "Containers", "English Fluency"]
  },
  "qualification_match": false,
  "experience_match": true
}
```

### 7.3 JD 1 × Resume 3 — Senior Dev (10+ Years)

```json
{
  "score_breakdown": {
    "must_have_skills_score": 23.3,
    "experience_score": 30.0,
    "good_to_have_skills_score": 0.0,
    "qualifications_score": 10.0
  },
  "match_score": 6.3,
  "reasoning": [
    "Candidate possesses 10 years of experience, exceeding the non-specified minimum requirement.",
    "Strong match in core backend skills (Core Java, Spring Boot, SQL, REST) but lacks specific tools like ELK, AWS CloudWatch, Postman, and Swagger.",
    "No mentioned experience with Docker, Containers, or AWS Cloud from the good-to-have list.",
    "Perfect qualification match with a Bachelor of Engineering in Computer Science."
  ],
  "matched_skills": {
    "must_have": ["Core Java", "Spring Boot", "Rest API", "SQL"],
    "good_to_have": []
  },
  "missing_skills": {
    "must_have": ["Java 17", "JSON", "XML", "Yaml", "Postman", "Swagger", "ELK", "AWS CloudWatch"],
    "good_to_have": ["AWS Cloud", "Docker", "Containers", "English Fluency"]
  },
  "qualification_match": true,
  "experience_match": true
}
```

### 7.4 JD 1 × Resume 4 — Fresh Graduate

```json
{
  "score_breakdown": {
    "must_have_skills_score": 20.0,
    "experience_score": 0.0,
    "good_to_have_skills_score": 0.0,
    "qualifications_score": 10.0
  },
  "match_score": 3.0,
  "reasoning": [
    "Candidate possesses core must-have skills like Java, Spring Boot, and SQL, but lacks cloud monitoring (ELK, AWS CloudWatch) and API documentation tools (Swagger, Postman).",
    "Experience score is 0 as the candidate's total_years is listed as null.",
    "Candidate has a strong qualification match with a BE in Computer Engineering.",
    "No good-to-have skills such as AWS Cloud or Docker were found in the resume."
  ],
  "matched_skills": {
    "must_have": ["Java", "Spring Boot", "REST APIs", "SQL"],
    "good_to_have": []
  },
  "missing_skills": {
    "must_have": ["Java 17", "JSON", "XML", "Yaml", "Postman", "Swagger", "ELK", "AWS CloudWatch"],
    "good_to_have": ["AWS Cloud", "Docker", "Containers", "English Fluency"]
  },
  "qualification_match": true,
  "experience_match": false
}
```

### 7.5 JD 2 × Resume 1 — Mid-level Aligned

```json
{
  "score_breakdown": {
    "must_have_skills_score": 36.36,
    "experience_score": 30.0,
    "good_to_have_skills_score": 20.0,
    "qualifications_score": 10.0
  },
  "match_score": 9.6,
  "reasoning": [
    "Candidate matches 10 out of 11 must-have skills, missing only EJB.",
    "Exceeds the minimum experience requirement of 3 years with a total of 4 years.",
    "Possesses all 6 listed good-to-have skills, including Spring Boot and REST/SOAP.",
    "Holds a Bachelor of Engineering in Computer Science, fulfilling qualification needs."
  ],
  "matched_skills": {
    "must_have": ["Core Java", "Advanced Java", "J2EE", "Hibernate", "MySQL", "SQL", "jQuery", "HTML5", "CSS3", "JavaScript"],
    "good_to_have": ["Oracle", "Tomcat", "Glassfish", "REST web services", "SOAP web services", "Spring Boot"]
  },
  "missing_skills": {
    "must_have": ["EJB"],
    "good_to_have": []
  },
  "qualification_match": true,
  "experience_match": true
}
```

### 7.6 JD 2 × Resume 2 — Completely Unrelated (Graphic Designer)

```json
{
  "score_breakdown": {
    "must_have_skills_score": 0.0,
    "experience_score": 30.0,
    "good_to_have_skills_score": 0.0,
    "qualifications_score": 0.0
  },
  "match_score": 3.0,
  "reasoning": [
    "Candidate is a Graphic Designer, while the role is for a Java Developer; there is zero overlap in technical skill sets.",
    "Candidate meets the minimum experience requirement of 3 years (7 years total), but in an entirely unrelated field.",
    "No matching must-have or good-to-have technical skills were found in the resume."
  ],
  "matched_skills": { "must_have": [], "good_to_have": [] },
  "missing_skills": {
    "must_have": ["Core Java", "Advanced Java", "J2EE", "EJB", "Hibernate", "MySQL", "SQL", "jQuery", "HTML5", "CSS3", "JavaScript"],
    "good_to_have": ["Oracle", "Tomcat", "Glassfish", "REST web services", "SOAP web services", "Spring Boot"]
  },
  "qualification_match": false,
  "experience_match": true
}
```

### 7.7 JD 2 × Resume 3 — Senior Dev (10+ Years)

```json
{
  "score_breakdown": {
    "must_have_skills_score": 40.0,
    "experience_score": 30.0,
    "good_to_have_skills_score": 20.0,
    "qualifications_score": 10.0
  },
  "match_score": 10.0,
  "reasoning": [
    "Candidate possesses 100% of the must-have skills and 100% of the good-to-have skills specified in the JD.",
    "Total experience (10 years) exceeds the minimum requirement of 3 years.",
    "Highest qualification (B.E. in Computer Science) and professional certifications strongly align with the technical role."
  ],
  "matched_skills": {
    "must_have": ["Core Java", "Advanced Java", "J2EE", "EJB", "Hibernate", "MySQL", "SQL", "jQuery", "HTML5", "CSS3", "JavaScript"],
    "good_to_have": ["Oracle", "Tomcat", "Glassfish", "REST", "SOAP", "Spring Boot"]
  },
  "missing_skills": { "must_have": [], "good_to_have": [] },
  "qualification_match": true,
  "experience_match": true
}
```

### 7.8 JD 2 × Resume 4 — Fresh Graduate

```json
{
  "score_breakdown": {
    "must_have_skills_score": 10.9,
    "experience_score": 0.0,
    "good_to_have_skills_score": 6.7,
    "qualifications_score": 10.0
  },
  "match_score": 2.8,
  "reasoning": [
    "Candidate lacks the minimum required 3 years of professional experience (total_years is null).",
    "Only a small fraction of must-have skills (MySQL, Java/JavaScript) match; missing critical J2EE, EJB, Hibernate, and frontend stack.",
    "Possesses a strong academic background in Computer Engineering and relevant certifications."
  ],
  "matched_skills": {
    "must_have": ["Java", "MySQL", "JavaScript"],
    "good_to_have": ["Spring Boot", "REST APIs"]
  },
  "missing_skills": {
    "must_have": ["Advanced Java", "J2EE", "EJB", "Hibernate", "SQL", "jQuery", "HTML5", "CSS3"],
    "good_to_have": ["Oracle", "Tomcat", "Glassfish", "SOAP web services"]
  },
  "qualification_match": true,
  "experience_match": false
}
```
