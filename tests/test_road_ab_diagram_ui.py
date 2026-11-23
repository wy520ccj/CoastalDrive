"""既有实际A/B静态读取与明确边界夹具；图解交互不推进物理或写成绩。"""

import hashlib
from pathlib import Path

import pytest
from test_brake_road_ab import attempt, config

from application import CoastalDrive
from player_road_ab import PlayerRoadAB
from race import GameMode


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, output=tmp_path/'game')
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.back_to_menu()
    yield game
    game.close_game()


@pytest.mark.parametrize('kind', ['slalom', 'short', 'precision_failed'])
def test_graph_table_navigation_and_readonly_snapshot(app, tmp_path, kind):
    brakes = kind != 'slalom'
    if kind == 'precision_failed':
        store = PlayerRoadAB(tmp_path/'precision-fixture.json', brakes=True)
        store.freeze(attempt(short=False, succeeded=False), config(2))
        store.observe(attempt(2, short=False, error=2.))
    else:
        source = Path('docs/evidence')/('BRAKE-ROAD-AB-01/normal/player-braking-ab.json' if brakes else
                                       'PLAYER-ROAD-AB-01/normal/player-road-ab.json')
        path = tmp_path/'actual-ab.json'
        path.write_bytes(source.read_bytes())
        store = PlayerRoadAB(path, brakes=brakes)
    if brakes:
        app.choose_braking_lesson(GameMode.SHORT_BRAKING if kind == 'short' else GameMode.BRAKING_LESSON)
        app.player_brake_ab = store
    else:
        app.choose_slalom_lesson(GameMode.FAST_SLALOM)
        app.player_road_ab = store
    before = app.session.current
    old = hashlib.sha256(store.path.read_bytes()).hexdigest()
    app.open_player_road_ab('brakes' if brakes else 'tires')
    panel, diagram = app.player_road_panel, app.player_road_panel.diagram
    assert app.main_menu.home.isHidden()
    assert panel.graph and not diagram.root.isHidden() and all(column.isHidden() for column in panel.columns)
    if not brakes:
        assert diagram.selected == 2 and '超线' in diagram.detail.getText()
        app.key_down('arrow_right')
        app.key_up('arrow_right')
        assert diagram.selected == 3 and 'A 未到达' in diagram.detail.getText()
        diagram.buttons[5]['command'](*diagram.buttons[5]['extraArgs'])
        assert diagram.selected == 5 and '320m' in diagram.detail.getText()
    else:
        assert all(button.isHidden() for button in diagram.buttons)
        assert '入门' in diagram.detail.getText()
        if kind == 'precision_failed':
            assert '失败不算成绩' in diagram.detail.getText() and 'B−A' not in panel.delta.getText()
    assert diagram.detail.getTightBounds(panel.root)[0].z > panel.delta.getTightBounds(panel.root)[1].z+.02
    app.key_down('space')
    app.key_up('space')
    assert not panel.graph and diagram.root.isHidden() and all(not column.isHidden() for column in panel.columns)
    panel.tabs[2]['command'](*panel.tabs[2]['extraArgs'])
    assert panel.view == 2 and all(not column.isHidden() for column in panel.parameters)
    assert all(column.isHidden() for column in panel.columns) and diagram.root.isHidden()
    assert store.a['created_at'][:19] in panel.metadata.getText()
    assert '制动扭矩' in panel.parameters[0].getText()
    panel.tabs[0]['command'](*panel.tabs[0]['extraArgs'])
    assert panel.graph and not diagram.root.isHidden()
    count = diagram.root.getNumChildren()
    panel.show(store)
    panel.show(store)
    assert diagram.root.getNumChildren() == count
    assert app.session.current == before and hashlib.sha256(store.path.read_bytes()).hexdigest() == old
    app.key_down('escape')
    app.key_up('escape')
    assert panel.root.isHidden() and (app.braking_menu if brakes else app.slalom_menu)


def test_return_from_brake_to_empty_gates_restores_detail_and_disables_retest(app, tmp_path):
    brakes = PlayerRoadAB(tmp_path/'brakes.json', brakes=True)
    brakes.freeze(attempt(short=False, succeeded=False), config(2))
    app.player_brake_ab = brakes
    app.open_player_road_ab('brakes')
    app.player_road_ab = PlayerRoadAB(tmp_path/'gates.json')
    app.open_player_road_ab('tires')
    panel = app.player_road_panel
    assert panel.diagram.detail.getX() > panel.diagram.buttons[-1].getX()
    assert panel.retest_button['state'] == 'disabled'
    before = app.session.current
    panel.key('enter')
    assert app.workspace == 'game' and app.session.current == before
