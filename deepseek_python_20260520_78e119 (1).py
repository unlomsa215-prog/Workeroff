# main.py
import logging
import random
import asyncio
import json
import os
import secrets
from datetime import datetime
from typing import Dict, Optional, Any, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = ""
ADMIN_PASSWORD = "1873"
SUPPORT_USERNAME = "@Kyniks_me"
CHAT_USERNAME = "@chatmansorybotwt"
CHANNEL_USERNAME = "@workermen_mansorynews"
BOT_NAME = "MANSORY"
BOT_VERSION = "3.2"

# ========== БАЗА ДАННЫХ ==========
class Database:
    def __init__(self, db_file='database.json'):
        self.db_file = db_file
        self.data = self.load_data()
        self._migrate()
    
    def _migrate(self):
        if "promocodes" not in self.data:
            self.data["promocodes"] = {}
        if "cheques" not in self.data:
            self.data["cheques"] = {}
        if "used_cheques" not in self.data:
            self.data["used_cheques"] = []
        if "used_promocodes" not in self.data:
            self.data["used_promocodes"] = {}
        if "users" not in self.data:
            self.data["users"] = {}
        if "banned" not in self.data:
            self.data["banned"] = []
        if "referrals" not in self.data:
            self.data["referrals"] = {}
        self.save_data()
    
    def load_data(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"users": {}, "banned": [], "referrals": {}, "promocodes": {}, "cheques": {}, "used_cheques": [], "used_promocodes": {}}
    
    def save_data(self):
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Ошибка сохранения БД: {e}")
    
    def get_user(self, user_id: int) -> Dict:
        uid = str(user_id)
        if uid not in self.data["users"]:
            self.data["users"][uid] = {
                "balance": 5000,
                "games_played": 0,
                "games_won": 0,
                "total_bet": 0,
                "total_win": 0,
                "last_bonus": 0,
                "first_name": "",
                "username": "",
                "referrer": None,
                "referrals": []
            }
            self.save_data()
        return self.data["users"][uid]
    
    def get_balance(self, user_id: int) -> int:
        return self.get_user(user_id).get("balance", 0)
    
    def update_balance(self, user_id: int, amount: int):
        user = self.get_user(user_id)
        user["balance"] = user.get("balance", 0) + amount
        self.save_data()
    
    def update_stats(self, user_id: int, bet: int, win: int = 0, is_win: bool = False):
        user = self.get_user(user_id)
        user["games_played"] = user.get("games_played", 0) + 1
        user["total_bet"] = user.get("total_bet", 0) + bet
        if is_win:
            user["games_won"] = user.get("games_won", 0) + 1
            user["total_win"] = user.get("total_win", 0) + win
        self.save_data()
    
    def is_banned(self, user_id: int) -> bool:
        return str(user_id) in self.data["banned"]
    
    def ban_user(self, user_id: int) -> bool:
        uid = str(user_id)
        if uid in self.data["banned"]:
            return False
        self.data["banned"].append(uid)
        self.save_data()
        return True
    
    def unban_user(self, user_id: int) -> bool:
        uid = str(user_id)
        if uid not in self.data["banned"]:
            return False
        self.data["banned"].remove(uid)
        self.save_data()
        return True
    
    def get_top_users(self, limit: int = 15) -> List:
        users = []
        for uid, data in self.data["users"].items():
            users.append((uid, data))
        users.sort(key=lambda x: x[1].get("balance", 0), reverse=True)
        return users[:limit]
    
    def get_registered_count(self) -> int:
        return len(self.data["users"])
    
    def get_all_users(self) -> Dict:
        return self.data["users"]
    
    def get_user_info(self, user_id: str) -> Optional[Dict]:
        return self.data["users"].get(user_id)
    
    def add_referral(self, user_id: int, referrer_id: int):
        user = self.get_user(user_id)
        if user["referrer"] is None and referrer_id != user_id:
            user["referrer"] = referrer_id
            self.update_balance(referrer_id, 1000)
            ref_user = self.get_user(referrer_id)
            if user_id not in ref_user["referrals"]:
                ref_user["referrals"].append(user_id)
            self.save_data()
            return True
        return False
    
    def get_referral_stats(self, user_id: int) -> Dict:
        user = self.get_user(user_id)
        referrals_list = user.get("referrals", [])
        active = 0
        for ref_id in referrals_list:
            ref_user = self.get_user(ref_id)
            if ref_user.get("games_played", 0) > 0:
                active += 1
        return {
            "total": len(referrals_list),
            "active": active,
            "referrer": user.get("referrer")
        }
    
    # ========== ПРОМОКОДЫ ==========
    def create_promocode(self, code: str, max_activations: int, amount: int) -> bool:
        if code in self.data["promocodes"]:
            return False
        self.data["promocodes"][code] = {
            "max_activations": max_activations,
            "used_count": 0,
            "amount": amount,
            "users": []
        }
        self.save_data()
        return True
    
    def activate_promocode(self, user_id: int, code: str) -> Dict:
        promocode = self.data["promocodes"].get(code)
        if not promocode:
            return {"success": False, "reason": "not_found"}
        
        uid = str(user_id)
        if uid in promocode["users"]:
            return {"success": False, "reason": "already_used"}
        
        if promocode["used_count"] >= promocode["max_activations"]:
            return {"success": False, "reason": "expired"}
        
        if uid in self.data["used_promocodes"]:
            if code in self.data["used_promocodes"][uid]:
                return {"success": False, "reason": "already_used"}
        
        promocode["used_count"] += 1
        promocode["users"].append(uid)
        
        if uid not in self.data["used_promocodes"]:
            self.data["used_promocodes"][uid] = []
        self.data["used_promocodes"][uid].append(code)
        
        self.update_balance(user_id, promocode["amount"])
        self.save_data()
        
        return {"success": True, "amount": promocode["amount"]}
    
    def delete_promocode(self, code: str) -> bool:
        if code in self.data["promocodes"]:
            del self.data["promocodes"][code]
            self.save_data()
            return True
        return False
    
    def get_all_promocodes(self) -> Dict:
        return self.data.get("promocodes", {})
    
    # ========== ЧЕКИ ==========
    def create_cheque(self, user_id: int, amount: int, activations: int) -> Optional[str]:
        balance = self.get_balance(user_id)
        total_cost = amount * activations
        if total_cost > balance:
            return None
        
        self.update_balance(user_id, -total_cost)
        
        code = secrets.token_urlsafe(8)
        while code in self.data["cheques"]:
            code = secrets.token_urlsafe(8)
        
        self.data["cheques"][code] = {
            "creator": str(user_id),
            "amount": amount,
            "max_activations": activations,
            "used_count": 0,
            "users": [],
            "created_at": datetime.now().timestamp()
        }
        self.save_data()
        return code
    
    def activate_cheque(self, user_id: int, code: str) -> Dict:
        cheque = self.data["cheques"].get(code)
        if not cheque:
            return {"success": False, "reason": "not_found"}
        
        uid = str(user_id)
        if uid in cheque["users"]:
            return {"success": False, "reason": "already_used"}
        
        if cheque["used_count"] >= cheque["max_activations"]:
            return {"success": False, "reason": "expired"}
        
        cheque["used_count"] += 1
        cheque["users"].append(uid)
        
        if "used_cheques" not in self.data:
            self.data["used_cheques"] = []
        self.data["used_cheques"].append({
            "code": code,
            "user": uid,
            "amount": cheque["amount"],
            "time": datetime.now().timestamp()
        })
        
        self.update_balance(user_id, cheque["amount"])
        self.save_data()
        
        return {"success": True, "amount": cheque["amount"]}
    
    def get_cheque_info(self, code: str) -> Optional[Dict]:
        return self.data["cheques"].get(code)
    
    def get_my_cheques(self, user_id: int) -> List:
        user_cheques = []
        for code, data in self.data["cheques"].items():
            if data["creator"] == str(user_id):
                user_cheques.append({
                    "code": code,
                    "amount": data["amount"],
                    "max": data["max_activations"],
                    "used": data["used_count"],
                    "created_at": data["created_at"]
                })
        return user_cheques
    
    def get_cheque_stats(self, user_id: int) -> Dict:
        used = []
        for item in self.data.get("used_cheques", []):
            if item["user"] == str(user_id):
                used.append(item)
        return {
            "total_used": len(used),
            "total_amount": sum(u["amount"] for u in used),
            "cheques": used
        }

# ========== ПАРСЕР СУММ С СУФФИКСАМИ (РУССКИЕ ТОЖЕ РАБОТАЮТ) ==========
def parse_amount(amount_str: str, current_balance: int = None) -> int:
    """Парсит сумму с суффиксами: k, m, b, t, qa, qi, sx, sp, o, n, d, all и русскими к, м, б, т, кк, мм, бб, тт"""
    if not amount_str:
        return 0
    
    amount_str = str(amount_str).lower().strip().replace(',', '.')
    
    # Специальный случай: all (весь баланс)
    if amount_str == 'all' and current_balance is not None:
        return current_balance
    
    # Русские суффиксы (сначала длинные)
    suffixes = [
        ('кк', 10**6), ('мм', 10**12), ('бб', 10**18), ('тт', 10**24),
        ('к', 1000), ('м', 10**6), ('б', 10**9), ('т', 10**12),
        ('к', 1000), ('м', 10**6), ('б', 10**9), ('т', 10**12),
        ('qa', 10**15), ('qi', 10**18), ('sx', 10**21), ('sp', 10**24),
        ('o', 10**27), ('n', 10**30), ('d', 10**33),
        ('k', 1000), ('m', 10**6), ('b', 10**9), ('t', 10**12)
    ]
    
    for suffix, multiplier in suffixes:
        if amount_str.endswith(suffix):
            num_part = amount_str[:-len(suffix)]
            try:
                if '.' in num_part:
                    num = float(num_part)
                else:
                    num = int(num_part)
                return int(num * multiplier)
            except ValueError:
                continue
    
    # Если нет суффикса, пробуем просто число
    try:
        return int(float(amount_str))
    except ValueError:
        return 0

def format_number(num: int) -> str:
    """Форматирует число с суффиксами для красивого отображения"""
    if num >= 10**33:
        return f"{num / 10**33:.2f}D".rstrip('0').rstrip('.') if num % (10**33) != 0 else f"{num // 10**33}D"
    if num >= 10**30:
        return f"{num / 10**30:.2f}N".rstrip('0').rstrip('.')
    if num >= 10**27:
        return f"{num / 10**27:.2f}O".rstrip('0').rstrip('.')
    if num >= 10**24:
        return f"{num / 10**24:.2f}Sp".rstrip('0').rstrip('.')
    if num >= 10**21:
        return f"{num / 10**21:.2f}Sx".rstrip('0').rstrip('.')
    if num >= 10**18:
        return f"{num / 10**18:.2f}Qi".rstrip('0').rstrip('.')
    if num >= 10**15:
        return f"{num / 10**15:.2f}Qa".rstrip('0').rstrip('.')
    if num >= 10**12:
        return f"{num / 10**12:.2f}T".rstrip('0').rstrip('.')
    if num >= 10**9:
        return f"{num / 10**9:.2f}B".rstrip('0').rstrip('.')
    if num >= 10**6:
        return f"{num / 10**6:.2f}M".rstrip('0').rstrip('.')
    if num >= 1000:
        return f"{num / 1000:.2f}K".rstrip('0').rstrip('.')
    return f"{num:,}".replace(",", " ")

# ========== НАСТРОЙКИ ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

db = Database()

BONUS_COOLDOWN = 3600

active_crash_games: Dict[str, Dict] = {}
active_dice_games: Dict[str, Dict] = {}
active_mines_games: Dict[str, Dict] = {}
active_russian_roulette_games: Dict[str, Dict] = {}
admin_sessions: Dict[str, bool] = {}

# ========== ЭМОДЗИ ==========
EMOJI = {
    "dart": "🎯", "coin": "💎", "bonus": "🎁", "win": "✅", "lose": "❌",
    "party": "🎉", "admin": "👑", "ban": "🔨", "unban": "🔓", "dice": "🎲",
    "join": "🤝", "cancel": "❌", "crash": "💥", "gem": "💎",
    "sword": "⚔️", "crown": "👑", "coinflip": "🪙", "race": "🏎️", "card": "🃏",
    "stats": "📊", "top": "🏆", "support": "🆘", "info": "ℹ️", "warning": "⚠️",
    "fire": "🔥", "star": "⭐", "shield": "🛡️", "target": "🎯", "magic": "✨",
    "referral": "🔗", "gift": "🎁", "cheque": "🧾", "promo": "🎫", "share": "📤",
    "copy": "📋", "clock": "⏰", "football": "⚽", "bomb": "💣", "mine": "💎",
    "skull": "💀", "gun": "🔫", "bullet": "💥", "rocket": "🚀"
}

# ========== ИГРЫ 50/50 ==========
GAMES_50 = {
    'монетка': {'emoji': '🪙', 'name': 'МОНЕТКА', 'desc': 'Орёл или Решка?', 'mult': 2.0, 
                'options': {'орёл': 'heads', 'решка': 'tails'}},
    'дуэль': {'emoji': '⚔️', 'name': 'ДУЭЛЬ', 'desc': 'Ты или противник?', 'mult': 2.0,
              'options': {'я': 'me', 'противник': 'enemy'}},
    'гонки': {'emoji': '🏎️', 'name': 'ГОНКИ', 'desc': 'Красный или Синий?', 'mult': 2.0,
              'options': {'красный': 'red', 'синий': 'blue'}},
    'карта': {'emoji': '🃏', 'name': 'КАРТА', 'desc': 'Чёрная или Красная?', 'mult': 2.0,
              'options': {'чёрная': 'black', 'красная': 'red'}},
    'кристалл': {'emoji': '💎', 'name': 'КРИСТАЛЛ', 'desc': 'Свет или Тьма?', 'mult': 2.0,
                 'options': {'свет': 'light', 'тьма': 'dark'}}
}

# ========== МНОЖИТЕЛИ ДЛЯ МИН (ИСПРАВЛЕНЫ ДЛЯ 1 МИНЫ - МЕНЬШЕ) ==========
MINES_MULTIPLIERS = {
    1: {1: 1.05, 2: 1.11, 3: 1.18, 4: 1.25, 5: 1.33, 6: 1.43, 7: 1.54, 8: 1.67, 9: 1.82, 10: 2.00, 
         11: 2.22, 12: 2.50, 13: 2.86, 14: 3.33, 15: 4.00, 16: 5.00, 17: 6.67, 18: 10.00, 19: 20.00, 
         20: 50.00, 21: 100.00, 22: 250.00, 23: 500.00, 24: 1000.00},
    2: {1: 1.18, 2: 1.43, 3: 1.82, 4: 2.50, 5: 3.33, 6: 5.00, 7: 7.14, 8: 12.50, 9: 25.00, 10: 50.00, 
         11: 100.00, 12: 250.00, 13: 500.00, 14: 1000.00, 15: 2500.00, 16: 5000.00, 17: 10000.00, 
         18: 25000.00, 19: 50000.00, 20: 100000.00},
    3: {1: 1.25, 2: 1.67, 3: 2.50, 4: 4.00, 5: 6.67, 6: 12.50, 7: 25.00, 8: 50.00, 9: 100.00, 10: 250.00, 
         11: 500.00, 12: 1000.00, 13: 2500.00, 14: 5000.00, 15: 10000.00, 16: 25000.00, 17: 50000.00, 
         18: 100000.00},
    4: {1: 1.33, 2: 2.00, 3: 3.33, 4: 6.67, 5: 12.50, 6: 33.33, 7: 66.67, 8: 166.67, 9: 500.00, 10: 1000.00, 
         11: 2500.00, 12: 5000.00, 13: 10000.00, 14: 25000.00, 15: 50000.00, 16: 100000.00},
    5: {1: 1.43, 2: 2.50, 3: 5.00, 4: 12.50, 5: 33.33, 6: 100.00, 7: 250.00, 8: 1000.00, 9: 2500.00, 
         10: 10000.00, 11: 25000.00, 12: 100000.00}
}

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def is_admin_session(user_id: int) -> bool:
    return admin_sessions.get(str(user_id), False)

