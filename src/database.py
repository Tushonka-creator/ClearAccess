"""
Модуль работы с базой данных SQLite для СКУД ClearAccess.
Отвечает за хранение, создание таблиц, инициализацию и выполнение CRUD-операций.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Tuple

from src.models import (
    User, Card, AccessPoint, EventLog,
    UserStatus, UserRole, CardStatus, LockStatus, EventType
)

# Путь к файлу базы данных SQLite
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "clear_access.db")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Создает и возвращает соединение с базой данных SQLite."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Позволяет обращаться к полям по именам колонок
    # Регистрируем регистронезависимую функцию LOWER для корректного поиска на русском языке
    conn.create_function("LOWER", 1, lambda s: s.lower() if s is not None else "")
    return conn


def init_db(db_path: str = DB_PATH):
    """
    Инициализирует структуру таблиц базы данных в соответствии с ТЗ ClearAccess:
    - users (пользователи/сотрудники)
    - cards (RFID-карты)
    - access_points (точки прохода: турникеты, двери)
    - event_logs (хронология событий и проходов)
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Таблица сотрудников и гостей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                department TEXT NOT NULL,
                position TEXT NOT NULL DEFAULT 'Сотрудник',
                status TEXT NOT NULL DEFAULT 'absent',
                role TEXT NOT NULL DEFAULT 'employee',
                phone TEXT,
                created_at TEXT NOT NULL
            );
        """)

        # 2. Таблица RFID-карт доступа
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                card_number TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'active',
                issued_at TEXT NOT NULL,
                expires_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)

        # 3. Таблица точек доступа (турникетов, дверей)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS access_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                lock_status TEXT NOT NULL DEFAULT 'normal',
                is_alarm INTEGER NOT NULL DEFAULT 0
            );
        """)

        # 4. Таблица журнала событий (Event Logs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                access_point_id INTEGER NOT NULL,
                card_number TEXT NOT NULL,
                user_id INTEGER,
                user_name TEXT,
                details TEXT,
                FOREIGN KEY (access_point_id) REFERENCES access_points (id)
            );
        """)

        conn.commit()


def seed_initial_data(db_path: str = DB_PATH):
    """Заполняет базу данных начальными демонстрационными записями, если она пуста."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Проверяем, есть ли уже записи в таблице точек доступа
        cursor.execute("SELECT COUNT(*) as count FROM access_points;")
        if cursor.fetchone()["count"] == 0:
            # Создаем начальные точки прохода
            points = [
                ("КПП-1 (Главный вход — Турникет А)", "Центральный вестибюль, 1 этаж", "normal", 0),
                ("КПП-1 (Главный вход — Турникет Б)", "Центральный вестибюль, 1 этаж", "normal", 0),
                ("Турникет 2 (Северное крыло)", "Корпус А, служебный вход", "normal", 0),
                ("Дверь 302 (Серверная / ИТ)", "3 этаж, технический коридор", "normal", 0),
            ]
            cursor.executemany(
                "INSERT INTO access_points (name, location, lock_status, is_alarm) VALUES (?, ?, ?, ?);",
                points
            )

        # Проверяем, есть ли уже сотрудники
        cursor.execute("SELECT COUNT(*) as count FROM users;")
        if cursor.fetchone()["count"] == 0:
            now = datetime.now().isoformat()
            initial_users = [
                ("Иванов Алексей Сергеевич", "Отдел ИТ и автоматизации", "Главный инженер ИТ", "present", "employee", "+7 916 244-11-09", now),
                ("Смирнова Елена Дмитриевна", "Управление персоналом", "Начальник отдела кадров", "present", "employee", "+7 925 881-34-12", now),
                ("Петров Михаил Юрьевич", "Служба безопасности", "Заместитель начальника СБ", "present", "admin", "+7 903 712-90-55", now),
                ("Кузнецова Ольга Андреевна", "Бухгалтерия", "Главный бухгалтер", "absent", "employee", "+7 915 303-45-77", now),
                ("Морозов Сергей Павлович", "АХЧ", "Заведующий хозяйством", "present", "employee", "+7 905 120-77-44", now),
            ]
            cursor.executemany(
                "INSERT INTO users (full_name, department, position, status, role, phone, created_at) VALUES (?, ?, ?, ?, ?, ?, ?);",
                initial_users
            )

            # Привязываем RFID-карты к созданным пользователям
            cards = [
                (1, "04:A2:8B:1F", "active", now, None),
                (2, "1C:44:E9:02", "active", now, None),
                (3, "FA:33:10:8C", "active", now, None),
                (4, "3B:77:22:9A", "active", now, None),
                (5, "88:F1:C3:09", "active", now, None),
            ]
            cursor.executemany(
                "INSERT INTO cards (user_id, card_number, status, issued_at, expires_at) VALUES (?, ?, ?, ?, ?);",
                cards
            )

            # Добавляем начальные события проходов
            events = [
                (now, "entry", 1, "04:A2:8B:1F", 1, "Иванов Алексей Сергеевич", "Штатный проход"),
                (now, "entry", 1, "1C:44:E9:02", 2, "Смирнова Елена Дмитриевна", "Штатный проход"),
                (now, "entry", 4, "FA:33:10:8C", 3, "Петров Михаил Юрьевич", "Доступ в серверную разрешен"),
            ]
            cursor.executemany(
                "INSERT INTO event_logs (timestamp, event_type, access_point_id, card_number, user_id, user_name, details) VALUES (?, ?, ?, ?, ?, ?, ?);",
                events
            )

        conn.commit()


