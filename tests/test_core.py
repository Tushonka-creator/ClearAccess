import os
import tempfile
import unittest

from src.core import ClearAccessCore
from src.models import CardStatus, UserRole, LockStatus


class TestClearAccessCore(unittest.TestCase):
    def setUp(self):
        # Создаем временную базу данных для изолированного тестирования
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.core = ClearAccessCore(db_path=self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_scenario_1_quick_search(self):
        """Тест сценария 1: Быстрый поиск сотрудника и хронология проходов."""
        results = self.core.quick_search_employee("Иванов")
        self.assertTrue(len(results) > 0)

        employee_data = results[0]
        self.assertEqual(employee_data["user"].full_name, "Иванов Алексей Сергеевич")
        self.assertTrue(employee_data["is_present"])
        self.assertIsNotNone(employee_data["card"])

    def test_scenario_2_issue_temporary_pass(self):
        """Тест сценария 2: Выдача временного пропуска."""
        res = self.core.issue_temporary_pass(
            full_name="Тестовый Гость",
            department_or_purpose="Совещание",
            card_number="FF:FF:FF:FF",
            validity_hours=4,
            role=UserRole.GUEST
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["user"].full_name, "Тестовый Гость")
        self.assertEqual(res["card"].status, CardStatus.TEMPORARY)

        # Проверяем проход по выданной временной карте
        pass_res = self.core.process_pass_attempt(card_number="FF:FF:FF:FF", point_id=1, direction="entry")
        self.assertTrue(pass_res["granted"])

    def test_scenario_3_alarm_and_blocking(self):
        """Тест сценария 3: Реакция на тревогу и управление блокировкой."""
        # Срабатывание датчика
        alarm_res = self.core.trigger_sensor_alarm(point_id=3)
        self.assertTrue(alarm_res["is_alarm"])

        # Снятие тревоги
        clear_res = self.core.clear_sensor_alarm(point_id=3)
        self.assertTrue(clear_res["success"])


if __name__ == "__main__":
    unittest.main()