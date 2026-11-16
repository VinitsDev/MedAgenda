"""Relógio do consultório: hora de parede, sem fuso (as tabelas não guardam fuso)."""
from datetime import datetime


def agora():
    return datetime.now()