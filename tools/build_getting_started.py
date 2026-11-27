"""Build the one-page English getting-started guide. Requires reportlab and pypdf."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'output/pdf/FilmScan_Tuner_Getting_Started_EN.pdf'
VERSION = (ROOT / 'VERSION').read_text().strip()
BLUE = colors.HexColor('#246078')
INK = colors.HexColor('#172d3a')
PALE = colors.HexColor('#edf4f6')
STYLE = {
    'brand': ParagraphStyle('brand', fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=BLUE),
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=28, leading=33, textColor=INK, spaceAfter=6),
    'subtitle': ParagraphStyle('subtitle', fontName='Helvetica', fontSize=10.5, leading=14, textColor=BLUE, spaceAfter=10),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10, leading=13.5, textColor=INK),
    'heading': ParagraphStyle('heading', fontName='Helvetica-Bold', fontSize=11.5, leading=15, textColor=INK, spaceAfter=3),
    'number': ParagraphStyle('number', fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=BLUE),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=9, leading=12, textColor=INK),
}


def p(text, kind='body'):
    return Paragraph(text, STYLE[kind])


def step(number, title, text):
    table = Table([[p(str(number), 'number'), [p(title, 'heading'), p(text)]]], colWidths=[30, 457])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 11),
    ]))
    return table


def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor('#d6e1e5'))
    canvas.line(54, 63, A4[0] - 54, 63)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(BLUE)
    url = 'https://github.com/chto0703009/FilmScan-Tuner'
    canvas.drawString(54, 47, url)
    canvas.linkURL(url, (54, 45, 54 + canvas.stringWidth(url, 'Helvetica', 8), 57))
    canvas.drawString(54, 33, f'v{VERSION} | English | Christer Törnkvist | 27 November 2026')
    canvas.drawRightString(A4[0] - 54, 33, '1 / 1')


story = [p('FilmScan Tuner', 'brand'), p('Getting started', 'title'),
         p('Exposure and noise evaluation for camera scanning.', 'subtitle'),
         p('Set your digital camera exposure for scanning C-41 colour or black-and-white negatives using VALOI hardware with a CS Light light table, or another camera-scanning setup. The app is not limited to VALOI or CS Light; you set the camera yourself.'), Spacer(1, 14)]
story += [
    step(1, 'Install and open',
         'Open the DMG and drag the app for your Mac to <b>Applications</b>: Apple Silicon (macOS 14+) or Intel (macOS 13+). Eject the DMG, then open FilmScan Tuner. Python and LibRaw are included; MATLAB is not required.'),
    step(2, 'Photograph clear film base plus fog (FB+F)',
         'Use a clear, developed, unexposed area from the film being scanned, with no scene, lettering, perforations or holder edge in the measurement area. Keep camera, ISO, aperture, lighting and geometry fixed. Change only shutter time, in 1/3-stop steps. Capture at least three times spanning one stop; for example <b>1/20, 1/15, 1/10 and 1/8 s</b>. Save original RAW files.'),
    step(3, 'Add the bracket and describe the sample',
         'Click <b>Add FB+F RAWs…</b> and select the bracket. Fill in <b>Light setup</b> (for example, your light and brightness setting) and <b>Film base + fog</b> (for example, Gold 200, clear area from this roll). Tick <b>Same FB+F sample in all RAWs</b>. Leave <b>Automatic area</b> enabled.'),
    step(4, 'Analyse and choose an exposure',
         'Click <b>Analyse RAW images</b> and wait for completion. <b>Exposure comparison</b> opens with the recommended or provisional shutter time and marks clipping. See <b>Results</b> for details. Inspect any area warning in <b>RAW preview</b> and adjust the yellow rectangle over clean film if needed, then analyse again. <b>PASS</b> meets the exposure criteria; <b>LOW</b> means weak signal; <b>REVIEW / FAIL</b> need attention. Resolve proportionality warnings before using a candidate. Add further test exposures if requested.'),
    step(5, 'Set the camera and verify',
         'Select a passing time in <b>Choose a measured time</b>. Set that time on the camera and take a fresh FB+F capture to verify it. The example bracket above is not a universal exposure recommendation. Repeat the evaluation when film base, ISO, aperture or lighting changes.'),
    step(6, 'Optional: evaluate dark noise at the chosen time',
         'Click <b>Evaluate dark noise</b>. Take at least <b>2 independent dark RAWs</b> (8-16 recommended) with the lens capped, matching camera, ISO, shutter time and aperture, at similar sensor temperature. Disable long-exposure noise reduction. Click <b>Add dark RAWs…</b>, then <b>Evaluate noise</b>. See noise, signal and clipping together on a log scale in <b>Exposure comparison</b>. <b>Dark noise</b> gives S/N and bit estimates.'),
]
note = Table([[p('<b>Understand the noise result.</b> S/N uses temporal dark noise and excludes photon shot noise. Effective range bits describe noise-limited range; they are not ADC ENOB or nominal camera bit depth. See the handbook for definitions. Original RAW files are unchanged.', 'small')]], colWidths=[487])
note.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), PALE), ('BOX', (0, 0), (-1, -1), .5, colors.HexColor('#d6e1e5')), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
story.append(note)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=54, rightMargin=54,
                  topMargin=39, bottomMargin=77, title='FilmScan Tuner - Getting started',
                  author='Christer Törnkvist', subject='Exposure and noise evaluation for camera scanning.').build(story, onFirstPage=footer, onLaterPages=footer)
assert len(PdfReader(OUTPUT).pages) == 1, 'Getting started must fit on one page.'
print(OUTPUT)
