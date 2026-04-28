"""
CV Adapter — LLM-based CV customization for Kreator CV — Tomasz Uściński.

Rules enforced in the prompt:
- LLM is EDITOR, not author
- Must NOT invent jobs, education, achievements, numbers, technologies, industries or certifications
- Must NOT change dates, company names, or job titles
- May rephrase, reorder, and emphasize existing content
- Enforces character limits per field
- If a required competency is not in the base profile, LLM must NOT add it as fact —
  may suggest transferable/related skills or phrase the text more cautiously
"""

import json
import sys
from pathlib import Path

# openai_client.py lives at project root (works both locally and on Render)
sys.path.insert(0, str(Path(__file__).parent.parent))
from openai_client import chat  # noqa: E402

MASTER_CV_PATH = Path(__file__).parent.parent / "data" / "master_cv.json"

# ── Character limits (enforced in prompts + frontend) ────────────────
CHAR_LIMITS = {
    "summary":      900,
    "competencies": 600,
    "bullet":       200,
}

SYSTEM_PROMPT = """
Jesteś ekspertem od pisania CV pod kątem ATS i rekruterów.
Twoja rola: REDAKTOR, nie autor. Pracujesz wyłącznie na profilu Tomasza Uścińskiego.

ZASADY (bezwzględne):
1. NIE dodajesz nowych stanowisk, firm, projektów, liczb, osiągnięć ani certyfikatów.
2. NIE zmieniasz dat, nazw stanowisk ani wykształcenia.
3. NIE WYMYŚLAJ doświadczenia, kompetencji, narzędzi, branż, liczb, osiągnięć ani certyfikatów, których nie ma w profilu bazowym Tomasza Uścińskiego albo w dostarczonym CV. Jeśli ogłoszenie wymaga kompetencji, której profil bazowy nie potwierdza, nie dopisuj jej jako faktu. Możesz wskazać kompetencje pokrewne, transferowalne lub sformułować tekst ostrożniej.
4. MOŻESZ: przeformułować treść, zmienić kolejność punktów, podkreślić inne aspekty, dostosować język do ogłoszenia.
5. Wszystkie treści MUSZĄ wynikać z materiału źródłowego (master CV Tomasza Uścińskiego).
6. Optymalizuj pod ATS — używaj słów kluczowych z ogłoszenia tam, gdzie pasują do realnego doświadczenia.
7. Nie wypychaj słów kluczowych na siłę (keyword stuffing) — tylko naturalne użycie.
8. Zachowaj profesjonalny, konkretny styl. Unikaj przesadnego marketingowego tonu.
9. POZYCJONOWANIE KANDYDATA: Tomasz Uściński posiada silne doświadczenie biznesowe, sprzedażowe, founderskie, C-level i w komercjalizacji technologii. Może używać AI, LLM, GitHub, Python, PostgreSQL, Render, Sanity i narzędzi API w praktycznych procesach biznesowych, automatyzacji i prototypowaniu. NIE opisuj go jako senior software engineera, backend developera, ML engineera ani data engineera, chyba że profil bazowy jednoznacznie potwierdza taką rolę. Dla ogłoszeń IT-oriented pozycjonuj go jako lidera biznesowo-technologicznego, praktyka automatyzacji sprzedaży/procesów opartego na AI, operatora komercyjno-produktowego i menadżera skutecznie współpracującego z zespołami technicznymi.

WYKRYWANIE JĘZYKA I JĘZYK WYJŚCIA CV:
- Przed wygenerowaniem sekcji CV wykryj dominujący język ogłoszenia rekrutacyjnego.
- Jeśli ogłoszenie jest po angielsku: generuj WSZYSTKIE sekcje CV w naturalnym, profesjonalnym US English. Nie tłumacz dosłownie — przepisz jako naturalne executive CV.
- Jeśli ogłoszenie jest po polsku: generuj WSZYSTKIE sekcje CV w języku polskim.
- Jeśli ogłoszenie jest mieszane: użyj języka dominującego.
- Nie mieszaj polskiego i angielskiego w tej samej sekcji CV.
- Dla angielskich CV: section_1.name = "Professional Summary", section_2.name = "Key Competencies".
- Dla polskich CV: section_1.name = "Profil zawodowy", section_2.name = "Kluczowe kompetencje".
- Zwróć pola: job_language ("pl" | "en" | "unknown"), cv_output_language ("pl" | "en-US"), language_confidence ("high" | "medium" | "low").

ROZPOZNAWANIE TYPU STANOWISKA I AKCENTY CV:
Przed wygenerowaniem sekcji CV sklasyfikuj ogłoszenie pod kątem typu stanowiska:
- "individual_contributor": samodzielne role biznesowo-sprzedażowe bez wyraźnej odpowiedzialności za zarządzanie zespołem — Business Development Manager, Client Partner, Senior Client Partner, Account Executive, Sales Executive, Key Account Manager, Growth Manager, Partnership Manager, Commercial Manager bez zarządzania zespołem, samodzielna rola hunterska/doradcza/relacyjna.
- "sales_leadership": rola z odpowiedzialnością za zarządzanie zespołem, strategię sprzedaży, targety, budżet, hiring, coaching, proces, pipeline na poziomie zespołu lub firmy — Head of Sales, Sales Director, VP Sales, Commercial Director, Revenue Director, Country Manager, General Manager, Managing Director, Team Lead, Head of Business Development.
- "mixed": ogłoszenie łączy samodzielną sprzedaż z odpowiedzialnością za zespół (np. Head of Sales z własną sprzedażą, Client Partner z budową zespołu).
- "unknown": nie można ustalić na podstawie ogłoszenia.

Na podstawie klasyfikacji dobierz akcenty CV:
Dla individual_contributor podkreśl:
- samodzielne pozyskiwanie klientów B2B (business development, hunting, prospecting)
- budowanie relacji z decydentami
- consultative selling, discovery, value proposition
- outbound, cold outreach, personalizacja
- ICP, account research
- pipeline ownership i zamykanie szans
- automatyzacja sprzedaży oparta na AI/LLM (Apollo, GitHub, Python) — jeśli relevantne
- zdolność do samodzielnego działania

Dla sales_leadership podkreśl:
- doświadczenie C-level / Head of Sales / Managing Director / Członek Zarządu
- zarządzanie, budowanie i coaching zespołu sprzedaży
- strategia sprzedaży i GTM
- sales operations, procesy, KPI, budżety
- wzrost przychodów, P&L
- zarządzanie pipeline'em na poziomie zespołu/firmy
- cross-functional leadership (marketing, produkt, IT, finanse, ryzyko)
- hiring i skalowanie organizacji sprzedaży

Dla mixed: łącz oba obszary, priorytet nadaj temu, co silniej wynika z ogłoszenia.
Nie wymyślaj doświadczenia — używaj wyłącznie potwierdzonego profilu bazowego.

Zwróć pola: role_type ("individual_contributor" | "sales_leadership" | "mixed" | "unknown"), role_type_confidence ("high" | "medium" | "low"), role_type_reasoning (krótkie wyjaśnienie, 1-2 zdania), cv_emphasis (lista akcentów wybranych do CV, max 8 pozycji).

NATURALNA OPTYMALIZACJA ATS — BEZWZGLĘDNE ZASADY:
Używaj słów kluczowych z ogłoszenia naturalnie i widocznie w sekcjach CV. Obowiązuje bezwzględny zakaz:
- ukrytych, niewidzialnych ani białych słów kluczowych,
- mikroskopijnego tekstu,
- słów kluczowych tylko w metadanych,
- keyword stuffingu (nadmiernego powtarzania).

Przed wygenerowaniem sekcji CV sklasyfikuj słowa kluczowe z ogłoszenia:
- "supported": wyraźnie potwierdzone w profilu Tomasza,
- "adjacent": nie wprost potwierdzone, ale powiązane z jego doświadczeniem,
- "unsupported": niepotwierdzone — NIE używaj jako faktu.

Używaj słów kluczowych tylko jeśli:
- brzmią naturalnie w zdaniu,
- wynikają z realnego doświadczenia,
- nie tworzą listy SEO/ATS spam,
- są widoczne w normalnym tekście CV.

Dla "Professional Summary" / "Profil zawodowy": wplataj słowa kluczowe w płynne zdania.
Dla "Key Competencies" / "Kluczowe kompetencje": używaj zwartych fraz kompetencyjnych — bez przeładowanych łańcuchów keywordów.

Dopasowanie języka CV a słowa kluczowe:
- cv_output_language = "pl": naturalna polszczyzna; angielskie nazwy narzędzi i stanowisk możesz zachować; unikaj mieszania bez potrzeby.
- cv_output_language = "en-US": naturalny executive English; stosuj terminy jak: sales leadership, business development, go-to-market, revenue growth, client acquisition, sales operations, AI-enabled outreach, SaaS, FinTech, InsurTech — tylko gdy pasują do ogłoszenia.

Dopasowanie do typu roli a słowa kluczowe:
- individual_contributor: naturalnie wzmacniaj frazy: business development, client acquisition, consultative selling, decision-maker engagement, outbound campaigns, relationship building, pipeline ownership, ICP/account research, AI/LLM-assisted outreach, Apollo, sales execution.
- sales_leadership: naturalnie wzmacniaj frazy: sales leadership, team management, hiring, coaching, sales strategy, go-to-market, revenue growth, P&L, sales budgets, KPI management, sales operations, pipeline management, cross-functional leadership.
- mixed: stosuj oba zestawy bez przeciążania tekstu.

Zwróć pole ats_keyword_strategy z polami:
- supported_keywords: potwierdzone w profilu
- adjacent_keywords: powiązane, ale nie wprost potwierdzone
- unsupported_keywords: pominięte — brak potwierdzenia
- used_keywords: faktycznie użyte w wygenerowanych sekcjach
- excluded_keywords: ważne, lecz pominięte z powodu braku potwierdzenia
- naturalness_notes: krótki opis (1-2 zdania) jak słowa kluczowe zostały wplecione

Kontrola jakości (przed zwróceniem JSON, bez chain-of-thought):
- Usuń keyword stuffing.
- Usuń nieudokumentowane twierdzenia.
- Przepisz awkward keyword insertions.
- Upewnij się, że tekst brzmi jak profesjonalne CV dla rekrutera i systemu ATS.

ANALIZA LUK / NIEDOPASOWANIA (experience_gap_analysis):
Po wygenerowaniu sekcji CV przygotuj krótką analizę luk dla użytkownika. Zawiera:
- title: tytuł sekcji w języku zgodnym z cv_output_language: dla "en-US" = "Experience gaps vs. job posting", dla "pl" = "Niedopasowanie doświadczenia do ogłoszenia".
- text: jeden krótki, naturalny akapit (3-6 zdań) opisujący, które wymagania ogłoszenia profil Tomasza spełnia, a których nie potwierdza wprost. Nie krytykuj kandydata. Ton: neutralny, praktyczny, profesjonalny.
- confirmed_strengths: lista obszarów wyraźnie potwierdzonych w profilu i pasujących do ogłoszenia.
- gaps: lista wymagań z ogłoszenia, których profil Tomasza nie potwierdza wprost.
- transferable_angles: lista pokrewnych doświadczeń, które można bezpiecznie zaakcentować jako substytut.
- do_not_claim: lista elementów, których LLM nie powinien dopisywać jako faktów (bo ich nie ma w profilu bazowym).
Ta analiza służy tylko użytkownikowi w UI przed wysyłką CV. NIE wstawiaj do sekcji CV (summary, competencies, experience). NIE osłabiaj tekstu CV przez wzmiankę o lukach w treści CV.
Przy poprawianiu CV (revise_full_cv): zachowaj lub zaktualizuj experience_gap_analysis. Nie zamykaj luk przez wymyslanie niepotwierdzonych doświadczeń.

NIEZMIENNE FAKTY DOŚWIADCZENIA ZAWODOWEGO (fixed_experience_facts):
Nazwy firm, branże/opisy firm, stanowiska i okresy zatrudnienia z sekcji fixed_experience_facts w profilu bazowym są FAKTAMI STAŁYMI i NIEZMIENNYMI. Nie wolno ich zmieniać, przeformułowywać, skracać, rozszerzać, wnioskować ani adaptować pod ogłoszenie. Można adaptować wyłącznie opisy obowiązków, zakresu odpowiedzialności i osiągnięć w ramach danego stanowiska. Firma, branża, stanowisko i okres muszą pozostać dokładnie takie, jak zdefiniowane w fixed_experience_facts. Dla wersji PL używaj period_pl. Dla wersji EN/en-US używaj period_en.

The company names, industries, job titles and employment periods in fixed_experience_facts are immutable facts. Do not change, rewrite, infer, extend, shorten or adapt them to the job posting. You may adapt only the descriptions, responsibilities and achievements, but the company, industry, title and period must remain exactly as defined in fixed_experience_facts. For Polish CV output use period_pl. For English CV output use period_en.

LIMITY ZNAKÓW (bezwzględne — nie przekraczaj):
- Podsumowanie zawodowe / Professional Summary: max 900 znaków
- Lista kompetencji (łącznie wszystkie): max 600 znaków
- Każdy punkt w doświadczeniu (każde bullet): max 200 znaków
Jeśli tekst przekroczyłby limit — skróć, zachowując kluczowe informacje i słowa ATS.

Odpowiedź zawsze w formacie JSON, zgodnie ze schematem wyjściowym.
""".strip()


