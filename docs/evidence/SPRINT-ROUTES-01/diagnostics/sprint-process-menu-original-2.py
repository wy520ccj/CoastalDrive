from pathlib import Path
import sys
sys.path.insert(0,str(Path.cwd()/'src'))
from application import CoastalDrive
if __name__=='__main__':
    app=CoastalDrive(smoke=True, independent_clock=True, output=Path('logs/validation/SPRINT-ROUTES-01-process-menu-original-2'))
    try:
        app.taskMgr.remove('finish-smoke'); app.taskMgr.remove('drive-update')
        app.back_to_menu(); app._shown_phase=None; app.refresh_panel()
    finally:
        app.close_game()
