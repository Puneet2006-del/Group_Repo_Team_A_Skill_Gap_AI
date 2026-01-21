import streamlit as st
import re
import pdfplumber
import docx
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from fpdf import FPDF
import pandas as pd

st.markdown("""
    <style>
        .stProgress > div > div > div {
            background-color: var(--bar-color) !important;
        }
    </style>
""", unsafe_allow_html=True)

# ================= UTILS =================

def normalize_skill(skill):
    return skill.lower().strip()
SOFT_SKILL_SYNONYMS = {
    "communication": [
        "communication", "verbal communication", "written communication"
    ],
    "teamwork": ["teamwork", "team player", "collaboration"],
    "problem solving": ["problem solving", "analytical thinking"],
    "quick learner": ["quick learner", "fast learner", "self learner"],
    "hardworking": ["hardworking", "work ethic"],
    "time management": ["time management"],
    "adaptability": ["adaptability", "flexibility"],
}

def get_soft_skill_status(jd_skill, resume_skills):
    jd_norm = normalize_skill(jd_skill)

    # 1️⃣ Exact match
    for r in resume_skills:
        if normalize_skill(r) == jd_norm:
            return "exact"

    # 2️⃣ Synonym-based partial match ONLY
    if jd_norm in SOFT_SKILL_SYNONYMS:
        for r in resume_skills:
            if normalize_skill(r) in SOFT_SKILL_SYNONYMS[jd_norm]:
                return "partial"

    # 3️⃣ Otherwise missing
    return "missing"

SYNONYM_MAP = {
    "machine learning": [
        "machine learning",
        "basic machine learning concepts",
        "ml",
        "machine learning basics"
    ],
    "data visualization": [
        "data visualization",
        "visualization",
        "matplotlib",
        "power bi",
        "powerbi",
        "tableau",
        "data viz",
        "visualisation"
    ],
    "sql": [
        "sql",
        "database querying",
        "dbms",
        "database management",
        "sql programming"
    ],
    "python": [
        "python",
        "python programming",
        "python programmer",
        "numpy",
        "pandas",
        "matplotlib",
        "scikit-learn"
    ],
    "excel": [
        "excel",
        "microsoft excel",
        "ms excel",
        "advanced excel",
        "excal"  # fix your typo case
    ],
    "data analysis": [
        "data analysis",
        "data analytics",
        "data interpretation",
        "analyzing data",
        "data analyst"
    ]
}

def build_synonym_lookup():
    lookup = {}
    for canonical, variants in SYNONYM_MAP.items():
        for v in variants:
            lookup[v] = canonical
    return lookup

SYNONYM_LOOKUP = build_synonym_lookup()

# 🔥 REPLACE OLD FUNCTION WITH THIS
def get_match_status(jd_skill, resume_skills):
    jd_norm = normalize_skill(jd_skill)

    # 1️⃣ Exact match (STRICT)
    for r in resume_skills:
        if normalize_skill(r) == jd_norm:
            return "exact"

    # 2️⃣ Controlled partial match via synonyms ONLY
    for canonical, variants in SYNONYM_MAP.items():
        if jd_norm in variants:
            for r in resume_skills:
                r_norm = normalize_skill(r)
                if r_norm == canonical or r_norm in variants:
                    return "partial"

    # 3️⃣ Truly missing
    return "missing"

# ================= UTILS =================

def clean_text(text):
    """Clean extracted text from PDF/DOCX files - PRESERVE URLs"""
    # Remove cid patterns
    text = re.sub(r'\$cid[:]*\d+\$', '', text, flags=re.IGNORECASE)
    
    # Fix camelCase spacing
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    
    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()
def detect_sections(text):
    sections = {}
    current_section = "general"
    sections[current_section] = []

    for line in text.split("\n"):
        line_strip = line.strip().upper()

        # Detect headings
        if line_strip in [
            "TECHNICAL SKILLS",
            "SKILLS",
            "TECHNICAL SKILLS:",
            "EDUCATIONAL QUALIFICATION",
            "PROJECT",
            "CAREER OBJECTIVE"
        ]:
            current_section = line_strip.replace(":", "")
            sections[current_section] = []
        else:
            sections[current_section].append(line)

    return sections

def extract_text(file):
    """Extract text from uploaded file"""
    if file.type == "application/pdf":
        text = ""
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(layout=True)
                if page_text:
                    text += page_text + "\n"
        return text
    elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = docx.Document(file)
        text = "\n".join([para.text for para in doc.paragraphs])
        
        # 🔥 Normalize bullets & symbols
        text = re.sub(r"[•▪●◦–—]", " ", text)
        return text
    elif file.type == "text/plain":
        return file.read().decode("utf-8")
    return ""