# ── Language field validation ─────────────────────────────────────────

def _validate_role_fields(adapted: dict) -> tuple[str, str, str, list]:
    """
    Validates and normalises LLM-returned role type fields.
    Returns (role_type, role_type_confidence, role_type_reasoning, cv_emphasis).
    """
    valid_types = ("individual_contributor", "sales_leadership", "mixed", "unknown")
    valid_conf  = ("high", "medium", "low")

    role_type   = adapted.get("role_type", "unknown")
    rt_conf     = adapted.get("role_type_confidence", "low")
    rt_reason   = adapted.get("role_type_reasoning", "")
    cv_emphasis = adapted.get("cv_emphasis", [])

    if role_type not in valid_types:
        role_type = "unknown"
    if rt_conf not in valid_conf:
        rt_conf = "low"
    if not isinstance(cv_emphasis, list):
        cv_emphasis = []
    if not isinstance(rt_reason, str):
        rt_reason = ""

    return role_type, rt_conf, rt_reason, cv_emphasis


def _validate_ats_strategy(adapted: dict) -> dict:
    """
    Validates and normalises the ats_keyword_strategy field from LLM response.
    Returns a safe dict with all expected sub-fields.
    """
    raw = adapted.get("ats_keyword_strategy", {})
    if not isinstance(raw, dict):
        raw = {}

    def _list(key: str) -> list:
        v = raw.get(key, [])
        return v if isinstance(v, list) else []

    def _str(key: str) -> str:
        v = raw.get(key, "")
        return v if isinstance(v, str) else ""

    return {
        "supported_keywords":  _list("supported_keywords"),
        "adjacent_keywords":   _list("adjacent_keywords"),
        "unsupported_keywords": _list("unsupported_keywords"),
        "used_keywords":       _list("used_keywords"),
        "excluded_keywords":   _list("excluded_keywords"),
        "naturalness_notes":   _str("naturalness_notes"),
    }


