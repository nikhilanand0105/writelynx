import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

SAMPLE_DOC = Path("sample_documents/academic_research_report.docx")
SAMPLE_SOURCE = Path("sample_documents/chen_zhao_reference_paper.docx")

def test_full_api_workflow():
    assert SAMPLE_DOC.exists()
    assert SAMPLE_SOURCE.exists()

    # 1. Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # 2. Upload Document
    with open(SAMPLE_DOC, "rb") as f:
        res_upload = client.post(
            "/api/documents/upload",
            files={"file": ("academic_research_report.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    assert res_upload.status_code == 200
    doc_data = res_upload.json()
    doc_id = doc_data["id"]
    assert doc_data["word_count"] > 100
    assert doc_data["table_count"] == 1

    # 3. Get Document Structure
    res_struct = client.get(f"/api/documents/{doc_id}/structure")
    assert res_struct.status_code == 200
    struct_data = res_struct.json()
    assert len(struct_data["blocks"]) > 5
    assert "Abstract" in struct_data["sections"]

    # 4. Upload Reference Source
    with open(SAMPLE_SOURCE, "rb") as f:
        res_source = client.post(
            f"/api/documents/{doc_id}/sources",
            files={"file": ("chen_zhao_reference_paper.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"is_external_report": False}
        )
    assert res_source.status_code == 200
    source_data = res_source.json()
    assert source_data["token_count"] > 20

    # 5. Run Analysis
    res_analyze = client.post(
        f"/api/documents/{doc_id}/analyze",
        json={"editing_mode": "clarity"}
    )
    assert res_analyze.status_code == 200
    analyze_json = res_analyze.json()
    assert "job_id" in analyze_json

    # Check Analysis Status and Job progress
    res_status = client.get(f"/api/documents/{doc_id}/analysis/status")
    assert res_status.status_code == 200
    status_json = res_status.json()
    assert "job" in status_json

    # Test Job Cancellation Endpoint
    res_cancel = client.post(f"/api/jobs/{analyze_json['job_id']}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["cancel_requested"] is True

    # Retrieve analysis results
    res_analysis = client.get(f"/api/documents/{doc_id}/analysis")
    assert res_analysis.status_code == 200
    analysis_data = res_analysis.json()
    metrics = analysis_data["metrics"]
    assert metrics["analyzed_sources_count"] >= 1
    assert "local_textual_overlap_percentage" in metrics

    # Test Finding Review Endpoint
    if len(analysis_data["findings"]) > 0:
        finding_id = analysis_data["findings"][0]["id"]
        res_rev_find = client.post(
            f"/api/findings/{finding_id}/review",
            json={"review_status": "user_reviewed", "user_notes": "Reviewed in test."}
        )
        assert res_rev_find.status_code == 200
        assert res_rev_find.json()["review_status"] == "user_reviewed"

    # Test Detector Reports Endpoint
    res_reps = client.get(f"/api/documents/{doc_id}/detector-reports")
    assert res_reps.status_code == 200
    assert isinstance(res_reps.json(), list)

    # 6. Retrieve Suggestions
    res_sug = client.get(f"/api/documents/{doc_id}/suggestions")
    assert res_sug.status_code == 200
    sug_list = res_sug.json()
    assert len(sug_list) > 0

    first_sug = sug_list[0]
    # Accept the suggestion
    res_accept = client.post(f"/api/suggestions/{first_sug['id']}/accept")
    assert res_accept.status_code == 200
    assert res_accept.json()["success"] is True

    # 7. Check Revision Log
    res_revs = client.get(f"/api/documents/{doc_id}/revisions")
    assert res_revs.status_code == 200
    assert len(res_revs.json()) >= 1

    # 8. Run Validation
    res_val = client.post(f"/api/documents/{doc_id}/validate")
    assert res_val.status_code == 200
    val_report = res_val.json()
    assert val_report["archive_valid"] is True
    assert val_report["reopened_successfully"] is True

    # 9. Export Revised DOCX
    res_exp_docx = client.post(f"/api/documents/{doc_id}/export/docx")
    assert res_exp_docx.status_code == 200
    export_docx_data = res_exp_docx.json()
    assert "download_url" in export_docx_data

    # Download exported DOCX
    res_dl = client.get(export_docx_data["download_url"])
    assert res_dl.status_code == 200
    assert len(res_dl.content) > 1000

    # 10. Export Revised PDF
    res_exp_pdf = client.post(f"/api/documents/{doc_id}/export/pdf")
    assert res_exp_pdf.status_code == 200
    export_pdf_data = res_exp_pdf.json()
    assert "download_url" in export_pdf_data

    res_dl_pdf = client.get(export_pdf_data["download_url"])
    assert res_dl_pdf.status_code == 200
    assert len(res_dl_pdf.content) > 1000
