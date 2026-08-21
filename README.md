# Seshadripuram College - Web Application & Campus Portal 🎓

A modern, high-performance, and feature-rich college web application built with **Python (Flask)**, **Jinja2 Templating**, **Tailwind CSS**, and **JavaScript animations (AOS)**.

Inspired by the academic excellence and infrastructure of **Seshadripuram College**, Bengaluru.

---

## 📌 Current State & Overview

The project is fully functional, styled in a luxury **Royal Navy & Amber Accent** theme, and features an advanced **Super Admin Control Matrix** that dynamically controls public module visibility and College Admin permission access in real-time.

All code is committed and pushed to GitHub: [https://github.com/naveen3438/college-project.git](https://github.com/naveen3438/college-project.git)

---

## 🌟 Existing Key Features

### 1. ⚙️ Root Super Admin Control Matrix (`/superadmin`)
- **Master Site-Wide Toggle**: Instantly enable or disable any module site-wide in real-time.
- **Admin Access Authority Matrix**: Grant or revoke specific module permissions for the College Admin desk.
- **Floating Sidebar & FAB Control**: Dedicated master toggle for the right-corner quick action buttons (`floating_sidebar`).

### 2. 🏛️ College Administration Portal (`/admin`)
- **Admissions Verification Table**: Manage online applications with status tags (`VERIFIED`, `UNDER REVIEW`, `SEAT LOCKED`).
- **Gallery Management Center**: Upload new photo highlights and remove archived photos.
- **Forum Management Center**: Post official college announcements and discussion topics.

### 3. 🔒 Restricted Admin Security
- **Public Read-Only Gallery (`/gallery`)**: Uploading and deleting photo highlights are removed from public view and restricted exclusively to Admin & Super Admin.
- **Public Read-Only Forum (`/forum`)**: Topic creation buttons and post modals are removed from public view and restricted exclusively to Admin & Super Admin.

### 4. 🌙 100% Dark Mode Accessibility
- Complete high-contrast dark theme support across all pages, cards, tables, forms, and navigation menus.
- Automatic contrast adjustments ensuring no dark-on-dark unreadable text.

### 5. 📚 Academic Programs & University Question Papers (`/departments` & `/course_detail`)
- Comprehensive degree pages for **UG** (BCA, BBA, BCom, BA, BSc) and **PG** (MCA, MBA, MCom, MSc).
- Interactive **Previous University Exam Question Paper Repository** with PDF downloads.

### 6. 📝 Online Admission Application (`/apply`)
- 4-step online admission workflow, document upload checklist, eligibility calculator, and submission portal.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.x, Flask, Jinja2 Templating
- **Frontend**: HTML5, Tailwind CSS, FontAwesome 6, Google Fonts (*Plus Jakarta Sans*)
- **Animations & Interactivity**: AOS (Animate On Scroll), Custom JS Counter Observer
- **Server / Deployment**: Gunicorn ready, Flask WSGI

---

## 🚀 How to Run Locally

### Prerequisites
Ensure Python 3.x is installed on your system.

### Steps:

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/naveen3438/college-project.git
   cd college-project
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Application**:
   ```bash
   python app.py
   ```

4. **Open in Browser**:
   - Public Portal: `http://127.0.0.1:5000/`
   - Super Admin Control: `http://127.0.0.1:5000/superadmin`
   - College Admin Portal: `http://127.0.0.1:5000/admin`

---

## 📜 License & Copyright

© 2026 Seshadripuram College. All rights reserved. Affiliated to Bengaluru City University.
