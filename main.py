import json
import random
import re
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.resources import resource_add_path
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton


# =========================================================
# ОСНОВНЫЕ НАСТРОЙКИ
# =========================================================

BASE = Path(__file__).resolve().parent

resource_add_path(str(BASE))

FONT_PATH = BASE / "fonts" / "Arial.ttf"
DATA_PATH = BASE / "data" / "questions.json"
KV_PATH = BASE / "testov.kv"

APP_NAME = "ТехПрофи"

DEFAULT_NUM = 25
DEFAULT_MINUTES = 15
DEFAULT_PASS = 20

ADMIN_CODE = "TEST_OVIK"


# =========================================================
# ШРИФТ
# =========================================================

LabelBase.register(
    name="AppArial",
    fn_regular=str(FONT_PATH)
)


# =========================================================
# ЗАГРУЗКА БАНКА ВОПРОСОВ
# =========================================================

def load_bank():
    with DATA_PATH.open(
        "r",
        encoding="utf-8"
    ) as file:
        obj = json.load(file)

    bank_name = obj.get(
        "bank_name",
        ""
    )

    questions = obj.get(
        "questions",
        []
    )

    if not isinstance(
        questions,
        list
    ):
        raise ValueError(
            "Поле 'questions' в questions.json "
            "должно быть списком"
        )

    return bank_name, questions


# =========================================================
# НОРМАЛИЗАЦИЯ ОТВЕТОВ
# =========================================================

def canon_list(value):
    if isinstance(value, list):
        parts = value
    else:
        parts = str(
            value or ""
        ).split(";")

    return {
        str(item).strip().casefold()
        for item in parts
        if str(item).strip()
    }


# =========================================================
# ПРОВЕРКА ПРАВИЛЬНОСТИ ОТВЕТА
# =========================================================

def is_correct(question, answer):

    question_type = question.get(
        "type",
        ""
    )

    if question_type == "несколько":

        return (
            canon_list(answer)
            ==
            canon_list(
                question.get(
                    "correct",
                    []
                )
            )
        )

    acceptable = canon_list(
        question.get(
            "correct",
            []
        )
    )

    user_answer = str(
        answer or ""
    ).strip().casefold()

    return user_answer in acceptable


# =========================================================
# ОПРЕДЕЛЕНИЕ ТИПА КЛАВИАТУРЫ
# =========================================================

def is_numeric_answer(question):
    """
    Числовая клавиатура открывается только тогда,
    когда все допустимые ответы являются числами.

    Примеры:

    120
    2.5
    -15

    -> числовая клавиатура

    EI 60
    2 метра
    120 мм
    текст

    -> обычная клавиатура
    """

    correct = question.get(
        "correct",
        []
    )

    if not isinstance(
        correct,
        list
    ):
        correct = [correct]

    if not correct:
        return False

    numeric_pattern = re.compile(
        r"^[+-]?\d+(?:[.,]\d+)?$"
    )

    for answer in correct:

        answer_text = str(
            answer
        ).strip()

        if not numeric_pattern.fullmatch(
            answer_text
        ):
            return False

    return True


# =========================================================
# ГЛАВНЫЙ ЭКРАН
# =========================================================

class Login(Screen):

    bank = StringProperty("")
    admin_enabled = BooleanProperty(False)

    def on_pre_enter(self, *args):

        app = App.get_running_app()

        self.bank = getattr(
            app,
            "bank_name",
            ""
        )

        self.update_admin_state()

    def update_admin_state(
        self,
        *args
    ):

        if "name" not in self.ids:
            return

        value = (
            self.ids.name.text.strip()
        )

        self.admin_enabled = (
            value == ADMIN_CODE
        )

        if self.admin_enabled:

            self.ids.msg.text = (
                "Административный режим доступен"
            )

            self.ids.msg.color = (
                0.10,
                0.45,
                0.15,
                1
            )

        else:

            if (
                self.ids.msg.text
                ==
                "Административный режим доступен"
            ):
                self.ids.msg.text = ""

            self.ids.msg.color = (
                0.75,
                0.10,
                0.10,
                1
            )

    def open_settings(self):

        self.update_admin_state()

        if not self.admin_enabled:
            return

        # Очищаем служебный пароль
        # после входа в настройки.
        self.ids.name.text = ""

        self.manager.current = (
            "settings"
        )

    def start(self, mode):

        name = (
            self.ids.name.text.strip()
        )

        if not name:

            self.ids.msg.color = (
                0.75,
                0.10,
                0.10,
                1
            )

            self.ids.msg.text = (
                "Введите фамилию и инициалы"
            )

            return

        # Административный код нельзя
        # использовать как ФИО тестируемого.
        if name == ADMIN_CODE:

            self.ids.msg.color = (
                0.75,
                0.10,
                0.10,
                1
            )

            self.ids.msg.text = (
                "Для запуска тестирования "
                "введите ФИО тестируемого"
            )

            return

        app = App.get_running_app()

        app.user = name
        app.mode = mode

        app.prepare_questions()

        if not app.questions:

            self.ids.msg.text = (
                "Банк вопросов пуст"
            )

            return

        self.ids.msg.text = ""

        test_screen = (
            self.manager.get_screen(
                "test"
            )
        )

        # Сначала полностью подготавливаем тест.
        test_screen.begin()

        # Только после этого переходим
        # на экран тестирования.
        self.manager.current = "test"


