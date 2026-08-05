# PDF Parsing Library Evaluation — Resume & JD Extraction

> **Decision**: Based on this evaluation, **Docling** is the selected parsing library for the EZScreen AI pipeline.
> For how it is used in the pipeline, see [AI_PROCESSING.md](../architecture/AI_PROCESSING.md) §4 Document Parsing.

---

## Libraries Evaluated

| Library | Type | Notes |
|---------|------|-------|
| **Docling** | Open-source (local) | IBM Research. Outputs clean Markdown. Handles multi-column, tables, bullets natively. |
| **LlamaParse** | Cloud API | Strong on most layouts but dropped entire sections in some cases. |
| **PyMuPDF4LLM** | Open-source (local) | Fast. Good on simple/moderate layouts. Struggles with multi-column reading order. |
| **OpenDataLoader** | Open-source (local) | Reliable on single-column. Breaks on complex layouts and sidebars. |
| **MarkItDown** | Open-source (local) | Microsoft. Fails on graphical and multi-column layouts. Produces garbled output. |

---

## Test Documents

| # | Resume Style | Key Challenge |
|---|---|---|
| Resume 1 | Graphical CV | Image-heavy, complex visual layout |
| Resume 2 | Formal CV | Heavy use of Markdown-style tables |
| Resume 3 | Two-Column CV | Left sidebar + main column layout |
| Resume 4 | Simple CV | Single column, standard format |
| Resume 5 | Compact CV | Dense text, compressed header area |
| JD | Standard Job Description | Consistent paragraph/list structure |

---

## Comprehensive Evaluation

