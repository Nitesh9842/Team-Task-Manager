import os
import re
from datetime import date, datetime
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass, Mapped, mapped_column
from typing import List, Optional

ROLE_ADMIN = "Admin"
ROLE_MEMBER = "Member"
TASK_TODO = "Todo"
TASK_IN_PROGRESS = "In Progress"
TASK_DONE = "Done"
TASK_STATUSES = [TASK_TODO, TASK_IN_PROGRESS, TASK_DONE]
PRIORITIES = ["Low", "Medium", "High"]

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
setattr(login_manager, "login_view", "login")


project_members = db.Table(
    "project_members",
    db.Column("project_id", db.Integer, db.ForeignKey("projects.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("joined_at", db.DateTime, default=datetime.utcnow, nullable=False),
)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(120), nullable=False)
    email: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    role: Mapped[str] = mapped_column(db.String(20), nullable=False, default=ROLE_MEMBER)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    owned_projects: Mapped[List["Project"]] = db.relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    projects: Mapped[List["Project"]] = db.relationship("Project", secondary=project_members, back_populates="members")
    created_tasks: Mapped[List["Task"]] = db.relationship("Task", back_populates="creator", foreign_keys="Task.created_by_id")
    assigned_tasks: Mapped[List["Task"]] = db.relationship("Task", back_populates="assignee", foreign_keys="Task.assigned_to_id")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Project(db.Model):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    owner: Mapped["User"] = db.relationship("User", back_populates="owned_projects")
    tasks: Mapped[List["Task"]] = db.relationship("Task", back_populates="project", cascade="all, delete-orphan")
    members: Mapped[List["User"]] = db.relationship("User", secondary=project_members, back_populates="projects")


class Task(db.Model):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(db.String(180), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    status: Mapped[str] = mapped_column(db.String(30), nullable=False, default=TASK_TODO)
    priority: Mapped[str] = mapped_column(db.String(20), nullable=False, default="Medium")
    due_date: Mapped[Optional[date]] = mapped_column(db.Date, nullable=True)
    project_id: Mapped[int] = mapped_column(db.ForeignKey("projects.id"), nullable=False)
    created_by_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project: Mapped["Project"] = db.relationship("Project", back_populates="tasks")
    creator: Mapped["User"] = db.relationship("User", back_populates="created_tasks", foreign_keys=[created_by_id])
    assignee: Mapped[Optional["User"]] = db.relationship("User", back_populates="assigned_tasks", foreign_keys=[assigned_to_id])


def seed_demo_data() -> None:
    if db.session.query(User).count() > 0:
        return

    admin = User()
    admin.name = "Demo Admin"
    admin.email = "admin@demo.com"
    admin.role = ROLE_ADMIN
    admin.set_password("Admin@12345")
    member = User()
    member.name = "Demo Member"
    member.email = "member@demo.com"
    member.role = ROLE_MEMBER
    member.set_password("Member@12345")

    db.session.add_all([admin, member])
    db.session.flush()

    project = Project(
        name="Launch Roadmap",
        description="Sample project with tasks, team members, and progress tracking.",
        owner=admin,
    )
    project.members.extend([admin, member])
    db.session.add(project)
    db.session.flush()

    db.session.add_all(
        [
            Task(
                title="Define MVP scope",
                description="Finalize the first version and target outcome.",
                status=TASK_DONE,
                priority="High",
                due_date=date.today(),
                project=project,
                creator=admin,
                assignee=member,
            ),
            Task(
                title="Prepare launch checklist",
                description="Collect deployment, QA, and rollout tasks.",
                status=TASK_IN_PROGRESS,
                priority="Medium",
                due_date=date.today(),
                project=project,
                creator=admin,
                assignee=admin,
            ),
        ]
    )
    db.session.commit()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    database_url = os.environ.get("DATABASE_URL", "sqlite:///team_task_manager.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgresql://") and "+psycopg2" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        db.create_all()
        seed_demo_data()

    return app


app = create_app()


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


@app.context_processor
def inject_globals() -> dict:
    return {
        "role_admin": ROLE_ADMIN,
        "task_statuses": TASK_STATUSES,
        "priorities": PRIORITIES,
        "today": date.today(),
    }


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must include letters and numbers."
    return None


def parse_date(value: str | None) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    return date.fromisoformat(value)


def parse_int(value) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def accessible_projects_for(user) -> list[Project]:
    if user.role == ROLE_ADMIN:
        return Project.query.order_by(Project.created_at.desc()).all()
    return (
        Project.query.join(project_members)
        .filter(project_members.c.user_id == user.id)
        .order_by(Project.created_at.desc())
        .all()
    )


def can_manage_project(user, project: Project) -> bool:
    return user.role == ROLE_ADMIN or project.owner_id == user.id


def can_access_project(user, project: Project) -> bool:
    if user.role == ROLE_ADMIN:
        return True
    return project.owner_id == user.id or user in project.members


def can_manage_task(user, task: Task) -> bool:
    return user.role == ROLE_ADMIN or task.project.owner_id == user.id or task.created_by_id == user.id


def require_json() -> dict:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    return payload


def project_progress(project: Project) -> dict:
    total = len(project.tasks)
    done = sum(1 for task in project.tasks if task.status == TASK_DONE)
    overdue = sum(
        1
        for task in project.tasks
        if task.due_date and task.due_date < date.today() and task.status != TASK_DONE
    )
    percent = 0 if total == 0 else round((done / total) * 100)
    return {"total": total, "done": done, "overdue": overdue, "percent": percent}


def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "project_id": task.project_id,
        "project_name": task.project.name,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "assigned_to": task.assignee.name if task.assignee else None,
    }


def project_to_dict(project: Project) -> dict:
    progress = project_progress(project)
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "owner": project.owner.name,
        "members": len(project.members),
        "tasks": progress["total"],
        "done": progress["done"],
        "overdue": progress["overdue"],
        "percent": progress["percent"],
        "created_at": project.created_at.isoformat(),
    }


