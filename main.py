import json
import random
from pathlib import Path

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.resources import resource_add_path


# ---------------------------------------------------------
# Пути и основные настройки приложения
# ---------------------------------------------------------

BASE = Path(__file__).resolve().parent

resource_add_path(str(BASE))

FONT_PATH = BASE / "fonts" / "Arial.ttf"
DATA_PATH = BASE / "data" / "questions.json"
KV_PATH = BASE / "testov.kv"

APP_NAME = "Тест_ОВ"

DEFAULT_NUM = 25
DEFAULT_MINUTES = 15
DEFAULT_PASS = 20


# ---------------------------------------------------------
# Шрифт
# ---------------------------------------------------------

LabelBase.register(
    name="AppArial",
    fn_regular=str(FONT_PATH)
)


# ---------------------------------------------------------
# Загрузка банка вопросов
# ---------------------------------------------------------

def load_bank():
    with DATA_PATH.open("r", encoding="utf-8") as file:
        obj = json.load(file)

    bank_name = obj.get("bank_name", "")
    questions = obj.get("questions", [])

    if not isinstance(questions, list):
        raise ValueError(
            "Поле 'questions' в questions.json должно быть списком"
        )

    return bank_name, questions


# ---------------------------------------------------------
# Работа с ответами
# ---------------------------------------------------------

def canon_list(value):
    if isinstance(value, list):
        parts = value
    else:
        parts = str(value or "").split(";")

    return {
        str(item).strip().casefold()
        for item in parts
        if str(item).strip()
    }


def is_correct(question, answer):
    question_type = question.get("type", "")

    if question_type == "несколько":
        return canon_list(answer) == canon_list(
            question.get("correct", [])
        )

    acceptable = canon_list(
        question.get("correct", [])
    )

    return (
        str(answer or "").strip().casefold()
        in acceptable
    )


# ---------------------------------------------------------
# Экран входа
# ---------------------------------------------------------

class Login(Screen):

    bank = StringProperty("")

    def on_pre_enter(self, *args):
        app = App.get_running_app()

        # Безопасно получаем название банка.
        # Даже если экран откроется раньше полной
        # инициализации приложения, падения не будет.
        self.bank = getattr(
            app,
            "bank_name",
            ""
        )

    def start(self, mode):
        name = self.ids.name.text.strip()

        if not name:
            self.ids.msg.text = (
                "Введите фамилию и инициалы"
            )
            return

        self.ids.msg.text = ""

        app = App.get_running_app()

        app.user = name
        app.mode = mode

        app.prepare_questions()

        if not app.questions:
            self.ids.msg.text = (
                "Банк вопросов пуст"
            )
            return

        test_screen = self.manager.get_screen(
            "test"
        )

        self.manager.current = "test"

        test_screen.begin()


# ---------------------------------------------------------
# Экран тестирования
# ---------------------------------------------------------

