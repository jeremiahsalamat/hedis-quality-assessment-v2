const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  LevelFormat, PageOrientation, ImageRun, PageBreak
} = require('docx');

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const cellBorders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 80, bottom: 80, left: 120, right: 120 };

const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const P  = (t) => new Paragraph({ children: [new TextRun(t)], spacing: { after: 120 } });
const Pbold = (b, t) => new Paragraph({
  children: [new TextRun({ text: b, bold: true }), new TextRun(t)],
  spacing: { after: 120 }
});
const Bullet = (t) => new Paragraph({
  numbering: { reference: "bullets", level: 0 },
  children: [new TextRun(t)]
});
const BulletBold = (b, t) => new Paragraph({
  numbering: { reference: "bullets", level: 0 },
  children: [new TextRun({ text: b, bold: true }), new TextRun(t)]
});
const Quote = (t) => new Paragraph({
  children: [new TextRun({ text: t, italics: true })],
  indent: { left: 480 },
  spacing: { before: 120, after: 120 },
  border: { left: { style: BorderStyle.SINGLE, size: 12, color: "5A7A9A", space: 8 } }
});
const Spacer = () => new Paragraph({ children: [new TextRun("")] });

function scorecardTable(headers, rows, colWidths) {
  const headerColor = "2D5F8B";
  const totalWidth = colWidths.reduce((a,b)=>a+b, 0);
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({
        tableHeader: true,
        children: headers.map((h, i) => new TableCell({
          borders: cellBorders, margins: cellMargins,
          width: { size: colWidths[i], type: WidthType.DXA },
          shading: { fill: headerColor, type: ShadingType.CLEAR },
          children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, color: "FFFFFF" })] })]
        }))
      }),
      ...rows.map(row => new TableRow({
        children: row.map((c, i) => new TableCell({
          borders: cellBorders, margins: cellMargins,
          width: { size: colWidths[i], type: WidthType.DXA },
          children: [new Paragraph({ children: [new TextRun(c)] })]
        }))
      }))
    ]
  });
}

const flowchartPng = fs.readFileSync('/home/claude/hedis_v2/diagrams/pipeline_flowchart.png');