def get_multiplier_emoji(mult: float) -> str:
    if mult >= 10:
        return "🔥"
    elif mult >= 5:
        return "⭐"
    elif mult >= 2:
        return "✨"
    return "💰"

# ========== ФУНКЦИЯ ДЛЯ РАСЧЕТА ВЕРОЯТНОСТИ КРАША ==========
def get_crash_probability(target_mult: float) -> float:
    """Чем выше икс, тем меньше шанс выигрыша (как в gmines)"""
    # Базовая формула: шанс ~ 1/(x^1.5) с ограничением
    if target_mult <= 1:
        return 1.0
    prob = 1.0 / (target_mult ** 1.5)
    # Ограничиваем шанс между 0.01% и 95%
    return max(0.0001, min(0.95, prob))

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard(user_id: int = None) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['coin']} Баланс", callback_data='balance'),
         InlineKeyboardButton(f"{EMOJI['bonus']} Бонус", callback_data='bonus')],
        [InlineKeyboardButton(f"{EMOJI['dart']} Дартс", callback_data='darts_info'),
         InlineKeyboardButton(f"{EMOJI['dice']} Кости", callback_data='dice_info'),
         InlineKeyboardButton(f"{EMOJI['mine']} Мины", callback_data='mines_info')],
        [InlineKeyboardButton(f"{EMOJI['football']} Футбол", callback_data='football_info'),
         InlineKeyboardButton(f"{EMOJI['gun']} Рулетка", callback_data='roulette_info'),
         InlineKeyboardButton(f"{EMOJI['rocket']} Краш", callback_data='crash_info')],
        [InlineKeyboardButton(f"{EMOJI['coinflip']} 50/50", callback_data='games50_info'),
         InlineKeyboardButton(f"{EMOJI['top']} Топ 15", callback_data='top15')],
        [InlineKeyboardButton(f"{EMOJI['cheque']} Чеки", callback_data='cheques_menu'),
         InlineKeyboardButton(f"{EMOJI['promo']} Промокод", callback_data='activate_promo_menu')],
        [InlineKeyboardButton(f"{EMOJI['stats']} Профиль", callback_data='profile'),
         InlineKeyboardButton(f"{EMOJI['info']} Помощь", callback_data='help_info')],
        [InlineKeyboardButton(f"{EMOJI['support']} Поддержка", url=f'https://t.me/{SUPPORT_USERNAME.replace("@", "")}'),
         InlineKeyboardButton(f"{EMOJI['fire']} Канал", url=f'https://t.me/{CHANNEL_USERNAME.replace("@", "")}')],
    ]
    if user_id and is_admin_session(user_id):
        keyboard.append([InlineKeyboardButton(f"{EMOJI['admin']} Админ панель", callback_data='admin_panel')])
    return InlineKeyboardMarkup(keyboard)

def get_cheques_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['cheque']} Создать чек", callback_data='create_cheque')],
        [InlineKeyboardButton(f"{EMOJI['gift']} Активировать чек", callback_data='activate_cheque')],
        [InlineKeyboardButton(f"{EMOJI['stats']} Мои чеки", callback_data='my_cheques')],
        [InlineKeyboardButton(f"{EMOJI['stats']} Статистика чеков", callback_data='cheque_stats')],
        [InlineKeyboardButton(f"{EMOJI['cancel']} Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['coin']} Выдать MS", callback_data='admin_give')],
        [InlineKeyboardButton(f"{EMOJI['coin']} Забрать MS", callback_data='admin_take')],
        [InlineKeyboardButton(f"{EMOJI['promo']} Создать промокод", callback_data='admin_create_promo')],
        [InlineKeyboardButton(f"{EMOJI['promo']} Список промокодов", callback_data='admin_list_promos')],
        [InlineKeyboardButton(f"{EMOJI['ban']} Забанить", callback_data='admin_ban')],
        [InlineKeyboardButton(f"{EMOJI['unban']} Разбанить", callback_data='admin_unban')],
        [InlineKeyboardButton(f"{EMOJI['stats']} Статистика", callback_data='admin_stats')],
        [InlineKeyboardButton(f"{EMOJI['shield']} Список банов", callback_data='admin_bans')],
        [InlineKeyboardButton(f"{EMOJI['cancel']} Назад", callback_data='back_to_main')],
        [InlineKeyboardButton(f"{EMOJI['admin']} Выйти из админки", callback_data='admin_logout')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_crash_keyboard(game_id: str, bet: int, target_mult: float) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['rocket']} Запустить ракету!", callback_data=f'crash_launch_{game_id}')],
        [InlineKeyboardButton(f"{EMOJI['coin']} Забрать {format_number(int(bet * target_mult))} (x{target_mult:.2f})", 
                              callback_data=f'crash_cashout_{game_id}')],
        [InlineKeyboardButton(f"{EMOJI['cancel']} Забрать ставку", callback_data=f'crash_cancel_{game_id}')],
        [InlineKeyboardButton(f"{EMOJI['cancel']} Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_mines_keyboard(game_id: str, mines_count: int, revealed: List[int], current_mult: float, bet: int) -> InlineKeyboardMarkup:
    keyboard = []
    for i in range(0, 25, 5):
        row = []
        for j in range(5):
            cell = i + j
            if cell in revealed:
                row.append(InlineKeyboardButton("💎", callback_data=f'mines_noop_{game_id}'))
            else:
                row.append(InlineKeyboardButton("⬛", callback_data=f'mines_reveal_{game_id}_{cell}'))
        keyboard.append(row)
    win_amount = int(bet * current_mult)
    keyboard.append([InlineKeyboardButton(f"💰 Забрать {format_number(win_amount)} (x{current_mult:.2f})", callback_data=f'mines_cashout_{game_id}')])
    keyboard.append([InlineKeyboardButton(f"{EMOJI['cancel']} Назад", callback_data='back_to_main')])
    return InlineKeyboardMarkup(keyboard)

def get_roulette_keyboard(game_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(f"{EMOJI['gun']} Выстрелить!", callback_data=f'roulette_shoot_{game_id}')],
        [InlineKeyboardButton(f"{EMOJI['cancel']} Забрать ставку", callback_data=f'roulette_cancel_{game_id}')],
        [InlineKeyboardButton(f"{EMOJI['cancel']} Назад", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(f"{EMOJI['cancel']} Назад", callback_data='back_to_main')]])

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(
            f"{EMOJI['ban']} <b>ВЫ ЗАБЛОКИРОВАНЫ!</b>\n\n"
            f"Вы не можете использовать этого бота.\n"
            f"По вопросам: {SUPPORT_USERNAME}",
            parse_mode='HTML'
        )
        return
    
    args = context.args
    if args and len(args) > 0:
        if args[0].startswith("ref_"):
            try:
                referrer_id = int(args[0].split("_")[1])
                if referrer_id != user.id:
                    db.add_referral(user.id, referrer_id)
            except (IndexError, ValueError):
                pass
        elif args[0].startswith("cheque_"):
            cheque_code = args[0].replace("cheque_", "")
            result = db.activate_cheque(user.id, cheque_code)
            if result["success"]:
                await update.message.reply_text(
                    f"{EMOJI['party']} <b>ЧЕК АКТИВИРОВАН!</b> {EMOJI['party']}\n\n"
                    f"{EMOJI['coin']} <b>+{format_number(result['amount'])} MS</b>",
                    parse_mode='HTML'
                )
            else:
                errors = {"not_found": "❌ Чек не найден!", "expired": "❌ Чек уже использован!", "already_used": "❌ Вы уже активировали этот чек!"}
                await update.message.reply_text(errors.get(result['reason'], "Ошибка активации!"), parse_mode='HTML')
    
    user_data = db.get_user(user.id)
    user_data['username'] = user.username or ''
    user_data['first_name'] = user.first_name or 'Игрок'
    db.save_data()
    
    balance = db.get_balance(user.id)
    ref_stats = db.get_referral_stats(user.id)
    
    welcome_text = (
        f"{EMOJI['star']} <b>ДОБРО ПОЖАЛОВАТЬ В {BOT_NAME}!</b> {EMOJI['star']}\n\n"
        f"👤 <b>Игрок:</b> {user.first_name}\n"
        f"{EMOJI['coin']} <b>Баланс:</b> {format_number(balance)} MS\n\n"
        f"🔗 <b>ТВОЯ РЕФЕРАЛЬНАЯ ССЫЛКА:</b>\n"
        f"<code>https://t.me/{context.bot.username}?start=ref_{user.id}</code>\n\n"
        f"📊 <b>РЕФЕРАЛЫ:</b>\n"
        f"┌ 👥 Всего: {ref_stats['total']}\n"
        f"└ 🎮 Активных: {ref_stats['active']}\n\n"
        f"🎁 <b>БОНУС ЗА ПРИГЛАШЕНИЕ:</b>\n"
        f"└ +1000 MS за каждого друга!\n\n"
        f"{EMOJI['fire']} <b>ДОСТУПНЫЕ ИГРЫ:</b>\n"
        f"┌ {EMOJI['dart']} <b>Дартс</b> — x2.05 / x3.1\n"
        f"├ {EMOJI['dice']} <b>Кости</b> — мультиплеер (2-8 игроков)\n"
        f"├ {EMOJI['dice']} <b>Кубик</b> — >3 / <3 (x2.1)\n"
        f"├ {EMOJI['mine']} <b>Мины</b> — x1.05 до x1,000\n"
        f"├ {EMOJI['football']} <b>Футбол</b> — гол/мимо (x2.1)\n"
        f"├ {EMOJI['gun']} <b>Русская рулетка</b> — x1.6\n"
        f"├ {EMOJI['rocket']} <b>Краш</b> — выбирай икс, чем выше, тем меньше шанс!\n"
        f"└ {EMOJI['coinflip']} <b>5 игр 50/50</b> — x2.0\n\n"
        f"{EMOJI['bonus']} <b>Бонус:</b> +2500 MS | Раз в час\n"
        f"{EMOJI['magic']} <b>Переводы:</b> <code>Дать [сумма] [@username]</code>\n"
        f"{EMOJI['cheque']} <b>Чеки:</b> Создавай чеки и делись с друзьями!\n"
        f"{EMOJI['promo']} <b>Промокоды:</b> Введи промокод в чат для активации!\n\n"
        f"<i>Используй кнопки ниже для навигации!</i>"
    )
    
    await update.message.reply_text(welcome_text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    help_text = (
        f"{EMOJI['info']} <b>ПОМОЩЬ ПО БОТУ {BOT_NAME}</b> {EMOJI['info']}\n"
        f"└ <b>Версия:</b> {BOT_VERSION}\n\n"
        f"{EMOJI['fire']} <b>КОМАНДЫ:</b>\n"
        f"┌ /start — Главное меню\n"
        f"├ /balance — Проверить баланс\n"
        f"├ /bonus — Получить бонус\n"
        f"├ /top — Топ 15 богатых\n"
        f"├ /profile — Полный профиль\n"
        f"├ /referrals — Мои рефералы\n"
        f"├ /referral_link — Моя реферальная ссылка\n"
        f"└ /help — Эта справка\n\n"
        f"{EMOJI['dart']} <b>ИГРЫ:</b>\n"
        f"┌ <code>дартс [сумма] [красное/белое/центр]</code>\n"
        f"├ <code>кубик [сумма] [больше/меньше]</code>\n"
        f"├ <code>кости [сумма] [игроки 2-8]</code>\n"
        f"├ <code>мины [сумма] [бомбы 1-5]</code>\n"
        f"├ <code>футбол [сумма] [гол/мимо]</code>\n"
        f"├ <code>рулетка [сумма]</code>\n"
        f"├ <code>краш [сумма] [икс]</code> — пример: <code>краш 1000 2</code>\n"
        f"└ <code>[монетка/дуэль/гонки/карта/кристалл] [сумма] [выбор]</code>\n\n"
        f"{EMOJI['cheque']} <b>ЧЕКИ:</b>\n"
        f"┌ <code>/createcheque [сумма] [активации]</code> — создать чек\n"
        f"└ <code>/usecheque [код]</code> — активировать чек\n\n"
        f"{EMOJI['promo']} <b>ПРОМОКОДЫ:</b>\n"
        f"└ Отправь код промокода в чат!\n\n"
        f"{EMOJI['magic']} <b>ПЕРЕВОДЫ:</b>\n"
        f"└ <code>Дать [сумма] [@username]</code>\n\n"
        f"{EMOJI['support']} <b>Поддержка:</b> {SUPPORT_USERNAME}"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user.id)
    )

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    balance = db.get_balance(user.id)
    await update.message.reply_text(
        f"{EMOJI['coin']} <b>Ваш баланс:</b> {format_number(balance)} MS",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user.id)
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    user_data = db.get_user(user.id)
    games_played = user_data.get('games_played', 0)
    games_won = user_data.get('games_won', 0)
    win_rate = (games_won / games_played * 100) if games_played > 0 else 0
    total_bet = user_data.get('total_bet', 0)
    total_win = user_data.get('total_win', 0)
    ref_stats = db.get_referral_stats(user.id)
    cheque_stats = db.get_cheque_stats(user.id)
    
    text = (
        f"{EMOJI['stats']} <b>ВАШ ПРОФИЛЬ</b> {EMOJI['stats']}\n\n"
        f"👤 <b>Имя:</b> {user.first_name}\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n\n"
        f"{EMOJI['coin']} <b>Баланс:</b> {format_number(db.get_balance(user.id))} MS\n\n"
        f"📊 <b>ИГРОВАЯ СТАТИСТИКА:</b>\n"
        f"┌ 🎮 Сыграно игр: {games_played}\n"
        f"├ 🏆 Побед: {games_won}\n"
        f"├ 📈 Винрейт: {win_rate:.1f}%\n"
        f"├ 💰 Всего поставлено: {format_number(total_bet)} MS\n"
        f"└ 🎁 Всего выиграно: {format_number(total_win)} MS\n\n"
        f"🔗 <b>РЕФЕРАЛЬНАЯ СТАТИСТИКА:</b>\n"
        f"┌ 👥 Приглашено: {ref_stats['total']}\n"
        f"└ 🎮 Активных: {ref_stats['active']}\n\n"
        f"{EMOJI['cheque']} <b>СТАТИСТИКА ЧЕКОВ:</b>\n"
        f"┌ 🧾 Активировано чеков: {cheque_stats['total_used']}\n"
        f"└ 💰 Получено по чекам: {format_number(cheque_stats['total_amount'])} MS\n\n"
        f"<i>Приглашай друзей и получай +1000 MS!</i>"
    )
    
    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user.id)
    )

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.get_top_users(15)
    
    if not users:
        await update.message.reply_text(f"{EMOJI['stats']} Нет игроков в топе!", parse_mode='HTML')
        return
    
    text = f"{EMOJI['top']} <b>ТОП 15 БОГАТЫХ ИГРОКОВ</b> {EMOJI['top']}\n\n"
    medals = ["🥇", "🥈", "🥉", "📌", "📌", "📌", "📌", "📌", "📌", "📌", "📌", "📌", "📌", "📌", "📌"]
    
    for i, (uid, data) in enumerate(users):
        name = data.get('first_name', f'Игрок{uid[:6]}')
        balance = data.get('balance', 0)
        medal = medals[i] if i < len(medals) else "📍"
        text += f"{medal} <b>{i+1}.</b> {name[:20]} — {EMOJI['coin']} {format_number(balance)} MS\n"
    
    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=get_main_keyboard(update.effective_user.id)
    )

