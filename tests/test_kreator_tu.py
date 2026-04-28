"""
Tests for Kreator CV — Tomasz Uściński instance.

Tests cover:
- Character limits on generated CV sections
- DOCX generation and placeholder integrity
- No hallucination beyond base profile
- Filename generation
- History storage
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_DIR      = Path(__file__).parent.parent
MASTER_CV_PATH = BASE_DIR / "data" / "master_cv.json"


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def master_cv() -> dict:
    """Load master CV from data/master_cv.json."""
    with open(MASTER_CV_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_adapted_cv(master_cv) -> dict:
    """Minimal adapted CV for testing docx generation and char limits."""
    return {
        "personal":   master_cv["personal"],
        "education":  master_cv["education"],
        "languages":  master_cv["languages"],
        "interests":  master_cv.get("interests", ""),
        "rodo_clause": master_cv.get("rodo_clause", ""),
        "summary": "Doświadczony lider sprzedaży z wieloletnim doświadczeniem w sprzedaży B2B SaaS. "
                   "Specjalizuję się w zarządzaniu pipeline'em, negocjacjach i budowaniu relacji z klientami.",
        "competencies": [
            "Sprzedaż B2B", "Negocjacje", "Pipeline management", "CRM", "SaaS", "GTM strategy"
        ],
        "experience": [
            {
                "title": "Head of Sales",
                "dates": "2022 – nadal",
                "bullets": [
                    "Zarządzanie procesem sprzedaży end-to-end w segmencie enterprise.",
                    "Budowanie i coaching zespołu SDR oraz AE.",
                ],
            }
        ],
        "ats_keywords": ["sprzedaż B2B", "SaaS", "negocjacje"],
        "match_score": 80,
        "match_notes": "Dobre dopasowanie do roli komercyjnej.",
        "covered_requirements": [],
        "gaps": [],
        "ats_report": {"used": [], "not_used": []},
        "company": "Testowa Firma",
        "job_title": "Sales Director",
    }


# ── Test: master_cv.json structure ───────────────────────────────────

class TestMasterCV:
    def test_file_exists(self):
        assert MASTER_CV_PATH.exists(), "data/master_cv.json musi istnieć"

    def test_candidate_name(self, master_cv):
        assert master_cv["personal"]["name"] == "Tomasz Uściński", \
            "Imię kandydata musi być 'Tomasz Uściński'"

    def test_required_keys(self, master_cv):
        required = {"personal", "summary", "competencies", "education", "languages", "experience"}
        missing = required - set(master_cv.keys())
        assert not missing, f"Brakujące klucze w master_cv.json: {missing}"

    def test_personal_fields(self, master_cv):
        p = master_cv["personal"]
        assert "name" in p
        assert "email" in p
        assert "phone" in p

    def test_experience_is_list(self, master_cv):
        assert isinstance(master_cv["experience"], list)
        assert len(master_cv["experience"]) >= 1

    def test_no_other_candidate_name(self, master_cv):
        """Ensure Anna Jakubowska's data is not present in this instance."""
        raw = json.dumps(master_cv)
        assert "Anna Jakubowska" not in raw, \
            "master_cv.json nie może zawierać danych Anny Jakubowskiej"


# ── Test: character limits ────────────────────────────────────────────

class TestCharLimits:
    def test_summary_limit(self, sample_adapted_cv):
        from src.cv_adapter import CHAR_LIMITS
        summary = sample_adapted_cv["summary"]
        assert len(summary) <= CHAR_LIMITS["summary"], \
            f"Podsumowanie ({len(summary)} znaków) przekracza limit {CHAR_LIMITS['summary']}"

    def test_competencies_combined_limit(self, sample_adapted_cv):
        from src.cv_adapter import CHAR_LIMITS
        combined = "  •  ".join(sample_adapted_cv["competencies"])
        assert len(combined) <= CHAR_LIMITS["competencies"], \
            f"Kompetencje łącznie ({len(combined)} znaków) przekraczają limit {CHAR_LIMITS['competencies']}"

    def test_bullet_limit(self, sample_adapted_cv):
        from src.cv_adapter import CHAR_LIMITS
        for job in sample_adapted_cv["experience"]:
            for bullet in job.get("bullets", []):
                assert len(bullet) <= CHAR_LIMITS["bullet"], \
                    f"Bullet '{bullet[:40]}...' ({len(bullet)} znaków) przekracza limit {CHAR_LIMITS['bullet']}"


# ── Test: DOCX generation ─────────────────────────────────────────────

