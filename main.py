import json
import math
import random
import re
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.resources import resource_add_path
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton


# =========================================================
# ПУТИ И НАСТРОЙКИ
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
# ИСТОЧНИКИ
# =========================================================

def clean_source_name(name):
    name = str(name or "").strip()
    if name.lower().endswith(".dat"):
        name = name[:-4]
    return name.strip()


def extract_source_code(text):
    text = clean_source_name(text)
    if not text:
        return ""

    match = re.search(r"\bСП\s+\d+(?:\.\d+)+", text, flags=re.IGNORECASE)
    if match:
        return match.group(0).strip()

    match = re.search(r"Федеральный\s+закон\s+№?\s*\d+", text, flags=re.IGNORECASE)
    if match:
        return match.group(0).strip()

    if text.casefold().startswith("постановление правительства"):
        return text

    return text


def discover_dat_sources():
    result = []
    if not DATA_DIR.exists():
        return result

    try:
        files = sorted(DATA_DIR.glob("*.dat"), key=lambda path: path.name.casefold())
    except Exception:
        return result

    for path in files:
        display_name = clean_source_name(path.name)
        if not display_name:
            continue
        source_id = extract_source_code(display_name)
        result.append({
            "id": source_id,
            "name": display_name,
            "filename": path.name,
        })

    return result


# =========================================================
# ЗАГРУЗКА QUESTIONS.JSON
# =========================================================

def load_bank():
    with DATA_PATH.open("r", encoding="utf-8") as file:
        obj = json.load(file)

    bank_name = str(obj.get("bank_name", "")).strip()
    questions = obj.get("questions", [])

    if not isinstance(questions, list):
        raise ValueError("Поле 'questions' должно быть списком")

    normalized = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        item = dict(question)
        if not item.get("bank_name"):
            item["bank_name"] = bank_name
        normalized.append(item)

    return bank_name, normalized


def get_question_source_id(question, default_bank=""):
    source_id = str(question.get("source_id", "")).strip()
    if source_id:
        return extract_source_code(source_id)

    question_bank = str(question.get("bank_name", "")).strip()
    if question_bank:
        return extract_source_code(question_bank)

    source = question.get("source", "")
    if isinstance(source, dict):
        document = str(source.get("document", "")).strip()
        if document:
            return extract_source_code(document)
    else:
        source_text = str(source or "").strip()
        if source_text:
            return extract_source_code(source_text)

    return extract_source_code(default_bank)


# =========================================================
# ОТВЕТЫ
# =========================================================

def canon_list(value):
    parts = value if isinstance(value, list) else str(value or "").split(";")
    return {str(item).strip().casefold() for item in parts if str(item).strip()}


def is_correct(question, answer):
    question_type = question.get("type", "")
    if question_type == "несколько":
        return canon_list(answer) == canon_list(question.get("correct", []))

    acceptable = canon_list(question.get("correct", []))
    user_answer = str(answer or "").strip().casefold()
    return user_answer in acceptable


# =========================================================
# ТИП КЛАВИАТУРЫ
# =========================================================

def is_numeric_answer(question):
    correct = question.get("correct", [])
    if not isinstance(correct, list):
        correct = [correct]
    if not correct:
        return False

    pattern = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")
    return all(pattern.fullmatch(str(answer).strip()) for answer in correct)


# =========================================================
# ВАРИАНТЫ ОТВЕТОВ
# =========================================================