def _validate_gap_analysis(adapted: dict, cv_output_language: str = "pl") -> dict:
    """
    Validates and normalises the experience_gap_analysis field from LLM response.
    Returns a safe dict with all expected sub-fields.
    """
    default_title = (
        "Experience gaps vs. job posting"
        if cv_output_language == "en-US"
        else "Niedopasowanie doświadczenia do ogłoszenia"
    )
    raw = adapted.get("experience_gap_analysis", {})
    if not isinstance(raw, dict):
        raw = {}

    def _str(key: str) -> str:
        v = raw.get(key, "")
        return v if isinstance(v, str) else ""

    def _list(key: str) -> list:
        v = raw.get(key, [])
        return v if isinstance(v, list) else []

    return {
        "title":               _str("title") or default_title,
        "text":                _str("text"),
        "confirmed_strengths": _list("confirmed_strengths"),
        "gaps":                _list("gaps"),
        "transferable_angles": _list("transferable_angles"),
        "do_not_claim":        _list("do_not_claim"),
    }


def _validate_language_fields(adapted: dict) -> tuple[str, str, str]:
    """
    Validates and normalises LLM-returned language fields.
    Returns (job_language, cv_output_language, language_confidence).
    """
    job_lang = adapted.get("job_language", "unknown")
    cv_lang  = adapted.get("cv_output_language", "pl")
    conf     = adapted.get("language_confidence", "low")

    if job_lang not in ("pl", "en", "unknown"):
        job_lang = "unknown"
    if cv_lang not in ("pl", "en-US"):
        cv_lang = "pl"
    if conf not in ("high", "medium", "low"):
        conf = "low"

    # If language is unknown, force Polish output
    if job_lang == "unknown":
        cv_lang = "pl"

    return job_lang, cv_lang, conf

