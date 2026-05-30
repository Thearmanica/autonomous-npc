"""
Oyun durumu (state) ve tool function'lar. Turkce destekli.
"""

import json
import os
from typing import Optional

STATE_FILE = "game_state.json"


class GameState:
    def __init__(self):
        self.gold = 100
        self.inventory = {}
        self.active_quests = []
        self.completed_quests = []
        self.load()

    def save(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "gold": self.gold,
                "inventory": self.inventory,
                "active_quests": self.active_quests,
                "completed_quests": self.completed_quests,
            }, f, indent=2, ensure_ascii=False)

    def load(self):
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.gold = data.get("gold", 100)
            self.inventory = data.get("inventory", {})
            self.active_quests = data.get("active_quests", [])
            self.completed_quests = data.get("completed_quests", [])
        except (json.JSONDecodeError, OSError):
            pass

    def reset(self):
        self.gold = 100
        self.inventory = {}
        self.active_quests = []
        self.completed_quests = []
        self.save()

    def summary(self) -> str:
        inv = ", ".join(f"{k} x{v}" for k, v in self.inventory.items()) or "(empty)"
        q = ", ".join(qq["title"] for qq in self.active_quests) or "(none)"
        return f"Gold: {self.gold} | Inventory: {inv} | Quests: {q}"

    def summary_tr(self) -> str:
        inv = ", ".join(f"{k} x{v}" for k, v in self.inventory.items()) or "(bos)"
        q = ", ".join(qq["title"] for qq in self.active_quests) or "(yok)"
        return f"Altin: {self.gold} | Envanter: {inv} | Gorevler: {q}"


state = GameState()


# ====================== Tool Functions ======================
def give_item(item_name: str, quantity: int = 1, price: int = 0) -> dict:
    if price > 0 and state.gold < price:
        return {
            "success": False,
            "reason": f"Player only has {state.gold} gold, cannot afford {price}.",
            "player_state": state.summary_tr(),
        }
    state.gold -= price
    state.inventory[item_name] = state.inventory.get(item_name, 0) + quantity
    state.save()
    return {
        "success": True,
        "message": f"Gave {quantity}x {item_name} to player for {price} gold.",
        "player_state": state.summary_tr(),
    }


def take_gold(amount: int, reason: str = "") -> dict:
    if state.gold < amount:
        return {
            "success": False,
            "reason": f"Player only has {state.gold} gold.",
            "player_state": state.summary_tr(),
        }
    state.gold -= amount
    state.save()
    return {
        "success": True,
        "message": f"Took {amount} gold from player. Reason: {reason or 'unspecified'}.",
        "player_state": state.summary_tr(),
    }


def give_gold(amount: int, reason: str = "") -> dict:
    state.gold += amount
    state.save()
    return {
        "success": True,
        "message": f"Gave {amount} gold to player. Reason: {reason or 'unspecified'}.",
        "player_state": state.summary_tr(),
    }


def check_inventory() -> dict:
    return {
        "gold": state.gold,
        "inventory": state.inventory,
        "active_quests": [q["title"] for q in state.active_quests],
    }


def offer_quest(quest_id: str, title: str, description: str, reward_gold: int, giver: str) -> dict:
    if any(q["id"] == quest_id for q in state.active_quests):
        return {"success": False, "reason": f"Quest '{quest_id}' is already active."}
    if any(q["id"] == quest_id for q in state.completed_quests):
        return {"success": False, "reason": f"Quest '{quest_id}' is already completed."}
    quest = {
        "id": quest_id, "title": title, "description": description,
        "reward_gold": reward_gold, "giver": giver,
    }
    state.active_quests.append(quest)
    state.save()
    return {
        "success": True,
        "message": f"Quest '{title}' added. Reward: {reward_gold} gold.",
        "player_state": state.summary_tr(),
    }


def complete_quest(quest_id: str) -> dict:
    quest = next((q for q in state.active_quests if q["id"] == quest_id), None)
    if not quest:
        return {"success": False, "reason": f"No active quest with id '{quest_id}'."}
    state.active_quests.remove(quest)
    state.completed_quests.append(quest)
    state.gold += quest["reward_gold"]
    state.save()
    return {
        "success": True,
        "message": f"Quest '{quest['title']}' completed. Player got {quest['reward_gold']} gold.",
        "player_state": state.summary_tr(),
    }


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "give_item",
            "description": "Give an item to the player. price='0' for free gifts. NUMBERS AS STRINGS (e.g. '50', '1').",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "snake_case item name, e.g. 'demir_kilic', 'iyilesme_iksiri'."},
                    "quantity": {"type": "string", "description": "Number as string, e.g. '1'"},
                    "price": {"type": "string", "description": "Gold cost as string, e.g. '50' or '0'"},
                },
                "required": ["item_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_gold",
            "description": "Take gold from player (fine, bribe). Amount as STRING.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "string", "description": "Number as string"},
                    "reason": {"type": "string"},
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "give_gold",
            "description": "Give gold to player (gift, refund). Amount as STRING.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "string", "description": "Number as string"},
                    "reason": {"type": "string"},
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_inventory",
            "description": "Look at what the player has. Use before completing quests, or when player asks what they own.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "offer_quest",
            "description": "Offer a quest. quest_id should be snake_case. reward_gold as STRING.",
            "parameters": {
                "type": "object",
                "properties": {
                    "quest_id": {"type": "string"},
                    "title": {"type": "string", "description": "Turkish quest title."},
                    "description": {"type": "string", "description": "Turkish 1-2 sentence task description."},
                    "reward_gold": {"type": "string", "description": "Number as string"},
                    "giver": {"type": "string"},
                },
                "required": ["quest_id", "title", "description", "reward_gold", "giver"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_quest",
            "description": "Mark a quest complete. ONLY call if proof item is in player inventory.",
            "parameters": {
                "type": "object",
                "properties": {"quest_id": {"type": "string"}},
                "required": ["quest_id"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "give_item": give_item, "take_gold": take_gold, "give_gold": give_gold,
    "check_inventory": check_inventory, "offer_quest": offer_quest, "complete_quest": complete_quest,
}


def _coerce_int(value, default=0):
    """LLM bazen integer'i string olarak yolluyor. Zorla int'e cevir."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            try:
                return int(float(value))
            except ValueError:
                return default
    if isinstance(value, float):
        return int(value)
    return default


def _normalize_args(name: str, args: dict) -> dict:
    """Tool argumanlarini Python tipi olarak normalize et."""
    args = dict(args)  # kopya
    int_fields_per_tool = {
        "give_item": ["quantity", "price"],
        "take_gold": ["amount"],
        "give_gold": ["amount"],
        "offer_quest": ["reward_gold"],
    }
    for field in int_fields_per_tool.get(name, []):
        if field in args:
            args[field] = _coerce_int(args[field], default=0)
    return args


def execute_tool(name: str, args: dict) -> dict:
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return {"success": False, "reason": f"Unknown tool: {name}"}
    try:
        normalized = _normalize_args(name, args)
        return fn(**normalized)
    except TypeError as e:
        return {"success": False, "reason": f"Bad arguments for {name}: {e}"}
    except Exception as e:
        return {"success": False, "reason": f"Tool error: {e}"}
