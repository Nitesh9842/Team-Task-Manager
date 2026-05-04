# Team Task Manager

Team Task Manager is a Flask-based web app for creating projects, managing members, assigning tasks, and tracking progress with role-based access control.

## Features

- Authentication with signup and login
- Role-based access for Admin and Member accounts
- Project creation and team management
- Task assignment, status updates, and overdue tracking
- Dashboard with project and task progress summaries
- REST API endpoints for dashboard, projects, members, and tasks

## Tech Stack

- Python
- Flask
- SQLAlchemy
- Flask-Login
- HTML, CSS, JavaScript
- SQLite locally, PostgreSQL on Railway

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python app.py
```

4. Open `http://127.0.0.1:5000`

## Demo Accounts

The app seeds demo data the first time it starts:

- Admin: `admin@demo.com` / `Admin@12345`
- Member: `member@demo.com` / `Member@12345`

You can also create a fresh account through signup. The first registered user becomes Admin.

## Railway Deployment

1. Push the repository to GitHub.
2. Create a new Railway project and deploy from the GitHub repo.
3. Add a PostgreSQL database in Railway and connect it.
4. Set these environment variables:

- `SECRET_KEY` = a long random secret
- `DATABASE_URL` = Railway PostgreSQL connection string

5. Set the start command to:

```bash
gunicorn app:app
```

## API Endpoints

- `GET /api/dashboard`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/<project_id>`
- `POST /api/projects/<project_id>/members`
- `DELETE /api/projects/<project_id>/members/<user_id>`
- `POST /api/projects/<project_id>/tasks`
- `PATCH /api/tasks/<task_id>/status`
- `DELETE /api/tasks/<task_id>`

## Notes

- SQLite is used automatically when `DATABASE_URL` is not set.
- All database tables are created at startup.
- The app is ready for Railway using PostgreSQL in production.