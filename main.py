import json
import math
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
# ПУТИ
# =========================================================

BASE = Path(__file__).resolve().parent
resource_add_path(str(BASE))

DATA_DIR = BASE / "data"
DATA_PATH = DATA_DIR / "questions.json"
KV_PATH = BASE / "testov.kv"

FONT_PATH = BASE / "fonts" / "Arial.ttf"
FONT_BOLD_PATH = BASE / "fonts" / "Arial-Bold.ttf"

APP_NAME = "ТехПрофи"
ADMIN_CODE = "TEST_OVIK"


# =========================================================
# НАСТРОЙКИ ПО УМОЛЧАНИЮ
# =========================================================

DEFAULT_NUM = 25
DEFAULT_MINUTES = 15
DEFAULT_PASS_PERCENT = 80


# =========================================================
# ШРИФТЫ
# =========================================================

LabelBase.register(
    name="AppArial",
    fn_regular=str(FONT_PATH),
    fn_bold=str(FONT_BOLD_PATH),
)


# =========================================================
# РАБОТА С НАЗВАНИЯМИ ИСТОЧНИКОВ
# =========================================================

def clean_source_name(name):
    """
    Удаляет расширение .dat и лишние пробелы.
    """

    name = str(name or "").strip()

    if name.lower().endswith(".dat"):
        name = name[:-4]

    return name.strip()


def extract_source_code(text):
    """
    Пытается получить короткое обозначение документа
    из полного названия или строки source.

    Примеры:
    СП 7.13130.2013 ...
        -> СП 7.13130.2013

    СП 60.13330.2020 ...
        -> СП 60.13330.2020

    Федеральный закон 384
        -> Федеральный закон 384
    """

    text = clean_source_name(text)

    if not text:
        return ""

    # СП
    match = re.search(
        r"\bСП\s+\d+(?:\.\d+)+",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        return match.group(0).strip()

    # Федеральный закон
    match = re.search(
        r"Федеральный\s+закон\s+№?\s*\d+",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        return match.group(0).strip()

    # Постановление Правительства
    if text.casefold().startswith(
        "постановление правительства"
    ):
        return text

    return text


# =========================================================
# ПОИСК .DAT
# =========================================================

def discover_dat_sources():
    """
    Находит все .dat в data/.

    Возвращает список словарей:

    {
        "id": "СП 7.13130.2013",
        "name": "СП 7.13130.2013 Отопление, ...",
        "filename": "...dat"
    }

    Название пользователю показывается без .dat.
    """

    result = []

    if not DATA_DIR.exists():
        return result

    try:
        files = sorted(
            DATA_DIR.glob("*.dat"),
            key=lambda path: path.name.casefold(),
        )
    except Exception:
        return result

    for path in files:

        display_name = clean_source_name(
            path.name
        )

        if not display_name:
            continue

        source_id = extract_source_code(
            display_name
        )

        result.append(
            {
                "id": source_id,
                "name": display_name,
                "filename": path.name,
            }
        )

    return result


# =========================================================
# ЗАГРУЗКА QUESTIONS.JSON
# =========================================================

def load_bank():

    with DATA_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:

        obj = json.load(file)

    bank_name = str(
        obj.get(
            "bank_name",
            "",
        )
    ).strip()

    questions = obj.get(
        "questions",
        [],
    )

    if not isinstance(
        questions,
        list,
    ):
        raise ValueError(
            "Поле 'questions' должно быть списком"
        )

    normalized_questions = []

    for question in questions:

        if not isinstance(
            question,
            dict,
        ):
            continue

        item = dict(question)

        if not item.get("bank_name"):
            item["bank_name"] = bank_name

        normalized_questions.append(
            item
        )

    return (
        bank_name,
        normalized_questions,
    )


# =========================================================
# ОПРЕДЕЛЕНИЕ ИСТОЧНИКА ВОПРОСА
# =========================================================

def get_question_source_id(
    question,
    default_bank="",
):
    """
    Определяет, к какому нормативному документу
    относится вопрос.

    Приоритет:
    1. source_id
    2. bank_name
    3. поле source
    4. общий bank_name questions.json
    """

    source_id = str(
        question.get(
            "source_id",
            "",
        )
    ).strip()

    if source_id:
        return extract_source_code(
            source_id
        )

    question_bank = str(
        question.get(
            "bank_name",
            "",
        )
    ).strip()

    if question_bank:
        return extract_source_code(
            question_bank
        )

    source = question.get(
        "source",
        "",
    )

    if isinstance(
        source,
        dict,
    ):

        document = str(
            source.get(
                "document",
                "",
            )
        ).strip()

        if document:
            return extract_source_code(
                document
            )

    else:

        source_text = str(
            source or ""
        ).strip()

        if source_text:
            return extract_source_code(
                source_text
            )

    return extract_source_code(
        default_bank
    )


# =========================================================
# ОТВЕТЫ
# =========================================================

def canon_list(value):

    if isinstance(
        value,
        list,
    ):
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


def is_correct(
    question,
    answer,
):

    question_type = question.get(
        "type",
        "",
    )

    if question_type == "несколько":

        return (
            canon_list(answer)
            ==
            canon_list(
                question.get(
                    "correct",
                    [],
                )
            )
        )

    acceptable = canon_list(
        question.get(
            "correct",
            [],
        )
    )

    user_answer = str(
        answer or ""
    ).strip().casefold()

    return user_answer in acceptable


# =========================================================
# ТИП КЛАВИАТУРЫ
# =========================================================

def is_numeric_answer(
    question,
):

    correct = question.get(
        "correct",
        [],
    )

    if not isinstance(
        correct,
        list,
    ):
        correct = [correct]

    if not correct:
        return False

    pattern = re.compile(
        r"^[+-]?\d+(?:[.,]\d+)?$"
    )

    return all(
        pattern.fullmatch(
            str(answer).strip()
        )
        for answer in correct
    )


# =========================================================
# MULTIPLE CHOICE
# =========================================================

class MultiAnswerRow(BoxLayout):

    selected = BooleanProperty(
        False
    )

    def __init__(
        self,
        **kwargs,
    ):

        super().__init__(
            **kwargs
        )

        with self.canvas.before:

            self.bg_color = Color(
                .97,
                .96,
                .94,
                1,
            )

            self.bg_rect = Rectangle(
                pos=self.pos,
                size=self.size,
            )

        with self.canvas.after:

            Color(
                0,
                0,
                0,
                1,
            )

            self.border = Line(
                rectangle=(
                    self.x,
                    self.y,
                    self.width,
                    self.height,
                ),
                width=1.15,
            )

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            selected=self._update_selected,
        )

    def _update_canvas(
        self,
        *args,
    ):

        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

        self.border.rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
        )

    def _update_selected(
        self,
        *args,
    ):

        if self.selected:

            self.bg_color.rgba = (
                .82,
                .74,
                .64,
                1,
            )

        else:

            self.bg_color.rgba = (
                .97,
                .96,
                .94,
                1,
            )