| Document Style | Parsing Library | Data Extraction & Section Coverage | Structural Formatting Quality | Overall Rating |
|:---|:---|:---|:---|:---|
| **Resume 1: Graphical CV**<br>*(Complex Image-Heavy Layout)* | **🏆 Docling** | Extracted all text perfectly. | ⭐ **Excellent.** Preserved bullet points. Maintained logical reading order. | ⭐⭐⭐⭐ |
| | **LlamaParse (Cloud)** | Good extraction. | ✅ **Good.** Handled the graphical layout decently. | ⭐⭐⭐ |
| | **PyMuPDF4LLM** | All text extracted, but candidate name was buried inside body text. | ⚠️ **Poor.** Headers mixed with body text. Reading order corrupted. | ⭐⭐ |
| | **OpenDataLoader** | Extracted, but reading order broken. | ⚠️ **Poor.** Left and right column data got tangled. | ⭐⭐ |
| | **MarkItDown** | Extracted. | ❌ **Failed.** Flattened entire resume into one unreadable paragraph. | ⭐ |
| | | | | |
| **Resume 2: Formal CV**<br>*(Heavy Markdown Tables)* | **🏆 Docling** | All data extracted cleanly. | ⭐ **Excellent.** Flawless, perfectly aligned `\|--\|--\|` Markdown tables. | ⭐⭐⭐⭐⭐ |
| | **PyMuPDF4LLM** | All extracted (Address and Course slightly merged). | ✅ **Good.** Successfully built acceptable Markdown tables. | ⭐⭐⭐ |
| | **LlamaParse (Cloud)** | All extracted cleanly. | ✅ **Good.** Generated valid Markdown tables. | ⭐⭐⭐ |
| | **OpenDataLoader** | Extracted, but columns merged. | ⚠️ **Poor.** Table data became hard to separate logically. | ⭐⭐ |
| | **MarkItDown** | All extracted. | ⚠️ **Poor.** Flattened table rows into plain, unstructured text. | ⭐⭐ |
| | | | | |
| **Resume 3: Two-Column CV**<br>*(Left Sidebar Layout)* | **🏆 Docling** | ✅ Extracted perfectly. Read Sidebar first, Main column second. | ⭐ **Excellent.** Perfect logical reading order and clean bullet formatting for skills. | ⭐⭐⭐⭐⭐ |
| | **PyMuPDF4LLM** | ✅ Extracted perfectly. Read Sidebar first, Main column second. | ✅ **Good.** Kept sections logically intact. | ⭐⭐⭐⭐ |
| | **OpenDataLoader** | ❌ Reading order broken (Achievements rendered above Candidate Name). | ⚠️ **Poor.** Sections were completely jumbled out of order. | ⭐⭐ |
| | **MarkItDown** | All extracted. | ❌ **Failed.** Forced entire resume into bizarre, broken side-by-side table cells. | ⭐⭐ |
| | **LlamaParse (Cloud)** | ❌ **DROPPED ENTIRE "TECH SKILLS" SECTION.** | ❌ **Critical Failure.** Essential candidate skills were lost entirely. | ⭐ |
| | | | | |
| **Resume 4: Simple CV**<br>*(Single Column)* | **🏆 Docling** | Perfect extraction. | ⭐ **Excellent.** Clean Markdown with actual `-` bullet points. | ⭐⭐⭐⭐⭐ |
| | **PyMuPDF4LLM** | Perfect extraction. | ✅ **Good.** Clean `##` headers used. | ⭐⭐⭐⭐ |
| | **OpenDataLoader** | Perfect extraction. | ✅ **Good.** Reliable on simple layouts. | ⭐⭐⭐⭐ |
| | **LlamaParse (Cloud)** | Perfect extraction. | ✅ **Good.** Reliable on simple layouts. | ⭐⭐⭐⭐ |
| | **MarkItDown** | Perfect extraction. | ⚠️ **Poor.** Corrupted standard bullet points into `(cid:127)` garbage characters. | ⭐⭐⭐ |
| | | | | |
| **Resume 5: Compact CV**<br>*(Dense Text Layout)* | **🏆 Docling** | ⚠️ Name/Contact moved to the absolute BOTTOM. | ✅ **Good.** Body formatting was perfect, but header placement was a PDF artifact issue. | ⭐⭐⭐⭐ |
| | **OpenDataLoader** | Perfect extraction. | ✅ **Good.** | ⭐⭐⭐⭐ |
| | **LlamaParse (Cloud)** | Perfect extraction. | ✅ **Good.** | ⭐⭐⭐⭐ |
| | **PyMuPDF4LLM** | Name and Degree merged on same line. | ✅ **Good.** | ⭐⭐⭐ |
| | **MarkItDown** | Header broken up. | ⚠️ **Poor.** Overused tables to represent plain text paragraphs. | ⭐⭐ |
| | | | | |
| **Job Description (JD)**<br>*(Standard Format)* | **🏆 Docling** | All sections extracted perfectly. | ⚠️ **Okay.** Skills squashed into a single paragraph (due to source PDF structure). | ⭐⭐⭐⭐ |
| | **PyMuPDF4LLM** | All sections extracted perfectly. | ⚠️ **Okay.** Skills squashed into a single paragraph. | ⭐⭐⭐⭐ |
| | **LlamaParse (Cloud)** | All sections extracted perfectly. | ⚠️ **Okay.** Skills squashed into a single paragraph. | ⭐⭐⭐⭐ |
| | **MarkItDown** | All sections extracted perfectly. | ⚠️ **Okay.** Skills squashed into a single paragraph. | ⭐⭐⭐ |
| | **OpenDataLoader** | All sections extracted perfectly. | ⚠️ **Okay.** Skills squashed into a single paragraph. | ⭐⭐⭐ |

---

## Library Score Summary

| Library | Graphical CV | Formal CV (Tables) | Two-Column CV | Simple CV | Compact CV | JD | **Total / 30** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Docling** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **27** |
| **PyMuPDF4LLM** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | **20** |
| **LlamaParse** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **19** |
| **OpenDataLoader** | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | **17** |
| **MarkItDown** | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | **13** |

---

## Decision: Why Docling

- **Consistent across all layout types** — the only library that scored 4+ stars on every resume format.
- **Best-in-class table handling** — outputs clean `|--|--|` Markdown tables that pass directly to the LLM.
- **Multi-column reading order** — correctly reads sidebar → main column without jumbling sections.
- **Local execution** — no cloud API dependency, no data privacy concerns, no per-call cost.
- **Known limitation** — on dense-header PDFs, the name/contact block can be displaced to the bottom. This is a PDF artifact issue, not a Docling bug, and the LLM prompt handles it gracefully.
