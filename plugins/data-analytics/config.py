# -*- coding: utf-8 -*-
import os

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
DATA_PATH = os.path.join(BASE_PATH, 'data')
DB_PATH = os.path.join(DATA_PATH, 'analytics.db')
LOG_PATH = os.path.join(BASE_PATH, 'log')

# 确保目录存在
os.makedirs(DATA_PATH, exist_ok=True)
os.makedirs(LOG_PATH, exist_ok=True)