# ------------------- CRUD ОПЕРАЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ -------------------

def add_user(user: User, db_path: str = DB_PATH) -> int:
    """Добавляет нового пользователя в базу данных и возвращает его ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (full_name, department, position, status, role, phone, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                user.full_name,
                user.department,
                user.position,
                user.status.value if isinstance(user.status, UserStatus) else user.status,
                user.role.value if isinstance(user.role, UserRole) else user.role,
                user.phone,
                user.created_at,
            )
        )
        conn.commit()
        return cursor.lastrowid


def find_users_by_query(query: str, db_path: str = DB_PATH) -> List[User]:
    """
    Быстрый поиск сотрудников по фамилии/имени или подразделению (Сценарий №1 ТЗ).
    Поиск регистронезависимый.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        search_pattern = f"%{query.strip().lower()}%"
        cursor.execute(
            """
            SELECT * FROM users 
            WHERE LOWER(full_name) LIKE ? OR LOWER(department) LIKE ?
            ORDER BY full_name ASC;
            """,
            (search_pattern, search_pattern)
        )
        rows = cursor.fetchall()
        return [
            User(
                id=r["id"],
                full_name=r["full_name"],
                department=r["department"],
                position=r["position"],
                status=UserStatus(r["status"]),
                role=UserRole(r["role"]),
                phone=r["phone"],
                created_at=r["created_at"],
            )
            for r in rows
        ]


def get_user_by_id(user_id: int, db_path: str = DB_PATH) -> Optional[User]:
    """Получает пользователя по его идентификатору ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return User(
            id=row["id"],
            full_name=row["full_name"],
            department=row["department"],
            position=row["position"],
            status=UserStatus(row["status"]),
            role=UserRole(row["role"]),
            phone=row["phone"],
            created_at=row["created_at"],
        )


def update_user_status(user_id: int, new_status: UserStatus, db_path: str = DB_PATH):
    """Обновляет статус нахождения пользователя ('present' или 'absent')."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET status = ? WHERE id = ?;",
            (new_status.value if isinstance(new_status, UserStatus) else new_status, user_id)
        )
        conn.commit()


def get_present_users(db_path: str = DB_PATH) -> List[User]:
    """Возвращает список всех сотрудников и гостей, находящихся на объекте в данный момент."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE status = 'present' ORDER BY full_name ASC;")
        rows = cursor.fetchall()
        return [
            User(
                id=r["id"],
                full_name=r["full_name"],
                department=r["department"],
                position=r["position"],
                status=UserStatus(r["status"]),
                role=UserRole(r["role"]),
                phone=r["phone"],
                created_at=r["created_at"],
            )
            for r in rows
        ]


# ------------------- CRUD ОПЕРАЦИИ ДЛЯ КАРТ ДОСТУПА -------------------

def add_card(card: Card, db_path: str = DB_PATH) -> int:
    """Регистрирует RFID-карту за пользователем."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO cards (user_id, card_number, status, issued_at, expires_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (
                card.user_id,
                card.card_number,
                card.status.value if isinstance(card.status, CardStatus) else card.status,
                card.issued_at,
                card.expires_at,
            )
        )
        conn.commit()
        return cursor.lastrowid


