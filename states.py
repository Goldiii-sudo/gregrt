"""FSM состояния бота"""
from aiogram.fsm.state import State, StatesGroup


class GenerationStates(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_image = State()
    waiting_for_context_prompt = State()
    waiting_for_search_query = State()
