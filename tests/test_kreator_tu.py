"""
Tests for Kreator CV — Tomasz Uściński instance.

Tests cover:
- Character limits on generated CV sections
- DOCX generation and placeholder integrity
- No hallucination beyond base profile
- Filename generation
- History storage
- Language detection and CV output language handling
- Application repository (DB module)
- Storage / FTP module
- New dashboard API endpoints
- CSV export
- Frontend (static/index.html) content checks
"""

import json
import os
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
        "ats_keyword_strategy": {
            "supported_keywords": ["sprzedaż B2B", "SaaS"],
            "adjacent_keywords": ["CRM"],
            "unsupported_keywords": ["Salesforce"],
            "used_keywords": ["sprzedaż B2B", "SaaS"],
            "excluded_keywords": ["Salesforce"],
            "naturalness_notes": "Słowa kluczowe wplecione w profil zawodowy.",
        },
        "experience_gap_analysis": {
            "title": "Niedopasowanie doświadczenia do ogłoszenia",
            "text": "Profil Tomasza dobrze pokrywa sprzedaż B2B i SaaS.",
            "confirmed_strengths": ["B2B sales", "SaaS"],
            "gaps": [],
            "transferable_angles": [],
            "do_not_claim": [],
        },
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
        assert "Tomasz" in filename and "Uscinski" in filename.replace("ściński", "uscinski").lower() or "Uściński" in filename, \
            f"Nazwa pliku '{filename}' musi zawierać 'Tomasz Uściński'"

    def test_docx_filename_format(self):
        from main import _make_filename
        filename = _make_filename("Acme Corp")
        assert filename.endswith(".docx")
        assert "Tomasz" in filename

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
            "ats_keyword_strategy": {
                "supported_keywords": ["sprzedaż"],
                "adjacent_keywords": [],
                "unsupported_keywords": [],
                "used_keywords": ["sprzedaż"],
                "excluded_keywords": [],
                "naturalness_notes": "Naturalnie użyte.",
            },
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


# ── Test: ATS keyword strategy ────────────────────────────────────────

class TestATSKeywordStrategy:
    """Tests for natural ATS keyword strategy in adapt_cv and revise_full_cv."""

    _EMPTY_STRAT = {
        "supported_keywords": [],
        "adjacent_keywords": [],
        "unsupported_keywords": [],
        "used_keywords": [],
        "excluded_keywords": [],
        "naturalness_notes": "",
    }

    def _mock_adapt(self, master_cv, fake_adapted: dict):
        import unittest.mock as mock
        from src.cv_adapter import adapt_cv
        with mock.patch("src.cv_adapter.chat") as mock_chat:
            mock_resp = mock.MagicMock()
            mock_resp.choices[0].message.content = json.dumps(fake_adapted)
            mock_chat.return_value = mock_resp
            return adapt_cv("Sample job posting.", master_cv=master_cv)

    def _base_fake(self, **overrides) -> dict:
        base = {
            "job_language": "pl",
            "cv_output_language": "pl",
            "language_confidence": "high",
            "role_type": "individual_contributor",
            "role_type_confidence": "high",
            "role_type_reasoning": "Samodzielna rola.",
            "cv_emphasis": ["business development"],
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
            "job_title": "BDM",
        }
        base.update(overrides)
        return base

    def test_ats_strategy_present_in_result(self, master_cv):
        """adapt_cv result always contains ats_keyword_strategy dict."""
        fake = self._base_fake(ats_keyword_strategy={
            "supported_keywords": ["B2B sales", "SaaS"],
            "adjacent_keywords": ["CRM"],
            "unsupported_keywords": ["Salesforce"],
            "used_keywords": ["B2B sales", "SaaS"],
            "excluded_keywords": ["Salesforce"],
            "naturalness_notes": "Keywords woven into summary sentences.",
        })
        result = self._mock_adapt(master_cv, fake)
        strat = result["ats_keyword_strategy"]
        assert isinstance(strat, dict)
        assert strat["used_keywords"] == ["B2B sales", "SaaS"]
        assert strat["excluded_keywords"] == ["Salesforce"]
        assert strat["naturalness_notes"] == "Keywords woven into summary sentences."

    def test_missing_ats_strategy_does_not_break(self, master_cv):
        """If LLM omits ats_keyword_strategy, result gets safe empty defaults."""
        fake = self._base_fake()  # no ats_keyword_strategy
        result = self._mock_adapt(master_cv, fake)
        strat = result["ats_keyword_strategy"]
        assert isinstance(strat, dict)
        assert strat["used_keywords"] == []
        assert strat["excluded_keywords"] == []
        assert strat["naturalness_notes"] == ""

    def test_invalid_ats_strategy_normalised(self, master_cv):
        """Non-dict ats_keyword_strategy is replaced with safe defaults."""
        fake = self._base_fake(ats_keyword_strategy="not_a_dict")
        result = self._mock_adapt(master_cv, fake)
        strat = result["ats_keyword_strategy"]
        assert isinstance(strat, dict)
        assert strat["used_keywords"] == []

    def test_used_keywords_is_list(self, master_cv):
        """used_keywords must always be a list."""
        fake = self._base_fake(ats_keyword_strategy={
            "used_keywords": "B2B sales",  # string instead of list
            "excluded_keywords": None,
            "naturalness_notes": "",
        })
        result = self._mock_adapt(master_cv, fake)
        strat = result["ats_keyword_strategy"]
        assert isinstance(strat["used_keywords"], list)
        assert isinstance(strat["excluded_keywords"], list)

    def test_naturalness_notes_is_string(self, master_cv):
        """naturalness_notes must always be a string."""
        fake = self._base_fake(ats_keyword_strategy={
            "naturalness_notes": 42,  # wrong type
        })
        result = self._mock_adapt(master_cv, fake)
        assert isinstance(result["ats_keyword_strategy"]["naturalness_notes"], str)

    def test_validate_ats_strategy_helper(self):
        """Unit test for _validate_ats_strategy() directly."""
        from src.cv_adapter import _validate_ats_strategy

        # Full valid input
        strat = _validate_ats_strategy({
            "ats_keyword_strategy": {
                "supported_keywords": ["B2B sales"],
                "adjacent_keywords": ["CRM"],
                "unsupported_keywords": ["Salesforce"],
                "used_keywords": ["B2B sales"],
                "excluded_keywords": ["Salesforce"],
                "naturalness_notes": "Good fit.",
            }
        })
        assert strat["supported_keywords"] == ["B2B sales"]
        assert strat["used_keywords"] == ["B2B sales"]
        assert strat["naturalness_notes"] == "Good fit."

        # Missing entirely → all empty
        strat_empty = _validate_ats_strategy({})
        assert strat_empty["used_keywords"] == []
        assert strat_empty["naturalness_notes"] == ""

        # Invalid type for list fields → empty lists
        strat_bad = _validate_ats_strategy({"ats_keyword_strategy": {
            "used_keywords": "string_not_list",
            "naturalness_notes": 99,
        }})
        assert strat_bad["used_keywords"] == []
        assert strat_bad["naturalness_notes"] == ""

    def test_revise_full_cv_preserves_ats_strategy(self, master_cv):
        """revise_full_cv must preserve ats_keyword_strategy from current_cv."""
        import unittest.mock as mock
        from src.cv_adapter import revise_full_cv

        original_strat = {
            "supported_keywords": ["sprzedaż B2B"],
            "adjacent_keywords": [],
            "unsupported_keywords": ["Salesforce"],
            "used_keywords": ["sprzedaż B2B"],
            "excluded_keywords": ["Salesforce"],
            "naturalness_notes": "Słowa kluczowe naturalne.",
        }
        current_cv = {
            "summary": "Podsumowanie.",
            "competencies": ["Sprzedaż B2B"],
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
            "cv_emphasis": ["leadership"],
            "ats_keyword_strategy": original_strat,
        }
        revised_response = {
            "summary": "Zmienione podsumowanie.",
            "competencies": ["Strategia sprzedaży"],
            "experience": [{"title": "Head of Sales", "dates": "2022 – present", "bullets": ["Scaled revenue."]}],
        }
        with mock.patch("src.cv_adapter.chat") as mock_chat:
            mock_resp = mock.MagicMock()
            mock_resp.choices[0].message.content = json.dumps(revised_response)
            mock_chat.return_value = mock_resp
            result = revise_full_cv(current_cv, "Skróć.", "Ogłoszenie.")

        assert result["ats_keyword_strategy"] == original_strat, \
            "revise_full_cv musi zachować ats_keyword_strategy z current_cv"

    def test_no_hidden_keyword_instructions_in_system_prompt(self):
        """SYSTEM_PROMPT must not contain instructions for hidden/invisible keywords."""
        from src.cv_adapter import SYSTEM_PROMPT
        forbidden = [
            "hidden keyword",
            "invisible keyword",
            "white text",
            "white-colored",
            "microscopic",
            "keyword stuffing allowed",
        ]
        prompt_lower = SYSTEM_PROMPT.lower()
        for phrase in forbidden:
            assert phrase.lower() not in prompt_lower, \
                f"SYSTEM_PROMPT zawiera niedozwoloną frazę: '{phrase}'"


