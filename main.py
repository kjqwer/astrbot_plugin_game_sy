from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import *
from astrbot.api.event import MessageChain
import random
import asyncio
from typing import Dict, List, Set

@register("huanju", "kjqwdw", "欢乐21点游戏插件", "1.0.0", "https://github.com/kjqwer/astrbot_plugin_game_sy")  
class HuanJuPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        self.game_rooms: Dict[str, Dict] = {}
        # 21点只需要一副牌，不需要大小王
        self.cards = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        self.suits = ['♠', '♥', '♣', '♦']
        
    @filter.command_group("hj")
    def huanju(self):
        '''欢乐21点指令组'''
        pass

    @huanju.command("create")
    async def create_game(self, event: AstrMessageEvent):
        '''创建一个21点游戏房间'''
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令！")
            return
            
        if group_id in self.game_rooms:
            yield event.plain_result("当前群已存在牌局！")
            return
            
        self.game_rooms[group_id] = {
            "players": set(),
            "status": "waiting",  # waiting, playing
            "current_cards": {},  # 玩家手牌
            "creator": event.get_sender_id(),
            "current_player": None,  # 当前回合玩家
            "player_status": {},  # 玩家状态（要牌/停牌）
            "points": {}  # 玩家点数
        }
        
        yield event.plain_result("21点游戏房间创建成功！请使用 /hj join 加入游戏，2-4人即可开始。")

    @huanju.command("join")
    async def join_game(self, event: AstrMessageEvent):
        '''加入游戏'''
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令！")
            return
            
        if group_id not in self.game_rooms:
            yield event.plain_result("当前群未创建牌局！请使用 /hj create 创建")
            return
            
        room = self.game_rooms[group_id]
        if room["status"] != "waiting":
            yield event.plain_result("牌局已经开始，无法加入！")
            return
            
        player_id = event.get_sender_id()
        if player_id in room["players"]:
            yield event.plain_result("你已经在牌局中了！")
            return
            
        if len(room["players"]) >= 4:
            yield event.plain_result("房间已满！")
            return
            
        room["players"].add(player_id)
        yield event.plain_result(f"加入成功！当前玩家数: {len(room['players'])}/4")
        
        if len(room["players"]) >= 2:
            yield event.plain_result("人数已达2人，可以使用 /hj start 开始游戏")

    @huanju.command("start")
    async def start_game(self, event: AstrMessageEvent):
        '''开始游戏'''
        group_id = event.message_obj.group_id
        if not group_id or group_id not in self.game_rooms:
            yield event.plain_result("当前群没有创建的牌局！")
            return
            
        room = self.game_rooms[group_id]
        if room["status"] != "waiting":
            yield event.plain_result("游戏已经开始！")
            return
            
        if len(room["players"]) < 2:
            yield event.plain_result("人数不足，至少需要2人才能开始游戏！")
            return
            
        if event.get_sender_id() != room["creator"]:
            yield event.plain_result("只有房主才能开始游戏！")
            return
            
        await self.init_game(event, group_id)

    @huanju.command("hit")
    async def hit(self, event: AstrMessageEvent):
        '''要牌'''
        group_id = event.message_obj.group_id
        if not group_id or group_id not in self.game_rooms:
            yield event.plain_result("当前群没有进行中的牌局！")
            return
            
        room = self.game_rooms[group_id]
        player_id = event.get_sender_id()
        
        if room["status"] != "playing" or player_id != room["current_player"]:
            yield event.plain_result("还没轮到你的回合！")
            return
            
        if room["player_status"].get(player_id) == "stand":
            yield event.plain_result("你已经选择停牌了！")
            return
            
        # 发一张牌
        card = self.draw_card(room)
        room["current_cards"][player_id].append(card)
        points = self.calculate_points(room["current_cards"][player_id])
        room["points"][player_id] = points
        
        cards_str = " ".join(room["current_cards"][player_id])
        await self.context.send_message(
            event.unified_msg_origin,
            MessageChain().at(player_id).message(f"\n你要了一张牌: {card}\n当前手牌: {cards_str}\n当前点数: {points}")
        )
        
        if points > 21:
            room["player_status"][player_id] = "bust"
            yield event.plain_result(f"爆牌了！")
            await self.next_player(event, group_id)
        else:
            yield event.plain_result(f"请选择 /hj hit 继续要牌 或 /hj stand 停牌")

    @huanju.command("stand")
    async def stand(self, event: AstrMessageEvent):
        '''停牌'''
        group_id = event.message_obj.group_id
        if not group_id or group_id not in self.game_rooms:
            yield event.plain_result("当前群没有进行中的牌局！")
            return
            
        room = self.game_rooms[group_id]
        player_id = event.get_sender_id()
        
        if room["status"] != "playing" or player_id != room["current_player"]:
            yield event.plain_result("还没轮到你的回合！")
            return
            
        room["player_status"][player_id] = "stand"
        points = room["points"][player_id]
        yield event.plain_result(f"你选择停牌，最终点数: {points}")
        await self.next_player(event, group_id)

    async def init_game(self, event: AstrMessageEvent, group_id: str):
        '''初始化游戏'''
        room = self.game_rooms[group_id]
        room["status"] = "playing"
        room["current_cards"] = {player_id: [] for player_id in room["players"]}
        room["player_status"] = {player_id: "playing" for player_id in room["players"]}
        room["points"] = {player_id: 0 for player_id in room["players"]}
        
        # 生成一副牌
        self.deck = []
        for suit in self.suits:
            for card in self.cards:
                self.deck.append(f"{suit}{card}")
        random.shuffle(self.deck)
        room["deck"] = self.deck
        
        # 每人发两张牌
        for player_id in room["players"]:
            for _ in range(2):
                card = self.draw_card(room)
                room["current_cards"][player_id].append(card)
            points = self.calculate_points(room["current_cards"][player_id])
            room["points"][player_id] = points
            
            cards_str = " ".join(room["current_cards"][player_id])
            await self.context.send_message(
                event.unified_msg_origin,
                MessageChain().at(player_id).message(f"\n你的手牌是: {cards_str}\n当前点数: {points}")
            )
        
        # 设置第一个玩家
        room["current_player"] = list(room["players"])[0]
        yield event.plain_result(f"游戏开始！请 {room['current_player']} 选择 /hj hit 要牌 或 /hj stand 停牌")

    def draw_card(self, room: Dict) -> str:
        '''抽一张牌'''
        return room["deck"].pop()

    def calculate_points(self, cards: List[str]) -> int:
        '''计算点数'''
        points = 0
        ace_count = 0
        
        for card in cards:
            value = card[1:]  # 去掉花色
            if value in ['J', 'Q', 'K']:
                points += 10
            elif value == 'A':
                ace_count += 1
            else:
                points += int(value)
        
        # 处理A的点数
        for _ in range(ace_count):
            if points + 11 <= 21:
                points += 11
            else:
                points += 1
                
        return points

    async def next_player(self, event: AstrMessageEvent, group_id: str):
        '''处理下一个玩家'''
        room = self.game_rooms[group_id]
        players = list(room["players"])
        current_index = players.index(room["current_player"])
        
        # 找下一个未停牌的玩家
        next_player = None
        for i in range(1, len(players)):
            index = (current_index + i) % len(players)
            if room["player_status"][players[index]] == "playing":
                next_player = players[index]
                break
        
        if next_player:
            room["current_player"] = next_player
            yield event.plain_result(f"轮到 {next_player} 的回合，请选择 /hj hit 要牌 或 /hj stand 停牌")
        else:
            # 游戏结束，计算结果
            await self.end_game(event, group_id)

    async def end_game(self, event: AstrMessageEvent, group_id: str):
        '''游戏结束'''
        room = self.game_rooms[group_id]
        
        # 找出未爆牌的最大点数
        max_points = 0
        winners = []
        for player_id, status in room["player_status"].items():
            points = room["points"][player_id]
            if status != "bust" and points <= 21:
                if points > max_points:
                    max_points = points
                    winners = [player_id]
                elif points == max_points:
                    winners.append(player_id)
        
        # 显示结果
        result = "游戏结束！\n"
        for player_id in room["players"]:
            cards_str = " ".join(room["current_cards"][player_id])
            status = "爆牌" if room["player_status"][player_id] == "bust" else f"{room['points'][player_id]}点"
            result += f"{player_id}: {cards_str} ({status})\n"
        
        if winners:
            result += f"\n获胜者: {', '.join(winners)} ({max_points}点)"
        else:
            result += "\n所有人都爆牌了！"
        
        yield event.plain_result(result)
        del self.game_rooms[group_id]

    @huanju.command("help")
    async def show_help(self, event: AstrMessageEvent):
        '''显示帮助信息'''
        help_text = """欢乐21点指令说明：
/hj create - 创建游戏房间
/hj join - 加入游戏
/hj start - 开始游戏（仅房主可用）
/hj hit - 要牌
/hj stand - 停牌
/hj quit - 退出游戏
/hj help - 显示本帮助信息

游戏规则：
1. 2-4人即可开始游戏
2. A可以算1点或11点
3. JQK都算10点
4. 其他牌按面值计算


5. 超过21点爆牌
6. 未爆牌者中点数最大者获胜
"""
        yield event.plain_result(help_text)
