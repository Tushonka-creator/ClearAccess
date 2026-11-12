"""
Модуль моделей данных (Data Models) для СКУД ClearAccess.
Определяет сущности предметной области контроля доступа в соответствии с ТЗ.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class UserStatus(str, Enum):
    """Текущее местонахождение человека относительно объекта."""
    PRESENT = "present"   # Находится на объекте
    ABSENT = "absent"     # Вне объекта


class UserRole(str, Enum):
    """Категория пользователя."""
    EMPLOYEE = "employee"      # Штатный сотрудник
    GUEST = "guest"            # Разовый посетитель / гость
    CONTRACTOR = "contractor"  # Подрядчик / сервис
    ADMIN = "admin"            # Администратор / охрана


class CardStatus(str, Enum):
    """Статус RFID-карты доступа."""
    ACTIVE = "active"          # Активна, проход разрешен
    BLOCKED = "blocked"        # Заблокирована (черный список / утеря)
    TEMPORARY = "temporary"    # Временная (разовый пропуск)
    EXPIRED = "expired"        # Истек срок действия


class LockStatus(str, Enum):
    """Режим работы исполнительного механизма (замка / турникета)."""
    NORMAL = "normal"                          # Штатный режим (по картам)
    LOCKED = "locked"                          # Принудительно заблокирован
    UNLOCKED_EMERGENCY = "unlocked_emergency"  # Аварийная разблокировка (эвакуация / пожар)


class EventType(str, Enum):
    """Тип события в журнале СКУД."""
    ENTRY = "entry"            # Успешный вход
    EXIT = "exit"              # Успешный выход
    DENIED = "denied"          # Отказ в доступе (карта заблокирована или нет прав)
    ALARM = "alarm"            # Тревога (сработка геркона, взлом двери)
    TEMP_PASS = "temp_pass"    # Выдача временного пропуска


@dataclass
class User:
    """Сущность сотрудника или посетителя."""
    id: Optional[int]
    full_name: str
    department: str
    position: str = "Сотрудник"
    status: UserStatus = UserStatus.ABSENT
    role: UserRole = UserRole.EMPLOYEE
    phone: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Card:
    """Электронная RFID-карта (пропуск)."""
    id: Optional[int]
    user_id: int
    card_number: str                 # Уникальный UID карты, например "04:A2:8B:1F"
    status: CardStatus = CardStatus.ACTIVE
    issued_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None # Срок окончания для временных карт


@dataclass
class AccessPoint:
    """Точка прохода (турникет, дверь со считывателем, шлагбаум)."""
    id: Optional[int]
    name: str                        # Например: "КПП-1 (Турникет А)"
    location: str                    # Например: "Главный вестибюль, 1 этаж"
    lock_status: LockStatus = LockStatus.NORMAL
    is_alarm: bool = False           # Флаг тревоги (взлом/удержание створки)


@dataclass
class EventLog:
    """Запись в журнале событий СКУД."""
    id: Optional[int]
    timestamp: str
    event_type: EventType
    access_point_id: int
    card_number: str
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    details: Optional[str] = None
