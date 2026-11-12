import sys
from datetime import datetime
from src.core import ClearAccessCore
from src.models import UserRole, LockStatus, CardStatus
import src.database as db


def print_banner():
    print("=" * 65)
    print("   СКУД ClearAccess («Прозрачный доступ») — Прототип v0.1")
    print("   Лаконичный интерфейс, быстрый поиск и учет доступа")
    print("=" * 65)


def display_menu():
    print("\nГЛАВНОЕ МЕНЮ ОПЕРАТОРА:")
    print("  [1] 🔍 [Сценарий 1] Быстрый поиск сотрудника (по фамилии)")
    print("  [2] 🪪 [Сценарий 2] Выдать временный пропуск за 2 клика")
    print("  [3] 🚨 [Сценарий 3] Симуляция тревоги (сработка датчика двери)")
    print("  [4] 💳 Приложить RFID-карту к турникету (эмуляция считывателя)")
    print("  [5] 👥 Сводка присутствующих на объекте (для МЧС и охраны)")
    print("  [6] 📜 Журнал последних событий (Live Log)")
    print("  [7] 🚪 Статус точек доступа (турникеты и блокировки)")
    print("  [8] 🧪 Запустить автотест всех сценариев")
    print("  [0] Выход")


def action_search_employee(app: ClearAccessCore):
    print("\n--- СЦЕНАРИЙ 1: БЫСТРЫЙ ПОИСК СОТРУДНИКА ---")
    query = input("Введите фамилию или подразделение (например, Иванов, Смирнова, ИТ): ").strip()
    if not query:
        print("Поисковый запрос не может быть пустым.")
        return

    results = app.quick_search_employee(query)
    if not results:
        print(f"❌ По запросу '{query}' никто не найден.")
        return

    print(f"\nНайдено записей: {len(results)}")
    for idx, item in enumerate(results, start=1):
        u = item["user"]
        c = item["card"]
        status_marker = "🟢 НА ОБЪЕКТЕ" if item["is_present"] else "⚪ ВНЕ ОБЪЕКТА"
        print(f"\n{idx}. {u.full_name} | {status_marker}")
        print(f"   Должность:     {u.position} ({u.department})")
        print(f"   RFID-карта:    {c.card_number if c else 'Не привязана'} (Статус: {c.status.value if c else '—'})")
        print(f"   Телефон:       {u.phone or 'Не указан'}")
        
        events = item["recent_events"]
        if events:
            print("   Последние события проходов:")
            for e in events[:3]:
                print(f"     • [{e.timestamp[:19]}] {e.event_type.value.upper()} | {e.details or ''}")
        else:
            print("   Проходов за текущую смену нет.")


def action_issue_temporary_pass(app: ClearAccessCore):
    print("\n--- СЦЕНАРИЙ 2: ВЫДАЧА ВРЕМЕННОГО ПРОПУСКА В 2 КЛИКА ---")
    name = input("1. ФИО посетителя: ").strip()
    if not name:
        print("Ошибка: ФИО обязательно.")
        return

    purpose = input("2. Организация / цель визита (Enter для 'Гостевой визит'): ").strip()
    
    # Генерация или ввод номера карты
    default_card = f"TMP:{datetime.now().strftime('%M%S')}:AA"
    card_in = input(f"3. Номер RFID-карты (Enter для автогенерации '{default_card}'): ").strip()
    card_number = card_in if card_in else default_card

    try:
        res = app.issue_temporary_pass(
            full_name=name,
            department_or_purpose=purpose or "Гостевой визит",
            card_number=card_number,
            validity_hours=8,
            role=UserRole.GUEST
        )
        print(f"\n✅ {res['message']}")
        print(f"   Пропуск #{res['card'].id} выдан на 8 часов. Карта {card_number} активна!")
    except ValueError as e:
        print(f"❌ Ошибка выдачи: {e}")


def action_trigger_alarm(app: ClearAccessCore):
    print("\n--- СЦЕНАРИЙ 3: РЕАКЦИЯ НА ТРЕВОЖНОЕ СОБЫТИЕ ---")
    points = db.get_all_access_points(app.db_path)
    print("Выберите точку доступа для симуляции сработки датчика:")
    for p in points:
        alarm_text = "🚨 ТРЕВОГА" if p.is_alarm else "Норма"
        print(f"  [{p.id}] {p.name} ({alarm_text})")

    try:
        pid = int(input("Введите ID точки: ").strip())
        res = app.trigger_sensor_alarm(pid, reason="Несанкционированное вскрытие дверного полотна")
        print(f"\n🚨 {res['message']}")
        print("Зона подсвечена на схеме охраны!")

        # Предлагаем оператору мгновенное действие
        act = input("Действие охраны: [1] Заблокировать точку, [2] Снять тревогу, [Enter] Оставить: ").strip()
        if act == "1":
            db.set_point_lock(pid, LockStatus.LOCKED, app.db_path)
            print("🔒 Точка доступа экстренно ЗАБЛОКИРОВАНА.")
        elif act == "2":
            app.clear_sensor_alarm(pid)
            print("✅ Тревога снята и квитирована.")
    except (ValueError, IndexError) as e:
        print(f"Ошибка ввода: {e}")


