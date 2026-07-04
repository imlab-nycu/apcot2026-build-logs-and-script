# APCOT 2026 Proceedings Workflow

This document explains how the proceedings were built and which files correspond to each step.

## 1. Collect the source material

The process starts from the abstract index pages and the abstract archive.

Files:
- [apcot2026_abstract_index_v3.html](apcot2026_abstract_index_v3.html)
- [apcot2026_abstract_index_v4.html](apcot2026_abstract_index_v4.html)
- [APCOT_Abstract/](APCOT_Abstract/)

## 2. Build the master manifest

The abstracts and metadata are turned into a manifest that lists the proceedings entries.

Files:
- [derived/APCOT2026_proceedings_manifest.csv](derived/APCOT2026_proceedings_manifest.csv)
- [derived/APCOT2026_proceedings_manifest.json](derived/APCOT2026_proceedings_manifest.json)

## 3. Generate the public manifest

The master manifest is filtered or adapted into a public version for release builds.

Files:
- [derived/APCOT2026_public_proceedings_manifest.csv](derived/APCOT2026_public_proceedings_manifest.csv)
- [derived/APCOT2026_public_proceedings_manifest.json](derived/APCOT2026_public_proceedings_manifest.json)

## 4. Clean and audit the author data

Several audit passes were used to normalize author names, compare against PDFs, and apply manual fixes.

Files:
- [derived/APCOT2026_public_v7_author_replacement_audit.csv](derived/APCOT2026_public_v7_author_replacement_audit.csv)
- [derived/APCOT2026_public_v7a_author_cleanup_audit.csv](derived/APCOT2026_public_v7a_author_cleanup_audit.csv)
- [derived/APCOT2026_public_v7b_manual_author_overrides.csv](derived/APCOT2026_public_v7b_manual_author_overrides.csv)
- [derived/APCOT2026_public_v7c_pdf_author_crosscheck.csv](derived/APCOT2026_public_v7c_pdf_author_crosscheck.csv)
- [derived/APCOT2026_public_v7d_manual_pdf_checks.csv](derived/APCOT2026_public_v7d_manual_pdf_checks.csv)
- [derived/APCOT2026_public_v8_proceedings_manifest_authors_clean.csv](derived/APCOT2026_public_v8_proceedings_manifest_authors_clean.csv)
- [derived/APCOT2026_public_v9_proceedings_manifest_authors_clean.csv](derived/APCOT2026_public_v9_proceedings_manifest_authors_clean.csv)
- [derived/APCOT2026_public_v10_proceedings_manifest_authors_clean.csv](derived/APCOT2026_public_v10_proceedings_manifest_authors_clean.csv)

## 5. Build the proceedings PDFs

Each release variant produced a build log and one or more PDFs.

Files:
- [derived/APCOT2026_public_v4_build_log.json](derived/APCOT2026_public_v4_build_log.json)
- [derived/APCOT2026_public_v4_front_matter.pdf](derived/APCOT2026_public_v4_front_matter.pdf)
- [derived/APCOT2026_Abstract_Proceedings_public_v4.pdf](derived/APCOT2026_Abstract_Proceedings_public_v4.pdf)
- [derived/APCOT2026_public_v5_build_log.json](derived/APCOT2026_public_v5_build_log.json)
- [derived/APCOT2026_public_v6_preview_build_log.json](derived/APCOT2026_public_v6_preview_build_log.json)
- [derived/APCOT2026_public_v9_build_log.json](derived/APCOT2026_public_v9_build_log.json)
- [derived/APCOT2026_public_v10_build_log.json](derived/APCOT2026_public_v10_build_log.json)

## 6. Generate numbered and compressed editions

Later releases included numbered and compressed variants.

Files:
- [derived/APCOT2026_public_v9_numbered_build_log.json](derived/APCOT2026_public_v9_numbered_build_log.json)
- [derived/APCOT2026_public_v9_numbered_compressed_build_log.json](derived/APCOT2026_public_v9_numbered_compressed_build_log.json)
- [derived/APCOT2026_public_v10_numbered_build_log.json](derived/APCOT2026_public_v10_numbered_build_log.json)
- [derived/APCOT2026_public_v10_numbered_compressed_build_log.json](derived/APCOT2026_public_v10_numbered_compressed_build_log.json)

## 7. Build the table of contents pages

The TOC pages are generated from the cleaned manifest by the dedicated Python script.

Files:
- [make_public_v10b_toc.py](make_public_v10b_toc.py)
- [derived/APCOT2026_public_v10b_toc_pages.pdf](derived/APCOT2026_public_v10b_toc_pages.pdf)
- [derived/APCOT2026_public_v10b_toc_build_log.json](derived/APCOT2026_public_v10b_toc_build_log.json)

## 8. Produce the front matter

The front matter is built separately for each public release line.

Files:
- [derived/APCOT2026_front_matter.pdf](derived/APCOT2026_front_matter.pdf)
- [derived/APCOT2026_public_front_matter.pdf](derived/APCOT2026_public_front_matter.pdf)
- [derived/APCOT2026_public_v9_front_matter.pdf](derived/APCOT2026_public_v9_front_matter.pdf)
- [derived/APCOT2026_public_v10b_front_matter.pdf](derived/APCOT2026_public_v10b_front_matter.pdf)

## 9. Record the build outputs

Each stage writes a build log so the pipeline can be audited and reproduced.

Files:
- [derived/APCOT2026_build_log.json](derived/APCOT2026_build_log.json)
- [derived/APCOT2026_public_build_log.json](derived/APCOT2026_public_build_log.json)
- [derived/APCOT2026_public_v10b_front_matter_build_log.json](derived/APCOT2026_public_v10b_front_matter_build_log.json)

## Notes

- PDFs are intentionally excluded from the repository size calculation when you only want lightweight artifacts.
- The repository README is a short overview; this file is the fuller workflow explanation.