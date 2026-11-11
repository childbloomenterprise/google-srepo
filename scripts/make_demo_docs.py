from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "app" / "demo"
WIDTH, HEIGHT = 1240, 1754
INK = (30, 40, 54)
BLUE = (29, 78, 121)
MUTED = (90, 100, 110)
BANNER = "SYNTHETIC DEMO DOCUMENT — not a real person or insurer"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    file = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    return ImageFont.truetype(file, size)


def create_page(case_id: str, index: int, title: str, lines: list[str]) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), (250, 248, 241))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((42, 42, WIDTH - 42, HEIGHT - 42), radius=20, outline=(180, 175, 160), width=3)
    draw.rectangle((68, 68, WIDTH - 68, 145), fill=(255, 236, 190))
    draw.text((90, 88), BANNER, font=font(27, bold=True), fill=(138, 46, 28))
    draw.text((90, 185), "CLAIMBACK • SYNTHETIC CASE FILE", font=font(22, bold=True), fill=BLUE)
    draw.line((90, 226, WIDTH - 90, 226), fill=(165, 174, 180), width=3)
    y = 270
    draw.text((90, y), title, font=font(40, bold=True), fill=INK)
    y += 82
    for line in lines:
        if line == "":
            y += 28
        elif line.startswith("## "):
            y += 18
            draw.text((90, y), line[3:], font=font(29, bold=True), fill=BLUE)
            y += 52
        else:
            draw.text((90, y), line, font=font(25), fill=INK)
            y += 43
    draw.line((90, HEIGHT - 160, WIDTH - 90, HEIGHT - 160), fill=(190, 190, 180), width=2)
    draw.text((90, HEIGHT - 132), f"Fictional training example • Page {index} of 3", font=font(20), fill=MUTED)

    # Simulate an imperfect phone photograph while keeping printed text legible.
    image = image.rotate(random.Random(index * 13).uniform(-0.65, 0.65), resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(226, 224, 216))
    pixels = image.load()
    rng = random.Random(index * 831)
    for _ in range(9000):
        x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
        r, g, b = pixels[x, y]
        delta = rng.choice((-2, -1, 1, 2))
        pixels[x, y] = (max(0, min(255, r + delta)), max(0, min(255, g + delta)), max(0, min(255, b + delta)))
    output = ROOT / case_id / f"{index:02d}-{title.lower().replace(' ', '-')}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)


PARTIAL_CUT = [
    (
        "Policy Schedule",
        [
            "SURAKSHA HEALTH INSURANCE CO. LTD. (fictional)",
            "Policyholder: Asha Kulkarni (fictional)",
            "Address: 22 Sample Lane, Pune, Maharashtra (fictional)",
            "Policy number: SHI-DEMO-2018-0421",
            "Product: Family Health Secure • Individual policy",
            "First policy start date: 01 April 2018",
            "Continuous renewal: No break in cover through 2026",
            "Eligible room category: Twin-sharing room",
            "Policy sum insured: ₹5,00,000",
            "",
            "Synthetic schedule prepared only for the ClaimBack demo.",
        ],
    ),
    (
        "Hospital Bill and Discharge Summary",
        [
            "SUNRISE MULTISPECIALITY HOSPITAL, PUNE (fictional)",
            "Patient: Asha Kulkarni • Admission: 18 Aug 2026",
            "Discharge: 22 Aug 2026 • Acute appendicitis",
            "Procedure: Laparoscopic appendectomy • ICU: 2 days",
            "Single room chosen by patient; twin-sharing is eligible.",
            "",
            "## Billed amount",
            "Room and hospital charges                         ₹ 62,400",
            "Pharmacy and consumables                         ₹ 72,000",
            "Diagnostics and laboratory                       ₹ 31,000",
            "ICU charges (2 days)                              ₹ 24,000",
            "Room-associated surgeon fee                      ₹ 20,000",
            "OT package incl. listed consumables               ₹ 5,050",
            "Other eligible treatment charges                  ₹ 4,000",
            "TOTAL CLAIMED                                    ₹ 2,18,450",
            "",
            "Discharge summary confirms appendectomy and ICU care.",
        ],
    ),
    (
        "Insurer Settlement Advice",
        [
            "SURAKSHA HEALTH INSURANCE CO. LTD. (fictional)",
            "Insured: Asha Kulkarni • Claim: SHI-CLM-2026-08218",
            "Claim type: Reimbursement • Submitted: 02 Sep 2026",
            "Decision date: 10 Oct 2026",
            "Amount claimed: ₹2,18,450 • Amount paid: ₹1,62,950",
            "",
            "## Deductions from settlement",
            "Proportionate deduction 30% — pharmacy & consumables ₹21,600",
            "Proportionate deduction 30% — diagnostics            ₹9,300",
            "Proportionate deduction 30% — ICU charges             ₹7,200",
            "Proportionate deduction 30% — room-associated surgeon ₹6,000",
            "Non-medical items (items billed inside OT package)     ₹4,800",
            "Room rent excess above eligible category               ₹6,600",
            "TOTAL DEDUCTED                                        ₹55,500",
            "",
            "The room-associated surgeon fee varies by room category.",
            "This settlement advice cites no additional policy clause.",
        ],
    ),
]