OUTPUT_SCHEMA = {
    "job_language": "\"pl\" | \"en\" | \"unknown\" — dominant language of the job posting",
    "cv_output_language": "\"pl\" | \"en-US\" — language used for all generated CV sections",
    "language_confidence": "\"high\" | \"medium\" | \"low\" — confidence in language detection",
    "role_type": "\"individual_contributor\" | \"sales_leadership\" | \"mixed\" | \"unknown\" — classified role type",
    "role_type_confidence": "\"high\" | \"medium\" | \"low\" — confidence in role type classification",
    "role_type_reasoning": "string — brief explanation of role classification (1-2 sentences)",
    "cv_emphasis": "list[string] — selected emphasis areas for this CV (max 8 items)",
    "summary": "string — profil zawodowy / Professional Summary (max 900 znaków/chars)",
    "competencies": "list[string] — lista kompetencji / Key Competencies (max 14 items, total max 600 chars)",
    "experience": [
        {
            "title": "string — bez zmian z matki / unchanged from source",
            "dates": "string — bez zmian z matki / unchanged from source",
            "bullets": "list[string] — każdy punkt max 200 znaków / each bullet max 200 chars"
        }
    ],
    "ats_keyword_strategy": {
        "supported_keywords":  "list[string] — keywords clearly supported by Tomasz's profile",
        "adjacent_keywords":   "list[string] — keywords related but not directly confirmed",
        "unsupported_keywords": "list[string] — keywords not supported — omit as factual claims",
        "used_keywords":       "list[string] — keywords actually used in generated sections",
        "excluded_keywords":   "list[string] — important job keywords omitted due to lack of profile support",
        "naturalness_notes":   "string — brief note on how keywords were integrated (1-2 sentences)",
    },
    "experience_gap_analysis": {
        "title":               "string — section title in cv_output_language: 'Experience gaps vs. job posting' (en-US) or 'Niedopasowanie doświadczenia do ogłoszenia' (pl)",
        "text":                "string — concise paragraph (3-6 sentences) for the user: what is confirmed, what is missing, what can be safely positioned as transferable",
        "confirmed_strengths": "list[string] — areas clearly confirmed in Tomasz's profile that match the job posting",
        "gaps":                "list[string] — job posting requirements not directly confirmed in Tomasz's profile",
        "transferable_angles": "list[string] — adjacent/transferable experience that can safely substitute",
        "do_not_claim":        "list[string] — items that must not be added to the CV as factual claims",
    },
    "ats_keywords": "list[string] — ATS keywords from job posting matching the CV",
    "match_score": "int 0-100 — match rating",
    "match_notes": "string — brief justification (2-3 sentences, in cv_output_language)",
    "covered_requirements": "list[string] — job requirements well covered by CV (max 5)",
    "gaps": "list[string] — requirements missing or weakly covered (max 5)",
    "ats_report": {
        "used": [{"keyword": "string", "locations": ["Summary | Competencies | Experience — {title}"]}],
        "not_used": [{"keyword": "string", "reason": "string"}]
    },
    "company": "string — company name from job posting (or '')",
    "job_title": "string — job title from job posting"
}


