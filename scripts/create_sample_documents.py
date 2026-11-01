from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

def create_sample_docs():
    out_dir = Path("sample_documents")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Academic Research Report
    doc = docx.Document()
    
    # Title
    title = doc.add_paragraph()
    r_title = title.add_run("Deep Residual Learning for Robust Semantic Document Analysis")
    r_title.bold = True
    r_title.font.size = Pt(18)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Authors
    author = doc.add_paragraph()
    r_auth = author.add_run("Dr. Elena Vance, Department of Computer Science, University of Technology")
    r_auth.italic = True
    author.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Abstract
    h_abs = doc.add_heading("Abstract", level=1)
    p_abs = doc.add_paragraph(
        "Accurate classification of complex textual representations requires principled empirical frameworks. "
        "In this paper we propose a transformer-based neural network architecture optimized for multi-domain academic text. "
        "Our method demonstrates an F1-score of 0.92 on the benchmark dataset, outperforming baseline SVM and Random Forest models. "
        "Furthermore, our empirical evaluations demonstrate high inference throughput with latency of 14.5 ms per sample. "
        "The proposed approach addresses long-standing challenges in structural document preservation."
    )

    # Section 1: Introduction
    doc.add_heading("1. Introduction", level=1)
    doc.add_paragraph(
        "Modern academic document pipelines must ensure rigorous textual attribution and semantic integrity [1]. "
        "Due to the fact that prior methodologies frequently rely on simplistic lexical filters, subtle conceptual overlap is often overlooked. "
        "In order to resolve these limitations, researchers have explored dense neural embeddings [2]."
    )
    doc.add_paragraph(
        "The remainder of this paper is organized as follows. Section 2 discusses related work. "
        "Section 3 outlines our methodology, while Section 4 presents experimental evaluations."
    )

    # Section 2: Related Work
    doc.add_heading("2. Related Work", level=1)
    doc.add_paragraph(
        "Traditional text comparison systems rely heavily on string distance heuristics and character n-grams [1]. "
        "Studies show that lexical matching fails when authors paraphrase content without proper attribution. "
        "As stated by Chen and Zhao: \"Verbatim textual reproduction undermines academic transparency and scholarly merit\" [3]. "
        "Our work builds upon these foundational principles while introducing robust invariant metrics."
    )

    # Section 3: Methodology
    doc.add_heading("3. Methodology", level=1)
    doc.add_paragraph(
        "We formalize our feature representation through a combination of contextualized token embeddings and structural graph relations. "
        "The model is initialized with 12 layers and 768 hidden dimensions. "
        "Training was conducted by us using the Adam optimizer with a learning rate of 2e-5 and batch size of 32 for 10 epochs."
    )

    # Section 4: Experimental Results
    doc.add_heading("4. Experimental Results", level=1)
    doc.add_paragraph(
        "Table 1 summarizes the empirical performance across standard academic evaluation metrics. "
        "Our proposed architecture achieves superior accuracy and precision compared to legacy baselines."
    )

    # Table 1
    table = doc.add_table(rows=4, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Model", "Accuracy (%)", "F1-Score", "Latency (ms)"]
    for c_idx, h in enumerate(headers):
        cell = table.cell(0, c_idx)
        cell.text = h
        cell.paragraphs[0].runs[0].bold = True

    data = [
        ["SVM Baseline", "81.4%", "0.79", "3.2 ms"],
        ["Random Forest", "84.1%", "0.82", "5.8 ms"],
        ["Proposed Model", "94.6%", "0.92", "14.5 ms"],
    ]
    for r_idx, row in enumerate(data, start=1):
        for c_idx, val in enumerate(row):
            table.cell(r_idx, c_idx).text = val

    p_cap = doc.add_paragraph()
    r_cap = p_cap.add_run("Table 1: Benchmark comparison against baseline classification algorithms.")
    r_cap.italic = True

    doc.add_paragraph(
        "As shown in Figure 1, the convergence rate remains stable throughout 10 epochs. "
        "The empirical results demonstrate a lot of improvement over prior state-of-the-art benchmarks."
    )

    # Section 5: References
    doc.add_heading("References", level=1)
    doc.add_paragraph("[1] A. Smith and B. Taylor, \"Foundations of Modern Plagiarism Detection,\" Journal of Academic Computing, vol. 14, no. 2, pp. 110-125, 2021.")
    doc.add_paragraph("[2] M. Jordan, \"Contextual Embeddings for Information Retrieval,\" IEEE Transactions on Knowledge Engineering, vol. 28, no. 4, pp. 405-419, 2022.")
    doc.add_paragraph("[3] K. Chen and L. Zhao, \"Integrity and Attribution in Higher Education Writing,\" ACM Computing Surveys, vol. 50, no. 1, pp. 1-22, 2023.")

    report_path = out_dir / "academic_research_report.docx"
    doc.save(str(report_path))
    print(f"Created: {report_path}")

    # 2. Reference Source Document (contains overlap with section 2)
    doc_source = docx.Document()
    doc_source.add_heading("Integrity and Attribution in Higher Education Writing", level=1)
    doc_source.add_paragraph("By K. Chen and L. Zhao, 2023.")
    doc_source.add_paragraph(
        "Verbatim textual reproduction undermines academic transparency and scholarly merit. "
        "Traditional text comparison systems rely heavily on string distance heuristics and character n-grams. "
        "When passages are duplicated without clear attribution, readers cannot distinguish the author's primary contributions from prior findings."
    )
    doc_source.add_paragraph(
        "Modern academic document pipelines must ensure rigorous textual attribution and semantic integrity."
    )
    source_path = out_dir / "chen_zhao_reference_paper.docx"
    doc_source.save(str(source_path))
    print(f"Created: {source_path}")

if __name__ == "__main__":
    create_sample_docs()