def extract_name_and_linkedin(text):
    """Extract candidate name and LinkedIn URL from resume text - returns tuple (name, linkedin_url)"""
    name = "Candidate"
    linkedin_url = ""
    
    # ===== 1. FIRST: Look for LinkedIn URL =====
    # Strategy 1: Look for Markdown format [text](url)
    markdown_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    markdown_matches = re.findall(markdown_pattern, text)
    
    for link_text, url in markdown_matches:
        if 'linkedin.com' in url.lower():
            linkedin_url = url
            break
        elif 'linkedin.com' in link_text.lower():
            linkedin_url = link_text
            break
    
    # Strategy 2: Look for "LinkedIn:" followed by URL
    if not linkedin_url:
        linkedin_label_pattern = r'LinkedIn[:]?\s*([^\s]+)'
        match = re.search(linkedin_label_pattern, text, re.IGNORECASE)
        if match:
            potential_url = match.group(1)
            if 'linkedin.com' in potential_url.lower():
                linkedin_url = potential_url
    
    # Strategy 3: Look for any LinkedIn URL in text
    if not linkedin_url:
        linkedin_url_patterns = [
            r'(https?://(?:www\.)?linkedin\.com/[^\s]+)',
            r'(www\.linkedin\.com/[^\s]+)',
            r'(linkedin\.com/[^\s]+)',
        ]
        
        for pattern in linkedin_url_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                linkedin_url = match.group(1)
                break
    
    # Clean the LinkedIn URL if found
    if linkedin_url:
        linkedin_url = linkedin_url.strip()
        # Remove any trailing punctuation
        linkedin_url = re.sub(r'[.,;:)\]]+$', '', linkedin_url)
        # Ensure proper protocol
        if not linkedin_url.startswith('http'):
            if linkedin_url.startswith('www.'):
                linkedin_url = 'https://' + linkedin_url
            elif linkedin_url.startswith('linkedin.com'):
                linkedin_url = 'https://www.' + linkedin_url
    
    # ===== 2. SECOND: Look for Name =====
    # Try to find name from the text
    lines = text.split('\n')
    
    # Pattern 1: Look for name in first few lines (most resumes have name at top)
    for line in lines[:10]:
        line = line.strip()
        if line:
            # Remove common prefixes/suffixes
            clean_line = re.sub(r'^[#\*\s]+|[#\*\s]+$', '', line)
            words = clean_line.split()
            
            # Check if it looks like a name (2-4 words, capitalized)
            if 2 <= len(words) <= 4:
                capitalized_words = sum(1 for w in words if w and w[0].isupper())
                if capitalized_words >= len(words) - 1:
                    # Make sure it's not a URL or other metadata
                    if not any(x in line.lower() for x in ['@', 'http', '://', 'www.', 'linkedin', 'phone', 'mobile']):
                        name = clean_line
                        break
    
    # Pattern 2: Look for "Name:" pattern
    if name == "Candidate":
        for line in lines:
            name_match = re.search(r'Name[:]?\s*([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)+)', line, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).strip()
                break
    
    # Pattern 3: Extract from email if present
    if name == "Candidate":
        email_match = re.search(r'([a-zA-Z0-9._%+-]+)@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        if email_match:
            email_local = email_match.group(1)
            if '.' in email_local:
                name_parts = email_local.split('.')
                name_parts = [p for p in name_parts if p and not p.isdigit()]
                if len(name_parts) >= 2:
                    name = ' '.join([p.title() for p in name_parts[:2]])
    
    return name, linkedin_url

def extract_professional_summary(text):
    """
    Extract the FULL professional summary exactly as written in the resume.
    Handles inline + multi-line summaries.
    """

    text = re.sub(r"\n{2,}", "\n", text)
    lines = text.split("\n")

    START_HEADERS = [
        "PROFESSIONAL SUMMARY",
        "SUMMARY",
        "CAREER OBJECTIVE",
        "OBJECTIVE",
        "PROFILE",
        "ABOUT ME"
    ]
    
    TOP_HEADERS = [
    "TECHNICAL SKILLS",
    "SOFT SKILLS",
    "SKILLS",
    "PROJECTS",
    "EDUCATION",
    "EXPERIENCE",
    "CERTIFICATIONS",
    "ACHIEVEMENTS"
]

    def detect_sections(text):
        sections = {}
        current_section = "GENERAL"
        sections[current_section] = []

        for line in text.split("\n"):
            line_strip = line.strip().upper().rstrip(":")

            if line_strip in TOP_HEADERS:
                current_section = line_strip
                sections[current_section] = []
            else:
                sections[current_section].append(line)

        return sections



    collected = []
    capturing = False

    for line in lines:
        clean = line.strip()
        upper = clean.upper()

        # Start capture
        for header in START_HEADERS:
            if upper.startswith(header):
                capturing = True

                # Handle inline summary
                inline = clean[len(header):].strip(" :-")
                if inline:
                    collected.append(inline)
                break
        else:
            if capturing:
                # Stop when next section starts
                if any(upper.startswith(h) for h in TOP_HEADERS):
                    break

                if clean:
                    collected.append(clean)

    summary = " ".join(collected).strip()

    if len(summary) >= 30:
        return summary

    return "Professional summary not clearly specified in the resume."

# ================= COMPREHENSIVE SKILL LISTS =================

TECHNICAL_SKILLS = [
    
    # Add these for Data Analyst JD
    "Data Analysis",
    "Data Interpretation",
    "Microsoft Excel",
    "MS Excel",
    "Advanced Excel",
    "Data Visualization",
    "Matplotlib",
    "Power BI",
    "Database Querying",
    "DBMS",
    
    # Core Programming & Embedded
    "Python", "Numpy", "Pandas", "Num Py", "Embedded C", "C", "C++", "Java", "JavaScript",
    "Embedded Systems", "Microcontroller", "Microcontroller Programming", "Machine Learning","Deep Learning",
    "Arduino", "Arduino Nano", "Arduino Uno", "Raspberry Pi", "ESP32", "ESP8266",

    # Specific Microcontrollers & Tools
    "8051 Microcontroller", "8051", "PIC Microcontroller", "AVR",
    "Keil", "Keil uVision", "MPLAB", "Proteus", "Proteus Simulation",

    #Machine Learing & Deep Learning
    "Machine Learing", "Deep Learing", "NLP", "Streamlit",
    
    #Front-end 
    "HTML", "CSS", "React", "Nodejs",
        
    # Protocols & Interfacing
    "I2C", "SPI", "UART", "GPIO", "ADC", "DAC",
    "Sensor Interfacing", "Actuator", "Relay", "LCD", "LED",
    "IR Sensor", "IR Sensors", "Ultrasonic Sensor", "LM35",

    # HDL & FPGA
    "Verilog HDL", "Verilog", "VHDL", "FPGA",

    # Data & Other Tools
    "SQL", "MySQL", "Excel", "MATLAB", "Simulink",
    "Internet of Things", "IoT", "GSM", "Bluetooth", "WiFi Module",

    # General Technical
    "Data Structures", "Algorithms", "OOP", "Git", "GitHub",
    "Circuit Design", "PCB Design", "Firmware Development",
    "RTOS", "Embedded Linux"
]

SOFT_SKILLS = [
    "Communication", "Verbal Communication", "Written Communication",
    "Teamwork", "Collaboration", "Leadership",
    "Problem Solving", "Critical Thinking", "Analytical Thinking",
    "Time Management", "Adaptability", "Flexibility",
    "Quick Learner", "Fast Learner", "Self Learner", "Eager to Learn",
    "Hardworking", "Work Ethic", "Dedication",
    "Active Listening", "Interpersonal Skills",
    "Presentation Skills", "Documentation"
]

def extract_additional_technical_terms(text):
    """
    Extract unknown technical terms (order preserved)
    Example: Arduino Nano, 8051, LM35, IR Sensor
    """
    results = []
    seen = set()

    lines = text.split("\n")
    for line in lines:
        # Only scan technical sections
        if any(k in line.lower() for k in ["technical", "skills", "tools", "technologies", "hardware"]):
            tokens = re.findall(r'\b[A-Z][A-Za-z0-9\-]{2,}\b', line)
            for t in tokens:
                key = t.lower()
                if key not in seen:
                    seen.add(key)
                    results.append(t)

    return results

def extract_skills(text):
    """
    Improved skill extraction:
    - Technical skills: searched in whole resume
    - Soft skills: searched ONLY after 'Soft Skills' heading (prevents leakage from degree names)
    - Basic false-positive filtering
    """
    skills = []
    seen = set()
    full_text_lower = text.lower()

    # ─── Try to isolate soft skills section to avoid false positives ───
    soft_section_text = full_text_lower
    if "soft skills" in full_text_lower:
        parts = full_text_lower.split("soft skills", 1)
        if len(parts) > 1:
            # Take text after "soft skills" until next major section or ~2000 chars
            remaining = parts[1]
            cutoff_phrases = ["education", "projects", "experience", "certification", "hobbies", "declaration"]
            for phrase in cutoff_phrases:
                if phrase in remaining:
                    remaining = remaining.split(phrase, 1)[0]
            soft_section_text = remaining[:2000]  # safety limit

    # 1. Technical skills – whole document
    for skill in TECHNICAL_SKILLS:
        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        if re.search(pattern, full_text_lower):
            key = skill.lower()
            if key not in seen:
                skills.append({"name": skill, "type": "Technical", "confidence": 92})
                seen.add(key)

    # 2. Soft skills – only in soft section (or fallback to whole text if no section found)
    for skill in SOFT_SKILLS:
        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        if re.search(pattern, soft_section_text):
            key = skill.lower()
            if key not in seen:
                skills.append({"name": skill, "type": "Soft", "confidence": 88})
                seen.add(key)

    # ─── Simple post-filters to remove common false positives ───
    # Post-filters - remove obvious false positives
    filtered_skills = []
    has_embedded_c = any("embedded c" in s["name"].lower() for s in skills)

    for s in skills:
        name_lower = s["name"].lower().strip()

        # Skip plain "C" when Embedded C exists
        if name_lower in ["c", "c programming", "c language"] and has_embedded_c:
            continue

        # Optional: skip very generic terms if you want
        if name_lower in ["sensor", "sensors"]:
            continue  # if you don't want generic "Sensor"

        filtered_skills.append(s)

    return filtered_skills

def normalize_and_merge_skills(skills_list):
    """
    Merge very similar / variant skill names into one canonical name.
    This prevents duplicates like 'Arduino' + 'Arduino Nano'.
    Expand the merge_rules dict as you see more real resumes.
    """
    # Define groups: "canonical_key": [possible variant substrings or exact names]
    merge_rules = {
        "arduino nano": ["arduino nano", "arduino", "nano", "arduino uno", "arduino-nano"],
        "8051 microcontroller": ["8051", "8051 microcontroller", "8051 micro controller"],
        "microcontroller": ["microcontroller", "microcontrollers", "mcu"],
        "ir sensor": ["ir sensor", "ir sensors", "ir blink sensor", "eye blink sensor", "ir eye sensor"],
        "microsoft excel": ["microsoft excel", "ms excel", "excel", "advanced excel"],
        "verilog hdl": ["verilog hdl", "verilog", "hdl", "veriloghdl"],
        "embedded c": ["embedded c", "embedded c programming", "c (embedded)"],
        # You can add more rules here later
    }

    canonical_map = {}

    for skill in skills_list:
        name_lower = skill["name"].lower().strip().replace("-", " ")

        found = False
        for canon_key, variants in merge_rules.items():
            if any(v in name_lower for v in variants) or name_lower == canon_key:
                display_name = canon_key.title()  # Use clean canonical name
                if canon_key not in canonical_map or skill["confidence"] > canonical_map[canon_key]["confidence"]:
                    canonical_map[canon_key] = {
                        "name": display_name,
                        "type": skill["type"],
                        "confidence": max(skill["confidence"], canonical_map.get(canon_key, {}).get("confidence", 0))
                    }
                found = True
                break

        if not found:
            key = name_lower
            if key not in canonical_map or skill["confidence"] > canonical_map[key]["confidence"]:
                canonical_map[key] = skill

    # Return sorted list: Technical first, then Soft
    merged = list(canonical_map.values())
    tech = sorted([s for s in merged if s["type"] == "Technical"], key=lambda x: x["name"].lower())
    soft = sorted([s for s in merged if s["type"] == "Soft"], key=lambda x: x["name"].lower())
    
    return tech + soft  # ← This is the final return — nothing after this!

def skill_distribution_chart(tech, soft):
    """Create skill distribution pie chart"""
    fig, ax = plt.subplots(figsize=(3, 3))
    if tech + soft > 0:
        ax.pie(
            [tech, soft],
            labels=["Technical Skills", "Soft Skills"],
            startangle=90,
            wedgeprops=dict(width=0.4),
            colors=['#4CAF50', '#2196F3']
        )
    else:
        ax.text(0.5, 0.5, 'No Skills\nFound', ha='center', va='center', fontsize=12)
    ax.axis("equal")
    return fig

def display_skill(skill):
    skill = skill.strip()
    lower = skill.lower()
    
    if lower == "sql":
        return "SQL"
    if "verilog" in lower:
        return "Verilog HDL"
    if "ir " in lower or "ir sensor" in lower:
        return "IR Sensor"
    if "embedded c" in lower:
        return "Embedded C"
    if lower == "c":
        return "C"  # But filter should remove it
    
    return skill.title()

# ================= MAIN APP =================

st.set_page_config(
    page_title="Skill Gap AI Analyzer",
    layout="wide"
)

st.markdown(
    """
    <div style="background-color:#3f51b5;padding:15px;border-radius:6px">
        <h2 style="color:white;">Skill Gap AI: Resume and Job Description Analyzer</h2>
        <p style="color:white;">
        Data Ingestion & Parsing · Skill Extraction · Gap Analysis · Dashboard & Reports
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

# File Upload
col1, col2 = st.columns(2)

with col1:
    st.subheader("📤 Upload Resume")
    resume_file = st.file_uploader(
        "Choose a resume file",
        type=["pdf", "docx", "txt"],
        key="resume"
    )

with col2:
    st.subheader("📤 Upload Job Description")
    jd_file = st.file_uploader(
        "Choose a job description file",
        type=["pdf", "docx", "txt"],
        key="jd"
    )

if resume_file and jd_file:
    # Milestone 1: Data Ingestion & Parsing
    st.markdown("## Milestone 1: Data Ingestion & Parsing")

    # ────────────────────────────────────────────────────────────────
    # SAFE FILE READING WITH ERROR HANDLING
    # ────────────────────────────────────────────────────────────────
    resume_text = ""
    jd_text = ""

    # Read Resume
    try:
        resume_text = extract_text(resume_file)
        resume_text = clean_text(resume_text)
    except Exception as e:
        st.error(f"Failed to read resume file: {str(e)}")
        resume_text = ""

    # Read Job Description
    try:
        jd_text = extract_text(jd_file)
        jd_text = clean_text(jd_text)
    except Exception as e:
        st.error(f"Failed to read job description file: {str(e)}")
        jd_text = ""

    # User-friendly feedback if reading failed
    if not resume_text and not jd_text:
        st.warning("⚠️ Could not read content from either file. Please check file format and try again.")
    elif not resume_text:
        st.warning("⚠️ Could not read the resume file. Preview and analysis will be limited.")
    elif not jd_text:
        st.warning("⚠️ Could not read the job description file. Gap analysis may be incomplete.")

    # ────────────────────────────────────────────────────────────────
    # Show previews only if we have at least some content
    # ────────────────────────────────────────────────────────────────
    if resume_text or jd_text:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Resume Preview**")
            if resume_text:
                st.text_area(
                    "",
                    resume_text,
                    height=400,
                    label_visibility="collapsed",
                    key="resume_preview"
                )
            else:
                st.info("Resume content could not be loaded.")

        with col2:
            st.markdown("**Job Description Preview**")
            if jd_text:
                st.text_area(
                    "",
                    jd_text,
                    height=400,
                    label_visibility="collapsed",
                    key="jd_preview"
                )
            else:
                st.info("Job Description content could not be loaded.")

    # Milestone 2: Skill Extraction
    st.markdown("## Milestone 2: Skill Extraction using NLP")
    # Milestone 2: Skill Extraction using NLP
    resume_skills_raw = extract_skills(resume_text)
    resume_skills = normalize_and_merge_skills(resume_skills_raw)

    jd_skills_raw = extract_skills(jd_text)
    jd_skills = normalize_and_merge_skills(jd_skills_raw)   # also merge for JD (good practice)


    tech_resume = [s for s in resume_skills if s["type"] == "Technical"]
    soft_resume = [s for s in resume_skills if s["type"] == "Soft"]
    tech_jd = [s for s in jd_skills if s["type"] == "Technical"]
    soft_jd = [s for s in jd_skills if s["type"] == "Soft"]

    col1, col2 = st.columns([2.5, 1])

    with col1:
        # Resume Skills Section
        # Inside the Milestone 2 section of your App:
        st.markdown("### Resume Skills")
        if resume_skills:
            # Separate and sort skills alphabetically within each type
            tech_chips = sorted(
                [s for s in resume_skills if s["type"] == "Technical"],
                key=lambda x: x["name"].lower()
            )
            
            soft_chips = sorted(
                [s for s in resume_skills if s["type"] == "Soft"],
                key=lambda x: x["name"].lower()
            )
            
            # Initialize skills_html with Technical heading
            skills_html = """
            <div style="margin-bottom: 12px;">
                <strong style="font-size: 16px; color: #2E7D32;">Technical Skills</strong>
            </div>
            """
            
            # Add Technical Skills chips (GREEN)
            for s in tech_chips:
                name = display_skill(s["name"])  # Use display_skill for proper capitalization
                skills_html += f'<span style="background:#4CAF50; color:white; padding:6px 14px; border-radius:20px; margin:4px; display:inline-block; font-size:13px; font-weight:500;">{name}</span>'
            
            # Add Soft Skills heading with spacing
            skills_html += """
            <div style="margin: 32px 0 12px 0;">
                <strong style="font-size: 16px; color: #1565C0;">Soft Skills</strong>
            </div>
            """
            
            # Add Soft Skills chips (BLUE)
            for s in soft_chips:
                name = display_skill(s["name"])
                skills_html += f'<span style="background:#2196F3; color:white; padding:6px 14px; border-radius:20px; margin:4px; display:inline-block; font-size:13px; font-weight:500;">{name}</span>'
                
            st.markdown(skills_html, unsafe_allow_html=True)
        else:
            st.info("No skills detected.")

        # ===== EXTRACT AND DISPLAY NAME + LINKEDIN =====
        # Extract name and LinkedIn
        candidate_name, linkedin_url = extract_name_and_linkedin(resume_text)

        # Display the results
        if linkedin_url:
            st.markdown(f"**👤 Name:** [{candidate_name}]({linkedin_url})")
            st.markdown(f"**🔗 LinkedIn:** {linkedin_url}")
        else:
            st.markdown(f"**👤 Name:** {candidate_name}")
            st.info("⚠️ LinkedIn URL not found in resume")
        # ===== END NAME/LINKEDIN SECTION =====

        st.markdown(f"**🧑‍💼 Professional Summary:** {extract_professional_summary(resume_text)}")
        
        st.markdown("**🛠 Detailed Skills:**")
        for s in resume_skills:
            icon = "🛠" if s["type"] == "Technical" else "🤝"
            st.markdown(f"{icon} {s['name']} ({s['type']})")

        # Job Description Skills Section
        st.markdown("### Job Description Skills")
        if jd_skills:
            skills_html = ""
            for s in jd_skills:
                color = "#FF9800" if s["type"] == "Technical" else "#9C27B0"
                skills_html += f'<span style="background:{color};color:white;padding:6px 14px;border-radius:20px;margin:4px;display:inline-block;font-size:13px;font-weight:500;">{s["name"]}</span>'
            st.markdown(skills_html, unsafe_allow_html=True)
        else:
            st.info("No skills detected in job description")
        
        st.markdown("**🛠 Detailed Skills:**")
        for s in jd_skills:
            icon = "🛠" if s["type"] == "Technical" else "🤝"
            st.markdown(f"{icon} {s['name']} ({s['type']})")

    with col2:
        st.markdown("### Resume Skill Distribution")
        fig = skill_distribution_chart(len(tech_resume), len(soft_resume))
        st.pyplot(fig, use_container_width=True)
        
        st.metric("Technical Skills", len(tech_resume))
        st.metric("Soft Skills", len(soft_resume))
        st.metric("Total Skills", len(resume_skills))
        
        avg_conf = round(sum(s["confidence"] for s in resume_skills) / len(resume_skills), 1) if resume_skills else 0
        st.metric("Avg Confidence", f"{avg_conf}%")
        
        st.markdown("### 🔍 Detailed Skill Confidence")
        for skill in resume_skills:
            color = "#4CAF50" if skill["type"] == "Technical" else "#2196F3"
            st.markdown(f"**{skill['name']}**")
            st.progress(skill["confidence"] / 100)

    # Milestone 3: Skill Gap Analysis
    st.markdown("## Milestone 3: Skill Gap Analysis & Similarity Matching")
    resume_skill_names = {s["name"].lower() for s in resume_skills}
    resume_skill_map = {
    normalize_skill(s["name"]): s["name"]
    for s in resume_skills
    }
    jd_skill_names = {s["name"].lower() for s in jd_skills}

    matched = set()
    partial = set()
    missing = set()

    for jd_skill in jd_skill_names:
        status = get_match_status(jd_skill, resume_skill_names)

        if status == "exact":
            matched.add(jd_skill)
        elif status == "partial":
            partial.add(jd_skill)
        else:
            missing.add(jd_skill)

    missing = jd_skill_names - matched - partial


    overall_match = int((len(matched) / len(jd_skill_names)) * 100) if jd_skill_names else 0

    left, right = st.columns([3, 2])

    with left:
        st.markdown("### Similarity Matrix")
        jd_list = sorted(jd_skill_names)
        resume_list = sorted([display_skill(s) for s in resume_skill_names])

        st.caption(
            f"Comparing {len(resume_list)} resume skills with {len(jd_list)} job description skills"
        )
        
        if resume_list and jd_list:
            # Limit number of skills for better visualization
            max_skills = 15
            if len(resume_list) > max_skills:
                jd_list_display = jd_list
                st.info(f"Showing first {max_skills} resume skills")
            else:
                resume_list_display = resume_list
                
            if len(jd_list) > max_skills:
                jd_list_display = jd_list[:max_skills]
                st.info(f"Showing first {max_skills} job skills")
            else:
                jd_list_display = jd_list

# ================= Similarity Matrix + Overview =================

                if jd_list_display:

                    # Create similarity matrix
                    fig = go.Figure()

                    STATUS_ROW = {
                        "exact": "✅ Exact Match",
                        "partial": "🟡 Partial Match",
                        "missing": "❌ Missing"
                    }

                    COLOR_MAP = {
                        "exact": "green",
                        "partial": "orange",
                        "missing": "red"
                    }

                    SIZE_MAP = {
                        "exact": 26,
                        "partial": 22,
                        "missing": 16
                    }

                    for jd_skill in jd_list_display:
                        jd_norm = normalize_skill(jd_skill)
                        status = "missing"
                        matched_resume_skill = None  # IMPORTANT

                        if jd_skill in SOFT_SKILLS:
                            status = get_soft_skill_status(jd_skill, resume_skill_names)
                        else:
                            status = get_match_status(jd_skill, resume_skill_names)

                        # Exact match → same skill
                        if status == "exact":
                            matched_resume_skill = display_skill(jd_skill)

                        # Partial match → controlled synonym match
                        elif status == "partial":
                            jd_norm = normalize_skill(jd_skill)

                            for canonical, variants in SYNONYM_MAP.items():
                                if jd_norm in variants:
                                    for r in resume_skill_names:
                                        if normalize_skill(r) == canonical or normalize_skill(r) in variants:
                                            matched_resume_skill = resume_skill_map.get(
                                                normalize_skill(r), r
                                            )
                                            break

                        fig.add_trace(go.Scatter(
                            x=[display_skill(jd_skill)],
                            y=[STATUS_ROW[status]],
                            mode="markers+text" if status == "partial" else "markers",
                            text=[matched_resume_skill] if status == "partial" else None,
                            textposition="top center",
                            marker=dict(
                                size=SIZE_MAP[status],
                                color=COLOR_MAP[status],
                                line=dict(color="black", width=1)
                            ),
                            hovertemplate=(
                                "<b>JD Skill:</b> %{x}<br>"
                                "<b>Status:</b> " + STATUS_ROW[status] + "<br>" +
                                "<b>Matched Resume Skill:</b> " +
                                (matched_resume_skill if matched_resume_skill else "—") +
                                "<extra></extra>"
                            ),
                            showlegend=False
                        ))

                    fig.update_layout(
                        height=380,
                        plot_bgcolor="white",
                        margin=dict(l=120, r=40, t=30, b=80),
                        xaxis=dict(
                            title="<b>Job Description Skills</b>",
                            tickangle=45,
                            showgrid=True,
                            gridcolor="lightgray"
                        ),
                        yaxis=dict(
                            title="<b>Match Status</b>",
                            categoryorder="array",
                            categoryarray=[
                                "✅ Exact Match",
                                "🟡 Partial Match",
                                "❌ Missing"
                            ],
                            showgrid=True,
                            gridcolor="lightgray"
                        ),
                        showlegend=False
                    )

                    st.plotly_chart(fig, use_container_width=True)
                st.markdown("### Missing Skills")
                if missing:
                    for skill in sorted(missing):
                        st.markdown(f"❌ **{skill.title()}**")
                else:
                    st.success("No missing skills! ✅")

            # ================= RIGHT SIDE : SKILL MATCH OVERVIEW =================

            with right:
                st.markdown("### Skill Match Overview")

                total_jd = len(jd_list_display)
                overall_match = int((len(matched) / total_jd) * 100) if total_jd else 0

                match_color = (
                    "#10B981" if overall_match >= 70
                    else "#F59E0B" if overall_match >= 50
                    else "#EF4444"
                )

                c1, c2 = st.columns(2)
                c3, c4 = st.columns(2)

                c1.markdown(f"""
                <div style="background:{match_color};padding:15px;border-radius:10px;text-align:center;">
                    <h3 style="color:white;margin:0;">{overall_match}%</h3>
                    <p style="color:white;margin:0;">Overall Match</p>
                </div>
                """, unsafe_allow_html=True)

                c2.metric("Matched Skills", len(matched))
                c3.metric("Partial Matches", len(partial))
                c4.metric("Missing Skills", len(missing))

                # --- Donut chart ---
                if matched or partial or missing:
                    total = len(matched) + len(partial) + len(missing)

                    # Create the donut chart
                    donut = go.Figure(go.Pie(
                        labels=["Matched", "Partial", "Missing"],
                        values=[len(matched), len(partial), len(missing)],
                        hole=0.65,
                        marker_colors=["#10B981", "#F59E0B", "#EF4444"],

                        # ✅ SHOW PERCENT ONLY ONCE
                        textinfo="percent",
                        textposition="inside",
                        textfont=dict(size=14, color="white"),
                        insidetextorientation="radial",

                        # Hover info (does NOT duplicate text)
                        hoverinfo="label+value"
                    ))

                    # ✅ Center annotation (overall match)
                    donut.add_annotation(
                        text=f"<b>{overall_match}%</b>",
                        x=0.5, y=0.5,
                        font=dict(size=28, color="#333", family="Arial Black"),
                        showarrow=False
                    )

                    donut.update_layout(
                        height=300,
                        margin=dict(t=20, b=20, l=20, r=20),
                        showlegend=True,
                        legend=dict(
                            orientation="h",
                            x=0.5,
                            xanchor="center",
                            y=-0.1,
                            font=dict(size=12)
                        ),
                        title=dict(
                            text="Skill Match Distribution",
                            x=0.5,
                            xanchor="center",
                            font=dict(size=16)
                        )
                    )

                    st.plotly_chart(donut, use_container_width=True)


    # Milestone 4: Dashboard & Reports
    st.markdown("## Milestone 4: Dashboard & Report Export")

    # Prepare data for visualization
    all_skills = sorted(list(jd_skill_names | resume_skill_names))
    
    if all_skills:
        resume_scores = []
        jd_scores = []

        resume_set = {normalize_skill(s) for s in resume_skill_names}
        jd_set    = {normalize_skill(s) for s in jd_skill_names}

        for skill in all_skills:
            norm = normalize_skill(skill)
            
            # Resume coverage: high if present in resume
            resume_scores.append(95 if norm in resume_set else 10)
            
            # JD requirement: high if present in JD
            jd_scores.append(95 if norm in jd_set else 10)

        df_skills = pd.DataFrame({
            "Skill": [s.title() for s in all_skills],
            "Resume Skill %": resume_scores,
            "Job Requirement %": jd_scores
        })

        # Key metrics cards
        st.markdown("### 📊 Performance Metrics")
        c1, c2, c3, c4 = st.columns(4)
        
        c1.markdown(f"""
        <div style="background:#E0F2FE;padding:20px;border-radius:10px;text-align:center;border-left:5px solid #0EA5E9;">
        <h2 style="color:#0EA5E9;margin:0;">{overall_match}%</h2>
        <p style="margin:0;">Overall Match</p>
        </div>
        """, unsafe_allow_html=True)
        
        c2.markdown(f"""
        <div style="background:#DCFCE7;padding:20px;border-radius:10px;text-align:center;border-left:5px solid #22C55E;">
        <h2 style="color:#166534;margin:0;">{len(matched)}</h2>
        <p style="margin:0;">Matched Skills</p>
        </div>
        """, unsafe_allow_html=True)
        
        c3.markdown(f"""
        <div style="background:#FEF3C7;padding:20px;border-radius:10px;text-align:center;border-left:5px solid #F59E0B;">
        <h2 style="color:#92400E;margin:0;">{len(partial)}</h2>
        <p style="margin:0;">Partial Matches</p>
        </div>
        """, unsafe_allow_html=True)
        
        c4.markdown(f"""
        <div style="background:#FEE2E2;padding:20px;border-radius:10px;text-align:center;border-left:5px solid #EF4444;">
        <h2 style="color:#991B1B;margin:0;">{len(missing)}</h2>
        <p style="margin:0;">Missing Skills</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        # Skill Comparison Chart
        left, right = st.columns([3, 1])

        with left:
            st.markdown("### 📈 Skill Match Overview")
            fig = go.Figure()
            fig.add_bar(
                x=df_skills["Skill"], 
                y=df_skills["Resume Skill %"], 
                name="Resume Skills", 
                marker_color="#3B82F6"
            )
            fig.add_bar(
                x=df_skills["Skill"], 
                y=df_skills["Job Requirement %"], 
                name="Job Requirements", 
                marker_color="#10B981"
            )
            fig.update_layout(
                barmode="group", 
                height=350, 
                yaxis_title="Percentage (%)",
                xaxis_tickangle=45,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("### ⚖️ Skill Comparison")
            for skill in all_skills:
                norm = normalize_skill(skill)
                
                if norm in jd_set:                      # Skill is required in JD
                    if norm in matched:
                        percent = 100                   # Perfect Match
                        status_text = "Perfect Match"
                        bar_color = "#22C55E"           # Green
                    elif norm in partial:
                        percent = 50                    # Partial Match
                        status_text = "Partial Match"
                        bar_color = "#F59E0B"           # Yellow
                    else:
                        percent = 20                    # Missing
                        status_text = "Missing"
                        bar_color = "#EF4444"           # Red
                else:                                   # Extra skill only in resume
                    percent = 30
                    status_text = "Resume Extra"
                    bar_color = "#3B82F6"               # Blue (for extra resume skills)

                # Show skill name + status + percentage
                st.markdown(f"**{skill.title()}** – {status_text} ({percent}%)")

                # Colored progress bar using inline div (since st.progress is always blue)
                st.markdown(
                    f'<div style="background-color:{bar_color};height:20px;border-radius:10px;width:{percent}%;margin:6px 0;"></div>',
                    unsafe_allow_html=True
                )

            st.markdown("### 🎯 Key Skill Match Percentages")
            cols = st.columns(min(len(all_skills), 6))

            for i, skill in enumerate(all_skills):
                norm = normalize_skill(skill)
                
                if norm in jd_set:  # skill is required in JD
                    if norm in matched:
                        percent = 100
                        bg, fg = "#DCFCE7", "#22C55E"   # green - perfect match
                    elif norm in partial:
                        percent = 50
                        bg, fg = "#FEF3C7", "#F59E0B"   # yellow - partial
                    else:
                        percent = 20
                        bg, fg = "#FEE2E2", "#EF4444"   # red - missing
                else:  # extra skill only in resume
                    percent = 30
                    bg, fg = "#FFEDD5", "#3B82F6"      # orange - resume extra

                col_idx = i % len(cols)
                cols[col_idx].markdown(f"""
                <div style="background:{bg};width:80px;height:80px;border-radius:50%;
                display:flex;align-items:center;justify-content:center;margin:auto;border:3px solid {fg};">
                <b style="color:{fg};font-size:18px;">{percent}%</b>
                </div>
                <p style="text-align:center;margin-top:6px;font-size:11px;"><b>{skill.title()}</b></p>
                """, unsafe_allow_html=True)

        with right:
            st.markdown("### 👤 Role View")
            selected_role = st.radio("", ["Job Seeker", "Recruiter"], horizontal=True, key="role")
            
            if len(all_skills) >= 3:
                radar = go.Figure()

                # Decide axis labels and corresponding scores based on view
                if selected_role == "Job Seeker":
                    theta_labels = [s.title() for s in all_skills] + [all_skills[0].title()]  # All unique skills
                    jd_r = jd_scores + [jd_scores[0]]                                            # Purple = JD requirement
                    resume_r = resume_scores + [resume_scores[0]]                                # Blue = Your resume coverage
                    partial_r = [55 if s.lower() in partial else 0 for s in all_skills] + [0]
                else:
                    # Recruiter: ONLY JD skills on axis
                    jd_only_skills = [s for s in all_skills if s.lower() in jd_skill_names]
                    if not jd_only_skills:
                        jd_only_skills = all_skills[:1]  # fallback if no JD skills

                    theta_labels = [s.title() for s in jd_only_skills] + [jd_only_skills[0].title()]

                    # Map JD scores to JD-only axis
                    jd_r = [jd_scores[all_skills.index(s)] if s in all_skills else 0 for s in jd_only_skills] + [0]

                    # Matched / Partial only on JD skills
                    matched_r = [85 if s.lower() in matched else 0 for s in jd_only_skills] + [0]
                    partial_r = [55 if s.lower() in partial else 0 for s in jd_only_skills] + [0]

                    # No resume line in recruiter view (gaps clear)

                # JD base (always strong green)
                radar.add_trace(go.Scatterpolar(
                    r=jd_r,
                    theta=theta_labels,
                    fill="toself",
                    name="Job Requirement",
                    line_color="#A855F7",          # <-- Purple (reddish-purple)
                    fillcolor="rgba(168, 85, 247, 0.25)",   # lighter fill
                    opacity=0.85
                ))

                if selected_role == "Job Seeker":
                    # Strong resume profile for job seeker
                    radar.add_trace(go.Scatterpolar(
                        r=resume_r,
                        theta=theta_labels,
                        fill="toself",
                        name="Your Full Profile (Resume Skills)",
                        line_color="#3B82F6",          # <-- Blue
                        fillcolor="rgba(59, 130, 246, 0.45)",   # a bit stronger fill
                        opacity=0.95
                    ))
                    title_text = "Your Complete Skill Alignment vs Job Requirement"

                else:  # Recruiter: Only matched + partial overlays
                    # Matched (darker green)
                    radar.add_trace(go.Scatterpolar(
                        r=matched_r,
                        theta=theta_labels,
                        fill="toself",
                        name="Matched Skills",
                        line_color="#22C55E",
                        fillcolor="rgba(34, 197, 94, 0.6)",
                        opacity=0.9
                    ))

                    # Partial (yellow)
                    radar.add_trace(go.Scatterpolar(
                        r=partial_r,
                        theta=theta_labels,
                        fill="toself",
                        name="Partial Matches",
                        line_color="#F59E0B",
                        fillcolor="rgba(245, 158, 11, 0.6)",
                        opacity=0.8
                    ))

                    # Optional: Red outline for missing (uncomment if you want red border on missing)
                    missing_r = [jd_scores[all_skills.index(s)] if s.lower() not in matched and s.lower() not in partial else 0 for s in jd_only_skills] + [0]
                    radar.add_trace(go.Scatterpolar(
                       r=missing_r,
                        theta=theta_labels,
                        mode="lines",
                        name="Missing Skills (Gaps)",
                        line=dict(color="#EF4444", width=3, dash="dot"),
                        fill=None,
                        showlegend=True
                    ))

                    title_text = "Candidate Fit vs Job Requirement (Recruiter View - Gaps Highlighted)"

                radar.update_layout(
                    polar=dict(
                        radialaxis=dict(range=[0, 100], visible=True, tickfont=dict(size=12)),
                        angularaxis=dict(
                            showticklabels=True,
                            tickfont=dict(size=11),           # Smaller font if many skills
                            rotation=90,                      # Rotate labels
                            direction="clockwise"
                        )
                    ),
                    height=520,                               # Bigger chart
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5),
                    title=dict(text="Your Complete Skill Alignment vs Job Requirement", x=0.5, xanchor="center", font=dict(size=18)),
                    margin=dict(t=120, b=220, l=80, r=80)     # Extra bottom space for labels
                )

                st.plotly_chart(radar, use_container_width=True)
            else:
                st.info("Need at least 3 skills for radar chart")

            st.markdown("### 🚀 Upskilling Recommendations")
            if missing or partial:
                for skill in sorted(missing | partial):
                    st.warning(f"Improve **{skill.title()}** through courses and hands-on projects")
            else:
                st.success("Perfect match! All required skills are present.")

        # Export Section - FIXED
        st.markdown("---")
        st.markdown("### 📥 Export Reports")
        
        def generate_pdf_report():
            """Generate PDF report without encoding issues"""
            pdf = FPDF()
            pdf.add_page()
            
            # Title
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "Skill Gap Analysis Report", ln=True, align="C")
            pdf.ln(10)
            
            # Candidate Info - FIXED: Use extract_name_and_linkedin instead of extract_name
            candidate_name, linkedin_url = extract_name_and_linkedin(resume_text)
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 8, f"Candidate: {candidate_name}", ln=True)
            if linkedin_url:
                pdf.cell(0, 8, f"LinkedIn: {linkedin_url}", ln=True)
            pdf.cell(0, 8, f"Overall Match: {overall_match}%", ln=True)
            pdf.ln(5)
            
            # Matched Skills
            if matched:
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 8, "Matched Skills:", ln=True)
                pdf.set_font("Arial", "", 12)
                for skill in sorted(matched):
                    pdf.cell(0, 8, f"  - {skill.title()}", ln=True)
                pdf.ln(5)
            
            # Missing Skills
            if missing:
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 8, "Missing Skills:", ln=True)
                pdf.set_font("Arial", "", 12)
                for skill in sorted(missing):
                    pdf.cell(0, 8, f"  - {skill.title()}", ln=True)
                pdf.ln(5)
            
            # Recommendations
            if missing or partial:
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 8, "Recommendations:", ln=True)
                pdf.set_font("Arial", "", 12)
                for skill in sorted(missing | partial):
                    pdf.cell(0, 8, f"  - Improve {skill.title()} through courses", ln=True)
            
            return pdf.output(dest='S').encode('latin-1')
        
        def generate_csv_report():
            """Generate CSV report with skill scores instead of Yes/No"""
            import io
            output = io.StringIO()

            # CSV Header
            output.write("Skill,Status,Resume Score (%),Job Requirement Score (%)\n")

            for skill in sorted(all_skills):
                if skill in matched:
                    status = "Matched"
                    resume_score = 85
                    jd_score = 90
                elif skill in partial:
                    status = "Partial"
                    resume_score = 55
                    jd_score = 80
                else:
                    status = "Missing"
                    resume_score = 20
                    jd_score = 90

                output.write(
                    f"{skill.title()},{status},{resume_score},{jd_score}\n"
                )

            return output.getvalue().encode("utf-8")

        
        # Download buttons
        col1, col2 = st.columns(2)
        
        with col1:
            try:
                pdf_data = generate_pdf_report()
                st.download_button(
                    label="📄 Download PDF Report",
                    data=pdf_data,
                    file_name="skill_gap_report.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"PDF generation failed. Error: {str(e)[:50]}...")
        
        with col2:
            try:
                csv_data = generate_csv_report()
                st.download_button(
                    label="📊 Download CSV Report",
                    data=csv_data,
                    file_name="skill_gap_data.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"CSV generation failed. Error: {str(e)[:50]}...")

    else:
        st.warning("No skills detected for visualization")

else:
    st.info("👈 Please upload both a resume and a job description to start the analysis.")