class TestDocxGeneration:
    def test_generates_docx_file(self, sample_adapted_cv):
        from src.docx_generator import generate_cv_docx
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "Tomasz_Uscinski_test.docx"
            result = generate_cv_docx(sample_adapted_cv, output)
            assert result.exists(), "Plik .docx musi zostać zapisany"
            assert result.stat().st_size > 5000, "Plik .docx jest podejrzanie mały"

    def test_docx_filename_contains_candidate(self):
        from main import _make_filename
        filename = _make_filename("TestFirma")
        assert "Tomasz_Uscinski" in filename, \
            f"Nazwa pliku '{filename}' musi zawierać 'Tomasz_Uscinski'"

    def test_docx_filename_format(self):
        from main import _make_filename
        filename = _make_filename("Acme Corp")
        assert filename.endswith(".docx")
        assert "Tomasz_Uscinski" in filename

    def test_docx_contains_candidate_name(self, sample_adapted_cv):
        """DOCX content must reference Tomasz Uściński, not another candidate."""
        from src.docx_generator import generate_cv_docx
        from docx import Document
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.docx"
            generate_cv_docx(sample_adapted_cv, output)
            doc = Document(str(output))
            full_text = " ".join(p.text for p in doc.paragraphs).upper()
            assert "TOMASZ" in full_text or "UŚCIŃSKI" in full_text, \
                "Dokument DOCX musi zawierać imię i nazwisko Tomasza Uścińskiego"
            assert "ANNA JAKUBOWSKA" not in full_text, \
                "Dokument DOCX nie może zawierać danych Anny Jakubowskiej"


# ── Test: no hallucination beyond base profile ────────────────────────

class TestNoHallucination:
    """
    Unit-level guardrails — verifies that cv_adapter does not silently
    merge adapted content from a different candidate into the locked fields.
    """

    def test_merge_experience_preserves_title_and_dates(self):
        from src.cv_adapter import _merge_experience
        master_exp = [{"title": "Head of Sales", "dates": "2022 – nadal", "bullets": ["oryginał"]}]
        adapted_exp = [{"title": "Head of Sales", "dates": "ZMIENIONE", "bullets": ["nowe"]}]
        merged = _merge_experience(master_exp, adapted_exp)
        assert merged[0]["title"] == "Head of Sales"
        assert merged[0]["dates"] == "2022 – nadal", \
            "Daty muszą być zablokowane — tylko z matki"
        assert merged[0]["bullets"] == ["nowe"], \
            "Bullets mogą być zastąpione przez LLM"

    def test_adapt_cv_preserves_personal(self, master_cv):
        """adapt_cv must always copy personal data from master_cv, not invent it."""
        from src.cv_adapter import adapt_cv
        # Build minimal adapted result manually to test result assembly
        import unittest.mock as mock
        fake_adapted = {
            "summary": "Krótkie podsumowanie.",
            "competencies": ["Sprzedaż"],
            "experience": [],
            "ats_keywords": [],
            "match_score": 50,
            "match_notes": "",
            "covered_requirements": [],
            "gaps": [],
            "ats_report": {"used": [], "not_used": []},
            "company": "",
            "job_title": "",
        }
        with mock.patch("src.cv_adapter.chat") as mock_chat:
            mock_resp = mock.MagicMock()
            mock_resp.choices[0].message.content = json.dumps(fake_adapted)
            mock_chat.return_value = mock_resp
            result = adapt_cv("Sample job posting text for testing purposes.", master_cv=master_cv)

        assert result["personal"]["name"] == "Tomasz Uściński"
        assert result["personal"]["email"] == master_cv["personal"]["email"]


# ── Test: history module ──────────────────────────────────────────────

class TestHistory:
    def test_add_and_retrieve_entry(self, tmp_path, monkeypatch):
        from src import history
        fake_path = tmp_path / "history.json"
        monkeypatch.setattr(history, "HISTORY_PATH", fake_path)

        entry_id = history.add_entry(
            company="Testowa Firma",
            job_title="Sales Director",
            match_score=82,
            filename="Tomasz_Uscinski_TestowaFirma_2026.04.28.docx",
            job_url="https://example.com/job/123",
            job_text_preview="Poszukujemy doświadczonego lidera sprzedaży...",
            ats_keywords_count=5,
        )
        entries = history.get_all()
        assert len(entries) == 1
        assert entries[0]["company"] == "Testowa Firma"
        assert entries[0]["match_score"] == 82
        assert "Tomasz_Uscinski" in entries[0]["filename"]

    def test_delete_entry(self, tmp_path, monkeypatch):
        from src import history
        fake_path = tmp_path / "history.json"
        monkeypatch.setattr(history, "HISTORY_PATH", fake_path)

        entry_id = history.add_entry(
            company="Firma X", job_title="AE", match_score=60,
            filename="Tomasz_Uscinski_FirmaX_2026.04.28.docx",
        )
        assert history.delete_entry(entry_id) is True
        assert history.get_all() == []