# =========================================================
# ЭКРАН ТЕСТИРОВАНИЯ
# =========================================================

class Test(Screen):

    question = StringProperty("")
    progress = StringProperty("")
    timer = StringProperty("")
    source = StringProperty("")
    message = StringProperty("")

    idx = NumericProperty(0)

    event = None
    input = None
    btns = None

    # -----------------------------------------------------
    # НАЧАЛО ТЕСТА
    # -----------------------------------------------------

    def begin(self):

        app = App.get_running_app()

        self.idx = 0

        app.saved = [
            ""
            for _ in app.questions
        ]

        app.seconds = (
            DEFAULT_MINUTES * 60
        )

        self.message = ""
        self.source = ""

        if self.event:

            self.event.cancel()
            self.event = None

        # Таймер нужен только
        # в контрольном тестировании.
        if app.mode == "контроль":

            self.event = (
                Clock.schedule_interval(
                    self.tick,
                    1
                )
            )

        self.render()

    # -----------------------------------------------------
    # ТАЙМЕР
    # -----------------------------------------------------

    def tick(self, dt):

        app = App.get_running_app()

        app.seconds -= 1

        if app.seconds < 0:
            app.seconds = 0

        self.timer = (
            f"{app.seconds // 60:02d}:"
            f"{app.seconds % 60:02d}"
        )

        if app.seconds <= 0:

            self.finish()

            return False

        return True

    # -----------------------------------------------------
    # ПОЛУЧЕНИЕ ТЕКУЩЕГО ОТВЕТА
    # -----------------------------------------------------

    def get_current_answer(self):

        app = App.get_running_app()

        if not app.questions:
            return ""

        if self.idx < 0:
            return ""

        if self.idx >= len(
            app.questions
        ):
            return ""

        question = (
            app.questions[self.idx]
        )

        question_type = (
            question.get(
                "type",
                ""
            )
        )

        # Текстовый вопрос
        if question_type == "текстовый":

            if self.input is None:
                return ""

            return (
                self.input.text.strip()
            )

        # Один вариант ответа
        if question_type == "один":

            if not self.btns:
                return ""

            for button in self.btns:

                if button.state == "down":
                    return button.text

            return ""

        # Несколько вариантов ответа
        if question_type == "несколько":

            if not self.btns:
                return ""

            selected = []

            for (
                option,
                checkbox
            ) in self.btns:

                if checkbox.active:
                    selected.append(
                        option
                    )

            return "; ".join(
                selected
            )

        return ""

    # -----------------------------------------------------
    # СОХРАНЕНИЕ ОТВЕТА
    # -----------------------------------------------------

    def save_current(self):

        app = App.get_running_app()

        answer = (
            self.get_current_answer()
        )

        if (
            0 <= self.idx
            < len(app.saved)
        ):
            app.saved[self.idx] = answer

        return answer

    # -----------------------------------------------------
    # ПРОВЕРКА НАЛИЧИЯ ОТВЕТА
    # -----------------------------------------------------

    def has_answer(self):

        answer = (
            self.get_current_answer()
        )

        return bool(
            str(answer).strip()
        )

    # -----------------------------------------------------
    # ОТОБРАЖЕНИЕ ВОПРОСА
    # -----------------------------------------------------

    def render(self):

        app = App.get_running_app()

        if not app.questions:
            return

        if self.idx < 0:
            self.idx = 0

        if self.idx >= len(
            app.questions
        ):
            self.idx = (
                len(app.questions) - 1
            )

        question = (
            app.questions[self.idx]
        )

        self.question = (
            question.get(
                "text",
                ""
            )
        )

        self.progress = (
            f"Вопрос {self.idx + 1} "
            f"из {len(app.questions)}"
        )

        self.message = ""
        self.source = ""

        if app.mode == "обучение":

            self.timer = ""

        else:

            self.timer = (
                f"{app.seconds // 60:02d}:"
                f"{app.seconds % 60:02d}"
            )

        answers_box = (
            self.ids.answers
        )

        answers_box.clear_widgets()

        self.input = None
        self.btns = []

        question_type = (
            question.get(
                "type",
                ""
            )
        )

        saved_answer = ""

        if (
            self.idx
            < len(app.saved)
        ):
            saved_answer = (
                app.saved[self.idx]
            )

        # =================================================
        # ТЕКСТОВЫЙ ОТВЕТ
        # =================================================

        if question_type == "текстовый":

            if is_numeric_answer(
                question
            ):
                keyboard_type = "number"
            else:
                keyboard_type = "text"

            self.input = TextInput(
                text=saved_answer,
                multiline=False,
                font_name="AppArial",
                font_size="18sp",
                size_hint_y=None,
                height=dp(54),
                input_type=keyboard_type,
                write_tab=False
            )

            answers_box.add_widget(
                self.input
            )

        # =================================================
        # ОДИН ВАРИАНТ ОТВЕТА
        # =================================================

        elif question_type == "один":

            options = question.get(
                "options",
                []
            )

            for option in options:

                option_text = str(
                    option
                )

                button = ToggleButton(
                    text=option_text,
                    group="answer_group",
                    font_name="AppArial",
                    font_size="16sp",
                    size_hint_y=None,
                    height=dp(64),
                    halign="center",
                    valign="middle",
                    padding=(
                        dp(14),
                        dp(12)
                    )
                )

                # Ограничиваем ширину текста,
                # чтобы длинные ответы переносились.
                button.text_size = (
                    max(
                        Window.width
                        - dp(70),
                        dp(200)
                    ),
                    None
                )

                button.bind(
                    texture_size=(
                        self._resize_answer_button
                    )
                )

                if (
                    str(
                        saved_answer
                    ).strip()
                    ==
                    option_text
                ):
                    button.state = "down"

                answers_box.add_widget(
                    button
                )

                self.btns.append(
                    button
                )

        # =================================================
        # НЕСКОЛЬКО ВАРИАНТОВ
        # =================================================

        elif question_type == "несколько":

            saved = canon_list(
                saved_answer
            )

            options = question.get(
                "options",
                []
            )

            for option in options:

                option_text = str(
                    option
                )

                row = BoxLayout(
                    size_hint_y=None,
                    height=dp(64),
                    spacing=dp(8),
                    padding=(
                        dp(4),
                        dp(6)
                    )
                )

                checkbox = CheckBox(
                    active=(
                        option_text.casefold()
                        in saved
                    ),
                    size_hint_x=None,
                    width=dp(48)
                )

                label = Label(
                    text=option_text,
                    font_name="AppArial",
                    font_size="16sp",
                    color=(
                        0,
                        0,
                        0,
                        1
                    ),
                    halign="left",
                    valign="middle",
                    size_hint_y=None,
                    height=dp(52)
                )

                label.bind(
                    width=(
                        self._resize_multi_label
                    )
                )

                label.bind(
                    texture_size=(
                        self._resize_multi_row
                    )
                )

                row.add_widget(
                    checkbox
                )

                row.add_widget(
                    label
                )

                answers_box.add_widget(
                    row
                )

                self.btns.append(
                    (
                        option_text,
                        checkbox
                    )
                )

        # =================================================
        # НЕИЗВЕСТНЫЙ ТИП
        # =================================================

        else:

            self.question = (
                "Ошибка: неизвестный "
                "тип вопроса"
            )

    # -----------------------------------------------------
    # АДАПТИВНАЯ ВЫСОТА КНОПКИ
    # -----------------------------------------------------

    def _resize_answer_button(
        self,
        button,
        texture_size
    ):

        button.height = max(
            dp(64),
            texture_size[1] + dp(30)
        )

    # -----------------------------------------------------
    # ПЕРЕНОС ТЕКСТА MULTI
    # -----------------------------------------------------

    def _resize_multi_label(
        self,
        label,
        width
    ):

        label.text_size = (
            width,
            None
        )

    # -----------------------------------------------------
    # ВЫСОТА MULTI
    # -----------------------------------------------------

    def _resize_multi_row(
        self,
        label,
        texture_size
    ):

        label.height = max(
            dp(52),
            texture_size[1] + dp(18)
        )

        if label.parent:

            label.parent.height = (
                label.height + dp(12)
            )

    # -----------------------------------------------------
    # СЛЕДУЮЩИЙ ВОПРОС
    # -----------------------------------------------------

    def next(self):

        app = App.get_running_app()

        if not app.questions:
            return

        # Запрещаем переход,
        # пока пользователь не ответил.
        if not self.has_answer():

            self.message = (
                "Сначала выберите "
                "или введите ответ"
            )

            return

        self.message = ""

        self.save_current()

        # Последний вопрос.
        if self.idx >= (
            len(app.questions) - 1
        ):

            self.finish()

            return

        self.idx += 1

        self.render()

    # -----------------------------------------------------
    # ПРЕДЫДУЩИЙ ВОПРОС
    # -----------------------------------------------------

    def prev(self):

        app = App.get_running_app()

        if not app.questions:
            return

        self.save_current()

        self.message = ""

        if self.idx > 0:

            self.idx -= 1

            self.render()

    # -----------------------------------------------------
    # ПОКАЗАТЬ ПРАВИЛЬНЫЙ ОТВЕТ
    # -----------------------------------------------------

    def show_correct(self):

        app = App.get_running_app()

        if not app.questions:
            return

        if not self.has_answer():

            self.message = (
                "Сначала выберите "
                "или введите ответ"
            )

            return

        self.message = ""

        self.save_current()

        question = (
            app.questions[self.idx]
        )

        correct = question.get(
            "correct",
            []
        )

        if isinstance(
            correct,
            list
        ):

            correct_text = "; ".join(
                str(item)
                for item in correct
            )

        else:

            correct_text = str(
                correct
            )

        source = question.get(
            "source",
            ""
        )

        self.source = (
            "Правильный ответ: "
            + correct_text
            + "\n\nИсточник: "
            + str(source)
        )

    # -----------------------------------------------------
    # ЗАВЕРШЕНИЕ ТЕСТИРОВАНИЯ
    # -----------------------------------------------------

    def finish(self):

        app = App.get_running_app()

        # Сохраняем последний ответ,
        # если он существует.
        try:
            self.save_current()
        except Exception:
            pass

        # Останавливаем таймер.
        if self.event:

            self.event.cancel()
            self.event = None

        score = 0

        for (
            question,
            answer
        ) in zip(
            app.questions,
            app.saved
        ):

            if is_correct(
                question,
                answer
            ):
                score += 1

        required_score = min(
            DEFAULT_PASS,
            len(app.questions)
        )

        passed = (
            score >= required_score
        )

        result_screen = (
            self.manager.get_screen(
                "result"
            )
        )

        if passed:
            status = "Тест пройден"
        else:
            status = "Тест не пройден"

        result_screen.text = (
            f"{app.user}\n\n"
            f"Результат: "
            f"{score} из "
            f"{len(app.questions)}"
            f"\n\n"
            f"{status}"
        )

        self.manager.current = (
            "result"
        )