def action_emulate_pass(app: ClearAccessCore):
    print("\n--- ЭМУЛЯЦИЯ ПРИКЛАДЫВАНИЯ КАРТЫ К СЧИТЫВАТЕЛЮ ---")
    print("Примеры зарегистрированных карт:")
    print("  04:A2:8B:1F - Иванов (ИТ)")
    print("  1C:44:E9:02 - Смирнова (Кадры)")
    print("  FA:33:10:8C - Петров (СБ)")
    print("  99:99:99:99 - Неизвестная незарегистрированная карта")
    
    card_number = input("\nВведите номер RFID-карты: ").strip()
    direction = input("Направление: [1] Вход, [2] Выход (по умолчанию 1): ").strip()
    dir_val = "exit" if direction == "2" else "entry"

    res = app.process_pass_attempt(card_number, point_id=1, direction=dir_val)
    if res["granted"]:
        print(f"\n🟢 ДОСТУП РАЗРЕШЕН! Турникет открыт.")
        print(f"   Сотрудник: {res['user_name']} ({res['department']})")
    else:
        print(f"\n🔴 ДОСТУП ЗАПРЕЩЕН! {res['reason']}")


def action_evacuation_list(app: ClearAccessCore):
    print("\n--- СВОДКА ПРИСУТСТВУЮЩИХ НА ОБЪЕКТЕ (МЧС / ОХРАНА) ---")
    present = app.get_evacuation_summary()
    print(f"Всего людей на территории: {len(present)} чел.\n")
    print(f"{'№':<3} | {'ФИО':<30} | {'Подразделение':<25} | {'Категория':<10}")
    print("-" * 75)
    for idx, u in enumerate(present, start=1):
        print(f"{idx:<3} | {u.full_name:<30} | {u.department:<25} | {u.role.value:<10}")


def action_show_logs(app: ClearAccessCore):
    print("\n--- ЖУРНАЛ ПОСЛЕДНИХ СОБЫТИЙ СКУД ---")
    events = db.get_recent_events(limit=10, db_path=app.db_path)
    for e in events:
        print(f"[{e.timestamp[11:19]}] {e.event_type.value.upper():<8} | Карта: {e.card_number:<12} | {e.user_name or '—':<24} | {e.details or ''}")


def action_show_points(app: ClearAccessCore):
    print("\n--- ТОЧКИ ПРОХОДА И РЕЖИМЫ РАБОТЫ ---")
    points = db.get_all_access_points(app.db_path)
    for p in points:
        alarm = "🚨 ТРЕВОГА" if p.is_alarm else "✅ Норма"
        lock = "🔒 Блокирован" if p.lock_status == LockStatus.LOCKED else "🟢 Штатный"
        print(f"[{p.id}] {p.name:<38} | Замок: {lock:<14} | Сигнализация: {alarm}")


def run_auto_tests(app: ClearAccessCore):
    print("\n--- ЗАПУСК АВТОМАТИЧЕСКОЙ ПРОВЕРКИ 3 СЦЕНАРИЕВ ---")
    print("1. Тест сценария 1 (Поиск 'Иванов')...", end=" ")
    res1 = app.quick_search_employee("Иванов")
    assert len(res1) > 0 and res1[0]["user"].full_name == "Иванов Алексей Сергеевич"
    print("УСПЕШНО ✅")

    print("2. Тест сценария 2 (Выдача временного пропуска)...", end=" ")
    res2 = app.issue_temporary_pass("Тестовый Гость", "Тест-Компания", "TMP:TEST:01", 8)
    assert res2["success"] is True
    print("УСПЕШНО ✅")

    print("3. Тест валидации прохода по выданной карте...", end=" ")
    res_pass = app.process_pass_attempt("TMP:TEST:01", 1, "entry")
    assert res_pass["granted"] is True
    print("УСПЕШНО ✅")

    print("4. Тест сценария 3 (Сработка тревоги)...", end=" ")
    res_alarm = app.trigger_sensor_alarm(4, "Тестовый взлом")
    assert res_alarm["is_alarm"] is True
    app.clear_sensor_alarm(4)
    print("УСПЕШНО ✅")
    print("\nВсе ключевые сценарии работают корректно и соответствуют ТЗ!")


def main():
    app = ClearAccessCore()
    print_banner()

    # Если передан аргумент --test, запускаем автотест и выходим
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_auto_tests(app)
        return

    while True:
        display_menu()
        choice = input("\nВыберите действие (0-8): ").strip()

        if choice == "1":
            action_search_employee(app)
        elif choice == "2":
            action_issue_temporary_pass(app)
        elif choice == "3":
            action_trigger_alarm(app)
        elif choice == "4":
            action_emulate_pass(app)
        elif choice == "5":
            action_evacuation_list(app)
        elif choice == "6":
            action_show_logs(app)
        elif choice == "7":
            action_show_points(app)
        elif choice == "8":
            run_auto_tests(app)
        elif choice == "0":
            print("\nЗавершение работы СКУД ClearAccess. До свидания!")
            break
        else:
            print("Неверный выбор. Пожалуйста, введите цифру от 0 до 8.")


if __name__ == "__main__":
    main()