class Test(Screen):

    question = StringProperty("")
    progress = StringProperty("")
    timer = StringProperty("")
    source = StringProperty("")

    idx = NumericProperty(0)

    event = None
    input = None
    btns = None

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

        if self.event:
            self.event.cancel()
            self.event = None

        if app.mode == "контроль":
            self.event = Clock.schedule_interval(
                self.tick,
                1
            )

        self.render()

    def tick(self, dt):
        app = App.get_running_app()

        app.seconds -= 1

        self.timer = (
            f"{app.seconds // 60:02d}:"
            f"{app.seconds % 60:02d}"
        )

        if app.seconds <= 0:
            self.finish()
            return False

        return True

    def save_current(self):
        app = App.get_running_app()

        if not app.questions:
            return ""

        if self.idx >= len(app.questions):
            return ""

        question = app.questions[self.idx]

        question_type = question.get(
            "type",
            ""
        )

        answer = ""

        if question_type == "текстовый":

            if self.input is not None:
                answer = (
                    self.input.text.strip()
                )

        elif question_type == "один":

            if self.btns:
                answer = next(
                    (
                        button.text
                        for button in self.btns
                        if button.state == "down"
                    ),
                    ""
                )

        elif question_type == "несколько":

            if self.btns:
                answer = "; ".join(
                    option
                    for option, checkbox
                    in self.btns
                    if checkbox.active
                )

        if self.idx < len(app.saved):
            app.saved[self.idx] = answer

        return answer

    def render(self):

        from kivy.uix.togglebutton import (
            ToggleButton
        )
        from kivy.uix.checkbox import CheckBox
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.textinput import TextInput

        app = App.get_running_app()

        if not app.questions:
            return

        if self.idx < 0:
            self.idx = 0

        if self.idx >= len(app.questions):
            self.idx = (
                len(app.questions) - 1
            )

        question = app.questions[
            self.idx
        ]

        self.question = question.get(
            "text",
            ""
        )

        self.progress = (
            f"Вопрос {self.idx + 1} "
            f"из {len(app.questions)}"
        )

        self.source = ""

        if app.mode == "обучение":
            self.timer = ""
        else:
            self.timer = (
                f"{app.seconds // 60:02d}:"
                f"{app.seconds % 60:02d}"
            )

        answers_box = self.ids.answers

        answers_box.clear_widgets()

        self.input = None
        self.btns = []

        question_type = question.get(
            "type",
            ""
        )

        saved_answer = ""

        if self.idx < len(app.saved):
            saved_answer = (
                app.saved[self.idx]
            )

        # -------------------------------------------------
        # Текстовый вопрос
        # -------------------------------------------------

        if question_type == "текстовый":

            self.input = TextInput(
                text=saved_answer,
                multiline=False,
                font_name="AppArial",
                font_size="18sp",
                size_hint_y=None,
                height="52dp"
            )

            answers_box.add_widget(
                self.input
            )

        # -------------------------------------------------
        # Один вариант ответа
        # -------------------------------------------------

        elif question_type == "один":

            options = question.get(
                "options",
                []
            )

            for option in options:

                button = ToggleButton(
                    text=str(option),
                    group="ans",
                    font_name="AppArial",
                    font_size="16sp",
                    size_hint_y=None,
                    height="64dp"
                )

                if saved_answer == option:
                    button.state = "down"
                else:
                    button.state = "normal"

                answers_box.add_widget(
                    button
                )

                self.btns.append(
                    button
                )

        # -------------------------------------------------
        # Несколько вариантов ответа
        # -------------------------------------------------

        elif question_type == "несколько":

            saved = canon_list(
                saved_answer
            )

            options = question.get(
                "options",
                []
            )

            for option in options:

                option_text = str(option)

                row = BoxLayout(
                    size_hint_y=None,
                    height="64dp",
                    spacing="6dp"
                )

                checkbox = CheckBox(
                    active=(
                        option_text.casefold()
                        in saved
                    ),
                    size_hint_x=.12
                )

                label = Label(
                    text=option_text,
                    font_name="AppArial",
                    halign="left",
                    valign="middle"
                )

                label.bind(
                    size=lambda widget, size:
                    setattr(
                        widget,
                        "text_size",
                        (size[0], None)
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

        else:
            self.question = (
                "Ошибка: неизвестный "
                "тип вопроса"
            )

    def next(self):

        app = App.get_running_app()

        if not app.questions:
            return

        self.save_current()

        if self.idx >= (
            len(app.questions) - 1
        ):
            self.finish()
            return

        self.idx += 1

        self.render()

    def prev(self):

        if not App.get_running_app().questions:
            return

        self.save_current()

        if self.idx > 0:
            self.idx -= 1
            self.render()

    def show_correct(self):

        app = App.get_running_app()

        if not app.questions:
            return

        self.save_current()

        question = app.questions[
            self.idx
        ]

        correct = question.get(
            "correct",
            []
        )

        if isinstance(correct, list):
            correct_text = "; ".join(
                str(item)
                for item in correct
            )
        else:
            correct_text = str(correct)

        source = question.get(
            "source",
            ""
        )

        self.source = (
            "Правильный ответ: "
            + correct_text
            + "\nИсточник: "
            + str(source)
        )

    def finish(self):

        app = App.get_running_app()

        try:
            self.save_current()
        except Exception:
            pass

        if self.event:
            self.event.cancel()
            self.event = None

        score = sum(
            is_correct(question, answer)
            for question, answer
            in zip(
                app.questions,
                app.saved
            )
        )

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

        result_screen.text = (
            f"{app.user}\n\n"
            f"Результат: "
            f"{score} из "
            f"{len(app.questions)}\n"
            + (
                "Тест пройден"
                if passed
                else "Тест не пройден"
            )
        )

        self.manager.current = "result"


# ---------------------------------------------------------
# Экран результата
# ---------------------------------------------------------

class Result(Screen):

    text = StringProperty("")


# ---------------------------------------------------------
# Основное приложение
# ---------------------------------------------------------

class TestOVApp(App):

    title = APP_NAME

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Все используемые поля создаём заранее.
        # Это исключает ошибку вида:
        # AttributeError: TestOVApp has no attribute ...
        self.bank_name = ""
        self.pool = []
        self.questions = []
        self.saved = []

        self.user = ""
        self.mode = ""

        self.seconds = 0

    def build(self):

        # Сначала загружаем данные.
        self.bank_name, self.pool = (
            load_bank()
        )

        # Только после этого создаём интерфейс.
        root = Builder.load_file(
            str(KV_PATH)
        )

        return root

    def on_start(self):

        # Дополнительно обновляем название
        # банка после полного запуска App.
        if self.root:
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

    def prepare_questions(self):

        self.questions = list(
            self.pool
        )

        random.shuffle(
            self.questions
        )

        if self.mode == "контроль":
            self.questions = (
                self.questions[
                    :min(
                        DEFAULT_NUM,
                        len(self.questions)
                    )
                ]
            )


# ---------------------------------------------------------
# Запуск
# ---------------------------------------------------------

if __name__ == "__main__":
    TestOVApp().run()