def adapt_cv(job_posting: str, master_cv: dict | None = None) -> dict:
    """
    Adapts the master CV (Tomasz Uściński) to a specific job posting using LLM.

    Args:
        job_posting: Full text of the job posting.
        master_cv:   Optional override of master CV data.
                     If None, loads from data/master_cv.json.

    Returns:
        Dict with adapted CV content plus analysis metadata.

    Raises:
        ValueError: If LLM response cannot be parsed as JSON.
        RuntimeError: If no model in the fallback chain responds.
    """
    if master_cv is None:
        with open(MASTER_CV_PATH, encoding="utf-8") as f:
            master_cv = json.load(f)

    user_message = f"""
## PROFIL KANDYDATA — TOMASZ UŚCIŃSKI (źródło prawdy — nie modyfikuj struktury):
{json.dumps(master_cv, ensure_ascii=False, indent=2)}

## OGŁOSZENIE REKRUTACYJNE:
{job_posting}

## ZADANIE:
1. Wykryj dominujący język ogłoszenia (job_language: "pl" | "en" | "unknown").
2. Określ język wyjścia CV (cv_output_language: "pl" | "en-US") i pewność detekcji (language_confidence: "high" | "medium" | "low").
3. Sklasyfikuj typ stanowiska (role_type: "individual_contributor" | "sales_leadership" | "mixed" | "unknown"), pewność klasyfikacji (role_type_confidence: "high" | "medium" | "low"), krótkie uzasadnienie (role_type_reasoning, 1-2 zdania) i wybierz akcenty CV (cv_emphasis: lista max 8 pozycji).
4. Sklasyfikuj słowa kluczowe ATS z ogłoszenia jako: supported / adjacent / unsupported (per zasady SYSTEM_PROMPT). Zapisz wyniki w ats_keyword_strategy.
5. Dostosuj treść CV Tomasza Uścińskiego do tego ogłoszenia w wykrytym języku wyjścia, akcentując kwalifikacje odpowiednie do sklasyfikowanego typu roli. Używaj słów kluczowych naturalnie i widocznie w tekście — nie dodawaj ukrytych, białych ani mikroskopijnych słów kluczowych.
   - Jeśli cv_output_language = "en-US": pisz WSZYSTKIE sekcje po angielsku (Professional Summary, Key Competencies, bullets). Nie tłumacz dosłownie — przepisz naturalnym executive English.
   - Jeśli cv_output_language = "pl": pisz WSZYSTKIE sekcje po polsku.
6. Zachowaj wszystkie stanowiska, daty i fakty. Podkreśl doświadczenia relevantne dla tej roli.
7. Po wygenerowaniu sekcji CV wykonaj cichą kontrolę jakości: usuń keyword stuffing, usuń nieudokumentowane twierdzenia, przepisz awkward insertions — bez chain-of-thought. Zwróć tylko finalny JSON.
PILNUJ LIMITÓW ZNAKÓW — podsumowanie max 900, kompetencje łącznie max 600, każdy bullet max 200.
NIE wymyślaj kompetencji, liczb ani osiągnięć spoza profilu bazowego.

Po wygenerowaniu CV uzupełnij ats_keyword_strategy oraz przeanalizuj:
- które słowa kluczowe ATS z ogłoszenia znalazły się w CV i gdzie (ats_report.used),
- których nie użyto i dlaczego (ats_report.not_used),
- które wymagania z ogłoszenia są dobrze pokryte przez CV (covered_requirements),
- jakie luki istnieją między ogłoszeniem a profilem (gaps),
- wyodrębnij nazwę firmy i stanowisko z ogłoszenia.

Zwróć TYLKO poprawny JSON zgodny z tym schematem:
{json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2)}
""".strip()

    response = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_completion_tokens=5000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    if not raw:
        raise ValueError(
            "Model nie zwrócił treści. Sprawdź, czy ogłoszenie zawiera wystarczającą ilość tekstu "
            "(minimum 100-200 słów). Jeśli korzystasz z linku LinkedIn, wklej treść ogłoszenia ręcznie."
        )

    try:
        adapted = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM zwrócił niepoprawny JSON: {exc}\n\nRaw:\n{raw}") from exc

    job_language, cv_output_language, language_confidence = _validate_language_fields(adapted)
    role_type, role_type_confidence, role_type_reasoning, cv_emphasis = _validate_role_fields(adapted)
    ats_keyword_strategy = _validate_ats_strategy(adapted)
    gap_analysis = _validate_gap_analysis(adapted, cv_output_language)

    result = {
        "personal":             master_cv["personal"],
        "education":            master_cv["education"],
        "languages":            master_cv["languages"],
        "interests":            master_cv.get("interests", ""),
        "rodo_clause":          master_cv.get("rodo_clause_en", "") if cv_output_language == "en-US" else master_cv.get("rodo_clause", ""),
        "summary":              adapted.get("summary", master_cv["summary"]),
        "competencies":         adapted.get("competencies", master_cv["competencies"]),
        "experience":           _merge_experience(master_cv["experience"], adapted.get("experience", [])),
        "ats_keywords":         adapted.get("ats_keywords", []),
        "match_score":          adapted.get("match_score", 0),
        "match_notes":          adapted.get("match_notes", ""),
        "covered_requirements": adapted.get("covered_requirements", []),
        "gaps":                 adapted.get("gaps", []),
        "ats_report":           adapted.get("ats_report", {"used": [], "not_used": []}),
        "ats_keyword_strategy": ats_keyword_strategy,
        "experience_gap_analysis": gap_analysis,
        "company":              adapted.get("company", ""),
        "job_title":            adapted.get("job_title", ""),
        "job_language":         job_language,
        "cv_output_language":   cv_output_language,
        "language_confidence":  language_confidence,
        "role_type":            role_type,
        "role_type_confidence": role_type_confidence,
        "role_type_reasoning":  role_type_reasoning,
        "cv_emphasis":          cv_emphasis,
    }

    return result


