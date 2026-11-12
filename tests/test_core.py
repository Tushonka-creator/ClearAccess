"""
Модульные тесты для проверки бизнес-логики и базы данных СКУД ClearAccess (Этап 6 ТЗ).
Использует стандартную библиотеку unittest (не требует сторонних зависимостей).
Проверяют работу 3 пользовательских сценариев и валидацию данных.
"""

import os
import tempfile
import unittest

from src.models import UserRole, UserStatus, CardStatus
from src.core import ClearAccessCore
import src.database as db


class TestClearAccessCore(unittest.TestCase):
    """Набор тестов для проверки ядра СКУД ClearAccess."""

    def setUp(self):
        """Создает изолированную временную базу данных SQLite для каждого теста."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_scud.db")
        self.core_app = ClearAccessCore(db_path=self.temp_db_path)

    def tearDown(self):
        """Очищает временные файлы после теста."""
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    def test_01_initial_seed_data(self):
        """Проверка начальной инициализации базы данных."""
        points = db.get_all_access_points(self.core_app.db_path)
        self.assertGreaterEqual(len(points), 4, "Точки прохода должны быть инициализированы")

        users = db.find_users_by_query("Иванов", self.core_app.db_path)
        self.assertEqual(len(users), 1, "Сотрудник Иванов должен присутствовать в демо-данных")
        self.assertEqual(users[0].full_name, "Иванов Алексей Сергеевич")

    def test_02_scenario_1_quick_search(self):
        """
        Тест Сценария 1: Быстрый поиск сотрудника охраной.
        Охранник вводит фамилию -> мгновенно получает статус и хронологию.
        """
        results = self.core_app.quick_search_employee("Смирнова")
        self.assertEqual(len(results), 1)
        found = results[0]
        self.assertEqual(found["user"].full_name, "Смирнова Елена Дмитриевна")
        self.assertTrue(found["is_present"])
        self.assertEqual(found["status_text"], "НА ОБЪЕКТЕ")
        self.assertEqual(found["card"].card_number, "1C:44:E9:02")
        self.assertGreaterEqual(len(found["recent_events"]), 1)

    def test_03_scenario_2_issue_temporary_pass(self):
        """
        Тест Сценария 2: Выдача временного пропуска за 2 клика.
        """
        result = self.core_app.issue_temporary_pass(
            full_name="Николаев Виктор Сергеевич",
            department_or_purpose="ООО 'АудитКонсалт'",
            card_number="TMP:AA:11:22",
            validity_hours=8,
            role=UserRole.GUEST,
            phone="+7 999 123-45-67"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["user"].full_name, "Николаев Виктор Сергеевич")
        self.assertEqual(result["card"].card_number, "TMP:AA:11:22")
        self.assertEqual(result["card"].status, CardStatus.TEMPORARY)

        # Проверяем, что пропуск теперь работает на турникете
        pass_res = self.core_app.process_pass_attempt("TMP:AA:11:22", point_id=1, direction="entry")
        self.assertTrue(pass_res["granted"])
        self.assertIn("Николаев", pass_res["user_name"])

    def test_04_scenario_3_security_alarm(self):
        """
        Тест Сценария 3: Реакция на тревожное событие (сработка датчика).
        """
        # Срабатывает тревога на Серверной 302 (point_id=4)
        alarm_res = self.core_app.trigger_sensor_alarm(point_id=4, reason="Взлом замка двери")
        self.assertTrue(alarm_res["success"])
        self.assertTrue(alarm_res["is_alarm"])

        # Проверяем в базе
        point = db.get_access_point_by_id(4, self.core_app.db_path)
        self.assertTrue(point.is_alarm)

        # Оператор квитирует тревогу
        clear_res = self.core_app.clear_sensor_alarm(point_id=4)
        self.assertTrue(clear_res["success"])

        point_after = db.get_access_point_by_id(4, self.core_app.db_path)
        self.assertFalse(point_after.is_alarm)

    def test_05_blocked_card_denial(self):
        """Тест запрета прохода по заблокированной карте."""
        # Блокируем карту Кузнецовой (3B:77:22:9A)
        db.update_card_status("3B:77:22:9A", CardStatus.BLOCKED, self.core_app.db_path)

        # Попытка прохода
        pass_res = self.core_app.process_pass_attempt("3B:77:22:9A", point_id=1, direction="entry")
        self.assertFalse(pass_res["granted"])
        self.assertEqual(pass_res["reason"], "Карта заблокирована")

    def test_06_unknown_card_denial(self):
        """Тест запрета прохода по неизвестной карте."""
        pass_res = self.core_app.process_pass_attempt("UNKNOWN:99:99", point_id=1, direction="entry")
        self.assertFalse(pass_res["granted"])
        self.assertEqual(pass_res["reason"], "Неизвестная карта")

    def test_07_evacuation_summary(self):
        """Тест формирования списка присутствующих для МЧС."""
        present_list = self.core_app.get_evacuation_summary()
        self.assertGreater(len(present_list), 0)
        for u in present_list:
            self.assertEqual(u.status, UserStatus.PRESENT)


if __name__ == "__main__":
    unittest.main()