def get_card_by_number(card_number: str, db_path: str = DB_PATH) -> Optional[Card]:
    """Находит карту по ее RFID UID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE card_number = ?;", (card_number.strip(),))
        row = cursor.fetchone()
        if not row:
            return None
        return Card(
            id=row["id"],
            user_id=row["user_id"],
            card_number=row["card_number"],
            status=CardStatus(row["status"]),
            issued_at=row["issued_at"],
            expires_at=row["expires_at"],
        )


def get_card_by_user_id(user_id: int, db_path: str = DB_PATH) -> Optional[Card]:
    """Получает активную карту сотрудника."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE user_id = ? ORDER BY id DESC LIMIT 1;", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return Card(
            id=row["id"],
            user_id=row["user_id"],
            card_number=row["card_number"],
            status=CardStatus(row["status"]),
            issued_at=row["issued_at"],
            expires_at=row["expires_at"],
        )


def update_card_status(card_number: str, new_status: CardStatus, db_path: str = DB_PATH):
    """Блокирует или активирует карту доступа."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cards SET status = ? WHERE card_number = ?;",
            (new_status.value if isinstance(new_status, CardStatus) else new_status, card_number)
        )
        conn.commit()


# ------------------- ТОЧКИ ПРОХОДА (ТУРНИКЕТЫ И ДВЕРИ) -------------------

def get_all_access_points(db_path: str = DB_PATH) -> List[AccessPoint]:
    """Возвращает все сконфигурированные точки прохода."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM access_points ORDER BY id ASC;")
        rows = cursor.fetchall()
        return [
            AccessPoint(
                id=r["id"],
                name=r["name"],
                location=r["location"],
                lock_status=LockStatus(r["lock_status"]),
                is_alarm=bool(r["is_alarm"]),
            )
            for r in rows
        ]


def get_access_point_by_id(point_id: int, db_path: str = DB_PATH) -> Optional[AccessPoint]:
    """Получает точку доступа по её идентификатору."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM access_points WHERE id = ?;", (point_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return AccessPoint(
            id=row["id"],
            name=row["name"],
            location=row["location"],
            lock_status=LockStatus(row["lock_status"]),
            is_alarm=bool(row["is_alarm"]),
        )


def set_point_alarm(point_id: int, is_alarm: bool, db_path: str = DB_PATH):
    """Устанавливает или сбрасывает статус тревоги на точке прохода."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE access_points SET is_alarm = ? WHERE id = ?;",
            (1 if is_alarm else 0, point_id)
        )
        conn.commit()


def set_point_lock(point_id: int, lock_status: LockStatus, db_path: str = DB_PATH):
    """Устанавливает режим блокировки исполнительного механизма точки."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE access_points SET lock_status = ? WHERE id = ?;",
            (lock_status.value if isinstance(lock_status, LockStatus) else lock_status, point_id)
        )
        conn.commit()


# ------------------- ЖУРНАЛ СОБЫТИЙ (EVENT LOGS) -------------------

def log_event(event: EventLog, db_path: str = DB_PATH) -> int:
    """Записывает событие прохода или тревоги в журнал."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO event_logs (timestamp, event_type, access_point_id, card_number, user_id, user_name, details)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                event.timestamp,
                event.event_type.value if isinstance(event.event_type, EventType) else event.event_type,
                event.access_point_id,
                event.card_number,
                event.user_id,
                event.user_name,
                event.details,
            )
        )
        conn.commit()
        return cursor.lastrowid


def get_recent_events(limit: int = 50, db_path: str = DB_PATH) -> List[EventLog]:
    """Возвращает последние события из журнала для ленты мониторинга."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM event_logs ORDER BY id DESC LIMIT ?;",
            (limit,)
        )
        rows = cursor.fetchall()
        return [
            EventLog(
                id=r["id"],
                timestamp=r["timestamp"],
                event_type=EventType(r["event_type"]),
                access_point_id=r["access_point_id"],
                card_number=r["card_number"],
                user_id=r["user_id"],
                user_name=r["user_name"],
                details=r["details"],
            )
            for r in rows
        ]


def get_user_events(user_id: int, limit: int = 20, db_path: str = DB_PATH) -> List[EventLog]:
    """Возвращает историю проходов конкретного сотрудника (Сценарий №1)."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM event_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?;",
            (user_id, limit)
        )
        rows = cursor.fetchall()
        return [
            EventLog(
                id=r["id"],
                timestamp=r["timestamp"],
                event_type=EventType(r["event_type"]),
                access_point_id=r["access_point_id"],
                card_number=r["card_number"],
                user_id=r["user_id"],
                user_name=r["user_name"],
                details=r["details"],
            )
            for r in rows
        ]