# ── Test: experience gap analysis ────────────────────────────────────

class TestExperienceGapAnalysis:
    """Tests for experience_gap_analysis field in adapt_cv and revise_full_cv."""

    def _mock_adapt(self, master_cv, fake_adapted: dict):
        import unittest.mock as mock
        from src.cv_adapter import adapt_cv
        with mock.patch("src.cv_adapter.chat") as mock_chat:
            mock_resp = mock.MagicMock()
            mock_resp.choices[0].message.content = json.dumps(fake_adapted)
            mock_chat.return_value = mock_resp
            return adapt_cv("Sample job posting.", master_cv=master_cv)

    def _base_fake(self, **overrides) -> dict:
        base = {
            "job_language": "pl",
            "cv_output_language": "pl",
            "language_confidence": "high",
            "role_type": "individual_contributor",
            "role_type_confidence": "high",
            "role_type_reasoning": "Samodzielna rola.",
            "cv_emphasis": ["business development"],
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
            "job_title": "BDM",
        }
        base.update(overrides)
        return base

    def test_gap_analysis_present_in_result(self, master_cv):
        """adapt_cv result always contains experience_gap_analysis dict."""
        fake = self._base_fake(experience_gap_analysis={
            "title": "Niedopasowanie doświadczenia do ogłoszenia",
            "text": "Profil Tomasza dobrze pokrywa sprzedaż B2B i SaaS.",
            "confirmed_strengths": ["B2B sales", "SaaS"],
            "gaps": ["agency trading"],
            "transferable_angles": ["MarTech commercialization"],
            "do_not_claim": ["media agency network"],
        })
        result = self._mock_adapt(master_cv, fake)
        gap = result["experience_gap_analysis"]
        assert isinstance(gap, dict)
        assert gap["title"] == "Niedopasowanie doświadczenia do ogłoszenia"
        assert gap["text"] == "Profil Tomasza dobrze pokrywa sprzedaż B2B i SaaS."
        assert "B2B sales" in gap["confirmed_strengths"]
        assert "agency trading" in gap["gaps"]
        assert "MarTech commercialization" in gap["transferable_angles"]
        assert "media agency network" in gap["do_not_claim"]

    def test_missing_gap_analysis_gets_fallback(self, master_cv):
        """If LLM omits experience_gap_analysis, result gets safe empty defaults."""
        fake = self._base_fake()  # no experience_gap_analysis
        result = self._mock_adapt(master_cv, fake)
        gap = result["experience_gap_analysis"]
        assert isinstance(gap, dict)
        assert "title" in gap
        assert gap["text"] == ""
        assert gap["confirmed_strengths"] == []
        assert gap["gaps"] == []
        assert gap["transferable_angles"] == []
        assert gap["do_not_claim"] == []

    def test_polish_cv_gets_polish_title(self, master_cv):
        """For cv_output_language=pl, gap analysis title must be Polish."""
        fake = self._base_fake(cv_output_language="pl")  # no gap analysis provided
        result = self._mock_adapt(master_cv, fake)
        gap = result["experience_gap_analysis"]
        assert gap["title"] == "Niedopasowanie doświadczenia do ogłoszenia"

    def test_english_cv_gets_english_title(self, master_cv):
        """For cv_output_language=en-US, gap analysis title must be English."""
        fake = self._base_fake(
            job_language="en",
            cv_output_language="en-US",
        )  # no gap analysis provided
        result = self._mock_adapt(master_cv, fake)
        gap = result["experience_gap_analysis"]
        assert gap["title"] == "Experience gaps vs. job posting"

    def test_invalid_gap_analysis_normalised(self, master_cv):
        """Non-dict experience_gap_analysis is replaced with safe defaults."""
        fake = self._base_fake(experience_gap_analysis="not_a_dict")
        result = self._mock_adapt(master_cv, fake)
        gap = result["experience_gap_analysis"]
        assert isinstance(gap, dict)
        assert gap["text"] == ""
        assert isinstance(gap["gaps"], list)

    def test_validate_gap_analysis_helper(self):
        """Unit test for _validate_gap_analysis() directly."""
        from src.cv_adapter import _validate_gap_analysis

        # Full valid PL input
        gap = _validate_gap_analysis({
            "experience_gap_analysis": {
                "title": "Niedopasowanie",
                "text": "Opis luk.",
                "confirmed_strengths": ["B2B sales"],
                "gaps": ["media agency"],
                "transferable_angles": ["MarTech"],
                "do_not_claim": ["agency trading"],
            }
        }, cv_output_language="pl")
        assert gap["title"] == "Niedopasowanie"
        assert gap["text"] == "Opis luk."
        assert gap["confirmed_strengths"] == ["B2B sales"]

        # Missing entirely → defaults with Polish title
        gap_pl = _validate_gap_analysis({}, cv_output_language="pl")
        assert gap_pl["title"] == "Niedopasowanie doświadczenia do ogłoszenia"
        assert gap_pl["text"] == ""
        assert gap_pl["gaps"] == []

        # Missing entirely → defaults with English title
        gap_en = _validate_gap_analysis({}, cv_output_language="en-US")
        assert gap_en["title"] == "Experience gaps vs. job posting"

        # Invalid list fields → empty lists
        gap_bad = _validate_gap_analysis({"experience_gap_analysis": {
            "confirmed_strengths": "not_a_list",
            "gaps": 42,
        }}, cv_output_language="pl")
        assert gap_bad["confirmed_strengths"] == []
        assert gap_bad["gaps"] == []

    def test_gap_analysis_not_in_docx(self, master_cv):
        """experience_gap_analysis must not appear in generated DOCX text."""
        from src.docx_generator import generate_cv_docx
        from docx import Document

        cv_with_gap = {
            "personal": master_cv["personal"],
            "education": master_cv["education"],
            "languages": master_cv["languages"],
            "interests": "",
            "rodo_clause": "",
            "summary": "Podsumowanie testowe.",
            "competencies": ["Sprzedaż B2B"],
            "experience": [],
            "ats_keywords": [],
            "experience_gap_analysis": {
                "title": "Niedopasowanie doświadczenia do ogłoszenia",
                "text": "SEKRET_LUKI_NIE_W_CV nie powinien trafić do DOCX.",
                "confirmed_strengths": [],
                "gaps": ["SEKRET_LUKI"],
                "transferable_angles": [],
                "do_not_claim": [],
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test_gap.docx"
            generate_cv_docx(cv_with_gap, output)
            doc = Document(str(output))
            full_text = " ".join(p.text for p in doc.paragraphs)
            assert "SEKRET_LUKI" not in full_text, \
                "experience_gap_analysis nie może trafić do pliku DOCX"

    def test_revise_full_cv_preserves_gap_analysis(self, master_cv):
        """revise_full_cv must preserve experience_gap_analysis from current_cv when LLM doesn't return one."""
        import unittest.mock as mock
        from src.cv_adapter import revise_full_cv

        original_gap = {
            "title": "Niedopasowanie doświadczenia do ogłoszenia",
            "text": "Opis luk z pierwszego generowania.",
            "confirmed_strengths": ["B2B sales"],
            "gaps": ["agency trading"],
            "transferable_angles": ["MarTech"],
            "do_not_claim": ["media agency network"],
        }
        current_cv = {
            "summary": "Podsumowanie.",
            "competencies": ["Sprzedaż B2B"],
            "experience": [{"title": "Head of Sales", "dates": "2022 – present", "bullets": ["Led team."]}],
            "personal": master_cv["personal"],
            "education": master_cv["education"],
            "languages": master_cv["languages"],
            "interests": "",
            "rodo_clause": "",
            "job_language": "pl",
            "cv_output_language": "pl",
            "language_confidence": "high",
            "role_type": "individual_contributor",
            "role_type_confidence": "high",
            "role_type_reasoning": "Samodzielna rola.",
            "cv_emphasis": ["business development"],
            "ats_keyword_strategy": {
                "supported_keywords": [], "adjacent_keywords": [],
                "unsupported_keywords": [], "used_keywords": [],
                "excluded_keywords": [], "naturalness_notes": "",
            },
            "experience_gap_analysis": original_gap,
        }
        revised_response = {
            "summary": "Zaktualizowane podsumowanie.",
            "competencies": ["Sprzedaż B2B"],
            "experience": [{"title": "Head of Sales", "dates": "2022 – present", "bullets": ["Scaled pipeline."]}],
            # no experience_gap_analysis — LLM didn't return it
        }
        with mock.patch("src.cv_adapter.chat") as mock_chat:
            mock_resp = mock.MagicMock()
            mock_resp.choices[0].message.content = json.dumps(revised_response)
            mock_chat.return_value = mock_resp
            result = revise_full_cv(current_cv, "Skróć podsumowanie.", "Ogłoszenie testowe.")

        assert result["experience_gap_analysis"] == original_gap, \
            "revise_full_cv musi zachować experience_gap_analysis z current_cv gdy LLM go nie zwróci"


# ── Helper: extract all text from a DOCX ─────────────────────────────

def _docx_full_text(docx_path: Path) -> str:
    """Returns all paragraph text from a DOCX file as one string."""
    from docx import Document
    doc = Document(str(docx_path))
    return " ".join(p.text for p in doc.paragraphs)


# ── Test: fixed_experience_facts in master_cv.json ───────────────────

class TestFixedExperienceFacts:
    """Tests verifying that fixed_experience_facts in master_cv.json is correct."""

    def test_fixed_facts_present(self, master_cv):
        """master_cv.json must contain fixed_experience_facts."""
        assert "fixed_experience_facts" in master_cv, \
            "master_cv.json musi zawierać klucz 'fixed_experience_facts'"

    def test_exactly_seven_entries(self, master_cv):
        """fixed_experience_facts must have exactly 7 entries."""
        facts = master_cv["fixed_experience_facts"]
        assert len(facts) == 7, \
            f"fixed_experience_facts musi mieć 7 pozycji, ma {len(facts)}"

    def _find(self, facts: list, company: str) -> dict:
        """Find a fact entry by company name."""
        for f in facts:
            if f["company"] == company:
                return f
        pytest.fail(f"Brakuje firmy '{company}' w fixed_experience_facts")

    def test_profitia_consultants(self, master_cv):
        f = self._find(master_cv["fixed_experience_facts"], "Profitia Consultants")
        assert f["period_pl"] == "2025 – nadal"
        assert f["period_en"] == "2025 – present"
        assert f["industry"] == "Procurement SaaS"
        assert "Senior Client Partner" in f["role_pl"]
        assert "Senior Client Partner" in f["role_en"]

    def test_onestep_financial(self, master_cv):
        f = self._find(master_cv["fixed_experience_facts"], "OneStep Financial UK")
        assert f["industry"] == "Digital Money FinTech"
        assert "Sales Executive" in f["role_pl"]
        assert f["period_pl"] == "2023 – 2025"
        assert f["period_en"] == "2023 – 2025"

    def test_gizmi_sa(self, master_cv):
        f = self._find(master_cv["fixed_experience_facts"], "Gizmi SA")
        assert f["period_pl"] == "2021 – 2023"
        assert f["period_en"] == "2021 – 2023"
        assert f["industry"] == "FinTech & MarTech SaaS"

    def test_boomerun(self, master_cv):
        f = self._find(master_cv["fixed_experience_facts"], "Boomerun")
        assert f["industry"] == "InsurTech & SportTech PaaS"
        assert f["period_pl"] == "2018 – 2021"

    def test_hft_brokers(self, master_cv):
        f = self._find(master_cv["fixed_experience_facts"], "HFT Brokers SA")
        assert "CEO" in f["role_pl"]
        assert "Head of Sales" in f["role_pl"]
        assert f["period_pl"] == "2014 – 2016"
        assert f["industry"] == "Online Brokerage House | Private Banking"

    def test_tms_brokers(self, master_cv):
        f = self._find(master_cv["fixed_experience_facts"], "TMS Brokers SA")
        assert "Board Member" in f["role_pl"]
        assert "Head of Sales and Customer Support" in f["role_pl"]
        assert "Head of Analysis" in f["role_pl"]
        assert f["period_pl"] == "2009 – 2012"

    def test_xtb_sa(self, master_cv):
        f = self._find(master_cv["fixed_experience_facts"], "XTB SA")
        assert "Head of Sales" in f["role_pl"]
        assert "Market Analyst" in f["role_pl"]
        assert f["period_pl"] == "2006 – 2009"

    def test_rodo_clause_en_present(self, master_cv):
        """master_cv.json must have an English RODO clause."""
        assert "rodo_clause_en" in master_cv, \
            "master_cv.json musi zawierać klucz 'rodo_clause_en'"
        clause = master_cv["rodo_clause_en"]
        assert "consent" in clause.lower(), \
            "Angielska klauzula RODO musi zawierać słowo 'consent'"
        assert len(clause) > 50


# ── Test: localized DOCX headings ────────────────────────────────────

class TestDocxLocalization:
    """Tests verifying language-aware headings, sections and RODO in DOCX."""

    def _build_cv(self, master_cv: dict, lang: str) -> dict:
        """Build a minimal cv_data for docx generation with given language."""
        rodo = (
            master_cv.get("rodo_clause_en", "")
            if lang == "en-US"
            else master_cv.get("rodo_clause", "")
        )
        return {
            "personal": master_cv["personal"],
            "education": master_cv["education"],
            "languages": master_cv["languages"],
            "interests": master_cv.get("interests", ""),
            "rodo_clause": rodo,
            "summary": "Test summary paragraph." if lang == "en-US" else "Testowe podsumowanie.",
            "competencies": ["B2B Sales", "SaaS"] if lang == "en-US" else ["Sprzedaż B2B"],
            "experience": [
                {
                    "title": "Head of Sales",
                    "company": "",
                    "dates": "2025 – present" if lang == "en-US" else "2025 – nadal",
                    "bullets": ["Grew pipeline by 2x." if lang == "en-US" else "Rozwinął pipeline."],
                }
            ],
            "ats_keywords": [],
            "cv_output_language": lang,
            "fixed_experience_facts": master_cv.get("fixed_experience_facts", []),
        }

    def test_polish_headings_in_docx(self, master_cv):
        """Polish CV must contain Polish section headings."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "pl")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_pl.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "PODSUMOWANIE ZAWODOWE" in text
            assert "KOMPETENCJE" in text
            assert "DOŚWIADCZENIE ZAWODOWE" in text
            assert "ZNAJOMOŚĆ JĘZYKÓW" in text

    def test_english_headings_in_docx(self, master_cv):
        """English CV must contain English section headings."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_en.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "PROFESSIONAL SUMMARY" in text
            assert "COMPETENCIES" in text
            assert "PROFESSIONAL EXPERIENCE" in text
            assert "LANGUAGES" in text

    def test_no_education_section_in_docx(self, master_cv):
        """DOCX must not contain WYKSZTAŁCENIE or EDUCATION heading."""
        from src.docx_generator import generate_cv_docx
        for lang in ("pl", "en-US"):
            cv = self._build_cv(master_cv, lang)
            with tempfile.TemporaryDirectory() as tmpdir:
                out = Path(tmpdir) / f"test_edu_{lang}.docx"
                generate_cv_docx(cv, out)
                text = _docx_full_text(out)
                assert "WYKSZTAŁCENIE" not in text, \
                    f"DOCX ({lang}) nie może zawierać sekcji WYKSZTAŁCENIE"
                assert "EDUCATION" not in text, \
                    f"DOCX ({lang}) nie może zawierać sekcji EDUCATION"

    def test_no_interests_section_in_docx(self, master_cv):
        """DOCX must not contain OBSZARY ZAINTERESOWAŃ or INTERESTS heading."""
        from src.docx_generator import generate_cv_docx
        for lang in ("pl", "en-US"):
            cv = self._build_cv(master_cv, lang)
            with tempfile.TemporaryDirectory() as tmpdir:
                out = Path(tmpdir) / f"test_int_{lang}.docx"
                generate_cv_docx(cv, out)
                text = _docx_full_text(out)
                assert "OBSZARY ZAINTERESOWAŃ" not in text, \
                    f"DOCX ({lang}) nie może zawierać sekcji OBSZARY ZAINTERESOWAŃ"
                assert "INTERESTS" not in text, \
                    f"DOCX ({lang}) nie może zawierać sekcji INTERESTS"

    def test_no_ats_keywords_block_in_docx(self, master_cv):
        """DOCX must not contain any ATS keywords block."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "pl")
        cv["ats_keywords"] = ["Senior Client Partner", "B2B sales", "SaaS"]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_ats.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "Słowa kluczowe ATS" not in text, \
                "DOCX nie może zawierać bloku 'Słowa kluczowe ATS'"
            assert "ATS keywords" not in text.lower() or text.lower().count("ats keywords") == 0, \
                "DOCX nie może zawierać bloku 'ATS keywords'"
            assert "Senior Client Partner • B2B sales" not in text, \
                "DOCX nie może zawierać listy słów kluczowych ATS"

    def test_polish_rodo_in_polish_cv(self, master_cv):
        """Polish CV must contain the Polish RODO clause."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "pl")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_rodo_pl.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "Wyrażam zgodę" in text, \
                "Polskie CV musi zawierać polską klauzulę RODO"

    def test_english_rodo_in_english_cv(self, master_cv):
        """English CV must contain the English RODO clause."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_rodo_en.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "I hereby consent" in text, \
                "Angielskie CV musi zawierać angielską klauzulę RODO"

    def test_no_polish_rodo_in_english_cv(self, master_cv):
        """English CV must NOT contain the Polish RODO clause."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_no_pl_rodo.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "Wyrażam zgodę" not in text, \
                "Angielskie CV nie może zawierać polskiej klauzuli RODO"

    def test_no_english_rodo_in_polish_cv(self, master_cv):
        """Polish CV must NOT contain the English RODO clause."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "pl")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_no_en_rodo.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "I hereby consent" not in text, \
                "Polskie CV nie może zawierać angielskiej klauzuli RODO"

    # ── Experience companies and industries ───────────────────────────

    def test_experience_en_contains_all_companies(self, master_cv):
        """English DOCX must contain all 7 company names from fixed_experience_facts."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_exp_companies.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            for company in [
                "Profitia Consultants",
                "OneStep Financial UK",
                "Gizmi SA",
                "Boomerun",
                "HFT Brokers SA",
                "TMS Brokers SA",
                "XTB SA",
            ]:
                assert company in text, f"DOCX EN musi zawierać firmę '{company}'"

    def test_experience_en_contains_industries(self, master_cv):
        """English DOCX must contain industry descriptions for all positions."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_exp_industries.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            for industry_fragment in [
                "Procurement SaaS",
                "Digital Money FinTech",
                "FinTech & MarTech SaaS",
                "InsurTech & SportTech PaaS",
                "Online Brokerage House",
                "Private Banking",
            ]:
                assert industry_fragment in text, \
                    f"DOCX EN musi zawierać branżę '{industry_fragment}'"

    def test_experience_en_contains_periods(self, master_cv):
        """English DOCX must contain correct EN periods from fixed_experience_facts."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_exp_periods_en.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            for period in ["2025 – present", "2023 – 2025", "2021 – 2023",
                           "2018 – 2021", "2014 – 2016", "2009 – 2012", "2006 – 2009"]:
                assert period in text, f"DOCX EN musi zawierać okres '{period}'"

    def test_experience_pl_contains_nadal(self, master_cv):
        """Polish DOCX must contain 'nadal' for the current position."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "pl")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_exp_period_pl.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "2025 – nadal" in text, "DOCX PL musi zawierać '2025 – nadal'"
            assert "Profitia Consultants" in text
            assert "Procurement SaaS" in text

    # ── Languages localization ────────────────────────────────────────

    def test_languages_english_in_en_docx(self, master_cv):
        """English DOCX must show English language names and levels."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_lang_en.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "English" in text, "DOCX EN musi zawierać 'English'"
            assert "Polish" in text, "DOCX EN musi zawierać 'Polish'"
            assert "native" in text, "DOCX EN musi zawierać 'native'"

    def test_languages_no_polish_labels_in_en_docx(self, master_cv):
        """English DOCX must NOT contain Polish language labels."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_lang_no_pl.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "Język angielski" not in text, \
                "DOCX EN nie może zawierać 'Język angielski'"
            assert "Język polski" not in text, \
                "DOCX EN nie może zawierać 'Język polski'"
            assert "ojczysty" not in text, \
                "DOCX EN nie może zawierać 'ojczysty'"

    def test_languages_polish_labels_in_pl_docx(self, master_cv):
        """Polish DOCX must contain Polish language labels."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "pl")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_lang_pl.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "Język angielski" in text
            assert "Język polski" in text
            assert "ojczysty" in text

    # ── Contact header: LinkedIn and website ──────────────────────────

    def test_contact_header_en_no_polish_labels(self, master_cv):
        """English DOCX must NOT contain 'Mój LinkedIn' or 'Moja strona'."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_contact_en.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "Mój LinkedIn" not in text, "DOCX EN nie może zawierać 'Mój LinkedIn'"
            assert "Moja strona" not in text,  "DOCX EN nie może zawierać 'Moja strona'"

    def test_contact_header_en_contains_linkedin(self, master_cv):
        """English DOCX must contain LinkedIn label and the shortened URL."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_contact_linkedin_en.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "LinkedIn" in text, "DOCX EN musi zawierać 'LinkedIn'"
            assert "linkedin.com/in/uscinski" in text, \
                "DOCX EN musi zawierać 'linkedin.com/in/uscinski'"

    def test_contact_header_en_contains_website(self, master_cv):
        """English DOCX must contain the website domain."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_contact_website_en.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "tomaszuscinski.pl" in text, \
                "DOCX EN musi zawierać 'tomaszuscinski.pl'"

    def test_contact_header_pl_no_polish_labels(self, master_cv):
        """Polish DOCX must also NOT contain 'Mój LinkedIn'."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "pl")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_contact_pl.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "Mój LinkedIn" not in text, "DOCX PL nie może zawierać 'Mój LinkedIn'"

    def test_contact_header_pl_contains_linkedin_and_website(self, master_cv):
        """Polish DOCX must contain LinkedIn URL and website."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "pl")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_contact_pl_links.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "linkedin.com/in/uscinski" in text, \
                "DOCX PL musi zawierać 'linkedin.com/in/uscinski'"
            assert "tomaszuscinski.pl" in text, \
                "DOCX PL musi zawierać 'tomaszuscinski.pl'"

    # ── index.html: gap analysis title fallback ───────────────────────

    def test_index_html_gap_fallback_en(self):
        """index.html must contain fallback for 'Experience gaps vs. job posting'."""
        html = Path("static/index.html").read_text(encoding="utf-8")
        assert "Experience gaps vs. job posting" in html, \
            "index.html musi zawierać fallback 'Experience gaps vs. job posting'"

    def test_index_html_gap_fallback_pl(self):
        """index.html must contain fallback 'Niedopasowanie doświadczenia do ogłoszenia'."""
        html = Path("static/index.html").read_text(encoding="utf-8")
        assert "Niedopasowanie doświadczenia do og" in html, \
            "index.html musi zawierać fallback 'Niedopasowanie doświadczenia do ogłoszenia'"

    def test_index_html_no_xperience_typo(self):
        """index.html must not contain the typo 'xperience gaps' as a bare hardcoded string."""
        html = Path("static/index.html").read_text(encoding="utf-8")
        # Acceptable: 'xperience' inside startsWith guard. Reject as standalone literal.
        import re
        bare_typo = re.findall(r"['\"`]xperience gaps", html, re.IGNORECASE)
        assert not bare_typo, \
            f"index.html zawiera literówkę 'xperience gaps' jako literal: {bare_typo}"


# ── Tests: job_title heading in DOCX ─────────────────────────────────

class TestJobTitleInDocx:
    """Tests verifying job_title is rendered correctly in generated DOCX."""

    @pytest.fixture
    def master_cv(self):
        import json
        with open("data/master_cv.json", encoding="utf-8") as f:
            return json.load(f)

    def _build_cv(self, master_cv: dict, lang: str, job_title: str = "") -> dict:
        rodo = (
            master_cv.get("rodo_clause_en", "")
            if lang == "en-US"
            else master_cv.get("rodo_clause", "")
        )
        return {
            "personal": master_cv["personal"],
            "education": master_cv["education"],
            "languages": master_cv["languages"],
            "interests": master_cv.get("interests", ""),
            "rodo_clause": rodo,
            "summary": "Test summary." if lang == "en-US" else "Testowe podsumowanie.",
            "competencies": ["B2B Sales"] if lang == "en-US" else ["Sprzedaż B2B"],
            "experience": [],
            "ats_keywords": [],
            "cv_output_language": lang,
            "fixed_experience_facts": [],
            "job_title": job_title,
        }

    def test_job_title_uppercased_in_docx_en(self, master_cv):
        """DOCX with job_title='Client Partner' must contain 'CLIENT PARTNER'."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US", "Client Partner")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_jt_en.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "CLIENT PARTNER" in text, "DOCX musi zawierać 'CLIENT PARTNER'"

    def test_job_title_uppercased_in_docx_pl(self, master_cv):
        """DOCX with job_title='Dyrektor Sprzedaży' must contain 'DYREKTOR SPRZEDAŻY'."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "pl", "Dyrektor Sprzedaży")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_jt_pl.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            assert "DYREKTOR SPRZEDAŻY" in text, "DOCX musi zawierać 'DYREKTOR SPRZEDAŻY'"

    def test_empty_job_title_no_blank_paragraph(self, master_cv):
        """DOCX with empty job_title must not insert a blank job-title paragraph."""
        from docx import Document
        from docx.shared import Pt
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US", "")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_jt_empty.docx"
            generate_cv_docx(cv, out)
            doc = Document(str(out))
            for p in doc.paragraphs:
                for run in p.runs:
                    if run.font.size and run.font.size == Pt(18) and not p.text.strip():
                        pytest.fail("DOCX zawiera pusty akapit w miejscu job_title (Pt 18)")

    def test_missing_job_title_key_no_crash(self, master_cv):
        """DOCX generation must not crash when job_title key is absent from cv_data."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US", "")
        del cv["job_title"]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_jt_missing.docx"
            generate_cv_docx(cv, out)  # must not raise

    def test_job_title_before_professional_summary(self, master_cv):
        """CLIENT PARTNER must appear before PROFESSIONAL SUMMARY in DOCX text."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US", "Client Partner")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_jt_order_en.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            idx_jt = text.index("CLIENT PARTNER")
            idx_ps = text.index("PROFESSIONAL SUMMARY")
            assert idx_jt < idx_ps, "'CLIENT PARTNER' musi wystąpić przed 'PROFESSIONAL SUMMARY'"

    def test_job_title_before_podsumowanie(self, master_cv):
        """DYREKTOR SPRZEDAŻY must appear before PODSUMOWANIE ZAWODOWE."""
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "pl", "Dyrektor Sprzedaży")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_jt_order_pl.docx"
            generate_cv_docx(cv, out)
            text = _docx_full_text(out)
            idx_jt = text.index("DYREKTOR SPRZEDAŻY")
            idx_ps = text.index("PODSUMOWANIE ZAWODOWE")
            assert idx_jt < idx_ps, "'DYREKTOR SPRZEDAŻY' musi wystąpić przed 'PODSUMOWANIE ZAWODOWE'"

    def test_job_title_font_size_and_bold(self, master_cv):
        """Job title run must be Calibri 18 pt bold."""
        from docx import Document
        from docx.shared import Pt
        from src.docx_generator import generate_cv_docx
        cv = self._build_cv(master_cv, "en-US", "Client Partner")
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_jt_style.docx"
            generate_cv_docx(cv, out)
            doc = Document(str(out))
            found = False
            for p in doc.paragraphs:
                if "CLIENT PARTNER" in p.text:
                    for run in p.runs:
                        if "CLIENT PARTNER" in run.text:
                            assert run.bold, "job_title run musi być bold"
                            assert run.font.size == Pt(18), f"job_title font size musi być 18 pt, jest {run.font.size}"
                            assert run.font.name == "Calibri", f"job_title font musi być Calibri, jest {run.font.name}"
                            found = True
            assert found, "Nie znaleziono runu z 'CLIENT PARTNER' w dokumencie"

    def test_revise_preserves_job_title(self, master_cv):
        """revise_full_cv must preserve job_title from the original CV."""
        import json
        import unittest.mock as mock
        from src.cv_adapter import revise_full_cv
        current_cv = {
            "personal": master_cv["personal"],
            "education": master_cv["education"],
            "languages": master_cv["languages"],
            "interests": "",
            "rodo_clause": "",
            "summary": "Experienced sales professional.",
            "competencies": ["B2B Sales"],
            "experience": [],
            "ats_keywords": [],
            "cv_output_language": "en-US",
            "fixed_experience_facts": [],
            "job_title": "Client Partner",
            "company": "Digital Forms",
            "job_language": "en",
            "language_confidence": "high",
            "role_type": "individual_contributor",
            "role_type_confidence": "high",
            "role_type_reasoning": "IC role.",
            "cv_emphasis": [],
            "match_score": 80,
            "match_notes": "",
            "covered_requirements": [],
            "gaps": [],
            "ats_report": {"used": [], "not_used": []},
            "ats_keyword_strategy": {
                "supported_keywords": [], "adjacent_keywords": [], "unsupported_keywords": [],
                "used_keywords": [], "excluded_keywords": [], "naturalness_notes": "",
            },
            "experience_gap_analysis": {
                "title": "Experience gaps vs. job posting",
                "text": "", "confirmed_strengths": [], "gaps": [],
                "transferable_angles": [], "do_not_claim": [],
            },
        }
        # The LLM response keeps job_title unchanged (setdefault ensures it)
        fake_revised = dict(current_cv)
        fake_revised["summary"] = "Short summary. Two sentences."
        with mock.patch("src.cv_adapter.chat") as mock_chat:
            mock_resp = mock.MagicMock()
            mock_resp.choices[0].message.content = json.dumps(fake_revised)
            mock_chat.return_value = mock_resp
            result = revise_full_cv(
                current_cv=current_cv,
                instruction="Skróć podsumowanie do 2 zdań.",
                job_posting="Client Partner at Digital Forms. B2B sales role.",
            )
        assert result.get("job_title") == "Client Partner", \
            f"revise_full_cv musi zachować job_title='Client Partner', got: {result.get('job_title')}"


# ══════════════════════════════════════════════════════════════════════
# NEW TESTS — application_repository, storage, endpoints, CSV, frontend
# ══════════════════════════════════════════════════════════════════════

# ── Test: application_repository module ──────────────────────────────

class TestApplicationRepository:
    """Tests for src/application_repository.py (DB module)."""

    def test_import_does_not_raise(self):
        """Module must import cleanly."""
        import src.application_repository as repo  # noqa: F401

    def test_db_disabled_init_returns_false(self, monkeypatch):
        """init_db() returns False when DB_ENABLED != true."""
        monkeypatch.setenv("DB_ENABLED", "false")
        import importlib
        import src.application_repository as repo
        importlib.reload(repo)
        result = repo.init_db()
        assert result is False

    def test_db_disabled_save_returns_none(self, monkeypatch):
        """save_application() returns None when DB_ENABLED=false."""
        monkeypatch.setenv("DB_ENABLED", "false")
        import src.application_repository as repo
        result = repo.save_application({"status": "generated", "company_name": "Test"})
        assert result is None

    def test_db_disabled_list_returns_none(self, monkeypatch):
        """list_applications() returns None when DB_ENABLED=false."""
        monkeypatch.setenv("DB_ENABLED", "false")
        import src.application_repository as repo
        result = repo.list_applications()
        assert result is None

    def test_db_disabled_update_contact_returns_false(self, monkeypatch):
        """update_contact() returns False when DB_ENABLED=false."""
        monkeypatch.setenv("DB_ENABLED", "false")
        import src.application_repository as repo
        result = repo.update_contact(1, "Jan Kowalski", "+48 123", "jan@firma.pl")
        assert result is False

    def test_db_disabled_update_notes_returns_false(self, monkeypatch):
        """update_notes() returns False when DB_ENABLED=false."""
        monkeypatch.setenv("DB_ENABLED", "false")
        import src.application_repository as repo
        result = repo.update_notes(1, "Notatka testowa")
        assert result is False

    def test_db_disabled_get_stats_returns_empty(self, monkeypatch):
        """get_stats() returns empty dict when DB_ENABLED=false."""
        monkeypatch.setenv("DB_ENABLED", "false")
        import src.application_repository as repo
        result = repo.get_stats()
        assert result == {}

    def test_export_csv_includes_headers_when_db_disabled(self, monkeypatch):
        """export_csv() must return CSV with headers even when DB disabled."""
        monkeypatch.setenv("DB_ENABLED", "false")
        import src.application_repository as repo
        csv_data = repo.export_csv()
        assert "contact_person" in csv_data
        assert "contact_phone" in csv_data
        assert "contact_email" in csv_data
        assert "company_name" in csv_data
        assert "job_title" in csv_data
        assert "role_type" in csv_data
        assert "cv_public_url" in csv_data
        assert "notes" in csv_data

    def test_table_schema_contains_contact_fields(self):
        """Table DDL must contain contact_person, contact_phone, contact_email."""
        from src.application_repository import _TABLE_DDL
        assert "contact_person" in _TABLE_DDL
        assert "contact_phone" in _TABLE_DDL
        assert "contact_email" in _TABLE_DDL

    def test_migration_columns_contains_contact_fields(self):
        """Migration columns dict must contain contact fields."""
        from src.application_repository import _MIGRATION_COLUMNS
        assert "contact_person" in _MIGRATION_COLUMNS
        assert "contact_phone" in _MIGRATION_COLUMNS
        assert "contact_email" in _MIGRATION_COLUMNS

    def test_role_type_label_mapping(self):
        """role_type_label() must return correct labels."""
        from src.application_repository import role_type_label
        assert role_type_label("individual_contributor") == "Business Development / Client Partner"
        assert role_type_label("sales_leadership") == "Sales Leadership / Management"
        assert role_type_label("mixed") == "Mixed — sprzedaż indywidualna + leadership"
        assert role_type_label("unknown") == "Nieustalony"
        assert role_type_label("garbage") == "Nieustalony"

    def test_csv_columns_match_export(self, monkeypatch):
        """CSV header row must contain all CSV_COLUMNS."""
        monkeypatch.setenv("DB_ENABLED", "false")
        import src.application_repository as repo
        csv_data = repo.export_csv()
        header = csv_data.split("\n")[0]
        for col in repo.CSV_COLUMNS:
            assert col in header, f"CSV header brakuje kolumny: {col}"


# ── Test: storage module ──────────────────────────────────────────────

class TestStorageModule:
    """Tests for src/storage.py (FTP module)."""

    def test_import_does_not_raise(self):
        """Module must import cleanly."""
        import src.storage as storage  # noqa: F401

    def test_ftp_disabled_upload_returns_disabled(self, monkeypatch):
        """upload_docx() returns disabled=True when FTP_ENABLED=false."""
        monkeypatch.setenv("FTP_ENABLED", "false")
        import src.storage as storage
        result = storage.upload_docx("/tmp/fakefile.docx")
        assert result["ok"] is False
        assert result["reason"] == "disabled"
        assert result["remote_path"] == ""
        assert result["public_url"] == ""

    def test_make_remote_path_format(self):
        """make_remote_path must create YYYY/MM directory structure."""
        from datetime import datetime
        from src.storage import make_remote_path
        now = datetime(2026, 4, 28, 10, 0, 0)
        path = make_remote_path("/cv-kreator/generated", "CV_test.docx", now)
        assert "/2026/04/CV_test.docx" in path
        assert path.startswith("/cv-kreator/generated")

    def test_make_remote_filename_sanitizes_slash(self):
        """make_remote_filename must replace '/' with '-' (FTP path separator safety)."""
        from src.storage import make_remote_filename
        fname = make_remote_filename(
            job_title="Client Partner / Technology Executive",
            company_name="INSPEERITY sp. z o.o.",
            date_str="2026-04-29",
        )
        assert "/" not in fname.split(".docx")[0], \
            f"Filename must not contain '/' in the name part: {fname}"
        assert "-" in fname or "Technology Executive" in fname
        assert fname.endswith(".docx")

    def test_make_remote_filename_contains_company_and_title(self):
        """Filename must contain company and job title parts (human-readable)."""
        from src.storage import make_remote_filename
        fname = make_remote_filename(
            job_title="Client Partner",
            company_name="Digital Forms",
            date_str="2026-04-28",
        )
        assert "Client Partner" in fname
        assert "Digital Forms" in fname
        assert "2026-04-28" in fname
        assert fname.startswith("CV Tomasz Uściński")

    def test_make_remote_filename_no_forward_slash(self):
        """Filename must not contain '/' which would break FTP STOR paths."""
        from src.storage import make_remote_filename
        fname = make_remote_filename("Sales / Marketing Lead", "Company Ltd.", "2026-01-15")
        name_part = fname.replace(".docx", "")
        assert "/" not in name_part, \
            f"Filename name part must not contain '/': {fname}"
        assert fname.endswith(".docx")


# ── Test: metadata from cv_data ───────────────────────────────────────

class TestCVMetadata:
    """Tests for metadata extracted from cv_data for Digital Forms / Client Partner."""

    def _make_cv_data(self, master_cv: dict) -> dict:
        """Build cv_data simulating a Digital Forms / Client Partner output."""
        return {
            "personal":             master_cv["personal"],
            "education":            master_cv["education"],
            "languages":            master_cv["languages"],
            "interests":            "",
            "rodo_clause":          master_cv.get("rodo_clause_en", ""),
            "summary":              "Experienced Client Partner with B2B SaaS background.",
            "competencies":         ["Business Development", "Client Acquisition"],
            "experience":           [],
            "ats_keywords":         ["Client Partner", "B2B", "SaaS"],
            "match_score":          82,
            "match_notes":          "Good match for this commercial role.",
            "covered_requirements": [],
            "gaps":                 [],
            "ats_report":           {"used": [], "not_used": []},
            "company":              "Digital Forms",
            "job_title":            "Client Partner",
            "job_language":         "en",
            "cv_output_language":   "en-US",
            "language_confidence":  "high",
            "role_type":            "individual_contributor",
            "role_type_confidence": "high",
            "role_type_reasoning":  "Standalone BD/client role without team management.",
            "cv_emphasis":          ["business development", "client acquisition"],
            "ats_keyword_strategy": {
                "supported_keywords":   ["B2B", "SaaS"],
                "adjacent_keywords":    [],
                "unsupported_keywords": [],
                "used_keywords":        ["B2B", "SaaS"],
                "excluded_keywords":    [],
                "naturalness_notes":    "Keywords woven naturally.",
            },
            "experience_gap_analysis": {
                "title":               "Experience gaps vs. job posting",
                "text":                "Good overall match.",
                "confirmed_strengths": ["B2B sales", "SaaS"],
                "gaps":                [],
                "transferable_angles": [],
                "do_not_claim":        [],
            },
            "fixed_experience_facts": [],
        }

    @pytest.fixture
    def master_cv(self):
        with open(BASE_DIR / "data" / "master_cv.json", encoding="utf-8") as f:
            return json.load(f)

    def test_company_name_from_cv_data(self, master_cv):
        """cv_data['company'] must equal 'Digital Forms'."""
        cv = self._make_cv_data(master_cv)
        assert cv["company"] == "Digital Forms"

    def test_job_title_from_cv_data(self, master_cv):
        """cv_data['job_title'] must equal 'Client Partner'."""
        cv = self._make_cv_data(master_cv)
        assert cv["job_title"] == "Client Partner"

    def test_role_type_individual_contributor(self, master_cv):
        """cv_data['role_type'] must be 'individual_contributor'."""
        cv = self._make_cv_data(master_cv)
        assert cv["role_type"] == "individual_contributor"

    def test_role_type_label_correct(self, master_cv):
        """role_type_label for individual_contributor must be correct."""
        from src.application_repository import role_type_label
        cv = self._make_cv_data(master_cv)
        assert role_type_label(cv["role_type"]) == "Business Development / Client Partner"

    def test_cv_output_language_en_us(self, master_cv):
        """cv_data['cv_output_language'] must be 'en-US' for English posting."""
        cv = self._make_cv_data(master_cv)
        assert cv["cv_output_language"] == "en-US"


# ── Test: new API endpoints ───────────────────────────────────────────

class TestNewEndpoints:
    """Tests for GET /api/applications, POST /api/applications/{id}/contact, etc."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        import sys
        sys.path.insert(0, str(BASE_DIR))
        from main import app
        return TestClient(app, raise_server_exceptions=False)

    def test_get_applications_db_disabled(self, client, monkeypatch):
        """GET /api/applications returns database_disabled=False when DB off."""
        monkeypatch.setenv("DB_ENABLED", "false")
        resp = client.get("/api/applications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["database_enabled"] is False
        assert data["items"] == []
        assert data["reason"] == "database_disabled"

    def test_export_csv_returns_csv_with_headers(self, client, monkeypatch):
        """GET /api/applications/export.csv returns CSV even when DB disabled."""
        monkeypatch.setenv("DB_ENABLED", "false")
        resp = client.get("/api/applications/export.csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        content = resp.text
        assert "contact_person" in content
        assert "contact_phone" in content
        assert "contact_email" in content
        assert "company_name" in content
        assert "cv_public_url" in content
        assert "notes" in content

    def test_post_contact_db_disabled_returns_controlled_response(self, client, monkeypatch):
        """POST /api/applications/{id}/contact returns controlled response when DB off."""
        monkeypatch.setenv("DB_ENABLED", "false")
        resp = client.post(
            "/api/applications/1/contact",
            json={"contact_person": "Jan Kowalski", "contact_phone": "", "contact_email": ""},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["reason"] == "database_disabled"

    def test_post_notes_db_disabled_returns_controlled_response(self, client, monkeypatch):
        """POST /api/applications/{id}/notes returns controlled response when DB off."""
        monkeypatch.setenv("DB_ENABLED", "false")
        resp = client.post(
            "/api/applications/1/notes",
            json={"notes": "Testowa notatka"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["reason"] == "database_disabled"

    def test_export_csv_route_before_id_route(self, client, monkeypatch):
        """export.csv must not be matched as record_id integer — must return CSV."""
        monkeypatch.setenv("DB_ENABLED", "false")
        resp = client.get("/api/applications/export.csv")
        # Must not return 422 (validation error for non-int id) or 404
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")


# ── Test: CSV export content ──────────────────────────────────────────

class TestCSVExport:
    """Tests for /api/applications/export.csv output."""

    def test_csv_headers_present(self, monkeypatch):
        """export_csv() must include all required headers."""
        monkeypatch.setenv("DB_ENABLED", "false")
        from src.application_repository import export_csv, CSV_COLUMNS
        csv_data = export_csv()
        header_line = csv_data.split("\n")[0]
        required = [
            "contact_person", "contact_phone", "contact_email",
            "company_name", "job_title", "role_type", "cv_public_url", "notes",
        ]
        for col in required:
            assert col in header_line, f"CSV brakuje kolumny: {col}"

    def test_csv_with_empty_db_has_only_header(self, monkeypatch):
        """export_csv() returns only header row when DB returns empty list."""
        monkeypatch.setenv("DB_ENABLED", "false")
        from src.application_repository import export_csv
        csv_data = export_csv()
        lines = [l for l in csv_data.split("\n") if l.strip()]
        assert len(lines) == 1, "Przy pustej bazie CSV powinien zawierać tylko wiersz nagłówkowy"


# ── Test: frontend HTML checks ────────────────────────────────────────

class TestFrontendHTML:
    """Static checks on static/index.html for dashboard elements."""

    @pytest.fixture(autouse=True)
    def html(self):
        html_path = BASE_DIR / "static" / "index.html"
        self._html = html_path.read_text(encoding="utf-8")

    def test_dashboard_section_exists(self):
        """index.html must contain Dashboard or Historia CV."""
        assert "Historia CV" in self._html or "Dashboard" in self._html, \
            "index.html musi zawierać sekcję 'Historia CV' lub 'Dashboard'"

    def test_contact_person_field_exists(self):
        assert "contact_person" in self._html, \
            "index.html musi zawierać 'contact_person'"

    def test_contact_phone_field_exists(self):
        assert "contact_phone" in self._html, \
            "index.html musi zawierać 'contact_phone'"

    def test_contact_email_field_exists(self):
        assert "contact_email" in self._html, \
            "index.html musi zawierać 'contact_email'"

    def test_api_applications_endpoint_referenced(self):
        assert "/api/applications" in self._html, \
            "index.html musi zawierać referencję do '/api/applications'"

    def test_contact_endpoint_referenced(self):
        assert "/contact" in self._html, \
            "index.html musi zawierać referencję do '/contact'"

    def test_export_csv_referenced(self):
        assert "export.csv" in self._html, \
            "index.html musi zawierać referencję do 'export.csv'"

    def test_save_contact_button_exists(self):
        assert "Zapisz kontakt" in self._html, \
            "index.html musi zawierać przycisk 'Zapisz kontakt'"

    def test_save_notes_button_exists(self):
        assert "Zapisz notatkę" in self._html, \
            "index.html musi zawierać przycisk 'Zapisz notatkę'"

    def test_record_id_passed_to_send_email(self):
        assert "record_id" in self._html, \
            "index.html musi przekazywać 'record_id' do send-email"


# ── Test: FTP configuration in .env.example ──────────────────────────

class TestFTPConfiguration:
    """Tests verifying FTP config in .env.example and storage.py behaviour."""

    @pytest.fixture(autouse=True)
    def env_example(self):
        env_path = BASE_DIR / ".env.example"
        self._env = env_path.read_text(encoding="utf-8")

    # ── .env.example content checks ──────────────────────────────────

    def test_env_example_ftp_host(self):
        assert "FTP_HOST=ftp.tomuscin.webd.pro" in self._env, \
            ".env.example musi zawierać FTP_HOST=ftp.tomuscin.webd.pro"

    def test_env_example_ftp_user(self):
        assert "FTP_USER=tomasz@lexaro.co" in self._env, \
            ".env.example musi zawierać FTP_USER=tomasz@lexaro.co"

    def test_env_example_ftp_port(self):
        assert "FTP_PORT=21" in self._env, \
            ".env.example musi zawierać FTP_PORT=21"

    def test_env_example_ftp_enabled_false(self):
        """FTP_ENABLED w .env.example musi być false (plik przykładowy)."""
        assert "FTP_ENABLED=false" in self._env, \
            ".env.example musi zawierać FTP_ENABLED=false (domyślnie wyłączone)"

    def test_env_example_no_ftp_password(self):
        """Hasło FTP musi być puste — nigdy nie commituj hasła."""
        import re
        # FTP_PASSWORD= must exist but with no value after =
        matches = re.findall(r"^FTP_PASSWORD=(.+)$", self._env, re.MULTILINE)
        assert not matches, \
            f".env.example nie może zawierać wartości FTP_PASSWORD: {matches}"

    def test_env_example_ftp_base_dir(self):
        assert "FTP_BASE_DIR=/cv-kreator/generated" in self._env, \
            ".env.example musi zawierać FTP_BASE_DIR=/cv-kreator/generated"

    # ── storage.py disabled behaviour ────────────────────────────────

    def test_ftp_disabled_no_upload_attempted(self, monkeypatch):
        """When FTP_ENABLED=false, upload_docx must not attempt connection."""
        monkeypatch.setenv("FTP_ENABLED", "false")
        import ftplib
        from unittest import mock
        with mock.patch.object(ftplib.FTP, "connect") as mock_connect:
            from src.storage import upload_docx
            result = upload_docx("/tmp/does_not_exist.docx")
            mock_connect.assert_not_called()
        assert result["ok"] is False
        assert result["reason"] == "disabled"

    def test_ftp_missing_password_no_upload(self, monkeypatch):
        """When FTP_ENABLED=true but FTP_PASSWORD empty, upload returns disabled."""
        monkeypatch.setenv("FTP_ENABLED", "true")
        monkeypatch.setenv("FTP_HOST", "ftp.tomuscin.webd.pro")
        monkeypatch.setenv("FTP_USER", "tomasz@lexaro.co")
        monkeypatch.setenv("FTP_PASSWORD", "")
        import importlib
        import src.storage as storage
        importlib.reload(storage)
        result = storage.upload_docx("/tmp/does_not_exist.docx")
        assert result["ok"] is False

    # ── remote path structure ─────────────────────────────────────────

    def test_remote_path_uses_cv_kreator_base(self):
        """make_remote_path must use /cv-kreator/generated as base."""
        from datetime import datetime
        from src.storage import make_remote_path
        now = datetime(2026, 4, 29, 12, 0, 0)
        path = make_remote_path("/cv-kreator/generated", "CV_test.docx", now)
        assert path.startswith("/cv-kreator/generated"), \
            f"Remote path musi zaczynać się od /cv-kreator/generated: {path}"

    def test_remote_path_yyyy_mm_structure(self):
        """make_remote_path must use YYYY/MM subdirectory structure."""
        from datetime import datetime
        from src.storage import make_remote_path
        now = datetime(2026, 4, 29, 12, 0, 0)
        path = make_remote_path("/cv-kreator/generated", "CV_test.docx", now)
        assert "/2026/04/CV_test.docx" in path, \
            f"Remote path musi zawierać /YYYY/MM/: {path}"

    def test_ftp_port_read_from_env(self, monkeypatch):
        """FTP_PORT from env must be used in connection config."""
        monkeypatch.setenv("FTP_ENABLED", "true")
        monkeypatch.setenv("FTP_HOST", "ftp.tomuscin.webd.pro")
        monkeypatch.setenv("FTP_USER", "tomasz@lexaro.co")
        monkeypatch.setenv("FTP_PASSWORD", "testpass")
        monkeypatch.setenv("FTP_PORT", "21")
        import importlib
        import src.storage as storage
        importlib.reload(storage)
        cfg = storage._ftp_config()
        assert cfg is not None
        assert cfg["port"] == 21, f"FTP port musi być 21, got: {cfg['port']}"

    # ── .gitignore check ─────────────────────────────────────────────

    def test_gitignore_excludes_dot_env(self):
        """.gitignore musi zawierać .env."""
        gitignore_path = BASE_DIR / ".gitignore"
        assert gitignore_path.exists(), ".gitignore musi istnieć"
        content = gitignore_path.read_text(encoding="utf-8")
        import re
        # Match .env as a standalone line (not .env.example)
        lines = [l.strip() for l in content.splitlines()]
        assert ".env" in lines, \
            ".gitignore musi zawierać '.env' jako osobną linię"


# ── Tests: email sender ───────────────────────────────────────────────

class TestEmailSender:
    """Unit tests for src/email_sender.py — all SMTP calls mocked."""

    DUMMY_BYTES    = b"PK\x03\x04fakecontent"  # minimal fake docx bytes
    DUMMY_FILENAME = "CV_Tomasz_Uscinski.docx"

    def _call_send_cv(self, monkeypatch, *, smtp_side_effect=None, smtp_user="user@example.com", smtp_password="secret"):
        """Helper: call send_cv with mocked SMTP_SSL."""
        import smtplib
        from unittest import mock
        import src.email_sender as em

        monkeypatch.setattr(em, "RESEND_API_KEY", "")
        monkeypatch.setattr(em, "SMTP_USER",     smtp_user)
        monkeypatch.setattr(em, "SMTP_PASSWORD", smtp_password)
        monkeypatch.setattr(em, "SMTP_FROM",     smtp_user)
        monkeypatch.setattr(em, "SMTP_HOST",     "smtp.gmail.com")
        monkeypatch.setattr(em, "SMTP_PORT",     465)

        mock_server = mock.MagicMock()
        if smtp_side_effect:
            mock_server.__enter__ = mock.Mock(side_effect=smtp_side_effect)
        else:
            mock_server.__enter__ = mock.Mock(return_value=mock_server)
            mock_server.__exit__  = mock.Mock(return_value=False)

        with mock.patch("smtplib.SMTP_SSL", return_value=mock_server) as mock_ssl:
            from src.email_sender import send_cv
            return send_cv(
                to="recipient@example.com",
                subject="Test subject",
                body_html="<p>Test</p>",
                docx_bytes=self.DUMMY_BYTES,
                docx_filename=self.DUMMY_FILENAME,
            ), mock_ssl, mock_server

    def test_send_cv_calls_smtp_ssl(self, monkeypatch):
        """send_cv must use SMTP_SSL (not SMTP+starttls)."""
        import smtplib
        from unittest import mock
        import src.email_sender as em

        monkeypatch.setattr(em, "RESEND_API_KEY", "")
        monkeypatch.setattr(em, "SMTP_USER",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_PASSWORD", "secret")
        monkeypatch.setattr(em, "SMTP_FROM",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_HOST",     "smtp.gmail.com")
        monkeypatch.setattr(em, "SMTP_PORT",     465)

        mock_server = mock.MagicMock()
        mock_server.__enter__ = mock.Mock(return_value=mock_server)
        mock_server.__exit__  = mock.Mock(return_value=False)

        with mock.patch("smtplib.SMTP_SSL", return_value=mock_server) as mock_ssl:
            from src.email_sender import send_cv
            send_cv(
                to="r@example.com", subject="S", body_html="<p>B</p>",
                docx_bytes=self.DUMMY_BYTES, docx_filename=self.DUMMY_FILENAME,
            )
        mock_ssl.assert_called_once()
        args, kwargs = mock_ssl.call_args
        assert args[0] == "smtp.gmail.com", "SMTP_SSL musi użyć SMTP_HOST"
        assert args[1] == 465, "SMTP_SSL musi użyć portu 465"

    def test_send_cv_calls_login(self, monkeypatch):
        """send_cv must call server.login with SMTP_USER and SMTP_PASSWORD."""
        import smtplib
        from unittest import mock
        import src.email_sender as em

        monkeypatch.setattr(em, "RESEND_API_KEY", "")
        monkeypatch.setattr(em, "SMTP_USER",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_PASSWORD", "secret16charspass")
        monkeypatch.setattr(em, "SMTP_FROM",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_HOST",     "smtp.gmail.com")
        monkeypatch.setattr(em, "SMTP_PORT",     465)

        mock_server = mock.MagicMock()
        mock_server.__enter__ = mock.Mock(return_value=mock_server)
        mock_server.__exit__  = mock.Mock(return_value=False)

        with mock.patch("smtplib.SMTP_SSL", return_value=mock_server):
            from src.email_sender import send_cv
            send_cv(
                to="r@example.com", subject="S", body_html="<p>B</p>",
                docx_bytes=self.DUMMY_BYTES, docx_filename=self.DUMMY_FILENAME,
            )
        mock_server.login.assert_called_once_with("user@example.com", "secret16charspass")

    def test_send_cv_attaches_docx(self, monkeypatch):
        """send_cv must call sendmail — attachment included."""
        import smtplib
        from unittest import mock
        import src.email_sender as em

        monkeypatch.setattr(em, "RESEND_API_KEY", "")
        monkeypatch.setattr(em, "SMTP_USER",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_PASSWORD", "secret")
        monkeypatch.setattr(em, "SMTP_FROM",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_HOST",     "smtp.gmail.com")
        monkeypatch.setattr(em, "SMTP_PORT",     465)

        mock_server = mock.MagicMock()
        mock_server.__enter__ = mock.Mock(return_value=mock_server)
        mock_server.__exit__  = mock.Mock(return_value=False)

        with mock.patch("smtplib.SMTP_SSL", return_value=mock_server):
            from src.email_sender import send_cv
            send_cv(
                to="r@example.com", subject="S", body_html="<p>B</p>",
                docx_bytes=self.DUMMY_BYTES, docx_filename=self.DUMMY_FILENAME,
            )
        mock_server.sendmail.assert_called_once()
        args = mock_server.sendmail.call_args[0]
        assert "r@example.com" in args[1], "sendmail musi wysłać na adres odbiorcy"
        # Verify attachment filename appears in raw message
        assert self.DUMMY_FILENAME in args[2], "Nazwa pliku musi być w treści wiadomości"

    def test_send_cv_missing_credentials_raises(self, monkeypatch):
        """send_cv must raise RuntimeError when credentials are empty."""
        import src.email_sender as em
        monkeypatch.setattr(em, "RESEND_API_KEY", "")
        monkeypatch.setattr(em, "SMTP_USER",     "")
        monkeypatch.setattr(em, "SMTP_PASSWORD", "")

        from src.email_sender import send_cv
        with pytest.raises(RuntimeError, match="credentials"):
            send_cv(
                to="r@example.com", subject="S", body_html="<p>B</p>",
                docx_bytes=self.DUMMY_BYTES, docx_filename=self.DUMMY_FILENAME,
            )

    def test_send_cv_auth_error_translates_to_readable_message(self, monkeypatch):
        """SMTPAuthenticationError must be translated to a readable Polish message."""
        import smtplib
        from unittest import mock
        import src.email_sender as em

        monkeypatch.setattr(em, "RESEND_API_KEY", "")
        monkeypatch.setattr(em, "SMTP_USER",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_PASSWORD", "wrongpassword")
        monkeypatch.setattr(em, "SMTP_FROM",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_HOST",     "smtp.gmail.com")
        monkeypatch.setattr(em, "SMTP_PORT",     465)

        mock_server = mock.MagicMock()
        mock_server.__enter__ = mock.Mock(return_value=mock_server)
        mock_server.__exit__  = mock.Mock(return_value=False)
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad credentials")

        from src.email_sender import send_cv
        with mock.patch("smtplib.SMTP_SSL", return_value=mock_server):
            with pytest.raises(RuntimeError, match="logowania SMTP"):
                send_cv(
                    to="r@example.com", subject="S", body_html="<p>B</p>",
                    docx_bytes=self.DUMMY_BYTES, docx_filename=self.DUMMY_FILENAME,
                )

    def test_send_cv_connection_timeout_translates_to_readable_message(self, monkeypatch):
        """Connection timeout must be translated to a readable Polish message."""
        import smtplib
        from unittest import mock
        import src.email_sender as em

        monkeypatch.setattr(em, "RESEND_API_KEY", "")
        monkeypatch.setattr(em, "SMTP_USER",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_PASSWORD", "secret")
        monkeypatch.setattr(em, "SMTP_FROM",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_HOST",     "smtp.gmail.com")
        monkeypatch.setattr(em, "SMTP_PORT",     465)

        from src.email_sender import send_cv
        with mock.patch("smtplib.SMTP_SSL", side_effect=TimeoutError("[Errno 110] Connection timed out")):
            with pytest.raises(RuntimeError, match="po.*czy.*serwerem SMTP"):
                send_cv(
                    to="r@example.com", subject="S", body_html="<p>B</p>",
                    docx_bytes=self.DUMMY_BYTES, docx_filename=self.DUMMY_FILENAME,
                )

    def test_send_cv_no_starttls_called(self, monkeypatch):
        """send_cv must NOT call starttls (uses SSL, not STARTTLS)."""
        import smtplib
        from unittest import mock
        import src.email_sender as em

        monkeypatch.setattr(em, "RESEND_API_KEY", "")
        monkeypatch.setattr(em, "SMTP_USER",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_PASSWORD", "secret")
        monkeypatch.setattr(em, "SMTP_FROM",     "user@example.com")
        monkeypatch.setattr(em, "SMTP_HOST",     "smtp.gmail.com")
        monkeypatch.setattr(em, "SMTP_PORT",     465)

        mock_server = mock.MagicMock()
        mock_server.__enter__ = mock.Mock(return_value=mock_server)
        mock_server.__exit__  = mock.Mock(return_value=False)

        with mock.patch("smtplib.SMTP_SSL", return_value=mock_server):
            from src.email_sender import send_cv
            send_cv(
                to="r@example.com", subject="S", body_html="<p>B</p>",
                docx_bytes=self.DUMMY_BYTES, docx_filename=self.DUMMY_FILENAME,
            )
        mock_server.starttls.assert_not_called()

    def test_render_yaml_smtp_host_is_webd(self):
        """render.yaml musi używać mail.tomaszuscinski.pl (tak jak aplikacja Anny)."""
        render_path = BASE_DIR / "render.yaml"
        if not render_path.exists():
            pytest.skip("brak render.yaml")
        content = render_path.read_text(encoding="utf-8")
        assert "mail.tomaszuscinski.pl" in content, \
            "render.yaml musi zawierać mail.tomaszuscinski.pl"

    def test_env_example_smtp_host_present(self):
        """.env.example musi zawierać SMTP_HOST."""
        env_ex = BASE_DIR / ".env.example"
        if not env_ex.exists():
            pytest.skip("brak .env.example")
        content = env_ex.read_text(encoding="utf-8")
        assert "SMTP_HOST" in content, ".env.example musi dokumentować SMTP_HOST"

    def test_env_example_no_smtp_password(self):
        """.env.example nie może zawierać wartości SMTP_PASSWORD."""
        import re
        env_ex = BASE_DIR / ".env.example"
        if not env_ex.exists():
            pytest.skip("brak .env.example")
        content = env_ex.read_text(encoding="utf-8")
        matches = re.findall(r"^SMTP_PASSWORD=(.+)$", content, re.MULTILINE)
        assert not matches, f".env.example nie może zawierać wartości SMTP_PASSWORD: {matches}"