def _merge_experience(master_exp: list, adapted_exp: list) -> list:
    """Merges adapted bullets into master entries. Title + dates locked."""
    adapted_map = {e.get("title", ""): e for e in adapted_exp}
    merged = []
    for orig in master_exp:
        title = orig["title"]
        if title in adapted_map:
            merged.append({
                "title":   orig["title"],
                "dates":   orig["dates"],
                "bullets": adapted_map[title].get("bullets", orig["bullets"]),
            })
        else:
            merged.append(orig)
    return merged


def analyze_job_posting(job_posting: str) -> dict:
    """
    Analyzes job posting and extracts key requirements, including language detection.

    Returns:
        Dict with: required_experience, responsibilities, technologies,
        ats_keywords, tone, priority_competencies, company, job_title,
        job_language, cv_output_language, language_confidence.
    """
    response = chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert HR analyst. Analyze job postings and return JSON. "
                    "Always detect the dominant language of the job posting and include "
                    "job_language, cv_output_language and language_confidence in your response."
                )
            },
            {
                "role": "user",
                "content": f"""Analyze this job posting and return JSON with the following fields:
{{
  "job_language": "pl" | "en" | "unknown",
  "cv_output_language": "pl" | "en-US",
  "language_confidence": "high" | "medium" | "low",
  "role_type": "individual_contributor" | "sales_leadership" | "mixed" | "unknown",
  "role_type_confidence": "high" | "medium" | "low",
  "role_type_reasoning": "brief explanation of role classification (1-2 sentences)",
  "cv_emphasis": ["list of CV emphasis areas selected for this role, max 8"],
  "required_experience": ["list of experience requirements"],
  "responsibilities": ["list of main responsibilities"],
  "technologies": ["tools, systems, platforms"],
  "ats_keywords": ["key ATS keywords"],
  "tone": "description of job posting tone (1 sentence)",
  "priority_competencies": ["top 5 competencies expected by employer"],
  "company": "company name (or '' if not found)",
  "job_title": "job title from the posting"
}}

Rules for language fields:
- job_language: dominant language of the job posting text
- cv_output_language: "en-US" if job_language is "en", "pl" otherwise
- language_confidence: how confident you are in the language detection

Rules for role_type:
- "individual_contributor": standalone BD / client partner / AE / KAM / commercial roles without people management
- "sales_leadership": Head of Sales / Director / VP / GM / MD / Team Lead roles with team, strategy, hiring, budgets
- "mixed": role combines individual sales ownership with team leadership responsibility
- "unknown": cannot determine from the posting

JOB POSTING:
{job_posting}"""
            }
        ],
        max_completion_tokens=1500,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"raw": raw}

    # Apply language field validation/normalisation
    job_lang, cv_lang, conf = _validate_language_fields(result)
    result["job_language"]        = job_lang
    result["cv_output_language"]  = cv_lang
    result["language_confidence"] = conf

    # Apply role type field validation/normalisation
    role_type, rt_conf, rt_reason, cv_emphasis = _validate_role_fields(result)
    result["role_type"]            = role_type
    result["role_type_confidence"] = rt_conf
    result["role_type_reasoning"]  = rt_reason
    result["cv_emphasis"]          = cv_emphasis
    return result


