"""普通提示与醒目错误条；原始异常写入启动日志，不向用户输出英文堆栈。"""

import json
import logging
import re

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, OnscreenText
from panda3d.core import TextNode

from ui.lab_widgets import MUTED

ERROR = (.65, .13, .10, 1)


class LabFeedback:
    def __init__(self, app):
        self.footer = OnscreenText(parent=app.root, font=app.font, fg=MUTED,
            text="选择工况，开始第一次试验", pos=(-.88, -.925), scale=.035,
            wordwrap=51, align=TextNode.ALeft, mayChange=True)
        self.root = DirectFrame(parent=app.root, frameColor=(1., .94, .90, 1),
            frameSize=(-.94, 1.72, -.99, -.73), sortOrder=130, state=DGG.NORMAL)
        DirectFrame(parent=self.root, frameColor=ERROR,
                    frameSize=(-.94, -.925, -.99, -.73))
        app.text("请检查以下问题", -.86, -.79, .043, ERROR, parent=self.root)
        self.message = OnscreenText(parent=self.root, font=app.font, fg=ERROR, text="",
            pos=(-.86, -.855), scale=.037, wordwrap=64, align=TextNode.ALeft, mayChange=True)
        app.button("收起提示", 1.48, -.785, .34, self.dismiss, parent=self.root)
        self.root.hide()

    def setText(self, text):
        self.footer.setText(text if len(text) <= 90 else text[:89]+"…")

    def getText(self):
        return self.message.getText() if not self.root.isHidden() else self.footer.getText()

    def error(self, text):
        self.message.setText(text if len(text) <= 155 else text[:135]+"……（完整原因见启动日志）")
        self.setText(text)
        self.root.show()

    def dismiss(self):
        self.root.hide()


def error_text(error):
    if isinstance(error, FileNotFoundError):
        return "找不到所需文件，请确认文件仍在原位置。"
    if isinstance(error, PermissionError):
        return "无法读写文件，请检查文件权限或是否被其他程序占用。"
    if isinstance(error, json.JSONDecodeError):
        return f"文件内容不是有效JSON，请检查第{error.lineno}行、第{error.colno}列。"
    if isinstance(error, UnicodeError):
        return "文件编码不正确，请使用UTF-8格式的文件。"
    message = str(error)
    if re.match(r"^[\u4e00-\u9fff]", message):
        return message
    if isinstance(error, (KeyError, TypeError, ValueError)):
        return "文件内容或参数格式不符合要求，请检查所选文件及参数。"
    if isinstance(error, OSError):
        return "文件或目录操作失败，请确认路径有效且磁盘可写。"
    return "计算未能完成，已保留完成部分；详细原因已记录到启动日志。"


def log_error(action, error):
    logging.getLogger("vehicle-lab").error("%s: %s", action, error,
                                           exc_info=(type(error), error, error.__traceback__))
