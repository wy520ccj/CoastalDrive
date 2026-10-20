"""完整亲驾A/B并排，失败无有效总时间，条件变化不生成差值。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode

from player_road_ab import mismatches
from ui import theme


class PlayerRoadPanel:
    def __init__(self, parent, font, textures):
        self.root = DirectFrame(parent=parent, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.70, 1.70, -.86, .80), sortOrder=115, state=DGG.NORMAL)

        def text(value, x, z, scale=.038, color=theme.INK):
            return OnscreenText(parent=self.root, text=value, font=font, fg=color, align=TextNode.ALeft,
                pos=(x, z), scale=scale, mayChange=True)

        text('亲自驾驶 · 改装前后道路对照', -1.52, .62, .060)
        self.status = text('', -1.52, .48, .035, theme.SEA)
        self.status.textNode.setWordwrap(86)
        self.cards = [text('', x, .28, .038, color) for x, color in ((-1.52, theme.SEA), (.12, theme.INK))]
        for card in self.cards:
            card.textNode.setWordwrap(37)
        self.columns = [text('', x, -.05, .035) for x in (-1.52, -.40, .55)]
        self.delta = text('', -1.52, -.40, .034, theme.SEA)
        self.notice = text('', -1.52, -.50, .029, theme.MUTED)
        self.notice.textNode.setWordwrap(102)
        text('同一道题与输入设置，驾驶操作仍可不同；本页不证明单一硬件因果，也不授奖。', -1.52, -.62, .028, theme.MUTED)
        self.back = DirectButton(parent=self.root, text='返回前胎配方 · Esc', text_font=font, text_fg=theme.INK,
            text_scale=.040, frameTexture=textures, frameColor=(1, 1, 1, 1), relief=DGG.FLAT, pressEffect=False,
            frameSize=(-.65, .65, -.055, .055), pos=(0, 0, -.75), command=self.hide)
        self.root.hide()

    def show(self, store):
        a, b = store.a, store.b
        self.status.setText('从结算安装不同前胎时固定A，重试后记录最近一次完整B。' if a is None else
            ('高速验车' if a['context']['mode'] == 'fast_slalom' else '连续过门')+' · A固定 / B取最近一次结束记录')
        for side, item, label in zip(self.cards, (a, b), ('A · 安装前这一次', 'B · 安装后最近一次'), strict=True):
            if item is None:
                side.setText(label+'\n暂无记录'+('\n亲自完成或结束同题后建立' if label.startswith('B') else ''))
                continue
            result = item['result']
            elapsed = f"有效{result['run_seconds']:.3f}s" if result['succeeded'] else '未通过 · 无有效总时间'
            side.setText(f"{label} · 前胎{item['config']['lateral_stiffness']/1000:g}k\n"
                         f"{result['gates']}/6门 · {elapsed}\n"+result['reason'][:50])
        rows = [['门'], ['A余量m'], ['B余量m']]
        for index in range(6):
            rows[0].append(str(index+1))
            for column, item in zip(rows[1:], (a, b), strict=True):
                margins = item['result']['clearances'] if item else ()
                column.append(f'{margins[index]:+.3f}' if index < len(margins) else '未到达')
        for column, row in zip(self.columns, rows, strict=True):
            column.setText('\n'.join(row))
        differences = mismatches(a, b) if a is not None and b is not None else []
        if differences:
            self.delta.setText('条件不同，不计算差值。')
        elif a is not None and b is not None and a['result']['succeeded'] and b['result']['succeeded']:
            self.delta.setText(f"有效用时 B−A {b['result']['run_seconds']-a['result']['run_seconds']:+.3f}s；负值表示本次B更快")
        else:
            self.delta.setText('双方都有效完成后才比较总用时；漏门记录只看已到达的门。')
        note = store.notice or '；'.join(differences) or (
            ('A记录于'+a['created_at'][:19]+'；' if a else '')+
            'A在下次结算改装时替换；B取同目标硬件最近整次记录，不拼接单门。')
        self.notice.setText(note[:150])
        self.root.show()

    def key(self, key):
        if key in ('escape', 'enter'):
            self.hide()

    def hide(self):
        self.root.hide()