async def bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    user_data = db.get_user(user.id)
    last_bonus = user_data.get('last_bonus', 0)
    current_time = datetime.now().timestamp()
    
    if current_time - last_bonus < BONUS_COOLDOWN:
        remaining = BONUS_COOLDOWN - (current_time - last_bonus)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        text = (
            f"{EMOJI['warning']} <b>Бонус уже получен!</b>\n\n"
            f"⏰ Следующий через: {minutes} мин {seconds} сек\n\n"
            f"{EMOJI['coin']} Бонус: +2500 MS"
        )
        await update.message.reply_text(text, parse_mode='HTML')
        return
    
    db.update_balance(user.id, 2500)
    user_data['last_bonus'] = current_time
    db.save_data()
    balance = db.get_balance(user.id)
    
    text = (
        f"{EMOJI['bonus']} <b>БОНУС ПОЛУЧЕН!</b> {EMOJI['bonus']}\n\n"
        f"{EMOJI['coin']} +2500 MS\n"
        f"💰 <b>Баланс:</b> {format_number(balance)} MS\n\n"
        f"⏰ Следующий бонус через 1 час"
    )
    
    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user.id)
    )

async def referral_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = context.bot.username
    link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    text = (
        f"🔗 <b>ТВОЯ РЕФЕРАЛЬНАЯ ССЫЛКА</b> 🔗\n\n"
        f"<code>{link}</code>\n\n"
        f"📢 <b>Поделись с друзьями!</b>\n"
        f"🎁 За каждого приглашенного ты получишь <b>+1000 MS</b>\n"
        f"👥 Другу тоже дается <b>5000 MS</b> на старт!\n\n"
        f"💎 <i>Чем больше друзей — тем выше ты в топе!</i>"
    )
    await update.message.reply_text(text, parse_mode='HTML')

async def referrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats = db.get_referral_stats(user.id)
    if stats['total'] == 0:
        await update.message.reply_text(
            f"{EMOJI['referral']} У тебя пока нет рефералов. Пригласи друзей по ссылке /referral_link и получи +1000 MS за каждого!",
            parse_mode='HTML'
        )
        return
    
    text = f"{EMOJI['referral']} <b>ТВОИ РЕФЕРАЛЫ</b> {EMOJI['referral']}\n\n"
    text += f"👥 <b>Всего:</b> {stats['total']}\n"
    text += f"🎮 <b>Активных:</b> {stats['active']}\n\n"
    text += f"💎 <b>Заработано:</b> {stats['total'] * 1000} MS\n\n"
    text += f"🔗 <i>Твоя ссылка: /referral_link</i>"
    await update.message.reply_text(text, parse_mode='HTML')

# ========== ПЕРЕВОДЫ ==========
async def give_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    # Получаем текст сообщения
    text = update.message.text.strip()
    # Удаляем слово "дать" из начала
    text = text[4:].strip() if text.lower().startswith('дать ') else ''
    
    if not text:
        await update.message.reply_text(
            f"{EMOJI['lose']} <b>Неверный формат!</b>\n\n"
            f"📝 Используй: <code>Дать [сумма] [@username]</code>\n\n"
            f"🎯 <b>Примеры:</b>\n"
            f"┌ <code>Дать 1000 @username</code>\n"
            f"├ <code>Дать 1к @username</code>\n"
            f"├ <code>Дать all @username</code> — весь баланс\n"
            f"└ <code>Дать 100м @username</code> — 100 миллионов",
            parse_mode='HTML'
        )
        return
    
    parts = text.split()
    if len(parts) < 2:
        await update.message.reply_text(
            f"{EMOJI['lose']} <b>Неверный формат!</b>\n\n"
            f"📝 Используй: <code>Дать [сумма] [@username]</code>",
            parse_mode='HTML'
        )
        return
    
    amount_str = parts[0]
    target_username = parts[1].replace("@", "")
    
    receiver = None
    for uid, data in db.get_all_users().items():
        if data.get("username") == target_username:
            receiver = int(uid)
            break
    
    if not receiver:
        await update.message.reply_text(f"{EMOJI['lose']} Пользователь @{target_username} не найден!", parse_mode='HTML')
        return
    
    if user.id == receiver:
        await update.message.reply_text(f"{EMOJI['lose']} Нельзя перевести самому себе!", parse_mode='HTML')
        return
    
    sender_balance = db.get_balance(user.id)
    amount = parse_amount(amount_str, sender_balance)
    
    if amount <= 0:
        await update.message.reply_text(f"{EMOJI['lose']} Сумма должна быть больше 0! (ты ввел: {amount_str})", parse_mode='HTML')
        return
    
    if amount > sender_balance:
        await update.message.reply_text(
            f"{EMOJI['lose']} <b>Недостаточно средств!</b>\n"
            f"💰 Ваш баланс: {format_number(sender_balance)} MS",
            parse_mode='HTML'
        )
        return
    
    db.update_balance(user.id, -amount)
    db.update_balance(receiver, amount)
    
    receiver_name = db.get_user(receiver).get('first_name', target_username)
    
    await update.message.reply_text(
        f"{EMOJI['magic']} <b>ПЕРЕВОД ВЫПОЛНЕН!</b> {EMOJI['magic']}\n\n"
        f"👤 <b>От:</b> {user.first_name}\n"
        f"👤 <b>Кому:</b> {receiver_name}\n"
        f"{EMOJI['coin']} <b>Сумма:</b> {format_number(amount)} MS\n\n"
        f"💰 <b>Ваш баланс:</b> {format_number(db.get_balance(user.id))} MS",
        parse_mode='HTML'
    )

