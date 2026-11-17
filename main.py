"""
Главный файл запуска прототипа СКУД ClearAccess.
Демонстрирует работу основных сценариев (поиск, выдача пропуска, симуляция прохода).
"""

from src.core import ClearAccessCore


def main():
    print("=== Инициализация системы СКУД ClearAccess ===")
    core = ClearAccessCore()

    print("\n--- [Сценарий 1] Поиск сотрудника по запросу 'Иванов' ---")
    found = core.quick_search_employee("Иванов")
    for item in found:
        user = item["user"]
        print(f"Сотрудник: {user.full_name} | Отдел: {user.department}")
        print(f"Статус: {item['status_text']} | Карта: {item['card'].card_number}")
        print(f"Последних событий в логе: {len(item['recent_events'])}")

    print("\n--- [Сценарий 2] Выдача временного гостевого пропуска ---")
    try:
        pass_result = core.issue_temporary_pass(
            full_name="Власов Олег Игоревич",
            department_or_purpose="Технический аудит",
            card_number="99:88:77:66",
            validity_hours=2
        )
        print(pass_result["message"])
    except Exception as e:
        print(f"Ошибка выдачи пропуска: {e}")

    print("\n--- [Тест прохода через турникет КПП-1] ---")
    # Проверяем карту штатного сотрудника (Иванов Алексей, карта 04:A2:8B:1F)
    access_result = core.process_pass_attempt("04:A2:8B:1F", point_id=1, direction="entry")
    print(f"Результат прохода: {access_result.get('message')}")

    print("\n--- [Сводка МЧС: Список людей на объекте] ---")
    present_users = core.get_evacuation_summary()
    print(f"Всего людей на объекте: {len(present_users)}")
    for u in present_users:
        print(f" • {u.full_name} ({u.department})")

    print("\nПрототип успешно запущен и готов к работе!")


if __name__ == "__main__":
    main()