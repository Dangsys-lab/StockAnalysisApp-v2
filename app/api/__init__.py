# -*- coding: utf-8 -*-
"""
API蓝图模块
"""

from flask import Blueprint

api_bp = Blueprint('api', __name__)

from app.api import indicators, iap, market, portfolio, report, scheduler
