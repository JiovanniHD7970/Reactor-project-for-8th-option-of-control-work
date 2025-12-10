Reactor — учебный проект
Язык: Python + C
Описание:
Графическая программа для исследования работы реактора.
Основные вычисления выполняются в C-библиотеке reactor_model.dll, Python используется для интерфейса и визуализации.

Структура проекта:
src/
  app.py              — GUI на Tkinter
  db.py               — работа с SQLite
  model_core.py       — загрузка DLL, вызовы C-функции
  reactor_model.c     — реализация функции compute_CB
  reactor_model.dll   — собранная C-библиотека

Для запуска:
release/
  app.exe             — Открыть
