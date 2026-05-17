#!/usr/bin/env python3
"""
Generate the 30,000-token synthetic legal contract file.
Run once before the webinar.

Tries to use the Qwen2.5 tokenizer for accurate token counting.
Falls back to character-count estimation (~4 chars/token) if transformers unavailable.

Usage:
    python chapters/chapter2_noisy_neighbor/generate_contract.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

OUTPUT = Path(__file__).parent / "legal_contract_30k.txt"
TARGET_TOKENS = 30_000

PARTIES = [
    "NimbusAI Technologies Inc.", "GlobalStar Ventures LLC", "TechCorp Solutions Ltd.",
    "Meridian Data Group", "Apex Consulting Partners", "Quantum Systems Corp.",
]

CLAUSE_TEMPLATES = [
    "WHEREAS, {party1} (hereinafter \"Company\") and {party2} (hereinafter \"Client\") "
    "have entered into negotiations for the purposes of {purpose}; and",

    "NOW THEREFORE, in consideration of the mutual covenants and agreements contained herein, "
    "and for other good and valuable consideration, the receipt and sufficiency of which are "
    "hereby acknowledged, the parties agree as follows:",

    "Section {n}.{sub} Definitions. As used in this Agreement, the following terms shall have "
    "the meanings set forth below. \"{term}\" means {definition}. Any capitalized term not "
    "otherwise defined herein shall have the meaning ascribed to it in the applicable schedule.",

    "Section {n}.{sub} Representations and Warranties. Each party represents and warrants to "
    "the other that: (a) it has full power and authority to enter into this Agreement and to "
    "perform its obligations hereunder; (b) this Agreement has been duly authorized by all "
    "necessary corporate action; (c) this Agreement constitutes the legal, valid and binding "
    "obligation of such party, enforceable against it in accordance with its terms.",

    "Section {n}.{sub} Confidentiality. Each party agrees to maintain in strict confidence all "
    "Confidential Information disclosed by the other party. \"Confidential Information\" means "
    "any information that: (i) is marked as confidential or proprietary at the time of "
    "disclosure; (ii) is disclosed in circumstances where a reasonable person would understand "
    "it to be confidential; or (iii) relates to the disclosing party's business, technology, "
    "financial information, customer lists, trade secrets, or intellectual property.",

    "Section {n}.{sub} Limitation of Liability. IN NO EVENT SHALL EITHER PARTY BE LIABLE TO "
    "THE OTHER FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, "
    "INCLUDING WITHOUT LIMITATION LOSS OF PROFITS, LOSS OF REVENUE, LOSS OF DATA, BUSINESS "
    "INTERRUPTION, OR COST OF SUBSTITUTE SERVICES, EVEN IF SUCH PARTY HAS BEEN ADVISED OF "
    "THE POSSIBILITY OF SUCH DAMAGES. EACH PARTY'S TOTAL LIABILITY UNDER THIS AGREEMENT SHALL "
    "NOT EXCEED THE AMOUNTS PAID OR PAYABLE IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM.",

    "Section {n}.{sub} Indemnification. Each party (\"Indemnifying Party\") shall defend, "
    "indemnify, and hold harmless the other party (\"Indemnified Party\") and its officers, "
    "directors, employees, agents, successors, and assigns from and against any and all claims, "
    "damages, liabilities, costs, and expenses (including reasonable attorneys' fees) arising "
    "out of or resulting from: (a) the Indemnifying Party's breach of any representation, "
    "warranty, or obligation under this Agreement; (b) the Indemnifying Party's negligence or "
    "willful misconduct; or (c) any third-party claim that the Indemnifying Party's work "
    "product infringes any intellectual property right of such third party.",

    "Section {n}.{sub} Intellectual Property. All work product, inventions, discoveries, "
    "improvements, software, documentation, and other materials developed by either party in "
    "connection with this Agreement (collectively, \"Work Product\") shall be deemed works made "
    "for hire and shall be the exclusive property of the Company, to the extent permitted by "
    "applicable law. Each party hereby irrevocably assigns to the other all right, title, and "
    "interest in and to any Work Product that does not qualify as a work made for hire.",

    "Section {n}.{sub} Term and Termination. This Agreement shall commence on the Effective "
    "Date and shall continue for a period of {years} ({years_word}) years unless sooner "
    "terminated in accordance with this Section. Either party may terminate this Agreement: "
    "(a) upon {notice_days} ({notice_days_word}) days' prior written notice; (b) immediately, "
    "upon written notice, if the other party materially breaches any provision of this "
    "Agreement and such breach is not cured within thirty (30) days after written notice; or "
    "(c) immediately, if the other party becomes insolvent or files for bankruptcy protection.",

    "Section {n}.{sub} Dispute Resolution. The parties shall attempt to resolve any dispute "
    "arising out of or relating to this Agreement through good-faith negotiation for a period "
    "of not less than thirty (30) days. If the dispute cannot be resolved through negotiation, "
    "the parties agree to submit the dispute to binding arbitration administered by the "
    "American Arbitration Association under its Commercial Arbitration Rules. The arbitration "
    "shall be conducted in {city}, {state}, and the award shall be final and binding.",

    "Section {n}.{sub} Governing Law. This Agreement shall be governed by and construed in "
    "accordance with the laws of the State of {state}, without regard to its conflict of laws "
    "principles. The parties hereby consent to personal jurisdiction in {state} for purposes "
    "of enforcing this Agreement.",

    "Section {n}.{sub} Data Protection. Each party shall comply with all applicable data "
    "protection and privacy laws and regulations, including without limitation the General Data "
    "Protection Regulation (GDPR), the California Consumer Privacy Act (CCPA), and any other "
    "applicable privacy legislation. The parties shall implement appropriate technical and "
    "organizational measures to protect personal data against unauthorized access, disclosure, "
    "alteration, or destruction, including encryption, access controls, and regular security "
    "audits.",
]

PURPOSES = [
    "establishing a framework for enterprise software licensing",
    "providing managed cloud infrastructure services",
    "delivering professional consulting and advisory services",
    "developing and licensing artificial intelligence solutions",
    "providing data analytics and business intelligence services",
    "establishing a strategic technology partnership",
]

TERMS = [
    ("Service Level Agreement", "a written commitment to a specific level of service performance"),
    ("Uptime", "the percentage of time during which the Service is available and operational"),
    ("Processing Fee", "the fee charged per unit of computation consumed by the Client"),
    ("Data Residency", "the requirement that certain data must remain within a specified geography"),
    ("Force Majeure Event", "an event beyond a party's reasonable control including acts of God, war, pandemic, and natural disasters"),
    ("Authorized User", "any employee or contractor of Client who has been granted access credentials"),
]

CITIES = ["San Francisco", "New York", "Chicago", "Austin", "Seattle", "Boston"]
STATES = ["California", "New York", "Delaware", "Texas", "Washington", "Massachusetts"]


def generate_contract_text(rng: random.Random) -> str:
    lines = []
    party1, party2 = rng.sample(PARTIES, 2)
    purpose = rng.choice(PURPOSES)
    city = rng.choice(CITIES)
    state = rng.choice(STATES)

    lines.append("SERVICE AGREEMENT")
    lines.append(f"This Service Agreement (the \"Agreement\") is entered into as of the date")
    lines.append(f"last signed below (the \"Effective Date\") by and between:")
    lines.append(f"  {party1}, a Delaware corporation (\"Company\"), and")
    lines.append(f"  {party2}, a limited liability company (\"Client\").")
    lines.append("")

    section = 1
    while True:
        for sub, tmpl in enumerate(CLAUSE_TEMPLATES, 1):
            years = rng.randint(1, 5)
            years_word = ["one", "two", "three", "four", "five"][years - 1]
            notice_days = rng.choice([30, 60, 90])
            notice_days_word = {30: "thirty", 60: "sixty", 90: "ninety"}[notice_days]
            term_name, term_def = rng.choice(TERMS)
            text = tmpl.format(
                party1=party1, party2=party2, purpose=purpose,
                n=section, sub=sub, term=term_name, definition=term_def,
                years=years, years_word=years_word,
                notice_days=notice_days, notice_days_word=notice_days_word,
                city=city, state=state,
            )
            lines.append(text)
            lines.append("")
        section += 1
        # Check length periodically
        if section % 5 == 0:
            candidate = "\n".join(lines)
            if _token_count(candidate) >= TARGET_TOKENS:
                return candidate

    return "\n".join(lines)


def _token_count(text: str) -> int:
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
        return len(tok.encode(text))
    except Exception:
        return len(text) // 4  # rough fallback


def main() -> None:
    rng = random.Random(42)
    print(f"Generating ~{TARGET_TOKENS:,}-token synthetic legal contract...")

    text = generate_contract_text(rng)
    tokens = _token_count(text)
    print(f"Generated {len(text):,} chars ≈ {tokens:,} tokens")

    OUTPUT.write_text(text, encoding="utf-8")
    print(f"Saved to {OUTPUT}")

    if tokens < TARGET_TOKENS * 0.9:
        print(f"WARNING: token count ({tokens}) is below target ({TARGET_TOKENS}). Re-run may be needed.")
    elif tokens > TARGET_TOKENS * 1.1:
        print(f"Note: token count ({tokens}) is above target but that's fine for the demo.")


if __name__ == "__main__":
    main()
