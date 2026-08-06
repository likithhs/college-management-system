# Seshadripuram College - Official Web Application 🎓

A modern, responsive, and feature-rich college web application built with **Python (Flask)**, **HTML5**, **Tailwind CSS**, and **JavaScript animations (GSAP & AOS)**. Inspired by the academic excellence and infrastructure of **Seshadripuram College**, Bengaluru.

---

## 🌟 Key Features

1. **Dynamic Navigation & Live Ticker**:
   - Live News Ticker marquee for real-time announcements.
   - NAAC A++ accreditation badges and top utility header.
   - Fully responsive navigation with active page indicators and mobile drawer menu.

2. **Hero & Quick Action Cards**:
   - Dynamic hero section with floating interactive quick-link cards (*News & Circulars*, *Admission Query*, *Campus Gallery*, *Campus Forum*).

3. **Key Pillars & Animated Stat Counters**:
   - Animated count-up counters for NAAC A++ rating, 100+ Computer Terminals, and 45,000+ Library Volumes.

4. **Multi-Page Architecture (Flask Routes)**:
   - `GET /` - Home Landing Page
   - `GET /about` - Institutional Vision, Mission, & Leadership
   - `GET /admission` - Admission Guidelines, Eligibility Matrix & Fee breakdown
   - `GET /apply` - Interactive 2026-27 Admission Application Form
   - `GET /departments` - Academic Departments Overview
   - `GET /course/<course_code>` - Course Syllabus Breakdown & University Question Papers Download (BCA, MCA, BBA, BCom, MBA, MCom, BA, BSc, MSc)
   - `GET /facilities` - Computer Labs, Digital Library, Sports Complex, Hostels
   - `GET /placements` - Recruiter Showcase & Placement Statistics
   - `GET /gallery` - Filterable Lightbox Photo & Video Gallery
   - `GET /students-corner` - Clubs, NCC/NSS, Exam Schedules & Circulars
   - `GET /forum` - Campus Discussion Forum for Students & Alumni
   - `GET /contact` - Campus Location, Direct Contact Form
   - `GET /login` - Student & Staff Portal Sign-in
   - `GET /admin` - College Administration Control Dashboard

5. **UI & Animations**:
   - Smooth entrance animations using AOS (Animate on Scroll).
   - Micro-interactions, hover card elevations, and custom glassmorphism styles.
   - Toast notification alerts for user actions.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.x, Flask, Jinja2 Templating
- **Frontend**: HTML5, Tailwind CSS, FontAwesome 6, Google Fonts (*Plus Jakarta Sans*)
- **Animations & Interactivity**: AOS (Animate On Scroll), Custom JS Counter Observer
- **Deployment**: Gunicorn ready, Flask WSGI

---

## 🚀 How to Run Locally

### Prerequisites
Make sure you have Python installed on your system.

### Installation Steps

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/naveen3438/college-project.git
   cd college-project
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Flask Development Server**:
   ```bash
   python app.py
   ```

4. **Open in Web Browser**:
   Navigate to `http://127.0.0.1:5000` to view the college application!

---

## 📜 License & Copyright

© 2026 Seshadripuram College. All rights reserved. Affiliated to Bengaluru City University.
