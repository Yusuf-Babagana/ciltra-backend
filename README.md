# Ciltra Platform — Backend API

**Ciltra** is a Django REST Framework-powered backend for an online certification and examination platform. It allows students to register, purchase and take timed exams (MCQ & theory), receive AI-assisted or manual grading, and earn verifiable digital certificates.

---

## ✨ Features

- **JWT Authentication** — Email-based login with access/refresh tokens (SimpleJWT)
- **Role-Based Access Control** — Three roles: `Student`, `Teacher`, and `Admin`
- **Exam Management** — Categorised exams with configurable duration, pass marks, and pricing
- **Question Bank** — MCQ and open-ended (theory) questions with difficulty tagging
- **Exam Sessions** — Timed exam attempts with per-answer storage
- **Manual Grading Workflow** — Teacher review queue for theory submissions
- **Certificate Issuance** — Unique UUID-based certificates with public verification URLs
- **Payment Integration** — Paystack payment processing with transaction tracking
- **CORS Support** — Configured for cross-origin requests from the Next.js frontend

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| Framework | Django 5.2 + Django REST Framework 3.15 |
| Authentication | JWT via `djangorestframework-simplejwt` |
| Database | SQLite (dev) — swap for PostgreSQL in production |
| CORS | `django-cors-headers` |
| Payment | Paystack |
| Deployment | Nginx + Gunicorn (on `ciltra.org`) |

---

## 📁 Project Structure

```
ciltra-backend/
│
├── ciltra_platform/               # Main Django project package (inner)
│   ├── ciltra_platform/           # Project settings & root URL config
│   │   ├── settings.py            # All project settings (JWT, CORS, DB, Paystack)
│   │   ├── urls.py                # Root URL dispatcher
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   ├── users/                     # User management & authentication app
│   │   ├── models.py              # Custom User model (email login, roles)
│   │   ├── views.py               # Register, Login, StudentList, AdminStats
│   │   ├── serializers.py         # Register, JWT token, Student list serializers
│   │   ├── permissions.py         # IsAdmin, IsTeacher, IsStudent permission classes
│   │   ├── backends.py            # Custom email authentication backend
│   │   └── urls.py
│   │
│   ├── exams/                     # Exam and question bank app
│   │   ├── models.py              # ExamCategory, Exam, Question, Option
│   │   ├── views.py               # ExamViewSet, QuestionViewSet, CategoryViewSet
│   │   ├── serializers.py
│   │   └── urls.py
│   │
│   ├── assessments/               # Exam-taking and grading app
│   │   ├── models.py              # ExamSession, StudentAnswer
│   │   ├── views.py               # StartExam, SubmitExam, PendingGrading, SubmitGrade
│   │   ├── serializers.py
│   │   └── urls.py
│   │
│   ├── payments/                  # Payment processing app
│   │   ├── models.py              # Transaction (Paystack reference, status)
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── certificates/              # Certificate issuance & verification app
│   │   ├── models.py              # Certificate (UUID, verification URL)
│   │   ├── views.py               # CertificateInventory, StudentCertificateList
│   │   ├── serializers.py
│   │   └── urls.py
│   │
│   ├── manage.py
│   ├── settings.py                # (outer-level dev settings override)
│   └── db.sqlite3
│
├── requirements.txt               # Python dependencies
├── manage.py                      # Root Django management entry point
└── README.md
```

---

## 🔌 API Endpoints

### Authentication
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/api/auth/register/` | Create a new student account | Public |
| `POST` | `/api/auth/login/` | Email + password → JWT tokens | Public |

### Exams
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/exams/` | List all active exams | Authenticated |
| `POST` | `/api/exams/` | Create a new exam | Teacher / Admin |
| `GET/PUT/DELETE` | `/api/exams/<id>/` | Retrieve, update or delete exam | Teacher / Admin |
| `GET/POST` | `/api/questions/` | List or add questions to the bank | Teacher / Admin |
| `GET/POST` | `/api/categories/` | List or create exam categories | Teacher / Admin |

### Student — Exam Taking
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/exams/attempts/` | View all own exam attempts | Student |
| `POST` | `/api/exams/<exam_id>/start/` | Begin an exam session | Student |
| `POST` | `/api/exams/session/<session_id>/submit/` | Submit answers | Student |
| `GET` | `/api/exams/session/<pk>/` | View session result | Student |

### Student — Certificates
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/certificates/` | List own earned certificates | Student |

### Admin — Management
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/api/admin/stats/` | Dashboard stats (exams, students, certs) | Admin |
| `GET` | `/api/admin/candidates/` | List all students | Admin |
| `GET` | `/api/admin/grading/pending/` | Queue of ungraded theory sessions | Teacher / Admin |
| `POST` | `/api/admin/grading/submit/<session_id>/` | Submit manual grade for a session | Teacher / Admin |
| `GET` | `/api/admin/certificates/` | Full certificate inventory | Admin |

---

## 🚀 Getting Started

### 1. Clone & create a virtual environment

```bash
git clone https://github.com/Yusuf-Babagana/ciltra-backend.git
cd ciltra-backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run migrations

```bash
cd ciltra_platform
python manage.py migrate
```

### 4. Create a superuser (Admin)

```bash
python manage.py createsuperuser
```

### 5. Start the development server

```bash
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/`.

---

## 🔒 Environment & Security Notes

> **Warning:** The `settings.py` contains a plaintext `SECRET_KEY` and Paystack API keys. Before deploying to production:
> - Move all secrets to environment variables or a `.env` file (use `python-decouple` or `django-environ`)
> - Set `DEBUG = False`
> - Switch the database from SQLite to PostgreSQL
> - Set `ALLOWED_HOSTS` appropriately

---

## 👤 User Roles

| Role | Description |
|---|---|
| `student` | Can register, purchase exams, take exams, and view their certificates |
| `teacher` | Can create/manage exams & questions, and grade theory submissions |
| `admin` | Full platform access including student management and dashboard stats |

---

## 📜 License

This project is proprietary. All rights reserved © Ciltra.
