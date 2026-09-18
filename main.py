import json
import random
import re
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    NumericProperty,
    StringProperty,
)
from kivy.resources import resource_add_path
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

# =========================================================
# ПУТИ И НАСТРОЙКИ
# =========================================================

BASE = Path(__file__).resolve().parent

resource_add_path(str(BASE))

FONT_PATH = BASE / "fonts" / "Arial.ttf"
FONT_BOLD_PATH = BASE / "fonts" / "Arial-Bold.ttf"

DATA_PATH = BASE / "data" / "questions.json"
KV_PATH = BASE / "testov.kv"

APP_NAME = "ТехПрофи"

DEFAULT_NUM = 25
DEFAULT_MINUTES = 15
DEFAULT_PASS = 20

ADMIN_CODE = "TEST_OVIK"


# =========================================================
# ШРИФТЫ
# =========================================================

LabelBase.register(
    name="AppArial",
    fn_regular=str(FONT_PATH),
    fn_bold=str(FONT_BOLD_PATH),
)


# =========================================================
# ЗАГРУЗКА ВОПРОСОВ
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
            "Поле 'questions' должно быть списком"
        )

    return bank_name, questions


# =========================================================
# ОБРАБОТКА ОТВЕТОВ
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
# ОПРЕДЕЛЕНИЕ КЛАВИАТУРЫ
# =========================================================

def is_numeric_answer(question):

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

    pattern = re.compile(
        r"^[+-]?\d+(?:[.,]\d+)?$"
    )

    for answer in correct:

        if not pattern.fullmatch(
            str(answer).strip()
        ):
            return False

    return True


# =========================================================
# СТРОКА ОТВЕТА С НЕСКОЛЬКИМИ ВАРИАНТАМИ
# =========================================================

class MultiAnswerRow(BoxLayout):

    selected = BooleanProperty(False)

    def __init__(
        self,
        **kwargs
    ):

        super().__init__(**kwargs)

        with self.canvas.before:

            self.bg_color = Color(
                .97,
                .96,
                .94,
                1
            )

            self.bg_rect = Rectangle(
                pos=self.pos,
                size=self.size
            )

        with self.canvas.after:

            self.line_color = Color(
                0,
                0,
                0,
                1
            )

            self.border = Line(
                rectangle=(
                    self.x,
                    self.y,
                    self.width,
                    self.height
                ),
                width=1.2
            )

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            selected=self._update_selected
        )

    def _update_canvas(
        self,
        *args
    ):

        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

        self.border.rectangle = (
            self.x,
            self.y,
            self.width,
            self.height
        )

    def _update_selected(
        self,
        *args
    ):

        if self.selected:

            self.bg_color.rgba = (
                .82,
                .74,
                .64,
                1
            )

        else:

            self.bg_color.rgba = (
                .97,
                .96,
                .94,
                1
            )


# =========================================================
# ГЛАВНЫЙ ЭКРАН
# =========================================================