def revise_field(
    field_name: str,
    current_text: str,
    user_comment: str,
    job_posting: str,
    char_limit: int,
    cv_output_language: str = "pl",
) -> str:
    """
    Revises a single CV field based on user comment, respecting char limit.
    The cv_output_language parameter ensures the revision stays in the same
    language as the generated CV, regardless of the comment's language.
    """
    if cv_output_language == "en-US":
        lang_rule = (
            "The current CV output language is en-US. "
            "Revise the text in natural, professional US English. "
            "Do not switch to Polish even if the user's comment is in Polish."
        )
    else:
        lang_rule = (
            "Obecny język CV to polski. "
            "Poprawiaj tekst po polsku. "
            "Nie zmieniaj języka na angielski, nawet jeśli komentarz użytkownika jest po angielsku."
        )

    response = chat(
        messages=[
            {
                "role": "system",
                "content": f"""Jesteś ekspertem od CV Tomasza Uścińskiego. Edytujesz jedno pole CV na prośbę użytkownika.

ZASADY:
- Zachowaj fakty, stanowiska, daty — nie wymyślaj nowych doświadczeń, kompetencji ani osiągnięć
- Nie dopisuj informacji, których nie ma w profilu bazowym Tomasza Uścińskiego
- Uwzględnij komentarz użytkownika
- Nie przekraczaj {char_limit} znaków (BEZWZGLĘDNY LIMIT)
- Zwróć TYLKO poprawiony tekst, bez komentarza, bez cudzysłowów
- JĘZYK: {lang_rule}
- ATS: używaj słów kluczowych z ogłoszenia naturalnie i widocznie. Nie dodawaj ukrytych, białych ani mikroskopijnych słów kluczowych. Jeśli użytkownik prosi o keyword, którego profil bazowy nie potwierdza, pomin go lub użyj powiązanego pojęcia bez twierdzenia o bezpośredniej ekspertyzie.

Pole: {field_name}
Limit znaków: {char_limit}"""
            },
            {
                "role": "user",
                "content": f"""Komentarz: {user_comment}

Obecny tekst ({len(current_text)} znaków):
{current_text}

Kontekst ogłoszenia (fragment):
{job_posting[:800]}

Zwróć TYLKO poprawiony tekst (max {char_limit} znaków)."""
            }
        ],
        max_completion_tokens=600,
    )

    revised = response.choices[0].message.content.strip()
    if revised.startswith('"') and revised.endswith('"'):
        revised = revised[1:-1]
    return revised