def task_counts(tasks: list[Task]) -> dict:
    total = len(tasks)
    done = sum(1 for task in tasks if task.status == TASK_DONE)
    in_progress = sum(1 for task in tasks if task.status == TASK_IN_PROGRESS)
    todo = sum(1 for task in tasks if task.status == TASK_TODO)
    overdue = sum(
        1
        for task in tasks
        if task.due_date and task.due_date < date.today() and task.status != TASK_DONE
    )
    return {
        "total": total,
        "done": done,
        "in_progress": in_progress,
        "todo": todo,
        "overdue": overdue,
        "completion": 0 if total == 0 else round(done / total * 100),
    }


def flash_form_errors(errors: list[str]) -> None:
    for error in errors:
        flash(error, "error")


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        errors = []

        if len(name) < 2:
            errors.append("Name must be at least 2 characters long.")
        if not validate_email(email):
            errors.append("Enter a valid email address.")
        if User.query.filter_by(email=email).first():
            errors.append("That email is already registered.")
        password_error = validate_password(password)
        if password_error:
            errors.append(password_error)
        if password != confirm_password:
            errors.append("Passwords do not match.")

        if errors:
            flash_form_errors(errors)
        else:
            role = ROLE_ADMIN if User.query.count() == 0 else ROLE_MEMBER
            user = User()
            user.name = name
            user.email = email
            user.role = role
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))

    return render_template("auth/register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f"Welcome back, {user.name}.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("auth/login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    projects = accessible_projects_for(current_user)
    project_ids = [project.id for project in projects]

    tasks = []
    if project_ids:
        tasks = (
            Task.query.filter(Task.project_id.in_(project_ids))
            .order_by(Task.due_date.is_(None), Task.due_date.asc(), Task.updated_at.desc())
            .all()
        )

    metrics = task_counts(tasks)
    recent_tasks = tasks[:5]
    overdue_tasks = [task for task in tasks if task.due_date and task.due_date < date.today() and task.status != TASK_DONE]

    project_cards = [
        {
            "project": project,
            "progress": project_progress(project),
        }
        for project in projects
    ]

    return render_template(
        "dashboard.html",
        projects=project_cards,
        tasks=tasks,
        recent_tasks=recent_tasks,
        overdue_tasks=overdue_tasks,
        metrics=metrics,
    )


@app.route("/projects")
@login_required
def projects_page():
    projects = accessible_projects_for(current_user)
    project_cards = [
        {
            "project": project,
            "progress": project_progress(project),
        }
        for project in projects
    ]
    return render_template("projects/list.html", projects=project_cards)


@app.route("/projects/new", methods=["GET", "POST"])
@login_required
def create_project():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        errors = []

        if len(name) < 3:
            errors.append("Project name must be at least 3 characters long.")
        if len(name) > 160:
            errors.append("Project name must be 160 characters or fewer.")

        if errors:
            flash_form_errors(errors)
        else:
            project = Project(name=name, description=description, owner=current_user)
            project.members.append(current_user)
            db.session.add(project)
            db.session.commit()
            flash("Project created.", "success")
            return redirect(url_for("project_detail", project_id=project.id))

    return render_template("projects/form.html", project=None)


@app.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        abort(404)
    if not can_access_project(current_user, project):
        abort(403)

    sorted_tasks = sorted(
        project.tasks,
        key=lambda task: (
            task.status == TASK_DONE,
            task.due_date is None,
            task.due_date or date.max,
            task.updated_at,
        ),
    )
    return render_template(
        "projects/detail.html",
        project=project,
        tasks=sorted_tasks,
        progress=project_progress(project),
        can_manage=can_manage_project(current_user, project),
    )


@app.route("/projects/<int:project_id>/tasks", methods=["POST"])
@login_required
def create_task(project_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        abort(404)
    if not can_access_project(current_user, project):
        abort(403)

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    priority = request.form.get("priority", "Medium")
    status = request.form.get("status", TASK_TODO)

    errors = []
    try:
        due_date = parse_date(request.form.get("due_date"))
    except ValueError:
        due_date = None
        errors.append("Enter a valid due date.")

    try:
        assigned_to_id = parse_int(request.form.get("assigned_to_id"))
    except ValueError:
        assigned_to_id = None
        errors.append("Assigned user must be a valid project member.")

    if len(title) < 3:
        errors.append("Task title must be at least 3 characters long.")
    if len(title) > 180:
        errors.append("Task title must be 180 characters or fewer.")
    if priority not in PRIORITIES:
        errors.append("Select a valid priority.")
    if status not in TASK_STATUSES:
        errors.append("Select a valid status.")

    assignee = None
    if assigned_to_id is not None:
        assignee = db.session.get(User, assigned_to_id)
        if assignee is None or assignee not in project.members:
            errors.append("Assigned user must be a project member.")

    if errors:
        flash_form_errors(errors)
        return redirect(url_for("project_detail", project_id=project.id))

    task = Task(
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        status=status,
        project=project,
        creator=current_user,
        assignee=assignee,
    )
    db.session.add(task)
    db.session.commit()
    flash("Task created.", "success")
    return redirect(url_for("project_detail", project_id=project.id))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id: int):
    task = db.session.get(Task, task_id)
    if task is None:
        abort(404)
    if not can_manage_task(current_user, task):
        abort(403)

    project_id = task.project_id
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/team")
@login_required
def team_page():
    if current_user.role != ROLE_ADMIN:
        abort(403)

    users = User.query.order_by(User.created_at.desc()).all()
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template("team.html", users=users, projects=projects)


@app.route("/team/role/<int:user_id>", methods=["POST"])
@login_required
def update_role(user_id: int):
    if current_user.role != ROLE_ADMIN:
        abort(403)

    user = db.session.get(User, user_id)
    if user is None:
        abort(404)

    requested_role = request.form.get("role")
    if requested_role not in {ROLE_ADMIN, ROLE_MEMBER}:
        flash("Select a valid role.", "error")
        return redirect(url_for("team_page"))

    if user.id == current_user.id and requested_role != ROLE_ADMIN:
        flash("You cannot demote your own admin account while signed in.", "error")
        return redirect(url_for("team_page"))

    if user.role == ROLE_ADMIN and requested_role != ROLE_ADMIN:
        admin_count = User.query.filter_by(role=ROLE_ADMIN).count()
        if admin_count <= 1:
            flash("At least one admin must remain on the system.", "error")
            return redirect(url_for("team_page"))

    user.role = requested_role
    db.session.commit()
    flash("User role updated.", "success")
    return redirect(url_for("team_page"))


@app.route("/projects/<int:project_id>/members", methods=["POST"])
@login_required
def add_project_member(project_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        abort(404)
    if not can_manage_project(current_user, project):
        abort(403)

    email = normalize_email(request.form.get("email"))
    member = User.query.filter_by(email=email).first()
    if member is None:
        flash("No user found with that email address.", "error")
    elif member in project.members:
        flash("That user is already on the project.", "error")
    else:
        project.members.append(member)
        db.session.commit()
        flash("Member added to the project.", "success")
    return redirect(url_for("project_detail", project_id=project.id))


@app.route("/projects/<int:project_id>/members/<int:user_id>/remove", methods=["POST"])
@login_required
def remove_project_member(project_id: int, user_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        abort(404)
    if not can_manage_project(current_user, project):
        abort(403)

    member = db.session.get(User, user_id)
    if member is None:
        abort(404)

    if member.id == project.owner_id:
        flash("The project owner cannot be removed.", "error")
    elif member in project.members:
        project.members.remove(member)
        db.session.commit()
        flash("Member removed from the project.", "success")
    return redirect(url_for("project_detail", project_id=project.id))


@app.route("/api/dashboard")
@login_required
def api_dashboard():
    projects = accessible_projects_for(current_user)
    project_ids = [project.id for project in projects]
    tasks = []
    if project_ids:
        tasks = Task.query.filter(Task.project_id.in_(project_ids)).all()

    return jsonify(
        {
            "metrics": task_counts(tasks),
            "projects": [project_to_dict(project) for project in projects],
            "tasks": [task_to_dict(task) for task in tasks],
        }
    )


@app.route("/api/projects")
@login_required
def api_projects_list():
    projects = accessible_projects_for(current_user)
    return jsonify({"projects": [project_to_dict(project) for project in projects]})


@app.route("/api/projects", methods=["POST"])
@login_required
def api_projects_create():
    payload = require_json()
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()

    if len(name) < 3:
        return jsonify({"error": "Project name must be at least 3 characters long."}), 422

    project = Project(name=name, description=description, owner=current_user)
    project.members.append(current_user)
    db.session.add(project)
    db.session.commit()
    return jsonify({"project": project_to_dict(project)}), 201


@app.route("/api/projects/<int:project_id>")
@login_required
def api_project_detail(project_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        return jsonify({"error": "Project not found."}), 404
    if not can_access_project(current_user, project):
        return jsonify({"error": "Forbidden."}), 403

    return jsonify(
        {
            "project": project_to_dict(project),
            "members": [
                {"id": member.id, "name": member.name, "email": member.email, "role": member.role}
                for member in project.members
            ],
            "tasks": [task_to_dict(task) for task in project.tasks],
        }
    )


@app.route("/api/projects/<int:project_id>/members", methods=["POST"])
@login_required
def api_add_project_member(project_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        return jsonify({"error": "Project not found."}), 404
    if not can_manage_project(current_user, project):
        return jsonify({"error": "Forbidden."}), 403

    payload = require_json()
    email = normalize_email(payload.get("email"))
    member = User.query.filter_by(email=email).first()
    if member is None:
        return jsonify({"error": "No user found with that email address."}), 404
    if member in project.members:
        return jsonify({"error": "User is already a project member."}), 409

    project.members.append(member)
    db.session.commit()
    return jsonify({"message": "Member added.", "members": [{"id": user.id, "name": user.name, "email": user.email} for user in project.members]})


@app.route("/api/projects/<int:project_id>/members/<int:user_id>", methods=["DELETE"])
@login_required
def api_remove_project_member(project_id: int, user_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        return jsonify({"error": "Project not found."}), 404
    if not can_manage_project(current_user, project):
        return jsonify({"error": "Forbidden."}), 403

    member = db.session.get(User, user_id)
    if member is None:
        return jsonify({"error": "User not found."}), 404
    if member.id == project.owner_id:
        return jsonify({"error": "The project owner cannot be removed."}), 409
    if member not in project.members:
        return jsonify({"error": "User is not a project member."}), 404

    project.members.remove(member)
    db.session.commit()
    return jsonify({"message": "Member removed."})


@app.route("/api/projects/<int:project_id>/tasks", methods=["POST"])
@login_required
def api_create_task(project_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        return jsonify({"error": "Project not found."}), 404
    if not can_access_project(current_user, project):
        return jsonify({"error": "Forbidden."}), 403

    payload = require_json()
    title = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip()
    status = payload.get("status") or TASK_TODO
    priority = payload.get("priority") or "Medium"

    try:
        due_date = parse_date(payload.get("due_date"))
    except ValueError:
        return jsonify({"error": "Enter a valid due date."}), 422

    try:
        assignee_id = parse_int(payload.get("assigned_to_id"))
    except ValueError:
        return jsonify({"error": "Assigned user must be a valid project member."}), 422

    if len(title) < 3:
        return jsonify({"error": "Task title must be at least 3 characters long."}), 422
    if status not in TASK_STATUSES:
        return jsonify({"error": "Invalid status."}), 422
    if priority not in PRIORITIES:
        return jsonify({"error": "Invalid priority."}), 422

    assignee = None
    if assignee_id is not None:
        assignee = db.session.get(User, assignee_id)
        if assignee is None or assignee not in project.members:
            return jsonify({"error": "Assigned user must be a project member."}), 422

    task = Task(
        title=title,
        description=description,
        status=status,
        priority=priority,
        due_date=due_date,
        project=project,
        creator=current_user,
        assignee=assignee,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"task": task_to_dict(task)}), 201


@app.route("/api/tasks/<int:task_id>/status", methods=["PATCH"])
@login_required
def api_update_task_status(task_id: int):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404
    if not can_access_project(current_user, task.project):
        return jsonify({"error": "Forbidden."}), 403

    payload = require_json()
    status = payload.get("status")
    if status not in TASK_STATUSES:
        return jsonify({"error": "Invalid status."}), 422

    task.status = status
    db.session.commit()
    return jsonify({"message": "Task updated.", "task": task_to_dict(task)})


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def api_delete_task(task_id: int):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404
    if not can_manage_task(current_user, task):
        return jsonify({"error": "Forbidden."}), 403

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted."})


@app.errorhandler(403)
def forbidden(_error):
    return render_template("errors/403.html"), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("errors/404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)
