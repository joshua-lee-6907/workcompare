from PyQt5.QtCore import QThread, pyqtSignal
import time


class CoreWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, payload: dict):
        super().__init__()
        self.payload = payload
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            # ===== 在这里接入你自己的核心 .py 函数 =====
            # 示例：for p, msg in your_core_function(self.payload): emit progress
            result_rows = []
            for i in range(1, 101):
                if self._stop:
                    self.progress.emit(i, '任务已停止')
                    return
                time.sleep(0.03)
                self.progress.emit(i, f'正在处理... {i}%')
                if i % 20 == 0:
                    result_rows.append({'步骤': i, '状态': '完成', '说明': f'阶段 {i//20}'})
            self.finished_ok.emit(result_rows)
        except Exception as e:
            self.failed.emit(str(e))
