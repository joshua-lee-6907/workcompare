# ilrt-app

## 已完成改造
1. 提供 `PySide6 / PyQt5` 双兼容界面外壳。
2. 提供核心计算类 `DecimalEngine`（默认 60 位精度）。
3. 在 `main_window.py` 使用 `addSubInterface(...)` 挂载 `page_calculator` 与 `setting_interface`。
4. 通过 `QSettings` 持久化 `decimal_precision`，设置页 SpinBox 实时写入。
5. 提供 Inno Setup 便携打包脚本：`packaging/ilrt_portable.iss`。

## 运行
```bash
cd ilrt-app
python app.py
```