const content = [
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "HEDIS Quality Assessment Project v2", bold: true, size: 40 })],
    spacing: { after: 120 }
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Interview Walkthrough & Speaking Guide", size: 28, color: "5A6A7A" })],
    spacing: { after: 240 }
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Prepared for the MedPOINT Management interview, Data Analyst, Quality Management Informatics", italics: true, color: "5A6A7A" })],
    spacing: { after: 360 }
  }),

  // SECTION 1: PITCH
  H1("1. The 90-second pitch"),
  Pbold("What to say if an interviewer opens with: ", "\"Walk me through this HEDIS project.\""),
  Spacer(),
  Quote("I built a HEDIS pipeline that calculates five measures, COL-E, CCS-E, CBP, EED, and AWV, from synthetic claims, pharmacy, and EHR data for a California IPA book of business. The dataset has 2,500 members spread across Commercial, Medi-Cal, Medicare Advantage, Medi-Medi, and Covered California, because that's the payer mix MedPOINT actually manages. Every ICD-10, CPT, HCPCS, and LOINC code in the value set table is a real NCQA code from the MY 2025 specifications, so the queries mirror what a real quality team would write. For each measure, I build the eligible population, apply the required exclusions, define the numerator from both the claims path and the ECDS lab-result path where applicable, and then stratify the rate by payer line. The output is a member-level gap list that a care coordinator could act on today."),
  Spacer(),
  P("Keep it conversational. Don't rush through it. Pause where the bolded concepts are, denominator, exclusions, numerator, ECDS, payer stratification. Those are the terms an interviewer listens for."),
  Spacer(),
  H3("On transparency about AI"),
  P("If they ask how the dataset was created, be direct. Say the data is synthetic, you designed it to mirror the structure of real IPA data (X12 claims, LOINC lab results, NCPDP pharmacy fills) with a payer mix that reflects MedPOINT's actual book, and you used Claude to accelerate the data generation so you could spend your time on what matters for learning: the measure logic, getting every NCQA code right, and nailing the denominator/exclusion/numerator pattern. The rates the queries produce landed within a few points of national HEDIS averages, which told you the data had the right shape. That's a strength, not something to hedge on."),

  // SECTION 2: WHY FIVE
  H1("2. Why these five measures"),
  P("A good answer shows judgment, not just knowledge. When asked why you picked these five, lead with the MedPOINT payer mix:"),
  Spacer(),
  scorecardTable(
    ["Measure", "Population", "Target Payer(s)", "Why it matters"],
    [
      ["COL-E", "Ages 45-75", "Commercial, Medi-Cal, MA", "Public-reported; FIT kits close the gap cheaply at scale"],
      ["CCS-E", "Women 21-64", "Commercial, Medi-Cal", "Medi-Cal and Commercial core measure; women's health equity focus"],
      ["CBP",   "Ages 18-85 w/ HTN", "All lines", "Medicare STARs triple-weighted; huge prevalence"],
      ["EED",   "Ages 18-75 w/ DM", "All lines", "Diabetes bundle measure; reported with HBD and BPD"],
      ["AWV",   "Ages 66+ MA/MMP", "Medicare Advantage", "Closes multiple HEDIS gaps in one visit; drives HCC coding"]
    ],
    [1400, 1700, 2400, 3600]
  ),
  Spacer(),
  Pbold("Key insight to drop: ", "\"The reason I chose this mix is that each measure hits a different part of MedPOINT's book. CBP stresses your Medicare Advantage population. COL-E and CCS-E are where the Medi-Cal gaps are biggest. EED is the diabetes bundle. And AWV is the visit type that lets your PCPs close multiple gaps in one encounter, which matters for an IPA because you're the ones on the hook when rates don't move.\""),

  // SECTION 3: -E
  H1("3. The \"-E\" suffix (what your cousin asked you to know)"),
  P("This is the single most important HEDIS concept to have crisp in an interview. It signals you understand where the industry is heading."),
  Spacer(),
  H2("Short answer"),
  P("The \"-E\" stands for ECDS, Electronic Clinical Data Systems. It's NCQA's reporting standard that lets plans count numerator events from structured EHR data (lab results via LOINC, HIE feeds, case management systems) instead of just claims."),
  Spacer(),
  H2("Why NCQA created it"),
  BulletBold("Claims-only is slow. ", "Chart review for the Hybrid Method is expensive. You're paying people to flip through medical records every spring."),
  BulletBold("EHR data is richer. ", "A pap smear happens in the chart and the lab long before it ever shows up in a claim. ECDS gives credit for it as soon as the data exists."),
  BulletBold("It's a multi-year transition. ", "NCQA has been moving measures to ECDS one at a time. COL went ECDS-only in MY 2024. CCS followed in MY 2025. NCQA has set a goal of removing the Hybrid method entirely by MY 2029."),
  Spacer(),
  H2("The five measures in this project, by reporting method"),
  scorecardTable(
    ["Measure", "Method", "Why"],
    [
      ["COL-E", "ECDS-only since MY 2024", "-E suffix; pulls from claims + lab results"],
      ["CCS-E", "ECDS-only since MY 2025", "-E suffix; formerly CCS"],
      ["CBP",   "Admin + Hybrid (MY 2025)", "Being replaced by new BPC-E measure (see below)"],
      ["EED",   "Admin only (Hybrid retired MY 2025)", "All events from claims/EHR structured data"],
      ["AWV",   "CMS billing measure", "Not NCQA-published; IPA operational measure"]
    ],
    [1600, 2800, 4700]
  ),
  Spacer(),
  H3("Advanced point to save for later in the interview"),
  P("In MY 2025, NCQA introduced a new measure called BPC-E (Blood Pressure Control for Patients with Hypertension). It's the ECDS replacement for CBP. BPC-E is meaningfully different from CBP in two ways. First, it expands the denominator: members with one hypertension diagnosis plus a dispensed antihypertensive in the prior year or first six months of the MY are now included, not just the \"2+ dx on different dates\" rule. Second, the representative BP logic changed. CBP uses the lowest systolic and lowest diastolic of the most recent day. BPC-E uses the most recent reading taken on that day. Both measures coexist in MY 2025 while plans transition. If you get asked about CBP during the interview, mentioning BPC-E shows you're tracking the spec updates."),
  Spacer(),
  Pbold("Gotcha to watch for: ", "an interviewer might ask whether EED has an \"-E\" because the name sounds similar. It does not. The E in EED stands for Eye Exam, not ECDS. EED is reported via the Administrative Method only (the Hybrid Method was retired in MY 2025)."),

  // SECTION 4: PIPELINE
  new Paragraph({ children: [new PageBreak()] }),
  H1("4. The pipeline (the flowchart your cousin asked for)"),
  P("This is the visual anchor of the interview. Have it open on screen or printed. Walk through it left-to-right, one stage at a time. Don't jump around."),
  Spacer(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new ImageRun({
      data: flowchartPng,
      transformation: { width: 600, height: 386 },
      type: 'png'
    })]
  }),
  Spacer(),
  H2("How to narrate the flowchart"),
  Pbold("Stage 1, Raw data sources. ", "Start here. \"In any IPA, raw data lands in a handful of standard formats. Claims come in as X12 837 transactions, the industry standard for claim submission, carrying ICD-10 diagnoses, CPT and HCPCS procedure codes, and place-of-service codes. EHR and HIE feeds carry vitals and lab results coded in LOINC. Pharmacy data comes in NCPDP format with NDC drug codes and days supply. Eligibility, X12 834, tells you who's enrolled, when, and on which payer line. The provider roster maps NPIs to specialties and PCP panels.\""),
  Spacer(),
  Pbold("Stage 2, Ingest and clean. ", "\"Before any measure logic runs, the data has to be trustworthy. You standardize identifiers so the same member ID links across claims, pharmacy, and EHR. You dedupe claims because plans send adjustments, voids, and replacements. You validate codes. An ICD-10 has a specific format, same for NDC. You handle nulls and missing data carefully. Then you load everything into a normalized database, in MedPOINT's case SQL Server, indexed on member_id so the joins are fast.\""),
  Spacer(),
  Pbold("Stage 3, HEDIS measure logic. ", "\"Every HEDIS measure follows the same four-step pattern. First, continuous enrollment. If a member wasn't enrolled for the measurement year, they don't count, period. Second, the eligible population: age, sex, and the clinical event criteria. For CBP that's two or more outpatient visits with a hypertension diagnosis. Third, required exclusions: hospice, palliative care, things like hysterectomy for CCS that make the measure not applicable. What's left is your denominator. Fourth, the numerator logic: did this member actually receive the appropriate service within the right window? Divide one by the other, multiply by 100, and you have the rate.\""),
  Spacer(),
  Pbold("Stage 4, Report and delivery. ", "\"Rates alone aren't useful. What's useful is the gap list, the member-level detail showing who should have had the service and didn't. That's what care coordinators reach out on. At MedPOINT, that output lives in Cozeva for provider-facing dashboards and gets submitted to health plans for P4P reports and STARs lookups. Then the action loop: outreach closes gaps, the pipeline re-runs, rates improve.\""),

  // SECTION 5: CBP DEEP DIVE
  H1("5. Walking through one measure, CBP"),
  P("If an interviewer asks you to go deeper on a specific measure, pick CBP. It has all the pieces: event criteria, exclusions, most-recent-reading logic, and a simple numerator."),
  Spacer(),
  H2("Denominator"),
  BulletBold("Age: ", "18 to 85 as of December 31 of the measurement year."),
  BulletBold("Event: ", "At least two outpatient, telehealth, or e-visit encounters on different dates of service with an ICD-10 diagnosis of I10 (essential hypertension), between January 1 of the year prior to the measurement year and June 30 of the measurement year."),
  BulletBold("Required exclusions: ", "Hospice or palliative care during the measurement year. Members who died during the year. Members 66+ with advanced illness and frailty, or in long-term care."),
  Spacer(),
  H2("Numerator"),
  BulletBold("Representative BP: ", "The most recent blood pressure reading during the measurement year."),
  BulletBold("Multiple readings same day: ", "Use the LOWEST systolic and LOWEST diastolic of that day. This is the part many new analysts miss."),
  BulletBold("Compliance threshold: ", "Both the systolic must be <140 mm Hg AND the diastolic must be <90 mm Hg."),
  BulletBold("No reading in MY: ", "Member is assumed NOT controlled. They count against you."),
  Spacer(),
  H2("SQL structure"),
  P("I built this as a chain of CTEs, a layered filter any analyst reviewing the code can follow in order. CTE one identifies HTN-diagnosed members using GROUP BY and HAVING with a DISTINCT service-date count. CTE two filters to the 18-85 age range. CTE three pulls hospice cases. CTE four applies the exclusions via LEFT JOIN with a NULL check, that's the anti-join pattern. Then I aggregate BP readings per day to get the lowest values, use the ROW_NUMBER window function to find the most recent reading, and finally apply the <140/90 threshold. The last SELECT uses UNION ALL to produce both the overall rate and the payer-stratified rates."),
  Spacer(),
  H2("The rate the project produces"),
  Pbold("61.78% overall. ", "That's right in line with published national averages. The Medicare population in the project hits 58.56%, slightly lower than Commercial, which tracks with what you'd see in a real book because MA members tend to be older with more resistant hypertension."),

  // SECTION 6: Q&A
  new Paragraph({ children: [new PageBreak()] }),
  H1("6. Likely questions and how to answer them"),
  Spacer(),
  H3("\"What's the difference between a HEDIS measure's denominator and its eligible population?\""),
  P("The eligible population is everyone who meets the age, sex, and event criteria before exclusions. The denominator is the eligible population minus the required exclusions. Hospice, hysterectomy for CCS, gestational-only diabetes for EED, those exclusions come out before you divide. If you skip this step, your rates will be artificially low because you're counting people the measure doesn't apply to."),
  Spacer(),
  H3("\"Why does CBP require two diagnoses on different dates?\""),
  P("Two reasons. Clinically, a single hypertension diagnosis could be a miscoded visit. Someone with elevated BP once isn't necessarily hypertensive. Requiring two dates is NCQA's way of filtering to members who actually have a sustained hypertension diagnosis. The \"different dates\" part is key. Two diagnoses on the same claim don't count."),
  Spacer(),
  H3("\"What happens if a member has no BP reading during the measurement year?\""),
  P("They fail the measure. NCQA's rule is: if there's no reading, assume the BP is not controlled. This is intentional. It penalizes plans for not engaging the member. It's also why outreach for BP-only visits is so important for IPAs."),
  Spacer(),
  H3("\"How would you handle a FIT test that shows up in lab results but not in claims?\""),
  P("That's the exact case ECDS was built for. Under COL-E, I can count a FIT result as a numerator event if the LOINC code matches the FOBT/FIT Result value set, even if no CPT 82274 ever appeared on a claim. In my project, the numerator CTE does a UNION between the procedure-claims path and the lab-results path. Without ECDS, an FQHC that captures the test in the EHR but doesn't bill for it would unfairly lose credit."),
  Spacer(),
  H3("\"Walk me through how you'd explain a drop in CBP rate to an IPA leadership team.\""),
  P("First, confirm the drop is real. Check the denominator. Did the HTN-diagnosed population grow? That expands the denominator faster than the numerator can catch up. Second, stratify. Is the drop uniform across payers, or concentrated in Medicare Advantage? Third, drill to the provider level. Are one or two PCP panels accounting for most of the decline? Fourth, look at the BP readings themselves. Are members being SEEN but the readings are running high, or are they not being seen at all? Each of those root causes triggers a different intervention: outreach for missed visits, clinical optimization for uncontrolled readings, or provider education for under-documentation."),
  Spacer(),
  H3("\"If you had to explain HEDIS to a friend outside healthcare, how would you?\""),
  P("HEDIS is basically a report card for health plans. It measures whether they're actually delivering care that the evidence says matters: screenings, diabetes management, blood pressure control. Every year, NCQA publishes the exact definitions, and every plan reports the same measures the same way. It's how we turn \"healthcare quality\" from a marketing phrase into something you can actually track."),
  Spacer(),

  // SECTION 7: STUCK
  H1("7. If you get stuck"),
  P("A few escape hatches that will make you look thoughtful, not flustered."),
  Spacer(),
  BulletBold("If asked about a measure you don't know: ", "\"I'd want to look at the NCQA technical specification to make sure I gave you a precise answer, but the general pattern of any HEDIS measure is the same. Define the eligible population, apply the required exclusions, and then check whether the numerator event happened within the right window. Could you tell me a bit more about the measure so I can think about which piece you're asking about?\""),
  BulletBold("If asked about a tool you don't know: ", "\"I haven't worked in that tool directly yet, but I know the underlying SQL and the HEDIS logic. I learned Cozeva's role in the pipeline from researching MedPOINT, and I'd expect to come up to speed quickly on whatever specific platform your team uses.\""),
  BulletBold("If asked about industry experience: ", "\"The quality pipeline I built is as close as I could get to the real thing without being inside an IPA. Where I'd still have to learn is the operational side: health plan relationships, audit prep, P4P contract specifics. That's exactly why this role appeals to me.\""),
  Spacer(),

  // SECTION 8: CLOSE
  H1("8. The humanitarian close"),
  P("When they ask why healthcare, or why MedPOINT specifically, don't lead with career transition logic. Lead with the patient."),
  Spacer(),
  Quote("Working in store operations taught me that systems only matter if they help real people. In healthcare, a HEDIS gap isn't a number. It's someone whose screening got missed, whose blood pressure never got checked, whose diabetes is silently doing damage. What drew me to MedPOINT is that you're the layer that actually closes those gaps. You manage almost a million Californians across the plans that cover our most vulnerable populations: Medi-Cal, Medi-Medi, Medicare Advantage. A data analyst on a quality team here gets to turn code into outreach, and outreach into a phone call that might save someone's life. That's work I'd be proud to do."),
  Spacer(),
  P("Don't memorize that word-for-word. Internalize the three beats: system thinking from your past, understanding of what MedPOINT actually does, and the human stakes. Say it in your own voice."),

  Spacer(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "End of Interview Walkthrough", italics: true, color: "7A8A9A" })],
    spacing: { before: 480 }
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Project repo: github.com/jeremiahsalamat/hedis-quality-assessment-v2", color: "7A8A9A", size: 20 })]
  })
];

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "1A3A5C" },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: "2D5F8B" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, italics: true, font: "Arial", color: "4A5A6A" },
        paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 } }
    ]
  },
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "\u2022",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } }
      }]
    }]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    children: content
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync('/home/claude/hedis_v2/docs/HEDIS_v2_Interview_Walkthrough.docx', buf);
  console.log('Document created.');
});