# =========================================================
# LOGIN
# =========================================================

class Login(Screen):

    bank = StringProperty("")
    admin_enabled = BooleanProperty(
        False
    )

    def on_pre_enter(
        self,
        *args,
    ):

        app = App.get_running_app()

        self.bank = getattr(
            app,
            "bank_name",
            "",
        )

        self.update_admin_state()

    def update_admin_state(
        self,
        *args,
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
                1,
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
                1,
            )

    def open_settings(
        self,
    ):

        self.update_admin_state()

        if not self.admin_enabled:
            return

        self.ids.name.text = ""

        settings_screen = (
            self.manager.get_screen(
                "settings"
            )
        )

        settings_screen.load_values()

        self.manager.current = (
            "settings"
        )

    def start(
        self,
        mode,
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
                "Нет вопросов для выбранных источников"
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
# TEST
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
    # START
    # -----------------------------------------------------

    def begin(
        self,
    ):

        app = App.get_running_app()

        self.idx = 0

        app.saved = [
            ""
            for _ in app.questions
        ]

        app.seconds = (
            app.test_minutes * 60
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
                    1,
                )
            )

        self.render()

    # -----------------------------------------------------
    # TIMER
    # -----------------------------------------------------

    def tick(
        self,
        dt,
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
    # CURRENT ANSWER
    # -----------------------------------------------------

    def get_current_answer(
        self,
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
            app.questions[
                self.idx
            ]
        )

        question_type = (
            question.get(
                "type",
                "",
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
                row,
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
    # SAVE
    # -----------------------------------------------------

    def save_current(
        self,
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

    def has_answer(
        self,
    ):

        return bool(
            str(
                self.get_current_answer()
            ).strip()
        )

    # -----------------------------------------------------
    # SOURCE
    # -----------------------------------------------------

    def show_source_after_answer(
        self,
        *args,
    ):

        app = App.get_running_app()

        if app.mode != "обучение":
            return

        if not self.has_answer():

            self.source = ""
            return

        self.save_current()
        self.show_source()

    def show_source(
        self,
    ):

        app = App.get_running_app()

        if not app.questions:
            return

        question = (
            app.questions[
                self.idx
            ]
        )

        source = question.get(
            "source",
            "",
        )

        if isinstance(
            source,
            dict,
        ):

            document = str(
                source.get(
                    "document",
                    "",
                )
            ).strip()

            section = str(
                source.get(
                    "section",
                    "",
                )
            ).strip()

            text = str(
                source.get(
                    "text",
                    "",
                )
            ).strip()

            parts = [
                part
                for part in (
                    document,
                    section,
                    text,
                )
                if part
            ]

            self.source = (
                "\n\n".join(
                    parts
                )
            )

        else:

            self.source = str(
                source or ""
            ).strip()

    # -----------------------------------------------------
    # RENDER
    # -----------------------------------------------------

    def render(
        self,
    ):

        app = App.get_running_app()

        if not app.questions:
            return

        self.idx = max(
            0,
            min(
                self.idx,
                len(app.questions) - 1,
            ),
        )

        question = (
            app.questions[
                self.idx
            ]
        )

        self.question = (
            question.get(
                "text",
                "",
            )
        )

        self.progress = (
            f"Вопрос {self.idx + 1} "
            f"из {len(app.questions)}"
        )

        self.message = ""
        self.source = ""

        if app.mode == "контроль":

            self.timer = (
                f"{app.seconds // 60:02d}:"
                f"{app.seconds % 60:02d}"
            )

        else:
            self.timer = ""

        answers_box = (
            self.ids.answers
        )

        answers_box.clear_widgets()

        self.input = None
        self.btns = []

        question_type = (
            question.get(
                "type",
                "",
            )
        )

        saved_answer = ""

        if self.idx < len(
            app.saved
        ):

            saved_answer = (
                app.saved[
                    self.idx
                ]
            )

        # =================================================
        # TEXT
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
                    dp(15),
                ),
            )

            self.input.bind(
                on_text_validate=
                self.show_source_after_answer
            )

            self.input.bind(
                focus=
                self._text_focus_changed
            )

            answers_box.add_widget(
                self.input
            )

        # =================================================
        # SINGLE
        # =================================================

        elif question_type == "один":

            for option in question.get(
                "options",
                [],
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
                    height=dp(56),
                    halign="center",
                    valign="middle",
                    padding=(
                        dp(12),
                        dp(10),
                    ),
                    color=(
                        .08,
                        .07,
                        .06,
                        1,
                    ),
                    background_normal="",
                    background_down="",
                    background_color=(
                        .92,
                        .90,
                        .87,
                        1,
                    ),
                )

                button.text_size = (
                    max(
                        Window.width
                        - dp(70),
                        dp(200),
                    ),
                    None,
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
                    button.state,
                )

                answers_box.add_widget(
                    button
                )

                self.btns.append(
                    button
                )

            if (
                saved_answer
                and
                app.mode == "обучение"
            ):
                self.show_source()

        # =================================================
        # MULTIPLE
        # =================================================

        elif question_type == "несколько":

            saved = canon_list(
                saved_answer
            )

            for option in question.get(
                "options",
                [],
            ):

                option_text = str(
                    option
                )

                row = MultiAnswerRow(
                    orientation="horizontal",
                    size_hint_y=None,
                    height=dp(56),
                    spacing=dp(4),
                    padding=(
                        dp(6),
                        dp(5),
                    ),
                )

                checkbox = CheckBox(
                    active=(
                        option_text.casefold()
                        in saved
                    ),
                    size_hint_x=None,
                    width=dp(42),
                    color=(
                        .20,
                        .16,
                        .12,
                        1,
                    ),
                )

                label = Label(
                    text=option_text,
                    font_name="AppArial",
                    font_size="16sp",
                    color=(
                        .08,
                        .07,
                        .06,
                        1,
                    ),
                    halign="left",
                    valign="middle",
                    size_hint_y=None,
                    height=dp(46),
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
                    self._multiple_state_changed(
                        r,
                        value,
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
                        row,
                    )
                )

            if (
                saved_answer
                and
                app.mode == "обучение"
            ):
                self.show_source()

        else:

            self.question = (
                "Ошибка: неизвестный тип вопроса"
            )

    # -----------------------------------------------------
    # TEXT SOURCE
    # -----------------------------------------------------

    def _text_focus_changed(
        self,
        widget,
        focused,
    ):

        if not focused:
            self.show_source_after_answer()

    # -----------------------------------------------------
    # SINGLE STATE
    # -----------------------------------------------------

    def _single_state_changed(
        self,
        button,
        state,
    ):

        if state == "down":

            button.background_color = (
                .78,
                .68,
                .57,
                1,
            )

            self.show_source_after_answer()

        else:

            button.background_color = (
                .92,
                .90,
                .87,
                1,
            )

    # -----------------------------------------------------
    # MULTIPLE STATE
    # -----------------------------------------------------

    def _multiple_state_changed(
        self,
        row,
        value,
    ):

        row.selected = value

        Clock.schedule_once(
            lambda dt:
            self.show_source_after_answer(),
            0,
        )

    # -----------------------------------------------------
    # ADAPTIVE HEIGHT
    # -----------------------------------------------------

    def _resize_answer_button(
        self,
        button,
        texture_size,
    ):

        button.height = max(
            dp(56),
            texture_size[1]
            + dp(24),
        )

    def _resize_multi_label(
        self,
        label,
        width,
    ):

        label.text_size = (
            width,
            None,
        )

    def _resize_multi_row(
        self,
        label,
        texture_size,
    ):

        label.height = max(
            dp(46),
            texture_size[1]
            + dp(14),
        )

        if label.parent:

            label.parent.height = (
                label.height
                + dp(10)
            )

    # -----------------------------------------------------
    # NEXT
    # -----------------------------------------------------

    def next(
        self,
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
            >=
            len(app.questions) - 1
        ):

            self.finish()
            return

        self.idx += 1
        self.render()

    # -----------------------------------------------------
    # PREVIOUS
    # -----------------------------------------------------

    def prev(
        self,
    ):

        app = App.get_running_app()

        if not app.questions:
            return

        self.save_current()
        self.message = ""

        if self.idx > 0:

            self.idx -= 1
            self.render()

    # -----------------------------------------------------
    # CORRECT ANSWER
    # -----------------------------------------------------

    def show_correct(
        self,
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
            app.questions[
                self.idx
            ]
        )

        correct = question.get(
            "correct",
            [],
        )

        if isinstance(
            correct,
            list,
        ):

            correct_text = (
                "; ".join(
                    str(item)
                    for item in correct
                )
            )

        else:

            correct_text = str(
                correct
            )

        self.message = (
            "Правильный ответ: "
            + correct_text
        )

        if app.mode == "обучение":
            self.show_source()

    # -----------------------------------------------------
    # FINISH
    # -----------------------------------------------------

    def finish(
        self,
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
            answer,
        ) in zip(
            app.questions,
            app.saved,
        ):

            if is_correct(
                question,
                answer,
            ):
                score += 1

        required_score = math.ceil(
            len(app.questions)
            *
            app.pass_percent
            /
            100
        )

        passed = (
            score
            >=
            required_score
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
            f"{len(app.questions)}\n\n"
            f"Для успешного прохождения: "
            f"{app.pass_percent}% "
            f"({required_score} правильных)\n\n"
            f"{status}"
        )

        self.manager.current = (
            "result"
        )


# =========================================================
# RESULT
# =========================================================

class Result(Screen):

    text = StringProperty("")


# =========================================================
# SETTINGS
# =========================================================

class AdminSettings(Screen):

    message = StringProperty("")

    def on_pre_enter(
        self,
        *args,
    ):

        self.load_values()

    # -----------------------------------------------------
    # LOAD
    # -----------------------------------------------------

    def load_values(
        self,
    ):

        self.message = ""

    # -----------------------------------------------------
    # СПИСОК ИСТОЧНИКОВ
    # -----------------------------------------------------

    def get_sources(
        self,
    ):

        app = App.get_running_app()

        result = []

        for source in (
            app.source_catalog
        ):

            source_id = source["id"]

            result.append(
                {
                    "id": source_id,
                    "name": source["name"],
                    "filename":
                        source["filename"],
                    "selected":
                        source_id
                        in app.selected_sources,
                }
            )

        return result

    # -----------------------------------------------------
    # ВКЛЮЧИТЬ / ВЫКЛЮЧИТЬ
    # -----------------------------------------------------

    def set_source_selected(
        self,
        source_id,
        selected,
    ):

        app = App.get_running_app()

        source_id = str(
            source_id
        ).strip()

        if selected:

            app.selected_sources.add(
                source_id
            )

        else:

            app.selected_sources.discard(
                source_id
            )

    # -----------------------------------------------------
    # ВСЕ ИСТОЧНИКИ
    # -----------------------------------------------------

    def select_all_sources(
        self,
    ):

        app = App.get_running_app()

        app.selected_sources = {
            item["id"]
            for item
            in app.source_catalog
        }

    def clear_all_sources(
        self,
    ):

        app = App.get_running_app()

        app.selected_sources = set()

    def all_sources_selected(
        self,
    ):

        app = App.get_running_app()

        if not app.available_sources:
            return False

        return set(
            app.available_sources
        ).issubset(
            app.selected_sources
        )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    def save_settings(
        self,
        question_count=None,
        test_minutes=None,
        pass_percent=None,
    ):

        app = App.get_running_app()

        if not app.selected_sources:

            self.message = (
                "Выберите хотя бы один "
                "источник вопросов"
            )

            return False

        try:

            if question_count is not None:

                question_count = int(
                    question_count
                )

                if question_count <= 0:
                    raise ValueError

                app.question_count = (
                    question_count
                )

            if test_minutes is not None:

                test_minutes = int(
                    test_minutes
                )

                if test_minutes <= 0:
                    raise ValueError

                app.test_minutes = (
                    test_minutes
                )

            if pass_percent is not None:

                pass_percent = int(
                    pass_percent
                )

                if not (
                    1
                    <=
                    pass_percent
                    <=
                    100
                ):
                    raise ValueError

                app.pass_percent = (
                    pass_percent
                )

        except (
            TypeError,
            ValueError,
        ):

            self.message = (
                "Проверьте значения настроек"
            )

            return False

        if app.save_settings():

            self.message = (
                "Настройки сохранены"
            )

            return True

        self.message = (
            "Не удалось сохранить настройки"
        )

        return False

    # -----------------------------------------------------
    # BACK
    # -----------------------------------------------------

    def go_back(
        self,
    ):

        self.manager.current = (
            "login"
        )


# =========================================================
# APP
# =========================================================

class TechProfiApp(App):

    title = APP_NAME

    question_count = NumericProperty(
        DEFAULT_NUM
    )

    test_minutes = NumericProperty(
        DEFAULT_MINUTES
    )

    pass_percent = NumericProperty(
        DEFAULT_PASS_PERCENT
    )

    def __init__(
        self,
        **kwargs,
    ):

        super().__init__(
            **kwargs
        )

        self.bank_name = ""

        self.pool = []
        self.questions = []
        self.saved = []

        self.user = ""
        self.mode = ""

        self.seconds = 0

        # Полный каталог .dat
        self.source_catalog = []

        # Только ID документов
        self.available_sources = []

        # Выбранные ID
        self.selected_sources = set()

        self.settings_path = None

    # -----------------------------------------------------
    # BUILD
    # -----------------------------------------------------

    def build(
        self,
    ):

        self.bank_name, self.pool = (
            load_bank()
        )

        # Находим все .dat в data/
        self.collect_sources()

        try:

            Window.softinput_mode = (
                "below_target"
            )

        except Exception:
            pass

        return Builder.load_file(
            str(KV_PATH)
        )

    # -----------------------------------------------------
    # START
    # -----------------------------------------------------

    def on_start(
        self,
    ):

        self.settings_path = (
            Path(self.user_data_dir)
            /
            "settings.json"
        )

        self.load_settings()

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
    # ИСТОЧНИКИ
    # -----------------------------------------------------

    def collect_sources(
        self,
    ):
        """
        Основной источник списка документов —
        файлы data/*.dat.

        Например:

        data/
        ├── СП 7.13130.2013 ... .dat
        ├── СП 60.13330.2020 ... .dat
        └── Федеральный закон 384.dat
        """

        self.source_catalog = (
            discover_dat_sources()
        )

        # Если по какой-либо причине .dat
        # не найдены, не ломаем приложение.
        # Используем bank_name из questions.json.
        if (
            not self.source_catalog
            and
            self.bank_name
        ):

            bank = clean_source_name(
                self.bank_name
            )

            self.source_catalog = [
                {
                    "id":
                        extract_source_code(
                            bank
                        ),
                    "name":
                        bank,
                    "filename":
                        "",
                }
            ]

        self.available_sources = [
            item["id"]
            for item
            in self.source_catalog
        ]

        # Убираем возможные дубли ID.
        unique_sources = []

        for source_id in (
            self.available_sources
        ):

            if (
                source_id
                and
                source_id
                not in unique_sources
            ):
                unique_sources.append(
                    source_id
                )

        self.available_sources = (
            unique_sources
        )

        # По умолчанию выбраны ВСЕ.
        self.selected_sources = set(
            self.available_sources
        )

    # -----------------------------------------------------
    # LOAD SETTINGS
    # -----------------------------------------------------

    def load_settings(
        self,
    ):

        self.question_count = (
            DEFAULT_NUM
        )

        self.test_minutes = (
            DEFAULT_MINUTES
        )

        self.pass_percent = (
            DEFAULT_PASS_PERCENT
        )

        # При первой установке —
        # ВСЕ источники включены.
        self.selected_sources = set(
            self.available_sources
        )

        if not self.settings_path:
            return

        if not self.settings_path.exists():
            return

        try:

            with self.settings_path.open(
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(
                    file
                )

            self.question_count = max(
                1,
                int(
                    data.get(
                        "question_count",
                        DEFAULT_NUM,
                    )
                ),
            )

            self.test_minutes = max(
                1,
                int(
                    data.get(
                        "test_minutes",
                        DEFAULT_MINUTES,
                    )
                ),
            )

            self.pass_percent = max(
                1,
                min(
                    100,
                    int(
                        data.get(
                            "pass_percent",
                            DEFAULT_PASS_PERCENT,
                        )
                    ),
                ),
            )

            current_sources = set(
                self.available_sources
            )

            saved_sources = set(
                data.get(
                    "selected_sources",
                    [],
                )
            )

            known_sources = set(
                data.get(
                    "known_sources",
                    [],
                )
            )

            # То, что пользователь выбирал раньше.
            selected = (
                saved_sources
                &
                current_sources
            )

            # Новые .dat автоматически включаются.
            new_sources = (
                current_sources
                -
                known_sources
            )

            selected.update(
                new_sources
            )

            # Совместимость со старым файлом настроек.
            if (
                not known_sources
                and
                not saved_sources
            ):
                selected = set(
                    current_sources
                )

            self.selected_sources = (
                selected
            )

        except Exception:

            # Повреждённый settings.json
            # не должен ломать приложение.
            self.question_count = (
                DEFAULT_NUM
            )

            self.test_minutes = (
                DEFAULT_MINUTES
            )

            self.pass_percent = (
                DEFAULT_PASS_PERCENT
            )

            self.selected_sources = set(
                self.available_sources
            )

    # -----------------------------------------------------
    # SAVE SETTINGS
    # -----------------------------------------------------

    def save_settings(
        self,
    ):

        if not self.settings_path:

            self.settings_path = (
                Path(self.user_data_dir)
                /
                "settings.json"
            )

        data = {

            "question_count":
                int(
                    self.question_count
                ),

            "test_minutes":
                int(
                    self.test_minutes
                ),

            "pass_percent":
                int(
                    self.pass_percent
                ),

            "selected_sources":
                sorted(
                    self.selected_sources
                ),

            "known_sources":
                sorted(
                    self.available_sources
                ),
        }

        try:

            self.settings_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with self.settings_path.open(
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    data,
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            return True

        except Exception:

            return False

    # -----------------------------------------------------
    # PREPARE QUESTIONS
    # -----------------------------------------------------

    def prepare_questions(
        self,
    ):
        """
        Фильтрует вопросы questions.json
        по выбранным нормативным документам.
        """

        filtered = []

        for question in self.pool:

            source_id = (
                get_question_source_id(
                    question,
                    self.bank_name,
                )
            )

            if (
                source_id
                in
                self.selected_sources
            ):
                filtered.append(
                    question
                )

        random.shuffle(
            filtered
        )

        if self.mode == "контроль":

            count = min(
                int(
                    self.question_count
                ),
                len(filtered),
            )

            self.questions = (
                filtered[:count]
            )

        else:

            # В обучении таймера нет,
            # но фильтр выбранных источников работает.
            self.questions = (
                filtered
            )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    TechProfiApp().run()
