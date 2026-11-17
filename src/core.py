"""
Модуль бизнес-логики (Core Logic) для СКУД ClearAccess.
Реализует 3 ключевых пользовательских сценария из проектного задания:
1. Быстрый поиск сотрудника и хронология проходов.
2. Выдача временного пропуска за 2 клика.
3. Реакция на тревожные события и управление блокировками.
А также базовый алгоритм валидации карт на контроллерах турникетов.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from src.models import (
    User, Card, AccessPoint, EventLog,
    UserStatus, UserRole, CardStatus, LockStatus, EventType
)
import src.database as db


class ClearAccessCore:
    """Ядро системы управления доступом ClearAccess."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or db.DB_PATH
        # Инициализируем базу данных и сидируем демо-данные
        db.init_db(self.db_path)
        db.seed_initial_data(self.db_path)

    # -------------------------------------------------------------------------
    # СЦЕНАРИЙ 1: БЫСТРЫЙ ПОИСК СОТРУДНИКА (ДЛЯ ОХРАНЫ)
    # -------------------------------------------------------------------------

    def quick_search_employee(self, query: str) -> List[Dict[str, Any]]:
        """
        Сценарий 1 ТЗ: Охранник вводит фамилию в строку поиска.
        Программа мгновенно находит сотрудника, показывает его статус (на объекте ли он)
        и выводит хронологию последних проходов.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        users = db.find_users_by_query(clean_query, self.db_path)
        results = []

        for user in users:
            # Получаем карту сотрудника
            card = db.get_card_by_user_id(user.id, self.db_path)
            # Получаем последние 5 проходов сотрудника
            events = db.get_user_events(user.id, limit=5, db_path=self.db_path)

            results.append({
                "user": user,
                "card": card,
                "is_present": user.status == UserStatus.PRESENT,
                "status_text": "НА ОБЪЕКТЕ" if user.status == UserStatus.PRESENT else "ВНЕ ОБЪЕКТА",
                "recent_events": events,
            })

        return results

    # -------------------------------------------------------------------------
    # СЦЕНАРИЙ 2: ВЫДАЧА ВРЕМЕННОГО ПРОПУСКА В 2 КЛИКА (ДЛЯ АДМИНИСТРАТОРА)
    # -------------------------------------------------------------------------

    def issue_temporary_pass(
        self,
        full_name: str,
        department_or_purpose: str,
        card_number: str,
        validity_hours: int = 8,
        role: UserRole = UserRole.GUEST,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Сценарий 2 ТЗ: Администратор нажимает «Новый пропуск»,
        вводит данные гостя и прикладывает карту.
        Программа записывает карту в базу и активирует доступ без сложных меню.
        """
        if not full_name.strip():
            raise ValueError("ФИО посетителя не может быть пустым.")

        if not card_number.strip():
            raise ValueError("Номер карты RFID обязателен для выдачи пропуска.")

        # Проверяем, не занята ли уже эта карта
        existing_card = db.get_card_by_number(card_number, self.db_path)
        if existing_card:
            raise ValueError(f"Карта {card_number} уже зарегистрирована в системе.")

        now = datetime.now()
        expires_at = (now + timedelta(hours=validity_hours)).isoformat()

        # 1. Создаем пользователя (гостя/подрядчика)
        new_user = User(
            id=None,
            full_name=full_name.strip(),
            department=department_or_purpose.strip() or "Гостевой визит",
            position="Посетитель" if role == UserRole.GUEST else "Подрядчик",
            status=UserStatus.PRESENT,  # Считается зашедшим на объект
            role=role,
            phone=phone,
            created_at=now.isoformat()
        )
        user_id = db.add_user(new_user, self.db_path)
        new_user.id = user_id

        # 2. Регистрируем временную RFID-карту
        new_card = Card(
            id=None,
            user_id=user_id,
            card_number=card_number.strip(),
            status=CardStatus.TEMPORARY,
            issued_at=now.isoformat(),
            expires_at=expires_at
        )
        card_id = db.add_card(new_card, self.db_path)
        new_card.id = card_id

        # 3. Фиксируем выдачу пропуска в журнале
        db.log_event(
            EventLog(
                id=None,
                timestamp=now.isoformat(),
                event_type=EventType.TEMP_PASS,
                access_point_id=1,  # КПП-1
                card_number=card_number,
                user_id=user_id,
                user_name=full_name,
                details=f"Выдан разовый пропуск на {validity_hours} ч. (действует до {expires_at[:16]})"
            ),
            self.db_path
        )

        return {
            "success": True,
            "user": new_user,
            "card": new_card,
            "message": f"Пропуск успешно выдан для {full_name} на {validity_hours} ч."
        }

    # -------------------------------------------------------------------------
    # СЦЕНАРИЙ 3: РЕАКЦИЯ НА ТРЕВОЖНОЕ СОБЫТИЕ (ДАТЧИК / ВЗЛОМ)
    # -------------------------------------------------------------------------

    def trigger_sensor_alarm(self, point_id: int, reason: str = "Сработка физического датчика двери (геркон)") -> Dict[str, Any]:
        """
        Сценарий 3 ТЗ: Срабатывает физический датчик.
        Программа подсвечивает проблемную зону, фиксирует тревогу в логах
        и позволяет оператору мгновенно среагировать.
        """
        point = db.get_access_point_by_id(point_id, self.db_path)
        if not point:
            raise ValueError(f"Точка прохода #{point_id} не найдена.")

        # Устанавливаем статус тревоги
        db.set_point_alarm(point_id, is_alarm=True, db_path=self.db_path)

        # Записываем тревогу в журнал
        now_iso = datetime.now().isoformat()
        db.log_event(
            EventLog(
                id=None,
                timestamp=now_iso,
                event_type=EventType.ALARM,
                access_point_id=point_id,
                card_number="SENSOR:ALARM",
                user_id=None,
                user_name="Система безопасности",
                details=f"ТРЕВОГА на точке '{point.name}': {reason}"
            ),
            self.db_path
        )

        return {
            "success": True,
            "point_id": point_id,
            "point_name": point.name,
            "is_alarm": True,
            "message": f"ТРЕВОГА: {point.name} — {reason}"
        }

    def clear_sensor_alarm(self, point_id: int) -> Dict[str, Any]:
        """Снимает/квитирует тревогу на точке прохода."""
        point = db.get_access_point_by_id(point_id, self.db_path)
        if not point:
            raise ValueError(f"Точка #{point_id} не найдена.")

        db.set_point_alarm(point_id, is_alarm=False, db_path=self.db_path)

        now_iso = datetime.now().isoformat()
        db.log_event(
            EventLog(
                id=None,
                timestamp=now_iso,
                event_type=EventType.ENTRY,
                access_point_id=point_id,
                card_number="OPERATOR:RESET",
                user_name="Оператор СКУД",
                details=f"Тревога квитирована и сброшена оператором"
            ),
            self.db_path
        )

        return {
            "success": True,
            "message": f"Тревога на точке '{point.name}' успешно снята."
        }

    # -------------------------------------------------------------------------
    # ОБРАБОТКА ПРОХОДА (ВАЛИДАЦИЯ RFID НА ТУРНИКЕТЕ)
    # -------------------------------------------------------------------------

    def process_pass_attempt(self, card_number: str, point_id: int, direction: str = "entry") -> Dict[str, Any]:
        """
        Основной цикл валидации прохода при прикладывании карты к считывателю:
        1. Проверка существования и режима точки прохода.
        2. Проверка карты в базе.
        3. Проверка статуса блокировки карты.
        4. Фиксация результата и обновление статуса сотрудника.
        """
        now_iso = datetime.now().isoformat()
        point = db.get_access_point_by_id(point_id, self.db_path)

        if not point:
            return {"granted": False, "reason": "Точка прохода не существует"}

        # Проверка блокировки точки доступа
        if point.lock_status == LockStatus.LOCKED:
            db.log_event(
                EventLog(
                    id=None,
                    timestamp=now_iso,
                    event_type=EventType.DENIED,
                    access_point_id=point_id,
                    card_number=card_number,
                    details="Отказ: точка прохода принудительно заблокирована охраной"
                ),
                self.db_path
            )
            return {"granted": False, "reason": "Точка прохода заблокирована"}

        # Поиск карты
        card = db.get_card_by_number(card_number, self.db_path)
        if not card:
            db.log_event(
                EventLog(
                    id=None,
                    timestamp=now_iso,
                    event_type=EventType.DENIED,
                    access_point_id=point_id,
                    card_number=card_number,
                    details="Отказ: карта не зарегистрирована в базе данных СКУД"
                ),
                self.db_path
            )
            return {"granted": False, "reason": "Неизвестная карта"}

        # Проверка статуса карты
        if card.status == CardStatus.BLOCKED:
            user = db.get_user_by_id(card.user_id, self.db_path)
            db.log_event(
                EventLog(
                    id=None,
                    timestamp=now_iso,
                    event_type=EventType.DENIED,
                    access_point_id=point_id,
                    card_number=card_number,
                    user_id=card.user_id,
                    user_name=user.full_name if user else "Неизвестно",
                    details="Отказ: карта находится в черном списке (заблокирована)"
                ),
                self.db_path
            )
            return {"granted": False, "reason": "Карта заблокирована"}

        # Проверка срока действия временной карты
        if card.status == CardStatus.TEMPORARY and card.expires_at:
            if datetime.now().isoformat() > card.expires_at:
                db.update_card_status(card.card_number, CardStatus.EXPIRED, self.db_path)
                return {"granted": False, "reason": "Срок действия временного пропуска истек"}

        # Успешный проход!
        user = db.get_user_by_id(card.user_id, self.db_path)
        new_status = UserStatus.PRESENT if direction == "entry" else UserStatus.ABSENT

        if user:
            db.update_user_status(user.id, new_status, self.db_path)

        event_type = EventType.ENTRY if direction == "entry" else EventType.EXIT
        db.log_event(
            EventLog(
                id=None,
                timestamp=now_iso,
                event_type=event_type,
                access_point_id=point_id,
                card_number=card_number,
                user_id=card.user_id,
                user_name=user.full_name if user else "Сотрудник",
                details=f"Проход разрешен ({'Вход' if direction == 'entry' else 'Выход'})"
            ),
            self.db_path
        )

        return {
            "granted": True,
            "user_name": user.full_name if user else "Сотрудник",
            "department": user.department if user else "",
            "direction": direction,
            "message": f"Доступ разрешен: {user.full_name if user else ''}"
        }

    # -------------------------------------------------------------------------
    # СВОДКА ДЛЯ МЧС И РУКОВОДСТВА
    # -------------------------------------------------------------------------

    def get_evacuation_summary(self) -> List[User]:
        """Возвращает список всех сотрудников и гостей, находящихся на объекте."""
        return db.get_present_users(self.db_path)
