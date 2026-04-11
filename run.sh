#!/bin/bash
pip install aiohttp aiogram pydantic pydantic-settings aiosqlite "apscheduler>=3.10,<4.0" python-dotenv
python -m src.main