PED_REJECTION = [
    (
        "Policy Schedule",
        [
            "SURAKSHA HEALTH INSURANCE CO. LTD. (fictional)",
            "Policyholder: Kabir Deshmukh (fictional)",
            "Address: 9 Demo Park, Pune, Maharashtra (fictional)",
            "Policy number: SHI-DEMO-2019-0615",
            "Product: Family Health Secure • Individual policy",
            "First policy start date: 15 June 2019",
            "Continuous renewal: No break in cover through 2026",
            "Renewal history supplied to insurer for every year",
            "Sum insured: ₹5,00,000 • Claim sub-limit: None stated",
            "",
            "Synthetic schedule prepared only for the ClaimBack demo.",
        ],
    ),
    (
        "Hospital Bill and Discharge Summary",
        [
            "SUNRISE MULTISPECIALITY HOSPITAL, PUNE (fictional)",
            "Patient: Kabir Deshmukh • Admission: 20 Aug 2026",
            "Discharge: 24 Aug 2026",
            "Treatment: Acute gallbladder inflammation and surgery",
            "No diabetes diagnosis or treatment is recorded in this summary.",
            "",
            "## Hospital charges",
            "Surgery, room, investigations, medicines and treatment",
            "Total submitted claim amount: ₹3,40,000",
            "Hospital discharge summary and itemised bill enclosed.",
            "",
            "The policyholder reports no known diabetes before admission.",
        ],
    ),
    (
        "Insurer Rejection Letter",
        [
            "SURAKSHA HEALTH INSURANCE CO. LTD. (fictional)",
            "Insured: Kabir Deshmukh • Claim: SHI-CLM-2026-08110",
            "Cashless and reimbursement claim amount: ₹3,40,000",
            "Decision date: 05 Sep 2026 • Admission: 20 Aug 2026",
            "",
            "## Decision",
            "Your claim is rejected for non-disclosure of pre-existing diabetes.",
            "The claim is also not admissible due to delayed intimation.",
            "",
            "The above decision is as per policy terms and conditions.",
            "No specific policy clause is stated in this letter.",
            "No committee approval details are provided.",
            "",
            "No supporting evidence of a prior diabetes diagnosis is enclosed.",
        ],
    ),
]


def main() -> None:
    for case_id, pages in (("partial-cut", PARTIAL_CUT), ("ped-rejection", PED_REJECTION)):
        for index, (title, lines) in enumerate(pages, start=1):
            create_page(case_id, index, title, lines)


if __name__ == "__main__":
    main()
