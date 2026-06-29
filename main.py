"""
二维码生成器 - Supabase 存储版 (仅文字)
适配 Pydroid 3，支持中文字体
"""
import os
import sys
import traceback
import threading
import time
import requests
import qrcode
from io import BytesIO
from kivy.app import App
from kivy.logger import Logger
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.video import Video
from kivy.core.image import Image as CoreImage
from kivy.clock import mainthread
from kivy.utils import platform

# ======================== 中文字体支持 ========================
if platform == 'android':
    DEFAULT_FONT = "/system/fonts/NotoSansCJK-Regular.ttc"
elif platform == 'win':
    DEFAULT_FONT = "C:/Windows/Fonts/msyh.ttc"
elif platform == 'linux':
    DEFAULT_FONT = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
else:
    DEFAULT_FONT = None

# 注册字体（如果存在）
if DEFAULT_FONT and os.path.exists(DEFAULT_FONT):
    from kivy.core.text import LabelBase
    LabelBase.register(name='CustomFont', fn_regular=DEFAULT_FONT)
    FONT_NAME = 'CustomFont'
else:
    FONT_NAME = None

# ===== 配置 =====
SUPABASE_URL = "https://pyffuyljlasofxqptebq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB5ZmZ1eWxqbGFzb2Z4cXB0ZWJxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE4MDY1NjgsImV4cCI6MjA4NzM4MjU2OH0.f6Il6uCiBT8jHpG1sckSw3WVWYquEbL2eHncCJHGuLo"
BUCKET_NAME = "videos"

# 错误日志保存路径（方便排查）
ERROR_LOG = '/sdcard/qr_error.log' if platform == 'android' else 'qr_error.log'

# ===== 全局异常捕获 =====
def global_exception_handler(exc_type, exc_value, exc_tb):
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    with open(ERROR_LOG, 'a') as f:
        f.write(f"Uncaught: {error_msg}\n")
    Logger.error(f"Uncaught: {error_msg}")

sys.excepthook = global_exception_handler


class QRGeneratorApp(App):
    def build(self):
        self.title = "二维码生成器"
        # 不再需要图片/视频路径
        # self.selected_image_path = None
        # self.selected_video_path = None
        # self.uploading = False  # 文字模式不需要上传

        # 主 Tab 面板（只有一个 Tab，也可以不加 Tab，但保留结构）
        tabs = TabbedPanel(do_default_tab=False)

        # --- 文字 Tab ---
        tab_text = TabbedPanelItem(text='文字')
        layout_text = BoxLayout(orientation='vertical', padding=10, spacing=10)
        self.text_input = TextInput(hint_text='输入文字', multiline=False, font_name=FONT_NAME if FONT_NAME else '')
        self.text_input.bind(on_text_validate=self.generate_text_qr)
        btn_text = Button(text='生成文字二维码', size_hint_y=None, height=50, font_name=FONT_NAME if FONT_NAME else '')
        btn_text.bind(on_press=self.generate_text_qr)
        self.text_qr_img = Image(size_hint=(1, 0.6))
        layout_text.add_widget(self.text_input)
        layout_text.add_widget(btn_text)
        layout_text.add_widget(self.text_qr_img)
        tab_text.add_widget(layout_text)
        tabs.add_widget(tab_text)

        # 不再添加图片和视频 Tab

        # 检查存储权限（仅Android，文字模式其实不需要存储权限，但保留无妨）
        if platform == 'android':
            self.check_storage_permission()

        return tabs

    # ---------- 权限检查（不依赖 android.permissions） ----------
    def check_storage_permission(self):
        """检查是否有读取外部存储的权限，没有则弹窗提示"""
        try:
            # 尝试读取 /sdcard 目录，如果失败则权限不足
            test_path = '/sdcard'
            if os.path.exists(test_path):
                # 尝试列出目录
                os.listdir(test_path)
            else:
                self.show_popup('权限提示', '请手动授予存储权限：\n设置 → 应用 → Pydroid 3 → 权限 → 存储')
        except PermissionError:
            self.show_popup('权限提示', '存储权限未授予，请手动开启：\n设置 → 应用 → Pydroid 3 → 权限 → 存储')
        except Exception as e:
            Logger.warning(f"权限检查异常: {e}")

    # ---------- 文字生成 ----------
    def generate_text_qr(self, instance):
        try:
            text = self.text_input.text.strip()
            if not text:
                self.show_popup('提示', '请输入文字')
                return
            img = qrcode.make(text)
            self.display_qr(self.text_qr_img, img)
        except Exception as e:
            self.log_error('文字生成失败', e)
            self.show_popup('错误', str(e))

    # ---------- 显示二维码（主线程安全） ----------
    @mainthread
    def display_qr(self, image_widget, qr_img):
        try:
            buf = BytesIO()
            qr_img.save(buf, format='PNG')
            buf.seek(0)
            core_img = CoreImage(BytesIO(buf.read()), ext='png')
            texture = core_img.texture
            texture.flip_vertical()
            image_widget.texture = texture
        except Exception as e:
            self.log_error('显示二维码失败', e)

    # ---------- 弹窗（主线程安全） ----------
    @mainthread
    def show_popup(self, title, message):
        try:
            content = BoxLayout(orientation='vertical', padding=10, spacing=10)
            from kivy.uix.scrollview import ScrollView
            sv = ScrollView(size_hint=(1, 0.8))
            label = Label(text=message, halign='left', valign='top', font_name=FONT_NAME if FONT_NAME else '')
            label.bind(size=lambda s, w: setattr(s, 'text_size', (s.width, None)))
            sv.add_widget(label)
            btn = Button(text='确定', size_hint_y=None, height=50, font_name=FONT_NAME if FONT_NAME else '')
            content.add_widget(sv)
            content.add_widget(btn)
            popup = Popup(title=title, content=content, size_hint=(0.9, 0.6))
            btn.bind(on_press=popup.dismiss)
            popup.open()
        except Exception as e:
            with open(ERROR_LOG, 'a') as f:
                f.write(f"弹窗失败: {traceback.format_exc()}\n")

    # ---------- 错误日志 ----------
    def log_error(self, msg, e):
        with open(ERROR_LOG, 'a') as f:
            f.write(f"{msg}: {traceback.format_exc()}\n")
        Logger.error(f"{msg}: {e}")


if __name__ == '__main__':
    try:
        QRGeneratorApp().run()
    except Exception as e:
        with open(ERROR_LOG, 'a') as f:
            f.write(f"应用启动崩溃: {traceback.format_exc()}\n")
        raise