class AnswerRowBase(BoxLayout):
    selected = BooleanProperty(False)
    status = StringProperty("normal")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.checkbox = None

        with self.canvas.before:
            self.bg_color = Color(.99, .985, .97, 1)
            self.bg_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(12)],
            )

        with self.canvas.after:
            self.border_color = Color(.82, .76, .68, 1)
            self.border = Line(
                rounded_rectangle=(
                    self.x,
                    self.y,
                    self.width,
                    self.height,
                    dp(12),
                ),
                width=1.0,
            )

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            selected=self._update_visual,
            status=self._update_visual,
        )

    def attach_checkbox(self, checkbox):
        self.checkbox = checkbox
        self._update_visual()

    def _update_canvas(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            dp(12),
        )

    def _update_visual(self, *args):
        # После нажатия "Ответ" в режиме обучения.
        if self.status == "correct":
            self.bg_color.rgba = (.84, .95, .85, 1)
            self.border_color.rgba = (.08, .55, .20, 1)
            if self.checkbox is not None:
                self.checkbox.color = (.05, .55, .18, 1)
            return

        if self.status == "wrong":
            self.bg_color.rgba = (.98, .84, .84, 1)
            self.border_color.rgba = (.86, .12, .10, 1)
            if self.checkbox is not None:
                self.checkbox.color = (.90, .10, .08, 1)
            return

        # Обычное состояние до проверки ответа.
        if self.selected:
            self.bg_color.rgba = (.91, .85, .77, 1)
            self.border_color.rgba = (.55, .42, .29, 1)
            if self.checkbox is not None:
                self.checkbox.color = (.48, .34, .22, 1)
        else:
            self.bg_color.rgba = (.99, .985, .97, 1)
            self.border_color.rgba = (.82, .76, .68, 1)
            if self.checkbox is not None:
                self.checkbox.color = (.38, .38, .38, 1)


class SingleAnswerRow(AnswerRowBase):
    """Карточка одиночного ответа с круглым radio checkbox."""

    def on_touch_down(self, touch):
        if (
            self.collide_point(*touch.pos)
            and self.checkbox is not None
            and not self.checkbox.disabled
        ):
            self.checkbox.active = True
            return True
        return super().on_touch_down(touch)


class MultiAnswerRow(AnswerRowBase):
    """Карточка множественного ответа с обычным checkbox."""

    def on_touch_down(self, touch):
        if (
            self.collide_point(*touch.pos)
            and self.checkbox is not None
            and not self.checkbox.disabled
        ):
            self.checkbox.active = not self.checkbox.active
            return True
        return super().on_touch_down(touch)


# =========================================================
# LOGIN
# =========================================================

class Login(Screen):
    bank = StringProperty("")
    admin_enabled = BooleanProperty(False)

    def on_pre_enter(self, *args):
        app = App.get_running_app()
        self.bank = getattr(app, "bank_name", "")
        self.update_admin_state()

    def update_admin_state(self, *args):
        if "name" not in self.ids:
            return

        value = self.ids.name.text.strip()
        self.admin_enabled = value == ADMIN_CODE

        if self.admin_enabled:
            self.ids.msg.text = "Административный режим доступен"
            self.ids.msg.color = (.10, .45, .15, 1)
        else:
            if self.ids.msg.text == "Административный режим доступен":
                self.ids.msg.text = ""
            self.ids.msg.color = (.75, .10, .10, 1)

    def open_settings(self):
        self.update_admin_state()
        if not self.admin_enabled:
            return

        self.ids.name.text = ""
        settings_screen = self.manager.get_screen("settings")
        settings_screen.load_values()
        self.manager.current = "settings"

    def start(self, mode):
        name = self.ids.name.text.strip()

        if not name:
            self.ids.msg.text = "Введите фамилию и инициалы"
            return

        if name == ADMIN_CODE:
            self.ids.msg.text = "Для запуска тестирования введите ФИО тестируемого"
            return

        app = App.get_running_app()
        app.user = name
        app.mode = mode
        app.prepare_questions()

        if not app.questions:
            self.ids.msg.text = "Нет вопросов для выбранных источников"
            return

        self.ids.msg.text = ""
        test = self.manager.get_screen("test")
        test.begin()
        self.manager.current = "test"


# =========================================================
# TEST
# =========================================================