def revise_full_cv(current_cv: dict, instruction: str, job_posting: str) -> dict:
    """
    Revises the entire adapted CV based on a free-form user instruction.

    The structure (personal, education, languages) is preserved.
    Only summary, competencies, and experience bullets may change.
    The cv_output_language from current_cv is preserved — revision language
    matches the language already used in the CV, not the instruction language.
    """
    cv_output_language = current_cv.get("cv_output_language", "pl")
    role_type          = current_cv.get("role_type", "unknown")
    cv_emphasis        = current_cv.get("cv_emphasis", [])

    if cv_output_language == "en-US":
        lang_rule = (
            "The current CV output language is en-US. "
            "Revise ALL sections in natural, professional US English. "
            "Do not switch to Polish even if the user instruction is in Polish. "
            "Preserve the language unless the user explicitly requests a language change."
        )
    else:
        lang_rule = (
            "Obecny język CV to polski. "
            "Poprawiaj WSZYSTKIE sekcje po polsku. "
            "Nie zmieniaj języka na angielski, nawet jeśli instrukcja użytkownika jest po angielsku. "
            "Zachowaj język, chyba że użytkownik wyraźnie prosi o zmianę języka."
        )

    # Build role emphasis rule for the revision prompt
    if role_type == "individual_contributor":
        role_rule = (
            "The current role type is individual_contributor. "
            "Preserve emphasis on: business development, client acquisition, independent sales execution, "
            "consultative selling, outbound, pipeline ownership and relationship building. "
            "Do NOT shift emphasis towards team management or leadership unless the user explicitly asks."
        )
    elif role_type == "sales_leadership":
        role_rule = (
            "The current role type is sales_leadership. "
            "Preserve emphasis on: leadership, team management, sales strategy, P&L, revenue growth, "
            "sales operations, hiring and coaching. "
            "Do NOT shift emphasis towards individual sales execution unless the user explicitly asks."
        )
    elif role_type == "mixed":
        role_rule = (
            "The current role type is mixed (individual sales + team leadership). "
            "Preserve a balanced emphasis covering both individual contribution and leadership. "
            "Do NOT drop either perspective unless the user explicitly asks."
        )
    else:
        role_rule = "Preserve the current CV positioning and emphasis."
    cv_snapshot = {
        "summary":      current_cv.get("summary", ""),
        "competencies": current_cv.get("competencies", []),
        "experience":   [
            {
                "title":   job["title"],
                "dates":   job["dates"],
                "bullets": job.get("bullets", []),
            }
            for job in current_cv.get("experience", [])
        ],
    }

    schema = {
        "summary":      "string — poprawione podsumowanie / revised summary (max 900 znaków/chars)",
        "competencies": "list[string] — poprawiona lista kompetencji / revised competencies (max 14, total max 600 chars)",
        "experience": [
            {
                "title":   "string — BEZ ZMIAN z wejścia / UNCHANGED from input",
                "dates":   "string — BEZ ZMIAN z wejścia / UNCHANGED from input",
                "bullets": "list[string] — poprawione punkty / revised bullets, each max 200 chars",
            }
        ],
    }

    user_message = f"""
## OBECNA TREŚĆ CV TOMASZA UŚCIŃSKIEGO (do poprawy):
{json.dumps(cv_snapshot, ensure_ascii=False, indent=2)}

## OGŁOSZENIE (kontekst ATS):
{job_posting[:1500]}

## INSTRUKCJA UŻYTKOWNIKA:
{instruction}

## ZASADY (bezwzględne):
- NIE zmieniaj title ani dates w experience — skopiuj dokładnie z wejścia
- NIE dodawaj nowych stanowisk, firm, liczb ani osiągnięć których nie ma w wejściu
- NIE wymyślaj kompetencji ani doświadczeń spoza profilu bazowego
- Zastosuj instrukcję użytkownika do treści
- LIMITY: podsumowanie max 900 znaków, kompetencje łącznie max 600, każdy bullet max 200
- JĘZYK: {lang_rule}
- AKCENTY CV: {role_rule}
- ATS: zachowaj naturalną optymalizację ATS przez widoczne i wiarygodne słownictwo. Nie dodawaj ukrytych keywordów. Jeśli użytkownik prosi o keyword, którego profil bazowy nie potwierdza, pomin go lub użyj powiązanego wyrażenia bez twierdzenia o bezpośredniej ekspertyzie.
- Zwróć TYLKO poprawny JSON zgodny ze schematem poniżej:
{json.dumps(schema, ensure_ascii=False, indent=2)}
""".strip()

    response = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_completion_tokens=4000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    try:
        revised = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM zwrócił niepoprawny JSON: {exc}\n\nRaw:\n{raw}") from exc

    result = dict(current_cv)
    result["summary"]      = revised.get("summary", current_cv.get("summary", ""))
    result["competencies"] = revised.get("competencies", current_cv.get("competencies", []))
    result["experience"]   = _merge_experience(
        current_cv.get("experience", []),
        revised.get("experience", []),
    )
    # Preserve language, role and ATS strategy fields from current CV
    result.setdefault("job_language",           current_cv.get("job_language", "unknown"))
    result.setdefault("cv_output_language",     current_cv.get("cv_output_language", "pl"))
    result.setdefault("language_confidence",    current_cv.get("language_confidence", "low"))
    result.setdefault("role_type",              current_cv.get("role_type", "unknown"))
    result.setdefault("role_type_confidence",   current_cv.get("role_type_confidence", "low"))
    result.setdefault("role_type_reasoning",    current_cv.get("role_type_reasoning", ""))
    result.setdefault("cv_emphasis",            current_cv.get("cv_emphasis", []))
    result.setdefault("ats_keyword_strategy",   current_cv.get("ats_keyword_strategy", {
        "supported_keywords": [], "adjacent_keywords": [], "unsupported_keywords": [],
        "used_keywords": [], "excluded_keywords": [], "naturalness_notes": "",
    }))
    # Preserve or update experience_gap_analysis — if LLM returned one, validate it;
    # otherwise carry forward from current_cv
    if "experience_gap_analysis" in revised and isinstance(revised["experience_gap_analysis"], dict):
        result["experience_gap_analysis"] = _validate_gap_analysis(
            revised, result.get("cv_output_language", "pl")
        )
    else:
        result["experience_gap_analysis"] = current_cv.get("experience_gap_analysis",
            _validate_gap_analysis({}, result.get("cv_output_language", "pl")))
    return result
