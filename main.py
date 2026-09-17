import json, random
from pathlib import Path
from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.resources import resource_add_path

BASE=Path(__file__).resolve().parent
resource_add_path(str(BASE))
LabelBase.register(name='AppArial', fn_regular=str(BASE/'fonts'/'Arial.ttf'))
APP_NAME='Тест_ОВ'; DEFAULT_NUM=25; DEFAULT_MINUTES=15; DEFAULT_PASS=20

def load_bank():
    obj=json.loads((BASE/'data'/'questions.json').read_text(encoding='utf-8'))
    return obj['bank_name'], obj['questions']

def canon_list(v):
    if isinstance(v,list): parts=v
    else: parts=str(v or '').split(';')
    return {str(x).strip().casefold() for x in parts if str(x).strip()}

def is_correct(q, ans):
    if q['type']=='несколько': return canon_list(ans)==canon_list(q['correct'])
    acceptable=canon_list(q['correct'])
    return str(ans or '').strip().casefold() in acceptable

class Login(Screen):
    bank=StringProperty('')
    def on_pre_enter(self): self.bank=App.get_running_app().bank_name
    def start(self, mode):
        name=self.ids.name.text.strip()
        if not name: self.ids.msg.text='Введите фамилию и инициалы'; return
        app=App.get_running_app(); app.user=name; app.mode=mode; app.prepare_questions()
        self.manager.current='test'; self.manager.get_screen('test').begin()

class Test(Screen):
    question=StringProperty(''); progress=StringProperty(''); timer=StringProperty(''); source=StringProperty(''); idx=NumericProperty(0)
    event=None
    def begin(self):
        a=App.get_running_app(); self.idx=0; a.saved=['']*len(a.questions); a.seconds=DEFAULT_MINUTES*60
        if self.event: self.event.cancel()
        self.event=Clock.schedule_interval(self.tick,1) if a.mode=='контроль' else None
        self.render()
    def tick(self,dt):
        a=App.get_running_app(); a.seconds-=1; self.timer=f'{a.seconds//60:02d}:{a.seconds%60:02d}'
        if a.seconds<=0: self.finish(); return False
    def save_current(self):
        a=App.get_running_app(); q=a.questions[self.idx]
        if q['type']=='текстовый': ans=self.input.text.strip()
        elif q['type']=='один': ans=next((b.text for b in self.btns if b.state=='down'),'')
        else: ans='; '.join(o for o,c in self.btns if c.active)
        a.saved[self.idx]=ans; return ans
    def render(self):
        from kivy.uix.togglebutton import ToggleButton
        from kivy.uix.checkbox import CheckBox
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.textinput import TextInput
        a=App.get_running_app(); q=a.questions[self.idx]
        self.question=q['text']; self.progress=f'Вопрос {self.idx+1} из {len(a.questions)}'; self.source=''
        self.timer='' if a.mode=='обучение' else f'{a.seconds//60:02d}:{a.seconds%60:02d}'
        box=self.ids.answers; box.clear_widgets()
        if q['type']=='текстовый':
            self.input=TextInput(text=a.saved[self.idx],multiline=False,font_name='AppArial',font_size='18sp',size_hint_y=None,height='52dp'); box.add_widget(self.input)
        elif q['type']=='один':
            self.btns=[]
            for o in q['options']:
                b=ToggleButton(text=o,group='ans',font_name='AppArial',font_size='16sp',size_hint_y=None,height='64dp',text_size=(None,None)); b.state='down' if a.saved[self.idx]==o else 'normal'; box.add_widget(b); self.btns.append(b)
        else:
            self.btns=[]; saved=canon_list(a.saved[self.idx])
            for o in q['options']:
                row=BoxLayout(size_hint_y=None,height='64dp',spacing='6dp'); c=CheckBox(active=o.casefold() in saved,size_hint_x=.12); lab=Label(text=o,font_name='AppArial',halign='left',valign='middle'); lab.bind(size=lambda w,s:setattr(w,'text_size',(s[0],None))); row.add_widget(c); row.add_widget(lab); box.add_widget(row); self.btns.append((o,c))
    def next(self):
        self.save_current()
        if self.idx>=len(App.get_running_app().questions)-1: self.finish(); return
        self.idx+=1; self.render()
    def prev(self):
        self.save_current()
        if self.idx>0: self.idx-=1; self.render()
    def show_correct(self):
        self.save_current(); q=App.get_running_app().questions[self.idx]
        self.source='Правильный ответ: '+ '; '.join(q['correct'])+'\nИсточник: '+q['source']
    def finish(self):
        try: self.save_current()
        except: pass
        if self.event: self.event.cancel(); self.event=None
        a=App.get_running_app(); score=sum(is_correct(q,ans) for q,ans in zip(a.questions,a.saved)); passed=score>=min(DEFAULT_PASS,len(a.questions))
        r=self.manager.get_screen('result'); r.text=f'{a.user}\n\nРезультат: {score} из {len(a.questions)}\n'+('Тест пройден' if passed else 'Тест не пройден'); self.manager.current='result'

class Result(Screen): text=StringProperty('')
class TestOVApp(App):
    title=APP_NAME
    def build(self):
        self.bank_name,self.pool=load_bank(); return Builder.load_file(str(BASE/'testov.kv'))
    def prepare_questions(self):
        self.questions=list(self.pool); random.shuffle(self.questions)
        if self.mode=='контроль': self.questions=self.questions[:min(DEFAULT_NUM,len(self.questions))]

TestOVApp().run()