class Test(Screen):
    question = StringProperty("")
    progress = StringProperty("")
    progress_ratio = NumericProperty(0.0)
    progress_percent = StringProperty("0%")
    timer = StringProperty("")
    source = StringProperty("")
    message = StringProperty("")
    answer_revealed = BooleanProperty(False)

    idx = NumericProperty(0)
    event = None
    input = None
    btns = None

    def begin(self):
        app = App.get_running_app()
        self.idx = 0
        app.saved = ["" for _ in app.questions]
        app.seconds = int(app.test_minutes) * 60
        self.message = ""
        self.source = ""
        self.answer_revealed = False

        if self.event:
            self.event.cancel()
            self.event = None

        if app.mode == "контроль":
            self.event = Clock.schedule_interval(self.tick, 1)

        self.render()

    def tick(self, dt):
        app = App.get_running_app()
        app.seconds -= 1
        if app.seconds < 0:
            app.seconds = 0

        self.timer = f"{app.seconds // 60:02d}:{app.seconds % 60:02d}"

        if app.seconds <= 0:
            self.finish()
            return False

        return True

    def get_current_answer(self):
        app = App.get_running_app()
        if not app.questions:
            return ""
        if not (0 <= self.idx < len(app.questions)):
            return ""

        question = app.questions[self.idx]
        question_type = question.get("type", "")

        if question_type == "текстовый":
            if self.input is None:
                return ""
            return self.input.text.strip()

        if question_type == "один":
            for option, checkbox, row in self.btns or []:
                if checkbox.active:
                    return option
            return ""

        if question_type == "несколько":
            selected = []
            for option, checkbox, row in self.btns or []:
                if checkbox.active:
                    selected.append(option)
            return "; ".join(selected)

        return ""

    def save_current(self):
        app = App.get_running_app()
        answer = self.get_current_answer()
        if 0 <= self.idx < len(app.saved):
            app.saved[self.idx] = answer
        return answer

    def has_answer(self):
        return bool(str(self.get_current_answer()).strip())

    def show_source(self):
        app = App.get_running_app()
        if not app.questions:
            return

        question = app.questions[self.idx]
        source = question.get("source", "")

        if isinstance(source, dict):
            document = clean_source_name(source.get("document", ""))
            section = str(source.get("section", "")).strip()
            text = str(source.get("text", "")).strip()
            parts = [part for part in (document, section, text) if part]
            self.source = "\n\n".join(parts)
        else:
            self.source = clean_source_name(source)

    def render(self):
        app = App.get_running_app()
        if not app.questions:
            return

        self.idx = max(0, min(self.idx, len(app.questions) - 1))
        question = app.questions[self.idx]
        self.question = question.get("text", "")

        total_questions = len(app.questions)
        current_question = self.idx + 1

        self.progress = f"Вопрос {current_question} из {total_questions}"

        if total_questions:
            self.progress_ratio = current_question / total_questions
            self.progress_percent = f"{round(self.progress_ratio * 100)}%"
        else:
            self.progress_ratio = 0.0
            self.progress_percent = "0%"

        self.message = ""
        self.source = ""
        self.answer_revealed = False

        if app.mode == "контроль":
            self.timer = f"{app.seconds // 60:02d}:{app.seconds % 60:02d}"
        else:
            # В режиме обучения таймер полностью скрыт.
            self.timer = ""

        answers_box = self.ids.answers
        answers_box.clear_widgets()
        self.input = None
        self.btns = []

        question_type = question.get("type", "")
        saved_answer = app.saved[self.idx] if self.idx < len(app.saved) else ""

        if question_type == "текстовый":
            keyboard_type = "number" if is_numeric_answer(question) else "text"

            self.input = TextInput(
                text=saved_answer,
                multiline=False,
                font_name="AppArial",
                font_size="18sp",
                size_hint_y=None,
                height=dp(58),
                input_type=keyboard_type,
                write_tab=False,
                padding=(dp(14), dp(15)),
            )

            answers_box.add_widget(self.input)

        elif question_type == "один":
            group_name = f"single_answer_{id(self)}_{self.idx}"

            for option in question.get("options", []):
                option_text = str(option)

                row = SingleAnswerRow(
                    orientation="horizontal",
                    size_hint_y=None,
                    height=dp(66),
                    spacing=dp(8),
                    padding=(dp(8), dp(7)),
                )

                checkbox = CheckBox(
                    active=(str(saved_answer).strip() == option_text),
                    group=group_name,
                    size_hint_x=None,
                    width=dp(46),
                    color=(.38, .38, .38, 1),
                )

                label = Label(
                    text=option_text,
                    font_name="AppArial",
                    font_size="16sp",
                    color=(.08, .07, .06, 1),
                    halign="left",
                    valign="middle",
                    size_hint_y=None,
                    height=dp(48),
                )

                label.bind(width=self._resize_answer_label)
                label.bind(
                    texture_size=lambda lbl, size, r=row:
                    self._resize_answer_row(lbl, size, r)
                )

                checkbox.bind(
                    active=lambda cb, value, r=row:
                    self._single_checkbox_changed(r, value)
                )

                row.attach_checkbox(checkbox)
                row.selected = checkbox.active
                row.add_widget(checkbox)
                row.add_widget(label)

                answers_box.add_widget(row)
                self.btns.append((option_text, checkbox, row))

        elif question_type == "несколько":
            saved = canon_list(saved_answer)

            for option in question.get("options", []):
                option_text = str(option)

                row = MultiAnswerRow(
                    orientation="horizontal",
                    size_hint_y=None,
                    height=dp(66),
                    spacing=dp(8),
                    padding=(dp(8), dp(7)),
                )

                checkbox = CheckBox(
                    active=(option_text.casefold() in saved),
                    size_hint_x=None,
                    width=dp(46),
                    color=(.38, .38, .38, 1),
                )

                label = Label(
                    text=option_text,
                    font_name="AppArial",
                    font_size="16sp",
                    color=(.08, .07, .06, 1),
                    halign="left",
                    valign="middle",
                    size_hint_y=None,
                    height=dp(48),
                )

                label.bind(width=self._resize_answer_label)
                label.bind(
                    texture_size=lambda lbl, size, r=row:
                    self._resize_answer_row(lbl, size, r)
                )

                checkbox.bind(
                    active=lambda cb, value, r=row:
                    self._multiple_checkbox_changed(r, value)
                )

                row.attach_checkbox(checkbox)
                row.selected = checkbox.active
                row.add_widget(checkbox)
                row.add_widget(label)

                answers_box.add_widget(row)
                self.btns.append((option_text, checkbox, row))

        else:
            self.question = "Ошибка: неизвестный тип вопроса"

    def _single_checkbox_changed(self, row, value):
        row.selected = value

    def _multiple_checkbox_changed(self, row, value):
        row.selected = value

    def _resize_answer_label(self, label, width):
        label.text_size = (width, None)

    def _resize_answer_row(self, label, texture_size, row):
        label.height = max(dp(48), texture_size[1] + dp(16))
        row.height = label.height + dp(14)

    def next(self):
        app = App.get_running_app()
        if not app.questions:
            return

        if not self.has_answer():
            self.message = "Сначала выберите или введите ответ"
            return

        self.message = ""
        self.save_current()

        if self.idx >= len(app.questions) - 1:
            self.finish()
            return

        self.idx += 1
        self.render()

    def prev(self):
        app = App.get_running_app()
        if not app.questions:
            return

        self.save_current()
        self.message = ""

        if self.idx > 0:
            self.idx -= 1
            self.render()

    def show_correct(self):
        app = App.get_running_app()
        if not app.questions:
            return

        # Кнопка "Ответ" используется только в режиме обучения.
        if app.mode != "обучение":
            return

        if not self.has_answer():
            self.message = "Сначала выберите или введите ответ"
            return

        self.message = ""
        self.save_current()
        self.answer_revealed = True

        question = app.questions[self.idx]
        question_type = question.get("type", "")
        correct = question.get("correct", [])

        if question_type in ("один", "несколько"):
            correct_values = canon_list(correct)

            for option, checkbox, row in self.btns or []:
                option_key = str(option).strip().casefold()

                if option_key in correct_values:
                    # Все правильные ответы зелёные.
                    row.status = "correct"
                elif checkbox.active:
                    # Выбранные ошибочные ответы красные.
                    row.status = "wrong"
                else:
                    row.status = "normal"

                checkbox.disabled = True

        else:
            if isinstance(correct, list):
                correct_text = "; ".join(str(item) for item in correct)
            else:
                correct_text = str(correct)

            self.message = "Правильный ответ: " + correct_text

            if self.input is not None:
                self.input.disabled = True

        self.show_source()

    def finish(self):
        app = App.get_running_app()

        try:
            self.save_current()
        except Exception:
            pass

        if self.event:
            self.event.cancel()
            self.event = None

        score = 0
        for question, answer in zip(app.questions, app.saved):
            if is_correct(question, answer):
                score += 1

        required_score = math.ceil(
            len(app.questions) * int(app.pass_percent) / 100
        )
        passed = score >= required_score

        result = self.manager.get_screen("result")
        status = "Тест пройден" if passed else "Тест не пройден"

        result.text = (
            f"{app.user}\n\n"
            f"Результат: {score} из {len(app.questions)}\n\n"
            f"Условие успешного прохождения: {int(app.pass_percent)}%\n\n"
            f"{status}"
        )

        self.manager.current = "result"


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

    def on_pre_enter(self, *args):
        self.load_values()

    def load_values(self):
        self.message = ""
        app = App.get_running_app()

        if "question_count" in self.ids:
            self.ids.question_count.text = str(int(app.question_count))

        if "test_minutes" in self.ids:
            self.ids.test_minutes.text = str(int(app.test_minutes))

        if "pass_percent" in self.ids:
            self.ids.pass_percent.text = str(int(app.pass_percent))

        Clock.schedule_once(self.build_source_rows, 0)

    def build_source_rows(self, *args):
        if "sources_box" not in self.ids:
            return

        app = App.get_running_app()
        box = self.ids.sources_box
        box.clear_widgets()

        for source in app.source_catalog:
            source_id = source["id"]
            source_name = source["name"]

            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(78),
                spacing=dp(8),
                padding=(dp(8), dp(6)),
            )

            checkbox = CheckBox(
                active=(source_id in app.selected_sources),
                size_hint_x=None,
                width=dp(42),
                color=(.20, .16, .12, 1),
            )

            # ВАЖНО: здесь НЕ используем AppArial.
            # Стандартный Kivy/Roboto корректно отображает кириллицу на Android.
            label = Label(
                text=source_name,
                font_name="Roboto",
                font_size="14sp",
                color=(.08, .07, .06, 1),
                halign="left",
                valign="middle",
            )

            label.bind(size=self._update_source_label)
            checkbox.bind(
                active=lambda cb, value, sid=source_id: self.on_source_checkbox(sid, value)
            )

            row.add_widget(checkbox)
            row.add_widget(label)
            box.add_widget(row)

        self.update_select_all_checkbox()

    def _update_source_label(self, label, size):
        label.text_size = (size[0], None)

    def on_source_checkbox(self, source_id, active):
        app = App.get_running_app()

        if active:
            app.selected_sources.add(source_id)
        else:
            app.selected_sources.discard(source_id)

        self.update_select_all_checkbox()

    def update_select_all_checkbox(self):
        if "all_sources" not in self.ids:
            return

        app = App.get_running_app()
        all_selected = bool(app.available_sources) and set(app.available_sources).issubset(
            app.selected_sources
        )
        checkbox = self.ids.all_sources

        if checkbox.active != all_selected:
            checkbox.active = all_selected

    def toggle_all_sources(self, active):
        app = App.get_running_app()

        if active:
            app.selected_sources = set(app.available_sources)
        else:
            app.selected_sources = set()

        self.build_source_rows()

    def save_settings(self, question_count=None, test_minutes=None, pass_percent=None):
        app = App.get_running_app()

        if not app.selected_sources:
            self.message = "Выберите хотя бы один источник вопросов"
            return False

        try:
            question_count = int(question_count)
            test_minutes = int(test_minutes)
            pass_percent = int(pass_percent)

            if question_count <= 0:
                raise ValueError
            if test_minutes <= 0:
                raise ValueError
            if not (1 <= pass_percent <= 100):
                raise ValueError

        except (TypeError, ValueError):
            self.message = "Проверьте значения настроек"
            return False

        app.question_count = question_count
        app.test_minutes = test_minutes
        app.pass_percent = pass_percent

        if app.save_user_settings():
            self.message = "Настройки сохранены"
            return True

        self.message = "Не удалось сохранить настройки"
        return False

    def go_back(self):
        self.manager.current = "login"


