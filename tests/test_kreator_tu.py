"""
Tests for Kreator CV — Tomasz Uściński instance.

Tests cover:
- Character limits on generated CV sections
- DOCX generation and placeholder integrity
- No hallucination beyond base profile
- Filename generation
- History storage
- Language detection and CV output language handling
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
        "job_language": "pl",
        "cv_output_language": "pl",
        "language_confidence": "high",
        "role_type": "sales_leadership",
        "role_type_confidence": "high",
        "role_type_reasoning": "Stanowisko Head of Sales z odpowiedzialnością za zespół.",
        "cv_emphasis": ["leadership", "team management", "revenue growth"],
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
            "job_language": "pl",
            "cv_output_language": "pl",
            "language_confidence": "high",
            "role_type": "individual_contributor",
            "role_type_confidence": "high",
            "role_type_reasoning": "Samodzielna rola sprzedażowa.",
            "cv_emphasis": ["business development"],
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


# ── Test: language detection ──────────────────────────────────────────

class TestLanguageDetection:
    """Tests for LLM-based language detection in adapt_cv and validate helpers."""

    def _mock_adapt(self, master_cv, fake_adapted: dict):
        """Helper: run adapt_cv with a mocked LLM response."""
        import unittest.mock as mock
        from src.cv_adapter import adapt_cv
        with mock.patch("src.cv_adapter.chat") as mock_chat:
            mock_resp = mock.MagicMock()
            mock_resp.choices[0].message.content = json.dumps(fake_adapted)
            mock_chat.return_value = mock_resp
            return adapt_cv("Sample job posting.", master_cv=master_cv)

    def test_polish_posting_returns_pl(self, master_cv):
        """Polish job posting: job_language=pl, cv_output_language=pl."""
        fake = {
            "job_language": "pl",
            "cv_output_language": "pl",
            "language_confidence": "high",
            "summary": "Podsumowanie po polsku.",
            "competencies": ["Sprzedaż B2B"],
            "experience": [],
            "ats_keywords": [],
            "match_score": 70,
            "match_notes": "",
            "covered_requirements": [],
            "gaps": [],
            "ats_report": {"used": [], "not_used": []},
            "company": "Firma PL",
            "job_title": "Dyrektor Sprzedaży",
        }
        result = self._mock_adapt(master_cv, fake)
        assert result["job_language"] == "pl"
        assert result["cv_output_language"] == "pl"
        assert result["language_confidence"] == "high"

    def test_english_posting_returns_en(self, master_cv):
        """English job posting: job_language=en, cv_output_language=en-US."""
        fake = {
            "job_language": "en",
            "cv_output_language": "en-US",
            "language_confidence": "high",
            "summary": "Experienced sales leader with 15+ years in B2B SaaS.",
            "competencies": ["B2B Sales", "Revenue Growth"],
            "experience": [],
            "ats_keywords": ["sales", "SaaS"],
            "match_score": 78,
            "match_notes": "Good match for this commercial role.",
            "covered_requirements": [],
            "gaps": [],
            "ats_report": {"used": [], "not_used": []},
            "company": "Acme Corp",
            "job_title": "Head of Sales",
        }
        result = self._mock_adapt(master_cv, fake)
        assert result["job_language"] == "en"
        assert result["cv_output_language"] == "en-US"
        assert result["language_confidence"] == "high"

    def test_fallback_when_language_fields_missing(self, master_cv):
        """If LLM omits language fields, defaults apply: unknown/pl/low."""
        fake = {
            # No language fields
            "summary": "Fallback podsumowanie.",
            "competencies": ["Sprzedaż"],
            "experience": [],
            "ats_keywords": [],
            "match_score": 40,
            "match_notes": "",
            "covered_requirements": [],
            "gaps": [],
            "ats_report": {"used": [], "not_used": []},
            "company": "",
            "job_title": "",
        }
        result = self._mock_adapt(master_cv, fake)
        assert result["job_language"] == "unknown"
        assert result["cv_output_language"] == "pl"
        assert result["language_confidence"] == "low"

    def test_invalid_language_values_normalised(self, master_cv):
        """Invalid LLM values are sanitised to safe defaults."""
        fake = {
            "job_language": "de",        # invalid
            "cv_output_language": "fr",  # invalid
            "language_confidence": "very_high",  # invalid
            "summary": "Summary.",
            "competencies": ["Sales"],
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
        result = self._mock_adapt(master_cv, fake)
        assert result["job_language"] == "unknown"
        assert result["cv_output_language"] == "pl"
        assert result["language_confidence"] == "low"

    def test_validate_language_fields_helper(self):
        """Unit test for _validate_language_fields() directly."""
        from src.cv_adapter import _validate_language_fields

        # Valid Polish
        assert _validate_language_fields({"job_language": "pl", "cv_output_language": "pl", "language_confidence": "high"}) == ("pl", "pl", "high")
        # Valid English
        assert _validate_language_fields({"job_language": "en", "cv_output_language": "en-US", "language_confidence": "medium"}) == ("en", "en-US", "medium")
        # Unknown forces pl output
        assert _validate_language_fields({"job_language": "unknown", "cv_output_language": "en-US", "language_confidence": "low"}) == ("unknown", "pl", "low")
        # Missing all → defaults
        assert _validate_language_fields({}) == ("unknown", "pl", "low")
        # Invalid values → defaults
        assert _validate_language_fields({"job_language": "zh", "cv_output_language": "de", "language_confidence": "extreme"}) == ("unknown", "pl", "low")

    def test_revise_full_cv_preserves_language(self, master_cv):
        """revise_full_cv must keep cv_output_language from current_cv."""
        import unittest.mock as mock
        from src.cv_adapter import revise_full_cv

        current_cv = {
            "summary": "Experienced leader.",
            "competencies": ["B2B Sales"],
            "experience": [{"title": "Head of Sales", "dates": "2022 – present", "bullets": ["Led sales team."]}],
            "personal": master_cv["personal"],
            "education": master_cv["education"],
            "languages": master_cv["languages"],
            "interests": "",
            "rodo_clause": "",
            "job_language": "en",
            "cv_output_language": "en-US",
            "language_confidence": "high",
        }
        revised_response = {
            "summary": "Dynamic sales leader with proven track record.",
            "competencies": ["Enterprise Sales"],
            "experience": [{"title": "Head of Sales", "dates": "2022 – present", "bullets": ["Scaled revenue 2x."]}],
        }
        with mock.patch("src.cv_adapter.chat") as mock_chat:
            mock_resp = mock.MagicMock()
            mock_resp.choices[0].message.content = json.dumps(revised_response)
            mock_chat.return_value = mock_resp
            result = revise_full_cv(current_cv, "Make it more concise.", "English job posting.")

        assert result["cv_output_language"] == "en-US", \
            "revise_full_cv must preserve cv_output_language from current_cv"
        assert result["job_language"] == "en"
        assert result["language_confidence"] == "high"


# ── Test: role type detection ─────────────────────────────────────────

class TestRoleTypeDetection:
    """Tests for LLM-based role type detection in adapt_cv."""

    def _mock_adapt(self, master_cv, fake_adapted: dict):
        """Helper: run adapt_cv with a mocked LLM response."""
        import unittest.mock as mock
        from src.cv_adapter import adapt_cv
        with mock.patch("src.cv_adapter.chat") as mock_chat:
            mock_resp = mock.MagicMock()
            mock_resp.choices[0].message.content = json.dumps(fake_adapted)
            mock_chat.return_value = mock_resp
            return adapt_cv("Sample job posting.", master_cv=master_cv)

    def _base_fake(self, **overrides) -> dict:
        """Minimal valid LLM response with sensible defaults."""
        base = {
            "job_language": "pl",
            "cv_output_language": "pl",
            "language_confidence": "high",
            "summary": "Podsumowanie.",
            "competencies": ["Sprzedaż B2B"],
            "experience": [],
            "ats_keywords": [],
            "match_score": 70,
            "match_notes": "",
            "covered_requirements": [],
            "gaps": [],
            "ats_report": {"used": [], "not_used": []},
            "company": "Firma",
            "job_title": "Test",
        }
        base.update(overrides)
        return base

    def test_individual_contributor_posting(self, master_cv):
        """Business Development Manager posting → role_type=individual_contributor."""
        fake = self._base_fake(
            role_type="individual_contributor",
            role_type_confidence="high",
            role_type_reasoning="Samodzielna rola hunterska bez zarządzania zespołem.",
            cv_emphasis=["business development", "client acquisition", "outbound"],
            job_title="Business Development Manager",
        )
        result = self._mock_adapt(master_cv, fake)
        assert result["role_type"] == "individual_contributor"
        assert result["role_type_confidence"] == "high"
        assert "business development" in result["cv_emphasis"]

    def test_sales_leadership_posting(self, master_cv):
        """Head of Sales posting → role_type=sales_leadership."""
        fake = self._base_fake(
            role_type="sales_leadership",
            role_type_confidence="high",
            role_type_reasoning="Rola kierownicza z odpowiedzialnością za zespół i strategię.",
            cv_emphasis=["leadership", "team management", "revenue growth", "sales strategy"],
            job_title="Head of Sales",
        )
        result = self._mock_adapt(master_cv, fake)
        assert result["role_type"] == "sales_leadership"
        assert result["role_type_confidence"] == "high"
        assert "leadership" in result["cv_emphasis"]

    def test_mixed_role_posting(self, master_cv):
        """Mixed role posting → role_type=mixed."""
        fake = self._base_fake(
            role_type="mixed",
            role_type_confidence="medium",
            role_type_reasoning="Rola łączy własną sprzedaż z budową zespołu.",
            cv_emphasis=["business development", "leadership", "client acquisition"],
            job_title="Commercial Director",
        )
        result = self._mock_adapt(master_cv, fake)
        assert result["role_type"] == "mixed"
        assert result["role_type_confidence"] == "medium"

    def test_fallback_when_role_fields_missing(self, master_cv):
        """If LLM omits role_type fields, defaults apply: unknown/low/''/'[]'."""
        fake = self._base_fake()  # no role fields
        result = self._mock_adapt(master_cv, fake)
        assert result["role_type"] == "unknown"
        assert result["role_type_confidence"] == "low"
        assert result["role_type_reasoning"] == ""
        assert result["cv_emphasis"] == []

    def test_invalid_role_type_normalised(self, master_cv):
        """Invalid role_type value is normalised to 'unknown'."""
        fake = self._base_fake(
            role_type="director",           # invalid
            role_type_confidence="extreme", # invalid
            cv_emphasis="not_a_list",       # invalid
        )
        result = self._mock_adapt(master_cv, fake)
        assert result["role_type"] == "unknown"
        assert result["role_type_confidence"] == "low"
        assert result["cv_emphasis"] == []

    def test_validate_role_fields_helper(self):
        """Unit test for _validate_role_fields() directly."""
        from src.cv_adapter import _validate_role_fields

        # Valid individual_contributor
        rt, rc, rr, ce = _validate_role_fields({
            "role_type": "individual_contributor",
            "role_type_confidence": "high",
            "role_type_reasoning": "Samodzielna rola.",
            "cv_emphasis": ["business development"],
        })
        assert rt == "individual_contributor"
        assert rc == "high"
        assert rr == "Samodzielna rola."
        assert ce == ["business development"]

        # Valid sales_leadership
        rt, rc, rr, ce = _validate_role_fields({
            "role_type": "sales_leadership",
            "role_type_confidence": "medium",
            "role_type_reasoning": "Zarządzanie zespołem.",
            "cv_emphasis": ["leadership"],
        })
        assert rt == "sales_leadership"

        # Missing all → defaults
        rt, rc, rr, ce = _validate_role_fields({})
        assert rt == "unknown"
        assert rc == "low"
        assert rr == ""
        assert ce == []

        # Invalid values → defaults
        rt, rc, rr, ce = _validate_role_fields({
            "role_type": "ceo", "role_type_confidence": "ultra", "cv_emphasis": 42
        })
        assert rt == "unknown"
        assert rc == "low"
        assert ce == []

    def test_revise_full_cv_preserves_role_type(self, master_cv):
        """revise_full_cv must preserve role_type, cv_emphasis from current_cv."""
        import unittest.mock as mock
        from src.cv_adapter import revise_full_cv

        current_cv = {
            "summary": "Experienced sales leader.",
            "competencies": ["B2B Sales"],
            "experience": [{"title": "Head of Sales", "dates": "2022 – present", "bullets": ["Led team."]}],
            "personal": master_cv["personal"],
            "education": master_cv["education"],
            "languages": master_cv["languages"],
            "interests": "",
            "rodo_clause": "",
            "job_language": "pl",
            "cv_output_language": "pl",
            "language_confidence": "high",
            "role_type": "sales_leadership",
            "role_type_confidence": "high",
            "role_type_reasoning": "Rola kierownicza.",
            "cv_emphasis": ["leadership", "team management"],
        }
        revised_response = {
            "summary": "Doświadczony lider sprzedaży.",
            "competencies": ["Strategia sprzedaży"],
            "experience": [{"title": "Head of Sales", "dates": "2022 – present", "bullets": ["Skalował przychody 2x."]}],
        }
        with mock.patch("src.cv_adapter.chat") as mock_chat:
            mock_resp = mock.MagicMock()
            mock_resp.choices[0].message.content = json.dumps(revised_response)
            mock_chat.return_value = mock_resp
            result = revise_full_cv(current_cv, "Skróć podsumowanie.", "Polskie ogłoszenie.")

        assert result["role_type"] == "sales_leadership", \
            "revise_full_cv musi zachować role_type z current_cv"
        assert result["cv_emphasis"] == ["leadership", "team management"]
        assert result["role_type_reasoning"] == "Rola kierownicza."
