"""Create a one-page English release summary. Requires reportlab."""
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'output/pdf/Camera41_exp_Summary_EN.pdf'
INK=colors.HexColor('#172d3a');BLUE=colors.HexColor('#246078')
styles={
 'title':ParagraphStyle('title',fontName='Helvetica-Bold',fontSize=24,leading=29,textColor=INK,spaceAfter=8),
 'author':ParagraphStyle('author',fontName='Helvetica-Bold',fontSize=11,leading=15,textColor=BLUE,spaceAfter=15),
 'h':ParagraphStyle('h',fontName='Helvetica-Bold',fontSize=12,leading=16,textColor=BLUE,spaceBefore=9,spaceAfter=5),
 'body':ParagraphStyle('body',fontName='Helvetica',fontSize=9.5,leading=12.5,textColor=INK,spaceAfter=7)}
def para(text,style):return Paragraph(escape(text).replace('\n','<br/>'),styles[style])
sections=[
 ('Why use Camera-41_exp?', 'Camera-41_exp helps set the digital camera exposure when digitising C-41 colour and black-and-white (B&W) film negatives with a VALOI setup. At a fixed aperture, it compares RAW captures of clear film base plus fog to find a shutter speed that gives a strong signal with room before clipping. Too much exposure can clip a sensor channel. Too little leaves a weak signal, making noise more visible when the scan is brightened.'),
 ('Workflow', '1. Open Camera-41_exp from Applications.\n2. Use Add FB+F RAWs… to load an exposure bracket of the same empty film sample.\n3. Enter Light setup and Film base + fog. Tick Same FB+F sample in all RAWs.\n4. Press Analyse RAW images and read Results and Exposure comparison.\n5. Verify the selected time with a fresh capture.'),
 ('Measurement area and results', 'The app normally uses the central 70% of image width and height. Unexpected structure triggers a yellow rectangle for inspection and manual adjustment. Preview brightness does not affect measurements.\nPASS: at least 1/3 EV margin in all Bayer channels and no failing fraction at/above the limit. LOW: weak channel signal. REVIEW: inspect the channel results. FAIL: too many values reach or exceed the limit. Read the channel report and check the film sample and area before changing shutter time.'),
 ('Optional dark noise', 'After exposure analysis, select a passing time in Choose a measured time and enable Evaluate dark noise (optional). Capture at least 2 independent capped-lens dark RAWs (8-16 recommended), with the same camera, ISO, time, aperture and similar temperature. Disable long-exposure noise reduction. Use Add dark RAWs… then Evaluate noise. Dark noise shows S/N and noise-limited bits per channel. S/N excludes photon shot noise; effective range bits are not ADC ENOB. See the handbook for definitions. PRE and NEG remain independent; no JSON is transferred.'),
 ('Installation, startup and log', 'Open Camera-41_exp-1.1.0-python-macos.dmg. Drag the Apple Silicon app to Applications on an M-series Mac, or choose the Intel app for an Intel Mac. Add your own film-base RAWs with Add FB+F RAWs…. Open log shows the local diagnostic log. Quit the app before replacing it.')]

story=[para('Camera-41_exp v1.1.0','title'),para('Christer Törnkvist | Summary','author')]
for h,b in sections:story.extend([para(h,'h'),para(b,'body')])
def footer(c,doc):
 w,h=A4;c.setStrokeColor(colors.HexColor('#d6e1e5'));c.line(54,65,w-54,65);c.setFillColor(BLUE);c.setFont('Helvetica',9)
 email='christer@borgasundsfotografiska.se';url='https://github.com/chto0703009/Camera-41_exp'
 c.drawString(54,49,email);c.linkURL('mailto:'+email,(54,47,54+c.stringWidth(email,'Helvetica',9),59))
 c.drawString(54,35,url);c.linkURL(url,(54,33,54+c.stringWidth(url,'Helvetica',9),45));c.setFont('Helvetica',8);c.drawString(54,20,'v1.1.0 | 22 November 2026 | GPL-3.0-or-later')
SimpleDocTemplate(str(FILE),pagesize=A4,leftMargin=54,rightMargin=54,topMargin=48,bottomMargin=80,
 title='Camera-41_exp v1.1.0 - Summary',author='Christer Törnkvist').build(story,onFirstPage=footer,onLaterPages=footer)
print(FILE)
