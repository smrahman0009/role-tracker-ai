"""Tests for the contact-info extractor."""

from role_tracker.resume.extract import extract_contact_info

_TYPICAL_HEADER = """\
Shaikh Mushfikur Rahman
Halifax, NS · +1 (782) 882-0852 · smrahman0009@gmail.com
linkedin.com/in/shaikh-rahman · github.com/smrahman0009

PROFESSIONAL SUMMARY
Data scientist with five years building production ML systems...
"""


def test_extracts_email() -> None:
    c = extract_contact_info(_TYPICAL_HEADER)
    assert c.email == "smrahman0009@gmail.com"


def test_extracts_phone() -> None:
    c = extract_contact_info(_TYPICAL_HEADER)
    # Whatever surface form the resume used — we keep it as-is.
    assert "782" in c.phone and "0852" in c.phone


def test_extracts_linkedin() -> None:
    c = extract_contact_info(_TYPICAL_HEADER)
    assert c.linkedin_url == "https://linkedin.com/in/shaikh-rahman"


def test_extracts_github() -> None:
    c = extract_contact_info(_TYPICAL_HEADER)
    assert c.github_url == "https://github.com/smrahman0009"


def test_extracts_name_from_first_line() -> None:
    c = extract_contact_info(_TYPICAL_HEADER)
    assert c.name == "Shaikh Mushfikur Rahman"


def test_skips_section_headings_for_name() -> None:
    """A resume with no name line shouldn't return 'Professional Summary'."""
    text = (
        "PROFESSIONAL SUMMARY\n"
        "I'm a data scientist...\n"
    )
    c = extract_contact_info(text)
    assert c.name == ""


def test_handles_alternate_phone_formats() -> None:
    formats = [
        "Phone: 782-882-0852",
        "+44 20 7946 0958",
        "(902) 555-1234",
        "902.555.1234",
    ]
    for f in formats:
        c = extract_contact_info(f"Jane Doe\n{f}\njane@example.com\n")
        assert c.phone, f"Failed to extract from: {f}"


def test_does_not_match_year_as_phone() -> None:
    text = "Jane Doe\nGraduated 2024\njane@example.com\n"
    c = extract_contact_info(text)
    assert c.phone == ""


def test_does_not_match_room_number_as_phone() -> None:
    text = "Jane Doe\nRoom 304B\njane@example.com\n"
    c = extract_contact_info(text)
    assert c.phone == ""


def test_normalizes_linkedin_without_protocol() -> None:
    text = "Jane Doe\nlinkedin.com/in/jane-doe-12\n"
    c = extract_contact_info(text)
    assert c.linkedin_url.startswith("https://")


def test_extracts_https_linkedin_with_country_subdomain() -> None:
    text = "Jane Doe\nhttps://ca.linkedin.com/in/jane-doe\n"
    c = extract_contact_info(text)
    assert "ca.linkedin.com/in/jane-doe" in c.linkedin_url


def test_populated_fields_helper() -> None:
    c = extract_contact_info(_TYPICAL_HEADER)
    populated = c.populated_fields()
    assert "name" in populated
    assert "email" in populated
    assert "linkedin_url" in populated


def test_empty_resume_returns_all_blank() -> None:
    c = extract_contact_info("")
    assert c.populated_fields() == []


def test_resume_with_only_name() -> None:
    c = extract_contact_info("Jane Doe\n\nExperience...\n")
    assert c.name == "Jane Doe"
    assert c.email == ""
    assert c.phone == ""