class Login(Screen):

    bank = StringProperty("")
    admin_enabled = BooleanProperty(False)

    def on_pre_enter(
        self,
        *args
    ):

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
                .10,
                .45,
                .15,
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
                .75,
                .10,
                .10,
                1
            )

    def open_settings(
        self
    ):

        self.update_admin_state()

        if not self.admin_enabled:
            return

        self.ids.name.text = ""

        self.manager.current = (
            "settings"
        )

    def start(
        self,
        mode
    ):

        name = (
            self.ids.name.text.strip()
        )

        if not name:

            self.ids.msg.text = (
                "Введите фамилию и инициалы"
            )

            return

        if name == ADMIN_CODE:

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

        test = (
            self.manager.get_screen(
                "test"
            )
        )

        test.begin()

        self.manager.current = (
            "test"
        )


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

        if app.mode == "контроль":

            self.event = (
                Clock.schedule_interval(
                    self.tick,
                    1
                )
            )

        self.render()

    # -----------------------------------------------------

    def tick(
        self,
        dt
    ):

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

    def get_current_answer(
        self
    ):

        app = App.get_running_app()

        if not app.questions:
            return ""

        if not (
            0 <= self.idx
            < len(app.questions)
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

        if question_type == "текстовый":

            if self.input is None:
                return ""

            return (
                self.input.text.strip()
            )

        if question_type == "один":

            for button in (
                self.btns or []
            ):

                if button.state == "down":
                    return button.text

            return ""

        if question_type == "несколько":

            selected = []

            for (
                option,
                checkbox,
                row
            ) in (
                self.btns or []
            ):

                if checkbox.active:

                    selected.append(
                        option
                    )

            return "; ".join(
                selected
            )

        return ""

    # -----------------------------------------------------

    def save_current(
        self
    ):

        app = App.get_running_app()

        answer = (
            self.get_current_answer()
        )

        if (
            0 <= self.idx
            < len(app.saved)
        ):

            app.saved[
                self.idx
            ] = answer

        return answer

    # -----------------------------------------------------

    def has_answer(
        self
    ):

        return bool(
            str(
                self.get_current_answer()
            ).strip()
        )

    # -----------------------------------------------------

    def render(
        self
    ):

        app = App.get_running_app()

        if not app.questions:
            return

        self.idx = max(
            0,
            min(
                self.idx,
                len(app.questions) - 1
            )
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

            self.timer = "--:--"

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

        if self.idx < len(
            app.saved
        ):

            saved_answer = (
                app.saved[self.idx]
            )

        # =================================================
        # ТЕКСТОВЫЙ ОТВЕТ
        # =================================================

        if question_type == "текстовый":

            keyboard_type = (
                "number"
                if is_numeric_answer(
                    question
                )
                else "text"
            )

            self.input = TextInput(
                text=saved_answer,
                multiline=False,
                font_name="AppArial",
                font_size="18sp",
                size_hint_y=None,
                height=dp(58),
                input_type=keyboard_type,
                write_tab=False,
                padding=(
                    dp(14),
                    dp(15)
                )
            )

            answers_box.add_widget(
                self.input
            )

        # =================================================
        # ОДИН ВАРИАНТ
        # =================================================

        elif question_type == "один":

            for option in question.get(
                "options",
                []
            ):

                option_text = str(
                    option
                )

                button = ToggleButton(
                    text=option_text,
                    group="answer_group",
                    font_name="AppArial",
                    font_size="16sp",

                    size_hint_y=None,
                    height=dp(68),

                    halign="center",
                    valign="middle",

                    padding=(
                        dp(14),
                        dp(12)
                    ),

                    background_normal="",
                    background_down="",

                    background_color=(
                        .92,
                        .90,
                        .87,
                        1
                    )
                )

                button.text_size = (
                    max(
                        Window.width
                        - dp(70),
                        dp(200)
                    ),
                    None
                )

                button.bind(
                    texture_size=
                    self._resize_answer_button
                )

                button.bind(
                    state=
                    self._single_state_changed
                )

                if (
                    str(
                        saved_answer
                    ).strip()
                    ==
                    option_text
                ):

                    button.state = "down"

                self._single_state_changed(
                    button,
                    button.state
                )

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

            for option in question.get(
                "options",
                []
            ):

                option_text = str(
                    option
                )

                row = MultiAnswerRow(
                    orientation="horizontal",
                    size_hint_y=None,
                    height=dp(68),
                    spacing=dp(10),

                    padding=(
                        dp(10),
                        dp(7)
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
                        .08,
                        .07,
                        .06,
                        1
                    ),

                    halign="left",
                    valign="middle",

                    size_hint_y=None,
                    height=dp(54)
                )

                label.bind(
                    width=
                    self._resize_multi_label
                )

                label.bind(
                    texture_size=
                    self._resize_multi_row
                )

                checkbox.bind(
                    active=lambda cb, value, r=row:
                    setattr(
                        r,
                        "selected",
                        value
                    )
                )

                row.selected = (
                    checkbox.active
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
                        checkbox,
                        row
                    )
                )

        else:

            self.question = (
                "Ошибка: неизвестный тип вопроса"
            )

    # =====================================================
    # ЦВЕТ ВЫБРАННОГО ОТВЕТА
    # =====================================================

    def _single_state_changed(
        self,
        button,
        state
    ):

        if state == "down":

            button.background_color = (
                .78,
                .68,
                .57,
                1
            )

        else:

            button.background_color = (
                .92,
                .90,
                .87,
                1
            )

    # =====================================================

    def _resize_answer_button(
        self,
        button,
        texture_size
    ):

        button.height = max(
            dp(68),
            texture_size[1]
            + dp(30)
        )

    # =====================================================

    def _resize_multi_label(
        self,
        label,
        width
    ):

        label.text_size = (
            width,
            None
        )

    # =====================================================

    def _resize_multi_row(
        self,
        label,
        texture_size
    ):

        label.height = max(
            dp(54),
            texture_size[1]
            + dp(18)
        )

        if label.parent:

            label.parent.height = (
                label.height
                + dp(14)
            )

    # =====================================================
    # СЛЕДУЮЩИЙ ВОПРОС
    # =====================================================

    def next(
        self
    ):

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

        if (
            self.idx
            >= len(app.questions) - 1
        ):

            self.finish()
            return

        self.idx += 1

        self.render()

    # =====================================================
    # ПРЕДЫДУЩИЙ ВОПРОС
    # =====================================================

    def prev(
        self
    ):

        app = App.get_running_app()

        if not app.questions:
            return

        self.save_current()

        self.message = ""

        if self.idx > 0:

            self.idx -= 1

            self.render()

    # =====================================================
    # ПОКАЗАТЬ ПРАВИЛЬНЫЙ ОТВЕТ
    # =====================================================

    def show_correct(
        self
    ):

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

        correct = (
            question.get(
                "correct",
                []
            )
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

        source = (
            question.get(
                "source",
                ""
            )
        )

        self.source = (
            "Правильный ответ: "
            + correct_text
            + "\n\nИсточник: "
            + str(source)
        )

    # =====================================================
    # ЗАВЕРШИТЬ ТЕСТ
    # =====================================================

    def finish(
        self
    ):

        app = App.get_running_app()

        try:

            self.save_current()

        except Exception:
            pass

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

        result = (
            self.manager.get_screen(
                "result"
            )
        )

        status = (
            "Тест пройден"
            if passed
            else "Тест не пройден"
        )

        result.text = (
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
# РЕЗУЛЬТАТ
# =========================================================

class Result(Screen):

    text = StringProperty("")


# =========================================================
# НАСТРОЙКИ АДМИНИСТРАТОРА
# =========================================================

class AdminSettings(Screen):

    def go_back(
        self
    ):

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

    def build(
        self
    ):

        self.bank_name, self.pool = (
            load_bank()
        )

        try:

            Window.softinput_mode = (
                "below_target"
            )

        except Exception:
            pass

        return Builder.load_file(
            str(KV_PATH)
        )

    def on_start(
        self
    ):

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

    def prepare_questions(
        self
    ):

        self.questions = list(
            self.pool
        )

        random.shuffle(
            self.questions
        )

        if self.mode == "контроль":

            count = min(
                DEFAULT_NUM,
                len(self.questions)
            )

            self.questions = (
                self.questions[:count]
            )


# =========================================================
# ЗАПУСК
# =========================================================

if __name__ == "__main__":

    TechProfiApp().run()