# ========== ИГРА ДАРТС ==========
async def darts_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    parts = update.message.text.split()
    
    if len(parts) < 3:
        await update.message.reply_text(
            f"{EMOJI['dart']} <b>ИГРА ДАРТС</b> {EMOJI['dart']}\n\n"
            f"📝 <b>Формат:</b> <code>дартс [сумма] [красное/белое/центр]</code>\n\n"
            f"🎯 <b>Примеры:</b>\n"
            f"┌ <code>дартс 100 красное</code>\n"
            f"├ <code>дартс 1к белое</code>\n"
            f"└ <code>дартс all центр</code>\n\n"
            f"💰 <b>Множители:</b>\n"
            f"┌ 🔴 Красное: <b>x2.05</b>\n"
            f"├ ⚪ Белое: <b>x2.05</b>\n"
            f"└ 🟡 Центр: <b>x3.1</b>",
            parse_mode='HTML'
        )
        return
    
    try:
        amount_str = parts[1]
        bet_color = parts[2].lower()
    except (IndexError, ValueError):
        await update.message.reply_text(f"{EMOJI['lose']} Неверный формат!", parse_mode='HTML')
        return
    
    balance = db.get_balance(user.id)
    bet_amount = parse_amount(amount_str, balance)
    
    color_map = {'красное': 'red', 'белое': 'white', 'центр': 'center'}
    if bet_color not in color_map:
        await update.message.reply_text(
            f"{EMOJI['lose']} Доступные цвета: красное, белое, центр",
            parse_mode='HTML'
        )
        return
    
    if bet_amount <= 0:
        await update.message.reply_text(f"{EMOJI['lose']} Ставка должна быть больше 0! (ты ввел: {amount_str})", parse_mode='HTML')
        return
    
    if bet_amount > balance:
        await update.message.reply_text(
            f"{EMOJI['lose']} Недостаточно средств!\n💰 Баланс: {format_number(balance)} MS",
            parse_mode='HTML'
        )
        return
    
    db.update_balance(user.id, -bet_amount)
    db.update_stats(user.id, bet_amount)
    
    msg = await update.message.reply_text(f"{EMOJI['dart']} <b>БРОСОК...</b>", parse_mode='HTML')
    await asyncio.sleep(0.8)
    
    colors = ['red', 'white', 'center']
    weights = [0.4, 0.4, 0.2]
    result_color = random.choices(colors, weights=weights)[0]
    
    for _ in range(3):
        await msg.edit_text(f"{EMOJI['dart']}➡️ <b>БРОСОК...</b>", parse_mode='HTML')
        await asyncio.sleep(0.2)
        await msg.edit_text(f"➡️{EMOJI['dart']} <b>БРОСОК...</b>", parse_mode='HTML')
        await asyncio.sleep(0.2)
    
    if result_color == 'red':
        result_text = f"{EMOJI['dart']}🔴 <b>ПОПАДАНИЕ В КРАСНОЕ!</b>"
        multiplier = 2.05
    elif result_color == 'white':
        result_text = f"{EMOJI['dart']}⚪ <b>ПОПАДАНИЕ В БЕЛОЕ!</b>"
        multiplier = 2.05
    else:
        result_text = f"{EMOJI['dart']}🟡 <b>ПОПАДАНИЕ В ЦЕНТР!</b>"
        multiplier = 3.1
    
    await msg.edit_text(result_text, parse_mode='HTML')
    await asyncio.sleep(1)
    
    if color_map[bet_color] == result_color:
        win_amount = int(bet_amount * multiplier)
        db.update_balance(user.id, win_amount)
        db.update_stats(user.id, bet_amount, win_amount, True)
        new_balance = db.get_balance(user.id)
        
        await update.message.reply_text(
            f"{EMOJI['win']} <b>ПОБЕДА!</b> {get_multiplier_emoji(multiplier)}\n\n"
            f"🎯 Множитель: <b>x{multiplier}</b>\n"
            f"{EMOJI['coin']} +{format_number(win_amount)} MS\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    else:
        new_balance = db.get_balance(user.id)
        await update.message.reply_text(
            f"{EMOJI['lose']} <b>ПРОИГРЫШ!</b>\n\n"
            f"{EMOJI['coin']} -{format_number(bet_amount)} MS\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )

# ========== ИГРА КУБИК ==========
async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    parts = update.message.text.split()
    
    if len(parts) < 3:
        await update.message.reply_text(
            f"{EMOJI['dice']} <b>ИГРА КУБИК</b> {EMOJI['dice']}\n\n"
            f"📝 <b>Формат:</b> <code>кубик [сумма] [больше/меньше]</code>\n\n"
            f"🎯 <b>Примеры:</b>\n"
            f"┌ <code>кубик 100 больше</code>\n"
            f"├ <code>кубик 1к меньше</code>\n"
            f"└ <code>кубик all больше</code>\n\n"
            f"📊 <b>Правила:</b>\n"
            f"┌ Выпадает число от 1 до 6\n"
            f"├ >3 — победа при выборе \"больше\"\n"
            f"├ <3 — победа при выборе \"меньше\"\n"
            f"└ 3 — возврат ставки\n\n"
            f"💰 <b>Выигрыш:</b> x2.1",
            parse_mode='HTML'
        )
        return
    
    try:
        amount_str = parts[1]
        choice = parts[2].lower()
    except (IndexError, ValueError):
        await update.message.reply_text(f"{EMOJI['lose']} Неверный формат!", parse_mode='HTML')
        return
    
    balance = db.get_balance(user.id)
    bet_amount = parse_amount(amount_str, balance)
    
    if bet_amount <= 0:
        await update.message.reply_text(f"{EMOJI['lose']} Ставка должна быть больше 0! (ты ввел: {amount_str})", parse_mode='HTML')
        return
    
    if choice not in ['больше', 'меньше']:
        await update.message.reply_text(f"{EMOJI['lose']} Выберите: больше или меньше!", parse_mode='HTML')
        return
    
    if bet_amount > balance:
        await update.message.reply_text(
            f"{EMOJI['lose']} Недостаточно средств!\n💰 Баланс: {format_number(balance)} MS",
            parse_mode='HTML'
        )
        return
    
    db.update_balance(user.id, -bet_amount)
    db.update_stats(user.id, bet_amount)
    
    msg = await update.message.reply_dice(emoji="🎲")
    await asyncio.sleep(2)
    
    roll = msg.dice.value
    
    if roll > 3:
        result = "больше"
    elif roll < 3:
        result = "меньше"
    else:
        result = "ровно"
    
    if result == choice:
        win_amount = int(bet_amount * 2.1)
        db.update_balance(user.id, win_amount)
        db.update_stats(user.id, bet_amount, win_amount, True)
        new_balance = db.get_balance(user.id)
        
        await update.message.reply_text(
            f"{EMOJI['win']} <b>ПОБЕДА!</b> {EMOJI['fire']}\n\n"
            f"🎲 <b>Выпало:</b> {roll}\n"
            f"📊 <b>Ваш выбор:</b> {choice.upper()}\n"
            f"{EMOJI['coin']} <b>+{format_number(win_amount)} MS</b> (x2.1)\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    elif result == "ровно":
        db.update_balance(user.id, bet_amount)
        new_balance = db.get_balance(user.id)
        
        await update.message.reply_text(
            f"⚖️ <b>НИЧЬЯ!</b>\n\n"
            f"🎲 <b>Выпало:</b> {roll}\n"
            f"{EMOJI['coin']} <b>Ставка возвращена:</b> {format_number(bet_amount)} MS\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    else:
        new_balance = db.get_balance(user.id)
        
        await update.message.reply_text(
            f"{EMOJI['lose']} <b>ПРОИГРЫШ!</b>\n\n"
            f"🎲 <b>Выпало:</b> {roll}\n"
            f"📊 <b>Ваш выбор:</b> {choice.upper()}\n"
            f"{EMOJI['coin']} <b>-{format_number(bet_amount)} MS</b>\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )

# ========== ИГРЫ 50/50 ==========
async def game50_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    game = GAMES_50.get(game_type)
    if not game:
        return
    
    parts = update.message.text.split()
    
    if len(parts) < 3:
        options = list(game['options'].keys())
        options_text = "/".join(options)
        await update.message.reply_text(
            f"{game['emoji']} <b>{game['name']}</b> {game['emoji']}\n\n"
            f"📝 <b>Формат:</b> <code>{game_type} [сумма] [{options_text}]</code>\n\n"
            f"🎯 <b>Пример:</b> <code>{game_type} 100 {options[0]}</code>\n\n"
            f"💰 <b>Выигрыш:</b> x{game['mult']}",
            parse_mode='HTML'
        )
        return
    
    try:
        amount_str = parts[1]
        choice = parts[2].lower()
    except (IndexError, ValueError):
        await update.message.reply_text(f"{EMOJI['lose']} Неверный формат!", parse_mode='HTML')
        return
    
    balance = db.get_balance(user.id)
    bet_amount = parse_amount(amount_str, balance)
    
    if choice not in game['options']:
        valid = "/".join(game['options'].keys())
        await update.message.reply_text(f"{EMOJI['lose']} Доступные варианты: {valid}", parse_mode='HTML')
        return
    
    if bet_amount <= 0:
        await update.message.reply_text(f"{EMOJI['lose']} Ставка должна быть больше 0! (ты ввел: {amount_str})", parse_mode='HTML')
        return
    
    if bet_amount > balance:
        await update.message.reply_text(
            f"{EMOJI['lose']} Недостаточно средств!\n💰 Баланс: {format_number(balance)} MS",
            parse_mode='HTML'
        )
        return
    
    db.update_balance(user.id, -bet_amount)
    db.update_stats(user.id, bet_amount)
    
    msg = await update.message.reply_text(f"{game['emoji']} {game['desc']} 🔄", parse_mode='HTML')
    await asyncio.sleep(1.5)
    
    result = random.choice(list(game['options'].values()))
    result_ru = None
    for ru, en in game['options'].items():
        if en == result:
            result_ru = ru
            break
    
    if game['options'][choice] == result:
        win_amount = int(bet_amount * game['mult'])
        db.update_balance(user.id, win_amount)
        db.update_stats(user.id, bet_amount, win_amount, True)
        new_balance = db.get_balance(user.id)
        
        await msg.edit_text(
            f"{EMOJI['win']} <b>ПОБЕДА В {game['name']}!</b> {EMOJI['party']}\n\n"
            f"🎲 <b>Ваш выбор:</b> {choice.upper()}\n"
            f"🎲 <b>Результат:</b> {result_ru.upper()}\n"
            f"{EMOJI['coin']} <b>+{format_number(win_amount)} MS</b> (x{game['mult']})\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    else:
        new_balance = db.get_balance(user.id)
        
        await msg.edit_text(
            f"{EMOJI['lose']} <b>ПРОИГРЫШ В {game['name']}!</b>\n\n"
            f"🎲 <b>Ваш выбор:</b> {choice.upper()}\n"
            f"🎲 <b>Результат:</b> {result_ru.upper()}\n"
            f"{EMOJI['coin']} <b>-{format_number(bet_amount)} MS</b>\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )

# ========== ИГРА КРАШ (КАК В GMINES) ==========
async def crash_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    parts = update.message.text.split()
    
    if len(parts) < 3:
        await update.message.reply_text(
            f"{EMOJI['rocket']} <b>ИГРА КРАШ</b> {EMOJI['rocket']}\n\n"
            f"📝 <b>Формат:</b> <code>краш [сумма] [икс]</code>\n\n"
            f"🎯 <b>Примеры:</b>\n"
            f"┌ <code>краш 1000 2</code> — шанс ~35%\n"
            f"├ <code>краш 1к 5</code> — шанс ~9%\n"
            f"├ <code>краш all 10</code> — шанс ~3%\n"
            f"└ <code>краш 500 100</code> — шанс ~0.1%\n\n"
            f"📊 <b>Правила:</b>\n"
            f"┌ Ты выбираешь желаемый множитель (икс)\n"
            f"├ Чем выше икс — тем меньше шанс на победу\n"
            f"├ Если ракета долетит до твоего икса — ты выигрываешь\n"
            f"├ Если ракета взорвётся раньше — ты проигрываешь\n"
            f"└ Можешь забрать выигрыш ДО запуска ракеты!\n\n"
            f"<i>Формула: шанс ~ 1/(x^1.5)</i>",
            parse_mode='HTML'
        )
        return
    
    try:
        amount_str = parts[1]
        target_mult = float(parts[2])
    except (IndexError, ValueError):
        await update.message.reply_text(f"{EMOJI['lose']} Неверный формат! Пример: <code>краш 1000 2</code>", parse_mode='HTML')
        return
    
    balance = db.get_balance(user.id)
    bet_amount = parse_amount(amount_str, balance)
    
    if target_mult < 1.01:
        await update.message.reply_text(f"{EMOJI['lose']} Икс должен быть больше 1.01!", parse_mode='HTML')
        return
    
    if target_mult > 1000:
        await update.message.reply_text(f"{EMOJI['lose']} Максимальный икс: 1000!", parse_mode='HTML')
        return
    
    if bet_amount <= 0:
        await update.message.reply_text(f"{EMOJI['lose']} Ставка должна быть больше 0! (ты ввел: {amount_str})", parse_mode='HTML')
        return
    
    if bet_amount > balance:
        await update.message.reply_text(
            f"{EMOJI['lose']} Недостаточно средств!\n💰 Баланс: {format_number(balance)} MS",
            parse_mode='HTML'
        )
        return
    
    # Проверяем, не слишком ли низкий шанс (минимальный 0.01%)
    prob = get_crash_probability(target_mult)
    if prob < 0.0001:
        await update.message.reply_text(f"{EMOJI['lose']} Шанс слишком низкий (меньше 0.01%). Выбери икс поменьше!", parse_mode='HTML')
        return
    
    db.update_balance(user.id, -bet_amount)
    db.update_stats(user.id, bet_amount)
    
    game_id = str(datetime.now().timestamp())
    
    active_crash_games[game_id] = {
        'user_id': str(user.id),
        'bet_amount': bet_amount,
        'target_mult': target_mult,
        'status': 'active'
    }
    
    win_amount = int(bet_amount * target_mult)
    prob_percent = prob * 100
    
    text = (
        f"{EMOJI['rocket']} <b>ИГРА КРАШ</b> {EMOJI['rocket']}\n\n"
        f"💰 <b>Ставка:</b> {format_number(bet_amount)} MS\n"
        f"🎯 <b>Целевой икс:</b> x{target_mult:.2f}\n"
        f"📈 <b>Шанс на победу:</b> {prob_percent:.4f}%\n"
        f"💎 <b>Потенциальный выигрыш:</b> {format_number(win_amount)} MS\n\n"
        f"{EMOJI['warning']} Чем выше икс, тем меньше шанс!\n"
        f"<i>Нажми на ракету, чтобы запустить!</i>"
    )
    
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=get_crash_keyboard(game_id, bet_amount, target_mult))

async def crash_launch(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    query = update.callback_query
    user = query.from_user
    
    game = active_crash_games.get(game_id)
    if not game:
        await query.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    if game['user_id'] != str(user.id):
        await query.answer("❌ Это не твоя кнопка!", show_alert=True)
        return
    
    if game['status'] != 'active':
        await query.answer("❌ Игра уже завершена!", show_alert=True)
        return
    
    await query.edit_message_text(f"{EMOJI['rocket']} 🚀 <b>ЗАПУСК РАКЕТЫ!</b>\n\nРакета взлетает...", parse_mode='HTML')
    await asyncio.sleep(1)
    
    # Генерируем случайный икс, на котором взорвётся ракета
    # Используем распределение: чем выше икс, тем меньше шанс
    # Краш-точка: случайное число от 1.01 до 1000 с экспоненциальным распределением
    crash_point = 1.01
    while crash_point <= 1.01:
        # Экспоненциальное распределение для реалистичных крашей
        crash_point = 1.01 + random.expovariate(1.5) * 2
        if crash_point > 1000:
            crash_point = 1000
    
    target_mult = game['target_mult']
    
    # Анимация подъёма множителя
    steps = [1.1, 1.2, 1.3, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0, 50.0, 70.0, 100.0, 150.0, 200.0, 300.0, 500.0, 700.0, 900.0, 1000.0]
    last_text = ""
    for step in steps:
        if step > crash_point:
            break
        if step > target_mult + 0.1 and target_mult < crash_point:
            # Игрок выиграл, прерываем анимацию
            break
        if step <= target_mult:
            text = f"{EMOJI['rocket']} 🚀 <b>КРАШ-ТОЧКА:</b> x{step:.2f}...\n<i>Ракета летит выше!</i>"
            if text != last_text:
                await query.edit_message_text(text, parse_mode='HTML')
                last_text = text
                await asyncio.sleep(0.3)
    
    if target_mult <= crash_point:
        # ПОБЕДА!
        win_amount = int(game['bet_amount'] * target_mult)
        db.update_balance(user.id, win_amount)
        db.update_stats(user.id, game['bet_amount'], win_amount, True)
        new_balance = db.get_balance(user.id)
        
        del active_crash_games[game_id]
        
        await query.edit_message_text(
            f"{EMOJI['party']} <b>РАКЕТА ДОЛЕТЕЛА!</b> {EMOJI['party']}\n\n"
            f"🎯 <b>Твой икс:</b> x{target_mult:.2f}\n"
            f"💥 <b>Ракета взорвалась на:</b> x{crash_point:.2f}\n"
            f"{EMOJI['coin']} <b>Выигрыш:</b> +{format_number(win_amount)} MS\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    else:
        # ПРОИГРЫШ
        del active_crash_games[game_id]
        
        await query.edit_message_text(
            f"{EMOJI['crash']} <b>ВЗРЫВ РАКЕТЫ!</b> {EMOJI['crash']}\n\n"
            f"🎯 <b>Твой икс:</b> x{target_mult:.2f}\n"
            f"💥 <b>Ракета взорвалась на:</b> x{crash_point:.2f}\n"
            f"{EMOJI['coin']} <b>Ставка потеряна:</b> {format_number(game['bet_amount'])} MS\n\n"
            f"💔 <b>Ты проиграл!</b>\n"
            f"<i>Попробуй взять икс поменьше в следующий раз!</i>",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )

async def crash_cashout(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    query = update.callback_query
    user = query.from_user
    
    game = active_crash_games.get(game_id)
    if not game:
        await query.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    if game['user_id'] != str(user.id):
        await query.answer("❌ Это не твоя кнопка!", show_alert=True)
        return
    
    if game['status'] != 'active':
        await query.answer("❌ Игра уже завершена!", show_alert=True)
        return
    
    db.update_balance(user.id, game['bet_amount'])
    new_balance = db.get_balance(user.id)
    
    del active_crash_games[game_id]
    
    await query.edit_message_text(
        f"{EMOJI['cancel']} <b>ТЫ ЗАБРАЛ СТАВКУ</b>\n\n"
        f"{EMOJI['coin']} <b>Возвращено:</b> {format_number(game['bet_amount'])} MS\n\n"
        f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user.id)
    )

async def crash_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    await crash_cashout(update, context, game_id)  # То же самое

# ========== ИГРА МИНЫ ==========
async def mines_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    parts = update.message.text.split()
    
    if len(parts) < 3:
        await update.message.reply_text(
            f"{EMOJI['mine']} <b>ИГРА МИНЫ</b> {EMOJI['mine']}\n\n"
            f"📝 <b>Формат:</b> <code>мины [сумма] [бомбы 1-5]</code>\n\n"
            f"🎯 <b>Примеры:</b>\n"
            f"┌ <code>мины 1000 3</code>\n"
            f"├ <code>мины 1к 5</code>\n"
            f"└ <code>мины all 1</code>\n\n"
            f"📊 <b>Правила (как в gmines):</b>\n"
            f"┌ Поле 5x5 (25 клеток)\n"
            f"├ Выбери количество бомб (1-5)\n"
            f"├ Открывай клетки с алмазами 💎\n"
            f"├ Попади на бомбу 💣 — проигрыш\n"
            f"├ Множитель растёт с каждой открытой клеткой\n"
            f"└ Можешь забрать выигрыш в любой момент\n\n"
            f"💰 <b>Множители для 1 бомбы:</b> x1.05 → x1000\n"
            f"<i>Точные множители как в оригинале</i>",
            parse_mode='HTML'
        )
        return
    
    try:
        amount_str = parts[1]
        mines_count = int(parts[2])
    except (IndexError, ValueError):
        await update.message.reply_text(f"{EMOJI['lose']} Неверный формат! Пример: <code>мины 1000 3</code>", parse_mode='HTML')
        return
    
    balance = db.get_balance(user.id)
    bet_amount = parse_amount(amount_str, balance)
    
    if mines_count < 1 or mines_count > 5:
        await update.message.reply_text(f"{EMOJI['lose']} Количество бомб: от 1 до 5!", parse_mode='HTML')
        return
    
    if bet_amount <= 0:
        await update.message.reply_text(f"{EMOJI['lose']} Ставка должна быть больше 0! (ты ввел: {amount_str})", parse_mode='HTML')
        return
    
    if bet_amount > balance:
        await update.message.reply_text(
            f"{EMOJI['lose']} Недостаточно средств!\n💰 Баланс: {format_number(balance)} MS",
            parse_mode='HTML'
        )
        return
    
    db.update_balance(user.id, -bet_amount)
    db.update_stats(user.id, bet_amount)
    
    game_id = str(datetime.now().timestamp())
    
    all_cells = list(range(25))
    bomb_positions = random.sample(all_cells, mines_count)
    
    active_mines_games[game_id] = {
        'user_id': str(user.id),
        'bet_amount': bet_amount,
        'mines_count': mines_count,
        'bomb_positions': bomb_positions,
        'revealed': [],
        'current_mult': 1.0,
        'cells_opened': 0,
        'status': 'active'
    }
    
    text = (
        f"{EMOJI['mine']} <b>ИГРА МИНЫ</b> {EMOJI['mine']}\n\n"
        f"💰 <b>Ставка:</b> {format_number(bet_amount)} MS\n"
        f"💣 <b>Бомб на поле:</b> {mines_count}\n"
        f"💎 <b>Алмазов:</b> {25 - mines_count}\n"
        f"📈 <b>Текущий множитель:</b> x1.00\n"
        f"💎 <b>Текущий выигрыш:</b> {format_number(bet_amount)} MS\n\n"
        f"<i>Открывай клетки с алмазами 💎, избегай бомб 💣!</i>"
    )
    
    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=get_mines_keyboard(game_id, mines_count, [], 1.0, bet_amount)
    )

async def mines_reveal(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str, cell: int):
    query = update.callback_query
    user = query.from_user
    
    game = active_mines_games.get(game_id)
    if not game:
        await query.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    if game['user_id'] != str(user.id):
        await query.answer("❌ Это не твоя кнопка!", show_alert=True)
        return
    
    if game['status'] != 'active':
        await query.answer("❌ Игра уже завершена!", show_alert=True)
        return
    
    if cell in game['revealed']:
        await query.answer("❌ Эта клетка уже открыта!", show_alert=True)
        return
    
    if cell in game['bomb_positions']:
        game['status'] = 'finished'
        del active_mines_games[game_id]
        
        await query.edit_message_text(
            f"{EMOJI['crash']} <b>ВЗРЫВ БОМБЫ!</b> {EMOJI['crash']}\n\n"
            f"{EMOJI['mine']} Вы попали на бомбу 💣!\n"
            f"{EMOJI['coin']} Ставка потеряна: {format_number(game['bet_amount'])} MS\n\n"
            f"💔 <b>Вы проиграли!</b>\n"
            f"<i>Попробуйте снова!</i>",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
        return
    
    game['revealed'].append(cell)
    game['cells_opened'] += 1
    
    mines_count = game['mines_count']
    opened = game['cells_opened']
    
    if mines_count in MINES_MULTIPLIERS and opened in MINES_MULTIPLIERS[mines_count]:
        game['current_mult'] = MINES_MULTIPLIERS[mines_count][opened]
    else:
        safe_cells = 25 - mines_count
        prob = 1.0
        for i in range(opened):
            prob *= (safe_cells - i) / (25 - i)
        game['current_mult'] = 1.0 / prob if prob > 0 else 1000000
    
    current_win = int(game['bet_amount'] * game['current_mult'])
    
    if len(game['revealed']) == (25 - mines_count):
        win_amount = current_win
        db.update_balance(game['user_id'], win_amount)
        db.update_stats(game['user_id'], game['bet_amount'], win_amount, True)
        new_balance = db.get_balance(game['user_id'])
        
        del active_mines_games[game_id]
        
        await query.edit_message_text(
            f"{EMOJI['party']} <b>ПОЛНАЯ ПОБЕДА!</b> {EMOJI['party']}\n\n"
            f"{EMOJI['mine']} Вы нашли все алмазы 💎!\n"
            f"📊 <b>Открыто клеток:</b> {game['cells_opened']}\n"
            f"💰 <b>Множитель:</b> x{game['current_mult']:.2f}\n"
            f"{EMOJI['coin']} <b>Выигрыш:</b> +{format_number(win_amount)} MS\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
        return
    
    text = (
        f"{EMOJI['win']} <b>АЛМАЗ НАЙДЕН!</b> {EMOJI['gem']}\n\n"
        f"{EMOJI['mine']} <b>Ставка:</b> {format_number(game['bet_amount'])} MS\n"
        f"💣 <b>Бомб на поле:</b> {game['mines_count']}\n"
        f"💎 <b>Открыто алмазов:</b> {game['cells_opened']}/{25 - game['mines_count']}\n"
        f"📈 <b>Текущий множитель:</b> x{game['current_mult']:.2f}\n"
        f"💎 <b>Текущий выигрыш:</b> {format_number(current_win)} MS\n\n"
        f"<i>Продолжай открывать или забери выигрыш!</i>"
    )
    
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=get_mines_keyboard(game_id, game['mines_count'], game['revealed'], game['current_mult'], game['bet_amount'])
    )

async def mines_cashout(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    query = update.callback_query
    user = query.from_user
    
    game = active_mines_games.get(game_id)
    if not game:
        await query.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    if game['user_id'] != str(user.id):
        await query.answer("❌ Это не твоя кнопка!", show_alert=True)
        return
    
    if game['status'] != 'active':
        await query.answer("❌ Игра уже завершена!", show_alert=True)
        return
    
    win_amount = int(game['bet_amount'] * game['current_mult'])
    db.update_balance(game['user_id'], win_amount)
    if game['cells_opened'] > 0:
        db.update_stats(game['user_id'], game['bet_amount'], win_amount, True)
    new_balance = db.get_balance(game['user_id'])
    
    del active_mines_games[game_id]
    
    await query.edit_message_text(
        f"{EMOJI['win']} <b>ВЫ ЗАБРАЛИ ВЫИГРЫШ!</b> {EMOJI['coin']}\n\n"
        f"{EMOJI['mine']} <b>Открыто алмазов:</b> {game['cells_opened']}\n"
        f"📈 <b>Множитель:</b> x{game['current_mult']:.2f}\n"
        f"{EMOJI['coin']} <b>Выигрыш:</b> +{format_number(win_amount)} MS\n\n"
        f"💰 <b>Баланс:</b> {format_number(new_balance)} MS\n\n"
        f"🎉 <b>Поздравляем!</b>",
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user.id)
    )

async def mines_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("❌ Эта клетка уже открыта!", show_alert=True)

# ========== ИГРА ФУТБОЛ ==========
async def football_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    parts = update.message.text.split()
    
    if len(parts) < 3:
        await update.message.reply_text(
            f"{EMOJI['football']} <b>ИГРА ФУТБОЛ</b> {EMOJI['football']}\n\n"
            f"📝 <b>Формат:</b> <code>футбол [сумма] [гол/мимо]</code>\n\n"
            f"🎯 <b>Примеры:</b>\n"
            f"┌ <code>футбол 100 гол</code>\n"
            f"├ <code>футбол 1к мимо</code>\n"
            f"└ <code>футбол all гол</code>\n\n"
            f"💰 <b>Выигрыш:</b> x2.1 при голе\n"
            f"⚽ <i>Бот отправляет эмодзи мяча, смотри на результат!</i>",
            parse_mode='HTML'
        )
        return
    
    try:
        amount_str = parts[1]
        choice = parts[2].lower()
    except (IndexError, ValueError):
        await update.message.reply_text(f"{EMOJI['lose']} Неверный формат! Пример: <code>футбол 100 гол</code>", parse_mode='HTML')
        return
    
    balance = db.get_balance(user.id)
    bet_amount = parse_amount(amount_str, balance)
    
    if choice not in ['гол', 'мимо']:
        await update.message.reply_text(f"{EMOJI['lose']} Выберите: гол или мимо!", parse_mode='HTML')
        return
    
    if bet_amount <= 0:
        await update.message.reply_text(f"{EMOJI['lose']} Ставка должна быть больше 0! (ты ввел: {amount_str})", parse_mode='HTML')
        return
    
    if bet_amount > balance:
        await update.message.reply_text(
            f"{EMOJI['lose']} Недостаточно средств!\n💰 Баланс: {format_number(balance)} MS",
            parse_mode='HTML'
        )
        return
    
    db.update_balance(user.id, -bet_amount)
    db.update_stats(user.id, bet_amount)
    
    msg = await update.message.reply_dice(emoji="⚽")
    await asyncio.sleep(2)
    
    roll = msg.dice.value
    
    if roll >= 4:
        result = "гол"
    else:
        result = "мимо"
    
    if choice == result:
        win_amount = int(bet_amount * 2.1)
        db.update_balance(user.id, win_amount)
        db.update_stats(user.id, bet_amount, win_amount, True)
        new_balance = db.get_balance(user.id)
        
        await update.message.reply_text(
            f"{EMOJI['win']} <b>ГОООЛ!</b> {EMOJI['football']}\n\n"
            f"⚽ <b>Результат:</b> {result.upper()}!\n"
            f"🎯 <b>Ваш выбор:</b> {choice.upper()}\n"
            f"{EMOJI['coin']} <b>+{format_number(win_amount)} MS</b> (x2.1)\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    else:
        new_balance = db.get_balance(user.id)
        
        await update.message.reply_text(
            f"{EMOJI['lose']} <b>МИМО!</b> {EMOJI['football']}\n\n"
            f"⚽ <b>Результат:</b> {result.upper()}!\n"
            f"🎯 <b>Ваш выбор:</b> {choice.upper()}\n"
            f"{EMOJI['coin']} <b>-{format_number(bet_amount)} MS</b>\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )

# ========== РУССКАЯ РУЛЕТКА ==========
async def russian_roulette_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    parts = update.message.text.split()
    
    if len(parts) < 2:
        await update.message.reply_text(
            f"{EMOJI['gun']} <b>РУССКАЯ РУЛЕТКА</b> {EMOJI['gun']}\n\n"
            f"📝 <b>Формат:</b> <code>рулетка [сумма]</code>\n\n"
            f"🎯 <b>Пример:</b> <code>рулетка 1000</code>\n\n"
            f"📊 <b>Правила:</b>\n"
            f"┌ В барабане 6 патронов, 1 боевой\n"
            f"├ Крутишь барабан и стреляешь\n"
            f"├ Попал — проигрыш ставки\n"
            f"├ Промах — выигрыш x1.6\n"
            f"└ Можно забрать выигрыш в любой момент\n\n"
            f"💰 <b>Выигрыш:</b> x1.6",
            parse_mode='HTML'
        )
        return
    
    try:
        amount_str = parts[1]
    except (IndexError, ValueError):
        await update.message.reply_text(f"{EMOJI['lose']} Неверный формат!", parse_mode='HTML')
        return
    
    balance = db.get_balance(user.id)
    bet_amount = parse_amount(amount_str, balance)
    
    if bet_amount <= 0:
        await update.message.reply_text(f"{EMOJI['lose']} Ставка должна быть больше 0! (ты ввел: {amount_str})", parse_mode='HTML')
        return
    
    if bet_amount > balance:
        await update.message.reply_text(
            f"{EMOJI['lose']} Недостаточно средств!\n💰 Баланс: {format_number(balance)} MS",
            parse_mode='HTML'
        )
        return
    
    db.update_balance(user.id, -bet_amount)
    db.update_stats(user.id, bet_amount)
    
    game_id = str(datetime.now().timestamp())
    
    active_russian_roulette_games[game_id] = {
        'user_id': str(user.id),
        'bet_amount': bet_amount,
        'status': 'active',
        'shot_fired': False,
        'current_mult': 1.0
    }
    
    text = (
        f"{EMOJI['gun']} <b>РУССКАЯ РУЛЕТКА</b> {EMOJI['gun']}\n\n"
        f"💰 <b>Ставка:</b> {format_number(bet_amount)} MS\n"
        f"📈 <b>Множитель:</b> x1.0\n"
        f"💎 <b>Выигрыш при победе:</b> {format_number(int(bet_amount * 1.6))} MS (x1.6)\n\n"
        f"{EMOJI['warning']} <b>Правила:</b>\n"
        f"┌ В барабане 6 патронов, 1 боевой\n"
        f"├ Нажми на курок и проверь удачу!\n"
        f"├ Промах — победа!\n"
        f"└ Попал — проигрыш!\n\n"
        f"<i>Нажми на курок или забери ставку!</i>"
    )
    
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=get_roulette_keyboard(game_id))

async def roulette_shoot(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    query = update.callback_query
    user = query.from_user
    
    game = active_russian_roulette_games.get(game_id)
    if not game:
        await query.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    if game['user_id'] != str(user.id):
        await query.answer("❌ Это не твоя кнопка!", show_alert=True)
        return
    
    if game['status'] != 'active':
        await query.answer("❌ Игра уже завершена!", show_alert=True)
        return
    
    if game.get('shot_fired'):
        await query.answer("❌ Ты уже выстрелил!", show_alert=True)
        return
    
    await query.edit_message_text(f"{EMOJI['gun']} 🔫 <b>Кручу барабан...</b>", parse_mode='HTML')
    await asyncio.sleep(0.8)
    await query.edit_message_text(f"{EMOJI['gun']} 🔫 <b>Прицеливаюсь...</b>", parse_mode='HTML')
    await asyncio.sleep(0.8)
    await query.edit_message_text(f"{EMOJI['gun']} 💥 <b>ЩЕЛЧОК...</b>", parse_mode='HTML')
    await asyncio.sleep(0.8)
    
    is_dead = random.randint(1, 6) == 1
    
    if is_dead:
        game['status'] = 'finished'
        del active_russian_roulette_games[game_id]
        
        await query.edit_message_text(
            f"{EMOJI['crash']} <b>ВЫ УБИТЫ!</b> {EMOJI['skull']}\n\n"
            f"{EMOJI['gun']} Боевой патрон попал в вас!\n"
            f"{EMOJI['coin']} Ставка потеряна: {format_number(game['bet_amount'])} MS\n\n"
            f"💔 <b>Вы проиграли!</b>\n"
            f"<i>Попробуйте снова!</i>",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
        return
    
    game['shot_fired'] = True
    game['current_mult'] = 1.6
    win_amount = int(game['bet_amount'] * 1.6)
    
    text = (
        f"{EMOJI['win']} <b>ВЫ ВЫЖИЛИ!</b> {EMOJI['party']}\n\n"
        f"{EMOJI['gun']} Патрон был холостым!\n\n"
        f"💰 <b>Ставка:</b> {format_number(game['bet_amount'])} MS\n"
        f"📈 <b>Множитель:</b> x1.6\n"
        f"{EMOJI['coin']} <b>Выигрыш:</b> +{format_number(win_amount)} MS\n\n"
        f"<i>Нажми \"Забрать\", чтобы получить выигрыш!</i>"
    )
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_roulette_keyboard(game_id))

async def roulette_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    query = update.callback_query
    user = query.from_user
    
    game = active_russian_roulette_games.get(game_id)
    if not game:
        await query.answer("❌ Игра не найдена!", show_alert=True)
        return
    
    if game['user_id'] != str(user.id):
        await query.answer("❌ Это не твоя кнопка!", show_alert=True)
        return
    
    if game['status'] != 'active':
        await query.answer("❌ Игра уже завершена!", show_alert=True)
        return
    
    if game.get('shot_fired'):
        win_amount = int(game['bet_amount'] * 1.6)
        db.update_balance(game['user_id'], win_amount)
        db.update_stats(game['user_id'], game['bet_amount'], win_amount, True)
        new_balance = db.get_balance(game['user_id'])
        
        del active_russian_roulette_games[game_id]
        
        await query.edit_message_text(
            f"{EMOJI['win']} <b>ВЫ ЗАБРАЛИ ВЫИГРЫШ!</b> {EMOJI['coin']}\n\n"
            f"{EMOJI['gun']} <b>Ставка:</b> {format_number(game['bet_amount'])} MS\n"
            f"📈 <b>Множитель:</b> x1.6\n"
            f"{EMOJI['coin']} <b>Выигрыш:</b> +{format_number(win_amount)} MS\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    else:
        db.update_balance(game['user_id'], game['bet_amount'])
        new_balance = db.get_balance(game['user_id'])
        del active_russian_roulette_games[game_id]
        
        await query.edit_message_text(
            f"{EMOJI['cancel']} <b>ВЫ ЗАБРАЛИ СТАВКУ</b>\n\n"
            f"{EMOJI['coin']} <b>Возвращено:</b> {format_number(game['bet_amount'])} MS\n\n"
            f"💰 <b>Баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )

# ========== ИГРА КОСТИ (МУЛЬТИПЛЕЕР) ==========
async def create_dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    parts = update.message.text.split()
    
    if len(parts) < 3:
        await update.message.reply_text(
            f"{EMOJI['dice']} <b>КОСТИ (МУЛЬТИПЛЕЕР)</b> {EMOJI['dice']}\n\n"
            f"📝 <b>Формат:</b> <code>кости [сумма] [игроки 2-8]</code>\n\n"
            f"🎯 <b>Примеры:</b>\n"
            f"┌ <code>кости 100 4</code>\n"
            f"├ <code>кости 1к 6</code>\n"
            f"└ <code>кости all 2</code>\n\n"
            f"📊 <b>Правила:</b>\n"
            f"┌ Все игроки делают одинаковую ставку\n"
            f"├ Победитель забирает 95% банка\n"
            f"└ При ничьей — переброс\n\n"
            f"💰 <b>Комиссия:</b> 5%",
            parse_mode='HTML'
        )
        return
    
    try:
        amount_str = parts[1]
        max_players = int(parts[2])
    except (IndexError, ValueError):
        await update.message.reply_text(f"{EMOJI['lose']} Неверный формат!", parse_mode='HTML')
        return
    
    balance = db.get_balance(user.id)
    bet_amount = parse_amount(amount_str, balance)
    
    if bet_amount <= 0:
        await update.message.reply_text(f"{EMOJI['lose']} Ставка должна быть больше 0! (ты ввел: {amount_str})", parse_mode='HTML')
        return
    
    if max_players < 2 or max_players > 8:
        await update.message.reply_text(f"{EMOJI['lose']} Количество игроков: 2-8!", parse_mode='HTML')
        return
    
    if bet_amount > balance:
        await update.message.reply_text(
            f"{EMOJI['lose']} Недостаточно средств!\n💰 Баланс: {format_number(balance)} MS",
            parse_mode='HTML'
        )
        return
    
    db.update_balance(user.id, -bet_amount)
    
    game_id = str(datetime.now().timestamp())
    active_dice_games[game_id] = {
        'creator_id': str(user.id),
        'creator_name': user.first_name,
        'bet_amount': bet_amount,
        'max_players': max_players,
        'players': [{'id': str(user.id), 'name': user.first_name, 'bet': bet_amount}],
        'status': 'waiting',
        'created_at': datetime.now()
    }
    
    await show_dice_game(update, game_id, is_new=True)

async def show_dice_game(update, game_id: str, is_new: bool = False, callback_query=None):
    game = active_dice_games.get(game_id)
    if not game:
        return
    
    current_players = len(game['players'])
    max_players = game['max_players']
    bet_amount = game['bet_amount']
    total_pool = bet_amount * current_players
    winner_takes = int(total_pool * 0.95)
    
    text = (
        f"{EMOJI['dice']} <b>ИГРА В КОСТИ</b> {EMOJI['dice']}\n\n"
        f"💰 <b>Ставка:</b> {format_number(bet_amount)} MS\n"
        f"👥 <b>Игроки:</b> {current_players}/{max_players}\n"
        f"🏆 <b>Банк:</b> {format_number(total_pool)} MS\n"
        f"🎯 <b>Выигрыш:</b> {format_number(winner_takes)} MS\n\n"
        f"<b>👤 Участники:</b>\n"
    )
    
    for i, player in enumerate(game['players'], 1):
        text += f"{i}. {player['name']} — {EMOJI['coin']} {format_number(player['bet'])} MS\n"
    
    text += f"\n⏳ <i>Ожидание игроков...</i>"
    
    user = update.effective_user if not callback_query else callback_query.from_user
    
    if game['creator_id'] == str(user.id) and current_players >= 2:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{EMOJI['dice']} Начать игру!", callback_data=f'dice_start_{game_id}'),
             InlineKeyboardButton(f"{EMOJI['cancel']} Отменить игру", callback_data=f'dice_cancel_game_{game_id}')],
            [InlineKeyboardButton(f"{EMOJI['cancel']} Назад", callback_data='back_to_main')]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{EMOJI['join']} Участвовать ({current_players}/{max_players})", callback_data=f'dice_join_{game_id}'),
             InlineKeyboardButton(f"{EMOJI['cancel']} Отменить ставку", callback_data=f'dice_cancel_{game_id}')],
            [InlineKeyboardButton(f"{EMOJI['cancel']} Назад", callback_data='back_to_main')]
        ])
    
    if is_new and hasattr(update, 'message') and update.message:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=keyboard)
    elif callback_query:
        await callback_query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)

async def dice_join(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    query = update.callback_query
    user = query.from_user
    
    if db.is_banned(user.id):
        await query.answer("❌ Вы заблокированы!", show_alert=True)
        return
    
    game = active_dice_games.get(game_id)
    if not game or game['status'] != 'waiting':
        await query.answer("❌ Игра недоступна!", show_alert=True)
        return
    
    for player in game['players']:
        if player['id'] == str(user.id):
            await query.answer("❌ Вы уже участвуете!", show_alert=True)
            return
    
    if len(game['players']) >= game['max_players']:
        await query.answer("❌ Игра заполнена!", show_alert=True)
        return
    
    balance = db.get_balance(user.id)
    if balance < game['bet_amount']:
        await query.answer(f"❌ Нужно {format_number(game['bet_amount'])} MS!", show_alert=True)
        return
    
    db.update_balance(user.id, -game['bet_amount'])
    game['players'].append({'id': str(user.id), 'name': user.first_name, 'bet': game['bet_amount']})
    
    await query.answer("✅ Вы присоединились!")
    await show_dice_game(update, game_id, callback_query=query)

async def dice_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    query = update.callback_query
    user = query.from_user
    
    game = active_dice_games.get(game_id)
    if not game or game['status'] != 'waiting':
        await query.answer("❌ Отменить нельзя!", show_alert=True)
        return
    
    player_index = None
    for i, player in enumerate(game['players']):
        if player['id'] == str(user.id):
            player_index = i
            break
    
    if player_index is None:
        await query.answer("❌ Вы не участвуете!", show_alert=True)
        return
    
    db.update_balance(user.id, game['players'][player_index]['bet'])
    game['players'].pop(player_index)
    
    if len(game['players']) == 0:
        del active_dice_games[game_id]
        await query.edit_message_text(f"{EMOJI['cancel']} Игра отменена", parse_mode='HTML')
        return
    
    if game['creator_id'] == str(user.id) and len(game['players']) > 0:
        game['creator_id'] = game['players'][0]['id']
        game['creator_name'] = game['players'][0]['name']
    
    await query.answer("✅ Вы вышли! Ставка возвращена.")
    await show_dice_game(update, game_id, callback_query=query)

async def dice_cancel_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    query = update.callback_query
    user = query.from_user
    
    game = active_dice_games.get(game_id)
    if not game or game['creator_id'] != str(user.id):
        await query.answer("❌ Нельзя!", show_alert=True)
        return
    
    for player in game['players']:
        db.update_balance(player['id'], player['bet'])
    
    del active_dice_games[game_id]
    await query.edit_message_text(f"{EMOJI['cancel']} Игра отменена. Ставки возвращены.", parse_mode='HTML')

async def dice_start(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str):
    query = update.callback_query
    user = query.from_user
    
    game = active_dice_games.get(game_id)
    if not game or game['creator_id'] != str(user.id) or len(game['players']) < 2:
        await query.answer("❌ Нельзя начать!", show_alert=True)
        return
    
    game['status'] = 'playing'
    await query.edit_message_text(f"{EMOJI['dice']} <b>ИГРА НАЧАЛАСЬ!</b>\n\nБросаем кости...", parse_mode='HTML')
    await asyncio.sleep(1)
    
    results = []
    for player in game['players']:
        roll = random.randint(1, 6)
        results.append({'player': player, 'roll': roll})
    
    results.sort(key=lambda x: x['roll'], reverse=True)
    
    winner = results[0]
    ties = [r for r in results if r['roll'] == winner['roll']]
    
    if len(ties) > 1:
        new_results = []
        for t in ties:
            new_roll = random.randint(1, 6)
            new_results.append({'player': t['player'], 'roll': new_roll})
        new_results.sort(key=lambda x: x['roll'], reverse=True)
        winner = new_results[0]
    
    total_pool = game['bet_amount'] * len(game['players'])
    win_amount = int(total_pool * 0.95)
    db.update_balance(winner['player']['id'], win_amount)
    db.update_stats(winner['player']['id'], game['bet_amount'], win_amount, True)
    
    results_text = "🎲 <b>РЕЗУЛЬТАТЫ БРОСКОВ:</b>\n\n"
    for r in results:
        medal = "🏆" if r['player']['id'] == winner['player']['id'] else "📌"
        results_text += f"{medal} {r['player']['name']}: <b>{r['roll']}</b>\n"
    
    results_text += f"\n{EMOJI['party']} <b>ПОБЕДИТЕЛЬ:</b> {winner['player']['name']}\n"
    results_text += f"{EMOJI['coin']} <b>Выигрыш:</b> {format_number(win_amount)} MS"
    
    del active_dice_games[game_id]
    
    await query.edit_message_text(
        results_text,
        parse_mode='HTML',
        reply_markup=get_main_keyboard(user.id)
    )

# ========== СИСТЕМА ЧЕКОВ ==========
async def create_cheque_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            f"{EMOJI['cheque']} <b>СОЗДАНИЕ ЧЕКА</b> {EMOJI['cheque']}\n\n"
            f"📝 <b>Формат:</b> <code>/createcheque [сумма] [активации]</code>\n\n"
            f"🎯 <b>Пример:</b> <code>/createcheque 1000 5</code>",
            parse_mode='HTML'
        )
        return
    
    try:
        amount_str = context.args[0]
        activations = int(context.args[1])
    except (IndexError, ValueError):
        await update.message.reply_text(f"{EMOJI['lose']} Сумма и активации должны быть числами!", parse_mode='HTML')
        return
    
    balance = db.get_balance(user.id)
    amount = parse_amount(amount_str, balance)
    
    if amount <= 0 or activations <= 0:
        await update.message.reply_text(f"{EMOJI['lose']} Сумма и активации должны быть больше 0!", parse_mode='HTML')
        return
    
    if activations > 100:
        await update.message.reply_text(f"{EMOJI['lose']} Максимум активаций: 100!", parse_mode='HTML')
        return
    
    cheque_code = db.create_cheque(user.id, amount, activations)
    
    if not cheque_code:
        await update.message.reply_text(
            f"{EMOJI['lose']} <b>Недостаточно средств!</b>\n"
            f"💰 Нужно: {format_number(amount * activations)} MS",
            parse_mode='HTML'
        )
        return
    
    cheque_link = f"https://t.me/{context.bot.username}?start=cheque_{cheque_code}"
    
    text = (
        f"{EMOJI['party']} <b>ЧЕК УСПЕШНО СОЗДАН!</b> {EMOJI['party']}\n\n"
        f"{EMOJI['cheque']} <b>Сумма:</b> {format_number(amount)} MS\n"
        f"{EMOJI['join']} <b>Активаций:</b> {activations}\n"
        f"{EMOJI['coin']} <b>Списано:</b> {format_number(amount * activations)} MS\n\n"
        f"🔗 <b>ССЫЛКА ДЛЯ АКТИВАЦИИ:</b>\n"
        f"<code>{cheque_link}</code>\n\n"
        f"{EMOJI['share']} <b>ПОДЕЛИТЬСЯ ЧЕКОМ:</b>"
    )
    
    share_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{EMOJI['share']} Поделиться чеком", url=f"https://t.me/share/url?url={cheque_link}&text=🎁 Получи {format_number(amount)} MS по моему чеку!")]
    ])
    
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=share_keyboard)

async def use_cheque_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            f"{EMOJI['cheque']} <b>АКТИВАЦИЯ ЧЕКА</b> {EMOJI['cheque']}\n\n"
            f"📝 <b>Формат:</b> <code>/usecheque [код]</code>\n\n"
            f"🎯 <b>Пример:</b> <code>/usecheque abc123xyz</code>",
            parse_mode='HTML'
        )
        return
    
    code = context.args[0]
    result = db.activate_cheque(user.id, code)
    
    if result["success"]:
        new_balance = db.get_balance(user.id)
        await update.message.reply_text(
            f"{EMOJI['party']} <b>ЧЕК АКТИВИРОВАН!</b> {EMOJI['party']}\n\n"
            f"{EMOJI['coin']} <b>+{format_number(result['amount'])} MS</b>\n\n"
            f"💰 <b>Ваш баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    else:
        errors = {
            "not_found": "❌ Чек не найден! Проверьте код.",
            "expired": "❌ Чек уже использован! Все активации исчерпаны.",
            "already_used": "❌ Вы уже активировали этот чек!"
        }
        await update.message.reply_text(
            f"{EMOJI['lose']} {errors.get(result['reason'], 'Ошибка активации!')}",
            parse_mode='HTML'
        )

async def my_cheques_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    
    cheques = db.get_my_cheques(user.id)
    
    if not cheques:
        await query.edit_message_text(
            f"{EMOJI['cheque']} <b>У ВАС НЕТ ЧЕКОВ</b>\n\n"
            f"Создайте чек через кнопку \"Создать чек\" или командой /createcheque",
            parse_mode='HTML',
            reply_markup=get_cheques_keyboard()
        )
        return
    
    text = f"{EMOJI['cheque']} <b>ВАШИ ЧЕКИ</b> {EMOJI['cheque']}\n\n"
    for ch in cheques:
        status = f"✅ {ch['used']}/{ch['max']} активаций"
        text += f"┌ 🧾 <code>{ch['code']}</code>\n"
        text += f"├ 💰 {format_number(ch['amount'])} MS\n"
        text += f"└ {status}\n\n"
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_cheques_keyboard())

async def cheque_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    
    stats = db.get_cheque_stats(user.id)
    
    text = (
        f"{EMOJI['stats']} <b>СТАТИСТИКА ЧЕКОВ</b> {EMOJI['stats']}\n\n"
        f"{EMOJI['gift']} <b>Активировано чеков:</b> {stats['total_used']}\n"
        f"{EMOJI['coin']} <b>Получено MS:</b> {format_number(stats['total_amount'])} MS\n"
    )
    
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_cheques_keyboard())

# ========== СИСТЕМА ПРОМОКОДОВ ==========
async def activate_promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    code = update.message.text.strip().upper()
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    result = db.activate_promocode(user.id, code)
    
    if result["success"]:
        new_balance = db.get_balance(user.id)
        await update.message.reply_text(
            f"{EMOJI['party']} <b>ПРОМОКОД АКТИВИРОВАН!</b> {EMOJI['party']}\n\n"
            f"{EMOJI['coin']} <b>+{format_number(result['amount'])} MS</b>\n\n"
            f"💰 <b>Ваш баланс:</b> {format_number(new_balance)} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    else:
        errors = {
            "not_found": "❌ Промокод не найден!",
            "expired": "❌ Промокод уже использован! Все активации исчерпаны.",
            "already_used": "❌ Вы уже активировали этот промокод!"
        }
        await update.message.reply_text(
            f"{EMOJI['lose']} {errors.get(result['reason'], 'Ошибка активации!')}",
            parse_mode='HTML'
        )

# ========== АДМИН-ФУНКЦИИ ==========
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(f"👑 Введи пароль: /admin {ADMIN_PASSWORD}")
        return
    if context.args[0] == ADMIN_PASSWORD:
        admin_sessions[str(user.id)] = True
        await update.message.reply_text(
            f"{EMOJI['admin']} <b>АДМИН ПАНЕЛЬ</b> {EMOJI['admin']}\n\n"
            f"Доступные команды:\n"
            f"┌ /give [@username] [сумма] — выдать MS\n"
            f"├ /take [@username] [сумма] — забрать MS\n"
            f"├ /createpromo [название] [активации] [сумма] — создать промокод\n"
            f"├ /delpromo [название] — удалить промокод\n"
            f"├ /listpromo — список промокодов\n"
            f"├ /ban [@username] — забанить\n"
            f"├ /unban [@username] — разбанить\n"
            f"├ /admin_stats — статистика бота\n"
            f"├ /bans_list — список банов\n"
            f"├ /admin_logout — выход из админки\n"
            f"└ /broadcast [сообщение] — рассылка",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text("❌ Неверный пароль!")

async def admin_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if str(user.id) in admin_sessions:
        del admin_sessions[str(user.id)]
        await update.message.reply_text("👋 Вы вышли из админ-панели.")
    else:
        await update.message.reply_text("❌ Вы не в админ-панели.")

def admin_required(func):
    async def wrapper(update, context):
        user = update.effective_user
        if not is_admin_session(user.id):
            await update.message.reply_text("❌ Нет доступа. Войди через /admin")
            return
        await func(update, context)
    return wrapper

@admin_required
async def admin_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("📝 /give @username 1000")
        return
    target = context.args[0].replace("@", "")
    try:
        amount = parse_amount(context.args[1], 10**18)
    except:
        await update.message.reply_text("❌ Сумма числом!")
        return
    
    for uid, data in db.get_all_users().items():
        if data.get("username") == target or uid == target:
            db.update_balance(int(uid), amount)
            await update.message.reply_text(f"✅ Выдано {format_number(amount)} MS пользователю {data.get('first_name')}")
            return
    await update.message.reply_text("❌ Пользователь не найден")

@admin_required
async def admin_take(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("📝 /take @username 1000")
        return
    target = context.args[0].replace("@", "")
    try:
        amount = parse_amount(context.args[1], 10**18)
    except:
        await update.message.reply_text("❌ Сумма числом!")
        return
    
    for uid, data in db.get_all_users().items():
        if data.get("username") == target or uid == target:
            db.update_balance(int(uid), -amount)
            await update.message.reply_text(f"✅ Забрано {format_number(amount)} MS у {data.get('first_name')}")
            return
    await update.message.reply_text("❌ Пользователь не найден")

@admin_required
async def admin_create_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("📝 /createpromo [название] [активации] [сумма]\nПример: /createpromo SUPER2024 100 500")
        return
    
    code = context.args[0].upper()
    try:
        max_activations = int(context.args[1])
        amount = parse_amount(context.args[2], 10**18)
    except ValueError:
        await update.message.reply_text("❌ Активации и сумма должны быть числами!")
        return
    
    if db.create_promocode(code, max_activations, amount):
        await update.message.reply_text(
            f"{EMOJI['promo']} <b>ПРОМОКОД СОЗДАН!</b>\n\n"
            f"📝 <b>Код:</b> <code>{code}</code>\n"
            f"👥 <b>Активаций:</b> {max_activations}\n"
            f"{EMOJI['coin']} <b>Сумма:</b> {format_number(amount)} MS",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(f"❌ Промокод {code} уже существует!")

@admin_required
async def admin_del_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("📝 /delpromo [название]")
        return
    
    code = context.args[0].upper()
    if db.delete_promocode(code):
        await update.message.reply_text(f"✅ Промокод {code} удален!")
    else:
        await update.message.reply_text(f"❌ Промокод {code} не найден!")

@admin_required
async def admin_list_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    promos = db.get_all_promocodes()
    
    if not promos:
        await update.message.reply_text("📭 Нет активных промокодов")
        return
    
    text = f"{EMOJI['promo']} <b>СПИСОК ПРОМОКОДОВ</b>\n\n"
    for code, data in promos.items():
        text += f"┌ <code>{code}</code>\n"
        text += f"├ 💰 {format_number(data['amount'])} MS\n"
        text += f"├ 👥 {data['used_count']}/{data['max_activations']}\n"
        text += f"└ {'✅ Активен' if data['used_count'] < data['max_activations'] else '❌ Исчерпан'}\n\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

@admin_required
async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📝 /ban @username")
        return
    target = context.args[0].replace("@", "")
    for uid, data in db.get_all_users().items():
        if data.get("username") == target or uid == target:
            db.ban_user(int(uid))
            await update.message.reply_text(f"🔨 Забанен {data.get('first_name')}")
            return
    await update.message.reply_text("❌ Не найден")

@admin_required
async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📝 /unban @username")
        return
    target = context.args[0].replace("@", "")
    for uid, data in db.get_all_users().items():
        if data.get("username") == target or uid == target:
            db.unban_user(int(uid))
            await update.message.reply_text(f"🔓 Разбанен {data.get('first_name')}")
            return
    await update.message.reply_text("❌ Не найден")

@admin_required
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users = db.get_registered_count()
    banned = len(db.data["banned"])
    total_coins = sum(u.get('balance', 0) for u in db.data["users"].values())
    total_games = sum(u.get('games_played', 0) for u in db.data["users"].values())
    total_refs = sum(len(u.get('referrals', [])) for u in db.data["users"].values())
    total_cheques_used = len(db.data.get("used_cheques", []))
    total_promos = len(db.data.get("promocodes", {}))
    
    text = (
        f"📊 <b>СТАТИСТИКА БОТА</b>\n\n"
        f"👥 Игроков: {total_users}\n"
        f"🔨 В бане: {banned}\n"
        f"💎 Всего MS: {format_number(total_coins)}\n"
        f"🎮 Игр сыграно: {total_games}\n"
        f"🔗 Всего рефералов: {total_refs}\n"
        f"🧾 Активировано чеков: {total_cheques_used}\n"
        f"🎫 Создано промокодов: {total_promos}\n"
        f"🔥 Версия: {BOT_VERSION}"
    )
    await update.message.reply_text(text, parse_mode='HTML')

@admin_required
async def bans_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.data["banned"]:
        await update.message.reply_text("🚫 Нет забаненных")
        return
    text = "🚫 <b>ЗАБАНЕННЫЕ</b>\n\n"
    for uid in db.data["banned"]:
        data = db.get_user_info(uid)
        name = data.get('first_name', uid) if data else uid
        text += f"• {name}\n"
    await update.message.reply_text(text, parse_mode='HTML')

@admin_required
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📢 /broadcast [текст]")
        return
    msg = " ".join(context.args)
    sent = 0
    for uid in db.get_all_users().keys():
        try:
            await context.bot.send_message(int(uid), f"📢 <b>РАССЫЛКА</b>\n\n{msg}", parse_mode='HTML')
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await update.message.reply_text(f"✅ Отправлено {sent} пользователям")

# ========== ОБРАБОТЧИК КНОПОК ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    if db.is_banned(user.id):
        await query.edit_message_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    data = query.data
    
    # ===== ОСНОВНЫЕ КНОПКИ =====
    if data == 'balance':
        await query.edit_message_text(
            f"{EMOJI['coin']} <b>Ваш баланс:</b> {format_number(db.get_balance(user.id))} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    
    elif data == 'bonus':
        user_data = db.get_user(user.id)
        last_bonus = user_data.get('last_bonus', 0)
        current_time = datetime.now().timestamp()
        
        if current_time - last_bonus < BONUS_COOLDOWN:
            remaining = BONUS_COOLDOWN - (current_time - last_bonus)
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            text = f"{EMOJI['warning']} <b>Бонус уже получен!</b>\n\n⏰ Следующий через: {minutes} мин {seconds} сек\n\n{EMOJI['coin']} Бонус: +2500 MS"
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
            return
        
        db.update_balance(user.id, 2500)
        user_data['last_bonus'] = current_time
        db.save_data()
        balance = db.get_balance(user.id)
        
        text = f"{EMOJI['bonus']} <b>БОНУС ПОЛУЧЕН!</b> {EMOJI['bonus']}\n\n{EMOJI['coin']} <b>+2500 MS</b>\n💰 <b>Баланс:</b> {format_number(balance)} MS\n\n⏰ Следующий бонус через 1 час"
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
    
    elif data == 'profile':
        user_data = db.get_user(user.id)
        games_played = user_data.get('games_played', 0)
        games_won = user_data.get('games_won', 0)
        win_rate = (games_won / games_played * 100) if games_played > 0 else 0
        total_bet = user_data.get('total_bet', 0)
        total_win = user_data.get('total_win', 0)
        ref_stats = db.get_referral_stats(user.id)
        cheque_stats = db.get_cheque_stats(user.id)
        
        text = (
            f"{EMOJI['stats']} <b>ВАШ ПРОФИЛЬ</b> {EMOJI['stats']}\n\n"
            f"👤 <b>Имя:</b> {user.first_name}\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n\n"
            f"{EMOJI['coin']} <b>Баланс:</b> {format_number(db.get_balance(user.id))} MS\n\n"
            f"📊 <b>ИГРОВАЯ СТАТИСТИКА:</b>\n"
            f"┌ 🎮 Сыграно игр: {games_played}\n"
            f"├ 🏆 Побед: {games_won}\n"
            f"├ 📈 Винрейт: {win_rate:.1f}%\n"
            f"├ 💰 Всего поставлено: {format_number(total_bet)} MS\n"
            f"└ 🎁 Всего выиграно: {format_number(total_win)} MS\n\n"
            f"🔗 <b>РЕФЕРАЛЬНАЯ СТАТИСТИКА:</b>\n"
            f"┌ 👥 Приглашено: {ref_stats['total']}\n"
            f"└ 🎮 Активных: {ref_stats['active']}\n\n"
            f"{EMOJI['cheque']} <b>СТАТИСТИКА ЧЕКОВ:</b>\n"
            f"┌ 🧾 Активировано чеков: {cheque_stats['total_used']}\n"
            f"└ 💰 Получено по чекам: {format_number(cheque_stats['total_amount'])} MS\n\n"
            f"<i>Приглашай друзей и получай +1000 MS!</i>"
        )
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
    
    elif data == 'help_info':
        help_text = (
            f"{EMOJI['info']} <b>ПОМОЩЬ ПО БОТУ</b> {EMOJI['info']}\n\n"
            f"<b>📝 КОМАНДЫ:</b>\n"
            f"┌ /start — Главное меню\n"
            f"├ /balance — Баланс\n"
            f"├ /bonus — Бонус\n"
            f"├ /top — Топ 15\n"
            f"├ /profile — Профиль\n"
            f"├ /referrals — Рефералы\n"
            f"├ /referral_link — Реф. ссылка\n"
            f"└ /help — Справка\n\n"
            f"<b>🎲 ИГРЫ:</b>\n"
            f"┌ <code>дартс 100 красное</code>\n"
            f"├ <code>кубик 100 больше</code>\n"
            f"├ <code>кости 100 4</code>\n"
            f"├ <code>мины 1000 3</code>\n"
            f"├ <code>футбол 100 гол</code>\n"
            f"├ <code>рулетка 1000</code>\n"
            f"├ <code>краш 1000 2</code>\n"
            f"└ <code>монетка 100 орёл</code>\n\n"
            f"{EMOJI['cheque']} <b>ЧЕКИ:</b>\n"
            f"┌ <code>/createcheque 1000 5</code> — создать чек\n"
            f"└ <code>/usecheque КОД</code> — активировать чек\n\n"
            f"{EMOJI['promo']} <b>ПРОМОКОДЫ:</b>\n"
            f"└ Отправь код в чат для активации!\n\n"
            f"{EMOJI['support']} <b>Поддержка:</b> {SUPPORT_USERNAME}"
        )
        await query.edit_message_text(help_text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
    
    elif data == 'darts_info':
        text = (
            f"{EMOJI['dart']} <b>ИГРА ДАРТС</b> {EMOJI['dart']}\n\n"
            f"📝 <b>Формат:</b> <code>дартс [сумма] [цвет]</code>\n\n"
            f"<b>🎯 Цвета и множители:</b>\n"
            f"┌ 🔴 <b>Красное</b> — x2.05\n"
            f"├ ⚪ <b>Белое</b> — x2.05\n"
            f"└ 🟡 <b>Центр</b> — x3.1\n\n"
            f"<b>📊 Вероятности:</b>\n"
            f"┌ Красное: 40%\n"
            f"├ Белое: 40%\n"
            f"└ Центр: 20%\n\n"
            f"<i>Пример: <code>дартс 500 центр</code></i>"
        )
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
    
    elif data == 'dice_info':
        text = (
            f"{EMOJI['dice']} <b>КОСТИ (МУЛЬТИПЛЕЕР)</b> {EMOJI['dice']}\n\n"
            f"📝 <b>Формат:</b> <code>кости [сумма] [игроки 2-8]</code>\n\n"
            f"<b>📊 Правила:</b>\n"
            f"┌ Все игроки делают одинаковую ставку\n"
            f"├ Победитель определяется по наибольшему числу\n"
            f"├ При ничьей — переброс между победителями\n"
            f"└ Победитель забирает 95% банка\n\n"
            f"💰 <b>Комиссия:</b> 5%\n"
            f"<i>Пример: <code>кости 1000 4</code></i>"
        )
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
    
    elif data == 'mines_info':
        text = (
            f"{EMOJI['mine']} <b>МИНЫ</b> {EMOJI['mine']}\n\n"
            f"📝 <b>Формат:</b> <code>мины [сумма] [бомбы 1-5]</code>\n\n"
            f"<b>📊 Правила (как в gmines):</b>\n"
            f"┌ Поле 5x5 (25 клеток)\n"
            f"├ Выбери количество бомб (1-5)\n"
            f"├ Открывай клетки с алмазами 💎\n"
            f"├ Попади на бомбу 💣 — проигрыш\n"
            f"├ Множитель растёт с каждой открытой клеткой\n"
            f"└ Можешь забрать выигрыш в любой момент\n\n"
            f"💰 <b>Множители для 1 бомбы:</b> x1.05 → x1000\n"
            f"<i>Пример: <code>мины 1000 3</code></i>"
        )
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
    
    elif data == 'football_info':
        text = (
            f"{EMOJI['football']} <b>ФУТБОЛ</b> {EMOJI['football']}\n\n"
            f"📝 <b>Формат:</b> <code>футбол [сумма] [гол/мимо]</code>\n\n"
            f"<b>📊 Правила:</b>\n"
            f"┌ Бот отправляет эмодзи мяча ⚽\n"
            f"├ Результат может быть: ГОЛ или МИМО\n"
            f"└ Угадай правильно — получишь x2.1\n\n"
            f"💰 <b>Выигрыш:</b> x2.1\n"
            f"<i>Пример: <code>футбол 100 гол</code></i>"
        )
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
    
    elif data == 'roulette_info':
        text = (
            f"{EMOJI['gun']} <b>РУССКАЯ РУЛЕТКА</b> {EMOJI['gun']}\n\n"
            f"📝 <b>Формат:</b> <code>рулетка [сумма]</code>\n\n"
            f"<b>📊 Правила:</b>\n"
            f"┌ В барабане 6 патронов, 1 боевой\n"
            f"├ Крутишь барабан и стреляешь\n"
            f"├ Попал — проигрыш ставки\n"
            f"├ Промах — выигрыш x1.6\n"
            f"└ Можно забрать выигрыш в любой момент\n\n"
            f"💰 <b>Выигрыш:</b> x1.6\n"
            f"<i>Пример: <code>рулетка 1000</code></i>"
        )
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
    
    elif data == 'crash_info':
        text = (
            f"{EMOJI['rocket']} <b>ИГРА КРАШ</b> {EMOJI['rocket']}\n\n"
            f"📝 <b>Формат:</b> <code>краш [сумма] [икс]</code>\n\n"
            f"<b>📊 Правила:</b>\n"
            f"┌ Ты выбираешь желаемый множитель (икс)\n"
            f"├ Чем выше икс — тем меньше шанс на победу\n"
            f"├ Если ракета долетит до твоего икса — ты выигрываешь\n"
            f"├ Если ракета взорвётся раньше — ты проигрываешь\n"
            f"└ Можешь забрать выигрыш ДО запуска ракеты!\n\n"
            f"📈 <b>Шансы:</b>\n"
            f"┌ x2 — ~35%\n"
            f"├ x5 — ~9%\n"
            f"├ x10 — ~3%\n"
            f"└ x100 — ~0.1%\n\n"
            f"<i>Пример: <code>краш 1000 2</code></i>"
        )
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
    
    elif data == 'games50_info':
        text = f"{EMOJI['coinflip']} <b>ИГРЫ 50/50 (x2.0)</b> {EMOJI['coinflip']}\n\n"
        for g in GAMES_50:
            text += f"<b>{GAMES_50[g]['emoji']} {GAMES_50[g]['name']}:</b> {GAMES_50[g]['desc']}\n"
        text += f"\n📝 <b>Формат:</b> <code>[игра] [сумма] [выбор]</code>\n"
        text += f"<i>Пример: <code>монетка 100 орёл</code></i>"
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
    
    elif data == 'top15':
        users = db.get_top_users(15)
        
        if not users:
            await query.edit_message_text(f"{EMOJI['stats']} Нет игроков в топе!", parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
            return
        
        text = f"{EMOJI['top']} <b>ТОП 15 БОГАТЫХ ИГРОКОВ</b> {EMOJI['top']}\n\n"
        medals = ["🥇", "🥈", "🥉", "📌", "📌", "📌", "📌", "📌", "📌", "📌", "📌", "📌", "📌", "📌", "📌"]
        
        for i, (uid, data_user) in enumerate(users):
            name = data_user.get('first_name', f'Игрок{uid[:6]}')
            balance = data_user.get('balance', 0)
            medal = medals[i] if i < len(medals) else "📍"
            text += f"{medal} <b>{i+1}.</b> {name[:20]} — {EMOJI['coin']} {format_number(balance)} MS\n"
        
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_keyboard(user.id))
    
    # ===== ЧЕКИ =====
    elif data == 'cheques_menu':
        await query.edit_message_text(
            f"{EMOJI['cheque']} <b>СИСТЕМА ЧЕКОВ</b> {EMOJI['cheque']}\n\n"
            f"📝 <b>Чеки позволяют:</b>\n"
            f"┌ Создавать подарочные сертификаты\n"
            f"├ Делиться MS с друзьями\n"
            f"└ Активировать бонусы по коду\n\n"
            f"Выберите действие:",
            parse_mode='HTML',
            reply_markup=get_cheques_keyboard()
        )
    
    elif data == 'create_cheque':
        await query.edit_message_text(
            f"{EMOJI['cheque']} <b>СОЗДАНИЕ ЧЕКА</b> {EMOJI['cheque']}\n\n"
            f"📝 <b>Формат:</b> <code>/createcheque [сумма] [активации]</code>\n\n"
            f"🎯 <b>Пример:</b> <code>/createcheque 1000 5</code>\n\n"
            f"💰 <b>Стоимость:</b> сумма × активации",
            parse_mode='HTML',
            reply_markup=get_cheques_keyboard()
        )
    
    elif data == 'activate_cheque':
        await query.edit_message_text(
            f"{EMOJI['cheque']} <b>АКТИВАЦИЯ ЧЕКА</b> {EMOJI['cheque']}\n\n"
            f"📝 <b>Формат:</b> <code>/usecheque [код]</code>\n\n"
            f"🎯 <b>Пример:</b> <code>/usecheque abc123xyz</code>",
            parse_mode='HTML',
            reply_markup=get_cheques_keyboard()
        )
    
    elif data == 'my_cheques':
        await my_cheques_callback(update, context)
    
    elif data == 'cheque_stats':
        await cheque_stats_callback(update, context)
    
    elif data == 'activate_promo_menu':
        await query.edit_message_text(
            f"{EMOJI['promo']} <b>АКТИВАЦИЯ ПРОМОКОДА</b> {EMOJI['promo']}\n\n"
            f"📝 <b>Как активировать?</b>\n"
            f"┌ Просто отправьте код промокода в чат!\n"
            f"└ Пример: <code>SUPER2024</code>\n\n"
            f"💡 <i>Промокоды дают бонусные MS!</i>",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    
    # ===== АДМИН ПАНЕЛЬ =====
    elif data == 'admin_panel':
        if not is_admin_session(user.id):
            await query.edit_message_text(f"{EMOJI['lose']} Нет прав! Войдите через /admin", parse_mode='HTML')
            return
        await query.edit_message_text(
            f"{EMOJI['admin']} <b>АДМИН ПАНЕЛЬ</b> {EMOJI['admin']}\n\n"
            f"👑 Добро пожаловать, {user.first_name}!\n"
            f"Выберите действие:",
            parse_mode='HTML',
            reply_markup=get_admin_panel_keyboard()
        )
    
    elif data == 'admin_logout':
        if str(user.id) in admin_sessions:
            del admin_sessions[str(user.id)]
        await query.edit_message_text(
            f"{EMOJI['cancel']} Вы вышли из админ-панели.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    
    elif data == 'back_to_main':
        await query.edit_message_text(
            f"{EMOJI['star']} <b>ГЛАВНОЕ МЕНЮ</b> {EMOJI['star']}\n\n"
            f"👤 {user.first_name}\n"
            f"💰 Баланс: {format_number(db.get_balance(user.id))} MS",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user.id)
        )
    
    # ===== АДМИН КНОПКИ =====
    elif data == 'admin_give':
        await query.edit_message_text(
            f"{EMOJI['admin']} <b>Выдача MS</b>\n\n"
            f"Используй команду:\n"
            f"<code>/give @username СУММА</code>\n\n"
            f"Пример: <code>/give @username 5000</code>",
            parse_mode='HTML',
            reply_markup=get_admin_panel_keyboard()
        )
    elif data == 'admin_take':
        await query.edit_message_text(
            f"{EMOJI['admin']} <b>Забор MS</b>\n\n"
            f"Используй команду:\n"
            f"<code>/take @username СУММА</code>\n\n"
            f"Пример: <code>/take @username 5000</code>",
            parse_mode='HTML',
            reply_markup=get_admin_panel_keyboard()
        )
    elif data == 'admin_create_promo':
        await query.edit_message_text(
            f"{EMOJI['admin']} <b>Создать промокод</b>\n\n"
            f"<code>/createpromo НАЗВАНИЕ АКТИВАЦИИ СУММА</code>\n\n"
            f"Пример: <code>/createpromo SUPER2024 100 500</code>",
            parse_mode='HTML',
            reply_markup=get_admin_panel_keyboard()
        )
    elif data == 'admin_list_promos':
        await admin_list_promo(update, context)
    elif data == 'admin_ban':
        await query.edit_message_text(
            f"{EMOJI['admin']} <b>Бан игрока</b>\n\n"
            f"Используй команду:\n"
            f"<code>/ban @username</code>\n\n"
            f"Пример: <code>/ban @username</code>",
            parse_mode='HTML',
            reply_markup=get_admin_panel_keyboard()
        )
    elif data == 'admin_unban':
        await query.edit_message_text(
            f"{EMOJI['admin']} <b>Разбан игрока</b>\n\n"
            f"Используй команду:\n"
            f"<code>/unban @username</code>\n\n"
            f"Пример: <code>/unban @username</code>",
            parse_mode='HTML',
            reply_markup=get_admin_panel_keyboard()
        )
    elif data == 'admin_stats':
        total_users = db.get_registered_count()
        banned_count = len(db.data["banned"])
        total_coins = sum(u.get('balance', 0) for u in db.data["users"].values())
        total_games = sum(u.get('games_played', 0) for u in db.data["users"].values())
        total_refs = sum(len(u.get('referrals', [])) for u in db.data["users"].values())
        
        text = (
            f"{EMOJI['stats']} <b>СТАТИСТИКА БОТА</b>\n\n"
            f"👥 Игроков: {total_users}\n"
            f"{EMOJI['ban']} В бане: {banned_count}\n"
            f"{EMOJI['coin']} Всего MS: {format_number(total_coins)}\n"
            f"💰 Средний баланс: {format_number(int(total_coins / max(1, total_users)))}\n\n"
            f"🎮 Игр сыграно: {total_games}\n"
            f"🔗 Всего рефералов: {total_refs}\n\n"
            f"🔥 Версия: {BOT_VERSION}"
        )
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_admin_panel_keyboard())
    elif data == 'admin_bans':
        if not db.data["banned"]:
            await query.edit_message_text(f"{EMOJI['unban']} Нет забаненных игроков.", parse_mode='HTML', reply_markup=get_admin_panel_keyboard())
            return
        
        text = f"{EMOJI['ban']} <b>ЗАБАНЕННЫЕ ИГРОКИ</b>\n\n"
        for uid in db.data["banned"]:
            user_data = db.get_user_info(uid)
            if user_data:
                name = user_data.get('first_name', f'ID: {uid}')
                text += f"• {name}\n"
        
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_admin_panel_keyboard())
    
    # ===== ИГРЫ В КОСТИ =====
    elif data.startswith('dice_join_'):
        game_id = data.replace('dice_join_', '')
        await dice_join(update, context, game_id)
    elif data.startswith('dice_cancel_'):
        game_id = data.replace('dice_cancel_', '')
        await dice_cancel(update, context, game_id)
    elif data.startswith('dice_cancel_game_'):
        game_id = data.replace('dice_cancel_game_', '')
        await dice_cancel_game(update, context, game_id)
    elif data.startswith('dice_start_'):
        game_id = data.replace('dice_start_', '')
        await dice_start(update, context, game_id)
    
    # ===== МИНЫ =====
    elif data.startswith('mines_reveal_'):
        parts = data.split('_')
        game_id = parts[2]
        cell = int(parts[3])
        await mines_reveal(update, context, game_id, cell)
    elif data.startswith('mines_cashout_'):
        game_id = data.replace('mines_cashout_', '')
        await mines_cashout(update, context, game_id)
    elif data.startswith('mines_noop_'):
        await mines_noop(update, context)
    
    # ===== РУССКАЯ РУЛЕТКА =====
    elif data.startswith('roulette_shoot_'):
        game_id = data.replace('roulette_shoot_', '')
        await roulette_shoot(update, context, game_id)
    elif data.startswith('roulette_cancel_'):
        game_id = data.replace('roulette_cancel_', '')
        await roulette_cancel(update, context, game_id)
    
    # ===== КРАШ =====
    elif data.startswith('crash_launch_'):
        game_id = data.replace('crash_launch_', '')
        await crash_launch(update, context, game_id)
    elif data.startswith('crash_cashout_'):
        game_id = data.replace('crash_cashout_', '')
        await crash_cashout(update, context, game_id)
    elif data.startswith('crash_cancel_'):
        game_id = data.replace('crash_cancel_', '')
        await crash_cancel(update, context, game_id)

# ========== ТЕКСТОВЫЙ ХЕНДЛЕР ==========
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_banned(user.id):
        await update.message.reply_text(f"{EMOJI['ban']} Вы заблокированы!", parse_mode='HTML')
        return
    
    text = update.message.text.strip()
    text_lower = text.lower()
    
    # Проверка на промокод
    code_to_check = text.upper()
    if (not text.startswith('/') and not text.startswith('http') and 
        len(code_to_check) <= 30 and code_to_check.isalnum()):
        result = db.activate_promocode(user.id, code_to_check)
        if result["success"]:
            new_balance = db.get_balance(user.id)
            await update.message.reply_text(
                f"{EMOJI['party']} <b>ПРОМОКОД АКТИВИРОВАН!</b> {EMOJI['party']}\n\n"
                f"{EMOJI['coin']} <b>+{format_number(result['amount'])} MS</b>\n\n"
                f"💰 <b>Ваш баланс:</b> {format_number(new_balance)} MS",
                parse_mode='HTML',
                reply_markup=get_main_keyboard(user.id)
            )
            return
    
    # Обработка команды "Дать" (перевод)
    if text_lower.startswith('дать '):
        await give_command(update, context)
        return
    
    # Обычные команды
    if text_lower in ['помощь', 'help', 'хелп']:
        await help_command(update, context)
    elif text_lower in ['топ', 'top', 'топ15', 'top15', 'топ 15']:
        await top_command(update, context)
    elif text_lower in ['баланс', 'balance', 'б', 'b']:
        await balance_command(update, context)
    elif text_lower in ['бонус', 'bonus']:
        await bonus_command(update, context)
    elif text_lower in ['профиль', 'profile']:
        await profile_command(update, context)
    elif text_lower in ['рефералы', 'referrals']:
        await referrals_command(update, context)
    elif text_lower in ['ссылка', 'referral_link']:
        await referral_link_command(update, context)
    elif text_lower.startswith('дартс'):
        await darts_game(update, context)
    elif text_lower.startswith('кубик'):
        await dice_game(update, context)
    elif text_lower.startswith('кости'):
        await create_dice_game(update, context)
    elif text_lower.startswith('мины'):
        await mines_game(update, context)
    elif text_lower.startswith('футбол'):
        await football_game(update, context)
    elif text_lower.startswith('рулетка'):
        await russian_roulette_game(update, context)
    elif text_lower.startswith('краш'):
        await crash_game_command(update, context)
    elif text_lower.startswith('монетка'):
        await game50_handler(update, context, 'монетка')
    elif text_lower.startswith('дуэль'):
        await game50_handler(update, context, 'дуэль')
    elif text_lower.startswith('гонки'):
        await game50_handler(update, context, 'гонки')
    elif text_lower.startswith('карта'):
        await game50_handler(update, context, 'карта')
    elif text_lower.startswith('кристалл'):
        await game50_handler(update, context, 'кристалл')

# ========== ЗАПУСК ==========
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("bonus", bonus_command))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("referral_link", referral_link_command))
    application.add_handler(CommandHandler("referrals", referrals_command))
    
    # Чеки
    application.add_handler(CommandHandler("createcheque", create_cheque_command))
    application.add_handler(CommandHandler("usecheque", use_cheque_command))
    
    # Админ команды
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("admin_logout", admin_logout))
    application.add_handler(CommandHandler("give", admin_give))
    application.add_handler(CommandHandler("take", admin_take))
    application.add_handler(CommandHandler("createpromo", admin_create_promo))
    application.add_handler(CommandHandler("delpromo", admin_del_promo))
    application.add_handler(CommandHandler("listpromo", admin_list_promo))
    application.add_handler(CommandHandler("ban", admin_ban))
    application.add_handler(CommandHandler("unban", admin_unban))
    application.add_handler(CommandHandler("admin_stats", admin_stats))
    application.add_handler(CommandHandler("bans_list", bans_list))
    application.add_handler(CommandHandler("broadcast", broadcast))
    
    # Обработчики
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("=" * 50)
    print(f"🤖 {BOT_NAME} v{BOT_VERSION} ЗАПУЩЕН!")
    print("=" * 50)
    print(f"👑 Админ пароль: {ADMIN_PASSWORD}")
    print(f"💎 Валюта: MS")
    print(f"🎯 Дартс: x2.05 / x3.1")
    print(f"🧾 Система чеков: активна (1 раз на пользователя)")
    print(f"🎫 Система промокодов: активна (1 раз на пользователя)")
    print(f"🎲 Кости: мультиплеер (2-8 игроков)")
    print(f"🎲 Кубик: >3 / <3 (x2.1)")
    print(f"💣 Мины: как в @gminesbot (x1.05 до x1000 для 1 бомбы)")
    print(f"⚽ Футбол: гол/мимо (x2.1)")
    print(f"🔫 Русская рулетка: x1.6 (1/6 шанс на смерть)")
    print(f"🚀 Краш: как в gmines, чем выше икс, тем меньше шанс!")
    print(f"🎮 5 игр 50/50: x2.0")
    print(f"🎁 Бонус: 2500 MS в час")
    print(f"🔗 Реферальная система: +1000 MS за друга")
    print(f"🆘 Поддержка: {SUPPORT_USERNAME}")
    print(f"📢 Канал: {CHANNEL_USERNAME}")
    print(f"💬 Чат: {CHAT_USERNAME}")
    print("=" * 50)
    print("📝 СУММЫ С СУФФИКСАМИ (РАБОТАЮТ РУССКИЕ ТОЖЕ):")
    print("┌ к / K = тысяча")
    print("├ м / M = миллион")
    print("├ б / B = миллиард")
    print("├ т / T = триллион")
    print("├ кк = миллион")
    print("├ мм = триллион")
    print("├ бб = квинтиллион")
    print("├ тт = септиллион")
    print("├ qa / Qa = квадриллион")
    print("├ qi / Qi = квинтиллион")
    print("├ sx / Sx = секстиллион")
    print("├ sp / Sp = септиллион")
    print("├ o / O = октиллион")
    print("├ n / N = нониллион")
    print("├ d / D = дециллион")
    print("└ all = весь баланс")
    print("=" * 50)
    print("💸 КОМАНДА ДЛЯ ПЕРЕВОДОВ:")
    print("└ Дать [сумма] [@username]  (например: Дать 1000 @username)")
    print("=" * 50)
    print("⚠️ Админ панель скрыта! Вход: /admin ПАРОЛЬ")
    print("=" * 50)
    print("🛡️ ЗАЩИТА ОТ ЧУЖИХ КНОПОК: активна!")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()