# =========================================================
# APP
# =========================================================

class TechProfiApp(App):
    title = APP_NAME

    # Реактивный режим приложения.
    # Нужен, чтобы testov.kv автоматически показывал/скрывал таймер.
    mode = StringProperty("")

    question_count = NumericProperty(DEFAULT_NUM)
    test_minutes = NumericProperty(DEFAULT_MINUTES)
    pass_percent = NumericProperty(DEFAULT_PASS_PERCENT)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bank_name = ""
        self.pool = []
        self.questions = []
        self.saved = []

        self.user = ""
        self.seconds = 0

        self.source_catalog = []
        self.available_sources = []
        self.selected_sources = set()

        self.settings_path = None

    def build(self):
        self.bank_name, self.pool = load_bank()
        self.collect_sources()

        try:
            Window.softinput_mode = "below_target"
        except Exception:
            pass

        Builder.load_file(str(KV_PATH))

        manager = ScreenManager()
        manager.add_widget(Login(name="login"))
        manager.add_widget(Test(name="test"))
        manager.add_widget(Result(name="result"))
        manager.add_widget(AdminSettings(name="settings"))
        return manager

    def on_start(self):
        self.settings_path = Path(self.user_data_dir) / "settings.json"
        self.load_user_settings()

        if not self.root:
            return

        try:
            login = self.root.get_screen("login")
            login.bank = self.bank_name
        except Exception:
            pass

    def collect_sources(self):
        """
        Источники формируются прежде всего из questions.json.
        Это гарантирует, что идентификаторы источников в настройках
        полностью совпадают с source_id самих вопросов.

        .dat используются только как резервный вариант.
        """
        catalog_by_id = {}

        for question in self.pool:
            source_id = get_question_source_id(question, self.bank_name)

            if not source_id:
                continue

            if source_id not in catalog_by_id:
                catalog_by_id[source_id] = {
                    "id": source_id,
                    "name": source_id,
                    "filename": "",
                }

        if catalog_by_id:
            self.source_catalog = sorted(
                catalog_by_id.values(),
                key=lambda item: item["name"].casefold(),
            )
        else:
            # Резерв: если questions.json не содержит источников,
            # пробуем получить их из .dat.
            self.source_catalog = discover_dat_sources()

        self.available_sources = [
            source["id"]
            for source in self.source_catalog
            if source.get("id")
        ]

        # При первой установке / после обновления все источники доступны.
        self.selected_sources = set(self.available_sources)

    def load_user_settings(self):
        self.question_count = DEFAULT_NUM
        self.test_minutes = DEFAULT_MINUTES
        self.pass_percent = DEFAULT_PASS_PERCENT
        self.selected_sources = set(self.available_sources)

        if not self.settings_path:
            return
        if not self.settings_path.exists():
            return

        try:
            with self.settings_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            self.question_count = max(1, int(data.get("question_count", DEFAULT_NUM)))
            self.test_minutes = max(1, int(data.get("test_minutes", DEFAULT_MINUTES)))
            self.pass_percent = max(
                1,
                min(100, int(data.get("pass_percent", DEFAULT_PASS_PERCENT))),
            )

            current_sources = set(self.available_sources)
            saved_sources = set(data.get("selected_sources", []))
            known_sources = set(data.get("known_sources", []))

            selected = saved_sources & current_sources
            new_sources = current_sources - known_sources
            selected.update(new_sources)

            if not known_sources and not saved_sources:
                selected = set(current_sources)

            self.selected_sources = selected

        except Exception:
            self.question_count = DEFAULT_NUM
            self.test_minutes = DEFAULT_MINUTES
            self.pass_percent = DEFAULT_PASS_PERCENT
            self.selected_sources = set(self.available_sources)

    def save_user_settings(self):
        if not self.settings_path:
            self.settings_path = Path(self.user_data_dir) / "settings.json"

        data = {
            "question_count": int(self.question_count),
            "test_minutes": int(self.test_minutes),
            "pass_percent": int(self.pass_percent),
            "selected_sources": sorted(self.selected_sources),
            "known_sources": sorted(self.available_sources),
        }

        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)

            with self.settings_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)

            return True

        except Exception:
            return False

    def prepare_questions(self):
        filtered = []

        for question in self.pool:
            source_id = get_question_source_id(question, self.bank_name)

            if source_id in self.selected_sources:
                filtered.append(question)

        random.shuffle(filtered)

        if self.mode == "контроль":
            count = min(int(self.question_count), len(filtered))
            self.questions = filtered[:count]
        else:
            self.questions = filtered


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    TechProfiApp().run()