# =========================================================
# ЭКРАН РЕЗУЛЬТАТА
# =========================================================

class Result(Screen):

    text = StringProperty("")


# =========================================================
# АДМИНИСТРАТИВНЫЕ НАСТРОЙКИ
#
# ВАЖНО:
# НЕ НАЗЫВАЕМ КЛАСС Settings.
#
# У Kivy уже существует собственный класс Settings.
# Именно конфликт этого имени приводил к:
#
# ScreenManagerException:
# ScreenManager accepts only Screen widget
# =========================================================

class AdminSettings(Screen):

    def go_back(self):

        self.manager.current = (
            "login"
        )


# =========================================================
# ПРИЛОЖЕНИЕ
# =========================================================

class TechProfiApp(App):

    title = APP_NAME

    def __init__(
        self,
        **kwargs
    ):

        super().__init__(**kwargs)

        self.bank_name = ""

        self.pool = []
        self.questions = []
        self.saved = []

        self.user = ""
        self.mode = ""

        self.seconds = 0

    # -----------------------------------------------------
    # BUILD
    # -----------------------------------------------------

    def build(self):

        self.bank_name, self.pool = (
            load_bank()
        )

        # При появлении Android-клавиатуры
        # рабочая область должна сдвигаться,
        # чтобы поле ввода не скрывалось.
        try:

            Window.softinput_mode = (
                "below_target"
            )

        except Exception:
            pass

        root_widget = (
            Builder.load_file(
                str(KV_PATH)
            )
        )

        return root_widget

    # -----------------------------------------------------
    # ПОСЛЕ ЗАПУСКА
    # -----------------------------------------------------

    def on_start(self):

        if not self.root:
            return

        try:

            login = (
                self.root.get_screen(
                    "login"
                )
            )

            login.bank = (
                self.bank_name
            )

        except Exception:
            pass

    # -----------------------------------------------------
    # ПОДГОТОВКА ВОПРОСОВ
    # -----------------------------------------------------

    def prepare_questions(self):

        self.questions = list(
            self.pool
        )

        random.shuffle(
            self.questions
        )

        # В контрольном режиме
        # ограничиваем число вопросов.
        if self.mode == "контроль":

            question_count = min(
                DEFAULT_NUM,
                len(self.questions)
            )

            self.questions = (
                self.questions[
                    :question_count
                ]
            )


# =========================================================
# ЗАПУСК
# =========================================================

if __name__ == "__main__":

    TechProfiApp().run()
